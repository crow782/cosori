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


    def test_partial_nutrient_update_preserves_unspecified_values(self):
        food = self.store.add_food(
            "Latte", nutrients_per_100g={"energy_kcal": 50, "protein_g": 3.2}
        )
        updated = self.store.update_food(
            food["id"], nutrients_per_100g={"energy_kcal": 55}
        )
        self.assertEqual(updated["energy_kcal"], 55)
        self.assertEqual(updated["protein_g"], 3.2)

        cleared = self.store.update_food(
            food["id"], nutrients_per_100g={"protein_g": None}
        )
        self.assertIsNone(cleared["protein_g"])
        self.assertEqual(cleared["energy_kcal"], 55)

    def test_day_week_and_month_summaries_use_local_calendar(self):
        food = self.store.add_food(
            "Test", nutrients_per_100g={"energy_kcal": 100, "protein_g": 10}
        )
        # Both entries fall on 29 March in Europe/Rome, across the DST jump.
        self.store.add_entry(
            food["id"], 100, "breakfast",
            consumed_at="2026-03-29T00:30:00+01:00",
        )
        self.store.add_entry(
            food["id"], 100, "lunch",
            consumed_at="2026-03-29T03:30:00+02:00",
        )
        # This one is still 28 March locally and must not enter the day total.
        self.store.add_entry(
            food["id"], 100, "snack",
            consumed_at="2026-03-28T23:30:00+01:00",
        )

        day = self.store.period_summary("day", "2026-03-29", "Europe/Rome")
        self.assertEqual(day["entry_count"], 2)
        self.assertEqual(day["days_with_entries"], 1)
        self.assertEqual(day["totals"]["energy_kcal"], 200)
        self.assertEqual(day["by_day"][0]["date"], "2026-03-29")
        self.assertEqual(day["by_day"][0]["by_meal"]["breakfast"]["entry_count"], 1)

        week = self.store.period_summary("week", "2026-03-29", "Europe/Rome")
        self.assertEqual(week["start_date"], "2026-03-23")
        self.assertEqual(week["end_date_exclusive"], "2026-03-30")
        self.assertEqual(week["entry_count"], 3)

        month = self.store.period_summary("month", "2026-03-29", "Europe/Rome")
        self.assertEqual(month["start_date"], "2026-03-01")
        self.assertEqual(month["end_date_exclusive"], "2026-04-01")
        self.assertEqual(month["entry_count"], 3)

    def test_summary_keeps_unknown_nutrients_as_none(self):
        food = self.store.add_food("Alimento senza valori")
        self.store.add_entry(
            food["id"], 80, "snack",
            consumed_at="2026-11-28T12:00:00+01:00",
        )
        summary = self.store.period_summary("day", "2026-11-28", "Europe/Rome")
        self.assertIsNone(summary["totals"]["energy_kcal"])
        self.assertEqual(summary["entry_count"], 1)

    def test_period_summary_rejects_invalid_period_and_timezone(self):
        with self.assertRaises(ValueError):
            self.store.period_summary("year", "2026-11-28", "Europe/Rome")
        with self.assertRaises(ValueError):
            self.store.period_summary("day", "2026-11-28", "Not/A_Real_Zone")


    def test_timestamps_preserve_microseconds_and_normalize_to_utc(self):
        food = self.store.add_food("Acqua")
        entry = self.store.add_entry(
            food["id"], 250, "snack",
            consumed_at="2026-11-28T13:15:16.123456+01:00",
        )
        self.assertEqual(
            entry["consumed_at"], "2026-11-28T12:15:16.123456+00:00"
        )

    def test_empty_summary_and_year_boundary(self):
        empty = self.store.period_summary("day", "2026-02-28", "Europe/Rome")
        self.assertEqual(empty["entry_count"], 0)
        self.assertEqual(empty["days_with_entries"], 0)
        self.assertIsNone(empty["totals"]["energy_kcal"])
        food = self.store.add_food(
            "Mandorle", nutrients_per_100g={"energy_kcal": 600}
        )
        self.store.add_entry(
            food["id"], 10, "dinner",
            consumed_at="2026-12-31T23:30:00+01:00",
        )
        self.store.add_entry(
            food["id"], 10, "breakfast",
            consumed_at="2027-01-01T00:30:00+01:00",
        )
        december = self.store.period_summary("month", "2026-12-31", "Europe/Rome")
        january = self.store.period_summary("month", "2027-01-01", "Europe/Rome")
        self.assertEqual(december["entry_count"], 1)
        self.assertEqual(january["entry_count"], 1)
        self.assertEqual(december["end_date_exclusive"], "2027-01-01")

    def test_leap_february_month_range(self):
        february = self.store.period_summary("month", "2028-02-29", "Europe/Rome")
        self.assertEqual(february["start_date"], "2028-02-01")
        self.assertEqual(february["end_date_exclusive"], "2028-03-01")

    def test_database_schema_version_is_initialized(self):
        import sqlite3
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)


    def test_schema_v1_migrates_legacy_second_precision_timestamps(self):
        import sqlite3
        food = self.store.add_food("Caffè")
        entry = self.store.add_entry(
            food["id"], 100, "breakfast",
            consumed_at="2026-11-28T08:00:00+01:00",
        )
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE entries SET consumed_at=? WHERE id=?",
                ("2026-11-28T07:00:00+00:00", entry["id"]),
            )
            db.execute("PRAGMA user_version = 1")
        reopened = FoodDiaryStore(self.db_path)
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
            stored = db.execute(
                "SELECT consumed_at FROM entries WHERE id=?", (entry["id"],)
            ).fetchone()[0]
        self.assertEqual(stored, "2026-11-28T07:00:00.000000+00:00")
        rows = reopened.list_entries(
            "2026-11-28T08:00:00+01:00",
            "2026-11-28T09:00:00+01:00",
        )
        self.assertEqual(len(rows), 1)

    def test_anchor_date_rejects_datetime(self):
        with self.assertRaises(ValueError):
            self.store.period_summary(
                "day", datetime(2026, 11, 28), "Europe/Rome"
            )

    def test_integrity(self):
        self.assertEqual(self.store.integrity_check(), "ok")


if __name__ == "__main__":
    unittest.main()
