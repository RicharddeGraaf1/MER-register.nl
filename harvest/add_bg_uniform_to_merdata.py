"""add_bg_uniform_to_merdata.py — verrijk web/mer-data.js met een UNIFORME
bevoegd-gezag-naam per traject.

De rauwe bevoegd_gezag-strings uit de Commissie-data zijn zwaar versplinterd
(1299 varianten voor 377 echte overheden — mede-overheden achter elkaar geplakt).
Dit voegt `bevoegdGezagUniform` toe: het canonieke core.bronhouder.label waar de
bronhouder is geresolveerd, anders de rauwe string. Zo wordt het BG-filter bruikbaar.

    MER_PROD_URL="postgresql://..." python add_bg_uniform_to_merdata.py
"""
import json
import os
import re
from pathlib import Path

import psycopg

MERDATA = Path(__file__).parent.parent / "web" / "mer-data.js"


def main():
    js = MERDATA.read_text(encoding="utf-8")
    m = re.search(r"export const trajecten = (\[.*\]);", js, re.S)
    trajecten = json.loads(m.group(1))

    with psycopg.connect(os.environ["MER_PROD_URL"], connect_timeout=30) as pg:
        cur = pg.cursor()
        cur.execute("""SELECT p.slug, COALESCE(b.label, p.bevoegd_gezag) AS uniform, b.overheidscode
                       FROM mer.project p LEFT JOIN core.bronhouder b ON b.overheidscode=p.bronhouder_code""")
        by_slug = {slug: (uni, code) for slug, uni, code in cur.fetchall()}

    n = 0
    for t in trajecten:
        uni, code = by_slug.get(t["id"], (t.get("bevoegdGezag"), None))
        t["bevoegdGezagUniform"] = uni or t.get("bevoegdGezag")
        t["bronhouderCode"] = code
        if code:
            n += 1

    body = json.dumps(trajecten, ensure_ascii=False, indent=1)
    js = js[:m.start(1)] + body + js[m.end(1):]
    MERDATA.write_text(js, encoding="utf-8")
    uniek = len({t["bevoegdGezagUniform"] for t in trajecten})
    print(f"Verrijkt: {n}/{len(trajecten)} met geresolveerde bronhouder; "
          f"{uniek} unieke bevoegdGezagUniform-waarden (was {len({t['bevoegdGezag'] for t in trajecten})} rauw).")


if __name__ == "__main__":
    main()
