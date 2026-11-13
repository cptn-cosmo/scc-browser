from pathlib import Path

import pytest

from scc_browser.gamedirs import GameInstall
from scc_browser.installer import Installer, file_name_for, site_style_name


def head(hid, title, file):
    return {
        "id": hid,
        "title": title,
        "dnaUrl": f"https://images.example/{hid}/{file}",
        "previewUrl": f"https://images.example/{hid}/x.jpeg",
        "user": {"name": "Pilot"},
    }


@pytest.fixture
def setup(tmp_path):
    inst = GameInstall(tmp_path / "StarCitizen" / "LIVE", "Custom")
    return inst, Installer(tmp_path / "manifest.json")


def test_names():
    assert site_style_name("John  Wick: JW4!") == "john_wick_jw4"
    assert file_name_for(head("1", "x", "maxblazar.chf")) == "maxblazar"
    assert file_name_for({"id": "1", "title": "Ünïcode Name"}) == "ünïcode_name"
    assert file_name_for({"id": "1", "title": "!!!"}) == "character"


def test_install_list_uninstall(setup):
    inst, ins = setup
    p = ins.install(inst, head("a", "John Wick", "john_wick.chf"), b"BB\x00\x00")
    assert p == inst.characters_dir / "john_wick.chf"
    assert p.read_bytes() == b"BB\x00\x00"
    assert ins.installed_ids(inst) == {"a"}
    [f] = ins.list_files(inst)
    assert (f.head_id, f.title, f.author) == ("a", "John Wick", "Pilot")
    ins.uninstall_id(inst, "a")
    assert not p.exists()
    assert ins.installed_ids(inst) == set()


def test_name_collisions_do_not_overwrite(setup):
    inst, ins = setup
    inst.characters_dir.mkdir(parents=True)
    (inst.characters_dir / "john_wick.chf").write_bytes(b"manual")
    a = ins.install(inst, head("a", "John Wick", "john_wick.chf"), b"A")
    b = ins.install(inst, head("b", "John Wick", "john_wick.chf"), b"B")
    assert (a.name, b.name) == ("john_wick_2.chf", "john_wick_3.chf")
    assert (inst.characters_dir / "john_wick.chf").read_bytes() == b"manual"
    # reinstalling the same character reuses its file
    assert ins.install(inst, head("a", "John Wick", "john_wick.chf"), b"A2") == a
    files = {f.path.name: f.head_id for f in ins.list_files(inst)}
    assert files == {"john_wick.chf": None, "john_wick_2.chf": "a", "john_wick_3.chf": "b"}


def test_manifest_survives_restart_and_external_delete(setup, tmp_path):
    inst, ins = setup
    p = ins.install(inst, head("a", "A", "a.chf"), b"x")
    again = Installer(tmp_path / "manifest.json")
    assert again.installed_ids(inst) == {"a"}
    p.unlink()
    assert again.installed_ids(inst) == set()


def test_empty_download_rejected(setup):
    inst, ins = setup
    with pytest.raises(ValueError):
        ins.install(inst, head("a", "A", "a.chf"), b"")
    assert not list(inst.characters_dir.glob("*"))


def test_remove_manual_file(setup):
    inst, ins = setup
    inst.characters_dir.mkdir(parents=True)
    f = inst.characters_dir / "mine.chf"
    f.write_bytes(b"x")
    ins.remove_file(inst, f)
    assert not f.exists()


def test_no_target(setup):
    _, ins = setup
    assert ins.installed_ids(None) == set()
    assert ins.list_files(None) == []
