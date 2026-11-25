
import argparse
import json
import re

from pathlib import Path


# ============================================================
# Configuration
# ============================================================

UNKNOWN_MARKS = {
    "",
    "automatic",
    "unknown",
    "none",
    "null"
}

MEASURE_AGGREGATIONS = {
    "sum",
    "avg",
    "average",
    "cnt",
    "count",
    "min",
    "max",
    "median",
    "attr",
    "stdev",
    "var",
    "countd"
}

DIMENSION_AGGREGATIONS = {
    "",
    "none",
    "io"
}

GEOGRAPHIC_FIELDS = {
    "state",
    "country",
    "city",
    "latitude",
    "longitude",
    "postal code",
    "zip code",
    "region"
}

DATE_PATTERN = re.compile(
    r"\b(date|year|month|quarter|day|week|time)\b",
    re.IGNORECASE
)


# ============================================================
# Helpers
# ============================================================

def load_json(path):

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize(value):

    value = str(value or "").strip().lower()

    value = re.sub(r"[_\-]+", " ", value)

    value = re.sub(r"\s+", " ", value)

    return value


def is_geographic_field(field_name):

    field = normalize(field_name)

    return field in GEOGRAPHIC_FIELDS


def is_date_field(field_name):

    return bool(DATE_PATTERN.search(str(field_name)))


def get_shelf_fields(worksheet):

    """
    Read structured metadata from Rows and Columns shelves.
    """

    fields = []

    for shelf_name in ["row_shelf", "column_shelf"]:

        shelf_items = worksheet.get(shelf_name, [])

        if not isinstance(shelf_items, list):
            continue

        for item in shelf_items:

            if not isinstance(item, dict):
                continue

            field_name = item.get("field", "")

            aggregation = normalize(
                item.get("aggregation", "")
            )

            if not field_name:
                continue

            fields.append({
                "field": field_name,
                "aggregation": aggregation,
                "shelf": shelf_name
            })

    return fields


# ============================================================
# Metadata analysis
# ============================================================

def classify_fields(worksheet):

    fields = get_shelf_fields(worksheet)

    measures = []
    dimensions = []

    for item in fields:

        aggregation = item["aggregation"]

        if aggregation in MEASURE_AGGREGATIONS:

            measures.append(item)

        elif aggregation in DIMENSION_AGGREGATIONS:

            dimensions.append(item)

        else:

            # Unknown aggregation:
            # Keep the field for further analysis.
            item["classification"] = "unknown"

    return measures, dimensions, fields


# ============================================================
# Rule-based chart inference
# ============================================================

def analyze_automatic_chart(worksheet):

    measures, dimensions, all_fields = classify_fields(
        worksheet
    )

    evidence = []

    warnings = []

    geographic_dimensions = [
        item for item in dimensions
        if is_geographic_field(item["field"])
    ]

    date_dimensions = [
        item for item in dimensions
        if is_date_field(item["field"])
    ]

    # --------------------------------------------------------
    # Rule 1: Need both a measure and a dimension
    # --------------------------------------------------------

    if not measures or not dimensions:

        return {
            "predicted_chart_type": None,
            "confidence": "Low",
            "confidence_score": 0.0,
            "rule": "INSUFFICIENT_METADATA",
            "evidence": [
                "A reliable measure and dimension combination "
                "could not be identified."
            ],
            "warnings": [
                "More Tableau metadata is required."
            ],
            "decision": "MANUAL_REVIEW"
        }

    evidence.append(
        f"Found {len(measures)} measure field(s)."
    )

    evidence.append(
        f"Found {len(dimensions)} dimension field(s)."
    )

    # --------------------------------------------------------
    # Rule 2: Date dimension + measure -> Line candidate
    # --------------------------------------------------------

    if date_dimensions:

        evidence.append(
            "A date-related dimension was found."
        )

        evidence.append(
            "A measure is available for the time axis."
        )

        return {
            "predicted_chart_type": "Line",
            "confidence": "Medium",
            "confidence_score": 0.70,
            "rule": "DATE_DIMENSION_WITH_MEASURE",
            "evidence": evidence,
            "warnings": [
                "Confirm the actual Tableau mark and date "
                "axis configuration before migration."
            ],
            "decision": "ANALYSIS_REQUIRED"
        }

    # --------------------------------------------------------
    # Rule 3: Geographic dimension + measure
    # --------------------------------------------------------

    if geographic_dimensions:

        geo_names = [
            item["field"]
            for item in geographic_dimensions
        ]

        evidence.append(
            "Geographic-looking dimension(s) found: "
            + ", ".join(geo_names)
        )

        warnings.append(
            "A geographic field does not prove that the "
            "original visualization is a map."
        )

        warnings.append(
            "Verify Tableau geographic roles and mark "
            "configuration before selecting a map."
        )

        return {
            "predicted_chart_type": "Bar",
            "confidence": "Low",
            "confidence_score": 0.55,
            "rule": "GEOGRAPHIC_DIMENSION_WITH_MEASURE",
            "alternative_candidates": ["Map"],
            "evidence": evidence,
            "warnings": warnings,
            "decision": "ANALYSIS_REQUIRED"
        }

    # --------------------------------------------------------
    # Rule 4: Dimension(s) + measure(s) -> Bar candidate
    # --------------------------------------------------------

    evidence.append(
        "Categorical dimension(s) and measure(s) "
        "were found on Tableau shelves."
    )

    evidence.append(
        "A Bar Chart is a possible visualization "
        "for this field arrangement."
    )

    warnings.append(
        "The shelf arrangement alone cannot prove "
        "that the original chart is a Bar Chart."
    )

    warnings.append(
        "Check encodings, mark details and the "
        "original Tableau visualization."
    )

    return {
        "predicted_chart_type": "Bar",
        "confidence": "Medium",
        "confidence_score": 0.65,
        "rule": "DIMENSION_WITH_MEASURE",
        "evidence": evidence,
        "warnings": warnings,
        "decision": "ANALYSIS_REQUIRED"
    }


# ============================================================
# Worksheet analyzer
# ============================================================

def analyze_worksheet(worksheet):

    mark_type = str(
        worksheet.get("mark_type", "Automatic")
    ).strip()

    worksheet_name = worksheet.get(
        "name",
        "Unnamed Worksheet"
    )

    # --------------------------------------------------------
    # Explicit Tableau mark type
    # --------------------------------------------------------

    if normalize(mark_type) not in UNKNOWN_MARKS:

        return {
            "worksheet_name": worksheet_name,
            "original_mark_type": mark_type,
            "predicted_chart_type": mark_type,
            "confidence": "High",
            "confidence_score": 1.0,
            "rule": "EXPLICIT_TABLEAU_MARK",
            "evidence": [
                f"Tableau explicitly defines the mark type "
                f"as '{mark_type}'."
            ],
            "warnings": [],
            "decision": "EXPLICIT_TYPE"
        }

    # --------------------------------------------------------
    # Automatic mark type
    # --------------------------------------------------------

    analysis = analyze_automatic_chart(worksheet)

    analysis["worksheet_name"] = worksheet_name

    analysis["original_mark_type"] = mark_type

    return analysis


# ============================================================
# Main analyzer
# ============================================================

def analyze_inventory(inventory):

    worksheets = inventory.get("worksheets", [])

    if not isinstance(worksheets, list):

        raise ValueError(
            "Inventory must contain a worksheets list."
        )

    results = []

    for worksheet in worksheets:

        if not isinstance(worksheet, dict):
            continue

        results.append(
            analyze_worksheet(worksheet)
        )

    summary = {}

    for result in results:

        decision = result["decision"]

        summary[decision] = (
            summary.get(decision, 0) + 1
        )

    return {
        "tool": "Tableau Visualization Rule-Based Analyzer",
        "version": "1.0",
        "total_worksheets": len(results),
        "summary": summary,
        "analysis": results,
        "warning": (
            "Predictions are rule-based candidates, not "
            "confirmed original Tableau chart types. "
            "Validate before migration."
        )
    }


# ============================================================
# Command line
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Analyze Tableau worksheet metadata "
            "and infer possible visualization types."
        )
    )

    parser.add_argument(
        "--inventory",
        required=True,
        help="Path to Tableau inventory JSON"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output analysis JSON path"
    )

    args = parser.parse_args()

    inventory = load_json(args.inventory)

    result = analyze_inventory(inventory)

    output_path = Path(args.output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nVisualization analysis completed.")

    print(
        f"Total worksheets: {result['total_worksheets']}"
    )

    print(
        f"Summary: {result['summary']}"
    )

    print(
        f"Output saved to: {output_path}"
    )

    print("\nWorksheet predictions:")

    for item in result["analysis"]:

        print(
            f"- {item['worksheet_name']}: "
            f"{item['predicted_chart_type']} | "
            f"Confidence: {item['confidence']} | "
            f"Rule: {item['rule']}"
        )


if __name__ == "__main__":
    main()
