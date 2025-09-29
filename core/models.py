# core/models.py

from dataclasses import dataclass, field, replace
from typing import Optional, List, Tuple
import numpy as np
from pathlib import Path
from core.constants import ChannelKind

@dataclass(frozen=True)
class SpectrometerSettings:
    start_pixel: int = 0
    stop_pixel: int = 0
    exposure_ms: float = 1.0
    n_averages: int = 1
    cordyn_dark: bool = False
    smooth_pix: int = 0
    smooth_model: int = 0
    saturation_detection: bool = False
    trigger_mode: int = 0
    trigger_source: int = 0
    trigger_source_type: int = 0

@dataclass(frozen=True)
class Spectrum:
    wavelength_nm: np.ndarray    # float64
    counts: np.ndarray           # float32/float64
    ts_iso: str
    settings_snapshot: SpectrometerSettings
    serial: Optional[str]
    role: str                    # "sample" | "reference" | "dark" | "abs" | "repeat"

@dataclass
class CalibrationSet:
    reference: Optional[Spectrum] = None
    dark: Optional[Spectrum] = None
    abs_cal: Optional[Spectrum] = None
    sample: Optional[Spectrum] = None

    def is_complete_for_reflectance(self) -> bool:
        return self.reference is not None and self.dark is not None and self.sample is not None

@dataclass
class ChannelState:
    kind: ChannelKind
    connected: bool = False
    serial: Optional[str] = None
    num_pixels: int = 0
    wavelength_nm_full: Optional[np.ndarray] = None
    settings: SpectrometerSettings = field(default_factory=SpectrometerSettings)
    calib: CalibrationSet = field(default_factory=CalibrationSet)
    latest_sample: Optional[Spectrum] = None
    repeats_buffer: List[Spectrum] = field(default_factory=list)
    reflectance: Optional[Tuple[np.ndarray, np.ndarray]] = None  # (λ, R)

@dataclass
class SessionState:
    save_dir: Path
    vis: ChannelState
    nir: ChannelState
    log: List[str] = field(default_factory=list)

    def channels(self):
        yield self.vis
        yield self.nir

    def append_log(self, msg: str):
        self.log.append(msg)
