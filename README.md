# cfd-rans-postproc

Automatische postprocessing van OpenFOAM RANS-simulaties van sporters in
een luchtstroming (wielrenners, schaatsers, skeleton-atleten), lokaal in
Python — zonder ParaView of een OpenFOAM-installatie. Het script leest
uitsluitend de oplossingsdata van een simulatie en genereert per case:

- `results.csv`: luchtweerstand (N), CdA (m²), frontaal oppervlak (m²) en
  CD per atleet en totaal;
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

- Python 3.11+ met `numpy`, `matplotlib` en `pillow`.

## Gebruik

Vanuit de repositorymap:

```bash
py -m src.cfd_postproc --case "pad/naar/simulatiemap" [--time 1600]
```

Opties (bekijk ze allemaal met `--help`):

- `--case` — map van de simulatie (vereist);
- `--time` — te verwerken tijdmap; standaard de laatst weggeschreven tijd;
- `--body-patches` — wanden van de atleten, standaard `pilot,stoker`;
- `--slice-y` — positie van de slice in y-richting, standaard 0;
- `--rho` en `--u-ref` — luchtdichtheid (standaard 1,225 kg/m³) en
  referred in klassnelheid (standaard uit `system/Variables`: `u_inlet`);
- `--overwrite` — sta schrijven naar een bestaande `output-custom` toe.

## Controleren

```bash
py -m unittest discover -s tests -v
```

De acceptatie van versie 1 wordt bepaald door vergelijking van de
gegenereerde waarden met de bestaande postprocessing van de onderzoeker
(zie `plan-van-aanpak.md`, §8).
