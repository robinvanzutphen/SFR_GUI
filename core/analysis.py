# core/analysis.py

import numpy as np
from typing import Tuple
from core.models import Spectrum
from core.constants import FULL_SCALE_COUNTS

def saturation_percent(counts: np.ndarray, full_scale: float = FULL_SCALE_COUNTS) -> float:
    if counts is None or counts.size == 0:
        return 0.0
    return float(np.nanmax(counts) / full_scale * 100.0)

def compute_reflectance(sample: Spectrum, reference: Spectrum, dark: Spectrum) -> Tuple[np.ndarray, np.ndarray]:
    """
    (S - D) / (R - D) with strict wavelength-equality requirement.
    Raises ValueError if wavelength grids mismatch or shapes differ.
    """
    lam_s = sample.wavelength_nm
    lam_r = reference.wavelength_nm
    lam_d = dark.wavelength_nm

    # Strict equality requested by user (no resampling)
    if lam_s.shape != lam_r.shape or lam_s.shape != lam_d.shape:
        raise ValueError("Wavelength grids must match exactly (shape mismatch).")
    if not (np.allclose(lam_s, lam_r) and np.allclose(lam_s, lam_d)):
        raise ValueError("Wavelength grids must match exactly (values mismatch).")

    num = sample.counts - dark.counts
    den = reference.counts - dark.counts

    with np.errstate(divide='ignore', invalid='ignore'):
        refl = np.where(den != 0, num / den, np.nan)

    return lam_s, refl
