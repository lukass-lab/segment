---
title: "Coronary Artery Segmentation Landscape"
subtitle: "Inner/outer wall geometry, graph topology, and hemodynamic relevance for CT-FFR and CT-QFR"
author: "Steffen Lukas <steffen.lukas@charite.de>"
date: "24 April 2026"
version: "1.2"
status: "Technical landscape note"
bibliography: col/references.bib
csl: plan/vancouver-superscript.csl
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
  \setmainfont{Liberation Sans}
  \setsansfont{Liberation Sans}
  \newcommand{\headerfont}{\sffamily}
  \setlength{\headheight}{14pt}
  \pagestyle{fancy}
  \fancyhf{}
  \fancyhead[L]{\headerfont\fontsize{9}{11}\selectfont Coronary Artery Segmentation Landscape}
  \fancyhead[R]{\headerfont\fontsize{9}{11}\selectfont \thepage}
  \renewcommand{\headrulewidth}{0pt}
  \renewcommand{\footrulewidth}{0pt}
  \makeatletter\let\ps@plain\ps@fancy\makeatother
---

# Abstract

Coronary artery segmentation for CT-derived physiology and plaque analysis is no longer just a voxel-classification problem. A useful pipeline must recover the contrast-filled inner lumen, estimate the outer vessel wall or external elastic membrane (EEM), preserve branch topology, label the coronary tree, and retain enough geometric fidelity for curvature, bifurcation, diameter, remodeling, and plaque-related hemodynamic analysis. This landscape note organizes the field into four method families: classical geometric methods, deep-learning extraction and labeling, geometric shape analysis and manifold learning, and flow-oriented commercial or translational pipelines. Particular emphasis is placed on four cutting-edge geometrical or graph-based coronary methods that clarify the current direction of the field: graph neural network labeling of the coronary tree [@hampe2024], topology-preserving connected extraction [@qiu2025], curvature and shear-related plaque biology [@zhang2024curvature], and hemodynamic sensitivity to anatomical variation [@garcha2025]. AutoPlaque/APQ is an additional anchor because it is a regulatory-cleared, outcome-linked quantitative coronary plaque analysis pipeline developed by the Cedars-Sinai/Dey group, and because it produces exactly the kind of lumen, wall, plaque, and remodeling outputs that are useful as comparator or teacher data [@dey2009apq; @dey2010apqivus; @lin2022; @fda2023autoplaque; @miller2024autoplaque]. For a Charite-Zuse Institute Berlin collaboration, the strategic opportunity is to combine these coronary-specific advances with ZIB's strengths in non-Euclidean statistical shape analysis, manifold-valued graph learning, and the Morphomatics ecosystem [@morphomatics2021; @vontycowicz2018shape; @ambellan2021shape; @hanik2024manifoldgcn]. The CtaPlus/CT-muFR line of work is also relevant because it demonstrates a commercial-grade automated lumen, vessel wall, plaque, and physiology stack, although it does not provide an open algorithmic implementation [@weng2024ctmufr; @li2025ctmufr; @li2026ctaplusplaque].

# Why This Matters For CT-FFR And CT-QFR

For CT-FFR or CT-QFR work, segmentation quality is judged by downstream physiology, not by mask overlap alone. The model needs a continuous centerline, reliable lumen area along arc length, stable minimum-lumen-area localization, interpretable side branches, and branch geometry that supports either direct flow computation or physiologic scaling laws. This is why topological continuity, branch labeling, and geometric plausibility matter as much as Dice score.

For advanced plaque analysis, the harder target is the coupled relationship between the inner lumen surface and outer vessel wall. The lumen drives pressure-drop and CT-QFR-style computations, but the outer wall is needed for plaque burden, positive remodeling, eccentricity, wall thickness, and vessel-specific vulnerability assessment. In CCTA, the outer boundary is often ambiguous because non-calcified plaque, myocardium, perivascular fat, adjacent veins, and calcium blooming can erase a clean intensity edge. This is exactly where geometric shape priors can add value beyond thresholding.

The practical lesson is that the field is converging on a hybrid model: deep learning performs the high-throughput image interpretation; graph, topology, and centerline constraints repair or regularize the vascular tree; statistical shape models regularize the continuous wall surfaces; and hemodynamic models use the resulting geometry to compute pressure drop, wall shear stress, plaque burden, or QFR-like functional indices [@frangi1998; @metz2009; @murray1926; @taylor2024murray; @vontycowicz2018shape].

# Four Method Pillars

## Classical And Geometric Methods

Classical methods remain important because they encode structure that generic segmentation networks often miss. Frangi vesselness filtering enhances tubular structures by analyzing Hessian eigenvalues and remains a common preprocessing or tracking prior for coronary CTA [@frangi1998]. Minimum-cost path methods use vesselness or related image costs to extract coronary centerlines from user-supplied or automatically proposed endpoints [@metz2009]. These methods are weaker as complete standalone segmenters, but they are still useful as topology-aware scaffolds and quality-control comparators.

Murray's law is especially relevant for physiology. In coronary trees, it links parent and daughter vessel diameters to a flow-efficient branching rule and therefore provides a defensible prior for branch flow allocation or side-branch reconstruction when direct measurement is unreliable [@murray1926; @taylor2024murray]. In CT-QFR-style workflows, this is the bridge between segmented anatomy and pressure-flow computation: the segmentation must not merely trace vessels, but also produce branch calibers and bifurcations that are physiologically coherent.

## Deep Learning Segmentation

CNN and U-Net-derived methods dominate current coronary CTA segmentation because they handle local image texture, plaque, calcium, lumen contrast, and volumetric context at scale. nnU-Net is the general benchmark philosophy: strong task-specific baselines can be obtained by carefully adapting preprocessing, architecture, and training strategy to the dataset rather than assuming a single fixed network is optimal [@Isensee2021nnUNet]. Coronary plaque and multi-structure CTA segmentation studies show the same pattern: model performance depends heavily on task definition, annotation target, and post-processing rules [@baskaran2020segment; @javorszky2022].

For CT-FFR, the limitation is that a visually plausible mask can still be physiologically unusable. Small gaps, broken distal branches, wrong side-branch attribution, or a shifted centerline near the MLA can distort the resistance integral and the contraction-loss term. This is why topology-aware losses, graph post-processing, and explicit centerline repair have become central rather than decorative.

## Geometric Shape Analysis And Manifold Learning

This is the missing pillar for a ZIB-facing collaboration. Classical vesselness methods locate tubular structures, and CNNs classify voxels, but neither directly represents the artery as a continuous anatomical object. Geometric shape analysis treats the coronary artery as a surface or coupled-surface object: an inner lumen surface and an outer vessel-wall surface evolving along a centerline and across a branching tree. The relevant quantities are not only voxel labels, but cross-sectional area, perimeter, wall thickness, eccentricity, remodeling index, surface curvature, branch tapering, anatomical correspondence, and deformation modes.

The ZIB contribution would be to model these objects in non-Euclidean shape spaces rather than as independent Euclidean point clouds or binary masks. Tycowicz and collaborators have developed efficient Riemannian statistical shape models using differential coordinates and discrete fundamental forms, implemented in the open-source Morphomatics library [@vontycowicz2018shape; @ambellan2021shape; @morphomatics2021]. The direct coronary translation would be a statistical prior over plausible inner/outer wall pairs: the lumen and outer wall can deform, but their relationship should remain anatomically coherent, smooth along arc length, and compatible with branching geometry. A second benefit is correspondence: wall shapes from different patients or time points can be compared in a common shape space, so local plaque-related deformation can be studied as geometry rather than only as aggregate volume.

This does not replace deep learning. It changes the target that deep learning predicts and the way failures are repaired. A CNN or transformer can provide image evidence for lumen, calcium, plaque, and wall candidates; a shape-space model can then regularize the coupled surfaces in regions where CT intensity is unreliable. Similar shape-informed segmentation ideas have already improved medical image segmentation outside the coronary domain by combining statistical shape knowledge with deep learning [@kofler2024shape]. The collaboration opportunity is to make this vessel-specific: a graph of coronary branches whose node or edge features are not just vectors, but manifold-valued local wall shapes.

## Tree Labeling, Topology, And Hemodynamics

Recent work pushes beyond "where are vessel voxels?" toward "what coronary tree is this, and what does its geometry imply?" Hampe et al. use graph neural networks to label extracted coronary artery trees in CCTA, combining geometry and local intensity information across adjacent vessel segments [@hampe2024]. In that work, the graph is mainly a discrete anatomical scaffold for extraction, pruning, and labeling. A ZIB-style extension would keep the same branch graph but lift its node or edge states into a geometric shape space: each cross-section, short vessel segment, or branch patch could carry an inner/outer wall shape, local deformation, or uncertainty distribution. Manifold-valued GNN layers are a natural methodological bridge for that step [@hanik2024manifoldgcn].

Qiu et al. target the connectivity problem directly with a three-stage extraction framework that performs segmentation, centerline reconnection, and missing-vessel reconstruction [@qiu2025]. Zhang et al. show why curvature and shear-related descriptors matter biologically, especially for plaque onset and progression [@zhang2024curvature]. Garcha and Grande Gutierrez show, using synthetic left coronary models and CFD, that hemodynamic phenotypes are sensitive to vascular structure, including diameter ratios, bifurcation geometry, tortuosity, and plaque topology [@garcha2025].

# Four Recent Methods To Anchor The Discussion

| Method | Main contribution | Open problem exposed | Relevance for this project |
|---|---|---|---|
| Hampe et al. 2024 [@hampe2024] | Automatic coronary tree extraction followed by graph neural network anatomical labeling. | Anatomical labels remain hard when extraction is imperfect, dominance varies, branches are small, and segment classes are imbalanced. | Supports the idea that coronary segmentation should end as a labeled graph, not only as a binary mask. This is important for vessel-specific CT-FFR reporting and for mapping lesions to named branches. |
| Qiu et al. 2025 [@qiu2025] | Topology-preserving extraction with segmentation, centerline reconnection, and missing-vessel reconstruction. | Thin distal vessels, tortuous structures, low contrast, stenoses, and local breaks still produce under-segmentation or false reconnections. | Directly addresses broken trees near small distal vessels, tortuous segments, low contrast, stenosis, and plaque. This is the closest methodological fit to the flow-readiness problem. |
| Zhang et al. 2024 [@zhang2024curvature] | Links coronary curvature, topological shear variation, and plaque onset/progression using anatomy and CFD-derived hemodynamic features. | Centerline smoothing, lumen boundary error, and branch reconstruction can change curvature and shear descriptors enough to alter biological interpretation. | Shows why centerline geometry, curvature estimation, and bifurcation handling are not secondary details. They affect biologically meaningful hemodynamic descriptors. |
| Garcha and Grande Gutierrez 2025 [@garcha2025] | Quantifies sensitivity of coronary hemodynamics to vascular-structure variation in healthy and diseased synthetic LCA models. | Flow metrics are sensitive to diameter ratios, bifurcation position, angle, tortuosity, and plaque topology; small geometric errors can be amplified. | Reinforces that branch diameters, diameter ratios, bifurcation positions, angles, tortuosity, and plaque topology can change local flow metrics. Segmentation must preserve these features accurately enough for sensitivity analysis. |

Together, these four papers define the current coronary-specific methodological direction. Hampe et al. make the tree clinically named; Qiu et al. make it connected; Zhang et al. explain why curvature and shear descriptors matter; and Garcha and Grande Gutierrez show why the exact geometry of branching and diameter ratios matters for computed hemodynamics. Their shared limitation, from the Charite-ZIB perspective, is that they still mainly operate on centerlines, labels, masks, or synthetic lumen geometries. They do not yet solve the coupled inner/outer wall problem needed for robust plaque burden and remodeling analysis.

# Charite-ZIB Collaboration Opportunity

The strongest collaboration framing is therefore not "build another coronary U-Net." It is: build an open, shape-aware coronary graph model that couples image evidence with geometric priors. Charite contributes the clinical CCTA problem, plaque/CT-FFR relevance, validation targets, and access to expert annotation workflows. ZIB contributes Riemannian shape spaces, statistical shape modeling, manifold-valued graph learning, and open tooling through Morphomatics [@morphomatics2021].

The concrete research object could be a coronary tree graph whose edges are vessel segments and whose local state is a paired wall geometry: inner lumen contour plus outer wall or EEM contour at ordered cross-sections. The model should learn normal tapering, expected wall-thickness variation, eccentric plaque deformation, bifurcation shape, and branch-specific uncertainty. This would let the algorithm infer plausible outer wall geometry where CCTA intensity is ambiguous, while still respecting visible lumen evidence and branch topology.

This framing also makes the project attractive beyond one disease endpoint. The same graph-and-shape representation supports CT-QFR, CT-FFR, plaque burden, positive remodeling, vessel eccentricity, curvature, tortuosity, and longitudinal change. Because Riemannian shape spaces provide intrinsic distances and geodesic paths between anatomical shapes, the same representation could support mathematically defined plaque progression or regression metrics between baseline and follow-up CCTA. It gives the collaboration a mathematical core rather than a purely empirical segmentation benchmark.

# Commercial And Translational Pipelines

Commercial CCTA analysis platforms generally combine segmentation, plaque quantification, branch labeling, and rule-based tissue characterization rather than relying on a single end-to-end neural network. Consensus documents on quantitative cardiovascular imaging emphasize the need for standardized coronary stenosis and plaque quantification, reproducibility, and careful validation before quantitative imaging biomarkers are used clinically [@qci2023coronary; @nieman2024standards; @schulze2025coronary; @chandrashekhar2025acc].

## AutoPlaque/APQ As A Plaque-Segmentation Anchor

AutoPlaque is especially important for this project because it sits at the intersection of method development, regulatory clearance, and real clinical research use. The older APQ line developed by Dey and colleagues used scan-specific attenuation thresholds for lumen, non-calcified plaque, calcified plaque, and epicardial fat, combined with knowledge-based coronary segmentation and geometric modeling to define plaque components in 3D [@dey2009apq]. That early design already contains one of the key lessons for our own work: plaque segmentation is not only a local HU classification problem, because the vessel-wall boundary, lumen attenuation, surrounding fat, and coronary geometry jointly determine what counts as plaque.

The modern deep-learning AutoPlaque line moves this idea into a cross-sectional sequence model. Lin et al. describe a hierarchical ConvLSTM network operating on straightened CCTA vessel cross-sections around predefined coronary centerlines, with a multitask design for vessel wall and for lumen/plaque components [@lin2022]. The network uses local cross-sectional appearance plus neighboring cross-sections to preserve along-vessel context, and the outputs are then translated into clinically meaningful plaque classes and stenosis metrics. Later descriptions of the AutoPlaque v3.0 workflow emphasize expert-annotated coronary segments at least 2.0 mm in diameter, per-patient plaque volumes over the coronary tree, adaptive scan-specific HU thresholds for non-calcified and calcified constituents, and low-attenuation plaque defined with a fixed threshold below 30 HU [@miller2024autoplaque].

The FDA 510(k) record K212758 makes the regulatory status and intended role concrete [@fda2023autoplaque]. Autoplaque 3.0 is a Class II, prescription-use, workstation-based post-processing application for CCTA that aids trained clinicians in analyzing coronary plaques, luminal stenoses, and remodeling; it explicitly does not replace physician judgment. The clearance summary states that version 3.0 includes deep-learning-based vessel, plaque, and lumen segmentation, with clinician review and editing if needed. It reports validation against expert readers in a multicenter U.S. cohort of 201 patients and 781 lesions and a non-U.S. cohort of 175 patients and 1081 lesions, plus a comparison with the prior predicate APQ/ORS device. The measured outputs include total, calcified, non-calcified, and low-density non-calcified plaque volumes and burdens; plaque composition; vessel and lumen profiles; diameter and area stenosis; MLD, MLA, lesion length; contrast density difference; and remodeling index.

The clinical evidence base is unusually strong for a segmentation-derived plaque tool. In the Lancet Digital Health multicenter study, the deep-learning system was trained on 921 patients and 5045 lesions and tested against an external cohort and IVUS. It reported intraclass correlations of 0.964 for total plaque volume and 0.879 for diameter stenosis against expert readers, and 0.949 for total plaque volume and 0.904 for minimal lumen area against IVUS, while mean per-patient analysis time was 5.65 seconds versus 25.66 minutes for expert manual analysis [@lin2022]. The same paper linked deep-learning plaque burden to future myocardial infarction in SCOT-HEART. Subsequent work extended the clinical framing from absolute plaque volume to age- and sex-specific plaque percentiles, showing that patients in high plaque-volume percentiles had higher myocardial infarction risk in external samples [@miller2024autoplaque]. Reproducibility work has also tested AI-enabled plaque measurements across systolic and diastolic CCTA phases, which is directly relevant if DISCHARGE studies include phase variation or mixed reconstruction choices [@florestomasino2024].

For the landscape, AutoPlaque is therefore cutting edge in a different way from Hampe, Qiu, Zhang, or Garcha. It is less about open graph topology and less about first-principles hemodynamics; its strength is clinically scaled plaque phenotyping. It makes the coupled lumen-vessel-plaque target operational and shows that quantitative plaque outputs can be fast, reproducible, regulatory-clearable, and prognostically meaningful. The Lin et al. paper notes that research source code may be shared under a non-commercial, no-derivatives license after request and data-use agreement, but that is still not the same as a turnkey open implementation or a complete specification of the regulated product [@lin2022]. From an open Charite-ZIB development perspective, the remaining limitation is that the internal model, uncertainty handling, centerline generation, post-processing, and editing rules are not fully transparent. AutoPlaque-derived voxel masks should therefore be treated as high-value teacher labels or silver-standard annotations, not as unquestionable ground truth.

This distinction matters for using DISCHARGE plaque segmentations. The voxel labels are valuable because they encode expert-vetted, clinically meaningful plaque taxonomy at scale. They can initialize a model, define a comparator, or provide weak supervision for lumen, plaque, and wall candidates. But our tool should not simply learn to imitate AutoPlaque's final masks. It should learn a more general representation: centerline-aligned inner and outer contours, graph-local plaque geometry, uncertainty, scanner/protocol covariates, and branch-aware topology. The correct research question is not "can we reproduce AutoPlaque?" but "can we use AutoPlaque-derived plaque evidence to build an open, geometry-aware coronary representation that exposes where plaque, lumen, wall, and physiology interact?"

For Pulse Medical-style CT-QFR or CT-muFR workflows, the most relevant concept is the hybrid anatomy-physiology stack: automatic or semi-automatic coronary reconstruction, lumen and plaque classification, branch-level geometry, Murray-law-based or related flow allocation, and rapid computation of pressure-derived functional indices [@tu2016; @taylor2024murray]. The CAREER CT-muFR study reported prospective on-site diagnostic performance, and the later fully automatic CCTA reconstruction and CT-muFR analysis reported high feasibility with average analysis time around 1.6 min per patient [@weng2024ctmufr; @li2025ctmufr]. This aligns with the broader field: deep learning handles image interpretation, but hemodynamic computation still depends on explicit geometry, branch topology, and physiologic assumptions.

The Li et al. plaque paper is relevant, with a caveat [@li2026ctaplusplaque]. It is a 2026 European Heart Journal - Digital Health paper, not a 2024 paper, and it is not a complete public specification of the CTA Plus algorithm. It does, however, describe an in-house CCTA pipeline using a coarse-to-fine scheme with multi-task 3D U-Net segmentation, a fully convolutional regression network, and adaptive HU thresholds for plaque composition. The paper explicitly states that the lumen and vessel wall segmentation method was integrated into CtaPlus for CT-muFR computation. In 91 patients with 153 co-registered lesions, automatic plaque quantification correlated with OCT for plaque volume, while the limitations section highlights exactly the hard problems for open development: small post-hoc sample size, modest composition accuracy, CT/OCT slice mismatch, heterogeneous scanners and protocols, stented vessels excluded from training, manual or semi-automatic high-risk plaque features, and unvalidated cutoffs.

# Particular Challenges And Open Problems

The main technical challenge is complete, topologically correct extraction of a coronary tree from imperfect CCTA. Small distal branches, low contrast, motion artefact, calcium blooming, severe stenosis, stents, and adjacent veins can all create gaps or false branches. A flow-ready system therefore needs more than a segmentation network: it needs explicit graph construction, reconnection logic, branch deletion logic, and uncertainty flags.

The second challenge is anatomical graph labeling. Clinical and physiological interpretation depends on knowing whether a lesion is in LAD, LCx, RCA, diagonal, obtuse marginal, PDA, or a smaller named branch. Hampe et al. show that GNN labeling is feasible, but the remaining open problem is robustness under extraction errors, dominance variants, anomalous anatomy, missing distal branches, and under-represented labels [@hampe2024].

The third challenge is preserving geometry that matters for physiology. CT-FFR and CT-QFR-style methods depend on lumen area along arc length, minimum lumen area, lesion length, side-branch locations, bifurcation diameters, tapering, curvature, tortuosity, and plaque topology. Zhang et al. and Garcha and Grande Gutierrez make the key point: curvature, diameter ratios, bifurcation position, angle, and tortuosity are not cosmetic descriptors; they can change shear-related biomarkers and local pressure or flow estimates [@zhang2024curvature; @garcha2025].

The fourth challenge is plaque and wall characterization, especially the outer vessel wall. CCTA has partial-volume effects, calcification blooming, variable contrast attenuation, adjacent veins, and weak HU separation between non-calcified plaque, myocardium, and perivascular tissue. AutoPlaque/APQ and CtaPlus both show that AI plus scan-adapted attenuation logic can be clinically useful, but they also show that plaque composition is more fragile than total plaque volume [@dey2009apq; @lin2022; @li2026ctaplusplaque]. Thresholding is therefore not wrong, but it is insufficient as the central principle for outer-wall delineation. The open problem is geometric: infer a plausible EEM/outer-wall surface where intensity gradients are weak or missing, while preserving the measured lumen and the branch-level tree. This is the natural place for coupled statistical shape priors, surface smoothness along arc length, and manifold-valued uncertainty rather than independent voxel decisions.

The fifth challenge is validation. Dice score is necessary but not sufficient. A useful benchmark should include centerline continuity, graph edit distance, branch-label accuracy, lumen area error along arc length, outer-wall area error, wall-thickness error, remodeling-index error, MLA localization error, bifurcation diameter ratios, curvature/tortuosity error, plaque volume error, Riemannian shape-distance metrics, uncertainty calibration, and downstream CT-FFR or CT-QFR error. Cross-modality validation also needs careful CCTA-OCT-IVUS-ICA registration because the modalities differ in slice spacing, imaging plane, catheter alignment, penetration depth, and acquisition timing. Quantitative-CCTA consensus documents also stress that tube voltage, tube current, lumen contrast, noise, reconstruction kernel, motion, calcium blooming, and vessel size can materially change plaque output, so validation needs acquisition metadata rather than masks alone [@nieman2024standards; @chandrashekhar2025acc].

# Impact Of An Open Source Solution

An open source coronary segmentation and graph pipeline would fill a real gap because most clinically mature systems are proprietary. The highest-impact deliverable would not be only a neural network; it would be a reproducible end-to-end stack that outputs masks, centerlines, labeled coronary graphs, paired inner/outer wall surfaces, branch-level lumen and wall profiles, plaque volumes, geometric descriptors, QC flags, and flow-model-ready files.

The scientific impact would be reproducibility. Researchers could compare graph methods, topology repair, branch labeling, wall-shape priors, plaque quantification, and hemodynamic models on the same data structures and metrics. The clinical-translation impact would be transparency: users could inspect where a broken branch, noisy MLA, uncertain outer wall, or unstable plaque boundary enters a CT-FFR or CT-QFR computation. The engineering impact would be modularity: teams could swap segmentation, graph extraction, labeling, shape-space regularization, uncertainty, and flow modules without rebuilding the whole pipeline.

The open problems would remain substantial. A credible open solution needs curated multi-vendor CCTA data, robust de-identification, annotation tools for centerlines and branch labels, synthetic tree generators for stress testing, privacy-preserving evaluation, and documentation of failure modes. It would also need clear separation between research use and regulated clinical deployment. Even so, an open reference implementation could become the benchmark layer that commercial and academic systems currently lack.

# Implications For A Flow-Ready Segmentation Pipeline

The immediate target should be a flow-ready coronary graph rather than a full research-grade segmentation of every visible vessel. Minimum useful outputs are:

1. a continuous proximal-to-distal centerline for the target vessel;
2. ordered inner lumen contours and areas along arc length;
3. ordered outer wall or EEM contours with wall-thickness and remodeling metrics;
4. an MLA location that is stable under local perturbation;
5. labeled side branches and bifurcation neighborhoods;
6. explicit flags for gaps, low contrast, calcium blooming, motion, stents, and unresolved branch takeoffs;
7. branch-level diameter ratios, curvature, tortuosity, tapering, eccentricity, and wall-shape descriptors;
8. plaque and wall metrics with uncertainty estimates where possible;
9. a reference-mode decision for CT-FFR or CT-QFR computation.

This framing makes the recent methods operational. Hampe-style graph labeling can support anatomical reporting and branch mapping [@hampe2024]. Qiu-style reconnection and missing-vessel reconstruction can reduce physiologically damaging discontinuities [@qiu2025]. Zhang-style curvature and shear descriptors motivate accurate centerline geometry [@zhang2024curvature]. Garcha-style sensitivity analysis motivates preserving branch diameter ratios and bifurcation geometry rather than smoothing them away [@garcha2025].

For AutoPlaque-derived DISCHARGE voxel data, the practical handoff should follow the FDA, ACC, and SCCT logic: original CCTA series identifier, reconstruction phase, scanner, kVp, tube-current or noise information, reconstruction kernel, contrast/lumen attenuation metadata where available, software version, vessel-diameter threshold, analyzed coronary-tree length, label set, image and analysis quality, QA/QC status, evidence of manual review or edits, and any excluded vessels or segments [@fda2023autoplaque; @nieman2024standards; @chandrashekhar2025acc]. Segment-level provenance matters because plaque volumes are only comparable if vessel length, location, diameter threshold, and exclusion rules are known.

The masks should be converted into centerline-aligned contours and paired inner/outer wall surfaces as early as possible. That conversion turns a proprietary voxel output into a project-native geometric object while preserving the clinical value of the AutoPlaque analysis. If these labels are ever used longitudinally, the comparison should be even stricter: same or harmonized scanner protocol, kVp, reconstruction kernel, coronary segments, and software version where possible; report absolute and annualized total and non-calcified plaque-volume change; and require visual concordance before treating apparent progression or regression as biological signal [@nieman2024standards; @chandrashekhar2025acc].

# Key Terms

| Term | Meaning in this landscape |
|---|---|
| Voxel-wise semantic segmentation | Classification of CTA voxels into lumen, plaque, calcium, wall, or background classes. |
| Quantitative coronary plaque analysis | Software-derived measurement of plaque volume, burden, composition, stenosis, and remodeling from CCTA. |
| Teacher or silver-standard label | A high-value label from expert-reviewed software such as AutoPlaque that can supervise development but should not be treated as biological ground truth. |
| Inner lumen surface | Boundary of the contrast-filled vessel lumen; primary source for stenosis, MLA, and pressure-drop computation. |
| Outer wall or EEM surface | External vessel boundary needed for plaque burden, wall thickness, remodeling, and eccentricity assessment. |
| Centerline | Ordered vessel path used to sample cross-sections, compute arc length, and define pressure-drop integration. |
| Coronary graph | Branch-node representation of the coronary tree, including bifurcations and labeled segments. |
| Topology preservation | Avoidance or repair of broken branches, false vessel islands, and disconnected distal segments. |
| Riemannian shape space | Non-Euclidean space in which anatomical surfaces or deformations are analyzed with intrinsic geometry. |
| Manifold-valued graph | Branch graph whose node or edge features can be shapes, rotations, positive-definite matrices, or other non-Euclidean data. |
| Murray's law | Physiologic branching prior relating parent and daughter vessel diameters and flow allocation. |
| Curvature | Local bending of the coronary centerline; relevant for shear patterns and plaque-prone geometry. |
| Flow-ready geometry | A segmentation export that is continuous, labeled, QC-flagged, and usable for CT-FFR or CT-QFR computation. |

# Conclusion

The coronary segmentation field is moving from mask generation toward graph-based, topology-preserving, physiology-aware reconstruction. For CT-FFR and CT-QFR, the most defensible approach is therefore hybrid: use deep learning for robust lumen and plaque extraction, use graph and topology constraints to preserve the coronary tree, use branch labeling for clinical interpretation, and retain the geometric features that drive hemodynamic sensitivity. For a Charite-ZIB collaboration, the key upgrade is to make the vessel wall a first-class geometric object: coupled inner and outer wall surfaces embedded in a coronary graph and regularized by non-Euclidean statistical shape analysis. The four highlighted coronary methods make the clinical direction concrete: label the tree, keep it connected, measure curvature and shear-relevant geometry, and respect the sensitivity of flow to vascular structure. AutoPlaque shows that fast, regulatory-cleared, outcome-linked plaque quantification is already feasible and should be used as a serious comparator and teacher source, especially for DISCHARGE plaque masks. ZIB's shape-space and manifold-valued learning methods provide the natural mathematical layer for turning those labels into an open, reproducible wall-geometry pipeline rather than a proprietary mask imitation exercise. The CtaPlus literature shows that this kind of automated stack is clinically plausible, while the remaining opportunity is to make the data model, validation metrics, and failure analysis open enough for reproducible development.
