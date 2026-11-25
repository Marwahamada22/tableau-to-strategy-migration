
#!/usr/bin/env python3
"""
Tableau Workbook (.twb / .twbx) Parser for Strategy Migration.

Extracts:
- Data sources
- Fields and columns
- Parameters
- Worksheets
- Rows and Columns shelves
- Mark types
- Visual encodings
- Filters
- Dashboards
- Actions
- Migration metadata
"""

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET

from dataclasses import dataclass, field, asdict
from pathlib import Path


# ============================================================
# Tableau mark type -> Strategy visualization candidate
# ============================================================

MARK_TO_STRATEGY_VIZ = {
    "Bar": "bar",
    "Line": "line",
    "Area": "area",
    "Pie": "pie",
    "Square": "heat_map",
    "Circle": "scatter",
    "Shape": "custom",
    "Text": "grid",
    "Map": "map",
    "Polygon": "map",
    "Gantt Bar": "gantt",
    "Automatic": "auto",
}


# ============================================================
# Data classes
# ============================================================

@dataclass
class EncodingInfo:
    channel: str = ""
    field: str = ""
    type: str = ""


@dataclass
class FilterInfo:
    name: str = ""
    field: str = ""
    class_type: str = ""
    column: str = ""


@dataclass
class WorksheetInfo:
    name: str = ""
    datasource: str = ""
    datasource_caption: str = ""
    mark_type: str = "Automatic"

    rows: list = field(default_factory=list)
    columns: list = field(default_factory=list)

    row_shelf: list = field(default_factory=list)
    column_shelf: list = field(default_factory=list)

    encodings: list = field(default_factory=list)
    filters: list = field(default_factory=list)
    used_fields: list = field(default_factory=list)
    sort_fields: list = field(default_factory=list)

    strategy_viz_type: str = "auto"


@dataclass
class DataSourceInfo:
    name: str = ""
    caption: str = ""
    connection_type: str = ""
    fields: list = field(default_factory=list)


@dataclass
class DashboardInfo:
    name: str = ""
    worksheets: list = field(default_factory=list)
    objects: list = field(default_factory=list)


@dataclass
class ParameterInfo:
    name: str = ""
    datatype: str = ""
    value: str = ""
    allowable_values: list = field(default_factory=list)


@dataclass
class TableauInventory:
    source_file: str = ""
    tableau_version: str = ""

    data_sources: list = field(default_factory=list)
    worksheets: list = field(default_factory=list)
    dashboards: list = field(default_factory=list)
    parameters: list = field(default_factory=list)

    complexity_score: int = 0
    complexity_level: str = "Unknown"

    migration_notes: list = field(default_factory=list)
    strategy_recommendations: list = field(default_factory=list)


# ============================================================
# XML helper functions
# ============================================================

def get_xml_root(file_path):
    """
    Read .twb or .twbx and return Tableau workbook XML root.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Input Tableau file does not exist: {file_path}"
        )

    suffix = file_path.suffix.lower()

    if suffix == ".twb":
        tree = ET.parse(file_path)
        return tree.getroot()

    if suffix == ".twbx":
        with zipfile.ZipFile(file_path, "r") as archive:

            twb_files = [
                name for name in archive.namelist()
                if name.lower().endswith(".twb")
            ]

            if not twb_files:
                raise ValueError(
                    "No .twb workbook XML found inside the .twbx archive."
                )

            # Usually there is one workbook XML file.
            xml_content = archive.read(twb_files[0])

            return ET.fromstring(xml_content)

    raise ValueError(
        "Unsupported file format. Use .twb or .twbx."
    )


def clean_field_ref(ref):
    """
    Convert Tableau field references into readable field names.

    Example:
    [datasource].[sum:Sales:qk] -> Sales
    [datasource].[none:State:nk] -> State
    [datasource].[io:Sub-Category Set:nk] -> Sub-Category Set
    """

    if not ref:
        return ""

    parts = re.findall(r"\[([^\]]+)\]", ref)

    if not parts:
        return ref.strip()

    field_part = parts[-1].strip()

    if ":" in field_part:
        segments = field_part.split(":")

        if len(segments) >= 3:
            field_part = ":".join(segments[1:-1])
        else:
            field_part = segments[-1]

    return field_part.strip()


def parse_shelf_expression(element):
    """
    Extract fields and aggregations from Tableau Rows / Columns shelves.

    Example:
    SUM(Sales) -> Sales, aggregation=sum
    State -> State
    """

    if element is None:
        return []

    raw_expression = "".join(element.itertext()).strip()

    references = re.findall(
        r"\[([^\]]+)\]",
        raw_expression
    )

    results = []

    for token in references:

        token = token.strip()

        # Ignore Tableau internal references.
        if token == "__tableau_internal_object_id__":
            continue

        # Ignore datasource identifiers.
        if token.startswith("federated."):
            continue

        if token.startswith("Parameters"):
            continue

        aggregation = ""
        field_name = token

        parts = token.split(":")

        if len(parts) >= 3:
            aggregation = parts[0]
            field_name = ":".join(parts[1:-1])

        if not field_name:
            continue

        if field_name in {
            "Measure Names",
            "Measure Values"
        }:
            continue

        results.append({
            "field": field_name,
            "aggregation": aggregation,
            "raw_reference": token,
            "raw_expression": raw_expression
        })

    return results


def unique_list(values):
    """Remove duplicates while preserving order."""

    return list(dict.fromkeys(
        value for value in values if value
    ))


# ============================================================
# Tableau Parser
# ============================================================

class TableauParser:

    def __init__(self, file_path):

        self.file_path = Path(file_path)
        self.root = get_xml_root(self.file_path)

        self.inventory = TableauInventory(
            source_file=str(self.file_path)
        )

        self.inventory.tableau_version = (
            self.root.get("version", "")
        )

    # --------------------------------------------------------
    # Main parsing function
    # --------------------------------------------------------

    def parse(self):

        self._parse_data_sources()
        self._parse_parameters()
        self._parse_worksheets()
        self._parse_dashboards()
        self._calculate_complexity()
        self._generate_recommendations()

        return self.inventory

    # --------------------------------------------------------
    # Data sources
    # --------------------------------------------------------

    def _parse_data_sources(self):

        datasources_el = self.root.find("datasources")

        if datasources_el is None:
            return

        for ds_el in datasources_el.findall("datasource"):

            ds = DataSourceInfo(
                name=ds_el.get("name", ""),
                caption=ds_el.get("caption", "")
            )

            connection = ds_el.find(".//connection")

            if connection is not None:
                ds.connection_type = connection.get(
                    "class",
                    ""
                )

            for column in ds_el.findall(".//column"):

                field_name = column.get("name", "")

                if field_name:
                    ds.fields.append({
                        "name": field_name.strip("[]"),
                        "caption": column.get("caption", ""),
                        "datatype": column.get("datatype", ""),
                        "role": column.get("role", ""),
                        "type": column.get("type", "")
                    })

            self.inventory.data_sources.append(ds)

    # --------------------------------------------------------
    # Parameters
    # --------------------------------------------------------

    def _parse_parameters(self):

        for param_el in self.root.findall(".//column"):

            if param_el.get("param-domain-type") is None:
                continue

            parameter = ParameterInfo(
                name=param_el.get("caption", param_el.get("name", "")),
                datatype=param_el.get("datatype", ""),
                value=param_el.get("value", "")
            )

            for member in param_el.findall(".//member"):

                value = member.get("value", "")

                if value:
                    parameter.allowable_values.append(value)

            self.inventory.parameters.append(parameter)

    # --------------------------------------------------------
    # Worksheets
    # --------------------------------------------------------

    def _parse_worksheets(self):

        worksheets_el = self.root.find("worksheets")

        if worksheets_el is None:
            return

        for ws_el in worksheets_el.findall("worksheet"):

            ws = WorksheetInfo(
                name=ws_el.get("name", "")
            )

            table_el = ws_el.find("table")

            if table_el is None:
                self.inventory.worksheets.append(ws)
                continue

            # 1. Data source information

            view_el = table_el.find("view")

            if view_el is not None:

                ds_refs = view_el.find("datasources")

                if ds_refs is not None:

                    for ds in ds_refs.findall("datasource"):

                        caption = ds.get("caption", "")
                        name = ds.get("name", "")

                        if caption:
                            ws.datasource_caption = caption
                            ws.datasource = name

                        elif not ws.datasource:
                            ws.datasource = name

            # 2. Rows and Columns shelves
            # They are direct children of <table>.

            rows_el = table_el.find("rows")
            cols_el = table_el.find("cols")

            ws.row_shelf = parse_shelf_expression(rows_el)
            ws.column_shelf = parse_shelf_expression(cols_el)

            ws.rows = unique_list([
                item["field"]
                for item in ws.row_shelf
            ])

            ws.columns = unique_list([
                item["field"]
                for item in ws.column_shelf
            ])

            # 3. Mark type
            # Mark is inside table/panes/pane/mark.

            mark_elements = table_el.findall(
                ".//pane/mark"
            )

            if mark_elements:

                mark_types = [
                    mark.get("class", "Automatic")
                    for mark in mark_elements
                ]

                ws.mark_type = mark_types[0]

                if len(mark_types) > 1:

                    self.inventory.migration_notes.append(
                        f"Worksheet '{ws.name}' contains multiple "
                        f"mark types: {', '.join(mark_types)}. "
                        f"Review before migration."
                    )

            # 4. Encodings

            for pane in table_el.findall(".//pane"):

                enc_el = pane.find("encodings")

                if enc_el is None:
                    continue

                channels = [
                    "color",
                    "size",
                    "text",
                    "detail",
                    "tooltip",
                    "shape",
                    "label",
                    "lod"
                ]

                for channel in channels:

                    for channel_el in enc_el.findall(channel):

                        field_ref = channel_el.get(
                            "column",
                            ""
                        )

                        if not field_ref:
                            continue

                        ws.encodings.append(
                            EncodingInfo(
                                channel=channel,
                                field=clean_field_ref(field_ref),
                                type=channel_el.get("type", "")
                            )
                        )

            # 5. Filters

            for filter_el in table_el.findall(".//filter"):

                filt = self._parse_filter(filter_el)

                if filt:
                    ws.filters.append(filt)

            # 6. Used fields from datasource dependencies

            for dep in ws_el.findall(
                ".//datasource-dependencies"
            ):

                for col in dep.findall("column"):

                    field_name = col.get(
                        "name",
                        ""
                    ).strip("[]")

                    if (
                        field_name
                        and field_name not in ws.used_fields
                    ):
                        ws.used_fields.append(field_name)

            # Add fields from Rows and Columns.

            for field_name in ws.rows + ws.columns:

                if (
                    field_name
                    and field_name not in ws.used_fields
                ):
                    ws.used_fields.append(field_name)

            # Add encoding fields.

            for encoding in ws.encodings:

                if (
                    encoding.field
                    and encoding.field not in ws.used_fields
                ):
                    ws.used_fields.append(encoding.field)

            # 7. Sorting

            for sort_el in table_el.findall(".//sort"):

                sort_field = clean_field_ref(
                    sort_el.get("column", "")
                )

                sort_dir = sort_el.get(
                    "direction",
                    "ASC"
                )

                if sort_field:

                    ws.sort_fields.append({
                        "field": sort_field,
                        "direction": sort_dir
                    })

            # 8. Strategy visualization candidate

            ws.strategy_viz_type = MARK_TO_STRATEGY_VIZ.get(
                ws.mark_type,
                "auto"
            )

            self.inventory.worksheets.append(ws)

    # --------------------------------------------------------
    # Filter parser
    # --------------------------------------------------------

    def _parse_filter(self, filter_el):

        column = filter_el.get("column", "")

        field_name = clean_field_ref(column)

        return FilterInfo(
            name=filter_el.get("name", ""),
            field=field_name,
            class_type=filter_el.get("class", ""),
            column=column
        )

    # --------------------------------------------------------
    # Dashboards
    # --------------------------------------------------------

    def _parse_dashboards(self):

        dashboards_el = self.root.find("dashboards")

        if dashboards_el is None:
            return

        for dashboard_el in dashboards_el.findall("dashboard"):

            dashboard = DashboardInfo(
                name=dashboard_el.get("name", "")
            )

            # Find worksheets referenced by dashboard zones.

            for zone in dashboard_el.findall(".//zone"):

                worksheet_name = zone.get(
                    "name",
                    ""
                )

                if (
                    worksheet_name
                    and worksheet_name not in dashboard.worksheets
                ):
                    dashboard.worksheets.append(
                        worksheet_name
                    )

                zone_type = zone.get("type", "")

                if zone_type:
                    dashboard.objects.append({
                        "type": zone_type,
                        "name": worksheet_name,
                        "x": zone.get("x", ""),
                        "y": zone.get("y", ""),
                        "w": zone.get("w", ""),
                        "h": zone.get("h", "")
                    })

            self.inventory.dashboards.append(dashboard)

    # --------------------------------------------------------
    # Complexity score
    # --------------------------------------------------------

    def _calculate_complexity(self):

        score = 0

        score += len(self.inventory.worksheets) * 2
        score += len(self.inventory.dashboards) * 5
        score += len(self.inventory.parameters) * 2

        for ws in self.inventory.worksheets:

            score += len(ws.filters)
            score += len(ws.encodings)
            score += len(ws.sort_fields)

            if ws.mark_type == "Automatic":
                score += 1

        self.inventory.complexity_score = score

        if score < 20:
            level = "Low"

        elif score < 50:
            level = "Medium"

        elif score < 100:
            level = "High"

        else:
            level = "Very High"

        self.inventory.complexity_level = level

    # --------------------------------------------------------
    # Strategy recommendations
    # --------------------------------------------------------

    def _generate_recommendations(self):

        for ws in self.inventory.worksheets:

            if ws.mark_type == "Automatic":

                self.inventory.strategy_recommendations.append(
                    f"Worksheet '{ws.name}': Tableau mark type is "
                    f"Automatic. Analyze shelves and encodings before "
                    f"choosing a Strategy visualization."
                )

            elif ws.strategy_viz_type == "custom":

                self.inventory.strategy_recommendations.append(
                    f"Worksheet '{ws.name}': Check whether a suitable "
                    f"native Strategy visualization exists; custom "
                    f"implementation may be required."
                )

            else:

                self.inventory.strategy_recommendations.append(
                    f"Worksheet '{ws.name}': Candidate Strategy "
                    f"visualization is '{ws.strategy_viz_type}'. "
                    f"Verify availability in the target environment."
                )

    # --------------------------------------------------------
    # Convert to JSON
    # --------------------------------------------------------

    def to_dict(self):

        return asdict(self.inventory)

    def save_json(self, output_path):

        output_path = Path(output_path)

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
                self.to_dict(),
                file,
                indent=4,
                ensure_ascii=False
            )

        print(
            f"\nInventory saved successfully: {output_path}"
        )


# ============================================================
# Command line interface
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Parse Tableau .twb/.twbx workbook "
            "for Strategy migration."
        )
    )

    parser.add_argument(
        "input",
        help="Path to Tableau .twb or .twbx file"
    )

    parser.add_argument(
        "--output",
        default="tableau_inventory.json",
        help="Output JSON file path"
    )

    args = parser.parse_args()

    try:

        tableau_parser = TableauParser(args.input)

        inventory = tableau_parser.parse()

        tableau_parser.save_json(args.output)

        print("\n========== PARSING SUMMARY ==========")

        print(
            f"Worksheets: {len(inventory.worksheets)}"
        )

        print(
            f"Dashboards: {len(inventory.dashboards)}"
        )

        print(
            f"Data Sources: {len(inventory.data_sources)}"
        )

        print(
            f"Parameters: {len(inventory.parameters)}"
        )

        print(
            f"Complexity Score: {inventory.complexity_score}"
        )

        print(
            f"Complexity Level: {inventory.complexity_level}"
        )

        print("\nWorksheet visualization metadata:")

        for ws in inventory.worksheets:

            print(
                f"- {ws.name}: "
                f"Mark={ws.mark_type}, "
                f"Rows={ws.rows}, "
                f"Columns={ws.columns}, "
                f"Strategy Candidate={ws.strategy_viz_type}"
            )

        print("\nParsing completed successfully.")

    except Exception as error:

        print(f"\nERROR: {error}")
        raise


if __name__ == "__main__":
    main()
