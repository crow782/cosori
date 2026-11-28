# Food Diary SQLite – prototipo isolato

> **NON INSTALLARE IN PRODUZIONE.** Questo prototipo è separato dai package e dai firmware attuali. Non modifica né sostituisce `homeassistant/packages/food_diary.yaml`, i file ESPHome o la configurazione Home Assistant esistente.

## Scopo

Validare il livello di persistenza prima di scrivere l'integrazione Home Assistant e la dashboard Lovelace. Il prototipo usa soltanto Python standard library e SQLite.

## Contenuto

- `storage.py`: archivio SQLite, catalogo alimenti e diario delle porzioni.
- `schema.sql`: schema leggibile del database (lo storage applica lo stesso schema all'inizializzazione).
- `DEVELOPMENT_LOG.md`: registro delle fasi, delle scelte e dei controlli.
- `tests/test_storage.py`: test automatici senza dipendenze esterne.
- `DEVELOPMENT_LOG.md`: registro delle decisioni, delle modifiche e dello stato dei test.

## Esecuzione test

Dalla cartella del prototipo:

```bash
python -m unittest discover -s tests -v
```

I test usano un database temporaneo e non scrivono nella configurazione Home Assistant.

## Modello

- `foods`: catalogo alimenti, barcode univoco se presente, nutrienti per 100 g; valori sconosciuti memorizzati come SQL NULL.
- `entries`: singole porzioni consumate con pasto, data/ora ISO 8601, origine e snapshot di nome, marca e nutrienti. Modificare un alimento nel catalogo non cambia le registrazioni precedenti.

I pasti ammessi sono `breakfast`, `lunch`, `dinner`, `snack`. Le date devono includere un offset UTC per evitare timestamp ambigui. I timestamp vengono normalizzati in UTC preservando la precisione al microsecondo. Il database usa `PRAGMA user_version` (versione schema 2); all'apertura viene applicata la migrazione dalla versione 1, che normalizza i timestamp preesistenti alla precisione uniforme. Versioni future non riconosciute vengono rifiutate invece di essere aperte silenziosamente.

## Riepiloghi temporali

Il metodo `period_summary(period, anchor_date, timezone_name)` supporta `day`, `week` e `month`. `anchor_date` accetta una data (non un datetime). Restituisce il totale del periodo e le righe giornaliere, con subtotali per pasto. La settimana inizia lunedì. `timezone_name` è un identificatore IANA, ad esempio `Europe/Rome`; i confini del periodo sono calcolati nel fuso locale e convertiti in UTC per la query. In questo modo sono gestiti anche i giorni di 23 o 25 ore dovuti all'ora legale.

I nutrienti vengono sommati solo quando noti: se tutte le voci hanno un determinato nutriente sconosciuto, il totale resta `null` (`None` in Python), non zero. Le statistiche settimanali e mensili includono `days_with_entries`, così i giorni senza registrazioni non vengono confusi con giorni a zero calorie.

Durante `update_food`, i nutrienti non specificati vengono mantenuti. Per azzerare esplicitamente un valore occorre passare quel nutriente con valore `None`.

## Limiti attuali

Questo è solo il livello dati. Non contiene ancora:
- integrazione caricabile in Home Assistant, config flow o servizi;
- chiamate Open Food Facts;
- collegamento a Cosori/GM67;
- gestione delle sessioni di scansione;
- dashboard o moduli Lovelace;
- migrazione dei dati dal package attuale.

Non copiare questi file in `custom_components` e non cambiare la configurazione attiva. Prima si eseguono i test isolati; poi si valuterà una vera integrazione con test su una copia di Home Assistant.
