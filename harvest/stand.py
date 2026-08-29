"""stand.py — past wat de site toont nog bij wat de harvest weet?

Antwoordt op één vraag: mag mer-register.nl nu gepubliceerd worden, of zou dat
een register tonen dat achterloopt?

Bestaansreden: de site is *gebakken*. `web/mer-data.js` is een statische export
uit `data/mer.db`; er is geen runtime-koppeling met `/v1/mer/*`. Loopt de
harvest of de export achter, dan faalt er niets — de site ziet er precies even
actueel uit als daarvoor en toont maandenoude trajecten. Precies dat gebeurde
tussen 21-07-2026 en 27-08-2026.

Twee manieren waarop het achter kan lopen; ze horen bij de stappen die ze
oplossen (zie het OCD-runbook, stap 6d):

  A. export ouder dan de harvest-store   -> export_mer_data.py + de verrijkers
  B. harvest-store zelf verouderd        -> load_events.py / load_commissie.py

**Alleen B zet de poort op rood.** A wordt gerapporteerd maar blokkeert niet,
want `publish.py` regenereert de export zelf in zijn build-fase — daarop weigeren
zou een rode poort geven voor precies het probleem dat de volgende stap oplost.
De harvest kan `publish.py` níet doen: die haalt externe bronnen op (KOOP SRU +
3.617 Commissie-pagina's) en hoort in de data-fase van de sync, niet in de
publicatie-fase.

Exitcode 0 = bij, 1 = achter, 2 = kan het niet vaststellen (store of export
ontbreekt). Bedoeld als poort vóór publiceren, dus "kan het niet vaststellen"
is géén 0.

Draai:  python harvest/stand.py [--json] [--max-dagen 14]

De prod-regel is INFORMATIEF en zet de poort niet op rood: hij vertelt of
`/v1/mer/*` meebeweegt met de store. Zolang de site gebakken is raakt dat de
bezoeker niet — zodra deelplan E (Pages-Function-proxy) landt wél, en dan hoort
deze regel een poortsignaal te worden.
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).parent
STORE = HERE / "data" / "mer.db"
EXPORT = HERE.parent / "web" / "mer-data.js"


def _nieuwste_publicatie(sq) -> str | None:
    r = sq.execute("SELECT max(datum_publicatie) FROM event").fetchone()
    return r[0] if r else None


def _nieuwste_bij_bron(timeout: int = 20) -> tuple[str | None, str]:
    """Vraag KOOP wat de nieuwste MER-publicatie is. Eén SRU-call.

    Waarom dit er is: tot 2026-08-29 keek de poort alleen naar de *leeftijd* van
    de nieuwste publicatie in de store (`--max-dagen 14`). Die drempel kan een
    stille bron niet van een stille harvest onderscheiden. Op 28-08 was de store
    zojuist volledig gesweept (2.261 van 2.261 beschikbaar) en stond de poort tóch
    op rood, puur omdat KOOP sinds 6 augustus geen MER-titel had gepubliceerd.
    `--force-preflight` was dan de enige uitweg — en een poort die je elke keer
    moet forceren, bewaakt niets meer.

    De juiste vraag is niet "hoe oud is het nieuwste item" maar "heeft de bron
    iets wat wij niet hebben". Retourneert (datum, toelichting); bij een
    onbereikbare bron retourneert hij (None, reden) en valt de aanroeper terug op
    de leeftijdsdrempel.
    """
    import re
    import urllib.parse
    import urllib.request
    SRU = "https://repository.overheid.nl/sru"
    QUERY = ('dt.title any "milieueffectrapport milieueffectrapportage"'
             ' sortBy dt.date/sort.descending')
    params = urllib.parse.urlencode({
        "operation": "searchRetrieve", "version": "2.0",
        "maximumRecords": 1, "startRecord": 1, "query": QUERY,
    })
    req = urllib.request.Request(
        f"{SRU}?{params}",
        headers={"User-Agent": "mer-register-stand/1.0 "
                               "(contact: richard.de.graaf@conteo-consulting.nl)"})
    try:
        xml = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    except Exception as e:
        return None, f"bron niet bereikbaar ({str(e)[:40]})"
    m = re.search(r"<dcterms:date[^>]*>(\d{4}-\d{2}-\d{2})", xml) or         re.search(r"<dt:date[^>]*>(\d{4}-\d{2}-\d{2})", xml) or         re.search(r">(\d{4}-\d{2}-\d{2})<", xml)
    if not m:
        return None, "kon de datum niet uit het SRU-antwoord lezen"
    return m.group(1), ""


def _prod_stand(events_lokaal: int) -> tuple[int | None, str]:
    """Telling van mer.event op prod. Retourneert (telling, toelichting)."""
    url = os.environ.get("MER_PROD_URL")
    if not url:
        return None, "MER_PROD_URL niet gezet"
    try:
        import psycopg
    except ImportError:
        return None, "psycopg niet geïnstalleerd"
    try:
        with psycopg.connect(url, connect_timeout=15) as pg, pg.cursor() as cur:
            cur.execute("SELECT to_regclass('mer.event')")
            if cur.fetchone()[0] is None:
                return None, "schema mer ontbreekt op prod"
            cur.execute("SELECT count(*) FROM mer.event")
            return cur.fetchone()[0], ""
    except Exception as e:  # proxy dicht, timeout, verkeerde DSN
        return None, f"prod niet bereikbaar: {type(e).__name__}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-dagen", type=int, default=14,
                   help="hoe oud de nieuwste KOOP-publicatie mag zijn (default 14)")
    p.add_argument("--json", action="store_true", help="machineleesbaar")
    p.add_argument("--geen-bron", action="store_true",
                   help="vraag KOOP niet; val terug op de leeftijdsdrempel. "
                        "Voor offline gebruik -- niet als poort.")
    a = p.parse_args()

    if not STORE.exists():
        print(f"harvest-store ontbreekt: {STORE}\n"
              "Dit is niet de machine waarop de harvest draait, of data/ is "
              "leeggehaald (de store is gitignored — load_commissie.py moet dan "
              "3.617 projectpagina's opnieuw scrapen, ~1 uur).", file=sys.stderr)
        return 2
    if not EXPORT.exists():
        print(f"export ontbreekt: {EXPORT}", file=sys.stderr)
        return 2

    store_mtime = datetime.fromtimestamp(STORE.stat().st_mtime)
    export_mtime = datetime.fromtimestamp(EXPORT.stat().st_mtime)
    export_achter = export_mtime < store_mtime

    with sqlite3.connect(f"file:{STORE}?mode=ro", uri=True) as sq:
        events = sq.execute("SELECT count(*) FROM event").fetchone()[0]
        projecten = sq.execute("SELECT count(*) FROM project").fetchone()[0]
        nieuwste = _nieuwste_publicatie(sq)

    dagen_oud = None
    if nieuwste:
        try:
            dagen_oud = (date.today() - date.fromisoformat(nieuwste[:10])).days
        except ValueError:
            pass
    # Eerst de bron zelf vragen; dat is de enige meting die een stille bron van
    # een stille harvest onderscheidt. Pas als de bron onbereikbaar is, terug naar
    # de leeftijdsdrempel -- die is een noodrem, geen norm.
    bron_datum, bron_reden = (None, "overgeslagen (--geen-bron)")
    if not a.geen_bron:
        bron_datum, bron_reden = _nieuwste_bij_bron()

    if bron_datum and nieuwste:
        # Store gelijk of vóór op de bron = bij, ongeacht hoe oud het nieuwste
        # item is. Loopt de store achter, dan is er echt iets op te halen.
        harvest_achter = str(nieuwste)[:10] < bron_datum
        bron_oordeel = ("store is bij de bron" if not harvest_achter
                        else f"bron heeft nieuwere publicaties (tot {bron_datum})")
    else:
        harvest_achter = dagen_oud is None or dagen_oud > a.max_dagen
        bron_oordeel = (f"bron niet gebruikt: {bron_reden}; teruggevallen op de "
                        f"leeftijdsdrempel van {a.max_dagen} dagen")

    prod_events, prod_reden = _prod_stand(events)

    # export_achter telt bewust NIET mee — zie de toelichting in de docstring.
    achter = harvest_achter
    stand = {
        "events": events,
        "projecten": projecten,
        "nieuwste_publicatie": nieuwste,
        "dagen_oud": dagen_oud,
        "bron_nieuwste": bron_datum,
        "bron_oordeel": bron_oordeel,
        "harvest_achter": harvest_achter,
        "store_gewijzigd": store_mtime.isoformat(timespec="seconds"),
        "export_gewijzigd": export_mtime.isoformat(timespec="seconds"),
        "export_achter": export_achter,
        "prod_events": prod_events,
        "achter": achter,
    }

    if a.json:
        print(json.dumps(stand, ensure_ascii=False))
        return 1 if achter else 0

    print("stand mer-register.nl")
    print(f"  events in de store                  {events:>7}")
    print(f"  projecten in de store               {projecten:>7}")
    if dagen_oud is None:
        print( "  nieuwste KOOP-publicatie                  ?   -> load_events.py")
    else:
        print(f"  nieuwste KOOP-publicatie      {str(nieuwste)[:10]:>12}"
              f"  ({dagen_oud} dagen oud, max {a.max_dagen})"
              + ("   -> load_events.py" if harvest_achter else ""))
    print(f"  store gewijzigd            {store_mtime:%Y-%m-%d %H:%M}")
    print(f"  export gewijzigd           {export_mtime:%Y-%m-%d %H:%M}"
          + ("   -> export_mer_data.py + verrijkers (informatief)" if export_achter else ""))
    if prod_events is None:
        print(f"  mer.event op prod                         ?   ({prod_reden}, informatief)")
    else:
        verschil = prod_events - events
        print(f"  mer.event op prod                   {prod_events:>7}   "
              f"({verschil:+d} t.o.v. de store, informatief)")
    print()
    print(f"  bron (KOOP SRU)               {str(bron_datum or '?'):>12}  {bron_oordeel}")
    print()
    print("ACHTER — draai stap 6d vóór publiceren (OCD-runbook)"
          if achter else "BIJ — de export past bij de harvest; publiceren mag.")
    return 1 if achter else 0


if __name__ == "__main__":
    sys.exit(main())
