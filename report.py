#!/usr/bin/env python3
"""
Builds a single HTML report from the CSVs written by permits.py and bids.py.

Usage:
    python3 report.py --leads output/leads --bids output/bids --out output/report.html
"""
import argparse
import csv
import html
import json
import os
from datetime import datetime, timezone

PERMIT_COLUMNS = [
    ("address", "Address"), ("zip", "Zip"), ("permitdescription", "Permit Type"),
    ("typeofwork", "Work"), ("approvedscopeofwork", "Scope"),
    ("contractorname", "Contractor"), ("opa_owner", "Owner"),
    ("permitissuedate", "Issued"),
]
BID_COLUMNS = [
    ("bid_number", "Bid #"), ("title", "Title"), ("department", "Department"),
    ("buyer", "Buyer"), ("bid_opening", "Opens"), ("status", "Status"),
]

CSS = """
body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
       margin: 0; padding: 32px; background: #f7f7f8; color: #1a1a1a; }
h1 { margin-bottom: 4px; }
.meta { color: #666; margin-bottom: 24px; }
h2 { margin-top: 40px; border-bottom: 2px solid #ddd; padding-bottom: 6px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0 28px; }
.card { background: white; border: 1px solid #e0e0e0; border-radius: 8px;
        padding: 14px 18px; min-width: 140px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
.card .n { font-size: 26px; font-weight: 700; }
.card .l { color: #666; font-size: 13px; text-transform: capitalize; }
table { border-collapse: collapse; width: 100%; margin-bottom: 28px; background: white; }
th, td { border: 1px solid #e5e5e5; padding: 6px 10px; font-size: 13px; text-align: left;
         vertical-align: top; }
th { background: #fafafa; position: sticky; top: 0; }
tr:nth-child(even) { background: #fcfcfd; }
details { margin-bottom: 28px; background: white; border: 1px solid #e0e0e0; border-radius: 8px;
          padding: 10px 16px; }
summary { cursor: pointer; font-weight: 600; font-size: 15px; padding: 6px 0; }
.note { background: #fff8e1; border: 1px solid #f0dca0; border-radius: 6px;
        padding: 10px 14px; font-size: 13px; margin: 12px 0 24px; }
.small { color: #888; font-size: 12px; }
</style>
"""


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def table_html(rows, columns, limit=25):
    if not rows:
        return "<p class='small'>No rows.</p>"
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    body = []
    for row in rows[:limit]:
        cells = "".join(f"<td>{html.escape(str(row.get(key, '') or ''))}</td>" for key, _ in columns)
        body.append(f"<tr>{cells}</tr>")
    footer = f"<p class='small'>Showing {min(limit, len(rows))} of {len(rows)} rows — full list in the CSV.</p>" \
        if len(rows) > limit else ""
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>{footer}"


def section(title, csv_dir, columns, summary):
    parts = [f"<h2>{html.escape(title)}</h2>"]
    total = summary.get("total_permits") or summary.get("total_bids") or 0
    by_trade = summary.get("by_trade", {})
    parts.append("<div class='cards'>")
    parts.append(f"<div class='card'><div class='n'>{total}</div><div class='l'>total fetched</div></div>")
    for trade, count in sorted(by_trade.items(), key=lambda kv: -kv[1]):
        parts.append(f"<div class='card'><div class='n'>{count}</div>"
                      f"<div class='l'>{html.escape(trade.replace('_', ' '))}</div></div>")
    parts.append(f"<div class='card'><div class='n'>{summary.get('unclassified', 0)}</div>"
                  f"<div class='l'>unclassified</div></div>")
    parts.append("</div>")

    for trade, count in sorted(by_trade.items(), key=lambda kv: -kv[1]):
        rows = read_csv(os.path.join(csv_dir, f"{trade}.csv"))
        open_attr = " open" if trade == sorted(by_trade.items(), key=lambda kv: -kv[1])[0][0] else ""
        parts.append(
            f"<details{open_attr}><summary>{html.escape(trade.replace('_', ' ').title())} "
            f"({count})</summary>{table_html(rows, columns)}</details>"
        )
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads", default="output/leads")
    ap.add_argument("--bids", default="output/bids")
    ap.add_argument("--out", default="output/report.html")
    args = ap.parse_args()

    leads_summary_path = os.path.join(args.leads, "summary.json")
    bids_summary_path = os.path.join(args.bids, "summary.json")
    leads_summary = json.load(open(leads_summary_path)) if os.path.exists(leads_summary_path) else {}
    bids_summary = json.load(open(bids_summary_path)) if os.path.exists(bids_summary_path) else {}

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    body = ["<!doctype html><html><head><meta charset='utf-8'>",
            "<title>Lead Scan Report</title><style>", CSS, "</head><body>"]
    body.append("<h1>Lead Scan Report</h1>")
    body.append(f"<div class='meta'>Generated {generated}</div>")

    body.append(
        "<div class='note'><strong>How to read this:</strong> each card below is a trade "
        "category with a live count from today's scan. Click a category to see the actual "
        "leads/bids matched, with the source text that triggered the match. Full data is in "
        "the CSVs under <code>output/</code> — this page is just the human-readable view.</div>"
    )

    if leads_summary:
        body.append(section(
            f"Building Permit Leads — Philadelphia (last {leads_summary.get('days', '?')} days)",
            args.leads, PERMIT_COLUMNS, leads_summary))

    if bids_summary:
        body.append(section(
            f"Government Bid Alerts — {bids_summary.get('source', '').upper()}",
            args.bids, BID_COLUMNS, bids_summary))

    body.append("</body></html>")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(body))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
