import sys, traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from ui.login_window import LoginWindow

def _on_exception(exc_type, value, tb):
    msg = "".join(traceback.format_exception(exc_type, value, tb))
    QMessageBox.critical(None, "Unexpected error", f"An unexpected error occurred:\n\n{msg}")
    sys.__excepthook__(exc_type, value, tb)

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Remote XML Configurator")
    app.setFont(QFont("Segoe UI", 10))
    sys.excepthook = _on_exception
    LoginWindow().show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
