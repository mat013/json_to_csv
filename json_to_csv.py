"""
json_to_csv.py - Konverterer et eller flere JSON/YAML dokumenter til CSV format.

Filformat detekteres automatisk ud fra extension:
  .json        → læses som JSON
  .yml / .yaml → læses som YAML

Tilstande:
  Standard:    Lister placeres i samme celle (semikolon-separeret)
  --expand:    Lister ekspanderes til flere rækker (cartesian product ved flere lister)

Nested objekter flades altid ud med dot-notation.
Ved flere inputfiler tilføjes en '_kilde' kolonne automatisk.

Brug:
    python json_to_csv.py input.json
    python json_to_csv.py input.yml
    python json_to_csv.py input.json output.csv --expand
    python json_to_csv.py "data/*.json" output.csv
    python json_to_csv.py "data/**/*.yml" output.csv
    python json_to_csv.py "data/**/*" output.csv          (blandet json + yaml)

Afhængigheder:
    Standardbibliotek: json, csv, glob, argparse (ingen installation nødvendig)
    Tredjepart:        pyyaml  (kun nødvendig ved .yml/.yaml filer)
                       Installer med: pip install pyyaml
"""

import json
import csv
import sys
import argparse
import glob
from pathlib import Path
from itertools import product

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fil-opløsning
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".json", ".yml", ".yaml"}


def resolve_files(pattern: str) -> list:
    """
    Finder alle filer der matcher et mønster (understøtter wildcards og **).
    Filtrerer til understøttede filtyper og returnerer en sorteret liste.
    """
    matched = glob.glob(pattern, recursive=True)
    if not matched:
        print(f"Fejl: Ingen filer matchede mønsteret '{pattern}'.")
        sys.exit(1)

    files = sorted(
        Path(p) for p in matched
        if Path(p).is_file() and Path(p).suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        print(
            f"Fejl: Mønsteret '{pattern}' matchede ingen understøttede filer "
            f"({', '.join(SUPPORTED_EXTENSIONS)})."
        )
        sys.exit(1)

    return files


# ---------------------------------------------------------------------------
# Fil indlæsning (JSON + YAML)
# ---------------------------------------------------------------------------

def load_file(path: Path) -> list:
    ext = path.suffix.lower()
    with open(path, "r", encoding="utf-8") as f:
        if ext == ".json":
            data = json.load(f)
        elif ext in {".yml", ".yaml"}:
            if not YAML_AVAILABLE:
                print("Fejl: PyYAML er ikke installeret. Kør: pip install pyyaml")
                sys.exit(1)
            data = yaml.safe_load(f)
        else:
            print(f"Fejl: Ukendt filtype '{ext}' for '{path}'.")
            sys.exit(1)

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data

    print(f"Fejl: '{path}' – roden skal være et objekt {{}} eller en liste [].")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CSV skrivning
# ---------------------------------------------------------------------------

def write_csv(csv_path, flat_rows, source_column=None):
    all_keys = []
    if source_column:
        all_keys.append(source_column)
    for row in flat_rows:
        for key in row.keys():
            if key not in all_keys:
                all_keys.append(key)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in flat_rows:
            writer.writerow({key: row.get(key, "") for key in all_keys})

    print(f"Færdig! CSV gemt som: {csv_path}")
    print(f"  Rækker  : {len(flat_rows)}")
    print(f"  Kolonner: {len(all_keys)}")


# ---------------------------------------------------------------------------
# Tilstand 1: Lister i samme celle
# ---------------------------------------------------------------------------

def inline_list(lst):
    parts = []
    for item in lst:
        if isinstance(item, dict):
            parts.append(json.dumps(item, ensure_ascii=False))
        elif isinstance(item, list):
            parts.append(inline_list(item))
        else:
            parts.append(str(item) if item is not None else "")
    return "; ".join(parts)


def flatten_inline(obj, parent_key="", sep="."):
    items = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            if isinstance(value, dict):
                items.update(flatten_inline(value, new_key, sep))
            elif isinstance(value, list):
                items[new_key] = inline_list(value)
            else:
                items[new_key] = value
    return items


# ---------------------------------------------------------------------------
# Tilstand 2: Lister ekspanderes til flere rækker
# ---------------------------------------------------------------------------

def flatten_expand(obj, parent_key="", sep="."):
    scalar_fields = {}
    list_fields = {}

    for key, value in obj.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            sub_rows = flatten_expand(value, new_key, sep)
            if len(sub_rows) == 1:
                scalar_fields.update(sub_rows[0])
            else:
                list_fields[new_key] = sub_rows
        elif isinstance(value, list):
            expanded = expand_list(value, new_key, sep)
            if len(expanded) == 1 and not any(isinstance(i, dict) for i in value):
                scalar_fields.update(expanded[0])
            else:
                list_fields[new_key] = expanded
        else:
            scalar_fields[new_key] = value

    if not list_fields:
        return [scalar_fields]

    list_groups = list(list_fields.values())
    result_rows = []
    for combo in product(*list_groups):
        row = dict(scalar_fields)
        for part in combo:
            row.update(part)
        result_rows.append(row)

    return result_rows


def expand_list(lst, parent_key, sep="."):
    all_rows = []
    for item in lst:
        if isinstance(item, dict):
            all_rows.extend(flatten_expand(item, parent_key, sep))
        elif isinstance(item, list):
            all_rows.extend(expand_list(item, parent_key, sep))
        else:
            all_rows.append({parent_key: str(item) if item is not None else ""})
    return all_rows if all_rows else [{parent_key: ""}]


# ---------------------------------------------------------------------------
# Hoved
# ---------------------------------------------------------------------------

def json_to_csv(pattern, csv_path=None, expand=False, only_filename=True):
    files = resolve_files(pattern)
    multiple = len(files) > 1
    source_column = "_kilde" if multiple else None

    if multiple:
        print(f"Fandt {len(files)} filer:")
        for f in files:
            print(f"  {f}")

    all_flat_rows = []

    for path in files:
        rows = load_file(path)

        if expand:
            flat_rows = []
            for row in rows:
                flat_rows.extend(flatten_expand(row))
        else:
            flat_rows = [flatten_inline(row) for row in rows]

        if source_column:
            for row in flat_rows:
                row[source_column] = str(path) if not only_filename else path.name

        all_flat_rows.extend(flat_rows)

    if csv_path is None:
        if multiple:
            csv_path = "output.csv"
        else:
            csv_path = str(files[0].with_suffix(".csv"))

    write_csv(csv_path, all_flat_rows, source_column)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Konverterer JSON/YAML fil(er) til CSV.\n"
            "Filformat detekteres automatisk: .json → JSON, .yml/.yaml → YAML.\n"
            "Understøtter wildcards og ** rekursiv søgning."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        help="Sti eller wildcard-mønster, fx 'data/*.yml' eller 'data/**/*.json'",
    )
    parser.add_argument("output", nargs="?", help="Sti til output CSV-fil (valgfri)")
    parser.add_argument(
        "--expand",
        action="store_true",
        help="Ekspander lister til flere rækker i stedet for at samle dem i én celle",
    )
    parser.add_argument(
        "--absolut-sti",
        action="store_false",
        dest="only_filename",
        help="Vis den fulde sti i '_kilde' kolonnen i stedet for kun filnavnet",
    )
    args = parser.parse_args()

    json_to_csv(args.input, args.output, expand=args.expand, only_filename=args.only_filename)
