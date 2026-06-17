---
title: "Coupled Coronary Tree And Wall Geometry For CCTA Phenotyping: A Charité-ZIB-Cambridge Collaboration Proposal"
subtitle: "DISCHARGE-first CCTA-derived tree construction, coupled wall geometry, and downstream coronary phenotyping"
author: "Steffen Lukas <steffen.lukas@charite.de>"
date: "17 June 2026"
version: "1.8"
status: "Internal collaboration proposal"
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
  \usepackage{graphicx}
  \usepackage{float}
  \setmainfont{Liberation Sans}
  \setsansfont{Liberation Sans}
  \newcommand{\headerfont}{\sffamily}
  \setlength{\headheight}{14pt}
  \pagestyle{fancy}
  \fancyhf{}
  \fancyhead[L]{\headerfont\fontsize{9}{11}\selectfont Coronary Tree And Wall Geometry Proposal}
  \fancyhead[R]{\headerfont\fontsize{9}{11}\selectfont \thepage}
  \renewcommand{\headrulewidth}{0pt}
  \renewcommand{\footrulewidth}{0pt}
  \makeatletter\let\ps@plain\ps@fancy\makeatother
---

# Abstract

Coronary artery segmentation for CT-derived physiology and plaque analysis is no longer just a voxel-classification problem. A useful pipeline must recover the contrast-filled inner lumen, estimate the outer vessel wall, which on CCTA is an inferred external elastic membrane (EEM)-like boundary, preserve branch topology, label the coronary tree, and retain enough geometric fidelity for curvature, bifurcation, diameter, remodeling, and plaque-related hemodynamic analysis.

This proposal organizes the field into four method families: classical geometric methods, deep-learning extraction and labeling, geometric shape analysis and manifold learning, and graph-based representations with physiological consequences. Particular emphasis is placed on four methodological anchor references that clarify the current direction of the field: graph neural network labeling of the coronary tree [@hampe2024], topology-preserving connected extraction [@qiu2025], and two hemodynamic sensitivity studies that motivate why geometric fidelity matters, namely curvature and shear-related plaque biology [@zhang2024curvature] and sensitivity of coronary hemodynamics to anatomical variation [@garcha2025].

AutoPlaque/APQ serves as the clinical-deployment anchor because it is a regulatory-cleared, outcome-linked quantitative coronary plaque analysis pipeline developed by the Cedars-Sinai/Dey group, and because it produces exactly the kind of lumen, wall, plaque, and remodeling outputs that are useful as comparator or teacher data [@dey2009apq; @dey2010apqivus; @lin2022; @fda2023autoplaque; @miller2024autoplaque]. For a Charité-ZIB-Cambridge collaboration, the strategic opportunity is to combine these coronary-specific advances with ZIB's modern line in non-Euclidean shape analysis: manifold-valued graph learning, correspondence-free functional-map descriptors, topology-flexible varifold-distance methods transferred from tree inference, manifold-valued hypergraphs, and the Morphomatics ecosystem [@morphomatics2021; @hanik2024manifoldgcn; @mayer2024functionalmaps; @maignant2025varifoldtree; @stokke2025hypergraphs]. The earlier Riemannian statistical shape models remain the foundation, but they should not be the headline [@vontycowicz2018shape; @ambellan2021shape]. Other proprietary clinical stacks such as Cleerly, HeartFlow, Caristo, and Elucid provide useful background context on what clinically deployed CCTA analysis can look like, but they are not a practical basis for this collaboration because we do not have direct access to their internal models or engineering pipelines.

This proposal positions a Charité-ZIB-Cambridge pipeline whose central deliverable is a coupled inner/outer wall coronary graph, built DISCHARGE-first from source CCTA and refined with researcher-refined AutoPlaque/APQ-derived lesion masks, then regularized in non-Euclidean shape space. The CCTA-derived coronary graph is the primary object; the AutoPlaque/APQ-derived masks are high-value partial teacher, refinement, and quality-control data rather than an independent input modality or full-tree ground truth.

\begin{figure}[H]
\centering
\includegraphics[width=\linewidth]{col/coronary_shape_schematic.pdf}
\caption{The proposed object: a labeled coronary tree graph whose per-segment state is a paired inner/outer wall cross-section, lifted into a Riemannian shape space so deformation, uncertainty, and longitudinal change become intrinsic geometric quantities.}
\label{fig:coronary-shape}
\end{figure}

# Audience And Scope

This is an internal collaboration proposal for a DISCHARGE-first Charité-ZIB-Cambridge effort, building on Charité's custodianship of the DISCHARGE CCTA data, Marc Dewey's continuing study curation from Cambridge, and the researcher-refined AutoPlaque/APQ-derived lesion-centered segmentation masks already produced from those source images. It is not intended as an exhaustive survey.

# Why This Matters: From Lumen Mask To Clinical Phenotype

A useful coronary segmentation pipeline is not judged only by voxel overlap. It is judged by how many downstream clinical questions can be answered from a single coherent geometric representation of the coronary artery. The same lumen-wall-tree object should support stenosis grading, CT-FFR and CT-QFR-style physiology, quantitative plaque analysis, plaque composition, high-risk plaque features, and longitudinal progression or regression. This is why segmentation fidelity, topology preservation, and coupled inner/outer wall geometry matter simultaneously rather than as separate sub-problems.

For CT-FFR or CT-QFR work, segmentation quality is judged by downstream physiology, not by mask overlap alone. The model needs a continuous centerline, reliable lumen area along arc length, stable minimum-lumen-area localization, interpretable side branches, and branch geometry that supports either direct flow computation or physiologic scaling laws. This is why topological continuity, branch labeling, and geometric plausibility matter as much as Dice score.

For quantitative plaque analysis, the harder target is the coupled relationship between the inner lumen surface and outer vessel wall. The lumen drives pressure-drop and CT-QFR-style computations, but the outer wall drives plaque burden, percent atheroma volume (PAV), positive remodeling, eccentricity, wall thickness, and vessel-specific vulnerability assessment. Clinically used plaque-analysis stacks aim to report composition classes rather than just a binary plaque mask, because calcified, non-calcified, and low-attenuation components carry different biological and prognostic meaning [@dey2009apq; @lin2022; @miller2024autoplaque; @follmer2024; @chandrashekhar2025acc]. In CCTA, the outer boundary is often ambiguous because non-calcified plaque, myocardium, perivascular fat, adjacent veins, and calcium blooming can erase a clean intensity edge. On CT this boundary is inferred rather than directly visualized in the IVUS/OCT sense, which is exactly why geometric shape priors can add value beyond thresholding.

The same geometry also feeds adjacent biomarkers. Perivascular fat attenuation index (FAI) measurements, high-risk plaque (HRP) features, and longitudinal plaque progression or regression all depend on local wall geometry and on correspondence between baseline and follow-up anatomy. This is a natural fit for modern shape-space and graph-geometric methods: functional maps can reduce dependence on fixed landmarks, manifold-valued graph learning can propagate local wall states over the coronary tree, and Riemannian distances still provide intrinsic deformation measures between inner and outer wall surfaces [@mayer2024functionalmaps; @hanik2024manifoldgcn; @vontycowicz2018shape; @ambellan2021shape; @morphomatics2021; @nieman2024standards; @chandrashekhar2025acc].

The practical lesson is that the field is converging on a hybrid model: deep learning performs the high-throughput image interpretation; graph, topology, and centerline constraints repair or regularize the vascular tree; modern geometric learning regularizes wall surfaces and graph states without requiring a single fixed atlas; and physiology or plaque-analysis modules use the resulting geometry for pressure drop, wall shear stress, plaque burden, composition, remodeling, or QFR-like indices [@frangi1998; @metz2009; @murray1926; @taylor2024murray; @hanik2024manifoldgcn; @maignant2025varifoldtree].

# Four Method Pillars

## Classical And Geometric Methods

Classical methods remain important because they encode structure that generic segmentation networks often miss. Frangi vesselness filtering enhances tubular structures by analyzing Hessian eigenvalues and remains a common preprocessing or tracking prior for coronary CTA [@frangi1998]. Minimum-cost path methods use vesselness or related image costs to extract coronary centerlines from user-supplied or automatically proposed endpoints [@metz2009]. These methods are weaker as complete standalone segmenters, but they are still useful as topology-aware scaffolds and quality-control comparators.

In this proposal, minimum-cost or geodesic routing should remain a deterministic scaffold for centerline extraction, short-gap repair, alternative-path generation, and audit. It should not be treated as sufficient for plaque phenotyping or complete coronary tree construction.

Murray's law is especially relevant for physiology. In coronary trees, it links parent and daughter vessel diameters to a flow-efficient branching rule and therefore provides a defensible prior for branch flow allocation or side-branch reconstruction when direct measurement is unreliable [@murray1926; @taylor2024murray]. But it should be treated as an approximate physiological prior, not an exact law: coronary flow is pulsatile, vessels remodel, and the effective exponent is not always the textbook value of 3 [@taylor2024murray]. In CT-QFR-style workflows, this is the bridge between segmented anatomy and pressure-flow computation: the segmentation must not merely trace vessels, but also produce branch calibers and bifurcations that are physiologically coherent.

## Deep Learning Segmentation

CNN and U-Net-derived methods dominate current coronary CTA segmentation because they handle local image texture, plaque, calcium, lumen contrast, and volumetric context at scale. nnU-Net is the general benchmark philosophy: strong task-specific baselines can be obtained by carefully adapting preprocessing, architecture, and training strategy to the dataset rather than assuming a single fixed network is optimal [@Isensee2021nnUNet]. Coronary plaque and multi-structure CTA segmentation studies show the same pattern: model performance depends heavily on task definition, annotation target, and post-processing rules [@baskaran2020segment; @javorszky2022].

For CT-FFR, the limitation is that a visually plausible mask can still be physiologically unusable. Small gaps, broken distal branches, wrong side-branch attribution, or a shifted centerline near the MLA can distort the resistance integral and the contraction-loss term. This is why topology-aware losses, graph post-processing, and explicit centerline repair have become central rather than decorative.

Promptable foundation models such as Segment Anything and SAM-Med3D may still be useful for initialization, interactive correction, or weak-label generation, but in coronary CCTA they remain support tools unless paired with topology-aware tree construction and wall-shape regularization [@Kirillov2023SAM; @Zhang2024SAMMed3D].

For localization, cardiac-structure segmentation is the useful prior. Whole-heart or myocardium/aortic-root segmentation can crop the CCTA to the cardiac ROI, define a generous epicardial and periaortic search region, and focus ostium detection [@wasserthal2023totalsegmentator; @zhuang2019mmwhs; @bruns2022wholeheart]. That localization prior should remain soft: myocardial bridging, anomalous interarterial or intramural courses, grafts, and collaterals can leave the ordinary epicardial band. The actual coronary skeleton should still come from a dedicated coronary segmentation, tracking, and graph-repair model rather than from a generic organ-scale model. Given the available researcher-refined AutoPlaque/APQ-derived voxel masks, segmentation followed by skeletonization and reconnection is the lower-friction first engine; CNN orientation/radius tracking is a strong complementary route once centerline labels are derived or reviewed [@qiu2025; @wolterink2019centerline].

Those AutoPlaque/APQ-derived masks should be trained as partial labels unless a case has explicit full-tree review. Labeled lumen, wall, or plaque voxels provide positive and boundary evidence, but unlabeled visible coronary territory should be treated as `ignore`, not as background, otherwise the model is taught to suppress real but unanalyzed branches.

## Geometric Shape Analysis And Manifold Learning

This is the missing pillar for a ZIB-facing collaboration. Classical vesselness methods locate tubular structures, and CNNs classify voxels, but neither directly represents the artery as a continuous anatomical object. Geometric shape analysis treats the coronary artery as a surface or coupled-surface object: an inner lumen surface and an outer vessel-wall surface evolving along a centerline and across a branching tree. The relevant quantities are not only voxel labels, but cross-sectional area, perimeter, wall thickness, eccentricity, remodeling index, surface curvature, branch tapering, anatomical correspondence, and deformation modes.

The ZIB contribution would be to model these objects in non-Euclidean shape spaces and graph-geometric representations rather than as independent Euclidean point clouds or binary masks. The modern von Tycowicz line is especially well matched to coronaries: manifold GCNs provide neural layers for graphs whose node or edge states live on a Riemannian manifold, functional maps support shape comparison without requiring strict landmark correspondence, varifold-distance methods from tree inference give a topology-flexible way to compare branching structures, and manifold-valued hypergraphs are a natural language for bifurcations and other higher-order junctions [@hanik2024manifoldgcn; @mayer2024functionalmaps; @maignant2025varifoldtree; @stokke2025hypergraphs]. The varifold tree paper itself is a methodological transfer from single-cell trajectory inference, not a demonstrated coronary-vessel method. In coronary terms, this means the branch graph can carry local wall shapes, cross-sectional frames, plaque deformations, and uncertainty as geometric objects rather than flattening everything into scalar features.

The earlier Riemannian statistical shape models using differential coordinates and discrete fundamental forms remain important foundations, implemented in the open-source Morphomatics library [@vontycowicz2018shape; @ambellan2021shape; @morphomatics2021]. Their role in this proposal should be to ground the continuous wall-surface prior: the lumen and outer wall can deform, but their relationship should remain anatomically coherent, smooth along arc length, and compatible with branching geometry. The modern upgrade is that correspondence no longer has to be assumed globally. Functional maps and varifold-style representations are better matched to incomplete, lesion-centered, and topology-varying coronary observations.

Adjacent geometric-deep-learning primitives matter here too. Point-set networks such as PointNet++ and implicit-surface models such as Occupancy Networks illustrate two important alternatives to pure voxel labeling: operate directly on sampled vessel geometry, or represent the vessel surface as a continuous function rather than a rasterized mask [@qi2017pointnetpp; @mescheder2019occupancy]. Mesh-based refinement belongs in the same family. For coronary CCTA, these representations are best understood as complements rather than replacements for shape-space thinking: they can carry local wall patches or continuous surfaces, while a statistical shape prior keeps the coupled inner and outer walls anatomically coherent along the vessel and across branches.

This does not replace deep learning. It changes the target that deep learning predicts and the way failures are repaired. A CNN or transformer can provide image evidence for lumen, calcium, plaque, and wall candidates; a geometric graph model can then regularize the coupled surfaces and tree states in regions where CT intensity is unreliable. Similar shape-informed segmentation ideas have already improved medical image segmentation outside the coronary domain by combining statistical shape knowledge with deep learning [@kofler2024shape]. The collaboration opportunity is to make this vessel-specific: a coronary graph whose node, edge, and bifurcation states are manifold-valued local wall shapes, not just vectors.

## Graph-Based Representations And Physiological Consequences

Recent work pushes beyond "where are vessel voxels?" toward "what coronary tree is this, and what does its geometry imply?" Hampe et al. use graph neural networks to label extracted coronary artery trees in CCTA, combining geometry and local intensity information across adjacent vessel segments [@hampe2024]. In that work, the graph is mainly a discrete anatomical scaffold for extraction, pruning, and labeling. A ZIB-style extension would keep the same branch graph but lift its node or edge states into a geometric shape space: each cross-section, short vessel segment, or branch patch could carry an inner/outer wall shape, local deformation, or uncertainty distribution. The Manifold GCN journal version is the direct methodological anchor for this step [@hanik2024manifoldgcn].

For coronary trees, the graph design itself matters. The vessel tree is rooted at the coronary ostium, directional along flow, and naturally hierarchical. Generic undirected GCN-style message passing can blur parent-child semantics that are important for tapering, branch inheritance, and distal uncertainty. Message-passing networks with directional edge features, hierarchical pooling along the tree, and branch-aware node or edge states are therefore a more natural fit than treating the coronary graph as an arbitrary skeleton. Existing CCTA work on anatomical labeling and related cardiac CT tasks already shows the value of combining local image evidence with graph structure [@hampe2024; @ren2023coronarylabel; @vanhamersvelt2019].

There is also a direct mathematical precedent for doing statistics on anatomical trees rather than treating them as arbitrary graphs. The older BHV/Feragen line remains useful as foundation for tree-space thinking [@billera2001treespace; @feragen2012airway]. But the more modern, ZIB-native anchor is the varifold-distance machinery from varifold tree inference: although developed for single-cell trajectory trees rather than coronary vessels, it compares branching structures through geometric-measure distances and is therefore methodologically relevant to variable branch counts, incomplete observations, and soft correspondence [@maignant2025varifoldtree]. For coronaries, this is the modern answer to the atlas problem: use a typed anatomical grammar for clinical plausibility, but use varifold/tree-geometric distances to compare or regularize trees without forcing every patient into one fixed template.

The deeper opportunity is to make those graph states geometric rather than purely scalar. Instead of storing only a class label or a small feature vector, a node could encode a local cross-sectional wall shape, an orthonormal frame along the centerline, or a short paired inner/outer wall patch with uncertainty. Bifurcations should not be reduced to pairwise edges when their geometry is intrinsically parent-plus-multiple-daughters; manifold-valued hypergraphs give a natural way to model those higher-order relationships [@stokke2025hypergraphs]. This is where Morphomatics and manifold-valued graph learning become more than a buzzword: the graph becomes the carrier of anatomy, and the manifold becomes the carrier of local wall geometry. Equivariance is relevant here too. Coronary anatomy should not change semantically when the heart is rotated in scanner coordinates, so equivariant geometric architectures such as EGNNs or SE(3)-Transformers are a more concrete starting point than ad hoc orientation-dependent descriptors [@satorras2021egnn; @fuchs2020se3].

Qiu et al. target the connectivity problem directly with a three-stage extraction framework that performs segmentation, centerline reconnection, and missing-vessel reconstruction [@qiu2025]. Zhang et al. show why curvature and shear-related descriptors matter biologically, especially for plaque onset and progression [@zhang2024curvature]. Garcha and Grande Gutierrez show, using synthetic left coronary models and CFD, that hemodynamic phenotypes are sensitive to vascular structure, including diameter ratios, bifurcation geometry, tortuosity, and plaque topology [@garcha2025].

Taken together, these four methodological anchors define the current coronary-specific direction: label the tree, keep it connected, respect the biological importance of curvature and shear, and preserve the branching geometry that controls hemodynamic sensitivity. Their shared limitation, from the Charité-ZIB-Cambridge perspective, is that they still mainly operate on centerlines, labels, masks, or synthetic lumen geometries rather than on coupled inner and outer wall surfaces.

# Charité-ZIB-Cambridge Collaboration Opportunity

The strongest collaboration framing is therefore not "build another coronary U-Net." It is: build an open, shape-aware coronary graph model that couples image evidence with geometric priors. Charité contributes the clinical CCTA problem, local data access, validation targets, and expert review workflows. ZIB contributes the modern graph-geometric stack: Morphomatics, manifold-valued graph learning, functional-map correspondence, varifold tree comparison, and hypergraph modeling of junctions [@morphomatics2021; @hanik2024manifoldgcn; @mayer2024functionalmaps; @maignant2025varifoldtree; @stokke2025hypergraphs]. Cambridge, with Marc Dewey's continuing DISCHARGE role and radiology leadership, contributes study continuity, translational framing, and an external-but-aligned clinical perspective on downstream physiology and phenotyping.

The concrete research object should be a CCTA-derived `VesselTree`: an ostia-rooted coronary tree graph whose edges are vessel segments and whose local state is paired wall geometry, namely inner lumen contour plus outer-wall contour at ordered cross-sections. Figure \ref{fig:coronary-shape} summarizes the same handoff from labeled tree to paired wall contour to shape-space comparison. The model should learn normal tapering, expected wall-thickness variation, eccentric plaque deformation, bifurcation shape, and branch-specific uncertainty. This would let the algorithm infer plausible outer wall geometry where CCTA intensity is ambiguous, while still respecting visible lumen evidence and branch topology.

The corresponding review object should be a `VesselScene`: a per-vessel or per-edge export containing the branch centerline, CPR/MPR views, cross-sections, lumen and wall surfaces, contour overlays, lesion summaries, and validation reports. This separates the whole-tree analysis contract from the viewer-facing object used for expert review and downstream measurements.

This framing also makes the project attractive beyond one disease endpoint. The same graph-and-shape representation supports CT-QFR, CT-FFR, plaque burden, positive remodeling, vessel eccentricity, curvature, tortuosity, and longitudinal change. Because modern shape-space methods provide intrinsic distances, functional correspondence, graph-geometric propagation, and topology-flexible tree comparison, the same representation could support mathematically defined plaque progression or regression metrics between baseline and follow-up CCTA. It gives the collaboration a mathematical core rather than a purely empirical segmentation benchmark.

## Why Charité-Controlled Rather Than Open For Its Own Sake

The goal of this collaboration is not open source for its own sake. The goal is to build a Charité-controlled geometry layer that can be inspected, versioned, stress-tested, and improved jointly by Charité, ZIB, Cambridge, and collaborators working on physiology or longitudinal interpretation. The highest-impact deliverable would not be only a neural network; it would be a reproducible end-to-end stack that outputs masks, centerlines, labeled coronary graphs, paired inner/outer wall surfaces, branch-level lumen and wall profiles, plaque volumes, geometric descriptors, QC flags, and flow-model-ready files.

The scientific impact would be reproducibility inside the collaboration. Researchers could compare graph methods, topology repair, branch labeling, wall-shape priors, plaque quantification, and hemodynamic models on the same shared DISCHARGE-first data structures and metrics. The clinical-translation impact would be transparency: users could inspect where a broken branch, noisy MLA, uncertain outer wall, or unstable plaque boundary enters a CT-FFR or CT-QFR computation. The engineering impact would be modularity: teams could swap segmentation, graph extraction, labeling, shape-space regularization, uncertainty, and flow modules without rebuilding the whole pipeline.

The open problems remain substantial, but they are concrete and local. The immediate need is not to gather many external datasets. It is to consolidate DISCHARGE provenance, convert existing segmentations into project-native geometry, define a review subset, and build the first internally credible wall-aware graph representation. If that layer works on DISCHARGE, broader external benchmarking can follow as a second phase rather than a prerequisite.

# Clinical Stacks And The AutoPlaque Anchor

Commercial CCTA analysis platforms generally combine segmentation, plaque quantification, branch labeling, and rule-based tissue characterization rather than relying on a single end-to-end neural network. Consensus documents on quantitative cardiovascular imaging emphasize the need for standardized coronary stenosis and plaque quantification, reproducibility, and careful validation before quantitative imaging biomarkers are used clinically [@qci2023coronary; @nieman2024standards; @schulze2025coronary; @chandrashekhar2025acc].

In practical terms, the existing commercial landscape already hints at the functional decomposition. Plaque-first tools such as AutoPlaque emphasize lumen, wall, composition, and remodeling metrics; physiology-first stacks such as HeartFlow emphasize flow-ready centerlines, lumen geometry, and downstream pressure computation; phenotyping-oriented platforms such as Cleerly emphasize labeled vessels, lesion summaries, CAD-RADS-style reporting, and patient-level disease profiles; and inflammation-focused products depend on an accurate outer wall plus a reproducible perivascular ring. What these stacks generally do not expose as a first-class research object is the coupled inner/outer wall geometry itself. That is the specific opening for a Charité-ZIB-Cambridge collaboration.

## AutoPlaque/APQ As The Clinical-Deployment Anchor

AutoPlaque is especially important for this project because it sits at the intersection of method development, regulatory clearance, and real clinical research use. The older APQ line developed by Dey and colleagues used scan-specific attenuation thresholds for lumen, non-calcified plaque, calcified plaque, and epicardial fat, combined with knowledge-based coronary segmentation and geometric modeling to define plaque components in 3D [@dey2009apq]. That early design already contains one of the key lessons for our own work: plaque segmentation is not only a local HU classification problem, because the vessel-wall boundary, lumen attenuation, surrounding fat, and coronary geometry jointly determine what counts as plaque.

The modern deep-learning AutoPlaque line moves this idea into a cross-sectional sequence model. Lin et al. describe a hierarchical ConvLSTM network operating on straightened CCTA vessel cross-sections around predefined coronary centerlines, with a multitask design for vessel wall and for lumen/plaque components [@lin2022]. The network uses local cross-sectional appearance plus neighboring cross-sections to preserve along-vessel context, and the outputs are then translated into clinically meaningful plaque classes and stenosis metrics. Later descriptions of the AutoPlaque v3.0 workflow emphasize expert-annotated coronary segments at least 2.0 mm in diameter, per-patient plaque volumes over the coronary tree, adaptive scan-specific HU thresholds for non-calcified and calcified constituents, and low-attenuation plaque defined with a fixed threshold below 30 HU [@miller2024autoplaque].

The FDA 510(k) record K212758 makes the regulatory status and intended role concrete [@fda2023autoplaque]. Autoplaque 3.0 is a Class II, prescription-use, workstation-based post-processing application for CCTA that aids trained clinicians in analyzing coronary plaques, luminal stenoses, and remodeling; it explicitly does not replace physician judgment. The clearance summary states that version 3.0 includes deep-learning-based vessel, plaque, and lumen segmentation, with clinician review and editing if needed. It reports validation against expert readers in a multicenter U.S. cohort of 201 patients and 781 lesions and a non-U.S. cohort of 175 patients and 1081 lesions, plus a comparison with the prior predicate APQ/ORS device. The measured outputs include total, calcified, non-calcified, and low-density non-calcified plaque volumes and burdens; plaque composition; vessel and lumen profiles; diameter and area stenosis; minimal lumen diameter (MLD), minimal lumen area (MLA), lesion length; contrast density difference; and remodeling index.

The clinical evidence base is unusually strong for a segmentation-derived plaque tool. In the Lancet Digital Health multicenter study, the deep-learning system was trained on 921 patients and 5045 lesions and tested against an external cohort and IVUS [@lin2022]. The headline numbers are worth retaining because they explain why AutoPlaque is such a useful teacher source:

- intraclass correlation 0.964 for total plaque volume and 0.879 for diameter stenosis against expert readers;
- intraclass correlation 0.949 for total plaque volume and 0.904 for minimal lumen area against IVUS;
- mean per-patient analysis time 5.65 seconds versus 25.66 minutes for expert manual analysis.

The same paper linked deep-learning plaque burden to future myocardial infarction in SCOT-HEART. Subsequent work extended the clinical framing from absolute plaque volume to age- and sex-specific plaque percentiles, showing that patients in high plaque-volume percentiles had higher myocardial infarction risk in external samples [@miller2024autoplaque]. Reproducibility work has also tested AI-enabled plaque measurements across systolic and diastolic CCTA phases, which is directly relevant if DISCHARGE studies include phase variation or mixed reconstruction choices [@florestomasino2024].

For this proposal, AutoPlaque is cutting edge in a different way from Hampe, Qiu, Zhang, or Garcha. It is less about open graph topology and less about first-principles hemodynamics; its strength is clinically scaled plaque phenotyping. It makes the coupled lumen-vessel-plaque target operational and shows that quantitative plaque outputs can be fast, reproducible, regulatory-clearable, and prognostically meaningful. Lin et al. indicate that research code availability may be possible after request and agreement, but that is still not the same as a turnkey open implementation or a complete specification of the regulated product [@lin2022]. From an open Charité-ZIB-Cambridge development perspective, the remaining limitation is that the internal model, uncertainty handling, centerline generation, post-processing, and editing rules are not fully transparent. Researcher-refined AutoPlaque/APQ-derived voxel masks should therefore be treated as high-value teacher labels or silver-standard annotations, not as unquestionable ground truth. They also inherit tool-specific priors such as vessel-inclusion thresholds, centerline conventions, scan-adapted attenuation rules, and reader-edit patterns, so success cannot be defined only as agreement with AutoPlaque.

This distinction matters for using DISCHARGE plaque segmentations. The voxel labels are valuable because they encode expert-vetted, clinically meaningful plaque taxonomy at scale. But in our setting they are researcher-refined masks originally generated by AutoPlaque/APQ from the CCTA, and they are primarily lesion-centered labels around analyzed coronary lesions, not a complete full-tree labeling of the coronary vasculature. They can initialize a model, define a comparator, or provide weak supervision for lumen, plaque, and wall candidates within those regions. Our tool should therefore not simply learn to imitate AutoPlaque's final masks. It should learn a more general representation from the source CCTA: centerline-aligned inner and outer contours, local plaque geometry, uncertainty, scanner/protocol covariates, and explicit branch context attached to each lesion segment. Agreement with the refined AutoPlaque-derived masks is therefore a necessary benchmark but not a sufficient one; the open model must also be evaluated against anatomical review, physiology, and external references. The correct research question is not "can we reproduce AutoPlaque?" but "can we use AutoPlaque-derived plaque annotations to build an open, geometry-aware coronary representation that exposes where plaque, lumen, wall, and physiology interact?"

Other proprietary platforms such as Cleerly, HeartFlow, Caristo, and Elucid support the broader point that clinically useful coronary post-processing stacks exist, but they are not central to this proposal. For this collaboration, the practical starting point is DISCHARGE source CCTA plus the researcher-refined AutoPlaque/APQ-derived masks already available at Charité.

# DISCHARGE-First Scope And Immediate Work Packages

The central asset for this collaboration is not a hypothetical future dataset. It is the DISCHARGE study itself: Charité hosts the source CCTA volumes, related clinical context, and a substantial body of researcher-refined AutoPlaque/APQ-derived plaque segmentation masks generated from those images. Those masks are valuable, but they are primarily lesion-centered analyses around coronary lesions rather than full-tree annotations. That changes the project logic. The immediate goal is not to assemble a broad public benchmark or to reverse-engineer every commercial pipeline. The immediate goal is to turn existing DISCHARGE CCTA volumes and derived lesion-centered masks into a robust project-native geometry layer that all partners can work on. In practical terms, this is the shared object around which Charité, ZIB, and Cambridge should align. Public resources such as ASOCA, ImageCAS, CAT08, and ORCASCORE remain useful later as external stress tests, but they are not the coordination bottleneck for starting this collaboration.

The first work package is data and provenance consolidation. We should define one DISCHARGE-first analysis table that links each analyzed vessel or lesion to the source series, reconstruction phase, scanner, kernel, kVp, software version, vessel inclusion threshold, label scope, unlabeled-voxel policy, QC status, and evidence of manual review. Without that layer, plaque volume and wall measurements cannot be interpreted consistently.

The second work package is CCTA-derived tree construction. The source CCTA should define the initial tree and branch context: cardiac ROI, ostium candidates, candidate vessel components, branch alternatives, labels, topology configuration, and QC or reject flags. The output should be an ostia-rooted `VesselTree`, not only a mask or isolated lesion segment.

The third work package is paired wall geometry conversion. Researcher-refined AutoPlaque/APQ-derived voxel masks should be converted into centerline-aligned lumen contours, outer-wall contours, plaque components, and paired wall surfaces where they overlap accepted `VesselTree` edges. Because the available DISCHARGE labels are lesion-centered rather than full-tree masks, this conversion has to attach each lesion segment to the broader vessel centerline and branch context derived from source CCTA. This is the handoff from derived clinical annotations to an internal research representation that ZIB can regularize and analyze in shape space.

The fourth work package is focused expert review rather than broad external validation. Charité can define a clinically important review subset: proximal and mid-vessel plaques, remodeling-heavy cases, calcium-heavy cases, bifurcations, and cases with likely outer-wall ambiguity. These cases should be used to stress-test whether the geometric representation is anatomically plausible and useful for downstream physiology or plaque interpretation.

The fifth work package is model development and internal evaluation. ZIB should build the shape-aware graph representation and wall regularization on DISCHARGE-first data. Cambridge collaborators, including Marc Dewey, can then stress-test the representation from the standpoint of physiology, longitudinal change, and translational usefulness. External validation can come later; it is not the gating issue for starting this collaboration.

## Ownership And Data Governance

| WP | Lead | Supporting | Primary deliverable | Phase |
|---|---|---|---|---|
| WP1 Provenance and label-scope consolidation | Charité + Cambridge | ZIB | DISCHARGE-first analysis table, label policy, and governance schema | 0-3 mo |
| WP2 CCTA-derived tree construction | Charité + ZIB | Cambridge | Ostia-rooted `VesselTree` with labels, topology configuration, and QC flags | 3-6 mo |
| WP3 Paired wall geometry conversion | Charité + ZIB | Cambridge | Centerline-aligned lumen, outer-wall, and plaque geometry on accepted edges | 4-8 mo |
| WP4 Focused expert review | Charité | Cambridge, ZIB | Stress-test subset and failure taxonomy | 4-9 mo |
| WP5 Shape-aware graph model | ZIB | Charité, Cambridge | Wall-regularized `VesselTree` pipeline | 6-12 mo |

DISCHARGE source images should remain under Charité-governed access arrangements, with study curation coordinated with Marc Dewey in Cambridge; where possible, ZIB and Cambridge should work on approved derived geometric representations or within Charité-controlled environments unless a project-specific data-use agreement permits broader transfer.

# Particular Challenges And Open Problems

The main technical challenge is complete, topologically correct extraction of a coronary tree from imperfect CCTA. Small distal branches, low contrast, motion artefact, calcium blooming, severe stenosis, stents, and adjacent veins can all create gaps or false branches. A flow-ready system therefore needs more than a segmentation network: it needs explicit graph construction, reconnection logic, branch deletion logic, and uncertainty flags.

The second challenge is anatomical graph labeling. Clinical and physiological interpretation depends on knowing whether a lesion is in the left anterior descending artery (LAD), left circumflex artery (LCx), right coronary artery (RCA), diagonal branch, obtuse marginal branch, posterior descending artery (PDA), or a smaller named branch. Hampe et al. show that GNN labeling is feasible, but the remaining open problem is robustness under extraction errors, dominance variants, anomalous anatomy, missing distal branches, and under-represented labels [@hampe2024].

The practical prior should be a typed graph grammar rather than a rigid atlas. Dominance and left-main termination are configuration switches; diagonals, septals, obtuse marginals, and posterior branches are variable-multiplicity typed side branches; anomalous origins, grafts, collaterals, fistulae, and cyclic connections need explicit escape states rather than forced normal-tree labels.

The third challenge is preserving geometry that matters for physiology. CT-FFR and CT-QFR-style methods depend on lumen area along arc length, minimum lumen area, lesion length, side-branch locations, bifurcation diameters, tapering, curvature, tortuosity, and plaque topology. Zhang et al. and Garcha and Grande Gutierrez make the key point: curvature, diameter ratios, bifurcation position, angle, and tortuosity are not cosmetic descriptors; they can change shear-related biomarkers and local pressure or flow estimates [@zhang2024curvature; @garcha2025].

The fourth challenge is plaque and wall characterization, especially the outer vessel wall. CCTA has partial-volume effects, calcification blooming, variable contrast attenuation, adjacent veins, and weak HU separation between non-calcified plaque, myocardium, and perivascular tissue. AutoPlaque/APQ already shows that AI plus scan-adapted attenuation logic can be clinically useful, but plaque-composition measurements are likely less stable across phases, scanners, or readers than total plaque volume and therefore need especially careful validation [@florestomasino2024; @meah2021]. Thresholding is therefore not wrong, but it is insufficient as the central principle for outer-wall delineation. The open problem is geometric: infer a plausible outer-wall surface where intensity gradients are weak or missing, while preserving the measured lumen and the branch-level tree. This is the natural place for coupled shape priors, manifold-valued graph states, functional correspondence, surface smoothness along arc length, and uncertainty rather than independent voxel decisions.

The fifth challenge is validation. Dice score is necessary but not sufficient. A useful benchmark should include centerline continuity, graph edit distance, branch-label accuracy, lumen area error along arc length, outer-wall area error, wall-thickness error, remodeling-index error, MLA localization error, bifurcation diameter ratios, curvature/tortuosity error, plaque volume error, Riemannian shape-distance metrics, uncertainty calibration, and downstream CT-FFR or CT-QFR error.

For DISCHARGE, evaluation should be defined at two levels. On an expert-reviewed full-tree subset, the pipeline should be judged on branch labels, connectivity, graph topology, centerlines, and paired wall geometry for the whole coronary tree. On the larger lesion-centered AutoPlaque/APQ-derived mask set, evaluation should be restricted to the analyzed mask support, with no penalty for plausible unlabeled branches that were never annotated.

Cross-modality validation also needs careful CCTA-OCT-IVUS-ICA registration because the modalities differ in slice spacing, imaging plane, catheter alignment, penetration depth, and acquisition timing.

Quantitative-CCTA consensus documents also stress that tube voltage, tube current, lumen contrast, noise, reconstruction kernel, motion, calcium blooming, and vessel size can materially change plaque output, so validation needs acquisition metadata rather than masks alone [@nieman2024standards; @chandrashekhar2025acc].

Uncertainty and topology deserve to be explicit evaluation targets rather than afterthoughts. Coronary plaque morphology is precisely the kind of setting where local ambiguity can cause global interpretive error, and recent reviews have argued for quantifying topological uncertainty rather than reporting only point estimates [@singh2025uncertainty]. For this project, uncertainty should attach not only to voxel labels but also to branch existence, branch identity, wall position, and plaque burden. Topological data analysis is also relevant as a diagnostic layer: persistent-homology-style summaries and topology-aware losses or metrics can complement graph edit distance when asking whether a reconstruction preserved the intended branching structure [@singh2025tda].

# Implications For A Flow-Ready Segmentation Pipeline

The immediate target should be a flow-ready coronary graph rather than a full research-grade segmentation of every visible vessel. Minimum useful outputs are:

1. a continuous proximal-to-distal centerline for the target vessel;
2. ordered inner lumen contours and areas along arc length;
3. ordered outer-wall contours with wall-thickness and remodeling metrics;
4. an MLA location that is stable under local perturbation;
5. labeled side branches and bifurcation neighborhoods;
6. explicit flags for gaps, low contrast, calcium blooming, motion, stents, and unresolved branch takeoffs;
7. branch-level diameter ratios, curvature, tortuosity, tapering, eccentricity, and wall-shape descriptors;
8. plaque composition, wall metrics, and uncertainty estimates where possible;
9. a reference-mode decision for CT-FFR or CT-QFR computation.

The full-tree analysis object should be a `VesselTree`, while each accepted branch edge should be exportable as a `VesselScene` for CPR/MPR review and viewer consumption. The output should carry rejectable evidence rather than only final measurements: repaired-gap length, branch-jump risk, ostium confidence, centerline-definition mismatch, unresolved bifurcation zones, outer-wall nesting violations, and topology-prior mismatch should all be visible to downstream users.

The four methodological anchors listed above map directly onto this pipeline spec: labeled branches, reconnected topology, curvature-preserving centerlines, and bifurcation-preserving geometry [@hampe2024; @qiu2025; @zhang2024curvature; @garcha2025].

For researcher-refined AutoPlaque/APQ-derived DISCHARGE voxel masks, the practical handoff should follow the FDA, ACC, and SCCT logic. At minimum, the provenance table should store [@fda2023autoplaque; @nieman2024standards; @chandrashekhar2025acc]:

- original CCTA series identifier and reconstruction phase;
- scanner, kVp, tube-current or noise information, and reconstruction kernel;
- contrast or lumen attenuation metadata where available;
- software version and vessel-diameter threshold;
- analyzed segment or lesion identifier and local vessel location;
- label scope, such as lesion-centered partial, full-tree, mixed, or unknown;
- unlabeled-voxel policy, especially `ignore` versus background;
- topology configuration, dominance, branch label, and out-of-atlas status where available;
- label set, image and analysis quality, QA/QC status, and evidence of manual review or edits;
- any excluded vessels or segments.

Segment-level provenance matters because plaque volumes are only comparable if lesion location, analyzed length, diameter threshold, and exclusion rules are known.

After the CCTA-derived tree is available, overlapping masks should be converted into centerline-aligned contours and paired inner/outer wall surfaces as early as possible. For DISCHARGE this conversion should be framed honestly: the tree and branch context come from the source CCTA, while researcher-refined AutoPlaque/APQ-derived masks provide high-value local annotation evidence for lumen, wall, and plaque geometry. That step turns derived plaque annotations into a project-native geometric object that ZIB can regularize with manifold-valued graph learning, functional correspondence, varifold tree comparison, and shape-space priors while preserving the clinical value of the AutoPlaque analysis. If these labels are ever used longitudinally, the comparison should be even stricter: same or harmonized scanner protocol, kVp, reconstruction kernel, coronary segments, and software version where possible; report absolute and annualized total and non-calcified plaque-volume change within comparable analyzed regions; and require visual concordance before treating apparent progression or regression as biological signal [@nieman2024standards; @chandrashekhar2025acc].

# Key Terms

| Term | Meaning in this proposal |
|---|---|
| Voxel-wise semantic segmentation | Classification of CTA voxels into lumen, plaque, calcium, wall, or background classes. |
| Quantitative coronary plaque analysis | Software-derived measurement of plaque volume, burden, composition, stenosis, and remodeling from CCTA. |
| Teacher or silver-standard label | A high-value label from expert-reviewed software such as AutoPlaque that can supervise development but should not be treated as biological ground truth. In this project, these are often lesion-centered rather than full-tree labels. |
| Partial label | Annotation that is valid only within a known support region, such as an analyzed lesion segment. Unlabeled coronary territory outside that support should not automatically be treated as background. |
| Inner lumen surface | Boundary of the contrast-filled vessel lumen; primary source for stenosis, MLA, and pressure-drop computation. |
| Outer wall boundary | External vessel boundary needed for plaque burden, wall thickness, remodeling, and eccentricity assessment. On CCTA this is an inferred EEM-like boundary rather than a directly visualized IVUS/OCT surface. |
| Centerline | Ordered vessel path used to sample cross-sections, compute arc length, and define pressure-drop integration. |
| Centerline convention | Recorded definition of the centerline, such as lumen-medial, outer-wall-medial, imported, or mixed; needed because eccentric plaque can shift lumen-centroid paths away from the original vessel axis. |
| Coronary graph | Branch-node representation of the coronary tree, including bifurcations and labeled segments. |
| VesselTree | Whole-tree analysis object containing ostia, bifurcations, branch edges, topology configuration, labels, repair status, provenance, and per-edge geometry. |
| VesselScene | Per-vessel or per-edge review/export object containing one branch centerline, CPR/MPR views, cross-sections, lumen/wall surfaces, contour overlays, lesion summaries, and validation reports. |
| Topology grammar | Typed anatomical prior for coronary graph structure, including dominance, LM termination, allowed side-branch parents, branch multiplicity, and explicit escape states for variants or non-tree anatomy. |
| Topology preservation | Avoidance or repair of broken branches, false vessel islands, and disconnected distal segments. |
| Geodesic repair | Constrained use of minimum-cost routing for centerline extraction, short-gap repair, alternative-path generation, or audit, not a complete plaque-phenotyping method. |
| PAV | Percent atheroma volume; plaque burden normalized to vessel context and dependent on paired lumen and outer-wall geometry. |
| HRP features | High-risk plaque features such as positive remodeling, low-attenuation plaque, spotty calcification, or napkin-ring sign. |
| FAI | Perivascular fat attenuation index; inflammation-associated biomarker that depends on accurate outer-wall localization and a reproducible perivascular ring. |
| CAD-RADS | Coronary Artery Disease - Reporting and Data System; structured CCTA reporting framework for stenosis and plaque findings. |
| MLA / MLD | Minimal lumen area / minimal lumen diameter; local narrowing metrics used in stenosis grading and physiology assessment. |
| Riemannian shape space | Non-Euclidean space in which anatomical surfaces or deformations are analyzed with intrinsic geometry. |
| Functional map | Landmark-free representation of correspondence between shapes, useful when fixed point-to-point wall correspondence is unreliable. |
| Varifold tree distance | Geometric-measure distance for comparing branching structures without requiring identical branch topology or hard correspondence. |
| Manifold-valued graph | Branch graph whose node or edge features can be shapes, rotations, positive-definite matrices, or other non-Euclidean data. |
| Manifold-valued hypergraph | Higher-order graph model in which a bifurcation can be represented as one parent-plus-daughters relation rather than independent pairwise edges. |
| Murray's law | Physiologic branching prior relating parent and daughter vessel diameters and flow allocation. |
| Curvature | Local bending of the coronary centerline; relevant for shear patterns and plaque-prone geometry. |
| Flow-ready geometry | A segmentation export that is continuous, labeled, QC-flagged, and usable for CT-FFR or CT-QFR computation. |

# Conclusion

This proposal positions the collaboration around a concrete gap: turning DISCHARGE CCTA plus existing AutoPlaque lesion analyses into a shared, geometry-aware coronary representation rather than another isolated mask generator. The deliverable is a Charité-controlled pipeline that outputs a CCTA-derived `VesselTree`, paired inner and outer wall surfaces on accepted edges, plaque metrics, uncertainty, topology configuration, per-edge `VesselScene` exports, and flow-ready geometry that ZIB can regularize with modern graph-geometric and shape-space methods. The immediate next action is to consolidate provenance, construct a first DISCHARGE review-subset `VesselTree`, attach paired wall geometry where lesion masks support it, and stress-test that representation before broader external benchmarking.
