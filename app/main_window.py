# app/main_window.py (updated fragment)

from pathlib import Path
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QTabWidget, QFileDialog
from PyQt5.QtGui import QFont

from ui.panels import MeasurementPanel, ResponsePanel, SettingsPanel, RightPanel
from core.models import SessionState, ChannelState
from core.constants import ChannelKind
from core.devices import Spectrometer
from app.controllers import Controller


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectrometer GUI – refactored")
        self.setFont(QFont("Arial", 10))

        # Build UI
        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QHBoxLayout(central)
        self.tabs = QTabWidget()
        main_lay.addWidget(self.tabs)

        acq_tab = QWidget()
        acq_lay = QHBoxLayout(acq_tab)

        # Left: measurement & calibration
        self.meas_panel = MeasurementPanel()

        # Middle: plots only (raw + reflectance)
        self.resp_panel = ResponsePanel()

        # Right: settings + log (slightly wider)
        self.right_panel = RightPanel()

        # Add columns with stretch factors (1 | 3 | 2)
        acq_lay.addWidget(self.meas_panel, 1)
        acq_lay.addWidget(self.resp_panel, 3)
        acq_lay.addWidget(self.right_panel, 2)
        self.tabs.addTab(acq_tab, "Acquisition")

        # ---- Backward-compatibility aliases for existing controller code ----
        # Controller expects `self.set_panel` and writes logs to `self.resp_panel.log_txt`.
        # Point those to the right panel components.
        self.set_panel = self.right_panel.set_panel
        self.resp_panel.log_txt = self.right_panel.log_txt
        # --------------------------------------------------------------------

        # Session state & devices
        default_folder = Path.cwd()
        vis_state = ChannelState(kind=ChannelKind.VIS)
        nir_state = ChannelState(kind=ChannelKind.NIR)
        self.state = SessionState(save_dir=default_folder, vis=vis_state, nir=nir_state)

        self.devices = {
            ChannelKind.VIS: Spectrometer(),
            ChannelKind.NIR: Spectrometer()
        }

        # Controller
        self.ctrl = Controller(state=self.state, devices=self.devices, ui=self, parent_qobj=self)

        # Hook up UI buttons
        self._wire_buttons()

    # Proxy for QFileDialog in controller
    def getOpenFileName(self, *args, **kwargs):
        return QFileDialog.getOpenFileName(*args, **kwargs)

    def _wire_buttons(self):
        mp = self.meas_panel
        mp.setup_btn.clicked.connect(self.ctrl.setup_connections)
        mp.measure_btn.clicked.connect(self.ctrl.measure_single)
        mp.save_btn.clicked.connect(self.ctrl.save_results)
        mp.load_btn.clicked.connect(self.ctrl.load_results)
        mp.start_cont_btn.clicked.connect(self.ctrl.start_continuous)
        mp.stop_cont_btn.clicked.connect(self.ctrl.stop_continuous)
        mp.take_repeat_btn.clicked.connect(self.ctrl.start_repeated)
