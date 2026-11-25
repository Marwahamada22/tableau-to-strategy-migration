# Tableau to Strategy Migration

A Python-based workflow for migrating Tableau workbooks and their underlying data into Strategy (formerly MicroStrategy).

The project focuses on extracting Tableau workbook metadata, analyzing visualizations, mapping Tableau components to Strategy equivalents, and migrating the underlying data into Strategy.

## 1. Implemented Workflow

The migration workflow consists of the following components:

| Component | Description |
|---|---|
| `tableau_parser.py` | Extracts structured metadata from Tableau workbooks, including data sources, worksheets, dashboards, fields, and other relevant information. |
| `visualization_analyzer.py` | Analyzes Tableau worksheets and their visualizations to identify chart types and visualization properties. |
| `migration_mapper.py` | Maps Tableau components to their corresponding Strategy components. |
| `visualization_matcher.py` | Matches Tableau chart types with suitable Strategy visualization types. |
| `tableau_to_strategy_migration.py` | Extracts data from Tableau Hyper files, reads the underlying tables, classifies columns into Attributes and Metrics, and publishes the Dataset to Strategy. |

## 2. Current Progress

The data migration phase has been successfully completed.

- Extracted metadata from the Tableau workbook.
- Extracted data from the embedded Hyper file.
- Read and processed the source tables.
- Successfully published the Dataset to Strategy.
- Configured the required table joins.
- Created the required Metrics in the published Dataset.

## 3. Remaining Work

The next phase is to implement the API integration required to migrate Tableau dashboards and visualizations into Strategy.

The remaining tasks include:

- **Visualization Creation:** Programmatically create the corresponding visualizations in Strategy.
- **Visualization Mapping:** Translate Tableau chart types and configurations into compatible Strategy visualization configurations.
- **Dashboard Structure:** Recreate the dashboard layout and organize its visualizations.
- **Dataset Integration:** Connect the newly created visualizations to the published Strategy Dataset.
- **Dashboard Reconstruction:** Reproduce the original Tableau dashboard as closely as possible within Strategy.

## 4. Required Technical Support

Further investigation and technical guidance are required regarding:

- Available Strategy REST APIs and SDK capabilities for creating and configuring visualizations and dashboards programmatically.
- The recommended approach for translating Tableau workbook and dashboard metadata into Strategy dashboard objects.
- The API operations and object configurations required to connect visualizations to an existing published Dataset.

## 5. Current Status

**Data Migration: Completed**

The Dataset has been successfully published to Strategy, including the required table joins and Metrics.

**Dashboard and Visualization Migration: Pending**

The remaining focus is implementing the Strategy API integration to programmatically create visualizations and reconstruct the Tableau dashboard in Strategy.

## 6. What's Included

| File / Directory | Purpose |
|---|---|
| `SKILL.md` | Reusable instructions for the Tableau-to-Strategy migration workflow. |
| `tableau_parser.py` | Extracts structured metadata from `.twb` and `.twbx` Tableau workbooks. |
| `visualization_analyzer.py` | Analyzes Tableau worksheets and visualizations. |
| `migration_mapper.py` | Maps Tableau components to Strategy components. |
| `visualization_matcher.py` | Matches Tableau charts with suitable Strategy visualizations. |
| `tableau_to_strategy_migration.py` | Extracts Hyper data and publishes the Dataset to Strategy. |
| `references/FORMULA_TRANSLATION.md` | Reference for translating Tableau formulas into Strategy expressions. |
| `examples/` | Example files and usage references, where applicable. |

## 7. Migration Flow

```text
Tableau Workbook (.twb / .twbx)
              |
              v
     Metadata Extraction
       tableau_parser.py
              |
              v
   Visualization Analysis
    visualization_analyzer.py
              |
              v
      Component Mapping
      migration_mapper.py
              |
              v
    Visualization Matching
    visualization_matcher.py
              |
              v
       Data Migration
tableau_to_strategy_migration.py
              |
              v
     Strategy Dataset
    (Joins + Metrics)
              |
              v
      Strategy API Integration
              |
              v
  Visualizations and Dashboard
       (Remaining Work)
```

## 8. Technologies

- Python
- Tableau Workbook XML (`.twb` / `.twbx`)
- Tableau Hyper API
- Strategy REST API / SDK (dashboard integration phase)
- Strategy Dataset and Semantic Objects

---

**Project Goal:** Develop a reusable workflow that automates the migration of Tableau workbooks, data structures, visualizations, and dashboards into Strategy, reducing manual migration effort while preserving the original dashboard functionality and structure.
