# AGENTS.md — werkafspraken voor coding agents

Dit project is `cfd-rans-postproc`: automatische postprocessing van
OpenFOAM RANS-simulaties van sporters, in Python, lokaal, zonder ParaView.
Lees vóór aanvang `plan-van-aanpak.md`; dat plan is leidend voor scope en
acceptatiecriteria van de versies.

## Werkwijze

- Bouw in kleine, concrete stappen; houd versie 1 bewust beperkt tot de
  scope in `plan-van-aanpak.md` (§8).
- Na iéder versie: een commit en een push naar GitHub, plus een korte
  samenvatting van de nieuwe functionaliteit in `docs/handoffs/`.
- Bij het sluiten van een sessie: maak een nieuwe handoff in
  `docs/handoffs/` en herinner de gebruiker daar actief aan.
- Stop na versie 1 voor validatie door de gebruiker; bouw versie 2 pas na
  akkoord.
- Python-modules met underscores; documenten in kleine letters met
  streepjes; vaste namen `AGENTS.md`, `README.md`, `plan-van-aanpak.md`.
- De repository bevat uitsluitend code en documentatie — nooit
  simulatiedata, geometrie of andere vertrouwelijke bestanden.

## Data access

- Data-eigenaar/bevoegde rol: de gebruiker (onderzoeker, TU Delft-context).
  Toestemming: lezen van de case-mappen en voorbeelden zoals in
  plan-van-aanpak.md; alleen lokaal.
- Opzet: toegestaan sample (voorbeeldcase Run_Tandem_027) naast fictieve
  voorbeelden; geen ruwe veldwaarden kopiëren naar de repo.
- Uitvoering: gebruiker en agent lokaal op de werkmachine.
- Agent mag lezen: de aangewezen voorbeeldcase, de ParaView-voorbeelden
  (`.pvsm`) en de commerciële PDF op de paden genoemd in
  plan-van-aanpak.md — uitsluitend lokaal en alleen om structuur en
  outputvorm te begrijpen.
- Agent mag niet lezen, printen of uploaden: `data/private/`, `.env`,
  `.env.*` (uitzondering: `.env.example` met uitsluitend fictieve
  waarden), en alle oplossingsvelden of geometrie buiten de aangewezen
  voorbeeldcase; niets uit deze paden naar GitHub, online opslag of de
  agentcontext.
- Gebruikersnamen en wachtwoorden: nooit lezen, printen of opslaan in de
  repository; dit geldt ook voor `.env`-bestanden.
- Lokaal verwerken van echte data: toegestaan binnen de aangewezen
  voorbeeldcase; geen kopiëren, verplaatsen of publiceren van data.
- Ontwikkel en test met fictieve data in `data/example/`; elk voorbeeld
  < 1 MB. Voorbeelden van echte cases moeten geschoond zijn voordat ze in
  Git komen.
- Output: alleen berekende kernwaarden (CdA, CD, frontaal oppervlak),
  figuren en samenvattingen; gegenereerde resultaten blijven binnen de
  CFD-hoofdmap (per case in `output-custom`), buiten de repository.
- Technische toegangsregels (deny-regels per agent, o.a. voor
  `data/private/` en `.env`): nog in te stellen en te testen met een
  fictief proefbestand; nog niet geconfigureerd.
- Zolang toestemming of technische bescherming onduidelijk is: alleen
  fictieve data.

## Logging

- Per verwerkte case een logbestand in `output-custom` van die case:
  opgetreden fouten en hun reden, aangevuld met korte statusregels
  (tijdstip, component, status) van de belangrijke verwerkingen.
- Geen secrets, gebruikersnamen, wachtwoorden, persoonsgegevens of
  volledige veldwaarden in logs of foutmeldingen.
- Ruwe runtime- en testlogs (`logs/runtime/`, `logs/test/`) blijven
  buiten Git; geschoonde ontwikkelverslagen staan in `docs/handoffs/`.
