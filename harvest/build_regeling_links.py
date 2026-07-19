"""build_regeling_links.py — koppel MER-trajecten aan het onderliggende
omgevingsdocument (regeling) in OCD → tabel mer.project_regeling.

Zacht, want MER-events (KOOP) en OCD-regelingen (AKN) delen geen harde sleutel.
Strategie per instrument:
  - omgevingsplan/omgevingsvisie/omgevingsverordening/waterschapsverordening →
    p2p.regeling op bronhouder (gedisambigueerd op BESTUURSLAAG) + documenttype (1:1).
  - programma/projectbesluit → idem + verplichte TITEL-token-overlap (n per bronhouder).
  - bestemmingsplan → wro.ruimtelijk_instrument op bronhouder + naam-token-overlap.

    MER_PROD_URL="postgresql://..." python build_regeling_links.py
"""
import os
import re

import psycopg
from build_links import norm_bg, tokens   # zelfde normalisatie/stopwoorden

DT_1OP1 = {"omgevingsplan": "Omgevingsplan", "omgevingsvisie": "Omgevingsvisie"}
DT_TITEL = {"programma": "Programma", "projectbesluit": "Projectbesluit"}
THRESHOLD = 0.5


def laag_of(bg):
    b = (bg or "").lower()
    if "provincie" in b:
        return "provincie"
    if "waterschap" in b or "hoogheemraadschap" in b:
        return "waterschap"
    if "ministerie" in b or "rijkswaterstaat" in b or "minister" in b:
        return "rijk"
    if "gemeente" in b:
        return "gemeente"
    return None


def distinct_tokens(titel, bg):
    bg_toks = set(re.findall(r"[a-zà-ÿ0-9]{3,}", (bg or "").lower())) | set(norm_bg(bg).split())
    return tokens(titel) - bg_toks


def containment(ptoks, target):
    if not ptoks:
        return 0.0
    ttoks = tokens(target)
    return len(ptoks & ttoks) / len(ptoks)


def main():
    with psycopg.connect(os.environ["MER_PROD_URL"], connect_timeout=30) as pg:
        cur = pg.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS mer.project_regeling (
            project_slug text NOT NULL REFERENCES mer.project(slug) ON DELETE CASCADE,
            doel_type text NOT NULL, doel_id text NOT NULL, opschrift text,
            documenttype text, methode text, zekerheid numeric(3,2),
            datum_ingest timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (project_slug, doel_id))""")
        cur.execute("DELETE FROM mer.project_regeling")

        # index core.bronhouder: norm(naam) -> {laag: code}
        cur.execute("SELECT overheidscode,naam,bestuurslaag FROM core.bronhouder")
        bh = {}
        for code, naam, laag in cur.fetchall():
            bh.setdefault(norm_bg(naam), {})[laag] = code

        def resolve(bg):
            key = norm_bg(bg)
            opties = bh.get(key)
            if not opties:
                return None
            laag = laag_of(bg)
            if laag and laag in opties:
                return opties[laag]
            if len(opties) == 1:
                return next(iter(opties.values()))
            return None   # ambigu en geen laag-hint → niet koppelen

        # p2p.regeling per bronhouder
        cur.execute("SELECT bronhouder,documenttype,frbr_work,opschrift,citeertitel FROM p2p.regeling WHERE NOT inactief")
        reg = {}
        for code, dt, work, ops, cit in cur.fetchall():
            reg.setdefault((code, dt), []).append((work, ops or cit or ""))

        # wro-instrumenten per bronhouder (vastgesteld)
        cur.execute("SELECT bronhouder,idn,naam FROM wro.ruimtelijk_instrument WHERE planstatus='vastgesteld'")
        wro = {}
        for code, idn, naam in cur.fetchall():
            wro.setdefault(code, []).append((idn, naam or ""))

        cur.execute("SELECT slug,titel,bevoegd_gezag,instrument FROM mer.project")
        projects = cur.fetchall()

        links, tally = [], {}
        for slug, titel, bg, instr in projects:
            code = resolve(bg)
            if not code:
                continue
            if instr in DT_1OP1:
                cands = reg.get((code, DT_1OP1[instr]), [])
                if cands:
                    work, ops = cands[0]
                    links.append((slug, "ow", work, ops, DT_1OP1[instr], "bronhouder+documenttype", 0.90))
                    tally["ow-1op1"] = tally.get("ow-1op1", 0) + 1
            elif instr in DT_TITEL:
                ptoks = distinct_tokens(titel, bg)
                best = None
                for work, ops in reg.get((code, DT_TITEL[instr]), []):
                    s = containment(ptoks, ops)
                    if s >= THRESHOLD and (not best or s > best[2]):
                        best = (work, ops, s)
                if best:
                    links.append((slug, "ow", best[0], best[1], DT_TITEL[instr], "bronhouder+documenttype+titel", round(best[2], 2)))
                    tally["ow-titel"] = tally.get("ow-titel", 0) + 1
            elif instr == "bestemmingsplan":
                ptoks = distinct_tokens(titel, bg)
                best = None
                for idn, naam in wro.get(code, []):
                    s = containment(ptoks, naam)
                    if s >= THRESHOLD and (not best or s > best[2]):
                        best = (idn, naam, s)
                if best:
                    links.append((slug, "wro", best[0], best[1], "bestemmingsplan", "wro-naam", round(best[2], 2)))
                    tally["wro-naam"] = tally.get("wro-naam", 0) + 1

        cur.executemany("""INSERT INTO mer.project_regeling(project_slug,doel_type,doel_id,opschrift,documenttype,methode,zekerheid)
                           VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""", links)
        pg.commit()
        cur.execute("SELECT COUNT(DISTINCT project_slug) FROM mer.project_regeling")
        print(f"Gekoppeld: {len(links)} links over {cur.fetchone()[0]} trajecten (van {len(projects)}). Per methode: {tally}")
        print("\nVoorbeelden:")
        cur.execute("""SELECT p.titel, l.opschrift, l.methode, l.zekerheid, l.doel_id
                       FROM mer.project_regeling l JOIN mer.project p ON p.slug=l.project_slug
                       ORDER BY random() LIMIT 8""")
        for t, o, m, z, d in cur.fetchall():
            print(f"  '{t[:32]}' -> '{o[:36]}' ({m}, {z}) [{d[:40]}]")


if __name__ == "__main__":
    main()
