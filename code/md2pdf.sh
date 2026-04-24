#!/usr/bin/env bash
# Pandoc-based Markdown builder for the Segment workspace.
# Merged with the useful parts of the newer proposal/compression helpers while
# preserving Segment's repo-root paths for YAML metadata.
#
# Usage:
#   ./code/md2pdf.sh [file.md] [--docx] [--tex] [--no-pdf] [--csl PATH]
#   ./code/md2pdf.sh col/proposal.md --verbose

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./code/md2pdf.sh [file.md] [options]

Options:
  --docx           Also build DOCX
  --tex            Also build TeX
  --no-pdf         Skip PDF generation
  --csl PATH       Use an explicit CSL file
  --fontsize SIZE  Override PDF font size, e.g. 11pt or 12pt
  --margin VALUE   Override PDF margin, e.g. 1in or 2.5cm
  --verbose        Print resolved inputs and full pandoc commands
  -h, --help       Show this help
EOF
}

die() {
    echo "Error: $*" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

font_available() {
    local query="$1"
    command_exists fc-list && fc-list | grep -Fqi "$query"
}

read_front_matter() {
    local file="$1"

    if [[ "$(sed -n '1p' "$file")" != "---" ]]; then
        return 0
    fi

    awk '
        NR == 1 { next }
        /^---[[:space:]]*$/ || /^\.\.\.[[:space:]]*$/ { exit }
        { print }
    ' "$file"
}

front_matter_has_key() {
    local key="$1"
    [[ -n "$FRONT_MATTER" ]] && printf '%s\n' "$FRONT_MATTER" | grep -Eq "^[[:space:]]*${key}[[:space:]]*:"
}

first_existing_file() {
    local candidate
    for candidate in "$@"; do
        if [[ -f "$candidate" ]]; then
            realpath "$candidate"
            return 0
        fi
    done
    return 1
}

FILE=""
MAKE_PDF=true
MAKE_DOCX=false
MAKE_TEX=false
VERBOSE=false
CSL_OVERRIDE=""
FONT_SIZE_OVERRIDE=""
MARGIN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --docx)
            MAKE_DOCX=true
            ;;
        --tex)
            MAKE_TEX=true
            ;;
        --no-pdf)
            MAKE_PDF=false
            ;;
        --csl)
            shift
            [[ $# -gt 0 ]] || die "--csl requires a file path."
            CSL_OVERRIDE="$1"
            ;;
        --fontsize)
            shift
            [[ $# -gt 0 ]] || die "--fontsize requires a value like 11pt."
            FONT_SIZE_OVERRIDE="$1"
            ;;
        --margin)
            shift
            [[ $# -gt 0 ]] || die "--margin requires a value like 1in or 2.5cm."
            MARGIN_OVERRIDE="$1"
            ;;
        --verbose)
            VERBOSE=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            die "Unknown option: $1"
            ;;
        *)
            [[ -z "$FILE" ]] || die "Only one markdown file may be specified."
            FILE="$1"
            ;;
    esac
    shift
done

FILE="${FILE:-col/proposal.md}"
[[ -f "$FILE" ]] || die "Markdown file '$FILE' not found."

if ! $MAKE_PDF && ! $MAKE_DOCX && ! $MAKE_TEX; then
    die "Nothing to build. Remove --no-pdf or add --docx and/or --tex."
fi

command_exists pandoc || die "pandoc is not installed."
command_exists pandoc-crossref || die "pandoc-crossref is not installed."
if $MAKE_PDF; then
    command_exists xelatex || die "xelatex is not installed."
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(realpath "$SCRIPT_DIR/..")"
FULLPATH="$(realpath "$FILE")"
DIR="$(dirname "$FULLPATH")"
NAME="$(basename "$FULLPATH" .md)"

if [[ -n "$CSL_OVERRIDE" ]]; then
    [[ -f "$CSL_OVERRIDE" ]] || die "CSL file '$CSL_OVERRIDE' not found."
    CSL_OVERRIDE="$(realpath "$CSL_OVERRIDE")"
fi

FRONT_MATTER="$(read_front_matter "$FULLPATH")"

BIB_PATH="$(first_existing_file \
    "$DIR/references.bib" \
    "$DIR/../references.bib" \
    "$DIR/../../references.bib" \
    "$WORKSPACE/col/references.bib" \
    "$WORKSPACE/plan/references.bib" \
    "$WORKSPACE/code/references.bib" \
    "$WORKSPACE/references.bib" \
    "$WORKSPACE/manuscript/references.bib" \
    "$WORKSPACE/flow/references.bib" || true)"

CSL_PATH=""
if [[ -n "$CSL_OVERRIDE" ]]; then
    CSL_PATH="$CSL_OVERRIDE"
else
    CSL_PATH="$(first_existing_file \
        "$DIR/vancouver-superscript.csl" \
        "$DIR/nature.csl" \
        "$DIR/vancouver.csl" \
        "$DIR/../vancouver-superscript.csl" \
        "$DIR/../nature.csl" \
        "$DIR/../vancouver.csl" \
        "$WORKSPACE/plan/vancouver-superscript.csl" \
        "$WORKSPACE/plan/nature.csl" \
        "$WORKSPACE/plan/vancouver.csl" \
        "$WORKSPACE/code/vancouver-superscript.csl" \
        "$WORKSPACE/code/nature.csl" \
        "$WORKSPACE/code/vancouver.csl" \
        "$WORKSPACE/manuscript/vancouver-superscript.csl" \
        "$WORKSPACE/manuscript/nature.csl" \
        "$WORKSPACE/manuscript/vancouver.csl" || true)"
fi

MAINFONT="Arial"
if ! font_available "Arial"; then
    if font_available "Noto Sans"; then
        MAINFONT="Noto Sans"
    elif font_available "Liberation Sans"; then
        MAINFONT="Liberation Sans"
    else
        MAINFONT="DejaVu Sans"
    fi
fi

MONOFONT="Consolas"
if ! font_available "Consolas"; then
    if font_available "IBM Plex Mono"; then
        MONOFONT="IBM Plex Mono"
    elif font_available "Noto Sans Mono"; then
        MONOFONT="Noto Sans Mono"
    elif font_available "Courier New"; then
        MONOFONT="Courier New"
    elif font_available "Liberation Mono"; then
        MONOFONT="Liberation Mono"
    else
        MONOFONT="DejaVu Sans Mono"
    fi
fi

DEFAULT_FONT_SIZE="${FONT_SIZE_OVERRIDE:-11pt}"
if [[ -n "$MARGIN_OVERRIDE" ]]; then
    if [[ "$MARGIN_OVERRIDE" == *=* ]]; then
        DEFAULT_MARGIN="$MARGIN_OVERRIDE"
    else
        DEFAULT_MARGIN="margin=$MARGIN_OVERRIDE"
    fi
else
    DEFAULT_MARGIN="margin=1in"
fi
RESOURCE_PATH="$WORKSPACE:$DIR:$WORKSPACE/col:$WORKSPACE/plan:$WORKSPACE/code"
COMMON_ARGS=(
    "$FULLPATH"
    "--resource-path=$RESOURCE_PATH"
    "--filter=pandoc-crossref"
    "--citeproc"
    "--highlight-style=tango"
)

[[ -n "$BIB_PATH" ]] && ! front_matter_has_key "bibliography" && COMMON_ARGS+=("--bibliography=$BIB_PATH")
[[ -n "$CSL_PATH" ]] && ! front_matter_has_key "csl" && COMMON_ARGS+=("--csl=$CSL_PATH")
front_matter_has_key "date" || COMMON_ARGS+=("-M" "date=$(date +'%B %Y')")
front_matter_has_key "toc" || COMMON_ARGS+=("--toc")
front_matter_has_key "toc-depth" || COMMON_ARGS+=("--toc-depth=3")
front_matter_has_key "numbersections" || COMMON_ARGS+=("--number-sections")

if $VERBOSE; then
    echo "Workspace     : $WORKSPACE"
    echo "Input file    : $FULLPATH"
    echo "Output stem   : $DIR/$NAME"
    echo "Bibliography  : ${BIB_PATH:-none found}"
    echo "CSL style     : ${CSL_PATH:-none found}"
    echo "Resource path : $RESOURCE_PATH"
    echo "Main font     : $MAINFONT"
    echo "Mono font     : $MONOFONT"
    echo "Font size     : $DEFAULT_FONT_SIZE"
    echo "Margin        : $DEFAULT_MARGIN"
    [[ -n "$FRONT_MATTER" ]] && echo "YAML          : detected" || echo "YAML          : none"
fi

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
    front_matter_has_key "fontsize" || PDF_ARGS+=("-V" "fontsize:$DEFAULT_FONT_SIZE")
    front_matter_has_key "geometry" || PDF_ARGS+=("-V" "geometry:$DEFAULT_MARGIN")
    front_matter_has_key "linestretch" || PDF_ARGS+=("-V" "linestretch:1.2")

    echo "Building PDF: $PDF_OUT"
    $VERBOSE && echo "pandoc ${PDF_ARGS[*]}"
    pandoc "${PDF_ARGS[@]}"
    echo "PDF created: $PDF_OUT"
fi

if $MAKE_DOCX; then
    DOCX_OUT="$DIR/$NAME.docx"
    DOCX_ARGS=("${COMMON_ARGS[@]}" "-o" "$DOCX_OUT")
    echo "Building DOCX: $DOCX_OUT"
    $VERBOSE && echo "pandoc ${DOCX_ARGS[*]}"
    pandoc "${DOCX_ARGS[@]}"
    echo "DOCX created: $DOCX_OUT"
fi

if $MAKE_TEX; then
    TEX_OUT="$DIR/$NAME.tex"
    TEX_ARGS=("${COMMON_ARGS[@]}" "--standalone" "-o" "$TEX_OUT")
    echo "Building TEX: $TEX_OUT"
    $VERBOSE && echo "pandoc ${TEX_ARGS[*]}"
    pandoc "${TEX_ARGS[@]}"
    echo "TEX created: $TEX_OUT"
fi

echo "Done."
