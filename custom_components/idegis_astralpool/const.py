"""Constants for the Idegis / AstralPool integration."""
from __future__ import annotations

DOMAIN = "idegis_astralpool"

# Config flow keys
CONF_MODE = "mode"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

# Operating modes
MODE_CLOUD_MITM = "cloud_mitm"
MODE_MODBUS_RTU = "modbus_rtu"
MODE_POOLSTATION = "poolstation"

# Defaults for cloud-MITM mode
DEFAULT_MITM_HOST = "192.168.1.70"  # CT104 in the reference setup
DEFAULT_MITM_PORT = 8765
DEFAULT_SCAN_INTERVAL_S = 10

# Hardware identity (read from holding 0x06 in Modbus, or from B0 prefix in MITM)
ATTR_DEVICE_ID = "device_id"
ATTR_SESSION_TOKEN = "session_token"

# Manufacturer info shown in the device registry
MANUFACTURER = "Idegis / AstralPool (Fluidra)"
MODEL_DEFAULT = "Neolysis / Domotic 2 / Elite Connect"
