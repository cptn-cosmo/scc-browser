"""Custom-painted HUD widgets."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from . import theme as T


def restyle(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)


def draw_brackets(p: QPainter, r: QRectF, length=14.0, color=None, width=1.5):
    """Small L-shaped HUD corner marks."""
    p.setPen(QPen(color or T.ACCENT, width))
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    for (x, y, dx, dy) in ((l, t, 1, 1), (rt, t, -1, 1), (rt, b, -1, -1), (l, b, 1, -1)):
        p.drawLine(QPointF(x, y), QPointF(x + dx * length, y))
        p.drawLine(QPointF(x, y), QPointF(x, y + dy * length))


def cover_pixmap(p: QPainter, pm: QPixmap, target: QRectF):
    """Draw pm scaled to cover target, centre-cropped."""
    if pm.isNull():
        return
    s = max(target.width() / pm.width(), target.height() / pm.height())
    w, h = target.width() / s, target.height() / s
    src = QRectF((pm.width() - w) / 2, (pm.height() - h) / 2, w, h)
    p.drawPixmap(target, pm, src)


def draw_no_signal(p: QPainter, r: QRectF, text="ACQUIRING SIGNAL"):
    p.fillRect(r, T.BG_2)
    p.setPen(QPen(QColor(57, 198, 244, 18), 1))
    y = r.top()
    while y < r.bottom():
        p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        y += 4
    p.setPen(T.TEXT_DIM)
    p.setFont(T.font(9, 130))
    p.drawText(r, Qt.AlignCenter, text)


class HudBackground(QWidget):
    """Deep-space gradient with a faint tactical grid."""

    def paintEvent(self, _):
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, T.BG)
        g = QRadialGradient(QPointF(r.width() * 0.25, -r.height() * 0.1), max(r.width(), r.height()) * 0.9)
        g.setColorAt(0, QColor(18, 52, 78, 170))
        g.setColorAt(0.5, QColor(8, 22, 36, 90))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(r, g)
        p.setPen(QPen(QColor(57, 198, 244, 10), 1))
        step = 48
        for x in range(0, r.width(), step):
            p.drawLine(x, 0, x, r.height())
        for y in range(0, r.height(), step):
            p.drawLine(0, y, r.width(), y)


class Divider(QWidget):
    """Thin HUD rule with an accent segment on the left."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)

    def paintEvent(self, _):
        p = QPainter(self)
        y = self.height() / 2
        p.setPen(QPen(T.LINE, 1))
        p.drawLine(QPointF(0, y), QPointF(self.width(), y))
        p.setPen(QPen(T.ACCENT, 3))
        p.drawLine(QPointF(0, y), QPointF(min(120, self.width()), y))
        p.setPen(QPen(T.ACCENT, 1))
        for i in range(4):
            x = 130 + i * 8
            p.drawLine(QPointF(x, y - 2), QPointF(x + 4, y - 2))


class CharacterCard(QWidget):
    clicked = Signal(dict)
    actionClicked = Signal(dict)

    W, H, IMG = 236, 352, 236
    CUT = 16

    def __init__(self, head: dict, api, parent=None):
        super().__init__(parent)
        self.head = head
        self.api = api
        self.pix = QPixmap()
        self.hover = False
        self.installed = False
        self.busy = False
        self.has_target = True
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

        self.btn = QPushButton(self)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setGeometry(12, self.H - 46, self.W - 24, 34)
        self.btn.clicked.connect(lambda: self.actionClicked.emit(self.head))
        self._sync_button()

        api.pixmap(head.get("previewUrl", ""), self._on_pix)

    def _on_pix(self, pm: QPixmap):
        self.pix = pm
        self.update()

    def set_state(self, installed: bool | None = None, busy: bool | None = None, has_target: bool | None = None):
        if installed is not None:
            self.installed = installed
        if busy is not None:
            self.busy = busy
        if has_target is not None:
            self.has_target = has_target
        self._sync_button()
        self.update()

    def _sync_button(self):
        b = self.btn
        if self.busy:
            b.setText("TRANSFERRING…")
            b.setProperty("variant", "primary")
            b.setEnabled(False)
        elif self.installed:
            b.setText("✓  INSTALLED")
            b.setProperty("variant", "installed")
            b.setEnabled(True)
            b.setToolTip("Click to remove from the game folder")
        else:
            b.setText("INSTALL")
            b.setProperty("variant", "primary")
            b.setEnabled(self.has_target)
            b.setToolTip("" if self.has_target else "No Star Citizen folder selected")
        restyle(b)

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.head)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = T.chamfer_path(r, self.CUT)

        p.fillPath(path, T.PANEL_HI if self.hover else T.PANEL)

        # portrait
        p.save()
        p.setClipPath(path)
        img = QRectF(0, 0, self.W, self.IMG)
        if self.pix.isNull():
            draw_no_signal(p, img)
        else:
            cover_pixmap(p, self.pix, img)
        fade = QLinearGradient(0, self.IMG * 0.55, 0, self.IMG)
        fade.setColorAt(0, QColor(0, 0, 0, 0))
        fade.setColorAt(1, T.PANEL_HI if self.hover else T.PANEL)
        p.fillRect(img, fade)
        p.restore()

        # accent strip under image
        p.setPen(QPen(T.ACCENT if self.hover else T.ACCENT_DIM, 2))
        p.drawLine(QPointF(0, self.IMG), QPointF(56, self.IMG))

        # installed badge
        if self.installed:
            badge = QRectF(self.CUT + 4, 10, 86, 20)
            p.fillRect(badge, QColor(3, 20, 14, 220))
            p.setPen(QPen(T.OK, 1))
            p.drawRect(badge)
            p.setFont(T.font(8, 115))
            p.drawText(badge, Qt.AlignCenter, "◆ INSTALLED")

        # text
        x, w = 14, self.W - 28
        p.setPen(T.TEXT)
        f = T.font(12.5, 102)
        p.setFont(f)
        title = p.fontMetrics().elidedText(self.head.get("title", "?"), Qt.ElideRight, w)
        p.drawText(QRectF(x, self.IMG + 8, w, 24), Qt.AlignLeft | Qt.AlignVCenter, title)

        user = (self.head.get("user") or {}).get("name") or "UNKNOWN"
        counts = self.head.get("_count") or {}
        stats = f"♥ {counts.get('characterLikes', 0)}   ↓ {counts.get('characterDownloads', 0)}"
        p.setFont(T.font(8.5, 112))
        stats_w = p.fontMetrics().horizontalAdvance(stats)
        p.setPen(T.ACCENT)
        p.drawText(QRectF(x, self.IMG + 32, w, 18), Qt.AlignRight | Qt.AlignVCenter, stats)
        p.setPen(T.TEXT_DIM)
        p.drawText(QRectF(x, self.IMG + 32, w - stats_w - 10, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(f"BY {user.upper()}", Qt.ElideRight, w - stats_w - 10))

        # frame
        p.setPen(QPen(T.ACCENT if self.hover else T.LINE, 1.2 if self.hover else 1))
        p.drawPath(path)
        if self.hover:
            p.setPen(QPen(T.ACCENT, 2))
            p.drawLine(QPointF(self.W - 30, 1), QPointF(self.W - 1, 1))
            p.drawLine(QPointF(self.W - 1, 1), QPointF(self.W - 1, 30))


class CardGrid(QWidget):
    """Absolute-positioned responsive grid (cheap relayout on resize)."""

    GAP = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: list[CharacterCard] = []
        self._cols = 0
        self.empty_text = ""

    def clear(self):
        for c in self.cards:
            c.deleteLater()
        self.cards = []
        self._cols = 0
        self.relayout()

    def add(self, card: CharacterCard):
        card.setParent(self)
        self.cards.append(card)
        card.show()

    def relayout(self):
        cw, ch, g = CharacterCard.W, CharacterCard.H, self.GAP
        avail = max(self.width(), cw)
        cols = max(1, (avail + g) // (cw + g))
        total_w = cols * cw + (cols - 1) * g
        x0 = (avail - total_w) // 2
        for i, c in enumerate(self.cards):
            r, col = divmod(i, cols)
            c.move(x0 + col * (cw + g), r * (ch + g))
        rows = (len(self.cards) + cols - 1) // cols
        self.setMinimumHeight(max(0, rows * (ch + g) - g) + 8)
        self.update()

    def resizeEvent(self, e):
        self.relayout()

    def paintEvent(self, _):
        if self.cards or not self.empty_text:
            return
        p = QPainter(self)
        p.setPen(T.TEXT_DIM)
        p.setFont(T.font(12, 130))
        p.drawText(self.rect().adjusted(0, 60, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self.empty_text)


class Toast(QLabel):
    COLORS = {"info": T.ACCENT, "ok": T.OK, "warn": T.WARN, "error": T.DANGER}

    def __init__(self, parent):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(T.font(10.5, 105))
        self.hide()
        self._timer = QTimer(self, singleShot=True, timeout=self.hide)

    def show_message(self, text: str, kind="info", ms=3800):
        c = self.COLORS.get(kind, T.ACCENT)
        self.setStyleSheet(
            f"background: {T.rgba(T.BG_2, 0.96)}; color: {c.name()};"
            f"border: 1px solid {c.name()}; border-left: 4px solid {c.name()}; padding: 12px 22px;"
        )
        self.setText(text)
        par = self.parentWidget()
        self.setMaximumWidth(min(720, par.width() - 40))
        self.adjustSize()
        self.move((par.width() - self.width()) // 2, par.height() - self.height() - 48)
        self.raise_()
        self.show()
        self._timer.start(ms)


class Thumb(QWidget):
    def __init__(self, size: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.pix = QPixmap()

    def set_pixmap(self, pm):
        self.pix = pm
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = T.chamfer_path(r, 8)
        p.setClipPath(path)
        if self.pix.isNull():
            draw_no_signal(p, r, "CHF")
        else:
            cover_pixmap(p, self.pix, r)
        p.setClipping(False)
        p.setPen(QPen(T.LINE, 1))
        p.drawPath(path)


class InstalledRow(QWidget):
    removeClicked = Signal(object)
    clicked = Signal(object)

    def __init__(self, item, api, parent=None):
        super().__init__(parent)
        self.item = item
        self.hover = False
        self.setAttribute(Qt.WA_Hover)
        self.setFixedHeight(84)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 16, 10)
        lay.setSpacing(16)
        self.thumb = Thumb(64)
        lay.addWidget(self.thumb)
        if item.preview_url:
            api.pixmap(item.preview_url, self.thumb.set_pixmap)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(item.title or item.path.stem)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setFont(T.font(13, 102))
        sub = QLabel(
            (f"BY {item.author.upper()}   ·   " if item.author else "")
            + item.path.name
            + ("" if item.head_id else "   ·   NOT INSTALLED BY THIS APP")
        )
        sub.setObjectName("dim")
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub.setFont(T.font(9, 110))
        text.addStretch()
        text.addWidget(title)
        text.addWidget(sub)
        text.addStretch()
        lay.addLayout(text, 1)

        rm = QPushButton("REMOVE")
        rm.setProperty("variant", "danger")
        rm.setCursor(Qt.PointingHandCursor)
        rm.clicked.connect(lambda: self.removeClicked.emit(self.item))
        lay.addWidget(rm)
        if item.head_id:
            self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.item.head_id:
            self.clicked.emit(self.item)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = T.chamfer_path(r, 10)
        p.fillPath(path, T.PANEL_HI if self.hover else T.PANEL)
        p.setPen(QPen(T.ACCENT_DIM if self.hover else T.LINE, 1))
        p.drawPath(path)
        p.setPen(QPen(T.OK if self.item.head_id else T.TEXT_DIM, 3))
        p.drawLine(QPointF(1.5, 14), QPointF(1.5, self.height() - 14))
