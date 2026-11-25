
#!/usr/bin/env python3
"""
Generic Tableau-to-Strategy Migration Mapper

Reads a Tableau inventory JSON and generates a Strategy migration mapping plan.

Usage:
    python migration_mapper.py path/to/inventory.json

Optional:
    python migration_mapper.py path/to/inventory.json --output path/to/output.json
"""

import argparse
import json
import re
from pathlib import Path


# --------------------------------------------------
# 1. Normalize names to handle different JSON key styles
# --------------------------------------------------

def normalize(value):
    """Convert names to lowercase without spaces or special characters."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


# --------------------------------------------------
# 2. Extract a readable object name
# --------------------------------------------------

def get_object_name(item, fallback):
    """Get an object's name from common JSON property names."""

    if isinstance(item, dict):
        possible_names = [
            "name",
            "caption",
            "title",
            "display_name",
            "field_name",
            "worksheet_name",
            "dashboard_name",
            "table_name",
            "datasource_name",
        ]

        normalized_item = {
            normalize(key): value
            for key, value in item.items()
        }

        for key in possible_names:
            value = normalized_item.get(normalize(key))

            if isinstance(value, (str, int, float)):
                return str(value)

    if isinstance(item, str):
        return item

    return fallback


# --------------------------------------------------
# 3. Define Tableau-to-Strategy mapping rules
# --------------------------------------------------

SECTION_RULES = {
    "datasources": ("Data Source", "Dataset / Cube"),
    "tables": ("Table", "Logical Table"),
    "dimensions": ("Dimension", "Attribute"),
    "measures": ("Measure", "Metric"),
    "calculatedfields": (
        "Calculated Field",
        "Derived Attribute / Metric"
    ),
    "filters": ("Filter", "Filter / Selector"),
    "parameters": ("Parameter", "Prompt / Selector"),
    "worksheets": ("Worksheet", "Visualization"),
    "dashboards": ("Dashboard", "Dossier"),
    "actions": ("Dashboard Action", "Selector / Interaction"),
    "groups": ("Group", "Attribute / Group"),
    "sets": ("Set", "Attribute / Set"),
    "bins": ("Bin", "Attribute / Bin"),
}

# These keys may represent a collection of Tableau fields.
FIELD_SECTION_KEYS = {
    "columns",
    "fields",
}


# --------------------------------------------------
# 4. Classify fields using their available metadata
# --------------------------------------------------

def classify_field(item):
    """
    Decide whether a field should become an Attribute or Metric.
    Use available metadata; do not guess when it is unclear.
    """

    if not isinstance(item, dict):
        return {
            "source_type": "Field",
            "strategy_target": "Attribute or Metric",
            "status": "Needs review",
            "confidence": "Low",
            "notes": "Field metadata is not available."
        }

    metadata = {
        normalize(key): value
        for key, value in item.items()
    }

    role = str(
        metadata.get("role", "")
    ).lower()

    datatype = str(
        metadata.get("datatype", metadata.get("type", ""))
    ).lower()

    aggregation = metadata.get(
        "defaultaggregation",
        metadata.get("aggregation")
    )

    is_calculated = metadata.get(
        "iscalculated",
        metadata.get("calculated", False)
    )

    if isinstance(is_calculated, str):
        is_calculated = is_calculated.lower() in {
            "true", "yes", "1"
        }

    if role in {"measure", "quantitative"}:
        target = "Metric"
        source_type = "Measure"
        confidence = "Medium"

    elif role in {"dimension", "attribute", "ordinal", "nominal"}:
        target = "Attribute"
        source_type = "Dimension"
        confidence = "Medium"

    elif aggregation:
        target = "Metric"
        source_type = "Measure"
        confidence = "Medium"

    elif datatype in {
        "integer", "int", "float", "double", "decimal"
    }:
        target = "Attribute or Metric"
        source_type = "Numeric Field"
        confidence = "Low"

    else:
        target = "Attribute"
        source_type = "Dimension"
        confidence = "Low"

    if is_calculated:
        target = (
            "Derived Metric"
            if target == "Metric"
            else "Derived Attribute"
        )
        source_type = "Calculated Field"

    notes = []

    if not metadata.get("calculation", metadata.get("formula")) and is_calculated:
        notes.append("Calculation formula is missing.")

    if not aggregation and target in {"Metric", "Derived Metric"}:
        notes.append("Aggregation rule needs validation.")

    if datatype:
        notes.append(f"Source data type: {datatype}.")

    if not notes:
        notes.append("Review the mapping against the original Tableau workbook.")

    return {
        "source_type": source_type,
        "strategy_target": target,
        "status": "Needs review",
        "confidence": confidence,
        "notes": " ".join(notes)
    }


# --------------------------------------------------
# 5. Build mapping records
# --------------------------------------------------

def create_mapping(source_type, strategy_target, item, path):
    name = get_object_name(item, source_type)

    if source_type == "Field":
        classification = classify_field(item)

        return {
            "source_name": name,
            "source_type": classification["source_type"],
            "strategy_target": classification["strategy_target"],
            "source_path": path,
            "status": classification["status"],
            "confidence": classification["confidence"],
            "notes": classification["notes"]
        }

    return {
        "source_name": name,
        "source_type": source_type,
        "strategy_target": strategy_target,
        "source_path": path,
        "status": "Needs review",
        "confidence": "Medium",
        "notes": "Verify extracted metadata before migration."
    }


# --------------------------------------------------
# 6. Recursively inspect the JSON structure
# --------------------------------------------------

def scan_json(data, path="$", mappings=None):
    if mappings is None:
        mappings = []

    if isinstance(data, dict):

        for key, value in data.items():
            normalized_key = normalize(key)
            current_path = f"{path}.{key}"

            # Recognized Tableau object collections
            if normalized_key in SECTION_RULES:
                source_type, strategy_target = SECTION_RULES[
                    normalized_key
                ]

                items = value if isinstance(value, list) else [value]

                for index, item in enumerate(items):
                    item_path = f"{current_path}[{index}]"

                    mappings.append(
                        create_mapping(
                            source_type,
                            strategy_target,
                            item,
                            item_path
                        )
                    )

                    # Inspect nested objects too
                    scan_json(item, item_path, mappings)

            # Fields/columns need additional classification
            elif normalized_key in FIELD_SECTION_KEYS:
                items = value if isinstance(value, list) else [value]

                for index, item in enumerate(items):
                    item_path = f"{current_path}[{index}]"

                    mappings.append(
                        create_mapping(
                            "Field",
                            "Attribute or Metric",
                            item,
                            item_path
                        )
                    )

                    scan_json(item, item_path, mappings)

            else:
                scan_json(value, current_path, mappings)

    elif isinstance(data, list):
        for index, item in enumerate(data):
            scan_json(item, f"{path}[{index}]", mappings)

    return mappings


# --------------------------------------------------
# 7. Generate migration summary
# --------------------------------------------------

def generate_summary(mappings):

    summary = {}

    for item in mappings:
        target = item["strategy_target"]
        summary[target] = summary.get(target, 0) + 1

    return summary


# --------------------------------------------------
# 8. Main program
# --------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Generic Tableau-to-Strategy Migration Mapper"
    )

    parser.add_argument(
        "input",
        help="Path to the Tableau inventory JSON file"
    )

    parser.add_argument(
        "--output",
        help="Path for the generated migration mapping JSON"
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return

    try:
        with input_path.open("r", encoding="utf-8") as file:
            inventory = json.load(file)

    except json.JSONDecodeError as error:
        print(f"Error: Invalid JSON file: {error}")
        return

    if not isinstance(inventory, (dict, list)):
        print("Error: JSON root must be an object or an array.")
        return

    print("Reading inventory...")
    mappings = scan_json(inventory)

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(
            input_path.stem + "_migration_mapping.json"
        )
    )

    result = {
        "input_file": input_path.name,
        "migration_tool": "Generic Tableau-to-Strategy Mapper",
        "total_mapped_objects": len(mappings),
        "summary": generate_summary(mappings),
        "mappings": mappings
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nMigration mapping completed.")
    print(f"Objects mapped: {len(mappings)}")
    print(f"Output saved to: {output_path}")


if __name__ == "__main__":
    main()
