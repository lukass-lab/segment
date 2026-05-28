#!/usr/bin/env bash
# Pandoc-based Markdown build helper, adapted from the mednet paper layout.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./md2pdf.sh [file.md] [options]

Options:
  --docx           Also build DOCX output
  --tex            Also build TeX output
  --no-pdf         Skip PDF output
  --csl PATH       Use an explicit CSL file
  --fontsize SIZE  Override PDF font size, e.g. 11pt or 12pt
  --margin VALUE   Override PDF margin, e.g. 1in or 2.5cm
  --verbose        Print resolved inputs and pandoc commands
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

needs_crossref_filter() {
    local file="$1"
    grep -Eq '(@(fig|tbl|eq)[[:alnum:]_:-]*|\{#(fig|tbl|eq):|^[[:space:]]*(figPrefix|tblPrefix|eqnPrefix)[[:space:]]*:)' "$file"
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
        --verbose)
            VERBOSE=true
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

[[ -n "$FILE" ]] || die "Please provide a markdown file. Run with --help for usage."
[[ -f "$FILE" ]] || die "Markdown file '$FILE' not found."

if ! $MAKE_PDF && ! $MAKE_DOCX && ! $MAKE_TEX; then
    die "Nothing to build. Remove --no-pdf or add --docx and/or --tex."
fi

command_exists pandoc || die "pandoc is not installed."
if $MAKE_PDF; then
    command_exists xelatex || die "xelatex is not installed."
fi

FULLPATH="$(realpath "$FILE")"
DIR="$(dirname "$FULLPATH")"
NAME="$(basename "$FULLPATH" .md)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(realpath "$SCRIPT_DIR/..")"

if [[ -n "$CSL_OVERRIDE" ]]; then
    [[ -f "$CSL_OVERRIDE" ]] || die "CSL file '$CSL_OVERRIDE' not found."
    CSL_OVERRIDE="$(realpath "$CSL_OVERRIDE")"
fi

cd "$DIR"

FRONT_MATTER="$(read_front_matter "$FULLPATH")"
CROSSREF_NEEDED=false
if needs_crossref_filter "$FULLPATH"; then
    CROSSREF_NEEDED=true
    command_exists pandoc-crossref || die "pandoc-crossref is required by '$FILE' but is not installed."
fi

BIB_PATH="$(first_existing_file \
    "references.bib" \
    "../references.bib" \
    "$SCRIPT_DIR/references.bib" \
    "$REPO_ROOT/references.bib" || true)"

if [[ -n "$CSL_OVERRIDE" ]]; then
    CSL_PATH="$CSL_OVERRIDE"
else
    CSL_PATH="$(first_existing_file \
        "vancouver-superscript.csl" \
        "nature.csl" \
        "vancouver.csl" \
        "../vancouver-superscript.csl" \
        "../nature.csl" \
        "../vancouver.csl" \
        "$SCRIPT_DIR/vancouver-superscript.csl" \
        "$SCRIPT_DIR/nature.csl" \
        "$SCRIPT_DIR/vancouver.csl" \
        "$REPO_ROOT/vancouver-superscript.csl" \
        "$REPO_ROOT/nature.csl" \
        "$REPO_ROOT/vancouver.csl" || true)"
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
if [[ -n "$MARGIN_OVERRIDE" && "$MARGIN_OVERRIDE" != *=* ]]; then
    DEFAULT_MARGIN="margin=$MARGIN_OVERRIDE"
else
    DEFAULT_MARGIN="${MARGIN_OVERRIDE:-margin=2cm}"
fi

COMMON_ARGS=("$FULLPATH" "--citeproc" "--syntax-highlighting=tango")

if $CROSSREF_NEEDED; then
    COMMON_ARGS+=("--filter=pandoc-crossref")
fi

if [[ -n "$BIB_PATH" ]] && ! front_matter_has_key "bibliography"; then
    COMMON_ARGS+=("--bibliography=$BIB_PATH")
fi

if [[ -n "${CSL_PATH:-}" ]] && ! front_matter_has_key "csl"; then
    COMMON_ARGS+=("--csl=$CSL_PATH")
fi

if ! front_matter_has_key "date"; then
    COMMON_ARGS+=("-M" "date=$(date +'%B %Y')")
fi

if ! front_matter_has_key "toc"; then
    COMMON_ARGS+=("--toc")
fi

if ! front_matter_has_key "toc-depth"; then
    COMMON_ARGS+=("--toc-depth=3")
fi

if ! front_matter_has_key "numbersections" && ! front_matter_has_key "number-sections"; then
    COMMON_ARGS+=("--number-sections")
fi

$VERBOSE && echo "Working directory : $DIR"
$VERBOSE && echo "Script directory  : $SCRIPT_DIR"
$VERBOSE && echo "Repository root   : $REPO_ROOT"
$VERBOSE && echo "Input file        : $FULLPATH"
$VERBOSE && echo "Output stem       : $NAME"
$VERBOSE && { [[ -n "$FRONT_MATTER" ]] && echo "YAML front matter : detected" || echo "YAML front matter : none"; }
$VERBOSE && { [[ -n "$BIB_PATH" ]] && echo "Bibliography      : $BIB_PATH" || echo "Bibliography      : (none found)"; }
$VERBOSE && { [[ -n "${CSL_PATH:-}" ]] && echo "CSL style         : $CSL_PATH" || echo "CSL style         : (none found)"; }
$VERBOSE && echo "Main font         : $MAINFONT"
$VERBOSE && echo "Mono font         : $MONOFONT"

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

    if ! front_matter_has_key "fontsize"; then
        PDF_ARGS+=("-V" "fontsize:$DEFAULT_FONT_SIZE")
    fi

    if ! front_matter_has_key "geometry"; then
        PDF_ARGS+=("-V" "geometry:$DEFAULT_MARGIN")
    fi

    if ! front_matter_has_key "linestretch"; then
        PDF_ARGS+=("-V" "linestretch:1.2")
    fi

    # Colored links (Contents entries, cross-doc links, URLs) — matches the
    # mednet PDF style. Skipped if a doc sets these in its own front matter.
    # toccolor is required separately: pandoc's template resets TOC link color
    # unless it is set explicitly, even when colorlinks is on.
    if ! front_matter_has_key "colorlinks"; then
        PDF_ARGS+=("-V" "colorlinks:true")
    fi
    if ! front_matter_has_key "linkcolor"; then
        PDF_ARGS+=("-V" "linkcolor:blue")
    fi
    if ! front_matter_has_key "urlcolor"; then
        PDF_ARGS+=("-V" "urlcolor:blue")
    fi
    if ! front_matter_has_key "toccolor"; then
        PDF_ARGS+=("-V" "toccolor:blue")
    fi

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
