import csv
from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QLineEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from core.session import Session

TBL = """
QTableWidget{border:0.5px solid #d8d6d0;border-radius:8px;font-size:12px;background:#fff;color:#1a1a18;gridline-color:#ede}
QTableWidget::item{padding:6px 10px}QTableWidget::item:selected{background:#E6F1FB;color:#0C447C}
QHeaderView::section{background:#f5f5f3;border:none;border-bottom:0.5px solid #d8d6d0;padding:7px 10px;font-size:11px;font-weight:500;color:#6b6966}
"""

class AuditLogPanel(QWidget):
    COLS = ["Timestamp","File","Parameter","Old value","New value","Action"]

    def __init__(self, session: Session):
        super().__init__(); self.session = session; self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(24,20,24,20); lay.setSpacing(14)

        # header row
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Audit log", styleSheet="font-size:16px;font-weight:500;color:#1a1a18;")); hdr.addStretch()
        self.filter = QLineEdit(placeholderText="Filter by parameter or file…")
        self.filter.setStyleSheet("QLineEdit{padding:7px 12px;font-size:13px;border:0.5px solid #d8d6d0;border-radius:8px;background:#fff;color:#1a1a18;}QLineEdit:focus{border-color:#378ADD;}")
        self.filter.setFixedWidth(260); self.filter.textChanged.connect(self._filter); hdr.addWidget(self.filter)

        for label, style, slot in [
            ("Export CSV", "border:0.5px solid #d8d6d0;color:#4a4a47;", self._export),
            ("Clear log",  "border:0.5px solid #F09595;color:#A32D2D;", self._clear),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(f"QPushButton{{font-size:12px;padding:6px 14px;border-radius:6px;background:transparent;{style}}}QPushButton:hover{{background:#eceae4;}}")
            btn.clicked.connect(slot); hdr.addWidget(btn)
        lay.addLayout(hdr)

        self.count_chip = QLabel("0 changes recorded")
        self.count_chip.setStyleSheet("font-size:12px;color:#6b6966;padding:4px 10px;background:#f5f5f3;border-radius:6px;border:0.5px solid #d8d6d0;")
        lay.addWidget(self.count_chip)

        self.table = QTableWidget(0, len(self.COLS)); self.table.setStyleSheet(TBL)
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True); self.table.setSortingEnabled(True)
        lay.addWidget(self.table, 1)

        self.empty = QLabel("No changes recorded yet in this session.", alignment=Qt.AlignCenter,
                            styleSheet="font-size:14px;color:#a0a09a;padding:20px;")
        lay.addWidget(self.empty)

    def refresh(self):
        entries = self.session.audit_log
        self._populate(entries)
        n = len(entries)
        self.count_chip.setText(f"{n} change{'s' if n!=1 else ''} recorded")
        self.empty.setVisible(n == 0); self.table.setVisible(n > 0)

    def _populate(self, entries):
        self.table.setSortingEnabled(False); self.table.setRowCount(len(entries))
        for row, e in enumerate(reversed(entries)):
            vals = [e.get("ts",""), e.get("file",""), e.get("param",""),
                    e.get("old",""), e.get("new",""), e.get("action","edit")]
            for col, text in enumerate(vals):
                item = QTableWidgetItem(str(text))
                if col == 3: item.setForeground(QColor("#A32D2D"))
                if col == 4: item.setForeground(QColor("#3B6D11"))
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)

    def _filter(self, text):
        kw = text.strip().lower()
        data = [e for e in self.session.audit_log
                if kw in (e.get("param","") + e.get("file","") + e.get("old","") + e.get("new","")).lower()] if kw else self.session.audit_log
        self._populate(data)
        self.count_chip.setText(f"{len(data)} / {len(self.session.audit_log)} changes")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export audit log", "audit_log.csv", "CSV (*.csv)")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["ts","file","param","old","new","action"])
                w.writeheader(); w.writerows(self.session.audit_log)
            from ui.styled_dialogs import show_success
            show_success(self, "Exported", f"Audit log saved to:\n{path}")
        except Exception as e:
            from ui.styled_dialogs import show_error
            show_error(self, "Export error", str(e))

    def _clear(self):
        from ui.styled_dialogs import ask_yes_no
        if ask_yes_no(self, "Clear audit log", "Clear all records for this session? This cannot be undone."):
            self.session.audit_log.clear(); self.refresh()
