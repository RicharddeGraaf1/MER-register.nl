"""add_regeling_to_merdata.py — verrijk web/mer-data.js met de onderliggende
regeling(en) per traject uit prod mer.project_regeling.

De statische frontend leest mer-data.js; deze stap voegt per traject het veld
`onderliggendeRegelingen` toe (opschrift, documenttype, methode, zekerheid,
DSO-deeplink) zodat de koppeling + zekerheid in de UI getoond kan worden.

    MER_PROD_URL="postgresql://..." python add_regeling_to_merdata.py
"""
import json
import os
import re
from pathlib import Path

import psycopg

MERDATA = Path(__file__).parent.parent / "web" / "mer-data.js"


def deeplink(doel_type, doel_id):
    return (f"https://identifier.overheid.nl{doel_id}" if doel_type == "ow"
            else f"https://www.ruimtelijkeplannen.nl/?planidn={doel_id}")


def main():
    js = MERDATA.read_text(encoding="utf-8")
    m = re.search(r"export const trajecten = (\[.*\]);", js, re.S)
    trajecten = json.loads(m.group(1))

    with psycopg.connect(os.environ["MER_PROD_URL"], connect_timeout=30) as pg:
        cur = pg.cursor()
        cur.execute("""SELECT project_slug, doel_type, doel_id, opschrift, documenttype, methode, zekerheid
                       FROM mer.project_regeling ORDER BY project_slug, zekerheid DESC""")
        by_slug = {}
        for slug, dt, did, ops, doct, meth, zek in cur.fetchall():
            by_slug.setdefault(slug, []).append({
                "opschrift": ops, "documenttype": doct, "methode": meth,
                "zekerheid": float(zek) if zek is not None else None,
                "link": deeplink(dt, did),
            })

    n = 0
    for t in trajecten:
        rr = by_slug.get(t["id"], [])
        t["onderliggendeRegelingen"] = rr
        if rr:
            n += 1

    body = json.dumps(trajecten, ensure_ascii=False, indent=1)
    js = js[:m.start(1)] + body + js[m.end(1):]
    MERDATA.write_text(js, encoding="utf-8")
    print(f"Verrijkt: {n}/{len(trajecten)} trajecten met onderliggende regeling(en) -> web/mer-data.js")


if __name__ == "__main__":
    main()
