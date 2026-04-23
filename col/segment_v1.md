---
title: "Segmentation Reference for CT-FFR Geometry Development"
subtitle: "Coronary Lumen, Outer Wall, and Myocardium in DISCHARGE"
author: "Steffen Lukas <steffen.lukas@charite.de>"
date: "11 March 2026"
version: "1.0"
status: "Technical reference"
bibliography: ../references.bib
csl: ../vancouver-superscript.csl
reference-section-title: References
documentclass: article
geometry:
  - top=2.5cm
  - bottom=1.5cm
  - left=2.5cm
  - right=2.0cm
fontsize: 11pt
linestretch: 1.2
numbersections: true
toc: true
toc-depth: 2
header-includes: |
  \usepackage{booktabs}
  \usepackage{fontspec}
  \usepackage{amsmath}
  \usepackage{amssymb}
  \usepackage{tabularx}
  \usepackage{fancyhdr}
  \IfFontExistsTF{Arial}{\newfontfamily\headerfont{Arial}}{\newfontfamily\headerfont{Arimo}}
  \setlength{\headheight}{14pt}
  \pagestyle{fancy}
  \fancyhf{}
  \fancyhead[L]{\headerfont\fontsize{9}{11}\selectfont Segmentation Reference for CT-FFR Geometry Development}
  \fancyhead[R]{\headerfont\fontsize{9}{11}\selectfont \thepage}
  \renewcommand{\headrulewidth}{0pt}
  \renewcommand{\footrulewidth}{0pt}
  \makeatletter\let\ps@plain\ps@fancy\makeatother
---

# Abstract

This document is a technical segmentation reference for the DISCHARGE CT-FFR development track described in `manuscript_v14.md` and `proposal_v11.md`. It defines the flow-ready geometric outputs needed for reduced-order CT-FFR computation: continuous coronary lumen geometry, locally trusted outer-wall information where Glagov-constrained reference reconstruction is supportable, and myocardium segmentation for mass-based flow allocation. It also specifies the mathematical formulation of each segmentation task, minimum viable output contracts, quality-control criteria, and a staged workflow for the Berlin geometry-group collaboration. It is an internal technical reference rather than a deployment specification or a funding proposal.

# Purpose

This reference serves as a technical briefing for a Berlin geometry-group collaboration on how the coronary segmentation problem should be formulated mathematically for CT-FFR work.

It is **not**:

- a deployment architecture document;
- a browser-platform specification;
- a separate funding proposal.

Its purpose is narrower: define what segmentation outputs are actually required for reduced-order CT-FFR development, what inputs already exist, which methods are realistic, and which claims should remain conservative.

# Why Segmentation Matters Here

The current CT-FFR project needs segmentation for three distinct but linked tasks:

1. **Coronary lumen geometry** for the observed flow path and lumen-based pressure-drop terms.
2. **Coronary outer wall / vessel wall geometry** for Glagov-constrained reference reconstruction in analyzable segments.
3. **Myocardium segmentation** for LV mass estimation and mass-based flow allocation.

The segmentation target is therefore **flow-ready geometry**, not generic image annotation. In this document, **flow-ready** means that the export contains a continuous analyzable single-branch lumen path, an interpretable MLA neighborhood, sufficient proximal and distal span for the reduced-order pressure-drop calculation, an explicit reference-mode decision, and a QC state that makes CT-FFR eligibility computable rather than subjective.

Unless stated otherwise, **vessel** and **branch** are used interchangeably below to mean one analyzed edge of the coronary graph.

## Working glossary

- **flow-ready**: shorthand for the detailed inline definition above; an export state in which the vessel provides the geometric and QC variables required for stage-1 CT-FFR evaluation, with formal analyzability rules stated later in the QC and export sections;
- **vessel / branch**: one analyzed edge of the coronary graph, typically one proximal-to-distal path segment between graph nodes;
- **contour**: a generic closed boundary curve in one cross-section;
- **ring**: the ordered sampled polygon points representing one contour on one slice;
- **cross-section**: the orthogonal slice plane together with its derived contour(s), centroid, and area measurements;
- **trusted interval**: a contiguous run of slices over which outer-wall geometry passes local QC and may be used for Glagov-style reference reconstruction; formal stage-1 conditions are stated later under Coronary-Specific Strategy and QC;
- **bifurcation neighborhood**: a graph-distance neighborhood around a branch takeoff where the single-tube assumption is weakened and routine single-lumen measurements may be excluded.

## Minimum viable outputs

| Target | Role in CT-FFR | Minimum viable output | Preferred source | Fallback |
|--------|----------------|-----------------------|------------------|----------|
| **Coronary lumen** | Viscous term and MLA definition | Continuous centerline, ordered cross-sections, lumen area profile | Existing Medis contours where usable; CTA-derived completion elsewhere | Lumen-envelope baseline only (reference comparator from nearby healthy lumen rather than outer-wall geometry) |
| **Coronary outer wall** | Glagov reference reconstruction | Outer-wall contour around lesion and reference segments with local continuity | Existing Medis vessel-wall contours where reliable | Local reversion to lumen-envelope comparator |
| **LV myocardium** | CT-derived myocardial mass | LV myocardium mask plus raw and calibrated total LV mass fields with explicit state | Dedicated CT myocardium segmentation | Semi-automatic correction or alternate validated software |

A raw CT-derived mass estimate is not yet the final quantitative input. Before it is used in the flow model, the myocardium stage should carry an explicit calibration/QC state.

## Practical target for stage 1

The immediate segmentation target is **not** a complete coronary tree in every case. For development-phase CT-FFR, the practical target is:

- one matched target vessel per case;
- continuous proximal-to-distal lumen geometry over the interrogated segment;
- outer-wall geometry over the lesion and adjacent reference span, where available and plausible;
- an LV myocardium segmentation sufficient for total mass extraction.

This is consistent with the staged cohort logic in `manuscript_v14.md`.

## Stage-1 roadmap in one page

For newcomers, the practical order of operations is:

| Step | Primary object | Immediate question | Exit condition |
|------|----------------|--------------------|----------------|
| **1. Inventory** | Medis exports, CTA volumes, metadata | What geometry already exists and what is missing? | matched cases with standardized coordinate conventions plus contrast-series and reconstruction-phase metadata |
| **2. Lumen stabilization** | centerline and lumen area profile | Is there a continuous target-vessel lumen path with stable MLA? | lumen-core QC pass |
| **3. Outer-wall decision** | local nested wall geometry | Is the wall reliable enough to support Glagov reference reconstruction? | either a trusted interval meeting the Level-0 wall-use conditions in Coronary-Specific Strategy or explicit lumen-envelope fallback |
| **4. Myocardium mass** | LV myocardium domain | Is LV mass available in an explicit export state, and is it primary-usable or only sensitivity-grade? | `lv_mass_state` set to one of `raw_ct`, `prior_slope`, `calibrated`, `manually_corrected`, `provisional`, or `missing` |
| **5. Export and CT-FFR eligibility** | fixed vessel schema | Which branches of the 2×2 model family are actually allowed for this case? | `eligible_models` emitted together with QC flags |

This is the shortest operational summary of the document. Everything else specifies how each exit condition should be computed.

For this reference, the canonical LV-mass export states are:

- `raw_ct`: raw mass extracted, but no calibration has yet been applied;
- `prior_slope`: interim slope-only calibration applied from a pre-locked prior; sensitivity-only, not primary-ready;
- `calibrated`: paired-cohort calibration is locked and applied;
- `manually_corrected`: calibrated mass after recorded manual mask correction;
- `provisional`: a temporary estimate exists, but QC and/or calibration status is not locked for quantitative flow use;
- `missing`: no usable LV-mass export is available.

# Formal Interface to the CT-FFR Model

For implementers, the key point is that the segmentation stage is not judged by generic mask quality alone. It is judged by whether it supplies the geometric state variables consumed by the reduced-order CT-FFR model in `manuscript_v14.md`.

## Shared notation

This document uses the same core symbols as `manuscript_v14.md` and `proposal_v11.md`, with indexed discrete forms where appropriate:

| Continuous symbol | Discrete symbol | Meaning |
|-------------------|-----------------|---------|
| $M_{\text{CT}}$ | $M_{\text{CT}}$ | raw CT-derived LV myocardial mass before calibration |
| $A_{\text{lum}}(s)$ | $A_{\text{lum},i}$ | observed lumen cross-sectional area |
| $A_{\text{outer}}(s)$ | $A_{\text{outer},i}$ | outer-wall cross-sectional area where available |
| $A_{\text{ref}}(s)$ | $A_{\text{ref},i}$ | reconstructed local reference area, either lumen-envelope or Glagov-based |
| $s$ | $s_i$ | proximal-to-distal vessel arc length |
| $M_{\text{cal}}$ | $M_{\text{cal}}$ | calibrated CT-derived LV myocardial mass entering the flow model |
| $M_{\text{ref,cal}}$ | $M_{\text{ref,cal}}$ | reference calibrated LV myocardial mass used to normalize the allometric sensitivity model (primary anchor 250 g; defined in the flow-model sensitivity branch) |
| $f_v$ | $f_v$ | vessel territory fraction |
| $q_{\text{rest}}$ | $q_{\text{rest}}$ | resting perfusion per gram |
| $H$ | $H$ | hyperemic multiplier |
| $\rho_{\text{myo}}$ | $\rho_{\text{myo}}$ | adopted myocardial tissue density; stage-1 default $1.05$ g/mL |

## Required vessel representation

For each analyzable vessel, the segmentation output should be converted into an ordered sequence

$$
\{(\mathbf{c}_i, s_i, A_{\text{lum},i}, A_{\text{outer},i})\}_{i=0}^{N}
$$

where:

- $\mathbf{c}_i \in \mathbb{R}^3$ is the centerline point in physical coordinates;
- $s_i$ is cumulative arc length;
- $A_{\text{lum},i}$ is the lumen cross-sectional area;
- $A_{\text{outer},i}$ is the outer-wall cross-sectional area when available.

The arc-length coordinate is defined discretely by

$$
s_0 = 0, \qquad
s_i = s_{i-1} + \lVert \mathbf{c}_i - \mathbf{c}_{i-1} \rVert_2.
$$

The minimum-lumen-area site is then

$$
i_{\text{MLA}} = \arg\min_i A_{\text{lum},i},
\qquad
A_{\text{MLA}} = A_{\text{lum},i_{\text{MLA}}}.
$$

If outer-wall data are available, equivalent radii are defined by

$$
r_{\text{lum},i} = \sqrt{\frac{A_{\text{lum},i}}{\pi}},
\qquad
r_{\text{outer},i} = \sqrt{\frac{A_{\text{outer},i}}{\pi}}.
$$

These are the inputs used by the Glagov reconstruction in `manuscript_v14.md`.

## Discrete hemodynamic handoff

The lumen segmentation feeds the viscous term through the discrete resistance integral

$$
\Delta P_{\text{visc}}
\approx
K_v \mu Q
\sum_{i=0}^{N-1}
\frac{\Delta s_i}{\bar{A}_{\text{lum},i}^2},
\qquad
\bar{A}_{\text{lum},i} = \frac{A_{\text{lum},i} + A_{\text{lum},i+1}}{2}.
$$

For stage 1, this resistance integral should be evaluated only on the exported single-lumen branch path after unresolved bifurcation neighborhoods and other non-analyzable intervals have been excluded. If that exclusion would sever the target span or overlap the MLA neighborhood materially, the vessel should be rejected rather than repaired with an ad hoc branching correction.

The outer-wall segmentation, when usable, feeds the Glagov reconstruction through

$$
r_{\text{ref,G},i}
=
\max\!\left(r_{\text{outer},i} - T_{\text{healthy}},\; 1.05\,r_{\text{lum},i}\right),
\qquad
A_{\text{ref,G},i} = \pi r_{\text{ref,G},i}^2.
$$

Here $T_{\text{healthy}}$ is a single vessel-level scalar estimate applied uniformly along the analyzed span rather than a separate profile $T(s_i)$.

The contraction term then depends on

$$
A_{\text{ref,MLA}} = A_{\text{ref,G},i_{\text{MLA}}}
\quad
\text{or}
\quad
A_{\text{ref,L},i_{\text{MLA}}},
$$

depending on whether the vessel is running in Glagov or lumen-envelope mode.

This interface has an immediate practical consequence: segmentation error near small lumen areas matters disproportionately because the viscous contribution scales with $1/A^2$ and the contraction term is anchored at the MLA. A visually acceptable mask can therefore still be unacceptable for CT-FFR if it underestimates lumen area near the throat or truncates the distal path.

## Required myocardium representation

The myocardium stage must provide a binary LV myocardium mask

$$
m(\mathbf{x}) \in \{0,1\}
$$

from which CT-derived myocardial volume and mass are computed:

$$
V_{\text{myo}} = \sum_{\mathbf{x}} m(\mathbf{x}) \, \Delta V_{\text{vox}},
\qquad
M_{\text{CT}} = \rho_{\text{myo}} V_{\text{myo}}.
$$

Here $\Delta V_{\text{vox}}$ is the voxel volume and $\rho_{\text{myo}}$ is the adopted myocardial density in g/mL. For the flow model, the operational output is not raw $M_{\text{CT}}$ but a calibrated mass estimate

$$
M_{\text{cal}} = a + b \, M_{\text{CT}},
$$

where $(a,b)$ are to be estimated from a paired CT-CMR subset using the calibration procedure specified later. The vessel-demand model then uses either

$$
M_v = f_v M_{\text{cal}}
$$

or a future territory-specific map if such a map is later introduced.

If a paired calibration subset is not yet finalized on the active cohort, an interim slope-only prior may still be applied for sensitivity work, but that output should be exported as `prior_slope` rather than `calibrated`. Operationally, the stage-1 default is a cohort-wide zero-intercept slope-only Deming calibration $M_{\text{cal}} = b M_{\text{CT}}$ unless the paired subset shows a clear, clinically material intercept large enough to justify freeing $a$; sex-specific calibration maps may be examined as sensitivity analyses, but they are not required for the primary export contract. For the allometric sensitivity branch, the primary anchor is fixed at $M_{\text{ref,cal}} = 250$ g so that $M_{\text{ref},v} = f_v M_{\text{ref,cal}}$; sex-specific normative masses remain plausibility and sensitivity context rather than the default denominator.

# Current Data Reality

## What already exists

The project starts from useful but incomplete segmentation assets:

- partial Medis QAngio CT vessel exports [@medis2024; @reiber2010];
- lumen and vessel-wall contour rings in physical coordinates;
- some repeat-reader or dual-reader material for reproducibility work [@deknegt2018];
- native CTA volumes suitable for further processing.

## What does not yet exist

The following should **not** be assumed:

- a harmonized full-tree coronary segmentation dataset across all DISCHARGE cases;
- uniform outer-wall quality in calcified or noisy vessels;
- direct one-click export of flow-ready centerlines, lumen profiles, and outer-wall profiles for the full cohort;
- a complete myocardium segmentation pipeline already validated on the exact DISCHARGE workflow.

## Medis-specific value

The Medis exports remain highly valuable because they provide:

- direct contour-level lumen and vessel-wall geometry in at least part of the cohort;
- seed data for target-vessel QC;
- a reference set for comparing classical CTA completion against existing expert contours;
- a practical starting point for straightened-MPR review, contour plausibility checks, and mesh reconstruction.

They should be framed as **partial seed segmentations**, not as proof of end-to-end flow-readiness.

# Technical Geometry Representation

## Geometric reconstruction problem statement

Before establishing conventions, it is useful to state what problem the segmentation pipeline is actually solving. Three geometric inverse problems are coupled:

**Problem 1 (Lumen geometry):** Given CTA intensities $I: \mathbb{R}^3 \to \mathbb{R}$, recover a topology-preserving tubular surface $S_\text{lum}$ together with its embedded centerline $\gamma: [0,L] \to \mathbb{R}^3$ such that, for each arc-length parameter $s$, the cross-sectional area $A_\text{lum}(s) = \text{area}(S_\text{lum} \cap \Pi_s)$ provides a stable, QC-validated scalar profile for hemodynamic integration. The lumen problem has a unique correct answer (up to imaging resolution) and the uncertainty is measurement noise, not model choice.

**Problem 2 (Outer-wall geometry):** Given $I$ and $S_\text{lum}$, recover an outer-wall surface $S_\text{outer} \supset S_\text{lum}$ — i.e. a strictly enclosing nested tube — such that the local wall thickness $T(s) = r_\text{outer}(s) - r_\text{lum}(s)$ is physiologically plausible and stable enough to support Glagov reference reconstruction. This problem is **harder** than Problem 1 because: (a) the outer wall is less contrast-enhanced; (b) nestedness must be enforced as a hard constraint; (c) the fallback hierarchy applies when outer-wall data quality fails.

**Problem 3 (Myocardium mass):** Given $I$, recover the LV myocardium domain $\Omega_\text{myo} \subset \mathbb{R}^3$ such that the calibrated CT-derived mass $M_\text{cal} = a + b\,\rho_\text{myo} \cdot \text{vol}(\Omega_\text{myo})$ matches a paired CMR reference to within a pre-specified tolerance, with $a = 0$ as the stage-1 default unless the paired calibration subset justifies an intercept.

The coupling between these three problems is strictly one-directional in stage 1: Problem 1 $\to$ Problem 2 $\to$ Problem 3 $\to$ hemodynamic export. Each problem's output feeds the next as a fixed constraint, not a joint optimization variable. The detailed joint formulation is developed in the "Coupled geometric inverse-problem formulation" section below; the conventions here supply the mathematical infrastructure to express it.

## Coordinate conventions

Every segmentation route should end in the same physical coordinate system:

- all exported points stored in DICOM patient `LPS` coordinates, with image orientation / direction cosines applied before any cross-tool comparison;
- image intensities sampled in millimeters, not voxel indices;
- all cross-sections orthogonal to the current centerline tangent;
- proximal-to-distal ordering fixed before any area profile is exported.

If any upstream tool emits `RAS` coordinates, the conversion to `LPS` should happen once at ingest and not be deferred downstream. The metadata handoff should also retain the contrast series / phase and the CTA reconstruction phase used for segmentation, for example an R-R percentage or vendor phase label, because phase mismatch or inadequate gating is a common cause of apparent motion blur in the lumen and outer-wall tasks.

This matters because CT-FFR uses geometric integrals along arc length rather than unordered slice collections.

## Reconstruction-phase and motion-stability guidance

Coronary CTA segmentation is phase-sensitive. In many routine coronary CTA studies, the most motion-stable reconstruction lies in mid-to-late diastole, often around **65-75\% of the R-R interval**, but the correct choice remains vessel- and case-specific.

For stage-1 work:

- retain the series label and reconstruction phase with every vessel export;
- if multiple phases are available, prefer the phase whose lesion and MLA neighborhood is sharpest on quick curved-MPR review rather than assuming one globally best phase;
- if the target vessel remains motion-unstable at the MLA or over the lesion-reference span in all available phases, fail lumen analyzability rather than averaging across phases or silently accepting blur.

## Contours as polygons

Whether contours come from Medis or from CTA completion, each cross-section should be represented as an ordered polygon

$$
\mathcal{P}_i = \{\mathbf{p}_{i,j}\}_{j=1}^{M_i}
$$

in the local slice plane. Once projected to 2D coordinates $(x_{i,j}, y_{i,j})$, area is computed by the shoelace formula

$$
A_i
=
\frac{1}{2}
\left|
\sum_{j=1}^{M_i}
\left(
x_{i,j} y_{i,j+1} - x_{i,j+1} y_{i,j}
\right)
\right|,
$$

with cyclic indexing in $j$.

The local polygon centroid can be used for centerline refinement. In continuous form,

$$
\mathbf{c}_i =
\frac{1}{A_i}
\int_{\Omega_i} \mathbf{x} \, dA,
$$

and in practice is approximated from the polygon vertices or mask moments.

## Centerline frame and cross-sectional planes

Given ordered centerline points $\mathbf{c}_i$, define a tangent

$$
\mathbf{t}_i =
\frac{\mathbf{c}_{i+1} - \mathbf{c}_{i-1}}
{\lVert \mathbf{c}_{i+1} - \mathbf{c}_{i-1} \rVert_2}
$$

for interior points, with one-sided differences at the ends. A local orthonormal frame $(\mathbf{t}_i, \mathbf{n}_i, \mathbf{b}_i)$ then defines the cross-sectional plane

$$
\mathbf{x}_i(u,v)
=
\mathbf{c}_i + u \mathbf{n}_i + v \mathbf{b}_i.
$$

All contour extraction should be performed in this plane, not in fixed axial/coronal/sagittal slices, because lumen and wall geometry must be sampled perpendicular to the flow path. The implementation rule for stable frame transport is stated below under **Frenet-Serret frame and orthogonal slicing**: use a rotation-minimizing Bishop / parallel-transport frame for numerical slice orientation.

## Polar representation

For contour search, the local cross-section image can be reparameterized in polar coordinates:

$$
I_i(r,\theta) =
I\!\left(
\mathbf{c}_i
+
r \cos\theta \, \mathbf{n}_i
+
r \sin\theta \, \mathbf{b}_i
\right).
$$

This representation is useful because a closed lumen or outer-wall contour becomes a single-valued radial function $r(\theta)$, which is convenient for dynamic programming and for enforcing nested-contour constraints.

# Segmentation as a Geometric Reconstruction Problem

The most accurate high-level description is that coronary segmentation here is not mainly a "mask prediction" task. It is a **geometric reconstruction problem**. From CTA intensities and partial contour priors, the pipeline must recover:

1. an embedded vessel graph;
2. a set of centerline curves;
3. nested lumen and outer-wall tube surfaces along those curves;
4. bifurcation-node geometry;
5. a scalar myocardial mass quantity coupled to the vessel graph through territory assignment.

This framing is closer to the actual mathematical object needed by CT-FFR than a semantic-label view of the problem.

## Vessel tree as an embedded graph

Let the coronary tree be represented as a graph

$$
\mathcal{G} = (\mathcal{V}, \mathcal{E}),
$$

where:

- $\mathcal{V}$ are graph nodes, representing ostia, bifurcations, and terminal endpoints;
- $\mathcal{E}$ are vessel edges, representing individual branch segments between nodes.

Each edge $e \in \mathcal{E}$ is an embedded spatial curve

$$
\gamma_e : [0,L_e] \to \mathbb{R}^3,
$$

parameterized by arc length $s \in [0,L_e]$. In this language, the core lumen problem is: recover $\mathcal{G}$ and $\gamma_e(s)$ robustly from image data. The outer-wall problem is: recover an additional nested surface field attached to the same embedded graph. This graph view is standard in vascular image-based modeling and is more faithful to coronary anatomy than treating the vessel tree as an unordered voxel set [@antiga2008].

## Curve geometry of a vessel branch

For an arc-length-parameterized centerline $\gamma(s)$, the local tangent is

$$
\mathbf{T}(s) = \frac{d\gamma}{ds}.
$$

Curvature is

$$
\kappa(s) = \left\lVert \frac{d\mathbf{T}}{ds} \right\rVert,
$$

and for a general parameter $t$,

$$
\kappa(t)
=
\frac{\lVert \gamma'(t) \times \gamma''(t) \rVert}
{\lVert \gamma'(t) \rVert^3}.
$$

Torsion is

$$
\tau(t)
=
\frac{(\gamma'(t) \times \gamma''(t)) \cdot \gamma'''(t)}
{\lVert \gamma'(t) \times \gamma''(t) \rVert^2}.
$$

This Frenet-Serret torsion is undefined when $\kappa = 0$. In practical descriptor computation it should therefore be evaluated only where curvature exceeds a small numerical threshold, i.e. $\kappa > \varepsilon$, rather than on nearly straight or degenerate segments. A practical stage-1 default is $\varepsilon = 0.01 \;\text{mm}^{-1}$, exposed as a configurable parameter rather than hard-coded.

These quantities matter operationally:

- high curvature makes cross-sectional plane placement more sensitive to centerline noise;
- high torsion means the local vessel frame twists rapidly in 3D, which affects slice reformatting;
- abrupt non-physiologic curvature spikes are often segmentation artifacts rather than anatomy.

Coronary curvature is not merely a theoretical descriptor. It has been measured directly from reconstructed coronary axes and linked to the dynamic coronary geometry seen in angiographic and CT-based analyses [@gross1998; @zhu2009geometry; @prado2023geometry].

## Coupled geometric inverse-problem formulation

For collaboration with a geometry group, the strongest framing is not that the project contains three segmentation masks. The stronger framing is that it contains three **coupled geometric inverse problems** whose outputs happen to be representable as masks or contours.

Just as importantly, this section is **conceptual rather than prescriptive software design**. Stage-1 implementation does **not** solve one monolithic optimization over all geometric components simultaneously. It solves a staged pipeline with explicit handoffs:

1. infer the coronary graph and centerline path;
2. derive lumen contours and area profiles on orthogonal slices;
3. decide whether outer-wall information supports Level-0 Glagov use, fallback reference support, or lumen-envelope reversion;
4. derive and calibrate LV myocardium mass;
5. apply hemodynamic QC and emit the flow-ready export.

The joint notation below is therefore a compact way to describe dependency structure, not a claim that the codebase will implement one global optimizer.

Let the latent geometric state be

$$
\mathcal{X}
=
\Big(
\mathcal{G},
\{\gamma_e\}_{e \in \mathcal{E}},
\{S_{\text{lum},e}\}_{e \in \mathcal{E}},
\{S_{\text{outer},e}\}_{e \in \mathcal{E}},
\Omega_{\text{myo}},
\Phi_{\text{terr}}
\Big),
$$

where:

- $\mathcal{G}$ is the embedded coronary graph;
- $\gamma_e$ are branch centerlines;
- $S_{\text{lum},e}$ are lumen surfaces;
- $S_{\text{outer},e}$ are outer-wall surfaces;
- $\Omega_{\text{myo}} \subset \mathbb{R}^3$ is the LV myocardium domain;
- $\Phi_{\text{terr}}$ is a current or future map from myocardium to vessel territories.

In the present project, this latent-state definition is mainly **relational** rather than algorithmically literal. It specifies the coupled objects that the CT-FFR model depends on and makes their interactions explicit for collaboration.

Then the segmentation problem can be stated abstractly as

$$
\widehat{\mathcal{X}}
=
\arg\min_{\mathcal{X} \in \mathcal{A}}
\Big[
D(I,\mathcal{X})
+
\lambda_{\text{topo}} R_{\text{topo}}(\mathcal{G},\gamma)
+
\lambda_{\text{nest}} R_{\text{nest}}(S_{\text{lum}},S_{\text{outer}})
+
\lambda_{\text{mass}} R_{\text{mass}}(\Omega_{\text{myo}})
\Big],
$$

where $I$ denotes the CTA intensities and $\mathcal{A}$ is the admissible set of anatomically plausible geometric states. In practice, the stage-1 pipeline optimizes the image, topology, nesting, and mass-stability terms sequentially or in local subproblems; the hemodynamic relevance enters mainly **after** geometric candidates have been constructed, as a post-hoc sensitivity and QC weighting. Read the equation as a compact summary of the coupled constraints, not as the literal stage-1 implementation plan.

At minimum, the admissible set $\mathcal{A}$ should enforce:

- graph connectivity to the ostia and physiologic branch topology;
- positivity of lumen and outer-wall radii;
- nestedness $r_{\text{outer}} \ge r_{\text{lum}} + \delta_{\text{nest}}$ for a small non-crossing barrier $\delta_{\text{nest}} > 0$;
- absence of obvious self-intersection or branch-order inconsistency;
- plausible diameter, taper, and length scales for coronary branches;
- a bounded LV myocardium domain with controlled basal and apical truncation;
- a territory representation $\Phi_{\text{terr}}$ consistent with the currently available stage of the model.

In this decomposition:

- $D$ is an image-fidelity term;
- $R_{\text{topo}}$ enforces graph continuity and branch consistency;
- $R_{\text{nest}}$ enforces lumen/outer-wall nesting and surface regularity;
- $R_{\text{mass}}$ enforces mass-stable myocardium geometry;
- the $\lambda$ coefficients are not only regularization strengths, but also practical unit-conversion weights because the component terms live in different physical or abstract units.

The hemodynamic weighting term is more honestly written as a separate functional

$$
R_{\text{hemo}}^{\text{post}}(\mathcal{X}),
$$

which is evaluated after candidate geometries are available. It is used to rank geometric perturbations by their downstream effect on quantities such as MLA, $\sum \Delta s_i/\bar{A}_i^2$, $A_{\text{ref,MLA}}$, and final CT-FFR. In other words, it is a **QC and sensitivity-analysis term**, not a stage-1 regularizer active during every upstream optimization step.

Likewise, $\Phi_{\text{terr}}$ should not be interpreted as a stage-1 free optimization variable. In the present model it is determined analytically:

- **stage 1**: by dominance-adjusted territory fractions $f_v$ so that $M_v = f_v M_{\text{cal}}$;
- **later stages**: by an explicit graph-to-domain assignment rule derived from $\mathcal{G}$ and $\Omega_{\text{myo}}$, for example a geodesic or graph-Voronoi construction.

This is the main reason a geometry team is relevant here. The project is not asking only for class labels; it is asking for reconstruction of a multilayer geometric state under image, topology, surface, and flow-relevance constraints. Recent coronary methods are increasingly explicit about graph structure, topology preservation, and geometry-hemodynamics coupling rather than treating the vessel tree as a simple voxel object [@hampe2024; @qiu2025; @zhang2024curvature; @garcha2025].

## Three tasks as coupled geometric layers

Operationally, the latent state above decomposes into three coupled layers:

- **supply path**: coronary graph, centerline curves, and lumen area field;
- **reference/remodeling layer**: nested outer-wall geometry sufficient for local Glagov-style reference reconstruction;
- **demand layer**: calibrated myocardial domain and, later, territory assignment.

This is the implementation-facing view of the same state $\mathcal{X}$ rather than a second mathematical model. The downstream quantities that matter are still $A_{\text{lum}}(s)$, $A_{\text{ref,MLA}}$, and $M_{\text{cal}}$, but the layered phrasing is often the clearer bridge from the abstract inverse problem to concrete algorithm design.

## Lumen as a topology-preserving curve-and-tube problem

For each vessel edge $e \in \mathcal{E}$, the centerline is an embedded curve

$$
\gamma_e : [0,L_e] \to \mathbb{R}^3,
$$

and the lumen surface is a tube field around that curve:

$$
S_{\text{lum},e}(s,\theta)
=
\gamma_e(s)
+
r_{\text{lum},e}(s,\theta)
\big(
\cos\theta\,\mathbf{N}(s) + \sin\theta\,\mathbf{B}(s)
\big).
$$

The derived lumen area field, valid for star-shaped cross-sections with respect to the chosen center point, is

$$
A_{\text{lum},e}(s)
=
\frac{1}{2}
\int_0^{2\pi}
r_{\text{lum},e}(s,\theta)^2 \, d\theta.
$$

That star-shaped assumption is usually a reasonable local approximation in ordinary single-lumen segments, but it can fail near bifurcations, severe eccentricity, or off-center slice placement. The numerically preferred implementation in this project therefore remains contour extraction followed by polygon-based area computation using the shoelace formula defined earlier. The polar representation is primarily a local parameterization and optimization device, not the universal final area computation rule.

Under this formulation, the lumen task is not "predict a lumen mask". It is:

1. recover the graph topology $\mathcal{G}$;
2. recover each embedded centerline $\gamma_e$;
3. recover the cross-sectional radial field $r_{\text{lum},e}(s,\theta)$;
4. derive a stable ordered area field $A_{\text{lum}}(s)$.

This is the correct formulation for CT-FFR because the hemodynamic model consumes ordered cross-sections and arc-length samples, and the viscous term scales like

$$
\sum_i \frac{\Delta s_i}{\bar{A}_i^2},
$$

so local geometric error near small lumen areas is disproportionately important. Generic voxel overlap is therefore the wrong primary objective for this flow-resistance-specific CT-FFR use case, even though overlap metrics remain useful as supportive QC summaries. A geometry-aware lumen pipeline should prioritize topology-preserving extraction, centerline refinement, orthogonal slicing, and resistance-integral stability [@hampe2024; @qiu2025].

## Lumen and outer wall as a nested-surface problem

The outer-wall task is not "another vessel mask". It is the recovery of a second surface field that remains nested around the lumen surface on the same centerline graph:

$$
S_{\text{outer},e}(s,\theta)
=
\gamma_e(s)
+
r_{\text{outer},e}(s,\theta)
\big(
\cos\theta\,\mathbf{N}(s) + \sin\theta\,\mathbf{B}(s)
\big),
$$

subject to

$$
r_{\text{outer},e}(s,\theta)
\ge
r_{\text{lum},e}(s,\theta) + \delta_{\text{nest}}.
$$

This is a coupled inverse problem under partial observability:

- the lumen boundary is often image-visible;
- the outer wall is frequently weak, ambiguous, or corrupted by calcium and partial-volume effects;
- the two surfaces must remain nested and locally smooth;
- the output must be stable enough to support local reference reconstruction near lesions.

Here $\delta_{\text{nest}}$ is only the small mathematical or algorithmic non-crossing barrier used during reconstruction. The separate stage-1 QC threshold on observed wall margin is defined later under Coronary-Specific Strategy.

The hemodynamically relevant quantity is not a global wall Dice score. It is the stability of the local reference comparator, especially at the MLA, where

$$
g_{\text{ref}}
=
\frac{1}{A_{\text{MLA}}}
-
\frac{1}{A_{\text{ref,MLA}}}
$$

enters the contraction term. That is why outer-wall geometry should be framed as a **nested-surface reconstruction problem with biological remodeling meaning**, not just as boundary finding. In practice this naturally favors paired contour optimization, shape regularity penalties, and explicit nestedness constraints. It also creates a natural entry point for surface differential geometry, curvature regularization, and local shape-operator ideas in a geometry collaboration.

## Myocardium as a mass-stable volumetric-domain problem

For this project, the myocardium is best framed as a volumetric domain problem rather than mainly a surface problem. Let

$$
\Omega_{\text{myo}} \subset \mathbb{R}^3
$$

denote the LV myocardium domain. The stage-1 quantity of interest is not a detailed wall-mechanics description, but a stable calibrated mass:

$$
V_{\text{myo}} = |\Omega_{\text{myo}}|,
\qquad
M_{\text{CT}} = \rho_{\text{myo}} V_{\text{myo}},
\qquad
M_{\text{cal}} = a + b \, M_{\text{CT}}.
$$

The correct question is therefore not only whether the myocardium mask overlaps an expert mask, but whether clinically realistic boundary perturbations produce acceptable variation in $M_{\text{cal}}$. This is a geometric-measure problem: estimate a domain whose volume is stable under uncertainty and whose basal/apical truncation is controlled.

In a later stage, the natural geometric extension is a territory map

$$
\Phi_{\text{terr}} : \Omega_{\text{myo}} \to \mathcal{E}
\quad
\text{or to coronary territories,}
$$

which would convert the myocardium stage from a global mass problem into a graph-to-domain coupling problem. That is not required for stage 1, but it is the mathematically natural next step if the geometry group wants a deeper role in future demand modeling.

## Suggested geometry-group work packages

This framing supports a clean allocation of tasks to geometry-oriented team members:

| Work package | Latent object | Main mathematical questions | Immediate project output |
|--------------|---------------|-----------------------------|--------------------------|
| **G1. Coronary graph and centerline geometry** | $\mathcal{G}, \gamma_e$ | topology-preserving extraction, bifurcation handling, curvature/torsion regularity, graph consistency | ordered vessel graph and centerlines |
| **G2. Lumen cross-section geometry** | $r_{\text{lum}}(s,\theta), A_{\text{lum}}(s)$ | orthogonal slicing, contour regularization, taper continuity, MLA stability, resistance-integral sensitivity | flow-ready lumen area profiles |
| **G3. Nested wall geometry** | $S_{\text{lum}}, S_{\text{outer}}$ | paired-surface reconstruction, nestedness, local smoothness, lesion/reference-span plausibility | local Glagov-ready reference geometry |
| **G4. Myocardial domain and territory coupling** | $\Omega_{\text{myo}}, \Phi_{\text{terr}}$ | mass stability, boundary perturbation, future geodesic or graph-based territory assignment | calibrated LV mass now, territory mapping later |
| **G5. Uncertainty and geometric sensitivity** | perturbations of $\mathcal{X}$ | which geometric errors materially change CT-FFR, and where to spend QC effort | sensitivity-weighted QC and analyzability rules |

This table is useful administratively because it shows that geometry-group participation is not ornamental. Each work package corresponds to a mathematically distinct part of the latent state and to a concrete downstream quantity used by the CT-FFR model.

## Bridge from geometric formulation to implementation methods

The coupled inverse-problem language is useful only if it maps cleanly to actual method families. For this project, the bridge is:

- $\mathcal{G}, \gamma_e$ map to Medis centroid reconstruction, vesselness-guided minimal paths, and graph-aware bifurcation QC;
- $r_{\text{lum}}(s,\theta), A_{\text{lum}}(s)$ map to orthogonal reformatting, polar lumen search, polygon-area computation, and centroid-based centerline refinement;
- $S_{\text{outer}}$ maps to nested contour optimization plus outer-wall trust and fallback rules;
- $\Omega_{\text{myo}}$ maps to LV myocardium models, correction workflow, and calibration;
- $R_{\text{hemo}}^{\text{post}}$ maps to the analyzability gate, perturbation analysis, and reader/method agreement on MLA, resistance integral, and reference area.

So the geometric formulation is not a separate theoretical layer floating above the implementation. It is the compact statement of why the later classical, deep-learning, and QC sections look the way they do. The algorithmic specification and staged workflow below follow exactly this mapping from graph recovery to curve recovery to nested-surface recovery to myocardial mass-domain recovery.

## Differentiability requirements

Before introducing the moving frame, the required regularity of the centerline curve must be stated explicitly, as it determines what geometric quantities are well-defined.

A centerline $\gamma_e: [0, L_e] \to \mathbb{R}^3$ must be at least **$C^2$** (twice continuously differentiable in arc-length parameterization) for curvature $\kappa(s) = \lVert \gamma''(s) \rVert$ to be well-defined and continuous. $C^1$ regularity is sufficient for the tangent direction and arc length, but $C^2$ is necessary for meaningful curvature descriptors. In practice, discrete centerlines extracted from voxel images are piecewise linear ($C^0$) and require explicit smoothing to achieve working $C^2$ regularity; the smoothing procedure and its effect on local curvature and taper should be recorded as part of the QC provenance.

For the lumen and outer-wall radius fields:
- the area profile $A_\text{lum}(s)$ must be **absolutely continuous** along the vessel for the resistance integral $\sum \Delta s_i / \bar{A}_i^2$ to converge stably;
- the reference radius field used in Glagov reconstruction must be **monotone non-increasing** in the downstream direction over the analyzed span (taper assumption), **Lipschitz continuous**, and satisfy $r_\text{ref}(s) \ge (1 + \varepsilon) r_\text{lum}(s)$ for some $\varepsilon > 0$ to prevent degenerate inversions.

These regularity requirements define the admissible taper function class $\mathcal{F}_\text{taper}$:

$$
\mathcal{F}_\text{taper}
=
\bigl\{
f: [0,L] \to \mathbb{R}_{>0}
\;\big|\;
f \text{ is monotone non-increasing, Lipschitz, and } f(s) \ge (1+\varepsilon_\text{ref})\,r_\text{lum}(s)
\bigr\},
$$

with $\varepsilon_\text{ref}$ implementing the $r_\text{ref} \ge 1.05\,r_\text{lum}$ floor. This is not the empirical choice $T_\text{healthy} \in [0.40, 0.80]$ mm — it is the structural constraint class that any reference reconstruction method must satisfy to be admissible.

## Frenet-Serret frame and orthogonal slicing

Once curvature is nonzero, the local vessel geometry is described by the Frenet-Serret frame:

- $\mathbf{T}(s)$: tangent;
- $\mathbf{N}(s)$: principal normal;
- $\mathbf{B}(s)$: binormal.

The frame evolves as

$$
\frac{d\mathbf{T}}{ds} = \kappa \mathbf{N},
\qquad
\frac{d\mathbf{N}}{ds} = -\kappa \mathbf{T} + \tau \mathbf{B},
\qquad
\frac{d\mathbf{B}}{ds} = -\tau \mathbf{N}.
$$

For slice orientation and stable contour transport, the **Bishop (parallel-transport) frame** $\{\mathbf{T}, \mathbf{U}_1, \mathbf{U}_2\}$ is preferred. It satisfies the simpler ODE system:

$$
\frac{d\mathbf{T}}{ds} = \kappa_1\,\mathbf{U}_1 + \kappa_2\,\mathbf{U}_2,
\qquad
\frac{d\mathbf{U}_1}{ds} = -\kappa_1\,\mathbf{T},
\qquad
\frac{d\mathbf{U}_2}{ds} = -\kappa_2\,\mathbf{T},
$$

where $\kappa_1 = \langle \gamma'', \mathbf{U}_1 \rangle$ and $\kappa_2 = \langle \gamma'', \mathbf{U}_2 \rangle$ are the normal curvature components. Unlike the Frenet frame, the Bishop frame has no torsion term and remains well-defined and smooth through straight ($\kappa = 0$) segments; its twist accumulates globally but does not exhibit the local instabilities of the Frenet normal. The practical rule in this document is: use **Frenet** for curvature and torsion descriptors, and use **Bishop / parallel transport** for slice orientation, contour transport, and any implementation path that must remain stable through nearly straight segments.

## Arc length and tortuosity

The true vessel length is the centerline arc length

$$
L = \int \lVert \gamma'(t) \rVert \, dt.
$$

A simple tortuosity measure is

$$
\mathcal{T}_{\text{dist}} = \frac{L}{\lVert \gamma(L) - \gamma(0) \rVert},
$$

while a curvature-based measure is

$$
\mathcal{T}_{\kappa} = \int_0^L |\kappa(s)| \, ds.
$$

These are useful because tortuosity changes the geometric difficulty of segmentation:

- a highly tortuous vessel produces more rapidly changing cross-sectional orientation;
- centerline shortcuts become more likely if tracking is not regularized;
- distance-based truncation can hide substantial arc length in curved vessels.

Coronary tortuosity and related geometric indexes have been used explicitly in coronary morphometry studies and are relevant both for vessel characterization and for segmentation QC [@zhu2009geometry; @prado2023geometry].

## Tube surfaces and nested wall geometry

For a branch centerline $\gamma(s)$ with local normal $\mathbf{N}(s)$ and binormal $\mathbf{B}(s)$, the lumen and outer-wall surfaces can be written as tubular surfaces:

$$
\mathbf{S}_{\text{lum}}(s,\theta)
=
\gamma(s) + r_{\text{lum}}(s,\theta)
\big(
\cos\theta\,\mathbf{N}(s) + \sin\theta\,\mathbf{B}(s)
\big),
$$

$$
\mathbf{S}_{\text{outer}}(s,\theta)
=
\gamma(s) + r_{\text{outer}}(s,\theta)
\big(
\cos\theta\,\mathbf{N}(s) + \sin\theta\,\mathbf{B}(s)
\big).
$$

The nesting condition is

$$
r_{\text{outer}}(s,\theta) \ge r_{\text{lum}}(s,\theta) + \delta_{\text{nest}}
$$

for some small positive barrier $\delta_{\text{nest}}$.

This formulation makes the outer-wall task geometrically precise: the problem is not merely to draw a second contour, but to recover a second surface field that remains nested around the lumen field while preserving local smoothness and plausibility. When perivascular fat or calcification obscures the wall, what fails is the estimation of the nested tube geometry itself.

In principle, one can also compute surface curvatures from these lumen or wall surfaces. If $k_1$ and $k_2$ are principal curvatures, then

$$
H = \frac{k_1 + k_2}{2},
\qquad
K = k_1 k_2
$$

are the mean and Gaussian curvatures. For the present project these are optional secondary descriptors rather than primary exports, but they are a natural way to describe local irregularity or over-smoothed surface patches.

## Bifurcation geometry as a node problem

At a bifurcation node $v \in \mathcal{V}$, the geometry is no longer well described by a single tubular edge. If the parent and daughter edges have **unit** tangent vectors $\mathbf{T}_0$, $\mathbf{T}_1$, and $\mathbf{T}_2$ at the node, then branch angles can be defined by

$$
\theta_{0i} = \arccos(\mathbf{T}_0 \cdot \mathbf{T}_i),
\qquad i \in \{1,2\}.
$$

A simple 3D planarity index is

$$
\eta_{\text{planar}}
=
\left|
(\mathbf{T}_0 \times \mathbf{T}_1) \cdot \mathbf{T}_2
\right|,
\qquad
0 \le \eta_{\text{planar}} \le 1,
$$

with $\eta_{\text{planar}} = 0$ for a coplanar bifurcation and larger values indicating a more strongly non-planar local junction geometry.

This already shows why bifurcations are hard for segmentation: in a junction neighborhood, the single-curve, single-cross-section model breaks down. A cross-section through the takeoff can intersect multiple luminal components, and the simple polar assumption $r(\theta)$ may no longer describe the image.

The graph model itself is not restricted to binary junctions. If a node has degree greater than 3, retain it as a higher-order branch node and compute pairwise local angles from the dominant parent path to each incident daughter tangent as needed; the binary formulas above are local descriptors, not a restriction on graph degree.

Branching geometry also connects to vascular scaling. Murray's law gives the classical radius relation

$$
r_0^3 = r_1^3 + r_2^3,
$$

and coronary bifurcations have been analyzed from this geometric and fractal perspective in quantitative coronary studies [@murray1926; @finet2007]. Coronary morphometry work has also measured branching angles directly from reconstructed coronary trees, which makes these quantities useful not only as mathematical descriptors but as implementable QC variables [@zamir1986branching; @zhu2009geometry]. More recent coronary CFD and CT studies likewise treat bifurcation tortuosity and branching geometry as local geometric risk descriptors, which is directly relevant to branch-aware segmentation and QC [@malve2015; @prado2023geometry].

## Fractal and scaling structure of the tree

The coronary tree is not only a collection of isolated curved branches. It also shows tree-level scaling behavior. In practical terms:

- parent and daughter diameters follow branching relations;
- branch lengths and diameters co-vary across scales;
- subtree complexity can be summarized through graph-ordering or fractal-style descriptors.

One standard tree-order descriptor is a diameter-defined Strahler order $\omega(e)$ on edges. If $e$ is terminal, then

$$
\omega(e) = 1.
$$

If a parent edge $e_0$ is formed by daughters $e_1$ and $e_2$, then

$$
\omega(e_0)
=
\max\{\omega(e_1), \omega(e_2)\}
+
\mathbf{1}_{\{\omega(e_1)=\omega(e_2)\}},
$$

where $\mathbf{1}$ is the indicator of equal daughter order. In practice, coronary morphometry often uses a diameter-defined Strahler system rather than a purely topologic one, but the point is the same: the recovered tree should show a plausible hierarchy of branch scales rather than arbitrary branch fragmentation [@kassab1993; @schwarz2020].

One standard multiscale complexity descriptor is the box-counting dimension

$$
D_{\text{box}}
=
\lim_{\varepsilon \to 0}
\frac{\log N(\varepsilon)}{\log(1/\varepsilon)},
$$

where $N(\varepsilon)$ is the number of boxes of side length $\varepsilon$ needed to cover the embedded centerline set or vessel mask. In practice one estimates $D_{\text{box}}$ by regression over a finite scale range. Coronary trees are not exact mathematical fractals, but finite-scale fractal descriptors are still useful summaries of branching complexity and self-similar scaling tendencies [@finet2007; @schwarz2020].

This matters because segmentation quality should preserve not just local contours but also plausible tree structure. If branch radii or branch lengths violate expected scaling grossly, the issue may be geometric mistracking rather than anatomy. Coronary bifurcation studies and arterial scaling work support describing the tree in these geometric terms [@finet2007; @choykassab2008].

## Why this framing matters for the algorithm

Under this view, the segmentation pipeline can be summarized mathematically as the recovery of:

$$
\Big(
\mathcal{G},
\{\gamma_e\}_{e \in \mathcal{E}},
\{r_{\text{lum},e}(s,\theta)\}_{e \in \mathcal{E}},
\{r_{\text{outer},e}(s,\theta)\}_{e \in \mathcal{E}},
M_{\text{cal}}
\Big).
$$

The practical algorithmic subproblems then become:

- **graph recovery**: identify branches and bifurcation nodes;
- **curve recovery**: estimate centerlines with stable curvature and torsion;
- **surface recovery**: estimate nested lumen and outer-wall tube surfaces;
- **junction handling**: detect where the single-tube model fails near bifurcations;
- **global consistency**: keep the recovered geometry compatible with expected branching and scaling structure.

This is a more faithful description of the coronary segmentation problem for CT-FFR than saying merely that the project needs "a vessel mask." It also matches the way a geometry expert is likely to think about the problem.

The next section shifts from the continuous geometric formulation above to practical descriptors that can be computed on reconstructed coronary trees and used in QC, phenotype analysis, or exploratory geometry-hemodynamics work.

## Practical geometric descriptors for coronary CT

Once the coronary tree is represented as an embedded graph with centerlines and cross-sections, the most useful geometric descriptors are not mysterious. They are the quantities that summarize local bending, global tortuosity, branching structure, caliber scaling, and cross-sectional regularity.

**Summary table** — descriptor priority by project stage:

| Descriptor | Stage-1 required | Stage-2 useful | Research extension |
|---|---|---|---|
| Radius/diameter profile $r_\text{lum}(s)$, MLD, $A_\text{lum}$ | Yes | - | - |
| Tapering rate $\alpha_\text{taper}(s)$ | Yes | - | - |
| Curvature $\kappa(s)$: mean, max | - | Yes | - |
| Distance-based tortuosity $\mathcal{T}_\text{dist}$ | - | Yes | - |
| Cross-sectional eccentricity / circularity | - | Yes | - |
| Branch order (Strahler) | - | Yes | - |
| Bifurcation angle $\theta_{0i}$, asymmetry $A_\text{bif}$ | - | Yes | - |
| Torsion $\tau(s)$ statistics | - | - | Yes |
| Curvature-based tortuosity $\mathcal{T}_\kappa$, bending energy $E_\kappa$ | - | - | Yes |
| Murray scaling exponent $n$ | - | - | Yes |
| Bifurcation planarity $\eta_\text{planar}$ | - | - | Yes |
| Finite-scale fractal dimension $D_\text{box}$ | - | - | Yes |
| Graph Laplacian spectrum | - | - | Yes |
| Geodesic/normal curvature (epicardial surface reference) | - | - | Yes |
| Topological descriptors (persistent homology) | - | - | Yes |

Detailed mathematical definitions follow below.

For a stage-1 or stage-2 geometry package, the most relevant descriptors are:

1. **Curvature statistics**

   $$
   \kappa(s) = \left\lVert \frac{d\mathbf{T}}{ds} \right\rVert.
   $$

   Useful summaries are mean curvature, maximum curvature, and curvature variance along a branch.

2. **Torsion statistics**

   $$
   \tau(t)
   =
   \frac{(\gamma'(t) \times \gamma''(t)) \cdot \gamma'''(t)}
   {\lVert \gamma'(t) \times \gamma''(t) \rVert^2}.
   $$

   These quantify how strongly a branch twists out of plane. In practice, evaluate torsion only where $\kappa > 0.01 \;\text{mm}^{-1}$ or a cohort-specific configured threshold.

3. **Distance-based tortuosity**

   $$
   \mathcal{T}_{\text{dist}} = \frac{L}{\lVert \gamma(L) - \gamma(0) \rVert}.
   $$

4. **Curvature-based tortuosity**

   $$
   \mathcal{T}_{\kappa} = \int_0^L |\kappa(s)| \, ds.
   $$

5. **Bending energy**

   $$
   E_{\kappa} = \int_0^L \kappa(s)^2 \, ds.
   $$

   This is a stricter descriptor than $\int |\kappa| ds$ because it penalizes sharp bends disproportionately.

6. **Diameter or radius profile**

   $$
   r_{\text{lum}}(s) = \sqrt{\frac{A_{\text{lum}}(s)}{\pi}},
   \qquad
   D_{\text{lum}}(s) = 2r_{\text{lum}}(s).
   $$

   In practice the useful summaries are minimum lumen diameter, proximal reference diameter, and diameter variability.

7. **Branching angle**

   $$
   \theta_{0i} = \arccos(\mathbf{T}_0 \cdot \mathbf{T}_i).
   $$

8. **Bifurcation planarity**

   $$
   \eta_{\text{planar}}
   =
   \left|
   (\mathbf{T}_0 \times \mathbf{T}_1) \cdot \mathbf{T}_2
   \right|.
   $$

   With unit tangent vectors, this is `0` for a coplanar bifurcation and increases as the local junction becomes more non-planar.

9. **Murray-style branching exponent**

   $$
   r_0^n = r_1^n + r_2^n.
   $$

   The exponent $n$ can be estimated locally from parent/daughter radii and treated as a branch-scaling descriptor. In coronary work this should be treated as a measured descriptor rather than as a fixed law: recent synthesis papers show that reported coronary exponents vary across species, modalities, and definitions, with pooled values often below the ideal Murray exponent $3$ [@taylor2024murray].

10. **Cross-sectional eccentricity and circularity**

   If a cross-section is approximated by an ellipse with semi-axes $a \ge b$, then eccentricity is

   $$
   e = \sqrt{1 - \frac{b^2}{a^2}}.
   $$

   If $A$ and $P$ are section area and perimeter, circularity is

   $$
   C = \frac{4\pi A}{P^2}.
   $$

11. **Branch order**

    Using Strahler-type order,

    $$
    \omega(e) = 1
    \quad \text{for terminal edges,}
    $$

    and

    $$
    \omega(e_0)
    =
    \max\{\omega(e_1), \omega(e_2)\}
    +
    \mathbf{1}_{\{\omega(e_1)=\omega(e_2)\}}.
    $$

    This is a compact way to summarize whether the recovered tree preserves a plausible hierarchy of major and minor branches [@kassab1993; @schwarz2020].

12. **Finite-scale fractal dimension**

    $$
    D_{\text{box}}
    \approx
    \frac{d \log N(\varepsilon)}{d \log(1/\varepsilon)}.
    $$

    Here $N(\varepsilon)$ is the number of boxes of side length $\varepsilon$ intersecting the embedded tree or centerline set. In practice this is estimated over a finite range of scales, not in a strict asymptotic limit [@finet2007; @schwarz2020].

13. **Graph Laplacian spectrum**

    If $W$ is a weighted adjacency matrix and $D$ is the corresponding degree matrix, then

    $$
    L_{\text{graph}} = D - W.
    $$

    Low-order eigenvalues of $L_{\text{graph}}$ summarize global connectivity, subtree balance, and topologic fragility of the recovered vessel graph. This is more naturally a stage-2 geometry descriptor than a mandatory stage-1 export.

14. **Tapering rate**

    A simple local taper descriptor is

    $$
    \alpha_{\text{taper}}(s)
    =
    -\frac{dD_{\text{lum}}(s)}{ds},
    $$

    or in scale-normalized form

    $$
    \beta_{\text{taper}}(s)
    =
    -\frac{1}{D_{\text{lum}}(s)}
    \frac{dD_{\text{lum}}(s)}{ds}.
    $$

    This is useful because proximal-to-distal caliber loss is both a normal geometric feature and a common failure mode when centerlines truncate or when distal contours become unstable.

15. **Bifurcation asymmetry**

    A simple daughter-branch asymmetry measure is

    $$
    A_{\text{bif}}
    =
    \frac{|r_1-r_2|}{r_1+r_2},
    \qquad
    0 \le A_{\text{bif}} < 1.
    $$

    This helps separate nearly symmetric bifurcations from strongly dominant-side branches and is often more informative than branch angle alone when discussing local geometry or flow split.

These descriptors are not all mandatory exports for stage 1. But they are the natural geometric summaries of a reconstructed coronary tree, and several of them are directly useful as QC variables or exploratory phenotype descriptors.

## Optional advanced descriptors

If the Berlin collaboration wants a more explicitly geometric research arm, there are several natural extensions beyond the standard vessel metrics above:

- **geodesic and normal curvature** if the vessel course is represented relative to an epicardial surface, with

  $$
  \kappa_n = \kappa\, \mathbf{N} \cdot \mathbf{n}_{\text{surf}},
  \qquad
  \kappa_g = \sqrt{\kappa^2 - \kappa_n^2};
  $$
- **curvature entropy** or distributional summaries of $\kappa(s)$ and $\tau(s)$;
- **fractal or multi-scale descriptors** of subtree organization;
- **topological descriptors** such as persistent homology on vessel masks or centerline graphs;
- **surface roughness or shape operators** on lumen and wall meshes.

These are not required for the primary CT-FFR workflow. But they are mathematically natural if one wants to use the segmentation pipeline not only for flow derivation, but also for geometric phenotype analysis.

Recent coronary-tree work makes this direction concrete rather than speculative. Graph-based coronary tree extraction and labeling already treat the vessel tree explicitly as a geometric graph object [@hampe2024]. Topology-preserving extraction methods show that maintaining connected tree structure is itself now an algorithmic target rather than a side effect [@qiu2025]. Coronary geometry papers are also moving toward geometry-hemodynamics coupled descriptors rather than shape-only summaries, for example by comparing curvature with more topology-aware flow-related markers [@zhang2024curvature]. In parallel, TDA and topological-uncertainty papers are beginning to appear in coronary plaque and vessel analysis, which makes persistent homology a plausible research extension for ambiguity quantification, but not yet a routine stage-1 descriptor [@singh2025tda; @singh2025uncertainty].

## Bibliographic map for coronary geometry

The geometry literature relevant to this project is easiest to read in two layers: **established descriptors** that already have a clear place in coronary morphometry, and **emerging descriptors** that are currently better treated as research extensions than as required stage-1 outputs.

### Established descriptor families

The established material can be grouped at four levels.

1. **Local centerline shape**

   Curvature, torsion, arc length, tortuosity, and bending-energy style summaries describe how a vessel bends and twists in 3D. Classical coronary morphometry and more recent CT-based geometry papers support using these quantities as primary geometric descriptors [@gross1998; @zhu2009geometry; @prado2023geometry].

2. **Branch and bifurcation geometry**

   Branching angle, daughter asymmetry, caliber tapering, parent-daughter diameter relations, and Murray-style scaling all belong here. These descriptors are anchored both in classic vascular optimization theory and in coronary bifurcation studies [@murray1926; @zamir1986branching; @finet2007; @taylor2024murray].

3. **Whole-tree topology and hierarchy**

   Graph representation, branch order, graph depth, subtree organization, and finite-scale fractal complexity describe whether the recovered coronary tree has a plausible global hierarchy rather than just plausible local contours [@antiga2008; @kassab1993; @schwarz2020].

4. **Cross-sectional morphology**

   Radius profile, minimum lumen diameter, eccentricity, circularity, and outer-wall nesting describe the local tube geometry actually needed for CT-FFR and plaque-aware vessel characterization. These are the most directly actionable descriptors for the segmentation handoff to the hemodynamic model [@javorszky2022; @meah2021].

### Emerging and advanced directions

The newer literature adds several directions that are relevant for the Berlin geometry collaboration, but should still be framed as optional or stage-2 research work in this project.

1. **Geometry-hemodynamics coupled descriptors**

   Recent CFD-based work studies how bifurcation angle, diameter ratio, tortuosity, and plaque topology interact to generate adverse hemodynamic phenotypes. This is where pure geometry begins to couple to wall-shear and low-flow risk markers rather than staying as shape description alone [@zhang2024curvature; @garcha2025].

2. **Topology-preserving extraction**

   Newer segmentation and extraction papers increasingly treat topology preservation itself as a design objective, because broken connectivity invalidates many downstream geometric and hemodynamic quantities [@hampe2024; @qiu2025].

3. **Topological data analysis**

   Persistent homology and related TDA tools are beginning to appear in coronary imaging. At present they are best regarded as advanced research descriptors for ambiguity quantification or phenotype analysis, not as routine mandatory outputs [@singh2025tda; @singh2025uncertainty].

4. **Learned graph descriptors**

   Graph neural networks and geometric deep-learning methods suggest a path toward learned vessel-tree representations in which connectivity and multi-branch context are first-class objects rather than post hoc summary variables [@hampe2024].

### Recommended reading priority for this project

If a reader needs a compact literature entry point rather than the whole bibliography, the most useful sequence is:

1. Gross and Friedman [@gross1998], Zhu et al. [@zhu2009geometry], and Prado et al. [@prado2023geometry] for coronary centerline geometry;
2. Finet et al. [@finet2007], Zamir and Chee [@zamir1986branching], and Taylor et al. [@taylor2024murray] for bifurcation and scaling laws;
3. Antiga et al. [@antiga2008], Kassab et al. [@kassab1993], and Schwarz et al. [@schwarz2020] for graph and morphometric tree structure;
4. Hampe et al. [@hampe2024], Qiu et al. [@qiu2025], Zhang et al. [@zhang2024curvature], Garcha and Grande Gutiérrez [@garcha2025], Singh et al. [@singh2025tda], and Singh et al. [@singh2025uncertainty] for the modern graph, topology, and hemodynamics extensions.

This section is intentionally bibliographic rather than prescriptive. It is meant to help a mathematically oriented reviewer see how the present segmentation specification sits inside the existing coronary geometry literature.

# Segmentation Targets in More Detail

## Coronary lumen

For CT-FFR, coronary lumen segmentation must support:

- centerline extraction;
- ordered proximal-to-distal sampling;
- cross-sectional lumen area estimation;
- MLA localization;
- geometric continuity across lesion and reference regions.

The main failure modes are:

- motion artifact, often because the chosen reconstruction phase is not sufficiently motion-stable for the target vessel;
- calcific blooming;
- metallic stent blooming / beam hardening, which can make the in-stent lumen uninterpretable;
- branch confusion near bifurcations;
- loss of distal continuity in small vessels.

### Algorithmic requirement

The lumen stage is not complete when it has produced a semantic vessel mask. It is complete only when it has produced:

- an ordered centerline $\mathbf{c}_i$;
- orthogonal cross-sections;
- a lumen area profile $A_{\text{lum},i}$;
- a stable MLA location;
- a distal span long enough for the pressure-drop integral.

That is why centerline geometry and contour ordering are first-class outputs rather than implementation details.

## Coronary outer wall

Outer-wall segmentation is needed only where it changes the reference model. The core requirement is not perfect whole-tree plaque mapping; it is reliable outer-wall geometry in or near:

- the lesion segment;
- nearby reference segments;
- contiguous regions needed to reconstruct a plausible local reference profile.

Outer-wall segmentation is substantially harder than lumen segmentation in CCTA because:

- the wall boundary is low-contrast;
- the media-adventitia boundary is often poorly distinguishable from surrounding perivascular fat, which is the fundamental limiting contrast problem even when motion artifact is modest;
- calcification obscures the outer contour;
- metallic stents usually make both lumen and outer-wall interpretation unreliable over the stented interval;
- wall thickness is small relative to voxel size;
- positive remodeling can preserve lumen despite substantial plaque burden [@glagov1987; @schoenhagen2000; @stone2011].

Published direct coronary outer-wall segmentation work in CCTA is limited, which is why this part of the pipeline should remain conservative [@ghanem2019].

### Practical consequence for algorithm design

The outer-wall problem is best treated as a **local contouring problem around an already stabilized lumen path**, not as a whole-volume semantic task. For this project, the useful question is not "can we label all plaque?" but "can we recover a plausible outer boundary in the lesion and nearby reference region with enough local continuity to support $A_{\text{ref,MLA}}$?"

## Myocardium

For the CT-FFR model in `manuscript_v14.md`, myocardium segmentation is required primarily for **LV mass**, not for a full functional cine analysis.

That means the practical objective is:

- robust LV myocardium extraction;
- acceptable basal and apical boundary definition;
- total myocardial mass sufficient for vessel-territory flow allocation.

This is easier to justify than claiming immediate patient-specific perfusion territories for every case. In stage 1, vessel allocation can still rely on anatomical fractions while myocardium segmentation provides total mass.

### Mathematical output of the myocardium stage

For this project, the myocardium stage should be evaluated on the stability of

$$
M_{\text{CT}} = \rho_{\text{myo}} \sum_{\mathbf{x}} m(\mathbf{x}) \, \Delta V_{\text{vox}},
$$

not only on overlap metrics. A mask with slightly imperfect surface overlap may still be acceptable if it yields stable total mass after calibration; conversely, a visually good mask with systematic basal leakage may be unusable because it biases mass directly.

# Method Families Relevant To This Project

## Classical coronary segmentation package

The most relevant classical stack for this project combines:

- vessel enhancement filtering [@frangi1998];
- minimum-cost-path centerline extraction [@metz2009];
- cross-sectional reformatting;
- lumen and outer-wall boundary extraction in polar coordinates;
- centerline refinement from segmented lumen centroids.

This is the strongest method family for the CT-FFR project because it directly targets geometry rather than generic semantic masks.

### Why it fits the current project

It is attractive for the present use case because it is:

- deterministic;
- interpretable;
- compatible with partial manual inputs;
- adaptable to a per-vessel workflow;
- usable even when training data are limited or heterogeneous.

### Core steps

1. **Preprocessing**  
   Resample when needed and compute a vesselness map with a Hessian-based filter [@frangi1998]. This is useful in mid-vessel segments, but Frangi-type responses are less reliable near ostia, bifurcations, and heavy calcification, so calcified and branching segments require supplemental QC and often additional steps beyond vesselness alone.

2. **Centerline tracking**  
   Use one- or two-click minimum-cost-path extraction from CTA to establish the target-vessel trajectory [@metz2009].

3. **Cross-sectional extraction**  
   Build perpendicular slices along the centerline and preserve physical spacing.

4. **Boundary extraction**  
   Use polar-domain lumen search and, where image quality permits, nested inner/outer contour search. Here [@ghanem2019] is best read as general coronary wall/plaque-segmentation background rather than as a fully specified off-the-shelf recipe. In practical terms, the exact outer-wall contouring logic should be treated as a project development work package with explicit QC thresholds, not as a mature method that can simply be imported unchanged.

5. **Refinement and smoothing**  
   Replace corner-cutting centerlines with centroid-refined lumen paths and enforce proximal-to-distal continuity.

### Role in the project

This classical package should be treated as the **default completion and harmonization pathway** for CTA cases where Medis coverage is missing, partial, or inconsistent.

## Medis contour pathway

The Medis-specific pathway is not a separate scientific hypothesis. It is a practical route for:

- ingesting existing lumen and vessel-wall contours;
- reconstructing centerlines from contour centroids;
- generating meshes and straightened MPR views;
- checking contour continuity and ordering;
- exporting lumen and outer-wall area profiles for downstream modeling.

This pathway is especially useful for:

- early QC;
- reference contour comparison;
- lesion-level visualization;
- outer-wall plausibility review in partially segmented cases.

A practical gate remains implicit unless stated explicitly: Medis contour exports are vendor-format outputs, and their reuse outside the Medis software environment may depend on the available export pathway, institutional licence terms, and project-specific data-use permissions. Stage A should verify that the available exports can be parsed and processed within the research pipeline before the Medis pathway is treated as routine computational input.

It should remain a **data-harmonization asset**, not the sole segmentation strategy.

## Task-specific deep learning methods

There is published precedent for deep-learning segmentation in CCTA, but the evidence base is still patchier for coronary lumen plus outer wall than for larger cardiac structures.

Relevant examples include:

- multi-structure cardiac CT segmentation [@baskaran2020segment];
- automated plaque segmentation on coronary CTA [@javorszky2022];
- automatic coronary artery labeling [@ren2023coronarylabel];
- LV myocardium segmentation from cardiac CT/CCTA [@vanhamersvelt2019; @guo2020myocardium; @koo2020myocardium; @bruns2022wholeheart].

### What these methods are good for here

- accelerating lumen or plaque candidate generation;
- supporting myocardium extraction;
- assisting branch labeling and branch-specific bookkeeping;
- serving as comparators to the classical package.

### What they do not solve automatically

They do **not** remove the need for:

- per-vessel geometric QC;
- outer-wall plausibility checks in calcified segments;
- explicit continuity checks for flow derivation;
- conservative fallback when a model leaks, truncates, or loses distal geometry.

## Foundation-model route: SAM-Med3D

SAM-Med3D extends promptable segmentation to volumetric medical images [@Zhang2024SAMMed3D], building conceptually on the original SAM paradigm [@Kirillov2023SAM].

For this project, the important point is not hype but role:

- it may help as a promptable candidate generator for lumen, vessel wall, or myocardium;
- it may accelerate completion of missing segments;
- it may support human-in-the-loop correction workflows;
- it provides a useful comparator against classical and task-specific methods.

### Why it is interesting

Potential advantages:

- fast interactive prompting;
- broad anatomical prior from pre-training;
- flexibility across coronary lumen, myocardium, and possibly plaque-related structures;
- compatibility with a future human-correction workflow.

### Why it must remain secondary in the current CT-FFR proposal

Coronary CTA is a hard target for foundation models because of:

- small vessel caliber;
- motion artifact;
- calcific blooming;
- bifurcations and overlap;
- the need for **nested** lumen and outer-wall boundaries rather than only one semantic mask.

Most importantly, the published SAM-Med3D benchmarks cover broad volumetric organ tasks and cardiac MRI structures rather than coronary CTA lumen-plus-wall delineation [@Zhang2024SAMMed3D]. A strong task-specific baseline such as nnU-Net remains the right comparator [@Isensee2021nnUNet].

### Recommended role of SAM-Med3D in this project

SAM-Med3D should be treated as:

- an **optional research arm**;
- an **assisted completion tool**;
- a **benchmark against classical methods**;
- a possible aid for myocardium extraction and contour completion.

It should **not** be the only segmentation strategy assumed in `proposal_v11.md`.

# Algorithmic Specification

## Medis contour ingestion

For Medis-style contour exports, the minimum viable ingestion algorithm is:

1. parse each contour ring and preserve slice identity;
2. transform all points into one physical coordinate system, namely DICOM patient `LPS`;
3. compute polygon area and centroid for each ring;
4. sort rings into proximal-to-distal order;
5. fit or smooth the centroid path into a usable centerline;
6. emit $s_i$, $A_{\text{lum},i}$, and where available $A_{\text{outer},i}$.

At the ring level, if a contour consists of local 2D points $(x_{i,j}, y_{i,j})$, then area should be computed directly from the ring rather than by rasterizing and re-thresholding it. A practical first-pass centerline point is the vertex mean

$$
\mathbf{c}_i =
\frac{1}{M_i}
\sum_{j=1}^{M_i} \mathbf{p}_{i,j}.
$$

Arc length follows from the cumulative Euclidean distance between successive centroids. A spline or Savitzky-Golay smoothing pass is reasonable, but the smoothed path must remain ordered and must not shrink away from the lesion geometry.

For stage 1, a practical default is to resample the provisional centerline to **0.5-1.0 mm** spacing and then apply either:

- a cubic B-spline with knot spacing around **2-4 mm**; or
- a Savitzky-Golay filter with window length **5-9 samples** and polynomial order **3**.

Any smoothing pass that shifts the local centerline by more than about **0.5 mm** in the MLA neighborhood or changes local lumen area by more than about **5\%** without image support should trigger review rather than be accepted automatically.

## CTA-based centerline completion

When Medis coverage is incomplete, the geometric completion problem is to connect a proximal and distal vessel point by a minimum-cost path through a vesselness-weighted volume. In abstract form, define a cost map $C(\mathbf{x})$ from a vesselness response $V(\mathbf{x})$ such as

$$
C(\mathbf{x}) = \frac{1}{\varepsilon + V(\mathbf{x})}
\quad \text{or} \quad
C(\mathbf{x}) = \exp(-\alpha V(\mathbf{x})).
$$

The centerline is then the path

$$
\gamma^\ast
=
\arg\min_{\gamma}
\int_\gamma C(\mathbf{x}) \, ds
$$

between prescribed proximal and distal seed points. Fast-marching or related minimal-path methods are appropriate here because they produce a global optimum in the chosen cost field and naturally support interactive seeding.

This path is only a first pass. Minimal paths tend to cut corners in curved vessels, so the centerline should be refined after lumen segmentation by moving each sample back toward the lumen centroid in the orthogonal slice. If multiple reconstruction phases are available, the phase used for this path should be the one judged most motion-stable over the lesion and MLA neighborhood rather than whichever series happens to be loaded first.

## Cross-sectional extraction

Given a provisional centerline, generate a resampled sequence of equally spaced positions, typically at submillimeter spacing. At each position:

1. build the local Bishop / parallel-transport frame $(\mathbf{t}_i, \mathbf{u}_{1,i}, \mathbf{u}_{2,i})$;
2. sample a perpendicular patch with physical spacing preserved;
3. store the slice together with its world-to-slice transform.

The frame in step 1 should follow the Bishop / parallel-transport rule stated in the Frenet-Serret section unless the code is computing curvature or torsion descriptors explicitly. The transform matters because all subsequent contours and areas must be convertible back into physical coordinates for arc-length integration and for comparison against Medis contours.

## Polar-domain contour extraction

In each cross-section, contour extraction can be posed as an optimization problem over radial paths. For the lumen contour:

$$
r_{\text{lum}}^\ast(\theta)
=
\arg\min_{r(\theta)}
\sum_{\theta}
\Big[
C_{\text{lum}}(r(\theta),\theta)
+
\lambda_1 |r(\theta) - r(\theta-\Delta\theta)|
+
\lambda_2 |r(\theta) - 2r(\theta-\Delta\theta) + r(\theta-2\Delta\theta)|
\Big].
$$

Here $C_{\text{lum}}$ is a local image cost derived from intensity, gradient magnitude, and optional calcification penalties. The first regularizer penalizes jagged radius jumps; the second penalizes curvature oscillation around the contour.

In implementation, the radial coordinate should be normalized by the local search radius and the data term should be scaled slice-wise so that no single raw image channel dominates by units alone. A practical stage-1 starting point in these normalized units is $\lambda_1 \approx 0.5$ and $\lambda_2 \approx 0.25$, then tune upward if sawtooth or wavy contours appear and downward if eccentric lesion geometry is visibly over-smoothed.

The outer-wall contour uses an analogous optimization,

$$
r_{\text{outer}}^\ast(\theta)
=
\arg\min_{r(\theta)}
\sum_{\theta}
\Big[
C_{\text{outer}}(r(\theta),\theta)
+
\lambda_3 |r(\theta) - r(\theta-\Delta\theta)|
+
\lambda_4 |r(\theta) - 2r(\theta-\Delta\theta) + r(\theta-2\Delta\theta)|
\Big]
$$

subject to the nesting constraint

$$
r_{\text{outer}}(\theta) \ge r_{\text{lum}}(\theta) + \delta_{\text{nest}}
$$

for some small positive margin $\delta_{\text{nest}}$. This makes explicit what is otherwise often left implicit: outer-wall extraction is not just another edge detector, but a constrained contour-search problem coupled to the lumen estimate.

For clarity, this should be read as the small non-crossing barrier used inside the optimizer. A practical stage-1 implementation can start with $\delta_{\text{nest}}$ on the order of **0.05-0.10 mm** or another sub-voxel configured value.

The outer-wall cost $C_{\text{outer}}$ should combine at least four ingredients:

- outward edge evidence from gradient magnitude or signed edge response;
- a soft attraction to a plausible wall-thickness band relative to the lumen contour;
- a penalty for obviously implausible excursions into calcium bloom, stent artifact, or surrounding low-information background;
- a continuity preference relative to adjacent slices in the trusted interval.

In normalized units, a practical stage-1 starting point is $\lambda_3 \approx 0.75$ and $\lambda_4 \approx 0.35$, with stronger smoothing than for the lumen because the outer wall is less directly visible.

## Centerline refinement from the segmented lumen

Once lumen contours exist, the centerline should be updated from the contour centroids and then re-smoothed. In practical terms:

1. compute the centroid of each lumen contour;
2. replace the provisional centerline point by that centroid;
3. refit the path and recompute tangents;
4. repeat cross-sectional extraction if the correction is material.

This loop is important because centerline error feeds directly into cross-sectional orientation, which in turn changes the area profile and MLA estimate.

For stage 1, a practical stopping rule is: stop when the median centroid update falls below **0.10 mm** and the maximum update below **0.25 mm**, or after **3 iterations**, whichever comes first. Treat the correction as material if any point moves by more than about **0.5 mm** or if the MLA area changes by more than about **5\%** after one refinement cycle.

## Myocardium extraction and calibration

The myocardium problem is technically simpler because the final quantity of interest is scalar total mass rather than a detailed local wall profile. A practical algorithmic contract is:

1. infer or import an LV myocardium mask;
2. remove obvious basal and apical leakage;
3. compute raw CT mass from voxel volume;
4. calibrate that mass against paired CMR where available;
5. export both raw and calibrated mass together with QC flags.

Use $\rho_{\text{myo}} = 1.05 \;\text{g/mL}$ unless a project-specific value is declared explicitly. For stage 1, "basal leakage" should mean extension above the mitral-annular / basal valve plane into left-atrial or aortic-root space, and "apical leakage" should mean persistence beyond the last slice containing a compact circumferential LV myocardial ring. If those boundaries cannot be inferred reliably, require manual correction rather than exporting a calibrated mass silently.

The critical point is to retain both

$$
M_{\text{CT}}
\quad \text{and} \quad
M_{\text{cal}}
$$

in the export, because calibration status is part of the measurement state.

# Coronary-Specific Strategy

## Lumen-first principle

The first geometry to stabilize is the lumen path. Without a reliable lumen centerline and area profile:

- the viscous term cannot be computed robustly;
- lesion mapping is unstable;
- outer-wall interpretation becomes ungrounded.

Therefore the recommended order is:

1. lumen continuity;
2. centerline stabilization;
3. outer-wall completion where supported;
4. branch labeling if needed;
5. export to flow derivation.

## Outer-wall as a local enhancement, not a universal prerequisite

Outer-wall information should be used where it is good enough to alter the reference model. Where it is not reliable, the project should revert locally to the lumen-envelope comparator.

Here "local" means a contiguous interval around the MLA and adjacent reference span, not an arbitrary one-slice correction applied without interval context.

This is fully consistent with `manuscript_v14.md` and should be stated explicitly in any segmentation section derived from this document.

For stage-1 implementation, "good enough" should not remain implicit. A practical default is to allow Glagov-mode use only when all of the following hold over a trusted interval covering the lesion and adjacent reference span:

1. the trusted interval contains the MLA slice and extends at least

   $$
   L_{\text{wall,ref}} = \max(5 \text{ mm}, D_{\text{loc}})
   $$

   proximally and distally, after excluding bifurcation neighborhoods;
2. the nesting margin

   $$
   m_i = r_{\text{outer},i} - r_{\text{lum},i}
   $$

   is positive on all trusted slices and has median value at least **0.30 mm**;
3. no more than **10\%** of trusted slices carry a severe blooming or motion flag;
4. local area oscillation satisfies $o_i \le 0.35$ on at least **90\%** of trusted slices.

If any of these conditions fails, the vessel should revert locally to the lumen-envelope comparator rather than carrying low-confidence outer-wall geometry into $A_{\text{ref,MLA}}$.

The **0.30 mm** requirement above is a stage-1 QC acceptance threshold on observed wall margin, not the same quantity as the small algorithmic barrier $\delta_{\text{nest}}$ used to prevent contour crossing inside the reconstruction method. The four conditions above are operationalized in the formal $\texttt{wall\_L0}$ predicate in the Analyzability decision logic section: slices failing conditions 2–4 are excluded from the trusted set $\mathcal{I}_\text{trust}$; condition 1 is enforced as a bilateral interval threshold $\ell_\text{trust}^\pm(s_\text{MLA}) \ge \max(5\text{ mm}, D_\text{loc})$ on the remaining trusted slices.

## Stage-1 estimation of $T_{\text{healthy}}$

For Glagov-mode reference reconstruction, the stage-1 default should be to estimate the healthy wall thickness from the same trusted wall interval that supports outer-wall use rather than from a population constant alone.

Define the local wall margin

$$
m_i = r_{\text{outer},i} - r_{\text{lum},i}
$$

on trusted non-bifurcation slices outside the immediate MLA micro-neighborhood. Then the primary stage-1 estimator is

$$
T_{\text{healthy}}
=
\operatorname{median}\{m_i : i \in \mathcal{I}_{\text{ref,trusted}}\},
$$

where $\mathcal{I}_{\text{ref,trusted}}$ denotes the proximal and distal trusted reference slices retained after artifact and coverage QC. In practice, this requires at least one contiguous trusted support span of roughly **5 mm** on either the proximal or distal side.

To keep the CTA-visible total-wall estimate physiologically conservative and aligned with the companion manuscript, this primary estimate should be clipped to the stage-1 prior range **0.40–0.80 mm** [@nissen1991; @mintz2001; @choykassab2008].

If the trusted reference support is too short or too unstable to support the median estimator, the stage-1 fallback is

$$
T_{\text{healthy}}
=
\beta \, \operatorname{median}(r_{\text{lum},i}),
\qquad
\beta \approx 0.18,
$$

again clipped to **0.40–0.80 mm**, and exported with an explicit fallback reason such as insufficient trusted wall reference support.

This is intentionally a **single-scalar** approximation along the analyzed span. It is a conservative stage-1 simplification, not a claim that true wall thickness is constant along a positively remodeled lesion. In strongly remodeled segments it may therefore underestimate the local unconstricted reference radius rather than exaggerate it.

## Reference-reconstruction fallback hierarchy

The fallback problem should be defined on the reference geometry, not on a claim to recover the true outer wall everywhere. A practical hierarchy is:

- **Level 0**: measured outer wall over a trusted MLA-centered lesion/reference interval; this is the only primary-evidence Glagov mode.
- **Level 1**: local reconstruction from trusted proximal and distal outer-wall anchors along the centerline, for example shape-preserving interpolation or spline interpolation.
- **Level 2**: physiology-constrained or lumen-derived reference-lumen fallback when local anchors are inadequate, for example monotone tapering, Murray-style branch-order scaling [@murray1926], or kernel-smoothed healthy-radius reconstruction [@blanco2018; @shahzad2013].
- **Level 3**: population or anatomical priors only; these are sensitivity-only or exclusion-grade support, not primary Glagov evidence.

Two rules should remain explicit:

1. none of these fallback levels changes the observed lumen profile that enters the viscous term;
2. if the MLA neighborhood is supported only by Level-3 priors, the vessel should usually revert to `lumen_envelope` mode or be excluded from primary G-CT-FFR / MG-CT-FFR analyses.

This hierarchy is useful precisely because outer-wall information is sometimes locally difficult. It preserves continuity of the workflow while still recording how much of the reference model came from measured wall geometry versus higher-prior assumptions.

## Operational fallback triggers

Level-0 wall support should be revoked locally when common artifact or continuity failures are present in the MLA-centered interval. A practical stage-1 trigger table is:

| Trigger | Default threshold | Stage-1 action |
|---------|-------------------|----------------|
| Severe blooming or motion | present on more than **10\%** of trusted slices | downgrade to Level 1 or Level 2 support, otherwise revert to `lumen_envelope` |
| Non-physical nesting | any trusted slice with $r_{\text{outer}} \le r_{\text{lum}} + 0.30$ mm | do not treat the interval as direct measured-wall support |
| Outer-wall coverage gap | contour gap $> 3$ mm through the MLA neighborhood | use Level 1 only if trusted anchors remain on both sides |
| Excessive wall oscillation | QC limit violated on more than **10\%** of trusted slices | downgrade support level |
| Reader disagreement | repeated-read outer-wall area difference $> 20\%$ around the MLA, if repeated reads exist | allow only sensitivity-grade fallback, not primary Glagov support |

These thresholds are QC defaults for stage-1 workflow control. They are not claims that the true physiology changes discontinuously at those exact values.

## Stage-1 fallback decision logic

**Formal Level-0 eligibility predicate.** Let $\mathcal{I}_\text{trust} \subseteq \{1,\ldots,N\}$ denote the set of cross-sectional indices where outer-wall data is available and passes nesting and artefact QC. Define:

$$
\ell_\text{trust}^+(s_\text{MLA}) = \max_{i \in \mathcal{I}_\text{trust},\, s_i > s_\text{MLA}} (s_i - s_\text{MLA}), \quad
\ell_\text{trust}^-(s_\text{MLA}) = \max_{i \in \mathcal{I}_\text{trust},\, s_i < s_\text{MLA}} (s_\text{MLA} - s_i).
$$

Then Level-0 eligibility is:

$$
\texttt{wall\_L0} \;\Longleftrightarrow\;
\ell_\text{trust}^+(s_\text{MLA}) \ge \max(5\text{ mm},\, D_\text{loc}) \;\land\;
\ell_\text{trust}^-(s_\text{MLA}) \ge \max(5\text{ mm},\, D_\text{loc}) \;\land\;
\frac{|\mathcal{I}_\text{artefact} \cap \mathcal{I}_\text{trust}|}{|\mathcal{I}_\text{trust}|} \le 0.10,
$$

where $\mathcal{I}_\text{artefact}$ indexes severely artefacted slices and $D_\text{loc}$ is the local vessel diameter at the MLA. The three conditions enforce: (1) sufficient bilateral trusted interval; (2) sufficiently low artefact fraction. When $\texttt{wall\_L0}$ is false but outer-wall data exists, the fallback levels below apply.

The hierarchy above should be implemented as an explicit routing rule rather than an informal reviewer interpretation:

1. define the MLA-centered lesion/reference interval after bifurcation-neighborhood exclusion;
2. if measured wall covers that interval and passes coverage, nesting, and artifact QC, assign `fallback_level = 0`, `mla_support_mode = measured_wall`, and `glagov_primary_eligible = true`;
3. otherwise, if a short missing span is bracketed by trusted proximal and distal anchors, assign `fallback_level = 1` and use local interpolation;
4. otherwise, if local anchors are inadequate but vessel identity and taper priors remain credible, assign `fallback_level = 2` and use a taper prior or kernel-smoothed reference-lumen estimate as secondary support only;
5. otherwise, revert to `reference_mode = lumen_envelope`; if a Level-3 population prior is evaluated at all, export it only as sensitivity or exclusion-grade support;
6. in every non-Level-0 case, export `fallback_reason`, `mla_support_span_mm`, and `glagov_primary_eligible = false` explicitly.

The same rule applies to any derived remodeling biomarker: if `mla_support_mode != measured_wall` or `glagov_primary_eligible = false`, then `RI_Glagov` should be exported as indeterminate rather than back-filled from higher-prior support.

## Branch labeling and bookkeeping

Automatic branch labeling methods may be useful for:

- LAD / LCx / RCA assignment;
- branch-level QC;
- future vessel-territory refinement [@ren2023coronarylabel].

However, branch labeling is a support task. It should not be treated as the main segmentation bottleneck.

## Bifurcation handling

Bifurcations are not just a bookkeeping problem. They are one of the hardest parts of the segmentation algorithm itself.

The difficulty is structural:

- vesselness maps often merge parent and daughter branches near the takeoff;
- minimum-cost-path tracking can jump from the intended branch into a side branch or cut through the junction;
- a cross-section through a bifurcation is no longer well approximated by one simply connected lumen;
- the polar-contour assumption $r(\theta)$ becomes weak or invalid when the slice contains a branch ostium;
- outer-wall nesting is especially unstable in branch-takeoff regions.

For this reason, the vessel should be treated locally as a **graph with branch nodes**, not as one globally simple tube.

Plainly, the practical exclusion zone is a corridor extending about one to two local vessel diameters proximal and distal to the carina along each incident branch.

Let $v_{\text{bif}}$ denote a branch-takeoff node and let $D_{\text{loc}}(v_{\text{bif}})$ be the local parent-vessel diameter at that node. A useful operational definition of the bifurcation exclusion neighborhood is

$$
\mathcal{N}_{\text{bif}}(\eta_{\text{bif}})
=
\left\{
x \in \bigcup_{e \sim v_{\text{bif}}} e
:\;
d_{\mathcal{G}}(x, v_{\text{bif}})
\le
\eta_{\text{bif}} D_{\text{loc}}(v_{\text{bif}})
\right\},
$$

where $d_{\mathcal{G}}$ is graph distance along the incident centerline edges. For stage-1 work, a practical default is $\eta_{\text{bif}} \in [1,2]$, i.e. roughly one to two local vessel diameters proximal and distal to the carina along each incident branch.

The practical stage-1 policy should be:

1. detect and label branch takeoff locations on the centerline graph;
2. define a bifurcation neighborhood around each takeoff, for example by the graph-distance rule above;
3. exclude that neighborhood from healthy-reference estimation, outer-wall reference reconstruction, and routine MLA identification unless the local geometry is still clearly single-lumen;
4. analyze one target branch path at a time and flag true bifurcation lesions for separate review, separate analysis, or temporary exclusion.

So yes, bifurcation treatment is needed already at the segmentation stage, but mainly as a **graph-aware tracking and exclusion/QC problem**, not yet as a requirement for a full multi-branch hemodynamic solver in stage 1.

For stage-1 flow derivation, unresolved bifurcation neighborhoods should be excluded from the resistance integral and from routine MLA/reference estimation. If that exclusion would create an unresolved continuity gap or place the MLA inside the excluded neighborhood, reject the vessel rather than introducing a branching correction.

# Myocardium Strategy

This section is the operational counterpart of the **mass-stable volumetric domain** object $\Omega_{\text{myo}}$ introduced in the geometric framework above.

## What is needed now

For the current CT-FFR model, the myocardium problem is simpler than the coronary-wall problem. The project mainly needs:

- an LV myocardium mask;
- a reproducible total LV mass estimate;
- enough QC to avoid major basal/apical errors;
- a calibration state before the mass estimate is used as quantitative flow input.

## Realistic method options

Three practical options exist:

1. **Dedicated LV myocardium models on CT/CCTA** [@vanhamersvelt2019; @guo2020myocardium; @koo2020myocardium]
2. **Whole-heart segmentation models** from contrast-enhanced cardiac CT [@baskaran2020segment; @bruns2022wholeheart]
3. **Semi-automatic correction** when automatic output is good enough for rapid editing but not fully reliable

Here "semi-automatic correction" means that the automatic mask is treated as an editable draft and the operator corrects only the basal plane, apical tail, major atrial / aortic spillover, and obvious endocardial or epicardial leaks before recomputing mass. Corrected outputs should be exported with `lv_mass_state = manually_corrected` and remain traceable to the original automatic mask.

## Recommendation

For stage 1 of the CT-FFR project, myocardium segmentation should be treated as a **parallel but lower-risk task** than coronary outer-wall segmentation. If an automated LV myocardium method performs adequately, it can be used to provide total mass even while coronary-vessel harmonization remains incomplete.

## Calibration requirement

CT-derived LV mass should not be treated as modality-neutral. Published CT-versus-CMR comparisons show that LV mass measurements can agree well yet still differ enough to require explicit calibration rather than blind interchangeability [@schlosser2007]. Any LV mass entering the flow model should therefore pass through a CT-to-CMR calibration step, ideally in a paired DISCHARGE subset, before it is treated as a quantitative demand input. If only an interim prior-based slope is available, export that state explicitly as `prior_slope` rather than silently upgrading it to `calibrated`.

For stage 1, the preferred default is a cohort-wide slope-only Deming regression unless the paired subset demonstrates a clear intercept term that is both statistically credible and clinically material. Sex-specific maps may be reported as plausibility or sensitivity analyses, but they are not required to unlock primary mass-based exports.

Operationally, the default estimator should be **slope-only Deming regression** of paired CMR mass on CT mass, because both measurements carry non-trivial error. If the paired subset is too small to justify a stable intercept, keep the intercept fixed at zero and report the fitted slope with bootstrap uncertainty. Ordinary least squares may still be reported as a sensitivity analysis, but it should not be treated as the stage-1 default calibration rule because it ignores error in the CT-derived predictor.

The paired reference set should also be protocol-consistent rather than convenience-sampled. If the paired set is small, use all available paired cases. If it is larger than the minimum target, prefer a stratified subset spanning sex, body size or LV-mass tertiles, and major scanner / reconstruction families rather than a narrow convenience sample. The reference CMR mass should come from one locked protocol, ideally end-diastolic LV myocardial mass from a short-axis stack or equivalent volumetric protocol, with one explicit mitral-annular-to-apex boundary convention and one explicit papillary-muscle convention applied consistently across the subset.

## Current starting point

The prior proposal track already described a DISCHARGE nnU-Net-based LV myocardium pipeline [@Isensee2021nnUNet] seeded from Philips whole-heart outputs and trained on approximately 300 manually refined CT cases. In this reference, that pipeline should be treated as the primary Stage D starting point. The open question is its current operational availability and cohort-wide validation status, not whether myocardium extraction begins from zero.

### Dated operational status note

As of **11 March 2026**, the myocardium situation should be described operationally as follows:

| Item | Status for this reference |
|------|---------------------------|
| Model lineage | Documented nnU-Net-based DISCHARGE LV myocardium pipeline seeded from Philips whole-heart outputs |
| Training base | Approximately 300 manually refined CT cases, as described in the prior proposal track |
| What is known | A plausible stage-1 starting model exists in project history; myocardium extraction does not begin from zero |
| What is not yet confirmed here | active weights, preprocessing scripts, reproducible inference on the current cohort, and cohort-wide failure rate |
| Stage-D acceptance gate | run reproducibly on an initial pilot batch, require manual correction in no more than about **25\%** of pilot cases, and achieve calibrated mass error no worse than about **15\%** against the available paired CT-CMR or expert-reference subset |
| Fallback if gate fails | switch to an alternate validated whole-heart / LV myocardium model plus lightweight manual correction |

For calibration, the practical target should be a paired CT-CMR subset of at least **25** cases if available; if fewer paired cases exist, use all available paired cases and widen the reported uncertainty rather than pretending the calibration is exact.

# Recommended Staged Workflow

## Stage A: Inventory and harmonization

- inventory CTA volumes, Medis exports, and matching metadata;
- classify available contours by vessel, side, reader, and completeness;
- standardize coordinate conventions and contour ordering;
- define analyzability labels.

## Stage B: Medis-based QC and export

- parse existing lumen and vessel-wall contours;
- build centerlines from contour centroids;
- generate meshes and straightened MPR views;
- flag missing spans, implausible rings, and self-inconsistencies.

## Stage C: Classical CTA completion

- apply vesselness filtering and minimum-cost-path tracking to fill missing target-vessel spans;
- generate cross-sectional reformats;
- segment lumen and outer wall with nested-contour logic where possible;
- refine centerlines and enforce continuity.

## Stage D: LV myocardium extraction

- first test the previously described DISCHARGE nnU-Net LV myocardium pipeline on the active cohort;
- confirm current model availability and characterize obvious failure modes;
- derive LV mass and apply CT-to-CMR calibration before quantitative flow use;
- define a lightweight correction workflow for obvious failures.

## Stage E: Optional SAM-Med3D comparison

- test promptable segmentation for lumen, wall, and myocardium in a bounded research subset;
- compare against classical and task-specific methods;
- quantify where SAM helps, where it leaks, and where it does not add value.

## Stage F: Flow-ready export

For each analyzable vessel, export:

- branch label;
- reconstruction phase metadata;
- centerline;
- ordered cross-sectional positions;
- lumen area profile;
- outer-wall area profile or missingness flag;
- stent flag or stented intervals;
- lesion/MLA markers;
- QC flags;
- linked LV mass.

## Flow-ready export contract

For programmers, the easiest way to keep the segmentation and hemodynamic stages compatible is to treat the handoff as a fixed schema rather than as ad hoc intermediate files. At minimum, each exported vessel should contain:

| Field | Type | Units | Meaning |
|-------|------|-------|---------|
| `vessel_id` | string | - | LAD / LCx / RCA plus branch identifier; in stage 1 this is a bookkeeping label, not yet a myocardium-linked territory identifier |
| `recon_phase_label` | string or number | - | CTA reconstruction phase used for this export, e.g. vendor label or R-R percentage; stage-1 default is one phase label per exported vessel |
| `centerline_xyz` | array `(N,3)` | mm | Ordered world coordinates |
| `s_mm` | array `(N,)` | mm | Cumulative arc length |
| `A_lum_mm2` | array `(N,)` | mm$^2$ | Lumen area profile |
| `A_outer_mm2` | array `(N,)` or null | mm$^2$ | Outer-wall area profile |
| `mla_index` | integer | - | Index of the MLA site |
| `reference_mode` | enum | - | coarse summary label: `glagov_level0`, `fallback_reference`, or `lumen_envelope` |
| `outer_wall_available` | boolean array or intervals | - | Where outer-wall data are trusted |
| `trusted_wall_intervals` | intervals or null | mm | Explicit MLA-centered intervals with direct outer-wall support |
| `fallback_level` | integer or null | - | `0`, `1`, `2`, `3`, or `null` for pure lumen-envelope handling |
| `fallback_reason` | enum or string | - | Why higher-prior reference support was invoked, e.g. calcification, blooming, truncation, poor nesting, short coverage |
| `mla_support_mode` | enum | - | `measured_wall`, `local_reconstruction`, `taper_prior`, `population_prior`, or `lumen_envelope` |
| `mla_support_span_mm` | float or object | mm | Proximal/distal span over which the MLA neighborhood is supported by the declared reference mode |
| `glagov_primary_eligible` | boolean | - | True only when the MLA neighborhood is supported by measured wall and stage-1 Glagov QC passes |
| `ri_glagov` | float or null | - | Exploratory remodeling index $A_{\text{outer}}(s_{\text{MLA}}) / A_{\text{ref,G}}(s_{\text{MLA}})$ when Level-0 MLA support exists |
| `ri_glagov_state` | enum | - | `computed`, `indeterminate_fallback`, `indeterminate_no_wall`, or `not_requested` |
| `ri_glagov_category` | null | - | Not used in the current cycle; no category table is locked for the current ratio definition |
| `stent_in_target_span` | boolean or intervals | - | Whether a metallic stent lies in the analyzed target span; if interval-based, export the stented subspan |
| `analyzability_reason` | enum or string | - | `ok`, `segmentation_failure`, `anatomically_too_small`, `artifact_exclusion`, `bifurcation_exclusion`, `stent_exclusion`, or equivalent project-defined reason |
| `qc_flags` | object | - | Continuity, calcification, stent, truncation, nesting, reader disagreement |
| `lv_mass_raw_g` | float or null | g | Raw CT-derived LV mass before calibration, when extractable |
| `lv_mass_g` | float or null | g | Calibrated LV mass when calibration has been applied |
| `lv_mass_state` | enum | - | `raw_ct`, `prior_slope`, `calibrated`, `manually_corrected`, `provisional`, or `missing` |

The important design choice is that missingness must be explicit. If outer-wall data are unavailable over part of the vessel, that absence should be exported as a flag or interval mask rather than hidden by silently copying the lumen profile.

The same applies to fallback logic: a reference profile supported by measured wall, a short-gap interpolation, and a population prior are not the same kind of evidence and should never be collapsed into one unlabeled `glagov` field.

The **authoritative machine-readable state** is the combination of `fallback_level`, `mla_support_mode`, and `glagov_primary_eligible`. The field `reference_mode` is only a coarse human-readable summary:

- `glagov_level0` means `fallback_level = 0`, `mla_support_mode = measured_wall`, and `glagov_primary_eligible = true`;
- `fallback_reference` means Level-1, Level-2, or explicit Level-3 sensitivity support is carried in the export, but primary Glagov eligibility remains false;
- `lumen_envelope` means no fallback reference support is being carried as the active export state.

For LV mass, the authoritative machine-readable state is `lv_mass_state` together with `lv_mass_raw_g`, `lv_mass_g`, and the myocardium QC flags. The primary rule is deliberately narrow: only `calibrated` and `manually_corrected` count as mass-ready for the primary 2x2 analysis. `prior_slope` remains available for explicitly labeled sensitivity analyses, while `raw_ct`, `provisional`, and `missing` never unlock primary mass-based models.

RI_Glagov follows the same rule. It is a valid exploratory export only when the MLA neighborhood is directly wall-supported. If the reference at the MLA comes from fallback support, the correct export is an explicit indeterminate state, not a guessed remodeling index.

If a run disables the remodeling biomarker entirely, export `ri_glagov = null` together with `ri_glagov_state = not_requested` rather than overloading the indeterminate states.

Stage-1 export should also be **phase-consistent**: one exported vessel object should come from one chosen reconstruction phase. If different subspans would require different phases to remain analyzable, emit separate candidate exports or a future interval-level extension rather than silently mixing phases inside one centerline and area profile.

Likewise, stage-1 `vessel_id` should not be misread as a territory object. The reduced-order model may still use dominance-adjusted fractions $f_v$, but explicit myocardium-to-vessel assignment remains a later extension rather than part of the current export contract.

# Mapping to `manuscript_v14.md`

The segmentation stages are intended to feed the manuscript phases and cohorts rather than define a separate programme:

| Segmentation stage | Main manuscript alignment |
|--------------------|---------------------------|
| **Stage A-B** | Mostly `manuscript_v14.md` Phase 1; supports Cohorts A and B |
| **Stage C** | Completes missing vessel spans for Phase 1 and supports manuscript Phase 3 fallback-hierarchy development; mainly Cohorts A and B |
| **Stage D** | Supplies LV mass for the mass-based models in Phase 2 and then carries forward into Phase 5 expansion; relevant to Cohorts A-C |
| **Stage E** | Optional Phase 4 method-comparison work; mainly Cohort B |
| **Stage F** | Handoff point into manuscript Phases 2-5 for whichever cohort is analyzable |

# Quality Control Requirements

Every segmentation route should be evaluated against the same practical QC requirements:

1. **Continuity**  
   No major gaps across the analyzable vessel span.

2. **Nested geometry**  
   Outer wall must remain outside the lumen.

3. **Taper plausibility**  
   No unphysical oscillation or abrupt radius jumps without an anatomical reason.

4. **Calcification handling**  
   Segments dominated by blooming should be flagged rather than silently accepted.

5. **Metallic stent handling**  
   Stented intervals must be flagged explicitly. This includes bifurcation or carina-crossing stents. If the in-stent lumen or the MLA neighborhood is not interpretable, or if suspected in-stent restenosis cannot be reviewed as a clearly single lumen, the vessel is not flow-ready for that span.

6. **Proximal/distal truncation**  
   The exported vessel span must still cover the proximal reference, lesion region, and distal interrogation segment. Early cut-off should be flagged because it shortens the effective flow path and can bias both the viscous integral and local reference reconstruction.

7. **Reader or method agreement**  
   Where repeat Medis reads or overlapping methods exist, compare geometry and derived areas.

8. **Flow analyzability**  
   The end product must be judged by whether it supports stable pressure-drop computation, not only by generic overlap metrics.

## Derived QC variables

For a technical workflow, the checklist above should be backed by explicit derived variables:

1. **Arc-length monotonicity**  
   Require

   $$
   s_{i+1} > s_i
   $$

   throughout the exported vessel.

2. **Nesting margin**  
   Where outer-wall data exist, define

   $$
   m_i = r_{\text{outer},i} - r_{\text{lum},i}.
   $$

   Negative or near-zero $m_i$ indicates contour crossing or wall collapse.

3. **Local area oscillation**

   $$
   o_i =
   \frac{|A_{i+1} - A_i|}
   {\max(A_i, A_{i+1}, \varepsilon)}.
   $$

   Large oscillations without an anatomical cause indicate slice-ordering problems, contour instability, or centerline misalignment.

4. **Curvature spike check**

   Let

   $$
   \Delta s_{i-1} = s_i - s_{i-1},
   \qquad
   \Delta s_i = s_{i+1} - s_i,
   \qquad
   \bar{\Delta s}_i = \frac{\Delta s_{i-1} + \Delta s_i}{2}.
   $$

   After approximately uniform resampling, a practical local check is

   $$
   \kappa_i
   \approx
   \frac{\lVert \mathbf{c}_{i+1} - 2\mathbf{c}_i + \mathbf{c}_{i-1} \rVert_2}
   {\bar{\Delta s}_i^2}.
   $$

   Abrupt spikes often indicate path leakage into a neighboring branch or a tracking failure near calcification.

5. **Stent-in-span indicator**

   Export a boolean or interval-valued flag whenever a metallic stent overlaps the analyzed vessel span. Stent presence alone is not an automatic exclusion, but any MLA or lesion measurement inside a stented interval requires explicit interpretability review and disables routine outer-wall use there.

6. **Reference-span coverage**

   If $s_{\text{MLA}}$ is the MLA position, then the export should satisfy

   $$
   s_{\text{MLA}} - L_{\text{prox,min}} \ge 0,
   \qquad
   s_N - s_{\text{MLA}} \ge L_{\text{dist,min}}
   $$

   for project-defined proximal and distal minimum spans. The default stage-1 values used in this reference are stated in the threshold table below, but the logic should remain explicit in the QC code even if the numbers are later changed.

7. **Method disagreement in hemodynamically relevant variables**

   Where repeat readers or alternative methods exist, compare not only mask overlap but also:

   - $\Delta A_{\text{MLA}} / A_{\text{MLA}}$;
   - shift in MLA position along $s$;
   - change in the discrete resistance integral $\sum \Delta s_i / A_i^2$;
   - change in exported analyzability status.

These variables are closer to what the CT-FFR model actually consumes than a global Dice coefficient.

8. **Minimum analyzable caliber**

   Define the local equivalent lumen diameter

   $$
   D_{\text{eq},i} = 2\sqrt{\frac{A_{\text{lum},i}}{\pi}}.
   $$

   If $D_{\text{eq},i}$ remains below the project floor over the MLA neighborhood or over most of the distal interrogation span, classify the vessel as anatomically too small for stage-1 analysis rather than as a segmentation failure.

## Stage-1 default QC thresholds

To prevent ad hoc threshold drift during implementation, the project should start from explicit stage-1 defaults. These are engineering defaults for Cohorts A-B, not claims of universal physiology.

| QC item | Stage-1 default threshold | Consequence |
|---------|---------------------------|-------------|
| Arc-length monotonicity | require $\Delta s_i > 0$ for all samples | Any violation is a hard fail for flow export |
| Resampled spacing / continuity | target spacing $\le 1.0$ mm, with no unresolved gap $> 2.0$ mm | Hard fail if violated after attempted completion |
| Proximal reference span | $L_{\text{prox,min}} \ge 5$ mm from MLA | Hard fail if violated |
| Distal interrogation span | $L_{\text{dist,min}} \ge 10$ mm from MLA | Hard fail if violated |
| Local area oscillation | $o_i \le 0.35$ on at least 90\% of non-bifurcation slices; no run of more than two adjacent slices with $o_i > 0.50$ | Manual review; fail if unresolved |
| Curvature spike | no isolated $\kappa_i > 5 \times$ the local 5-slice median outside bifurcation neighborhoods | Manual review; fail if consistent with branch jump or path leak |
| Severe blooming / motion burden | severe artifact on no more than 25\% of the lesion-plus-reference span; the MLA slice itself must not be severely obscured | Hard fail for lumen analysis if MLA is obscured; otherwise review |
| Stented target span | explicit flag required; if a stent overlaps the MLA or lesion span and lumen interpretability remains unclear on review, fail lumen export; disable Glagov mode in the stented interval | Reject vessel or force lumen-envelope / local exclusion |
| Minimum analyzable caliber | if equivalent lumen diameter is persistently $< 1.5$ mm over the MLA neighborhood or over most of the distal interrogation span, classify as anatomically too small / hypoplastic for stage 1 | Exclude from flow analysis, but do not count as segmentation failure |
| Outer-wall nesting margin | for Glagov use, require $m_i > 0$ on all trusted slices and median $m_i \ge 0.30$ mm | If violated, revert to lumen-envelope mode |
| Outer-wall coverage | trusted wall interval must cover MLA plus at least $\max(5 \text{ mm}, D_{\text{loc}})$ proximally and distally, excluding bifurcation neighborhoods | If violated, revert to lumen-envelope mode |
| Outer-wall artifact burden | severe blooming / motion on no more than 10\% of trusted wall slices | If violated, revert to lumen-envelope mode |
| Reader / method disagreement | review if $\lvert \Delta A_{\text{MLA}} \rvert / A_{\text{MLA}} > 15\%$, MLA shift $> 3$ mm, or resistance-integral change $> 10\%$ | Manual adjudication before export |
| LV mass plausibility | primary-ready calibrated mass (`calibrated` or `manually_corrected`) in the rough physiologic range 50-400 g and no major basal/apical leak flag | Manual correction or reject mass input |
| LV mass calibration quality | pilot calibrated-mass error no worse than about 15\% against the paired CT-CMR / expert-reference subset | If the paired calibration is not yet locked, keep the export at `prior_slope` or `provisional` and do not treat it as a primary quantitative input |

These thresholds should be exported in configuration, not buried in handwritten scripts, so that later sensitivity work can stress-test them explicitly.

Their origin should also be stated plainly: these numbers are conservative engineering defaults derived from prior DISCHARGE planning, expert CTA review practice, and a deliberate preference for false-negative analyzability over silent false-positive flow readiness. They are starting points for sensitivity analysis, not validated physiologic constants.

## MLA-neighborhood overrides

The global stage-1 QC defaults above are not sufficient on their own because the reduced-order model is most sensitive near the lesion throat. Section "Uncertainty Propagation and Sensitivity" shows explicitly that the viscous term weights slices by $1/A^2$, and the contraction term depends directly on $A_{\text{MLA}}$ and $A_{\text{ref,MLA}}$. Therefore the MLA micro-neighborhood should carry tighter defaults than the rest of the vessel.

For stage 1, define the MLA micro-neighborhood as the interval

$$
\mathcal{N}_{\text{MLA}}
=
\{\, i : |s_i - s_{\text{MLA}}| \le 2 \text{ mm} \,\},
$$

or, when the sampling is coarser, the nearest three non-bifurcation slices on each side of the MLA.

| MLA-neighborhood QC item | Tighter stage-1 default | Consequence |
|--------------------------|-------------------------|-------------|
| Continuity gap near MLA | no unresolved gap $> 1.0$ mm inside $\mathcal{N}_{\text{MLA}}$ | Hard fail for stage-1 flow export |
| Local area oscillation near MLA | require $o_i \le 0.15$ on at least 90\% of slices in $\mathcal{N}_{\text{MLA}}$; no single slice with $o_i > 0.25$ without manual confirmation | Manual review; fail if unresolved |
| Curvature / path instability near MLA | no isolated $\kappa_i > 3 \times$ the local 5-slice median and no smoothing step that shifts the centerline by more than about **0.5 mm** at the MLA neighborhood | Manual review; fail if consistent with branch jump or path leak |
| MLA area disagreement | review if repeated readers or methods produce $\lvert \Delta A_{\text{MLA}} \rvert / A_{\text{MLA}} > 10\%$ | Manual adjudication before export |

These tighter defaults are justified by the first-order sensitivity calculations later in the document: when a lesion-near slice carries weight $w_i \approx 0.30$–$0.60$, a 10\% lumen-area error already produces roughly a 6–12\% viscous-term error, and small MLA-area errors can change the contraction term much more dramatically. The MLA neighborhood should therefore be treated as a special QC zone rather than as just another vessel segment.

## Analyzability decision logic

The vessel-level decision should be explicit enough that different implementers return the same model eligibility class from the same QC record.

**Formal predicate notation.** Define the following vessel-level boolean predicates:

| Predicate | Definition |
|---|---|
| $\texttt{lum\_ok}$ | lumen profile passes all hard-exclusion and stage-1 QC thresholds |
| $\texttt{mass\_ok}$ | `lv_mass_state \in \{\texttt{calibrated}, \texttt{manually\_corrected}\}` and calibrated LV mass passes the plausibility gate ($M_\text{cal} \in [50, 400]$ g) with no unresolved major basal/apical leak flag |
| $\texttt{wall\_L0}$ | outer-wall trusted interval covers MLA, $\ell_\text{trust} \ge \max(5\text{ mm}, D_\text{loc})$ bilateral, $\le 10\%$ artefacted slices → Level-0 Glagov eligible |
| $\texttt{wall\_L12}$ | outer-wall data supports Level-1 or Level-2 fallback reference only; $\texttt{wall\_L0}$ false |
| $\texttt{excl}$ | any hard-exclusion criterion triggered |

Model eligibility is then the deterministic map:

$$
\text{eligible}(v) = \begin{cases}
\{\} & \text{if } \texttt{excl} \\
\{\texttt{L-CT-FFR}\} & \text{if } \texttt{lum\_ok} \land \lnot \texttt{mass\_ok} \land \lnot (\texttt{wall\_L0} \lor \texttt{wall\_L12}) \\
\{\texttt{L},\texttt{M}\} & \text{if } \texttt{lum\_ok} \land \texttt{mass\_ok} \land \lnot (\texttt{wall\_L0} \lor \texttt{wall\_L12}) \\
\{\texttt{L}\} & \text{if } \texttt{lum\_ok} \land \lnot \texttt{mass\_ok} \land \texttt{wall\_L12} \\
\{\texttt{L},\texttt{M}\} & \text{if } \texttt{lum\_ok} \land \texttt{mass\_ok} \land \texttt{wall\_L12} \\
\{\texttt{L},\texttt{G}\} & \text{if } \texttt{lum\_ok} \land \lnot \texttt{mass\_ok} \land \texttt{wall\_L0} \\
\{\texttt{L},\texttt{M},\texttt{G},\texttt{MG}\} & \text{if } \texttt{lum\_ok} \land \texttt{mass\_ok} \land \texttt{wall\_L0}
\end{cases}
$$

where $\texttt{L}$, $\texttt{M}$, $\texttt{G}$, $\texttt{MG}$ abbreviate the four CT-FFR variants. This map is total, deterministic, and implementable as a single decision function given the QC flags above. The verbal description below expands each case.

If `lv_mass_state = prior_slope`, the export may still support a downstream sensitivity analysis that temporarily enables mass-based models, but that must be labeled explicitly as a sensitivity branch and must not overwrite the authoritative primary eligibility derived from $\texttt{mass\_ok}$.

### Hard exclusion from stage-1 flow analysis

Reject the vessel for stage-1 CT-FFR ($\texttt{excl} = \text{true}$) if any of the following remains unresolved after attempted correction:

- non-monotone arc length;
- unresolved continuity gap greater than 2 mm in the target span;
- proximal reference span under 5 mm or distal span under 10 mm from the MLA;
- severe lumen obscuration at the MLA by motion, blooming, or branch overlap;
- metallic stent crossing the MLA or lesion span, including carina-crossing or bifurcation stents, when the lumen remains uninterpretable on review;
- suspected in-stent restenosis when the putative in-stent MLA cannot be reviewed as a clearly interpretable single lumen;
- persistent equivalent lumen diameter under about 1.5 mm over the MLA neighborhood or most of the distal interrogation span, in which case mark the vessel as anatomically too small rather than as a segmentation failure;
- MLA located inside a bifurcation neighborhood that is not clearly single-lumen on review.

### Model-eligibility classes after lumen QC

If the hard exclusion criteria are not triggered, then the allowed model variants should be assigned as follows:

| Condition | Eligible CT-FFR variants | Export consequence |
|-----------|--------------------------|--------------------|
| Lumen core passes, mass unavailable or not primary-ready (`missing`, `raw_ct`, or `provisional`), outer wall unavailable or unreliable | `L-CT-FFR` | `reference_mode = lumen_envelope` |
| Lumen core passes, primary-ready mass passes (`calibrated` or `manually_corrected`), outer wall unavailable or unreliable | `L-CT-FFR`, `M-CT-FFR` | `reference_mode = lumen_envelope` |
| Lumen core passes, Level-1 or Level-2 fallback reference available, mass unavailable or not primary-ready (`missing`, `raw_ct`, or `provisional`) | `L-CT-FFR` | `reference_mode = fallback_reference`, `fallback_level in {1,2}`, `glagov_primary_eligible = false` |
| Lumen core passes, Level-1 or Level-2 fallback reference available, primary-ready mass passes (`calibrated` or `manually_corrected`) | `L-CT-FFR`, `M-CT-FFR` | `reference_mode = fallback_reference`, `fallback_level in {1,2}`, `glagov_primary_eligible = false` |
| Lumen core passes, outer wall passes at Level 0, mass unavailable or not primary-ready (`missing`, `raw_ct`, or `provisional`) | `L-CT-FFR`, `G-CT-FFR` | `reference_mode = glagov_level0` |
| Lumen core passes, outer wall passes at Level 0, primary-ready mass passes (`calibrated` or `manually_corrected`) | `L-CT-FFR`, `M-CT-FFR`, `G-CT-FFR`, `MG-CT-FFR` | full export allowed with `reference_mode = glagov_level0` |

This makes one important point operational: lumen analyzability is the base gate. Outer-wall and mass QC only decide which branches of the 2×2 model family are eligible. Fallback-reference exports are scientifically useful and should be preserved explicitly, but they do **not** by themselves unlock primary `G-CT-FFR` or `MG-CT-FFR` eligibility.

`prior_slope` is intentionally absent from the primary table above: it is a sensitivity-grade state, not a primary-ready one.

### Bifurcation-specific rule

Bifurcation lesions need a slightly sharper rule than "detect and flag":

- if the MLA falls inside $\mathcal{N}_{\text{bif}}(\eta_{\text{bif}})$ and the slice is multi-lumen or branch-overlap dominated, exclude the vessel from stage-1 flow analysis;
- if only the reference span intersects $\mathcal{N}_{\text{bif}}(\eta_{\text{bif}})$, keep lumen analysis but exclude that neighborhood from reference estimation and outer-wall trust;
- if the takeoff neighborhood is adjacent but not dominant, analyze one branch path only and carry a bifurcation-review flag.

## Inter-reader and inter-method validation protocol

Where repeat Medis reads or alternative methods exist, the project should compare not only masks but also the hemodynamically relevant exported quantities. A practical stage-1 protocol is:

1. use all repeated cases, or at least **20 vessels** if more are available;
2. compare exact analyzability class agreement, not only geometric overlap;
3. report median and 90th-percentile differences for:
   - $\lvert \Delta A_{\text{MLA}} \rvert / A_{\text{MLA}}$,
   - MLA shift along $s$,
   - relative change in $\sum \Delta s_i / A_i^2$,
   - relative change in $A_{\text{ref,MLA}}$ when Glagov mode is used,
   - relative change in calibrated LV mass when myocardium outputs are compared;
4. trigger manual adjudication whenever analyzability class changes or any of the review thresholds in the QC table is crossed.

The goal is not to force perfect contour overlap. The goal is to ensure that reader or method variation does not silently move a vessel from one CT-FFR model class to another.

## Artifact-mitigation defaults

Failure modes should be paired with default responses rather than only named in prose:

| Failure mode | Default response |
|--------------|------------------|
| Motion blur across more than 3 consecutive slices | review reconstruction-phase metadata and reformat on the intended motion-stable phase if available; if the MLA neighborhood remains blurred, reject the vessel |
| Calcific blooming at the outer wall | allow lumen analysis if the lumen boundary is still interpretable; otherwise disable Glagov mode locally |
| Calcific blooming at the MLA lumen boundary | manual review first; if the throat contour remains ambiguous, reject the vessel |
| Metallic stent blooming / beam hardening | export a stent flag or interval; if the stent overlaps the lesion or MLA and lumen interpretability is not clear, reject the vessel and disable Glagov mode there |
| Bifurcation stent or carina-crossing stent | if no clearly single-lumen branch path remains outside the stented takeoff, reject the vessel for stage-1 CT-FFR rather than forcing a branch-specific MLA |
| Suspected in-stent restenosis | do not define CTA-derived MLA inside the stent unless the in-stent lumen is explicitly interpretable on review; otherwise exclude the vessel |
| Persistently subthreshold distal caliber | classify as anatomically too small / hypoplastic rather than as a segmentation failure |
| Branch jump in minimal path tracking | re-seed on the intended branch and enforce bifurcation-neighborhood exclusion |
| Basal or apical myocardium leak | manual correction or alternate myocardium model before mass export |

## Rough runtime expectations

Implementation planning is easier if the document states rough operational scale. For stage-1 work, realistic ballpark times are:

- Medis ingest plus automatic profile extraction: **under 1 minute** per vessel, plus **2-5 minutes** review time;
- CTA minimal-path completion plus contour refinement: typically **2-10 minutes** per vessel depending on manual reseeding and wall difficulty;
- LV myocardium inference: typically **under 1 minute on GPU** or **5-10 minutes on CPU**, plus **2-5 minutes** correction on failed cases.

These are planning numbers, not benchmarking claims, but they matter for staffing and review expectations.

# Uncertainty Propagation and Sensitivity

For this project, uncertainty should be propagated through the **geometric quantities that enter the reduced-order model**, not only through generic segmentation scores. The minimum useful perturbation analysis therefore tracks how errors in lumen area, outer-wall area, centerline position, and myocardium mass affect:

- the discrete viscous resistance integral $\sum \Delta s_i / A_i^2$;
- the MLA area $A_{\text{MLA}}$;
- the reference MLA area $A_{\text{ref,MLA}}$;
- the calibrated LV mass $M_{\text{cal}}$;
- the final CT-FFR value.

## First-order sensitivity of the viscous term

Using the discrete midpoint form

$$
\Delta P_{\text{visc}}
=
K_v \mu Q
\sum_{i=0}^{N-1}
\frac{\Delta s_i}{\bar{A}_i^2},
\qquad
\bar{A}_i = \frac{A_i + A_{i+1}}{2},
$$

the first-order derivative with respect to a midpoint area is

$$
\frac{\partial \Delta P_{\text{visc}}}{\partial \bar{A}_i}
=
-2 K_v \mu Q \frac{\Delta s_i}{\bar{A}_i^3}.
$$

So a small perturbation $\delta \bar{A}_i$ induces

$$
\delta \Delta P_{\text{visc}}
\approx
\sum_i
\frac{\partial \Delta P_{\text{visc}}}{\partial \bar{A}_i}
\delta \bar{A}_i.
$$

This makes the main numerical point explicit: the viscous term is most sensitive where $\bar{A}_i$ is small. Segmentation error in a narrow lesion throat is therefore much more important than the same absolute area error in a large proximal segment.

Define normalized resistance weights

$$
w_i =
\frac{\Delta s_i / \bar{A}_i^2}
{\sum_k \Delta s_k / \bar{A}_k^2}.
$$

Then the relative first-order error is approximately

$$
\frac{\delta \Delta P_{\text{visc}}}{\Delta P_{\text{visc}}}
\approx
-2 \sum_i w_i \frac{\delta \bar{A}_i}{\bar{A}_i}
+
\sum_i w_i \frac{\delta (\Delta s_i)}{\Delta s_i}.
$$

The first term captures contour error; the second captures centerline or truncation error through segment lengths.

## First-order sensitivity of the contraction term

For

$$
\Delta P_{\text{sep}}
=
K_i \frac{\rho}{2} Q^2
\left(
\frac{1}{A_{\text{MLA}}} - \frac{1}{A_{\text{ref,MLA}}}
\right)^2,
$$

let

$$
g =
\frac{1}{A_{\text{MLA}}} - \frac{1}{A_{\text{ref,MLA}}}.
$$

Then

$$
\frac{\partial \Delta P_{\text{sep}}}{\partial A_{\text{MLA}}}
=
-K_i \rho Q^2 \frac{g}{A_{\text{MLA}}^2},
\qquad
\frac{\partial \Delta P_{\text{sep}}}{\partial A_{\text{ref,MLA}}}
=
K_i \rho Q^2 \frac{g}{A_{\text{ref,MLA}}^2}.
$$

This is the main reason local outer-wall error matters even if the full outer-wall profile is not used everywhere: once the vessel is run in Glagov mode, the reconstructed reference area at the MLA enters the contraction loss directly.

## Illustrative scale of segmentation-driven error

The first-order formulas above are useful, but implementers usually need one or two concrete numbers.

1. **Viscous-term illustration**  
   If a lesion-near slice contributes weight $w_i = 0.30$ in the discrete resistance integral, then a 10\% lumen-area underestimation at that slice gives

   $$
   \frac{\delta \Delta P_{\text{visc}}}{\Delta P_{\text{visc}}}
   \approx
   -2 w_i \frac{\delta \bar{A}_i}{\bar{A}_i}
   =
   -2(0.30)(-0.10)
   \approx 0.06,
   $$

   i.e. roughly a **6\%** increase in the viscous term. If the same slice carries $w_i = 0.60$, the same 10\% area error gives roughly a **12\%** increase.

2. **Contraction-term illustration**  
   If $A_{\text{MLA}} = 2.0$ mm$^2$ and $A_{\text{ref,MLA}} = 6.0$ mm$^2$, then

   $$
   g = \frac{1}{2.0} - \frac{1}{6.0} = 0.333 \;\text{mm}^{-2}.
   $$

   If the MLA area is overestimated by only 0.5 mm$^2$, then

   $$
   g' = \frac{1}{2.5} - \frac{1}{6.0} = 0.233 \;\text{mm}^{-2},
   $$

   so the contraction term scales by approximately

   $$
   \left(\frac{g'}{g}\right)^2 \approx 0.49,
   $$

   i.e. about a **50\%** reduction. The same absolute 0.5 mm$^2$ error in the reference area changes the contraction term much less. This is why the MLA contour is the single most sensitive local geometric quantity.

3. **Mass-flow illustration**  
   In the primary linear model, a 10\% calibrated-mass error produces a 10\% flow error in every vessel fed by that global mass estimate. The error is therefore global in sign, but not uniform in downstream CT-FFR impact because larger territories carry larger absolute flow changes.

## Sensitivity of the mass-based flow term

For the primary linear demand model,

$$
Q_{\text{rest},v} = q_{\text{rest}} f_v M_{\text{cal}},
\qquad
Q_{\text{hyp},v} = H Q_{\text{rest},v},
$$

so

$$
\frac{\delta Q_{\text{rest},v}}{Q_{\text{rest},v}}
=
\frac{\delta M_{\text{cal}}}{M_{\text{cal}}}
+
\frac{\delta f_v}{f_v}
+
\frac{\delta q_{\text{rest}}}{q_{\text{rest}}}.
$$

If $q_{\text{rest}}$ and $f_v$ are fixed in a given analysis, then the dominant segmentation-driven term is simply

$$
\frac{\delta Q_{\text{rest},v}}{Q_{\text{rest},v}}
=
\frac{\delta M_{\text{cal}}}{M_{\text{cal}}}.
$$

For the allometric sensitivity model,

$$
Q_{\text{rest},v}(\gamma)
=
q_{\text{rest}} M_{\text{ref},v}
\left(\frac{M_v}{M_{\text{ref},v}}\right)^\gamma,
$$

with $M_{\text{ref},v} = f_v M_{\text{ref,cal}}$ and $M_{\text{ref,cal}} = 250$ g in the primary stage-1 sensitivity branch,

the corresponding first-order relation is

$$
\frac{\delta Q_{\text{rest},v}}{Q_{\text{rest},v}}
\approx
\gamma \frac{\delta M_v}{M_v}
\quad
\text{if } q_{\text{rest}} \text{ and } M_{\text{ref},v} \text{ are held fixed}.
$$

So mass segmentation error is attenuated slightly when $\gamma < 1$, but it is never irrelevant.

## Practical uncertainty model

For implementation, the most useful uncertainty model is not independent white noise on every sample. A better approximation is:

1. **lumen contour perturbation** as smooth radial perturbations along $\theta$ and correlated perturbations along $s$;
2. **outer-wall perturbation** as lower-frequency radial perturbations with nesting preserved;
3. **centerline perturbation** as small orthogonal displacements that rotate the local cross-sectional plane;
4. **mass perturbation** as a scalar error on $M_{\text{CT}}$ plus uncertainty in the calibration map $(a,b)$.

The recommended propagation route is Monte Carlo:

$$
\{\text{geometry}, M_{\text{cal}}\}
\rightarrow
\{\Delta P_{\text{visc}}, \Delta P_{\text{sep}}, Q\}
\rightarrow
\text{CT-FFR}.
$$

For each vessel, the reportable uncertainty outputs should include at least:

- median CT-FFR;
- 5th and 95th percentile CT-FFR;
- perturbation-driven change in $A_{\text{MLA}}$;
- perturbation-driven change in $\sum \Delta s_i/A_i^2$;
- analyzability failure rate under perturbation.

# Claims That Are Safe To Use In The Manuscript And Proposal

The following claims are consistent with the current evidence base:

- partial Medis lumen and vessel-wall segmentations already exist and are useful seed data;
- additional segmentation harmonization and completion work is required before consistent flow derivation;
- development-phase CT-FFR can proceed on analyzable target-vessel segments rather than requiring a complete tree for every patient;
- LV myocardium segmentation is feasible and likely less difficult than reliable coronary outer-wall completion;
- SAM-Med3D is worth evaluating as an optional research tool, but it is not yet proven as a stand-alone solution for coronary CTA outer-wall segmentation.

The following claims should be avoided:

- that the full DISCHARGE CT cohort is already flow-ready;
- that coronary outer-wall segmentation in CCTA is solved;
- that inter-reader agreement on coronary outer-wall contours has already been validated to clinical standard for the DISCHARGE cohort specifically;
- that SAM-Med3D already has coronary CTA-specific evidence equivalent to task-specific models;
- that a deployment-grade browser platform is required for the core CT-FFR research aims.

# Conclusion

The segmentation problem for this project is manageable if it is framed correctly.

The right framing is:

- use existing Medis contours as partial seed geometry;
- build a classical coronary completion and QC package around CTA;
- obtain LV myocardium mass with a dedicated but simpler segmentation workflow;
- evaluate SAM-Med3D as an optional research enhancement, not as the primary assumption.

This keeps the segmentation strategy aligned with `manuscript_v14.md` and `proposal_v11.md`: conservative, staged, and centered on what is actually required for flow derivation.

# Appendix A: Implementation Skeletons

The purpose of this appendix is not to prescribe software architecture. It is to make the computational contract concrete enough that a programmer can implement the geometry pipeline without guessing what the document means operationally.

All code blocks in this appendix are **pseudocode skeletons**, not a locked production API. Helper names such as `project_ring_to_local_plane`, `solve_lumen_path`, or `distal_span_ok` stand for the earlier-defined geometric and QC operations and are intended to make the handoff logic explicit rather than to dictate exact function signatures.

## A1. Vessel export from contour rings

```python
def export_vessel_from_rings(rings):
    # rings: ordered lumen/outer rings with world coordinates
    # ring.plane should encode the local slice plane from the source export
    vessel = []
    for ring in rings:
        if ring.plane is None or len(ring.lumen_points) < 3:
            continue

        lumen_xy = project_ring_to_local_plane(ring.lumen_points, ring.plane)
        if is_self_intersecting(lumen_xy) or polygon_area(lumen_xy) <= 0:
            continue

        lumen_area = polygon_area(lumen_xy)
        lumen_centroid = polygon_centroid(lumen_xy)

        if ring.outer_points is not None:
            outer_xy = project_ring_to_local_plane(ring.outer_points, ring.plane)
            outer_area = polygon_area(outer_xy) if len(outer_xy) >= 3 else None
        else:
            outer_area = None

        vessel.append({
            "centroid_xyz": lift_to_world(lumen_centroid, ring.plane),
            "A_lum_mm2": lumen_area,
            "A_outer_mm2": outer_area,
        })

    vessel = sort_proximal_to_distal(vessel)
    vessel = smooth_centerline(
        vessel,
        method="savitzky_golay",
        window=7,
        polyorder=3,
    )
    vessel = add_arc_length(vessel)
    vessel = add_mla_index(vessel)
    return vessel
```

This is the minimal path from contour data to the ordered vessel object consumed downstream.

## A2. CTA completion by minimal path plus contour refinement

```python
def complete_vessel_from_ct(volume, start_xyz, end_xyz):
    volume_iso = resample_isotropic(volume)
    vesselness = compute_frangi(volume_iso)
    cost = np.exp(-alpha * vesselness)

    centerline = minimal_path(cost, start_xyz, end_xyz)
    centerline = resample_centerline(centerline, ds_mm=0.5)

    for _ in range(3):
        slices = []
        for point in centerline:
            frame = make_bishop_frame(centerline, point)
            patch = sample_cross_section(volume_iso, frame, size=64, spacing_mm=0.2)
            polar = to_polar(patch)

            # Dynamic-programming search in the polar cost field.
            lumen_r = solve_lumen_path(
                polar,
                lambda_1=0.5,
                lambda_2=0.25,
            )
            outer_r = solve_outer_path(
                polar,
                lumen_r,
                delta_nest_mm=0.05,
                lambda_3=0.75,
                lambda_4=0.35,
            )

            slices.append({
                "frame": frame,
                "lumen_contour": polar_to_world(lumen_r, frame),
                "outer_contour": polar_to_world(outer_r, frame) if outer_r is not None else None,
            })

        refined, shift_stats = refine_centerline_from_lumen_centroids(
            centerline,
            slices,
        )
        centerline = refined
        if shift_stats["median_mm"] < 0.10 and shift_stats["max_mm"] < 0.25:
            break

    return export_vessel_from_slices(refined, slices)
```

The operational sequence is deliberate: minimal path first, local contouring second, centerline refinement third.

## A3. LV mass extraction and calibration

```python
def export_lv_mass(mask, voxel_volume_ml, calibration=None, manually_corrected=False):
    # mask: binary LV myocardium mask
    # calibration: cohort-wide paired CT-CMR calibration map using slope-only Deming
    # as the stage-1 default; optional intercept only if the paired subset justifies it
    # if only an interim prior slope is available, export state prior_slope
    rho_myo_g_per_ml = 1.05
    phys_mass_range_g = (50.0, 400.0)

    if mask is None:
        return {
            "lv_mass_raw_g": None,
            "lv_mass_g": None,
            "lv_mass_state": "missing",
            "qc_flags": {
                "basal_plane_ok": None,
                "apical_limit_ok": None,
                "basal_leak": None,
                "apical_leak": None,
                "phys_range_ok": None,
            },
        }

    V_myo_ml = mask.sum() * voxel_volume_ml
    M_ct_g = rho_myo_g_per_ml * V_myo_ml
    M_cal_g = None
    lv_mass_state = "raw_ct"

    if calibration is not None:
        if calibration["mode"] == "slope_only":
            M_cal_g = calibration["b"] * M_ct_g
        else:
            M_cal_g = calibration["a"] + calibration["b"] * M_ct_g

        if calibration.get("source") == "prior_slope":
            lv_mass_state = "prior_slope"
        else:
            lv_mass_state = "manually_corrected" if manually_corrected else "calibrated"

    qc = {
        "basal_plane_ok": basal_plane_identified(mask),
        "apical_limit_ok": apical_limit_identified(mask),
        "basal_leak": detect_basal_leak(mask),
        "apical_leak": detect_apical_leak(mask),
        "phys_range_ok": (
            M_cal_g is not None
            and phys_mass_range_g[0] <= M_cal_g <= phys_mass_range_g[1]
        ),
    }

    if M_cal_g is not None and (
        not qc["phys_range_ok"] or qc["basal_leak"] or qc["apical_leak"]
    ):
        lv_mass_state = "provisional"

    return {
        "lv_mass_raw_g": M_ct_g,
        "lv_mass_g": M_cal_g,
        "lv_mass_state": lv_mass_state,
        "qc_flags": qc,
    }
```

The key requirement is to export raw and calibrated mass together whenever calibration exists, because later analyses may need to audit the calibration step directly. In the semi-automatic pathway, the corrected mask should replace the raw automatic mask only after the correction step is recorded and `lv_mass_state` is updated accordingly.

## A4. Hemodynamic QC-oriented analyzability gate

```python
def compute_resistance_integral(s_mm, A_lum_mm2):
    A_bar = 0.5 * (A_lum_mm2[:-1] + A_lum_mm2[1:])
    ds = np.diff(s_mm)
    return np.sum(ds / A_bar**2)


def summarize_reference_support(vessel, qc):
    if all([
        qc["nested_ok"] is True,
        qc["outer_plausible"] is True,
        qc["outer_coverage_ok"] is True,
    ]):
        return {
            "reference_mode": "glagov_level0",
            "fallback_level": 0,
            "fallback_reason": None,
            "mla_support_mode": "measured_wall",
            "mla_support_span_mm": measured_wall_span_mm(vessel),
            "glagov_primary_eligible": True,
        }

    if local_reference_fallback_ok(vessel, qc):
        return {
            "reference_mode": "fallback_reference",
            "fallback_level": 1,
            "fallback_reason": classify_fallback_reason(vessel, qc),
            "mla_support_mode": "local_reconstruction",
            "mla_support_span_mm": fallback_support_span_mm(vessel, level=1),
            "glagov_primary_eligible": False,
        }

    if taper_prior_ok(vessel, qc):
        return {
            "reference_mode": "fallback_reference",
            "fallback_level": 2,
            "fallback_reason": classify_fallback_reason(vessel, qc),
            "mla_support_mode": "taper_prior",
            "mla_support_span_mm": fallback_support_span_mm(vessel, level=2),
            "glagov_primary_eligible": False,
        }

    if population_prior_exported(vessel):
        return {
            "reference_mode": "fallback_reference",
            "fallback_level": 3,
            "fallback_reason": classify_fallback_reason(vessel, qc),
            "mla_support_mode": "population_prior",
            "mla_support_span_mm": fallback_support_span_mm(vessel, level=3),
            "glagov_primary_eligible": False,
        }

    return {
        "reference_mode": "lumen_envelope",
        "fallback_level": None,
        "fallback_reason": classify_fallback_reason(vessel, qc),
        "mla_support_mode": "lumen_envelope",
        "mla_support_span_mm": None,
        "glagov_primary_eligible": False,
    }


def assess_flow_analyzability(vessel):
    qc = {}
    qc["arc_length_monotone"] = np.all(np.diff(vessel["s_mm"]) > 0)
    qc["has_distal_span"] = distal_span_ok(vessel)
    qc["has_proximal_span"] = proximal_span_ok(vessel)
    qc["no_large_gaps"] = continuity_ok(vessel)
    qc["oscillation_ok"] = local_area_oscillation_ok(vessel["A_lum_mm2"])
    qc["mla_not_obscured"] = mla_slice_visible(vessel)
    qc["outside_unresolved_bifurcation"] = bifurcation_gate_ok(vessel)
    qc["minimum_caliber_ok"] = minimum_caliber_ok(vessel)
    qc["stent_in_target_span"] = bool(vessel.get("stent_in_target_span", False))
    qc["stent_ok"] = stent_gate_ok(vessel)

    if vessel["A_outer_mm2"] is not None and not qc["stent_in_target_span"]:
        qc["nested_ok"] = nesting_ok(vessel["A_lum_mm2"], vessel["A_outer_mm2"])
        qc["outer_plausible"] = outer_wall_plausibility_ok(vessel)
        qc["outer_coverage_ok"] = outer_wall_coverage_ok(vessel)
    else:
        qc["nested_ok"] = None
        qc["outer_plausible"] = None
        qc["outer_coverage_ok"] = None

    resistance_integral = compute_resistance_integral(
        vessel["s_mm"], vessel["A_lum_mm2"]
    )

    lumen_core_ok = all([
        qc["arc_length_monotone"],
        qc["has_distal_span"],
        qc["has_proximal_span"],
        qc["no_large_gaps"],
        qc["oscillation_ok"],
        qc["mla_not_obscured"],
        qc["outside_unresolved_bifurcation"],
        qc["minimum_caliber_ok"],
        qc["stent_ok"],
    ])

    reference_state = (
        summarize_reference_support(vessel, qc)
        if lumen_core_ok
        else {
            "reference_mode": "lumen_envelope",
            "fallback_level": None,
            "fallback_reason": "lumen_core_failed",
            "mla_support_mode": "lumen_envelope",
            "mla_support_span_mm": None,
            "glagov_primary_eligible": False,
        }
    )

    glagov_ok = lumen_core_ok and reference_state["glagov_primary_eligible"]

    mass_ok = vessel.get("lv_mass_state") in {"calibrated", "manually_corrected"}

    hard_fail_reasons = [
        name
        for name in [
            "arc_length_monotone",
            "has_distal_span",
            "has_proximal_span",
            "no_large_gaps",
            "oscillation_ok",
            "mla_not_obscured",
            "outside_unresolved_bifurcation",
            "minimum_caliber_ok",
            "stent_ok",
        ]
        if qc[name] is not True
    ]

    vessel["qc_flags"] = qc
    vessel["rejection_reasons"] = hard_fail_reasons
    vessel["analyzability_reason"] = (
        "ok" if lumen_core_ok else classify_analyzability_reason(hard_fail_reasons, vessel)
    )
    vessel["resistance_integral"] = resistance_integral
    vessel["flow_analyzable"] = lumen_core_ok
    vessel["reference_mode"] = reference_state["reference_mode"]
    vessel["fallback_level"] = reference_state["fallback_level"]
    vessel["fallback_reason"] = reference_state["fallback_reason"]
    vessel["mla_support_mode"] = reference_state["mla_support_mode"]
    vessel["mla_support_span_mm"] = reference_state["mla_support_span_mm"]
    vessel["glagov_primary_eligible"] = reference_state["glagov_primary_eligible"]
    vessel["ri_glagov_state"] = (
        "computed"
        if glagov_ok and vessel.get("ri_glagov") is not None
        else "indeterminate_fallback"
        if reference_state["mla_support_mode"] in {
            "local_reconstruction",
            "taper_prior",
            "population_prior",
        }
        else "indeterminate_no_wall"
    )
    eligible_models = []
    if lumen_core_ok:
        eligible_models.append("L-CT-FFR")
        if mass_ok:
            eligible_models.append("M-CT-FFR")
        if glagov_ok:
            eligible_models.append("G-CT-FFR")
        if glagov_ok and mass_ok:
            eligible_models.append("MG-CT-FFR")
    vessel["eligible_models"] = eligible_models
    return vessel
```

This makes explicit that analyzability is not a visual label. It is a computational decision about whether the exported vessel can support stable pressure-drop evaluation.

# Mathematical Open Problems for Geometry Collaboration

This section poses four precise mathematical questions that arise directly from the CT-FFR geometry problem and are well suited to a collaboration with researchers in differential geometry, geometric statistics, or shape analysis. They are not engineering tasks; they are theoretical questions whose answers would materially improve the methodological foundation of the project.

---

**P1. Optimal curvature estimation from noisy arc-length samples.**

Given $N$ discrete centerline points $\{\mathbf{c}_i\}_{i=0}^N$ sampled from a $C^2$ curve with sub-voxel positional noise $\sigma \approx 0.3$–$0.5$ mm, what is the minimax-optimal estimator of curvature $\kappa(s)$ and what is its convergence rate in $N$? Standard finite-difference estimators have $O(h^2)$ discretization error and are sensitive to noise amplification at the second-difference order. Kernel-smoothed estimators [@antiga2008] have tuning parameters whose optimal choice depends on the unknown signal-to-noise ratio. A theory for optimal bandwidth selection in this specific vascular context — where curvature enters both the torsion descriptor computation and the slice orientation — is missing from the literature. A minimax bound would also clarify when reported coronary curvature differences between observers are resolution-limited versus biologically meaningful.

---

**P2. Nested-surface registration as a constrained problem on a shape manifold.**

The lumen-outer-wall pair $(S_\text{lum}, S_\text{outer})$ must satisfy the nesting constraint $r_\text{outer}(s,\theta) > r_\text{lum}(s,\theta)$ everywhere. Inter-patient registration or atlas construction of coronary vessel geometry therefore faces a constrained optimization problem: find a diffeomorphism $\phi$ of the ambient 3D space such that $\phi$ maps one nested-surface pair to another while preserving the nesting order. Standard diffeomorphic registration frameworks (LDDMM, SyN) do not enforce surface nesting as a hard constraint. Is there a well-posed variational formulation of nested-surface atlas estimation on the space $\mathcal{M}_\text{nested} = \{(S_\text{lum}, S_\text{outer}) : r_\text{outer} > r_\text{lum}\}$? What metric on $\mathcal{M}_\text{nested}$ is appropriate for atlas-based reference reconstruction?

---

**P3. Reference taper reconstruction as a variational problem under monotonicity and nestedness constraints.**

Given observed outer-wall radii $\{r_{\text{outer},i}\}$ on a trusted interval $\mathcal{I}_\text{trusted}$ and observed lumen radii $\{r_{\text{lum},i}\}$ on the full vessel span, the Glagov reference reconstruction problem can be stated as:

$$
\hat{r}_\text{ref} = \arg\min_{f \in \mathcal{F}_\text{taper}} \sum_{i \in \mathcal{I}_\text{trusted}} \bigl(f(s_i) - (r_{\text{outer},i} - T_{\text{healthy}})\bigr)^2 + \lambda \int \bigl(f''(s)\bigr)^2 ds,
$$

subject to $f(s) \ge (1+\varepsilon)\,r_\text{lum}(s)$ for all $s$. This is an isotonic regression problem with a smoothness penalty and a pointwise inequality constraint. What is the structure of the solution, and in particular: does the optimal solution exhibit the same characteristic "flat then increasing" structure as unconstrained isotonic regression, or does the interaction with the smoothness penalty change the contact structure? What is the effect of the $\varepsilon$-dependent floor constraint on the bias of $\hat{r}_\text{ref}$ at the MLA site, which is where the constraint is most likely to be active?

---

**P4. Geometric taxonomy of coronary tree topologies and its metric structure.**

The coronary graph $\mathcal{G} = (\mathcal{V}, \mathcal{E})$ varies in topology across patients: right-dominant, left-dominant, co-dominant, and anomalous configurations create different numbers and arrangements of branches. Inter-patient comparison of CT-FFR outputs — or atlas-based analysis — requires a meaningful distance between coronary tree topologies. Labeled tree edit distance is well-studied for combinatorial trees, but coronary graphs are embedded in 3D with spatially structured branch lengths, calibers, and territory associations. Is there a metric on the space of embedded, labeled, metric coronary graphs that:
1. can be computed in polynomial time for graphs of realistic coronary complexity (8–15 named branches);
2. respects the hemodynamic ordering (proximal branches upstream of distal);
3. reduces to a meaningful continuous distance when only branch calibers or territory fractions change, not topology?

Such a metric would enable principled cohort stratification by coronary anatomy, atlas-guided reference reconstruction, and topologically-aware population normalization of CT-FFR outputs.
