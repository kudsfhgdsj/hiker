"""Field types shared by the request schemas of several modules."""

from typing import Annotated

from pydantic import BeforeValidator, StringConstraints


def blank_to_none(value):
    if isinstance(value, str):
        return value.strip() or None
    return value


def optional_text(max_length: int, pattern: str | None = None):
    """Optional text; surrounding whitespace is removed and a blank value becomes null."""
    text = Annotated[str, StringConstraints(max_length=max_length, pattern=pattern)]
    return Annotated[text | None, BeforeValidator(blank_to_none)]


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# A free word to sort things by: tours, planned routes.
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


def unique_tags(tags: list[str]) -> list[str]:
    """The same tag twice says nothing new, whatever its case; the first spelling stays."""
    seen: dict[str, str] = {}
    for tag in tags:
        seen.setdefault(tag.casefold(), tag)
    return list(seen.values())
