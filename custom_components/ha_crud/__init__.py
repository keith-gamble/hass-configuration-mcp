"""Home Assistant CRUD REST API component.

This component exposes REST endpoints for managing Home Assistant
resources like Lovelace dashboards, automations, scenes, and more.

Endpoints are registered based on the resources enabled in the config.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENABLED_RESOURCES,
    DATA_DASHBOARDS_COLLECTION,
    DEFAULT_RESOURCES,
    DOMAIN,
    RESOURCE_DASHBOARDS,
)
from .views import (
    DashboardConfigView,
    DashboardDetailView,
    DashboardListView,
)

_LOGGER = logging.getLogger(__name__)

# Track registered views to avoid duplicate registration
_REGISTERED_VIEWS: set[str] = set()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA CRUD REST API from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Get enabled resources from options (or defaults)
    enabled_resources = entry.options.get(CONF_ENABLED_RESOURCES, DEFAULT_RESOURCES)

    _LOGGER.info("HA CRUD REST API setting up with resources: %s", enabled_resources)

    # Initialize DashboardsCollection if dashboards are enabled
    if RESOURCE_DASHBOARDS in enabled_resources:
        await _setup_dashboards_collection(hass)

    # Register views for enabled resources
    _register_views(hass, enabled_resources)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _setup_dashboards_collection(hass: HomeAssistant) -> None:
    """Set up the dashboards collection for CRUD operations."""
    # Import here to avoid circular imports and ensure lovelace is loaded
    try:
        from homeassistant.components.lovelace.dashboard import DashboardsCollection
    except ImportError:
        _LOGGER.error("Could not import DashboardsCollection from lovelace")
        return

    # Create and load the collection (shares storage with lovelace component)
    collection = DashboardsCollection(hass)
    await collection.async_load()
    hass.data[DATA_DASHBOARDS_COLLECTION] = collection
    _LOGGER.debug("DashboardsCollection initialized with %d items", len(collection.data))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        del hass.data[DOMAIN][entry.entry_id]

    # Note: HTTP views cannot be unregistered in HA, they persist until restart
    _LOGGER.info(
        "HA CRUD REST API unloaded. Note: API endpoints remain active until HA restart."
    )

    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    enabled_resources = entry.options.get(CONF_ENABLED_RESOURCES, DEFAULT_RESOURCES)
    _LOGGER.info("HA CRUD REST API options updated. Enabled resources: %s", enabled_resources)

    # Register any newly enabled views
    _register_views(hass, enabled_resources)

    # Note: We can't unregister views, so disabled resources remain until restart
    _LOGGER.info(
        "Note: Disabled resources will stop being available after HA restart."
    )


def _register_views(hass: HomeAssistant, enabled_resources: list[str]) -> None:
    """Register HTTP views for enabled resources."""
    global _REGISTERED_VIEWS

    # Dashboard views
    if RESOURCE_DASHBOARDS in enabled_resources and RESOURCE_DASHBOARDS not in _REGISTERED_VIEWS:
        hass.http.register_view(DashboardListView())
        hass.http.register_view(DashboardDetailView())
        hass.http.register_view(DashboardConfigView())
        _REGISTERED_VIEWS.add(RESOURCE_DASHBOARDS)
        _LOGGER.info("Registered dashboard API endpoints at /api/config/dashboards")

    # Future resource views will be added here:
    # if RESOURCE_AUTOMATIONS in enabled_resources and RESOURCE_AUTOMATIONS not in _REGISTERED_VIEWS:
    #     hass.http.register_view(AutomationListView())
    #     ...
    #     _REGISTERED_VIEWS.add(RESOURCE_AUTOMATIONS)

    # if RESOURCE_SCENES in enabled_resources and RESOURCE_SCENES not in _REGISTERED_VIEWS:
    #     ...

    # if RESOURCE_SCRIPTS in enabled_resources and RESOURCE_SCRIPTS not in _REGISTERED_VIEWS:
    #     ...

    # if RESOURCE_HELPERS in enabled_resources and RESOURCE_HELPERS not in _REGISTERED_VIEWS:
    #     ...
