"""Gedeelde harvest-laag voor mer-register.nl: beleefde HTTP met 429-detectie,
adaptieve throttling, en SQLite-helpers.

429-beleid (conform gebruikersinstructie "stop of verlaag frequentie"):
- op HTTP 429/503: respecteer Retry-After indien aanwezig, anders exponentiële
  backoff (30s, 60s, 120s, ...);
- verhoog daarna de basis-vertraging blijvend (adaptief afremmen);
- na MAX_STRIKES opeenvolgende 429/503's: stop met een RateLimited-exception,
  zodat de aanroeper netjes kan afbreken (de harvest is resumable).
"""
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "mer-register-harvester/1.0 (+https://mer-register.nl; contact: richard.de.graaf@conteo-consulting.nl)"}
HERE = Path(__file__).parent
DB_PATH = HERE / "data" / "mer.db"

MAX_STRIKES = 5
_state = {"delay_bump": 0.0}   # adaptieve extra vertraging, groeit bij 429's


class RateLimited(Exception):
    """Aanhoudende 429/503 — de aanroeper hoort te stoppen en later te hervatten."""


def _sleep(base):
    time.sleep(base + _state["delay_bump"])


def http_get(url, base_delay=1.0, timeout=60):
    """GET met beleefde vertraging en 429/503-backoff. Retourneert tekst.
    Gooit RateLimited na aanhoudende throttling."""
    strikes = 0
    while True:
        _sleep(base_delay)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                strikes += 1
                if strikes >= MAX_STRIKES:
                    raise RateLimited(f"{e.code} na {strikes} pogingen op {url}")
                retry_after = e.headers.get("Retry-After")
                wait = int(retry_after) if (retry_after or "").isdigit() else 30 * (2 ** (strikes - 1))
                _state["delay_bump"] = min(_state["delay_bump"] + 0.5, 5.0)  # blijvend afremmen
                print(f"  ! {e.code} — backoff {wait}s (strike {strikes}/{MAX_STRIKES}, "
                      f"basisvertraging nu +{_state['delay_bump']:.1f}s)")
                time.sleep(wait)
                continue
            raise
        except (TimeoutError, urllib.error.URLError) as e:
            # Sinds 2026-09-13. Hiervoor ving deze lus alleen HTTPError, en een
            # socket-timeout glipte er dus langs: load_events.py viel om op
            # pagina 1250 van 2266 met "The read operation timed out" en liet de
            # harvest halverwege staan. `stand.py` meldt dan ACHTER, niet "de
            # vorige poging is geklapt" -- en zo liep kanaal A dagen achter
            # zonder dat iemand het zag.
            #
            # Dit is de spiegel van de noodrem in de OCD-loader: daar ging het om
            # te lang doorgaan met een fout die niet overgaat, hier om te vroeg
            # stoppen bij een fout die dat wel doet. Een retry-lus hoort dat
            # onderscheid te maken.
            #
            # Let op: HTTPError is een subklasse van URLError, dus deze except
            # MOET onder die van HTTPError staan -- anders vangt hij de 429/503
            # weg en verdwijnt de Retry-After-afhandeling.
            strikes += 1
            if strikes >= MAX_STRIKES:
                raise RateLimited(f"{type(e).__name__} na {strikes} pogingen op {url}")
            wait = 5 * strikes
            print(f"  ! {type(e).__name__} — opnieuw over {wait}s "
                  f"(poging {strikes}/{MAX_STRIKES})")
            time.sleep(wait)
            continue


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 30000")   # wacht i.p.v. 'database is locked' bij parallelle loader
    return con


def init_schema(con):
    con.executescript((HERE / "schema_sqlite.sql").read_text(encoding="utf-8"))
    con.commit()


def set_state(con, bron, cursor):
    con.execute("INSERT INTO harvest_state(bron,cursor,laatste_run) VALUES(?,?,datetime('now')) "
                "ON CONFLICT(bron) DO UPDATE SET cursor=excluded.cursor, laatste_run=excluded.laatste_run",
                (bron, cursor))
    con.commit()


def get_state(con, bron):
    row = con.execute("SELECT cursor FROM harvest_state WHERE bron=?", (bron,)).fetchone()
    return row[0] if row else None
