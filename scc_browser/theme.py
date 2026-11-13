"""Star Citizen / mobiGlas inspired look: deep space navy, cyan HUD lines, chamfered panels."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainterPath

ASSETS = Path(__file__).with_name("assets")

BG = QColor("#03070c")
BG_2 = QColor("#081420")
PANEL = QColor(10, 26, 40, 225)
PANEL_HI = QColor(16, 40, 60, 235)
LINE = QColor("#1b4560")
ACCENT = QColor("#39c6f4")
ACCENT_DIM = QColor("#1c6f90")
ACCENT_GLOW = QColor(57, 198, 244, 60)
TEXT = QColor("#d4ecf7")
TEXT_DIM = QColor("#6f91a3")
OK = QColor("#46e3a4")
WARN = QColor("#f2a531")
DANGER = QColor("#ff5c4d")

FONT_FAMILY = "Electrolize"


def load_fonts() -> str:
    fid = QFontDatabase.addApplicationFont(str(ASSETS / "Electrolize-Regular.ttf"))
    fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    global FONT_FAMILY
    FONT_FAMILY = fams[0] if fams else "Sans Serif"
    return FONT_FAMILY


def font(pt: float, spacing: float = 100, bold=False) -> QFont:
    f = QFont(FONT_FAMILY)
    f.setPointSizeF(pt)
    f.setLetterSpacing(QFont.PercentageSpacing, spacing)
    f.setBold(bold)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def chamfer_path(r: QRectF, c: float, tl=True, tr=False, br=True, bl=False) -> QPainterPath:
    p = QPainterPath()
    p.moveTo(QPointF(r.left() + (c if tl else 0), r.top()))
    p.lineTo(QPointF(r.right() - (c if tr else 0), r.top()))
    if tr:
        p.lineTo(QPointF(r.right(), r.top() + c))
    p.lineTo(QPointF(r.right(), r.bottom() - (c if br else 0)))
    if br:
        p.lineTo(QPointF(r.right() - c, r.bottom()))
    p.lineTo(QPointF(r.left() + (c if bl else 0), r.bottom()))
    if bl:
        p.lineTo(QPointF(r.left(), r.bottom() - c))
    p.lineTo(QPointF(r.left(), r.top() + (c if tl else 0)))
    p.closeSubpath()
    return p


def rgba(c: QColor, a: float | None = None) -> str:
    alpha = c.alphaF() if a is None else a
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha:.3f})"


def stylesheet() -> str:
    return f"""
* {{
    font-family: "{FONT_FAMILY}";
    color: {TEXT.name()};
    outline: none;
}}
QMainWindow, QDialog {{ background: {BG.name()}; }}
QToolTip {{
    background: {BG_2.name()}; color: {TEXT.name()};
    border: 1px solid {ACCENT_DIM.name()}; padding: 6px;
}}
QLabel#dim {{ color: {TEXT_DIM.name()}; }}
QLabel#kicker {{ color: {ACCENT.name()}; font-size: 9pt; }}
QLabel#title {{ font-size: 20pt; color: {TEXT.name()}; }}

QLineEdit {{
    background: {rgba(BG_2, 0.85)};
    border: 1px solid {LINE.name()};
    border-left: 3px solid {ACCENT_DIM.name()};
    padding: 8px 12px; font-size: 11pt;
    selection-background-color: {ACCENT.name()}; selection-color: {BG.name()};
}}
QLineEdit:focus {{ border-color: {ACCENT.name()}; border-left-color: {ACCENT.name()}; }}

QPushButton {{
    background: {rgba(ACCENT, 0.04)};
    border: 1px solid {ACCENT_DIM.name()};
    color: {ACCENT.name()};
    padding: 7px 16px; font-size: 10pt;
}}
QPushButton:hover {{ background: {rgba(ACCENT, 0.16)}; border-color: {ACCENT.name()}; color: #ffffff; }}
QPushButton:pressed {{ background: {ACCENT.name()}; color: {BG.name()}; }}
QPushButton:disabled {{ color: {TEXT_DIM.name()}; border-color: {LINE.name()}; background: transparent; }}

QPushButton[variant="primary"] {{ background: {rgba(ACCENT, 0.85)}; color: {BG.name()}; border-color: {ACCENT.name()}; }}
QPushButton[variant="primary"]:hover {{ background: #7fdcff; color: {BG.name()}; }}
QPushButton[variant="primary"]:disabled {{ background: {rgba(LINE, 0.6)}; color: {TEXT_DIM.name()}; border-color: {LINE.name()}; }}
QPushButton[variant="installed"] {{ background: {rgba(OK, 0.10)}; color: {OK.name()}; border-color: {rgba(OK, 0.6)}; }}
QPushButton[variant="installed"]:hover {{ background: {rgba(DANGER, 0.15)}; color: {DANGER.name()}; border-color: {DANGER.name()}; }}
QPushButton[variant="danger"] {{ color: {DANGER.name()}; border-color: {rgba(DANGER, 0.5)}; background: transparent; }}
QPushButton[variant="danger"]:hover {{ background: {rgba(DANGER, 0.15)}; border-color: {DANGER.name()}; color: #ffffff; }}

QPushButton[variant="tab"] {{
    background: transparent; border: none; border-bottom: 2px solid transparent;
    color: {TEXT_DIM.name()}; padding: 10px 18px; font-size: 11pt;
}}
QPushButton[variant="tab"]:hover {{ color: {TEXT.name()}; }}
QPushButton[variant="tab"]:checked {{ color: {ACCENT.name()}; border-bottom: 2px solid {ACCENT.name()}; }}

QPushButton[variant="seg"] {{ padding: 7px 14px; color: {TEXT_DIM.name()}; border-color: {LINE.name()}; background: transparent; }}
QPushButton[variant="seg"]:hover {{ color: {TEXT.name()}; border-color: {ACCENT_DIM.name()}; }}
QPushButton[variant="seg"]:checked {{ color: {ACCENT.name()}; border-color: {ACCENT.name()}; background: {rgba(ACCENT, 0.12)}; }}

QComboBox {{
    background: {rgba(BG_2, 0.85)}; border: 1px solid {LINE.name()};
    border-left: 3px solid {ACCENT.name()};
    padding: 6px 10px; min-width: 260px; font-size: 10pt;
}}
QComboBox:hover {{ border-color: {ACCENT_DIM.name()}; border-left-color: {ACCENT.name()}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; border: none; width: 0; }}
QComboBox QAbstractItemView {{
    background: {BG_2.name()}; border: 1px solid {ACCENT_DIM.name()};
    selection-background-color: {rgba(ACCENT, 0.25)}; selection-color: #ffffff; padding: 4px;
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px 4px 0; }}
QScrollBar::handle:vertical {{ background: {ACCENT_DIM.name()}; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT.name()}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; height: 0; }}

QMessageBox {{ background: {BG_2.name()}; }}
QFileDialog {{ background: {BG_2.name()}; }}
"""
