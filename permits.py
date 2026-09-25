#!/usr/bin/env python3
"""
Philadelphia building/zoning permit lead scanner.

Pulls recent permits from the City of Philadelphia's open data API (Carto SQL,
no key required), classifies each permit by contractor trade, and writes one
CSV per trade to output/leads/ — the weekly lead list product.

Usage:
    python3 permits.py --days 7
    python3 permits.py --days 30 --out output/leads
"""
import argparse
import csv
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

CARTO_URL = "https://phl.carto.com/api/v2/sql"

FIELDS = [
    "permitnumber", "permittype", "permitdescription", "typeofwork",
    "approvedscopeofwork", "status", "commercialorresidential",
    "address", "zip", "council_district",
    "contractorname", "contractoraddress1", "contractorcity",
    "contractorstate", "contractorzip",
    "opa_owner", "permitissuedate",
]

# Order matters: more specific trades are checked before general ones.
TRADE_RULES = [
    ("solar", [r"\bsolar\b", r"\bphotovoltaic\b", r"\bpv system\b"]),
    ("roofing", [r"\broof(?!.*\bdeck)", r"\bre-?roof", r"\bshingl"]),
    ("hvac", [r"\bhvac\b", r"\bfurnace\b", r"\bboiler\b", r"\bair condition",
              r"\bheat pump\b", r"\bmini-?split\b", r"\bduct"]),
    ("pool_deck_fence", [r"\bpool\b", r"\bdeck\b", r"\bfence\b", r"\bpatio\b"]),
    ("demolition", [r"\bdemoli", r"\bdemo\b", r"\braze\b"]),
    ("kitchen_bath", [r"\bkitchen\b", r"\bbathroom\b", r"\bbath\b"]),
    ("new_construction", [r"\bnew construction\b", r"\bnew dwelling\b",
                           r"\berect\b", r"\bnew building\b"]),
    ("signs", [r"\bsign\b", r"\bsignage\b", r"\bbanner\b"]),
    ("commercial_fitout", [r"\bfit-?out\b", r"\btenant improvement\b",
                            r"\bchange of use\b", r"\bcommercial\b"]),
]

# Explicit exclusions to kill false positives (checked per-trade).
EXCLUSIONS = {
    "roofing": [r"\bon roof\b", r"\bat roof\b", r"\broof deck\b", r"\brooftop unit\b",
                r"\bsolar\b", r"\bphotovoltaic\b"],
}


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lead-scan/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_permits(days, limit=5000):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    query = (
        f"SELECT {', '.join(FIELDS)} FROM permits "
        f"WHERE permitissuedate >= '{since}' "
        f"ORDER BY permitissuedate DESC LIMIT {limit}"
    )
    url = f"{CARTO_URL}?q={urllib.parse.quote(query)}"
    data = http_get_json(url)
    return data.get("rows", [])


def classify(row):
    text = " ".join(str(row.get(f) or "") for f in
                     ("permitdescription", "typeofwork", "approvedscopeofwork")).lower()
    matches = []
    for trade, patterns in TRADE_RULES:
        if any(re.search(p, text) for p in patterns):
            excluded = any(re.search(p, text) for p in EXCLUSIONS.get(trade, []))
            if not excluded:
                matches.append(trade)
    return matches


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = FIELDS + ["matched_trades"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="output/leads")
    ap.add_argument("--city", default="philadelphia")
    args = ap.parse_args()

    print(f"Fetching Philadelphia permits from the last {args.days} day(s)...")
    permits = fetch_permits(args.days)
    print(f"Fetched {len(permits)} permits.")

    by_trade = {}
    unclassified = []
    for row in permits:
        trades = classify(row)
        row["matched_trades"] = ";".join(trades)
        if not trades:
            unclassified.append(row)
            continue
        for trade in trades:
            by_trade.setdefault(trade, []).append(row)

    summary = {"days": args.days, "total_permits": len(permits), "by_trade": {}}
    for trade, rows in sorted(by_trade.items(), key=lambda kv: -len(kv[1])):
        path = os.path.join(args.out, f"{trade}.csv")
        write_csv(path, rows)
        summary["by_trade"][trade] = len(rows)
        print(f"  {trade:20s} {len(rows):4d} leads -> {path}")

    write_csv(os.path.join(args.out, "unclassified.csv"), unclassified)
    summary["unclassified"] = len(unclassified)
    print(f"  {'unclassified':20s} {len(unclassified):4d} rows -> {args.out}/unclassified.csv")

    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    main()
