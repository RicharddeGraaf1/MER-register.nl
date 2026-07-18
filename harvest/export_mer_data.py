"""export_mer_data.py — bouw trajecten uit de harvest-store → web/mer-data.js
in exact de vorm die het Claude-ontwerp verwacht.

Project-centrisch: één traject per Commissie-project, verrijkt met zijn
gekoppelde KOOP-events (kanaal A) en documenten (kanaal B). Coördinaat +
provincie via PDOK Locatieserver (gecachet in tabel `geocache`).

Losse MER-beoordelingsbesluiten zonder Commissie-dossier worden (nog) niet als
apart traject getoond — dat vraagt event-clustering; zie docs/entity-koppeling.md.

    python export_mer_data.py [--limit N]
"""
import argparse
import json
import re
import urllib.parse

import lib

PDOK = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
NL_CENTROID = [52.15, 5.38]

PROV_CENTROID = {
    "Groningen": [53.22, 6.57], "Fryslân": [53.10, 5.79], "Drenthe": [52.86, 6.62],
    "Overijssel": [52.44, 6.44], "Flevoland": [52.53, 5.60], "Gelderland": [52.06, 5.90],
    "Utrecht": [52.08, 5.16], "Noord-Holland": [52.60, 4.85], "Zuid-Holland": [51.99, 4.47],
    "Zeeland": [51.49, 3.85], "Noord-Brabant": [51.56, 5.10], "Limburg": [51.21, 5.94],
}


def geocode(con, bg):
    """(lat, lon, provincie) voor een bevoegd-gezag-naam. Gecachet; PDOK Locatieserver."""
    if not bg:
        return (*NL_CENTROID, None)
    key = bg.strip()
    row = con.execute("SELECT lat,lon,provincie FROM geocache WHERE naam=?", (key,)).fetchone()
    if row:
        return (row[0], row[1], row[2])

    naam = re.sub(r"^\s*(gemeente|provincie)\s+", "", bg, flags=re.I).split(",")[0].strip()
    is_prov = bool(re.match(r"\s*provincie", bg, re.I)) or naam in PROV_CENTROID
    lat = lon = prov = None
    if "ministerie" not in bg.lower() and "rijkswaterstaat" not in bg.lower():
        typ = "provincie" if is_prov else "gemeente"
        q = urllib.parse.urlencode({"q": naam, "fq": f"type:{typ}",
                                    "fl": "provincienaam,centroide_ll", "rows": 1})
        try:
            data = json.loads(lib.http_get(f"{PDOK}?{q}", base_delay=0.4))
            docs = data.get("response", {}).get("docs", [])
            if docs:
                prov = docs[0].get("provincienaam")
                m = re.search(r"POINT\(([\d.]+)\s+([\d.]+)\)", docs[0].get("centroide_ll", ""))
                if m:
                    lon, lat = float(m.group(1)), float(m.group(2))
        except Exception:
            pass
    if lat is None:  # fallback: provincie-centroïde of NL
        c = PROV_CENTROID.get(naam if is_prov else prov, NL_CENTROID)
        lat, lon = c
        prov = prov or (naam if is_prov else None)
    con.execute("INSERT OR REPLACE INTO geocache(naam,lat,lon,provincie,bron) VALUES(?,?,?,?,?)",
                (key, lat, lon, prov, "pdok" if prov else "fallback"))
    con.commit()
    return (lat, lon, prov)


INSTRUMENT_RULES = [
    ("omgevingsvergunning", r"omgevingsvergunning|vergunning"),
    ("projectbesluit",      r"projectbesluit"),
    ("omgevingsvisie",      r"omgevingsvisie"),
    ("omgevingsplan",       r"omgevingsplan"),
    ("bestemmingsplan",     r"bestemmingsplan|structuurvisie|structuurplan|tracébesluit|inpassingsplan|streekplan"),
    ("programma",           r"programma|plan-?mer|beleidsplan|actieprogramma|structuurvisie"),
]


def instrument_from_title(titel):
    low = (titel or "").lower()
    for label, pat in INSTRUMENT_RULES:
        if re.search(pat, low):
            return label
    return "overig"


def majority_instrument(events, titel):
    counts = {}
    for e in events:
        if e["instrument"] and e["instrument"] != "overig":
            counts[e["instrument"]] = counts.get(e["instrument"], 0) + 1
    if counts:
        return max(counts, key=counts.get)
    return instrument_from_title(titel)   # fallback: uit de projecttitel (voor document-only trajecten)


EVENT_LABEL = {"mer-beoordeling: geen MER nodig": "mer-beoordeling: geen MER nodig"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    args = ap.parse_args()
    con = lib.connect()
    try:                                   # migratie voor bestaande DB's zonder provincie-kolom
        con.execute("ALTER TABLE geocache ADD COLUMN provincie TEXT")
    except Exception:
        pass
    con.execute("DELETE FROM geocache WHERE provincie IS NULL AND bron='pdok'")  # foute cache-rijen opnieuw

    projects = con.execute("SELECT slug,titel,bevoegd_gezag,initiatiefnemer FROM project").fetchall()
    trajecten = []
    for slug, titel, bg, init in projects:
        events = [dict(zip(("datum", "type", "blad", "link", "instrument"), r)) for r in con.execute(
            """SELECT e.datum_publicatie,e.event_type,e.publicatieblad,e.url,e.instrument
               FROM project_event_link l JOIN event e ON e.koop_id=l.koop_id
               WHERE l.project_slug=? ORDER BY e.datum_publicatie""", (slug,)).fetchall()]
        docs = [dict(zip(("soort", "titel", "link"), r)) for r in con.execute(
            """SELECT soort, soort||' — '||replace(bestandsnaam,'.pdf',''), url FROM document
               WHERE project_slug=? AND soort<>'overig' ORDER BY
                 CASE soort WHEN 'MER' THEN 0 WHEN 'startnotitie' THEN 1 WHEN 'richtlijnen' THEN 2
                            WHEN 'toetsingsadvies' THEN 3 ELSE 4 END""", (slug,)).fetchall()]
        if not events and not docs:
            continue                       # leeg project: overslaan
        lat, lon, prov = geocode(con, bg)
        trajecten.append({
            "id": slug, "titel": titel or slug,
            "bevoegdGezag": bg or "onbekend",
            "initiatiefnemer": init or (bg or "onbekend"),
            "instrument": majority_instrument(events, titel),
            "provincie": prov,
            "coord": [round(lat, 4), round(lon, 4)],
            "events": [{"datum": e["datum"], "type": e["type"], "blad": e["blad"], "link": e["link"]} for e in events],
            "documenten": docs,
        })
        if len(trajecten) >= args.limit:
            break

    trajecten.sort(key=lambda t: (t["events"][-1]["datum"] if t["events"] else "0000"), reverse=True)
    write_mer_data(trajecten)
    ne = sum(len(t["events"]) for t in trajecten)
    nd = sum(len(t["documenten"]) for t in trajecten)
    print(f"Export: {len(trajecten)} trajecten, {ne} events, {nd} documenten -> web/mer-data.js")


def write_mer_data(trajecten):
    body = json.dumps(trajecten, ensure_ascii=False, indent=1)
    js = f"""// mer-data.js — ECHTE data uit de nationale harvest (harvest/mer.db),
// gegenereerd door harvest/export_mer_data.py. Kanaal A = KOOP, kanaal B = Commissie m.e.r.

export const EVENT_TYPES = ['voornemen/NRD','mer-beoordeling','mer-beoordeling: geen MER nodig','terinzage MER','vaststelling met MER'];
export const INSTRUMENTEN = ['projectbesluit','omgevingsplan','omgevingsvergunning','bestemmingsplan','omgevingsvisie','programma'];
export const DOC_SOORTEN = ['MER','MER-bijlage','startnotitie','richtlijnen','toetsingsadvies'];
export const PROVINCIES = ['Groningen','Fryslân','Drenthe','Overijssel','Flevoland','Gelderland','Utrecht','Noord-Holland','Zuid-Holland','Zeeland','Noord-Brabant','Limburg'];

export const trajecten = {body};
"""
    (lib.HERE.parent / "web" / "mer-data.js").write_text(js, encoding="utf-8")


if __name__ == "__main__":
    main()
