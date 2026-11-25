#!/usr/bin/env python3
"""
Tableau to Strategy Migration Executor
---------------------------------------
Input:  Tableau .twbx file (with a .hyper extract inside)
Output: Published multi-table Dataset in Strategy

Stages:
1. Extract the Hyper file from the TWBX.
2. Read all Hyper tables.
3. Classify columns into Attributes and Metrics, using the roles
   defined in the workbook itself (works for any dashboard, not only task_2).
4. Connect to Strategy using your existing browser session (SSO).
5. Create and publish a multi-table Dataset.

Publishing a Dataset does not create joins, filters, visualizations or a
Dashboard. Those are a separate authoring stage.

Usage:
  python tableau_to_strategy_migration.py dashboard/task_2.twbx --dry-run
  python tableau_to_strategy_migration.py dashboard/task_2.twbx --name My_Dataset

Environment (never paste these in chat or save them in files):
  MSTR_TOKEN, MSTR_COOKIE      required for upload (not for --dry-run)
  MSTR_BASE_URL                optional
  MSTR_PROJECT_NAME            optional (default: MicroStrategy Tutorial)
  MSTR_DATASET_NAME            optional (default: Tableau_Migrated_Dataset)
"""

import argparse
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import requests
from tableauhyperapi import (
    HyperProcess,
    Connection as HyperConnection,
    Telemetry,
)
from mstrio.connection import Connection as StrategyConnection
from mstrio.project_objects import SuperCube


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_URL = os.getenv(
    "MSTR_BASE_URL",
    "https://education.cloud.microstrategy.com/MicroStrategyLibrary/api",
)
PROJECT_NAME = os.getenv("MSTR_PROJECT_NAME", "MicroStrategy Tutorial")
DEFAULT_DATASET_NAME = os.getenv("MSTR_DATASET_NAME", "Tableau_Migrated_Dataset")

# Numeric columns whose name looks like an identifier stay Attributes
# (Row ID, Order ID, Postal Code, ...).
IDENTIFIER_PATTERN = re.compile(
    r"(^|[\s_\-])(id|code|key|zip|postal)([\s_\-]|$)", re.IGNORECASE
)

# Tableau appends a 32-character hex suffix to table names inside extracts.
HYPER_SUFFIX = re.compile(r"_[0-9A-Fa-f]{32}$")


# ============================================================
# 2. INPUT VALIDATION
# ============================================================

def validate_input(path):
    if not path.exists():
        raise FileNotFoundError(f"Tableau file not found: {path.resolve()}")
    if path.suffix.lower() != ".twbx":
        raise ValueError("Input must be a .twbx file.")
    print(f"\nTableau input: {path.resolve()}")


# ============================================================
# 3. EXTRACT HYPER FILE
# ============================================================

def extract_hyper_file(twbx_path, destination):
    print("\n[1/5] Extracting Hyper file from TWBX...")

    with zipfile.ZipFile(twbx_path, "r") as archive:
        hyper_files = [
            n for n in archive.namelist() if n.lower().endswith(".hyper")
        ]
        if not hyper_files:
            raise FileNotFoundError("No .hyper extract found inside the TWBX file.")
        if len(hyper_files) > 1:
            print(f"Found {len(hyper_files)} Hyper files. Using the first one.")

        selected = hyper_files[0]
        output_path = destination / Path(selected).name

        with archive.open(selected) as source, open(output_path, "wb") as target:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)

    print(f"Hyper file extracted: {output_path.name}")
    return output_path


# ============================================================
# 4. READ WORKBOOK ROLES (what Tableau says is a measure)
# ============================================================

def load_measure_names(twbx_path):
    """Names and captions of non-calculated numeric measures in the workbook."""
    names = set()
    with zipfile.ZipFile(twbx_path, "r") as archive:
        twb_files = [n for n in archive.namelist() if n.lower().endswith(".twb")]
        if not twb_files:
            return names
        root = ET.fromstring(archive.read(twb_files[0]))

    for ds in root.iter("datasource"):
        if ds.get("name") == "Parameters":
            continue
        for col in ds.findall("column"):
            if col.find("calculation") is not None:
                continue
            if col.get("role") == "measure" and col.get("datatype") in (
                "integer",
                "real",
            ):
                names.add(col.get("name", "").strip("[]").lower())
                if col.get("caption"):
                    names.add(col.get("caption").lower())
    names.discard("")
    return names


def load_dimension_names(twbx_path):
    """Names and captions of non-calculated fields the workbook explicitly
    declares as dimensions."""
    names = set()
    with zipfile.ZipFile(twbx_path, "r") as archive:
        twb_files = [n for n in archive.namelist() if n.lower().endswith(".twb")]
        if not twb_files:
            return names
        root = ET.fromstring(archive.read(twb_files[0]))

    for ds in root.iter("datasource"):
        if ds.get("name") == "Parameters":
            continue
        for col in ds.findall("column"):
            if col.find("calculation") is not None:
                continue
            if col.get("role") == "dimension":
                names.add(col.get("name", "").strip("[]").lower())
                if col.get("caption"):
                    names.add(col.get("caption").lower())
    names.discard("")
    return names


# ============================================================
# 5. READ HYPER TABLES AND CLASSIFY COLUMNS
# ============================================================

def clean_table_name(raw_name):
    return HYPER_SUFFIX.sub("", str(raw_name).strip('"'))


def classify_columns(dataframe, measure_names, dimension_names):
    attributes, metrics = [], []

    for column in dataframe.columns:
        is_identifier = bool(IDENTIFIER_PATTERN.search(column))
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        is_numeric = numeric.notna().sum() == dataframe[column].notna().sum() \
            and dataframe[column].notna().any()

        # Tableau only stores explicit overrides in the .twb, so fields like
        # Quantity or Discount may not be listed at all. An explicit dimension
        # stays an attribute; everything else numeric is treated as a measure.
        key = column.lower()
        is_measure = key in measure_names or key not in dimension_names

        if is_measure and is_numeric and not is_identifier:
            dataframe[column] = numeric
            metrics.append(column)
        else:
            attributes.append(column)

    return attributes, metrics


def read_hyper_tables(hyper_path, measure_names, dimension_names):
    print("\n[2/5] Reading Hyper tables...")
    tables_data = {}

    with HyperProcess(
        telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU
    ) as hyper:
        with HyperConnection(
            endpoint=hyper.endpoint, database=str(hyper_path)
        ) as connection:

            for schema in connection.catalog.get_schema_names():
                for table in connection.catalog.get_table_names(schema):
                    definition = connection.catalog.get_table_definition(table)
                    columns = [str(c.name).strip('"') for c in definition.columns]

                    rows = connection.execute_list_query(
                        f"SELECT * FROM {table}"
                    )
                    dataframe = pd.DataFrame(rows, columns=columns)

                    name = clean_table_name(table.name)
                    attributes, metrics = classify_columns(
                        dataframe, measure_names, dimension_names
                    )

                    tables_data[name] = {
                        "dataframe": dataframe,
                        "attributes": attributes,
                        "metrics": metrics,
                    }

                    print(f"\nTable: {name}")
                    print(f"Rows: {len(dataframe):,}")
                    print(f"Attributes ({len(attributes)}): {attributes}")
                    print(f"Metrics ({len(metrics)}): {metrics}")

    if not tables_data:
        raise RuntimeError("No tables were read from Hyper.")

    print(f"\nTotal tables extracted: {len(tables_data)}")
    return tables_data


# ============================================================
# 6. CONNECT TO STRATEGY (SSO session: token + cookie)
# ============================================================

def session_headers():
    token = os.getenv("MSTR_TOKEN")
    cookie = os.getenv("MSTR_COOKIE")
    if not token or not cookie:
        raise RuntimeError(
            "MSTR_TOKEN and MSTR_COOKIE are required. This account uses SSO, "
            "so username/password login does not work. Copy a fresh token and "
            "cookie from the browser first."
        )
    return {
        "X-MSTR-AuthToken": token,
        "Cookie": cookie,
        "Accept": "application/json",
    }


def connect_to_strategy():
    print("\n[3/5] Connecting to Strategy using the existing session...")
    headers = session_headers()

    response = requests.post(
        f"{BASE_URL}/auth/identityToken", headers=headers, timeout=30
    )
    # Some versions return 200 and others 201.
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Identity token creation failed: "
            f"{response.status_code} - {response.text[:300]}"
        )

    identity_token = response.headers.get("X-MSTR-IdentityToken")
    if not identity_token:
        raise RuntimeError("Identity token was not returned.")

    connection = StrategyConnection(
        base_url=BASE_URL,
        identity_token=identity_token,
        project_name=PROJECT_NAME,
        verbose=False,
    )
    print("SUCCESS: connected.")
    print("Project:", connection.project_name)
    return connection


def dataset_exists(connection, dataset_name):
    """Best-effort duplicate check. Returns True / False / None (unknown).
    [UNVERIFIED] search endpoint and result shape on this server version."""
    try:
        headers = session_headers()
        headers["X-MSTR-ProjectID"] = connection.project_id
        response = requests.get(
            f"{BASE_URL}/searches/results",
            headers=headers,
            params={"name": dataset_name, "pattern": 4, "limit": 50},
            timeout=30,
        )
        if not response.ok:
            return None
        results = response.json().get("result", [])
        return any(item.get("name") == dataset_name for item in results)
    except Exception:
        return None


# ============================================================
# 7. CREATE AND PUBLISH DATASET
# ============================================================

def publish_dataset(connection, tables_data, dataset_name):
    print("\n[4/5] Creating multi-table Dataset...")

    dataset = SuperCube(connection=connection, name=dataset_name)

    for table_name, info in tables_data.items():
        print(f"\nAdding table: {table_name} ({len(info['dataframe']):,} rows)")
        dataset.add_table(
            name=table_name,
            data_frame=info["dataframe"],
            update_policy="add",
            to_attribute=info["attributes"],
            to_metric=info["metrics"],
        )

    print("\nUploading and publishing Dataset...")
    dataset.create()
    print("Dataset created. Name:", dataset_name)
    return dataset


# ============================================================
# 8. MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("twbx", nargs="?", default="dashboard/task_2.twbx")
    parser.add_argument("--name", default=DEFAULT_DATASET_NAME,
                        help="Dataset name in Strategy")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read and classify only. No connection, no upload.")
    parser.add_argument("--force", action="store_true",
                        help="Upload even if a dataset with this name exists.")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt.")
    args = parser.parse_args()

    print("=" * 60)
    print("TABLEAU TO STRATEGY MIGRATION")
    print("=" * 60)

    twbx = Path(args.twbx)
    validate_input(twbx)
    connection = None

    try:
        measure_names = load_measure_names(twbx)
        dimension_names = load_dimension_names(twbx)
        print(f"Explicit measure roles in workbook: {len(measure_names)}")
        print(f"Explicit dimension roles in workbook: {len(dimension_names)}")

        with tempfile.TemporaryDirectory(prefix="tableau_strategy_") as tmp:
            hyper_path = extract_hyper_file(twbx, Path(tmp))
            tables_data = read_hyper_tables(
                hyper_path, measure_names, dimension_names
            )

            if args.dry_run:
                print("\nDry run only. Nothing was sent to Strategy.")
                return

            connection = connect_to_strategy()

            exists = dataset_exists(connection, args.name)
            if exists and not args.force:
                raise RuntimeError(
                    f"A dataset named '{args.name}' already exists. "
                    "Use --name for a new name, or --force to upload anyway."
                )
            if exists is None:
                print("Warning: could not check for an existing dataset "
                      "with this name.")

            if not args.yes:
                answer = input(
                    f"\nCreate dataset '{args.name}' in project "
                    f"'{PROJECT_NAME}'? [y/N]: "
                ).strip().lower()
                if answer != "y":
                    print("Cancelled. Nothing was uploaded.")
                    return

            publish_dataset(connection, tables_data, args.name)

        print("\n" + "=" * 60)
        print("DATASET MIGRATION STAGE COMPLETED")
        print("=" * 60)
        print("\nStill requiring the dashboard authoring stage:")
        print("- Validate table relationships and joins")
        print("- Create Strategy filters")
        print("- Create compatible visualizations")
        print("- Create and save the Strategy Dashboard")
        print("- Verify the final Dashboard in Library")

    except Exception as error:
        print("\n" + "=" * 60)
        print("MIGRATION FAILED")
        print("=" * 60)
        print(type(error).__name__, ":", str(error))
        sys.exit(1)

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()