"""HTTP views for dashboard REST API."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from ..const import (
    API_BASE_PATH_DASHBOARDS,
    CONF_ICON,
    CONF_REQUIRE_ADMIN,
    CONF_SHOW_IN_SIDEBAR,
    CONF_TITLE,
    CONF_URL_PATH,
    ERR_DASHBOARD_EXISTS,
    ERR_DASHBOARD_NOT_FOUND,
    ERR_INVALID_CONFIG,
    ERR_YAML_DASHBOARD,
    LOVELACE_DATA,
    MODE_STORAGE,
    MODE_YAML,
)
from ..validation import (
    validate_create_data,
    validate_dashboard_config,
    validate_patch_data,
    validate_update_data,
)

if TYPE_CHECKING:
    from homeassistant.components.lovelace import LovelaceData

_LOGGER = logging.getLogger(__name__)


def get_lovelace_data(hass: HomeAssistant) -> dict[str, Any]:
    """Get lovelace data from hass.data."""
    return hass.data.get(LOVELACE_DATA, {})


def get_dashboards_collection(hass: HomeAssistant):
    """Get the dashboards collection for storage dashboards."""
    return hass.data.get("lovelace_dashboards")


class DashboardListView(HomeAssistantView):
    """View to list all dashboards and create new ones."""

    url = API_BASE_PATH_DASHBOARDS
    name = "api:config:dashboards"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request - list all dashboards.

        Returns:
            200: JSON array of dashboard metadata
        """
        hass: HomeAssistant = request.app["hass"]
        lovelace_data = get_lovelace_data(hass)

        if not lovelace_data:
            return self.json([])

        dashboards = []
        dashboard_configs = lovelace_data.get("dashboards", {})

        for url_path, config in dashboard_configs.items():
            try:
                info = await config.async_get_info()
                dashboard_data = {
                    "id": url_path if url_path else "lovelace",
                    "url_path": url_path,
                    "mode": info.get("mode", MODE_STORAGE),
                    "title": info.get("title"),
                    "icon": info.get("icon"),
                    "show_in_sidebar": info.get("show_in_sidebar", True),
                    "require_admin": info.get("require_admin", False),
                }
                dashboards.append(dashboard_data)
            except Exception as err:
                _LOGGER.warning(
                    "Error getting info for dashboard %s: %s",
                    url_path,
                    err,
                )
                continue

        return self.json(dashboards)

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request - create new dashboard.

        Request body:
            {
                "url_path": "my-dashboard",
                "title": "My Dashboard",
                "icon": "mdi:view-dashboard",
                "show_in_sidebar": true,
                "require_admin": false
            }

        Returns:
            201: Dashboard created successfully
            400: Invalid request data
            401: Not authorized (non-admin)
            409: Dashboard already exists
        """
        hass: HomeAssistant = request.app["hass"]

        # Check admin permission
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message(
                "Admin permission required",
                HTTPStatus.UNAUTHORIZED,
            )

        try:
            body = await request.json()
        except ValueError:
            return self.json_message(
                "Invalid JSON in request body",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        # Validate request data
        try:
            validated_data = validate_create_data(body)
        except vol.Invalid as err:
            return self.json_message(
                f"Invalid configuration: {err}",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        url_path = validated_data[CONF_URL_PATH]
        lovelace_data = get_lovelace_data(hass)
        dashboard_configs = lovelace_data.get("dashboards", {})

        # Check if dashboard already exists
        if url_path in dashboard_configs:
            return self.json_message(
                f"Dashboard '{url_path}' already exists",
                HTTPStatus.CONFLICT,
                ERR_DASHBOARD_EXISTS,
            )

        # Check if URL path conflicts with existing panels
        if url_path in hass.data.get("frontend_panels", {}):
            return self.json_message(
                f"URL path '{url_path}' conflicts with existing panel",
                HTTPStatus.CONFLICT,
                ERR_DASHBOARD_EXISTS,
            )

        # Create the dashboard via the collection
        try:
            collection = get_dashboards_collection(hass)
            if collection is None:
                return self.json_message(
                    "Dashboard collection not available. Ensure lovelace is in storage mode.",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

            await collection.async_create_item(validated_data)

            return self.json(
                {
                    "id": url_path,
                    "url_path": url_path,
                    "title": validated_data[CONF_TITLE],
                    "icon": validated_data.get(CONF_ICON, "mdi:view-dashboard"),
                    "show_in_sidebar": validated_data.get(CONF_SHOW_IN_SIDEBAR, True),
                    "require_admin": validated_data.get(CONF_REQUIRE_ADMIN, False),
                    "mode": MODE_STORAGE,
                },
                HTTPStatus.CREATED,
            )
        except Exception as err:
            _LOGGER.exception("Error creating dashboard: %s", err)
            return self.json_message(
                f"Error creating dashboard: {err}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


class DashboardDetailView(HomeAssistantView):
    """View for single dashboard operations."""

    url = API_BASE_PATH_DASHBOARDS + "/{dashboard_id}"
    name = "api:config:dashboard"
    requires_auth = True

    async def get(
        self, request: web.Request, dashboard_id: str
    ) -> web.Response:
        """Handle GET request - get single dashboard metadata.

        Path params:
            dashboard_id: The dashboard URL path (or "lovelace" for default)

        Returns:
            200: Dashboard metadata
            404: Dashboard not found
        """
        hass: HomeAssistant = request.app["hass"]
        lovelace_data = get_lovelace_data(hass)

        if not lovelace_data:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        # Handle default dashboard
        url_path = None if dashboard_id == "lovelace" else dashboard_id
        dashboard_configs = lovelace_data.get("dashboards", {})

        config = dashboard_configs.get(url_path)
        if config is None:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        try:
            info = await config.async_get_info()
        except Exception as err:
            _LOGGER.error("Error getting dashboard info: %s", err)
            return self.json_message(
                f"Error retrieving dashboard: {err}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        result = {
            "id": dashboard_id,
            "url_path": url_path,
            "mode": info.get("mode", MODE_STORAGE),
            "title": info.get("title"),
            "icon": info.get("icon"),
            "show_in_sidebar": info.get("show_in_sidebar", True),
            "require_admin": info.get("require_admin", False),
        }

        return self.json(result)

    async def put(
        self, request: web.Request, dashboard_id: str
    ) -> web.Response:
        """Handle PUT request - full update of dashboard metadata.

        Path params:
            dashboard_id: The dashboard URL path

        Request body:
            {
                "title": "New Title",
                "icon": "mdi:new-icon",
                "show_in_sidebar": true,
                "require_admin": false
            }

        Returns:
            200: Dashboard updated
            400: Invalid request data
            401: Not authorized (non-admin)
            404: Dashboard not found
            409: Cannot modify YAML dashboard
        """
        hass: HomeAssistant = request.app["hass"]

        # Check admin permission
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message(
                "Admin permission required",
                HTTPStatus.UNAUTHORIZED,
            )

        lovelace_data = get_lovelace_data(hass)
        url_path = None if dashboard_id == "lovelace" else dashboard_id
        dashboard_configs = lovelace_data.get("dashboards", {})

        config = dashboard_configs.get(url_path)
        if config is None:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        # Check if YAML dashboard (read-only)
        info = await config.async_get_info()
        if info.get("mode") == MODE_YAML:
            return self.json_message(
                f"Dashboard '{dashboard_id}' is YAML-based and read-only",
                HTTPStatus.CONFLICT,
                ERR_YAML_DASHBOARD,
            )

        try:
            body = await request.json()
        except ValueError:
            return self.json_message(
                "Invalid JSON in request body",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        try:
            validated_data = validate_update_data(body)
        except vol.Invalid as err:
            return self.json_message(
                f"Invalid configuration: {err}",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        try:
            collection = get_dashboards_collection(hass)
            if collection is None:
                return self.json_message(
                    "Dashboard collection not available",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

            await collection.async_update_item(url_path, validated_data)

            return self.json({
                "id": dashboard_id,
                "url_path": url_path,
                "mode": MODE_STORAGE,
                **validated_data,
            })
        except Exception as err:
            _LOGGER.exception("Error updating dashboard: %s", err)
            return self.json_message(
                f"Error updating dashboard: {err}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    async def patch(
        self, request: web.Request, dashboard_id: str
    ) -> web.Response:
        """Handle PATCH request - partial update of dashboard metadata.

        Path params:
            dashboard_id: The dashboard URL path

        Request body (all fields optional):
            {
                "title": "New Title",
                "icon": "mdi:new-icon",
                "show_in_sidebar": false,
                "require_admin": true
            }

        Returns:
            200: Dashboard updated
            400: Invalid request data
            401: Not authorized (non-admin)
            404: Dashboard not found
            409: Cannot modify YAML dashboard
        """
        hass: HomeAssistant = request.app["hass"]

        # Check admin permission
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message(
                "Admin permission required",
                HTTPStatus.UNAUTHORIZED,
            )

        lovelace_data = get_lovelace_data(hass)
        url_path = None if dashboard_id == "lovelace" else dashboard_id
        dashboard_configs = lovelace_data.get("dashboards", {})

        config = dashboard_configs.get(url_path)
        if config is None:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        # Check if YAML dashboard (read-only)
        info = await config.async_get_info()
        if info.get("mode") == MODE_YAML:
            return self.json_message(
                f"Dashboard '{dashboard_id}' is YAML-based and read-only",
                HTTPStatus.CONFLICT,
                ERR_YAML_DASHBOARD,
            )

        try:
            body = await request.json()
        except ValueError:
            return self.json_message(
                "Invalid JSON in request body",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        if not body:
            return self.json_message(
                "Request body cannot be empty",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        try:
            validated_data = validate_patch_data(body)
        except vol.Invalid as err:
            return self.json_message(
                f"Invalid configuration: {err}",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        try:
            collection = get_dashboards_collection(hass)
            if collection is None:
                return self.json_message(
                    "Dashboard collection not available",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

            await collection.async_update_item(url_path, validated_data)

            # Fetch updated info
            updated_info = await config.async_get_info()

            return self.json({
                "id": dashboard_id,
                "url_path": url_path,
                "mode": MODE_STORAGE,
                "title": updated_info.get("title"),
                "icon": updated_info.get("icon"),
                "show_in_sidebar": updated_info.get("show_in_sidebar", True),
                "require_admin": updated_info.get("require_admin", False),
            })
        except Exception as err:
            _LOGGER.exception("Error updating dashboard: %s", err)
            return self.json_message(
                f"Error updating dashboard: {err}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    async def delete(
        self, request: web.Request, dashboard_id: str
    ) -> web.Response:
        """Handle DELETE request - delete a dashboard.

        Path params:
            dashboard_id: The dashboard URL path

        Returns:
            204: Dashboard deleted (no content)
            401: Not authorized (non-admin)
            404: Dashboard not found
            409: Cannot delete YAML or default dashboard
        """
        hass: HomeAssistant = request.app["hass"]

        # Check admin permission
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message(
                "Admin permission required",
                HTTPStatus.UNAUTHORIZED,
            )

        # Cannot delete default dashboard
        if dashboard_id == "lovelace":
            return self.json_message(
                "Cannot delete the default dashboard",
                HTTPStatus.CONFLICT,
                "default_dashboard_protected",
            )

        lovelace_data = get_lovelace_data(hass)
        url_path = dashboard_id
        dashboard_configs = lovelace_data.get("dashboards", {})

        config = dashboard_configs.get(url_path)
        if config is None:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        # Check if YAML dashboard (cannot delete via API)
        info = await config.async_get_info()
        if info.get("mode") == MODE_YAML:
            return self.json_message(
                f"Dashboard '{dashboard_id}' is YAML-based and cannot be deleted via API",
                HTTPStatus.CONFLICT,
                ERR_YAML_DASHBOARD,
            )

        try:
            collection = get_dashboards_collection(hass)
            if collection is None:
                return self.json_message(
                    "Dashboard collection not available",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

            await collection.async_delete_item(url_path)

            return web.Response(status=HTTPStatus.NO_CONTENT)
        except Exception as err:
            _LOGGER.exception("Error deleting dashboard: %s", err)
            return self.json_message(
                f"Error deleting dashboard: {err}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


class DashboardConfigView(HomeAssistantView):
    """View for dashboard configuration (views/cards) operations."""

    url = API_BASE_PATH_DASHBOARDS + "/{dashboard_id}/config"
    name = "api:config:dashboard:config"
    requires_auth = True

    async def get(
        self, request: web.Request, dashboard_id: str
    ) -> web.Response:
        """Get the full configuration (views/cards) of a dashboard.

        Path params:
            dashboard_id: The dashboard URL path (or "lovelace" for default)

        Returns:
            200: Dashboard configuration (views, cards, etc.)
            404: Dashboard or config not found
        """
        hass: HomeAssistant = request.app["hass"]
        lovelace_data = get_lovelace_data(hass)

        if not lovelace_data:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        url_path = None if dashboard_id == "lovelace" else dashboard_id
        dashboard_configs = lovelace_data.get("dashboards", {})

        config = dashboard_configs.get(url_path)
        if config is None:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        try:
            dashboard_config = await config.async_load(force=False)
            return self.json(dashboard_config)
        except Exception as err:
            # ConfigNotFound or other errors
            _LOGGER.warning("Error loading dashboard config: %s", err)
            return self.json_message(
                f"Configuration for dashboard '{dashboard_id}' not found or empty",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

    async def put(
        self, request: web.Request, dashboard_id: str
    ) -> web.Response:
        """Replace the full configuration of a dashboard.

        Path params:
            dashboard_id: The dashboard URL path (or "lovelace" for default)

        Request body:
            {
                "views": [...],
                "title": "Optional Dashboard Title"
            }

        Returns:
            200: Configuration saved
            400: Invalid configuration
            401: Not authorized (non-admin)
            404: Dashboard not found
            409: YAML dashboard is read-only
        """
        hass: HomeAssistant = request.app["hass"]

        # Check admin permission
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message(
                "Admin permission required",
                HTTPStatus.UNAUTHORIZED,
            )

        lovelace_data = get_lovelace_data(hass)
        url_path = None if dashboard_id == "lovelace" else dashboard_id
        dashboard_configs = lovelace_data.get("dashboards", {})

        dashboard = dashboard_configs.get(url_path)
        if dashboard is None:
            return self.json_message(
                f"Dashboard '{dashboard_id}' not found",
                HTTPStatus.NOT_FOUND,
                ERR_DASHBOARD_NOT_FOUND,
            )

        # Check if YAML dashboard (read-only)
        info = await dashboard.async_get_info()
        if info.get("mode") == MODE_YAML:
            return self.json_message(
                f"Dashboard '{dashboard_id}' is YAML-based and read-only",
                HTTPStatus.CONFLICT,
                ERR_YAML_DASHBOARD,
            )

        try:
            body = await request.json()
        except ValueError:
            return self.json_message(
                "Invalid JSON in request body",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        try:
            validated_config = validate_dashboard_config(body)
        except vol.Invalid as err:
            return self.json_message(
                f"Invalid configuration: {err}",
                HTTPStatus.BAD_REQUEST,
                ERR_INVALID_CONFIG,
            )

        try:
            await dashboard.async_save(validated_config)
            return self.json(validated_config)
        except Exception as err:
            _LOGGER.exception("Error saving dashboard config: %s", err)
            return self.json_message(
                f"Error saving configuration: {err}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
