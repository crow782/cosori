"""Constants for the Food Diary integration."""

from typing import Final

DOMAIN: Final = "food_diary"

CONF_WEIGHT_ENTITY: Final = "weight_entity"
CONF_BARCODE_ENTITY: Final = "barcode_entity"

CONF_DEFAULT_MEAL: Final = "default_meal"
CONF_AUTO_SAVE: Final = "auto_save"
CONF_WEIGHT_TIMEOUT: Final = "weight_timeout_seconds"
CONF_ZERO_THRESHOLD: Final = "zero_threshold_g"
CONF_OFF_ENABLED: Final = "openfoodfacts_enabled"
CONF_OFF_COUNTRY: Final = "openfoodfacts_country"
CONF_OFF_LANGUAGE: Final = "openfoodfacts_language"

DEFAULT_OPTIONS: Final = {
    CONF_DEFAULT_MEAL: "snack",
    CONF_AUTO_SAVE: True,
    CONF_WEIGHT_TIMEOUT: 45,
    CONF_ZERO_THRESHOLD: 2.0,
    CONF_OFF_ENABLED: True,
    CONF_OFF_COUNTRY: "it",
    CONF_OFF_LANGUAGE: "it",
}

MEALS: Final = ("breakfast", "lunch", "dinner", "snack")
