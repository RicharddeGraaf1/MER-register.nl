-- schema_sqlite.sql — harvest-store voor mer-register.nl.
-- Materialiseert het goedgekeurde `mer`-schema in SQLite. Dit is de HARVEST-laag;
-- hij laadt later 1-op-1 in OCD-Postgres (schema `mer`). Verschillen t.o.v.
-- ../sql/mer-schema.sql zijn bewust en klein:
--   * geen cross-schema FK's (core.bronhouder / vth.etl_run bestaan hier niet);
--     bronhouder_id blijft NULL tot de OCD-load.
--   * project heeft `slug` als natuurlijke sleutel (altijd aanwezig); project_nr
--     is een nullable kolom (niet elk Commissie-project heeft PDF's → geen nummer).

CREATE TABLE IF NOT EXISTS event (
    koop_id            TEXT PRIMARY KEY,
    titel              TEXT NOT NULL,
    datum_publicatie   TEXT,
    publicatieblad     TEXT,
    bevoegd_gezag_naam TEXT,
    bronhouder_id      INTEGER,
    event_type         TEXT,
    instrument         TEXT,
    subject_taxonomie  TEXT,
    url                TEXT,
    inhoud_tekst       TEXT,
    raw_xml            TEXT,
    ingest_run_id      INTEGER,
    datum_ingest       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_event_datum      ON event (datum_publicatie DESC);
CREATE INDEX IF NOT EXISTS idx_event_type       ON event (event_type);
CREATE INDEX IF NOT EXISTS idx_event_bg         ON event (bevoegd_gezag_naam);

CREATE TABLE IF NOT EXISTS project (
    slug             TEXT PRIMARY KEY,
    project_nr       INTEGER,
    titel            TEXT NOT NULL,
    bevoegd_gezag    TEXT,
    bronhouder_id    INTEGER,
    initiatiefnemer  TEXT,
    start_advisering TEXT,
    advies_type      TEXT,
    url              TEXT,
    lastmod          TEXT,
    datum_ingest     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_project_bg ON project (bevoegd_gezag);

CREATE TABLE IF NOT EXISTS document (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_slug  TEXT NOT NULL REFERENCES project (slug) ON DELETE CASCADE,
    soort         TEXT,
    bestandsnaam  TEXT,
    url           TEXT NOT NULL,
    mirror_url    TEXT,
    datum_ingest  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_slug, bestandsnaam)
);
CREATE INDEX IF NOT EXISTS idx_document_project ON document (project_slug);

CREATE TABLE IF NOT EXISTS project_event_link (
    project_slug  TEXT NOT NULL REFERENCES project (slug) ON DELETE CASCADE,
    koop_id       TEXT NOT NULL REFERENCES event (koop_id) ON DELETE CASCADE,
    match_methode TEXT,
    zekerheid     REAL,
    datum_ingest  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (project_slug, koop_id)
);

CREATE TABLE IF NOT EXISTS besluit_extref (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    besluit_work  TEXT NOT NULL,
    extref_url    TEXT NOT NULL,
    doel_soort    TEXT,
    datum_ingest  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (besluit_work, extref_url)
);

-- Geocache voor bevoegd-gezag-centroïden (PDOK Locatieserver), voor de export.
CREATE TABLE IF NOT EXISTS geocache (
    naam       TEXT PRIMARY KEY,
    lat        REAL,
    lon        REAL,
    provincie  TEXT,
    bron       TEXT
);

-- Resumability / voortgang per bron.
CREATE TABLE IF NOT EXISTS harvest_state (
    bron        TEXT PRIMARY KEY,
    cursor      TEXT,
    laatste_run TEXT
);
