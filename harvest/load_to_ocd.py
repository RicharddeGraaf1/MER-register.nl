"""load_to_ocd.py — laad de harvest-store (SQLite mer.db) naar OCD-Postgres, schema `mer`.

Idempotent (ON CONFLICT upsert). Past eerst ../sql/mer-schema.sql toe. Provincie/
lat/lon komen uit de geocache (join op bevoegd_gezag). bronhouder_id blijft NULL
(resolutie tegen core.bronhouder is een latere stap).

Verbinding via env-var MER_PROD_URL (nooit in de repo/transcript):
    MER_PROD_URL="postgresql://...:...@host:port/db" python load_to_ocd.py
"""
import os
import sqlite3
from pathlib import Path

import psycopg

from export_mer_data import instrument_from_title, majority_instrument

HERE = Path(__file__).parent
SQLITE = HERE / "data" / "mer.db"
DDL = HERE.parent / "sql" / "mer-schema.sql"


def rows(sq, q):
    cur = sq.execute(q)
    cols = [c[0] for c in cur.description]
    return cols, cur.fetchall()


def main():
    url = os.environ["MER_PROD_URL"]
    sq = sqlite3.connect(SQLITE)

    with psycopg.connect(url, connect_timeout=30) as pg:
        cur = pg.cursor()
        print("Schema toepassen…")
        cur.execute(DDL.read_text(encoding="utf-8"))
        cur.execute("ALTER TABLE mer.project ADD COLUMN IF NOT EXISTS instrument text")
        pg.commit()

        # instrument per project (meerderheid gekoppelde events, anders projecttitel)
        instr = {}
        for slug, titel in sq.execute("SELECT slug,titel FROM project").fetchall():
            evs = [{"instrument": r[0]} for r in sq.execute(
                """SELECT e.instrument FROM project_event_link l JOIN event e ON e.koop_id=l.koop_id
                   WHERE l.project_slug=?""", (slug,)).fetchall()]
            instr[slug] = majority_instrument(evs, titel)

        # --- event ---
        _, ev = rows(sq, """SELECT koop_id,titel,datum_publicatie,publicatieblad,bevoegd_gezag_naam,
                                   event_type,instrument,subject_taxonomie,url FROM event""")
        cur.executemany(
            """INSERT INTO mer.event(koop_id,titel,datum_publicatie,publicatieblad,bevoegd_gezag_naam,
                                     event_type,instrument,subject_taxonomie,url)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(koop_id) DO UPDATE SET titel=EXCLUDED.titel,event_type=EXCLUDED.event_type,
                     instrument=EXCLUDED.instrument,datum_publicatie=EXCLUDED.datum_publicatie""", ev)
        print(f"  mer.event: {len(ev)}")

        # --- project (met provincie/lat/lon uit geocache) ---
        _, pr = rows(sq, """SELECT p.slug,p.project_nr,p.titel,p.bevoegd_gezag,p.initiatiefnemer,
                                   p.start_advisering,g.provincie,g.lat,g.lon,p.url,p.lastmod
                            FROM project p LEFT JOIN geocache g ON g.naam=trim(p.bevoegd_gezag)""")
        # start_advisering/lastmod zijn vrije tekst → NULL laten waar niet-parsebaar
        def clean(r):
            r = list(r)
            r[5] = None            # start_advisering: Nederlandse tekst, niet als date laden
            r[10] = None           # lastmod: sitemap-timestamp, optioneel
            return r + [instr.get(r[0])]   # instrument achteraan
        cur.executemany(
            """INSERT INTO mer.project(slug,project_nr,titel,bevoegd_gezag,initiatiefnemer,
                                       start_advisering,provincie,lat,lon,url,lastmod,instrument)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(slug) DO UPDATE SET titel=EXCLUDED.titel,bevoegd_gezag=EXCLUDED.bevoegd_gezag,
                     initiatiefnemer=EXCLUDED.initiatiefnemer,provincie=EXCLUDED.provincie,
                     lat=EXCLUDED.lat,lon=EXCLUDED.lon,instrument=EXCLUDED.instrument""", [clean(r) for r in pr])
        print(f"  mer.project: {len(pr)}")

        # --- document ---
        _, dc = rows(sq, "SELECT project_slug,soort,bestandsnaam,url FROM document")
        cur.executemany(
            """INSERT INTO mer.document(project_slug,soort,bestandsnaam,url) VALUES(%s,%s,%s,%s)
               ON CONFLICT(project_slug,bestandsnaam) DO NOTHING""", dc)
        print(f"  mer.document: {len(dc)}")

        # --- link ---
        _, lk = rows(sq, "SELECT project_slug,koop_id,match_methode,zekerheid FROM project_event_link")
        cur.executemany(
            """INSERT INTO mer.project_event_link(project_slug,koop_id,match_methode,zekerheid)
               VALUES(%s,%s,%s,%s) ON CONFLICT(project_slug,koop_id) DO UPDATE SET zekerheid=EXCLUDED.zekerheid""", lk)
        print(f"  mer.project_event_link: {len(lk)}")

        pg.commit()
        for t in ("event", "project", "document", "project_event_link"):
            cur.execute(f"SELECT COUNT(*) FROM mer.{t}")
            print(f"  prod mer.{t} = {cur.fetchone()[0]}")
    sq.close()
    print("Klaar.")


if __name__ == "__main__":
    main()
