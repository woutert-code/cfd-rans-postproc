# DECISIONS.md — Technische en functionele besluiten

Dit document bevat alle importante besluiten die genomen zijn tijdens de ontwikkeling van `cfd-rans-postproc`.
Elk besluit is gedateerd en genummerd voor traceerbaarheid.

---

## Besluit 001: Gebruik van mean-velden uit OpenFOAM-cases

**Datum:** 2026-11-10
**Status:** Actief
**Beslissing:**

> **Altijd de tijdsgemiddelde (mean) velden uit de OpenFOAM-case gebruiken voor postprocessing.**
> Als mean-velden niet beschikbaar zijn, moet dit worden **gemeld in het logbestand**,
> en mag er **als fallback** gebruik worden gemaakt van de instantane (niet-gemiddelde) velden.

### Toepassing

Voor de volgende velden geldt:
- **Druk:** `pMean` → fallback: `p`
- **Snelheid:** `UMean` → fallback: `U`
- **Wandschuifspanning:** `wallShearStressMean` → fallback: `wallShearStress`

### Implementatie

In `src/cfd_postproc/case_runner.py`:
```python
p_path = os.path.join(t, "pMean") if os.path.exists(os.path.join(t, "pMean")) else os.path.join(t, "p")
wss_path = os.path.join(t, "wallShearStressMean") if os.path.exists(wss_path) else os.path.join(t, "wallShearStress")
u_path = os.path.join(t, "UMean") if os.path.exists(u_path) else os.path.join(t, "U")
```

### Logging

Als mean-velden ontbreken, wordt een **WARNING** gelogd:
```
WARNING: mean-velden ontbreken: <lijst>; valt terug op niet-gemiddelde velden
```

### Motivatie

1. **Nauwkeurigheid:** Tijdsgemiddelde velden (`*Mean`) zijn **stabiel** en representatief voor RANS-simulaties
2. **Consistentie:** Alle krachten (druk, schuif) en visualisaties gebruiken dezelfde tijdsbasis
3. **Flexibiliteit:** Fallback naar instantane velden zorgt voor **robuustheid** als mean-velden ontbreken
4. **Transparantie:** Gebruiker weet via het logbestand welke velden daadwerkelijk zijn gebruikt

### Impact

- **Versie 1.1+:** Gebruikt mean-velden waar beschikbaar
- **Validatie:** Resultaten met mean-velden zijn betrouwbaarder voor RANS-simulaties
- **Fallback:** Script blijft werken als mean-velden ontbreken (bijv. in testcases)

---

## Template voor nieuwe besluiten

```markdown
## Besluit XXX: [Korte titel]

**Datum:** YYYY-MM-DD
**Status:** Actief / Verouderd / Vervangen door [nr]
**Beslissing:**

> [Beschrijving van het besluit]

### Toepassing

[Hoe wordt het besluit toegepast?]

### Implementatie

[Code voorbeeld of referentie naar bestandslocatie]

### Motivatie

[Redenen voor dit besluit]

### Impact

[Gevolgen voor de code, gebruikers, validatie, etc.]
```

---

## Overzicht van actieve besluiten

| Nr | Titel | Datum | Status |
|----|-------|-------|--------|
| 001 | Gebruik van mean-velden | 2026-11-10 | Actief |
