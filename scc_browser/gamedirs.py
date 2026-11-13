"""Locate Star Citizen installations (Wine/Proton prefixes) on Linux."""

from __future__ import annotations

import os
import re
import string
import sys
from dataclasses import dataclass
from pathlib import Path

CHANNELS = ("LIVE", "PTU", "EPTU", "TECH-PREVIEW", "HOTFIX")
CHARACTERS_SUBDIR = Path("user", "client", "0", "CustomCharacters")

# Where the RSI launcher may have put the game inside a prefix's drive_c.
RSI_LOCATIONS = (
    Path("Program Files", "Roberts Space Industries"),
    Path("Program Files (x86)", "Roberts Space Industries"),
    Path("Roberts Space Industries"),
    Path("Games", "Roberts Space Industries"),
)

HOME = Path.home()
STEAM_ROOTS = (
    HOME / ".local/share/Steam",
    HOME / ".steam/steam",
    HOME / ".steam/root",
    HOME / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    HOME / ".var/app/com.valvesoftware.Steam/data/Steam",
    HOME / "snap/steam/common/.local/share/Steam",
)
GAMES_DIR = HOME / "Games"
GAMES_SCAN_DEPTH = 3


@dataclass(frozen=True)
class GameInstall:
    channel_dir: Path
    source: str  # where it was found: "Steam", "~/Games", "Wine", "Custom"

    @property
    def channel(self) -> str:
        return self.channel_dir.name

    @property
    def characters_dir(self) -> Path:
        return self.channel_dir / CHARACTERS_SUBDIR

    def display_path(self, path: Path | None = None) -> str:
        s = str(path or self.channel_dir)
        home = str(HOME)
        return "~" + s[len(home):] if s.startswith(home + os.sep) else s

    def short_path(self) -> str:
        """The Wine prefix holding this install, or the channel dir if not in a prefix."""
        parts = self.channel_dir.parts
        if "drive_c" in parts:
            return self.display_path(Path(*parts[: parts.index("drive_c")]))
        return self.display_path()


def _is_channel_dir(p: Path) -> bool:
    if not p.is_dir():
        return False
    if p.name.upper() in CHANNELS:
        return True
    return (p / "Bin64").is_dir() or (p / "Data.p4k").exists()


def channels_in(star_citizen_dir: Path) -> list[Path]:
    try:
        children = sorted(star_citizen_dir.iterdir())
    except OSError:
        return []
    return [c for c in children if _is_channel_dir(c)]


def star_citizen_dirs_in_prefix(prefix: Path) -> list[Path]:
    drive_c = prefix / "drive_c"
    found = []
    for loc in RSI_LOCATIONS:
        sc = drive_c / loc / "StarCitizen"
        if sc.is_dir():
            found.append(sc)
    return found


def _parse_library_paths(vdf: Path) -> list[Path]:
    try:
        text = vdf.read_text(errors="replace")
    except OSError:
        return []
    paths = []
    for m in re.finditer(r'"path"\s+"((?:[^"\\]|\\.)*)"', text):
        paths.append(Path(m.group(1).replace("\\\\", "\\")))
    return paths


def steam_libraries() -> list[Path]:
    libs: dict[Path, None] = {}
    for root in STEAM_ROOTS:
        if not (root / "steamapps").is_dir():
            continue
        libs[root.resolve()] = None
        for vdf in (root / "steamapps/libraryfolders.vdf", root / "config/libraryfolders.vdf"):
            for lib in _parse_library_paths(vdf):
                if (lib / "steamapps").is_dir():
                    libs[lib.resolve()] = None
    return list(libs)


def prefixes_in_steam_library(lib: Path) -> list[Path]:
    compat = lib / "steamapps" / "compatdata"
    try:
        return [d / "pfx" for d in compat.iterdir() if (d / "pfx" / "drive_c").is_dir()]
    except OSError:
        return []


def _scan_for_prefixes(root: Path, depth: int) -> tuple[list[Path], list[Path]]:
    """Walk `root` up to `depth` levels looking for Wine prefixes and Steam libraries."""
    prefixes, libraries = [], []
    stack = [(root, 0)]
    seen = set()
    while stack:
        d, level = stack.pop()
        try:
            key = d.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        if (d / "drive_c").is_dir():
            prefixes.append(d)
            continue  # don't descend into a prefix
        if (d / "steamapps").is_dir():
            libraries.append(d)
        if level >= GAMES_SCAN_DEPTH or level >= depth:
            continue
        try:
            for entry in os.scandir(d):
                if entry.is_dir() and not entry.name.startswith("."):
                    stack.append((Path(entry.path), level + 1))
        except OSError:
            pass
    return prefixes, libraries


def detect_installs() -> list[GameInstall]:
    """Find every Star Citizen channel directory (LIVE, PTU, ...) we can."""
    candidates: list[tuple[Path, str]] = []  # (wine prefix, source)

    for lib in steam_libraries():
        candidates += [(p, "Steam") for p in prefixes_in_steam_library(lib)]

    if GAMES_DIR.is_dir():
        prefixes, libraries = _scan_for_prefixes(GAMES_DIR, GAMES_SCAN_DEPTH)
        candidates += [(p, "~/Games") for p in prefixes]
        for lib in libraries:
            candidates += [(p, "Steam") for p in prefixes_in_steam_library(lib)]

    default_wine = HOME / ".wine"
    if (default_wine / "drive_c").is_dir():
        candidates.append((default_wine, "Wine"))

    sc_dirs: list[tuple[Path, str]] = []
    for prefix, source in candidates:
        sc_dirs += [(sc, source) for sc in star_citizen_dirs_in_prefix(prefix)]

    if sys.platform == "win32":
        sc_dirs += [(sc, "Windows") for sc in windows_star_citizen_dirs()]
        sc_dirs += [(sc, "RSI Launcher") for sc in launcher_log_star_citizen_dirs()]

    installs: dict[Path, GameInstall] = {}
    for sc, source in sc_dirs:
        for ch in channels_in(sc):
            installs.setdefault(ch.resolve(), GameInstall(ch, source))

    return sort_installs(installs.values())


# -- Windows --------------------------------------------------------------

def windows_drives() -> list[Path]:
    if sys.platform != "win32":
        return []
    import ctypes

    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [Path(f"{letter}:\\") for i, letter in enumerate(string.ascii_uppercase) if mask >> i & 1]


def windows_star_citizen_dirs(drives: list[Path] | None = None) -> list[Path]:
    """The launcher's default locations (and common variants) on every drive."""
    found = []
    for drive in windows_drives() if drives is None else drives:
        for loc in RSI_LOCATIONS:
            sc = drive / loc / "StarCitizen"
            try:
                if sc.is_dir():
                    found.append(sc)
            except OSError:  # e.g. an empty card reader
                pass
    return found


# Matches "X:\...\StarCitizen" followed by a channel, as the RSI launcher logs it.
_LOG_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/][^\"'\r\n<>|*?:]*?[\\/]StarCitizen)[\\/](?:%s)\b" % "|".join(map(re.escape, CHANNELS)),
    re.IGNORECASE,
)


def star_citizen_dirs_from_log(text: str) -> list[Path]:
    text = text.replace("\\\\", "\\")  # JSON-escaped backslashes
    seen: dict[str, None] = {}
    for m in _LOG_PATH_RE.finditer(text):
        seen.setdefault(m.group(1).replace("/", "\\"), None)
    return [Path(p) for p in seen]


def launcher_log_star_citizen_dirs(appdata: Path | None = None) -> list[Path]:
    """Install locations mentioned in the RSI launcher's logs (custom library folders)."""
    if appdata is None:
        env = os.environ.get("APPDATA")
        if not env:
            return []
        appdata = Path(env)
    base = appdata / "rsilauncher"
    logs = list(base.glob("*.log")) + list(base.glob("logs/*.log"))
    found: dict[Path, None] = {}
    for log in logs:
        try:
            with open(log, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                fh.seek(max(0, fh.tell() - 4 * 1024 * 1024))
                text = fh.read().decode("utf-8", errors="replace")
        except OSError:
            continue
        for sc in star_citizen_dirs_from_log(text):
            try:
                if sc.is_dir():
                    found.setdefault(sc, None)
            except OSError:
                pass
    return list(found)


def sort_installs(installs) -> list[GameInstall]:
    def key(i: GameInstall):
        ch = i.channel.upper()
        return (CHANNELS.index(ch) if ch in CHANNELS else len(CHANNELS), str(i.channel_dir))
    return sorted(installs, key=key)


def installs_from_user_path(path: Path) -> list[GameInstall]:
    """Turn a folder picked by the user into channel installs.

    Accepts a channel dir (LIVE), the StarCitizen dir, a Wine prefix, the
    CustomCharacters dir itself, or any parent of those within a few levels.
    """
    path = path.expanduser()
    if path.name == "CustomCharacters":
        return [GameInstall(path.parents[3], "Custom")]
    if path.is_dir() and (path.name.upper() in CHANNELS or (path / "Data.p4k").exists()):
        return [GameInstall(path, "Custom")]
    chans = channels_in(path)
    if chans:
        return [GameInstall(c, "Custom") for c in chans]
    found = []
    prefixes, libraries = _scan_for_prefixes(path, 2)
    for lib in libraries:
        prefixes += prefixes_in_steam_library(lib)
    for prefix in prefixes:
        for sc in star_citizen_dirs_in_prefix(prefix):
            found += [GameInstall(c, "Custom") for c in channels_in(sc)]
    return sort_installs(found)


if __name__ == "__main__":
    for inst in detect_installs():
        print(f"[{inst.source}] {inst.channel}: {inst.channel_dir}")
