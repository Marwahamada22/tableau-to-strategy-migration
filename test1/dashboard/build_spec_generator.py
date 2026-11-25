#!/usr/bin/env python3
"""
build_spec_generator.py  -  Stage 2: analyze worksheets/dashboards and bind to the published dataset.
READ-ONLY: it never writes to Strategy.

Usage:
  python build_spec_generator.py dashboard/task_2.twbx --offline
  python build_spec_generator.py dashboard/task_2.twbx --dataset-name Tableau_Migrated_Dataset
  python build_spec_generator.py dashboard/task_2.twbx --dataset-id <ID>

Env (for binding only; never paste in chat): MSTR_TOKEN, MSTR_COOKIE, MSTR_PROJECT
"""
import argparse, json, math, os, re, zipfile
from collections import Counter
import xml.etree.ElementTree as ET
from pathlib import Path
import requests

BASE = os.getenv("MSTR_BASE_URL",
                 "https://education.cloud.microstrategy.com/MicroStrategyLibrary/api")
PROJECT = os.getenv("MSTR_PROJECT", "B7CA92F04B9FAE8D941C3E9B7E0CD754")
BR = re.compile(r"\[([^\[\]]+)\]")
AGG = {"sum": "SUM", "avg": "AVG", "cnt": "COUNT", "ctd": "COUNTD", "min": "MIN",
       "max": "MAX", "med": "MEDIAN", "none": None, "io": "SET",
       "yr": "YEAR", "qr": "QUARTER", "mn": "MONTH", "dy": "DAY", "wk": "WEEK",
       "tyr": "YEAR", "tqr": "QUARTER", "tmn": "MONTH", "tdy": "DAY", "twk": "WEEK"}
MEASURE_AGGS = {"SUM", "AVG", "COUNT", "COUNTD", "MIN", "MAX", "MEDIAN"}
MARK_TO_VIZ = {"Bar": "bar_chart", "Line": "line_chart", "Area": "area_chart",
               "Pie": "pie_ring", "Map": "map_markers", "Circle": "scatter_bubble",
               "Square": "heat_map", "Text": "grid", "Polygon": "map_areas",
               "Shape": "scatter_bubble", "Gantt Bar": None}
CHANNELS = {"color": "color_by", "size": "size_by", "text": "label", "detail": "break_by",
            "lod": "break_by", "tooltip": "tooltip", "shape": "shape_by", "label": "label"}


# ---------------------------------------------------------------- load
def load_twb(path):
    p = Path(path)
    if p.suffix.lower() == ".twbx":
        with zipfile.ZipFile(p) as z:
            name = next(n for n in z.namelist() if n.endswith(".twb"))
            return ET.fromstring(z.read(name))
    return ET.parse(p).getroot()


def build_catalog(root):
    """field name -> metadata (caption, role, datatype, semantic role, kind, formula)."""
    cat = {}
    for ds in root.iter("datasource"):
        is_param = ds.get("name") == "Parameters"
        for col in ds.findall("column"):
            name = col.get("name", "").strip("[]")
            if not name:
                continue
            calc = col.find("calculation")
            cls = calc.get("class", "") if calc is not None else ""
            if is_param or col.get("param-domain-type"):
                kind = "parameter"
            elif cls == "bin":
                kind = "bin"
            elif cls == "categorical-bin":
                kind = "group"
            elif calc is not None and calc.get("formula"):
                kind = "calc"
            elif calc is not None:
                kind = "unknown_calc"
            else:
                kind = "field"
            cat[name] = {"caption": col.get("caption") or name, "role": col.get("role", ""),
                         "datatype": col.get("datatype", ""), "kind": kind,
                         "semantic_role": col.get("semantic-role", ""),
                         "formula": calc.get("formula", "") if calc is not None else ""}
        for g in ds.findall("group"):          # heuristic: groups vs sets via ui-builder
            name = g.get("name", "").strip("[]")
            ui = next((v for k, v in g.attrib.items() if k.endswith("ui-builder")), "")
            kind = "set" if "filter" in ui else "group" if "group" in ui else "unknown_group"
            cat[name] = {"caption": g.get("caption") or name, "role": "dimension",
                         "datatype": "string", "kind": kind, "semantic_role": "", "formula": ""}
    return cat


# ---------------------------------------------------------------- fields
def parse_shelf(text, cat):
    out = []
    for item in BR.findall(text or ""):
        if item.startswith("federated.") or item.startswith("__tableau_internal"):
            continue
        parts = item.split(":")
        if len(parts) >= 3:
            code, name, suffix = parts[0], ":".join(parts[1:-1]), parts[-1]
        else:
            code, name, suffix = None, item, ""
        if re.search(r"_[0-9A-Fa-f]{32}$", name) and code == "cnt":      # Number of Records
            table = re.sub(r"_[0-9A-Fa-f]{32}$", "", name)
            out.append({"name": f"{table} (record count)", "caption": f"Count of {table}",
                        "role": "measure", "aggregation": "COUNT", "kind": "record_count",
                        "datatype": "integer", "semantic_role": "", "formula": "",
                        "continuous": True})
            continue
        info = cat.get(name, {})
        agg = AGG.get(code) if code else None
        kind = info.get("kind", "field")
        if agg in MEASURE_AGGS:
            role = "measure"
        elif info.get("role") == "measure" and not agg and kind in ("field", "calc"):
            role = "measure"
        else:
            role = "dimension"
        out.append({"name": name, "caption": info.get("caption", name), "role": role,
                    "aggregation": agg, "kind": kind, "datatype": info.get("datatype", ""),
                    "semantic_role": info.get("semantic_role", ""),
                    "formula": info.get("formula", ""),
                    "continuous": suffix.startswith("q") or (code or "").startswith("t")})
    return out


def parse_filters(view, cat):
    out = []
    for f in view.findall("filter") if view is not None else []:
        fields = parse_shelf(f.get("column", ""), cat)
        if not fields or fields[-1]["name"].startswith("Action ("):
            continue
        fld = fields[-1]
        members, mode = [], "include"
        for g in f.iter("groupfilter"):
            if g.get("function") == "except":
                mode = "exclude"
            if g.get("member"):
                members.append(g.get("member").strip('"'))
        mn, mx = f.find("min"), f.find("max")
        ftype = f.get("class", "categorical")
        out.append({"field": fld["name"], "caption": fld["caption"], "type": ftype,
                    "mode": mode if members else "all_values_interactive",
                    "members": members,
                    "min": mn.text if mn is not None else None,
                    "max": mx.text if mx is not None else None})
    return out


# ---------------------------------------------------------------- viz decision
def decide_viz(mark, rows, cols, enc):
    allf = rows + cols
    dims = [f for f in allf if f["role"] == "dimension" and f["kind"] != "set"]
    meas = [f for f in allf if f["role"] == "measure"]
    geo = [f["caption"] for f in dims if f["semantic_role"]]
    alts = ["map_areas"] if geo and mark != "Map" else []
    if mark != "Automatic":
        viz = MARK_TO_VIZ.get(mark)
        orient = None
        if viz == "bar_chart":
            orient = "horizontal" if any(f["role"] == "measure" for f in cols) else "vertical"
        return {"viz_id": viz, "orientation": orient, "confidence": "high" if viz else "none",
                "rule": f"EXPLICIT_MARK_{mark}", "alternatives": alts}
    # Tableau "Automatic": depends on what is on the shelves
    has_date = any(f["datatype"] in ("date", "datetime") for f in dims)
    cont_date = any(f["datatype"] in ("date", "datetime") and f["continuous"] for f in dims)
    if len(meas) >= 2 and not dims:
        viz, rule = "scatter_bubble", "TWO_MEASURES"
    elif meas and cont_date:
        viz, rule = "line_chart", "CONTINUOUS_DATE_WITH_MEASURE"
    elif meas and dims and len(meas) == 1:
        viz, rule = "bar_chart", "DIMENSION_WITH_MEASURE"
    elif len(meas) == 1 and not dims:
        viz, rule = "kpi", "SINGLE_MEASURE"
    elif dims or meas:
        viz, rule = "grid", "MULTI_FIELD_DEFAULT"
    else:
        viz, rule = None, "NO_FIELDS"
    orient = None
    if viz == "bar_chart":
        orient = "horizontal" if any(f["role"] == "measure" for f in cols) else "vertical"
    return {"viz_id": viz, "orientation": orient,
            "confidence": "medium" if viz else "none", "rule": rule,
            "alternatives": alts, "has_date": has_date}


def analyze_worksheet(ws, cat, registry):
    view = ws.find("table/view")

    def shelf_text(tag):
        # In real workbooks <rows>/<cols> are children of <table>, siblings of <view>.
        for parent in (ws.find("table"), view):
            if parent is not None and parent.findtext(tag):
                return parent.findtext(tag)
        return ""

    rows = parse_shelf(shelf_text("rows"), cat)
    cols = parse_shelf(shelf_text("cols"), cat)
    marks = [m.get("class", "Automatic") for m in ws.iter("mark")]
    mark = next((m for m in marks if m != "Automatic"), "Automatic")
    enc, seen = [], set()
    for pane in ws.iter("pane"):
        e = pane.find("encodings")
        for ch in (e if e is not None else []):
            for f in parse_shelf(ch.get("column", ""), cat):
                key = (ch.tag, f["name"])
                if key not in seen:
                    seen.add(key)
                    enc.append({"strategy_slot": CHANNELS.get(ch.tag, ch.tag),
                                "tableau_channel": ch.tag, **f})
    decision = decide_viz(mark, rows, cols, enc)
    fields = {}
    for f in rows + cols + enc:
        fields.setdefault((f["name"], f["aggregation"]), f)
    status = "READY_TO_BUILD"
    if not decision["viz_id"] or (registry and decision["viz_id"] not in registry):
        status = "UNSUPPORTED"
    elif decision["confidence"] != "high" or any(
            f["kind"] in ("unknown_calc", "unknown_group") for f in fields.values()):
        status = "MANUAL_REVIEW"
    return {"name": ws.get("name"), "tableau_mark": mark, "viz": decision, "status": status,
            "rows": rows, "columns": cols, "encodings": enc,
            "dimensions": [f for f in fields.values() if f["role"] == "dimension"],
            "measures": [f for f in fields.values() if f["role"] == "measure"],
            "filters": parse_filters(view, cat)}


# ---------------------------------------------------------------- dashboards
def parse_dashboards(root, ws_names):
    out = []
    node = root.find("dashboards")
    for db in node.findall("dashboard") if node is not None else []:
        size = db.find("size")
        h_px = int(size.get("maxheight")) if size is not None and size.get("maxheight") else 900
        w_px = int(size.get("maxwidth")) if size is not None and size.get("maxwidth") else 1400
        zones = [z for z in db.iter("zone") if z.get("w")]
        unit_w = 100000 if any(z.get("w") == "100000" for z in zones) else w_px
        unit_h = 100000 if any(z.get("h") == "100000" for z in zones) else h_px
        rows_total = max(6, math.ceil(h_px / 150))
        items, skipped = [], Counter()
        for z in zones:
            t, name = z.get("type-v2", ""), z.get("name", "")
            if not t and name in ws_names:
                kind = "viz"
            elif t in ("filter", "paramctrl", "color", "text", "title"):
                kind = {"color": "legend", "title": "text"}.get(t, t)
            else:
                skipped[t or "container/other"] += 1
                continue
            x, y, w, h = (int(z.get(k, 0)) for k in "xywh")
            c0 = min(12, int(x / unit_w * 12) + 1)
            c1 = min(13, max(c0 + 1, round((x + w) / unit_w * 12) + 1))
            r0 = min(rows_total, int(y / unit_h * rows_total) + 1)
            r1 = min(rows_total + 1, max(r0 + 1, round((y + h) / unit_h * rows_total) + 1))
            items.append({"kind": kind, "name": name, "param": z.get("param"),
                          "col_start": c0, "col_end": c1, "row_start": r0, "row_end": r1})
        out.append({"dashboard": db.get("name"), "size_px": [w_px, h_px],
                    "grid": f"12 columns x {rows_total} rows (end exclusive)",
                    "zones": items, "skipped_zone_types": dict(skipped)})
    return out


# ---------------------------------------------------------------- Strategy binding (read-only)
def _session():
    s = requests.Session()
    s.headers.update({"X-MSTR-AuthToken": os.environ["MSTR_TOKEN"],
                      "X-MSTR-ProjectID": PROJECT, "Accept": "application/json"})
    if os.environ.get("MSTR_COOKIE"):
        s.headers["Cookie"] = os.environ["MSTR_COOKIE"]
    return s


def _collect(node, key, acc):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, list):
                acc += [i["name"] for i in v if isinstance(i, dict) and "name" in i]
            else:
                _collect(v, key, acc)
    elif isinstance(node, list):
        for i in node:
            _collect(i, key, acc)


def fetch_dataset(dataset_id, dataset_name):
    s = _session()
    if not dataset_id:   # [UNVERIFIED] search by name
        r = s.get(f"{BASE}/searches/results",
                  params={"name": dataset_name, "pattern": 4, "type": 3})
        print("search:", r.status_code)
        hits = [i for i in (r.json().get("result", []) if r.ok else [])
                if i.get("name") == dataset_name]
        if not hits:
            print("Dataset not found by name. Pass --dataset-id.")
            return None
        dataset_id = hits[0]["id"]
    r = s.get(f"{BASE}/cubes/{dataset_id}")        # [UNVERIFIED] response structure
    print("cube definition:", r.status_code)
    if not r.ok:
        print(r.text[:300])
        return None
    attrs, mets = [], []
    _collect(r.json(), "attributes", attrs)
    _collect(r.json(), "metrics", mets)
    return {"id": dataset_id, "name": dataset_name,
            "attributes": sorted(set(attrs)), "metrics": sorted(set(mets))}


def bind_fields(ws_specs, ds):
    attrs = {n.lower(): n for n in ds["attributes"]}
    mets = {n.lower(): n for n in ds["metrics"]}
    for ws in ws_specs:
        unbound = 0
        for f in ws["dimensions"] + ws["measures"]:
            f["bound_to"], f["note"] = None, ""
            if f["kind"] in ("group", "set", "bin", "calc", "unknown_calc", "unknown_group"):
                f["note"] = f"create in Strategy ({f['kind']})"
            elif f["kind"] == "record_count":
                f["note"] = "create metric: Count of table rows"
            elif f["role"] == "measure":
                m = mets.get(f["name"].lower())
                f["bound_to"] = {"type": "metric", "name": m} if m else None
                if m and f["aggregation"] not in (None, "SUM"):
                    f["note"] = f"dataset metric defaults to SUM; needs {f['aggregation']}"
            else:
                a = attrs.get(f["name"].lower()) or attrs.get(f["caption"].lower())
                f["bound_to"] = {"type": "attribute", "name": a} if a else None
            if not f["bound_to"]:
                unbound += 1
                f["note"] = f["note"] or "not found in dataset"
        ws["unbound_fields"] = unbound
        if unbound and ws["status"] == "READY_TO_BUILD":
            ws["status"] = "NEEDS_OBJECTS"


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("twbx")
    ap.add_argument("--dataset-id")
    ap.add_argument("--dataset-name", default="Tableau_Migrated_Dataset")
    ap.add_argument("--registry", default=str(Path("Tableau-Strategy-Migration-Skill") /
                    "references" / "strategy_visualization_capabilities.json"))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--output")
    a = ap.parse_args()

    root = load_twb(a.twbx)
    cat = build_catalog(root)
    registry = None
    if Path(a.registry).exists():
        registry = {v["id"] for v in json.load(open(a.registry, encoding="utf-8"))["visualizations"]
                    if v.get("availability") != "requires_implementation"}
    ws_specs = [analyze_worksheet(w, cat, registry)
                for w in root.find("worksheets").findall("worksheet")]
    dashboards = parse_dashboards(root, {w["name"] for w in ws_specs})
    dataset = None
    if not a.offline:
        dataset = fetch_dataset(a.dataset_id or os.getenv("MSTR_DATASET_ID"), a.dataset_name)
        if dataset:
            bind_fields(ws_specs, dataset)

    spec = {"source": a.twbx, "dataset": dataset, "worksheets": ws_specs, "dashboards": dashboards}
    out = a.output or str(Path(a.twbx).with_name(Path(a.twbx).stem + "_build_spec.json"))
    json.dump(spec, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    for w in ws_specs:
        print(f"{w['name'].strip():40} -> {str(w['viz']['viz_id']):16} "
              f"[{w['status']}] ({w['viz']['rule']})")
        print("   dims:", [d["caption"] for d in w["dimensions"]],
              "| measures:", [f"{m['aggregation']}({m['caption']})" for m in w["measures"]])
        if w["filters"]:
            print("   filters:", [(f["caption"], f["mode"]) for f in w["filters"]])
    for d in dashboards:
        kinds = Counter(z["kind"] for z in d["zones"])
        print(f"\nDashboard '{d['dashboard']}': {dict(kinds)} skipped={d['skipped_zone_types']}")
    print("\nsaved:", out)


if __name__ == "__main__":
    main()