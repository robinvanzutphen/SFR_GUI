# core/devices.py

import time
import numpy as np

class Spectrometer:
    """
    Thin wrapper around avaspec for a single device.
    Assign .handle and .serial externally after activation.
    """
    def __init__(self):
        self.handle = None
        self.serial = None
        self.num_pixels = 0
        self.wavelengths = None

    def get_device_info(self):
        if not self.handle or self.handle <= 0:
            raise RuntimeError("get_device_info: invalid handle")

        import avaspec
        num_pix = avaspec.AVS_GetNumPixels(self.handle)
        if num_pix < 1:
            raise RuntimeError("AVS_GetNumPixels returned <1")

        self.num_pixels = int(num_pix)

        lam_ret = avaspec.AVS_GetLambda(self.handle)
        if isinstance(lam_ret, tuple):
            err_code, c_lambda = lam_ret
            if err_code < 0:
                raise RuntimeError(f"AVS_GetLambda error {err_code}")
            raw = np.array(c_lambda, dtype=float)
        else:
            raw = np.array(lam_ret, dtype=float)

        self.wavelengths = raw[: self.num_pixels]

    def single_measurement(self,
                           start_pixel: int,
                           stop_pixel: int,
                           exposure_ms: float,
                           n_averages: int,
                           trigger_mode: int):
        """
        Returns (wavelength_nm, counts)
        """
        if not self.handle or self.handle <= 0:
            raise RuntimeError("single_measurement: invalid handle")
        if self.wavelengths is None or self.num_pixels <= 0:
            raise RuntimeError("single_measurement: call get_device_info first")

        import avaspec
        if stop_pixel is None or stop_pixel < start_pixel:
            stop_pixel = self.num_pixels - 1

        cfg = avaspec.MeasConfigType()
        cfg.m_StartPixel = int(start_pixel)
        cfg.m_StopPixel = int(stop_pixel)
        cfg.m_IntegrationTime = float(exposure_ms)
        cfg.m_IntegrationDelay = 0
        cfg.m_NrAverages = int(n_averages)
        cfg.m_CorDynDark_m_Enable = 0
        cfg.m_CorDynDark_m_ForgetPercentage = 0
        cfg.m_Smoothing_m_SmoothPix = 0
        cfg.m_Smoothing_m_SmoothModel = 0
        cfg.m_SaturationDetection = 0
        cfg.m_Trigger_m_Mode = int(trigger_mode)
        cfg.m_Trigger_m_Source = 0
        cfg.m_Trigger_m_SourceType = 0
        cfg.m_Control_m_StrobeControl = 0
        cfg.m_Control_m_LaserDelay = 0
        cfg.m_Control_m_LaserWidth = 0
        cfg.m_Control_m_LaserWaveLength = 0.0
        cfg.m_Control_m_StoreToRam = 1

        ret = avaspec.AVS_PrepareMeasure(self.handle, cfg)
        if ret < 0:
            raise RuntimeError(f"AVS_PrepareMeasure failed ({ret})")

        ret = avaspec.AVS_Measure(self.handle, 0, 1)
        if ret < 0:
            raise RuntimeError(f"AVS_Measure error ({ret})")

        while avaspec.AVS_PollScan(self.handle) == 0:
            time.sleep(0.001)

        ts, c_spec = avaspec.AVS_GetScopeData(self.handle)
        counts = np.array(c_spec[: self.num_pixels], dtype=np.float32)
        return self.wavelengths, counts
