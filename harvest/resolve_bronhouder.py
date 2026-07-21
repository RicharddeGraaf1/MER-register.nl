"""resolve_bronhouder.py — koppel mer.event/mer.project aan core.bronhouder.

core.bronhouder sleutelt op `overheidscode` (text, bv. gm0370), dus we vullen
een nieuwe kolom `bronhouder_code`. Match op genormaliseerde naam:
strip "Gemeente/Provincie/Waterschap"-prefix + eerste deel vóór komma + lower.

    MER_PROD_URL="postgresql://..." python resolve_bronhouder.py
"""
import os
import re
import unicodedata

import psycopg


def norm(s):
    if not s:
        return ""
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    s = s.split(",")[0].split(" - ")[0]
    s = re.sub(r"\b(gemeente|provincie|waterschap|hoogheemraadschap|het|de)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    with psycopg.connect(os.environ["MER_PROD_URL"], connect_timeout=30) as pg:
        cur = pg.cursor()
        for t in ("event", "project"):
            cur.execute(f"ALTER TABLE mer.{t} ADD COLUMN IF NOT EXISTS bronhouder_code text")
        pg.commit()

        # bronhouder-index: norm(naam) -> overheidscode; schone namen (geen '(')
        # en gemeente/provincie/waterschap-lagen krijgen voorrang.
        cur.execute("SELECT overheidscode, naam, bestuurslaag FROM core.bronhouder")
        idx = {}
        for code, naam, laag in cur.fetchall():
            k = norm(naam)
            if not k:
                continue
            score = (0 if "(" not in (naam or "") else 1,
                     0 if laag in ("gemeente", "provincie", "waterschap") else 1, len(naam or ""))
            if k not in idx or score < idx[k][1]:
                idx[k] = (code, score)

        def resolve_col(table, col):
            cur.execute(f"SELECT DISTINCT {col} FROM mer.{table} WHERE {col} IS NOT NULL")
            vals = [r[0] for r in cur.fetchall()]
            hits = [(idx[norm(v)][0], v) for v in vals if norm(v) in idx]
            cur.executemany(f"UPDATE mer.{table} SET bronhouder_code=%s WHERE {col}=%s", hits)
            pg.commit()
            cur.execute(f"SELECT count(*) FILTER (WHERE bronhouder_code IS NOT NULL), count(*) FROM mer.{table}")
            n, tot = cur.fetchone()
            print(f"  mer.{table}: {len(hits)}/{len(vals)} unieke BG's gematcht -> {n}/{tot} rijen gekoppeld")

        resolve_col("event", "bevoegd_gezag_naam")
        resolve_col("project", "bevoegd_gezag")
    print("Klaar.")


if __name__ == "__main__":
    main()
