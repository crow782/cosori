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
    """Convert Open Food Facts v1/v3 product data to the local food schema.

    The barcode lookup uses current API v3 nutrition data. The legacy full-text
    search endpoint still returns the older flat nutriments structure.
    Missing/invalid values remain None; v3 values are accepted only per 100 g.
    """
    status = payload.get("status")
    success = status == 1 or (
        isinstance(status, str) and status.startswith("success")
    )
    if not success:
        return None
    product = payload.get("product") or {}
    name = str(product.get("product_name") or "").strip()
    if not name:
        return None

    nutriments = product.get("nutriments") or {}
    if not nutriments:
        nutrition = product.get("nutrition") or {}
        aggregate = nutrition.get("aggregated_set") or {}
        if aggregate.get("per") in {"100g", "100 g"}:
            values = aggregate.get("nutrients") or {}

            def v3_value(key: str):
                item = values.get(key)
                if isinstance(item, Mapping):
                    return item.get("value_computed") if item.get("value_computed") is not None else item.get("value")
                return item

            nutriments = {
                "energy-kcal_100g": v3_value("energy-kcal"),
                "energy-kj_100g": v3_value("energy-kj"),
                "proteins_100g": v3_value("proteins"),
                "carbohydrates_100g": v3_value("carbohydrates"),
                "sugars_100g": v3_value("sugars"),
                "fat_100g": v3_value("fat"),
                "saturated-fat_100g": v3_value("saturated-fat"),
                "fiber_100g": v3_value("fiber"),
                "salt_100g": v3_value("salt"),
            }

    energy = nutriments.get("energy-kcal_100g")
    if energy in (None, "") and nutriments.get("energy-kj_100g") not in (None, ""):
        try:
            energy = float(nutriments["energy-kj_100g"]) / 4.184
        except (TypeError, ValueError):
            energy = None

    def optional_number(raw: Any) -> float | None:
        if raw is None or raw == "":
            return None
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number >= 0 else None

    nutrients = {
        "energy_kcal": optional_number(energy),
        "protein_g": optional_number(nutriments.get("proteins_100g")),
        "carbohydrates_g": optional_number(nutriments.get("carbohydrates_100g")),
        "sugars_g": optional_number(nutriments.get("sugars_100g")),
        "fat_g": optional_number(nutriments.get("fat_100g")),
        "saturated_fat_g": optional_number(nutriments.get("saturated-fat_100g")),
        "fiber_g": optional_number(nutriments.get("fiber_100g")),
        "salt_g": optional_number(nutriments.get("salt_100g")),
    }
    return {
        "name": name,
        "brand": product.get("brands"),
        "barcode": barcode or str(product.get("code") or ""),
        "nutrients_per_100g": nutrients,
        "source": "openfoodfacts",
    }


def classify_counter_change(previous: int | None, current: int | None) -> tuple[str, int]:
    """Classify a scan-counter update without treating startup/reset as scans."""
    if current is None:
        return "invalid", 0
    if previous is None:
        return "baseline", 0
    if current < previous:
        return "reset", 0
    increment = current - previous
    return ("increment", increment) if increment else ("unchanged", 0)
