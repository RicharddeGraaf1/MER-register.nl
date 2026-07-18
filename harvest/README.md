# harvest/ — MER-harvestpijplijn

Vult het goedgekeurde `mer`-schema nationaal. Stdlib-only Python (geen
dependencies). Data landt in een lokale SQLite-store `data/mer.db` (= de
harvest-laag; laadt later 1-op-1 in OCD-Postgres, schema `mer`).

## Nationale pijplijn (draai in deze volgorde)

```bash
python load_events.py         # kanaal A: KOOP SRU  -> tabel event   (~2.260 events)
python load_commissie.py      # kanaal B: Commissie -> project+document (~3.617 projecten, ~1u, resumable)
python build_links.py         # koppel A<->B         -> project_event_link
python export_mer_data.py     # bouw trajecten       -> ../web/mer-data.js
```

- **`lib.py`** — gedeelde HTTP (beleefd, 429-adaptief: bij aanhoudende 429/503
  remt af en stopt netjes) + SQLite-helpers.
- **`schema_sqlite.sql`** — het `mer`-schema in SQLite (harvest-variant van
  [`../sql/mer-schema.sql`](../sql/mer-schema.sql)).
- `load_commissie.py` is **resumable**: al gescrapete projecten worden
  overgeslagen; bij een 429-stop gewoon opnieuw draaien.
- `poc_amsterdam.py` blijft als de oorspronkelijke 5-projecten-PoC (vaste ankers).

Productie later: deze loaders migreren naar `OCD/dso-loader/src/loaders/` (net als
de `koop`-loader, waarmee `load_events.py` de SRU-client deelt) en schrijven dan
naar OCD-Postgres i.p.v. SQLite; `bronhouder_id` wordt daar geresolveerd.

---

## Oorspronkelijke PoC-verkenners

`harvest_sru.py` + `harvest_commissiemer.py` waren de eerste losse verkenners
(schrijven JSON, geen DB). Vervangen door de pijplijn hierboven; bewaard als
referentie.

## Kanalen

1. **`harvest_sru.py`** — officielebekendmakingen.nl (KOOP SRU-API, open, geen key).
   MER-*events*: kennisgevingen voornemen/NRD, mer-beoordelingsbesluiten,
   terinzageleggingen, vaststellingen. ~2.260 records met MER in de titel,
   ~12.000 full-text. Incrementeel via `--since YYYY-MM-DD`.
2. **`harvest_commissiemer.py`** — Commissie m.e.r. (sitemaps + projectpagina's).
   3.617 projecten met metadata (bevoegd gezag, initiatiefnemer, start advisering)
   en directe PDF's op `pas.commissiemer.nl/files/nl/<nr>/…` — inclusief de
   **MER'en zelf**, startnotities, richtlijnen en toetsingsadviezen.
   Plus 748 jurisprudentie-items (`case-law-sitemap.xml`).

## Draaien

```bash
python harvest_sru.py --max 100 [--since 2026-01-01]
python harvest_commissiemer.py --sample 12
```

Output in `data/*.json` (gitignored).

## Bekende PoC-beperkingen

- Event-classificatie in `harvest_sru.py` is regex-grof (~65% "overig" op
  Kamerstuk-ruis); productie: betere regels of LLM-classificatie (zoals de
  vergunningkennisgevingen-pipeline). Zie `../docs/entity-koppeling.md`.
- `doc_type`-mapping in `harvest_commissiemer.py` dekt nog niet alle
  bestandssuffixen ("onbekend").
- Koppeling tussen beide bronnen (kanaal A↔B) is nog niet gebouwd — ontwerp in
  `../docs/entity-koppeling.md`.
