# Claude Design-prompt — mer-register.nl UI

> Plak de tekst hieronder (vanaf "PROMPT") in Claude Design. Hij is zelfstandig
> leesbaar: context, data, schermen, interacties en visuele richting. Pas
> gerust aan; de datavelden komen 1-op-1 uit `../sql/mer-schema.sql`.

---

## PROMPT

Ontwerp de UI voor **mer-register.nl** — een publiek, gratis, doorzoekbaar
register van milieueffectrapportages (MER) en het bijbehorende m.e.r.-proces in
Nederland. Zero-build React SPA (single-file, CDN-imports), geen login, geen
cookies. Nederlandstalig.

### Waarom dit register bestaat (het verhaal dat de UI moet dragen)

Een MER is het belangrijkste milieudocument onder een groot ruimtelijk besluit,
maar juridisch een "op het besluit betrekking hebbend stuk": het wordt niet
vastgesteld en zit daarom **bewust niet in het landelijke DSO/Omgevingsloket**.
Het wordt alleen ~6 weken ter inzage gelegd en er is geen centrale plek. Gevolg:
het best onderbouwde milieudocument van een project is het **slechtst
ontsloten** stuk van de keten. mer-register.nl brengt de verspreide sporen samen.
De toon is dus: **helder, betrouwbaar, "eindelijk op één plek"** — een publieke
voorziening, geen commercieel product.

### Doelgroepen

- Omwonenden / belanghebbenden die willen weten of er een MER loopt in hun buurt.
- Journalisten, adviseurs, juristen, ambtenaren, onderzoekers.
- Iedereen die het *proces* wil volgen: van eerste voornemen tot vaststelling.

### De data (dit toont de UI)

Twee samengevoegde bronnen, gekoppeld tot één "traject" per project:

1. **Proces-events** (uit officiële bekendmakingen): elke publicatie met een
   MER-stap. Velden: titel, datum, publicatieblad, **bevoegd gezag**,
   **event-type** en **instrument** (zie waardelijsten), link naar de
   officiële publicatie.
   - event-type: `voornemen/NRD` · `mer-beoordeling` · `mer-beoordeling: geen
     MER nodig` · `terinzage MER` · `vaststelling met MER`
   - instrument: `projectbesluit` · `omgevingsplan` · `omgevingsvergunning` ·
     `bestemmingsplan` · `omgevingsvisie` · `programma`
2. **Projecten met documenten** (uit de Commissie m.e.r.): titel, bevoegd
   gezag, initiatiefnemer, startdatum advisering, en een set **downloadbare
   PDF's** met soort: `MER` · `MER-bijlage` · `startnotitie` · `richtlijnen` ·
   `toetsingsadvies`.

Eén register-item ("traject") = een project + zijn events (tijdlijn) + zijn
documenten. Niet elk traject heeft beide: sommige zijn alleen event (kort ter
inzage, geen Commissie-dossier), sommige alleen document-dossier. **Maak die
onvolledigheid zichtbaar** — het is de kern van het verhaal.

### Schermen

**1. Register (hoofdscherm) — drie zones:**
- **Links: filters.** Bevoegd gezag (zoekbaar), instrument, event-type,
  documentsoort (heeft MER-PDF ja/nee), periode (jaar-range), provincie, en een
  vrije-tekst-zoekbalk bovenaan. Toon actieve filters als chips.
- **Midden: resultaten.** Wisselbaar tussen **lijst** en **kaart** (pins per
  bevoegd gezag/locatie). Lijstitem = trajecttitel + BG + laatste processtap +
  datum + kleine iconen die tonen welke documenten beschikbaar zijn (MER /
  toetsingsadvies / …). Gepagineerd.
- **Rechts (of overlay): detail** van een geselecteerd traject — zie scherm 2.

**2. Trajectdetail — het onderscheidende scherm.** Dit is waar MER-register zich
onderscheidt van een gewone documentenlijst:
- Kop: projecttitel, bevoegd gezag, initiatiefnemer, instrument.
- **Proces-tijdlijn** (horizontaal of verticaal): de m.e.r.-stappen in
  chronologische volgorde — voornemen/NRD → mer-beoordeling → MER ter inzage →
  vaststelling — met per stap datum + link naar de officiële publicatie. Toon
  duidelijk welke stappen **ontbreken/onbekend** zijn (het gat).
- **Documenten**: downloadbare PDF's gegroepeerd per soort, met de MER
  prominent. Elk opent in nieuwe tab (extern gehost).
- Deeplink naar de officiële bekendmaking(en) en naar de Commissie-m.e.r.-pagina.

**3. Cijfers/overzicht (klein dashboard, secundair).** Omdat het verhaal over
*ontsluiting* gaat: een compacte pagina met tellingen — MER-trajecten per jaar,
per instrument, per provincie; aandeel trajecten mét vs. zónder beschikbare
MER-PDF (het ontsluitings-signaal). KPI-tegels + één of twee eerlijke grafieken.
Geen overladen dashboard.

### Interactie / gedrag

- URL-state in de query-string (filters + geselecteerd traject) zodat een view
  deelbaar is.
- Debounced zoeken, laadt vlot; werkt op mobiel (filters inklapbaar).
- Kaart optioneel/lazy — de lijst is de primaire modus.
- Toegankelijk (WCAG): toetsenbord-navigeerbaar, contrast, aria-labels.

### Visuele richting

Onderdeel van een familie civic-tech-viewers (omgevingsvergunningenregister.nl,
ponsenkaart.nl). Sluit visueel aan zonder te klonen:
- Rustig, warmwit canvas (~`#FAFAF7`), donkergroen accent (~`#0F4A37`); voel je
  vrij een tweede accent te kiezen dat bij "milieu/effect" past.
- Zakelijk-vertrouwd, overheids-neutraal maar niet saai; heldere typografie,
  royale witruimte, data leesbaar vooropgesteld.
- De **proces-tijdlijn** is het signatuur-element — besteed daar de meeste
  ontwerp-aandacht aan.
- Basemap voor de kaart: PDOK BRT-grijs (publiek), pins in het accent.

### Technische randvoorwaarden

- Single-file React (18) + Tailwind (Play CDN) + MapLibre GL voor de kaart +
  proj4 (RD↔WGS84) indien nodig. Geen build-step in de eerste versie.
- Data komt straks van een eigen API (`/v1/mer/*`); ontwerp tegen realistische
  voorbeelddata (verzin 15–20 plausibele trajecten met Nederlandse
  bevoegde-gezag-namen, gemengde instrumenten en gedeeltelijke tijdlijnen).
- Lever de mock-data apart zodat die makkelijk door echte API-calls te
  vervangen is.

### Wat expliciet NIET moet

- Geen fake-officiële uitstraling of rijkslogo's — dit is een onafhankelijk
  register, geen overheidssite.
- Geen accounts, betaalmuren, of "download na registratie".
- Geen suggestie dat het register compleet is: toon eerlijk waar data ontbreekt.
