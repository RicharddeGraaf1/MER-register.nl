"""load_events.py — kanaal A: MER-proces-events uit KOOP SRU → tabel `event`.

Nationaal, titel-treffers op milieueffectrapport(age). Idempotent (upsert op
koop_id), incrementeel via --since. SRU is de open harvest-endpoint van het
publicatiestelsel; beleefd maar niet overdreven traag (0,5s/req).

    python load_events.py [--since YYYY-MM-DD] [--max N]
"""
import argparse
import re
import urllib.parse

import lib

SRU = "https://repository.overheid.nl/sru"
BASE_QUERY = 'dt.title any "milieueffectrapport milieueffectrapportage"'

EVENT_RULES = [
    ("mer-beoordeling: geen MER nodig", r"geen milieueffectrapport|niet doorlopen"),
    ("voornemen/NRD",                   r"voornemen|notitie reikwijdte|reikwijdte en detailniveau|\bnrd\b"),
    ("terinzage MER",                   r"terinzage|ter inzage|tervisie|tervisielegging|ontwerp"),
    ("vaststelling met MER",            r"vaststell|vastgesteld|aanvaarden van de conclusies"),
    ("mer-beoordeling",                 r"beoordeling milieueffect|m\.e\.r\.?-?plicht|mer-beoordeling|aanmeldnotitie"),
]
INSTRUMENT_RULES = [
    ("omgevingsvergunning", r"omgevingsvergunning"),
    ("projectbesluit",      r"projectbesluit"),
    ("omgevingsplan",       r"omgevingsplan"),
    ("bestemmingsplan",     r"bestemmingsplan|tracébesluit|structuurvisie"),
    ("omgevingsvisie",      r"omgevingsvisie"),
    ("programma",           r"programma|plan-?mer"),
]


def classify(titel, rules, default):
    low = (titel or "").lower()
    for label, pat in rules:
        if re.search(pat, low):
            return label
    return default


def sru(query, start, batch):
    p = urllib.parse.urlencode({"operation": "searchRetrieve", "version": "2.0",
                                "maximumRecords": batch, "startRecord": start,
                                "query": query + " sortBy dt.date/sort.descending"})
    return lib.http_get(f"{SRU}?{p}", base_delay=0.5)


def parse(xml):
    for b in re.findall(r"<sru:recordData>.*?</sru:recordData>", xml, re.S):
        f = lambda t: (re.search(rf"<{t}[^>]*>([^<]+)</{t}>", b) or [None, None])[1]
        titel = f("dcterms:title") or ""
        yield {
            "koop_id": f("dcterms:identifier"), "titel": titel,
            "datum_publicatie": f("dcterms:date"),
            "publicatieblad": f("overheidwetgeving:publicatienaam"),
            "bevoegd_gezag_naam": f("dcterms:creator"),
            "subject_taxonomie": f("dcterms:subject"),
            "url": (re.search(r"<gzd:preferredUrl>([^<]+)<", b) or [None, None])[1],
            "event_type": classify(titel, EVENT_RULES, "mer-beoordeling"),
            "instrument": classify(titel, INSTRUMENT_RULES, "overig"),
        }


def upsert(con, rows):
    con.executemany(
        """INSERT INTO event(koop_id,titel,datum_publicatie,publicatieblad,bevoegd_gezag_naam,
                             subject_taxonomie,url,event_type,instrument)
           VALUES(:koop_id,:titel,:datum_publicatie,:publicatieblad,:bevoegd_gezag_naam,
                  :subject_taxonomie,:url,:event_type,:instrument)
           ON CONFLICT(koop_id) DO UPDATE SET
             titel=excluded.titel, datum_publicatie=excluded.datum_publicatie,
             publicatieblad=excluded.publicatieblad, bevoegd_gezag_naam=excluded.bevoegd_gezag_naam,
             event_type=excluded.event_type, instrument=excluded.instrument""",
        [r for r in rows if r["koop_id"]])
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--max", type=int, default=10000, dest="maximum")
    args = ap.parse_args()

    con = lib.connect()
    lib.init_schema(con)

    query = BASE_QUERY + (f' and dt.date >= "{args.since}"' if args.since else "")
    total = int(re.search(r"<sru:numberOfRecords>(\d+)", sru(query, 1, 0)).group(1))
    target = min(args.maximum, total)
    print(f"Kanaal A (KOOP): {total} MER-titel-events beschikbaar; laad max {target}")

    got, start = 0, 1
    try:
        while got < target:
            batch = min(50, target - got)
            rows = list(parse(sru(query, start, batch)))
            if not rows:
                break
            upsert(con, rows)
            got += len(rows)
            start += len(rows)
            if got % 250 < 50:
                print(f"  … {got}/{target}")
    except lib.RateLimited as e:
        print(f"GESTOPT door rate-limiting: {e}\n  Hervat later; {got} events geladen.")

    n = con.execute("SELECT COUNT(*) FROM event").fetchone()[0]
    lib.set_state(con, "event", f"laatste_start={start}")
    print(f"Klaar. Tabel `event` bevat nu {n} rijen.")
    con.close()


if __name__ == "__main__":
    main()
