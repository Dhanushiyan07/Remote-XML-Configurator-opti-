from PyQt5.QtWidgets import QLayout
from PyQt5.QtCore import Qt, QRect, QSize, QPoint

class FlowLayout(QLayout):
    # wraps child widgets like CSS flex-wrap
    def __init__(self, parent=None, h_spacing=6, v_spacing=6):
        super().__init__(parent)
        self._items = []
        self._hs, self._vs = h_spacing, v_spacing

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(Qt.Orientation(0))
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._layout(QRect(0,0,w,0), dry=True)
    def setGeometry(self, rect): super().setGeometry(rect); self._layout(rect, dry=False)
    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for item in self._items: s = s.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left()+m.right(), m.top()+m.bottom())

    def _layout(self, rect, dry):
        l, t, r, b = self.getContentsMargins()
        eff = rect.adjusted(l, t, -r, -b)
        x, y, row_h = eff.x(), eff.y(), 0
        for item in self._items:
            iw, ih = item.sizeHint().width(), item.sizeHint().height()
            nx = x + iw + self._hs
            if nx - self._hs > eff.right() and row_h > 0:
                x = eff.x(); y += row_h + self._vs; nx = x + iw + self._hs; row_h = 0
            if not dry: item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nx; row_h = max(row_h, ih)
        return y + row_h - rect.y() + b
