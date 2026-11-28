"""Isolated SQLite storage prototype for the Home Assistant Food Diary.

This module deliberately has no Home Assistant imports and can be tested
independently with the Python standard library.
"""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
from typing import Any, Mapping

MEALS = {"breakfast", "lunch", "dinner", "snack"}
FOOD_SOURCES = {"manual", "openfoodfacts"}
ENTRY_SOURCES = {"scan", "catalog", "manual"}
NUTRIENTS = (
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "sugars_g",
    "fat_g",
    "saturated_fat_g",
    "fiber_g",
    "salt_g",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        return _now()
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("consumed_at must include a timezone/UTC offset")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nutrient_values(values: Mapping[str, Any] | None) -> dict[str, float | None]:
    values = values or {}
    result: dict[str, float | None] = {}
    for key in NUTRIENTS:
        raw = values.get(key)
        if raw is None or raw == "":
            result[key] = None
            continue
        number = float(raw)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{key} must be a finite non-negative number")
        result[key] = number
    return result


class FoodDiaryStore:
    """Small repository for foods and consumed portions."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS foods (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
                    brand TEXT,
                    barcode TEXT UNIQUE,
                    energy_kcal REAL CHECK(energy_kcal IS NULL OR energy_kcal >= 0),
                    protein_g REAL CHECK(protein_g IS NULL OR protein_g >= 0),
                    carbohydrates_g REAL CHECK(carbohydrates_g IS NULL OR carbohydrates_g >= 0),
                    sugars_g REAL CHECK(sugars_g IS NULL OR sugars_g >= 0),
                    fat_g REAL CHECK(fat_g IS NULL OR fat_g >= 0),
                    saturated_fat_g REAL CHECK(saturated_fat_g IS NULL OR saturated_fat_g >= 0),
                    fiber_g REAL CHECK(fiber_g IS NULL OR fiber_g >= 0),
                    salt_g REAL CHECK(salt_g IS NULL OR salt_g >= 0),
                    source TEXT NOT NULL CHECK(source IN ('manual','openfoodfacts')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_foods_name ON foods(name COLLATE NOCASE);
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    food_id TEXT REFERENCES foods(id) ON DELETE SET NULL,
                    food_name_snapshot TEXT NOT NULL,
                    brand_snapshot TEXT,
                    barcode_snapshot TEXT,
                    weight_g REAL NOT NULL CHECK(weight_g > 0),
                    meal_type TEXT NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner','snack')),
                    consumed_at TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source IN ('scan','catalog','manual')),
                    energy_kcal REAL CHECK(energy_kcal IS NULL OR energy_kcal >= 0),
                    protein_g REAL CHECK(protein_g IS NULL OR protein_g >= 0),
                    carbohydrates_g REAL CHECK(carbohydrates_g IS NULL OR carbohydrates_g >= 0),
                    sugars_g REAL CHECK(sugars_g IS NULL OR sugars_g >= 0),
                    fat_g REAL CHECK(fat_g IS NULL OR fat_g >= 0),
                    saturated_fat_g REAL CHECK(saturated_fat_g IS NULL OR saturated_fat_g >= 0),
                    fiber_g REAL CHECK(fiber_g IS NULL OR fiber_g >= 0),
                    salt_g REAL CHECK(salt_g IS NULL OR salt_g >= 0),
                    nutrients_per_100g_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_entries_consumed_at ON entries(consumed_at);
                CREATE INDEX IF NOT EXISTS idx_entries_meal ON entries(meal_type);
            """)

    def add_food(
        self, name: str, *, brand: str | None = None, barcode: str | None = None,
        nutrients_per_100g: Mapping[str, Any] | None = None, source: str = "manual",
    ) -> dict[str, Any]:
        name = str(name).strip()
        if not name:
            raise ValueError("food name is required")
        if source not in FOOD_SOURCES:
            raise ValueError("unsupported food source")
        nutrient_values = _nutrient_values(nutrients_per_100g)
        now, food_id = _now(), str(uuid.uuid4())
        values = [nutrient_values[key] for key in NUTRIENTS]
        with self._connect() as db:
            db.execute(
                """INSERT INTO foods
                (id,name,brand,barcode,energy_kcal,protein_g,carbohydrates_g,sugars_g,
                 fat_g,saturated_fat_g,fiber_g,salt_g,source,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [food_id, name, _optional_text(brand), _optional_text(barcode),
                 *values, source, now, now],
            )
            row = db.execute("SELECT * FROM foods WHERE id=?", (food_id,)).fetchone()
        return dict(row)

    def update_food(self, food_id: str, **changes: Any) -> dict[str, Any]:
        allowed = {"name", "brand", "barcode", "nutrients_per_100g", "source"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported fields: {', '.join(sorted(unknown))}")
        with self._connect() as db:
            row = db.execute("SELECT * FROM foods WHERE id=?", (food_id,)).fetchone()
            if row is None:
                raise KeyError(food_id)
            current = dict(row)
            name = str(changes.get("name", current["name"])).strip()
            if not name:
                raise ValueError("food name is required")
            source = changes.get("source", current["source"])
            if source not in FOOD_SOURCES:
                raise ValueError("unsupported food source")
            # A partial edit preserves omitted nutrients; explicit None clears one.
            merged_nutrients = {key: current[key] for key in NUTRIENTS}
            if "nutrients_per_100g" in changes:
                supplied = changes["nutrients_per_100g"] or {}
                unknown_nutrients = set(supplied) - set(NUTRIENTS)
                if unknown_nutrients:
                    raise ValueError(
                        f"unsupported nutrients: {', '.join(sorted(unknown_nutrients))}"
                    )
                merged_nutrients.update(supplied)
            nutrients = _nutrient_values(merged_nutrients)
            db.execute(
                """UPDATE foods SET name=?,brand=?,barcode=?,energy_kcal=?,protein_g=?,
                carbohydrates_g=?,sugars_g=?,fat_g=?,saturated_fat_g=?,fiber_g=?,salt_g=?,
                source=?,updated_at=? WHERE id=?""",
                [name,
                 _optional_text(changes.get("brand", current["brand"])),
                 _optional_text(changes.get("barcode", current["barcode"])),
                 *[nutrients[k] for k in NUTRIENTS], source, _now(), food_id],
            )
            return dict(db.execute("SELECT * FROM foods WHERE id=?", (food_id,)).fetchone())

    def get_food(self, food_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM foods WHERE id=?", (food_id,)).fetchone()
            return dict(row) if row else None

    def find_food_by_barcode(self, barcode: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM foods WHERE barcode=?", (str(barcode).strip(),)).fetchone()
            return dict(row) if row else None

    def search_foods(self, query: str = "", *, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= int(limit) <= 500:
            raise ValueError("limit must be between 1 and 500")
        escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_query}%"
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM foods
                WHERE name LIKE ? ESCAPE '\\' OR COALESCE(brand,'') LIKE ? ESCAPE '\\'
                ORDER BY name COLLATE NOCASE, brand COLLATE NOCASE LIMIT ?""",
                (pattern, pattern, int(limit)),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_food(self, food_id: str) -> None:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM foods WHERE id=?", (food_id,))
            if cursor.rowcount == 0:
                raise KeyError(food_id)

    def add_entry(
        self, food_id: str, weight_g: float, meal_type: str, *,
        consumed_at: str | datetime | None = None, source: str = "catalog",
    ) -> dict[str, Any]:
        weight = float(weight_g)
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("weight_g must be a finite positive number")
        if meal_type not in MEALS:
            raise ValueError("unsupported meal_type")
        if source not in ENTRY_SOURCES:
            raise ValueError("unsupported entry source")
        timestamp, entry_id = _timestamp(consumed_at), str(uuid.uuid4())
        with self._connect() as db:
            food = db.execute("SELECT * FROM foods WHERE id=?", (food_id,)).fetchone()
            if food is None:
                raise KeyError(food_id)
            per100 = {key: food[key] for key in NUTRIENTS}
            portion = {
                key: (value * weight / 100 if value is not None else None)
                for key, value in per100.items()
            }
            db.execute(
                """INSERT INTO entries
                (id,food_id,food_name_snapshot,brand_snapshot,barcode_snapshot,weight_g,
                 meal_type,consumed_at,source,energy_kcal,protein_g,carbohydrates_g,sugars_g,
                 fat_g,saturated_fat_g,fiber_g,salt_g,nutrients_per_100g_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [entry_id, food_id, food["name"], food["brand"], food["barcode"], weight,
                 meal_type, timestamp, source, *[portion[k] for k in NUTRIENTS],
                 json.dumps(per100, allow_nan=False), _now(), _now()],
            )
            return dict(db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone())

    def list_entries(self, start: str, end: str) -> list[dict[str, Any]]:
        start_ts, end_ts = _timestamp(start), _timestamp(end)
        if start_ts > end_ts:
            raise ValueError("start must not be after end")
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM entries WHERE consumed_at >= ? AND consumed_at < ?
                ORDER BY consumed_at, created_at""", (start_ts, end_ts)
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_entry(self, entry_id: str) -> None:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
            if cursor.rowcount == 0:
                raise KeyError(entry_id)


    @staticmethod
    def _sum_nutrients(rows: list[dict[str, Any]]) -> dict[str, float | None]:
        """Sum known nutrient values; keep a nutrient NULL if every row is unknown."""
        totals: dict[str, float | None] = {}
        for key in NUTRIENTS:
            known = [row[key] for row in rows if row[key] is not None]
            totals[key] = sum(known) if known else None
        return totals

    def period_summary(
        self, period: str, anchor_date: str | date, timezone_name: str
    ) -> dict[str, Any]:
        """Return local-calendar totals for one day, ISO week, or calendar month.

        anchor_date selects the day/week/month. timezone_name must be an IANA
        zone such as Europe/Rome. Stored timestamps remain UTC; local grouping
        occurs after conversion so DST days can be 23 or 25 hours long.
        """
        if isinstance(anchor_date, str):
            try:
                selected_date = date.fromisoformat(anchor_date)
            except ValueError as exc:
                raise ValueError("anchor_date must be YYYY-MM-DD") from exc
        elif isinstance(anchor_date, date):
            selected_date = anchor_date
        else:
            raise ValueError("anchor_date must be a date or YYYY-MM-DD string")

        try:
            local_zone = ZoneInfo(timezone_name)
        except (TypeError, ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("timezone_name must be a valid IANA timezone") from exc

        if period == "day":
            first_day = selected_date
            last_day = first_day + timedelta(days=1)
        elif period == "week":
            first_day = selected_date - timedelta(days=selected_date.weekday())
            last_day = first_day + timedelta(days=7)
        elif period == "month":
            first_day = selected_date.replace(day=1)
            if first_day.month == 12:
                last_day = date(first_day.year + 1, 1, 1)
            else:
                last_day = date(first_day.year, first_day.month + 1, 1)
        else:
            raise ValueError("period must be 'day', 'week', or 'month'")

        local_start = datetime.combine(first_day, datetime.min.time(), local_zone)
        local_end = datetime.combine(last_day, datetime.min.time(), local_zone)
        entries = self.list_entries(local_start.isoformat(), local_end.isoformat())

        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            consumed = datetime.fromisoformat(entry["consumed_at"]).astimezone(local_zone)
            grouped.setdefault(consumed.date().isoformat(), []).append(entry)

        by_day: list[dict[str, Any]] = []
        for day_key in sorted(grouped):
            day_entries = grouped[day_key]
            by_meal: dict[str, Any] = {}
            for meal in sorted(MEALS):
                meal_entries = [item for item in day_entries if item["meal_type"] == meal]
                if meal_entries:
                    by_meal[meal] = {
                        "entry_count": len(meal_entries),
                        "totals": self._sum_nutrients(meal_entries),
                    }
            by_day.append({
                "date": day_key,
                "entry_count": len(day_entries),
                "totals": self._sum_nutrients(day_entries),
                "by_meal": by_meal,
            })

        return {
            "period": period,
            "timezone": timezone_name,
            "start_date": first_day.isoformat(),
            "end_date_exclusive": last_day.isoformat(),
            "entry_count": len(entries),
            "days_with_entries": len(by_day),
            "totals": self._sum_nutrients(entries),
            "by_day": by_day,
        }

    def integrity_check(self) -> str:
        with self._connect() as db:
            return str(db.execute("PRAGMA integrity_check").fetchone()[0])
