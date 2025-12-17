"""Config flow for HA CRUD REST API."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    AVAILABLE_RESOURCES,
    CONF_ENABLED_RESOURCES,
    DEFAULT_RESOURCES,
    DOMAIN,
    RESOURCE_AUTOMATIONS,
    RESOURCE_DASHBOARDS,
    RESOURCE_HELPERS,
    RESOURCE_SCENES,
    RESOURCE_SCRIPTS,
)

RESOURCE_LABELS = {
    RESOURCE_DASHBOARDS: "Lovelace Dashboards",
    RESOURCE_AUTOMATIONS: "Automations",
    RESOURCE_SCENES: "Scenes",
    RESOURCE_SCRIPTS: "Scripts",
    RESOURCE_HELPERS: "Helpers",
}


class HaCrudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA CRUD REST API."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Only allow a single instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="HA CRUD REST API",
                data={},
                options={
                    CONF_ENABLED_RESOURCES: user_input.get(
                        CONF_ENABLED_RESOURCES, DEFAULT_RESOURCES
                    )
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLED_RESOURCES,
                        default=DEFAULT_RESOURCES,
                    ): vol.All(
                        cv.multi_select(
                            {key: RESOURCE_LABELS[key] for key in AVAILABLE_RESOURCES}
                        ),
                    ),
                }
            ),
            description_placeholders={
                "docs_url": "https://github.com/keith-gamble/ha-crud"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return HaCrudOptionsFlow(config_entry)


class HaCrudOptionsFlow(OptionsFlow):
    """Handle options flow for HA CRUD REST API."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_resources = self.config_entry.options.get(
            CONF_ENABLED_RESOURCES, DEFAULT_RESOURCES
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLED_RESOURCES,
                        default=current_resources,
                    ): cv.multi_select(
                        {key: RESOURCE_LABELS[key] for key in AVAILABLE_RESOURCES}
                    ),
                }
            ),
        )
