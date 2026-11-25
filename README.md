

1. Implemented Flow

The current workflow consists of the following components:

tableau_parser.py: Extracts Tableau workbook metadata, including data sources, worksheets, dashboards, fields, and other relevant information.
visualization_analyzer.py: Analyzes Tableau worksheets and visualizations.
migration_mapper.py: Maps Tableau components to their corresponding Strategy components.
visualization_matcher.py: Matches Tableau chart types with suitable Strategy visualizations.
tableau_to_strategy_migration.py: Extracts data from the Tableau Hyper file, reads the tables, classifies columns into Attributes and Metrics, and publishes the Dataset to Strategy.

2. Current Progress

Successfully extracted Tableau workbook metadata.
Successfully extracted data from the Hyper file.
Successfully published the Dataset to Strategy.
Created the required table joins and Metrics in the published Dataset.

3. Remaining Work

The remaining step is to implement the API integration between Tableau and Strategy to migrate the dashboard structure and visualizations.

This includes:

Creating the corresponding visualizations in Strategy.
Mapping Tableau chart configurations to Strategy visualization configurations.
Creating the dashboard layout and connecting the visualizations to the published Dataset.
Reproducing the dashboard as closely as possible to the original Tableau dashboard.

4. Required Support

I need guidance on the available Strategy REST APIs/SDKs for programmatically creating and configuring visualizations and dashboards, and the recommended approach for translating Tableau dashboard  into Strategy dashboard objects.



Current Status: The data migration part is completed, including Dataset publishing, joins, and Metrics. The remaining focus is dashboard and visualization migration through the Strategy APIs.






## What's Included

| File | Purpose |
|------|---------|
| `SKILL.md` | Claude skills file — the reusable instruction set for Tableau→Strategy migration |
| `tableau_parser.py` | Python parser that extracts structured inventory from .twb/.twbx files |
| `references/FORMULA_TRANSLATION.md` | Complete Tableau formula → Strategy expression mapping |
| `test_superstore.twb` | Sample Tableau workbook for testing (Superstore dataset) |
