"""Install / remove character (.chf) files and remember what we installed."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .gamedirs import GameInstall

if sys.platform == "win32":
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "scc-browser"
else:
    DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "scc-browser"
MANIFEST = DATA_DIR / "installed.json"


def site_style_name(text: str) -> str:
    """Mirror the website's own file-name normalisation."""
    s = re.sub(r"[^\w\s]", "", text)
    s = re.sub(r"\s\s+", " ", s).strip()
    return s.replace(" ", "_").lower()


def file_name_for(head: dict) -> str:
    base = Path(unquote(urlparse(head.get("dnaUrl", "")).path)).stem
    base = site_style_name(base) or site_style_name(head.get("title", "")) or "character"
    return base[:64]


@dataclass
class InstalledFile:
    path: Path
    head_id: str | None = None
    title: str | None = None
    author: str | None = None
    preview_url: str | None = None


class Installer:
    def __init__(self, manifest_path: Path = MANIFEST):
        self.manifest_path = manifest_path
        self._data: dict[str, dict[str, dict]] = {}
        self._load()

    # -- manifest ---------------------------------------------------------
    def _load(self):
        try:
            self._data = json.loads(self.manifest_path.read_text())
        except (OSError, ValueError):
            self._data = {}

    def _save(self):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.manifest_path)

    def _entries(self, inst: GameInstall) -> dict[str, dict]:
        """id -> entry for this install, pruned of files deleted outside the app."""
        key = str(inst.characters_dir)
        entries = self._data.get(key, {})
        alive = {i: e for i, e in entries.items() if (inst.characters_dir / e["file"]).is_file()}
        if alive != entries:
            self._data[key] = alive
            self._save()
        return alive

    # -- queries ----------------------------------------------------------
    def installed_ids(self, inst: GameInstall | None) -> set[str]:
        return set(self._entries(inst)) if inst else set()

    def list_files(self, inst: GameInstall | None) -> list[InstalledFile]:
        if not inst:
            return []
        by_file = {e["file"]: (i, e) for i, e in self._entries(inst).items()}
        try:
            files = sorted(inst.characters_dir.glob("*.chf"), key=lambda p: p.name.lower())
        except OSError:
            return []
        out = []
        for f in files:
            if f.name in by_file:
                hid, e = by_file[f.name]
                out.append(InstalledFile(f, hid, e.get("title"), e.get("author"), e.get("preview")))
            else:
                out.append(InstalledFile(f))
        return out

    # -- actions ----------------------------------------------------------
    def install(self, inst: GameInstall, head: dict, data: bytes) -> Path:
        if not data:
            raise ValueError("Downloaded character file is empty")
        target_dir = inst.characters_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        entries = self._entries(inst)
        hid = head["id"]
        if hid in entries:
            name = entries[hid]["file"]
        else:
            stem = file_name_for(head)
            taken = {e["file"] for e in entries.values()}
            name, n = f"{stem}.chf", 2
            while (target_dir / name).exists() or name in taken:
                name, n = f"{stem}_{n}.chf", n + 1

        fd, tmp = tempfile.mkstemp(dir=target_dir, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, target_dir / name)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

        self._data.setdefault(str(target_dir), {})[hid] = {
            "file": name,
            "title": head.get("title"),
            "author": (head.get("user") or {}).get("name"),
            "preview": head.get("previewUrl"),
        }
        self._save()
        return target_dir / name

    def uninstall_id(self, inst: GameInstall, head_id: str) -> None:
        entry = self._entries(inst).get(head_id)
        if entry:
            self.remove_file(inst, inst.characters_dir / entry["file"])

    def remove_file(self, inst: GameInstall, path: Path) -> None:
        path.unlink(missing_ok=True)
        key = str(inst.characters_dir)
        entries = self._data.get(key, {})
        self._data[key] = {i: e for i, e in entries.items() if e["file"] != path.name}
        self._save()
