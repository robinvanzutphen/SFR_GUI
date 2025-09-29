# core/constants.py

from enum import Enum

# Device serials – adjust to your hardware
DEFAULT_VIS_SERIAL = "1711311U1"
DEFAULT_NIR_SERIAL = "1801119U1"

# Wavelength threshold to guess channel from data if filename lacks prefix
VIS_NIR_SPLIT_NM = 1050.0

# ADC full-scale used for "saturation %" display
FULL_SCALE_COUNTS = 16200.0

# CSV/Files
CSV_COMMENT_PREFIX = "# "
TIME_FORMAT_FILE = "%Y%m%d_%H%M%S"
TIME_FORMAT_ISO = "%Y-%m-%dT%H:%M:%S"

class ChannelKind(Enum):
    VIS = "VIS"
    NIR = "NIR"
