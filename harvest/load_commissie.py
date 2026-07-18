"""load_commissie.py — kanaal B: Commissie m.e.r.-projecten + documenten
→ tabellen `project` + `document`.

Route: advice-sitemaps (volledige inventaris, mét lastmod) → per projectpagina
metadata + kern-documenten (PDF-URL's, geen downloads). Resumable: al gescrapete
slugs worden overgeslagen. Beleefd: 1s/req, 429-adaptief (stopt netjes bij
aanhoudende throttling).

    python load_commissie.py [--limit N] [--refresh]   # --refresh: her-scrape alles
"""
import argparse
import re

import lib

SITEMAPS = [f"https://www.commissiemer.nl/advice-sitemap{i}.xml" for i in ("", 2, 3, 4)]
KERN_SOORTEN = ["MER", "startnotitie", "richtlijnen", "toetsingsadvies", "MER-bijlage"]
MAX_BIJLAGEN = 2


def doc_type(fname):
    f = fname.lower()
    m = re.match(r"a?\d+[-_]?(\d+)?([a-z_]+)", f)
    code = (m.group(2) or "").strip("_") if m else ""
    if "toetsingsadvies" in f or re.search(r"(^|[_-])ts(\b|[_-])", f) or code == "ts":
        return "toetsingsadvies"
    if "richtlijn" in f or "vastrl" in f or code in ("rl", "vastrl"):
        return "richtlijnen"
    if ("reikwijdte" in f or "startnotitie" in f or "aanmeldnotitie" in f
            or re.search(r"(^|[_-])(sn|rd|notrw)(\b|[_-])", f) or code in ("sn", "rd", "notrw")):
        return "startnotitie"
    if re.search(r"(^|[_-])mer[-_].*hr|hoofdrapport|(^|[_-])mer\.pdf|planmer", f) or code in ("mer", "planmer"):
        return "MER"
    if ("mer" in f and ("bijlage" in f or "samenvatting" in f)) or code == "mer_bijl":
        return "MER-bijlage"
    if re.search(r"onderzoek|achtergrond|rapport|quick-scan|bijlage|effectrapportage", f):
        return "MER-bijlage"
    return "overig"


def _rank(soort, url):
    f = url.lower()
    s = 10 if "persbericht" in f else 0
    if soort == "MER":
        if re.search(r"[-_]hr|hoofdrapport|samenvatting", f):
            s -= 5
        if "bijlage" in f:
            s += 3
    return (s, len(url))


def select_kern(pdfs):
    by = {}
    for u in pdfs:
        by.setdefault(doc_type(u.split("/")[-1]), []).append(u)
    out = []
    for soort in KERN_SOORTEN:
        for u in sorted(by.get(soort, []), key=lambda u: _rank(soort, u))[: (MAX_BIJLAGEN if soort == "MER-bijlage" else 1)]:
            out.append((soort, u.split("/")[-1], u))
    return out


def cm_field(html, label):
    text = re.sub(r"<[^>]+>", "|", html)
    m = re.search(rf"\|{label}\|", text)
    if not m:
        return None
    for tok in text[m.end():].split("|"):
        tok = re.sub(r"\s+", " ", tok).strip()
        if tok:
            return tok[:200]
    return None


def sitemap_entries():
    out = {}
    for sm in SITEMAPS:
        xml = lib.http_get(sm, base_delay=1.0)
        for loc, mod in re.findall(r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", xml):
            slug = loc.rstrip("/").split("/")[-1]
            out[slug] = {"url": loc, "lastmod": mod}
    return out


def scrape(slug, url):
    h = lib.http_get(url, base_delay=1.0)
    titel = re.sub(r"<[^>]+>", "", (re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S) or [None, ""])[1]).strip()
    pdfs = sorted(set(re.findall(r'href="(https://pas\.commissiemer\.nl/files/[^"]+)"', h)))
    project_nr = None
    if pdfs:
        m = re.search(r"/files/nl/(\d+)/", pdfs[0])
        project_nr = int(m.group(1)) if m else None
    return {
        "titel": titel, "project_nr": project_nr,
        "bevoegd_gezag": cm_field(h, "Bevoegd gezag"),
        "initiatiefnemer": cm_field(h, "Initiatiefnemer"),
        "start_advisering": cm_field(h, "Start advisering"),
        "documenten": select_kern(pdfs),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    con = lib.connect()
    lib.init_schema(con)

    print("Kanaal B (Commissie m.e.r.): sitemaps ophalen…")
    entries = sitemap_entries()
    done = set() if args.refresh else {r[0] for r in con.execute("SELECT slug FROM project").fetchall()}
    todo = [(s, e) for s, e in entries.items() if s not in done][: args.limit]
    print(f"  {len(entries)} projecten in sitemap; {len(done)} al geladen; {len(todo)} te doen")

    n = 0
    try:
        for slug, e in todo:
            p = scrape(slug, e["url"])
            con.execute(
                """INSERT INTO project(slug,project_nr,titel,bevoegd_gezag,initiatiefnemer,
                                       start_advisering,url,lastmod)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(slug) DO UPDATE SET
                     project_nr=excluded.project_nr, titel=excluded.titel,
                     bevoegd_gezag=excluded.bevoegd_gezag, initiatiefnemer=excluded.initiatiefnemer,
                     start_advisering=excluded.start_advisering, lastmod=excluded.lastmod""",
                (slug, p["project_nr"], p["titel"], p["bevoegd_gezag"], p["initiatiefnemer"],
                 p["start_advisering"], e["url"], e["lastmod"]))
            con.execute("DELETE FROM document WHERE project_slug=?", (slug,))
            con.executemany(
                "INSERT OR IGNORE INTO document(project_slug,soort,bestandsnaam,url) VALUES(?,?,?,?)",
                [(slug, s, fn, u) for (s, fn, u) in p["documenten"]])
            con.commit()
            n += 1
            if n % 100 == 0:
                print(f"  … {n}/{len(todo)} projecten (laatst: {slug})")
    except lib.RateLimited as ex:
        print(f"GESTOPT door rate-limiting: {ex}\n  Resumable — draai opnieuw om te hervatten. {n} nieuw geladen.")

    tot = con.execute("SELECT COUNT(*) FROM project").fetchone()[0]
    docs = con.execute("SELECT COUNT(*) FROM document").fetchone()[0]
    lib.set_state(con, "project", f"geladen={tot}")
    print(f"Klaar deze run: +{n}. Tabel `project`={tot}, `document`={docs}.")
    con.close()


if __name__ == "__main__":
    main()
