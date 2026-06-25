# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**json_to_csv** is a Python utility that converts JSON and YAML files to CSV format. It supports wildcards and recursive patterns, and offers two modes for handling nested arrays: inline (compact) and expand (cartesian product).

The tool automatically detects file format from extension (.json, .yml, .yaml) and handles mixed file types. When processing multiple files, it adds a `_kilde` (source) column. Nested objects are always flattened using dot notation (e.g., `person.name.first`).

## Running the Tool

### CLI Mode

**Basic usage:**
```bash
python json_to_csv.py input.json
python json_to_csv.py input.yml output.csv
```

**With wildcards:**
```bash
python json_to_csv.py "data/*.json" output.csv
python json_to_csv.py "data/**/*.yml" output.csv    # recursive
python json_to_csv.py "data/**/*" output.csv         # mixed JSON and YAML
```

**Expand mode** (expands lists into multiple rows using cartesian product):
```bash
python json_to_csv.py input.json output.csv --expand
```

**Full path in source column** (instead of just filename):
```bash
python json_to_csv.py "data/*.json" output.csv --absolut-sti
```

### Web App Mode

Start the Flask web interface:
```bash
./run.sh
```

Then open http://localhost:5000 in your browser. The interface provides:
- Textarea for pasting JSON/YAML input
- Checkbox for expand mode
- Real-time CSV preview
- Copy to clipboard and download buttons

## Dependencies

- **Standard library** (always available): json, csv, sys, argparse, glob, pathlib, itertools
- **PyYAML** (optional, only needed for .yml/.yaml files): Install with `pip install -r requirement.txt`

Note: The script gracefully handles missing PyYAML and exits with an error message if YAML files are encountered without it.

## Architecture

The single `json_to_csv.py` file is organized into logical sections:

### File Resolution (`resolve_files`)
Glob-based pattern matching that:
- Expands wildcards and `**` recursive patterns
- Filters to supported extensions (.json, .yml, .yaml)
- Returns a sorted list of Path objects
- Exits with an error if no files match the pattern

### File Loading (`load_file`)
Detects format by extension and loads data:
- JSON files: standard `json.load()`
- YAML files: `yaml.safe_load()` (fails gracefully if PyYAML not installed)
- Normalizes single objects to a list: `{"key": "val"}` → `[{"key": "val"}]`
- Validates that root is object or array; exits if not

### CSV Output (`write_csv`)
Collects all columns from all rows, then:
- Writes headers in the order columns are discovered
- Uses `utf-8-sig` encoding (standard for Excel)
- Prints summary: row and column counts

### Flattening Modes

**Inline mode** (`flatten_inline`, default):
- Nested dicts become dot-separated keys
- Lists remain as semicolon-separated strings in a single cell
- Nested lists are serialized as JSON
- Result: one row per input object, compact output

**Expand mode** (`flatten_expand` + `expand_list`):
- Nested dicts become dot-separated keys (same as inline)
- Lists trigger row expansion: each item becomes a separate row
- Multiple lists in one object produce cartesian product (all combinations)
- Scalar lists (non-dict items) with a single element stay inline
- Result: possibly many rows per input object; explores all list combinations

The key difference: inline mode preserves structure in cells; expand mode denormalizes to flat rows.

### Main Entry Point
`json_to_csv()` function orchestrates the workflow:
1. Resolve input files
2. Load and flatten each file
3. Add `_kilde` column if multiple files
4. Combine all rows
5. Auto-generate output path if not specified
6. Write CSV

## Key Design Decisions

- **Format detection by extension**: No sniffing; extension is the source of truth. This keeps logic simple and predictable.
- **Dot notation for nesting**: Unambiguous and spreadsheet-friendly; avoids the need for multi-level headers.
- **Cartesian product for expand mode**: Ensures all combinations of list items are represented. Useful for exploding denormalized data.
- **Source column only on multi-file runs**: Reduces clutter for single-file conversions; automatically added when needed.
- **Filename vs. full path**: Defaults to filename only (simpler, more readable); `--absolut-sti` flag for full paths if needed.
- **Graceful degradation for PyYAML**: Script runs fine without it; only fails if a YAML file is encountered.

## Web App Structure

**app.py** - Flask application that exposes the conversion logic via a REST API:
- `/` - Serves the web interface (index.html)
- `/api/convert` - POST endpoint that accepts JSON/YAML and returns CSV

**templates/index.html** - Web interface with:
- Textarea for JSON/YAML input
- Checkbox for expand mode toggle
- Convert button that calls the API
- CSV preview with row/column stats
- Copy and download buttons
- Error/success messaging
- Loading spinner

The web app reuses the core flattening functions from json_to_csv.py to ensure identical behavior between CLI and web modes.

## Testing Strategy

For CLI mode, verify changes with:
1. Test with sample JSON/YAML files
2. Verify glob patterns work (including `**` recursion)
3. Compare inline vs. expand output on nested structures
4. Check multi-file runs include `_kilde` column
5. Verify CSV encoding compatibility with Excel

For web mode, verify:
1. Input validation and error messages
2. CSV download and copy functionality
3. Expand mode toggle works correctly
4. Large CSV preview (truncated to 20 lines for performance)

