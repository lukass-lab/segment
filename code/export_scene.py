#!/usr/bin/env python3
"""Export a `VesselScene` bundle for one vessel.

Layout follows perfect_vessel_viewer_plan.md / "Scene Bundle Format":

    vessel_scene_{patient}_{vessel}.zip
    ├── manifest.json
    ├── centerline.json
    ├── cpr/{cross_volume.nii.gz, long_volume.nii.gz, frame.json}
    ├── surfaces/{lumen.glb, wall.glb}
    ├── overlays/medis_rings.json
    ├── quant/per_station_metrics.json        (placeholder, populated later)
    ├── validation.json                        (from validate_scene.py)
    └── preview.png

Usage
-----
    python export_scene.py \\
        --patient 01-BER-0088 --vessel LAD \\
        --medis  ../data/..._lad.txt \\
        --cta    ../data/01-BER-0088.nii.gz \\
        --cross  ../data/01-BER-0088_LAD_cpr_cross.nii.gz \\
        --long   ../data/01-BER-0088_LAD_cpr_long.nii.gz \\
        --inner  ../data/01-BER-0088_LAD_inner.gii \\
        --outer  ../data/01-BER-0088_LAD_outer.gii \\
        --preview ../data/previews/slide.png \\
        --validation ../data/01-BER-0088_LAD_validation.json \\
        --out    ../data/vessel_scene_01-BER-0088_LAD.zip
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
import trimesh

import medis_to_cpr as mtc

SCHEMA_VERSION = "vessel_scene/0.1"


def git_hash(cwd: Path) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=cwd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None
    except Exception:
        return None


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gii_to_glb_bytes(gii_path: Path, color_rgba: tuple[int, int, int, int]) -> bytes:
    g = nib.load(str(gii_path))
    v = f = None
    for d in g.darrays:
        if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_POINTSET"]:
            v = np.asarray(d.data, dtype=np.float32)
        elif d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_TRIANGLE"]:
            f = np.asarray(d.data, dtype=np.int64)
    if v is None or f is None:
        raise ValueError(f"{gii_path} missing vertices or faces")
    mesh = trimesh.Trimesh(vertices=v, faces=f, process=False)
    mesh.visual.face_colors = color_rgba
    # Export to glTF binary (.glb)
    scene = trimesh.Scene(mesh)
    return scene.export(file_type="glb")


def centerline_json(centerline: np.ndarray, tangents: np.ndarray,
                    normals: np.ndarray, binormals: np.ndarray,
                    target_sp: float,
                    frame_method: str = "double_reflection_wang2008") -> dict:
    arc = np.concatenate([[0.0],
                          np.cumsum(np.linalg.norm(np.diff(centerline, axis=0), axis=1))])
    return {
        "schema":      "centerline/0.1",
        "n_stations":  int(len(centerline)),
        "spacing_mm":  float(target_sp),
        "total_length_mm": float(arc[-1]),
        "frame_method":   frame_method,
        "points":      centerline.astype(np.float64).tolist(),
        "tangents":    tangents.astype(np.float64).tolist(),
        "normals":     normals.astype(np.float64).tolist(),
        "binormals":   binormals.astype(np.float64).tolist(),
        "arc_length":  arc.astype(np.float64).tolist(),
    }


def medis_rings_json(lumen_rings, wall_rings):
    return {
        "schema":       "medis_rings/0.1",
        "n_lumen":      len(lumen_rings),
        "n_wall":       len(wall_rings),
        "lumen_world":  [r.astype(np.float64).tolist() for r in lumen_rings],
        "wall_world":   [r.astype(np.float64).tolist() for r in wall_rings],
        "note":         "ring points in world (mm) coordinates; one ring per traced slice",
    }


def per_station_metrics_placeholder(n_stations: int) -> dict:
    """Empty quant scaffold — filled in by a future quant pass."""
    return {
        "schema":       "per_station_metrics/0.1",
        "n_stations":   int(n_stations),
        "metrics":      [],  # list of {station, lumen_area_mm2, lumen_diam_eff_mm, ...}
        "note":         "placeholder — populated by quantify_scene.py once implemented",
    }


def lesion_summary_placeholder() -> dict:
    return {
        "schema":   "lesion_summary/0.1",
        "lesions":  [],
        "note":     "placeholder — populated by quantify_scene.py once implemented",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patient", required=True)
    ap.add_argument("--vessel",  required=True)
    ap.add_argument("--medis",   required=True)
    ap.add_argument("--cta",     required=True)
    ap.add_argument("--cross",   required=True)
    ap.add_argument("--long",    required=True)
    ap.add_argument("--inner",   required=True)
    ap.add_argument("--outer",   required=True)
    ap.add_argument("--preview", required=True)
    ap.add_argument("--validation", required=True)
    ap.add_argument("--out",     required=True)
    ap.add_argument("--include-cta", action="store_true",
                    help="embed full CTA NIfTI in the bundle (default: reference only)")
    args = ap.parse_args()

    medis = Path(args.medis); cta = Path(args.cta)
    cross = Path(args.cross); lng = Path(args.long)
    inner = Path(args.inner); outer = Path(args.outer)
    preview = Path(args.preview); val = Path(args.validation)
    out = Path(args.out)

    # ---- Compute centerline + frame (matches what was used in the CPR) ----
    contours, _, _ = mtc.parse_medis_contours_with_slicedist(str(medis))
    lumen_rings = contours["Lumen"]
    wall_rings  = contours["VesselWall"]
    cross_img = sitk.ReadImage(str(cross))
    target_sp = min(cross_img.GetSpacing())
    centerline_raw = mtc.extract_centerline(lumen_rings)
    centerline = mtc.resample_centerline(centerline_raw, target_sp)
    tangents = mtc.compute_tangent_vectors(centerline)
    frame_method = "double_reflection_wang2008"
    normals, binormals = mtc.compute_double_reflection_rmf(centerline, tangents)

    # ---- CTA provenance ----
    cta_img = sitk.ReadImage(str(cta))

    # ---- Render meshes to glTF in-memory ----
    print("Rendering meshes -> glTF...")
    lumen_glb = gii_to_glb_bytes(inner, color_rgba=(230, 57, 70, 255))
    wall_glb  = gii_to_glb_bytes(outer, color_rgba=(61, 165, 217, 90))

    # ---- Manifest ----
    repo_root = Path(__file__).resolve().parent.parent
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "patient_id":     args.patient,
        "vessel_name":    args.vessel,
        "source_type":    "medis",
        "created_at":     dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit":     git_hash(repo_root),
        "ct": {
            "path_referenced": str(cta) if not args.include_cta else None,
            "embedded":        args.include_cta,
            "size":            list(cta_img.GetSize()),
            "spacing":         list(cta_img.GetSpacing()),
            "origin":          list(cta_img.GetOrigin()),
            "direction":       list(cta_img.GetDirection()),
            "sha256":          sha256_file(cta),
        },
        "cpr": {
            "cross":     "cpr/cross_volume.nii.gz",
            "long":      "cpr/long_volume.nii.gz",
            "frame":     "cpr/frame.json",
            "pixel_spacing_mm": float(target_sp),
        },
        "surfaces": {
            "lumen": {"path": "surfaces/lumen.glb", "color_rgba": [230, 57, 70, 255]},
            "wall":  {"path": "surfaces/wall.glb",  "color_rgba": [61, 165, 217, 90]},
        },
        "overlays": {
            "medis_rings": "overlays/medis_rings.json",
        },
        "quant": {
            "per_station":     "quant/per_station_metrics.json",
            "lesion_summary":  "quant/lesion_summary.json",
        },
        "validation":  "validation.json",
        "preview":     "preview.png",
        "algorithm_versions": {
            "centerline_method":     "lumen_centroids (MEDIS) + cubic spline arc-length resample",
            "frame_method":          frame_method,
            "ct_reformat_order":     1,
            "mask_reformat_order":   0,
            "display_interpolation": "nearest",
            "cross_section_fov_mm":  14.0,
        },
    }

    # ---- Build zip --------------------------------------------------------
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing {out}...")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("centerline.json",
                   json.dumps(centerline_json(centerline, tangents, normals, binormals, target_sp,
                                              frame_method=frame_method), indent=2))
        z.writestr("cpr/frame.json",
                   json.dumps(centerline_json(centerline, tangents, normals, binormals, target_sp,
                                              frame_method=frame_method), indent=2))
        z.write(cross,  arcname="cpr/cross_volume.nii.gz")
        z.write(lng,    arcname="cpr/long_volume.nii.gz")
        z.writestr("surfaces/lumen.glb", lumen_glb)
        z.writestr("surfaces/wall.glb",  wall_glb)
        z.writestr("overlays/medis_rings.json",
                   json.dumps(medis_rings_json(lumen_rings, wall_rings)))
        z.writestr("quant/per_station_metrics.json",
                   json.dumps(per_station_metrics_placeholder(len(centerline)), indent=2))
        z.writestr("quant/lesion_summary.json",
                   json.dumps(lesion_summary_placeholder(), indent=2))
        if val.exists():
            z.write(val,     arcname="validation.json")
        if preview.exists():
            z.write(preview, arcname="preview.png")
        if args.include_cta and cta.exists():
            z.write(cta, arcname="ct/cta.nii.gz")

    sz_mb = out.stat().st_size / 1024 / 1024
    print(f"  wrote {out}  ({sz_mb:.1f} MB)")
    # listing
    with zipfile.ZipFile(out) as z:
        for info in z.infolist():
            print(f"    {info.file_size:>10d}  {info.filename}")


if __name__ == "__main__":
    sys.exit(main() or 0)
