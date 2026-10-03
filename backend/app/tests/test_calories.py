# ruff: noqa: F811 - fixtures are imported from the protocols tests
import pytest

from app.modules.protocols import calories
from app.tests.test_protocols import (  # noqa: F401
    TOURS,
    anna,
    bea,
    cleo,
    create_tour,
    dora,
    gear_item,
    people,
    put,
    revisions,
    share,
)
from app.tests.test_public_links import PUBLIC, create_link, token_of
from app.tests.test_track import garmin_gpx, upload

PROFILE = "/api/v1/me/profile"
# The test track: 1112 m, 100 m of ascent, 10 minutes, average heart rate 136.


def set_profile(client, person, **fields):
    assert client.put(PROFILE, json=fields, headers=person.headers).status_code == 200


def tracked(client, person, **gpx_options):
    return upload(client, person, create_tour(client, person), garmin_gpx(**gpx_options)).json()


def current(client, person, tour):
    return client.get(f"{TOURS}/{tour['id']}", headers=person.headers).json()


# --- Formulas ---


def test_keytel_formulas_for_male_female_and_mean():
    male, _ = calories.heart_rate_kcal(136, 75, 40, "male", 10)
    female, _ = calories.heart_rate_kcal(136, 75, 40, "female", 10)

    # (-55.0969 + 0.6309·136 + 0.1988·75 + 0.2017·40) / 4.184 = 12.831 kcal/min
    assert male == pytest.approx(128.3, abs=0.05)
    # (-20.4022 + 0.4472·136 − 0.1263·75 + 0.074·40) / 4.184 = 8.103 kcal/min
    assert female == pytest.approx(81.0, abs=0.05)
    for sex in ("trans", "undisclosed", None):
        value, formula = calories.heart_rate_kcal(136, 75, 40, sex, 10)
        assert value == pytest.approx((male + female) / 2)
        assert formula == "mean"
    assert calories.heart_rate_kcal(30, 75, 20, "male", 10)[0] == 0.0


def test_acsm_walking_formula():
    # VO2 = 0.1·1112 + 1.8·100 + 3.5·10 = 326.2 ml/kg; · 84 kg / 1000 · 5 kcal
    assert calories.acsm_walking_kcal(1112, 100, 10, 84) == pytest.approx(137.0, abs=0.05)
    assert calories.acsm_walking_kcal(0, 0, 60, 70) == pytest.approx(73.5)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"weight_kg": None}, "no_profile"),
        ({"stats": None}, "no_track"),
        ({"stats": {"distance_m": 0}}, "no_track"),
        ({"stats": {"distance_m": 1000}, "tour_minutes": None}, "no_duration"),
    ],
)
def test_estimate_gives_a_reason_when_it_is_not_possible(changes, reason):
    arguments = {
        "stats": {"distance_m": 1000, "total_time_s": 600},
        "weight_kg": 75,
        "birth_year": 1986,
        "sex": "male",
        "tour_year": 2026,
        "pack_weight_g": 0,
        "tour_minutes": None,
    } | changes

    result = calories.estimate(**arguments)

    assert (result.kcal, result.method, result.reason) == (None, None, reason)


# --- In tours ---


def test_heart_rate_estimate_with_profile(client, anna):
    set_profile(client, anna, weight_kg=75, birth_year=1986, sex="male")

    tour = tracked(client, anna)

    assert tour["calories_burned"] is None
    assert tour["calories_burned_source"] == "estimated"
    assert tour["computed"]["calories_burned"] == 128
    assert tour["calories_estimate"] == {
        "method": "heart_rate",
        "reason": None,
        "parameters": {
            "average_heart_rate": 136,
            "weight_kg": 75.0,
            "age": 40,
            "sex_formula": "male",
            "minutes": 10.0,
        },
    }


@pytest.mark.parametrize(
    ("sex", "formula", "kcal"),
    [
        ("female", "female", 81),
        ("trans", "mean", 105),
        ("undisclosed", "mean", 105),
        (None, "mean", 105),
    ],
)
def test_sex_selects_the_formula(client, anna, sex, formula, kcal):
    set_profile(client, anna, weight_kg=75, birth_year=1986, sex=sex)

    tour = tracked(client, anna)

    assert tour["computed"]["calories_burned"] == kcal
    assert tour["calories_estimate"]["parameters"]["sex_formula"] == formula


def test_walking_estimate_without_heart_rate_uses_body_and_pack_weight(client, anna):
    set_profile(client, anna, weight_kg=75)
    tent = gear_item(client, anna, weight_g=9000)

    tour = tracked(client, anna, with_sensors=False)
    with_pack = put(client, anna, tour, gear=[{"gear_item_id": tent["id"]}]).json()

    assert tour["computed"]["calories_burned"] == 122
    assert tour["calories_estimate"]["method"] == "acsm_walking"
    assert with_pack["computed"]["calories_burned"] == 137
    assert with_pack["calories_estimate"]["parameters"] == {
        "weight_kg": 75.0,
        "pack_weight_kg": 9.0,
        "distance_m": tour["track_stats"]["distance_m"],
        "ascent_m": 100,
        "minutes": 10.0,
    }
    lighter = put(client, anna, with_pack, pack_weight_start_g=4000).json()
    assert lighter["calories_estimate"]["parameters"]["pack_weight_kg"] == 4.0


def test_heart_rate_without_birth_year_falls_back_to_walking(client, anna):
    set_profile(client, anna, weight_kg=75)

    tour = tracked(client, anna)

    assert tour["calories_estimate"]["method"] == "acsm_walking"


def test_track_without_time_uses_the_duration_of_the_tour(client, anna):
    set_profile(client, anna, weight_kg=75)
    tour = tracked(client, anna, with_time=False, with_sensors=False)
    assert tour["calories_estimate"] == {"method": None, "reason": "no_duration", "parameters": {}}
    assert tour["calories_burned_source"] is None

    timed = put(client, anna, tour, duration_minutes=10).json()

    assert timed["computed"]["calories_burned"] == 122
    assert timed["calories_burned_source"] == "estimated"


def test_no_estimate_without_profile_or_track(client, anna):
    without_profile = tracked(client, anna)
    set_profile(client, anna, weight_kg=75)
    without_track = create_tour(client, anna, duration_minutes=60)

    assert without_profile["calories_estimate"]["reason"] == "no_profile"
    assert without_profile["computed"]["calories_burned"] is None
    assert without_profile["calories_burned_source"] is None
    assert without_track["calories_estimate"]["reason"] == "no_track"


def test_manual_value_always_wins_and_can_be_replaced_by_the_estimate(client, anna):
    set_profile(client, anna, weight_kg=75, birth_year=1986, sex="male")
    tour = tracked(client, anna)
    url = f"{TOURS}/{tour['id']}/calories/estimate"

    manual = put(client, anna, tour, calories_burned=900).json()

    assert (manual["calories_burned"], manual["calories_burned_source"]) == (900.0, "manual")
    # The estimate is still reported next to the manual value.
    assert manual["computed"]["calories_burned"] == 128

    response = client.post(url, headers=anna.headers)

    assert response.status_code == 200
    estimated = response.json()
    assert (estimated["calories_burned"], estimated["calories_burned_source"]) == (
        None,
        "estimated",
    )
    assert estimated["version"] == manual["version"] + 1
    assert revisions(client, anna, tour)["items"][0]["change_summary"] == (
        "calories_burned, calories_burned_source"
    )


def test_estimate_endpoint_reports_why_it_cannot_estimate(client, anna, bea):
    tour = put(client, anna, tracked(client, anna), calories_burned=900).json()

    response = client.post(f"{TOURS}/{tour['id']}/calories/estimate", headers=anna.headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_profile"
    assert current(client, anna, tour)["calories_burned"] == 900.0
    assert (
        client.post(f"{TOURS}/{tour['id']}/calories/estimate", headers=bea.headers).status_code
        == 404
    )


def test_changes_of_profile_and_track_change_the_estimate_at_once(client, anna):
    set_profile(client, anna, weight_kg=75, birth_year=1986, sex="male")
    tour = tracked(client, anna)
    version = tour["version"]

    set_profile(client, anna, weight_kg=90, birth_year=1986, sex="male")
    heavier = current(client, anna, tour)
    upload(client, anna, tour, garmin_gpx(count=21))
    longer = current(client, anna, tour)

    # (-55.0969 + 0.6309·136 + 0.1988·90 + 0.2017·40) / 4.184 · 10 = 135.4
    assert heavier["computed"]["calories_burned"] == 135
    # The estimate is derived on reading: a new profile adds no revision.
    assert heavier["version"] == version
    assert longer["calories_estimate"]["parameters"]["minutes"] == 20.0
    assert longer["computed"]["calories_burned"] > 300


def test_edit_users_can_save_a_tour_with_an_estimate(client, db, anna, bea, cleo):
    set_profile(client, anna, weight_kg=75, birth_year=1986, sex="male")
    tour = tracked(client, anna)
    share(db, tour, bea, "edit")
    share(db, tour, cleo, "read")

    seen = current(client, bea, tour)
    response = put(client, bea, seen, title="Von Bea")

    assert response.status_code == 200
    # Shared users see the value but not the profile data behind it.
    for person in (bea, cleo):
        shared = current(client, person, tour)
        assert shared["computed"]["calories_burned"] == 128
        assert shared["calories_burned_source"] == "estimated"
        assert shared["calories_estimate"] is None
        assert "weight_kg" not in str(shared)


def test_estimate_in_export_and_public_view(client, anna):
    set_profile(client, anna, weight_kg=75, birth_year=1986, sex="male")
    tour = tracked(client, anna)
    default = token_of(create_link(client, anna, tour))
    with_health = token_of(create_link(client, anna, tour, show_health_data=True))

    exported = client.get(f"{TOURS}/{tour['id']}/export", headers=anna.headers).json()["tour"]
    hidden = client.get(f"{PUBLIC}/{default}").json()
    shown = client.get(f"{PUBLIC}/{with_health}").json()

    assert (exported["calories_burned"], exported["calories_burned_source"]) == (128.0, "estimated")
    assert (hidden["calories_burned"], hidden["calories_burned_source"]) == (None, None)
    assert (shown["calories_burned"], shown["calories_burned_source"]) == (128.0, "estimated")
    assert "weight_kg" not in str(shown)
