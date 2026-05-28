#!/usr/bin/env python3
"""Polished 16:9 slide showcasing the coronary vessel visualisation POC.

Layout (mimics the Charité / European Radiology reference slide):
  - Title bar (dark blue) at top
  - Light-blue rounded box containing:
      * subtitle (bold)
      * bullet list on the left half
      * figure mosaic on the right half (3D mesh, axial CTA,
        full-width straightened MPR, four cross-sections)
  - One-paragraph caption below the box
  - Footer with citation / institute on the very bottom
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pyvista as pv
import SimpleITK as sitk
from matplotlib.patches import FancyBboxPatch
from scipy.ndimage import map_coordinates

sys.path.insert(0, str(Path(__file__).parent))
import make_previews as mp  # noqa: E402 — reuse render + projection helpers

pv.set_plot_theme("document")

DATA = Path("/home/lukass/workspace/segment/data")
OUT = DATA / "previews" / "slide.png"

# Cardiac CTA display window for this presentation slide:
# W1000 / L350 preserves the bright calcified-plaque tail in the FC51 CPR
# while keeping enough lumen/soft-tissue contrast for a projector.
WL = dict(cmap="gray", vmin=-150, vmax=850, interpolation="nearest")
XS_FOV_MM = mp.XS_FOV_MM
MPR_FOV_MM = 10.0

NAVY = "#1f3a68"
LIGHT_BLUE = "#dde8f5"
BORDER_BLUE = "#7ba0d3"
SOFT_GRAY = "#5b6470"
LUMEN_COLOR = mp.LUMEN_COLOR
WALL_COLOR  = mp.WALL_COLOR
TITLE_FS = 34
SUBTITLE_FS = 16
PIPELINE_FS = 16.5
SECTION_FS = 14.5
BULLET_FS = 12.8
CAPTION_FS = 11.6
PANEL_TITLE_FS = 11.8
ROW_TITLE_FS = 12.2
FOOTER_FS = 11.2


def load_arr(p):
    img = sitk.ReadImage(str(p))
    arr = sitk.GetArrayFromImage(img)
    return img, arr


def load_gii(p):
    g = nib.load(str(p))
    v, f = None, None
    for d in g.darrays:
        if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_POINTSET"]:
            v = np.asarray(d.data)
        elif d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_TRIANGLE"]:
            f = np.asarray(d.data)
    return v, f


def crop_white(img, pad=10):
    mask = (img < 250).any(axis=2)
    if not mask.any():
        return img
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    r0, r1 = max(0, rows[0] - pad), min(img.shape[0], rows[-1] + pad)
    c0, c1 = max(0, cols[0] - pad), min(img.shape[1], cols[-1] + pad)
    return img[r0:r1, c0:c1]


def render_mesh(inner, outer, centerline, view=(15, -65), size=(1500, 1500)):
    return mp.render_3d_mesh(
        inner,
        outer,
        centerline,
        view=view,
        size=size,
        zoom=1.0,
        transparent_background=True,
        background=LIGHT_BLUE,
    )


def render_points(points, color, centerline, view=(15, -65), size=(1500, 1500)):
    return mp.render_points_3d(
        points,
        color,
        centerline,
        view=view,
        size=size,
        point_size=5,
        zoom=1.0,
        transparent_background=True,
        background=LIGHT_BLUE,
    )


def sample_mpr(cross, theta_deg):
    S, Vn, Un = cross.shape
    cv, cu = Vn / 2.0, Un / 2.0
    half = min(Vn, Un) // 2
    t = np.arange(-half, half)
    th = np.deg2rad(theta_deg)
    dv, du = np.sin(th), np.cos(th)
    line_v = cv + t * dv
    line_u = cu + t * du
    out = np.zeros((len(t), S), dtype=np.float32)
    for s in range(S):
        out[:, s] = map_coordinates(
            cross[s],
            [line_v, line_u],
            order=mp.IMAGE_REFORMAT_ORDER,
            mode="constant",
            cval=-1024,
        )
    return out


def ring_envelope_for_mpr(rings, centerline, normals, binormals, theta_deg=0.0):
    """Return upper/lower contour envelopes for a straightened MPR angle.

    The MPR strip samples a line through each perpendicular CPR plane. For each
    MEDIS ring we project ring points onto the same line direction and plot the
    min/max extent as the visible longitudinal boundary envelope.
    """
    th = np.deg2rad(theta_deg)
    direction = np.array([np.cos(th), np.sin(th)])
    s_vals, low_vals, high_vals = [], [], []
    for ring in rings:
        centroid = ring.mean(axis=0)
        s_idx = int(np.argmin(np.linalg.norm(centerline - centroid, axis=1)))
        uv = mp.project_ring_to_uv(ring, centerline, normals, binormals, s_idx)
        q = uv @ direction
        s_vals.append(s_idx)
        low_vals.append(float(q.min()))
        high_vals.append(float(q.max()))
    order = np.argsort(s_vals)
    return np.asarray(s_vals)[order], np.asarray(low_vals)[order], np.asarray(high_vals)[order]


def world_to_vox(points, img):
    sp = np.array(img.GetSpacing())
    o = np.array(img.GetOrigin())
    D_inv = np.array(img.GetDirection()).reshape(3, 3).T
    return (D_inv @ (points - o).T).T / sp


# ---------- Load data ----------
print("Loading...")
MEDIS_TXT = DATA / "01-BER-0088_20181010_Session_Session 16_04_2021 14_46 _ecrf_lad.txt"
cta_img, cta = load_arr(DATA / "01-BER-0088.nii.gz")
# FC51 for cross-sections + MPR (sharp kernel)
cta_sharp_path = DATA / "01-BER-0088_FC51.nii.gz"
cross_sharp_img, cross_sharp = load_arr(DATA / "01-BER-0088_LAD_cpr_cross_FC51.nii.gz")
inner = load_gii(DATA / "01-BER-0088_LAD_inner.gii")
outer = load_gii(DATA / "01-BER-0088_LAD_outer.gii")

print("Parsing MEDIS rings + recomputing FC51 frame...")
lumen_rings, wall_rings = mp.load_medis_rings(MEDIS_TXT)
cl_frame, n_frame, b_frame, xs_pixel_spacing = mp.compute_frame_for_cpr(MEDIS_TXT, cta_sharp_path)
centerline = cl_frame
print(f"  cta {cta.shape}  cross_sharp {cross_sharp.shape}  centerline {centerline.shape}")
print(f"  MEDIS rings: lumen {len(lumen_rings)}  wall {len(wall_rings)}  "
      f"xs pixel spacing {xs_pixel_spacing:.4f} mm")

# ---------- Pre-render heavy panels ----------
print("Rendering 3D mesh + point clouds...")
mesh_img = render_mesh(inner, outer, centerline, view=(15, -65), size=(1500, 1500))
lumen_pts = np.vstack(lumen_rings)
wall_pts  = np.vstack(wall_rings)
pc_lumen_img = render_points(lumen_pts, LUMEN_COLOR, centerline, view=(15, -65))
pc_wall_img = render_points(wall_pts, WALL_COLOR, centerline, view=(15, -65))

print("Sampling straightened MPR (FC51 sharp)...")
mpr0 = sample_mpr(cross_sharp, 0)
mpr_rows = max(4, int(round(MPR_FOV_MM / xs_pixel_spacing)))
mpr_rows = min(mpr_rows, mpr0.shape[0])
mpr_row0 = (mpr0.shape[0] - mpr_rows) // 2
mpr0_display = mpr0[mpr_row0:mpr_row0 + mpr_rows]
lumen_env = ring_envelope_for_mpr(lumen_rings, cl_frame, n_frame, b_frame, theta_deg=0)
wall_env = ring_envelope_for_mpr(wall_rings, cl_frame, n_frame, b_frame, theta_deg=0)

# Axial slice + centerline overlay (use FC03 = better in-plane resolution)
cl_vox = world_to_vox(centerline, cta_img)
z_idx = int(np.round(cl_vox[:, 2].mean()))
z_idx = np.clip(z_idx, 0, cta.shape[0] - 1)
axial_slc = cta[z_idx]
axial_slc_display = np.flipud(axial_slc)
cl_vox_display = cl_vox.copy()
cl_vox_display[:, 1] = cta.shape[1] - 1 - cl_vox_display[:, 1]

# Pick four cross-sections at vessel fractions
S = cross_sharp.shape[0]
xs_idx = [int(S * f) for f in (0.18, 0.40, 0.62, 0.85)]
xs_labels = ["proximal", "mid-prox", "mid-dist", "distal"]

# ---------- Build slide ----------
print("Composing slide...")
plt.rcParams.update({"font.family": "DejaVu Sans"})
FIG_W, FIG_H = 20, 11.25  # 16:9 inches
fig = plt.figure(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor("white")

# --- Header band (above box) ---
HEADER_TOP = 0.965
HEADER_BOT = 0.875

# Title
fig.text(0.045, 0.935, "Coronary Vessel Visualisation",
         fontsize=TITLE_FS, color=NAVY, fontweight="bold", va="center")
fig.text(0.045, 0.895, "From MEDIS expert contours to multi-view 3D + CPR",
         fontsize=SUBTITLE_FS, color=SOFT_GRAY, va="center")

# Subject icon top-right
ax_icon = fig.add_axes([0.918, 0.885, 0.038, 0.07])
ax_icon.set_xlim(0, 1); ax_icon.set_ylim(0, 1); ax_icon.axis("off")
ax_icon.add_patch(mpatches.Circle((0.5, 0.78), 0.18, color=NAVY))
ax_icon.add_patch(mpatches.FancyBboxPatch((0.18, 0.05), 0.64, 0.55,
                                          boxstyle="round,pad=0.02,rounding_size=0.18",
                                          color=NAVY, lw=0))

# Header divider
ax_div = fig.add_axes([0.045, HEADER_BOT, 0.91, 0.003])
ax_div.set_facecolor(BORDER_BLUE); ax_div.set_xticks([]); ax_div.set_yticks([])
for s in ax_div.spines.values():
    s.set_visible(False)

# --- Main box ---
BOX_X0, BOX_X1 = 0.030, 0.970
BOX_Y0, BOX_Y1 = 0.070, 0.865
BOX_W, BOX_H = BOX_X1 - BOX_X0, BOX_Y1 - BOX_Y0

ax_box = fig.add_axes([BOX_X0, BOX_Y0, BOX_W, BOX_H])
ax_box.set_xlim(0, 1); ax_box.set_ylim(0, 1); ax_box.axis("off")
box = FancyBboxPatch((0.0, 0.0), 1.0, 1.0,
                     boxstyle="round,pad=0.0,rounding_size=0.012",
                     facecolor=LIGHT_BLUE, edgecolor=BORDER_BLUE, linewidth=1.3,
                     transform=ax_box.transAxes, clip_on=False)
ax_box.add_patch(box)

# Sub-title (full width inside the box)
ax_box.text(0.022, 0.94,
            "Pipeline:   axial CT  →  expert lumen contours  →  centerline  →  CPR  +  straightened MPR  +  3D mesh",
            fontsize=PIPELINE_FS, color=NAVY, fontweight="bold")

# === LEFT half: bullets ===
LEFT_X = 0.022
LEFT_W = 0.36

ax_box.text(LEFT_X, 0.86, "Visualisations enabled by the pipeline:",
            fontsize=SECTION_FS, color=NAVY, fontweight="bold")
bullets = [
    "Patient 01-BER-0088  ·  vessel LAD",
    f"MEDIS expert tracing: {len(lumen_rings)} lumen + {len(wall_rings)} wall rings",
    "Centerline = lumen centroids; Rotation-Minimising Frame",
    "3D mesh + separate lumen / vessel-wall point clouds",
    "Sharp recon kernel (FC51) preserves plaque & wall edges",
    "Straightened MPR rotatable 360° around vessel axis",
    f"Cross-sections zoomed to {XS_FOV_MM:.0f} mm FOV with MEDIS overlay",
    "All views share one world-coordinate frame",
]
y = 0.80
for txt in bullets:
    ax_box.text(LEFT_X + 0.005, y, "•", fontsize=BULLET_FS + 1, color=NAVY, fontweight="bold")
    ax_box.text(LEFT_X + 0.022, y, txt, fontsize=BULLET_FS, color="#28323e", va="center")
    y -= 0.055

# Caption block bottom-left
cap_y = 0.20
ax_box.text(LEFT_X, cap_y,
            "Straightened MPR (centre) ‘unfolds’ the curved vessel into a single",
            fontsize=CAPTION_FS, color=SOFT_GRAY, style="italic")
ax_box.text(LEFT_X, cap_y - 0.038,
            "strip for full-length stenosis assessment. Cross-sections (bottom)",
            fontsize=CAPTION_FS, color=SOFT_GRAY, style="italic")
ax_box.text(LEFT_X, cap_y - 0.076,
            "show perpendicular slices through the contrast-filled lumen.",
            fontsize=CAPTION_FS, color=SOFT_GRAY, style="italic")

# === RIGHT half: figure panels ===
# Right half of the box in FIGURE coordinates:
RIGHT_X0 = BOX_X0 + BOX_W * 0.355          # left edge of right column
RIGHT_X1 = BOX_X0 + BOX_W * 0.992          # right edge
RIGHT_W = RIGHT_X1 - RIGHT_X0

# Vertical layout (figure coords):
# subtitle baseline ≈ BOX_Y0 + 0.94*BOX_H = 0.085 + 0.940*0.770 = 0.809
# leave room below subtitle starting at fig_y ≈ 0.785
# bottom edge of panels stops at fig_y ≈ 0.105 (above box bottom padding)
PANEL_TOP = BOX_Y0 + 0.895 * BOX_H
PANEL_BOT = BOX_Y0 + 0.025 * BOX_H
PANEL_SPAN = PANEL_TOP - PANEL_BOT   # ~0.655

# Heights and gaps (fractions of PANEL_SPAN)
ROW1_FRAC = 0.43
ROW2_FRAC = 0.18
ROW3_FRAC = 0.25
TITLE_GAP = 0.030
ROW_GAP   = (1.0 - ROW1_FRAC - ROW2_FRAC - ROW3_FRAC - 3 * TITLE_GAP) / 2  # >=0

def yh(frac_top, frac_h):
    """Return (bottom_y, height) in figure coords given fractions of PANEL_SPAN, top-down."""
    top = PANEL_TOP - frac_top * PANEL_SPAN
    h = frac_h * PANEL_SPAN
    return top - h, h


# Cumulative offsets (top → bottom)
cur = 0.0
# Row 1 panels
r1_b, r1_h = yh(cur + TITLE_GAP, ROW1_FRAC)
cur += TITLE_GAP + ROW1_FRAC + ROW_GAP
# Row 2 panel
r2_b, r2_h = yh(cur + TITLE_GAP, ROW2_FRAC)
cur += TITLE_GAP + ROW2_FRAC + ROW_GAP
# Row 3 panels
r3_b, r3_h = yh(cur + TITLE_GAP, ROW3_FRAC)


def title_above(ax, txt):
    """Place a panel title just above the axes inside the box."""
    ax.text(0.5, 1.012, txt, transform=ax.transAxes,
            ha="center", va="bottom", fontsize=PANEL_TITLE_FS, color=NAVY, fontweight="bold")


def styled_spines(ax):
    for s in ax.spines.values():
        s.set_edgecolor(BORDER_BLUE); s.set_linewidth(0.8)
    ax.set_xticks([]); ax.set_yticks([])


# Row 1: 4 panels — lumen points | wall points | mesh | axial CTA.
# The axial image is square, so give it a square physical axes box to make its
# displayed height match the tall 3D panels without distorting anatomy.
gap1 = 0.004
axial_w = r1_h * (FIG_H / FIG_W)
panel_w = (RIGHT_W - axial_w - 3 * gap1) / 3

ax_lumen = fig.add_axes([RIGHT_X0, r1_b, panel_w, r1_h])
ax_lumen.set_facecolor(LIGHT_BLUE)
ax_lumen.imshow(pc_lumen_img, interpolation="nearest")
styled_spines(ax_lumen)
title_above(ax_lumen, "MEDIS lumen points")

ax_wall_x = RIGHT_X0 + panel_w + gap1
ax_wall = fig.add_axes([ax_wall_x, r1_b, panel_w, r1_h])
ax_wall.set_facecolor(LIGHT_BLUE)
ax_wall.imshow(pc_wall_img, interpolation="nearest")
styled_spines(ax_wall)
title_above(ax_wall, "MEDIS wall points")

ax_mesh_x = ax_wall_x + panel_w + gap1
ax_mesh = fig.add_axes([ax_mesh_x, r1_b, panel_w, r1_h])
ax_mesh.set_facecolor(LIGHT_BLUE)
ax_mesh.imshow(mesh_img)
styled_spines(ax_mesh)
title_above(ax_mesh, "3D vessel mesh")

ax_axial_x = ax_mesh_x + panel_w + gap1
ax_axial = fig.add_axes([ax_axial_x, r1_b, axial_w, r1_h])
ax_axial.imshow(axial_slc_display, **WL)
near = np.abs(cl_vox_display[:, 2] - z_idx) < 30
ax_axial.scatter(cl_vox_display[near, 0], cl_vox_display[near, 1],
                 c="#ffb000", s=8, alpha=0.95, edgecolor="black", linewidth=0.25)
styled_spines(ax_axial)
title_above(ax_axial, f"Axial CTA  z = {z_idx}  (A up)")

# Row 2: Straightened MPR (full right-side width)
ax_mpr = fig.add_axes([RIGHT_X0, r2_b, RIGHT_W, r2_h])
mpr_half_mm = (mpr0_display.shape[0] / 2.0) * xs_pixel_spacing
ax_mpr.imshow(
    mpr0_display,
    **WL,
    aspect="auto",
    extent=[0, cross_sharp.shape[0] - 1, mpr_half_mm, -mpr_half_mm],
)
for s_vals, lo, hi, color in [
    (*lumen_env, LUMEN_COLOR),
    (*wall_env, WALL_COLOR),
]:
    ax_mpr.plot(s_vals, lo, color=color, lw=1.8, alpha=0.95)
    ax_mpr.plot(s_vals, hi, color=color, lw=1.8, alpha=0.95)
styled_spines(ax_mpr)
title_above(ax_mpr, f"Straightened MPR  (FC51 sharp)   —   full length, {2*mpr_half_mm:.1f} mm vertical FOV")
ax_mpr.text(0.995, 0.04, f"{mp.IMAGE_REFORMAT_LABEL} reformat · nearest display",
            transform=ax_mpr.transAxes, ha="right", va="bottom",
            fontsize=9.5, color="white",
            bbox=dict(facecolor="black", alpha=0.35, edgecolor="none", pad=2.5))

# Row 3: 4 cross-sections — zoomed to XS_FOV_MM, with MEDIS lumen + wall overlays
n_xs = 4
gap = 0.010
xs_w = (RIGHT_W - (n_xs - 1) * gap) / n_xs
fig.text(RIGHT_X0, r3_b + r3_h + 0.018,
         f"Cross-sections   ·   FC51 linear reformat   ·   {XS_FOV_MM:.0f} mm FOV   "
         f"·   red lumen   ·   cyan wall",
         fontsize=ROW_TITLE_FS, color=NAVY, fontweight="bold")
half = XS_FOV_MM / 2.0
for k, (s_idx, lab) in enumerate(zip(xs_idx, xs_labels)):
    ax = fig.add_axes([RIGHT_X0 + k * (xs_w + gap), r3_b, xs_w, r3_h])
    cropped = mp.crop_to_fov(cross_sharp[s_idx], xs_pixel_spacing, XS_FOV_MM)
    ax.imshow(cropped, **WL, extent=[-half, half, half, -half])
    r_i = mp.best_ring_for_slice(s_idx, cl_frame, lumen_rings)
    r_w = mp.best_ring_for_slice(s_idx, cl_frame, wall_rings)
    mp.draw_medis_overlay(ax, lumen_rings[r_i], wall_rings[r_w],
                          cl_frame, n_frame, b_frame, s_idx, XS_FOV_MM)
    styled_spines(ax)
    ax.set_xticks([]); ax.set_yticks([])
    ax.text(0.5, 1.012, f"{lab}   (s = {s_idx})", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=11, color=NAVY)

# --- Footer ---
fig.text(0.045, 0.05, "Charité / DISCHARGE  ·  Patient 01-BER-0088  ·  LAD  ·  MEDIS contours + CTA",
         fontsize=FOOTER_FS, color=SOFT_GRAY, va="center")
fig.text(0.955, 0.05, "Coronary Vessel Visualisation POC",
         fontsize=FOOTER_FS, color=SOFT_GRAY, ha="right", va="center", style="italic")
ax_rule = fig.add_axes([0.045, 0.030, 0.91, 0.003])
ax_rule.set_facecolor(BORDER_BLUE); ax_rule.set_xticks([]); ax_rule.set_yticks([])
for s in ax_rule.spines.values():
    s.set_visible(False)

fig.savefig(OUT, dpi=170, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"saved {OUT}")
