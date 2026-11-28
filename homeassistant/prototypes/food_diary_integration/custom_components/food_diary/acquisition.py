"""Pure acquisition state helpers for the Food Diary integration.

This module has no Home Assistant dependency so its safety rules can be tested
with the Python standard library.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

_BARCODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{3,63}$")


def normalize_barcode(value: Any) -> str | None:
    """Normalize a scanner value; reject empty, placeholder and unsafe values."""
    if value is None:
        return None
    barcode = str(value).strip()
    if barcode.lower() in {"", "unknown", "unavailable", "none", "null"}:
        return None
    if not _BARCODE_RE.fullmatch(barcode):
        return None
    return barcode


def parse_weight_grams(value: Any, unit: str | None = None) -> float | None:
    """Parse a finite weight and normalize supported units to grams."""
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(weight):
        return None
    normalized_unit = (unit or "g").strip().lower()
    if normalized_unit in {"g", "gram", "grams"}:
        return weight
    if normalized_unit in {"kg", "kilogram", "kilograms"}:
        return weight * 1000
    if normalized_unit in {"mg", "milligram", "milligrams"}:
        return weight / 1000
    return None


@dataclass
class ScanSession:
    """One product waiting to be paired with a weighed portion."""

    barcode: str
    zero_seen: bool
    weight_g: float | None = None
    food: dict[str, Any] | None = None
    status: str = "looking_up"
    error: str | None = None

    def observe_weight(self, weight_g: float | None, zero_threshold_g: float) -> None:
        """Require a zero baseline after the scan before accepting positive weight."""
        if weight_g is None:
            return
        if weight_g <= zero_threshold_g:
            self.zero_seen = True
            self.weight_g = None
            if self.food is not None:
                self.status = "waiting_for_weight"
            return
        if self.zero_seen and weight_g > zero_threshold_g:
            self.weight_g = weight_g
            self.status = "ready" if self.food is not None else "waiting_for_product"

    @property
    def can_save(self) -> bool:
        """Whether the session has both a known product and a valid portion."""
        return (
            self.food is not None
            and self.weight_g is not None
            and self.weight_g > 0
            and self.zero_seen
        )

def parse_openfoodfacts_product(
    payload: Mapping[str, Any], barcode: str
) -> dict[str, Any] | None:
    """Convert an Open Food Facts v2 response into the local food schema.

    Missing nutrient values remain None. Energy is normalized to kcal/100 g.
    """
    if payload.get("status") != 1:
        return None
    product = payload.get("product") or {}
    name = str(product.get("product_name") or "").strip()
    if not name:
        return None
    nutriments = product.get("nutriments") or {}
    energy = nutriments.get("energy-kcal_100g")
    if energy is None and nutriments.get("energy-kj_100g") is not None:
        try:
            energy = float(nutriments["energy-kj_100g"]) / 4.184
        except (TypeError, ValueError):
            energy = None
    nutrients = {
        "energy_kcal": energy,
        "protein_g": nutriments.get("proteins_100g"),
        "carbohydrates_g": nutriments.get("carbohydrates_100g"),
        "sugars_g": nutriments.get("sugars_100g"),
        "fat_g": nutriments.get("fat_100g"),
        "saturated_fat_g": nutriments.get("saturated-fat_100g"),
        "fiber_g": nutriments.get("fiber_100g"),
        "salt_g": nutriments.get("salt_100g"),
    }
    return {
        "name": name,
        "brand": product.get("brands"),
        "barcode": barcode,
        "nutrients_per_100g": nutrients,
        "source": "openfoodfacts",
    }
