"""Unit tests for scanner value parsing and portion gating."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

# Load the pure helper directly: importing the integration package would run
# its Home Assistant-dependent __init__.py, which these tests intentionally avoid.
_MODULE_PATH = Path(__file__).with_name("acquisition.py")
_SPEC = importlib.util.spec_from_file_location("food_diary_acquisition", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

ScanSession = _MODULE.ScanSession
normalize_barcode = _MODULE.normalize_barcode
parse_openfoodfacts_product = _MODULE.parse_openfoodfacts_product
parse_weight_grams = _MODULE.parse_weight_grams
classify_counter_change = _MODULE.classify_counter_change


class BarcodeNormalizationTests(unittest.TestCase):
    def test_strips_whitespace(self):
        self.assertEqual(normalize_barcode("  8017596008299\n"), "8017596008299")

    def test_rejects_empty_and_sensor_placeholders(self):
        for value in (None, "", "unknown", "unavailable", "None"):
            with self.subTest(value=value):
                self.assertIsNone(normalize_barcode(value))

    def test_rejects_control_characters_and_too_short_values(self):
        self.assertIsNone(normalize_barcode("123"))
        self.assertIsNone(normalize_barcode("1234\n456"))


class WeightParsingTests(unittest.TestCase):
    def test_grams(self):
        self.assertEqual(parse_weight_grams("125.5", "g"), 125.5)

    def test_kilograms(self):
        self.assertEqual(parse_weight_grams("0.125", "kg"), 125)

    def test_milligrams(self):
        self.assertEqual(parse_weight_grams("125000", "mg"), 125)

    def test_rejects_non_finite_and_unknown_units(self):
        self.assertIsNone(parse_weight_grams("nan", "g"))
        self.assertIsNone(parse_weight_grams("12", "lb"))


class OpenFoodFactsParserTests(unittest.TestCase):
    def test_preserves_unknown_nutrients_as_none(self):
        product = parse_openfoodfacts_product(
            {
                "status": 1,
                "product": {
                    "product_name": "Plain yogurt",
                    "brands": "Example",
                    "nutriments": {"energy-kcal_100g": "62", "proteins_100g": "4.5"},
                },
            },
            "8017596008299",
        )
        self.assertIsNotNone(product)
        self.assertEqual(product["nutrients_per_100g"]["energy_kcal"], 62.0)
        self.assertEqual(product["nutrients_per_100g"]["protein_g"], 4.5)
        self.assertIsNone(product["nutrients_per_100g"]["fat_g"])

    def test_converts_kj_to_kcal_when_kcal_missing(self):
        product = parse_openfoodfacts_product(
            {"status": 1, "product": {"product_name": "Food", "nutriments": {"energy-kj_100g": 418.4}}},
            "8017596008299",
        )
        self.assertAlmostEqual(product["nutrients_per_100g"]["energy_kcal"], 100)

    def test_parses_v3_aggregated_nutrients(self):
        product = parse_openfoodfacts_product(
            {
                "status": "success",
                "product": {
                    "product_name": "Yogurt",
                    "brands": "Example",
                    "nutrition": {
                        "aggregated_set": {
                            "per": "100g",
                            "nutrients": {
                                "energy-kcal": {"value_computed": 62},
                                "proteins": {"value": 4.5},
                                "fat": {"value_computed": None, "value": 3.2},
                            },
                        }
                    },
                },
            },
            "8017596008299",
        )
        self.assertEqual(product["nutrients_per_100g"]["energy_kcal"], 62)
        self.assertEqual(product["nutrients_per_100g"]["protein_g"], 4.5)
        self.assertEqual(product["nutrients_per_100g"]["fat_g"], 3.2)

    def test_v3_non_100g_values_are_not_misrepresented(self):
        product = parse_openfoodfacts_product(
            {
                "status": "success",
                "product": {
                    "product_name": "Drink",
                    "nutrition": {
                        "aggregated_set": {
                            "per": "100ml",
                            "nutrients": {"energy-kcal": {"value": 42}},
                        }
                    },
                },
            },
            "8017596008299",
        )
        self.assertIsNone(product["nutrients_per_100g"]["energy_kcal"])

    def test_invalid_nutrient_values_remain_unknown(self):
        product = parse_openfoodfacts_product(
            {"status": 1, "product": {"product_name": "Food", "nutriments": {"proteins_100g": "trace", "fat_100g": "-1"}}},
            "8017596008299",
        )
        self.assertIsNone(product["nutrients_per_100g"]["protein_g"])
        self.assertIsNone(product["nutrients_per_100g"]["fat_g"])

    def test_rejects_not_found_or_missing_product_name(self):
        self.assertIsNone(parse_openfoodfacts_product({"status": 0}, "8017596008299"))
        self.assertIsNone(parse_openfoodfacts_product({"status": 1, "product": {}}, "8017596008299"))


class CounterChangeTests(unittest.TestCase):
    def test_initial_value_is_baseline_not_a_scan(self):
        self.assertEqual(classify_counter_change(None, 7), ("baseline", 0))

    def test_single_increment(self):
        self.assertEqual(classify_counter_change(7, 8), ("increment", 1))

    def test_multiple_increment_is_reported_as_burst(self):
        self.assertEqual(classify_counter_change(7, 9), ("increment", 2))

    def test_reset_is_not_a_scan(self):
        self.assertEqual(classify_counter_change(7, 0), ("reset", 0))

    def test_invalid_counter_is_rejected(self):
        self.assertEqual(classify_counter_change(7, None), ("invalid", 0))


class ScanSessionTests(unittest.TestCase):
    def test_positive_weight_before_zero_is_not_accepted(self):
        session = ScanSession("8017596008299", zero_seen=False)
        session.food = {"id": "food-1", "name": "Example"}
        session.observe_weight(125, 2)
        self.assertFalse(session.can_save)
        self.assertIsNone(session.weight_g)

    def test_requires_zero_then_new_positive_stable_weight(self):
        session = ScanSession("8017596008299", zero_seen=False)
        session.food = {"id": "food-1", "name": "Example"}
        session.observe_weight(125, 2)
        session.observe_weight(0, 2)
        self.assertFalse(session.can_save)
        session.observe_weight(126.5, 2)
        self.assertTrue(session.can_save)
        self.assertEqual(session.weight_g, 126.5)

    def test_zero_baseline_at_scan_allows_next_positive_weight(self):
        session = ScanSession("8017596008299", zero_seen=True)
        session.food = {"id": "food-1"}
        session.observe_weight(0, 2)
        session.observe_weight(85, 2)
        self.assertTrue(session.can_save)

    def test_unknown_product_can_keep_weight_pending(self):
        session = ScanSession("8017596008299", zero_seen=True)
        session.observe_weight(100, 2)
        self.assertEqual(session.status, "waiting_for_product")
        self.assertFalse(session.can_save)
        session.food = {"id": "food-1"}
        self.assertTrue(session.can_save)

    def test_unavailable_reading_invalidates_previously_accepted_weight(self):
        session = ScanSession("8017596008299", zero_seen=True)
        session.food = {"id": "food-1"}
        session.observe_weight(125, 2)
        self.assertTrue(session.can_save)

        session.observe_weight(None, 2)

        self.assertFalse(session.can_save)
        self.assertIsNone(session.weight_g)
        self.assertFalse(session.zero_seen)
        self.assertEqual(session.status, "waiting_for_zero")

    def test_negative_reading_does_not_count_as_zero_or_valid_weight(self):
        session = ScanSession("8017596008299", zero_seen=False)
        session.food = {"id": "food-1"}

        session.observe_weight(-0.5, 2)

        self.assertFalse(session.zero_seen)
        self.assertFalse(session.can_save)
        self.assertIsNone(session.weight_g)
        self.assertEqual(session.status, "waiting_for_zero")

    def test_negative_reading_invalidates_an_accepted_weight(self):
        session = ScanSession("8017596008299", zero_seen=True)
        session.food = {"id": "food-1"}
        session.observe_weight(80, 2)

        session.observe_weight(-1, 2)

        self.assertFalse(session.can_save)
        self.assertIsNone(session.weight_g)

    def test_exact_zero_threshold_counts_as_zero(self):
        session = ScanSession("8017596008299", zero_seen=False)
        session.observe_weight(2, 2)
        self.assertTrue(session.zero_seen)
        self.assertIsNone(session.weight_g)


if __name__ == "__main__":
    unittest.main()
