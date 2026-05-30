#!/usr/bin/env python3

"""Build runtime map config from a user-editable JSON source.

Usage examples:
- python3 build_map.py
- python3 build_map.py json=layers-dev.json
- python3 build_map.py json=dev-layors.json test=true
- python3 build_map.py json=dev-layors.json test=test.sh

Behavior:
- Reads source JSON (default: layers-dev.json)
- Writes runtime JSON (layers.json)
- Ensures index.html points to layers.json
- Creates backup tar at /backup/<timestamp>.tar before writing
- If tests fail, reverts changed files from backup tar
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE_NAME = "layers-dev.json"
TARGET_PATH = ROOT / "layers.json"
INDEX_PATH = ROOT / "index.html"
BACKUP_DIR = ROOT / "backup"

TOP_LEVEL_LIST_KEYS = ["baseMaps", "mapLayers", "localMapLayers", "restQueries", "localQueries"]


def die(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def parse_kv_args(argv: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for token in argv:
        if token in {"-h", "--help", "help"}:
            print(__doc__)
            sys.exit(0)
        if "=" not in token:
            die(f"Invalid argument '{token}'. Use key=value format.")
        key, value = token.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key:
            die(f"Invalid argument '{token}'. Missing key before '='.")
        parsed[key] = value
    return parsed


def parse_test_mode(raw_value: str | None) -> tuple[bool, str | None, str]:
    if raw_value is None:
        return False, None, "disabled"

    value = raw_value.strip()
    lowered = value.lower()
    if lowered in {"", "0", "false", "no", "n", "off"}:
        return False, None, "disabled"
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True, None, "builtin"

    # Any non-boolean value is treated as a custom test script path.
    script = Path(value)
    if not script.is_absolute():
        script = ROOT / script
    return True, str(script), "custom"


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        die(f"Missing required file: {path}")
    except json.JSONDecodeError as exc:
        die(f"Invalid JSON in {path}: {exc}")


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    return default


def ensure_list(config: dict[str, Any], key: str) -> list[Any]:
    value = config.get(key, [])
    if value is None:
        return []
    if isinstance(value, list):
        return value
    die(f"Top-level key '{key}' must be a JSON array")


def normalize_map_layers(items: list[Any], key_name: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            die(f"{key_name}[{i}] must be an object")

        entry = dict(item)
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            die(f"{key_name}[{i}].name is required and must be a string")

        if key_name == "mapLayers":
            url = entry.get("url")
            if not isinstance(url, str) or not url.strip():
                die(f"{key_name}[{i}].url is required and must be a string")

            options = entry.get("options") or {}
            if not isinstance(options, dict):
                die(f"{key_name}[{i}].options must be an object")
            entry["options"] = options

        if key_name == "localMapLayers":
            table = entry.get("table")
            if not isinstance(table, str) or not table.strip():
                die(f"{key_name}[{i}].table is required and must be a string")

        entry["visibleByDefault"] = to_bool(entry.get("visibleByDefault"), default=False)
        normalized.append(entry)
    return normalized


def normalize_rest_queries(items: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            die(f"restQueries[{i}] must be an object")

        entry = dict(item)
        for required in ["label", "url"]:
            if not isinstance(entry.get(required), str) or not entry[required].strip():
                die(f"restQueries[{i}].{required} is required and must be a string")

        if "positiveText" not in entry:
            entry["positiveText"] = "Yes"
        if "negativeText" not in entry:
            entry["negativeText"] = "No"

        normalized.append(entry)
    return normalized


def normalize_local_queries(items: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            die(f"localQueries[{i}] must be an object")

        entry = dict(item)
        if not isinstance(entry.get("label"), str) or not entry["label"].strip():
            die(f"localQueries[{i}].label is required and must be a string")

        payload = entry.get("payload")
        if payload is None and isinstance(entry.get("arguments"), dict):
            payload = entry.get("arguments")
            entry["payload"] = payload
            entry.pop("arguments", None)
        if not isinstance(payload, dict):
            die(f"localQueries[{i}].payload must be an object")
        for required in ["table", "column"]:
            if not isinstance(payload.get(required), str) or not payload[required].strip():
                die(f"localQueries[{i}].payload.{required} is required and must be a string")

        entry["endpoint"] = entry.get("endpoint") or "/api/local_intersect"
        if not isinstance(entry["endpoint"], str):
            die(f"localQueries[{i}].endpoint must be a string")

        if "fallbackText" not in entry:
            entry["fallbackText"] = "No Data"

        normalized.append(entry)
    return normalized


def normalize_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        die("Source config root must be a JSON object")

    config = dict(raw)
    for key in TOP_LEVEL_LIST_KEYS:
        config[key] = ensure_list(config, key)

    config["baseMaps"] = normalize_map_layers(config["baseMaps"], "baseMaps")
    config["mapLayers"] = normalize_map_layers(config["mapLayers"], "mapLayers")
    config["localMapLayers"] = normalize_map_layers(config["localMapLayers"], "localMapLayers")
    config["restQueries"] = normalize_rest_queries(config["restQueries"])
    config["localQueries"] = normalize_local_queries(config["localQueries"])
    return config


def update_index_config_reference() -> bool:
    text = INDEX_PATH.read_text(encoding="utf-8")
    changed = False

    if "const LAYERS_CONFIG_PATH = " not in text:
        anchor = "const BUILD_FALLBACK_VERSION = 'v1.0.0';"
        injection = anchor + "\n        const LAYERS_CONFIG_PATH = 'layers.json';"
        if anchor in text:
            text = text.replace(anchor, injection, 1)
            changed = True
        else:
            die("Could not find build constant block in index.html")
    else:
        updated = re.sub(
            r"const\s+LAYERS_CONFIG_PATH\s*=\s*['\"][^'\"]+['\"];",
            "const LAYERS_CONFIG_PATH = 'layers.json';",
            text,
            count=1,
        )
        if updated != text:
            text = updated
            changed = True

    updated_fetch = re.sub(
        r"fetch\(\s*['\"]layers\.json\?v=['\"]\s*\+\s*new Date\(\)\.getTime\(\)\s*\)",
        "fetch(LAYERS_CONFIG_PATH + '?v=' + new Date().getTime())",
        text,
        count=1,
    )
    if updated_fetch != text:
        text = updated_fetch
        changed = True

    if changed:
        INDEX_PATH.write_text(text, encoding="utf-8")
    return changed


def write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def create_backup(paths: list[Path]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    backup_path = BACKUP_DIR / f"{stamp}.tar"

    with tarfile.open(backup_path, "w") as tar:
        for path in paths:
            if path.exists():
                tar.add(path, arcname=path.relative_to(ROOT))

    return backup_path


def restore_from_backup(backup_path: Path) -> None:
    if not backup_path.exists():
        die(f"Cannot restore; backup file missing: {backup_path}")

    with tarfile.open(backup_path, "r") as tar:
        for member in tar.getmembers():
            if member.isdir():
                continue
            destination = ROOT / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            if src is None:
                continue
            with destination.open("wb") as dst:
                dst.write(src.read())


def run_builtin_tests(normalized: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    generated = load_json(TARGET_PATH)
    for key in TOP_LEVEL_LIST_KEYS:
        if key not in generated or not isinstance(generated[key], list):
            failures.append(f"layers.json missing/invalid top-level list: {key}")

    index_text = INDEX_PATH.read_text(encoding="utf-8")
    if "const LAYERS_CONFIG_PATH = 'layers.json';" not in index_text:
        failures.append("index.html missing LAYERS_CONFIG_PATH constant")
    if "fetch(LAYERS_CONFIG_PATH + '?v=' + new Date().getTime())" not in index_text:
        failures.append("index.html missing config fetch using LAYERS_CONFIG_PATH")

    for i, query in enumerate(normalized.get("localQueries", []), start=1):
        payload = query.get("payload", {})
        if not payload.get("table") or not payload.get("column"):
            failures.append(f"localQueries[{i}] payload missing table/column")

    return failures


def run_custom_test_script(script_path: str) -> tuple[bool, str]:
    script = Path(script_path)
    if not script.exists():
        return False, f"Custom test script not found: {script}"

    result = subprocess.run(["bash", str(script)], cwd=ROOT)
    if result.returncode != 0:
        return False, f"Custom test script failed with exit code {result.returncode}: {script}"
    return True, f"Custom test script passed: {script}"


def main() -> None:
    args = parse_kv_args(sys.argv[1:])
    source_name = args.get("json", DEFAULT_SOURCE_NAME)
    run_tests, custom_test_script, test_mode = parse_test_mode(args.get("test"))

    source_path = Path(source_name)
    if not source_path.is_absolute():
        source_path = ROOT / source_path

    if not source_path.exists():
        if TARGET_PATH.exists():
            shutil.copyfile(TARGET_PATH, source_path)
            print(f"Created {source_path.name} from existing {TARGET_PATH.name}")
            print(f"Edit {source_path.name}, then run this command again.")
            return
        die(f"Neither {source_path.name} nor {TARGET_PATH.name} exists")

    source = load_json(source_path)
    normalized = normalize_config(source)

    backup_path = create_backup([TARGET_PATH, INDEX_PATH])
    print(f"Backup created: {backup_path}")

    try:
        write_json(TARGET_PATH, normalized)
        index_updated = update_index_config_reference()

        if run_tests:
            if custom_test_script:
                ok, message = run_custom_test_script(custom_test_script)
                print(message)
                if not ok:
                    raise RuntimeError(message)
            else:
                failures = run_builtin_tests(normalized)
                if failures:
                    raise RuntimeError("; ".join(failures))
                print("Built-in tests passed")
        else:
            print("Tests skipped")
    except Exception as exc:
        restore_from_backup(backup_path)
        die(f"Build failed and reverted from backup: {backup_path}\nReason: {exc}")

    print("Build complete")
    print(f"- Source: {source_path.name}")
    print(f"- Output: {TARGET_PATH.name}")
    print(f"- Test mode: {test_mode}")
    print(
        "- Index update: "
        + ("updated config reference in index.html" if index_updated else "already aligned")
    )
    print(
        "- Counts: "
        f"baseMaps={len(normalized['baseMaps'])}, "
        f"mapLayers={len(normalized['mapLayers'])}, "
        f"localMapLayers={len(normalized['localMapLayers'])}, "
        f"restQueries={len(normalized['restQueries'])}, "
        f"localQueries={len(normalized['localQueries'])}"
    )


if __name__ == "__main__":
    main()