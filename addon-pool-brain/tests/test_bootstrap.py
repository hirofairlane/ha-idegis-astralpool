"""Tests for the package auto-bootstrap.

Use `tmp_path` instead of touching `/homeassistant`. We don't test the
reload services here — those are HA-side and require the network
HA client, which is mocked separately.
"""
from __future__ import annotations

from pathlib import Path

import bootstrap
import pytest


@pytest.fixture
def sample_source(tmp_path: Path) -> Path:
    src = tmp_path / "src" / "idegis_pool_brain.yaml"
    src.parent.mkdir(parents=True)
    src.write_text("# initial content\nautomation: []\n")
    return src


def test_first_run_creates_package(tmp_path: Path, sample_source: Path):
    result = bootstrap.write_package(source=sample_source, ha_config_root=tmp_path)
    assert result["changed"] is True
    assert result["backup"] is None
    target = Path(result["path"])
    assert target.exists()
    assert target.read_text() == sample_source.read_text()


def test_second_run_is_noop_when_content_matches(tmp_path: Path, sample_source: Path):
    bootstrap.write_package(source=sample_source, ha_config_root=tmp_path)
    result = bootstrap.write_package(source=sample_source, ha_config_root=tmp_path)
    assert result["changed"] is False
    assert result["backup"] is None
    assert "up to date" in (result["reason"] or "")


def test_user_edited_file_is_backed_up(tmp_path: Path, sample_source: Path):
    bootstrap.write_package(source=sample_source, ha_config_root=tmp_path)
    target = tmp_path / "packages" / sample_source.name
    target.write_text("# user edited\nautomation:\n  - id: mine\n")
    # Now the source changes too (e.g. addon upgrade).
    sample_source.write_text("# new addon version\nautomation: []\n")
    result = bootstrap.write_package(source=sample_source, ha_config_root=tmp_path)
    assert result["changed"] is True
    assert result["backup"] is not None
    backup = Path(result["backup"])
    assert backup.exists()
    assert "user edited" in backup.read_text()
    assert "new addon version" in target.read_text()


def test_packages_dir_is_created_if_missing(tmp_path: Path, sample_source: Path):
    # tmp_path/packages does NOT exist yet.
    assert not (tmp_path / "packages").exists()
    bootstrap.write_package(source=sample_source, ha_config_root=tmp_path)
    assert (tmp_path / "packages").is_dir()


def test_missing_source_raises(tmp_path: Path):
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        bootstrap.write_package(source=missing, ha_config_root=tmp_path)


def test_reload_domains_calls_each_domain(monkeypatch):
    calls: list[tuple[str, str, dict]] = []

    class FakeHA:
        async def call_service(self, domain, service, data):
            calls.append((domain, service, data))
            return True

    import asyncio

    asyncio.run(bootstrap.reload_domains(FakeHA()))

    assert [c[0] for c in calls] == list(bootstrap.RELOAD_DOMAINS)
    assert all(c[1] == "reload" for c in calls)
    assert all(c[2] == {} for c in calls)


def test_reload_domains_logs_warning_on_failure(monkeypatch, caplog):
    class FailingHA:
        async def call_service(self, domain, service, data):
            return False

    import asyncio
    import logging

    with caplog.at_level(logging.WARNING):
        asyncio.run(bootstrap.reload_domains(FailingHA()))

    assert any("reload" in r.message for r in caplog.records)
