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
    app.setStyleSheet(theme.stylesheet())

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
