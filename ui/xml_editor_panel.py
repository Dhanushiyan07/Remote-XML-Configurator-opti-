import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton, QTextEdit,
    QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QScrollArea, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem,
    QFileDialog, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from core.session import Session
from core.validator import Validator
from core.xsd_parser import XSDParser
from ui.flow_layout import FlowLayout
from ui.styled_dialogs import (show_success, show_warning, show_error,
    ask_yes_no, ask_yes_no_cancel, ask_text)

# ── Styles ────────────────────────────────────────────────────────────────────
S = {
    "search":  ("QLineEdit{padding:7px 12px;font-size:13px;border:none;"
                "border-bottom:0.5px solid #d8d6d0;background:#f5f5f3;color:#1a1a18;border-radius:0;}"
                "QLineEdit:focus{border-bottom:1.5px solid #378ADD;background:#fff;}"),
    "list":    ("QListWidget{border:none;background:transparent;font-size:12px;outline:none;}"
                "QListWidget::item{padding:7px 12px;border-radius:6px;color:#4a4a47;}"
                "QListWidget::item:hover{background:#eceae4;}"
                "QListWidget::item:selected{background:#E6F1FB;color:#0C447C;font-weight:500;}"),
    "flbl":    "font-size:11px;color:#a0a09a;letter-spacing:0.05em;",
    "mono":    ("font-size:13px;font-family:monospace;color:#1a1a18;background:#f5f5f3;"
                "padding:7px 12px;border-radius:8px;border:0.5px solid #d8d6d0;"),
    "edit":    ("QLineEdit{padding:8px 12px;font-size:13px;font-family:monospace;"
                "border:0.5px solid #c8c6c0;border-left:3px solid #378ADD;"
                "border-radius:8px;background:#fff;color:#1a1a18;}"
                "QLineEdit:focus{border-color:#378ADD;}"),
    "save":    ("QPushButton{padding:8px 22px;font-size:13px;font-weight:500;"
                "background:#378ADD;color:#fff;border:none;border-radius:8px;}"
                "QPushButton:hover{background:#185FA5;}"
                "QPushButton:disabled{background:#b5d4f4;}"),
    "backup":  ("QPushButton{padding:8px 22px;font-size:13px;font-weight:500;"
                "background:#2E8B4A;color:#fff;border:none;border-radius:8px;}"
                "QPushButton:hover{background:#1D6333;}"),
    "discard": ("QPushButton{padding:8px 22px;font-size:13px;font-weight:500;"
                "background:#C0392B;color:#fff;border:none;border-radius:8px;}"
                "QPushButton:hover{background:#922B21;}"),
    "xml":     "QTextEdit{font-family:monospace;font-size:12px;background:#1e1e1e;color:#d4d4d4;border:none;padding:10px;}",
    "diff":    ("QTextEdit{font-family:monospace;font-size:12px;background:#f5f5f3;"
                "color:#1a1a18;border:0.5px solid #d8d6d0;border-radius:8px;padding:8px;}"),
}

CHIPS = {
    "type":     "background:#E6F1FB;color:#185FA5;border:0.5px solid #85B7EB;",
    "required": "background:#FCEBEB;color:#A32D2D;border:0.5px solid #F09595;",
    "optional": "background:#f5f5f3;color:#6b6966;border:0.5px solid #d8d6d0;",
    "xsd":      "background:#EAF3DE;color:#3B6D11;border:0.5px solid #97C459;",
    "range":    "background:#faeeda;color:#633806;border:0.5px solid #EF9F27;",
    "fixed":    "background:#FBEAF0;color:#72243E;border:0.5px solid #ED93B1;",
}


# ── Background workers ─────────────────────────────────────────────────────────
class FileLoader(QThread):
    done  = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, session, filename):
        super().__init__()
        self.session = session
        self.filename = filename

    def run(self):
        try:
            f = self.session.ssh.sftp.open(self.session.remote_path(self.filename))
            content = f.read().decode(); f.close()
            xsd = ""
            try:
                xf = self.session.ssh.sftp.open(
                    self.session.remote_path(self.filename.replace(".xml", ".xsd")))
                xsd = xf.read().decode(); xf.close()
            except Exception:
                pass
            self.done.emit(content, xsd)
        except Exception as e:
            self.error.emit(str(e))


class FileSaver(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, session, filename, xml_data, backup_name=None):
        super().__init__()
        self.session = session
        self.filename = filename
        self.xml_data = xml_data
        self.backup_name = backup_name

    def run(self):
        try:
            if self.backup_name:
                bf = self.session.ssh.sftp.open(
                    self.session.remote_path(self.backup_name), "w")
                bf.write(self.xml_data); bf.close()
            f = self.session.ssh.sftp.open(
                self.session.remote_path(self.filename), "w")
            f.write(self.xml_data); f.close()
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Main panel ────────────────────────────────────────────────────────────────
class XmlEditorPanel(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.validator = Validator()
        self.xsd_parser = XSDParser()
        self.root = None
        self.params = {}
        self.rules = {}
        self.validation_source = "None"
        self.selected = None
        self.current_val = ""
        self._input_widget = None   # the actual QLineEdit/QComboBox/etc (NOT the container)

        # debounce timer — prevents diff re-rendering on every keystroke
        self._diff_timer = QTimer()
        self._diff_timer.setSingleShot(True)
        self._diff_timer.setInterval(200)
        self._diff_timer.timeout.connect(self._do_diff)

        self._build()
        self._show_placeholder()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet("QSplitter::handle{background:#d8d6d0;}")
        split.setChildrenCollapsible(False)

        # ── Left panel: parameter list ─────────────────────────────────
        left = QFrame()
        left.setStyleSheet("QFrame{background:#f5f5f3;border:none;}")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search parameters…")
        self.search.setStyleSheet(S["search"])
        self.search.setMinimumHeight(38)
        self.search.textChanged.connect(self._filter)
        ll.addWidget(self.search)

        self.param_list = QListWidget()
        self.param_list.setStyleSheet(S["list"])
        self.param_list.itemClicked.connect(self._select)
        ll.addWidget(self.param_list, 1)

        self.count_lbl = QLabel("No file loaded")
        self.count_lbl.setStyleSheet("font-size:11px;color:#a0a09a;padding:6px 12px;")
        ll.addWidget(self.count_lbl)
        split.addWidget(left)

        # ── Right panel: XML source + edit form ────────────────────────
        right = QFrame()
        right.setStyleSheet("QFrame{background:#ffffff;border:none;}")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        vsplit = QSplitter(Qt.Vertical)
        vsplit.setHandleWidth(1)
        vsplit.setStyleSheet("QSplitter::handle{background:#d8d6d0;}")

        # dark XML source view (read-only)
        self.xml_view = QTextEdit()
        self.xml_view.setReadOnly(True)
        self.xml_view.setStyleSheet(S["xml"])
        self.xml_view.setMaximumHeight(180)
        self.xml_view.setPlaceholderText("Open a file to see XML source here.")
        vsplit.addWidget(self.xml_view)

        # scrollable edit area — this container stays alive permanently
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#ffffff;}")

        self._form_container = QWidget()           # permanent container, never replaced
        self._form_container.setStyleSheet("QWidget{background:#ffffff;}")
        self._form_layout = QVBoxLayout(self._form_container)
        self._form_layout.setContentsMargins(24, 20, 24, 20)
        self._form_layout.setSpacing(16)

        scroll.setWidget(self._form_container)
        vsplit.addWidget(scroll)
        vsplit.setStretchFactor(0, 1)
        vsplit.setStretchFactor(1, 3)

        rl.addWidget(vsplit, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setSizes([280, 720])
        outer.addWidget(split)

    # ── Form helpers ───────────────────────────────────────────────────────────

    def _clear_form(self):
        """Remove all widgets from the form layout without touching the container."""
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # clear sub-layouts too
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        self._input_widget = None
        self.diff_view = None

    def _show_placeholder(self):
        self._clear_form()
        lbl = QLabel("Select a parameter from the list to edit it.")
        lbl.setStyleSheet("font-size:14px;color:#a0a09a;")
        lbl.setAlignment(Qt.AlignCenter)
        self._form_layout.addStretch()
        self._form_layout.addWidget(lbl)
        self._form_layout.addStretch()

    def _chip(self, text, kind):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size:11px;padding:3px 9px;border-radius:6px;"
            + CHIPS.get(kind, CHIPS["optional"]))
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return lbl

    # ── File loading ───────────────────────────────────────────────────────────

    def load_file(self, filename):
        self.param_list.clear()
        self.params.clear()
        self.rules.clear()
        self.selected = None
        self.count_lbl.setText("Loading…")
        self._show_placeholder()
        self.xml_view.setPlainText("")

        self._loader = FileLoader(self.session, filename)
        self._loader.done.connect(lambda c, x: self._on_loaded(filename, c, x))
        self._loader.error.connect(
            lambda e: (show_error(self, "Load Error", e),
                       self.count_lbl.setText("Load failed")))
        self._loader.start()

    def _on_loaded(self, filename, content, xsd_content):
        self.xml_view.setPlainText(content)
        try:
            self.root = ET.fromstring(content)
        except ET.ParseError as e:
            show_error(self, "XML Parse Error", str(e))
            return

        self.params.clear()
        self._extract(self.root)

        if xsd_content:
            self.rules = self.xsd_parser.load_types(xsd_content)
            self.validation_source = filename.replace(".xml", ".xsd")
        else:
            self.rules = {}
            self.validation_source = "Inferred"
            if ask_yes_no(self, "No XSD Found",
                          f"No matching XSD for {filename}.\nLoad one manually?",
                          yes_label="Browse…", no_label="Skip"):
                path, _ = QFileDialog.getOpenFileName(
                    self, "Select XSD file", "", "XSD files (*.xsd)")
                if path:
                    with open(path, "r", encoding="utf-8") as fh:
                        self.rules = self.xsd_parser.load_types(fh.read())
                    self.validation_source = path.replace("\\", "/").split("/")[-1]

        self._populate(sorted(self.params.keys()))
        self.count_lbl.setText(f"{len(self.params)} parameters")

    def _extract(self, el, path=""):
        cur = (path + "." + el.tag) if path else el.tag
        for attr in el.attrib:
            self.params[cur + ".@" + attr] = (el, attr)
        if el.text and el.text.strip():
            self.params[cur] = (el, None)
        counts = {}
        for child in el:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            self._extract(child, f"{cur}.{child.tag}[{counts[child.tag]}]")

    # ── Parameter list ─────────────────────────────────────────────────────────

    def _populate(self, keys):
        self.param_list.clear()
        for key in keys:
            item = QListWidgetItem(key)
            tag = key.split(".")[-1]
            rule = self.rules.get(tag, {})
            dtype = rule.get("type", self.validator.infer_type(
                self._get_stored_val(*self.params[key])))
            item.setToolTip(f"Type: {dtype}")
            self.param_list.addItem(item)

    def _filter(self, text):
        kw = text.strip().lower()
        matches = [k for k in sorted(self.params.keys()) if kw in k.lower()]
        self._populate(matches)
        self.count_lbl.setText(f"{len(matches)} / {len(self.params)}")

    def _get_stored_val(self, el, attr):
        """Get value directly from the XML element (not from the input widget)."""
        return el.attrib.get(attr, "") if attr else (el.text.strip() if el.text else "")

    # ── Parameter selection & form build ──────────────────────────────────────

    def _select(self, item):
        tag = item.text()
        if tag not in self.params:
            return
        self.selected = tag
        el, attr = self.params[tag]
        self.current_val = self._get_stored_val(el, attr)
        tag_name = tag.split(".")[-1]
        rule = self.rules.get(tag_name, {})
        dtype = rule.get("type") or self.validator.infer_type(self.current_val)
        self._build_form(tag, self.current_val, rule, dtype)

    def _build_form(self, tag, value, rule, dtype):
        self._clear_form()

        # parameter path label
        path_lbl = QLabel(tag)
        path_lbl.setStyleSheet(
            "font-size:14px;font-weight:500;color:#1a1a18;"
            "padding-bottom:4px;border-bottom:0.5px solid #e0ded8;")
        path_lbl.setWordWrap(True)
        self._form_layout.addWidget(path_lbl)

        # chips row (wraps with FlowLayout)
        chip_container = QWidget()
        chip_container.setStyleSheet("QWidget{background:#ffffff;}")
        flow = FlowLayout(chip_container, h_spacing=6, v_spacing=5)
        flow.addWidget(self._chip(dtype, "type"))
        flow.addWidget(self._chip(
            "required" if rule.get("required") else "optional",
            "required" if rule.get("required") else "optional"))
        if "fixed" in rule:
            flow.addWidget(self._chip("fixed value", "fixed"))
        if "min" in rule or "max" in rule:
            flow.addWidget(self._chip(
                f"range: {rule.get('min','–')} – {rule.get('max','–')}", "range"))
        if "enum" in rule:
            flow.addWidget(self._chip(f"{len(rule['enum'])} allowed values", "type"))
        if "minLength" in rule or "maxLength" in rule:
            flow.addWidget(self._chip(
                f"length: {rule.get('minLength','–')}–{rule.get('maxLength','–')}", "range"))
        if "default" in rule:
            flow.addWidget(self._chip(f"default: {rule['default']}", "optional"))
        flow.addWidget(self._chip(f"XSD: {self.validation_source}", "xsd"))
        self._form_layout.addWidget(chip_container)

        # current value display
        self._form_layout.addWidget(QLabel("Current value", styleSheet=S["flbl"]))
        cur_val_lbl = QLabel(value if value else "(empty)")
        cur_val_lbl.setStyleSheet(S["mono"])
        cur_val_lbl.setWordWrap(True)
        self._form_layout.addWidget(cur_val_lbl)

        # type-specific input widget
        self._form_layout.addWidget(QLabel("New value", styleSheet=S["flbl"]))
        dt = str(dtype).lower()
        is_fixed = "fixed" in rule

        if "bool" in dt:
            w = QCheckBox("Enabled")
            w.setChecked(value.lower() in ("true", "1"))
            w.setEnabled(not is_fixed)
            w.stateChanged.connect(self._schedule_diff)
        elif "enum" in rule:
            w = QComboBox()
            w.setStyleSheet(
                "QComboBox{padding:7px 12px;font-size:13px;"
                "border:0.5px solid #c8c6c0;border-radius:8px;"
                "background:#fff;color:#1a1a18;}")
            w.addItems(rule["enum"])
            if value in rule["enum"]:
                w.setCurrentText(value)
            w.setEnabled(not is_fixed)
            w.currentTextChanged.connect(self._schedule_diff)
        elif "int" in dt or "integer" in dt:
            w = QSpinBox()
            w.setStyleSheet(
                "QSpinBox{padding:7px 12px;font-size:13px;"
                "border:0.5px solid #c8c6c0;border-radius:8px;background:#fff;}")
            w.setRange(int(rule.get("min", -2147483648)), int(rule.get("max", 2147483647)))
            try: w.setValue(int(value))
            except: pass
            w.setEnabled(not is_fixed)
            w.valueChanged.connect(self._schedule_diff)
        elif dt in ("float", "double", "decimal"):
            w = QDoubleSpinBox()
            w.setStyleSheet(
                "QDoubleSpinBox{padding:7px 12px;font-size:13px;"
                "border:0.5px solid #c8c6c0;border-radius:8px;background:#fff;}")
            w.setDecimals(4)
            w.setRange(float(rule.get("min", -1e9)), float(rule.get("max", 1e9)))
            try: w.setValue(float(value))
            except: pass
            w.setEnabled(not is_fixed)
            w.valueChanged.connect(self._schedule_diff)
        else:
            w = QLineEdit()
            w.setStyleSheet(S["edit"])
            w.setText(value)
            w.setEnabled(not is_fixed)
            if "pattern" in rule:
                w.setPlaceholderText(f"pattern: {rule['pattern']}")
            w.textChanged.connect(self._schedule_diff)

        w.setMinimumHeight(36)
        self._input_widget = w          # store input widget separately from container
        self._form_layout.addWidget(w)

        # diff preview
        self._form_layout.addWidget(QLabel("Change preview", styleSheet=S["flbl"]))
        self.diff_view = QTextEdit()
        self.diff_view.setStyleSheet(S["diff"])
        self.diff_view.setReadOnly(True)
        self.diff_view.setMaximumHeight(60)
        self._render_diff(value, value)
        self._form_layout.addWidget(self.diff_view)

        # action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.save_btn = QPushButton("Save to device")
        self.save_btn.setStyleSheet(S["save"])
        self.save_btn.setMinimumHeight(36)
        self.save_btn.clicked.connect(self._save)
        bk_btn = QPushButton("Create backup")
        bk_btn.setStyleSheet(S["backup"])
        bk_btn.setMinimumHeight(36)
        bk_btn.clicked.connect(self._backup_only)
        dc_btn = QPushButton("Discard")
        dc_btn.setStyleSheet(S["discard"])
        dc_btn.setMinimumHeight(36)
        dc_btn.clicked.connect(
            lambda: self._select(self.param_list.currentItem())
            if self.param_list.currentItem() else None)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(bk_btn)
        btn_row.addWidget(dc_btn)
        btn_row.addStretch()
        self._form_layout.addLayout(btn_row)
        self._form_layout.addStretch()

    # ── Diff preview ───────────────────────────────────────────────────────────

    def _schedule_diff(self, *_):
        """Debounce diff updates — wait 200ms after last keystroke."""
        self._diff_timer.start()

    def _do_diff(self):
        self._render_diff(self.current_val, self._get_input_val())

    def _render_diff(self, old, new):
        if self.diff_view is None:
            return
        tag = (self.selected or "value").split(".")[-1].replace("@", "")
        old_line = f'<font color="#E24B4A">- &lt;{tag}&gt;{old}&lt;/{tag}&gt;</font>'
        new_line = f'<font color="#639922">+ &lt;{tag}&gt;{new}&lt;/{tag}&gt;</font>'
        self.diff_view.setHtml(
            f'<pre style="font-family:monospace;font-size:12px;margin:0">'
            f'{old_line}<br>{new_line}</pre>')

    # ── Input value reader ─────────────────────────────────────────────────────

    def _get_input_val(self):
        """Read current value from the active input widget."""
        w = self._input_widget
        if isinstance(w, QCheckBox):      return "true" if w.isChecked() else "false"
        if isinstance(w, QComboBox):      return w.currentText()
        if isinstance(w, QSpinBox):       return str(w.value())
        if isinstance(w, QDoubleSpinBox): return str(w.value())
        if isinstance(w, QLineEdit):      return w.text()
        return ""

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save(self):
        if not self.selected or not self.root:
            return
        el, attr = self.params[self.selected]
        tag_name = self.selected.split(".")[-1]
        rule = self.rules.get(tag_name, {})

        if "fixed" in rule:
            show_warning(self, "Fixed Value",
                         "This value is fixed by XSD and cannot be changed.")
            return

        new_val = self._get_input_val()
        ok, msg = self.validator.validate(rule, new_val)
        if not ok:
            show_warning(self, "Validation Error", msg)
            return

        backup_name = None
        result = ask_yes_no_cancel(
            self, "Backup Before Save",
            "Create a backup before saving?",
            yes_label="Yes, backup", no_label="No, just save")
        if result == "cancel":
            return
        if result == "yes":
            default = self.session.active_file.replace(".xml", "_backup.xml")
            name, confirmed = ask_text(
                self, "Create Backup", "Backup file name:", default_text=default)
            if confirmed and name.strip():
                backup_name = name.strip()
                if not backup_name.endswith(".xml"):
                    backup_name += ".xml"

        old_val = self.current_val
        if attr: el.attrib[attr] = new_val
        else:    el.text = new_val
        xml_data = ET.tostring(self.root, encoding="unicode")

        self.save_btn.setEnabled(False)
        self.save_btn.setText("Saving…")
        self._saver = FileSaver(
            self.session, self.session.active_file, xml_data, backup_name)
        self._saver.done.connect(lambda: self._on_saved(old_val, new_val, xml_data))
        self._saver.error.connect(self._on_save_err)
        self._saver.start()

    def _on_saved(self, old, new, xml_data):
        self.session.log("edit", self.selected, old, new)
        self.current_val = new
        self.xml_view.setPlainText(xml_data)
        self._render_diff(new, new)
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save to device")
        show_success(self, "Saved", "XML saved successfully to the device.")

    def _on_save_err(self, e):
        show_error(self, "Save Error", e)
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save to device")

    def _backup_only(self):
        if not self.session.active_file or not self.root:
            return
        default = self.session.active_file.replace(".xml", "_backup.xml")
        name, ok = ask_text(
            self, "Create Backup", "Backup file name:", default_text=default)
        if not ok or not name.strip():
            return
        backup_name = name.strip()
        if not backup_name.endswith(".xml"):
            backup_name += ".xml"
        xml_data = ET.tostring(self.root, encoding="unicode")
        self._saver = FileSaver(
            self.session, self.session.active_file, xml_data, backup_name)
        self._saver.done.connect(
            lambda: show_success(self, "Backup Created", f"Backup saved as {backup_name}."))
        self._saver.error.connect(lambda e: show_error(self, "Backup Error", e))
        self._saver.start()
