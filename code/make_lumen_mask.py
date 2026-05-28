#!/usr/bin/env python3
"""Rasterize the MEDIS-derived lumen surface into a voxel mask aligned to the CTA grid.

Output is a NIfTI binary volume with the same affine as the source CTA, so the
mask drops in next to any downstream tool that already knows how to read the CTA.

Used to dry-run the mask-based pipeline (centerline-from-mask, surfaces, CPR) on
known geometry before any vendor plaque-mask data arrives.

Default method is VTK polydata-to-image stenciling in voxel-index space. This
avoids millions of per-point ray casts and preserves CTA alignment by converting
world-coordinate mesh vertices into CTA voxel coordinates before rasterization.
The older trimesh ray-cast path is available with ``--method trimesh``.

Usage
-----
    python make_lumen_mask.py \\
        --mesh ../data/01-BER-0088_LAD_inner.gii \\
        --cta  ../data/01-BER-0088.nii.gz \\
        --out  ../data/01-BER-0088_LAD_lumen_mask.nii.gz
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
import medis_to_cpr as mtc  # noqa: E402


def load_gii_mesh(p: Path) -> trimesh.Trimesh:
    g = nib.load(str(p))
    v = f = None
    for d in g.darrays:
        if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_POINTSET"]:
            v = np.asarray(d.data, dtype=np.float64)
        elif d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_TRIANGLE"]:
            f = np.asarray(d.data, dtype=np.int64)
    if v is None or f is None:
        raise ValueError(f"{p}: missing POINTSET or TRIANGLE darray")
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def world_to_vox_grid(world_pts: np.ndarray, cta_img: sitk.Image) -> np.ndarray:
    """Apply (i, j, k) = D^T (p - o) / s, the inverse of voxel-to-world."""
    sp = np.array(cta_img.GetSpacing())
    o  = np.array(cta_img.GetOrigin())
    Di = np.array(cta_img.GetDirection()).reshape(3, 3).T
    return (Di @ (world_pts - o).T).T / sp


def vox_to_world_grid(vox_pts: np.ndarray, cta_img: sitk.Image) -> np.ndarray:
    """p = o + D · diag(s) · (i, j, k)."""
    sp = np.array(cta_img.GetSpacing())
    o  = np.array(cta_img.GetOrigin())
    D  = np.array(cta_img.GetDirection()).reshape(3, 3)
    return o + (D @ (sp[:, None] * vox_pts.T)).T


def mesh_voxel_bbox(mesh: trimesh.Trimesh, cta_img: sitk.Image,
                    margin_voxels: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return clipped voxel-index bbox (v0, v1, size_xyz)."""
    size = np.array(cta_img.GetSize())  # (X, Y, Z) in SITK convention

    bbox_world = np.stack([mesh.bounds[0], mesh.bounds[1]])
    bbox_vox = world_to_vox_grid(bbox_world, cta_img)
    v0 = np.floor(bbox_vox.min(axis=0)).astype(int) - margin_voxels
    v1 = np.ceil (bbox_vox.max(axis=0)).astype(int) + margin_voxels
    v0 = np.clip(v0, 0, size - 1)
    v1 = np.clip(v1, 0, size - 1)
    return v0, v1, size


def rasterize_mesh_vtk(mesh: trimesh.Trimesh, cta_img: sitk.Image,
                       margin_voxels: int = 2) -> np.ndarray:
    """Voxelize a closed mesh via VTK stencil. Return mask as (z, y, x) uint8."""
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy

    v0, v1, size = mesh_voxel_bbox(mesh, cta_img, margin_voxels)
    nq = (v1 - v0 + 1)
    print(f"  query bbox (voxels): {v0.tolist()} → {v1.tolist()}  size {nq.tolist()}  "
          f"= {int(np.prod(nq)):,} voxels")

    # Convert world-coordinate vertices to voxel-index coordinates. The VTK
    # image grid below then lives in the same coordinate system as voxel centers.
    verts_vox = world_to_vox_grid(mesh.vertices, cta_img).astype(np.float32)

    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(verts_vox, deep=True))

    faces = np.asarray(mesh.faces, dtype=np.int64)
    cells = np.empty((len(faces), 4), dtype=np.int64)
    cells[:, 0] = 3
    cells[:, 1:] = faces
    polys = vtk.vtkCellArray()
    polys.SetCells(len(faces), numpy_to_vtk(cells.ravel(), deep=True, array_type=vtk.VTK_ID_TYPE))

    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(polys)

    white = vtk.vtkImageData()
    white.SetSpacing(1.0, 1.0, 1.0)
    white.SetOrigin(0.0, 0.0, 0.0)
    white.SetExtent(int(v0[0]), int(v1[0]), int(v0[1]), int(v1[1]), int(v0[2]), int(v1[2]))
    white.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    vtk_to_numpy(white.GetPointData().GetScalars())[:] = 1

    stencil = vtk.vtkPolyDataToImageStencil()
    stencil.SetInputData(poly)
    stencil.SetOutputSpacing(1.0, 1.0, 1.0)
    stencil.SetOutputOrigin(0.0, 0.0, 0.0)
    stencil.SetOutputWholeExtent(white.GetExtent())

    t0 = time.time()
    stencil.Update()

    imgstenc = vtk.vtkImageStencil()
    imgstenc.SetInputData(white)
    imgstenc.SetStencilConnection(stencil.GetOutputPort())
    imgstenc.ReverseStencilOff()
    imgstenc.SetBackgroundValue(0)
    imgstenc.Update()
    dt = time.time() - t0

    sub_flat = vtk_to_numpy(imgstenc.GetOutput().GetPointData().GetScalars()).astype(np.uint8)
    sub = sub_flat.reshape((nq[2], nq[1], nq[0]))  # VTK x-fastest order -> z,y,x
    n_in = int(sub.sum())
    print(f"  VTK stencil: {dt:.1f} s  ({n_in:,} inside / {sub.size:,} bbox voxels, "
          f"{100*n_in/sub.size:.2f}%)")

    mask = np.zeros((size[2], size[1], size[0]), dtype=np.uint8)
    mask[v0[2]:v1[2]+1, v0[1]:v1[1]+1, v0[0]:v1[0]+1] = sub
    return mask


def rasterize_mesh_trimesh(mesh: trimesh.Trimesh, cta_img: sitk.Image,
                           margin_voxels: int = 2) -> np.ndarray:
    """Ray-cast voxelization fallback. Slower than VTK for this mesh."""
    v0, v1, size = mesh_voxel_bbox(mesh, cta_img, margin_voxels)
    nq = (v1 - v0 + 1)
    print(f"  query bbox (voxels): {v0.tolist()} → {v1.tolist()}  size {nq.tolist()}  "
          f"= {int(np.prod(nq)):,} points")

    # Build voxel grid in (i, j, k) order; convert to world for containment test.
    ii, jj, kk = np.meshgrid(
        np.arange(v0[0], v1[0] + 1),
        np.arange(v0[1], v1[1] + 1),
        np.arange(v0[2], v1[2] + 1),
        indexing="ij",
    )
    vox = np.stack([ii.ravel(), jj.ravel(), kk.ravel()], axis=-1).astype(np.float64)
    world = vox_to_world_grid(vox, cta_img)

    # trimesh.contains does ray-casting; on watertight meshes it is reliable.
    t0 = time.time()
    inside = mesh.contains(world)
    dt = time.time() - t0
    n_in = int(inside.sum())
    print(f"  containment query: {dt:.1f} s  ({n_in:,} inside / {len(inside):,} total, "
          f"{100*n_in/len(inside):.2f}%)")

    # Reshape back to the bbox grid in (i, j, k) and slot it into the full volume.
    inside_grid = inside.reshape(ii.shape).astype(np.uint8)  # shape: (nx, ny, nz)
    # SITK array indexing is (z, y, x); transpose accordingly when slotting.
    mask = np.zeros((size[2], size[1], size[0]), dtype=np.uint8)
    mask[v0[2]:v1[2]+1, v0[1]:v1[1]+1, v0[0]:v1[0]+1] = inside_grid.transpose(2, 1, 0)
    return mask


def medis_lumen_volume(medis_path: Path) -> float:
    """Estimate lumen volume from MEDIS rings by trapezoidal area integration."""
    contours, _, _ = mtc.parse_medis_contours_with_slicedist(str(medis_path))
    rings = contours.get("Lumen", [])
    if len(rings) < 2:
        raise ValueError(f"{medis_path}: need at least two lumen rings")

    areas = []
    centroids = []
    for ring in rings:
        if len(ring) < 3:
            continue
        centroid = ring.mean(axis=0)
        X = ring - centroid
        _, _, vh = np.linalg.svd(X, full_matrices=False)
        u, v = vh[0], vh[1]
        xy = np.column_stack([X @ u, X @ v])
        x, y = xy[:, 0], xy[:, 1]
        area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
        areas.append(area)
        centroids.append(centroid)

    areas = np.asarray(areas)
    centroids = np.asarray(centroids)
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(centroids, axis=0), axis=1))])
    return float(np.trapz(areas, arc))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mesh", required=True, help="lumen GIfTI mesh, world coords")
    ap.add_argument("--cta",  required=True, help="source CTA NIfTI for grid alignment")
    ap.add_argument("--out",  required=True, help="output NIfTI mask path")
    ap.add_argument("--medis", default=None,
                    help="optional MEDIS txt for contour-volume sanity check")
    ap.add_argument("--method", choices=["vtk", "trimesh"], default="vtk",
                    help="voxelization backend (default: vtk; trimesh is slower ray-cast fallback)")
    ap.add_argument("--margin", type=int, default=2,
                    help="voxel margin around mesh bbox (default: 2)")
    args = ap.parse_args()

    print("Loading mesh + CTA grid...")
    mesh = load_gii_mesh(Path(args.mesh))
    cta_img = sitk.ReadImage(args.cta)
    print(f"  mesh: {len(mesh.vertices):,} verts  {len(mesh.faces):,} faces  "
          f"watertight={mesh.is_watertight}")
    print(f"  CTA:  size {list(cta_img.GetSize())}  spacing {[round(x,4) for x in cta_img.GetSpacing()]}")

    print("Rasterizing...")
    if args.method == "vtk":
        mask = rasterize_mesh_vtk(mesh, cta_img, margin_voxels=args.margin)
    else:
        mask = rasterize_mesh_trimesh(mesh, cta_img, margin_voxels=args.margin)

    # Save as NIfTI with the CTA affine
    mask_img = sitk.GetImageFromArray(mask)
    mask_img.CopyInformation(cta_img)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(mask_img, args.out, useCompression=True)
    out_mb = Path(args.out).stat().st_size / 1024 / 1024
    print(f"\nwrote {args.out}  ({out_mb:.2f} MB)")
    print(f"  voxels: {int(mask.sum()):,} positive of {mask.size:,} total")
    # Quick sanity checks.
    sp = cta_img.GetSpacing()
    vol_mm3 = float(mask.sum()) * sp[0] * sp[1] * sp[2]
    print(f"  lumen volume (mask):  {vol_mm3:.1f} mm³")
    print(f"  lumen volume (mesh):  {mesh.volume:.1f} mm³  (diagnostic only; lofted meshes can bias volume)")
    if args.medis:
        contour_vol = medis_lumen_volume(Path(args.medis))
        rel = abs(vol_mm3 - contour_vol) / contour_vol * 100
        print(f"  lumen volume (MEDIS contour integration): {contour_vol:.1f} mm³")
        print(f"  mask vs MEDIS contour volume difference: {rel:.2f}%")


if __name__ == "__main__":
    main()
