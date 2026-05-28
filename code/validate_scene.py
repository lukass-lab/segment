#!/usr/bin/env python3
"""Validation report for one VesselScene.

Computes every metric from the *Mathematical Validation Metrics* section of
perfect_vessel_viewer_plan.md and emits validation.json + a pass/fail summary.

Usage
-----
    python validate_scene.py \\
        --medis  ../data/01-BER-0088_..._lad.txt \\
        --cta    ../data/01-BER-0088.nii.gz \\
        --cross  ../data/01-BER-0088_LAD_cpr_cross.nii.gz \\
        --inner  ../data/01-BER-0088_LAD_inner.gii \\
        --outer  ../data/01-BER-0088_LAD_outer.gii \\
        --out    ../data/01-BER-0088_LAD_validation.json
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import SimpleITK as sitk

import medis_to_cpr as mtc


# Thresholds documented in perfect_vessel_viewer_plan.md
TH_UNIT       = 1e-6   # |||T|-1| etc.
TH_PERP       = 1e-6   # |T·N| etc.
TH_HANDED     = 0.999  # det([T,N,B])
TH_RING_MM    = 1.0    # max out-of-plane residual (mm)
TH_AFF_ORIGIN = 1e-3   # mm
TH_AFF_DIR    = 1e-4   # dimensionless Frobenius
TH_AFF_SPACE  = 1e-3   # mm
TH_TWIST_DEG  = 5.0    # degrees


def load_gii_vertices(p: Path) -> np.ndarray:
    g = nib.load(str(p))
    for d in g.darrays:
        if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_POINTSET"]:
            return np.asarray(d.data, dtype=np.float64)
    raise ValueError(f"no POINTSET in {p}")


def projection_rmf(tangents: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return mtc.compute_rotation_minimizing_frame(tangents)


def double_reflection_rmf(centerline: np.ndarray, tangents: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return mtc.compute_double_reflection_rmf(centerline, tangents)


def frame_metrics(T: np.ndarray, N: np.ndarray, B: np.ndarray) -> dict:
    eps_unit = float(np.max(np.abs(np.linalg.norm(np.stack([T, N, B], -2), axis=-1) - 1.0)))
    eps_perp = float(np.max([
        np.max(np.abs(np.einsum("ij,ij->i", T, N))),
        np.max(np.abs(np.einsum("ij,ij->i", T, B))),
        np.max(np.abs(np.einsum("ij,ij->i", N, B))),
    ]))
    dets = np.einsum("ij,ij->i", np.cross(T, N), B)  # det([T,N,B]) per row
    handed_min = float(np.min(dets))
    return {
        "epsilon_unit": eps_unit,
        "epsilon_perp": eps_perp,
        "det_min":      handed_min,
    }


def angle_between(u: np.ndarray, v: np.ndarray) -> float:
    cos = float(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-30), -1.0, 1.0))
    return math.degrees(math.acos(cos))


def in_cta_bounds(points_world: np.ndarray, cta_img: sitk.Image) -> tuple[float, int]:
    """Return fraction in-bounds and number out-of-bounds."""
    sp = np.array(cta_img.GetSpacing())
    o  = np.array(cta_img.GetOrigin())
    Di = np.array(cta_img.GetDirection()).reshape(3, 3).T
    vox = (Di @ (points_world - o).T).T / sp
    sz = np.array(cta_img.GetSize())
    inside = np.all((vox >= 0) & (vox <= sz - 1), axis=1)
    return float(inside.mean()), int((~inside).sum())


def ring_out_of_plane_residuals(rings: list[np.ndarray],
                                centerline: np.ndarray,
                                tangents: np.ndarray) -> dict:
    centroids = np.array([r.mean(axis=0) for r in rings])
    rho_max, rho_mean = [], []
    for ring, c in zip(rings, centroids):
        s_idx = int(np.argmin(np.linalg.norm(centerline - c, axis=1)))
        d = ring - centerline[s_idx]
        proj = np.abs(d @ tangents[s_idx])
        rho_max.append(float(proj.max()))
        rho_mean.append(float(proj.mean()))
    return {
        "n_rings":         len(rings),
        "rho_max_mm":      max(rho_max),
        "rho_max_p95_mm":  float(np.percentile(rho_max, 95)),
        "rho_mean_mm":     float(np.mean(rho_mean)),
    }


def affine_metrics(img_a: sitk.Image, img_b: sitk.Image) -> dict:
    oa, ob = np.array(img_a.GetOrigin()),   np.array(img_b.GetOrigin())
    sa, sb = np.array(img_a.GetSpacing()),  np.array(img_b.GetSpacing())
    Da     = np.array(img_a.GetDirection()).reshape(3, 3)
    Db     = np.array(img_b.GetDirection()).reshape(3, 3)
    return {
        "epsilon_origin_mm":  float(np.linalg.norm(oa - ob)),
        "epsilon_direction":  float(np.linalg.norm(Da - Db, ord="fro")),
        "epsilon_spacing_mm": float(np.linalg.norm(sa - sb)),
    }


@dataclass
class Check:
    name: str
    value: Any
    threshold: Any
    op: str       # "lt" | "gt" | "eq"
    units: str

    def passed(self) -> bool:
        if self.value is None or (isinstance(self.value, float) and not math.isfinite(self.value)):
            return False
        if self.op == "lt": return self.value < self.threshold
        if self.op == "gt": return self.value > self.threshold
        if self.op == "eq": return self.value == self.threshold
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--medis", required=True)
    ap.add_argument("--cta",   required=True)
    ap.add_argument("--cross", required=True, help="CPR cross-section .nii.gz used in this scene")
    ap.add_argument("--inner", required=True, help="lumen mesh .gii")
    ap.add_argument("--outer", required=True, help="vessel-wall mesh .gii")
    ap.add_argument("--mask",  default=None,   help="optional mask .nii.gz")
    ap.add_argument("--out",   required=True)
    ap.add_argument("--frame-method", choices=["double_reflection", "projection"],
                    default="double_reflection",
                    help="Frame method used by the scene being validated (default: double_reflection).")
    args = ap.parse_args()

    # ---- Load --------------------------------------------------------------
    contours, _, _ = mtc.parse_medis_contours_with_slicedist(args.medis)
    lumen_rings = contours["Lumen"]
    wall_rings  = contours["VesselWall"]

    cta_img   = sitk.ReadImage(args.cta)
    cross_img = sitk.ReadImage(args.cross)
    inner_verts = load_gii_vertices(Path(args.inner))
    outer_verts = load_gii_vertices(Path(args.outer))

    centerline_raw = mtc.extract_centerline(lumen_rings)
    target_sp = min(cross_img.GetSpacing())
    centerline = mtc.resample_centerline(centerline_raw, target_sp)
    tangents = mtc.compute_tangent_vectors(centerline)
    N_proj, B_proj = projection_rmf(tangents)
    N_dr,   B_dr   = double_reflection_rmf(centerline, tangents)
    if args.frame_method == "projection":
        N_scene, B_scene = N_proj, B_proj
        scene_method = "projection_bishop"
    else:
        N_scene, B_scene = N_dr, B_dr
        scene_method = "double_reflection_wang2008"

    # ---- Frame quality for the frame method used by the scene -------------
    fm = frame_metrics(tangents, N_scene, B_scene)
    coverage_frac, oob = in_cta_bounds(centerline, cta_img)
    ring_stats = ring_out_of_plane_residuals(lumen_rings, centerline, tangents)

    # ---- Twist drift against preferred double-reflection frame ------------
    drift_per_station = [angle_between(N_scene[k], N_dr[k]) for k in range(len(N_scene))]
    twist_drift_deg = float(np.max(drift_per_station))
    projection_vs_double = [angle_between(N_proj[k], N_dr[k]) for k in range(len(N_proj))]

    # ---- Surface sanity (counts, basic non-manifold-edge check) ------------
    def mesh_stats(name, gii_path):
        g = nib.load(str(gii_path))
        v = f = None
        for d in g.darrays:
            if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_POINTSET"]: v = np.asarray(d.data)
            if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_TRIANGLE"]: f = np.asarray(d.data)
        # edge multiplicity
        edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], axis=0)
        edges = np.sort(edges, axis=1)
        uniq, counts = np.unique(edges, axis=0, return_counts=True)
        return {
            "name":            name,
            "n_vertices":      int(len(v)),
            "n_triangles":     int(len(f)),
            "n_edges_nonmanifold": int((counts > 2).sum()),
            "n_edges_boundary":    int((counts == 1).sum()),
        }

    surf_inner = mesh_stats("lumen",  Path(args.inner))
    surf_outer = mesh_stats("wall",   Path(args.outer))

    # ---- Optional mask affine check ---------------------------------------
    aff = None
    if args.mask is not None and Path(args.mask).exists():
        mask_img = sitk.ReadImage(args.mask)
        aff = affine_metrics(cta_img, mask_img)

    # ---- Build pass/fail table --------------------------------------------
    checks = [
        Check("frame.epsilon_unit",     fm["epsilon_unit"],   TH_UNIT,    "lt", ""),
        Check("frame.epsilon_perp",     fm["epsilon_perp"],   TH_PERP,    "lt", ""),
        Check("frame.det_min",          fm["det_min"],        TH_HANDED,  "gt", ""),
        Check("centerline.coverage",    coverage_frac,        1.0,        "eq", ""),
        Check("medis.rho_max_mm",       ring_stats["rho_max_mm"], TH_RING_MM, "lt", "mm"),
        Check("surface.lumen.nonmanifold_edges",  surf_inner["n_edges_nonmanifold"], 0, "eq", ""),
        Check("surface.wall.nonmanifold_edges",   surf_outer["n_edges_nonmanifold"], 0, "eq", ""),
        Check("twist_drift_deg",        twist_drift_deg,      TH_TWIST_DEG, "lt", "deg"),
    ]
    if aff is not None:
        checks += [
            Check("affine.epsilon_origin_mm",  aff["epsilon_origin_mm"],  TH_AFF_ORIGIN, "lt", "mm"),
            Check("affine.epsilon_direction",  aff["epsilon_direction"],  TH_AFF_DIR,    "lt", ""),
            Check("affine.epsilon_spacing_mm", aff["epsilon_spacing_mm"], TH_AFF_SPACE,  "lt", "mm"),
        ]

    # ---- Emit --------------------------------------------------------------
    report = {
        "schema_version": "validation/0.1",
        "patient_id":  Path(args.medis).stem.split("_")[0],
        "vessel":      Path(args.inner).stem.split("_")[1] if "_" in Path(args.inner).stem else "?",
        "centerline":  {
            "n_stations":     int(len(centerline)),
            "target_spacing_mm": float(target_sp),
            "arc_length_mm":  float(np.sum(np.linalg.norm(np.diff(centerline, axis=0), axis=1))),
            "coverage":       coverage_frac,
            "out_of_bounds":  oob,
        },
        "frame":     fm,
        "medis_rings": ring_stats,
        "surfaces":  {"lumen": surf_inner, "wall": surf_outer},
        "twist_drift": {
            "scene_method": scene_method,
            "reference_method": "double_reflection_wang2008",
            "max_angle_deg": twist_drift_deg,
            "p95_angle_deg": float(np.percentile(drift_per_station, 95)),
            "projection_vs_double_reflection_max_angle_deg": float(np.max(projection_vs_double)),
            "projection_vs_double_reflection_p95_angle_deg": float(np.percentile(projection_vs_double, 95)),
        },
        "affine": aff,
        "checks":    [
            {"name": c.name, "value": c.value, "threshold": c.threshold,
             "op": c.op, "units": c.units, "pass": c.passed()}
            for c in checks
        ],
        "summary":   {
            "total":  len(checks),
            "passed": sum(1 for c in checks if c.passed()),
            "failed": sum(1 for c in checks if not c.passed()),
        },
    }

    Path(args.out).write_text(json.dumps(report, indent=2))
    # human summary
    print(f"\nVALIDATION  ({report['patient_id']} / {report['vessel']})")
    print(f"  arc length     {report['centerline']['arc_length_mm']:.1f} mm  "
          f"({report['centerline']['n_stations']} stations @ {report['centerline']['target_spacing_mm']:.3f} mm)")
    print(f"  twist drift    max {twist_drift_deg:.3f}°  p95 "
          f"{report['twist_drift']['p95_angle_deg']:.3f}°")
    print(f"  MEDIS residual max {ring_stats['rho_max_mm']:.3f} mm  "
          f"(p95 {ring_stats['rho_max_p95_mm']:.3f} mm)")
    print()
    for c in checks:
        flag = "PASS" if c.passed() else "FAIL"
        val = f"{c.value:.3g}" if isinstance(c.value, float) else str(c.value)
        thr = f"{c.threshold:.3g}" if isinstance(c.threshold, float) else str(c.threshold)
        unit = f" {c.units}" if c.units else ""
        print(f"  [{flag}] {c.name:42s} = {val:>10s}{unit}  ({c.op} {thr})")
    print(f"\n  {report['summary']['passed']}/{report['summary']['total']} checks passed")
    print(f"  written: {args.out}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
