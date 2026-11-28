# Food Diary SQLite – prototipo isolato

> **NON INSTALLARE IN PRODUZIONE.** Questo prototipo è separato dai package e dai firmware attuali. Non modifica né sostituisce `homeassistant/packages/food_diary.yaml`, i file ESPHome o la configurazione Home Assistant esistente.

## Scopo

Validare il livello di persistenza prima di scrivere l'integrazione Home Assistant e la dashboard Lovelace. Il prototipo usa soltanto Python standard library e SQLite.

## Contenuto

- `storage.py`: archivio SQLite, catalogo alimenti e diario delle porzioni.
- `schema.sql`: schema leggibile del database (lo storage applica lo stesso schema all'inizializzazione).
- `tests/test_storage.py`: test automatici senza dipendenze esterne.

## Esecuzione test

Dalla cartella del prototipo:

```bash
python -m unittest discover -s tests -v
```

I test usano un database temporaneo e non scrivono nella configurazione Home Assistant.

## Modello

- `foods`: catalogo alimenti, barcode univoco se presente, nutrienti per 100 g; valori sconosciuti memorizzati come SQL NULL.
- `entries`: singole porzioni consumate con pasto, data/ora ISO 8601, origine e snapshot di nome, marca e nutrienti. Modificare un alimento nel catalogo non cambia le registrazioni precedenti.

I pasti ammessi sono `breakfast`, `lunch`, `dinner`, `snack`. Le date devono includere un offset UTC per evitare timestamp ambigui.

## Limiti attuali

Questo è solo il livello dati. Non contiene ancora:
- integrazione caricabile in Home Assistant, config flow o servizi;
- chiamate Open Food Facts;
- collegamento a Cosori/GM67;
- gestione delle sessioni di scansione;
- dashboard o moduli Lovelace;
- migrazione dei dati dal package attuale.

Non copiare questi file in `custom_components` e non cambiare la configurazione attiva. Prima si eseguono i test isolati; poi si valuterà una vera integrazione con test su una copia di Home Assistant.
