"""Config flow for the experimental Food Diary integration."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class FoodDiaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the local Food Diary database."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Create the single local Food Diary instance."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Food Diary", data={})

        return self.async_show_form(step_id="user", data_schema=None)
