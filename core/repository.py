# core/repository.py

from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
import time
from core.models import Spectrum, SpectrometerSettings
from core.constants import (
    CSV_COMMENT_PREFIX, TIME_FORMAT_FILE, TIME_FORMAT_ISO,
    ChannelKind, VIS_NIR_SPLIT_NM
)

def _settings_to_header_lines(settings: SpectrometerSettings) -> List[str]:
    return [
        f"{CSV_COMMENT_PREFIX}start_pixel: {settings.start_pixel}",
        f"{CSV_COMMENT_PREFIX}stop_pixel: {settings.stop_pixel}",
        f"{CSV_COMMENT_PREFIX}exposure_ms: {settings.exposure_ms:.6f}",
        f"{CSV_COMMENT_PREFIX}n_averages: {settings.n_averages}",
        f"{CSV_COMMENT_PREFIX}cordyn_dark: {int(settings.cordyn_dark)}",
        f"{CSV_COMMENT_PREFIX}smooth_pix: {settings.smooth_pix}",
        f"{CSV_COMMENT_PREFIX}smooth_model: {settings.smooth_model}",
        f"{CSV_COMMENT_PREFIX}saturation_detection: {int(settings.saturation_detection)}",
        f"{CSV_COMMENT_PREFIX}trigger_mode: {settings.trigger_mode}",
        f"{CSV_COMMENT_PREFIX}trigger_source: {settings.trigger_source}",
        f"{CSV_COMMENT_PREFIX}trigger_source_type: {settings.trigger_source_type}",
    ]

def save_spectrum_csv(channel: ChannelKind, spectrum: Spectrum, folder: Path, name_hint: Optional[str] = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    ts = time.strftime(TIME_FORMAT_FILE)
    role_token = spectrum.role.upper()
    base_name = name_hint.strip() if name_hint else f"{role_token}"
    fname = f"{channel.value}_{base_name}_{ts}.csv"
    fpath = folder / fname

    header_lines = [f"{CSV_COMMENT_PREFIX}wavelength,counts"]
    header_lines.append(f"{CSV_COMMENT_PREFIX}channel: {channel.value}")
    header_lines.append(f"{CSV_COMMENT_PREFIX}role: {spectrum.role}")
    header_lines.append(f"{CSV_COMMENT_PREFIX}serial: {spectrum.serial or ''}")
    header_lines.append(f"{CSV_COMMENT_PREFIX}timestamp: {spectrum.ts_iso}")
    header_lines.extend(_settings_to_header_lines(spectrum.settings_snapshot))
    header = "\n".join(header_lines)

    arr = np.column_stack((spectrum.wavelength_nm, spectrum.counts))
    np.savetxt(str(fpath), arr, delimiter=",", header=header, comments=CSV_COMMENT_PREFIX)
    return fpath

def save_repeats_csv(channel: ChannelKind, wavelength_nm: np.ndarray, repeats_counts: np.ndarray, folder: Path, name_hint: Optional[str]) -> Path:
    """
    repeats_counts: shape (n_lambda, n_meas)
    """
    folder.mkdir(parents=True, exist_ok=True)
    ts = time.strftime(TIME_FORMAT_FILE)
    base_name = (name_hint.strip() if name_hint else "REPEAT")
    fname = f"REP_{channel.value}_{base_name}_{ts}.csv"
    fpath = folder / fname

    n_meas = repeats_counts.shape[1]
    header_cols = ["wavelength"] + [f"meas{i+1}" for i in range(n_meas)]
    header = CSV_COMMENT_PREFIX + ",".join(header_cols)

    out = np.column_stack((wavelength_nm, repeats_counts))
    np.savetxt(str(fpath), out, delimiter=",", header=header, comments=CSV_COMMENT_PREFIX)
    return fpath

def _infer_channel_from_file_and_data(path: Path, wavelength_nm: np.ndarray) -> ChannelKind:
    upper = path.name.upper()
    if upper.startswith("VIS_") or upper.startswith("REP_VIS_"):
        return ChannelKind.VIS
    if upper.startswith("NIR_") or upper.startswith("REP_NIR_"):
        return ChannelKind.NIR
    # fallback on wavelength range
    return ChannelKind.VIS if float(np.nanmax(wavelength_nm)) < VIS_NIR_SPLIT_NM else ChannelKind.NIR

def load_spectrum_csv(path: Path) -> Tuple[ChannelKind, Spectrum]:
    """
    Loads a single spectrum CSV saved by this app.
    Ignores commented lines (starting with '# ').
    """
    path = Path(path)
    data = np.loadtxt(str(path), delimiter=",", comments="#")
    if data.ndim == 1:
        # ensure 2D
        data = data.reshape(1, -1)
    wavelength = data[:, 0].astype(float)
    counts = data[:, 1].astype(float)

    # metadata is optional here; set safe defaults
    settings = SpectrometerSettings()
    chan = _infer_channel_from_file_and_data(path, wavelength)
    spectrum = Spectrum(
        wavelength_nm=wavelength,
        counts=counts,
        ts_iso=time.strftime(TIME_FORMAT_ISO),
        settings_snapshot=settings,
        serial=None,
        role="sample"
    )
    return chan, spectrum
