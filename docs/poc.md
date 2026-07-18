# PoC-inrichting — welke data, welke stappen

## ✅ Uitgevoerd: 5 Amsterdamse trajecten (2026-07-17)

Draaiend bewijs via [`../harvest/poc_amsterdam.py`](../harvest/poc_amsterdam.py):
5 vooraf gekozen Amsterdamse MER-trajecten, ~6 requests totaal.

| Traject | Instrument | Events (A) | Documenten (B) |
|---|---|---|---|
| Haven-Stad | omgevingsplan | 6 (NRD 2016 → vaststelling 2022) | 5 (incl. `mer-haven-stad-hr.pdf`) |
| Programma Windenergie Amsterdam 2030 | programma | 3 (2023→2024→2025) | 4 (plan-MER + rd + ts) |
| Strandeiland (IJburg) | omgevingsplan | 1 (NRD 2019) | 4 |
| Zeeburgereiland / Sluisbuurt | bestemmingsplan | 2 | 5 (mer/sn/rl/ts) |
| Schinkelkwartier | omgevingsplan | 4 (NRD 2019 → vaststelling 2024) | 2 (rd+ts, MER nog niet gepubliceerd) |

Totaal 16 events + 20 documenten. **De join werkt voor alle 5**: elk traject
matcht een KOOP-eventreeks (kanaal A) aan een Commissie-m.e.r.-dossier (kanaal B).
Output → [`../web/mer-data.js`](../web/mer-data.js) in exact de ontwerp-vorm;
het bestaande Claude-ontwerp draait erop (`cd web && python -m http.server`).

**Wat dit bewees**: bronnen leveren · event-classificatie werkt op afgebakende
scope (na 2 fixes: ontwerp vóór vaststelling; beschrijvende Commissie-bestands­-
namen) · datashape past · UI draait op echte data. **Wat nog ruw is**: de
project↔event-koppeling gebruikt hier vaste ankers (5 bekende projecten), niet de
generieke blocking+scoring-join uit `entity-koppeling.md` — dat is de volgende
opschaal-stap. Ook: Amsterdam-brede coördinaten zijn per project benaderd.

---

## Generieke inrichting (voor opschaling)

## Doel van de PoC

Eén **verticale plak** die de hele keten bewijst op **echte data**:
harvest (kanaal A + B) → entity-koppeling → `mer-data.js` → het bestaande
Claude-ontwerp draait erop. Als dat werkt, is elk risico van het project
afgedekt: de bronnen leveren, de koppeling klopt, de datavorm past, de UI toont.

**De PoC draait standalone — géén OCD nodig.** Alles lokaal: harvest naar JSON,
join in Python, output een `mer-data.js`. De OCD-integratie (schema `mer`,
`/v1/mer/*`) is productie (Fase 2), niet de PoC. Zo blijft de PoC licht en raakt
de 76 GB-DB niet.

## De datavorm die we moeten produceren (uit het ontwerp)

Het ontwerp verwacht een lijst **trajecten**. Dit is meteen het join-doel:

```js
traject = {
  id,                    // slug
  titel,                 // projecttitel
  bevoegdGezag,          // "Provincie Groningen" / "Gemeente Deventer" / ministerie
  initiatiefnemer,       // wie het project trekt
  instrument,            // projectbesluit | omgevingsplan | omgevingsvergunning | ...
  provincie,             // voor de filter + schematische kaart
  coord: [lat, lon],     // benadering (BG-centroïde volstaat; kaart is schematisch)
  events: [              // ← kanaal A (KOOP): de proces-tijdlijn
    { datum, type, blad, link }
  ],
  documenten: [          // ← kanaal B (Commissie m.e.r.): de PDF's
    { soort, titel, link }
  ],
}
```

Cruciaal: **niet elk traject heeft beide.** Sommige zijn alleen events (kort ter
inzage, geen Commissie-dossier), sommige alleen documenten (oud project),
sommige compleet. Die onvolledigheid ís het verhaal — de PoC moet alle drie de
gevallen op echte data laten zien.

## Welke data — scope-aanbeveling

Neem een **afgebakende maar rijke** scope, zodat de koppeling échte overlap heeft
om te bewijzen (niet twee bronnen die elkaar nooit raken):

> **Aanbeveling: alle MER-trajecten met bevoegd gezag = provincie / Rijk /
> waterschap, periode 2020–2026.**

Waarom deze snit:
- Provinciale/Rijks/waterschaps-projecten (windparken, wegen, dijken, industrie)
  zijn juist de projecten die **én** in KOOP-events **én** in de
  Commissie-m.e.r.-database zitten → de join is aantoonbaar.
- Overzichtelijk volume (honderden, geen tienduizenden) → handmatig te ijken.
- Gemeentelijke trajecten (vaak alleen event, geen Commissie-dossier) neem je als
  **contrast-set** mee om de "alleen events"-onvolledigheid te tonen.

Alternatief smaller: één provincie (bv. Groningen — windparken N33/Fryslân-achtig,
al in de mock present) voor een eerste snelle iteratie.

## Drie stappen

### Stap A — events harvesten (kanaal A, KOOP SRU)
`harvest_sru.py` bestaat al. Voor de PoC:
- Query: titel-hits op milieueffectrapport(age), gefilterd op publicatieblad
  (`Provinciaal blad`, `Staatscourant`, `Waterschapsblad`) + periode.
- Per record → `{ koop_id, titel, datum, blad, bevoegd_gezag, event_type,
  instrument, url }`.
- **event_type** afleiden uit de titel (voornemen/NRD · mer-beoordeling ·
  mer-beoordeling: geen MER nodig · terinzage MER · vaststelling met MER). De
  huidige regex is grof; voor de PoC-scope aanscherpen of een kleine
  hand-review doen (de scope is klein genoeg).

### Stap B — projecten + documenten harvesten (kanaal B, Commissie m.e.r.)
`harvest_commissiemer.py` bestaat al. Voor de PoC:
- Volledige sitemap-inventaris, dan de projectpagina's binnen scope scrapen
  (filter op bevoegd gezag / periode via `start_advisering`).
- Per project → `{ project_nr, titel, bevoegd_gezag, initiatiefnemer,
  start_advisering, documenten:[{soort, titel, url}] }`.
- **doc-soort** uit de bestandsnaam-suffix (`…mer.pdf`→MER, `sn`→startnotitie,
  `vastrl`→richtlijnen, `ts`→toetsingsadvies).

### Stap C — koppelen → `mer-data.js`
Nieuw scriptje `build_trajecten.py` (zie `entity-koppeling.md` voor de logica):
1. **Blokkeer** op bevoegd gezag + tijdvenster (events vs. `start_advisering`
   ±24 mnd).
2. **Score** op titel-trigram-gelijkenis na stopwoord-/boilerplate-stripping.
3. Boven drempel → één traject met events (A) + documenten (B); grijze zone →
   markeren voor hand-review; events zonder match → traject-met-alleen-events;
   Commissie-projecten zonder match → traject-met-alleen-documenten.
4. **coord**: bevoegd-gezag-naam → centroïde via een kleine lookup (PDOK
   Locatieserver of een statische gemeente/provincie-centroïdentabel — de kaart
   is schematisch, dus benadering volstaat).
5. Emit exact de `trajecten`-array + de `EVENT_TYPES/INSTRUMENTEN/DOC_SOORTEN/
   PROVINCIES`-constanten → `web/mer-data.js`.

### Resultaat
Vervang de mock-`mer-data.js` door de gegenereerde en open het ontwerp lokaal.
Werkt de UI met echte trajecten (inclusief de onvolledige), dan is de PoC
geslaagd.

## Wat de PoC bewijst — en wat hij bewust uitstelt

**Bewijst**: bronnen leveren · classificatie werkbaar op afgebakende scope ·
**de koppeling A↔B werkt** (het echte risico) · datavorm past op het ontwerp ·
UI draait op echte data.

**Stelt uit** (productie, ná PoC-akkoord):
- OCD-schema `mer` + loaders in `dso-loader` (Fase 2).
- `/v1/mer/*`-API + Cloudflare-deploy (Fase 4–5).
- Landelijke dekking, incrementele sync, event-classificatie op schaal (evt. LLM).
- Kanaal C (ExtRef-link-oogst) en D (Woo-index) verificatie.

## Validatie (meet-discipline)

Label handmatig ~20–30 bekende koppelingen als gouden set; meet precisie/recall
van de join vóór de drempel vast te zetten. Sanity-check: mediaan-tijdverschil
tussen Commissie-`start_advisering` en eerste KOOP-event moet klein en stabiel
zijn. (Zelfde discipline als de doorlooptijd-tweetrapsmatch in
omgevingsvergunningenregister.nl.)
