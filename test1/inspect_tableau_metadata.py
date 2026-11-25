
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

inventory_path = Path("dashboard/task_2_inventory.json")
workbook_path = Path("dashboard/task_2.twbx")

# 1. Inspect the existing inventory
print("\n========== INVENTORY STRUCTURE ==========")

with open(inventory_path, encoding="utf-8") as f:
    inventory = json.load(f)

print("Top-level keys:", list(inventory.keys())
      if isinstance(inventory, dict) else type(inventory).__name__)


def inspect_worksheet_sections(obj, path="$"):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower().replace("_", "") in {
                "worksheets", "worksheet"
            }:
                print(f"\nFound section: {path}.{key}")

                if isinstance(value, list) and value:
                    print("Number of items:", len(value))
                    print("First worksheet:")
                    print(json.dumps(
                        value[0],
                        indent=2,
                        ensure_ascii=False
                    )[:4000])

            inspect_worksheet_sections(value, f"{path}.{key}")

    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            inspect_worksheet_sections(item, f"{path}[{index}]")


inspect_worksheet_sections(inventory)


# 2. Inspect the original Tableau XML inside TWBX
print("\n========== TABLEAU WORKBOOK XML ==========")

with zipfile.ZipFile(workbook_path, "r") as archive:
    twb_files = [
        name for name in archive.namelist()
        if name.lower().endswith(".twb")
    ]

    if not twb_files:
        raise ValueError("No TWB XML file found inside the TWBX.")

    print("TWB file:", twb_files[0])

    root = ET.fromstring(archive.read(twb_files[0]))

    worksheets = root.findall(".//worksheets/worksheet")
    print("Worksheets found:", len(worksheets))

    for worksheet in worksheets:
        print("\n----------------------------------")
        print("Worksheet:", worksheet.get("name"))

        marks = worksheet.findall(".//mark")

        print("Mark types:", [
            mark.get("class") for mark in marks
        ])

        for shelf in ["rows", "cols"]:
            elements = worksheet.findall(f"./table/{shelf}")

            for element in elements:
                print(
                    shelf.upper() + ":",
                    ET.tostring(
                        element,
                        encoding="unicode"
                    )[:1500]
                )

        for encodings in worksheet.findall(".//encodings"):
            print(
                "ENCODINGS:",
                ET.tostring(
                    encodings,
                    encoding="unicode"
                )[:1500]
            )
