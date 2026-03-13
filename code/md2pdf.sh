#!/bin/bash
# Segment Platform — Markdown to PDF converter
# Adapted from SAFEGUARD BHF md2pdf.sh for the Charité Segment workspace
#
# Usage:
#   ./code/md2pdf.sh plan/sam3d.md
#   ./code/md2pdf.sh plan/sam3d.md --docx --verbose
#   ./code/md2pdf.sh plan/proposal.md --tex --no-pdf
#
# Flags:
#   --docx      Also produce a .docx file
#   --tex       Also produce a .tex file
#   --no-pdf    Skip PDF output (useful with --docx or --tex)
#   --verbose   Print resolved paths and pandoc command

set -e

# ── Defaults ──────────────────────────────────────────────────────────────────
FILE="${1:-plan/sam3d.md}"
MAKE_PDF=true
MAKE_DOCX=false
MAKE_TEX=false
VERBOSE=false

# ── Parse flags ───────────────────────────────────────────────────────────────
shift 2>/dev/null || true
for arg in "$@"; do
    case "$arg" in
        --docx)    MAKE_DOCX=true  ;;
        --tex)     MAKE_TEX=true   ;;
        --verbose) VERBOSE=true    ;;
        --no-pdf)  MAKE_PDF=false  ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# ── Validate input ─────────────────────────────────────────────────────────────
if [ ! -f "$FILE" ]; then
    echo "Error: Markdown file '$FILE' not found."
    echo "Usage: $0 [file.md] [--docx] [--tex] [--no-pdf] [--verbose]"
    exit 1
fi

# ── Resolve paths ─────────────────────────────────────────────────────────────
FULLPATH=$(realpath "$FILE")
DIR=$(dirname "$FULLPATH")
NAME=$(basename "$FULLPATH" .md)
WORKSPACE=$(realpath "$(dirname "$0")/..")   # repo root (one level above code/)

cd "$DIR"
$VERBOSE && echo "Working directory : $DIR"
$VERBOSE && echo "Workspace root    : $WORKSPACE"
$VERBOSE && echo "Input file        : $FULLPATH"
$VERBOSE && echo "Output stem       : $NAME"

# ── Detect YAML front matter ──────────────────────────────────────────────────
FRONT_MATTER=""
if [ "$(sed -n '1p' "$FULLPATH")" = "---" ]; then
    FRONT_MATTER=$(awk '
        NR == 1 { next }
        /^---[[:space:]]*$/ || /^\.\.\.[[:space:]]*$/ { exit }
        { print }
    ' "$FULLPATH")
fi

front_matter_has_key() {
    local key="$1"
    [ -n "$FRONT_MATTER" ] && printf '%s\n' "$FRONT_MATTER" | grep -Eq "^[[:space:]]*$key:"
}

$VERBOSE && { [ -n "$FRONT_MATTER" ] && echo "YAML front matter : detected" || echo "YAML front matter : none"; }

# ── Find bibliography ─────────────────────────────────────────────────────────
BIB_PATH=""
for candidate in \
    "references.bib" \
    "$WORKSPACE/plan/references.bib" \
    "$WORKSPACE/manuscript/references.bib" \
    "$WORKSPACE/flow/references.bib"; do
    if [ -f "$candidate" ]; then
        BIB_PATH=$(realpath "$candidate")
        break
    fi
done
$VERBOSE && { [ -n "$BIB_PATH" ] && echo "Bibliography      : $BIB_PATH" || echo "Bibliography      : (none found)"; }

# ── Find CSL ──────────────────────────────────────────────────────────────────
CSL_PATH=""
for candidate in \
    "vancouver-superscript.csl" \
    "nature.csl" \
    "vancouver.csl" \
    "$WORKSPACE/code/vancouver-superscript.csl" \
    "$WORKSPACE/code/nature.csl" \
    "$WORKSPACE/code/vancouver.csl" \
    "$WORKSPACE/plan/nature.csl" \
    "$WORKSPACE/plan/vancouver-superscript.csl" \
    "$WORKSPACE/manuscript/nature.csl" \
    "$WORKSPACE/manuscript/vancouver-superscript.csl"; do
    if [ -f "$candidate" ]; then
        CSL_PATH=$(realpath "$candidate")
        break
    fi
done
$VERBOSE && { [ -n "$CSL_PATH" ] && echo "CSL style         : $CSL_PATH" || echo "CSL style         : (none found)"; }

# ── Font detection ────────────────────────────────────────────────────────────
# Preference order: Arial > Noto Sans > Liberation Sans > DejaVu Sans
# Noto is preferred on Linux because it has full Unicode + emoji coverage
MAINFONT="Arial"
if ! fc-list | grep -qi "arial"; then
    if fc-list | grep -qi "Noto Sans" && ! fc-list | grep -qi "Noto Sans Mono"; then
        MAINFONT="Noto Sans"
    elif fc-list | grep -qi "Noto Sans"; then
        MAINFONT="Noto Sans"
    elif fc-list | grep -qi "Liberation Sans"; then
        MAINFONT="Liberation Sans"
    else
        MAINFONT="DejaVu Sans"
    fi
fi

MONOFONT="Consolas"
if ! fc-list | grep -qi "consolas"; then
    if fc-list | grep -qi "Noto Sans Mono"; then
        MONOFONT="Noto Sans Mono"
    elif fc-list | grep -qi "Liberation Mono"; then
        MONOFONT="Liberation Mono"
    else
        MONOFONT="DejaVu Sans Mono"
    fi
fi

$VERBOSE && echo "Main font         : $MAINFONT"
$VERBOSE && echo "Mono font         : $MONOFONT"

# ── Build common pandoc args ──────────────────────────────────────────────────
COMMON_ARGS=("$FULLPATH" "--filter=pandoc-crossref" "--citeproc")

[ -n "$BIB_PATH" ] && ! front_matter_has_key "bibliography" && COMMON_ARGS+=("--bibliography=$BIB_PATH")
[ -n "$CSL_PATH" ] && ! front_matter_has_key "csl" && COMMON_ARGS+=("--csl=$CSL_PATH")

COMMON_ARGS+=("--highlight-style=tango")
! front_matter_has_key "date" && COMMON_ARGS+=("-M" "date=$(date +'%B %Y')")
! front_matter_has_key "toc" && COMMON_ARGS+=("--toc")
! front_matter_has_key "toc-depth" && COMMON_ARGS+=("--toc-depth=3")
! front_matter_has_key "numbersections" && COMMON_ARGS+=("--number-sections")

# ── PDF output ────────────────────────────────────────────────────────────────
if $MAKE_PDF; then
    PDF_OUT="$DIR/$NAME.pdf"

    PDF_ARGS=(
        "${COMMON_ARGS[@]}"
        "--pdf-engine=xelatex"
        "--pdf-engine-opt=-interaction=nonstopmode"
        "-o" "$PDF_OUT"
        "-V" "mainfont:$MAINFONT"
        "-V" "monofont:$MONOFONT"
        "-V" "mathfont:Latin Modern Math"
        "-V" "papersize:a4"
    )
    ! front_matter_has_key "fontsize" && PDF_ARGS+=("-V" "fontsize:11pt")
    ! front_matter_has_key "geometry" && PDF_ARGS+=("-V" "geometry:margin=1in")
    ! front_matter_has_key "linestretch" && PDF_ARGS+=("-V" "linestretch:1.2")

    echo "▶ Building PDF: $PDF_OUT"
    $VERBOSE && echo "  pandoc ${PDF_ARGS[*]}"
    pandoc "${PDF_ARGS[@]}"
    echo "✓ PDF created : $PDF_OUT"
fi

# ── DOCX output ───────────────────────────────────────────────────────────────
if $MAKE_DOCX; then
    DOCX_OUT="$DIR/$NAME.docx"
    DOCX_ARGS=("${COMMON_ARGS[@]}" "-o" "$DOCX_OUT")
    echo "▶ Building DOCX: $DOCX_OUT"
    $VERBOSE && echo "  pandoc ${DOCX_ARGS[*]}"
    pandoc "${DOCX_ARGS[@]}"
    echo "✓ DOCX created : $DOCX_OUT"
fi

# ── TEX output ────────────────────────────────────────────────────────────────
if $MAKE_TEX; then
    TEX_OUT="$DIR/$NAME.tex"
    TEX_ARGS=("${COMMON_ARGS[@]}" "--standalone" "-o" "$TEX_OUT")
    echo "▶ Building TEX: $TEX_OUT"
    $VERBOSE && echo "  pandoc ${TEX_ARGS[*]}"
    pandoc "${TEX_ARGS[@]}"
    echo "✓ TEX created : $TEX_OUT"
fi

echo ""
echo "Done."
