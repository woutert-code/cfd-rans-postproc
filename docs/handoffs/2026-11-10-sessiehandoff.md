# Handoff: sessie 2026-11-10 — intake tot en met versie 1

Sessieverslag (geschoond), sluit de werksessie af. Gebaseerd op de
werkafspraken in `AGENTS.md`.

## Verloop van de sessie

1. **Intake** (uitgebreide variant, nieuwe repository): casus RANS-
   postprocessing van sporters; resultaat: `plan-van-aanpak.md` met data-
   afspraken (alles lokaal, vertrouwelijk, niets online), versie-1-scope
   en uitzoeklijst.
2. **Werkafspraken:** `AGENTS.md` met data-accessblok, Git-werkwijze
   (commit + push per versie, kleine stappen), handoff-afspraken en
   loggingafspraken; gebruikersnamen/wachtwoorden en `.env` worden nooit
   gelezen of opgeslagen.
3. **Bouw versie 1** in kleine, ge committe stappen (7 commits):
   OpenFOAM-lezers (binaire v2006-indeling), krachten en frontaal
   oppervlak, slice-figuur, runner met logging en CLI. Details en
   resultaten: zie de versie-1-handoff
   `2026-11-10-versie1-build-postprocessing-route.md`.
4. **Run op de voorbeeldcase** Run_Tandem_027: geslaagd in ~24 s;
   results.csv, slice-png en caselog in `output-custom`.
5. Alles gepusht naar `github.com/woutert-code/cfd-rans-postproc`
   (branch `main`).

## Huidige staat

- Versie 1 volgens plan-van-aanpak.md, sectie 8, staat klaar voor
  validatie; 16 unittests groen.
- Output van de voorbeeldcase staat in de case-map zelf (buiten de repo):
  `output-custom/results.csv` (pilot 22,3 N / CdA 0,142; stoker 17,0 N /
  CdA 0,108; totaal 39,3 N / CdA 0,251), `Run_Tandem_027_slice_y0.png`
  en `Run_Tandem_027_postprocessing.log`.

## Openstaande acties (volgende sessie)

1. **Validatie versie 1 (onderzoeker):** vergelijk `results.csv` met de
   bestaande postprocessing van dezelfde case. Let op: de oorspronkelijke
   handmatige referentiebestanden zijn vóór de bouw uit de case-map
   verdwenen (verplaatst of OneDrive-sync); ze zijn niet hersteld.
2. Na akkoond: versie 2 — Cp-distributie op de geometrie, additionele
   slices — daarna batchverwerking met batch-logging (plan, sectie 9).
3. Bekijk de slice-figuur en beoordeel strookdikte (standaard 0,02 m) en
   kleurschaal; instelbaar via `--slice-thickness` en `--slice-bins`.

## Werkwijze bij verder gaan

- Lees `plan-van-aanpak.md` (leidend), `AGENTS.md` (data-toegang en
  logging) en beide handoffs in `docs/handoffs/`.
- Tests draaien: `py -m unittest discover -s tests -v`.
- Tool draaien: `py -m src.cfd_postproc --case "pad/naar/case"` (opties:
  `--help`).
