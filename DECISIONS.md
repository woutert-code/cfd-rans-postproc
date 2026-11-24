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

## Template voor nieuwe besluiten

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

## Overzicht van actieve besluiten

| Nr | Titel | Datum | Status |
|----|-------|-------|--------|
| 001 | Gebruik van mean-velden | 2026-11-10 | Actief |
| 002 | Interactief startscherm via tkinter | 2026-11-24 | Actief |
| 003 | Startscherm: alleen essentiële invoervelden | 2026-11-24 | Actief |
| 004 | Standaard x-slice = 0.0 (net als y) | 2026-11-24 | Actief |
| 005 | Aandeel per atleet in totale weerstand in output | 2026-11-24 | Actief |
