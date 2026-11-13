import os
import sys


def main() -> int:
    # Prefer native Wayland; fall back to XWayland/X11 if unavailable.
    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from . import __version__, theme
    from .window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("scc-browser")
    app.setApplicationDisplayName("SC Character Databank")
    app.setOrganizationName("scc-browser")
    app.setDesktopFileName("gay.geeks.sccbrowser")  # Wayland app_id
    app.setWindowIcon(QIcon.fromTheme("gay.geeks.sccbrowser", QIcon(str(theme.ASSETS / "icon.svg"))))
    app.setApplicationVersion(__version__)
    theme.load_fonts()
    app.setFont(theme.font(10))
    app.setStyle("Fusion")
    if hasattr(app.styleHints(), "setColorScheme"):  # Qt 6.8+: dark window frame on Windows
        from PySide6.QtCore import Qt

        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyleSheet(theme.stylesheet())

    win = MainWindow()
    win.show()
    if os.environ.get("SCC_SMOKE_TEST"):  # CI: start up, then quit right away
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1500, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
