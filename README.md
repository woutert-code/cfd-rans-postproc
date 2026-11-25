# cfd-rans-postproc

Automatische postprocessing van OpenFOAM RANS-simulaties van sporters in
een luchtstroming (wielrenners, schaatsers, skeleton-atleten), lokaal in
Python — zonder ParaView of een OpenFOAM-installatie. Het script leest
uitsluitend de oplossingsdata van een simulatie en genereert per case:

- `results.csv`: luchtweerstand (N), CdA (m²), frontaal oppervlak (m²) en
  CD per atleet en totaal, plus per atleet het aandeel (%) in de totale
  luchtweerstand (`aandeel_van_totaal_pct`);
- een slice-figuur van het stromingsveld met de luchtsnelheid in
  x-richting;
- een logbestand met fouten en de voortgang van de verwerking.

De resultaten worden weggeschreven in een nieuwe map `output-custom`
binnen de map van de betreffende simulatie.

> **Vertrouwelijkheid:** de repository bevat alleen code en documentatie.
> Simulatiedata, geometrie en gegenereerde output blijven lokaal in de
> hoofdmap met CFD-cases en komen nooit in Git of online. Zie
> `AGENTS.md` en `plan-van-aanpak.md`.

## Werken met deze repository

- `plan-van-aanpak.md` — het plan van aanpak; leidend voor scope en
  acceptatiecriteria per versie.
- `AGENTS.md` — werkafspraken voor coding agents (data-toegang, logging,
  Git-werkwijze).
- `docs/handoffs/` — geschoonde verslagen per versie en per sessie.
- `src/cfd_postproc/` — de Python-package.
- `tests/` — gerichte unittests met kleine, fictieve voorbeedelcases.

## Vereisten

- **Python 3.11+** met **tkinter** (bij de standaardinstallatie van Python op
  Windows inbegrepen, ook de Microsoft Store-versie);
- `numpy`, `matplotlib`, `pillow`.

Installeren van de overige packages kan met:

```bash
python -m pip install numpy matplotlib pillow
```

Op deze machine is Python geïnstalleerd via de Microsoft Store en is de
`py`-launcher **niet** beschikbaar: gebruik dus overal `python` in plaats
van `py`.

## Starten via start.bat (interactief)

Dubbelklik `start.bat` in de repo-root (werkt vanaf elke locatie). Er opent
een startscherm waarin je de CFD-case map kiest ("Bladeren..."), optioneel
de slice-posities (y en x) aanpast (invoer: komma-gescheiden posities in
meter, bijv. `0.0` of `-1.0,0.0,0.5` — zie de hint onder de velden), het
vinkje "output-custom
overschrijven" zet en op **Start postprocessing** klikt. De overige
instellingen staan vast op de standaardwaarden (atleetpatches `pilot,stoker`,
rho 1,225 kg/m³, u-ref uit `u_inlet` in `system/Variables`, laatst
weggeschreven tijdmap, strookdikte 0,02 m) — voor afwijkende waarden gebruik
je de CLI hieronder. Tijdens de verwerking verschijnt de log live in het
scherm; na afloop toont het scherm de resultaten uit `results.csv` in een
tabel: luchtweerstand [N] met aandeel van het totaal [%], frontaal
oppervlak [m²], CD en CdA [m²] per atleet en totaal. `results.csv`, de slice-figuren en het logbestand worden
weggeschreven naar `output-custom` in de case-map; de figuren worden niet
geopend. In het startscherm staat onder de slice-velden een notitie hierover,
inclusief de opmerking dat de manier waarop slices worden gemaakt in een
volgende versie wordt verbeterd (plan-van-aanpak.md §12, punt 7).

Met **Geometrie tonen** opent een apart venster met de solid-geometrie van
Met **Geometrie tonen** opent een apart venster met de solid-geometrie van
de atleetpatches (`pilot,stoker`). De geometrie wordt bij voorkeur gehaald
uit **STL-bestanden**: eerst `constant/triSurface` in de case zelf, daarna
in de bijbehorende mesh-map naast de case (bij bijv. `Run_Tandem_027` de map
`Mesh_Tandem_027`, bestanden `pilot.stl` en `stoker.stl`). In dat geval hoeft
de polyMesh helemaal niet gelezen te worden — de aanzichten staan dan binnen
enkele seconden in het scherm, ook voor grote cases, en de weergave is de
originele CAD-oppervlakte i.p.v. de gesnapte mesh-vlakken. De STL-bestanden
blijven vertrouwelijk en buiten Git. Als er geen STL's beschikbaar zijn,
valt het venster terug op de polyMesh-route: vooraanzicht, zijaanzicht en
bovenaanzicht (2D, gerasteriseerd over alle faces, met de afmetingen uit de
bounding box — lengte × breedte × hoogte) plus een 3D-figuur die met de muis
draaibaar is (scroll = zoomen). Voor de 3D wordt het oppervlak cel-geïdecimeerd
(één face per oppervlakte-cel, ≤ 20.000 polygonen) en worden de polygonen
licht opgeblazen rond hun zwaartepunt, zodat het solid is zonder gaten bij
grote meshes (zie `src/cfd_postproc/geometrie.py`).

## Gebruik via de CLI (batch)

Vanuit de repositorymap:

```bash
python -m src.cfd_postproc --case "pad/naar/simulatiemap" [--time 1600]
```

Opties (bekijk ze allemaal met `--help`):

- `--case` — map van de simulatie (vereist);
- `--time` — te verwerken tijdmap; standaard de laatst weggeschreven tijd;
- `--body-patches` — wanden van de atleten, standaard `pilot,stoker`;
- `--slice-y` — positie(s) van slice-vlakken in y-richting, komma-gescheiden, standaard 0;
- `--slice-x` — idem in x-richting, standaard 0;
- `--rho` en `--u-ref` — luchtdichtheid (standaard 1,225 kg/m³) en
  referred in klassnelheid (standaard uit `system/Variables`: `u_inlet`);
- `--overwrite` — sta schrijven naar een bestaande `output-custom` toe.

## Controleren

```bash
python -m unittest discover -s tests -v
```

De acceptatie van versie 1 wordt bepaald door vergelijking van de
gegenereerde waarden met de bestaande postprocessing van de onderzoeker
(zie `plan-van-aanpak.md`, §8).
