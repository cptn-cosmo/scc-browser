import os
from pathlib import Path

import pytest

from scc_browser import gamedirs as g

RSI = Path("drive_c", "Program Files", "Roberts Space Industries", "StarCitizen")


def make_channel(prefix: Path, channel="LIVE") -> Path:
    d = prefix / RSI / channel
    (d / "Bin64").mkdir(parents=True)
    return d


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    games = home / "Games"
    games.mkdir(parents=True)
    steam = home / ".local/share/Steam"
    (steam / "steamapps").mkdir(parents=True)
    monkeypatch.setattr(g, "HOME", home)
    monkeypatch.setattr(g, "GAMES_DIR", games)
    monkeypatch.setattr(g, "STEAM_ROOTS", (steam,))
    return home, games, steam


def test_finds_prefix_in_games(env):
    _, games, _ = env
    live = make_channel(games / "star-citizen")
    ptu = make_channel(games / "star-citizen", "PTU")
    found = g.detect_installs()
    assert [i.channel_dir for i in found] == [live, ptu]
    assert found[0].source == "~/Games"
    assert found[0].characters_dir == live / "user/client/0/CustomCharacters"
    assert found[0].display_path().startswith(str(Path("~/Games")) + os.sep)
    assert found[0].short_path() == str(Path("~/Games/star-citizen"))


def test_finds_nested_prefix_but_not_too_deep(env):
    _, games, _ = env
    nested = make_channel(games / "lutris" / "star-citizen")
    make_channel(games / "a" / "b" / "c" / "d")  # deeper than the scan depth
    assert [i.channel_dir for i in g.detect_installs()] == [nested]


def test_finds_proton_prefix_in_extra_steam_library(env, tmp_path):
    _, _, steam = env
    lib = tmp_path / "SteamLibrary"
    live = make_channel(lib / "steamapps/compatdata/123456/pfx")
    (steam / "steamapps/libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n  "0" { "path" "%s" }\n  "1" { "path" "%s" }\n}\n' % (steam, lib)
    )
    found = g.detect_installs()
    assert [i.channel_dir for i in found] == [live]
    assert found[0].source == "Steam"


def test_steam_library_inside_games_dir(env):
    _, games, _ = env
    live = make_channel(games / "SteamLibrary/steamapps/compatdata/42/pfx")
    assert [i.channel_dir for i in g.detect_installs()] == [live]


def test_no_installs(env):
    assert g.detect_installs() == []


@pytest.mark.parametrize("pick", ["prefix", "sc", "live", "chars"])
def test_user_path(env, pick):
    _, games, _ = env
    prefix = games / "sc"
    live = make_channel(prefix)
    path = {
        "prefix": prefix,
        "sc": live.parent,
        "live": live,
        "chars": live / "user/client/0/CustomCharacters",
    }[pick]
    path.mkdir(parents=True, exist_ok=True)
    assert [i.channel_dir for i in g.installs_from_user_path(path)] == [live]


def test_user_path_unrelated(tmp_path):
    assert g.installs_from_user_path(tmp_path) == []


# -- Windows ---------------------------------------------------------------

def test_windows_default_locations(tmp_path):
    c, d = tmp_path / "C", tmp_path / "D"
    sc1 = c / "Program Files" / "Roberts Space Industries" / "StarCitizen"
    sc2 = d / "Roberts Space Industries" / "StarCitizen"
    (sc1 / "LIVE").mkdir(parents=True)
    (sc2 / "PTU").mkdir(parents=True)
    (tmp_path / "E").mkdir()
    assert g.windows_star_citizen_dirs([c, d, tmp_path / "E"]) == [sc1, sc2]
    assert [ch.name for ch in g.channels_in(sc2)] == ["PTU"]


def test_launcher_log_parsing():
    log = (
        '[info] verify "D:\\\\Games\\\\Roberts Space Industries\\\\StarCitizen\\\\LIVE\\\\Data.p4k"\n'
        "moved from C:\\tmp to E:/RSI/StarCitizen/PTU/ ok\n"
        "again D:\\Games\\Roberts Space Industries\\StarCitizen\\LIVE\n"
        "unrelated C:\\StarCitizen\\Screenshots\n"
    )
    assert [str(p) for p in g.star_citizen_dirs_from_log(log)] == [
        "D:\\Games\\Roberts Space Industries\\StarCitizen",
        "E:\\RSI\\StarCitizen",
    ]


def test_launcher_logs_only_existing_dirs(tmp_path, monkeypatch):
    real = tmp_path / "Games" / "StarCitizen"
    (real / "LIVE").mkdir(parents=True)
    logs = tmp_path / "AppData" / "rsilauncher" / "logs"
    logs.mkdir(parents=True)
    (logs / "log.log").write_text(f"install {real}{os.sep}LIVE\ninstall Z:\\Nope\\StarCitizen\\LIVE\n")
    monkeypatch.setattr(g, "star_citizen_dirs_from_log", lambda text: [real, Path("Z:/Nope/StarCitizen")])
    assert g.launcher_log_star_citizen_dirs(tmp_path / "AppData") == [real]
