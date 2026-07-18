"""PoC-harvester 2: projectendatabase Commissie voor de milieueffectrapportage.

Route: sitemaps (advice-sitemap*.xml, volledig, ~3.600 projecten) -> per
projectpagina metadata (bevoegd gezag, initiatiefnemer, datums) + directe
PDF-links (pas.commissiemer.nl/files/nl/<nr>/...), incl. de MER'en zelf.

Gebruik:
    python harvest_commissiemer.py [--sample N]   (default 12 pagina's)
Output: data/commissiemer_projects.json + console-statistiek.
"""
import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "mer-register-poc/0.1 (contact: richard.de.graaf@conteo-consulting.nl)"}
SITEMAPS = [f"https://www.commissiemer.nl/advice-sitemap{i}.xml" for i in ("", 2, 3, 4)]

# suffix in pas.commissiemer.nl-bestandsnaam -> documentsoort
DOC_TYPES = {
    "mer": "MER", "mer_bijl": "MER-bijlage", "sn": "startnotitie",
    "rl": "richtlijnen", "ts": "toetsingsadvies", "rd": "reikwijdte-detailniveau",
}


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def sitemap_urls():
    for sm in SITEMAPS:
        xml = get(sm)
        for loc, mod in re.findall(r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", xml):
            yield loc, mod


def field(html: str, label: str):
    """Pak de waarde die in de Projectinformatie-blokken na een label komt."""
    text = re.sub(r"<[^>]+>", "|", html)
    m = re.search(rf"\|{label}\|", text)
    if not m:
        return None
    for token in text[m.end():].split("|"):
        token = re.sub(r"\s+", " ", token).strip()
        if token:
            return token[:200]
    return None


def doc_type(fname: str) -> str:
    m = re.match(r"\d+-\d+([a-z_]+)", fname)
    return DOC_TYPES.get(m.group(1), m.group(1)) if m else "onbekend"


def scrape_project(url: str) -> dict:
    h = get(url)
    title = (re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S) or [None, ""])[1]
    pdfs = sorted(set(re.findall(r'href="(https://pas\.commissiemer\.nl/files/[^"]+)"', h)))
    project_nr = None
    if pdfs:
        m = re.search(r"/files/nl/(\d+)/", pdfs[0])
        project_nr = m.group(1) if m else None
    return {
        "url": url,
        "slug": url.rstrip("/").split("/")[-1],
        "titel": re.sub(r"<[^>]+>", "", title).strip(),
        "projectnummer": project_nr,
        "bevoegd_gezag": field(h, "Bevoegd gezag"),
        "initiatiefnemer": field(h, "Initiatiefnemer"),
        "start_advisering": field(h, "Start advisering"),
        "documenten": [
            {"url": u, "bestand": u.split("/")[-1], "soort": doc_type(u.split("/")[-1])}
            for u in pdfs
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=12)
    args = ap.parse_args()

    urls = list(sitemap_urls())
    print(f"Sitemap: {len(urls)} projectpagina's gevonden")

    # spreid de steekproef over de hele database (oud t/m nieuw)
    step = max(1, len(urls) // args.sample)
    sample = [urls[i][0] for i in range(0, len(urls), step)][: args.sample]

    projects = []
    for u in sample:
        try:
            projects.append(scrape_project(u))
        except Exception as e:  # PoC: doorgaan en tellen
            projects.append({"url": u, "error": str(e)})
        time.sleep(0.5)

    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    (out / "commissiemer_projects.json").write_text(
        json.dumps(projects, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = [p for p in projects if "error" not in p]
    with_docs = [p for p in ok if p["documenten"]]
    with_mer = [p for p in ok if any(d["soort"].startswith("MER") for d in p["documenten"])]
    print(f"Gescrapet: {len(ok)}/{len(projects)} ok -> data/commissiemer_projects.json")
    print(f"  met documenten: {len(with_docs)}, waarvan met MER-pdf: {len(with_mer)}")
    for p in ok:
        docs = ", ".join(sorted({d['soort'] for d in p['documenten']})) or "-"
        print(f"  [{p['projectnummer'] or '----'}] {p['titel'][:55]:55s} bg={str(p['bevoegd_gezag'])[:30]:30s} docs: {docs}")


if __name__ == "__main__":
    main()
