#!/usr/bin/env python3
"""Generate PNG previews of the LAD POC visualisations."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pyvista as pv
import SimpleITK as sitk
from matplotlib.gridspec import GridSpec
from scipy.ndimage import map_coordinates

sys.path.insert(0, str(Path(__file__).parent))
import medis_to_cpr as mtc  # noqa: E402

pv.set_plot_theme("document")

DATA = Path("/home/lukass/workspace/segment/data")
OUT = DATA / "previews"
OUT.mkdir(exist_ok=True)

PATIENT = "01-BER-0088"
VESSEL = "LAD"
MEDIS_TXT = DATA / f"{PATIENT}_20181010_Session_Session 16_04_2021 14_46 _ecrf_lad.txt"

# Cardiac CTA window: window 800, level 300 → vmin -100, vmax 700
WL = dict(cmap="gray", vmin=-100, vmax=700, interpolation="nearest")

# Reformatting CT intensities is a continuous-data operation. Use linear
# interpolation for oblique MPR sampling; keep imshow nearest to avoid display blur.
IMAGE_REFORMAT_ORDER = 1
IMAGE_REFORMAT_LABEL = "linear"

# Field-of-view in mm for zoomed cross-section panels (was implicitly 30 mm)
XS_FOV_MM = 14.0

LUMEN_COLOR = "#e63946"
WALL_COLOR = "#3da5d9"


def load_sitk_array(p: Path):
    img = sitk.ReadImage(str(p))
    arr = sitk.GetArrayFromImage(img)
    return img, arr


def load_gii_vertices_faces(p: Path):
    gii = nib.load(str(p))
    verts, faces = None, None
    for d in gii.darrays:
        if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_POINTSET"]:
            verts = np.asarray(d.data)
        elif d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_TRIANGLE"]:
            faces = np.asarray(d.data)
    return verts, faces


def world_to_vox(points, cta_img):
    sp = np.array(cta_img.GetSpacing())
    o = np.array(cta_img.GetOrigin())
    D_inv = np.array(cta_img.GetDirection()).reshape(3, 3).T
    return (D_inv @ (points - o).T).T / sp


def pv_mesh(verts, faces, color, opacity=1.0):
    f = np.hstack([np.full((len(faces), 1), 3, dtype=np.int64), faces]).astype(np.int64).ravel()
    mesh = pv.PolyData(verts.astype(np.float32), f)
    return mesh, dict(color=color, opacity=opacity, smooth_shading=True, specular=0.3)


def crop_white(img, pad=10):
    """Trim white border around a screenshot. img is HxWx3 uint8."""
    if img.shape[2] == 4:
        mask = img[:, :, 3] > 0
    else:
        mask = (img < 250).any(axis=2)
    if not mask.any():
        return img
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    r0, r1 = max(0, rows[0] - pad), min(img.shape[0], rows[-1] + pad)
    c0, c1 = max(0, cols[0] - pad), min(img.shape[1], cols[-1] + pad)
    return img[r0:r1, c0:c1]


def render_3d_mesh(inner, outer, centerline, view, size=(1200, 1200), zoom=1.0,
                   transparent_background=False, background="white"):
    """Render a 3D screenshot using pyvista. view is (elev, azim) in degrees."""
    p = pv.Plotter(off_screen=True, window_size=size)
    p.set_background(background)
    v_i, f_i = inner
    v_o, f_o = outer
    m_o, kw_o = pv_mesh(v_o, f_o, color="steelblue", opacity=0.20)
    m_i, kw_i = pv_mesh(v_i, f_i, color="firebrick", opacity=0.95)
    p.add_mesh(m_o, **kw_o)
    p.add_mesh(m_i, **kw_i)
    line = pv.lines_from_points(centerline.astype(np.float32))
    p.add_mesh(line, color="black", line_width=2)
    p.camera_position = "iso"
    elev, azim = view
    p.camera.elevation = elev
    p.camera.azimuth = azim
    p.reset_camera()
    if zoom != 1.0:
        p.camera.zoom(zoom)
    img = p.screenshot(return_img=True, transparent_background=transparent_background)
    p.close()
    return crop_white(img, pad=15)


def render_points_3d(points, color, centerline, view, size=(1200, 1200),
                     point_size=4, zoom=1.0, transparent_background=True,
                     background="white"):
    """Render a 3D point cloud + centerline. `points` is (N, 3) world coords."""
    p = pv.Plotter(off_screen=True, window_size=size)
    p.set_background(background)
    cloud = pv.PolyData(points.astype(np.float32))
    p.add_mesh(cloud, color=color, point_size=point_size, render_points_as_spheres=True)
    line = pv.lines_from_points(centerline.astype(np.float32))
    p.add_mesh(line, color="black", line_width=2)
    p.camera_position = "iso"
    elev, azim = view
    p.camera.elevation = elev
    p.camera.azimuth = azim
    p.reset_camera()
    if zoom != 1.0:
        p.camera.zoom(zoom)
    img = p.screenshot(return_img=True, transparent_background=transparent_background)
    p.close()
    return crop_white(img, pad=15)


def render_dual_points_3d(lumen_points, wall_points, centerline, view,
                          size=(1200, 1200), point_size=4, zoom=1.0,
                          transparent_background=True, background="white"):
    """Render lumen and wall point clouds together with a shared camera."""
    p = pv.Plotter(off_screen=True, window_size=size)
    p.set_background(background)
    lumen = pv.PolyData(lumen_points.astype(np.float32))
    wall = pv.PolyData(wall_points.astype(np.float32))
    p.add_mesh(wall, color=WALL_COLOR, point_size=point_size,
               render_points_as_spheres=True, opacity=0.86)
    p.add_mesh(lumen, color=LUMEN_COLOR, point_size=point_size,
               render_points_as_spheres=True, opacity=0.92)
    line = pv.lines_from_points(centerline.astype(np.float32))
    p.add_mesh(line, color="black", line_width=2)
    p.camera_position = "iso"
    elev, azim = view
    p.camera.elevation = elev
    p.camera.azimuth = azim
    p.reset_camera()
    if zoom != 1.0:
        p.camera.zoom(zoom)
    img = p.screenshot(return_img=True, transparent_background=transparent_background)
    p.close()
    return crop_white(img, pad=15)


def load_medis_rings(medis_path):
    """Parse MEDIS .txt and return (lumen_rings, wall_rings).

    Each is a list of (N_i, 3) world-coord arrays — one per traced slice.
    """
    contours, _, _ = mtc.parse_medis_contours_with_slicedist(str(medis_path))
    return contours["Lumen"], contours["VesselWall"]


def compute_frame_for_cpr(medis_path, cta_path):
    """Re-derive the resampled centerline + RMF that matches the given CTA's CPR.

    Mirrors the resampling logic in medis_to_cpr.py so projection coords align.
    Returns (centerline, normals, binormals, pixel_spacing_mm).
    """
    contours, _, _ = mtc.parse_medis_contours_with_slicedist(str(medis_path))
    centerline_raw = mtc.extract_centerline(contours["Lumen"])
    img = sitk.ReadImage(str(cta_path))
    target_sp = min(img.GetSpacing())
    cl = mtc.resample_centerline(centerline_raw, target_sp)
    tan = mtc.compute_tangent_vectors(cl)
    n, b = mtc.compute_rotation_minimizing_frame(tan)
    return cl, n, b, target_sp


def project_ring_to_uv(ring, centerline, normals, binormals, s_idx):
    """Project ring world-coord points onto local (U, V) frame at centerline[s_idx]."""
    P = centerline[s_idx]
    N = normals[s_idx]
    B = binormals[s_idx]
    D = ring - P
    u = D @ N
    v = D @ B
    return np.column_stack([u, v])  # mm


def best_ring_for_slice(s_idx, centerline_resampled, rings):
    """Return index of the MEDIS ring whose centroid is closest to centerline_resampled[s_idx]."""
    P = centerline_resampled[s_idx]
    centroids = np.array([r.mean(axis=0) for r in rings])
    return int(np.argmin(np.linalg.norm(centroids - P, axis=1)))


def crop_to_fov(xs_slice, pixel_spacing, fov_mm):
    """Centre-crop a (V, U) cross-section to roughly fov_mm × fov_mm."""
    Vn, Un = xs_slice.shape
    half_px = int(round(fov_mm / 2.0 / pixel_spacing))
    cv, cu = Vn // 2, Un // 2
    v0, v1 = max(0, cv - half_px), min(Vn, cv + half_px)
    u0, u1 = max(0, cu - half_px), min(Un, cu + half_px)
    return xs_slice[v0:v1, u0:u1]


def draw_medis_overlay(ax, lumen_ring, wall_ring,
                       centerline, normals, binormals, s_idx,
                       fov_mm):
    """Overlay closed MEDIS lumen + wall outlines on a zoomed cross-section axes.

    Assumes the imshow uses extent=[-fov/2, fov/2, fov/2, -fov/2] in mm.
    """
    lumen_uv = project_ring_to_uv(lumen_ring, centerline, normals, binormals, s_idx)
    wall_uv  = project_ring_to_uv(wall_ring,  centerline, normals, binormals, s_idx)
    lumen_uv = np.vstack([lumen_uv, lumen_uv[:1]])
    wall_uv  = np.vstack([wall_uv,  wall_uv[:1]])
    ax.plot(wall_uv[:, 0],  wall_uv[:, 1],  color=WALL_COLOR,  lw=2.2, alpha=0.98, label="wall (MEDIS)")
    ax.plot(lumen_uv[:, 0], lumen_uv[:, 1], color=LUMEN_COLOR, lw=2.2, alpha=0.98, label="lumen (MEDIS)")
    ax.plot(0, 0, "+", color="#00d4ff", ms=9, mew=1.6)
    half = fov_mm / 2.0
    ax.set_xlim(-half, half)
    ax.set_ylim(half, -half)  # image-y down convention


def fig_overview(cta, cta_img, long_arr, cross_arr, centerline, inner_verts, outer_verts,
                 lumen_rings, wall_rings, cl_frame, n_frame, b_frame, xs_pixel_spacing):
    fig = plt.figure(figsize=(20, 11))
    fig.suptitle(f"{PATIENT}  —  LAD  —  POC overview", fontsize=15, y=0.99)
    gs = GridSpec(2, 4, figure=fig, hspace=0.22, wspace=0.08)

    cl_vox = world_to_vox(centerline, cta_img)
    z_idx = int(np.round(cl_vox[:, 2].mean()))
    z_idx = np.clip(z_idx, 0, cta.shape[0] - 1)

    # Row 1: 3D mesh, lumen pts, wall pts, axial
    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(render_3d_mesh(inner_verts, outer_verts, centerline, view=(15, -65)))
    ax.set_title("(a) Lumen + vessel-wall mesh", fontsize=11); ax.axis("off")

    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(render_points_3d(np.vstack(lumen_rings), LUMEN_COLOR, centerline, view=(15, -65)))
    ax.set_title("(b) MEDIS lumen point cloud", fontsize=11); ax.axis("off")

    ax = fig.add_subplot(gs[0, 2])
    ax.imshow(render_points_3d(np.vstack(wall_rings), WALL_COLOR, centerline, view=(15, -65)))
    ax.set_title("(c) MEDIS vessel-wall point cloud", fontsize=11); ax.axis("off")

    ax = fig.add_subplot(gs[0, 3])
    ax.imshow(cta[z_idx], **WL)
    dist = np.abs(cl_vox[:, 2] - z_idx)
    keep = dist < 60
    ax.scatter(cl_vox[keep, 0], cl_vox[keep, 1],
               c=dist[keep], cmap="autumn_r", s=14, alpha=0.95,
               edgecolor="black", linewidth=0.3)
    ax.set_title(f"(d) Axial CTA  z={z_idx}  +  LAD centerline", fontsize=11); ax.axis("off")

    # Row 2: 4 zoomed cross-sections with MEDIS overlay
    n_s = cross_arr.shape[0]
    positions = [int(n_s * f) for f in (0.18, 0.40, 0.62, 0.85)]
    labels = ["proximal", "mid-prox", "mid-dist", "distal"]
    for k, (idx, lab) in enumerate(zip(positions, labels)):
        ax = fig.add_subplot(gs[1, k])
        cropped = crop_to_fov(cross_arr[idx], xs_pixel_spacing, XS_FOV_MM)
        half = XS_FOV_MM / 2.0
        ax.imshow(cropped, **WL, extent=[-half, half, half, -half])
        r_i = best_ring_for_slice(idx, cl_frame, lumen_rings)
        r_w = best_ring_for_slice(idx, cl_frame, wall_rings)
        draw_medis_overlay(ax, lumen_rings[r_i], wall_rings[r_w],
                           cl_frame, n_frame, b_frame, idx, XS_FOV_MM)
        ax.set_title(f"(e{k+1})  {lab}  ·  s={idx}  ·  {XS_FOV_MM:.0f} mm FOV", fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
        if k == 0:
            ax.legend(loc="upper right", fontsize=8, framealpha=0.85)

    out = OUT / "01_overview.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)


def sample_oblique_mpr(cross_arr, theta_deg):
    """Build a longitudinal MPR by sampling each perpendicular cross-section
    along a line through its centre at angle theta from the V axis.

    cross_arr shape: (S, V, U). Returns (line_len, S) image suitable for imshow.
    """
    S, Vn, Un = cross_arr.shape
    cv, cu = Vn / 2.0, Un / 2.0
    half = min(Vn, Un) // 2
    t = np.arange(-half, half)
    th = np.deg2rad(theta_deg)
    # direction in (v, u)
    dv, du = np.sin(th), np.cos(th)
    line_v = cv + t * dv
    line_u = cu + t * du
    out = np.zeros((len(t), S), dtype=np.float32)
    for s in range(S):
        out[:, s] = map_coordinates(
            cross_arr[s],
            [line_v, line_u],
            order=IMAGE_REFORMAT_ORDER,
            mode="constant",
            cval=-1024,
        )
    return out


def fig_mpr_rotation(cross_arr):
    angles = [0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5]
    fig, axes = plt.subplots(len(angles), 1, figsize=(14, 12))
    fig.suptitle(
        f"{PATIENT}  LAD  —  Straightened MPR rotation series  "
        f"({IMAGE_REFORMAT_LABEL} CT reformat, nearest display)",
        fontsize=15,
        y=0.995,
    )
    for ax, a in zip(axes, angles):
        m = sample_oblique_mpr(cross_arr, a)
        ax.imshow(m, **WL, aspect="auto")
        ax.set_ylabel(f"{a:5.1f}°", rotation=0, ha="right", va="center", fontsize=11)
        ax.set_xticks([]), ax.set_yticks([])
    axes[-1].set_xlabel("along vessel  (proximal → distal)")
    out = OUT / "02_mpr_rotation.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)


def fig_cross_walkthrough(cross_arr, lumen_rings, wall_rings,
                          cl_frame, n_frame, b_frame, xs_pixel_spacing):
    """Grid of 16 perpendicular cross-sections evenly spaced along the vessel,
    zoomed to XS_FOV_MM with MEDIS lumen + wall contour overlay."""
    n = 16
    S = cross_arr.shape[0]
    idx = np.linspace(20, S - 20, n).astype(int)
    fig, axes = plt.subplots(4, 4, figsize=(13, 13))
    fig.suptitle(
        f"{PATIENT}  LAD  —  Cross-section walkthrough  "
        f"({XS_FOV_MM:.0f} mm FOV  ·  red=lumen  ·  cyan=wall  ·  MEDIS overlay)",
        fontsize=13, y=0.995,
    )
    half = XS_FOV_MM / 2.0
    for ax, i in zip(axes.flat, idx):
        cropped = crop_to_fov(cross_arr[i], xs_pixel_spacing, XS_FOV_MM)
        ax.imshow(cropped, **WL, extent=[-half, half, half, -half])
        r_i = best_ring_for_slice(i, cl_frame, lumen_rings)
        r_w = best_ring_for_slice(i, cl_frame, wall_rings)
        draw_medis_overlay(ax, lumen_rings[r_i], wall_rings[r_w],
                           cl_frame, n_frame, b_frame, i, XS_FOV_MM)
        ax.set_title(f"s = {i}/{S}", fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = OUT / "03_cross_walkthrough.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)


def fig_axial_grid(cta, cta_img, centerline):
    """3×3 axial CTA grid with LAD centerline points overlaid where visible."""
    sp = cta_img.GetSpacing()
    o = cta_img.GetOrigin()
    D_inv = np.array(cta_img.GetDirection()).reshape(3, 3).T
    cl_local = centerline - np.array(o)
    cl_vox = (D_inv @ cl_local.T).T / np.array(sp)
    z_min, z_max = int(cl_vox[:, 2].min()), int(cl_vox[:, 2].max())
    # Extend a bit beyond vessel for context
    margin = (z_max - z_min) // 4
    z_lo = max(0, z_min - margin)
    z_hi = min(cta.shape[0] - 1, z_max + margin)
    slices = np.linspace(z_lo, z_hi, 9).astype(int)

    fig, axes = plt.subplots(3, 3, figsize=(13, 13))
    fig.suptitle(f"{PATIENT}  —  Axial CTA grid  (LAD centerline overlay)", fontsize=15, y=0.995)
    for ax, zi in zip(axes.flat, slices):
        ax.imshow(cta[zi], **WL)
        dist = np.abs(cl_vox[:, 2] - zi)
        keep = dist < 30
        if keep.any():
            ax.scatter(
                cl_vox[keep, 0], cl_vox[keep, 1],
                c=dist[keep], cmap="autumn_r", s=20, alpha=0.9,
                edgecolor="black", linewidth=0.3,
            )
        ax.set_title(f"z = {zi}", fontsize=10)
        ax.axis("off")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = OUT / "04_axial_grid.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)


def fig_mesh_3d(inner_verts, outer_verts, centerline):
    views = [("front",  0,   0),
             ("right", 0,  90),
             ("top",   90,  0),
             ("oblique", 25, 45)]
    fig, axes = plt.subplots(2, 2, figsize=(13, 13))
    fig.suptitle(f"{PATIENT}  LAD  —  3D vessel mesh  (red = lumen, translucent blue = vessel wall, black = centerline)",
                 fontsize=13, y=0.99)
    for ax, (title, elev, azim) in zip(axes.flat, views):
        img = render_3d_mesh(inner_verts, outer_verts, centerline,
                             view=(elev, azim), size=(1200, 1200), zoom=1.0)
        ax.imshow(img)
        ax.set_title(title)
        ax.axis("off")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = OUT / "05_mesh_3d.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)


def fig_pointclouds(lumen_rings, wall_rings, centerline):
    """Side-by-side 3D point clouds: lumen and vessel wall (separate panels)."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 9))
    fig.suptitle(
        f"{PATIENT}  LAD  —  MEDIS expert point clouds   "
        f"(left: lumen,  right: vessel wall)",
        fontsize=13, y=0.97,
    )
    lumen_pts = np.vstack(lumen_rings)
    wall_pts  = np.vstack(wall_rings)
    axes[0].imshow(render_points_3d(lumen_pts, LUMEN_COLOR, centerline,
                                     view=(15, -65), size=(1400, 1600), zoom=1.0))
    axes[0].set_title(f"Lumen  ·  {len(lumen_rings)} rings  ·  {len(lumen_pts)} points", fontsize=11)
    axes[0].axis("off")
    axes[1].imshow(render_points_3d(wall_pts, WALL_COLOR, centerline,
                                     view=(15, -65), size=(1400, 1600), zoom=1.0))
    axes[1].set_title(f"Vessel wall  ·  {len(wall_rings)} rings  ·  {len(wall_pts)} points", fontsize=11)
    axes[1].axis("off")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = OUT / "08_pointclouds.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    transparent_out = OUT / "08_pointclouds_transparent.png"
    fig.savefig(transparent_out, dpi=140, bbox_inches="tight", transparent=True)
    plt.close(fig)
    print("saved", out)
    print("saved", transparent_out)


def fig_hero(cta, cta_img, cross_arr, centerline, inner_verts, outer_verts,
             lumen_rings, wall_rings, cl_frame, n_frame, b_frame, xs_pixel_spacing):
    """Hero figure: 4-panel row (3D mesh + lumen pts + wall pts + axial),
    full-width straightened MPR, and 4 zoomed cross-sections with MEDIS overlay."""
    fig = plt.figure(figsize=(22, 12))
    fig.suptitle("01-BER-0088  —  LAD  —  Coronary vessel visualisation POC", fontsize=16, y=0.99)
    gs = GridSpec(3, 4, figure=fig, hspace=0.25, wspace=0.10,
                  height_ratios=[1.4, 0.6, 1.0])

    cl_vox = world_to_vox(centerline, cta_img)
    z_idx = int(np.round(cl_vox[:, 2].mean()))
    z_idx = np.clip(z_idx, 0, cta.shape[0] - 1)

    # Row 1: mesh, lumen pts, wall pts, axial
    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(render_3d_mesh(inner_verts, outer_verts, centerline, view=(15, -65)))
    ax.set_title("3D vessel mesh", fontsize=11); ax.axis("off")

    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(render_points_3d(np.vstack(lumen_rings), LUMEN_COLOR, centerline, view=(15, -65)))
    ax.set_title("MEDIS lumen point cloud", fontsize=11); ax.axis("off")

    ax = fig.add_subplot(gs[0, 2])
    ax.imshow(render_points_3d(np.vstack(wall_rings), WALL_COLOR, centerline, view=(15, -65)))
    ax.set_title("MEDIS vessel-wall point cloud", fontsize=11); ax.axis("off")

    ax = fig.add_subplot(gs[0, 3])
    ax.imshow(cta[z_idx], **WL)
    dist = np.abs(cl_vox[:, 2] - z_idx)
    keep = dist < 60
    ax.scatter(cl_vox[keep, 0], cl_vox[keep, 1],
               c=dist[keep], cmap="autumn_r", s=14, alpha=0.95,
               edgecolor="black", linewidth=0.3)
    ax.set_title(f"Axial CTA  z={z_idx}  +  centerline", fontsize=11); ax.axis("off")

    # Row 2: full-width straightened MPR
    ax = fig.add_subplot(gs[1, :])
    mpr = sample_oblique_mpr(cross_arr, 0)
    ax.imshow(mpr, **WL, aspect="auto")
    ax.set_title("Straightened MPR  (angle 0°,  full vessel length, proximal → distal)", fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])

    # Row 3: 4 zoomed cross-sections with MEDIS overlay
    S = cross_arr.shape[0]
    positions = [int(S * f) for f in (0.15, 0.40, 0.65, 0.90)]
    labels = ["proximal", "mid-prox", "mid-dist", "distal"]
    half = XS_FOV_MM / 2.0
    for k, (idx, lab) in enumerate(zip(positions, labels)):
        ax = fig.add_subplot(gs[2, k])
        cropped = crop_to_fov(cross_arr[idx], xs_pixel_spacing, XS_FOV_MM)
        ax.imshow(cropped, **WL, extent=[-half, half, half, -half])
        r_i = best_ring_for_slice(idx, cl_frame, lumen_rings)
        r_w = best_ring_for_slice(idx, cl_frame, wall_rings)
        draw_medis_overlay(ax, lumen_rings[r_i], wall_rings[r_w],
                           cl_frame, n_frame, b_frame, idx, XS_FOV_MM)
        ax.set_title(f"{lab}  ·  s={idx}  ·  {XS_FOV_MM:.0f} mm FOV", fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
        if k == 0:
            ax.legend(loc="upper right", fontsize=8, framealpha=0.85)

    out = OUT / "00_hero.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)


def main():
    print("Loading data...")
    cta_img, cta = load_sitk_array(DATA / f"{PATIENT}.nii.gz")
    long_img, long_arr = load_sitk_array(DATA / f"{PATIENT}_{VESSEL}_cpr_long.nii.gz")
    cross_img, cross_arr = load_sitk_array(DATA / f"{PATIENT}_{VESSEL}_cpr_cross.nii.gz")
    inner = load_gii_vertices_faces(DATA / f"{PATIENT}_{VESSEL}_inner.gii")
    outer = load_gii_vertices_faces(DATA / f"{PATIENT}_{VESSEL}_outer.gii")

    print("Parsing MEDIS rings...")
    lumen_rings, wall_rings = load_medis_rings(MEDIS_TXT)

    print("Recomputing centerline / RMF that matches the current CPR file...")
    cpr_cta_path = DATA / f"{PATIENT}.nii.gz"  # CPR was generated against this CTA
    cl_frame, n_frame, b_frame, target_sp = compute_frame_for_cpr(MEDIS_TXT, cpr_cta_path)
    print(f"  resampled centerline: {len(cl_frame)} points,  pixel spacing: {target_sp:.4f} mm")
    print(f"  MEDIS lumen rings: {len(lumen_rings)}  wall rings: {len(wall_rings)}")
    print(f"  CTA: {cta.shape}  cross: {cross_arr.shape}  long: {long_arr.shape}")
    centerline = cl_frame

    fig_hero(cta, cta_img, cross_arr, centerline, inner, outer,
             lumen_rings, wall_rings, cl_frame, n_frame, b_frame, target_sp)
    fig_overview(cta, cta_img, long_arr, cross_arr, centerline, inner, outer,
                 lumen_rings, wall_rings, cl_frame, n_frame, b_frame, target_sp)
    fig_mpr_rotation(cross_arr)
    fig_cross_walkthrough(cross_arr, lumen_rings, wall_rings,
                          cl_frame, n_frame, b_frame, target_sp)
    fig_axial_grid(cta, cta_img, centerline)
    fig_mesh_3d(inner, outer, centerline)
    fig_pointclouds(lumen_rings, wall_rings, centerline)
    print(f"\nAll previews saved under {OUT}/")


if __name__ == "__main__":
    main()
