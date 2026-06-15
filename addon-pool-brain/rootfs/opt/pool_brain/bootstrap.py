"""Auto-bootstrap of the companion HA package.

The add-on ships a YAML package (helpers, scripts, automations) under
`packages/idegis_pool_brain.yaml`. When the add-on starts and the
option `auto_bootstrap_package` is true (default), this module copies
that file into the user's Home Assistant `packages/` directory so the
companion automations become available without the user having to
clone the repo and paste files by hand.

Rules:

- Idempotent: re-copying the same content is a no-op.
- Versioned: we compare bytes; if the user has edited the file by hand,
  we don't blindly overwrite — we back up the user's version first to
  `.bak.<timestamp>` and then write ours.
- Hot reload: after writing, we call the HA reload services for the
  domains used in the package so the user doesn't have to restart HA.

The HA `/config` directory is mounted under `/homeassistant` inside the
add-on container (config.yaml has `homeassistant_config: rw`).
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

log = logging.getLogger("pool_brain.bootstrap")

HA_CONFIG_PATH = Path(os.environ.get("HA_CONFIG_PATH", "/homeassistant"))
PACKAGE_FILENAME = "idegis_pool_brain.yaml"
SOURCE_PATH = Path(__file__).parent / "packages" / PACKAGE_FILENAME

RELOAD_DOMAINS = (
    "input_text",
    "input_number",
    "input_boolean",
    "script",
    "automation",
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ensure_packages_dir(root: Path) -> Path:
    """Create `<root>/packages/` if it does not exist. Return it."""
    pkg_dir = root / "packages"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    return pkg_dir


def _backup(target: Path) -> Path | None:
    """Back up a file before overwriting it. Returns the backup path."""
    if not target.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = target.with_suffix(target.suffix + f".bak.{stamp}")
    shutil.copy2(target, backup)
    return backup


def write_package(
    *,
    source: Path = SOURCE_PATH,
    ha_config_root: Path | None = None,
) -> dict[str, str | bool]:
    """Copy the embedded package into the HA config tree.

    Returns a dict with the outcome: `{"changed": bool, "path": str,
    "backup": str | None, "reason": str}`. Doesn't raise on regular
    cases; raises only if the source itself is missing (developer
    error).
    """
    if not source.exists():
        raise FileNotFoundError(
            f"Bootstrap source missing at {source}; check the addon image."
        )

    root = ha_config_root or HA_CONFIG_PATH
    pkg_dir = _ensure_packages_dir(root)
    target = pkg_dir / source.name

    source_bytes = source.read_bytes()

    if target.exists():
        existing_bytes = target.read_bytes()
        if _digest(existing_bytes) == _digest(source_bytes):
            return {
                "changed": False,
                "path": str(target),
                "backup": None,
                "reason": "already up to date",
            }
        backup = _backup(target)
        target.write_bytes(source_bytes)
        return {
            "changed": True,
            "path": str(target),
            "backup": str(backup) if backup else None,
            "reason": "user-edited file backed up; addon version written",
        }

    target.write_bytes(source_bytes)
    return {
        "changed": True,
        "path": str(target),
        "backup": None,
        "reason": "package created for the first time",
    }


async def reload_domains(ha_client) -> dict[str, bool]:
    """Trigger reload services for the domains the package uses.

    Pass the singleton HA client (from `ha_client.HA`) so this stays
    testable.
    """
    results: dict[str, bool] = {}
    for domain in RELOAD_DOMAINS:
        ok = await ha_client.call_service(domain, "reload", {})
        results[domain] = ok
        if not ok:
            log.warning("reload %s did not return OK", domain)
    return results
