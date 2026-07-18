# mer-register.nl

Publiek doorzoekbaar register van **milieueffectrapportages (MER)** en het
bijbehorende m.e.r.-proces in Nederland.

## Waarom dit bestaat

De MER is juridisch een *"op het besluit betrekking hebbend stuk"*: het
onderbouwt een besluit (projectbesluit, omgevingsplan, vergunning) maar wordt
niet vastgesteld. Daardoor zit de MER **bewust niet in het DSO** — hij wordt
niet bekendgemaakt in het publicatieblad, alleen ~6 weken ter inzage gelegd, en
er is (nog) geen centrale voorziening voor die terinzagelegging. Het gevolg: het
belangrijkste milieudocument van een project is het **slechtst ontsloten stuk
van de keten**.

mer-register.nl brengt de verspreide bronnen samen tot één doorzoekbaar
register: de proces-events (KOOP) + de documenten zelf (Commissie m.e.r.).

Onderbouwing en juridische duiding staan in de kennisbank:
[`OmgevingswetKnowledgeBase/vault_v1/analysis/MER-register.nl — harvestbronnen en PoC.md`](../OmgevingswetKnowledgeBase/vault_v1/analysis/) +
gap **G-92** in `gaps.md`.

## Status

**Idee → PoC bewezen.** Twee harvestbronnen werken (2026-07-17). Nog geen
productie-datalaag en geen frontend. Zie [`docs/plan.md`](docs/plan.md).

## Architectuur (voorgesteld)

Zelfde patroon als [omgevingsvergunningenregister.nl](https://omgevingsvergunningenregister.nl):
**data in OCD, site standalone.**

```
  KOOP SRU-API ─┐                      ┌─ mer.event      (proces-events)
                ├─► dso-loader ─► OCD ─┤─ mer.project    (Commissie m.e.r.)
 Commissie m.e.r.┘   (loaders)  (schema├─ mer.document   (PDF-metadata)
                                 `mer`)└─ mer.*_link     (koppeling A↔B)
                                        │
                                        ▼
                              OCD-API  /v1/mer/*
                                        │
                                        ▼
                   mer-register.nl (deze repo) ── Cloudflare Pages
                   React SPA + Pages Function proxy (same-origin /api/*)
```

**Waarom data in OCD en niet standalone?** Kanaal A (KOOP SRU) is exact dezelfde
bron en API als `koop.vergunningkennisgeving` die al in OCD zit — de loader-,
ETL- en `core.bronhouder`-infrastructuur is herbruikbaar. De PDF's zelf gaan
níet de database in (alleen URL's; mirroren kan later naar R2 cold-storage).
Volledige afweging: [`docs/ocd-schema-voorstel.md`](docs/ocd-schema-voorstel.md).

## Repo-indeling

| Map | Inhoud |
|---|---|
| `docs/` | Projectdocumentatie: plan, PoC-inrichting, bron-inventarisatie, OCD-schema-voorstel, entity-koppeling, Claude-Design-prompt |
| `harvest/` | PoC-harvesters (stdlib-only Python). Productie-loaders migreren t.z.t. naar `OCD/dso-loader/` zodra het `mer`-schema is vastgelegd |
| `sql/` | DDL voor het voorgestelde `mer`-schema |
| `web/` | Frontend uit Claude Design (`MER-register.dc.html` + `support.js`-runtime) + het data-contract `mer-data.js` (nu mock; PoC genereert de echte versie) |

## Snel draaien (PoC)

```bash
cd harvest
python harvest_sru.py --max 100 [--since 2026-01-01]
python harvest_commissiemer.py --sample 12
```

Output belandt in `harvest/data/` (gitignored). Geen dependencies.

## Verwante projecten

- **[OCD]** — centrale databron + API (toekomstige `mer`-schema + `/v1/mer/*`)
- **[omgevingsvergunningenregister.nl]** — zusterproject, deelt de KOOP-SRU-bron en het deploy-patroon
- **[dso-implementatiemonitor.nl]** — mogelijke afnemer (MER-indicator)
- **[OmgevingswetKnowledgeBase]** — juridische onderbouwing
