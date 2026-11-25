
import argparse
import json
import re
from pathlib import Path


# Fields that may contain a Tableau visualization type.
CHART_TYPE_KEYS = {
    "charttype",
    "visualizationtype",
    "viztype",
    "marktype",
    "mark",
    "chart",
}

NAME_KEYS = {"name", "worksheetname", "sheetname", "title"}

# Values such as Automatic do not tell us the actual chart type.
UNKNOWN_TYPES = {
    "",
    "automatic",
    "unknown",
    "none",
    "null",
    "n/a",
}


def normalize(value):
    """Normalize names and chart types to make comparison easier."""
    value = str(value or "").strip().lower()
    value = re.sub(r"[_\-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def find_worksheet_list(data):
    """
    Find a list stored under a key such as worksheets or worksheet.
    Works with nested JSON structures.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if normalize_key(key) in {"worksheets", "worksheet"}:
                if isinstance(value, list):
                    return value

        for value in data.values():
            result = find_worksheet_list(value)
            if result is not None:
                return result

    elif isinstance(data, list):
        for item in data:
            result = find_worksheet_list(item)
            if result is not None:
                return result

    return None


def get_value_by_keys(item, possible_keys):
    """Return the first matching value from a dictionary."""
    if not isinstance(item, dict):
        return None

    for key, value in item.items():
        if normalize_key(key) in possible_keys:
            if isinstance(value, (str, int, float)):
                return value

    return None


def extract_chart_type(worksheet):
    value = get_value_by_keys(
        worksheet,
        {normalize_key(key) for key in CHART_TYPE_KEYS}
    )

    if value is None:
        return None

    value = str(value).strip()

    if normalize(value) in UNKNOWN_TYPES:
        return None

    return value


def extract_worksheets(inventory):
    worksheets = find_worksheet_list(inventory)

    if worksheets is None:
        raise ValueError(
            "Could not find a worksheets list in the inventory JSON."
        )

    results = []

    for index, worksheet in enumerate(worksheets, start=1):
        if not isinstance(worksheet, dict):
            continue

        name = get_value_by_keys(
            worksheet,
            {normalize_key(key) for key in NAME_KEYS}
        )

        results.append({
            "worksheet_name": str(name or f"Worksheet {index}"),
            "tableau_chart_type": extract_chart_type(worksheet),
        })

    return results



def load_capabilities(registry):
    """
    Load visualization capabilities from the registry.

    Supports both:
    - capabilities
    - visualizations
    """

    capabilities = registry.get("capabilities")

    if capabilities is None:
        capabilities = registry.get("visualizations")

    if not isinstance(capabilities, list):
        raise ValueError(
            "The registry must contain a 'capabilities' "
            "or 'visualizations' list."
        )

    if not capabilities:
        raise ValueError(
            "The visualization registry is empty."
        )

    return capabilities





def find_exact_match(chart_type, capabilities):
    """Find a native Strategy visualization with an equivalent Tableau type."""
    chart = normalize(chart_type)

    for capability in capabilities:
        availability = capability.get("availability", "")

        if availability != "documented_native_candidate":
            continue

        equivalents = capability.get("tableau_equivalents", [])

        for equivalent in equivalents:
            if chart == normalize(equivalent):
                return capability

    return None


def find_family_match(chart_type, capabilities):
    """
    Find a possible alternative from the same visualization family.
    This is a conversion candidate, not a guaranteed equivalent.
    """
    chart = normalize(chart_type)

    for capability in capabilities:
        if capability.get("availability") != "documented_native_candidate":
            continue

        equivalents = capability.get("tableau_equivalents", [])

        for equivalent in equivalents:
            if chart and chart in normalize(equivalent):
                return capability

    return None


def match_visualization(worksheet, capabilities):
    chart_type = worksheet["tableau_chart_type"]
    worksheet_name = worksheet["worksheet_name"]

    result = {
        "worksheet_name": worksheet_name,
        "tableau_chart_type": chart_type,
        "strategy_visualization": None,
        "decision": None,
        "confidence": "Low",
        "reason": "",
    }

    # Never guess a chart type from its worksheet name.
    if not chart_type:
        result["decision"] = "MANUAL_REVIEW"
        result["reason"] = (
            "The inventory does not contain a reliable chart type. "
            "More Tableau metadata is required."
        )
        return result

    exact_match = find_exact_match(chart_type, capabilities)

    if exact_match:
        result["strategy_visualization"] = exact_match.get("name")
        result["decision"] = "REUSE"
        result["confidence"] = "High"
        result["reason"] = (
            "A documented native Strategy visualization matches "
            "the Tableau chart type. Verify it in the target environment."
        )
        return result

    alternative = find_family_match(chart_type, capabilities)

    if alternative:
        result["strategy_visualization"] = alternative.get("name")
        result["decision"] = "CONVERT"
        result["confidence"] = "Low"
        result["reason"] = (
            "A possible Strategy alternative was found. "
            "The agent must validate whether the chart's data roles "
            "and behavior can be preserved."
        )
        return result

    custom = next(
        (
            item for item in capabilities
            if item.get("id") == "custom_visualization"
        ),
        None,
    )

    if custom:
        result["strategy_visualization"] = custom.get("name")
        result["decision"] = "CUSTOM"
        result["confidence"] = "Low"
        result["reason"] = (
            "No native equivalent was found. A custom visualization "
            "may be required and needs implementation assessment."
        )
        return result

    result["decision"] = "MANUAL_REVIEW"
    result["reason"] = "No matching Strategy capability was found."
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Match Tableau charts with Strategy capabilities."
    )

    parser.add_argument("--inventory", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    inventory = load_json(args.inventory)
    registry = load_json(args.registry)

    capabilities = load_capabilities(registry)
    worksheets = extract_worksheets(inventory)

    matches = [
        match_visualization(worksheet, capabilities)
        for worksheet in worksheets
    ]

    summary = {}

    for match in matches:
        decision = match["decision"]
        summary[decision] = summary.get(decision, 0) + 1

    output = {
        "tool": "Tableau-to-Strategy Visualization Matcher",
        "input_inventory": Path(args.inventory).name,
        "registry": Path(args.registry).name,
        "total_worksheets": len(matches),
        "summary": summary,
        "matches": matches,
        "warning": (
            "Documented native capabilities must be verified in the "
            "target Strategy environment. REUSE does not mean that an "
            "existing chart instance is automatically reused."
        ),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=4, ensure_ascii=False)

    print("Visualization matching completed.")
    print(f"Total worksheets: {len(matches)}")
    print(f"Summary: {summary}")
    print(f"Output saved to: {output_path}")


if __name__ == "__main__":
    main()
