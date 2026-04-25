# Laptop Registratie – Gebruikersgids

Een complete gids voor het beheer van laptops en leerlingen in het Laptop Registratie-systeem.

---

## Inhoudsopgave

1. [Overzicht](#overzicht)
2. [Tab: Registreer](#tab-registreer)
3. [Tab: Instellingen](#tab-instellingen)
4. [Tab: Tickets](#tab-tickets)
5. [Tab: Foto's](#tab-fotos)
6. [Barcodes & Navigatie](#barcodes--navigatie)
7. [Veelgestelde vragen](#veelgestelde-vragen)

---

## Overzicht

**Laptop Registratie** is een web-applicatie voor het registreren en beheren van laptopuitkering aan leerlingen. Het systeem houdt bij welke leerling welke laptop heeft, volgt problemen (tickets) per laptop, en ondersteunt fotodocumentatie.

### Starten

Navigeer naar https://localhost (of je productie-URL). Je ziet vier hoofdtabs bovenaan:

- **Tickets** — Laptopprobleem-tracker (standaard tabblad)
- **Registreer** — Laptop koppelen aan leerlingen
- **Instellingen** — Leerling- en laptopbeheer
- **Foto's** — Foto's uploaden en bekijken per laptop

Een donker/licht themawisselaar staat rechtsbovenin (☀/☾).

---

## Tab: Registreer

Dit is je **primaire werkplek** voor het snelle koppelen van laptops aan leerlingen, bijvoorbeeld bij uitreiking of terugname.

### Workflow: Laptop uitreiken

1. **Selecteer een leerling** uit de lijst links
   - Typ in het zoekveld om te filteren (zoekt op naam, stamnummer, gebruikersnaam, etc.)
   - Klik op de leerling of navigeer met `1UP`/`1DOWN`-barcodes

2. **Scan of voer het serienummer in** in het veld **"Scan barcode of typ serienummer…"**
   - Voor eigen laptops: scan `EIGEN LAPTOP` of typ `eigen laptop`
   - Focus verschuift automatisch na elke succesvolle koppeling

3. **Bevestig de koppeling**
   - Groen bericht "✓ Laptop gekoppeld" verschijnt
   - Leerling wordt automatisch opgeschoven naar de volgende
   - Je kunt meteen doorgaan

### Speciale barcodes

| Barcode | Functie | Opmerking |
|---------|---------|-----------|
| `1UP` | Vorige leerling selecteren | Snelle navigatie |
| `1DOWN` | Volgende leerling selecteren | Snelle navigatie |
| `EIGEN LAPTOP` | Markeer als eigen toestel | Leerling hoeft geen uitgedeelde laptop |
| `CLEAR` | Zoekveld leegmaken | Snelle reset |
| `INLEVEREN` | Laptop terugkoppelen | Alleen als leerling geselecteerd |

### Rechts: Recente koppelingen

Onderaan rechts zie je een overzicht van je laatste koppelingen (max. 10). Handig voor kontrol.

### Conflictdetectie

Wanneer je probeert een laptop aan twee leerlingen tegelijk toe te wijzen:
- Systeem waarschuwt: "Leerling heeft al laptop(s): [serienummer]"
- Kies **"Overschrijven"** om de oude koppeling te verbreken
- Of **Cancel** om af te zien

---

## Tab: Instellingen

Beheer de basis-data: leerlingen importeren, verwijderen, laptops aanmaken/bewerken.

### Subsectie: Beheer studenten

#### Leerlingen importeren (CSV)

1. Klik op **"CSV-bestand kiezen"** in het upload-gedeelte
2. Selecteer een CSV met kolommen:
   - `stamnummer` (uniek identifier)
   - `voornaam`, `naam`
   - `klas`, `klascode`, `klasnummer`
   - `gebruikersnaam`, `pointer`, etc.

3. Klik **"Importeren"**
   - Bestaande leerlingen worden bijgewerkt
   - Nieuwe leerlingen worden toegevoegd
   - `last_import` timestamp wordt ingesteld

#### Leerlingen zoeken en filteren

- **Zoekveld**: zoekt op stamnummer, voornaam, naam, klas, gebruikersnaam, pointer
- **"Toon uitgeschreven"**: leerlingen met oudere `last_import` dan de huidige import
- **Sidebar filters**:
  - **All** — alle leerlingen
  - **Met laptop** — gekoppelde laptops
  - **Zonder laptop** — nog geen laptop
  - **Eigen laptop** — eigen toestellen
  - **Uitgeschreven** — niet in meest recente import

#### Leerlingen verwijderen

1. Selecteer één of meer rijen (checkbox per rij)
2. Klik **"Selecteer alle"** (optioneel) om alle zichtbare leerlingen aan te vinken
3. Klik **"Verwijderen"**
4. Bevestig de actie
   - Leerling + bijbehorende laptopkoppeling worden verwijderd

### Subsectie: Beheer laptops

#### Nieuwe laptop toevoegen

1. Vul **Serienummer** in (bijv. `LNVG6X00AA8A`)
2. Vul **Stamnummer** in (optioneel; koppel later in Registreer-tab)
3. Klik **"Toevoegen"**

#### Laptop bewerken

1. Zoek in **Laptops beheren** op serienummer
2. Klik **"Bewerk"** op de rij
3. Werk **Serienummer** of **Stamnummer** bij
4. Klik **"Opslaan"**

#### Laptop verwijderen

1. Zoek in **Laptops beheren** op serienummer
2. Klik **"Verwijderen"**
3. Bevestig de permanente verwijdering

---

## Tab: Tickets

Dit is de **issue/probleemtracker** voor laptops. Registreer defecten, volg de tijdlijn en markeer als opgelost.

### Workflow: Probleem melden

1. **Zoeken** (optioneel):
   - Voer serienummer in het globale scan-veld in
   - Klik **+ Defect** in het scan-gedeelte
   - Of zoek in het linker panel

2. **Modaal openen** (+ Defect-knop)
   - **Serienummer**: start met voorgestelde waarde (uit scan)
   - **Beschrijving**: wat is kapot? (verplicht)
   - **Datum gerapporteerd**: vandaag (instelbaar)
   - **Categorie**: optionele indeling (bijv. "Scherm", "Toetsenbord")

3. **Opslaan**
   - Status = **"Aangemeld"** (geel)
   - Probleem verschijnt in het linker panel en detail-weergave

### Status-filters (boven)

- **Aangemeld** (geel) — net ingediend
- **Open** (rood) — in behandeling
- **Gesloten** (groen) — opgelost

Klik op de statistiekkaart om op status te filteren.

### Probleem bewerken

1. Selecteer het probleem in het linker panel
2. In het detail-gedeelte: klik **"Bewerk"**
3. Werk beschrijving, status, oplossing (als gesloten) bij
4. Klik **"Opslaan"**

### Entries (tijdlijn) toevoegen

1. Open een probleem
2. Scroll naar **"Entries"** onderaan
3. Klik **"+ Entry"** en voeg een notitie toe
   - Bijv. "Scherm vervangen" of "Wachten op onderdelen"
4. Klik **"Opslaan"**

Dit creëert een geschiedenis van acties per probleem.

### Probleem verwijderen

1. Selecteer het probleem
2. Klik **"Verwijderen"** in het detail-gedeelte
3. Bevestig

### Exports

- **"Export (geselecteerde laptop)"**: download alle problemen voor 1 laptop (CSV/Excel)
- **"Export (alles)"**: download alle problemen, inclusief gesloten

---

## Tab: Foto's

Documenteer de toestand van laptops met foto's. Handig voor schade-inventaris en garantie.

### Workflow: Foto uploaden

#### Via desktop/laptop

1. Voer het **serienummer** in (zoekveld)
2. Klik **"Galerie laden"**
3. Klik **"Foto toevoegen"** (of sleep een foto naar het uploadveld)
4. Selecteer een afbeelding van je computer
5. Foto wordt geupload en toegevoegd aan de galerie

#### Via mobiel (iOS/Android)

1. Ga naar https://localhost/photos
2. Voer het serienummer in
3. Klik **"Camera"** (of **"Upload bestand"**)
4. Neem een foto met je camera of kies uit je galerij
5. De foto wordt automatisch als base64 opgeslagen (geen bestand-upload nodig)

> **Tip**: Zorg voor goed licht en maak foto's van beide zijden voor volledige documentatie.

### Foto's bekijken

1. Voer serienummer in
2. **Galerie laden**
3. Klik op een miniatuur
4. **Lightbox** opent met volledige foto
   - **Zoom**: scroll (muisrad) in/uit
   - **Pan**: sleep (click + drag) als ingezoomd
   - **Sluit**: Esc-toets of klik buiten

### Foto verwijderen

1. Open galerie (zie boven)
2. Klik **"×"** op de miniatuur (of **"Verwijderen"** onder detail)
3. Bevestig

---

## Barcodes & Navigatie

### Globale scanbar (bovenaan)

- Altijd beschikbaar (rechts in topbalk)
- Binnenklik: focust automatisch
- **Sneltoets**: Cmd+K (Mac) of Ctrl+K (Windows/Linux)
- Voer serienummer in, druk Enter, of klik **+ Defect**

### Navigatiebarcodes

Werk je met een barcode-scanner (bijv. voor leerlingen)? Gebruik:

| Barcode | Doel |
|---------|------|
| `1UP` | Vorige leerling |
| `1DOWN` | Volgende leerling |
| `EIGEN LAPTOP` | Markeer als eigen laptop |
| `INLEVEREN` | Laptop terugkoppelen |
| `CLEAR` | Reset zoekveld |

Handmatig invoeren is ook mogelijk — typ en Enter.

---

## Veelgestelde vragen

### V: Hoe koppel ik snel 30 laptops?

**A**: 
1. Zorg dat alle leerlingen geïmporteerd zijn (Instellingen → Beheer studenten → Import CSV)
2. Ga naar **Registreer**
3. Klik leerling aan → scan serienummer → volgende leerling (automatisch)
4. Gebruik `1UP`/`1DOWN` barcodes als je leerlingen in volgorde wilt navigeren

Duur: ~3–4 min per 30 laptops, afhankelijk van scan-snelheid.

### V: Leerling heeft al een laptop, maar ik wil deze vervangen

**A**: 
1. Ga naar **Registreer**
2. Selecteer de leerling
3. Voer het NIEUWE serienummer in
4. Systeem waarschuwt: "Leerling heeft al laptop(s): [oud serienummer]"
5. Klik **"Overschrijven"**
6. De oude koppeling wordt verbroken, de nieuwe wordt ingesteld

### V: Foto's zijn zwart of wazig (mobiel)

**A**:
- Zorg voor goed licht (voorkant kamera)
- Schoon de camera-lens
- Zet de telefoon niet schuin (probeer recht op)
- Wacht totdat de focus groen wordt (op iOS: geel vierkant)

### V: Kan ik barcodes zelf genereren voor navigatie/acties?

**A**: 
Ja! Gebruik een barcode-generator voor Code 128 of Data Matrix met deze waarden:
- `1UP`, `1DOWN`, `EIGEN LAPTOP`, `INLEVEREN`, `CLEAR`

De app ondersteunt barcodes geprint op papier of in een spreadsheet.

### V: Hoe verwijder ik een leerling zonder hun laptop te verwijderen?

**A**: 
De app verwijdert standaard laptopkoppelingen samen met de leerling. Wil je dit voorkomen:
1. Ga naar **Instellingen → Beheer laptops**
2. Voer het serienummer in
3. Leeg het **Stamnummer**-veld
4. Klik **"Opslaan"**
5. Nu kun je de leerling verwijderen zonder de laptopgegevens te raken

### V: Waar staan mijn foto's?

**A**: 
Foto's worden opgeslagen in de directory `/uploads/laptops/` op de server. Elk bestand krijgt een unieke naam (`foto_<id>_<timestamp>.jpg`). Ze zijn altijd benaderbaar via de app, geen handmatige backup nodig (maar wel aanbevolen voor bedrijfszekerheid).

### V: Kan ik een export maken van alle gegevens?

**A**: 
- **Tickets** → **"Export (alles)"** downloadt alle problemen
- Voor leerlingen/laptops: **CSV → Excel** via je browser (standaard exportfunctie)

Wil je meer formats (JSON, SQL dump)? Neem contact op met IT.

### V: Theme wisselen (donker/licht)

**A**: 
Klik op het icoon **☀** / **☾** rechtsboven. Je voorkeur wordt onthouden.

---

## Support & Troubleshooting

### App reageert niet

1. Ververs de pagina (F5 of Cmd+R)
2. Wis browsercache (Instellingen → Privacy → Cookies/Cache)
3. Controleer je internetverbinding
4. Probeer een ander tabblad; navigeer terug

### Barcodescanner werkt niet

- Zorg dat de scanner zich "gedraagt als toetsenbord" (standaard HID-modus)
- Test met een tekstvoer-veld buiten de app
- Controleer of scanner de juiste code-symbologie stuurt

### Foto uploaden mislukt (mobiel)

- Controleer je internetverbinding (WiFi of mobiel data)
- Zorg dat de camera-permissies zijn gegeven (iOS: Instellingen → Privacy → Camera)
- Probeer een kleiner/lager-resolutie foto
- Wis browser-cache en probeer opnieuw

### Leerling/laptop verdwenen

- Controleer de filters (bijv. "Toon uitgeschreven")
- Zoek op naam of stamnummer
- Kijk in de recentste CSV-import

---

## Snelle referentie

| Actie | Pad | Sneltoets |
|-------|-----|-----------|
| Laptop koppelen | Tab: Registreer | — |
| Leerlingen importeren | Instellingen → Beheer studenten → CSV | — |
| Probleem melden | Tab: Tickets → + Defect | Cmd+K / Ctrl+K |
| Foto uploaden | Tab: Foto's → Galerie laden → + Foto | — |
| Theme wisselen | ☀ / ☾ (toprechts) | — |
| Navigatie vorige | `1UP` barcode | — |
| Navigatie volgende | `1DOWN` barcode | — |

---

**Versie**: 2.0.0 (april 2026)  
**Ondersteunde browsers**: Chrome, Firefox, Safari, Edge (alle moderne versies)  
**Mobiel**: iOS Safari, Android Chrome/Firefox (optimaal)
