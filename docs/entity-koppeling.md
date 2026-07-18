# Entity-koppeling — kanaal A ↔ B

Het echte werk achter mer-register.nl: hetzelfde m.e.r.-traject herkennen in
**kanaal A** (KOOP-events, per bevoegd gezag, per publicatie) én **kanaal B**
(Commissie m.e.r.-projectdatabase). Pas als die koppeling er is, draagt één
register-item de volledige keten: voornemen → beoordeling → MER-document →
terinzage → vaststelling.

## Waarom het niet triviaal is

- **Geen gedeelde sleutel.** KOOP-events hebben `koop_id` (`gmb-2026-…`);
  Commissie-projecten hebben een `project_nr`. Niets verbindt ze hard.
- **Verschillende granulariteit.** Eén Commissie-project (bv. "Windpark
  Nederwiek I-B") kan corresponderen met meerdere KOOP-events (voornemen,
  beoordeling, vaststelling) verspreid over maanden en publicatiebladen.
- **Naam-variatie.** "Windpark Nederwiek I-B" vs. "Kennisgeving milieueffect­-
  rapport windpark Nederwiek fase I" — zelfde project, andere string.
- **Onvolledige overlap.** Veel gemeentelijke project-MER'en zonder
  Commissie-betrokkenheid bestaan *alleen* als KOOP-event. Andersom staan oude
  projecten (jaren '90) wel in de Commissie-database maar niet in KOOP. De
  koppeling is dus per definitie partieel — dat is een feature (het toont het
  ontsluitings-gat), geen bug.

## Voorgestelde matching-aanpak (blokkeren → scoren)

1. **Blokkeren op bevoegd gezag + periode.** Resolveer beide kanten naar
   `core.bronhouder`. Beperk kandidaat-paren tot zelfde BG (of BG-cluster) en
   een tijdvenster rond `start_advisering` (Commissie) vs. `datum_publicatie`
   (KOOP), bv. ±24 maanden. Dit snoeit het kruisproduct drastisch.
2. **Scoren op titel-gelijkenis.** Binnen een blok: genormaliseerde
   token-overlap / trigram-similariteit (`pg_trgm`) tussen projecttitel en
   event-titel, na verwijderen van stopwoorden en boilerplate ("kennisgeving",
   "milieueffectrapport", "ter inzage", "ontwerp").
3. **Drempel + `zekerheid`.** Boven een harde drempel automatisch koppelen
   (`match_methode='naam+bg+periode'`, `zekerheid`=score); grijze zone
   markeren voor handmatige review; daaronder verwerpen.
4. **Anker via documentnamen (optioneel).** Commissie-PDF's dragen een
   projectnummer in het pad; als een KOOP-event naar `pas.commissiemer.nl`
   linkt (soms in de body), is dat een harde match — voorrang boven de score.

## Validatie

- Handmatig een gouden setje van ~30 bekende koppelingen labelen; precisie/recall
  meten vóór de drempel vast te zetten (zelfde discipline als de
  doorlooptijd-tweetrapsmatch in omgevingsvergunningenregister.nl).
- Mediaan-tijdverschil tussen gekoppelde Commissie-start en eerste KOOP-event
  als sanity-check (moet klein en stabiel zijn).

## Eerst lokaal

Beproef de logica op de bestaande PoC-output (`harvest/data/sru_events.json` +
`harvest/data/commissiemer_projects.json`) vóór het een `dso-loader`-stap wordt.
Pas als de matching overtuigt gaat `mer.project_event_link` de productie in.
