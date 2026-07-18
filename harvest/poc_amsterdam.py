"""PoC mer-register.nl — 5 MER-trajecten uit Amsterdam, end-to-end.

Keten: kanaal A (KOOP-events, al geharvest naar data/amsterdam_events_raw.json)
+ kanaal B (Commissie m.e.r.-documenten, 5 projectpagina's) -> join tot
'trajecten' -> web/mer-data.js in exact de vorm die het Claude-ontwerp verwacht.

Bewust klein: 5 vooraf gekozen projecten, ~6 requests totaal. Stdlib-only.

    python poc_amsterdam.py
"""
import json
import re
import urllib.request
from pathlib import Path

UA = {"User-Agent": "mer-register-poc/0.1 (richard.de.graaf@conteo-consulting.nl)"}
HERE = Path(__file__).parent
DATA = HERE / "data"
WEB = HERE.parent / "web"

# --- de 5 gekozen Amsterdamse trajecten -------------------------------------
# anchor = regex op de KOOP-titel; cm_slug = Commissie m.e.r.-projectpagina;
# coord = benaderende locatie in Amsterdam (kaart is schematisch).
PROJECTS = [
    {"id": "haven-stad", "titel": "Haven-Stad Amsterdam", "instrument": "omgevingsplan",
     "anchor": r"haven[- ]?stad|hamerkwartier|sloterdijk i mediacollege",
     "cm_slug": "ontwikkeling-haven-stad-amsterdam", "coord": [52.402, 4.872]},
    {"id": "windenergie-adam", "titel": "Programma Windenergie Amsterdam 2030", "instrument": "programma",
     "anchor": r"windenergie amsterdam",
     "cm_slug": "programma-windenergie-amsterdam", "coord": [52.370, 4.900]},
    {"id": "strandeiland", "titel": "Strandeiland (IJburg)", "instrument": "omgevingsplan",
     "anchor": r"strandeiland",
     "cm_slug": "strandeiland-ijburg-2-gemeente-amsterdam", "coord": [52.341, 5.021]},
    {"id": "zeeburgereiland-sluisbuurt", "titel": "Zeeburgereiland / Sluisbuurt", "instrument": "bestemmingsplan",
     "anchor": r"sluisbuurt|zeeburgereiland",
     "cm_slug": "herontwikkeling-zeeburgereiland-amsterdam", "coord": [52.373, 4.982]},
    {"id": "schinkelkwartier", "titel": "Schinkelkwartier", "instrument": "omgevingsplan",
     "anchor": r"schinkelkwartier",
     "cm_slug": "schinkelkwartier-amsterdam", "coord": [52.340, 4.851]},
]

# --- classificatie van KOOP-titels naar event-type -------------------------
# Volgorde telt: 'voornemen/NRD' en 'terinzage' (ontwerp) staan VOOR 'vaststelling',
# anders wint "ontwerp ... vaststelling hogere waarden" ten onrechte van terinzage.
EVENT_RULES = [
    ("mer-beoordeling: geen MER nodig", r"geen milieueffectrapport|niet doorlopen"),
    ("voornemen/NRD",                   r"voornemen|notitie reikwijdte|reikwijdte en detailniveau|\bnrd\b"),
    ("terinzage MER",                   r"terinzage|ter inzage|tervisie|tervisielegging|ontwerp"),
    ("vaststelling met MER",            r"vaststell|vastgesteld|aanvaarden van de conclusies"),
    ("mer-beoordeling",                 r"beoordeling milieueffect|m\.e\.r\.?-?plicht|mer-beoordeling|aanmeldnotitie"),
]

# Kern-documentsoorten die we tonen (achtergrondrapporten laten we vallen).
KERN_SOORTEN = ["MER", "startnotitie", "richtlijnen", "toetsingsadvies", "MER-bijlage"]
MAX_BIJLAGEN = 2


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "replace")


def classify_event(titel):
    low = (titel or "").lower()
    for label, pat in EVENT_RULES:
        if re.search(pat, low):
            return label
    return "mer-beoordeling"  # fallback: het is per definitie een m.e.r.-publicatie


def doc_type(fname):
    """Classificeer een pas.commissiemer.nl-bestandsnaam — dekt zowel het oude
    gecodeerde patroon (3102-002sn) als de nieuwere beschrijvende namen."""
    f = fname.lower()
    m = re.match(r"a?\d+[-_]?(\d+)?([a-z_]+)", f)   # code-suffix, bv. ...002sn / a3102_ts
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


def _doc_rank(soort, url):
    """Lager = liever tonen. Persberichten zakken; MER-hoofdrapport drijft boven."""
    f = url.lower()
    score = 0
    if "persbericht" in f:
        score += 10                      # het echte advies verkiezen boven de aankondiging
    if soort == "MER":
        if re.search(r"[-_]hr|hoofdrapport|samenvatting", f):
            score -= 5                    # hoofdrapport/samenvatting boven losse deelrapporten
        if "bijlage" in f:
            score += 3
    return (score, len(url))


def select_kern_documenten(pdfs):
    """Classificeer alle PDF's, houd per kern-soort het meest representatieve
    (bijlagen: max 2)."""
    by_soort = {}
    for u in pdfs:
        s = doc_type(u.split("/")[-1])
        by_soort.setdefault(s, []).append(u)
    out = []
    for soort in KERN_SOORTEN:
        urls = sorted(by_soort.get(soort, []), key=lambda u: _doc_rank(soort, u))
        for u in urls[: (MAX_BIJLAGEN if soort == "MER-bijlage" else 1)]:
            out.append({"soort": soort, "titel": doc_titel(soort, u), "link": u})
    return out


def doc_titel(soort, url):
    stem = url.split("/")[-1].rsplit(".", 1)[0]
    stem = re.sub(r"^a?\d+[-_]?\d*[-_]?", "", stem)          # code-prefix eraf
    stem = re.sub(r"[-_]+", " ", stem).strip()
    return f"{soort} — {stem[:60]}" if stem else f"{soort} — Commissie m.e.r."


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


def scrape_commissie(slug):
    """Haal documenten + metadata van één Commissie m.e.r.-projectpagina."""
    url = f"https://www.commissiemer.nl/advies/{slug}/"
    h = get(url)
    pdfs = sorted(set(re.findall(r'href="(https://pas\.commissiemer\.nl/files/[^"]+)"', h)))
    return {
        "url": url,
        "initiatiefnemer": cm_field(h, "Initiatiefnemer"),
        "start_advisering": cm_field(h, "Start advisering"),
        "documenten": select_kern_documenten(pdfs),
    }


def main():
    events = json.loads((DATA / "amsterdam_events_raw.json").read_text(encoding="utf-8"))

    trajecten = []
    for p in PROJECTS:
        # kanaal A: events die bij dit project horen, chronologisch, ontdubbeld op (datum,type)
        evs, seen = [], set()
        for e in sorted(events, key=lambda r: r["datum"] or ""):
            if not re.search(p["anchor"], (e["titel"] or "").lower()):
                continue
            etype = classify_event(e["titel"])
            k = (e["datum"], etype)
            if k in seen:
                continue
            seen.add(k)
            evs.append({"datum": e["datum"], "type": etype, "blad": e["blad"], "link": e["url"]})

        # kanaal B: Commissie m.e.r.-dossier
        cm = scrape_commissie(p["cm_slug"])

        trajecten.append({
            "id": p["id"],
            "titel": p["titel"],
            "bevoegdGezag": "Gemeente Amsterdam",
            "initiatiefnemer": cm["initiatiefnemer"] or "Gemeente Amsterdam",
            "instrument": p["instrument"],
            "provincie": "Noord-Holland",
            "coord": p["coord"],
            "events": evs,
            "documenten": cm["documenten"],
            "bronnen": {"commissie_mer": cm["url"]},
        })
        print(f"[{p['id']:26s}] events={len(evs):2d}  documenten={len(cm['documenten']):2d}  "
              f"(CM: {p['cm_slug']})")

    # opslaan als tussenresultaat + als drop-in mer-data.js voor het ontwerp
    (DATA / "amsterdam_trajecten.json").write_text(
        json.dumps(trajecten, ensure_ascii=False, indent=1), encoding="utf-8")
    write_mer_data(trajecten)
    print(f"\n-> {DATA/'amsterdam_trajecten.json'}")
    print(f"-> {WEB/'mer-data.js'} (echte data; herstel met git checkout voor de mock)")


def write_mer_data(trajecten):
    """Emit web/mer-data.js in exact de vorm die MER-register.dc.html verwacht."""
    body = json.dumps(trajecten, ensure_ascii=False, indent=2)
    js = f"""// mer-data.js — ECHTE PoC-data (5 Amsterdamse trajecten), gegenereerd door
// harvest/poc_amsterdam.py. Kanaal A = KOOP officielebekendmakingen (events),
// kanaal B = Commissie m.e.r. (documenten). Herstel de mock met `git checkout`.

export const EVENT_TYPES = [
  'voornemen/NRD',
  'mer-beoordeling',
  'mer-beoordeling: geen MER nodig',
  'terinzage MER',
  'vaststelling met MER',
];

export const INSTRUMENTEN = [
  'projectbesluit', 'omgevingsplan', 'omgevingsvergunning',
  'bestemmingsplan', 'omgevingsvisie', 'programma',
];

export const DOC_SOORTEN = ['MER', 'MER-bijlage', 'startnotitie', 'richtlijnen', 'toetsingsadvies'];

export const PROVINCIES = [
  'Groningen','Fryslân','Drenthe','Overijssel','Flevoland','Gelderland',
  'Utrecht','Noord-Holland','Zuid-Holland','Zeeland','Noord-Brabant','Limburg',
];

export const trajecten = {body};
"""
    WEB.mkdir(exist_ok=True)
    (WEB / "mer-data.js").write_text(js, encoding="utf-8")


if __name__ == "__main__":
    main()
