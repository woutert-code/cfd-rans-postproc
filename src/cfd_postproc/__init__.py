"""cfd_postproc — lokale postprocessing van OpenFOAM RANS-cases van sporters.

Versie 1: leest de oplossing van een gereconstrueerde simpleFoam-case
(binaire schrijfwijze), berekent luchtweerstand, CdA, frontaal oppervlak en
CD, en maakt een slice-figuur van de luchtsnelheid in x-richting. Zie
plan-van-aanpak.md in de repositoryroot voor scope en acceptatiecriteria.
"""

__version__ = "0.1.0"
