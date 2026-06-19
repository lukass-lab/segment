---
title: "TotalSegmentator Local Setup and ProstateX-0204 Run Memo"
author: "Frac Team"
date: "2026-05-23"
toc: true
toc-depth: 2
numbersections: false
header-includes:
  - \usepackage{tocloft}
  - \setlength{\cftbeforesecskip}{0.12em}
  - \setlength{\cftbeforesubsecskip}{0em}
  - \renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}
---

Status: local run memo. This records how TotalSegmentator was installed and run on Martha
for the ProstateX-0204 T2 fixture. It complements [fa-segment.md](fa-segment.md), which
owns the broader segmentation strategy.

# Summary

We installed a local segmentation environment in `.venv-seg`, downloaded one targeted
ProstateX-0204 transverse T2 series from TCIA, converted it from DICOM to NIfTI, and ran
TotalSegmentator `total_mr` on CPU and GPU.

The best current output for visual QA is:

```text
base:    subjects/prostatex-0204/t2.nii.gz
overlay: seg_out/t2-gpu-full/prostate.nii.gz
```

The full GPU run completed successfully on Martha's Quadro T2000, but it used 3621 MiB
of 4096 MiB VRAM. That is enough for this small fixture, but close enough to the ceiling
that larger volumes may fail on Martha. Rudolf remains the safer target for routine GPU
segmentation.

The main result is narrower than "pelvic segmentation works." TotalSegmentator gives a
plausible whole-gland prostate mask plus useful pelvic landmarks. It does **not** provide
the two masks required by the Michallek-faithful FA calculation: the internal-obturator
muscle calibration ROI and the tumour-interface analysis ROI.

# Installation

The environment was created in the repository root:

```bash
cd /home/lukass/workspace/frac
python3 -m venv .venv-seg
.venv-seg/bin/python -m pip install --upgrade pip
.venv-seg/bin/python -m pip install -r requirements-segmentation.txt
.venv-seg/bin/python -m pip install dcm2niix
```

The pinned segmentation requirements are:

```text
torch==2.5.1+cu121
TotalSegmentator==2.13.0
```

The installed converter is:

```text
dcm2niix v1.0.20260416
```

`dcm2niix` is available inside the virtual environment as:

```bash
.venv-seg/bin/dcm2niix
```

It is not assumed to be on the global shell `PATH`.

# Local Data Policy

The following local paths are intentionally ignored by Git:

```text
.venv-seg/
subjects/
seg_out/
```

`subjects/` contains the downloaded DICOM cache and derived NIfTI input. `seg_out/`
contains generated segmentation masks, run manifests, and GPU memory logs.

# Data Download

The fixture is patient `ProstateX-0204` from the public TCIA `PROSTATEx` collection.
The series list was queried with `tcia_utils`:

```bash
python3 -c "from tcia_utils import nbia; import json; s=nbia.getSeries(collection='PROSTATEx', patientId='ProstateX-0204'); print(json.dumps([{'uid':x.get('SeriesInstanceUID'),'desc':x.get('SeriesDescription'),'mod':x.get('Modality'),'series':x.get('SeriesNumber'),'images':x.get('ImageCount')} for x in s], indent=2))"
```

Two `t2_tse_tra` candidates were present. We used the earlier series:

```text
PatientID:         ProstateX-0204
Collection:        PROSTATEx
SeriesDescription: t2_tse_tra
SeriesNumber:      5
ImageCount:        21
SeriesInstanceUID: 1.3.6.1.4.1.14519.5.2.1.7311.5101.327326038201137210751244609393
```

Download command:

```bash
python3 -c "from tcia_utils import nbia; nbia.downloadSeries(['1.3.6.1.4.1.14519.5.2.1.7311.5101.327326038201137210751244609393'], input_type='list', path='subjects/prostatex-0204/dicom', max_workers=1)"
```

The downloaded DICOM cache is retained at:

```text
subjects/prostatex-0204/dicom/
```

# DICOM to NIfTI Conversion

The DICOM series was converted with the virtualenv `dcm2niix`:

```bash
.venv-seg/bin/dcm2niix -z y -o subjects/prostatex-0204 -f t2 subjects/prostatex-0204/dicom
```

The resulting input volume is:

```text
subjects/prostatex-0204/t2.nii.gz
subjects/prostatex-0204/t2.json
```

NIfTI sanity check:

```text
shape: 384 x 384 x 21
zooms: 0.5 x 0.5 x 3.0 mm
```

This is a 3D anatomical T2 volume. It is valid input for TotalSegmentator `total_mr`.
The 4D DCE perfusion fixture is not valid input for this run.

# Helper Script

Runs used:

```text
scripts/try_totalsegmentator.sh
```

The helper:

- validates that the input NIfTI is 3D
- creates/sources `.venv-seg` if needed
- installs `requirements-segmentation.txt` if TotalSegmentator is missing
- runs TotalSegmentator with `--task total_mr`
- writes one mask NIfTI per label
- writes `run.json` provenance
- records GPU memory to `gpu-memory.csv` for GPU runs

The run manifest includes:

```text
tool
tool_version
torch_version
python_version
task
mode
scope
fast
input
output_dir
device
command
runtime_s
exit_status
gpu_memory_log
peak_vram_mib
visual_qa_note
```

`mode` records the model speed variant: `fast` or `full`.
`scope` records the requested output class scope: `full` or `prostate` when
`--prostate-only` is used.

# Runs Performed

Four runs were performed and retained.

| Output directory | Device | Mode | Runtime | Peak VRAM | Status |
|---|---:|---:|---:|---:|---:|
| `seg_out/t2/` | CPU | fast | 13 s | n/a | success |
| `seg_out/t2-full/` | CPU | full | 29 s | n/a | success |
| `seg_out/t2-gpu-fast/` | GPU | fast | 33 s | 2547 MiB | success |
| `seg_out/t2-gpu-full/` | GPU | full | 62 s | 3621 MiB | success |

These are warm-cache runtimes after the TotalSegmentator weights were already present in
`~/.totalsegmentator`. The first cold run also downloads model weights and takes longer;
the local weight cache is currently about 614 MB for the models used here.

Commands:

```bash
./scripts/try_totalsegmentator.sh --fast --cpu subjects/prostatex-0204/t2.nii.gz seg_out/t2
./scripts/try_totalsegmentator.sh --cpu subjects/prostatex-0204/t2.nii.gz seg_out/t2-full
./scripts/try_totalsegmentator.sh --fast subjects/prostatex-0204/t2.nii.gz seg_out/t2-gpu-fast
./scripts/try_totalsegmentator.sh subjects/prostatex-0204/t2.nii.gz seg_out/t2-gpu-full
```

The recommended output for review is the full GPU result:

```text
seg_out/t2-gpu-full/prostate.nii.gz
```

# CPU and GPU Agreement

The full CPU and full GPU prostate masks are effectively identical for this fixture:

```text
CPU full prostate voxels: 50373
GPU full prostate voxels: 50364
Dice coefficient:         0.9999106584472438
Symmetric difference:     9 voxels
```

This small difference is consistent with numerical differences between CPU and GPU
inference kernels and is not an anatomical concern.

# What Frac Actually Needs

The current FA validation and strategy documents make the mask requirements explicit:

| Mask | Required for | Current source | Automation difficulty |
|---|---|---|---|
| Internal-obturator muscle sample | Step 1 intensity standardization | Reviewed DCE-native sample, seeded/landmark proposal on the selected FA reference, or future task-specific helper | Easier; needs a stable interior sample, not a perfect anatomical contour |
| Tumour-interface ROI | Step 4 mean-FD aggregation and max-mean-FD | Reviewed/imported ROI until the author rule is pinned down | Hard; blocked on lesion contour plus interface-band rule |

TotalSegmentator does not emit either of those target masks. This confirms the expectation
in [fa-segment.md](fa-segment.md): broad MR segmenters may expose nearby pelvic context
labels, but they should not be advertised as internal-obturator muscle ROI providers
unless their exact label list and validation prove that target.

What TotalSegmentator contributes now is context:

- whole-gland prostate mask for registration QA, gland context, lesion-search bounds, and
  later capsular-contact checks
- bladder, femur/hip, iliopsoas, gluteal, and iliac-vessel landmarks that may help a
  future atlas or landmark-based internal-obturator ROI proposer

# Segmentations Produced

The `total_mr` task writes one NIfTI mask per supported label. For this prostate T2 crop,
the full GPU run produced 52 files in `seg_out/t2-gpu-full/`: 50 label masks plus
`run.json` and `gpu-memory.csv`.

The mask files are:

```text
adrenal_gland_left.nii.gz
adrenal_gland_right.nii.gz
aorta.nii.gz
autochthon_left.nii.gz
autochthon_right.nii.gz
brain.nii.gz
clavicula_left.nii.gz
clavicula_right.nii.gz
colon.nii.gz
duodenum.nii.gz
esophagus.nii.gz
femur_left.nii.gz
femur_right.nii.gz
gallbladder.nii.gz
gluteus_maximus_left.nii.gz
gluteus_maximus_right.nii.gz
gluteus_medius_left.nii.gz
gluteus_medius_right.nii.gz
gluteus_minimus_left.nii.gz
gluteus_minimus_right.nii.gz
heart.nii.gz
hip_left.nii.gz
hip_right.nii.gz
humerus_left.nii.gz
humerus_right.nii.gz
iliac_artery_left.nii.gz
iliac_artery_right.nii.gz
iliac_vena_left.nii.gz
iliac_vena_right.nii.gz
iliopsoas_left.nii.gz
iliopsoas_right.nii.gz
inferior_vena_cava.nii.gz
intervertebral_discs.nii.gz
kidney_left.nii.gz
kidney_right.nii.gz
liver.nii.gz
lung_left.nii.gz
lung_right.nii.gz
pancreas.nii.gz
portal_vein_and_splenic_vein.nii.gz
prostate.nii.gz
sacrum.nii.gz
scapula_left.nii.gz
scapula_right.nii.gz
small_bowel.nii.gz
spinal_cord.nii.gz
spleen.nii.gz
stomach.nii.gz
urinary_bladder.nii.gz
vertebrae.nii.gz
```

Not every written label is meaningful in this field of view. In the full GPU run, 16 of
the 50 label masks were non-empty. Of those, 14 are useful candidates for Frac context or
landmark work, and 2 should be treated as suspicious/noisy for this crop. The remaining
34 masks were empty out-of-FOV labels written by the generic `total_mr` task.

## Tier 1: Direct Artifact Candidate

| Mask | Nonzero voxels | Approx. volume | Frac role |
|---|---:|---:|---|
| `prostate.nii.gz` | 50364 | 37.8 mL | Whole-gland context, registration QA, lesion-search bounds, and future capsular-contact checks |

The prostate mask is the only current TotalSegmentator output that should be considered
for direct downstream Frac use after visual QA. It is not the FA analysis ROI by itself.

## Tier 2: Pelvic Landmarks for Future ROI Proposals

These masks do not give the internal-obturator muscle directly. They are useful as a
landmark constellation for a future atlas, registration, or heuristic proposer that targets
the internal-obturator calibration sample.

| Mask | Nonzero voxels | Approx. volume |
|---|---:|---:|
| `hip_left.nii.gz` | 127716 | 95.8 mL |
| `hip_right.nii.gz` | 126306 | 94.7 mL |
| `femur_left.nii.gz` | 63171 | 47.4 mL |
| `femur_right.nii.gz` | 61749 | 46.3 mL |
| `urinary_bladder.nii.gz` | 125190 | 93.9 mL |
| `iliopsoas_left.nii.gz` | 53887 | 40.4 mL |
| `iliopsoas_right.nii.gz` | 44688 | 33.5 mL |
| `gluteus_maximus_left.nii.gz` | 75241 | 56.4 mL |
| `gluteus_maximus_right.nii.gz` | 46688 | 35.0 mL |
| `iliac_artery_left.nii.gz` | 3291 | 2.5 mL |
| `iliac_artery_right.nii.gz` | 3732 | 2.8 mL |
| `iliac_vena_left.nii.gz` | 4512 | 3.4 mL |
| `iliac_vena_right.nii.gz` | 4112 | 3.1 mL |

The gluteus-maximus asymmetry is likely influenced by the limited prostate T2 field of
view. Treat these as raw evidence and landmarks, not polished user-visible overlays.

## Tier 3: Suspicious or Noisy for This Crop

| Mask | Nonzero voxels | Approx. volume | Note |
|---|---:|---:|---|
| `gluteus_medius_left.nii.gz` | 477 | 0.36 mL | Tiny sliver, probably field-of-view edge artifact |
| `colon.nii.gz` | 29136 | 21.9 mL | Not a reliable bowel/rectum boundary source on this prostate T2 crop |

These should not be promoted into Frac outputs. If Frac later needs rectum or bowel
context, use a dedicated target or reviewed annotation rather than this generic colon mask.

## Empty Out-of-FOV Labels

The other 34 masks are compressed zero masks for labels outside this prostate field of
view or not detected here. Examples include upper-body and abdominal labels such as liver,
spleen, kidneys, lungs, heart, stomach, pancreas, gallbladder, adrenals, brain, scapulae,
clavicles, humeri, vertebrae, spinal cord, and several small muscle labels.

These files are harmless as raw TotalSegmentator output, but they should be filtered before
any backend capability registry or user-facing overlay list is generated. Otherwise Frac
would overstate what the model actually segmented in this volume.

# Missing Targets

| Target | TotalSegmentator output? | Frac implication |
|---|---|---|
| Internal-obturator muscle ROI | No | Use a DCE-native seeded/landmark proposal, promptable reviewer assistance, or a future small task-specific model on the selected FA reference; do not warp the tiny fixture mask between cases or from T2 |
| Prostate zones, such as PZ/TZ/CG | No | Need a prostate-specific gland/zones model, for example a Prostate158-style nnU-Net |
| Lesion | No | Need reviewed/imported masks first, then PI-CAI-style detector or lesion segmenter experiments |
| Tumour-interface ROI | No | Still blocked on the Michallek author rule and a trustworthy lesion contour |

# Frac Usage Recommendation

For the v1 reviewed-ROI appliance, keep only `prostate.nii.gz` as a candidate direct
downstream artifact after visual QA. Its role is registration/context QA, not FA ROI
measurement.

Keep the Tier-2 labels in `seg_out/` as raw evidence for future internal-obturator ROI
proposal work. Do not promote them to user-visible overlays by default, and do not include
them in the normal user-facing `labels` list unless the frontend has a separate
landmark-only display path. Do not claim that TotalSegmentator provides the required
muscle calibration ROI; at most, it supplies landmarks for a reviewed DCE-space proposal.

For a future backend model-capability entry, TotalSegmentator should be advertised
conservatively. The sketch below includes the required field set from
[fa-backend.md](fa-backend.md), but it is not a literal schema instance. It also proposes
one schema refinement: keep user-visible segmentation labels separate from hidden raw
landmark labels so the frontend does not surface landmark masks as normal segmentation
claims.

```yaml
id: totalsegmentator-total-mr
kind: segment
engine: TotalSegmentator
status: evaluation
modalities: ["MR"]
anatomy: ["prostate", "pelvis_landmarks"]
labels: ["prostate"]
license:
  name: Apache-2.0
  commercial_allowed: true
min_vram_gb: 8
supports_4d: false
outputs:
  user_visible_masks: ["prostate"]
  raw_landmark_masks:
    - urinary_bladder
    - hip_left
    - hip_right
    - femur_left
    - femur_right
    - iliopsoas_left
    - iliopsoas_right
    - gluteus_maximus_left
    - gluteus_maximus_right
    - iliac_artery_left
    - iliac_artery_right
    - iliac_vena_left
    - iliac_vena_right
  raw_evidence_files: ["run.json", "gpu-memory.csv"]
version:
  TotalSegmentator: "2.13.0"
  torch: "2.5.1+cu121"
weights:
  source: "~/.totalsegmentator"
  distribution: downloaded-on-first-use
  checksum: TBD
observed_fixture:
  input: "subjects/prostatex-0204/t2.nii.gz"
  gpu: "Quadro T2000"
  peak_vram_mib: 3621
  runtime_s: 62
```

Before this becomes an implementation contract, align the exact field shapes with
[fa-backend.md](fa-backend.md): `kind` should use the backend's canonical enum,
`labels` may need object entries rather than strings, `outputs` may need to remain a list
of output kinds, and `version` / `weights` should follow the backend registry schema.
The important policy decision is the split between advertised user-visible masks and raw
landmark evidence.

The `min_vram_gb` value above is deliberately more conservative than the 3621 MiB peak
observed on this small crop. The measured Martha run proves that this one fixture fits
in 4 GB, not that 4 GB is enough for routine pelvic MR segmentation.

That entry should explicitly **not** advertise `muscle_roi`, prostate zones, lesion
segmentation, or tumour-interface ROI support. It should also filter empty masks and
Tier-3 noisy masks before surfacing anything to the frontend.

# GPU Notes

Torch CUDA availability depends on direct GPU device access. In the restricted shell,
`torch.cuda.is_available()` reported `False` with an NVML warning because the sandbox did
not expose the NVIDIA device/NVML path fully to Python. With direct device access, the
same virtual environment reported:

```text
torch:          2.5.1+cu121
torch CUDA:     12.1
CUDA available: True
GPU:            Quadro T2000
```

The full GPU run peaked at 3621 MiB on a 4096 MiB card, approximately 88 percent of
reported VRAM. That is acceptable for this small 384 x 384 x 21 T2 fixture, but leaves
limited headroom.

# Visual QA

The computational run is complete, but the segmentation should not be promoted until it
has been visually checked in Frac.

Load the base volume:

```text
subjects/prostatex-0204/t2.nii.gz
```

Then load the overlay:

```text
seg_out/t2-gpu-full/prostate.nii.gz
```

Acceptance for this memo is modest: confirm that the prostate mask is in the expected
anatomical location and follows the gland well enough to be a plausible candidate mask.
This does not make TotalSegmentator a validated prostate segmentation method for Frac.
It only proves that the local pipeline can produce a mask candidate and provenance for a
known T2 fixture.

# Next Experiment

The cheapest next experiment is the sequence-independent gland test described in
[fa-segment.md](fa-segment.md):

1. run `register-dce` and use its selected calibration-informed FA reference frame
2. run TotalSegmentator `total_mr` on that exact DCE reference frame
3. use `register` to move the T2-derived prostate mask into the canonical FA grid
4. compare overlap and visual alignment

This tests whether TotalSegmentator's whole-gland output is stable enough across MR
contrasts to serve as cross-series registration sanity context. It also exercises the
required ordering: DCE frames to one reference first, then T2 to that reference. It still
does not solve muscle ROI, lesion, or tumour-interface automation.

# Reproduction Checklist

1. Create `.venv-seg` and install `requirements-segmentation.txt`.
2. Install `dcm2niix` into `.venv-seg`.
3. Query TCIA for `ProstateX-0204`.
4. Download the `t2_tse_tra` `SeriesNumber 5` UID.
5. Convert DICOM to `subjects/prostatex-0204/t2.nii.gz`.
6. Run `scripts/try_totalsegmentator.sh` on CPU or GPU, using one of the commands in
   [Runs Performed](#runs-performed).
7. Inspect `run.json`.
8. Overlay `prostate.nii.gz` on `t2.nii.gz` in Frac.
9. Record visual QA before using the mask in downstream FA work.
