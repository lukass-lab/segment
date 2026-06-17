---
title: "CCTA-First Coronary Tree Construction"
subtitle: "Learned tree extraction, topology priors, and coupled wall geometry with geodesic routing as a repair layer"
author: "Vessel Team"
date: 2026-06-17
---

# Purpose And Thesis

This document defines a CCTA-first strategy for building a coupled inner/outer wall coronary graph: a labeled vessel tree whose local state is not just a centerline or mask, but paired lumen and outer-wall geometry suitable for plaque phenotyping, CT-QFR/CT-FFR-style analysis, curvature, bifurcation descriptors, and longitudinal shape comparison.

Tree construction is the first structural bottleneck in that program. If the tree is broken, branch-swapped, or anatomically implausible, every downstream quantity becomes unstable: minimum lumen area, reference diameter, bifurcation exclusion, branch-level plaque burden, flow allocation, and wall-shape correspondence.

The central task is:

> Given a CCTA volume, detect and segment the coronary tree, then refine lumen, wall, plaque, labels, and QC using researcher-refined AutoPlaque/APQ-derived masks or expert annotations as secondary evidence.

The thesis is:

> Make the CCTA-derived coronary graph the primary object. Use learned segmentation and graph construction as the main engine, use researcher-refined AutoPlaque/APQ-derived masks as partial teacher/refinement/QC data, and reserve geodesic cost maps for constrained centerline routing, gap repair, and audit.

# Why Tree Construction Is Hard

Coronary tree construction couples topology, image evidence, and geometry:

- thin distal vessels are close to the CCTA resolution limit;
- blooming calcium, stents, veins, motion, and low contrast distort vessel evidence;
- centerlines can jump branches near bifurcations or parallel vessels;
- lumen-centroid centerlines are biased in eccentric plaque and positive remodeling;
- ostium and distal endpoint detection are separate failure modes;
- DISCHARGE-style trial data are multi-site, multi-scanner, and multi-protocol, so domain shift is a primary model-risk rather than a nuisance variable;
- researcher-refined AutoPlaque/APQ-derived masks are usually lesion-centered partial labels, not full-tree labels, so unlabeled visible vessels must not be treated as background during training;
- Dice can look acceptable while connectivity, HD95, branch assignment, or local diameter profiles are wrong;
- native coronaries are usually trees, but bypass grafts, anomalous anatomy, collaterals, fistulae, and anastomoses require explicit provenance rather than forced simplification.

The evaluation problem is as important as the extraction problem. Thin-vessel pipelines need boundary-distance, connectivity, branch-label, topology, and physiology-facing metrics, not only voxel overlap. Regional Hausdorff losses and differentiable morphology-like operators are useful references for moving beyond plain Dice [@guzzi2026regionalhd; @guzzi2024softmorph].

# Target Object

For this project, tree construction is not merely skeletonization. It is the process that turns the source CCTA volume, learned vessel probabilities, and derived annotation evidence into an explicit rooted coronary graph:

- nodes: ostia, bifurcations, branch endpoints, optional cross-section stations;
- edges: branch segments with ordered centerline samples;
- labels: LM, LAD, LCx, RCA, diagonal, obtuse marginal, septal, PDA/PLB, etc.;
- geometry: centerline, tangent, rotation-minimizing frame, lumen radius/area, outer-wall contour where available;
- topology: parent-child relation, branch order, graph distance, bifurcation neighborhoods;
- QC: gap flags, low-radius flags, branch-jump flags, disconnected components, artifact intervals, confidence/provenance.

The graph is the contract between segmentation and interpretation. The primary source should be the CCTA volume and the model-derived tree. Researcher-refined AutoPlaque/APQ-derived masks are valuable secondary evidence for refinement, validation, and teacher supervision, but they are derived from the same imaging study and should not be framed as an independent input modality or as the initial tree definition.

The practical implementation stance is therefore:

- coronary segmentation must recover lumen, outer wall, topology, labels, and branch geometry, because downstream physiology and plaque analysis are topology-sensitive;
- the first implementation should remain lightweight and auditable: distance transform inside the lumen mask, fast marching, physical-space backtracking, smoothing, arc-length resampling, and validation;
- cardiac-structure segmentation should be used as a localization prior: crop to the heart and aortic root, then use a generous epicardial/periaortic search region before dedicated coronary extraction [@wasserthal2023totalsegmentator; @zhuang2019mmwhs; @bruns2022wholeheart].

## Current Data Reality And Optional Validation Assets

The project should not assume that a harmonized full-tree coronary segmentation dataset already exists across all DISCHARGE cases. The current assets are powerful but uneven:

- source CCTA volumes are the base data;
- researcher-refined AutoPlaque/APQ-derived masks provide lesion-centered lumen/wall/plaque evidence for analyzed segments;
- MEDIS/QAngio CT exports, where available, provide optional expert lumen and vessel-wall contour rings in physical coordinates for legacy/prototype validation checks [@medis2024; @reiber2010];
- branch labels, vendor centerlines/CPR paths, and full-tree review status must be inventoried rather than assumed.

MEDIS contour rings are not an active dependency of the default pipeline. If available, they can serve as optional target-vessel validation evidence for centerline checks, lumen/wall contour geometry, frame and CPR/MPR validation, and reader-reproducibility work. They should not be treated as the project’s main input format, and they do not solve full-tree topology, distal branch coverage, or graft/collateral/anomaly handling.

The mask or contour set is not the clinical read. The tree is useful because it carries the CCTA into perpendicular cross-sections, straightened MPR/CPR views, lumen-area profiles, MLA localization, plaque/wall summaries, and downstream flow or plaque phenotyping.

# Approach Landscape

The relevant decision is not which single paper to reproduce. It is which method family should own each part of a CCTA-first coronary pipeline, given that the project has DISCHARGE data, additional local CCTA studies, and many researcher-refined masks originally generated by AutoPlaque/APQ from those CCTA studies. Those masks are a major asset, but they are often lesion-centered and tied to the analyzed vendor CPR/centerline convention rather than complete full-tree annotations. They can act as partial teacher labels, segment-level refinement targets, and QC comparators, while still being treated as silver-standard derived annotations rather than independent ground truth.

## Classical Vesselness And Geodesic Routing

Classical vesselness plus minimum-cost paths treats the coronary as a low-cost tube in the CCTA volume [@frangi1998; @metz2009]. Given a vesselness or learned probability map $V(x)$, a common traversal cost is:

$$
C(x) = \frac{1}{\varepsilon + V(x)}
\quad \text{or} \quad
C(x)=\exp(-\alpha V(x)).
$$

For mask-derived centerlines, the cost can come from the lumen distance transform:

$$
d(x) = \mathrm{dist}(x, \partial M_{\mathrm{lumen}}),
\qquad
P(x) = \frac{1}{d(x) + \varepsilon}.
$$

This is useful for deterministic baselines, centerlines from masks, interactive correction, and short-gap repair. It is brittle as the primary strategy in exactly the hard coronary cases: calcium blooming, stents, motion, low contrast, veins, bifurcations, and distal vessels. It also cannot infer plaque, wall geometry, or branch labels by itself.

## Connectivity-First Geodesic Graphs

Connectivity-first geodesic methods make the tree objective explicit: build candidate geodesic paths, preserve an over-connected graph, then prune to a plausible vascular tree [@moriconi2017vtrails; @moriconi2019geodesicmst]. The useful idea is the intermediate over-connected graph: it preserves multiple possible connections before a final decision is made.

The limitation is forcing a single minimum-spanning or acyclic answer too early. In coronary CTA, spatially close branches, bifurcations, calcified segments, and motion artifacts can create plausible but false shortcuts. These methods are therefore strong candidate-topology generators and baselines, not the final authority.

## Tube And Surface Geometric Models

Tube-model and surface-derived approaches represent vessels as centerlines plus radii, lumen surfaces, or maximal-inscribed spheres [@mohan2009tubular; @antiga2008]. They are valuable because they make branch geometry explicit rather than leaving it hidden in a voxel mask.

For this project, they are strongest after a lumen or vessel mask already exists. They can provide centerline extraction, radius profiles, geometric sanity checks, and comparison against the learned pipeline. Their weakness is that simplified tube assumptions are not enough for coronary plaque. Eccentric plaque, positive remodeling, bifurcation asymmetry, and outer-wall uncertainty require a richer paired lumen/outer-wall representation.

## Learned CCTA Segmentation And Reconnection

A learned CCTA-first model should be the main direction because this project has the data to support it. Coronary-specific work already points toward segmentation followed by explicit topology repair rather than segmentation alone [@qiu2025]. The model can learn CCTA-to-lumen, CCTA-to-vessel, CCTA-to-wall/plaque-support, and CCTA-to-centerline probability maps. Researcher-refined AutoPlaque/APQ-derived masks can supervise difficult boundaries, calibrate uncertainty, and expose systematic disagreements between raw CCTA evidence and derived contour annotations.

This is the approach that best uses DISCHARGE and the local curated masks: learned image evidence first, explicit graph construction second, repair and refinement third.

## Graph Refinement And Anatomical Labeling

Once a candidate tree exists, graph learning and anatomical rules can refine false positives, resolve branch labels, and flag implausible topology [@hampe2024]. This layer should produce label probabilities, pruning confidence, conflict flags, and review targets rather than silently overwriting geometry.

The right prior is a typed graph grammar rather than one rigid atlas. The normal coronary backbone is small enough to enumerate by configuration switches, especially dominance and left-main termination. Side branches are variable-count typed slots with allowed parents: diagonals from LAD, obtuse marginals from LCx, septals from LAD, acute marginals from RCA, and so on. Rare anomalies and acquired non-tree structures need an explicit escape rather than forced relabeling.

The modern ZIB/von Tycowicz line strengthens this layer. Manifold-valued graph learning supports geometric node/edge states [@hanik2024manifoldgcn]. Varifold-distance machinery, developed for single-cell trajectory-tree inference but methodologically transferable, supports topology-flexible comparison of branching structures [@maignant2025varifoldtree]. Manifold-valued hypergraphs are a natural fit for bifurcations, which are higher-order parent-plus-daughters junctions rather than independent pairwise edges [@stokke2025hypergraphs].

## Vendor-Mask Refinement And Human-Curated Teacher Data

The strongest project-specific asset is the pairing of source CCTA volumes with many researcher-refined segmentation masks originally generated by AutoPlaque/APQ. The pipeline should start from CCTA, detect and segment the coronary tree, then use those refined AutoPlaque/APQ-derived masks as high-value secondary evidence for:

- teacher supervision of lumen, wall, plaque, and centerline probability maps;
- branch-wise contour refinement after initial tree detection;
- vendor-vs-model disagreement analysis;
- hard-case subsets for calcium, stents, low contrast, and motion;
- validation of branch coverage, topology, HD95, local area profiles, and plaque burden;
- curated silver-standard training sets with manual correction provenance.

# Recommended Approach

The recommended architecture is a data-led graph-and-shape pipeline:

1. train or adapt a CCTA-first model for coronary lumen/vessel/tree probability using DISCHARGE and additional local datasets;
2. use researcher-refined AutoPlaque/APQ-derived masks as teacher labels, refinement targets, and QC comparators;
3. extract an over-connected candidate graph rather than immediately committing to one tree;
4. apply constrained geodesic routing only for centerline extraction, short-gap repair, and alternative-path generation;
5. use graph refinement for pruning, branch labels, and anatomical plausibility;
6. attach paired lumen/outer-wall/plaque geometry to accepted edges, with provenance and centerline convention stored explicitly;
7. add modern graph-geometric learning only after the deterministic contract is stable: manifold-valued graph states for branch geometry, varifold/tree distances for topology comparison, functional maps for correspondence, and hypergraph bifurcation states [@hanik2024manifoldgcn; @maignant2025varifoldtree; @mayer2024functionalmaps; @stokke2025hypergraphs].

The target is not "extract a connected skeleton." It is to build a labeled coronary graph whose edges carry coupled lumen/outer-wall geometry, uncertainty, topology configuration, and physiology-facing descriptors.

# Pipeline Architecture

The pipeline should be explicit about provenance at every stage.

## Stage 0: Inputs And Semantics

Start from the CCTA study and normalize it into a common physical coordinate system. Stage 0 should separate localization, seeding, and coronary extraction:

- localization: crop to the heart and aortic root using cardiac-structure segmentation;
- seeding: detect left and right coronary ostia on or near the aortic-root surface;
- tracing/segmentation: recover the coronary lumen/tree inside the soft cardiac search region.

Whole-heart segmentation is a localization prior, not a skeleton method. TotalSegmentator-like body/organ models, MM-WHS-style cardiac-substructure models, or dedicated cardiac CT models can provide myocardium, chambers, and aortic-root context [@wasserthal2023totalsegmentator; @zhuang2019mmwhs; @bruns2022wholeheart]. TotalSegmentator v2 also exposes higher-resolution cardiac subtasks such as `heartchambers_highres`; these are useful for aortic-root and myocardium localization, not for accepting a clinical coronary tree. Any generic coronary-artery output from a broad anatomical segmentor should be treated only as a coarse ROI, seed proposal, or QA comparator. It must not replace the dedicated coronary lumen/tree engine.

The localization prior should be generous and measured. The epicardial/periaortic band margin should be at least as large as the observed cardiac-structure surface error on the local DISCHARGE CCTA subset, plus a safety margin. If the band is a hard mask or too tight, it can erase myocardial bridging, anomalous interarterial or intramural courses, grafts, collaterals, or other clinically important out-of-band paths. Candidates outside the band should therefore be flagged for review, not silently discarded.

The ostia are a separate landmark problem. Aortic-root segmentation narrows the search region, but it does not by itself provide left and right coronary seeds. Ostia detection should have its own method, confidence, and manual-correction provenance.

The input bundle should include:

- CCTA volume, spacing, origin, and direction matrix;
- optional cardiac-structure masks, especially myocardium and aortic root, for localization and ostium search;
- coronary ostium candidates and optional distal endpoint candidates;
- vesselness, centerline-probability, lumen-probability, and/or wall/plaque probability maps;
- researcher-refined AutoPlaque/APQ-derived lumen/wall/plaque masks for refinement, teacher supervision, and QC;
- optional imported centerline or tree graph for comparison or bootstrapping, not as the default source of truth.

The pipeline should store:

- physical coordinate system with direction matrix, spacing, and origin;
- world-to-voxel sampling convention; CPR/MPR generation must use the direction matrix, not only origin and spacing;
- cardiac ROI provenance, including whether myocardium/aortic-root masks came from TotalSegmentator, MM-WHS-style nnU-Net, a dedicated cardiac CT model, manual correction, or another source;
- epicardial/periaortic band definition, band margin, and measured local whole-heart-surface error used to justify that margin;
- candidate vessel components;
- ostium and distal endpoint provenance, including whether each was detected by landmark CNN, inferred from aortic-root geometry, manual, imported, vendor-derived, or automatically detected;
- initial semantic labels if available;
- derived-mask provenance, including AutoPlaque/APQ software version, researcher edits, and review status.

## Stage 1: Candidate Centerline/Tree Extraction

Use source-specific defaults:

- Cardiac ROI prior: segment or import myocardium and aortic root, crop to the heart, and define a generous epicardial/periaortic search band. This is a soft localization prior, not a hard coronary mask; candidates outside the band should be flagged rather than silently discarded.
- Ostia detection: localize the left and right coronary ostia as explicit seed landmarks using a landmark detector, geometry from the aortic-root surface, or manual correction; store confidence separately from the downstream centerline confidence.
- CCTA volume: build vesselness and learned vessel/lumen probability maps, then infer ostium-rooted candidate branches.
- Initial AI lumen mask: use distance transform plus fast marching/backtracking, with explicit ostium/distal endpoint selection or detection.
- Dedicated coronary engine: given the available researcher-refined AutoPlaque/APQ-derived voxel masks, the lowest-friction first route is nnU-Net-class segmentation followed by skeletonization/reconnection, because the existing labels directly supervise voxel probabilities where labels exist [@Isensee2021nnUNet; @qiu2025]. These masks should be trained as partial labels unless a case is explicitly full-tree reviewed: labeled lumen/wall/plaque voxels are positive or boundary evidence, but unlabeled coronary territory is `ignore`, not background. Otherwise the model is trained to suppress real but unanalyzed branches. Public coronary CCTA resources can support this route: ImageCAS is the natural large-scale pretraining and benchmarking source, while ASOCA and Coronary Atlas data are useful for smaller expert-labeled stress testing with lumen annotations, centerlines, and meshes [@zeng2023imagecas; @gharleghi2022asoca; @gharleghi2023coronaryatlas]. Differentiable morphology and skeletonization-style operators can make this route more topology-aware during training by penalizing skeleton inconsistency rather than only voxel overlap [@guzzi2024softmorph]. A Wolterink-style CNN orientation/radius tracker is a strong second route, but it requires ordered centerline ground truth that must first be derived from masks, imported AutoPlaque/APQ centerlines if available, or reviewed centerlines [@wolterink2019centerline].
- Candidate graph: recover multiple plausible paths and branch alternatives, not just a single centerline.
- Clean lumen surface: optional VMTK/Voronoi/maximal-inscribed-sphere comparison route [@antiga2008].
- Derived masks: use researcher-refined AutoPlaque/APQ outputs after initial CCTA-derived detection to refine contours, compare branch coverage, and mark disagreement.

The default implementation should remain lightweight: distance transform, SimpleITK fast marching, first-party backtracking, smoothing, and validation. VMTK/SimVascular can be a validation route later, not a default dependency.

Seed and endpoint discovery should not be treated as solved by the centerline algorithm. For a fully automatic pipeline, ostium detection and distal endpoint selection are their own failure modes; both should be stored with confidence, source, and whether manual correction was used.

## Stage 2: Connectivity Repair

Use geodesic routing as a repair mechanism when the tree is broken:

- detect disconnected components;
- identify plausible endpoints based on distance, tangent direction, vesselness/probability, and branch context;
- route candidate gaps through a cost field;
- accept repairs only if they satisfy anatomical and image-evidence constraints.

A repair score should combine:

$$
S_{\mathrm{repair}}
=
w_D S_{\mathrm{distance}}
+ w_P S_{\mathrm{probability}}
+ w_\theta S_{\mathrm{direction}}
+ w_R S_{\mathrm{radius}}
+ w_A S_{\mathrm{anatomy}}
- w_B S_{\mathrm{branch\_jump}}.
$$

This is conceptually close to Qiu's distance-probability-cosine reconnection, but with explicit coronary-specific additions: radius/taper plausibility, branch identity, ostium-rooted direction, and bifurcation exclusion [@qiu2025]. The weights should be tuned and stress-tested on a DISCHARGE review subset, with separate reporting for short-gap repair, branch-jump avoidance, and false reconnection.

## Stage 3: Graph Construction And Topology Prior

Convert centerline candidates into a rooted graph:

- root at left/right coronary ostium;
- bifurcation nodes where branches split;
- edges as ordered centerline spans;
- optional station nodes every 0.5-1.0 mm for local geometry;
- graph-distance metric for bifurcation neighborhoods;
- branch labels and label probabilities;
- topology configuration: dominance, left-main termination, branch multiplicity, graph type, and out-of-atlas status.

Use a soft topology prior after candidate extraction, not during the first image-based detection step. Imposing a template too early can hallucinate missing branches or erase clinically important variants. The prior should live at graph-construction time, where it can condition labels, score plausibility, and decide whether the case fits normal coronary anatomy.

The configuration model should include:

- finite backbone switches: dominance, LM termination pattern, and RCA/LCx origin of PDA and posterolateral branches;
- typed variable-multiplicity side branches: diagonals, septals, obtuse marginals, ramus intermedius, conus, SA-nodal, AV-nodal, acute marginals;
- finite anomaly classes: anomalous origin, single coronary, ALCAPA, duplicated LAD, high takeoff, super-dominant variants;
- non-tree escape classes: CABG grafts, anastomoses, collaterals, fistulae, or cyclic connections.

This is a grammar, not an atlas image. It constrains allowed parent-child assignments while keeping an escape hatch:

- infer dominance from the crux and PDA/PLB origin;
- infer LM termination from the ostial and proximal left-coronary graph;
- assign typed branches only to allowed parents;
- score the template match rather than enforcing it;
- if no normal template fits above threshold, emit `out_of_atlas: true` and route to review.

This discrete configuration layer is the natural partner to the continuous ZIB shape-space model. Dominance and LM termination define different topology classes, so wall-shape correspondence and Fréchet means should be learned within compatible configurations rather than forced across incompatible trees. The older BHV/Feragen tree-space line is useful foundation [@billera2001treespace; @feragen2012airway], but the more modern ZIB-native transfer is the varifold-distance machinery from tree inference. That paper is not a coronary-vessel paper; it was developed for single-cell trajectory trees. The transferable part is comparing tree-like branching structures under variable branch counts and soft correspondence [@maignant2025varifoldtree]. Functional-map shape descriptors are similarly relevant for wall correspondence when fixed landmarks are unavailable or unreliable [@mayer2024functionalmaps]. SCCT-style CCTA reporting standards provide the clinical motivation for consistent segment-level coronary measurements [@nieman2024standards].

## Stage 4: Cross-Sectional Geometry

For each accepted branch edge:

1. resample by arc length;
2. compute tangent and rotation-minimizing frame;
3. extract perpendicular cross-sections;
4. derive first-pass lumen contours from the CCTA-derived segmentation;
5. refine lumen, outer-wall, and plaque contours using researcher-refined AutoPlaque/APQ-derived masks where available;
6. derive outer-wall contours where image and/or vendor evidence supports them;
7. refine the centerline according to the recorded convention: lumen-medial from lumen contours, or outer-wall-aware/vessel-medial where the outer wall is sufficiently supported;
8. repeat until centerline shifts and MLA change are below configured thresholds.

Important caveat: lumen-centroid refinement is biased in eccentric plaque. In a positively remodeled plaque with eccentric narrowing, the lumen centroid can sit on the patent side rather than the original vessel axis. If the project measures plaque burden, remodeling, or wall deformation, the centerline convention must be explicit: `lumen_medial`, `outer_wall_medial`, `imported`, or `mixed`. Otherwise the same numerical centerline may be interpreted incorrectly downstream.

This is the bridge from tree construction to the main scientific object. A centerline tree alone is not enough. The graph edge must carry a local paired wall state:

$$
e_i(s) = \left(c(s), F(s), \Gamma_{\mathrm{lumen}}(s), \Gamma_{\mathrm{outer}}(s), q(s)\right),
$$

where $c(s)$ is centerline, $F(s)$ is local frame, $\Gamma_{\mathrm{lumen}}$ and $\Gamma_{\mathrm{outer}}$ are contours or surface patches, and $q(s)$ is QC/provenance.

## Stage 5: QC And Reject Logic

Tree construction must produce rejectable evidence, not just a plausible-looking graph.

These QC choices are not cosmetic. Curvature, bifurcation geometry, diameter ratios, and tortuosity can change shear-related biomarkers and pressure/flow estimates, so abrupt geometry changes should be treated as downstream-risk signals rather than merely visual imperfections [@zhang2024curvature; @garcha2025]. Parent/daughter caliber checks should use Murray-style branching as a soft physiological prior, not as a hard law, because the exponent and assumptions can vary in real coronary anatomy [@murray1926; @taylor2024murray].

Essential flags:

- disconnected source mask;
- repaired gap length;
- branch-jump risk;
- ostium/endpoint low confidence;
- low-radius/near-boundary stations;
- centerline leaving mask;
- centerline-definition mismatch or eccentric-plaque centroid bias;
- bifurcation zone overlap;
- abrupt curvature spike;
- taper violation;
- implausible Murray-style parent/daughter relation;
- outer-wall nesting violation;
- artifact interval through MLA;
- label/topology conflict;
- topology-prior mismatch or out-of-atlas case;
- graph-type mismatch, for example graft/collateral/fistula coerced into a tree.

For initial tree extraction, unresolved bifurcation neighborhoods should be excluded from routine MLA/reference estimation. If the MLA falls inside an unresolved bifurcation zone, reject or route to manual review rather than forcing a single-branch measurement.

## VesselTree To VesselScene Handoff

The full-tree analysis object and the viewer object should be kept distinct:

- `VesselTree` is the whole coronary graph: ostia, bifurcations, branch edges, topology configuration, labels, repair status, provenance, and per-edge geometry.
- `VesselScene` is the per-vessel or per-edge presentation object: one branch centerline, CCTA CPR/MPR volumes, cross-sections, lumen/wall surfaces, contour overlays, lesion summaries, and validation reports.

Each accepted `VesselTree` edge should be exportable as one `VesselScene`. The edge-level `centerline_xyz_mm`, `tangent_xyz`, `frame_u_xyz`, and `frame_v_xyz` map to the scene centerline, tangents, normals, and binormals. The default scene frame should be a rotation-minimizing frame, preferably double-reflection RMF, because projection/Bishop-style propagation can accumulate clinically visible twist over long coronary branches.

# Evaluation And Acceptance Criteria

Distinct from the per-case QC flags in Stage 5, this section defines aggregate acceptance metrics for development, validation, and model comparison. Tree construction should be evaluated as a graph-and-geometry pipeline, not as a mask-only task. Dice or voxel overlap can remain a basic sanity check, but acceptance should depend on whether the output is connected, correctly labeled, physiologically plausible, and stable enough for plaque and flow analysis.

Minimum evaluation families:

- image-space segmentation: lumen/vessel Dice, HD95 or regional Hausdorff distance, boundary error, and branch-wise coverage;
- centerline quality: centerline distance, continuity, repaired-gap length, centerline leaving-mask rate, and ostium-to-distal path completeness;
- graph topology: connected components, graph edit distance, false branch rate, missed branch rate, branch-jump rate, and out-of-atlas detection;
- branch labeling: label accuracy for LM, LAD, LCx, RCA, diagonals, obtuse marginals, PDA/PLB, and confidence calibration;
- cross-sectional geometry: lumen area error along arc length, outer-wall area error, wall-thickness error, remodeling-index error, and MLA localization error;
- reformat and scene geometry: frame unit-length error, frame orthogonality error, frame determinant, centerline CT coverage, world-to-voxel affine/direction agreement, optional contour-ring residuals where expert rings are available, and surface manifoldness;
- bifurcation and physiology-facing geometry: parent/daughter diameter ratios, Murray-style residuals, bifurcation angle consistency, taper, curvature, and tortuosity [@murray1926; @taylor2024murray; @zhang2024curvature; @garcha2025];
- uncertainty and provenance: calibration of branch existence, branch identity, wall position, repair status, and source attribution;
- downstream sensitivity: effect of accepted/repaired/rejected segments on CT-FFR, CT-QFR, plaque burden, and longitudinal change where such downstream modules are available.

Validation splits should be patient-level and, where possible, scanner/site/protocol aware. Acquisition metadata matters because kVp, reconstruction kernel, noise, phase, contrast, motion, calcium blooming, and vessel size can materially change quantitative CCTA plaque and wall measurements [@nieman2024standards; @chandrashekhar2025acc].

For DISCHARGE, success should be defined at two levels. On an expert-reviewed full-tree subset, the pipeline should meet branch-label, connectivity, graph-topology, and centerline/geometry acceptance bars for the whole coronary tree. On the larger lesion-centered AutoPlaque/APQ-derived mask set, evaluation should be restricted to the analyzed mask support: agreement inside labeled segments, correct propagation of uncertainty outside them, and no penalty for plausible unlabeled branches that were never annotated. This prevents segment-level plaque masks from being mistaken for full-tree ground truth.

Existing prototype numbers should be used as calibration evidence for the geometry stack, not as universal thresholds or as a requirement to use MEDIS in the default workflow. In a single LAD prototype with expert contour rings, double-reflection RMF produced frame orthogonality error around `1.67e-16`, determinant minimum around `0.999999999`, full centerline CT coverage, watertight lumen and wall surfaces with zero non-manifold edges, contour-ring residual p95 `0.81 mm`, and contour-ring residual max `3.38 mm`. The p95 residual supports review-tier visual trust, while the max residual is endpoint-sensitive and should remain a quantitative caution. A projection-frame diagnostic showed about `18.6 deg` drift relative to double-reflection RMF, which is why RMF should be the default for quantitative CPR/MPR export.

# Role And Limits Of Geodesics

Geodesic cost-map methods are directly related to connectivity and routing. They help answer:

- How do we connect two visible vessel fragments?
- How do we extract a medial path from a lumen mask?
- How do we route through a low-confidence region without hand-drawing a centerline?
- How do we generate candidate centerlines for AI patch placement?
- How do we create a reproducible comparator to learned tracking?

They are weak as a complete coronary solution because:

- the cost map is only as good as the image evidence;
- calcification, blooming, low contrast, veins, motion, and stents can make the cheapest path anatomically wrong;
- minimal paths can cut corners unless radius/direction/curvature penalties are included;
- a single centerline path can jump branches near bifurcations;
- tree topology repair can create plausible-looking but false connections;
- outer-wall inference, plaque deformation, branch-level wall-shape correspondence, and longitudinal progression need more than lumen routing.

Geodesics are therefore a scaffold and audit layer. The project contribution is the scaffold plus a richer graph state: topology, paired wall geometry, uncertainty, source provenance, and physiology-facing descriptors.

# Implementation Plan

## What To Implement First

The next implementation step should be conservative:

1. Inventory the DISCHARGE/local data before training: number of CCTA cases, sites/scanners/protocols, which vessels and lesions have AutoPlaque/APQ-derived masks, whether any optional expert contour-ring exports exist for validation, whether labels are lesion-centered or full-tree, whether vendor centerlines/CPR paths are available, which cases have branch labels, calcium/stent/artifact distribution, and which cases can receive expert full-tree review.
2. Assemble a training and review subset with CCTA, researcher-refined AutoPlaque/APQ-derived masks, branch labels where available, and manual correction provenance; use active learning or uncertainty sampling to prioritize manual review of cases likely to improve topology and wall-boundary performance.
3. Implement or solidify CCTA cardiac-ROI localization, soft epicardial/periaortic band construction, ostium search, CCTA-to-vessel-probability, and CCTA-to-candidate-tree extraction.
4. Pretrain or benchmark the dedicated coronary model with ImageCAS, ASOCA, and Coronary Atlas where useful, then adapt lumen/tree probability models using the curated AutoPlaque/APQ-derived masks as partial teacher evidence; use patient/site/scanner-aware validation splits where possible, treat segmentation-plus-skeletonization as the first engine because the available supervision is voxel-mask based, mask unlabeled coronary territory as `ignore`, and test differentiable morphology/skeletonization losses for topology consistency.
5. Convert the initial AI lumen/tree mask to centerlines using distance transform, SimpleITK fast marching, and first-party backtracking.
6. Compare and refine against researcher-refined AutoPlaque/APQ-derived masks where available, storing disagreements as QC evidence and preserving the mask support region.
7. Add a first typed topology grammar: dominance, LM termination, allowed side-branch parents, out-of-atlas flag, and graph type.
8. Add branch/gap/topology QC before adding automatic repair.
9. Add simple geodesic gap repair only for short, well-constrained gaps with strong tangent, vesselness, and topology-prior agreement.
10. Keep VMTK as optional validation, not a dependency.
11. Store the result as a `VesselTree` bundle with graph, topology configuration, centerline, frame, surfaces, contours, metrics, and QC; export accepted branch edges as `VesselScene` bundles for CPR/MPR review and viewer consumption.
12. Add the modern geometric-learning layer after the deterministic contract is stable: manifold-valued graph states for branch geometry, varifold/tree distances for topology comparison, functional maps for correspondence, and hypergraph bifurcation states.

## What To Avoid

Avoid:

- presenting geodesic routing as enough for plaque phenotyping;
- repairing all gaps automatically;
- allowing minimal paths to cross bifurcation neighborhoods without branch constraints;
- forcing anomalous anatomy, grafts, collaterals, or fistulae into a normal acyclic tree;
- evaluating tree construction with Dice alone;
- hiding whether a vessel segment is measured, repaired, interpolated, or prior-driven.

## Reference Guide

The references divide naturally by role:

- geodesic connectivity and topology-aware vascular tree inference [@moriconi2017vtrails; @moriconi2019geodesicmst];
- coronary-specific segmentation, reconnection, tree refinement, anatomical labeling, and public CCTA coronary training/validation resources [@Isensee2021nnUNet; @zeng2023imagecas; @gharleghi2022asoca; @gharleghi2023coronaryatlas; @qiu2025; @hampe2024];
- coronary CTA tube models and surface-derived centerlines [@mohan2009tubular; @antiga2008];
- MEDIS/QAngio CT contour exports as optional legacy/prototype validation references, not as default pipeline inputs [@medis2024; @reiber2010];
- cardiac ROI and whole-heart/cardiac-structure localization [@wasserthal2023totalsegmentator; @zhuang2019mmwhs; @bruns2022wholeheart];
- CNN orientation/radius tracking as a coronary centerline extraction route once centerline labels are available [@wolterink2019centerline];
- orientation-aware geodesic tracking as a methodological reference for direction-sensitive costs [@vandenberg2024cartan];
- regional Hausdorff and morphology-aware losses for validation beyond Dice [@guzzi2026regionalhd; @guzzi2024softmorph];
- physiology-facing geometry, Murray-style branching priors, curvature, and hemodynamic sensitivity [@murray1926; @taylor2024murray; @zhang2024curvature; @garcha2025];
- peripheral-artery CTA segmentation as adjacent evidence for lower-limb vessel AI, not a coronary anchor [@guzzi2026lowerlimb];
- classical vesselness and minimum-cost paths as reproducible baseline components [@frangi1998; @metz2009];
- modern ZIB/von Tycowicz graph-geometric methods: manifold GCNs, functional-map shape descriptors, varifold/tree-distance transfer, and manifold-valued hypergraphs [@hanik2024manifoldgcn; @mayer2024functionalmaps; @maignant2025varifoldtree; @stokke2025hypergraphs];
- older tree-space and anatomical-tree labeling as foundations for statistics over varying topology [@billera2001treespace; @feragen2012airway];
- SCCT quantitative CCTA standards as the clinical motivation for consistent segment-level coronary geometry [@nieman2024standards].

# Proposed VesselTree Contract

A minimal export for each vessel tree should include:

```yaml
tree_id: case_id_left_or_right
source:
  ct_series: string
  primary_source: CCTA
  acquisition:
    scanner: string
    reconstruction_phase: string
    kvp: number
    tube_current_or_noise: string
    reconstruction_kernel: string
    contrast_or_lumen_attenuation: string
  initial_tree_method: ai_probability
  refinement_sources: [autoplaque_apq_derived_mask, researcher_refined_mask, manual]
  label_scope: lesion_centered_partial | full_tree | mixed | unknown
  unlabeled_voxels_policy: ignore | background | unknown
  vendor_centerline_available: bool
  centerline_method: distance_fmm
  centerline_definition: lumen_medial
  scene_export_granularity: per_edge | per_tree | none
  scene_frame_method: double_reflection_rmf | other_rmf | imported | unknown
localization:
  whs_model: totalsegmentator | mmwhs_nnunet | cardiac_ct_model | manual | other
  whs_version: string
  roi_source: myocardium_dilated | aortic_root | cardiac_roi_model | manual
  measured_whs_surface_error_mm: float
  band_margin_mm: float
  band_is_soft_prior: bool
  ostia_method: landmark_cnn | from_aortic_root | manual | imported
  ostia_confidence:
    left: float
    right: float
topology:
  dominance: right
  lm_termination: bifurcation
  template_id: string
  template_match_confidence: float
  out_of_atlas: bool
  anomaly_class: none
  graph_type: tree
  branch_multiplicity:
    diagonal: int
    obtuse_marginal: int
    septal: int
    posterolateral: int
nodes:
  - node_id: string
    type: ostium | bifurcation | endpoint | station
    xyz_mm: [x, y, z]
    confidence: float
edges:
  - edge_id: string
    parent_node: string
    child_node: string
    label: LAD | LCx | RCA | LM | D | OM | AM | PDA | PLB | unknown
    label_confidence: float
    centerline_xyz_mm: [[x, y, z]]
    arc_length_mm: [s0, s1, ...]
    tangent_xyz: [[tx, ty, tz]]
    frame_u_xyz: [[ux, uy, uz]]
    frame_v_xyz: [[vx, vy, vz]]
    lumen_area_mm2: [a0, a1, ...]
    outer_area_mm2: [a0, a1, ...]
    wall_support_level: measured | interpolated | taper_prior | population_prior | unavailable
    repair_status: original | repaired | rejected
    qc_flags: [string]
provenance:
  software_versions: {}
  parameters: {}
```

The controlled vocabularies should include the normal coronary configurations plus explicit escape values: `unknown`, `out_of_atlas`, anomalous origin, single coronary, ALCAPA, duplicated LAD, high takeoff, fistula, forest, DAG with grafts, and cyclic graph.

This contract keeps the tree usable even before the full shape-space model exists.

# References {-}

::: {#refs}
:::
