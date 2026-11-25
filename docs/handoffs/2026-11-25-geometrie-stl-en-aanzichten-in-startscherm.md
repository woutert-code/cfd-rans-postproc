# Handoff: sessie 2026-11-25 — python-fix, slice-prestaties, STL-geometrie en aanzichten in het startscherm

Sessieverslag, sluit de werksessie af. Bovenop de sessiehandoff van
2026-11-24 (44 tests groen op `dd12866` / daarna `21d0c5d` docs).

## Verloop van de sessie

1. **Repo opgehaald van GitHub** en handoffs, plan-van-aanpak, DECISIONS en
   AGENTS.md gelezen.
2. **`start.bat`-fix + README-vereisten** (`b5246a2`): op deze machine is de
   `py`-launcher niet beschikbaar; `start.bat` gebruikt nu `python -m
   src.cfd_postproc.gui`. README beschrijft de vereisten (Python 3.x met
   tkinter, numpy, matplotlib, PIL) en dat `python` in plaats van `py` gebruikt moet worden.
3. **Slice-prestaties** (`079a0e4`): de body-face zwaartepunten worden
   eenmaal berekend en gedeeld met alle slices. Getest op een 60M-cel case
   (Run_Tandem_001): verwerking inclusief één x- en één y-slice in ~8 min.
   Loganalyse bevestigde de verwachte besparing in de forceer-fase. Code is
   daarna door de gebruiker bevroren ("leave the code as it is now").
4. **Geometrie bij voorkeur uit STL-bestanden** (`11d6d44`, besluit 008):
   de aanzichten worden (2D én 3D) bij voorkeur uit de STL's van de
   atleten gehaald (`constant/triSurface` in de case, daarna de mesh-map
   naast de case), in plaats van uit het polyMesh. Bij grote cases (~70M
   cellen, polyMesh 7-8 GB) scheelt dat minuten: STL's lezen in < 0,1 s,
   het geometrie-venster opent in enkele seconden. Details in besluit 008.
5. **2D-aanzichten standaard in het startscherm** (besluit 009, deze sessie):
   zie hierna.
6. **Per-atleetkleuren in de aanzichten** (deze sessie): zie hierna.

## 2D-aanzichten standaard in het startscherm (besluit 009)

Op verzoek van de gebruiker staan de drie 2D-aanzichten (voor-, zij- en
bovenaanzicht) na het kiezen van een case-map **automatisch** tussen het
logvenster en de resultaten; het draaibare 3D-aanzicht blijft achter de knop
"Geometrie tonen".

- Nieuwe modulefunctie `gui.compute_geometry_payload(case_dir, patch_names)`:
  de gedeelde geometrieberekening (display-vrij), gebruikt door zowel de
  automatische aanzichten als "Geometrie tonen". Retourneert
  `(payload, waarschuwingen)`; waarschuwingen gaan bij het automatisch
  laden alleen naar het logvenster (geen popup).
- Achtergrondthread + polling met token (`_load_views_for_case`,
  `_poll_views`): een net gekozen case annuleert een lopend laden van de
  vorige case. Cache-hit (`_geo_cache`) tekent direct zonder thread.
- Raster van het startscherm: log rij 6-7, aanzichten rij 8 (placeholder +
  verborgen LabelFrames, `figsize=(3.1, 2.5)`, `with_title=False`),
  resultaten rij 9-11. `geometrie.make_view_figure` kreeg hiervoor de
  optionele parameters `figsize`, `dpi` en `with_title` (defaults
  onveranderd).

## Per-atleetkleuren (pilot lichtblauw, stoker donkerblauw)

De samengevoegde silhouette had één kleur; nu krijgt elke atleet een eigen
kleur (STL-route):

- `geometrie.PATCH_COLORS`: pilot `#6baed6` (lichtblauw), stoker `#08306b`
  (exact de "Blues"-kolormapwaarde die de samengevoegde silhouette eerder
  had — de stoker ziet er dus onveranderd uit). `_PATCH_ORDER` bepaalt de
  schildervolgorde: stoker eerst, pilot bovenop, zodat de voorste atleet
  zichtbaar blijft waar de projecties overlappen.
- `geometrie.raster_view_triangles` heeft nu een optionele `extent`-parameter:
  per atleet rasteriseren op hetzelfde rooster (zelfde oorsprong en
  afmeting), zodat de masks over elkaar getekend kunnen worden. Zonder
  `extent` onveranderd gedrag (eigen bbox + 2 px marge).
- `geometrie.make_view_figure` accepteert naast één mask ook een dict
  `{patchnaam: mask}`; dan wordt per patch de kleur uit `PATCH_COLORS`
  getekend (onbekende patches in de fallback-kleur). Implementatie:
  compositing in een RGB+alpha-array, één `imshow`.
- `geometrie.make_3d_figure(..., kleuren=...)`: één kleur per polygoon;
  in `gui.compute_geometry_payload` wordt per atleet gedecimeerd (budget
  naar rato van het aantal driehoeken, totaal ≤ `DEFAULT_MAX_POLYS_3D`),
  dus de pilot is ook in de 3D-figuur lichtblauw.
- Payload-contract uitgebreid met een negende veld `kleuren3d`
  (`(views, polys3d, bmin, bmax, n_total, n_3d, s, bron, kleuren3d)`):
  bij de STL-route een dict-views + kleurenlijst, bij de polyMesh-fallback
  één mask + `None` (alles één donkerblauwe kleur, zoals voorheen).
  De polyMesh-fallback is verder onveranderd (één samengevoegde silhouette).

## Documentatie

- `DECISIONS.md`: **besluit 009** (2D-aanzichten standaard in startscherm) +
  regel in het overzicht van actieve besluiten.
- `README.md`: beschrijving bijgewerkt (aanzichten laden automatisch tussen
  log en resultaten; 3D achter de knop; kleuren pilot lichtblauw / stoker
  donkerblauw; fallback één kleur); dubbele regel in het geometrieparagraaf
  verwijderd.

## Getest

- `python -m unittest discover -s tests`: **63 tests groen** (was 44 aan het
  eind van de sessie van 2026-11-24). Nieuw deze sessie o.a.:
  - `ComputeGeometryPayloadTest` (polyMesh-fallback + STL-route, inclusief
    dict-views en kleurenlijst);
  - raster met gedeelde `extent` geeft per atleet hetzelfde rooster;
  - `make_view_figure` met dict tekent pilot-pixels lichtblauw en
    stoker-pixels donkerblauw (alpha 1) en de achtergrond transparant;
  - kleurpins (`PATCH_COLORS`).
- Rookcheck (display-vrij) met twee fictieve STL's (3000 driehoeken per
  body): bron "stl", binnen elke view gelijk rooster, beide kleuren in de
  3D-polygoonlijst, figuren tekenen zonder fouten.
- Eerder in de sessie: verborgen-venster smoke-test van het startscherm
  (drie panelen getekend, cache gevuld, juiste statusregel).

## Actuele status

- `main` gesynchroniseerd met `origin/main`; besluiten 001-009 actief.
- Case-map structuur: case en mesh naast elkaar (`Run_Tandem_027` +
  `Mesh_Tandem_027`, OneDrive) óf in aparte Case-/Mesh-mappen
  (`E:\KNWU CFD\Tandem`). Beide worden door `find_stl_dir` gevonden.
- Sessie-cache: bij een tweede keer "Geometrie tonen" of wisselen van case
  terug naar een bekende case openen de aanzichten direct uit het geheugen.

## Open punten

- Kleuren visueel beoordelen op de echte cases (Run_Tandem_027, 8M cellen;
  Run_Tandem_001, 69M cellen): tint lichtblauw en de schildervolgorde
  (pilot bovenop) waar de projecties overlappen.
- Plan-van-aanpak.md §12 punt 7: betere slice-generatie (volgende versie).
- Echte mesh-simplificatie voor de 3D-weergave i.p.v. decimatie + inflatie
  (addendum 9 van de handoff van 2026-11-24) — met STL-driehoeken van
  ~1 mm minder urgent.
- Versie 2: Cp-distributie op de geometrie (plan-van-aanpak.md §9).
