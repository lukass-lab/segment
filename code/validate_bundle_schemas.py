#!/usr/bin/env python3
"""Validate a VesselScene bundle against the plan JSON Schemas.

This is intentionally a schema-level check only: it verifies artifact shape,
required fields, paths, and primitive types. Numerical/clinical validity remains
the job of validate_scene.py.

Usage:
    python code/validate_bundle_schemas.py data/vessel_scene_01-BER-0088_LAD.zip
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_ARTIFACTS = [
    ("vessel_scene_manifest", "manifest.json"),
    ("centerline", "centerline.json"),
    ("centerline", "cpr/frame.json"),
    ("per_station_metrics", "quant/per_station_metrics.json"),
    ("lesion_summary", "quant/lesion_summary.json"),
    ("validation", "validation.json"),
    ("medis_rings", "overlays/medis_rings.json"),
]


def load_schema(schema_dir: Path, name: str) -> dict:
    path = schema_dir / f"{name}.schema.json"
    with path.open() as f:
        schema = json.load(f)
    Draft202012Validator.check_schema(schema)
    return schema


def validate_artifact(zf: zipfile.ZipFile, schema_dir: Path, schema_name: str, artifact: str) -> list[str]:
    if artifact not in zf.namelist():
        return [f"missing artifact: {artifact}"]

    schema = load_schema(schema_dir, schema_name)
    instance = json.loads(zf.read(artifact))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    messages = []
    for error in errors:
        location = "/".join(str(p) for p in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to vessel_scene_*.zip")
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "plan" / "schemas",
        help="Directory containing *.schema.json files.",
    )
    args = parser.parse_args()

    if not args.bundle.exists():
        parser.error(f"bundle does not exist: {args.bundle}")
    if not args.schema_dir.exists():
        parser.error(f"schema directory does not exist: {args.schema_dir}")

    total_errors = 0
    with zipfile.ZipFile(args.bundle) as zf:
        names = set(zf.namelist())

        for schema_name, artifact in SCHEMA_ARTIFACTS:
            errors = validate_artifact(zf, args.schema_dir, schema_name, artifact)
            if errors:
                total_errors += len(errors)
                print(f"FAIL  {artifact}  ({schema_name})")
                for msg in errors[:10]:
                    print(f"  - {msg}")
                if len(errors) > 10:
                    print(f"  ... {len(errors) - 10} more")
            else:
                print(f"PASS  {artifact}  ({schema_name})")

        manifest = json.loads(zf.read("manifest.json")) if "manifest.json" in names else {}
        referenced = [
            manifest.get("cpr", {}).get("cross"),
            manifest.get("cpr", {}).get("long"),
            manifest.get("cpr", {}).get("frame"),
            manifest.get("surfaces", {}).get("lumen", {}).get("path"),
            manifest.get("surfaces", {}).get("wall", {}).get("path"),
            manifest.get("overlays", {}).get("medis_rings"),
            manifest.get("quant", {}).get("per_station"),
            manifest.get("quant", {}).get("lesion_summary"),
            manifest.get("validation"),
            manifest.get("preview"),
        ]
        for ref in [r for r in referenced if r]:
            if ref not in names:
                total_errors += 1
                print(f"FAIL  manifest reference missing from zip: {ref}")

    if total_errors:
        print(f"\nSchema validation failed: {total_errors} error(s)")
        return 1
    print("\nSchema validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
