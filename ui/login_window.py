from PyQt5.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFormLayout, QFrame, QSizePolicy, QSpacerItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from core.ssh_manager import SSHManager
from core.session import Session

FIELD = ("QLineEdit{padding:8px 12px;font-size:13px;border:0.5px solid #c8c6c0;"
         "border-radius:8px;background:#fafaf8;color:#1a1a18;}"
         "QLineEdit:focus{border:1.5px solid #378ADD;background:#fff;}")

class ConnectWorker(QThread):
    success = pyqtSignal(object)
    failure = pyqtSignal(str)

    def __init__(self, ip, username, password):
        super().__init__()
        self.ip, self.username, self.password = ip, username, password

    def run(self):
        try:
            ssh = SSHManager()
            ssh.connect(self.ip, self.username, self.password)
            self.success.emit(ssh)
        except Exception as e:
            self.failure.emit(str(e))

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Remote XML Configurator — Connect")
        self.setMinimumWidth(420); self.setMaximumWidth(480)
        self._worker = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # title bar
        tb = QFrame(); tb.setStyleSheet("#titleBar{background:#f5f5f3;border-bottom:1px solid #e0ded8;}")
        tb.setObjectName("titleBar")
        tbl = QHBoxLayout(tb); tbl.setContentsMargins(20,14,20,14)
        tbl.addWidget(QLabel("Remote XML Configurator", styleSheet="font-size:15px;font-weight:500;color:#1a1a18;"))
        root.addWidget(tb)

        # card
        cw = QFrame(); cl = QVBoxLayout(cw); cl.setContentsMargins(32,32,32,32)
        card = QFrame(); card.setStyleSheet("#card{background:#fff;border:0.5px solid #d0cec8;border-radius:12px;}")
        card.setObjectName("card")
        inner = QVBoxLayout(card); inner.setContentsMargins(28,28,28,28); inner.setSpacing(20)

        inner.addWidget(QLabel("Connect to edge device", styleSheet="font-size:18px;font-weight:500;color:#1a1a18;"))
        sub = QLabel("Enter SSH credentials for the remote device hosting your XML configs.")
        sub.setWordWrap(True); sub.setStyleSheet("font-size:13px;color:#6b6966;"); inner.addWidget(sub)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color:#e0ded8;"); inner.addWidget(sep)

        form = QFormLayout(); form.setSpacing(12)
        lbl = "font-size:13px;color:#4a4a47;font-weight:500;"
        self.ip_in   = QLineEdit(placeholderText="e.g. 192.168.1.45", minimumHeight=36); self.ip_in.setStyleSheet(FIELD)
        self.user_in = QLineEdit(placeholderText="username",           minimumHeight=36); self.user_in.setStyleSheet(FIELD)
        self.pass_in = QLineEdit(placeholderText="password",           minimumHeight=36); self.pass_in.setStyleSheet(FIELD)
        self.pass_in.setEchoMode(QLineEdit.Password); self.pass_in.returnPressed.connect(self._connect)

        self.eye = QPushButton("Show")
        self.eye.setCheckable(True)
        self.eye.setFixedHeight(36)
        self.eye.setStyleSheet("QPushButton{font-size:12px;padding:0 10px;border-radius:6px;border:0.5px solid #c8c6c0;background:transparent;color:#6b6966;}QPushButton:checked{color:#185FA5;border-color:#378ADD;}")
        self.eye.toggled.connect(lambda c: (self.pass_in.setEchoMode(QLineEdit.Normal if c else QLineEdit.Password), self.eye.setText("Hide" if c else "Show")))

        pw_row = QHBoxLayout(); pw_row.setSpacing(6); pw_row.addWidget(self.pass_in); pw_row.addWidget(self.eye)

        form.addRow(QLabel("IP address", styleSheet=lbl), self.ip_in)
        form.addRow(QLabel("Username",   styleSheet=lbl), self.user_in)
        form.addRow(QLabel("Password",   styleSheet=lbl), pw_row)
        inner.addLayout(form)

        self.status = QLabel("", styleSheet="font-size:12px;color:#A32D2D;", wordWrap=True); inner.addWidget(self.status)

        self.btn = QPushButton("Connect", minimumHeight=38)
        self.btn.setStyleSheet("QPushButton{font-size:14px;font-weight:500;background:#378ADD;color:#fff;border:none;border-radius:8px;}QPushButton:hover{background:#185FA5;}QPushButton:disabled{background:#b5d4f4;}")
        self.btn.clicked.connect(self._connect); inner.addWidget(self.btn)

        cl.addWidget(card); root.addWidget(cw)
        root.addItem(QSpacerItem(0,0,QSizePolicy.Minimum,QSizePolicy.Expanding))
        

    def _connect(self):
        ip = self.ip_in.text().strip(); user = self.user_in.text().strip(); pw = self.pass_in.text()
        if not all([ip, user, pw]): self.status.setText("Please fill in all fields."); return
        self.btn.setEnabled(False); self.btn.setText("Connecting…"); self.status.setText("")
        self._worker = ConnectWorker(ip, user, pw)
        self._worker.success.connect(self._on_success)
        self._worker.failure.connect(self._on_failure)
        self._worker.start()

    def _on_success(self, ssh):
        session = Session(ip=self.ip_in.text().strip(), username=self.user_in.text().strip(),
                          password=self.pass_in.text(), ssh=ssh)
        from ui.main_window import MainWindow
        self.main_window = MainWindow(session); self.main_window.show(); self.close()

    def _on_failure(self, err):
        self.btn.setEnabled(True); self.btn.setText("Connect")
        self.status.setText(f"Connection failed: {err}")
