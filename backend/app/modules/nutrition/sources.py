"""External food data behind an adapter interface.

Open Food Facts data is licensed under the ODbL: clients must name the source
wherever a food with `source = openfoodfacts` is shown.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx2

MAX_KCAL_PER_100G = 900


@dataclass(frozen=True)
class FoodData:
    barcode: str
    name: str
    brand: str | None = None
    kcal_per_100g: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    sugar_g: float | None = None
    salt_g: float | None = None
    serving_size_g: float | None = None
    image_url: str | None = None


class FoodSourceError(Exception):
    """The external source could not be reached or answered with garbage."""


class FoodSource(Protocol):
    def fetch_by_barcode(self, barcode: str) -> FoodData | None:
        """Return the product, None if the source does not know the barcode."""


class DisabledFoodSource:
    def fetch_by_barcode(self, barcode: str) -> FoodData | None:
        return None


def _number(value, maximum: float) -> float | None:
    """Tolerant conversion: anything that is not a plausible number becomes None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= number <= maximum:
        return None
    return round(number, 2)


def _text(value, max_length: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:max_length]


def parse_openfoodfacts_product(barcode: str, product: dict) -> FoodData | None:
    name = _text(product.get("product_name_de"), 200) or _text(product.get("product_name"), 200)
    if name is None:
        return None
    nutriments = product.get("nutriments")
    if not isinstance(nutriments, dict):
        nutriments = {}
    kcal = _number(nutriments.get("energy-kcal_100g"), MAX_KCAL_PER_100G)
    if kcal is None:
        kilojoule = _number(nutriments.get("energy-kj_100g"), MAX_KCAL_PER_100G * 4.184)
        kcal = round(kilojoule / 4.184, 1) if kilojoule is not None else None
    brand = _text(product.get("brands"), 500)
    image_url = _text(product.get("image_front_small_url"), 500)
    serving = _number(product.get("serving_quantity"), 5000)
    return FoodData(
        barcode=barcode,
        name=name,
        brand=brand.split(",")[0].strip()[:100] if brand else None,
        kcal_per_100g=kcal,
        protein_g=_number(nutriments.get("proteins_100g"), 100),
        carbs_g=_number(nutriments.get("carbohydrates_100g"), 100),
        fat_g=_number(nutriments.get("fat_100g"), 100),
        sugar_g=_number(nutriments.get("sugars_100g"), 100),
        salt_g=_number(nutriments.get("salt_100g"), 100),
        serving_size_g=serving or None,
        image_url=image_url if image_url and image_url.startswith("https://") else None,
    )


class OpenFoodFactsSource:
    FIELDS = "product_name,product_name_de,brands,nutriments,serving_quantity,image_front_small_url"

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        *,
        timeout: float = 5.0,
        transport: httpx2.BaseTransport | None = None,
    ):
        self._client = httpx2.Client(
            base_url=base_url,
            headers={"User-Agent": user_agent},
            timeout=timeout,
            transport=transport,
        )

    def fetch_by_barcode(self, barcode: str) -> FoodData | None:
        try:
            response = self._client.get(
                f"/api/v2/product/{barcode}.json", params={"fields": self.FIELDS}
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            body = response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise FoodSourceError(str(exc)) from exc
        if not isinstance(body, dict) or not isinstance(body.get("product"), dict):
            return None
        return parse_openfoodfacts_product(barcode, body["product"])
