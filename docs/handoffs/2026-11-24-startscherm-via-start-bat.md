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
  (scherm’, live log, tabel met pilot/stoker/totaal).
- Daarna door naar versie 2 (Cp-distributie op geometrie, batchverwerking).
