from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QFrame
from PyQt5.QtCore import Qt

# shared button styles
_PRI  = "QPushButton{padding:8px 22px;font-size:13px;font-weight:500;background:#378ADD;color:#fff;border:none;border-radius:8px;min-width:80px}QPushButton:hover{background:#185FA5}QPushButton:disabled{background:#b5d4f4}"
_SEC  = "QPushButton{padding:8px 18px;font-size:13px;border:0.5px solid #d8d6d0;background:transparent;color:#4a4a47;border-radius:8px;min-width:80px}QPushButton:hover{background:#eceae4}"
_SUC  = "QPushButton{padding:8px 22px;font-size:13px;font-weight:500;background:#2E8B4A;color:#fff;border:none;border-radius:8px;min-width:80px}QPushButton:hover{background:#1D6333}"
_DNG  = "QPushButton{padding:8px 22px;font-size:13px;font-weight:500;background:#C0392B;color:#fff;border:none;border-radius:8px;min-width:80px}QPushButton:hover{background:#922B21}"
_CARD = "QFrame{background:#fff;border:0.5px solid #d8d6d0;border-radius:12px;}"
_TTL  = "font-size:15px;font-weight:500;color:#1a1a18;"
_MSG  = "font-size:13px;color:#4a4a47;line-height:1.6;"
_INP  = "QLineEdit{padding:8px 12px;font-size:13px;border:0.5px solid #c8c6c0;border-radius:8px;background:#fafaf8;color:#1a1a18;}QLineEdit:focus{border-color:#378ADD;background:#fff;}"

_ICONS = {
    "info":     ("i",  "#185FA5","#E6F1FB","#85B7EB"),
    "warning":  ("!",  "#633806","#faeeda","#EF9F27"),
    "error":    ("x",  "#A32D2D","#FCEBEB","#F09595"),
    "success":  ("ok", "#3B6D11","#EAF3DE","#97C459"),
    "question": ("?",  "#185FA5","#E6F1FB","#85B7EB"),
    "backup":   ("S",  "#3B6D11","#EAF3DE","#97C459"),
}

def _badge(kind):
    ch, fg, bg, bd = _ICONS.get(kind, _ICONS["info"])
    lbl = QLabel(ch)
    lbl.setStyleSheet(f"font-size:14px;font-weight:bold;color:{fg};background:{bg};border:0.5px solid {bd};border-radius:18px;")
    lbl.setAlignment(Qt.AlignCenter); lbl.setFixedSize(36, 36); return lbl

def _card():
    f = QFrame(); f.setStyleSheet(_CARD)
    lay = QVBoxLayout(f); lay.setContentsMargins(24,22,24,22); lay.setSpacing(12)
    return f, lay

def _base_dialog(parent, kind, title, message, ok_label="OK", btn_style=None):
    d = QDialog(parent)
    d.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
    d.setAttribute(Qt.WA_TranslucentBackground)
    d.setMinimumWidth(360); d.setMaximumWidth(500)
    outer = QVBoxLayout(d); outer.setContentsMargins(0,0,0,0)
    f, cl = _card()
    # header row
    hdr = QHBoxLayout(); hdr.setSpacing(12)
    hdr.addWidget(_badge(kind)); t = QLabel(title); t.setStyleSheet(_TTL); hdr.addWidget(t, 1)
    cl.addLayout(hdr)
    # message
    msg = QLabel(message); msg.setStyleSheet(_MSG); msg.setWordWrap(True); cl.addWidget(msg)
    # ok button
    row = QHBoxLayout(); row.addStretch()
    ok = QPushButton(ok_label); ok.setStyleSheet(btn_style or _PRI)
    ok.clicked.connect(d.accept); ok.setDefault(True); row.addWidget(ok)
    cl.addLayout(row); outer.addWidget(f)
    return d

class StyledMessageDialog(QDialog):
    def __init__(self, parent, kind, title, message, ok_label="OK"):
        super().__init__(parent)
        btn = _DNG if kind=="error" else _SUC if kind=="success" else _PRI
        d = _base_dialog(parent, kind, title, message, ok_label, btn)
        d.exec_()

class StyledQuestionDialog(QDialog):
    def __init__(self, parent, title, message, yes_label="Yes", no_label="No", show_cancel=False, kind="question"):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(380); self.setMaximumWidth(520)
        self._result = "cancel"
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        f, cl = _card()
        hdr = QHBoxLayout(); hdr.setSpacing(12)
        hdr.addWidget(_badge(kind)); t = QLabel(title); t.setStyleSheet(_TTL); hdr.addWidget(t, 1)
        cl.addLayout(hdr)
        msg = QLabel(message); msg.setStyleSheet(_MSG); msg.setWordWrap(True); cl.addWidget(msg)
        row = QHBoxLayout(); row.setSpacing(8)
        if show_cancel:
            c = QPushButton("Cancel"); c.setStyleSheet(_SEC); c.clicked.connect(self._cancel); row.addWidget(c)
        row.addStretch()
        no = QPushButton(no_label); no.setStyleSheet(_SEC); no.clicked.connect(self._no); row.addWidget(no)
        yes = QPushButton(yes_label); yes.setStyleSheet(_PRI); yes.clicked.connect(self._yes); yes.setDefault(True); row.addWidget(yes)
        cl.addLayout(row); outer.addWidget(f)

    def _yes(self):    self._result="yes";    self.accept()
    def _no(self):     self._result="no";     self.accept()
    def _cancel(self): self._result="cancel"; self.accept()
    def exec_result(self): self.exec_(); return self._result

class StyledInputDialog(QDialog):
    def __init__(self, parent, title, label, default_text="", placeholder=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(380); self._ok = False
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        f, cl = _card()
        hdr = QHBoxLayout(); hdr.setSpacing(12)
        hdr.addWidget(_badge("backup")); t = QLabel(title); t.setStyleSheet(_TTL); hdr.addWidget(t, 1)
        cl.addLayout(hdr)
        lbl = QLabel(label); lbl.setStyleSheet("font-size:13px;color:#4a4a47;font-weight:500;"); cl.addWidget(lbl)
        self.input = QLineEdit(default_text); self.input.setPlaceholderText(placeholder)
        self.input.setStyleSheet(_INP); self.input.setMinimumHeight(36)
        self.input.returnPressed.connect(self._ok_clicked); cl.addWidget(self.input)
        row = QHBoxLayout(); row.addStretch()
        cc = QPushButton("Cancel"); cc.setStyleSheet(_SEC); cc.clicked.connect(self.reject); row.addWidget(cc)
        ok = QPushButton("OK"); ok.setStyleSheet(_PRI); ok.clicked.connect(self._ok_clicked); ok.setDefault(True); row.addWidget(ok)
        cl.addLayout(row); outer.addWidget(f)

    def _ok_clicked(self): self._ok = True; self.accept()
    def exec_result(self): self.exec_(); return self.input.text(), self._ok

# convenience wrappers
def show_info(p, title, msg):    _base_dialog(p,"info",title,msg).exec_()
def show_success(p, title, msg): _base_dialog(p,"success",title,msg,"Great",_SUC).exec_()
def show_warning(p, title, msg): _base_dialog(p,"warning",title,msg).exec_()
def show_error(p, title, msg):   _base_dialog(p,"error",title,msg,"Close",_DNG).exec_()
def ask_yes_no(p, title, msg, yes_label="Yes", no_label="No"):
    return StyledQuestionDialog(p,title,msg,yes_label,no_label).exec_result()=="yes"
def ask_yes_no_cancel(p, title, msg, yes_label="Yes", no_label="No"):
    return StyledQuestionDialog(p,title,msg,yes_label,no_label,show_cancel=True).exec_result()
def ask_text(p, title, label, default_text="", placeholder=""):
    return StyledInputDialog(p,title,label,default_text,placeholder).exec_result()
