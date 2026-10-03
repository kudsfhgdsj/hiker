"""Estimate of the calories burned on a tour.

A value entered by hand always wins. Without one, the server estimates and marks
the result as `estimated`. The estimate is computed whenever the tour is read,
from the track, the pack weight and the owner's current profile, so a change of
any of them takes effect at once.

Method `heart_rate` (needs heart rate in the track, body weight and birth year):
    Keytel et al. (2005), "Prediction of energy expenditure from heart rate
    monitoring during submaximal exercise", J Sports Sci 23(3).
    male:   kcal/min = (-55.0969 + 0.6309·HR + 0.1988·W + 0.2017·A) / 4.184
    female: kcal/min = (-20.4022 + 0.4472·HR − 0.1263·W + 0.0740·A) / 4.184
    HR = average heart rate (bpm), W = body weight (kg), A = age (years).
    For `trans`, `undisclosed` or no value the mean of both formulas is used.
    The formula is linear in HR, so average heart rate × duration equals the sum
    over all samples.

Method `acsm_walking` (needs a track, body weight and a duration):
    ACSM walking equation (ACSM's Guidelines for Exercise Testing and
    Prescription): VO2 [ml/kg/min] = 0.1·S + 1.8·S·G + 3.5, with speed S in
    m/min and grade G as a fraction. Summed over the tour:
    VO2 [ml/kg] = 0.1·distance_m + 1.8·ascent_m + 3.5·minutes
    kcal = VO2 · (body weight + pack weight) [kg] / 1000 · 5 kcal per litre O2.
    Limits: descent is not counted, the pack counts like body weight, and
    difficult terrain (snow, scree) costs more than the equation assumes.

No estimate: without body weight in the profile (`no_profile`), without a track
(`no_track`) or without any duration (`no_duration`).
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.auth import service as auth_service
from app.modules.protocols.models import Tour
from app.modules.protocols.snapshots import computed_values

KJ_PER_KCAL = 4.184
KCAL_PER_LITRE_O2 = 5.0
ACSM_HORIZONTAL = 0.1
ACSM_VERTICAL = 1.8
ACSM_RESTING = 3.5

HEART_RATE = "heart_rate"
ACSM_WALKING = "acsm_walking"


@dataclass(frozen=True)
class Estimate:
    kcal: float | None = None
    method: str | None = None
    reason: str | None = None
    parameters: dict = field(default_factory=dict)


def _keytel_male(heart_rate: float, weight_kg: float, age: float) -> float:
    return (-55.0969 + 0.6309 * heart_rate + 0.1988 * weight_kg + 0.2017 * age) / KJ_PER_KCAL


def _keytel_female(heart_rate: float, weight_kg: float, age: float) -> float:
    return (-20.4022 + 0.4472 * heart_rate - 0.1263 * weight_kg + 0.0740 * age) / KJ_PER_KCAL


def heart_rate_kcal(
    heart_rate: float, weight_kg: float, age: float, sex: str | None, minutes: float
) -> tuple[float, str]:
    """Calories and the formula used (`male`, `female` or `mean`)."""
    male = _keytel_male(heart_rate, weight_kg, age)
    female = _keytel_female(heart_rate, weight_kg, age)
    if sex in ("male", "female"):
        rate, formula = (male, "male") if sex == "male" else (female, "female")
    else:
        rate, formula = (male + female) / 2, "mean"
    # At a very low heart rate the regression drops below zero.
    return max(0.0, rate) * minutes, formula


def acsm_walking_kcal(
    distance_m: float, ascent_m: float, minutes: float, total_weight_kg: float
) -> float:
    oxygen_ml_per_kg = (
        ACSM_HORIZONTAL * distance_m + ACSM_VERTICAL * ascent_m + ACSM_RESTING * minutes
    )
    return oxygen_ml_per_kg * total_weight_kg / 1000 * KCAL_PER_LITRE_O2


def estimate(
    *,
    stats: dict | None,
    weight_kg: float | None,
    birth_year: int | None,
    sex: str | None,
    tour_year: int,
    pack_weight_g: float,
    tour_minutes: float | None,
) -> Estimate:
    """The estimate for one tour; pure function of its inputs."""
    if not weight_kg:
        return Estimate(reason="no_profile")
    if not stats or not stats.get("distance_m"):
        return Estimate(reason="no_track")
    track_seconds = stats.get("total_time_s")
    minutes = track_seconds / 60 if track_seconds else tour_minutes
    if not minutes:
        return Estimate(reason="no_duration")

    heart_rate = (stats.get("heart_rate") or {}).get("avg")
    if heart_rate and birth_year:
        age = tour_year - birth_year
        kcal, formula = heart_rate_kcal(heart_rate, weight_kg, age, sex, minutes)
        parameters = {
            "average_heart_rate": heart_rate,
            "weight_kg": weight_kg,
            "age": age,
            "sex_formula": formula,
            "minutes": round(minutes, 1),
        }
        return Estimate(kcal=round(kcal), method=HEART_RATE, parameters=parameters)

    pack_kg = pack_weight_g / 1000
    ascent = stats.get("ascent_m") or 0
    kcal = acsm_walking_kcal(stats["distance_m"], ascent, minutes, weight_kg + pack_kg)
    parameters = {
        "weight_kg": weight_kg,
        "pack_weight_kg": round(pack_kg, 1),
        "distance_m": stats["distance_m"],
        "ascent_m": ascent,
        "minutes": round(minutes, 1),
    }
    return Estimate(kcal=round(kcal), method=ACSM_WALKING, parameters=parameters)


def for_tour(db: Session, tour: Tour) -> Estimate:
    """The estimate for a tour with the current profile of its owner."""
    profile = auth_service.get_profile_by_user_id(db, tour.owner_id)
    computed = computed_values(tour)
    pack_weight = tour.pack_weight_start_g
    minutes = tour.duration_minutes
    return estimate(
        stats=tour.track_stats,
        weight_kg=profile.weight_kg if profile else None,
        birth_year=profile.birth_year if profile else None,
        sex=profile.sex if profile else None,
        tour_year=(tour.start_time or utcnow()).year,
        pack_weight_g=pack_weight if pack_weight is not None else computed.pack_weight_start_g,
        tour_minutes=minutes if minutes is not None else computed.duration_minutes,
    )


def effective(tour: Tour, estimated: Estimate) -> tuple[float | None, str | None]:
    """The value to show and where it comes from: a manual value always wins."""
    if tour.calories_burned is not None:
        return tour.calories_burned, "manual"
    if estimated.kcal is not None:
        return estimated.kcal, "estimated"
    return None, None
