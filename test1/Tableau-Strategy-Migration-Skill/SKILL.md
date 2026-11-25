---
name: tableau-to-strategy-migration
description: >
  Migrate Tableau workbooks (.twb/.twbx) to MicroStrategy/Strategy Cloud dossiers.
  Parses Tableau XML to extract data sources, calculated fields, worksheets, dashboards,
  filters, parameters, and LOD expressions, then translates them into Strategy semantic
  layer objects (metrics, attributes, filters) and dossier visualizations. Use when a user
  wants to convert Tableau dashboards to Strategy, compare Tableau vs Strategy capabilities,
  or plan a BI migration from Tableau to MicroStrategy/Strategy Cloud.
---

# Tableau → Strategy Cloud Migration Skill

Automate the migration of Tableau workbooks into MicroStrategy/Strategy Cloud dossiers,
including semantic model translation, calculated field conversion, and visual reconstruction.

## Prerequisites

- Tableau workbook exported as `.twb` (XML) or `.twbx` (packaged with data extracts)
- Access to Strategy Cloud environment with REST API or Claude in Chrome connector
- Target data warehouse/catalog accessible from Strategy (same source tables Tableau uses)
- Python 3.x available for parsing (lxml, xml.etree)

## Quick Reference: What Maps Where

| Tableau Concept | Strategy Equivalent | Notes |
|----------------|---------------------|-------|
| Data Source | Dataset / Cube | Strategy separates semantic layer from visualization |
| Dimension | Attribute | Map to attribute forms |
| Measure | Metric (Fact) | Aggregation defined at metric level |
| Calculated Field | Derived Metric or Attribute | Depends on whether it aggregates |
| LOD Expression (FIXED) | Metric with dimensionality override | Use level metrics in Strategy |
| LOD Expression (INCLUDE) | Metric at lower grain | Add attribute to metric definition |
| LOD Expression (EXCLUDE) | Metric ignoring dimension | Use dimensionality settings |
| Parameter | Prompt / Selector | Strategy prompts are more powerful |
| Filter (dimension) | Attribute Selector / Filter Panel | Field-based filtering |
| Filter (measure) | Metric Qualification | Threshold-based filtering |
| Set | Custom Group or Filter | Depends on complexity |
| Worksheet | Visualization (in dossier chapter) | One viz per worksheet typically |
| Dashboard | Dossier Page / Chapter | Dossier is the container |
| Story | Dossier with multiple chapters | Sequential narrative |
| Tooltip viz | Info Window / Custom Tooltip | Strategy supports rich tooltips |
| Dual Axis | Combination Chart | Use combo chart in Strategy |
| Reference Line | Threshold / Target Line | Built into chart formatting |
| Trend Line | Analytics line | Available in Strategy charts |
| Map (filled) | Choropleth / Shape Map | Strategy has robust geo support |
| Map (symbol) | Density Map / Bubble Map | Lat/long based |
| Tree Map | Tree Map | Direct equivalent |
| Scatter Plot | Scatter Plot | Direct equivalent |
| Box Plot | Box Plot | Direct equivalent |
| Gantt Chart | No direct equivalent | Use horizontal bar with date axis |
| Waterfall | Waterfall Chart | Direct equivalent |
| Funnel | Funnel Chart | Direct equivalent |
| Histogram | Histogram | Direct equivalent |
| Heat Map | Heat Map | Direct equivalent |
| Highlight Table | Heat Map Grid | Color-coded grid |
| Packed Bubbles | No direct equivalent | Use bubble chart or tree map |
| Text Table / Crosstab | Grid / Pivot Table | Strategy grids are very powerful |

## Migration Workflow

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. PARSE        Extract .twb XML → structured representation        │
├──────────────────────────────────────────────────────────────────────┤
│  2. INVENTORY    Catalog all objects: sources, fields, calcs, vizzes │
├──────────────────────────────────────────────────────────────────────┤
│  3. TRANSLATE    Convert Tableau expressions → Strategy expressions   │
├──────────────────────────────────────────────────────────────────────┤
│  4. MAP DATA     Confirm source tables exist in Strategy warehouse   │
├──────────────────────────────────────────────────────────────────────┤
│  5. BUILD        Create Strategy objects via REST API or UI           │
├──────────────────────────────────────────────────────────────────────┤
│  6. VALIDATE     Compare outputs side-by-side, verify numbers match  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Parse Tableau Workbook

### .twb File Structure (XML)

A Tableau `.twb` file is XML with this hierarchy:

```xml
<workbook>
  <preferences />
  <datasources>
    <datasource name="..." caption="...">
      <connection class="..." server="..." dbname="...">
        <relation type="..." name="..." table="...">
          <!-- JOINs defined here -->
        </relation>
      </connection>
      <column name="..." datatype="..." role="dimension|measure" type="..." caption="...">
        <calculation formula="..." class="tableau" />  <!-- calculated fields -->
      </column>
      <aliases />
      <column-instance />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="...">
      <table>
        <view>
          <datasources />
          <datasource-dependencies>
            <!-- columns used in this worksheet -->
          </datasource-dependencies>
          <rows>...</rows>          <!-- dimensions on rows shelf -->
          <cols>...</cols>          <!-- dimensions/measures on columns shelf -->
          <mark class="...">       <!-- mark type: bar, line, area, etc. -->
            <encoding attr="..." />
          </mark>
          <filter />               <!-- worksheet-level filters -->
          <slices />
        </view>
        <pane>
          <encodings>
            <color />
            <size />
            <text />
            <detail />
          </encodings>
        </pane>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name="...">
      <zones>
        <zone name="..." type="..." w="..." h="..." x="..." y="...">
          <!-- layout zones referencing worksheets, filters, legends -->
        </zone>
      </zones>
      <devicelayouts />
    </dashboard>
  </dashboards>
  <windows>
    <!-- tab order and active views -->
  </windows>
</workbook>
```

### Extraction Targets

Parse and extract into a structured inventory:

```python
migration_inventory = {
    "data_sources": [
        {
            "name": "datasource_name",
            "caption": "Human Readable Name",
            "connection": {
                "class": "sqlserver|postgres|databricks|...",
                "server": "hostname",
                "dbname": "database",
                "schema": "schema"
            },
            "tables": [
                {"name": "table_name", "schema": "schema", "alias": "alias"}
            ],
            "joins": [
                {
                    "left_table": "...", "right_table": "...",
                    "left_key": "...", "right_key": "...",
                    "type": "inner|left|right|full"
                }
            ],
            "columns": [
                {
                    "name": "[field_name]",
                    "caption": "Display Name",
                    "datatype": "string|integer|real|date|datetime|boolean",
                    "role": "dimension|measure",
                    "calculation": "SUM([Sales]) / SUM([Quantity])",  # if calculated
                    "default_aggregation": "sum|avg|count|min|max|none"
                }
            ],
            "parameters": [
                {
                    "name": "[Parameter 1]",
                    "caption": "Display Name",
                    "datatype": "string|integer|real|date",
                    "current_value": "...",
                    "allowable_values": "all|list|range",
                    "value_list": ["a", "b", "c"],
                    "range_min": "...", "range_max": "..."
                }
            ]
        }
    ],
    "worksheets": [...],
    "dashboards": [...],
    "filters": [...],
    "actions": [...]
}
```

### Key Parsing Rules

1. **Column names in brackets**: Tableau references fields as `[Field Name]`. Strip brackets for Strategy mapping.
2. **Calculated fields live inside `<column>` with `<calculation>`**: The `formula` attribute contains the Tableau expression.
3. **Data source references use internal names**: The `name` attribute (e.g., `federated.0abc123`) is the internal ID; `caption` is the display name.
4. **Joins are nested `<relation>` elements**: The outer relation wraps inner relations with join clauses.
5. **Mark type = chart type**: The `class` attribute on `<mark>` maps to visualization type (Automatic, Bar, Line, Area, Circle, Square, Text, Map, Pie, Gantt Bar, Polygon, Shape).
6. **Rows and Cols shelves**: Contain field references that define the axes of the visualization.
7. **Encoding channels**: `<color>`, `<size>`, `<text>`, `<detail>`, `<tooltip>`, `<shape>` inside `<encodings>` or `<mark>`.
8. **`.twbx` files are ZIP archives**: Unzip first to get the `.twb` and any packaged data extracts (`.hyper` files).

---

## Step 2: Translate Calculated Fields

### Tableau Formula → Strategy Metric/Attribute Expression

This is the most complex part of the migration. Tableau's formula language must be mapped
to either MicroStrategy metric expressions (SQL-based) or derived attribute expressions.

### Function Translation Reference

#### Aggregation Functions

| Tableau | Strategy Metric Expression | Notes |
|---------|---------------------------|-------|
| `SUM([Sales])` | `Sum(Sales)` | Direct mapping |
| `AVG([Price])` | `Avg(Price)` | Direct mapping |
| `COUNT([OrderID])` | `Count(OrderID)` | Direct mapping |
| `COUNTD([CustomerID])` | `Count(Distinct CustomerID)` | Use ApplySimple if needed |
| `MIN([Date])` | `Min(Date)` | Direct mapping |
| `MAX([Date])` | `Max(Date)` | Direct mapping |
| `MEDIAN([Value])` | `Median(Value)` | Available in Strategy |
| `ATTR([Field])` | Treat as attribute | Non-aggregating reference |
| `RUNNING_SUM(SUM([Sales]))` | Running sum metric (table calc) | Use OLAP/window function |
| `RUNNING_AVG(...)` | Running avg metric | Use OLAP/window function |
| `WINDOW_SUM(...)` | Window metric | Use OLAP/window function |
| `WINDOW_AVG(...)` | Window metric | Use OLAP/window function |
| `TOTAL(SUM([Sales]))` | Metric with "Report" level | Aggregates across entire report |

#### String Functions

| Tableau | Strategy (SQL Pass-through or Derived) | Notes |
|---------|---------------------------------------|-------|
| `LEFT([Name], 3)` | `LEFT(Name, 3)` or `SUBSTR(Name, 1, 3)` | Use ApplySimple for DB-native |
| `RIGHT([Name], 3)` | `RIGHT(Name, 3)` | DB-specific |
| `MID([Name], 2, 5)` | `SUBSTR(Name, 2, 5)` | Standard SQL |
| `LEN([Name])` | `LENGTH(Name)` | Standard SQL |
| `UPPER([Name])` | `UPPER(Name)` | Direct |
| `LOWER([Name])` | `LOWER(Name)` | Direct |
| `TRIM([Name])` | `TRIM(Name)` | Direct |
| `CONTAINS([Name], "abc")` | `Name LIKE '%abc%'` | Use in filter or ApplySimple |
| `STARTSWITH([Name], "A")` | `Name LIKE 'A%'` | Use in filter |
| `REPLACE([Name], "old", "new")` | `REPLACE(Name, 'old', 'new')` | DB-specific |
| `SPLIT([Name], "-", 1)` | `SPLIT_PART(Name, '-', 1)` | DB-specific, use ApplySimple |
| `[First] + " " + [Last]` | `ConcatStr(First, " ", Last)` or ApplySimple | Concatenation |

#### Date Functions

| Tableau | Strategy | Notes |
|---------|----------|-------|
| `DATEPART('year', [Date])` | `Year(Date)` attribute form | Map to date hierarchy |
| `DATEPART('quarter', [Date])` | `Quarter(Date)` | Use date hierarchy |
| `DATEPART('month', [Date])` | `Month(Date)` | Use date hierarchy |
| `DATEPART('week', [Date])` | `Week(Date)` | Use date hierarchy |
| `DATEPART('day', [Date])` | `Day(Date)` | Use date hierarchy |
| `DATETRUNC('month', [Date])` | First day of month calc | ApplySimple: `DATE_TRUNC('month', Date)` |
| `DATEDIFF('day', [Start], [End])` | `DATEDIFF(Start, End)` | Or ApplySimple for DB-specific |
| `DATEADD('month', 3, [Date])` | ApplySimple: `DATEADD(month, 3, Date)` | DB-specific |
| `TODAY()` | `CurrentDate()` | Strategy function |
| `NOW()` | `CurrentDateTime()` | Strategy function |
| `YEAR([Date])` | Year attribute form | Part of date hierarchy |
| `MONTH([Date])` | Month attribute form | Part of date hierarchy |
| `ISDATE([Field])` | Validation logic | Handle in ETL, not semantic layer |

#### Logical Functions

| Tableau | Strategy | Notes |
|---------|----------|-------|
| `IF [Sales] > 1000 THEN "High" ELSE "Low" END` | `Case When Sales > 1000 Then "High" Else "Low" End` or `If(Sales > 1000, "High", "Low")` | Strategy supports both |
| `IIF([Sales] > 0, [Sales], 0)` | `If(Sales > 0, Sales, 0)` | Direct |
| `CASE [Region] WHEN "East" THEN 1 WHEN "West" THEN 2 END` | `Case Region When "East" Then 1 When "West" Then 2 End` | Direct |
| `IFNULL([Sales], 0)` | `NullToZero(Sales)` or `IfNull(Sales, 0)` | Strategy has NullToZero |
| `ZN([Sales])` | `NullToZero(Sales)` | Tableau shorthand for IFNULL(x, 0) |
| `ISNULL([Field])` | `IsNull(Field)` | Direct |
| `[Sales] > 0 AND [Qty] > 0` | `Sales > 0 And Qty > 0` | Direct |
| `[Sales] > 0 OR [Qty] > 0` | `Sales > 0 Or Qty > 0` | Direct |
| `NOT [IsReturned]` | `Not(IsReturned)` | Direct |

#### Table Calculations → OLAP/Window Functions

Table calculations are Tableau's most complex feature. In Strategy, these translate to
either OLAP functions, derived metrics with specific dimensionality, or SQL window functions
via pass-through.

| Tableau Table Calc | Strategy Approach | Implementation |
|-------------------|-------------------|----------------|
| `RUNNING_SUM(SUM([Sales]))` | OLAP Running Sum | `RunningSum(Sum(Sales))` or window function |
| `RUNNING_AVG(SUM([Sales]))` | OLAP Running Avg | `RunningAvg(Sum(Sales))` |
| `INDEX()` | Row number | `Rank()` or `RowNumber()` via SQL |
| `FIRST()` | Offset from first | Custom derivation |
| `LAST()` | Offset from last | Custom derivation |
| `LOOKUP(SUM([Sales]), -1)` | Lag function | `Lag(Sum(Sales), 1)` via OLAP |
| `RANK(SUM([Sales]))` | Rank metric | `Rank(Sum(Sales))` — native in Strategy |
| `RANK_DENSE(...)` | Dense rank | `Rank()` with dense option |
| `RANK_UNIQUE(...)` | Row number rank | `RowNumber()` via SQL |
| `SIZE()` | Partition size | Custom calculation |
| `% of Total` | Percent to total | Native in Strategy metric options |
| `Difference from` | Metric comparison | Derived metric: Current - Previous |
| `% Difference from` | Metric comparison | Derived metric: (Curr - Prev) / Prev |
| `Moving Average` | N-period moving avg | OLAP `MovingAvg(metric, n)` |

### LOD Expressions → Strategy Dimensionality

LOD (Level of Detail) expressions are one of Tableau's most powerful features.
Strategy handles this through **metric dimensionality** — a core strength of the platform.

#### FIXED LOD

```
Tableau:  { FIXED [Customer] : SUM([Sales]) }
Strategy: Create a metric "Customer Sales" with:
          - Formula: Sum(Sales)
          - Dimensionality: "Report level" set to Customer
          - This metric always calculates at Customer level regardless of other dimensions in the viz
```

**Strategy implementation options:**
1. **Level metric**: Define the metric at a specific attribute level
2. **Subtotal metric**: Use subtotal dimensionality settings
3. **Derived metric with filter**: Create a child metric that controls its own grain

#### INCLUDE LOD

```
Tableau:  { INCLUDE [Product] : AVG([Sales]) }
Strategy: Create a metric that includes Product in its calculation even when
          Product is not on the visualization.
          - Use a "conditionality" or "dimensionality" extension on the base metric
```

#### EXCLUDE LOD

```
Tableau:  { EXCLUDE [Region] : SUM([Sales]) }
Strategy: Create a metric that ignores Region even when Region is on the visualization.
          - Use dimensionality settings to exclude the attribute
          - Or use a "Report" level metric that aggregates above Region
```

**Key insight**: Strategy's metric dimensionality system is actually MORE powerful than
Tableau LOD expressions because it's built into the semantic layer and inherited across
all reports. In Tableau, LODs must be redefined in every calculated field. In Strategy,
you define it once at the metric level.

---

## Step 3: Map Visualizations

### Worksheet → Dossier Visualization Mapping

For each Tableau worksheet, create a corresponding visualization in a Strategy dossier chapter.

#### Reading Tableau Worksheet XML

```xml
<worksheet name="Sales by Region">
  <table>
    <view>
      <datasources>
        <datasource caption="Sales Data" name="federated.abc123" />
      </datasources>
      <rows>[federated.abc123].[Region]</rows>
      <cols>[federated.abc123].[:Measure Names]</cols>
      <mark class="Bar">
        <encoding attr="color" field="[federated.abc123].[Category]" />
      </mark>
    </view>
  </table>
</worksheet>
```

**Translation rules:**
- `<rows>` fields → Strategy "Rows" zone (vertical axis / row grouping)
- `<cols>` fields → Strategy "Columns" zone (horizontal axis)
- `<mark class="Bar">` → Bar Chart visualization type
- `<encoding attr="color">` → "Color By" attribute in Strategy
- `<encoding attr="size">` → "Size By" metric in Strategy
- `<encoding attr="text">` → Data labels / "Text" in Strategy
- `<encoding attr="detail">` → "Break By" in Strategy (adds granularity without visual encoding)
- `<encoding attr="tooltip">` → Tooltip configuration

#### Mark Type → Strategy Visualization Type

| Tableau Mark | Strategy Visualization | Config Notes |
|-------------|----------------------|--------------|
| `Automatic` | Infer from context | Bar if discrete dimensions, line if continuous date |
| `Bar` | Vertical Bar Chart | Horizontal if dimension is on rows |
| `Line` | Line Chart | Add markers if few data points |
| `Area` | Area Chart | Stacked if multiple series |
| `Circle` | Scatter Plot | Needs two measure axes |
| `Square` | Heat Map | Color intensity by measure |
| `Text` | Grid / Table | Text table visualization |
| `Map` | Map Visualization | Geo hierarchy required |
| `Pie` | Pie Chart | Single dimension + single measure |
| `Gantt Bar` | Horizontal Bar | Date-based, no direct Gantt in Strategy |
| `Polygon` | Custom Shape Map | Advanced, may need manual recreation |
| `Shape` | Scatter with shapes | Use shape encoding in Strategy |

### Dashboard Layout → Dossier Page Layout

#### Reading Tableau Dashboard XML

```xml
<dashboard name="Executive Overview">
  <size maxheight="900" maxwidth="1400" minheight="900" minwidth="1400" />
  <zones>
    <zone h="300" w="700" x="0" y="0" name="Sales by Region" type="...">
      <!-- references worksheet -->
    </zone>
    <zone h="300" w="700" x="700" y="0" name="Revenue Trend" type="...">
      <!-- references worksheet -->
    </zone>
    <zone h="300" w="1400" x="0" y="300" name="Detail Table" type="...">
      <!-- references worksheet -->
    </zone>
  </zones>
</dashboard>
```

**Translation rules:**
- Dashboard `<size>` → Dossier page dimensions
- Each `<zone>` becomes a visualization panel in the dossier
- Zone `x, y, w, h` attributes → Panel positioning (Strategy uses a grid layout)
- Approximate Tableau pixel positions to Strategy's 12-column grid:
  - `x=0, w=700` out of 1400 total → columns 1-6 (left half)
  - `x=700, w=700` → columns 7-12 (right half)
  - `x=0, w=1400` → columns 1-12 (full width)

### Filter Actions → Strategy Selectors and Interactions

#### Tableau Filter Types → Strategy Equivalents

| Tableau Filter | Strategy Equivalent | Implementation |
|---------------|--------------------|-----------------| 
| Dimension filter (list) | Attribute Element Selector | Dropdown or multi-select list |
| Dimension filter (wildcard) | Attribute search selector | Text search with contains/starts with |
| Measure filter (range) | Metric Range Qualification | Slider or min/max inputs |
| Date filter (relative) | Date Selector (relative) | "Last N months" type selector |
| Date filter (range) | Date Selector (range) | Date picker with start/end |
| Top N filter | Metric-based rank filter | "Top N" in Strategy filter |
| Context filter | Filter execution order | Strategy handles via filter hierarchy |
| Parameter action | Selector-driven filtering | Strategy selectors + targets |
| Filter action (on select) | Panel interaction / Filter target | Cross-filtering between panels |
| Highlight action | Visual group | Highlight mode in Strategy |
| URL action | Link action | Hyperlink on click |
| Go to Sheet action | Navigation between chapters | Chapter navigation |

#### Cross-Filtering (Dashboard Actions)

In Tableau, you configure filter actions between worksheets. In Strategy, this is
handled through **panel selectors** and **filter targets**:

1. **Source panel**: The panel where the user clicks
2. **Target panels**: Panels that react to the selection
3. **Filter field**: The attribute that connects them (must exist in both panels' datasets)

**Strategy advantage**: If all panels use the same dataset/cube, cross-filtering is automatic.
You only need explicit configuration when panels use different data sources.

**Strategy implementation**:
- Page-level selectors automatically filter all panels on the page
- Panel-level interactions configured via "Use as Filter" on the source panel
- Group-level filtering for panels sharing a filter set

---

## Step 4: Build in Strategy

### Option A: Strategy REST API (Programmatic)

Use the Strategy REST API to create dossiers programmatically. This is the recommended
approach for automated/repeatable migrations.

#### API Workflow

```
1. POST /api/auth/login                    → Get auth token
2. GET  /api/model/tables                  → Verify source tables exist
3. POST /api/model/metrics                 → Create metrics
4. POST /api/model/attributes              → Create/verify attributes
5. POST /api/dossiers                      → Create empty dossier
6. PUT  /api/dossiers/{id}/definition      → Add chapters, pages, visualizations
7. POST /api/dossiers/{id}/instances       → Execute/validate
```

#### Dossier Definition JSON Structure

```json
{
  "name": "Migrated Dashboard - [Original Tableau Name]",
  "chapters": [
    {
      "name": "Page 1",
      "pages": [
        {
          "name": "Page 1",
          "visualizations": [
            {
              "name": "Sales by Region",
              "vizType": "grid",
              "rows": [
                {"id": "attr_region_id", "name": "Region", "type": "attribute"}
              ],
              "columns": [
                {"id": "metric_sales_id", "name": "Total Sales", "type": "metric"}
              ],
              "colorBy": [
                {"id": "attr_category_id", "name": "Category", "type": "attribute"}
              ],
              "filters": [...]
            }
          ],
          "selectors": [...]
        }
      ]
    }
  ]
}
```

### Option B: Strategy MCP Tools (Claude-Assisted)

If the Strategy MCP tools are connected, use them to:

1. **Query data model**: Use `Strategy:list_mosaic_models` and `Strategy:list_columns` to verify source tables
2. **Validate data**: Use `Strategy:query` to run SQL against the source and validate calculated field translations
3. **Build via UI**: Use the `strategy-dashboard-builder` skill with Claude in Chrome to build the dossier visually

### Option C: Hybrid Approach (Recommended for Complex Migrations)

1. Parse Tableau `.twb` with Python to generate the inventory and translations
2. Create the semantic layer objects (metrics, attributes) via REST API
3. Build the dossier layout via Claude in Chrome using the dashboard builder skill
4. Validate numbers by running SQL queries through the Strategy MCP `query` tool

---

## Step 5: Validate

### Validation Checklist

For each migrated visualization:

- [ ] **Data accuracy**: Numbers match between Tableau and Strategy (within rounding tolerance)
- [ ] **Aggregation correctness**: SUM/AVG/COUNT/COUNTD produce same results
- [ ] **Filter behavior**: Selecting the same filter value shows the same subset
- [ ] **Cross-filtering**: Clicking on a bar/segment filters other panels correctly
- [ ] **Date handling**: Date hierarchies (Year > Quarter > Month) drill correctly
- [ ] **Calculated fields**: Complex calculations produce matching results
- [ ] **Sort order**: Default sort matches original dashboard
- [ ] **Null handling**: NULL values treated consistently (shown, hidden, zero-filled)
- [ ] **Formatting**: Number formats, date formats, currency symbols correct

### Validation SQL Template

Run this against both the Tableau data source and Strategy warehouse to compare:

```sql
-- Validate a specific metric at a specific grain
SELECT
    [dimension_field] AS dimension_value,
    SUM([measure_field]) AS measure_total,
    COUNT(DISTINCT [key_field]) AS distinct_count
FROM [source_table]
WHERE [filter_conditions]
GROUP BY [dimension_field]
ORDER BY measure_total DESC
LIMIT 20;
```

---

## Common Migration Challenges

### Challenge 1: Tableau Extracts (.hyper files)

Tableau extracts contain pre-aggregated or filtered data snapshots. Strategy connects
to live data. You must:
1. Identify the original source query behind the extract
2. Verify all rows are available in the Strategy warehouse
3. Check if the extract includes any transformations (renamed columns, calculated fields baked in)

### Challenge 2: Blended Data Sources

Tableau data blending (linking on a shared dimension) is deprecated in favor of relationships.
In Strategy, this maps to:
- **Same warehouse**: Create a freeform SQL dataset with JOINs
- **Different warehouses**: Use Strategy's multi-source dataset capability
- **Fallback**: Create a view in the warehouse that pre-joins the tables

### Challenge 3: Table Calculations with Partitioning

Tableau table calcs use "Compute Using" / "Addressing & Partitioning" to control which
dimensions the calculation runs across. In Strategy:
- Use OLAP functions with explicit partition specifications
- Or use SQL window functions via `ApplySimple("WINDOW_FUNC() OVER (PARTITION BY ... ORDER BY ...)", ...)`

### Challenge 4: Custom SQL Data Sources

Tableau allows custom SQL as a data source. In Strategy:
- Create the SQL as a Freeform SQL report or dataset
- Or materialize it as a view in the warehouse
- Prefer materializing for performance

### Challenge 5: Row-Level Security

Tableau Row-Level Security (RLS) uses calculated fields or data source filters.
Strategy has built-in security filters at the attribute level in the semantic layer.
This is actually a major **upgrade** — security is enforced centrally, not per-workbook.

---

## Migration Estimation Guide

| Dashboard Complexity | Estimated Effort | Characteristics |
|---------------------|-----------------|-----------------|
| Simple | 1-2 hours | Single data source, no calcs, basic charts, <5 worksheets |
| Moderate | 4-8 hours | Calculated fields, filters, cross-filtering, 5-10 worksheets |
| Complex | 1-3 days | LOD expressions, table calcs, blended sources, 10+ worksheets |
| Enterprise | 1-2 weeks | Custom SQL, RLS, embedded analytics, parameters, 20+ worksheets |

### Complexity Scoring

Parse the `.twb` and auto-score:

```python
complexity_score = 0
complexity_score += len(calculated_fields) * 2        # each calc field adds complexity
complexity_score += len(lod_expressions) * 5           # LODs are hardest to translate
complexity_score += len(table_calculations) * 4        # table calcs need careful handling
complexity_score += len(parameters) * 2                # parameters need prompt mapping
complexity_score += len(data_sources) * 3              # multiple sources add join complexity
complexity_score += len(dashboard_actions) * 2         # actions need interaction mapping
complexity_score += len(custom_sql_sources) * 5        # custom SQL needs careful review

# Score interpretation:
# 0-10:  Simple
# 11-30: Moderate
# 31-60: Complex
# 61+:   Enterprise
```

---

## Selling the Migration: Strategy Advantages

When positioning this migration to prospects, emphasize these Strategy advantages over Tableau:

### Semantic Layer (The Killer Feature)
- **Tableau**: Calculated fields live in the workbook. Every analyst redefines "Revenue" differently.
- **Strategy**: Metrics are defined ONCE in the semantic layer and inherited by every report.
  Change the definition in one place, it updates everywhere.

### Governance & Security
- **Tableau**: Row-level security configured per workbook or data source.
- **Strategy**: Security defined at the semantic layer. One policy governs all content.

### Scalability
- **Tableau**: Performance degrades with data volume. Extracts are a workaround, not a solution.
- **Strategy**: Built for massive scale. Intelligent caching, in-memory cubes, incremental refresh.

### Mobile
- **Tableau**: Separate mobile layout required.
- **Strategy**: Dossiers are responsive by default with dedicated mobile optimization.

### Enterprise Distribution
- **Tableau**: Server-based sharing with viewer licenses.
- **Strategy**: Library-based distribution with subscriptions, batch distribution, and HyperIntelligence for embedding insights in any app.

### AI Integration
- **Strategy Auto**: Natural language querying built into the platform.
- Strategy's semantic layer means AI can query data with business context (metric definitions,
  attribute hierarchies) — something Tableau's flat model cannot provide.

---

## Supporting Files

- [TABLEAU_PARSER.md](references/TABLEAU_PARSER.md) — Python parser for .twb XML extraction
- [FORMULA_TRANSLATION.md](references/FORMULA_TRANSLATION.md) — Complete function-by-function mapping
- [VISUAL_MAPPING.md](references/VISUAL_MAPPING.md) — Detailed visualization type conversions
- [EXAMPLE_MIGRATIONS.md](references/EXAMPLE_MIGRATIONS.md) — Worked examples with before/after
