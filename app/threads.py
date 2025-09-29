# app/threads.py

from PyQt5.QtCore import QThread, pyqtSignal
from typing import Optional
from datetime import datetime
from core.constants import ChannelKind
from core.models import SpectrometerSettings, Spectrum
from core.analysis import saturation_percent

class ContinuousAcquisitionThread(QThread):
    """
    Emits (kind, Spectrum) continuously while running.
    """
    new_spectrum = pyqtSignal(object, object)  # ChannelKind, Spectrum

    def __init__(self, vis_dev, nir_dev, parent=None):
        super().__init__(parent)
        self.vis_dev = vis_dev
        self.nir_dev = nir_dev
        self.vis_settings: Optional[SpectrometerSettings] = None
        self.nir_settings: Optional[SpectrometerSettings] = None
        self._running = False

    def start_acquisition(self, vis_settings: SpectrometerSettings, nir_settings: SpectrometerSettings):
        self.vis_settings = vis_settings
        self.nir_settings = nir_settings
        self._running = True
        if not self.isRunning():
            self.start()

    def stop_acquisition(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                if getattr(self.vis_dev, "handle", None):
                    lam, spec = self.vis_dev.single_measurement(
                        start_pixel=self.vis_settings.start_pixel,
                        stop_pixel=self.vis_settings.stop_pixel,
                        exposure_ms=self.vis_settings.exposure_ms,
                        n_averages=self.vis_settings.n_averages,
                        trigger_mode=self.vis_settings.trigger_mode
                    )
                    sp = Spectrum(
                        wavelength_nm=lam, counts=spec,
                        ts_iso=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        settings_snapshot=self.vis_settings,
                        serial=self.vis_dev.serial, role="sample"
                    )
                    self.new_spectrum.emit(ChannelKind.VIS, sp)
                if getattr(self.nir_dev, "handle", None):
                    lam, spec = self.nir_dev.single_measurement(
                        start_pixel=self.nir_settings.start_pixel,
                        stop_pixel=self.nir_settings.stop_pixel,
                        exposure_ms=self.nir_settings.exposure_ms,
                        n_averages=self.nir_settings.n_averages,
                        trigger_mode=self.nir_settings.trigger_mode
                    )
                    sp = Spectrum(
                        wavelength_nm=lam, counts=spec,
                        ts_iso=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        settings_snapshot=self.nir_settings,
                        serial=self.nir_dev.serial, role="sample"
                    )
                    self.new_spectrum.emit(ChannelKind.NIR, sp)
            except Exception:
                # swallow to keep loop alive; controller logs on receive
                pass
            self.msleep(10)  # yield to GUI

class RepeatedAcquisitionThread(QThread):
    """
    Emits (kind, Spectrum, idx) repeatedly for count times with interval seconds
    """
    new_repeat = pyqtSignal(object, object, int)  # ChannelKind, Spectrum, idx

    def __init__(self, vis_dev, nir_dev, vis_settings: SpectrometerSettings, nir_settings: SpectrometerSettings,
                 count: int, interval_sec: float, parent=None):
        super().__init__(parent)
        self.vis_dev = vis_dev
        self.nir_dev = nir_dev
        self.vis_settings = vis_settings
        self.nir_settings = nir_settings
        self.count = int(count)
        self.interval_ms = int(max(0.0, float(interval_sec)) * 1000.0)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        from datetime import datetime
        for i in range(self.count):
            if not self._running:
                break
            if getattr(self.vis_dev, "handle", None):
                lam, spec = self.vis_dev.single_measurement(
                    start_pixel=self.vis_settings.start_pixel,
                    stop_pixel=self.vis_settings.stop_pixel,
                    exposure_ms=self.vis_settings.exposure_ms,
                    n_averages=self.vis_settings.n_averages,
                    trigger_mode=self.vis_settings.trigger_mode
                )
                sp = Spectrum(
                    wavelength_nm=lam, counts=spec,
                    ts_iso=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    settings_snapshot=self.vis_settings,
                    serial=self.vis_dev.serial, role="repeat"
                )
                self.new_repeat.emit(ChannelKind.VIS, sp, i)
            if getattr(self.nir_dev, "handle", None):
                lam, spec = self.nir_dev.single_measurement(
                    start_pixel=self.nir_settings.start_pixel,
                    stop_pixel=self.nir_settings.stop_pixel,
                    exposure_ms=self.nir_settings.exposure_ms,
                    n_averages=self.nir_settings.n_averages,
                    trigger_mode=self.nir_settings.trigger_mode
                )
                sp = Spectrum(
                    wavelength_nm=lam, counts=spec,
                    ts_iso=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    settings_snapshot=self.nir_settings,
                    serial=self.nir_dev.serial, role="repeat"
                )
                self.new_repeat.emit(ChannelKind.NIR, sp, i)
            self.msleep(self.interval_ms)
