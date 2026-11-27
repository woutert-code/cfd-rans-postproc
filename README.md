# cfd-rans-postproc

Automatische postprocessing van OpenFOAM RANS-simulaties van sporters in een
luchtstroming (wielrenners, schaatsers, skeleton-atleten) — lokaal in Python,
zonder ParaView of een OpenFOAM-installatie. Het script leest uitsluitend de
oplossingsdata van een simulatie.

## Wat krijg je?

Per case wordt een nieuwe map `output-custom` binnen de map van de simulatie
aangemaakt, met daarin:

- `results.csv` — luchtweerstand (N), CdA (m²), frontaal oppervlak (m²) en CD
  per atleet en totaal, plus per atleet het aandeel (%) in de totale
  luchtweerstand (`aandeel_van_totaal_pct`);
- slice-figuren van het stromingsveld met de luchtsnelheid in x-richting;
- een logbestand met fouten en de voortgang van de verwerking.

## Snelstart

1. Installeer **Python 3.11+** (bij de standaardinstallatie op Windows is
   tkinter inbegrepen, ook in de Microsoft Store-versie).
2. Installeer de overige packages:

   ```bash
   python -m pip install numpy matplotlib pillow
   ```

3. Dubbelklik **`start.bat`** in de repo-root (werkt vanaf elke locatie) en
   kies de map van je CFD-case. Klaar.

Eenmalig per machine is `python -m pip install ...` dus voldoende; daarna is
`start.bat` de enige stap die je nodig hebt.

![Het startscherm: case-map gekozen, 2D-aanzichten automatisch geladen, en de
resultaattabel die na afloop wordt gevuld.](docs/startscherm.png)

## De interface stap voor stap

1. **Kies de CFD-case map** via "Bladeren...". Zodra je een map kiest, worden
   de drie 2D-aanzichten (voor-, zij- en bovenaanzicht) automatisch geladen en
   verschijnen ze tussen het logvenster en de resultaten — hier is geen klik
   voor nodig.
2. **Pas eventueel de slice-posities aan** in de velden *Slice y* en *Slice x*:
   komma-gescheiden posities in meter, bijv. `0.0` of `-1.0,0.0,0.5` (zie ook
   de hint onder de velden).
3. **Zet desgewenst het vinkje** "Bestaande output-custom overschrijven" als
   er al een `output-custom` in de case-map staat.
4. **Klik op "Start postprocessing"**. Tijdens de verwerking verschijnt het
   log live in het scherm; na afloop toont de resultaattabel de waarden uit
   `results.csv`: luchtweerstand [N] met aandeel van het totaal [%], frontaal
   oppervlak [m²], CD en CdA [m²] per atleet en totaal. De slice-figuren
   worden weggeschreven maar niet geopend.

Met **"Geometrie tonen"** opent een apart venster met een 3D-figuur van de
geometrie, dat met de muis draaibaar is (scroll = zoomen).

Met **"Cp verdeling"** (rechts naast "Geometrie tonen") worden de drie
2D-aanzichten in het scherm **vervangen** door dezelfde aanzichten (voor,
zij, boven) gekleurd naar de drukcoëfficiënt Cp = p_wand / (½·u_ref²) op het
atleetoppervlak: rood = hoge druk, blauw = lage druk, met colorbar
(vast bereik −2 t/m 1). Cp volgt
uit de polyMesh en het drukveld (`pMean`, met fallback op `p`; u_ref =
`u_inlet` uit `system/Variables`), dus hiervoor wordt de mesh gelezen — bij
grote cases kan het laden even duren. Kies opnieuw een case-map om terug te
schakelen naar de gewone geometrie-aanzichten.

De overige instellingen staan vast op de standaardwaarden (atleetpatches
`pilot,stoker`, rho 1,225 kg/m³, u-ref uit `u_inlet` in `system/Variables`,
laatst weggeschreven tijdmap, strookdikte 0,02 m); voor afwijkende waarden
gebruik je de [CLI](#gebruik-via-de-cli-batch).

Achtergronddetails over hoe de aanzichten tot stand komen (STL's,
fallback-route, kleuren): zie [Geometrie en aanzichten](#geometrie-en-aanzichten).

## Gebruik via de CLI (batch)

Vanuit de repositorymap:

```bash
python -m src.cfd_postproc --case "pad/naar/simulatiemap" [--time 1600]
```

Alle opties zie je met `python -m src.cfd_postproc --help`; de belangrijkste:

| Optie | Betekenis | Standaard |
| --- | --- | --- |
| `--case` | map van de simulatie (vereist) | — |
| `--time` | te verwerken tijdmap | laatste tijdmap |
| `--body-patches` | wanden van de atleten | `pilot,stoker` |
| `--slice-y` | positie(s) van slice-vlakken in y, komma-gescheiden, in meters | `0` |
| `--slice-x` | idem in x-richting | `0` |
| `--rho` | luchtdichtheid | 1,225 kg/m³ |
| `--u-ref` | referentie-snelheid | `u_inlet` in `system/Variables` |
| `--overwrite` | schrijven naar een bestaande `output-custom` toestaan | niet toegestaan |

## Geometrie en aanzichten

De sectie hierboven vertelt hoe je de aanzichten *ziet*; hier staat hoe ze
*tot stand komen*:

- De aanzichten worden bij voorkeur gehaald uit **STL-bestanden**: eerst
  `constant/triSurface` in de case zelf, daarna in de bijbehorende mesh-map
  naast de case (bij `Run_Tandem_027` de map `Mesh_Tandem_027`, bestanden
  `pilot.stl` en `stoker.stl`). In dat geval hoeft de polyMesh helemaal niet
  gelezen te worden: de aanzichten staan binnen enkele seconden in het
  scherm, ook voor grote cases, en tonen de originele CAD-oppervlakte i.p.v.
  de gesnapte mesh-vlakken. Met STL's is de pilot lichtblauw en de stoker
  donkerblauw.
- Zijn er geen STL's beschikbaar, dan valt de weergave terug op de
  **polyMesh-route**: de aanzichten worden dan gerasteriseerd over alle
  faces, met de afmetingen uit de bounding box (lengte × breedte × hoogte),
  alles in één donkerblauwe kleur.
- Lukt het automatisch laden niet, dan verschijnt daarvan alleen een regel in
  het logvenster.
- Voor het 3D-venster wordt het oppervlak cel-geïndexeerd (één face per
  oppervlakte-cel, ≤ 20.000 polygonen) en worden de polygonen licht
  opgeblazen rond hun zwaartepunt, zodat het solide is zonder gaten bij
  grote meshes (zie `src/cfd_postproc/geometrie.py`).
- De **Cp-aanzichten** (knop "Cp verdeling") gebruiken altijd de
  polyMesh-body-faces: Cp is een veldwaarde per wandface en zit niet in de
  STL's. Per pixel wordt de dichtstbijzijnde face getoond (painter's
  algorithm, camerakant per aanzicht: front vanaf −x, zij vanaf +y, boven
  vanaf +z).

De manier waarop slices worden gemaakt wordt in een volgende versie
verbeterd (plan-van-aanpak.md §12, punt 7).

## Problemen oplossen

- **Er wordt niets weggeschreven** — er staat al een map `output-custom` in de
  case. Zet het vinkje "Bestaande output-custom overschrijven" (of gebruik
  `--overwrite` in de CLI).
- **"tkinter is niet beschikbaar"** — installeer Python opnieuw met tkinter
  (bij de standaardinstallatie van Python op Windows inbegrepen, ook de
  Microsoft Store-versie).
- **Aanzichten verschijnen niet** — waarschijnlijk zijn er geen STL's
  beschikbaar en valt de weergave terug op de langzamere polyMesh-route; de
  reden staat in het logvenster.
- **Op deze machine** is Python geïnstalleerd via de Microsoft Store en is de
  `py`-launcher niet beschikbaar: gebruik dus overal `python` in plaats van
  `py`.

## Over de resultaten

- `aandeel_van_totaal_pct` — per atleet het aandeel in de totale
  luchtweerstand; handig om direct te zien welke atleet het meeste probleem
  oplevert.
- De referentie-snelheid voor CD komt standaard uit `u_inlet` in
  `system/Variables` van de case; met `--u-ref` overschrijf je die.

## Vertrouwelijkheid

De repository bevat alleen code en documentatie. Simulatiedata, geometrie
(STL-bestanden) en gegenereerde output blijven lokaal in de hoofdmap met
CFD-cases en komen nooit in Git of online. Zie `AGENTS.md` en
`plan-van-aanpak.md`.

## Voor ontwikkelaars

- `plan-van-aanpak.md` — het plan van aanpak; leidend voor scope en
  acceptatiecriteria per versie.
- `AGENTS.md` — werkafspraken voor coding agents (data-toegang, logging,
  Git-werkwijze).
- `docs/handoffs/` — geschoonde verslagen per versie en per sessie.
- `src/cfd_postproc/` — de Python-package.
- `tests/` — gerichte unittests met kleine, fictieve voorbeelcases.

Tests draaien met:

```bash
python -m unittest discover -s tests -v
```

De acceptatie van versie 1 wordt bepaald door vergelijking van de
gegenereerde waarden met de bestaande postprocessing van de onderzoeker
(zie `plan-van-aanpak.md`, §8).
