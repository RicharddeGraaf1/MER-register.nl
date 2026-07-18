"""PoC-harvester 1: MER-events uit officielebekendmakingen.nl (KOOP SRU-API).

Oogst kennisgevingen/besluiten waarin een milieueffectrapport(age) figureert en
classificeert ze naar event-type. Stdlib-only.

Gebruik:
    python harvest_sru.py [--since YYYY-MM-DD] [--max N]
Output: data/sru_events.json + console-statistiek.
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

SRU = "https://repository.overheid.nl/sru"
UA = {"User-Agent": "mer-register-poc/0.1 (contact: richard.de.graaf@conteo-consulting.nl)"}

# Titel-query: vangt kennisgevingen die over een MER gaan (niet elke terloopse vermelding)
BASE_QUERY = 'dt.title any "milieueffectrapport milieueffectrapportage"'

EVENT_RULES = [
    ("mer-beoordeling:geen-mer-nodig", r"geen milieueffectrapport(age)? (hoeft|behoeft|nodig|opgesteld)|niet.{0,30}milieueffectrapport.{0,20}(nodig|opgesteld)"),
    ("mer-beoordeling",                r"m\.?e\.?r\.?-beoordeling|aanmeldnotitie|mer-beoordelingsbesluit"),
    ("voornemen/NRD",                  r"voornemen|notitie reikwijdte|reikwijdte en detailniveau|NRD|participatie"),
    ("terinzagelegging-mer",           r"ter inzage|terinzage|zienswijze"),
    ("vaststelling-met-mer",           r"vaststelling|vastgesteld|verleende|verleend"),
]

INSTRUMENT_RULES = [
    ("omgevingsvergunning", r"omgevingsvergunning"),
    ("omgevingsplan",       r"omgevingsplan"),
    ("projectbesluit",      r"projectbesluit"),
    ("bestemmingsplan",     r"bestemmingsplan"),
    ("omgevingsvisie",      r"omgevingsvisie"),
    ("programma",           r"programma"),
]


def classify(title: str, rules) -> str:
    low = title.lower()
    for label, pat in rules:
        if re.search(pat, low):
            return label
    return "overig"


def fetch(query: str, start: int, batch: int) -> str:
    params = urllib.parse.urlencode({
        "operation": "searchRetrieve",
        "version": "2.0",
        "maximumRecords": batch,
        "startRecord": start,
        "query": query + " sortBy dt.date/sort.descending",
    })
    req = urllib.request.Request(f"{SRU}?{params}", headers=UA)
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def parse_records(xml: str):
    for blob in re.findall(r"<sru:recordData>.*?</sru:recordData>", xml, re.S):
        def first(tag):
            m = re.search(rf"<{tag}[^>]*>([^<]+)</{tag}>", blob)
            return m.group(1).strip() if m else None
        title = first("dcterms:title") or ""
        yield {
            "id": first("dcterms:identifier"),
            "titel": title,
            "datum": first("dcterms:date"),
            "bevoegd_gezag": first("dcterms:creator"),
            "publicatie": first("overheidwetgeving:publicatienaam"),
            "url": (re.search(r"<gzd:preferredUrl>([^<]+)<", blob) or [None, None])[1],
            "event_type": classify(title, EVENT_RULES),
            "instrument": classify(title, INSTRUMENT_RULES),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="alleen records vanaf deze datum (YYYY-MM-DD)")
    ap.add_argument("--max", type=int, default=100, dest="maximum")
    args = ap.parse_args()

    query = BASE_QUERY
    if args.since:
        query += f' and dt.date >= "{args.since}"'

    total_xml = fetch(query, 1, 0)
    total = int(re.search(r"<sru:numberOfRecords>(\d+)", total_xml).group(1))
    print(f"Query: {query}\nTotaal beschikbaar: {total} records; harvest van max {args.maximum}\n")

    records, start = [], 1
    while len(records) < min(args.maximum, total):
        batch = min(50, args.maximum - len(records))
        xml = fetch(query, start, batch)
        got = list(parse_records(xml))
        if not got:
            break
        records.extend(got)
        start += len(got)
        time.sleep(0.3)

    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    (out / "sru_events.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    def tally(key):
        counts = {}
        for r in records:
            counts[r[key]] = counts.get(r[key], 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    print(f"Geharvest: {len(records)} events -> data/sru_events.json")
    print("Per event-type:", json.dumps(tally("event_type"), ensure_ascii=False, indent=1))
    print("Per instrument:", json.dumps(tally("instrument"), ensure_ascii=False, indent=1))
    print("Per publicatieblad:", json.dumps(tally("publicatie"), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
