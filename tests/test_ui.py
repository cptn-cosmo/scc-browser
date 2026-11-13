"""Headless smoke test of the custom widgets (no network)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from scc_browser import theme  # noqa: E402
from scc_browser.widgets import CardGrid, CharacterCard  # noqa: E402


class FakeApi:
    def pixmap(self, url, cb):
        pm = QPixmap(50, 50)
        pm.fill()
        cb(pm)


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.load_fonts()
    a.setStyleSheet(theme.stylesheet())
    return a


def test_font_bundled(app):
    assert theme.FONT_FAMILY == "Electrolize"


def test_card_states_and_grid(app):
    grid = CardGrid()
    grid.resize(CharacterCard.W * 3 + CardGrid.GAP * 2, 400)
    for i in range(7):
        grid.add(CharacterCard({"id": str(i), "title": f"Pilot {i}", "previewUrl": "x"}, FakeApi()))
    grid.relayout()
    assert grid.cards[3].pos().y() > 0 and grid.cards[3].pos().x() == grid.cards[0].pos().x()
    card = grid.cards[0]
    card.set_state(installed=True)
    assert "INSTALLED" in card.btn.text()
    card.set_state(installed=False, has_target=False)
    assert not card.btn.isEnabled()
    card.set_state(has_target=True, busy=True)
    assert not card.btn.isEnabled()
    assert not card.grab().isNull()
