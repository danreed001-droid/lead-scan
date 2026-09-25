# lead-scan

Two lead-generation pipelines built on public data:

1. **`permits.py`** — pulls live building/zoning permits from Philadelphia's
   open data API (Carto SQL, no key needed), classifies each by trade
   (roofing, HVAC, solar, demolition, new construction, kitchen/bath,
   pools/decks/fences, signs, commercial fit-out), and writes one CSV per
   trade under `output/leads/`. This is the weekly lead-list product.

2. **`bids.py`** — scrapes open government bid listings from the Ion Wave
   "BSO" procurement platform (confirmed working against NJSTART; the same
   parser works against PHLContracts and any other city/state running the
   same platform — just pass `--base-url`), classifies by trade (paving,
   HVAC, electrical, plumbing, landscaping, towing, janitorial, IT,
   printing, general construction), and writes one CSV per trade under
   `output/bids/`.

3. **`report.py`** — reads the CSVs from both and builds a single
   `output/report.html` you can open in a browser: summary counts per
   trade plus an expandable table of the actual leads/bids matched.

## Usage

```bash
python3 permits.py --days 14 --out output/leads
python3 bids.py --source njstart --out output/bids
python3 report.py --leads output/leads --bids output/bids --out output/report.html
```

Then open `output/report.html`.

## Known limitation

Philadelphia's own bid platform, PHLContracts, runs the same Ion Wave "BSO"
software as NJSTART (same URL layout: `/bso/view/search/external/advancedSearchBid.xhtml?openBids=true`),
so `bids.py --base-url https://www.phlcontracts.com --source phlcontracts`
should work unchanged — it just needs to be run from a network that can
reach `phlcontracts.com` (this dev sandbox's egress policy blocks that
specific domain; NJSTART is unaffected and was scanned live).
