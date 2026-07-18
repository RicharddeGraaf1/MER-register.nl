# OCD-schema-voorstel + afweging OCD-vs-standalone

## 1. De vraag: in OCD of los?

mer-register.nl heeft een datalaag nodig. Twee opties: een nieuw `mer`-schema
**in de bestaande OCD-database**, of een **zelfstandige database** voor dit
project.

### Aanbeveling: **hybride — datalaag in OCD, PDF's + site erbuiten**

| Overweging | In OCD | Standalone |
|---|---|---|
| **Kanaal A = zelfde bron als `koop`** | ✅ SRU-client, `vth.etl_run`-ETL-patroon en `core.bronhouder`-join zijn 1-op-1 herbruikbaar | ❌ alles opnieuw bouwen |
| **Bevoegd-gezag-join** | ✅ `core.bronhouder` bestaat al; MER-events koppelen aan dezelfde autoriteit als vergunningen/pons → cross-analyse gratis | ❌ eigen BG-tabel + matching |
| **API-laag** | ✅ OCD-API (Railway) + Pages-Function-proxy is het beproefde patroon voor álle viewers; `/v1/mer/*` erbij | ❌ eigen API + hosting |
| **Afnemers** | ✅ dso-implementatiemonitor.nl leest al uit OCD → MER-indicator slot-in | ➖ |
| **DB-omvang** | ⚠️ OCD is 76 GB en er is een actief "klein houden"-traject | ✅ eigen kleine DB |
| **Conceptuele zuiverheid** | ⚠️ "OCD = DSO-content", MER zit *niet* in DSO... | ✅ los = schoon |

Het zuiverheidsbezwaar (laatste rij) is zwak: OCD host in `koop`/`vth` **al**
niet-DSO-data uit precies dezelfde KOOP-bron. De MER-events zijn daarvan het
directe zusje. De omvang-zorg wordt opgevangen door **de PDF's buiten Postgres
te houden** (alleen URL's; mirroren kan later naar R2 cold-storage per de
opslagstrategie).

**Concreet:**

- **Datalaag → OCD**, nieuw schema `mer` (loaders in `dso-loader`, endpoints
  `/v1/mer/*` in `ocd-api`).
- **PDF-documenten → niet in de DB.** `mer.document` bewaart URL + metadata;
  fysiek mirroren (indien ooit nodig) naar R2, referentie via `mirror_url`.
- **Frontend → deze repo**, standalone op Cloudflare Pages (zoals
  omgevingsvergunningenregister.nl).

Dit is exact het model van omgevingsvergunningenregister.nl: data in OCD
(`koop`/`vth`), site in eigen repo. We volgen een bewezen pad.

## 2. Voorgesteld `mer`-schema

Vijf tabellen. `bron`-conventie volgt de KB-vault (`gebruiker` /
`agent-inferred` / `te-verifiëren`); alle afgeleide velden starten als
`agent-inferred` tot geverifieerd. Volledige DDL in
[`../sql/mer-schema.sql`](../sql/mer-schema.sql).

### `mer.event` — proces-events (kanaal A, KOOP SRU)
De ruggengraat: elke publicatie waarin een MER figureert. Deelt het
identifier-patroon met `koop.vergunningkennisgeving` (`gmb-2026-…`).

| kolom | type | herkomst |
|---|---|---|
| `koop_id` | text PK | KOOP `dcterms:identifier` |
| `titel` | text | `dcterms:title` |
| `datum_publicatie` | date | `dcterms:date` |
| `publicatieblad` | text | `overheidwetgeving:publicatienaam` |
| `bevoegd_gezag_naam` | text | `dcterms:creator` (rauw) |
| `bronhouder_id` | int FK → `core.bronhouder` | opgelost (nullable: Rijk/buitenland) |
| `event_type` | text | **afgeleid** uit titel (zie classificatie) |
| `instrument` | text | **afgeleid** uit titel |
| `subject_taxonomie` | text | `dcterms:subject` |
| `url` | text | `gzd:preferredUrl` |
| `inhoud_tekst` | text | body (optioneel, voor herclassificatie — als `koop`) |
| `raw_xml` | text | ruwe record (optioneel) |
| `ingest_run_id` | int FK → `vth.etl_run` | ETL-patroon |
| `datum_ingest` | timestamptz | |

### `mer.project` — Commissie m.e.r.-projecten (kanaal B)
| kolom | type | herkomst |
|---|---|---|
| `project_nr` | int PK | `pas.commissiemer.nl`-nummer |
| `slug` | text | URL-slug |
| `titel` | text | `<h1>` |
| `bevoegd_gezag` | text | projectpagina (rauw) |
| `bronhouder_id` | int FK → `core.bronhouder` | opgelost (nullable) |
| `initiatiefnemer` | text | projectpagina |
| `start_advisering` | date | projectpagina |
| `advies_type` | text | **afgeleid**: plan-mer / project-mer (⚠️ te-verifiëren onder Ow) |
| `url` | text | projectpagina |
| `lastmod` | timestamptz | sitemap (incrementeel) |
| `datum_ingest` | timestamptz | |

### `mer.document` — documenten bij een project (kanaal B)
De PDF's zelf blijven **extern**; hier alleen metadata + URL.

| kolom | type | herkomst |
|---|---|---|
| `id` | bigserial PK | |
| `project_nr` | int FK → `mer.project` | |
| `soort` | text | **afgeleid** uit bestandsnaam-suffix (MER / MER-bijlage / startnotitie / richtlijnen / toetsingsadvies / reikwijdte-detailniveau / overig) |
| `bestandsnaam` | text | |
| `url` | text | `pas.commissiemer.nl/files/…` |
| `mirror_url` | text NULL | R2, alleen indien gemirrord |
| `datum_ingest` | timestamptz | |

### `mer.project_event_link` — koppeling kanaal A ↔ B
Het echte werk (zie [`entity-koppeling.md`](entity-koppeling.md)). Een
Commissie-project ↔ zijn KOOP-events.

| kolom | type |
|---|---|
| `project_nr` | int FK → `mer.project` |
| `koop_id` | text FK → `mer.event` |
| `match_methode` | text (naam+bg+periode / handmatig / …) |
| `zekerheid` | numeric (0–1) |
| PK | (`project_nr`, `koop_id`) |

### `mer.besluit_extref` — link-oogst uit besluit-XML (kanaal C, optioneel)
Waar linkt een projectbesluit zijn terinzage-stukken naartoe? Meetbaar signaal
voor "welk BG ontsluit werkelijk".

| kolom | type |
|---|---|
| `id` | bigserial PK |
| `besluit_work` | text (FRBR work van het projectbesluit) |
| `extref_url` | text |
| `doel_soort` | text (open.overheid.nl-uuid / eigen-website / overig) |
| `datum_ingest` | timestamptz |

## 3. Event-classificatie (afgeleide velden)

`event_type` en `instrument` worden uit de titel afgeleid. De PoC doet dit met
regex (grof: ~65% "overig" op Kamerstuk-ruis). Productie-richting: strakkere
regels + optioneel een LLM-classificatie-pass (build-time, zoals de
vergunningkennisgevingen-pipeline). Waardelijst-voorstel:

- `event_type`: `voornemen-nrd` · `mer-beoordeling` · `mer-beoordeling-geen-mer`
  · `terinzage-mer` · `vaststelling-met-mer` · `overig`
- `instrument`: `projectbesluit` · `omgevingsplan` · `omgevingsvergunning`
  · `bestemmingsplan` · `omgevingsvisie` · `programma` · `overig`

## 4. Modelimpact (KB-vault)

De MER is geen beschikking, maar hoort qua "parallelle publicatiewereld naast
STOP/IMOW" bij dezelfde familie als [[model]] §14 (Pilaar 6 Beschikkingen).
Voorstel voor de vault: een eigen sectie (§15 "Milieueffectrapportage /
terinzage-stukken") met classes `MERproces-event`, `MERproject`, `MERdocument`,
allen `bron: te-verifiëren` tot bevestigd. Dit is een **KB-vault-actie**, los van
deze repo — hier alleen genoteerd zodat het niet zoekraakt.
