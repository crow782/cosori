"""Unit tests for scanner value parsing and portion gating."""
from __future__ import annotations

import unittest

from food_diary.acquisition import (\n    ScanSession, normalize_barcode, parse_openfoodfacts_product, parse_weight_grams\n)


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
        self.assertEqual(product["nutrients_per_100g"]["energy_kcal"], "62")
        self.assertEqual(product["nutrients_per_100g"]["protein_g"], "4.5")
        self.assertIsNone(product["nutrients_per_100g"]["fat_g"])

    def test_converts_kj_to_kcal_when_kcal_missing(self):
        product = parse_openfoodfacts_product(
            {"status": 1, "product": {"product_name": "Food", "nutriments": {"energy-kj_100g": 418.4}}},
            "8017596008299",
        )
        self.assertAlmostEqual(product["nutrients_per_100g"]["energy_kcal"], 100)

    def test_rejects_not_found_or_missing_product_name(self):
        self.assertIsNone(parse_openfoodfacts_product({"status": 0}, "8017596008299"))
        self.assertIsNone(parse_openfoodfacts_product({"status": 1, "product": {}}, "8017596008299"))


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


if __name__ == "__main__":
    unittest.main()
