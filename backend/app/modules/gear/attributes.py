"""Extra fields of gear that depend on its kind, e.g. the volume of a backpack.

A gear type can have a `kind`. The kind decides which attributes an item of that
type carries. New kinds and attributes are added here; clients read the
definitions from `GET /gear/meta` and build their forms from them.
"""

from dataclasses import dataclass

from app.core.errors import UnprocessableError


@dataclass(frozen=True)
class AttributeDef:
    key: str
    type: str  # "number" or "choice"
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    options: tuple[str, ...] = ()


KINDS: dict[str, tuple[AttributeDef, ...]] = {
    "backpack": (AttributeDef("volume_l", "number", unit="l", minimum=1, maximum=200),),
    # Stiffness categories of hiking and mountaineering boots.
    "shoes": (AttributeDef("shoe_category", "choice", options=("A", "B", "B/C", "C", "D")),),
}


def _invalid(key: str) -> UnprocessableError:
    return UnprocessableError(f"Invalid value for '{key}'", code="invalid_attribute")


def clean(kind: str | None, values: dict | None) -> dict:
    """The attributes that belong to the kind, validated. Others are dropped, so that
    changing the type of an item does not leave values behind that no longer apply."""
    result = {}
    for definition in KINDS.get(kind or "", ()):
        value = (values or {}).get(definition.key)
        if value is None or value == "":
            continue
        if definition.type == "number":
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise _invalid(definition.key)
            if not definition.minimum <= value <= definition.maximum:
                raise _invalid(definition.key)
            result[definition.key] = value
        else:
            if value not in definition.options:
                raise _invalid(definition.key)
            result[definition.key] = value
    return result
