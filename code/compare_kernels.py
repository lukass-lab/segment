#!/usr/bin/env python3
"""Side-by-side comparison: FC03 (smooth, default) vs FC51 (sharp kernel)."""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import SimpleITK as sitk
from scipy.ndimage import map_coordinates

DATA = Path("/home/lukass/workspace/segment/data")
OUT = DATA / "previews"

WL = dict(cmap="gray", vmin=-100, vmax=700, interpolation="nearest")


def load(p):
    return sitk.GetArrayFromImage(sitk.ReadImage(str(p)))


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
        out[:, s] = map_coordinates(cross[s], [line_v, line_u], order=0, mode="constant", cval=-1024)
    return out


smooth_cross = load(DATA / "01-BER-0088_LAD_cpr_cross.nii.gz")
sharp_cross  = load(DATA / "01-BER-0088_LAD_cpr_cross_FC51.nii.gz")
print("FC03 (smooth)", smooth_cross.shape, "FC51 (sharp)", sharp_cross.shape)

# Cross-sections at corresponding vessel fractions
fractions = [0.15, 0.30, 0.45, 0.60, 0.75, 0.90]
fig, axes = plt.subplots(2, len(fractions), figsize=(2.4 * len(fractions), 5.2))
fig.suptitle("Cross-section walkthrough  —  FC03 (smooth std kernel)   vs   FC51 (sharp kernel)", fontsize=13, y=1.02)
for col, frac in enumerate(fractions):
    s_smooth = int(smooth_cross.shape[0] * frac)
    s_sharp  = int(sharp_cross.shape[0]  * frac)
    axes[0, col].imshow(smooth_cross[s_smooth], **WL)
    axes[0, col].set_title(f"frac {frac:.2f}\n(s={s_smooth})", fontsize=9)
    axes[0, col].axis("off")
    axes[1, col].imshow(sharp_cross[s_sharp], **WL)
    axes[1, col].set_title(f"frac {frac:.2f}\n(s={s_sharp})", fontsize=9)
    axes[1, col].axis("off")
axes[0, 0].set_ylabel("FC03\nsmooth", fontsize=11)
axes[1, 0].set_ylabel("FC51\nsharp", fontsize=11)
# Override axis-off for first column to keep labels
for r, lab in enumerate(["FC03  smooth", "FC51  sharp"]):
    axes[r, 0].text(-0.08, 0.5, lab, transform=axes[r, 0].transAxes,
                    rotation=90, ha="center", va="center", fontsize=12, fontweight="bold")
fig.tight_layout()
out = OUT / "06_kernel_compare_cross.png"
fig.savefig(out, dpi=160, bbox_inches="tight")
plt.close(fig)
print("saved", out)

# Straightened MPR at 0° angle
mpr_smooth = sample_mpr(smooth_cross, 0)
mpr_sharp  = sample_mpr(sharp_cross,  0)
fig, axes = plt.subplots(2, 1, figsize=(14, 5))
fig.suptitle("Straightened MPR  —  FC03 (smooth) vs FC51 (sharp)", fontsize=13, y=0.99)
axes[0].imshow(mpr_smooth, **WL, aspect="auto")
axes[0].set_title("FC03  smooth std kernel", fontsize=11)
axes[0].axis("off")
axes[1].imshow(mpr_sharp, **WL, aspect="auto")
axes[1].set_title("FC51  sharp kernel", fontsize=11)
axes[1].axis("off")
fig.tight_layout()
out = OUT / "07_kernel_compare_mpr.png"
fig.savefig(out, dpi=160, bbox_inches="tight")
plt.close(fig)
print("saved", out)
