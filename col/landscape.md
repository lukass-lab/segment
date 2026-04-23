---
title: "Coronary Artery Segmentation Landscape"
subtitle: "Methods, topology, and hemodynamic relevance for CT-FFR and CT-QFR"
author: "Steffen Lukas <steffen.lukas@charite.de>"
date: "23 April 2026"
version: "1.0"
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
  \IfFontExistsTF{Arial}{\newfontfamily\headerfont{Arial}}{\newfontfamily\headerfont{Arimo}}
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

Coronary artery segmentation for CT-derived physiology is no longer just a voxel-classification problem. A useful pipeline must recover a continuous coronary lumen, preserve branch topology, label the coronary tree in a clinically interpretable way, and retain enough geometric fidelity for curvature, bifurcation, diameter, and plaque-related hemodynamic analysis. This landscape note organizes the field into three method families: classical geometric methods, deep-learning extraction and labeling, and flow-oriented commercial or translational pipelines. Particular emphasis is placed on four recent methods that clarify the current direction of the field: graph neural network labeling of the coronary tree [@hampe2024], topology-preserving connected extraction [@qiu2025], curvature and shear-related plaque biology [@zhang2024curvature], and hemodynamic sensitivity to anatomical variation [@garcha2025].

# Why This Matters For CT-FFR And CT-QFR

For CT-FFR or CT-QFR work, segmentation quality is judged by downstream physiology, not by mask overlap alone. The model needs a continuous centerline, reliable lumen area along arc length, stable minimum-lumen-area localization, interpretable side branches, and branch geometry that supports either direct flow computation or physiologic scaling laws. This is why topological continuity, branch labeling, and geometric plausibility matter as much as Dice score.

The practical lesson is that the field is converging on a hybrid model: deep learning performs the high-throughput image interpretation; graph, topology, and centerline constraints repair or regularize the vascular tree; and hemodynamic models use the resulting geometry to compute pressure drop, wall shear stress, or QFR-like functional indices [@frangi1998; @metz2009; @murray1926; @taylor2024murray].

# Three Method Pillars

## Classical And Geometric Methods

Classical methods remain important because they encode structure that generic segmentation networks often miss. Frangi vesselness filtering enhances tubular structures by analyzing Hessian eigenvalues and remains a common preprocessing or tracking prior for coronary CTA [@frangi1998]. Minimum-cost path methods use vesselness or related image costs to extract coronary centerlines from user-supplied or automatically proposed endpoints [@metz2009]. These methods are weaker as complete standalone segmenters, but they are still useful as topology-aware scaffolds and quality-control comparators.

Murray's law is especially relevant for physiology. In coronary trees, it links parent and daughter vessel diameters to a flow-efficient branching rule and therefore provides a defensible prior for branch flow allocation or side-branch reconstruction when direct measurement is unreliable [@murray1926; @taylor2024murray]. In CT-QFR-style workflows, this is the bridge between segmented anatomy and pressure-flow computation: the segmentation must not merely trace vessels, but also produce branch calibers and bifurcations that are physiologically coherent.

## Deep Learning Segmentation

CNN and U-Net-derived methods dominate current coronary CTA segmentation because they handle local image texture, plaque, calcium, lumen contrast, and volumetric context at scale. nnU-Net is the general benchmark philosophy: strong task-specific baselines can be obtained by carefully adapting preprocessing, architecture, and training strategy to the dataset rather than assuming a single fixed network is optimal [@Isensee2021nnUNet]. Coronary plaque and multi-structure CTA segmentation studies show the same pattern: model performance depends heavily on task definition, annotation target, and post-processing rules [@baskaran2020segment; @javorszky2022].

For CT-FFR, the limitation is that a visually plausible mask can still be physiologically unusable. Small gaps, broken distal branches, wrong side-branch attribution, or a shifted centerline near the MLA can distort the resistance integral and the contraction-loss term. This is why topology-aware losses, graph post-processing, and explicit centerline repair have become central rather than decorative.

## Tree Labeling, Topology, And Hemodynamics

Recent work pushes beyond "where are vessel voxels?" toward "what coronary tree is this, and what does its geometry imply?" Hampe et al. use graph neural networks to label extracted coronary artery trees in CCTA, combining geometry and local intensity information across adjacent vessel segments [@hampe2024]. Qiu et al. target the connectivity problem directly with a three-stage extraction framework that performs segmentation, centerline reconnection, and missing-vessel reconstruction [@qiu2025]. Zhang et al. show why curvature and shear-related descriptors matter biologically, especially for plaque onset and progression [@zhang2024curvature]. Garcha and Grande Gutierrez show, using synthetic left coronary models and CFD, that hemodynamic phenotypes are sensitive to vascular structure, including diameter ratios, bifurcation geometry, tortuosity, and plaque topology [@garcha2025].

# Four Recent Methods To Anchor The Discussion

| Method | Main contribution | Relevance for this project |
|---|---|---|
| Hampe et al. 2024 [@hampe2024] | Automatic coronary tree extraction followed by graph neural network anatomical labeling. | Supports the idea that coronary segmentation should end as a labeled graph, not only as a binary mask. This is important for vessel-specific CT-FFR reporting and for mapping lesions to named branches. |
| Qiu et al. 2025 [@qiu2025] | Topology-preserving extraction with segmentation, centerline reconnection, and missing-vessel reconstruction. | Directly addresses broken trees near small distal vessels, tortuous segments, low contrast, stenosis, and plaque. This is the closest methodological fit to the flow-readiness problem. |
| Zhang et al. 2024 [@zhang2024curvature] | Links coronary curvature, topological shear variation, and plaque onset/progression using anatomy and CFD-derived hemodynamic features. | Shows why centerline smoothing, curvature estimation, and bifurcation handling are not secondary details. They affect biologically meaningful hemodynamic descriptors. |
| Garcha and Grande Gutierrez 2025 [@garcha2025] | Quantifies sensitivity of coronary hemodynamics to vascular-structure variation in healthy and diseased synthetic LCA models. | Reinforces that branch diameters, diameter ratios, bifurcation positions, angles, tortuosity, and plaque topology can change local flow metrics. Segmentation must preserve these features accurately enough for sensitivity analysis. |

Together, these four papers define the current methodological direction. Hampe et al. make the tree clinically named; Qiu et al. make it connected; Zhang et al. explain why curvature and shear descriptors matter; and Garcha and Grande Gutierrez show why the exact geometry of branching and diameter ratios matters for computed hemodynamics.

# Commercial And Translational Pipelines

Commercial CCTA analysis platforms generally combine segmentation, plaque quantification, branch labeling, and rule-based tissue characterization rather than relying on a single end-to-end neural network. Consensus documents on quantitative cardiovascular imaging emphasize the need for standardized coronary stenosis and plaque quantification, reproducibility, and careful validation before quantitative imaging biomarkers are used clinically [@qci2023coronary; @schulze2025coronary].

For Pulse Medical-style CT-QFR workflows, the most relevant concept is the hybrid anatomy-physiology stack: automatic or semi-automatic coronary reconstruction, lumen and plaque classification, branch-level geometry, Murray-law-based or related flow allocation, and rapid computation of pressure-derived functional indices [@tu2016; @taylor2024murray]. This aligns with the broader field: deep learning handles image interpretation, but hemodynamic computation still depends on explicit geometry, branch topology, and physiologic assumptions.

# Implications For A Flow-Ready Segmentation Pipeline

The immediate target should be a flow-ready coronary graph rather than a full research-grade segmentation of every visible vessel. Minimum useful outputs are:

1. a continuous proximal-to-distal centerline for the target vessel;
2. ordered lumen areas along arc length;
3. an MLA location that is stable under local perturbation;
4. labeled side branches and bifurcation neighborhoods;
5. explicit flags for gaps, low contrast, calcium blooming, motion, stents, and unresolved branch takeoffs;
6. a reference-mode decision for CT-FFR or CT-QFR computation.

This framing makes the recent methods operational. Hampe-style graph labeling can support anatomical reporting and branch mapping [@hampe2024]. Qiu-style reconnection and missing-vessel reconstruction can reduce physiologically damaging discontinuities [@qiu2025]. Zhang-style curvature and shear descriptors motivate accurate centerline geometry [@zhang2024curvature]. Garcha-style sensitivity analysis motivates preserving branch diameter ratios and bifurcation geometry rather than smoothing them away [@garcha2025].

# Key Terms

| Term | Meaning in this landscape |
|---|---|
| Voxel-wise semantic segmentation | Classification of CTA voxels into lumen, plaque, calcium, wall, or background classes. |
| Centerline | Ordered vessel path used to sample cross-sections, compute arc length, and define pressure-drop integration. |
| Coronary graph | Branch-node representation of the coronary tree, including bifurcations and labeled segments. |
| Topology preservation | Avoidance or repair of broken branches, false vessel islands, and disconnected distal segments. |
| Murray's law | Physiologic branching prior relating parent and daughter vessel diameters and flow allocation. |
| Curvature | Local bending of the coronary centerline; relevant for shear patterns and plaque-prone geometry. |
| Flow-ready geometry | A segmentation export that is continuous, labeled, QC-flagged, and usable for CT-FFR or CT-QFR computation. |

# Conclusion

The coronary segmentation field is moving from mask generation toward graph-based, topology-preserving, physiology-aware reconstruction. For CT-FFR and CT-QFR, the most defensible approach is therefore hybrid: use deep learning for robust lumen and plaque extraction, use graph and topology constraints to preserve the coronary tree, use branch labeling for clinical interpretation, and retain the geometric features that drive hemodynamic sensitivity. The four highlighted methods make this direction concrete: label the tree, keep it connected, measure curvature and shear-relevant geometry, and respect the sensitivity of flow to vascular structure.
