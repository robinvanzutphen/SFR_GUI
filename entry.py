# entry.py
import sys
import os
from pathlib import Path

# --- Determine base directory (source vs frozen exe) ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = Path(sys._MEIPASS)   # runtime temp dir when frozen
else:
    BASE_DIR = Path(__file__).resolve().parent

# --- Ensure the project root is on sys.path ---
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# --- Ensure DLL search path includes our base dir ---
try:
    os.add_dll_directory(str(BASE_DIR))  # Windows 10+, safe no-op elsewhere
except Exception:
    pass

# --- UI libraries ---
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow


def main():
    # UI defaults
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')

    app = QApplication(sys.argv)
    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
