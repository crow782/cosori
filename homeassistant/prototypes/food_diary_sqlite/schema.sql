PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS foods (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    brand TEXT,
    barcode TEXT UNIQUE,
    energy_kcal REAL CHECK (energy_kcal IS NULL OR energy_kcal >= 0),
    protein_g REAL CHECK (protein_g IS NULL OR protein_g >= 0),
    carbohydrates_g REAL CHECK (carbohydrates_g IS NULL OR carbohydrates_g >= 0),
    sugars_g REAL CHECK (sugars_g IS NULL OR sugars_g >= 0),
    fat_g REAL CHECK (fat_g IS NULL OR fat_g >= 0),
    saturated_fat_g REAL CHECK (saturated_fat_g IS NULL OR saturated_fat_g >= 0),
    fiber_g REAL CHECK (fiber_g IS NULL OR fiber_g >= 0),
    salt_g REAL CHECK (salt_g IS NULL OR salt_g >= 0),
    source TEXT NOT NULL CHECK (source IN ('manual', 'openfoodfacts')),
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
    weight_g REAL NOT NULL CHECK (weight_g > 0),
    meal_type TEXT NOT NULL CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    consumed_at TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('scan', 'catalog', 'manual')),
    energy_kcal REAL CHECK (energy_kcal IS NULL OR energy_kcal >= 0),
    protein_g REAL CHECK (protein_g IS NULL OR protein_g >= 0),
    carbohydrates_g REAL CHECK (carbohydrates_g IS NULL OR carbohydrates_g >= 0),
    sugars_g REAL CHECK (sugars_g IS NULL OR sugars_g >= 0),
    fat_g REAL CHECK (fat_g IS NULL OR fat_g >= 0),
    saturated_fat_g REAL CHECK (saturated_fat_g IS NULL OR saturated_fat_g >= 0),
    fiber_g REAL CHECK (fiber_g IS NULL OR fiber_g >= 0),
    salt_g REAL CHECK (salt_g IS NULL OR salt_g >= 0),
    nutrients_per_100g_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_consumed_at ON entries(consumed_at);
CREATE INDEX IF NOT EXISTS idx_entries_meal ON entries(meal_type);
