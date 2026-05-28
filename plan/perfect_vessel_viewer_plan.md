---
title: "Perfect Vessel Viewer Upgrade Plan"
author: "Segment Project"
date: "2026-05-28"
toc: true
toc-depth: 2
numbersections: false
bibliography: references.bib
csl: vancouver-superscript.csl
link-citations: true
header-includes:
  - \usepackage{tocloft}
  - \setlength{\cftbeforesecskip}{0.12em}
  - \setlength{\cftbeforesubsecskip}{0em}
  - \renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}
---

Status: technical upgrade plan for the coronary vessel visualisation proof of concept.

# Perfect Vessel Viewer Upgrade Plan

## Goal

Build a robust coronary vessel viewer that can start from either expert MEDIS contours or a voxel plaque/wall mask, then produce aligned 3D, axial, CPR cross-section, and straightened MPR views for presentation, review, and later quantitative work.

The central design idea is a unified vessel model. MEDIS provides sparse expert contour rings; vendor plaque masks provide dense voxel labels. Both should be converted into the same internal representation:

`centerline + local frame + lumen surface + wall surface + optional plaque labels`.

Every view, export, and validation check should then operate on this unified model rather than on one source format directly.

## Canonical VesselScene Contract

The most important architecture decision is to freeze a common scene contract before building a larger app. The backend or preprocessing pipeline produces a `VesselScene`; the frontend consumes it. MEDIS and voxel-mask inputs must both emit the same object shape.

```ts
VesselScene = {
  patient_id: string,
  vessel_name: string,
  source_type: "medis" | "mask" | "hybrid",
  centerline: {
    points: number[][],       // N x 3 world-mm points
    tangents: number[][],
    normals: number[][],
    binormals: number[][],
    arc_length: number[],
    station_count: number
  },
  surfaces: {
    lumen: Mesh,
    wall: Mesh,
    plaque?: Mesh
  },
  volumes: {
    cpr_cross: NiftiVolume,
    cpr_long: NiftiVolume
  },
  overlays: {
    medis_rings?: PolylineSet,
    mask_contours?: PolylineSet
  },
  quant: {
    per_station: PerStationMetrics,
    lesion_summary: LesionSummary
  },
  provenance: {
    ct_uid: string,
    spacing: number[],
    origin: number[],
    direction: number[],
    algorithm_versions: object,
    created_at: string
  }
}
```

This contract is the boundary between compute and presentation. Once it is stable, a MEDIS converter, a vendor-mask converter, and a web viewer can be developed independently.

## Glossary

| Term | Meaning in this project |
|---|---|
| CTA | Coronary CT angiography volume used as the intensity image source. |
| MEDIS | Expert annotation/export format containing lumen and vessel-wall contour rings. |
| Lumen / inner wall | The contrast-filled inside of the vessel; the boundary used for diameter and stenosis measurements. |
| Vessel wall / outer wall | The outer vessel boundary around the lumen and plaque/wall tissue. |
| Plaque mask | Voxel label map describing plaque or wall tissue, usually between lumen and outer vessel wall. |
| Centerline | A 3D curve running through the vessel centre from proximal to distal. |
| Station `s` | Integer position along the resampled centerline; all linked views should use the same station index. |
| CPR | Curved Planar Reformation: a CT reformat that follows the curved vessel path instead of a fixed axial/coronal/sagittal plane. |
| CPR cross-section | A slice perpendicular to the vessel centerline at station `s`; used to inspect lumen/wall shape locally. |
| MPR | Multiplanar Reformation: an arbitrary 2D slice or slab sampled from a 3D CT volume. |
| Straightened MPR | A longitudinal CPR view where the curved vessel is unfolded into a straight strip from proximal to distal. |
| RMF | Rotation-Minimizing Frame: local tangent/normal/binormal axes transported along the centerline with minimal twist. |
| FC03 / FC51 | CT reconstruction kernels in this dataset. FC03 is smoother and useful for axial context; FC51 is sharper and better for vessel detail. |
| Window / level | Display mapping from HU values to grayscale; for the slide we use `W1000/L350` (`-150..850 HU`). |
| World coordinates | Physical millimetre coordinates from DICOM/NIfTI metadata, used to align CT, MEDIS, masks, and meshes. |
| Voxel coordinates | Integer or fractional array indices used when sampling the CT or mask volume. |
| Annulus mask | Binary/label mask containing the vessel-wall/plaque shell between inner lumen and outer wall. |
| FMM | Fast Marching Method used to find minimal-cost vessel paths through a distance/radius field. |
| glTF / GLB | Web-native 3D mesh format; `.glb` is the binary single-file form preferred for browser loading. |
| Scene bundle | A zip archive containing the `VesselScene` manifest, volumes, meshes, overlays, quant files, validation report, and preview image. |
| Taubin smoothing | Mesh smoothing without the volume shrinkage typical of plain Laplacian smoothing [@Taubin1995Smoothing]. |

## Current Presentation Prototype

- Input: MEDIS lumen and vessel-wall contour rings for patient `01-BER-0088`, vessel `LAD`.
- CT: DICOM converted to NIfTI; FC03 for axial context, FC51 sharp-kernel reconstruction for CPR/MPR detail.
- Display convention: axial CTA is shown with anterior up after accounting for NIfTI direction/orientation.
- Outputs:
  - 3D lumen/wall mesh from contour rings.
  - Separate 3D point clouds for inner/lumen and outer/wall contours.
  - Straightened MPR with lumen and wall boundary envelopes.
  - CPR cross-sections with MEDIS lumen and wall ring overlays.

## Technical Decisions Captured From The Prototype

- Use FC51 sharp-kernel CT for CPR/MPR detail. The earlier blur was mainly intrinsic to the FC03 standard/noise-reducing reconstruction, not a display bug.
- Use linear interpolation (`order=1`) for CT intensity reformats. At FC51 spacing this removes oblique staircase artifacts without materially blurring the already sharp reconstruction.
- Use nearest-neighbor display (`imshow(interpolation="nearest")`) for generated PNGs so no extra display-level smoothing is introduced.
- Use nearest-neighbor resampling only for labels, masks, or deliberately voxelated debug views.
- Keep separate lumen and vessel-wall point-cloud panels on the presentation slide when visibility matters; a combined point-cloud panel is useful as a compact alternative.
- Treat straightened-MPR contour overlays as projection envelopes unless exact plane/ring intersections are explicitly computed. The envelope is not the true outline of an oblique cut; it is the projected min/max silhouette of the ring set along the selected MPR chord.
- Use double-reflection RMF as the default frame method for CPR and scene bundles [@Wang2008RotationMinimizing]. Validation on the LAD prototype showed projection/Bishop propagation can drift by about `18.6°` relative to double-reflection, so the projection method is retained only as a diagnostic/backwards-compatible comparison.
- Freeze the `VesselScene` scene-bundle contract before building a larger app. The MEDIS pipeline, the voxel-mask pipeline, and the web viewer should meet at that contract rather than depending on each other's internal file formats.
- Use `.glb` for future browser-facing 3D surfaces and keep STL/GIfTI only as intermediate or legacy research exports.

## Coordinate Systems

| Space | Units | Axes | Purpose | Transform rule |
|---|---:|---|---|---|
| DICOM patient/world | mm | DICOM LPS unless converted | Physical reference for CT, MEDIS, masks, meshes | From DICOM tags or NIfTI affine/direction |
| Voxel index | index | `(i, j, k)` | Sampling source CTA/mask arrays | `voxel = D^-1 · (world - origin) / spacing` |
| CPR-cross | mm / station | `(U, V, S)` | Perpendicular cross-sections along vessel | `world = C[S] + U·N[S] + V·B[S]` |
| CPR-long | mm / station | `(S, U, V)` | Straightened MPR volume/viewer layout | Axis permutation of CPR-cross |

Orientation policy:

- Preserve physical coordinates internally.
- DICOM CT is usually LPS; NIfTI written by `dcm2niix` may encode an axis flip in the direction/affine matrix.
- Screenshot display is a separate presentation choice. For the current slide, axial CTA is shown anterior-up, so the array view is vertically flipped together with the centerline overlay.

## Mathematical Notation And Transforms

Use one explicit notation throughout the code and documentation:

- Patient/world point in millimetres: $\mathbf{p} = (x, y, z)^\top \in \mathbb{R}^3$.
- Voxel index, possibly fractional for interpolation: $\mathbf{i} = (i, j, k)^\top$.
- Image origin: $\mathbf{o}$.
- Voxel spacing: $\mathbf{s} = (s_i, s_j, s_k)^\top$.
- Direction matrix: $\mathbf{D} \in \mathbb{R}^{3 \times 3}$, orthonormal, usually from DICOM/NIfTI metadata.
- Centerline point at station $s_k$: $\mathbf{c}_k$.
- Local frame at station $k$: tangent $\mathbf{T}_k$, normal $\mathbf{N}_k$, binormal $\mathbf{B}_k$.

Voxel-to-world transform:

$$
\mathbf{p} = \mathbf{o} + \mathbf{D}\,\mathrm{diag}(\mathbf{s})\,\mathbf{i}.
$$

World-to-voxel transform:

$$
\mathbf{i} = \mathrm{diag}(\mathbf{s})^{-1}\mathbf{D}^{\top}(\mathbf{p} - \mathbf{o}).
$$

This formula is mandatory. Ignoring $\mathbf{D}$ caused the original all-zero CPR sampling bug.

CPR-cross coordinate map:

$$
\mathbf{p}(k,u,v) =
\mathbf{c}_k + u\,\mathbf{N}_k + v\,\mathbf{B}_k .
$$

Straightened MPR / rotational CPR map:

$$
\mathbf{p}(k,r,\theta) =
\mathbf{c}_k + r\left(\cos\theta\,\mathbf{N}_k + \sin\theta\,\mathbf{B}_k\right).
$$

Intensity sampling:

$$
I_{\mathrm{cross}}(u,v,k) =
I_{\mathrm{CTA}}\!\left(\mathbf{p}(k,u,v)\right),
$$

$$
I_{\mathrm{long}}(k,r,\theta) =
I_{\mathrm{CTA}}\!\left(\mathbf{p}(k,r,\theta)\right).
$$

Implementation convention:

- CT intensities use linear interpolation and an out-of-bounds value of `-1024 HU`.
- Masks and labels use nearest-neighbor interpolation.
- PNG display uses nearest-neighbor display interpolation to avoid extra visual smoothing.
- NIfTI/DICOM orientation should follow the metadata internally; screenshot orientation is a labelled display choice [@Nifti1Spec; @DICOMPS3].

## Core Mathematical Algorithms

### Centerline Parameterisation

Given raw centerline candidates $\mathbf{q}_0,\dots,\mathbf{q}_n$, first fit a smooth curve, then parameterise by arc length. For a discrete curve:

$$
L_i = \sum_{j=0}^{i-1}\|\mathbf{q}_{j+1} - \mathbf{q}_{j}\|_2 .
$$

Sample a smoothed spline curve at uniform stations:

$$
s_k = k\,\Delta s,\qquad
\mathbf{c}_k = \mathrm{Spline}(s_k).
$$

The spline should be fit before final arc-length resampling, otherwise annotation jitter or skeleton jaggedness is preserved in the frame [@DeBoor1978Splines].

Tangents use central differences and normalization:

$$
\mathbf{T}_k =
\frac{\mathbf{c}_{k+1}-\mathbf{c}_{k-1}}
{\|\mathbf{c}_{k+1}-\mathbf{c}_{k-1}\|_2}.
$$

Endpoint tangents use one-sided differences.

### Rotation-Minimizing Frame

Legacy comparison method: projection/Bishop step. Given $\mathbf{N}_k$ and the next tangent $\mathbf{T}_{k+1}$:

$$
\tilde{\mathbf{N}} =
\mathbf{N}_k - (\mathbf{N}_k \cdot \mathbf{T}_{k+1})\mathbf{T}_{k+1},
$$

$$
\mathbf{N}_{k+1} =
\frac{\tilde{\mathbf{N}}}{\|\tilde{\mathbf{N}}\|_2},
\qquad
\mathbf{B}_{k+1} =
\mathbf{T}_{k+1} \times \mathbf{N}_{k+1}.
$$

This is useful as a simple diagnostic method, but it accumulates measurable twist drift on real LAD geometry and should not be the exported default.

Default method: double-reflection RMF [@Wang2008RotationMinimizing]. Define a reflection about vector $\mathbf{v}$:

$$
R_{\mathbf{v}}(\mathbf{x}) =
\mathbf{x} -
2\frac{\mathbf{v}\cdot\mathbf{x}}{\mathbf{v}\cdot\mathbf{v}}\mathbf{v}.
$$

Then propagate the frame:

$$
\mathbf{v}_1 = \mathbf{c}_{k+1} - \mathbf{c}_{k},\qquad
\mathbf{T}^{L}_{k} = R_{\mathbf{v}_1}(\mathbf{T}_{k}),\qquad
\mathbf{N}^{L}_{k} = R_{\mathbf{v}_1}(\mathbf{N}_{k}),
$$

$$
\mathbf{v}_2 = \mathbf{T}_{k+1} - \mathbf{T}^{L}_{k},\qquad
\mathbf{N}_{k+1} = R_{\mathbf{v}_2}(\mathbf{N}^{L}_{k}),\qquad
\mathbf{B}_{k+1} = \mathbf{T}_{k+1}\times\mathbf{N}_{k+1}.
$$

If $\|\mathbf{v}_1\|$ or $\|\mathbf{v}_2\|$ is numerically tiny, fall back to copying or re-orthogonalizing the previous frame. This method is the target for quantitative exports.

### Centerline From Voxel Masks

If a lumen mask $M_{\mathrm{lumen}}$ is available, it is the preferred centerline source. Compute the Euclidean distance transform inside the lumen:

$$
d(\mathbf{x}) = \mathrm{dist}(\mathbf{x}, \partial M_{\mathrm{lumen}}).
$$

A fast-marching medial path solves:

$$
\|\nabla T(\mathbf{x})\| = P(\mathbf{x}),
\qquad
P(\mathbf{x}) = \frac{1}{d(\mathbf{x}) + \varepsilon}.
$$

Here $P$ is the traversal cost/slowness, so high-radius medial voxels have low cost. The centerline is recovered by following the steepest descent path on $T$ from distal seed to proximal seed, biased toward high-distance medial voxels [@Sethian1996FastMarching; @DeschampsCohen2001MinimalPaths].

If a clean lumen surface is available, the VMTK-style surface method is also appropriate: compute the internal Voronoi diagram of the lumen surface and extract a shortest path constrained to that diagram, with cost based on the inverse maximal-inscribed-sphere radius [@Antiga2008VMTK]. This produces centerline points with an associated local lumen radius and is particularly useful when the surface topology is clean and endpoints are known.

Fallback: 3D thinning/skeletonization, graph extraction, endpoint-constrained longest or lowest-cost path, then spline smoothing [@Lee1994Skeletons].

### Surface Extraction From Masks

For binary masks, extract the isosurface at level $0.5$ using marching cubes [@Lorensen1987MarchingCubes]. Vertices must then be mapped to world coordinates with the voxel-to-world transform above.

Mesh post-processing:

- split connected components and label them as lumen/wall by centerline containment and normal direction;
- Taubin smooth with non-shrinking parameters, e.g. $\lambda=0.50$, $\mu=-0.53$, about `20` iterations [@Taubin1995Smoothing];
- decimate with quadric error metrics toward a web budget, e.g. `8k-12k` triangles per surface [@Garland1997QuadricDecimation];
- recompute normals and preserve scalar fields such as wall thickness or plaque class.

## Core Viewer Requirements

1. Data loading
   - Load CTA volume with correct affine/direction handling.
   - Load MEDIS contours, mesh files, NIfTI masks, and metadata.
   - Preserve patient/world coordinates instead of assuming identity direction.

2. Geometry model
   - Smooth the raw centerline candidates, for example MEDIS lumen centroids, with a spline first.
   - Reparameterize the smoothed curve by arc length and resample at the target station spacing.
   - Compute a stable rotation-minimizing frame along the centerline.
   - Default method: double-reflection RMF for reproducibility and lower accumulated twist than simple projection propagation.
   - Initial frame should eventually have clinical meaning: project an anatomical direction such as anterior or an RAO/LAO reference into the plane perpendicular to the first tangent. The current "axis least aligned with tangent" rule is acceptable for prototype visualisation but arbitrary.
   - Store transforms between world, voxel, CPR, and straightened coordinates.

3. Views
   - Axial CTA with correct radiological orientation.
   - 3D view: point cloud, mesh, centerline, voxel-mask surface.
   - CPR cross-section view perpendicular to centerline.
   - Straightened MPR with rotatable angle around centerline.
   - Straightened MPR contour mode:
     - envelope overlay for presentation,
     - exact intersection overlay for quantitative review.
   - Linked cursor contract:
     - a single integer station index `s` is the shared state;
     - cross-section view displays CPR slice `s`;
     - straightened MPR displays a vertical cursor at column `s`;
     - 3D view highlights `centerline[s]`;
     - axial CTA jumps to the source slice closest to `centerline[s]`.

4. Visual overlays
   - MEDIS lumen and vessel-wall rings.
   - Mesh surfaces for lumen and vessel wall.
   - Centerline and station markers.
   - Voxel mask contours / marching-cubes surfaces.
   - Plaque components if available: calcified, non-calcified, low attenuation.

## MEDIS-Based Pipeline

1. Parse raw MEDIS contour `.txt`.
2. Extract lumen centroids as the initial centerline samples.
3. Smooth the centroid path with a spline to suppress ring-to-ring annotation jitter.
4. Resample the smoothed curve by arc length.
5. Compute rotation-minimizing frame.
6. Generate CPR volume by sampling CTA in world coordinates.
7. Project each MEDIS ring into local CPR coordinates for validation overlays.
8. Build meshes from contour rings for 3D rendering.

## Voxel-Mask / Vendor Plaque-Mask Pipeline

Future input may be a voxel mask representing the vessel wall/plaque volume between inner and outer boundaries. "Vendor plaque mask" is used generically here; a specific AutoPlaque/Cleerly-style export should be handled according to its actual label semantics.

The canonical input set should be:

- required: `{CTA, at least one vessel mask}`;
- preferred: `{lumen mask}` if the vendor provides it;
- optional/additional: `{plaque-annulus mask, outer-wall mask, centerline polyline, endpoint seeds}`.

The pipeline must degrade gracefully across these input shapes. If a lumen mask exists, use it as the primary source for centerline extraction and lumen-surface geometry. The plaque-annulus or wall mask then adds outer-wall/plaque information. A mask-only annulus can still provide outer wall, inner lumen boundary, and an estimated centerline, but that is the harder fallback case.

Expected handling:

1. Load `{CTA, mask}` and verify physical-space compatibility.
   - Compare spacing, origin, direction/affine, and orientation within tolerance.
   - If the mask is aligned but sampled differently, resample the mask to CTA space with nearest-neighbor interpolation.
   - Stop if the metadata implies unresolved registration mismatch.

2. Detect mask topology and semantic labels.
   - Classify each supplied mask as lumen, plaque annulus, outer wall, solid blob, disconnected components, or multi-branch structure.
   - Prefer a true lumen mask for centerline extraction.
   - For disconnected components, use connected-component filtering or explicit vessel selection.
   - Reject or flag non-annular masks if lumen/wall separation is required and cannot be inferred.

3. Recover or import the centerline, in priority order.
   - **If lumen mask exists:** compute the Euclidean distance transform inside the lumen, then route a fast-marching/minimal-cost path with cost approximately `1 / (distance + ε)` so the path follows the medial high-radius ridge [@DeschampsCohen2001MinimalPaths; @Sethian1996FastMarching; @Kimmel1998GeodesicPaths].
   - **If a clean lumen surface exists:** optionally use the VMTK/Voronoi centerline route. Extract a lumen surface, cap or define endpoints, compute the internal Voronoi diagram / maximal-inscribed-sphere radius field, and run shortest path with cost `1/R` [@Antiga2008VMTK].
   - **If only annulus exists:** first recover the lumen hole or inner surface, then use the lumen-mask or lumen-surface route above.
   - **Fallback:** voxel skeleton to graph to longest or endpoint-constrained path; then spline smooth and arc-length resample.
   - **Manual escape hatch:** accept a vendor-provided centerline, uploaded polyline, or two clicked endpoints plus auto-routing.
   - Validate that each centerline station remains safely inside the lumen or filled vessel volume; reject paths whose minimum distance-to-boundary is below a vessel-radius threshold, e.g. `< 1 mm`.

4. Smooth and resample the accepted centerline.
   - Fit a cubic spline or equivalent smooth curve before arc-length resampling.
   - Compute local tangent and RMF.
   - Store all world/voxel/CPR transforms in the scene bundle.

5. Extract surfaces from masks.
   - From a lumen mask: run marching cubes at `level=0.5` to obtain the lumen surface directly.
   - From an outer-wall mask: run marching cubes to obtain the outer wall surface.
   - From a plaque-annulus mask: run marching cubes and split components; a binary annulus may produce inner and outer surface components, but this must be validated.
   - Always transform vertices to world coordinates using `world = origin + direction · (spacing · voxel)`.
   - Label components as lumen and wall using mask semantics first, then centerline containment/distance and normal direction checks.
   - Smooth with Taubin smoothing, not plain Laplacian smoothing, to reduce staircase artifacts without shrinking the vessel [@Taubin1995Smoothing].
   - Decimate each surface to a target web budget, for example `8k-12k` triangles per surface.
   - Compute normals and optional per-vertex colors, e.g. wall thickness or plaque class.

6. Generate CPR/MPR using the same centerline/frame machinery as the MEDIS pipeline.
   - CT intensities use linear interpolation.
   - Mask labels use nearest-neighbor interpolation.
   - CPR-space label maps can then produce cross-section contours and straightened-MPR overlays.

7. Compute per-station quantitative metrics.

8. Write the common `VesselScene` scene bundle.

This pipeline is intentionally parallel to the MEDIS path. MEDIS builds surfaces from contour rings; the mask path builds surfaces from marching cubes. Downstream views, exports, validation reports, and quantitative metrics should not care which path created the scene.

## Optional Interactive Segmentation Track

The older `vessel-segmenter.md` plan describes a third source path: start from CTA only, let the user place two endpoint clicks, and estimate centerline, lumen, and outer wall with classical image processing. This is not required for the current presentation slide or for vendor-mask ingestion, but it is valuable as a fallback and as a future research feature.

Source input:

- CTA volume;
- two user-selected endpoints, e.g. proximal and distal LAD;
- optional vesselness map cache.

Pipeline:

1. Compute a vesselness image, e.g. Frangi/Hessian multi-scale filter.
2. Build a cost map where vessel-like voxels have low traversal cost.
3. Extract an initial centerline using FMM or minimal path between the endpoint seeds.
4. Generate perpendicular MPR cross-sections along that centerline.
5. Convert each cross-section into polar coordinates around the center point.
6. Use dynamic programming / graph search to find lumen and outer-wall radial boundaries.
7. Refine the centerline from lumen centroids to reduce corner cutting.
8. Smooth, arc-length resample, compute RMF, build surfaces, CPR volumes, overlays, and metrics.
9. Emit the same `VesselScene` bundle as the MEDIS and mask pipelines.

This track is more algorithmically ambitious than viewing a supplied mask. It should therefore be treated as optional and interactive, with visible confidence/validation outputs. It is useful when no MEDIS contours and no vendor plaque mask are available.

## Scene Bundle Format

A single vessel export should be a portable zip archive named like:

`vessel_scene_{patient}_{vessel}.zip`

Recommended layout:

```text
manifest.json
cta.nii.gz                         # optional full CT, or external reference
mask.nii.gz                        # source annulus/label mask audit trail
centerline.json                    # points, tangents, normals, binormals, arc length
cpr/
  cross_volume.nii.gz              # U x V x S CPR cross-section volume
  long_volume.nii.gz               # S x U x V straightened/rotational source
  frame.json                       # redundant frame copy for standalone use
surfaces/
  lumen.glb                        # inner/lumen surface
  wall.glb                         # outer vessel-wall surface
  plaque_components.glb            # optional plaque labels or components
overlays/
  medis_rings.json                 # if MEDIS source
  voxel_mask_uv.json               # per-station projected mask contours
quant/
  per_station_metrics.json
  lesion_summary.json
validation.json
preview.png
```

Format choices:

- `.glb` for meshes because it is web-native, compact, single-request, and supports normals, materials, and per-vertex colors. Prefer it over STL for the future app.
- `.nii.gz` for CT/CPR volumes because it preserves affine metadata and is supported by NiiVue.
- JSON for centerline, frame, validation, and quantitative metrics because it is inspectable and browser-native.
- One zip for upload/download ergonomics and reproducible audit trails.

## Scene Bundle Schemas

The scene bundle contract is now explicit: every JSON artifact in the zip has a JSON Schema in `plan/schemas/` and at least one worked example in `plan/examples/`. The schemas use JSON Schema Draft 2020-12.

Schema files:

- `plan/schemas/vessel_scene_manifest.schema.json` for `manifest.json`.
- `plan/schemas/centerline.schema.json` for `centerline.json` and `cpr/frame.json`.
- `plan/schemas/medis_rings.schema.json` for `overlays/medis_rings.json`.
- `plan/schemas/per_station_metrics.schema.json` for `quant/per_station_metrics.json`.
- `plan/schemas/lesion_summary.schema.json` for `quant/lesion_summary.json`.
- `plan/schemas/validation.schema.json` for `validation.json`.

Example files:

- `plan/examples/vessel_scene_manifest.example.json`.
- `plan/examples/centerline.example.json`.
- `plan/examples/medis_rings.example.json`.
- `plan/examples/validation.example.json`.
- `plan/examples/per_station_metrics.example_placeholder.json` and `plan/examples/per_station_metrics.example_populated.json`.
- `plan/examples/lesion_summary.example_placeholder.json` and `plan/examples/lesion_summary.example_populated.json`.

The LAD prototype bundle validates with:

```bash
python code/validate_bundle_schemas.py data/vessel_scene_01-BER-0088_LAD.zip
```

This schema validation is intentionally separate from medical/numerical validation. It answers "can a frontend or downstream tool safely parse this bundle?" The numerical report in `validation.json` answers "is this bundle geometrically and mathematically trustworthy?"

Schema versioning policy:

- Use `artifact_name/major.minor`, for example `vessel_scene/0.1` or `centerline/0.1`.
- Breaking changes bump the major version. Examples: renaming required keys, changing coordinate conventions, changing units, or changing array layout.
- Additive backwards-compatible changes bump the minor version. Examples: optional fields, extra diagnostic metrics, or new optional overlay files.
- Frontend loaders must reject unknown major versions and may warn on newer minor versions.
- Keep schemas and examples together: a schema change is not complete until the matching example file validates.
- The zip-level `manifest.json` is the source of truth for bundle version and paths; individual artifact schemas protect artifact-level parsing.

## Quantitative Outputs

The first viewer can remain visual, but the future quantitative review mode should always export explicit per-station and lesion-level outputs. CPR image-space contours are useful for display, but the preferred quantitative route is plane/surface intersection: intersect the lumen surface with the perpendicular plane at station $k$, recover a ring in $(u,v)$ coordinates, then compute the following metrics from that ring.

Lumen area:

$$
A_k = \frac{1}{2}\left|
\sum_{m=1}^{M}
u_m v_{m+1} - u_{m+1} v_m
\right|
$$

with cyclic indexing $M+1 \equiv 1$.

Effective lumen diameter:

$$
D_{\mathrm{eff},k} = 2\sqrt{\frac{A_k}{\pi}}.
$$

Minimum lumen diameter and minimum lumen area:

$$
\mathrm{MLD} = \min_{k \in \mathcal{L}} D_{\min,k},
\qquad
\mathrm{MLA} = \min_{k \in \mathcal{L}} A_k,
$$

where $\mathcal{L}$ is the analysed lesion or vessel segment. $D_{\min,k}$ should be documented as a Feret/minimum caliper diameter or as another explicit diameter definition.

Area stenosis:

$$
\mathrm{AS} =
1 - \frac{A_{\min}}{A_{\mathrm{ref}}},
\qquad
A_{\mathrm{ref}} =
\frac{A_{\mathrm{ref,prox}} + A_{\mathrm{ref,dist}}}{2}.
$$

Diameter stenosis:

$$
\mathrm{DS} =
1 - \frac{D_{\min}}{D_{\mathrm{ref}}}.
$$

Reference area/diameter selection must be recorded, because this choice changes the reported stenosis percentage [@Leipsic2014CCTA; @Cury2022CADRADS2].

Wall thickness for an inner-surface point $\mathbf{v}_{\mathrm{in}}$:

$$
t(\mathbf{v}_{\mathrm{in}}) =
\min_{\mathbf{v}_{\mathrm{out}}\in S_{\mathrm{outer}}}
\|\mathbf{v}_{\mathrm{out}}-\mathbf{v}_{\mathrm{in}}\|_2.
$$

Per-station wall thickness is the mean, median, maximum, and angular profile of all inner vertices in a tangent band around station $k$.

Plaque and calcium volume:

$$
V_{\mathrm{label}} =
N_{\mathrm{voxels,label}}\;s_i s_j s_k .
$$

Calcium volume from CTA can be counted inside the plaque/wall mask using a threshold such as `HU > 130`. An Agatston-style score requires a non-contrast calcium series and slice-specific rules:

$$
\mathrm{Score} =
\sum_{\mathrm{slices}}\sum_{\mathrm{lesions}}
A_{\mathrm{lesion}}\;w(\max \mathrm{HU}),
$$

with weights $w=1,2,3,4$ for maxima in `130-199`, `200-299`, `300-399`, and `>=400 HU`, respectively [@Agatston1990Calcium]. CCTA plaque attenuation categories should be documented separately from Agatston scoring [@MaurovichHorvat2014Plaque].

Export:

- per-station area, diameter, wall thickness, plaque burden, and calcium flags;
- lesion-level MLD, MLA, stenosis percentages, lesion length, plaque volumes, and reference choices;
- CSV/JSON with units and method metadata.

## Mathematical Validation Metrics

Direction-matrix check: all world-to-voxel sampling must use

$$
\mathbf{i} = \mathrm{diag}(\mathbf{s})^{-1}\mathbf{D}^{\top}(\mathbf{p} - \mathbf{o}).
$$

Frame unit-length error:

$$
\varepsilon_{\mathrm{unit}} =
\max_k \max\left(
\left|\|\mathbf{T}_k\|_2-1\right|,
\left|\|\mathbf{N}_k\|_2-1\right|,
\left|\|\mathbf{B}_k\|_2-1\right|
\right)
< 10^{-6}.
$$

Frame orthogonality error:

$$
\varepsilon_{\perp} =
\max_k \max\left(
|\mathbf{T}_k\cdot\mathbf{N}_k|,
|\mathbf{T}_k\cdot\mathbf{B}_k|,
|\mathbf{N}_k\cdot\mathbf{B}_k|
\right)
< 10^{-6}.
$$

Right-handedness:

$$
\min_k \det[\mathbf{T}_k,\mathbf{N}_k,\mathbf{B}_k] > 0.999.
$$

Centerline CT coverage:

$$
\frac{\#\{k:\mathbf{c}_k \in \Omega_{\mathrm{CTA}}\}}{N}=1.0.
$$

MEDIS ring out-of-plane residual:

$$
\rho_i =
\max_{\mathbf{p}\in R_i}
\left|
(\mathbf{p}-\mathbf{c}_{k(i)})\cdot\mathbf{T}_{k(i)}
\right|
< 1\,\mathrm{mm}.
$$

Mask/CTA affine agreement is checked componentwise, because origin and spacing are in millimetres while the direction matrix is dimensionless; combining them into a single scalar would be unit-inconsistent.

Origin offset (mm):

$$
\varepsilon_{\mathrm{o}} =
\|\mathbf{o}_{M}-\mathbf{o}_{CT}\|_2
< 10^{-3}\,\mathrm{mm}.
$$

Direction-matrix error (dimensionless, Frobenius norm of the difference of two orthonormal $3\times 3$ matrices, so $\varepsilon_{\mathbf{D}}\in[0,2\sqrt{2}]$):

$$
\varepsilon_{\mathbf{D}} =
\|\mathbf{D}_{M}-\mathbf{D}_{CT}\|_F
< 10^{-4}.
$$

Spacing error (mm):

$$
\varepsilon_{\mathbf{s}} =
\|\mathbf{s}_{M}-\mathbf{s}_{CT}\|_2
< 10^{-3}\,\mathrm{mm}.
$$

All three thresholds must hold. If any one fails:

- If the mask is on a known grid that is a rigid resample of the CTA (same direction, integer-scaled spacing, aligned origin within $\varepsilon_{\mathrm{o}}$), resample the mask to CTA space with nearest-neighbor interpolation.
- Otherwise stop and emit a registration-mismatch diagnostic; do not silently resample.

Centerline-in-mask check:

$$
\min_k d(\mathbf{c}_k,\partial M) > r_{\min},
\qquad r_{\min}=1\,\mathrm{mm}
$$

for mask-derived centerlines.

Surface checks:

- non-manifold edge count equals `0`;
- connected-component count matches expected topology;
- lumen/wall surfaces are watertight if surface-based quantification is enabled;
- vertex and triangle counts are reported before and after smoothing/decimation.

Twist-drift diagnostic:

$$
\Delta\phi =
\max_k \angle\left(
\mathbf{N}^{\mathrm{projection}}_k,
\mathbf{N}^{\mathrm{double-reflection}}_k
\right).
$$

If $\Delta\phi > 5^\circ$ for a projection/Bishop scene, regenerate with double-reflection RMF before exported quantitative views. The LAD prototype projection frame measured `18.6°` maximum drift, so double-reflection is now the default.

Straightened MPR contour overlays must be documented as projection envelopes unless exact plane/ring or plane/surface intersections are computed.

Validation should be interpreted in tiers rather than as one universal binary threshold. Presentation visualisation, clinical-review support, and published quantitative metrics have different tolerance requirements.

| Metric | Viz tier | Review tier | Quant tier | Notes |
|---|---:|---:|---:|---|
| Frame unit-length error | `< 1e-6` | `< 1e-6` | `< 1e-8` | numerical sanity check |
| Frame orthogonality error | `< 1e-6` | `< 1e-6` | `< 1e-8` | numerical sanity check |
| Frame determinant minimum | `> 0.999` | `> 0.999` | `> 0.9999` | right-handed frame |
| Centerline CT coverage | `= 1.0` | `= 1.0` | `= 1.0` | all stations inside source CT |
| MEDIS residual max | `< 5 mm` | `< 2 mm` | `< 1 mm` | max can be endpoint-sensitive |
| MEDIS residual p95 | `< 2 mm` | `< 1 mm` | `< 0.5 mm` | more useful than max for visual trust |
| Mask/CTA origin error | `< 1e-3 mm` | `< 1e-3 mm` | `< 1e-4 mm` | before resampling |
| Centerline-in-mask outside distance | `< 0.5 mm` | `< 0.25 mm` | `= 0 mm` | for mask-derived scenes |
| Projection-frame twist drift | `< 10 deg` | `< 5 deg` | `< 1 deg` | diagnostic; double-reflection should be default |
| Surface non-manifold edges | `= 0` | `= 0` | `= 0` | needed for surface quantification |

Under this scheme the LAD prototype is presentation-ready: `medis.rho_max = 3.38 mm` is acceptable for the viz tier, while `medis.rho_p95 = 0.81 mm` satisfies the review tier. The same report should still flag the max residual as a quantitative caution until endpoint rings or ring-to-station matching are tightened.

## Failure Modes And Fallbacks

| Failure mode | Detection | Fallback |
|---|---|---|
| Centerline exits CT volume | any station outside source image bounds | trim stations, warn, or require source series correction |
| Missing FC51/sharp reconstruction | no matching series/kernel found | use FC03 but label as standard-kernel context, not sharp plaque-detail view |
| Mask lacks lumen/wall labels | label schema missing or single foreground only | show mask surface, defer lumen/wall measurements, request label semantics |
| Skeleton branch ambiguity | multiple graph paths with similar cost | require seed points or manual vessel selection |
| Frame twist or instability | high station-to-station frame rotation | recompute with double-reflection RMF and smoothing |
| MEDIS and CT misregistration | ring residuals or bbox check fail | stop quantitative export and show registration diagnostic |
| Mask and CTA mismatch | spacing/origin/direction differ beyond tolerance | resample only if affine alignment is explicit; otherwise stop |
| Non-annular mask | topology has no lumen hole or ambiguous components | require lumen label, centerline, or manual confirmation |
| Bifurcation inside mask | graph has branch points near target vessel | one-vessel-at-a-time path selection or endpoint seeds |
| Total/subtotal occlusion | lumen hole disappears or distance field collapses | accept user centerline, mark local measurements unreliable |
| Stent or blooming artifact | very high HU and irregular lumen boundary | preserve visualisation but flag quantification caveat |
| Centerline leaves lumen/vessel volume | distance-to-boundary falls below threshold | reject centerline and fall back to alternate path/manual seeds |
| Surface not watertight | mesh boundary edges or invalid normals | repair mesh if possible; otherwise disable surface-based quant |

## Performance Targets

Initial targets for an interactive viewer:

- CPR/MPR generation for one vessel: `< 2 s` after source volume is loaded.
- Full interactive CTA-only segmentation from two endpoint clicks: initial target `20-60 s` per vessel on CPU.
- Linked station cursor update: `< 50 ms`.
- 3D mesh or mask first paint: `< 100 ms` for precomputed surfaces.
- Scene memory for one vessel and one CTA series: `< 500 MB`.
- Exported presentation slide generation: `< 10 s`.

These budgets influence whether the implementation should use NiiVue, VTK.js, Three.js, PyVista export, or precomputed PNG/NIfTI assets.

## Web Architecture Options

| Architecture | Compute location | Pros | Cons |
|---|---|---|---|
| Backend service | Python server, e.g. FastAPI worker | deterministic, fast, easy to cache, easy to log validation reports | requires hosting and upload of large CTA/mask files |
| Pure client | TypeScript plus ITK-WASM/Pyodide/Web Worker | static deployment, no server-side patient data handling | restrictive in practice for this workload: slow large-volume compute, browser memory ceiling, difficult debugging/validation |
| Hybrid scene-bundle workflow | backend/preprocessor emits bundle; browser renders | best practical UX: heavy compute once, fast interactive viewer | two pieces to maintain |

Recommended production path:

1. Python backend or local preprocessing CLI accepts `{cta.nii.gz, mask.nii.gz}` or MEDIS contours.
2. It emits the frozen `VesselScene` bundle.
3. Browser viewer loads the bundle.
4. NiiVue renders axial CTA, CPR cross-sections, and straightened MPR NIfTI volumes.
5. Three.js renders `.glb` lumen/wall/plaque surfaces.
6. A single shared `station_index` drives all panels.

For this project, do not put heavy preprocessing in the browser. Earlier browser-compute experiments with ITK-WASM/Pyodide/Web Workers were too restrictive for large CTA/mask workflows. Keep the browser as renderer, linked-view controller, and lightweight interaction layer. Use Python, either as a local CLI or backend service, for scene-bundle generation.

Plain TypeScript feasibility:

- The viewer itself can absolutely be plain TypeScript: NiiVue for NIfTI/CPR volumes, Three.js for `.glb` surfaces, a small state store for `station_index`, and JSON loaders for centerline/quant/validation.
- Light geometry can also be TypeScript: drawing overlays, interpolating along a precomputed centerline, changing MPR angle if the CPR-long volume is already present, and loading/slicing precomputed label maps.
- Heavy preprocessing should stay out of the browser. Marching cubes, distance transforms, FMM, Frangi vesselness, and large-volume resampling are technically possible with ITK-WASM/Pyodide/Web Workers, but previous tests were restrictive enough that they should not be the planned path.
- Production direction: Python local CLI/backend creates the scene bundle; the app frontend remains TypeScript-only.

Minimal frontend API contract:

```ts
type Vec3 = [number, number, number];

interface VesselScene {
  manifest: VesselSceneManifest;
  centerline: CenterlineFrame;
  validation?: ValidationReport;
}

interface SceneViewer {
  loadScene(zipUrlOrFile: string | File): Promise<VesselScene>;
  setStation(stationIndex: number): void;
  setMprAngle(thetaDeg: number): void;
  setWindowLevel(wMinHU: number, wMaxHU: number): void;
  getHUAt(worldLpsMm: Vec3): number | null;
  on(
    event: "stationChanged" | "angleChanged" | "windowLevelChanged",
    cb: (state: { stationIndex: number; thetaDeg: number }) => void
  ): () => void;
}
```

The concrete TypeScript types should be generated from the JSON Schemas or kept mechanically aligned with them. The central viewer state is still one `stationIndex`: cross-section slice, MPR cursor, 3D highlight, and nearest axial CTA slice all derive from that integer.

## Validation Report Targets

For every vessel/viewer export, produce a small machine-readable validation summary:

- CT series UID, reconstruction kernel, spacing, origin, direction.
- Vessel name, source type, contour/mask counts.
- Mask topology class: annulus, solid, disconnected, branched, or rejected.
- Mask/CTA alignment error or resampling transform.
- Centerline length and number of stations.
- Frame unit-length, orthogonality, and handedness errors.
- Fraction of centerline stations inside the source CT volume.
- Fraction of centerline stations inside the mask or filled vessel volume.
- Minimum and percentile distance-to-mask-boundary along the centerline.
- Surface watertightness, component count, and vertex/triangle counts before and after decimation.
- MEDIS ring-to-station distance statistics.
- Interpolation mode for CT intensities and masks.
- Axial display convention used in screenshots.
- Git commit or archive hash of the code.
- Algorithm versions: centerline method, smoothing parameters, RMF method, CPR spacing, interpolation order.
- Window/level, display interpolation, and screenshot timestamp.

## Worked Example: `01-BER-0088` LAD

This prototype case is the reference example for the current bundle contract.

Inputs:

- Patient/vessel: `01-BER-0088`, `LAD`.
- Source type: MEDIS expert contours plus CTA.
- MEDIS contours: `339` lumen rings and `339` vessel-wall rings.
- CTA: `512 x 512 x 512` voxels, spacing approximately `0.39 x 0.39 x 0.25 mm`.
- Axial orientation: dcm2niix output with direction matrix `(1,0,0; 0,-1,0; 0,0,1)`, so display code must handle the Y flip explicitly.

Generated geometry:

- Centerline length: `177.97 mm`.
- Stations: `710` at `0.25 mm` target spacing.
- Frame method: `double_reflection_wang2008`.
- CPR volumes:
  - `cpr/cross_volume.nii.gz`;
  - `cpr/long_volume.nii.gz`;
  - `cpr/frame.json` duplicate frame for standalone use.
- Surfaces:
  - lumen: `21,698` vertices, `43,392` triangles, watertight;
  - wall: `21,698` vertices, `43,392` triangles, watertight.
- Bundle: `data/vessel_scene_01-BER-0088_LAD.zip`, approximately `33 MB`.

Validation snapshot:

| Check | Value | Interpretation |
|---|---:|---|
| `frame.epsilon_unit` | `3.96e-10` | pass |
| `frame.epsilon_perp` | `1.67e-16` | pass |
| `frame.det_min` | `0.999999999` | pass |
| `centerline.coverage` | `1.0` | pass |
| `medis.rho_max_mm` | `3.38 mm` | viz-tier pass, quant caution |
| `medis.rho_max_p95_mm` | `0.81 mm` | review-tier pass |
| `surface.lumen.nonmanifold_edges` | `0` | pass |
| `surface.wall.nonmanifold_edges` | `0` | pass |
| `twist_drift_deg` | `0.0 deg` | pass for double-reflection scene |
| projection-vs-double diagnostic | `18.6 deg` | confirms why projection RMF should not be default |

Schema validation:

```bash
python code/validate_bundle_schemas.py data/vessel_scene_01-BER-0088_LAD.zip
```

Expected result: `manifest.json`, `centerline.json`, `cpr/frame.json`, quantitative placeholders, `validation.json`, and `overlays/medis_rings.json` all pass their schemas.

## Concrete Test Plan

Every implementation should include small synthetic phantoms plus the real LAD case. The synthetic tests protect the geometry and orientation math; the LAD test protects the real-world export path.

| Phantom | Geometry | What it tests | Pass criterion |
|---|---|---|---|
| P1 straight cylinder | lumen radius `2 mm`, wall radius `3 mm`, length `50 mm` | world/voxel round-trip, constant area, surface extraction | lumen area variation `< 1%` |
| P2 circular arc | radius of curvature `30 mm`, `90 deg` sweep | curved centerline, RMF propagation, CPR sampling | centerline and CPR coordinate error `< 0.1 mm` |
| P3 anisotropic spacing | spacing `0.3 x 0.3 x 1.0 mm` | anisotropic affine handling | round-trip physical error `< 1e-9 mm` |
| P4 non-identity direction | include LAS-style Y flip and/or oblique direction matrix | regression test for the original all-zero CPR bug | sampled tube intensity nonzero and bbox aligned |
| P5 branched mask | Y-shaped tube with one target branch and one distractor branch | branch selection, endpoint seeds, FMM/skeleton fallback | selected branch matches seed path |
| P6 real LAD | `01-BER-0088` LAD MEDIS + CTA | end-to-end scene export and validation | schema pass; validation at least viz tier; surfaces watertight |

Every pull request touching coordinate transforms, CPR sampling, frame computation, or mask handling should rerun at least P4 and P6.

## Future Implementation Plan

1. Refactor current scripts into reusable modules:
   - `io.py`
   - `centerline.py`
   - `frame.py`
   - `cpr.py`
   - `surfaces.py`
   - `viewer.py`

2. Add a structured vessel model:
   - implement the `VesselScene` schema;
   - patient id and vessel name;
   - source type: MEDIS, mask, or hybrid;
   - centerline and RMF frame;
   - lumen, wall, and optional plaque surfaces;
   - labels and CPR-space overlays;
   - quantitative metrics;
   - provenance metadata.

3. Add the concrete phantom tests listed above, starting with P4 and P6 as regression guards.

4. Build scene-bundle export:
   - `manifest.json`;
   - NIfTI CPR volumes;
   - `.glb` surfaces;
   - overlay JSON;
   - quantitative JSON/CSV;
   - validation report;
   - preview PNG.

5. Build an interactive viewer:
   - NiiVue for NIfTI volumes and slices,
   - Three.js for `.glb` 3D surfaces,
   - linked station slider,
   - angle slider for straightened MPR.

6. Add export modes:
   - single presentation slide,
   - appendix figures,
   - interactive HTML,
   - small validation report.

7. Optional later: CTA-only interactive segmentation:
   - endpoint-click UI;
   - vesselness/FMM centerline extraction;
   - polar dynamic-programming lumen/wall segmentation;
   - centerline refinement from lumen centroids;
   - export as the same `VesselScene` contract.

## Open Decisions

- Whether clinical display should default to linear CT reformat or nearest-neighbor debug view.
- Whether straightened MPR contour lines should be exact plane intersections or projection envelopes.
- How vendor plaque-mask labels encode lumen, wall, and plaque classes.
- Whether the viewer should support multiple vessels simultaneously or one vessel per scene.
- Whether 4-D / gated CT support is in scope.
- Whether hover readout should include HU, physical coordinates, station index, and plaque label.
- Whether the default axial display convention should be radiological or neurological, and how this is labelled in exports.
- Whether bifurcations are handled natively or represented as one selected branch per scene.
- Whether users can edit the centerline with 3D handles or only provide endpoint seeds.
- Whether scene bundles embed the full CTA or reference it externally to reduce file size.
- Whether production compute is a local Python CLI, FastAPI plus worker/cache, or serverless batch. Browser-only ITK-WASM/Pyodide is not the preferred path for heavy preprocessing.
- Whether `.glb` surfaces should store wall-thickness/plaque-class colors directly or reference separate scalar arrays.
- Whether CTA-only endpoint-based segmentation belongs in the first app version or remains a research/fallback module.

## References

::: {#refs}
:::
