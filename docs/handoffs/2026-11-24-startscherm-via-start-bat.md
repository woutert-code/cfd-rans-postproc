# Handoff: interactief startscherm via start.bat

2026-11-24 · sessie Mistral Vibe · bovenop versie 1.1 (commit dd12866)

## Wat is er gebouwd

Een interactief startscherm boven de bestaande runner, plus een
`start.bat` als startpunt:

- **`start.bat`** (repo-root, CRLF): `cd /d "%~dp0"` + `py -m src.cfd_postproc.gui`;
  werkt vanaf elke locatie; `pause` bij fout.
- **`src/cfd_postproc/gui.py`** (tkinter, geen nieuwe dependencies):
  folderkiezer ("Bladeren..." via `askdirectory`), invoervelden met dezelfde
  defaults als de CLI (atleetpatches `pilot,stoker`, rho 1,225, u-ref leeg =
  `u_inlet` uit `system/Variables`, tijdmap leeg = laatst, slice y/x,
  strookdikte, vinkje "output-custom overschrijven"), startknop, live
  logvenster en een resultatentabel.
- De verwerking draait in een **achtergrondthread**; logregels stromen via
  een `_QueueHandler` + queue naar het scherm (tkinter is niet thread-safe).
- Na afloop: `results.csv` wordt als tabel getoond — **weerstand [N],
  frontaal oppervlak [m²], CD, CdA [m²]** per patch en totaal. Figuren en log
  worden naar `output-custom` geschreven, **niet geopend**.
- Fouten: geen geldige case-map of geen `constant/polyMesh` → melding;
  `FileExistsError` →_vriendelijke melding + hint om "overschrijven" te vinken;
  overige fouten rood in het logvenster met verwijzing naar het caselog.

## Kleinere wijzingen in bestaande code

- `__main__.py`: standaard `--slice-x` als moduleconstante `DEFAULT_SLICE_X`
  (gedeelde bron voor CLI en GUI; CLI-gedrag onveranderd).
- `case_runner.py`: `process_case(..., extra_handlers=[...])` — optionele
  extra logging-handlers (voor de GUI); worden na afloop gesloten/verwijderd.
  Default `None`, dus CLI en bestaande tests ongewijzigd.

## Documentatie

- `README.md`: nieuwe sectie "Starten via start.bat (interactief)"; CLI-sectie
  hernoemd naar "Gebruik via de CLI (batch)".
- `DECISIONS.md`: **besluit 002** — tkinter-GUI via `start.bat`, geen nieuwe
  dependencies, CLI blijft voor batch.

## Getest

- `py -m unittest discover -s tests -v`: **26 tests groen** (9 nieuw in
  `tests/test_gui.py`: `parse_positions`/`parse_optional_*`, `build_kwargs`,
  `read_results_table` op een fictieve case, `extra_handlers` ontvangt
  logregels). GUI-logica getest zonder display.
- Smoke-test met verborgen Tk-venster op fictieve mini-case: start → live
  log (23 regels) → status "Klaar." → tabel met pilot/totaal → output-custom
  geschreven.
- `py -m src.cfd_postproc --help` ongewijzigd; `import src.cfd_postproc.gui`
  werkt vanaf de repo-root.

## Open punten

- Visueel testen op de echte case Run_Tandem_027 via `start.bat`
  (scherm, live log, tabel met pilot/stoker/totaal).
- Daarna door naar versie 2 (Cp-distributie op geometrie, batchverwerking).

## Addendum: robuustere melding bij ontbrekende mesh-bestanden

Gemeld bij het testen van `start.bat` op Run_Tandem_027: in
`constant/polyMesh` ontbrak het `faces`-bestand (verdwenen na
OneDrive-sync; de overige mesh-bestanden zijn wel lokaal). De run stopte
toen met een kale `FileNotFoundError: [Errno 2] ... faces`.

Aangepast (deze commit):

- `of_io.py`: `_require_file()` — elk lees-pad (mesh, veld, boundary) geeft
  nu een duidelijke `FileNotFoundError` ("mesh-bestand (faces) ontbreekt:
  <pad> — controleer of de case-map volledig lokaal beschikbaar is ...");
  `latest_time()` meldt een ontbrekende case-map als `ValueError`.
- `gui.py`: pre-check `missing_polymesh_files()` vóór het starten; het scherm
  meldt welke polyMesh-bestanden ontbreken (getest op Run_Tandem_027:
  `['faces']`) met hint om de case-map lokaal te zetten. Het logvenster
  wordt bij elke nieuwe start leeggemaakt (oude FOUT-regels blijven niet
  hangen). `FileNotFoundError` krijgt in het scherm een eigen melding.
- tests: +4 (30 totaal groen), o.a. ontbrekend `faces`/`p`-bestand en
  `missing_polymesh_files`.

Actie voor de gebruiker: herstel `constant/polyMesh/faces` in
Run_Tandem_027 (OneDrive-versiegeschiedenis/backup, of opnieuw
reconstrueren vanaf het cluster) — zonder `faces` is de mesh niet te lezen.

## Addendum 2: startscherm vereenvoudigd (besluit 003)

Op verzoek van de gebruiker zijn de velden **strookdikte, u-ref,
atleetpatches, rho en tijdmap** uit het startscherm verwijderd. Het scherm
bevat nu alleen: case-map, slice y, slice x, het vinkje overschrijven, de
startknop, het logvenster en de resultatentabel.

- `build_kwargs()` geeft alleen nog de schermvelden door; de overige
  parameters vallen terug op de defaults van `process_case()` (patches
  `pilot,stoker`, rho 1,225, u-ref = `u_inlet` uit `system/Variables`, laatste
  tijdmap, strookdikte 0,02 m). Afwijkende waarden: via de CLI.
- Parse-helpers voor de verwijderde velden verwijderd; tests aangepast.
- README en DECISIONS.md (besluit 003) bijgewerkt.

## Addendum 3: standaard x-slice = 0.0 + invoer-hint (besluit 004)

- `DEFAULT_SLICE_X` in `__main__.py` is nu `"0.0"` (was 30 posities van
  -1.0 t/m 1.9): standaard één x-slice op x = 0, net als y. CLI-helptekst
  aangepast; het startscherm gebruikt dezelfde default en de gebruiker kan
  het veld aanpassen.
- Onder de slice-velden in het scherm staat nu een korte hint:
  "Slice-invoer: komma-gescheiden posities in meter, bijv. 0.0 of
  -1.0,0.0,0.5".
- Test-pin toegevoegd (`DEFAULT_SLICE_X == "0.0"`); README en DECISIONS.md
  (besluit 004) bijgewerkt.

## Addendum 4: aandeel per atleet in de totale luchtweerstand (besluit 005)

- `results.csv` krijgt als laatste kolom `aandeel_van_totaal_pct` (100% bij
  de totaalrij); achteraan toegevoegd zodat bestaande parsers niet verschuiven.
- `case_runner` berekent en logt het aandeel per patch; het startscherm toont
  een extra kolom "aandeel [%]" direct na "weerstand [N]".
- Bij Run_Tandem_027 (versie 1.1-waarden): pilot 22,31 N ≈ 57%, stoker
  16,97 N ≈ 43%, totaal 39,28 N.
- Tests uitgebreid (aandeel-kolom in results.csv en in de schermtabel);
  README en DECISIONS.md (besluit 005) bijgewerkt.

## Addendum 5: notitie over slice-figuren in het startscherm

Onder de slice-velden staat nu een vaste notitie (`SLICE_NOTE` in `gui.py`):

> Slice-figuren worden weggeschreven naar output-custom in de case-map
> (worden niet geopend). De manier waarop slices worden gemaakt wordt in een
> volgende versie verbeterd (zie plan-van-aanpak.md §12, punt 7).

Getest via pin-test (`output-custom` en `volgende versie` in de notitie);
README en deze handoff bijgewerkt.

## Addendum 6: werkafspraak commit/push (besluit 006)

Op verzoek van de gebruiker geldt vanaf nu: **de agent vraagt eerst of
wijzigingen gecommit en gepusht mogen worden naar GitHub** — commit/push
gebeurt alleen na expliciete toestemming. Vastgelegd als besluit 006 in
`DECISIONS.md`; dit overrulet de "commit + push na iedere versie"-regel in
AGENTS.md voor commit/push.
