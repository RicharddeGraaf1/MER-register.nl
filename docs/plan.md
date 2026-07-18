# Plan — mer-register.nl

## Waar we staan (2026-07-17)

PoC-fase afgerond. Twee harvestbronnen bewezen werkend. Nog geen productie-datalaag,
geen frontend. Dit is een **gevalideerd idee met werkende prototypes**.

## Fasering

### Fase 0 — PoC ✅ klaar
- Vier kanalen empirisch getoetst, twee bewezen (KOOP SRU + Commissie m.e.r.).
- Harvesters in `harvest/`. Onderbouwing in de KB-vault (analysepagina + G-92).

### Fase 1 — Datamodel-akkoord · prio: hoog
- **`mer`-schema in OCD** vastleggen (zie `ocd-schema-voorstel.md` + `../sql/mer-schema.sql`).
- Beslissing bevestigen: datalaag in OCD, PDF's extern, site standalone.
- Modelimpact naar de KB-vault (§15-voorstel).

### Fase 2 — Productie-loaders · prio: hoog
- `harvest_sru.py` → `OCD/dso-loader/src/loaders/mer_sru.py` (deelt SRU-client
  met de `koop`-loader, incrementeel via `vth.etl_run`).
- `harvest_commissiemer.py` → `OCD/dso-loader/src/loaders/mer_commissie.py`
  (incrementeel via sitemap `<lastmod>`).
- Bronhouder-resolutie op `core.bronhouder`.
- Event-classificatie verbeteren (regels + evt. LLM-pass build-time).

### Fase 3 — Entity-koppeling · prio: hoog
- Kanaal A ↔ B matchen (`mer.project_event_link`). Zie `entity-koppeling.md`.
- Eerst lokaal beproeven op de PoC-datasets vóór de logica in een loader gaat.

### Fase 4 — API · prio: midden
- `/v1/mer/*`-endpoints in `ocd-api` (lijst + facets + detail + stats), zelfde
  patroon als `/v1/vergunningen/*`.

### Fase 5 — Frontend · prio: midden
- Ontwerp via Claude Design (`claude-design-prompt.md`).
- React SPA in `web/`, Cloudflare Pages + Pages-Function-proxy (patroon uit
  omgevingsvergunningenregister.nl).
- Domein registreren + koppelen.

### Fase 6 — Verrijking · prio: laag
- Kanaal C (ExtRef-link-oogst uit besluit-XML) als ontsluitings-signaal.
- Kanaal D (Woo-voorziening open.overheid.nl) verifiëren (⚠️ te-verifiëren).
- MER-indicator aanbieden aan dso-implementatiemonitor.nl.

## Openstaande beslissingen

1. **Domeinnaam** — `mer-register.nl` registreren? (nog niet gedaan)
2. **Productvorm** — los product of venster op dso-implementatiemonitor.nl?
   (huidige richting: los, maar met cross-links)
3. **PDF-mirroring** — nu niet; overwegen bij Fase 6 (R2 cold-storage,
   hergebruikregime overheidsdocumenten checken).
