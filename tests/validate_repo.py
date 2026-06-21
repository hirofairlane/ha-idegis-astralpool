#!/usr/bin/env python3
"""Static repo validation used by CI (and runnable locally).

This repo ships several independent components; this script validates the
cross-cutting, structural invariants of each:

  * every shipped YAML (add-on configs/builds, repository.yaml, HACS info,
    HA packages, dashboards, esphome) parses as YAML,
  * the HACS integration manifest.json is valid JSON and carries the
    required `domain` + `version` keys,
  * hacs.json is valid JSON,
  * each add-on's config.yaml `version` matches the VERSION constant baked
    into its Python source (the value the running code reports), so a
    release can't ship a code/metadata version skew.

Exit non-zero on any failure.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class _TolerantLoader(yaml.SafeLoader):
    """SafeLoader that tolerates Home Assistant / ESPHome custom tags.

    Files like esphome/*.yaml and ha-packages/*.yaml use domain-specific
    tags (``!secret``, ``!include``, ``!lambda``, ``!input`` …) that a plain
    SafeLoader rejects. We only want to assert the YAML is *well-formed*, not
    resolve those tags, so any unknown tag is parsed into a plain Python value.
    """


def _construct_unknown(loader: yaml.Loader, tag_suffix, node):  # noqa: ANN001
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_TolerantLoader.add_multi_constructor("!", _construct_unknown)

# YAML files that must parse. Globs are expanded relative to ROOT.
YAML_GLOBS = (
    "repository.yaml",
    "addon/config.yaml",
    "addon/build.yaml",
    "addon-pool-brain/config.yaml",
    "addon-pool-brain/build.yaml",
    "ha-packages/*.yaml",
    "dashboards/*.yaml",
    "esphome/*.yaml",
)

# JSON files that must parse.
JSON_FILES = (
    "hacs.json",
    "custom_components/idegis_astralpool/manifest.json",
)

# (config.yaml, python source, regex capturing the version literal)
VERSION_SYNC = (
    (
        "addon/config.yaml",
        "addon/rootfs/opt/idegis/capturer.py",
        r'ADDON_VERSION\s*=\s*"([^"]+)"',
    ),
    (
        "addon-pool-brain/config.yaml",
        "addon-pool-brain/rootfs/opt/pool_brain/mqtt_pub.py",
        r'"sw_version"\s*:\s*"([^"]+)"',
    ),
)


def _check_yaml(errors: list[str]) -> None:
    for pattern in YAML_GLOBS:
        matches = sorted(ROOT.glob(pattern)) if "*" in pattern else [ROOT / pattern]
        if not matches:
            errors.append(f"no YAML matched pattern: {pattern}")
            continue
        for path in matches:
            try:
                # load_all + tolerant loader: some files are multi-doc and
                # many use HA/ESPHome custom tags we don't need to resolve.
                list(yaml.load_all(path.read_text(), Loader=_TolerantLoader))
                print(f"OK   yaml {path.relative_to(ROOT)}")
            except Exception as exc:  # noqa: BLE001 - report any parse error
                errors.append(f"YAML parse failed for {path.relative_to(ROOT)}: {exc}")


def _check_json(errors: list[str]) -> None:
    for rel in JSON_FILES:
        path = ROOT / rel
        try:
            data = json.loads(path.read_text())
            print(f"OK   json {rel}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"JSON parse failed for {rel}: {exc}")
            continue
        if rel.endswith("manifest.json"):
            for key in ("domain", "version"):
                if not data.get(key):
                    errors.append(f"{rel}: missing required key '{key}'")
            if data.get("domain") and data["domain"] != "idegis_astralpool":
                errors.append(
                    f"{rel}: domain '{data['domain']}' != 'idegis_astralpool'"
                )


def _check_version_sync(errors: list[str]) -> None:
    for cfg_rel, src_rel, pattern in VERSION_SYNC:
        cfg = yaml.safe_load((ROOT / cfg_rel).read_text())
        cfg_version = cfg.get("version") if isinstance(cfg, dict) else None
        src = (ROOT / src_rel).read_text()
        m = re.search(pattern, src)
        src_version = m.group(1) if m else None
        if cfg_version and cfg_version == src_version:
            print(f"OK   version in sync: {cfg_rel} == {src_rel} ({cfg_version})")
        else:
            errors.append(
                f"version mismatch: {cfg_rel}={cfg_version} "
                f"{src_rel}={src_version}"
            )


def main() -> int:
    errors: list[str] = []
    _check_yaml(errors)
    _check_json(errors)
    _check_version_sync(errors)

    if errors:
        print("\nFAIL:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nAll static checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
