from flask import Flask, render_template, request, jsonify
import json
import csv
import io
from pathlib import Path
from itertools import product

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

app = Flask(__name__)


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


def parse_input(content):
    content = content.strip()
    if not content:
        raise ValueError("Input cannot be empty")

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        if YAML_AVAILABLE:
            try:
                data = yaml.safe_load(content)
            except:
                raise ValueError("Invalid JSON or YAML format")
        else:
            raise ValueError("Invalid JSON format. Install PyYAML to support YAML input.")

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data

    raise ValueError("Input must be a JSON object or array")


def convert_to_csv(rows, expand=False):
    if not rows:
        raise ValueError("No data to convert")

    flat_rows = []

    for row in rows:
        if expand:
            flat_rows.extend(flatten_expand(row))
        else:
            flat_rows.append(flatten_inline(row))

    all_keys = []
    for row in flat_rows:
        for key in row.keys():
            if key not in all_keys:
                all_keys.append(key)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=all_keys)
    writer.writeheader()
    for row in flat_rows:
        writer.writerow({key: row.get(key, "") for key in all_keys})

    return output.getvalue()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/convert", methods=["POST"])
def api_convert():
    try:
        data = request.json
        content = data.get("content", "").strip()
        expand = data.get("expand", False)

        if not content:
            return jsonify({"error": "Input cannot be empty"}), 400

        rows = parse_input(content)
        csv_content = convert_to_csv(rows, expand=expand)

        return jsonify({
            "success": True,
            "csv": csv_content
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
