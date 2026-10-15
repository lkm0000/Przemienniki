# Przemienniki PL → Icom ID-52

Pipeline generujacy plik CSV z polskimi przemiennikami do importu w radiu Icom ID-52.

## Zrodla danych

- **[mapy73.pl](https://mapy73.pl)** — baza YAML z repo [Hotel-Foxtrot-Tango-Echo/przemienniki-mapy73pl](https://github.com/Hotel-Foxtrot-Tango-Echo/przemienniki-mapy73pl) (AGPL-3.0)
- **[przemienniki.net](https://przemienniki.net)** — eksport RXF XML

## Pobieranie CSV

Najnowszy plik CSV dostepny jest w [GitHub Releases](../../releases/tag/latest) — budowany automatycznie codziennie o 01:17 UTC (03:17 czasu letniego, 02:17 zimowego).

## Uzycie lokalne

```bash
# Instalacja
pip install -e ".[dev]"

# Uruchomienie pipeline
python -m src --work-dir work --output output/przemienniki_id52.csv

# Testy
pytest -v
```

### Opcje CLI

| Flaga | Domyslnie | Opis |
|---|---|---|
| `--work-dir` | `work/` | Katalog roboczy (klony repo, pobrany XML) |
| `--output` | `output/przemienniki_id52.csv` | Sciezka wynikowego CSV |
| `--force` | off | Buduj niezaleznie od fingerprint |

## Pipeline

1. **Fetch** — klonowanie repo mapy73 + pobranie rxf.xml
2. **Parse** — parsowanie YAML i XML do wspolnego modelu `Repeater`
3. **Merge** — deduplikacja po `(call, band, mode)` z tolerancja 5 kHz
4. **Voivodeships** — przypisanie wojewodztw (GeoJSON + point-in-polygon)
5. **Export** — filtr FM + D-STAR, 2m + 70cm, status aktywny/testowy → CSV ID-52

## Format CSV (Icom ID-52)

Grupy = wojewodztwa (1-16). Kolumny:

```
Group No, Group Name, Name, Sub Name, Repeater Call Sign, Gateway Call Sign,
Frequency, Dup, Offset, Mode, TONE, Repeater Tone, RPT1USE,
Position, Latitude, Longitude, UTC Offset
```

## Licencja

AGPL-3.0 — patrz [LICENSE](LICENSE).
