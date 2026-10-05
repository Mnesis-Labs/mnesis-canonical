"""Actual package resource layouts, not fake repository directories or installed wheels."""
from __future__ import annotations

import importlib
import json
import shutil
import sys
import zipfile
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import IO, Literal, overload

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "mnesis_canonical"


@pytest.fixture
def installed_checker(tmp_path, monkeypatch):
    """Real production package in an isolated installed layout; no root embodiments/."""
    target = tmp_path / "installed"
    shutil.copytree(
        PACKAGE, target / "mnesis_canonical", ignore=shutil.ignore_patterns("__pycache__")
    )
    assert not (target / "embodiments").exists()
    saved = {n: m for n, m in sys.modules.items() if n.startswith("mnesis_canonical")}
    for name in saved:
        del sys.modules[name]
    monkeypatch.syspath_prepend(str(target))
    importlib.invalidate_caches()
    try:
        checker = importlib.import_module("mnesis_canonical.embodiment_check")
        checker_file = checker.__file__
        assert checker_file is not None
        assert Path(checker_file).resolve().is_relative_to(target)
        yield checker
    finally:
        for name in list(sys.modules):
            if name.startswith("mnesis_canonical"):
                del sys.modules[name]
        sys.modules.update(saved)
        importlib.invalidate_caches()


def test_installed_discovery_reads_real_package_resources(installed_checker):
    paths = installed_checker._discover_embodiments()
    assert [p.name for p in paths] == sorted([
        "airbot_play.json", "alohamini.json", "dual_airbot_play.json", "ego_human.json",
        "ego_human_5cam_v1.json", "so_arm101.json",
    ])
    assert all(p.is_file() for p in paths)
    assert "embodiment.schema.json" not in [p.name for p in paths]


@pytest.fixture
def zip_checker(tmp_path, monkeypatch):
    """Import actual source/resources from an archive, without an extracted package."""
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                bundle.write(path, "mnesis_canonical/" + path.relative_to(PACKAGE).as_posix())
    saved = {n: m for n, m in sys.modules.items() if n.startswith("mnesis_canonical")}
    for name in saved:
        del sys.modules[name]
    monkeypatch.syspath_prepend(str(archive))
    importlib.invalidate_caches()
    try:
        checker = importlib.import_module("mnesis_canonical.embodiment_check")
        checker_file = checker.__file__
        assert checker_file is not None
        assert str(archive) in checker_file
        assert isinstance(checker._EMBODIMENTS_DIR, zipfile.Path)
        yield checker
    finally:
        for name in list(sys.modules):
            if name.startswith("mnesis_canonical"):
                del sys.modules[name]
        sys.modules.update(saved)
        importlib.invalidate_caches()


def test_zip_schema_is_read_without_filesystem_extraction(zip_checker):
    assert zip_checker.load_schema()["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_zip_traversable_embodiment_api(installed_checker, tmp_path):
    """Real zip resource input to the public API, independent of parent import support."""
    archive = tmp_path / "resources.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in (PACKAGE / "embodiments").iterdir():
            if path.is_file():
                bundle.write(path, "embodiments/" + path.name)
    with zipfile.ZipFile(archive) as bundle:
        resource = zipfile.Path(bundle, "embodiments/so_arm101.json")
        assert installed_checker.load_embodiment(resource)["id"] == "so_arm101"


def test_zip_schema_resource_api(installed_checker, tmp_path, monkeypatch):
    archive = tmp_path / "schema.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(PACKAGE / "embodiments/embodiment.schema.json", "schema.json")
    with zipfile.ZipFile(archive) as bundle:
        monkeypatch.setattr(installed_checker, "_SCHEMA_PATH", zipfile.Path(bundle, "schema.json"))
        assert installed_checker.load_schema()["$schema"] == "https://json-schema.org/draft/2020-12/schema"


class ResourceOnly(Traversable):
    """A real resource provider exposing only the portable Traversable contract."""
    def __init__(self, resource: Traversable):
        self.resource = resource

    @property
    def name(self):
        return self.resource.name

    def iterdir(self):
        return (ResourceOnly(p) for p in self.resource.iterdir())

    def is_file(self):
        return self.resource.is_file()

    def is_dir(self):
        return self.resource.is_dir()

    def joinpath(self, *descendants):
        return ResourceOnly(self.resource.joinpath(*descendants))

    @overload
    def open(self, mode: Literal["r"] = "r", *args, **kwargs) -> IO[str]: ...

    @overload
    def open(self, mode: Literal["rb"], *args, **kwargs) -> IO[bytes]: ...

    def open(self, mode: Literal["r", "rb"] = "r", *args, **kwargs):
        return self.resource.open(mode, *args, **kwargs)

    def read_bytes(self) -> bytes:
        return self.resource.read_bytes()

    def read_text(self, encoding: str | None = None) -> str:
        return self.resource.read_text(encoding=encoding)


def test_cli_uses_portable_resource_names_not_path_stem(installed_checker, monkeypatch):
    resource = ResourceOnly(installed_checker._EMBODIMENTS_DIR)
    monkeypatch.setattr(installed_checker, "_EMBODIMENTS_DIR", resource)
    assert not hasattr(next(resource.iterdir()), "stem")
    assert installed_checker.main([]) == 0


def test_installed_cli_list_and_validate(installed_checker, capsys):
    assert installed_checker.main(["--list"]) == 0
    listed = capsys.readouterr()
    assert "so_arm101" in listed.out and "ego_human" in listed.out
    assert listed.err == ""
    assert installed_checker.main([]) == 0
    validated = capsys.readouterr()
    assert "All 6 embodiment(s) pass validation." in validated.out
    assert validated.err == ""


@pytest.mark.parametrize("bad_kind", ["json", "schema", "limits", "id"])
def test_installed_invalid_resources_still_fail(installed_checker, capsys, bad_kind):
    path = installed_checker._EMBODIMENTS_DIR / "so_arm101.json"
    data = installed_checker.load_embodiment(path)
    if bad_kind == "json":
        path.write_text("{bad", encoding="utf-8")
    else:
        if bad_kind == "schema":
            data["dof_per_arm"] = -1
        elif bad_kind == "limits":
            data["joint_limits"]["min"] = []
        else:
            data["id"] = "airbot_play"
        path.write_text(json.dumps(data), encoding="utf-8")
    assert installed_checker.main([]) == 1
    result = capsys.readouterr()
    assert "so_arm101.json" in result.out + result.err
    assert "All 6" not in result.out
    if bad_kind == "json":
        assert "LOAD ERROR" in result.err
    elif bad_kind == "id":
        assert "id mismatch" in result.err
    elif bad_kind == "schema":
        assert "less than the minimum" in result.err
    else:
        assert "joint_limits.min has 0 entries, expected 6" in result.err


def test_empty_installed_registry_is_io_exit_two(installed_checker, capsys):
    for path in installed_checker._discover_embodiments():
        path.unlink()
    assert installed_checker.main([]) == 2
    assert "No embodiment files found." in capsys.readouterr().err


def test_path_consumers_and_missing_files_remain_real(installed_checker, tmp_path):
    path = tmp_path / "direct.json"
    path.write_text('{"id":"direct"}', encoding="utf-8")
    assert installed_checker.load_embodiment(path) == {"id": "direct"}
    with pytest.raises(FileNotFoundError):
        installed_checker.load_embodiment(tmp_path / "missing.json")
    installed_checker._SCHEMA_PATH.unlink()
    with pytest.raises(FileNotFoundError):
        installed_checker.load_schema()


def test_full_zip_cli_reads_bundled_entries(zip_checker, capsys):
    assert zip_checker.main(["--list"]) == 0
    assert "so_arm101" in capsys.readouterr().out
    assert zip_checker.main([]) == 0
    assert "All 6 embodiment(s) pass validation." in capsys.readouterr().out


@pytest.fixture(params=["source", "installed", "zip"])
def manifest_module(request):
    if request.param != "source":
        request.getfixturevalue(request.param + "_checker")
    return importlib.import_module("mnesis_canonical.manifest")


def test_manifest_schema_bytes_and_valid_roundtrip(manifest_module, tmp_path):
    expected = json.loads((PACKAGE / "manifest.schema.json").read_text(encoding="utf-8"))
    assert manifest_module._MANIFEST_SCHEMA == expected
    episode = tmp_path / "episode"
    episode.mkdir()
    (episode / "data.jsonl").write_text(
        '{"episode_index":7,"t_ns":1000000}\n{"episode_index":7,"t_ns":5000000}\n',
        encoding="utf-8",
    )
    result = manifest_module.write_manifest(episode)
    assert json.loads(result.read_text(encoding="utf-8"))["durationMs"] == 4
    assert manifest_module.validate_manifest(episode) == {"ok": True, "errors": []}


@pytest.mark.parametrize("bad_kind", ["json", "schema", "count"])
def test_manifest_bad_content_still_rejected(manifest_module, tmp_path, bad_kind):
    episode = tmp_path / "episode"
    episode.mkdir()
    (episode / "data.jsonl").write_text('{"episode_index":7,"t_ns":1000000}\n',
                                        encoding="utf-8")
    result = manifest_module.write_manifest(episode)
    if bad_kind == "json":
        result.write_text("{bad", encoding="utf-8")
        expected = "cannot parse manifest.json"
    else:
        data = json.loads(result.read_text(encoding="utf-8"))
        if bad_kind == "schema":
            data["durationMs"] = -1
            expected = "manifest violates schema"
        else:
            data["frameCount"] = 2
            expected = "frameCount mismatch"
        result.write_text(json.dumps(data), encoding="utf-8")
    validation = manifest_module.validate_manifest(episode)
    assert validation["ok"] is False
    assert any(expected in error for error in validation["errors"])


@pytest.mark.parametrize("bad_kind", ["missing", "json"])
@pytest.mark.parametrize("layout", ["installed", "zip"])
def test_missing_or_invalid_schema_fails_real_package_import(
    tmp_path, monkeypatch, bad_kind, layout
):
    target = tmp_path / "broken-package"
    shutil.copytree(PACKAGE, target / "mnesis_canonical",
                    ignore=shutil.ignore_patterns("__pycache__"))
    schema = target / "mnesis_canonical/manifest.schema.json"
    if bad_kind == "missing":
        schema.unlink()
        expected = FileNotFoundError
    else:
        schema.write_text("{bad", encoding="utf-8")
        expected = json.JSONDecodeError
    import_path = target
    if layout == "zip":
        import_path = tmp_path / "broken-package.zip"
        with zipfile.ZipFile(import_path, "w") as bundle:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(target).as_posix())
    saved = {n: m for n, m in sys.modules.items() if n.startswith("mnesis_canonical")}
    for name in saved:
        del sys.modules[name]
    monkeypatch.syspath_prepend(str(import_path))
    importlib.invalidate_caches()
    try:
        with pytest.raises(expected):
            importlib.import_module("mnesis_canonical")
    finally:
        for name in list(sys.modules):
            if name.startswith("mnesis_canonical"):
                del sys.modules[name]
        sys.modules.update(saved)
        importlib.invalidate_caches()
