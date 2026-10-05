import pytest

from app.tests.conftest import auth_header, register

EMPTY_PROFILE = {
    "weight_kg": None,
    "birth_year": None,
    "sex": None,
    "max_heart_rate": None,
    "resting_heart_rate": None,
}
FULL_PROFILE = {
    "weight_kg": 72.5,
    "birth_year": 1988,
    "sex": "female",
    "max_heart_rate": 186,
    "resting_heart_rate": 52,
}


def test_profile_requires_login(client):
    assert client.get("/api/v1/me/profile").status_code == 401
    assert client.put("/api/v1/me/profile", json=FULL_PROFILE).status_code == 401


def test_profile_is_empty_until_saved(client):
    tokens = register(client)

    response = client.get("/api/v1/me/profile", headers=auth_header(tokens))

    assert response.status_code == 200
    assert response.json() == EMPTY_PROFILE


def test_profile_can_be_saved_and_read(client):
    headers = auth_header(register(client))

    saved = client.put("/api/v1/me/profile", json=FULL_PROFILE, headers=headers)

    assert saved.status_code == 200
    assert saved.json() == FULL_PROFILE
    assert client.get("/api/v1/me/profile", headers=headers).json() == FULL_PROFILE


def test_put_replaces_the_whole_profile(client):
    headers = auth_header(register(client))
    client.put("/api/v1/me/profile", json=FULL_PROFILE, headers=headers)

    client.put("/api/v1/me/profile", json={"weight_kg": 70}, headers=headers)

    assert client.get("/api/v1/me/profile", headers=headers).json() == {
        **EMPTY_PROFILE,
        "weight_kg": 70,
    }


@pytest.mark.parametrize("sex", ["female", "male", "trans", "undisclosed", None])
def test_profile_accepts_every_sex_option(client, sex):
    headers = auth_header(register(client))

    saved = client.put("/api/v1/me/profile", json={"sex": sex}, headers=headers)

    assert saved.status_code == 200
    assert saved.json()["sex"] == sex


def test_profile_is_private_to_its_owner(client):
    anna = auth_header(register(client))
    bea = auth_header(register(client, email="bea@example.org", display_name="Bea"))
    client.put("/api/v1/me/profile", json=FULL_PROFILE, headers=anna)

    assert client.get("/api/v1/me/profile", headers=bea).json() == EMPTY_PROFILE
    lookup = client.get("/api/v1/users/lookup", params={"email": "anna@example.org"}, headers=bea)
    assert set(lookup.json()) == {"id", "display_name"}


@pytest.mark.parametrize(
    "payload",
    [
        {"weight_kg": 5},
        {"weight_kg": 500},
        {"birth_year": 1800},
        {"birth_year": 3000},
        {"sex": "unknown"},
        {"max_heart_rate": 20},
        {"resting_heart_rate": 300},
    ],
)
def test_profile_validates_ranges(client, payload):
    headers = auth_header(register(client))

    assert client.put("/api/v1/me/profile", json=payload, headers=headers).status_code == 422
