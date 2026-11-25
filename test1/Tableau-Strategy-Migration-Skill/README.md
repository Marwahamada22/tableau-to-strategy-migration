# Tableau → Strategy Cloud Migration Toolkit

Automate the migration of Tableau workbooks (.twb/.twbx) to MicroStrategy/Strategy Cloud dossiers using Claude and a reusable skills file.

Inspired by [Cauchy.io's Power BI → Databricks migration approach](https://blog.cauchy.io/p/how-hard-is-it-to-migrate-a-power), this toolkit applies the same "AI-driven skills file" methodology to migrate Tableau dashboards into Strategy Cloud — with the critical advantage of Strategy's enterprise semantic layer.

## What's Included

| File | Purpose |
|------|---------|
| `SKILL.md` | Claude skills file — the reusable instruction set for Tableau→Strategy migration |
| `tableau_parser.py` | Python parser that extracts structured inventory from .twb/.twbx files |
| `references/FORMULA_TRANSLATION.md` | Complete Tableau formula → Strategy expression mapping |
| `test_superstore.twb` | Sample Tableau workbook for testing (Superstore dataset) |

## Quick Start

### 1. Parse a Tableau Workbook

```bash
python tableau_parser.py my_dashboard.twb --output inventory.json
```

This produces:
- A human-readable **migration summary** (printed to console)
- A structured **JSON inventory** of all data sources, calculated fields, worksheets, dashboards, parameters, filters, and actions
- An automatic **complexity score** (Simple / Moderate / Complex / Enterprise)
- **Strategy-specific recommendations** for the migration

### 2. Use the Skills File with Claude

Feed the `SKILL.md` to Claude Code (or reference it in your Claude project) along with the Tableau `.twb` file. Claude will:

1. Parse the workbook structure
2. Translate calculated fields (including LOD expressions) to Strategy metric expressions
3. Map visualizations to Strategy dossier equivalents
4. Generate the dossier definition for REST API deployment or UI-guided creation

### 3. Build in Strategy

Three approaches depending on your environment:

- **REST API**: Programmatic creation using Strategy's REST API
- **Strategy MCP**: Use Claude's connected Strategy MCP tools for data validation and dashboard building
- **Claude in Chrome**: Visual creation using the `strategy-dashboard-builder` skill

## Why Strategy Over Tableau?

### Semantic Layer (The Killer Feature)
Tableau calculated fields live in the workbook. Every analyst redefines "Revenue" differently. Strategy defines metrics **once** in the semantic layer — change it in one place, it updates everywhere.

### LOD Expressions → Native Dimensionality
Tableau LOD expressions (`{ FIXED ... }`) are per-field workarounds for a problem Strategy solves architecturally. Strategy's metric dimensionality system controls calculation level at the metric definition, inherited by every report automatically.

### Governance
Tableau Row-Level Security is configured per workbook. Strategy security is defined at the semantic layer — one policy governs all content.

### Scalability
Strategy is built for enterprise scale: intelligent caching, in-memory cubes, incremental refresh. No extract workarounds needed.

### AI Integration
Strategy Auto provides natural language querying powered by the semantic layer. The semantic context (metric definitions, hierarchies, relationships) enables AI to understand business meaning — something a flat visualization model cannot provide.

## Complexity Scoring

The parser automatically scores migration complexity:

| Score | Level | Characteristics |
|-------|-------|----------------|
| 0-10 | Simple | Single source, no calcs, basic charts |
| 11-30 | Moderate | Calculated fields, filters, cross-filtering |
| 31-60 | Complex | LOD expressions, table calcs, blended sources |
| 61+ | Enterprise | Custom SQL, RLS, parameters, 20+ worksheets |

## What Migrates Well

- Standard visualizations (bar, line, pie, scatter, map, table, KPI)
- Dimension/measure mappings
- Calculated fields (arithmetic, conditional, string, date)
- LOD expressions (map to Strategy's metric dimensionality — often cleaner)
- Parameters (become Strategy prompts/selectors)
- Dashboard layouts (approximate grid positioning)
- Filter actions (become Strategy selectors and panel interactions)

## Known Gaps

- **Packed bubbles**: No direct equivalent (use treemap or bubble chart)
- **Gantt charts**: Use horizontal bar with date axis
- **Story points**: Map to dossier chapters (sequential narrative)
- **Custom shapes**: Require separate asset upload
- **Tableau extensions**: Evaluate case-by-case
- **Hyper extracts**: Must identify and reconnect to original data source

## Contributing

Every migration surfaces new patterns. When you hit an edge case:

1. Document the Tableau pattern
2. Figure out the Strategy equivalent
3. Add it to the skills file
4. Test on the next migration

The skills file gets smarter with every dashboard migrated.
