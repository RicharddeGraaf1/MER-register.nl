# Inventarisatie harvestbronnen

Samenvatting van de vier onderzochte kanalen (empirisch getoetst 2026-07-17).
De volledige, geciteerde versie staat in de KB-vault:
`OmgevingswetKnowledgeBase/vault_v1/analysis/MER-register.nl — harvestbronnen en PoC.md`.

## Waarom de MER niet in het DSO zit

De MER is juridisch een **"op het besluit betrekking hebbend stuk"** (Toepassings­-
profiel projectbesluit §4.2.3): het onderbouwt het besluit maar wordt niet
vastgesteld. Daarom: geen bekendmaking in het publicatieblad, alleen
terinzagelegging (Awb 3:11/3:44, ~6 weken), en DSO-LV krijgt alleen
Regeling-onderdelen doorgeleverd. Er is geen centrale terinzage-voorziening
(gap G-92). Aanvraag-bijlagen (Omgevingsloket/STAM) zijn evenmin publiek.

## De vier kanalen

| # | Bron | Wat | Status |
|---|---|---|---|
| **A** | KOOP SRU-API (`repository.overheid.nl/sru`) | MER-*events*: voornemen/NRD, mer-beoordelingsbesluiten, terinzageleggingen, vaststellingen. Open, geen key. | ✅ bewezen |
| **B** | Commissie m.e.r. (`commissiemer.nl`) | De *documenten* zelf: 3.617 projecten via sitemaps + directe PDF's op `pas.commissiemer.nl`; 748 jurisprudentie-items. | ✅ bewezen |
| **C** | Besluit-XML (LVBB/KOOP) | `ExtRef`-links naar `open.overheid.nl/documenten/<uuid>` in projectbesluit-XML. | ✅ aangetoond |
| **D** | `open.overheid.nl` (Woo-index) | Doel van de terinzage-stukken; open zoek-API niet gevonden, robots restrictief. | ⚠️ te-verifiëren |

### Kanaal A — gemeten volumes (KOOP SRU)

| Query | Aantal |
|---|---|
| full-text "milieueffectrapport" | 12.035 |
| titel bevat milieueffectrapport(age) | 2.260 |
| full-text "mer-beoordelingsbesluit" | 1.272 |
| … Gemeenteblad | 3.831 |
| … Staatscourant | 4.589 |
| … Provinciaal blad | 956 |
| … Waterschapsblad | 355 |

Metadata per record: identifier, titel (event-type afleidbaar), datum,
`creator` = bevoegd gezag, publicatieblad, URL. Incrementeel op `dt.date`.
Zelfde API als `koop.vergunningkennisgeving` in OCD → infrastructuur herbruikbaar.

### Kanaal B — Commissie m.e.r.

Geen open API (WP REST dicht), maar volledige sitemaps (`advice-sitemap[1-4].xml`,
mét `<lastmod>` → incrementeel) en toestaande robots.txt. Per projectpagina:
titel, bevoegd gezag, initiatiefnemer, start advisering + directe PDF-links met
typeerbare suffixen (`…mer.pdf` = de MER zelf, `sn` = startnotitie, `vastrl` =
vastgestelde richtlijnen, `ts` = toetsingsadvies). `pas.commissiemer.nl` is de
facto het nationale MER-archief (terug tot de jaren '90).

**Dekking-kanttekening** ⚠️ te-verifiëren: onder de Ow lijkt het toetsingsadvies
alleen bij plan-m.e.r. verplicht en bij project-m.e.r. vrijwillig → de dekking
wordt voor recente project-MER'en selectiever.

## Bijvangst

- MER'en van Rijksprojecten duiken als **Kamerstuk-bijlage (`blg-…`) met directe
  PDF-URL** op in dezelfde KOOP-repository.
- Het ontsluitings-gat zelf ("belangrijkste milieudocument, slechtst ontsloten")
  is een publiceerbaar inzicht — data uit kanaal C meet het.
