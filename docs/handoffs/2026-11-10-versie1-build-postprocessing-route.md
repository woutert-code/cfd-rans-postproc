# Handoff: versie 1 — build postprocessing-route op één case

2026-11-10 · sessie Mistral Vibe · versie 1 van plan-van-aanpak.md, sectie 8

## Wat is er gebouwd

Volledige route voor één OpenFOAM-case (ESI v2006, binaire schrijfwijze,
parallelle run op het cluster, gereconstrueerd), lokaal en zonder ParaView
of OpenFOAM-installatie:

1. **OpenFOAM-lezers** (`src/cfd_postproc/of_io.py`): polyMesh
   (points, faces incl. de ascii-overgang tussen de twee binaire lijsten,
   owner, neighbour, boundary) en velden (interne velden als float32;
   patchwaarden per patchnaam gericht gelezen, bestand tegen binaire data).
   Wall pressure volgt via de owner-lijst (p is op de atleetwanden
   `zeroGradient`).
2. **Krachten en oppervlak** (`krachten.py`): gevectoriseerde
   oppervlaktevectoren per vertexaantal-groep; drukkracht
   `rho · Σ p·Sf` (p kinematisch [m²/s²]); schuifkracht
   `SHEAR_SIGN · rho · Σ wss·|Sf|` met SHEAR_SIGN = −1
   (tractie tegengesteld aan de wandnormaal; geverifieerd op de
   voorbeeldcase: schuifbijdrage positief); frontaal oppervlak via
   PIL-rasterisatie van de geprojecteerde silhouette (z-y-assen,
   resolutie standaard 2 mm).
3. **Slice** (`slice.py`): celzwaartepunten chunksgewijs (bincount over
   owner/neighbour), gemiddelde ux per bin in een strook rond het
   slice-vlak (standaard y = 0, 0,02 m), matplotlib-figuur.
4. **Runner en CLI** (`case_runner.py`, `__main__.py`):
   `py -m src.cfd_postproc --case <map>`; weigert een bestaande
   `output-custom` zonder `--overwrite`; schrijft `results.csv`
   (druk-/schuif-/totaalweerstand, frontaal oppervlak, CD, CdA per
   atleetpatch en totaal), de slice-png en een logbestand met fouten en
   voortgang (tijdstip + onderdeel + status) in de case.

## Wat is uitgevoerd

- Run op de voorbeeldcase Run_Tandem_027 (tijdmap 1600, u_inlet 16 m/s,
  rho 1,225): klaar in ±24 s, geen crashes of geheugenproblemen
  (piek ruim onder de 5,5 GB vrije ruimte); output:
  - `output-custom/results.csv`
  - `output-custom/Run_Tandem_027_slice_y0.png`
  - `output-custom/Run_Tandem_027_postprocessing.log`
- Resultaten: pilot weerstand 22,3 N (frontaal 0,291 m², CD 0,489,
  CdA 0,142), stoker 17,0 N (frontaal 0,279 m², CD 0,387, CdA 0,108);
  totaal 39,3 N (frontaal-silhouette 0,300 m², CD 0,836, CdA 0,251).
- 16 unittests op een volledig fictieve mini-case-generator
  (`tests/foam_fixture.py`): lezers, geometrie, krachten, frontaal
  oppervlak, volledige route, CLI en weigering bij bestaande map. Altijd
  draaien met: `py -m unittest discover -s tests -v`.

## Bevindingen tijdens de bouw

- De ForceCoeff-configuratie in de case verwijst naar patches
  `(GCM).*`; die bestaan niet in deze mesh (pilot, stoker), dus
  hergebruik van forceCoeff-uitvoer viel af.
- `output-custom` stond eerder met handmatige referentiebestanden
  (results.csv, 2 png’s); die zijn vóór de build verdwenen uit de
  case-map (door de gebruiker verplaatst of verwijderd, mogelijk
  OneDrive-sync). De map bevatte bij de testrun alleen het log van een
  eerdere mislukte poging; de run is met `--overwrite` gedaan. **Tip:**
  bewaar een kopie van de handmatige referentiewaarden voor de
  validatievergelijking.

## Nog te valideren (door de onderzoeker)

- Vergelijk `results.csv` met de bestaande postprocessing van dezelfde
  case (acceptatiecriterium versie 1). Controleer met name of
  druk-/schuifverdeling en CdA in de lijn liggen van eerdere waarden
  (verwachting tandem: voorste renner meer, achterste renner
  duidelijk minder weerstand; daar kloppen de resultaten mee).
- Beoordeel de slice-figuur (bereik, kleurschaal tot 1,05·u_inlet,
  strookdikte 0,02 m) en de frontale silhouette-resolutie van 2 mm.

## Open punten voor versie 2 (bewust buiten versie 1)

- Geometriefiguur met Cp-distributie en additionele slices
  (plan-van-aanpak.md, sectie 9).
- Batchverwerking van meerdere cases met batch-logging.
- Uitlijnen van de frontale-oppervlakmethode als de validatie daar
  aanleiding toe geeft (rasterresolutie `--frontal-dx` is instelbaar).
