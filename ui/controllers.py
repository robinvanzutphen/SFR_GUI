# app/controllers.py

import os
import threading
import time
from pathlib import Path
from datetime import datetime
import numpy as np

from core.constants import ChannelKind, DEFAULT_VIS_SERIAL, DEFAULT_NIR_SERIAL, TIME_FORMAT_ISO, FULL_SCALE_COUNTS
from core.models import SessionState, ChannelState, Spectrum
from core.analysis import saturation_percent, compute_reflectance
from core.repository import save_spectrum_csv, load_spectrum_csv, save_repeats_csv
from app.threads import ContinuousAcquisitionThread, RepeatedAcquisitionThread

class Controller:
    def __init__(self, state: SessionState, devices, ui, parent_qobj):
        """
        devices: dict {ChannelKind: Spectrometer}
        ui: object with fields: meas_panel, resp_panel, set_panel
        parent_qobj: the QMainWindow (for parenting dialogs/threads)
        """
        self.state = state
        self.devices = devices
        self.ui = ui
        self.parent = parent_qobj

        # Threads
        self.cont_thread = ContinuousAcquisitionThread(devices[ChannelKind.VIS], devices[ChannelKind.NIR], parent_qobj)
        self.cont_thread.new_spectrum.connect(self._on_continuous_spectrum)

        self.repeat_thread = None

        # Throttling
        self._last_cont_plot = 0.0
        self._cont_interval_s = 0.01
        self._last_refl_plot = 0.0
        self._refl_interval_s = 0.05

        self._wire_calibration_buttons()

    # ---------------- UI wiring helpers ----------------

    def _wire_calibration_buttons(self):
        entries = self.ui.meas_panel.calib_entries
        for key, entry in entries.items():
            entry.load_btn.clicked.connect(lambda _=False, k=key: self.load_calibration(k))
            entry.meas_btn.clicked.connect(lambda _=False, k=key: self.measure_calibration(k))

    def log(self, text: str):
        self.state.append_log(text)
        self.ui.resp_panel.log_txt.append(text)

    # ---------------- Connections ----------------

    def setup_connections(self):
        self.log("[INFO] Searching for Avantes spectrometers …")
        try:
            import avaspec
        except ImportError:
            self.log("[ERROR] avaspec library not found.")
            return

        # Reset any previous
        self.disconnect_spectrometers(silent=True)

        n_dev = avaspec.AVS_Init(0)
        if n_dev < 1:
            self.log("[ERROR] No spectrometers detected.")
            return

        devices = avaspec.AVS_GetList(n_dev)
        found_vis = found_nir = False

        for dev in devices:
            serial = dev.SerialNumber.decode().strip()
            handle = avaspec.AVS_Activate(dev)
            if handle <= 0:
                self.log(f"[ERROR] Could not activate {serial}.")
                continue

            if serial == DEFAULT_VIS_SERIAL:
                d = self.devices[ChannelKind.VIS]
                d.handle = handle
                d.serial = serial
                d.get_device_info()
                st = self.state.vis
                st.connected = True
                st.serial = serial
                st.num_pixels = d.num_pixels
                st.wavelength_nm_full = d.wavelengths.copy()
                # clamp UI range
                self.ui.set_panel.vis_set.stop_pix.setRange(0, d.num_pixels - 1)
                self.ui.set_panel.vis_set.stop_pix.setValue(d.num_pixels - 1)
                self.ui.meas_panel.chk_vis.setChecked(True)
                self.log("[INFO] Connected VIS ({})".format(serial))
                found_vis = True

            elif serial == DEFAULT_NIR_SERIAL:
                d = self.devices[ChannelKind.NIR]
                d.handle = handle
                d.serial = serial
                d.get_device_info()
                st = self.state.nir
                st.connected = True
                st.serial = serial
                st.num_pixels = d.num_pixels
                st.wavelength_nm_full = d.wavelengths.copy()
                self.ui.set_panel.nir_set.stop_pix.setRange(0, d.num_pixels - 1)
                self.ui.set_panel.nir_set.stop_pix.setValue(d.num_pixels - 1)
                self.ui.meas_panel.chk_nir.setChecked(True)
                self.log("[INFO] Connected NIR ({})".format(serial))
                found_nir = True

        if not found_vis:
            self.log("[WARNING] VIS spectrometer not found.")
        if not found_nir:
            self.log("[WARNING] NIR spectrometer not found.")

    def disconnect_spectrometers(self, silent: bool = False):
        try:
            import avaspec
        except ImportError:
            return

        for kind in (ChannelKind.VIS, ChannelKind.NIR):
            d = self.devices[kind]
            if getattr(d, "handle", None):
                try:
                    avaspec.AVS_StopMeasure(d.handle)
                    if not silent:
                        self.log(f"[INFO] Stopped measure on {d.serial}.")
                except Exception:
                    pass
        try:
            avaspec.AVS_Done()
            if not silent:
                self.log("[INFO] Closed Avantes interface.")
        except Exception:
            pass

        for ch in self.state.channels():
            ch.connected = False
            ch.serial = None
        self.ui.meas_panel.chk_vis.setChecked(False)
        self.ui.meas_panel.chk_nir.setChecked(False)

    # ---------------- Single measurement ----------------

    def measure_single(self):
        if not self.state.vis.connected and not self.state.nir.connected:
            self.log("[ERROR] No spectrometer connected.")
            return

        vis_set = self.ui.set_panel.get_vis()
        nir_set = self.ui.set_panel.get_nir()

        results = {}
        errors = {}

        def do_vis():
            try:
                if self.state.vis.connected:
                    lam, spec = self.devices[ChannelKind.VIS].single_measurement(
                        start_pixel=vis_set.start_pixel,
                        stop_pixel=vis_set.stop_pixel,
                        exposure_ms=vis_set.exposure_ms,
                        n_averages=vis_set.n_averages,
                        trigger_mode=vis_set.trigger_mode
                    )
                    sp = Spectrum(
                        wavelength_nm=lam, counts=spec,
                        ts_iso=datetime.now().strftime(TIME_FORMAT_ISO),
                        settings_snapshot=vis_set,
                        serial=self.devices[ChannelKind.VIS].serial,
                        role="sample"
                    )
                    results[ChannelKind.VIS] = sp
            except Exception as e:
                errors[ChannelKind.VIS] = e

        def do_nir():
            try:
                if self.state.nir.connected:
                    lam, spec = self.devices[ChannelKind.NIR].single_measurement(
                        start_pixel=nir_set.start_pixel,
                        stop_pixel=nir_set.stop_pixel,
                        exposure_ms=nir_set.exposure_ms,
                        n_averages=nir_set.n_averages,
                        trigger_mode=nir_set.trigger_mode
                    )
                    sp = Spectrum(
                        wavelength_nm=lam, counts=spec,
                        ts_iso=datetime.now().strftime(TIME_FORMAT_ISO),
                        settings_snapshot=nir_set,
                        serial=self.devices[ChannelKind.NIR].serial,
                        role="sample"
                    )
                    results[ChannelKind.NIR] = sp
            except Exception as e:
                errors[ChannelKind.NIR] = e

        threads = []
        if self.state.vis.connected:
            t = threading.Thread(target=do_vis); t.start(); threads.append(t)
        if self.state.nir.connected:
            t = threading.Thread(target=do_nir); t.start(); threads.append(t)
        for t in threads:
            t.join()

        # Update state & UI
        if ChannelKind.VIS in results:
            sp = results[ChannelKind.VIS]
            ch = self.state.vis
            ch.latest_sample = sp
            ch.calib.sample = sp
            vs = saturation_percent(sp.counts)
            self.log(f"[INFO] VIS sample measured – {sp.counts.size} pts (sat {vs:.1f}%).")
            entry = self.ui.meas_panel.calib_entries["sample"]
            entry.vis_ind.set_green()
            entry.vis_meta.setText(f"{sp.wavelength_nm.min():.2f}–{sp.wavelength_nm.max():.2f} nm")
        elif ChannelKind.VIS in errors:
            self.log(f"[ERROR] VIS sample measurement failed: {errors[ChannelKind.VIS]}")

        if ChannelKind.NIR in results:
            sp = results[ChannelKind.NIR]
            ch = self.state.nir
            ch.latest_sample = sp
            ch.calib.sample = sp
            ns = saturation_percent(sp.counts)
            self.log(f"[INFO] NIR sample measured – {sp.counts.size} pts (sat {ns:.1f}%).")
            entry = self.ui.meas_panel.calib_entries["sample"]
            entry.nir_ind.set_green()
            entry.nir_meta.setText(f"{sp.wavelength_nm.min():.2f}–{sp.wavelength_nm.max():.2f} nm")
        elif ChannelKind.NIR in errors:
            self.log(f"[ERROR] NIR sample measurement failed: {errors[ChannelKind.NIR]}")

        # Raw plot
        lam_v, spec_v = (self.state.vis.latest_sample.wavelength_nm, self.state.vis.latest_sample.counts) if self.state.vis.latest_sample else (None, None)
        lam_n, spec_n = (self.state.nir.latest_sample.wavelength_nm, self.state.nir.latest_sample.counts) if self.state.nir.latest_sample else (None, None)
        vs = saturation_percent(spec_v) if spec_v is not None else None
        ns = saturation_percent(spec_n) if spec_n is not None else None
        self.ui.resp_panel.spectrum_widget.plot_two(lam_vis=lam_v, spec_vis=spec_v, vis_sat=vs,
                                                    lam_nir=lam_n, spec_nir=spec_n, nir_sat=ns)

        # Reflectance
        self.update_reflectance_plot()

    # ---------------- Continuous ----------------

    def start_continuous(self):
        vis_set = self.ui.set_panel.get_vis()
        nir_set = self.ui.set_panel.get_nir()
        self.cont_thread.start_acquisition(vis_set, nir_set)

    def stop_continuous(self):
        self.cont_thread.stop_acquisition()

    def _on_continuous_spectrum(self, kind: ChannelKind, spectrum: Spectrum):
        # Stash
        ch = self.state.vis if kind is ChannelKind.VIS else self.state.nir
        ch.latest_sample = spectrum
        ch.calib.sample = spectrum

        # Update sample indicators
        entry = self.ui.meas_panel.calib_entries["sample"]
        if kind is ChannelKind.VIS:
            entry.vis_ind.set_green()
            entry.vis_meta.setText(f"{spectrum.wavelength_nm.min():.2f}–{spectrum.wavelength_nm.max():.2f} nm")
        else:
            entry.nir_ind.set_green()
            entry.nir_meta.setText(f"{spectrum.wavelength_nm.min():.2f}–{spectrum.wavelength_nm.max():.2f} nm")

        now = time.time()
        # Raw plot (throttled)
        if now - self._last_cont_plot >= self._cont_interval_s:
            self._last_cont_plot = now
            lam_v, spec_v = (self.state.vis.latest_sample.wavelength_nm, self.state.vis.latest_sample.counts) if self.state.vis.latest_sample else (None, None)
            lam_n, spec_n = (self.state.nir.latest_sample.wavelength_nm, self.state.nir.latest_sample.counts) if self.state.nir.latest_sample else (None, None)
            vs = saturation_percent(spec_v) if spec_v is not None else None
            ns = saturation_percent(spec_n) if spec_n is not None else None
            self.ui.resp_panel.spectrum_widget.plot_two(lam_vis=lam_v, spec_vis=spec_v, vis_sat=vs,
                                                        lam_nir=lam_n, spec_nir=spec_n, nir_sat=ns)

        # Reflectance (throttled)
        if now - self._last_refl_plot >= self._refl_interval_s:
            self._last_refl_plot = now
            self.update_reflectance_plot()

    # ---------------- Repeated ----------------

    def start_repeated(self):
        cnt = self.ui.meas_panel.repeat_count.value()
        interval = self.ui.meas_panel.repeat_interval.value()
        vis_set = self.ui.set_panel.get_vis()
        nir_set = self.ui.set_panel.get_nir()

        # Clear previous
        self.state.vis.repeats_buffer.clear()
        self.state.nir.repeats_buffer.clear()

        self.repeat_thread = RepeatedAcquisitionThread(
            self.devices[ChannelKind.VIS], self.devices[ChannelKind.NIR],
            vis_set, nir_set, cnt, interval, self.parent
        )
        self.repeat_thread.new_repeat.connect(self._on_repeated_spectrum)
        self.repeat_thread.finished.connect(self._save_repeated_results)
        self.repeat_thread.start()

    def _on_repeated_spectrum(self, kind: ChannelKind, spectrum: Spectrum, idx: int):
        ch = self.state.vis if kind is ChannelKind.VIS else self.state.nir
        ch.repeats_buffer.append(spectrum)

        # Live plot the last spectrum for that channel
        lam_v, spec_v = (self.state.vis.latest_sample.wavelength_nm, self.state.vis.latest_sample.counts) if self.state.vis.latest_sample else (None, None)
        lam_n, spec_n = (self.state.nir.latest_sample.wavelength_nm, self.state.nir.latest_sample.counts) if self.state.nir.latest_sample else (None, None)

        # Update current latest with incoming
        if kind is ChannelKind.VIS:
            lam_v, spec_v = spectrum.wavelength_nm, spectrum.counts
        else:
            lam_n, spec_n = spectrum.wavelength_nm, spectrum.counts

        vs = saturation_percent(spec_v) if spec_v is not None else None
        ns = saturation_percent(spec_n) if spec_n is not None else None
        self.ui.resp_panel.spectrum_widget.plot_two(lam_vis=lam_v, spec_vis=spec_v, vis_sat=vs,
                                                    lam_nir=lam_n, spec_nir=spec_n, nir_sat=ns)

    def _save_repeated_results(self):
        folder = Path(self.ui.meas_panel.save_dir_path or self.state.save_dir)
        name = self.ui.meas_panel.repeat_name.text().strip() or None

        # VIS
        if self.state.vis.repeats_buffer:
            lam = self.state.vis.repeats_buffer[0].wavelength_nm
            counts = np.column_stack([sp.counts for sp in self.state.vis.repeats_buffer])
            path = save_repeats_csv(ChannelKind.VIS, lam, counts, folder, name)
            self.log(f"[INFO] Saved VIS repeats → {path}")

        # NIR
        if self.state.nir.repeats_buffer:
            lam = self.state.nir.repeats_buffer[0].wavelength_nm
            counts = np.column_stack([sp.counts for sp in self.state.nir.repeats_buffer])
            path = save_repeats_csv(ChannelKind.NIR, lam, counts, folder, name)
            self.log(f"[INFO] Saved NIR repeats → {path}")

    # ---------------- Calibration (load/measure) ----------------

    def load_calibration(self, key: str):
        path, _ = self.parent.getOpenFileName(self.parent, f"Load calibration → {key}", "", "CSV files (*.csv)")
        if not path:
            return
        path = Path(path)
        try:
            chan, sp = load_spectrum_csv(path)
        except Exception as e:
            self.log(f"[ERROR] Failed to load calibration: {e}")
            return

        # Put into correct slot
        if chan is ChannelKind.VIS:
            entry = self.ui.meas_panel.calib_entries[key]
            entry.vis_ind.set_green()
            entry.vis_meta.setText(f"{sp.wavelength_nm.min():.2f}–{sp.wavelength_nm.max():.2f} nm")
            if key == "reference": self.state.vis.calib.reference = sp
            elif key == "dark":    self.state.vis.calib.dark = sp
            elif key == "abs":     self.state.vis.calib.abs_cal = sp
            elif key == "sample":  self.state.vis.calib.sample = sp
        else:
            entry = self.ui.meas_panel.calib_entries[key]
            entry.nir_ind.set_green()
            entry.nir_meta.setText(f"{sp.wavelength_nm.min():.2f}–{sp.wavelength_nm.max():.2f} nm")
            if key == "reference": self.state.nir.calib.reference = sp
            elif key == "dark":    self.state.nir.calib.dark = sp
            elif key == "abs":     self.state.nir.calib.abs_cal = sp
            elif key == "sample":  self.state.nir.calib.sample = sp

        self.log(f"[INFO] Loaded {chan.value} {key} → {path}")
        self.update_reflectance_plot()

    def measure_calibration(self, key: str):
        role = key  # "reference" | "dark" | "abs" | "sample"
        for kind in (ChannelKind.VIS, ChannelKind.NIR):
            d = self.devices[kind]
            ch = self.state.vis if kind is ChannelKind.VIS else self.state.nir
            if not ch.connected:
                self.log(f"[ERROR] {kind.value} not connected.")
                continue

            settings = self.ui.set_panel.get_vis() if kind is ChannelKind.VIS else self.ui.set_panel.get_nir()
            try:
                lam, spec = d.single_measurement(
                    start_pixel=settings.start_pixel,
                    stop_pixel=settings.stop_pixel,
                    exposure_ms=settings.exposure_ms,
                    n_averages=settings.n_averages,
                    trigger_mode=settings.trigger_mode
                )
                sp = Spectrum(
                    wavelength_nm=lam, counts=spec,
                    ts_iso=datetime.now().strftime(TIME_FORMAT_ISO),
                    settings_snapshot=settings,
                    serial=d.serial, role=role if role != "abs" else "abs"
                )
                # Store to calib slot
                if role == "reference": ch.calib.reference = sp
                elif role == "dark": ch.calib.dark = sp
                elif role == "abs": ch.calib.abs_cal = sp
                elif role == "sample": ch.calib.sample = sp

                # UI indicator
                entry = self.ui.meas_panel.calib_entries[key]
                meta = f"{len(lam)} px, {settings.exposure_ms:.2f} ms, {sp.ts_iso}"
                if kind is ChannelKind.VIS:
                    entry.vis_ind.set_green(); entry.vis_meta.setText(meta)
                else:
                    entry.nir_ind.set_green(); entry.nir_meta.setText(meta)

                # Save to CSV
                folder = Path(self.ui.meas_panel.save_dir_path or self.state.save_dir)
                out = save_spectrum_csv(kind, sp, folder)
                self.log(f"[INFO] Saved {kind.value} {role} → {out}")

            except Exception as e:
                entry = self.ui.meas_panel.calib_entries[key]
                if kind is ChannelKind.VIS: entry.vis_ind.set_red()
                else: entry.nir_ind.set_red()
                self.log(f"[ERROR] {kind.value} {role} measurement failed: {e}")

        self.update_reflectance_plot()

    # ---------------- Reflectance ----------------

    def update_reflectance_plot(self):
        lam_vis = refl_vis = None
        lam_nir = refl_nir = None

        # VIS
        cal = self.state.vis.calib
        if cal.is_complete_for_reflectance():
            try:
                lam_vis, refl_vis = compute_reflectance(cal.sample, cal.reference, cal.dark)
            except Exception as e:
                self.log(f"[WARNING] VIS reflectance not computed: {e}")

        # NIR
        cal = self.state.nir.calib
        if cal.is_complete_for_reflectance():
            try:
                lam_nir, refl_nir = compute_reflectance(cal.sample, cal.reference, cal.dark)
            except Exception as e:
                self.log(f"[WARNING] NIR reflectance not computed: {e}")

        self.ui.resp_panel.reflect_widget.plot_two(lam_vis=lam_vis, refl_vis=refl_vis,
                                                   lam_nir=lam_nir, refl_nir=refl_nir)

    # ---------------- Save/Load sample ----------------

    def save_results(self):
        if not self.state.vis.latest_sample and not self.state.nir.latest_sample:
            self.log("[WARNING] No sample to save.")
            return

        folder = Path(self.ui.meas_panel.save_dir_path or self.state.save_dir)
        name_base = self.ui.meas_panel.name_edit.text().strip() or None

        if self.state.vis.latest_sample is not None:
            out = save_spectrum_csv(ChannelKind.VIS, self.state.vis.latest_sample, folder, name_base)
            self.log(f"[INFO] Saved VIS sample → {out}")

        if self.state.nir.latest_sample is not None:
            out = save_spectrum_csv(ChannelKind.NIR, self.state.nir.latest_sample, folder, name_base)
            self.log(f"[INFO] Saved NIR sample → {out}")

    def load_results(self):
        path, _ = self.parent.getOpenFileName(self.parent, "Load sample", "", "CSV files (*.csv)")
        if not path:
            return
        path = Path(path)
        try:
            chan, sp = load_spectrum_csv(path)
        except Exception as e:
            self.log(f"[ERROR] Could not load CSV: {e}")
            return

        if chan is ChannelKind.VIS:
            self.state.vis.latest_sample = sp
            self.state.vis.calib.sample = sp
        else:
            self.state.nir.latest_sample = sp
            self.state.nir.calib.sample = sp

        self.log(f"[INFO] Loaded sample → {path}")

        lam_v, spec_v = (self.state.vis.latest_sample.wavelength_nm, self.state.vis.latest_sample.counts) if self.state.vis.latest_sample else (None, None)
        lam_n, spec_n = (self.state.nir.latest_sample.wavelength_nm, self.state.nir.latest_sample.counts) if self.state.nir.latest_sample else (None, None)
        vs = saturation_percent(spec_v) if spec_v is not None else None
        ns = saturation_percent(spec_n) if spec_n is not None else None
        self.ui.resp_panel.spectrum_widget.plot_two(lam_vis=lam_v, spec_vis=spec_v, vis_sat=vs,
                                                    lam_nir=lam_n, spec_nir=spec_n, nir_sat=ns)

        # Update "Sample" entry metadata quickly
        entry = self.ui.meas_panel.calib_entries["sample"]
        if chan is ChannelKind.VIS:
            entry.vis_ind.set_green()
            entry.vis_meta.setText(f"{sp.wavelength_nm.min():.2f} – {sp.wavelength_nm.max():.2f} nm")
        else:
            entry.nir_ind.set_green()
            entry.nir_meta.setText(f"{sp.wavelength_nm.min():.2f} – {sp.wavelength_nm.max():.2f} nm")

        self.update_reflectance_plot()
