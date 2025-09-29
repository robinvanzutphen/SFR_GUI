# ui/panels.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QCheckBox,
    QFileDialog, QLineEdit, QTabWidget, QFormLayout, QSpinBox, QDoubleSpinBox, QTextEdit
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from ui.widgets import SpectrumPlotWidget, ReflectancePlotWidget
from ui.indicators import IndicatorLabel

class CalibrationEntryWidget(QWidget):
    """One calibration step with Load/Measure and VIS/NIR rows."""
    ITEMS = [
        ("Reference", "reference"),
        ("Dark", "dark"),
        ("Absolute", "abs"),
        ("Sample", "sample"),
    ]

    def __init__(self, label_txt: str, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        lay = QVBoxLayout(self)

        # Header row
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel(f"{label_txt}:"))
        self.load_btn = QPushButton("Load")
        self.meas_btn = QPushButton("Measure")
        hdr.addWidget(self.load_btn)
        hdr.addWidget(self.meas_btn)
        hdr.addStretch()
        lay.addLayout(hdr)

        # VIS row
        row_v = QHBoxLayout()
        self.vis_ind = IndicatorLabel()
        row_v.addWidget(self.vis_ind)
        row_v.addWidget(QLabel("VIS:"))
        self.vis_meta = QLabel("No data")
        self.vis_meta.setFont(QFont("Arial", 8))
        row_v.addWidget(self.vis_meta)
        row_v.addStretch()
        lay.addLayout(row_v)

        # NIR row
        row_n = QHBoxLayout()
        self.nir_ind = IndicatorLabel()
        row_n.addWidget(self.nir_ind)
        row_n.addWidget(QLabel("NIR:"))
        self.nir_meta = QLabel("No data")
        self.nir_meta.setFont(QFont("Arial", 8))
        row_n.addWidget(self.nir_meta)
        row_n.addStretch()
        lay.addLayout(row_n)

class MeasurementPanel(QWidget):
    """Left column: connections, folder, single/continuous/repeated, calibration."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._save_dir_path = None
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)

        # Connection row
        conn = QHBoxLayout()
        self.setup_btn = QPushButton("Setup Connections")
        self.chk_vis = QCheckBox("Spectro VIS")
        self.chk_nir = QCheckBox("Spectro NIR")
        self.chk_vis.setEnabled(False)
        self.chk_nir.setEnabled(False)
        conn.addWidget(self.setup_btn)
        conn.addWidget(self.chk_vis)
        conn.addWidget(self.chk_nir)
        conn.addStretch()
        main.addLayout(conn)

        # Folder selector
        folder_row = QHBoxLayout()
        self.select_folder_btn = QPushButton("Select measurement folder")
        folder_row.addWidget(self.select_folder_btn)
        folder_row.addStretch()
        main.addLayout(folder_row)
        self.select_folder_btn.clicked.connect(self._choose_folder)

        # Single measurement group
        single_box = QGroupBox("Single Measurement")
        single_lay = QVBoxLayout(single_box)
        row = QHBoxLayout()
        self.measure_btn = QPushButton("Measure")
        self.save_btn = QPushButton("Save")
        self.load_btn = QPushButton("Load")
        for b in (self.measure_btn, self.save_btn, self.load_btn):
            b.setMinimumHeight(40)
            row.addWidget(b)
        row.addStretch()
        single_lay.addLayout(row)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Measurement name (optional)…")
        single_lay.addWidget(self.name_edit)
        main.addWidget(single_box)

        # Continuous acquisition
        cont_box = QGroupBox("Continuous Acquisition")
        cont_lay = QHBoxLayout(cont_box)
        self.start_cont_btn = QPushButton("Start Continuous")
        self.stop_cont_btn = QPushButton("Stop Continuous")
        for b in (self.start_cont_btn, self.stop_cont_btn):
            b.setMinimumHeight(40)
            cont_lay.addWidget(b)
        cont_lay.addStretch()
        main.addWidget(cont_box)

        # Repeated acquisition
        repeat_box = QGroupBox("Repeated Acquisition")
        form = QFormLayout(repeat_box)
        self.repeat_name = QLineEdit()
        self.repeat_name.setPlaceholderText("Name (optional)")
        self.repeat_count = QSpinBox(); self.repeat_count.setRange(1, 10000); self.repeat_count.setValue(10)
        self.repeat_interval = QDoubleSpinBox(); self.repeat_interval.setSuffix(" s"); self.repeat_interval.setRange(0.1, 3600.0); self.repeat_interval.setValue(1.0)
        form.addRow("Measurement Name:", self.repeat_name)
        form.addRow("Number of Measurements:", self.repeat_count)
        form.addRow("Interval (s):", self.repeat_interval)
        self.take_repeat_btn = QPushButton("Take Measurement")
        form.addRow(self.take_repeat_btn)
        main.addWidget(repeat_box)

        # Calibration box
        self.calib_entries = {}
        calib_box = QGroupBox("Calibration")
        v = QVBoxLayout(calib_box)
        for label_txt, key in CalibrationEntryWidget.ITEMS:
            entry = CalibrationEntryWidget(label_txt, key)
            self.calib_entries[key] = entry
            v.addWidget(entry)
        main.addWidget(calib_box)
        main.addStretch()

    def _choose_folder(self):
        from pathlib import Path
        folder = QFileDialog.getExistingDirectory(self, "Select folder for measurements")
        if folder:
            self._save_dir_path = folder
            # show only final folder name (cross-platform)
            last = Path(folder).name or folder
            self.select_folder_btn.setText(last)


    @property
    def save_dir_path(self):
        return self._save_dir_path

class ResponsePanel(QWidget):
    """Middle: spectrum plot and reflectance plot only."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        spec_box = QGroupBox("Spectrum")
        spec_lay = QVBoxLayout(spec_box)
        self.spectrum_widget = SpectrumPlotWidget()
        spec_lay.addWidget(self.spectrum_widget)
        lay.addWidget(spec_box, 1)

        refl_box = QGroupBox("Reflectance Spectrum")
        refl_lay = QVBoxLayout(refl_box)
        self.reflect_widget = ReflectancePlotWidget()
        refl_lay.addWidget(self.reflect_widget)
        lay.addWidget(refl_box, 1)
        
class RightPanel(QWidget):
    """Right column: spectrometer settings + log."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        # Settings panel
        self.set_panel = SettingsPanel()
        lay.addWidget(self.set_panel, 3)

        # Log panel
        log_box = QGroupBox("Log")
        log_lay = QVBoxLayout(log_box)
        self.log_txt = QTextEdit(); self.log_txt.setReadOnly(True)
        log_lay.addWidget(self.log_txt)
        lay.addWidget(log_box, 1)

class SpectrometerSettingsPanel(QWidget):
    """Right: all spectrometer settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)

        self.start_pix = QSpinBox(); self.start_pix.setRange(0, 4096); self.start_pix.setValue(0)
        self.stop_pix  = QSpinBox(); self.stop_pix.setRange(0, 4096); self.stop_pix.setValue(2047)
        self.exposure  = QDoubleSpinBox(); self.exposure.setRange(0.01, 10000.0); self.exposure.setSuffix(" ms"); self.exposure.setValue(1.0)
        self.n_avg     = QSpinBox(); self.n_avg.setRange(1, 1000); self.n_avg.setValue(1)
        self.cordyn    = QCheckBox("Enable")
        self.smooth_pix= QSpinBox(); self.smooth_pix.setRange(0, 100)
        self.smooth_mod= QSpinBox(); self.smooth_mod.setRange(0, 10)
        self.sat_det   = QCheckBox("Enable")
        self.trig_mode = QSpinBox(); self.trig_mode.setRange(0, 10); self.trig_mode.setValue(0)
        self.trig_src  = QSpinBox(); self.trig_src.setRange(0, 10); self.trig_src.setValue(0)
        self.trig_type = QSpinBox(); self.trig_type.setRange(0, 10); self.trig_type.setValue(0)

        form.addRow("Start Pixel:", self.start_pix)
        form.addRow("Stop Pixel:", self.stop_pix)
        form.addRow("Exposure:", self.exposure)
        form.addRow("Nr Averages:", self.n_avg)
        form.addRow("CorDynDark:", self.cordyn)
        form.addRow("Smoothing SmoothPix:", self.smooth_pix)
        form.addRow("Smoothing SmoothModel:", self.smooth_mod)
        form.addRow("Saturation Detection:", self.sat_det)
        form.addRow("Trigger Mode:", self.trig_mode)
        form.addRow("Trigger Source:", self.trig_src)
        form.addRow("Trigger Source Type:", self.trig_type)

    def get_settings(self):
        from core.models import SpectrometerSettings
        return SpectrometerSettings(
            start_pixel=self.start_pix.value(),
            stop_pixel=self.stop_pix.value(),
            exposure_ms=self.exposure.value(),
            n_averages=self.n_avg.value(),
            cordyn_dark=bool(self.cordyn.isChecked()),
            smooth_pix=self.smooth_pix.value(),
            smooth_model=self.smooth_mod.value(),
            saturation_detection=bool(self.sat_det.isChecked()),
            trigger_mode=self.trig_mode.value(),
            trigger_source=self.trig_src.value(),
            trigger_source_type=self.trig_type.value()
        )

class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        box = QGroupBox("Spectrometer Settings")
        v = QVBoxLayout(box)

        self.tabs = QTabWidget()
        self.vis_set = SpectrometerSettingsPanel()
        self.nir_set = SpectrometerSettingsPanel()
        self.tabs.addTab(self.vis_set, "VIS")
        self.tabs.addTab(self.nir_set, "NIR")
        v.addWidget(self.tabs)
        lay.addWidget(box)

    def get_vis(self):
        return self.vis_set.get_settings()

    def get_nir(self):
        return self.nir_set.get_settings()
