# Tableau → Strategy Formula Translation Reference

## Quick Decision Tree

```
Is it an aggregation (SUM, AVG, COUNT...)?
  → Strategy METRIC (fact-level expression)

Is it a row-level calculation without aggregation?
  → Strategy DERIVED ATTRIBUTE or Calculated Column

Does it contain { FIXED ... } ?
  → Strategy LEVEL METRIC with dimensionality set to the FIXED dimensions

Does it contain { INCLUDE ... } ?
  → Strategy metric with added dimensionality (include the extra attribute)

Does it contain { EXCLUDE ... } ?
  → Strategy metric with excluded dimensionality

Does it contain RUNNING_SUM, WINDOW_AVG, LOOKUP, INDEX, RANK?
  → Strategy OLAP FUNCTION or SQL Window Function via ApplySimple

Does it reference a Parameter?
  → Replace with Strategy PROMPT or SELECTOR reference
```

## Complete Function Mapping

### Aggregation Functions

| Tableau | Strategy Metric Expression | ApplySimple Alternative |
|---------|--------------------------|------------------------|
| `SUM([Sales])` | `Sum(Sales)` | N/A |
| `AVG([Price])` | `Avg(Price)` | N/A |
| `COUNT([ID])` | `Count(ID)` | N/A |
| `COUNTD([CustID])` | `Count(Distinct CustID)` | `ApplySimple("COUNT(DISTINCT #0)", CustID)` |
| `MIN([Date])` | `Min(Date)` | N/A |
| `MAX([Date])` | `Max(Date)` | N/A |
| `MEDIAN([Value])` | `Median(Value)` | `ApplySimple("PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY #0)", Value)` |
| `STDEV([Value])` | `Stdev(Value)` | N/A |
| `VAR([Value])` | Custom | `ApplySimple("VARIANCE(#0)", Value)` |
| `ATTR([Field])` | Use as attribute (non-aggregated) | N/A |
| `COLLECT([Geo])` | Not applicable | Geo handled differently |

### Logical / Conditional

| Tableau | Strategy Expression |
|---------|-------------------|
| `IF x > 0 THEN "A" ELSEIF x = 0 THEN "B" ELSE "C" END` | `Case When x > 0 Then "A" When x = 0 Then "B" Else "C" End` |
| `IIF(condition, true_val, false_val)` | `If(condition, true_val, false_val)` |
| `CASE [Field] WHEN "A" THEN 1 WHEN "B" THEN 2 ELSE 0 END` | `Case Field When "A" Then 1 When "B" Then 2 Else 0 End` |
| `IFNULL([Sales], 0)` | `NullToZero(Sales)` or `IfNull(Sales, 0)` |
| `ZN([Sales])` | `NullToZero(Sales)` |
| `ISNULL([Field])` | `IsNull(Field)` |
| `[A] AND [B]` | `A And B` |
| `[A] OR [B]` | `A Or B` |
| `NOT [Flag]` | `Not(Flag)` |
| `CONTAINS([Name], "text")` | `Name Like "%text%"` (in filter) or `ApplySimple("CASE WHEN #0 LIKE '%text%' THEN 1 ELSE 0 END", Name)` |

### String Functions

| Tableau | Strategy | Notes |
|---------|----------|-------|
| `LEFT(str, n)` | `LeftStr(str, n)` | Or `ApplySimple("LEFT(#0, #1)", str, n)` |
| `RIGHT(str, n)` | `RightStr(str, n)` | Or ApplySimple |
| `MID(str, start, len)` | `SubStr(str, start, len)` | 1-based indexing |
| `LEN(str)` | `Length(str)` | |
| `UPPER(str)` | `Upper(str)` | |
| `LOWER(str)` | `Lower(str)` | |
| `TRIM(str)` | `Trim(str)` | |
| `LTRIM(str)` | `LTrim(str)` | |
| `RTRIM(str)` | `RTrim(str)` | |
| `REPLACE(str, old, new)` | `ApplySimple("REPLACE(#0, #1, #2)", str, old, new)` | DB-specific |
| `SPLIT(str, delim, n)` | `ApplySimple("SPLIT_PART(#0, #1, #2)", str, delim, n)` | DB-specific |
| `str1 + str2` | `Concat(str1, str2)` | |
| `FIND(str, substr)` | `Position(substr In str)` | Note: argument order reverses |
| `SPACE(n)` | `ApplySimple("SPACE(#0)", n)` | |
| `ASCII(char)` | `ApplySimple("ASCII(#0)", char)` | |
| `CHAR(code)` | `ApplySimple("CHR(#0)", code)` | |
| `REGEXP_MATCH(str, pattern)` | `ApplySimple("REGEXP_LIKE(#0, #1)", str, pattern)` | DB-specific |
| `REGEXP_EXTRACT(str, pattern)` | `ApplySimple("REGEXP_SUBSTR(#0, #1)", str, pattern)` | DB-specific |
| `REGEXP_REPLACE(str, pattern, repl)` | `ApplySimple("REGEXP_REPLACE(#0, #1, #2)", str, pattern, repl)` | DB-specific |

### Date Functions

| Tableau | Strategy | Notes |
|---------|----------|-------|
| `YEAR([Date])` | Year form of Date attribute | Use date hierarchy |
| `QUARTER([Date])` | Quarter form | Use date hierarchy |
| `MONTH([Date])` | Month form | Use date hierarchy |
| `WEEK([Date])` | Week form | `ApplySimple("EXTRACT(WEEK FROM #0)", Date)` |
| `DAY([Date])` | Day form | Use date hierarchy |
| `DATEPART('year', [Date])` | Year form or `Year(Date)` | |
| `DATEPART('month', [Date])` | Month form or `Month(Date)` | |
| `DATETRUNC('month', [Date])` | `ApplySimple("DATE_TRUNC('month', #0)", Date)` | DB-specific |
| `DATEDIFF('day', [D1], [D2])` | `DateDiff(D1, D2)` | Or ApplySimple for precision |
| `DATEADD('month', n, [Date])` | `ApplySimple("DATEADD(month, #0, #1)", n, Date)` | DB-specific |
| `DATENAME('month', [Date])` | `MonthName(Date)` or formatting | |
| `TODAY()` | `CurrentDate()` | |
| `NOW()` | `CurrentDateTime()` | |
| `MAKEDATE(y, m, d)` | `ApplySimple("MAKE_DATE(#0,#1,#2)", y, m, d)` | DB-specific |
| `MAKEDATETIME(date, time)` | ApplySimple with DB function | |
| `ISDATE(str)` | Handle in ETL | Validation, not semantic layer |

### Math Functions

| Tableau | Strategy | Notes |
|---------|----------|-------|
| `ABS(x)` | `Abs(x)` | Direct |
| `ROUND(x, n)` | `Round(x, n)` | Direct |
| `CEILING(x)` | `Ceiling(x)` | Direct |
| `FLOOR(x)` | `Floor(x)` | Direct |
| `POWER(x, n)` | `Power(x, n)` | Direct |
| `SQRT(x)` | `Sqrt(x)` | Direct |
| `EXP(x)` | `Exp(x)` | Direct |
| `LN(x)` | `Ln(x)` | Direct |
| `LOG(x, base)` | `Log(x)` (base 10) or `Ln(x)/Ln(base)` | |
| `SIGN(x)` | `ApplySimple("SIGN(#0)", x)` | |
| `DIV(x, y)` | `Trunc(x / y)` | Integer division |
| `PI()` | `3.14159265358979` | Literal |
| `HEXBINX(x, y)` | No equivalent | Tableau-specific |
| `HEXBINY(x, y)` | No equivalent | Tableau-specific |

### Type Conversion

| Tableau | Strategy | Notes |
|---------|----------|-------|
| `INT(x)` | `Int(x)` or `Trunc(x)` | |
| `FLOAT(x)` | Cast in ApplySimple | `ApplySimple("CAST(#0 AS FLOAT)", x)` |
| `STR(x)` | `ToString(x)` or `CStr(x)` | |
| `DATE(str)` | `ApplySimple("CAST(#0 AS DATE)", str)` | |
| `DATETIME(str)` | `ApplySimple("CAST(#0 AS TIMESTAMP)", str)` | |

### Table Calculation → OLAP/Window Function Mapping

| Tableau | Strategy OLAP | SQL Window (via ApplySimple) |
|---------|--------------|------------------------------|
| `RUNNING_SUM(SUM(x))` | `RunningSum(Sum(x))` | `SUM(x) OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)` |
| `RUNNING_AVG(SUM(x))` | `RunningAvg(Sum(x))` | `AVG(x) OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)` |
| `RUNNING_MIN(SUM(x))` | `RunningMin(Sum(x))` | `MIN(x) OVER (...)` |
| `RUNNING_MAX(SUM(x))` | `RunningMax(Sum(x))` | `MAX(x) OVER (...)` |
| `RUNNING_COUNT(SUM(x))` | `RunningCount(Sum(x))` | `COUNT(x) OVER (...)` |
| `WINDOW_SUM(SUM(x), -2, 0)` | `MovingSum(Sum(x), 3)` | `SUM(x) OVER (... ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` |
| `WINDOW_AVG(SUM(x), -2, 0)` | `MovingAvg(Sum(x), 3)` | `AVG(x) OVER (... ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` |
| `INDEX()` | `RowNumber()` via SQL | `ROW_NUMBER() OVER (...)` |
| `RANK(SUM(x))` | `Rank(Sum(x))` | `RANK() OVER (ORDER BY SUM(x) DESC)` |
| `RANK_DENSE(SUM(x))` | `Rank(Sum(x))` with dense | `DENSE_RANK() OVER (...)` |
| `LOOKUP(SUM(x), -1)` | `Lag(Sum(x), 1)` | `LAG(SUM(x), 1) OVER (ORDER BY ...)` |
| `LOOKUP(SUM(x), 1)` | `Lead(Sum(x), 1)` | `LEAD(SUM(x), 1) OVER (ORDER BY ...)` |
| `FIRST()` | Custom derivation | `ROW_NUMBER() OVER (...) - 1` |
| `LAST()` | Custom derivation | `COUNT(*) OVER (...) - ROW_NUMBER() OVER (...)` |
| `SIZE()` | Custom derivation | `COUNT(*) OVER (PARTITION BY ...)` |
| `TOTAL(SUM(x))` | Report-level metric | `SUM(SUM(x)) OVER ()` |
| `% of Total` | `Percent to Total` metric | Native in Strategy metric options |

### LOD Expression → Strategy Metric Dimensionality

#### FIXED
```
Tableau:   { FIXED [Dim1], [Dim2] : AGG([Measure]) }
Strategy:  Create metric with Level = {Dim1, Dim2}
           The metric always computes at this level regardless of report context
```

#### INCLUDE
```
Tableau:   { INCLUDE [ExtraDim] : AGG([Measure]) }
Strategy:  Create metric that adds ExtraDim to its calculation level
           even when ExtraDim is not in the visualization
```

#### EXCLUDE
```
Tableau:   { EXCLUDE [Dim] : AGG([Measure]) }
Strategy:  Create metric that removes Dim from its calculation level
           even when Dim IS in the visualization
           → Use dimensionality: "Allow Smart Metric" or override level
```

## Common Composite Patterns

### Profit Ratio / Margin
```
Tableau:  SUM([Profit]) / SUM([Sales])
Strategy: Create derived metric: Sum(Profit) / Sum(Sales)
          Set Format: Percentage, 2 decimal places
```

### Year-over-Year Growth
```
Tableau:  (SUM([Sales]) - LOOKUP(SUM([Sales]), -1)) / ABS(LOOKUP(SUM([Sales]), -1))
Strategy: Create two metrics:
          1. Current Sales: Sum(Sales)
          2. Prior Year Sales: Sum(Sales) with date offset -1 year
          3. YoY Growth: (Current Sales - Prior Year Sales) / Prior Year Sales
          Or use OLAP: (Sum(Sales) - Lag(Sum(Sales), 1)) / Lag(Sum(Sales), 1)
```

### Moving Average
```
Tableau:  WINDOW_AVG(SUM([Sales]), -2, 0)
Strategy: MovingAvg(Sum(Sales), 3)
          Or SQL: AVG(SUM(Sales)) OVER (ORDER BY date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
```

### Percent of Total
```
Tableau:  SUM([Sales]) / TOTAL(SUM([Sales]))
Strategy: Enable "Percent to Total" on the metric
          Or: Sum(Sales) / Sum(Sales){~+}  (Report level denominator)
```

### Running Total
```
Tableau:  RUNNING_SUM(SUM([Sales]))
Strategy: RunningSum(Sum(Sales))
          Order by the date/category dimension on the axis
```

### Top N with Parameter
```
Tableau:  RANK(SUM([Sales])) <= [Parameter_TopN]
Strategy: Create Rank metric: Rank(Sum(Sales))
          Add metric qualification filter: Rank <= Prompt value
          Prompt replaces the Tableau parameter
```

## Parameter → Prompt Migration

| Tableau Parameter Feature | Strategy Prompt Feature |
|--------------------------|------------------------|
| Single value selection | Single-select prompt |
| Value list | List prompt with defined elements |
| Range (slider) | Numeric prompt with min/max |
| Type-in | Text prompt |
| Used in calculated field | Prompt answer referenced in metric expression |
| Used in filter | Prompt drives a filter condition |
| Used in reference line | Prompt sets threshold value |
| Parameter action (on click) | Selector-driven prompt (interactive) |

### Conversion Steps
1. Identify each parameter and where it's referenced
2. Create a Strategy prompt with matching data type and allowable values
3. Replace `[Parameter Name]` references in formulas with `?[Prompt Name]`
4. For parameter actions, use Strategy selectors that drive prompt answers
