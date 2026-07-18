# web/ — frontend (Claude Design-ontwerp)

Bestanden geïmporteerd uit het Claude-Design-project via de DesignSync-MCP:

| Bestand | Wat |
|---|---|
| `MER-register.dc.html` | het ontwerp (Design-Compiler-formaat: `<x-dc>`-template + logica in een `data-dc-script`-blok) |
| `support.js` | de DC-runtime — laadt React van CDN, parset `<x-dc>` en mount de UI automatisch |
| `mer-data.js` | het data-contract (nu **mock**; de PoC genereert de echte versie met dezelfde `trajecten`-vorm) |
| `index.html` | redirect naar `MER-register.dc.html` voor gemak |

## Lokaal bekijken

Het ontwerp doet `import('./mer-data.js')` dynamisch, dus het moet via een
**HTTP-server** draaien (niet `file://`). support.js haalt React van een CDN —
internet nodig.

```bash
cd web
python -m http.server 8123
# open daarna: http://localhost:8123/
```

## Let op — het is een ontwerp, geen productie-frontend

Het `.dc.html`-formaat leunt op de Claude-Design-runtime (`support.js`). Voor de
echte site wordt dit t.z.t. omgezet naar een gewone (single-file) React-SPA die
tegen `/v1/mer/*` praat — zelfde route als omgevingsvergunningenregister.nl. Voor
nu dient het als visuele referentie en als **draaiende demo zodra de PoC een
echte `mer-data.js` heeft geproduceerd**.
