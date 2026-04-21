"""Constants for the ReST Performance Bed integration."""

DOMAIN = "rest_bed"

ZONE_NAMES = ["Feet", "Hips", "Lumbar", "Head"]

MODE_MANUAL = "manual"
MODE_AUTOMATIC = "automatic"
MODE_POSITION = "position"
MODE_PRESSURE = "pressure"

MODES = [MODE_MANUAL, MODE_AUTOMATIC, MODE_POSITION, MODE_PRESSURE]

POSITION_PROFILE_OPTIONS = ["back", "side"]
POSITION_PROFILE_TO_KEY = {
    "back": "backprofile",
    "side": "sideprofile",
}

CALIBRATION_PREP_MODE = MODE_PRESSURE

MODEL_NAMES = {
    "daa": "P1",
    "maa": "P2/P3A",
    "mab": "P3",
    "mac": "P3A",
    "eaa": "P3B",
    "eab": "P3C",
    "eac": "P3D",
    "ead": "P3D",
    "exa": "P6",
}
