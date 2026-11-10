# logs

Afspraken voor logging in deze repository.

- **Per simulatiecase** schrijft het tool het logbestand naar
  `output-custom/<case>_postprocessing.log` in de map van die case, mét
  tijdstip, onderdeel (component) en status per verwerking plus fouten met
  hun reden. Case-logs horen bij de case en komen niet in deze repo.
- `logs/runtime/` — eventuele uitvoerlogs van lokale ontwikkelruns; buiten
  Git.
- `logs/test/` — ruwe testuitvoer; buiten Git.
- Geschoonde ontwikkelverslagen per versie en sessie staan in
  `docs/handoffs/`; die zijn wel in Git.
- In logs komt nooit: vertrouwelijke data, atleetgeometrie, secrets of
  gebruikersnamen/wachtwoorden; ook niet in foutmeldingen.
