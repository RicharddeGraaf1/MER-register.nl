"""build_links.py — koppel kanaal A (events) aan kanaal B (Commissie-projecten)
→ tabel `project_event_link`. Generieke variant van de PoC-ankers:
blocking op genormaliseerd bevoegd gezag → scoren op titel-overlap.

    python build_links.py
"""
import re
from datetime import date

import lib

# publicatiebladen die echte besluiten/kennisgevingen dragen (geen parlementaire ruis)
BESLUIT_BLADEN = ("Gemeenteblad", "Provinciaal blad", "Staatscourant",
                  "Waterschapsblad", "Blad gemeenschappelijke regeling")

STOP = set("""kennisgeving milieueffectrapport milieueffectrapportage mer m.e.r ontwerp
bestemmingsplan omgevingsplan omgevingsvergunning omgevingsvisie projectbesluit programma
vaststelling vastgesteld terinzagelegging terinzage tervisielegging gemeente provincie
besluit besluiten hogere waarden wet geluidhinder voornemen notitie reikwijdte detailniveau
plan ter inzage voorbereiding opstellen gewijzigde vaststellen aanvaarden conclusies
beoordeling plicht van de het een voor tot met en op in aan of nr bijbehorende""".split())

MAANDEN = {m: i for i, m in enumerate(
    "januari februari maart april mei juni juli augustus september oktober november december".split(), 1)}


def norm_bg(s):
    if not s:
        return ""
    s = s.lower()
    s = re.split(r",|/|;", s)[0]                        # eerste BG bij meerdere
    s = re.sub(r"\b(gemeente|provincie|de|het)\b", " ", s)
    if "rijkswaterstaat" in s or "ministerie" in s or "minister" in s:
        return "rijk"
    if "waterschap" in s or "hoogheemraadschap" in s:
        s = re.sub(r"\b(waterschap|hoogheemraadschap)\b", " ", s)
    return re.sub(r"[^a-zà-ÿ ]", " ", s).split() and re.sub(r"\s+", " ", s).strip() or ""


def tokens(titel):
    return {w for w in re.findall(r"[a-zà-ÿ0-9]{3,}", (titel or "").lower()) if w not in STOP}


def parse_dutch_date(s):
    if not s:
        return None
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", s.lower())
    if m and m.group(2) in MAANDEN:
        try:
            return date(int(m.group(3)), MAANDEN[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    return None


def year_of(iso):
    m = re.match(r"(\d{4})", iso or "")
    return int(m.group(1)) if m else None


def main():
    con = lib.connect()
    lib.init_schema(con)

    events = con.execute(
        f"SELECT koop_id,titel,datum_publicatie,bevoegd_gezag_naam FROM event "
        f"WHERE publicatieblad IN ({','.join('?'*len(BESLUIT_BLADEN))})", BESLUIT_BLADEN).fetchall()
    projects = con.execute(
        "SELECT slug,titel,bevoegd_gezag,start_advisering FROM project").fetchall()

    # index events per genormaliseerd BG
    ev_by_bg = {}
    for kid, tit, dat, bg in events:
        ev_by_bg.setdefault(norm_bg(bg), []).append((kid, tit, dat))

    THRESHOLD = 0.6
    con.execute("DELETE FROM project_event_link")
    n_links, n_projects_matched = 0, 0

    for slug, ptit, pbg, pstart in projects:
        bg = norm_bg(pbg)
        cands = ev_by_bg.get(bg, [])
        if not cands:
            continue
        # BG-naam-tokens zijn al de blocking-sleutel; ze mogen niet meetellen in de
        # titel-match (anders matcht elk event van dezelfde overheid op de BG-naam).
        bg_tokens = set(re.findall(r"[a-zà-ÿ0-9]{3,}", (pbg or "").lower())) | set(bg.split())
        ptoks = tokens(ptit) - bg_tokens
        if not ptoks:            # geen onderscheidend woord over BG heen → niet auto-koppelen
            continue
        pyear = (parse_dutch_date(pstart) or date(1900, 1, 1)).year
        matched = False
        for kid, etit, edat in cands:
            etoks = tokens(etit)
            if not etoks:
                continue
            # containment: hoeveel van de projecttitel-tokens zit in het event?
            score = len(ptoks & etoks) / len(ptoks)
            ey = year_of(edat)
            if score >= THRESHOLD and (pyear == 1900 or ey is None or abs(ey - pyear) <= 8):
                con.execute(
                    "INSERT OR REPLACE INTO project_event_link(project_slug,koop_id,match_methode,zekerheid) "
                    "VALUES(?,?,?,?)", (slug, kid, "bg+periode+titel", round(score, 2)))
                n_links += 1
                matched = True
        if matched:
            n_projects_matched += 1

    con.commit()
    print(f"Koppeling klaar: {n_links} links over {n_projects_matched} projecten "
          f"(van {len(projects)} projecten, {len(events)} besluit-events).")
    # steekproef
    print("\nVoorbeeld-koppelingen:")
    for row in con.execute(
        """SELECT p.titel, COUNT(*) c, MIN(e.datum_publicatie), MAX(e.datum_publicatie)
           FROM project_event_link l JOIN project p ON p.slug=l.project_slug
           JOIN event e ON e.koop_id=l.koop_id GROUP BY p.slug ORDER BY c DESC LIMIT 8""").fetchall():
        print(f"  {row[1]:2d} events  {row[2]}…{row[3]}  {row[0][:55]}")
    con.close()


if __name__ == "__main__":
    main()
