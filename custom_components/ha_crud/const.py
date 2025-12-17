"""Constants for ha_crud component."""

DOMAIN = "ha_crud"

# Configuration
CONF_ENABLED_RESOURCES = "enabled_resources"

# Resource types that can be exposed via the API
RESOURCE_DASHBOARDS = "dashboards"
RESOURCE_AUTOMATIONS = "automations"
RESOURCE_SCENES = "scenes"
RESOURCE_SCRIPTS = "scripts"
RESOURCE_HELPERS = "helpers"

# All available resource types (for config flow)
AVAILABLE_RESOURCES = [
    RESOURCE_DASHBOARDS,
    RESOURCE_AUTOMATIONS,
    RESOURCE_SCENES,
    RESOURCE_SCRIPTS,
    RESOURCE_HELPERS,
]

# Default enabled resources
DEFAULT_RESOURCES = [RESOURCE_DASHBOARDS]

# API Base paths - using /api/ha_crud/ to avoid conflicts with HA built-in /api/config/
API_BASE_PATH_DASHBOARDS = "/api/ha_crud/dashboards"
API_BASE_PATH_AUTOMATIONS = "/api/ha_crud/automations"
API_BASE_PATH_SCENES = "/api/ha_crud/scenes"
API_BASE_PATH_SCRIPTS = "/api/ha_crud/scripts"
API_BASE_PATH_HELPERS = "/api/ha_crud/helpers"

# Lovelace data keys
LOVELACE_DATA = "lovelace"

# Dashboard modes
MODE_STORAGE = "storage"
MODE_YAML = "yaml"

# Configuration keys
CONF_URL_PATH = "url_path"
CONF_TITLE = "title"
CONF_ICON = "icon"
CONF_SHOW_IN_SIDEBAR = "show_in_sidebar"
CONF_REQUIRE_ADMIN = "require_admin"

# Error codes
ERR_DASHBOARD_NOT_FOUND = "dashboard_not_found"
ERR_DASHBOARD_EXISTS = "dashboard_already_exists"
ERR_INVALID_CONFIG = "invalid_config"
ERR_YAML_DASHBOARD = "yaml_dashboard_readonly"
ERR_DEFAULT_DASHBOARD = "default_dashboard_protected"

# Data keys for hass.data storage
DATA_DASHBOARDS_COLLECTION = f"{DOMAIN}_dashboards_collection"
