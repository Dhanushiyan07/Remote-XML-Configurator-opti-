from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QTabWidget, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from core.session import Session
from ui.xml_editor_panel import XmlEditorPanel
from ui.device_monitor_panel import DeviceMonitorPanel
from ui.audit_log_panel import AuditLogPanel

SIDEBAR = "QFrame#sidebar{background:#f5f5f3;border-right:0.5px solid #d8d6d0;}"
NAV_BTN = ("QPushButton{text-align:left;padding:8px 12px;border:none;border-radius:8px;"
           "font-size:13px;color:#5f5e5a;background:transparent;}"
           "QPushButton:hover{background:#eceae4;color:#1a1a18;}"
           "QPushButton:checked{background:#fff;color:#1a1a18;font-weight:500;border:0.5px solid #d8d6d0;}")
FILE_BTN= ("QPushButton{text-align:left;padding:7px 10px;border:none;border-radius:6px;"
           "font-size:12px;color:#5f5e5a;background:transparent;}"
           "QPushButton:hover{background:#eceae4;}"
           "QPushButton:checked{background:#E6F1FB;color:#185FA5;font-weight:500;}")
TABS    = ("QTabWidget::pane{border:none;border-top:0.5px solid #d8d6d0;}"
           "QTabBar::tab{padding:10px 18px;font-size:13px;color:#6b6966;border:none;"
           "background:transparent;border-bottom:2px solid transparent;}"
           "QTabBar::tab:selected{color:#1a1a18;font-weight:500;border-bottom:2px solid #378ADD;}"
           "QTabBar::tab:hover{color:#1a1a18;}")

class FileListWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)
    def __init__(self, session): super().__init__(); self.session = session
    def run(self):
        try:
            files = sorted(f for f in self.session.ssh.sftp.listdir(self.session.REMOTE_DIR)
                           if f.lower().endswith(".xml"))
            self.done.emit(files)
        except Exception as e: self.error.emit(str(e))

class MainWindow(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.setWindowTitle(f"Remote XML Configurator — {session.ip}")
        self.resize(1280, 800); self.setMinimumSize(960, 600)
        self._file_btns = []; self._active_btn = None
        self._build()
        self._load_files()
        self._perf_timer = QTimer(self)
        self._perf_timer.timeout.connect(self._update_perf)
        self._perf_timer.start(8000)

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._title_bar())
        body = QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        body.addWidget(self._sidebar())
        self.tabs = QTabWidget(); self.tabs.setStyleSheet(TABS); self.tabs.setDocumentMode(True)
        self.editor  = XmlEditorPanel(self.session)
        self.monitor = DeviceMonitorPanel(self.session)
        self.audit   = AuditLogPanel(self.session)
        self.tabs.addTab(self.editor,  "XML editor")
        self.tabs.addTab(self.monitor, "Device monitor")
        self.tabs.addTab(self.audit,   "Audit log")
        self.tabs.currentChanged.connect(self._on_tab)
        body.addWidget(self.tabs, 1); root.addLayout(body, 1)
        root.addWidget(self._status_bar())

    def _title_bar(self):
        bar = QFrame(); bar.setObjectName("titleBar")
        bar.setStyleSheet("QFrame#titleBar{background:#f5f5f3;border-bottom:0.5px solid #d8d6d0;}")
        bar.setFixedHeight(52)
        lay = QHBoxLayout(bar); lay.setContentsMargins(20,0,20,0)
        lay.addWidget(QLabel("Remote XML Configurator", styleSheet="font-size:15px;font-weight:500;color:#1a1a18;"))
        lay.addStretch()
        badge = QLabel(f"  {self.session.ip} connected  ")
        badge.setStyleSheet("font-size:12px;padding:4px 12px;border-radius:8px;background:#eaf3de;color:#3B6D11;border:0.5px solid #97C459;")
        lay.addWidget(badge)
        disc = QPushButton("Disconnect")
        disc.setStyleSheet("QPushButton{font-size:12px;padding:5px 14px;border-radius:6px;border:0.5px solid #d8d6d0;background:transparent;color:#6b6966;}QPushButton:hover{color:#A32D2D;border-color:#F09595;}")
        disc.clicked.connect(self._disconnect); lay.addWidget(disc)
        return bar

    def _sidebar(self):
        sb = QFrame(); sb.setObjectName("sidebar"); sb.setStyleSheet(SIDEBAR); sb.setFixedWidth(200)
        lay = QVBoxLayout(sb); lay.setContentsMargins(10,14,10,14); lay.setSpacing(2)
        lay.addWidget(self._sect("Files"))
        self.file_container = QVBoxLayout(); self.file_container.setSpacing(2); lay.addLayout(self.file_container)
        self.loading_lbl = QLabel("Loading files…", styleSheet="font-size:12px;color:#a0a09a;padding:6px 10px;")
        self.file_container.addWidget(self.loading_lbl)
        lay.addSpacing(10); lay.addWidget(self._sect("Device"))
        m_btn = self._nav("Device monitor"); m_btn.clicked.connect(lambda: self.tabs.setCurrentWidget(self.monitor)); lay.addWidget(m_btn)
        a_btn = self._nav("Audit log");      a_btn.clicked.connect(lambda: self.tabs.setCurrentWidget(self.audit));   lay.addWidget(a_btn)
        lay.addSpacing(10); lay.addWidget(self._sect("Files"))
        r_btn = self._nav("Refresh list");   r_btn.clicked.connect(self._load_files); lay.addWidget(r_btn)
        lay.addStretch(); return sb

    def _status_bar(self):
        bar = QFrame(); bar.setObjectName("statusBar")
        bar.setStyleSheet("QFrame#statusBar{background:#f5f5f3;border-top:0.5px solid #d8d6d0;}")
        bar.setFixedHeight(32)
        lay = QHBoxLayout(bar); lay.setContentsMargins(16,0,16,0)
        self.conn_lbl = QLabel(f"Connected · {self.session.ip}", styleSheet="font-size:11px;color:#3B6D11;"); lay.addWidget(self.conn_lbl)
        sep = QFrame(); sep.setFrameShape(QFrame.VLine); sep.setStyleSheet("color:#d8d6d0;"); lay.addWidget(sep)
        self.file_lbl = QLabel("No file open", styleSheet="font-size:11px;color:#6b6966;"); lay.addWidget(self.file_lbl)
        lay.addStretch()
        self.perf_lbl = QLabel("CPU – · RAM –", styleSheet="font-size:11px;color:#6b6966;"); lay.addWidget(self.perf_lbl)
        return bar

    def _sect(self, text):
        return QLabel(text.upper(), styleSheet="font-size:10px;color:#a0a09a;letter-spacing:0.06em;padding:6px 10px 3px;")

    def _nav(self, text):
        btn = QPushButton(f"  {text}"); btn.setStyleSheet(NAV_BTN)
        btn.setCheckable(True); btn.setMinimumHeight(34); return btn

    def _load_files(self):
        for btn in self._file_btns: btn.setParent(None)
        self._file_btns.clear(); self._active_btn = None; self.loading_lbl.show()
        w = FileListWorker(self.session)
        w.done.connect(self._on_files); w.error.connect(self._on_file_err); w.start()
        self._fw = w

    def _on_files(self, files):
        self.loading_lbl.hide()
        for f in files:
            btn = QPushButton(f); btn.setStyleSheet(FILE_BTN)
            btn.setCheckable(True); btn.setMinimumHeight(30)
            btn.clicked.connect(lambda _, fn=f, b=btn: self._open(fn, b))
            self.file_container.addWidget(btn); self._file_btns.append(btn)

    def _on_file_err(self, msg):
        self.loading_lbl.setText("Load error"); QMessageBox.critical(self, "File list error", msg)

    def _open(self, filename, btn):
        if self._active_btn: self._active_btn.setChecked(False)
        self._active_btn = btn; btn.setChecked(True)
        self.session.active_file = filename
        self.file_lbl.setText(filename); self.editor.load_file(filename)
        self.tabs.setCurrentWidget(self.editor)

    def _on_tab(self, index):
        widget = self.tabs.widget(index)
        if widget is self.monitor: self.monitor.start_polling()
        else: self.monitor.stop_polling()
        if widget is self.audit: self.audit.refresh()

    def _update_perf(self):
        # use cached values from monitor panel first (no SSH call needed)
        try:
            mp = self.monitor
            if hasattr(mp, "_last_cpu") and mp._last_cpu is not None:
                self.perf_lbl.setText(f"CPU {mp._last_cpu:.0f}%  · RAM {mp._last_ram_pct:.0f}%"); return
        except Exception: pass
        # fallback: quick SSH poll, works on both Windows and Linux
        try:
            ssh = self.session.ssh.ssh
            hint = ssh.exec_command("ver 2>nul || echo linux", timeout=4)[1].read().decode().lower()
            if "windows" in hint or "microsoft" in hint:
                raw = ssh.exec_command('powershell -NoProfile -Command "(Get-Counter \'\\Processor(_Total)\\% Processor Time\' -SampleInterval 1 -MaxSamples 1).CounterSamples[0].CookedValue"', timeout=6)[1].read().decode().replace(",",".")
                cpu = 0.0
                for tok in raw.split():
                    try: cpu = float(tok); break
                    except: pass
                mem_r = ssh.exec_command('powershell -NoProfile -Command "$o=Get-CimInstance Win32_OperatingSystem 2>$null;if($o){Write-Output ($o.TotalVisibleMemorySize.ToString()+\' \'+$o.FreePhysicalMemory.ToString())}"', timeout=6)[1].read().decode().strip().split()
                ram = (int(mem_r[0])-int(mem_r[1]))*100/int(mem_r[0]) if len(mem_r)>=2 else 0
            else:
                cpu = float(ssh.exec_command("grep 'cpu ' /proc/stat|awk '{u=$2+$4;t=$2+$3+$4+$5;printf \"%.0f\",u/t*100}'", timeout=4)[1].read().decode() or 0)
                ram = float(ssh.exec_command("awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf \"%.0f\",(t-a)*100/t}' /proc/meminfo", timeout=4)[1].read().decode() or 0)
            self.perf_lbl.setText(f"CPU {cpu:.0f}%  · RAM {ram:.0f}%")
        except Exception: pass

    def _disconnect(self):
        if QMessageBox.question(self,"Disconnect","Disconnect from device and return to login?",
                                QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.monitor.stop_polling(); self.session.disconnect()
            from ui.login_window import LoginWindow
            self.login = LoginWindow(); self.login.show(); self.close()

    def closeEvent(self, e):
        self.monitor.stop_polling(); self.session.disconnect(); e.accept()
