# DECISIONS.md — Technische en functionele besluiten

Dit document bevat alle importante besluiten die genomen zijn tijdens de ontwikkeling van `cfd-rans-postproc`.
Elk besluit is gedateerd en genummerd voor traceerbaarheid.

---

## Besluit 001: Gebruik van mean-velden uit OpenFOAM-cases

**Datum:** 2026-11-10
**Status:** Actief
**Beslissing:**

> **Altijd de tijdsgemiddelde (mean) velden uit de OpenFOAM-case gebruiken voor postprocessing.**
> Als mean-velden niet beschikbaar zijn, moet dit worden **gemeld in het logbestand**,
> en mag er **als fallback** gebruik worden gemaakt van de instantane (niet-gemiddelde) velden.

### Toepassing

Voor de volgende velden geldt:
- **Druk:** `pMean` → fallback: `p`
- **Snelheid:** `UMean` → fallback: `U`
- **Wandschuifspanning:** `wallShearStressMean` → fallback: `wallShearStress`

### Implementatie

In `src/cfd_postproc/case_runner.py`:
```python
p_path = os.path.join(t, "pMean") if os.path.exists(os.path.join(t, "pMean")) else os.path.join(t, "p")
wss_path = os.path.join(t, "wallShearStressMean") if os.path.exists(wss_path) else os.path.join(t, "wallShearStress")
u_path = os.path.join(t, "UMean") if os.path.exists(u_path) else os.path.join(t, "U")
```

### Logging

Als mean-velden ontbreken, wordt een **WARNING** gelogd:
```
WARNING: mean-velden ontbreken: <lijst>; valt terug op niet-gemiddelde velden
```

### Motivatie

1. **Nauwkeurigheid:** Tijdsgemiddelde velden (`*Mean`) zijn **stabiel** en representatief voor RANS-simulaties
2. **Consistentie:** Alle krachten (druk, schuif) en visualisaties gebruiken dezelfde tijdsbasis
3. **Flexibiliteit:** Fallback naar instantane velden zorgt voor **robuustheid** als mean-velden ontbreken
4. **Transparantie:** Gebruiker weet via het logbestand welke velden daadwerkelijk zijn gebruikt

### Impact

- **Versie 1.1+:** Gebruikt mean-velden waar beschikbaar
- **Validatie:** Resultaten met mean-velden zijn betrouwbaarder voor RANS-simulaties
- **Fallback:** Script blijft werken als mean-velden ontbreken (bijv. in testcases)

---

## Besluit 002: Interactief startscherm via tkinter

**Datum:** 2026-11-24
**Status:** Actief
**Beslissing:**

> **Het startscherm is een tkinter-GUI (`src/cfd_postproc/gui.py`), gestart via `start.bat` in de repo-root. Geen nieuwe dependencies; de CLI (`py -m src.cfd_postproc`) blijft ongemoeid beschikbaar voor batchgebruik.**

### Toepassing

- `start.bat` → `py -m src.cfd_postproc.gui` (werkt vanaf elke locatie via `cd /d "%~dp0"`).
- De GUI is een dunne schil boven `case_runner.process_case()`: de verwerking draait in een achtergrondthread en logregels stromen live naar het scherm via `extra_handlers`.
- Na afloop toont het scherm `results.csv` als tabel (weerstand, frontaal oppervlak, CD, CdA); figuren worden weggeschreven maar niet geopend.

### Motivatie

1. **Geen extra installatie:** tkinter zit standaard in Python op Windows.
2. **Eenvoudigste start voor één lokale gebruiker:** dubbelklikken op `start.bat`.
3. **Geen duplicatie:** CLI en GUI delen dezelfde runner.

### Impact

- `case_runner.process_case()` heeft een optionele `extra_handlers`-parameter.
- GUI-logica (zonder display) getest in `tests/test_gui.py`.

---

## Besluit 003: Startscherm bevat alleen de essentiële invoervelden

**Datum:** 2026-11-24
**Status:** Actief
**Beslissing:**

> **Het startscherm (`gui.py`) bevat alleen: case-map, slice y, slice x en het vinkje "output-custom overschrijven". De overige parameters (atleetpatches, rho, u-ref, tijdmap, strookdikte) krijgen de standaardwaarden van `process_case()`; afwijkende waarden gaan via de CLI.**

### Motivatie

1. Minder invoervelden = minder kans op fouten bij de primaire use-case (tandem-cases met `pilot,stoker`).
2. De defaults leven op één plek (`process_case`), waardoor CLI en GUI consistent blijven.

### Impact

- `build_kwargs()` in `gui.py` geeft alleen de schermvelden door; de parse-helpers voor de verwijderde velden zijn meegeschoond.

---

## Besluit 004: Standaard x-slice is 0.0 (net als y)

**Datum:** 2026-11-24
**Status:** Actief
**Beslissing:**

> **`DEFAULT_SLICE_X = "0.0"`: standaard wordt één x-slice gemaakt op x = 0, net als de y-slice. Meer posities (komma-gescheiden, bijv. `-1.0,0.0,0.5`) zijn instelbaar via `--slice-x` / het startscherm, met een korte invoer-hint onder de velden.**

### Motivatie

1. Voor een eerste controle zijn weinig slices genoeg; 30 standaardfiguren per case was onnodig veel output.
2. Duidelijke invoer: de hint onder de slice-velden legt het formaat uit.

### Impact

- `DEFAULT_SLICE_X` in `__main__.py` (gedeeld door CLI en GUI); helptekst aangepast.
- In het startscherm staat onder slice y/x: "Slice-invoer: komma-gescheiden posities in meter, bijv. 0.0 of -1.0,0.0,0.5".

---

## Besluit 005: Aandeel van elke atleet in de totale luchtweerstand in de output

**Datum:** 2026-11-24
**Status:** Actief
**Beslissing:**

> **`results.csv` bevat als laatste kolom `aandeel_van_totaal_pct`: het percentage van de luchtweerstand van elke atleetpatch t.o.v. het totaal (totaalrij = 100%). Het startscherm toont deze kolom als "aandeel [%]" direct na de weerstand.**

### Motivatie

1. Bij een tandem is direct zichtbaar welk deel van de totale weerstand de pilot (voorste) vs. de stoker (achterste) veroorzaakt.
2. De kolom is achteraan toegevoegd, zodat bestaande parsers van `results.csv` niet verschuiven.

### Impact

- `case_runner` berekent het aandeel per patch en logt het; `_write_results()` schrijft de kolom; het startscherm toont haar via `RESULT_COLUMNS` in `gui.py`.

---

## Besluit 006: Commit en push alleen na expliciete toestemming van de gebruiker

**Datum:** 2026-11-24
**Status:** Actief
**Beslissing:**

> **Aanpassingen worden pas gecommit en gepusht naar GitHub nadat de gebruiker daar expliciet om vraagt of toestemming voor geeft. Na een wijziging vraagt de agent hiernaar. Dit geldt in plaats van de regel "na iedere versie een commit en een push" in AGENTS.md (die wordt hiermee voor commit/push overrulet).**

### Motivatie

- De gebruiker wil zelf controle over wat wanneer naar GitHub gaat.

### Impact

- Na een code- of documentwijziging staat de wijziging eerst alleen lokaal in de werkboom; de agent vraagt: "commit + push naar main?" Bij 'nee' blijft alles lokaal.
- De gebruiker kan per change of voor een hele sessie toestemming geven.

---

## Besluit 007: Geometrie-visualisatie in het startscherm (2D-views + draaibare 3D)

**Datum:** 2026-11-24
**Status:** Actief
**Beslissing:**

> **Via "Geometrie tonen" in het startscherm is de geometrie van de atleetpatches (`pilot,stoker`) te bekijken als solid: vooraanzicht, zijaanzicht en bovenaanzicht (2D, PIL-raster over alle faces, met afmetingen uit de bounding box) plus een 3D-figuur die in het scherm met de muis draaibaar is. Implementatie in `geometrie.py` met matplotlib-`Figure` + `FigureCanvasTkAgg` — geen nieuwe dependencies. Voor de 3D: cel-decimatie (één face per oppervlakte-cel, ≤ 20.000 polygonen — meer is te traag voor interactief draaien) + inflatie van elk polygon rond zijn zwaartepunt met factor celgrootte/face-diameter, zodat het solid is zonder gaten.**

### Motivatie

1. De gebruiker wil de atleetgeometrie (pilot + stoker) visueel kunnen begruiken zonder ParaView — dit is een eerste stap naar de geometriefiguur met Cp-distributie uit versie 2 (plan §9).
2. Alleen estándar-bibliotheken (numpy/matplotlib/tkinter), consistent met besluit 002.

### Impact

- Nieuw module `src/cfd_postproc/geometrie.py`; GUI-knop "Geometrie tonen" in `gui.py` (mesh laden in achtergrondthread, viewer in een `Toplevel` met `ttk.Notebook`).
- Tests in `tests/test_geometrie.py` (display-vrij).

---

## Besluit 008: Geometrie bij voorkeur uit STL-bestanden i.p.v. de polyMesh

**Datum:** 2026-11-25
**Status:** Actief
**Beslissing:**

> **De geometrieviewer gebruikt, als ze beschikbaar zijn, STL-bestanden van de atleten (binair of ascii) in plaats van de polyMesh. De STL's worden gezocht in `constant/triSurface` van de case zelf, daarna in de bijbehorende mesh-map naast de case (bij `Run_X` de map `Mesh_X`). Per atleetpatch staat er dan één bestand `<patchnaam>.stl`. De polyMesh-route blijft als fallback bestaan; er zijn geen nieuwe dependencies toegevoegd.**

### Toepassing

- `geometrie.find_stl_dir()` zoekt de triSurface-map in drie bekende structuren: `constant/triSurface` in de case zelf; broer/zus-map `Mesh_<rest van de casenaam>` naast de case (OneDrive-structuur); en `<hoofdmap>/Mesh/Mesh_<rest>` naast `<hoofdmap>/Case/` (structuur met aparte Case- en Mesh-mappen, bijv. `E:\KNWU CFD\Tandem`). `read_stl()` leest binair of ascii; `read_body_triangles()` geeft per patch de driehoeken (of None: fallback naar polyMesh).
- `gui.py` gebruikt de STL-route voor "Geometrie tonen" zodra alle atleetpatches als STL gevonden zijn; de polyMesh-pre-check geldt dan niet meer. Val de code terug op de polyMesh, dan verschijnt hiervan expliciet een waarschuwingsregel in het logvenster (geen stille fallback meer).
- 2D-views: PIL-raster van de driehoekprojecties; 3D: decimatie tot ≤ 20.000 driehoeken met dezelfde inflatieregel als de mesh-route.

### Motivatie

1. **Snelheid:** de polyMesh van grote cases (~70M cellen) is 7–8 GB en kost > 150 s om te lezen alleen om ~3,5M body-faces te kunnen tonen; de STL's (2 × 28 MB) lezen in < 0,1 s — het geometrievenster opent in ~10 s in plaats van minuten.
2. **Kwaliteit:** de STL is de originele CAD-oppervlakte, niet de gesnapte, gerefineerde mesh-vlakken.
3. **Gebruiksgemak:** de geometrie kan bekeken worden ook voordat de volledige case lokaal beschikbaar is; tijdens het mesh-ontwerp kan de geometrie al worden gecontroleerd via de mesh-map.

### Impact

- Nieuwe functies in `geometrie.py`: `find_stl_dir`, `read_stl`, `read_body_triangles`, `bounding_box_triangles`, `raster_view_triangles` (gevectoriseerde rasterisatie via pixel-bbox per driehoek, ~3x sneller dan de PIL-lus bij ~1M driehoeken), `decimate_triangles` (met celgrootteschatting en 1D uniek-sleutel; ~6x sneller dan de polyMesh-decimatie), plus inflatie in dezelfde stijl als de polyMesh-route.
- `gui.py` houdt het geometrieresultaat per case in het geheugen (sessie-cache): een tweede keer "Geometrie tonen" opent direct.
- De 3D-weergave bij de STL-route gebruikt dezelfde decimatie-plus-inflatie-benadering; echte mesh-simplificatie (addendum 9 van de handoff van 2026-11-24) blijft een open punt voor verbetering, maar is met STL-driehoeken van ~1 mm minder nodig.
- STL's zijn atleetgeometrie: net als de casedata vertrouwelijk en nooit in Git; tests gebruiken uitsluitend een klein fictief STL-bestand (`tests/test_geometrie_stl.py`).

## Besluit 009: 2D-aanzichten standaard zichtbaar in het startscherm

**Datum:** 2026-11-25
**Status:** Actief
**Beslissing:**

> De drie 2D-aanzichten (voor-, zij- en bovenaanzicht) worden automatisch geladen en getoond in het startscherm zodra een case-map is gekozen, tussen het logvenster en de resultaten in. Het draaibare 3D-aanzicht blijft achter de knop "Geometrie tonen".

### Toepassing

- `gui.py` start na het kiezen van een case-map (`_browse`) direct `_load_views_for_case()`: een achtergrondthread berekent via `compute_geometry_payload()` de drie 2D-views (STL-route bij voorkeur, polyMesh-fallback) en zet ze via een wachtrij terug naar de GUI-thread.
- De drie panelen staan in rasterrij 8; zolang er geen case is gekozen staat daar een placeholder. De LabelFrames van de views zijn verborgen tot ze geladen zijn.
- Fouten bij het automatisch laden gaan alleen naar het logvenster, niet als popup; "Geometrie tonen" werkt onveranderd en toont daarnaast het 3D-aanzicht.

### Motivatie

1. **Gebruiksgemak:** de 2D-geometriechecks waren elke keer een extra klik; ze zijn de meest gebruikte checks en horen direct zichtbaar te zijn na het kiezen van een case.
2. **Overzicht:** de volgorde op het startscherm wordt invoer, verwerking (log), geometrie-check, resultaten.
3. **Kost het weinig:** door de STL-route (besluit 008) duurt het laden van de views ~2 s, dus automatisch laden is zonder merkbare vertraging bij het kiezen van een case.

### Impact

- Nieuwe modulefunctie `compute_geometry_payload()` in `gui.py`, gedeeld door de automatische views en "Geometrie tonen"; worker/polling-patroon met token tegen verouderde resultaten.
- Raster van het startscherm verschuift: log op rij 6-7, views op rij 8, resultaten op rij 9-11.
- README beschrijft het nieuwe gedrag bij "Starten via start.bat".
```markdown
## Besluit XXX: [Korte titel]

**Datum:** YYYY-MM-DD
**Status:** Actief / Verouderd / Vervangen door [nr]
**Beslissing:**

> [Beschrijving van het besluit]

### Toepassing

[Hoe wordt het besluit toegepast?]

### Implementatie

[Code voorbeeld of referentie naar bestandslocatie]

### Motivatie

[Redenen voor dit besluit]

### Impact

[Gevolgen voor de code, gebruikers, validatie, etc.]
```

---

## Besluit 010: Cp-verdeling op de 2D-aanzichten via "Cp verdeling"

**Datum:** 2026-11-27
**Status:** Actief
**Beslissing:**

> **De knop "Cp verdeling" in het startscherm (rechts naast "Geometrie tonen") vervangt de drie 2D-aanzichten (voor-, zij- en bovenaanzicht) door dezelfde aanzichten gekleurd naar de drukcoëfficiënt Cp = (p_wand − p_ref) / (½·u_ref²) met p_ref = 0. Per body-face volgt de wanddruk uit de owner-cel (zeroGradient), net als bij `krachten.pressure_drag`; p is kinematisch [m²/s²]. `pMean` heeft de voorkeur met fallback op `p` (besluit 001, met waarschuwing in het logvenster); u_ref = `u_inlet` uit `system/Variables`. De STL-route kan geen Cp leveren (een STL bevat geen veldwaarden), dus de Cp-aanzichten gebruiken altijd de polyMesh-body-faces. Per pixel is de zichtbare face de dichtstbijzijnde t.o.v. de camerakant van de view (painter's algorithm via `geometrie.VIEW_DEPTH`: front vanaf −x, side vanaf +y, top vanaf +z). Kleurschaal: divergent `RdBu_r` met **vast bereik [−2, 1]** (`gui.CP_RANGE`), inclusief colorbar.**

### Toepassing

- `gui.compute_cp_payload(case_dir, body_patches)` (display-vrij, deelbaar met tests): leest mesh + drukveld, berekent Cp per face en rasteriseert per view een face-index-beeld (`geometrie.raster_view_index`) dat met `geometrie.cp_image_from_index` naar een Cp-beeld (NaN = achtergrond) wordt omgezet; figuur via `geometrie.make_cp_view_figure`.
- In het startscherm: knop "Cp verdeling" op rij 5, kolom 2 (direct rechts van "Geometrie tonen"); laden gebeurt in een achtergrondthread met token (verouderde resultaten worden genegeerd) en per-case sessie-cache. De bestaande 2D-panelen worden vervangen door de Cp-figuren (paneeltitel krijgt " — Cp"); bij opnieuw kiezen van een case-map keren de gewone geometrie-aanzichten terug.
- De berekening vereist de polyMesh: bij ontbrekende polyMesh-bestanden volgt dezelfde pre-check/melding als bij "Start postprocessing".

### Motivatie

1. **Versie 2 uit het plan** (plan-van-aanpak.md §9): Cp-distributie op de geometrie — dit is de eerste stap, direct in het startscherm bij de bestaande aanzichten.
2. Cp is een veldwaarde op de mesh-wanden; de STL's (besluit 008) kunnen die niet leveren, dus de polyMesh-route is hier noodzakelijk (bij ~70M-cel cases kost het lezen van de mesh minuten; de voortgang is zichtbaar in de statusregel).
3. Dezelfde drie aanzichten als de geometrie (front/zij/boven), zodat de Cp-verdeling direct te vergelijken is met de silhouette.

### Impact

- Nieuw in `geometrie.py`: `VIEW_DEPTH`, `raster_view_index`, `cp_image_from_index`, `make_cp_view_figure`, en de gedeelde raster-core `_bbox_arrays`/`_rasterize_bboxes` (waar `_rasterize_triangles_2d` nu ook op draait).
- Nieuw in `gui.py`: `compute_cp_payload`, knop `cp_btn`, `_show_cp`/`_poll_cp`/`_draw_cp_panels`, `_cp_cache`/`_cp_token`/`_cp_queue`.
- Tests: `TestRasterViewIndex`/`TestCpFigure` (incl. painter's-algorithm met synthetische mesh), `ComputeCpPayloadTest` (fixturecase: Cp = p/(½·u_ref²), pMean-waarschuwing, fouten bij ontbrekende u_inlet/patch).

---

## Overzicht van actieve besluiten

| Nr | Titel | Datum | Status |
|----|-------|-------|--------|
| 001 | Gebruik van mean-velden | 2026-11-10 | Actief |
| 002 | Interactief startscherm via tkinter | 2026-11-24 | Actief |
| 003 | Startscherm: alleen essentiële invoervelden | 2026-11-24 | Actief |
| 004 | Standaard x-slice = 0.0 (net als y) | 2026-11-24 | Actief |
| 005 | Aandeel per atleet in totale weerstand in output | 2026-11-24 | Actief |
| 006 | Commit/push alleen na expliciete toestemming | 2026-11-24 | Actief |
| 007 | Geometrie in startscherm: 2D-views + draaibare 3D | 2026-11-24 | Actief |
| 008 | Geometrie bij voorkeur uit STL-bestanden | 2026-11-25 | Actief |
| 009 | 2D-aanzichten standaard in startscherm | 2026-11-25 | Actief |
| 010 | Cp-verdeling op de 2D-aanzichten via "Cp verdeling" | 2026-11-27 | Actief |
