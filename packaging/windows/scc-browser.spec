# PyInstaller spec for the Windows build. Run from the repository root:
#   pyinstaller --noconfirm packaging/windows/scc-browser.spec
# Produces dist/scc-browser/ (one folder: starts faster and trips fewer
# antivirus heuristics than a one-file build).

from pathlib import Path

root = Path(SPECPATH).parents[1]

a = Analysis(
    [str(root / "packaging/windows/launcher.py")],
    pathex=[str(root)],
    datas=[(str(root / "scc_browser/assets"), "scc_browser/assets")],
    hiddenimports=["PySide6.QtSvg"],
    excludes=["tkinter", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
)
# Only ship the Qt plugins the app uses: a window, JPEG/SVG/ICO images, TLS.
# (The app uses the built-in Fusion style, so no style plugins.)
KEEP_PLUGIN_DIRS = {"platforms", "tls", "networkinformation", "imageformats", "iconengines"}
KEEP_IMAGEFORMATS = ("qjpeg", "qsvg", "qico")
DROP_LIBS = ("Qt6Quick", "Qt6Qml", "Qt6Pdf", "Qt6VirtualKeyboard", "Qt6OpenGL", "Qt6WebEngine", "Qt63D", "Qt6Multimedia")


def wanted(entry):
    dest = entry[0].replace("\\", "/")
    if "/plugins/" in dest:
        sub = dest.split("/plugins/", 1)[1].split("/")
        plugin = sub[-1].removeprefix("lib")  # libqjpeg.so on Linux, qjpeg.dll on Windows
        if sub[0] not in KEEP_PLUGIN_DIRS:
            return False
        if sub[0] == "imageformats" and not plugin.startswith(KEEP_IMAGEFORMATS):
            return False
        if sub[0] == "platforms" and not plugin.startswith(("qwindows", "qwayland", "qxcb", "qoffscreen")):
            return False
    name = dest.rsplit("/", 1)[-1]
    return not any(lib in name for lib in DROP_LIBS)


a.binaries = [e for e in a.binaries if wanted(e)]
a.datas = [e for e in a.datas if "/translations/" not in e[0].replace("\\", "/")]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="scc-browser",
    icon=str(root / "packaging/windows/scc-browser.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="scc-browser", upx=False)
