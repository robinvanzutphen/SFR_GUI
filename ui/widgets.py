# ui/widgets.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox,
    QGroupBox, QTextEdit, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
import pyqtgraph as pg
import numpy as np


# ---- helper: window the spectrum to a wavelength interval -----------------
def _slice_by_wavelength(wl, y, start_nm, stop_nm):
    """Return wl,y limited to [min(start,stop), max(start,stop)]."""
    if wl is None or y is None:
        return wl, y
    if len(wl) == 0:
        return wl, y
    lo, hi = (start_nm, stop_nm) if start_nm <= stop_nm else (stop_nm, start_nm)
    wl = np.asarray(wl)
    y  = np.asarray(y)
    m = (wl >= lo) & (wl <= hi)
    if not np.any(m):
        # return empty arrays of correct dtype; plot will blank (intended)
        return wl[:0], y[:0]
    return wl[m], y[m]


# =============================================================================
# SpectrumPlotWidget (raw VIS/NIR counts)
# =============================================================================
class SpectrumPlotWidget(QWidget):
    """Raw VIS/NIR spectra with saturation legend, Y-axis controls, and compact wavelength windows."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot = pg.PlotWidget(title="Raw Spectrum")
        self.plot.setLabel('bottom', "Wavelength", units='nm')
        self.plot.setLabel('left', "Counts")
        self.plot.showGrid(x=True, y=True)
        self.legend = self.plot.addLegend()
        vb = self.plot.getViewBox()
        vb.setBorder(pg.mkPen('k', width=2))

        self.vis_curve = self.plot.plot([], [], pen=pg.mkPen('b', width=1))
        self.nir_curve = self.plot.plot([], [], pen=pg.mkPen('r', width=1))

        # --- Y-axis controls ---
        y_controls = QHBoxLayout()
        y_controls.addWidget(QLabel("Y-Max:"))
        self.y_slider = QSlider(Qt.Horizontal)
        self.y_slider.setRange(0, 20000)
        self.y_slider.setValue(16500)
        y_controls.addWidget(self.y_slider)
        self.autoscale_cb = QCheckBox("Autoscale Y-Axis")
        y_controls.addWidget(self.autoscale_cb)
        y_controls.addStretch()
        self.y_slider.valueChanged.connect(self._update_range)
        self.autoscale_cb.toggled.connect(self._toggle_autoscale)

        # --- Compact one-row wavelength controls (VIS and NIR) ---
        self.wl_group = QGroupBox("Display range (nm)")
        wl_layout = QHBoxLayout(self.wl_group)

        def _box(val):
            b = QDoubleSpinBox()
            b.setRange(200, 2500)     # safe global bounds; later clamped to data
            b.setDecimals(1)
            b.setSingleStep(1.0)
            b.setValue(val)
            b.setMaximumWidth(80)     # compact
            return b

        # VIS mini-group: "VIS: [start] – [stop]"
        self.lbl_vis = QLabel("VIS:")
        self.vis_start = _box(400.0)
        self.lbl_dash_vis = QLabel("–")
        self.vis_stop  = _box(900.0)

        # NIR mini-group: "NIR: [start] – [stop]"
        self.lbl_nir = QLabel("NIR:")
        self.nir_start = _box(900.0)
        self.lbl_dash_nir = QLabel("–")
        self.nir_stop  = _box(1700.0)

        wl_layout.addWidget(self.lbl_vis);      wl_layout.addWidget(self.vis_start)
        wl_layout.addWidget(self.lbl_dash_vis); wl_layout.addWidget(self.vis_stop)
        wl_layout.addSpacing(15)
        wl_layout.addWidget(self.lbl_nir);      wl_layout.addWidget(self.nir_start)
        wl_layout.addWidget(self.lbl_dash_nir); wl_layout.addWidget(self.nir_stop)
        wl_layout.addStretch()

        for sb in (self.vis_start, self.vis_stop, self.nir_start, self.nir_stop):
            sb.valueChanged.connect(self._on_wl_changed)

        # --- main layout ---
        lay = QVBoxLayout(self)
        lay.addWidget(self.plot)
        lay.addLayout(y_controls)
        lay.addWidget(self.wl_group)

        # cache last arrays so spinbox changes re-apply without caller involvement
        self._last_vis = (None, None, None)   # (lam_vis, spec_vis, vis_sat)
        self._last_nir = (None, None, None)   # (lam_nir, spec_nir, nir_sat)

        # persistent flags: has this channel ever had data?
        self._has_vis_data = False
        self._has_nir_data = False

        # initialize control visibility (nothing hidden up-front)
        self._set_wl_controls_visibility(False, False)

    # ---------- Y-axis handlers ----------
    def _update_range(self, v):
        if not self.autoscale_cb.isChecked():
            self.plot.setYRange(0, v)

    def _toggle_autoscale(self, checked):
        self.y_slider.setEnabled(not checked)
        if checked:
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.plot.setYRange(0, self.y_slider.value())

    # ---------- wavelength controls visibility ----------
    def _set_wl_controls_visibility(self, vis_present: bool, nir_present: bool):
        # Use persistent flags so spin changes never hide controls unexpectedly.
        vis_show = self._has_vis_data
        nir_show = self._has_nir_data
        for w in (self.lbl_vis, self.vis_start, self.lbl_dash_vis, self.vis_stop):
            w.setVisible(vis_show)
        for w in (self.lbl_nir, self.nir_start, self.lbl_dash_nir, self.nir_stop):
            w.setVisible(nir_show)

    def _on_wl_changed(self, *_):
        # Ignore changes until any data has been drawn at least once
        if not (self._has_vis_data or self._has_nir_data):
            return
        lam_vis, spec_vis, vis_sat = self._last_vis
        lam_nir, spec_nir, nir_sat = self._last_nir
        self._apply_wl_and_plot(lam_vis, spec_vis, vis_sat, lam_nir, spec_nir, nir_sat)

    # ---------- core redraw with windowing ----------
    def _apply_wl_and_plot(self,
                           lam_vis, spec_vis, vis_sat,
                           lam_nir, spec_nir, nir_sat):
        # VIS
        vis_present_now = lam_vis is not None and spec_vis is not None and len(lam_vis) > 0
        if vis_present_now:
            s, e = self.vis_start.value(), self.vis_stop.value()
            wl_v, yy_v = _slice_by_wavelength(lam_vis, spec_vis, s, e)
            self.vis_curve.setData(wl_v, yy_v)
        else:
            self.vis_curve.setData([], [])

        # NIR
        nir_present_now = lam_nir is not None and spec_nir is not None and len(lam_nir) > 0
        if nir_present_now:
            s, e = self.nir_start.value(), self.nir_stop.value()
            wl_n, yy_n = _slice_by_wavelength(lam_nir, spec_nir, s, e)
            self.nir_curve.setData(wl_n, yy_n)
        else:
            self.nir_curve.setData([], [])

        # Legend
        self.legend.clear()
        self.legend.addItem(self.vis_curve, f"VIS ({vis_sat:.1f}% sat)" if vis_sat is not None else "VIS")
        self.legend.addItem(self.nir_curve, f"NIR ({nir_sat:.1f}% sat)" if nir_sat is not None else "NIR")

        # Keep control visibility in sync with "ever had data" state
        self._set_wl_controls_visibility(self._has_vis_data, self._has_nir_data)

        if self.autoscale_cb.isChecked():
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)

    # ---------- public API ----------
    def plot_two(self,
                 lam_vis=None, spec_vis=None, vis_sat=None,
                 lam_nir=None, spec_nir=None, nir_sat=None):
        # cache inputs
        self._last_vis = (lam_vis, spec_vis, vis_sat)
        self._last_nir = (lam_nir, spec_nir, nir_sat)

        # update "ever had data" flags
        self._has_vis_data = (lam_vis is not None and spec_vis is not None and len(lam_vis) > 0) or self._has_vis_data
        self._has_nir_data = (lam_nir is not None and spec_nir is not None and len(lam_nir) > 0) or self._has_nir_data

        # optional: clamp spin ranges to actual data bounds once data is seen
        try:
            if lam_vis is not None and len(lam_vis) > 0:
                self.vis_start.setMinimum(float(np.min(lam_vis)))
                self.vis_stop.setMaximum(float(np.max(lam_vis)))
            if lam_nir is not None and len(lam_nir) > 0:
                self.nir_start.setMinimum(float(np.min(lam_nir)))
                self.nir_stop.setMaximum(float(np.max(lam_nir)))
        except Exception:
            pass

        # draw with windowing
        self._apply_wl_and_plot(lam_vis, spec_vis, vis_sat, lam_nir, spec_nir, nir_sat)


# =============================================================================
# ReflectancePlotWidget (VIS/NIR % reflectance)
# =============================================================================
class ReflectancePlotWidget(QWidget):
    """Reflectance plot for VIS and NIR with fixed lower bound, overlay, and compact wavelength windows."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot = pg.PlotWidget(title="Reflectance Spectrum")
        self.plot.setLabel('bottom', "Wavelength", units='nm')
        self.plot.setLabel('left', "Reflectance", units='%')
        self.plot.showGrid(x=True, y=True)
        self.legend = self.plot.addLegend()
        self.plot.setYRange(-20, 140)

        self.vis_curve = self.plot.plot([], [], pen=pg.mkPen('b', width=1))
        self.nir_curve = self.plot.plot([], [], pen=pg.mkPen('r', width=1))

        # --- Y-axis controls ---
        y_controls = QHBoxLayout()
        y_controls.addWidget(QLabel("Y-Max (%):"))
        self.y_slider = QSlider(Qt.Horizontal)
        self.y_slider.setRange(0, 300)
        self.y_slider.setValue(140)
        y_controls.addWidget(self.y_slider)
        self.autoscale_cb = QCheckBox("Autoscale Y-Axis")
        y_controls.addWidget(self.autoscale_cb)
        y_controls.addStretch()
        self.y_slider.valueChanged.connect(self._update_range)
        self.autoscale_cb.toggled.connect(self._toggle_autoscale)

        # --- Compact one-row wavelength controls ---
        self.wl_group = QGroupBox("Display range (nm)")
        wl_layout = QHBoxLayout(self.wl_group)

        def _box(val):
            b = QDoubleSpinBox()
            b.setRange(200, 2500)     # safe global bounds; later clamped to data
            b.setDecimals(1)
            b.setSingleStep(1.0)
            b.setValue(val)
            b.setMaximumWidth(80)
            return b

        self.lbl_vis = QLabel("VIS:")
        self.vis_start = _box(400.0)
        self.lbl_dash_vis = QLabel("–")
        self.vis_stop  = _box(900.0)

        self.lbl_nir = QLabel("NIR:")
        self.nir_start = _box(900.0)
        self.lbl_dash_nir = QLabel("–")
        self.nir_stop  = _box(1700.0)

        wl_layout.addWidget(self.lbl_vis);      wl_layout.addWidget(self.vis_start)
        wl_layout.addWidget(self.lbl_dash_vis); wl_layout.addWidget(self.vis_stop)
        wl_layout.addSpacing(15)
        wl_layout.addWidget(self.lbl_nir);      wl_layout.addWidget(self.nir_start)
        wl_layout.addWidget(self.lbl_dash_nir); wl_layout.addWidget(self.nir_stop)
        wl_layout.addStretch()

        for sb in (self.vis_start, self.vis_stop, self.nir_start, self.nir_stop):
            sb.valueChanged.connect(self._on_wl_changed)

        # --- main layout ---
        lay = QVBoxLayout(self)
        lay.addWidget(self.plot)
        lay.addLayout(y_controls)
        lay.addWidget(self.wl_group)

        self._overlay_item = None

        # caches & flags
        self._last_vis = (None, None)  # (lam_vis, refl_vis)
        self._last_nir = (None, None)  # (lam_nir, refl_nir)
        self._has_vis_data = False
        self._has_nir_data = False

        # initialize control visibility
        self._set_wl_controls_visibility(False, False)

    # ---------- Y-axis handlers ----------
    def _update_range(self, v):
        if not self.autoscale_cb.isChecked():
            self.plot.setYRange(-20, v)

    def _toggle_autoscale(self, checked):
        self.y_slider.setEnabled(not checked)
        if checked:
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.plot.setYRange(-20, self.y_slider.value())

    # ---------- overlay helpers ----------
    def _show_overlay(self, text: str):
        if self._overlay_item is not None:
            try:
                self.plot.removeItem(self._overlay_item)
            except Exception:
                pass
            self._overlay_item = None

        vb = self.plot.getViewBox()
        (x0, x1), (y0, y1) = vb.viewRange()
        x_mid = 0.5 * (x0 + x1)
        y_mid = 0.5 * (y0 + y1)

        txt = pg.TextItem(anchor=(0.5, 0.5))
        html = (
            '<div style="background-color: rgba(255,255,255,220); '
            'color: black; padding: 6px; border: 1px solid black; border-radius: 4px;">'
            f'{text}'
            '</div>'
        )
        txt.setHtml(html)
        txt.setPos(x_mid, y_mid)
        self.plot.addItem(txt)
        self._overlay_item = txt

    def clear_overlay(self):
        if self._overlay_item is not None:
            try:
                self.plot.removeItem(self._overlay_item)
            except Exception:
                pass
            self._overlay_item = None

    # ---------- wavelength controls visibility ----------
    def _set_wl_controls_visibility(self, vis_present: bool, nir_present: bool):
        # Use persistent flags so spin changes never hide controls unexpectedly.
        vis_show = self._has_vis_data
        nir_show = self._has_nir_data
        for w in (self.lbl_vis, self.vis_start, self.lbl_dash_vis, self.vis_stop):
            w.setVisible(vis_show)
        for w in (self.lbl_nir, self.nir_start, self.lbl_dash_nir, self.nir_stop):
            w.setVisible(nir_show)

    def _on_wl_changed(self, *_):
        # Ignore changes until any data has been drawn at least once
        if not (self._has_vis_data or self._has_nir_data):
            return
        lam_vis, refl_vis = self._last_vis
        lam_nir, refl_nir = self._last_nir
        self._apply_wl_and_plot(lam_vis, refl_vis, lam_nir, refl_nir)

    # ---------- core redraw with windowing ----------
    def _apply_wl_and_plot(self, lam_vis, refl_vis, lam_nir, refl_nir):
        self.clear_overlay()

        vis_present_now = lam_vis is not None and refl_vis is not None and len(lam_vis) > 0
        nir_present_now = lam_nir is not None and refl_nir is not None and len(lam_nir) > 0

        if not vis_present_now and not nir_present_now:
            self.vis_curve.setData([], [])
            self.nir_curve.setData([], [])
            self._show_overlay("No Sample or Calibration Data Available")
            # keep controls visible based on ever-seen flags
            self._set_wl_controls_visibility(self._has_vis_data, self._has_nir_data)
            return

        if vis_present_now:
            s, e = self.vis_start.value(), self.vis_stop.value()
            wl_v, rr_v = _slice_by_wavelength(lam_vis, refl_vis, s, e)
            self.vis_curve.setData(wl_v, 100.0 * rr_v)
        else:
            self.vis_curve.setData([], [])

        if nir_present_now:
            s, e = self.nir_start.value(), self.nir_stop.value()
            wl_n, rr_n = _slice_by_wavelength(lam_nir, refl_nir, s, e)
            self.nir_curve.setData(wl_n, 100.0 * rr_n)
        else:
            self.nir_curve.setData([], [])

        self.legend.clear()
        self.legend.addItem(self.vis_curve, "VIS")
        self.legend.addItem(self.nir_curve, "NIR")

        # Keep control visibility in sync with ever-seen state
        self._set_wl_controls_visibility(self._has_vis_data, self._has_nir_data)

        if self.autoscale_cb.isChecked():
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.plot.setYRange(-20, self.y_slider.value())

    # ---------- public API ----------
    def plot_two(self, lam_vis=None, refl_vis=None, lam_nir=None, refl_nir=None):
        # cache inputs
        self._last_vis = (lam_vis, refl_vis)
        self._last_nir = (lam_nir, refl_nir)

        # update "ever had data" flags
        self._has_vis_data = (lam_vis is not None and refl_vis is not None and len(lam_vis) > 0) or self._has_vis_data
        self._has_nir_data = (lam_nir is not None and refl_nir is not None and len(lam_nir) > 0) or self._has_nir_data

        # optional: clamp spin ranges to actual data bounds once data is seen
        try:
            if lam_vis is not None and len(lam_vis) > 0:
                self.vis_start.setMinimum(float(np.min(lam_vis)))
                self.vis_stop.setMaximum(float(np.max(lam_vis)))
            if lam_nir is not None and len(lam_nir) > 0:
                self.nir_start.setMinimum(float(np.min(lam_nir)))
                self.nir_stop.setMaximum(float(np.max(lam_nir)))
        except Exception:
            pass

        # draw with windowing
        self._apply_wl_and_plot(lam_vis, refl_vis, lam_nir, refl_nir)
