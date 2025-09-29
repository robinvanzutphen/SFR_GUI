# ui/widgets.py

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox, QGroupBox, QTextEdit
from PyQt5.QtCore import Qt
import pyqtgraph as pg

class SpectrumPlotWidget(QWidget):
    """Raw VIS/NIR spectra with saturation legend and Y-axis controls."""
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

        # Controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Y-Max:"))
        self.y_slider = QSlider(Qt.Horizontal)
        self.y_slider.setRange(0, 20000)
        self.y_slider.setValue(16500)
        controls.addWidget(self.y_slider)
        self.autoscale_cb = QCheckBox("Autoscale Y-Axis")
        controls.addWidget(self.autoscale_cb)
        controls.addStretch()

        self.y_slider.valueChanged.connect(self._update_range)
        self.autoscale_cb.toggled.connect(self._toggle_autoscale)

        lay = QVBoxLayout(self)
        lay.addWidget(self.plot)
        lay.addLayout(controls)

    def _update_range(self, v):
        if not self.autoscale_cb.isChecked():
            self.plot.setYRange(0, v)

    def _toggle_autoscale(self, checked):
        self.y_slider.setEnabled(not checked)
        if checked:
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.plot.setYRange(0, self.y_slider.value())

    def plot_two(self,
                 lam_vis=None, spec_vis=None, vis_sat=None,
                 lam_nir=None, spec_nir=None, nir_sat=None):
        if lam_vis is not None and spec_vis is not None:
            self.vis_curve.setData(lam_vis, spec_vis)
        if lam_nir is not None and spec_nir is not None:
            self.nir_curve.setData(lam_nir, spec_nir)

        self.legend.clear()
        self.legend.addItem(self.vis_curve, f"VIS ({vis_sat:.1f}% sat)" if vis_sat is not None else "VIS")
        self.legend.addItem(self.nir_curve, f"NIR ({nir_sat:.1f}% sat)" if nir_sat is not None else "NIR")

        if self.autoscale_cb.isChecked():
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)

class ReflectancePlotWidget(QWidget):
    """Reflectance plot for VIS and NIR with fixed lower bound and overlay."""
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

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Y-Max (%):"))
        self.y_slider = QSlider(Qt.Horizontal)
        self.y_slider.setRange(0, 300)
        self.y_slider.setValue(140)
        controls.addWidget(self.y_slider)
        self.autoscale_cb = QCheckBox("Autoscale Y-Axis")
        controls.addWidget(self.autoscale_cb)
        controls.addStretch()
        self.y_slider.valueChanged.connect(self._update_range)
        self.autoscale_cb.toggled.connect(self._toggle_autoscale)

        lay = QVBoxLayout(self)
        lay.addWidget(self.plot)
        lay.addLayout(controls)

        self._overlay_item = None

    def _update_range(self, v):
        if not self.autoscale_cb.isChecked():
            self.plot.setYRange(-20, v)

    def _toggle_autoscale(self, checked):
        self.y_slider.setEnabled(not checked)
        if checked:
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.plot.setYRange(-20, self.y_slider.value())

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

    def plot_two(self, lam_vis=None, refl_vis=None, lam_nir=None, refl_nir=None):
        self.clear_overlay()

        if (lam_vis is None or refl_vis is None) and (lam_nir is None or refl_nir is None):
            # clear data and show overlay
            self.vis_curve.setData([], [])
            self.nir_curve.setData([], [])
            self._show_overlay("No Sample or Calibration Data Available")
            return

        if lam_vis is not None and refl_vis is not None:
            self.vis_curve.setData(lam_vis, 100.0 * refl_vis)
        if lam_nir is not None and refl_nir is not None:
            self.nir_curve.setData(lam_nir, 100.0 * refl_nir)

        self.legend.clear()
        self.legend.addItem(self.vis_curve, "VIS")
        self.legend.addItem(self.nir_curve, "NIR")

        if self.autoscale_cb.isChecked():
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.plot.setYRange(-20, self.y_slider.value())
