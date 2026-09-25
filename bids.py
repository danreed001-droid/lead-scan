#!/usr/bin/env python3
"""
Government bid alert scraper (Ion Wave "BSO" procurement platform).

NJSTART (state of New Jersey) runs on this platform and is publicly
reachable with a single unauthenticated GET — no login, no pagination
tricks needed for the open-bids list. Philadelphia's PHLContracts runs the
same underlying platform (same /bso/ URL layout), so the same parser works
there too; point --base-url at it from a machine that can reach it.

Usage:
    python3 bids.py --source njstart --days 21
    python3 bids.py --base-url https://www.phlcontracts.com --source phlcontracts
"""
import argparse
import csv
import html
import json
import os
import re
import urllib.request
from datetime import datetime

SOURCES = {
    "njstart": "https://www.njstart.gov",
    "phlcontracts": "https://www.phlcontracts.com",
}

OPEN_BIDS_PATH = "/bso/view/search/external/advancedSearchBid.xhtml?openBids=true"

TRADE_RULES = [
    ("paving", [r"\bpaving\b", r"\basphalt\b", r"\bmilling\b", r"\bstriping\b", r"\broad resurfac",
                r"\bpavement\b", r"\bslurry seal\b", r"\bmicrosurfac"]),
    ("hvac", [r"\bhvac\b", r"\bboiler\b", r"\bfurnace\b", r"\bair condition", r"\bchiller\b"]),
    ("electrical", [r"\belectrical\b", r"\belectrician\b", r"\bwiring\b", r"\blighting\b"]),
    ("plumbing", [r"\bplumbing\b", r"\bplumber\b", r"\bwater main\b", r"\bsewer\b"]),
    ("landscaping", [r"\blandscap", r"\bmowing\b", r"\btree removal\b", r"\bturf\b"]),
    ("towing", [r"\btowing\b", r"\bvehicle removal\b"]),
    ("janitorial", [r"\bjanitorial\b", r"\bcustodial\b", r"\bcleaning services\b"]),
    ("it", [r"\bit services\b", r"\bsoftware\b", r"\bnetwork\b", r"\bcybersecurity\b", r"\bcomputer\b"]),
    ("printing", [r"\bprinting\b", r"\bprinter\b", r"\bprint services\b"]),
    ("general_construction", [r"\bconstruction\b", r"\brenovation\b", r"\bgeneral contractor\b",
                               r"\bbuilding improvements\b"]),
]


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lead-scan/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def strip_tags(cell_html):
    text = re.sub(r"<[^>]+>", " ", cell_html)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def parse_open_bids(page_html, base_url):
    bids = []
    for row_html in re.findall(r'<tr data-ri="\d+"[^>]*>(.*?)</tr>', page_html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        if len(cells) < 8:
            continue
        link_match = re.search(r'href="([^"]+)"', cells[0])
        bid = {
            "bid_number": strip_tags(cells[0]),
            "detail_url": (base_url + html.unescape(link_match.group(1)))
                          if link_match else "",
            "department": strip_tags(cells[2]) if len(cells) > 2 else "",
            "buyer": strip_tags(cells[5]) if len(cells) > 5 else "",
            "title": strip_tags(cells[6]) if len(cells) > 6 else "",
            "bid_opening": strip_tags(cells[7]) if len(cells) > 7 else "",
            "status": strip_tags(cells[10]) if len(cells) > 10 else "",
        }
        if bid["bid_number"]:
            bids.append(bid)
    return bids


def classify(bid):
    text = bid.get("title", "").lower()
    matches = [trade for trade, patterns in TRADE_RULES
               if any(re.search(p, text) for p in patterns)]
    return matches


def write_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=SOURCES.keys(), default="njstart")
    ap.add_argument("--base-url", default=None,
                     help="Override base URL (e.g. to point at phlcontracts.com)")
    ap.add_argument("--out", default="output/bids")
    args = ap.parse_args()

    base_url = args.base_url or SOURCES[args.source]
    url = base_url + OPEN_BIDS_PATH
    print(f"Fetching open bids from {url} ...")
    page = fetch_html(url)
    bids = parse_open_bids(page, base_url)
    print(f"Parsed {len(bids)} open bids.")

    by_trade = {}
    unclassified = []
    for bid in bids:
        trades = classify(bid)
        bid["matched_trades"] = ";".join(trades)
        if not trades:
            unclassified.append(bid)
        for trade in trades:
            by_trade.setdefault(trade, []).append(bid)

    fieldnames = ["bid_number", "title", "department", "buyer", "bid_opening",
                  "status", "matched_trades", "detail_url"]

    summary = {"source": args.source, "total_bids": len(bids), "by_trade": {}}
    for trade, rows in sorted(by_trade.items(), key=lambda kv: -len(kv[1])):
        path = os.path.join(args.out, f"{trade}.csv")
        write_csv(path, rows, fieldnames)
        summary["by_trade"][trade] = len(rows)
        print(f"  {trade:20s} {len(rows):4d} bids -> {path}")

    write_csv(os.path.join(args.out, "unclassified.csv"), unclassified, fieldnames)
    summary["unclassified"] = len(unclassified)
    print(f"  {'unclassified':20s} {len(unclassified):4d} rows -> {args.out}/unclassified.csv")

    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    main()
