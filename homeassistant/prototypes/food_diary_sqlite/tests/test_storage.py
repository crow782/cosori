import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from storage import FoodDiaryStore


class FoodDiaryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "food.db"
        self.store = FoodDiaryStore(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_food_search_is_alphabetical_and_barcode_unique(self):
        self.store.add_food("Zucchero", barcode="123", nutrients_per_100g={"energy_kcal": 400})
        self.store.add_food("Avena")
        self.assertEqual([x["name"] for x in self.store.search_foods()], ["Avena", "Zucchero"])
        with self.assertRaises(Exception):
            self.store.add_food("Duplicato", barcode="123")

    def test_entry_snapshots_nutrients_and_survives_reopen(self):
        food = self.store.add_food(
            "Yogurt", nutrients_per_100g={"energy_kcal": 62, "protein_g": 4.5}
        )
        entry = self.store.add_entry(
            food["id"], 125, "breakfast",
            consumed_at=datetime(2026, 11, 28, 8, 30, tzinfo=timezone.utc),
        )
        self.assertAlmostEqual(entry["energy_kcal"], 77.5)
        self.store.update_food(
            food["id"], nutrients_per_100g={"energy_kcal": 100, "protein_g": 8}
        )
        reopened = FoodDiaryStore(self.db_path)
        rows = reopened.list_entries("2026-11-28T00:00:00+00:00", "2026-11-29T00:00:00+00:00")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["energy_kcal"], 77.5)
        self.assertIn('"energy_kcal": 62.0', rows[0]["nutrients_per_100g_json"])

    def test_unknown_nutrients_remain_null(self):
        food = self.store.add_food("Mela")
        entry = self.store.add_entry(food["id"], 150, "snack")
        self.assertIsNone(food["energy_kcal"])
        self.assertIsNone(entry["energy_kcal"])

    def test_validation(self):
        food = self.store.add_food("Pane")
        with self.assertRaises(ValueError):
            self.store.add_entry(food["id"], 0, "lunch")
        with self.assertRaises(ValueError):
            self.store.add_entry(food["id"], 30, "brunch")
        with self.assertRaises(ValueError):
            self.store.add_entry(food["id"], 30, "lunch",
                                 consumed_at="2026-11-28T10:00:00")

    def test_integrity(self):
        self.assertEqual(self.store.integrity_check(), "ok")


if __name__ == "__main__":
    unittest.main()
