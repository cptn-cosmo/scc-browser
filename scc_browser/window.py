"""Main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDateTime, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme as T
from .api import ORDERS, Api, character_page_url
from .gamedirs import GameInstall, detect_installs, installs_from_user_path, sort_installs
from .installer import Installer
from .widgets import (
    CardGrid,
    CharacterCard,
    Divider,
    HudBackground,
    InstalledRow,
    Toast,
    cover_pixmap,
    draw_brackets,
    draw_no_signal,
    restyle,
)


def button(text, variant=None, tip=None, checkable=False) -> QPushButton:
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if tip:
        b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setCursor(Qt.PointingHandCursor)
    return b


def label(text, obj=None, font=None) -> QLabel:
    l = QLabel(text)
    if obj:
        l.setObjectName(obj)
    if font:
        l.setFont(font)
    return l


class Portrait(QWidget):
    def __init__(self, size, parent=None):
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
        r = self.rect().adjusted(6, 6, -6, -6).toRectF()
        if self.pix.isNull():
            draw_no_signal(p, r)
        else:
            cover_pixmap(p, self.pix, r)
        p.setPen(QPen(T.LINE, 1))
        p.drawRect(r)
        draw_brackets(p, self.rect().toRectF().adjusted(1, 1, -1, -1), 22, T.ACCENT, 2)


class DetailDialog(QDialog):
    def __init__(self, head: dict, win: "MainWindow"):
        super().__init__(win)
        self.head, self.win = head, win
        self.setWindowTitle(head.get("title", "Character"))
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose)

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(28)

        portrait = Portrait(440)
        win.api.pixmap(head.get("previewUrl", ""), portrait.set_pixmap)
        root.addWidget(portrait, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(6)
        root.addLayout(col)
        col.addWidget(label("CHARACTER DOSSIER", "kicker", T.font(9, 160)))
        title = label(head.get("title", "?"), "title", T.font(22, 102))
        title.setWordWrap(True)
        title.setMaximumWidth(380)
        col.addWidget(title)
        col.addWidget(Divider())
        col.addSpacing(8)

        user = head.get("user") or {}
        created = QDateTime.fromString(head.get("createdAt", ""), Qt.ISODateWithMs)
        counts = head.get("_count") or {}
        rows = [
            ("CREATOR", user.get("name") or "Unknown"),
            ("RSI HANDLE", user.get("starCitizenHandle") or "—"),
            ("UPLOADED", created.toLocalTime().toString("yyyy-MM-dd  HH:mm") if created.isValid() else "—"),
            ("LIKES", str(counts.get("characterLikes", 0))),
            ("DOWNLOADS", str(counts.get("characterDownloads", 0))),
        ]
        if head.get("tags"):
            rows.append(("TAGS", ", ".join(str(t.get("name", t)) if isinstance(t, dict) else str(t) for t in head["tags"])))
        for k, v in rows:
            r = QHBoxLayout()
            r.addWidget(label(k, "dim", T.font(9, 130)))
            r.addStretch()
            val = label(v, None, T.font(11))
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            r.addWidget(val)
            col.addLayout(r)

        col.addSpacing(10)
        self.target_lbl = label("", "dim", T.font(9, 110))
        self.target_lbl.setWordWrap(True)
        self.target_lbl.setMaximumWidth(380)
        col.addWidget(self.target_lbl)
        col.addStretch()

        self.action = button("INSTALL", "primary")
        self.action.setMinimumHeight(42)
        self.action.clicked.connect(lambda: win.toggle_install(self.head))
        col.addWidget(self.action)
        row = QHBoxLayout()
        web = button("VIEW ON WEBSITE")
        web.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(character_page_url(head["id"]))))
        close = button("CLOSE")
        close.clicked.connect(self.accept)
        row.addWidget(web)
        row.addWidget(close)
        col.addLayout(row)

        win.stateChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        w, hid = self.win, self.head["id"]
        if hid in w.busy:
            self.action.setText("TRANSFERRING…")
            self.action.setProperty("variant", "primary")
            self.action.setEnabled(False)
        elif hid in w.installed_ids:
            self.action.setText("✓  INSTALLED — CLICK TO REMOVE")
            self.action.setProperty("variant", "installed")
            self.action.setEnabled(True)
        else:
            self.action.setText(f"INSTALL TO {w.target.channel}" if w.target else "NO GAME FOLDER SELECTED")
            self.action.setProperty("variant", "primary")
            self.action.setEnabled(w.target is not None)
        restyle(self.action)
        self.target_lbl.setText(
            f"TARGET  //  {w.target.display_path(w.target.characters_dir)}" if w.target else "Select a Star Citizen folder in the header."
        )


class MainWindow(QMainWindow):
    stateChanged = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Star Citizen Character Databank")
        self.resize(1320, 900)
        self.setMinimumSize(720, 560)

        self.settings = QSettings("scc-browser", "scc-browser")
        self.api = Api(self)
        self.installer = Installer()
        self.installs: list[GameInstall] = []
        self.target: GameInstall | None = None
        self.installed_ids: set[str] = set()
        self.busy: set[str] = set()

        self.page = 0
        self.has_next = True
        self.loading = False
        self.generation = 0
        self.seen_ids: set[str] = set()
        self.order = self.settings.value("order", "latest")
        if self.order not in dict(ORDERS):
            self.order = "latest"

        self._build()
        self.toast = Toast(self.centralWidget())
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.nav_browse.click(), self.search.setFocus()))
        QShortcut(QKeySequence("F5"), self, activated=self.reload)

        self.scan_installs(initial=True)
        self.reload()

    # ------------------------------------------------------------------ UI
    def _build(self):
        bg = HudBackground()
        self.setCentralWidget(bg)
        root = QVBoxLayout(bg)
        root.setContentsMargins(32, 22, 32, 14)
        root.setSpacing(0)

        # header
        head = QHBoxLayout()
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(label("STAR CITIZEN  //  COMMUNITY", "kicker", T.font(9, 180)))
        brand.addWidget(label("CHARACTER DATABANK", None, T.font(24, 108)))
        head.addLayout(brand)
        head.addSpacing(32)
        head.addStretch()

        tgt = QVBoxLayout()
        tgt.setSpacing(4)
        tgt.addWidget(label("INSTALL TARGET", "kicker", T.font(8.5, 170)), 0, Qt.AlignLeft)
        trow = QHBoxLayout()
        trow.setSpacing(6)
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(260)
        self.target_combo.setMaximumWidth(520)
        self.target_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.target_combo.setMinimumContentsLength(24)
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        trow.addWidget(self.target_combo)
        add = button("ADD FOLDER…", tip="Point at a Star Citizen install, Wine prefix or LIVE folder")
        add.clicked.connect(self.add_folder)
        rescan = button("RESCAN", tip="Search Steam libraries and ~/Games again")
        rescan.clicked.connect(lambda: self.scan_installs())
        self.open_btn = button("OPEN", tip="Open the CustomCharacters folder")
        self.open_btn.clicked.connect(self.open_folder)
        for b in (add, rescan, self.open_btn):
            trow.addWidget(b)
        tgt.addLayout(trow)
        head.addLayout(tgt)
        root.addLayout(head)
        root.addSpacing(14)
        root.addWidget(Divider())

        # nav + toolbar
        bar = QHBoxLayout()
        bar.setSpacing(0)
        self.nav_browse = button("BROWSE", "tab", checkable=True)
        self.nav_installed = button("INSTALLED", "tab", checkable=True)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        for i, b in enumerate((self.nav_browse, self.nav_installed)):
            grp.addButton(b, i)
            bar.addWidget(b)
        grp.idClicked.connect(self._nav)
        bar.addSpacing(24)

        self.browse_tools = QWidget()
        tl = QHBoxLayout(self.browse_tools)
        tl.setContentsMargins(0, 8, 0, 8)
        tl.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("SEARCH CHARACTERS…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(260)
        self._search_timer = QTimer(self, singleShot=True, interval=450, timeout=self.reload)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        self.search.returnPressed.connect(lambda: (self._search_timer.stop(), self.reload()))
        tl.addWidget(self.search, 1)
        tl.addSpacing(14)
        tl.addWidget(label("SORT", "dim", T.font(8.5, 150)))
        self.order_group = QButtonGroup(self)
        for key, text in ORDERS:
            b = button(text, "seg", checkable=True)
            b.setProperty("order", key)
            b.setChecked(key == self.order)
            self.order_group.addButton(b)
            tl.addWidget(b)
        self.order_group.buttonClicked.connect(self._order_changed)
        bar.addWidget(self.browse_tools, 1)

        self.installed_tools = QWidget()
        il = QHBoxLayout(self.installed_tools)
        il.setContentsMargins(0, 8, 0, 8)
        il.addStretch()
        r = button("REFRESH")
        r.clicked.connect(self.refresh_installed_view)
        il.addWidget(r)
        bar.addWidget(self.installed_tools, 1)
        root.addLayout(bar)
        root.addSpacing(10)

        # pages
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.grid = CardGrid()
        self.browse_scroll = QScrollArea()
        self.browse_scroll.setWidgetResizable(True)
        self.browse_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browse_scroll.setWidget(self.grid)
        self.browse_scroll.verticalScrollBar().valueChanged.connect(self._maybe_load_more)
        self.browse_scroll.verticalScrollBar().rangeChanged.connect(lambda *_: self._maybe_load_more())
        self.stack.addWidget(self.browse_scroll)

        self.installed_list = QWidget()
        self.installed_layout = QVBoxLayout(self.installed_list)
        self.installed_layout.setContentsMargins(0, 0, 12, 0)
        self.installed_layout.setSpacing(8)
        inst_scroll = QScrollArea()
        inst_scroll.setWidgetResizable(True)
        inst_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inst_scroll.setWidget(self.installed_list)
        self.stack.addWidget(inst_scroll)

        # footer
        root.addSpacing(8)
        root.addWidget(Divider())
        foot = QHBoxLayout()
        self.status_left = label("", "dim", T.font(8.5, 140))
        self.status_right = label("", "dim", T.font(8.5, 140))
        foot.addWidget(self.status_left)
        foot.addStretch()
        foot.addWidget(self.status_right)
        root.addLayout(foot)

        self.nav_browse.setChecked(True)
        self._nav(0)

    def _nav(self, idx):
        self.stack.setCurrentIndex(idx)
        self.browse_tools.setVisible(idx == 0)
        self.installed_tools.setVisible(idx == 1)
        if idx == 1:
            self.refresh_installed_view()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast.hide()

    # -------------------------------------------------------- game folders
    def scan_installs(self, initial=False):
        found = detect_installs()
        for p in self._custom_paths():
            found += installs_from_user_path(Path(p))
        uniq = {}
        for i in found:
            uniq.setdefault(str(i.channel_dir.resolve()), i)
        self.installs = sort_installs(uniq.values())
        self._fill_target_combo(self.settings.value("target", ""))
        if not initial:
            n = len(self.installs)
            self.toast.show_message(
                f"SCAN COMPLETE  //  {n} INSTALL{'S' if n != 1 else ''} FOUND" if n else
                "NO STAR CITIZEN INSTALL FOUND  //  USE “ADD FOLDER…”",
                "ok" if n else "warn",
            )
        elif not self.installs:
            QTimer.singleShot(400, lambda: self.toast.show_message(
                "NO STAR CITIZEN INSTALL DETECTED  //  USE “ADD FOLDER…” TO SELECT ONE", "warn", 7000))

    def _custom_paths(self) -> list[str]:
        v = self.settings.value("custom_paths", [])
        if isinstance(v, str):
            v = [v]
        return [p for p in (v or []) if p]

    def _fill_target_combo(self, prefer: str):
        c = self.target_combo
        c.blockSignals(True)
        c.clear()
        if not self.installs:
            c.addItem("NO INSTALL DETECTED", None)
            c.setEnabled(False)
        else:
            c.setEnabled(True)
            for i in self.installs:
                c.addItem(f"{i.channel}   ·   {i.short_path()}" + ("   ·   STEAM" if i.source == "Steam" else ""), str(i.channel_dir))
                c.setItemData(c.count() - 1, f"Found via {i.source}\n{i.characters_dir}", Qt.ToolTipRole)
            idx = max(0, c.findData(prefer)) if prefer else 0
            c.setCurrentIndex(idx)
        c.blockSignals(False)
        self._target_changed()

    def _target_changed(self, *_):
        data = self.target_combo.currentData()
        self.target = next((i for i in self.installs if str(i.channel_dir) == data), None)
        if self.target:
            self.settings.setValue("target", str(self.target.channel_dir))
        self.open_btn.setEnabled(self.target is not None)
        self.target_combo.setToolTip(str(self.target.characters_dir) if self.target else "")
        self.refresh_state()
        if self.stack.currentIndex() == 1:
            self.refresh_installed_view()

    def add_folder(self):
        start = str(Path.home() / "Games") if (Path.home() / "Games").is_dir() else str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Select Star Citizen folder (or its Wine prefix)", start)
        if not d:
            return
        found = installs_from_user_path(Path(d))
        if not found:
            QMessageBox.warning(
                self, "Not a Star Citizen folder",
                "Couldn't find a Star Citizen channel (LIVE, PTU, …) in:\n\n"
                f"{d}\n\nSelect the StarCitizen folder, a channel folder like LIVE, or the Wine prefix.",
            )
            return
        paths = self._custom_paths()
        if d not in paths:
            self.settings.setValue("custom_paths", paths + [d])
        self.settings.setValue("target", str(found[0].channel_dir))
        self.scan_installs(initial=True)
        self.toast.show_message(f"ADDED  //  {found[0].channel}  {found[0].display_path()}", "ok")

    def open_folder(self):
        if not self.target:
            return
        d = self.target.characters_dir
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    # --------------------------------------------------------------- state
    def refresh_state(self):
        self.installed_ids = self.installer.installed_ids(self.target)
        has = self.target is not None
        for c in self.grid.cards:
            c.set_state(installed=c.head["id"] in self.installed_ids, busy=c.head["id"] in self.busy, has_target=has)
        self._update_status()
        self.stateChanged.emit()

    def _update_status(self):
        if self.target:
            n = len(self.installer.list_files(self.target))
            self.status_right.setText(
                f"TARGET  //  {self.target.channel}  //  {n} CHARACTER FILE{'S' if n != 1 else ''} INSTALLED"
            )
        else:
            self.status_right.setText("TARGET  //  NONE")

    def _set_net_status(self, text):
        self.status_left.setText(f"◆  {text}")

    # -------------------------------------------------------------- browse
    def _order_changed(self, b):
        self.order = b.property("order")
        self.settings.setValue("order", self.order)
        self.reload()

    def reload(self):
        self.generation += 1
        self.page = 0
        self.has_next = True
        self.loading = False
        self.seen_ids.clear()
        self.grid.clear()
        self.grid.empty_text = ""
        self.browse_scroll.verticalScrollBar().setValue(0)
        self.load_next()

    def _maybe_load_more(self, *_):
        sb = self.browse_scroll.verticalScrollBar()
        if sb.maximum() - sb.value() < CharacterCard.H * 1.5:
            self.load_next()

    def load_next(self):
        if self.loading or not self.has_next:
            return
        self.loading = True
        gen = self.generation
        page = self.page + 1
        self._set_net_status(f"UPLINK  //  REQUESTING PAGE {page}…")
        self.api.fetch_heads(page, self.search.text(), self.order, lambda body, err: self._on_page(gen, page, body, err))

    def _on_page(self, gen, page, body, err):
        if gen != self.generation:
            return
        self.loading = False
        if err:
            self.has_next = False
            self._set_net_status("UPLINK FAILED")
            if not self.grid.cards:
                self.grid.empty_text = "CONNECTION TO DATABANK FAILED  //  PRESS F5 TO RETRY"
                self.grid.update()
            self.toast.show_message(f"NETWORK ERROR  //  {err}", "error", 6000)
            # allow retry when scrolling again
            QTimer.singleShot(5000, lambda: setattr(self, "has_next", True) if gen == self.generation else None)
            return
        self.page = page
        self.has_next = bool(body.get("hasNextPage"))
        has_target = self.target is not None
        for head in body.get("rows", []):
            if not head.get("id") or head["id"] in self.seen_ids:
                continue
            self.seen_ids.add(head["id"])
            card = CharacterCard(head, self.api)
            card.set_state(installed=head["id"] in self.installed_ids, busy=head["id"] in self.busy, has_target=has_target)
            card.clicked.connect(self.show_detail)
            card.actionClicked.connect(self.toggle_install)
            self.grid.add(card)
        self.grid.relayout()
        if not self.grid.cards:
            q = self.search.text().strip()
            self.grid.empty_text = f"NO RESULTS FOR “{q.upper()}”" if q else "NO CHARACTERS FOUND"
            self.grid.update()
        n = len(self.grid.cards)
        self._set_net_status(
            f"UPLINK ESTABLISHED  //  {n} RECORD{'S' if n != 1 else ''} LOADED"
            + ("" if self.has_next else "  //  END OF DATABANK")
        )
        QTimer.singleShot(0, self._maybe_load_more)

    def show_detail(self, head):
        DetailDialog(head, self).exec()

    # ------------------------------------------------------------- install
    def toggle_install(self, head):
        hid = head["id"]
        if hid in self.busy:
            return
        if not self.target:
            self.toast.show_message("SELECT A STAR CITIZEN FOLDER FIRST  //  “ADD FOLDER…”", "warn")
            return
        if hid in self.installed_ids:
            try:
                self.installer.uninstall_id(self.target, hid)
            except OSError as e:
                self.toast.show_message(f"REMOVE FAILED  //  {e}", "error", 6000)
                return
            self.toast.show_message(f"REMOVED  //  {head.get('title', '')}", "info")
            self.refresh_state()
            return
        url = head.get("dnaUrl")
        if not url:
            self.toast.show_message("THIS SUBMISSION HAS NO CHARACTER FILE", "error")
            return
        target = self.target
        self.busy.add(hid)
        self.refresh_state()

        def done(data, err):
            self.busy.discard(hid)
            if err:
                self.toast.show_message(f"DOWNLOAD FAILED  //  {err}", "error", 6000)
            else:
                try:
                    path = self.installer.install(target, head, data)
                except (OSError, ValueError) as e:
                    self.toast.show_message(f"INSTALL FAILED  //  {e}", "error", 6000)
                else:
                    self.api.report_download(hid)
                    self.toast.show_message(
                        f"INSTALLED  //  {head.get('title', '')}  →  {target.channel}/…/CustomCharacters/{path.name}", "ok"
                    )
            self.refresh_state()

        self.api.fetch_bytes(url, done)

    # ----------------------------------------------------------- installed
    def refresh_installed_view(self):
        lay = self.installed_layout
        while lay.count():
            it = lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        items = self.installer.list_files(self.target)
        if not self.target:
            lay.addWidget(label("NO STAR CITIZEN FOLDER SELECTED", "dim", T.font(12, 130)), 0, Qt.AlignHCenter)
        elif not items:
            msg = label("NO CHARACTER FILES INSTALLED IN THIS CHANNEL YET", "dim", T.font(12, 130))
            lay.addWidget(msg, 0, Qt.AlignHCenter)
        hint = None
        if self.target:
            hint = label(self.target.display_path(self.target.characters_dir), "dim", T.font(9, 105))
            hint.setToolTip(str(self.target.characters_dir))
            hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(hint)
        for item in items:
            row = InstalledRow(item, self.api)
            row.removeClicked.connect(self._remove_file)
            row.clicked.connect(self._installed_clicked)
            lay.addWidget(row)
        lay.addStretch()
        self._update_status()

    def _installed_clicked(self, item):
        head = {
            "id": item.head_id,
            "title": item.title or item.path.stem,
            "previewUrl": item.preview_url,
            "user": {"name": item.author},
        }
        DetailDialog(head, self).exec()
        self.refresh_installed_view()

    def _remove_file(self, item):
        if not item.head_id:
            r = QMessageBox.question(
                self, "Remove file?",
                f"“{item.path.name}” wasn't installed by this app.\nDelete it from the game folder anyway?",
            )
            if r != QMessageBox.Yes:
                return
        try:
            self.installer.remove_file(self.target, item.path)
        except OSError as e:
            self.toast.show_message(f"REMOVE FAILED  //  {e}", "error", 6000)
            return
        self.toast.show_message(f"REMOVED  //  {item.title or item.path.name}", "info")
        self.refresh_state()
        self.refresh_installed_view()
