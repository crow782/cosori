# Food Diary — contratto dati tra SQLite, integrazione e dashboard

> Specifica tecnica del prototipo. Descrive le API attualmente presenti e le regole che la dashboard dovrà rispettare. Non è un'implementazione frontend e non rende installabile l'integrazione.

## 1. Architettura

```text
Cosori BLE + GM67
      │ eventi ESPHome
      ▼
Home Assistant automazioni / script
      │ barcode + peso stabile + conferma utente
      ▼
food_diary integration (azioni HA)
      │ esecuzione SQLite fuori dall'event loop
      ▼
food_diary.db
      ▲
      │ risposte strutturate delle azioni
Dashboard Food Diary (frontend da scegliere)
```

Responsabilità:
- ESP32: acquisizione BLE della bilancia e lettura barcode; non interroga Open Food Facts e non scrive nel database.
- Home Assistant: orchestration scanner/bilancia, lookup Open Food Facts, gestione sessione e conferma.
- Integrazione Food Diary: archivio locale, registrazioni persistenti, query intervalli e aggregazioni.
- Dashboard: presentazione, ricerca, form, validazione e conferma; non calcola autonomamente i totali storici.

## 2. Modello dati

### Food (catalogo)
Un alimento è una scheda riutilizzabile: `id`, `name`, `brand`, `barcode`, `source` e nutrienti per 100 g. Il barcode è univoco quando presente. I nutrienti mancanti sono `null`.

### Entry (consumo)
Una registrazione è una porzione consumata: `id`, `food_id`, snapshot di nome/marca/barcode, `weight_g`, `meal_type`, `consumed_at`, `source`, nutrienti calcolati della porzione e snapshot dei nutrienti per 100 g.

La registrazione conserva uno snapshot: modificare in futuro il catalogo non deve cambiare retroattivamente ciò che è stato registrato. Se una scheda alimento viene eliminata, la registrazione resta consultabile grazie agli snapshot e `food_id` diventa NULL.

Pasti ammessi: `breakfast`, `lunch`, `dinner`, `snack`. Sorgenti entry: `scan`, `catalog`, `manual`.

## 3. Azioni Home Assistant già presenti

Dominio: `food_diary`. I nomi seguenti sono quelli registrati nel prototipo `custom_components/food_diary/services.py`.

| Azione | Input | Risposta |
|---|---|---|
| `search_foods` | `query`, `limit` | `foods[]` |
| `find_food_by_barcode` | `barcode` | `food` oppure null |
| `add_food` | `name`, opzionali `brand`, `barcode`, `nutrients_per_100g`, `source` | alimento creato, se richiesta risposta |
| `update_food` | `food_id` e campi da aggiornare | alimento aggiornato, se richiesta risposta |
| `delete_food` | `food_id` | nessun payload |
| `add_entry` | `food_id`, `weight_g`, `meal_type`, opzionali `consumed_at`, `source` | registrazione creata, se richiesta risposta |
| `list_entries` | `start`, `end` ISO con offset | `entries[]` |
| `delete_entry` | `entry_id` | nessun payload |
| `period_summary` | `period`, `anchor_date`, `timezone` | riepilogo strutturato |

Le query temporali usano intervalli semiaperti `[start, end)`. Le date del calendario sono interpretate nel fuso IANA passato alla summary, poi convertite in UTC per interrogare SQLite. La settimana inizia lunedì.

## 4. Contratto dei riepiloghi

La risposta corrente di `period_summary` contiene:
- `period`, `timezone`, `start_date`, `end_date_exclusive`;
- `entry_count`, `days_with_entries`;
- `totals` con un valore per nutriente oppure null;
- `by_day[]`, ciascuno con `date`, `entry_count`, `totals` e `by_meal`.

Regole confermate:
1. Una data assente da `by_day` è "nessun dato", non zero.
2. Il totale periodo somma le registrazioni presenti nell'intervallo.
3. La media giornaliera esclude le giornate senza registrazioni.
4. Un nutriente sconosciuto resta null; non deve essere trasformato in zero.

**Estensione appena implementata nel prototipo SQLite:** la risposta ora include:
- `days_with_entries`: giorni con almeno una registrazione;
- `days_with_energy_data`: giorni con almeno un valore kcal noto;
- `average_daily_energy_kcal`: media sulle giornate con kcal note;
- `average_days_count`: numero di giorni effettivamente usati nel denominatore;
- `nutrient_coverage`: per nutriente, numero di voci note, mancanti e flag di completezza, sia per il periodo sia per ogni giorno.

La media esclude i giorni senza registrazioni e anche i giorni per cui tutte le kcal sono sconosciute. Se una giornata contiene sia voci con kcal note sia voci senza kcal, la somma nota viene mantenuta ma la copertura segnala che è parziale: la UI deve mostrarlo chiaramente e non presentare il valore come completo. Nessun `null` viene convertito in zero.

**Verifica ancora necessaria:** il codice e i test sono stati aggiornati, ma i test devono passare nella CI prima di considerare validata questa estensione.

## 5. Flusso di acquisizione barcode + bilancia

Stati logici da rappresentare nell'interfaccia:
1. `idle`: in attesa.
2. `tare_required`: peso residuo o piatto non azzerato; chiedere tara.
3. `waiting_barcode`: zero stabile confermato, scanner pronto.
4. `barcode_received`: barcode acquisito e associato alla sessione.
5. `product_found`: trovato in archivio locale oppure in Open Food Facts.
6. `product_unknown`: nessun risultato; offrire ricerca alternativa, selezione catalogo o nuovo alimento.
7. `waiting_stable_weight`: attendere peso positivo stabile.
8. `review`: mostrare prodotto, grammi, pasto, nutrienti noti e valori mancanti.
9. `saved`: registrazione persistita.
10. `error` / `cancelled`: errore recuperabile o sessione annullata.

Vincoli:
- Prima della scansione eseguire tara e verificare zero stabile.
- Un solo prodotto pendente per sessione; evitare sovrascrittura del barcode.
- La pesata non va persa se il barcode non esiste in OFF.
- L'utente ha scelto la registrazione automatica quando il peso diventa stabile; mantenere l'opzione attiva di default, ma verificare il flusso end-to-end prima dell'uso reale.
- La bilancia non esegue tara via BLE secondo le verifiche attuali: la tara è un'operazione fisica.

## 6. Responsabilità del frontend

La dashboard deve:
- chiamare le azioni dell'integrazione e visualizzare le risposte;
- mantenere stati di caricamento, errore, nessun risultato e conferma;
- non duplicare le formule di aggregazione;
- non trasformare `null` in 0;
- inviare data/ora con offset esplicito o lasciare che l'integrazione usi il proprio orologio configurato;
- ricaricare il riepilogo dopo ogni aggiunta, modifica o cancellazione.

## 6. Configurazione dispositivi e frontend

Versione di riferimento comunicata dall'utente: Home Assistant Core 2026.11.3, Supervisor 2026.11.0, OS 18.4, Frontend 20261028.8. L'obiettivo è mantenere compatibilità con il maggior numero possibile di release Core 2026.

La configurazione finale sarà tramite config flow e options flow:
- selezione del sensore peso stabile con entity selector (dominio sensor, device class weight, integrazione ESPHome);
- selezione diretta dell'entità barcode tramite entity selector generico sul dominio `sensor`, ad esempio `sensor.barcode_scanner_last_barcode`;
- selezione diretta del contatore scansioni tramite entity selector generico sul dominio `sensor`, ad esempio `sensor.barcode_scanner_scan_count`;
- nessun MAC BLE o UUID GATT da inserire manualmente;
- opzioni per pasto predefinito, salvataggio automatico, timeout, soglia zero e lookup Open Food Facts.

Il firmware ESPHome attuale espone anche un'entità `text_sensor`/`sensor` che contiene l'ultimo barcode, ad esempio `sensor.barcode_scanner_last_barcode`. Il config flow prototipo seleziona direttamente questa entità: non è necessario identificare il device ESPHome né aggiungere un ID al payload. Il firmware continua inoltre a emettere `esphome.barcode_scanned`: il coordinator lo usa come conferma solo se esiste un unico incremento pendente e il barcode coincide con il sensore selezionato. Il contatore resta il trigger e l'entità barcode il fallback per scanner generici.

L'utente ha verificato che `sensor.barcode_scanner_scan_count` incrementa a ogni scansione, anche quando `sensor.barcode_scanner_last_barcode` mantiene lo stesso valore. Il runtime ascolta quindi `state_changed` sul contatore selezionato e legge il barcode dall'entità selezionata. Il coordinator deve verificare l'ordine di pubblicazione dei due sensori per evitare di associare il nuovo conteggio al barcode precedente. Non basarsi su `last_changed` del barcode e non richiedere modifiche al firmware attivo.

Per mantenere un'unica installazione HACS, la direzione scelta è un pannello Aurora incluso nella cartella dell'integrazione, servito localmente e registrato tramite API pubbliche di Home Assistant. Il frontend non avrà dipendenze CDN o framework di nicchia. Se il pannello non supera i test sulle release target, fallback a dashboard Lovelace con card native.

Dettagli packaging: [HACS_ARCHITECTURE.md](../food_diary_integration/HACS_ARCHITECTURE.md).

## 7. Sicurezza e persistenza
- Database nel percorso di configurazione Home Assistant, non nella directory del repository.
- Non inserire token, API key o dati personali nel repository.
- Usare parametri SQL e validazione già presente nel livello storage.
- Mantenere backup del file SQLite e test di ripristino prima dell'uso reale.
- Tutto il codice resta in `homeassistant/prototypes/` fino al superamento dei test.

## 8. Verifiche necessarie prima dell'interfaccia reale
- Eseguire unit test SQLite e CI.
- Verificare che la copia `integration/.../storage.py` sia identica al modulo di riferimento.
- Validare integrazione con la versione Home Assistant Core effettiva, inclusi config flow e risposte delle azioni.
- Definire esattamente il contratto per copertura nutrienti e medie.
- Scegliere frontend in base alle API frontend realmente disponibili.
- Testare mobile, tablet e desktop.


## 10. Runtime acquisition state machine

The prototype coordinator consumes the selected scan counter as the new-scan gate and the selected stable-weight entity as the scale source. It also listens for the current ESPHome event esphome.barcode_scanned, whose payload contains the barcode for that scan. The current firmware publishes the counter first, publishes the last-barcode entity next, then emits the event after 300 ms. For the current ESPHome firmware, the event is accepted only as a confirmation when exactly one counter increment is pending and its payload matches the selected barcode entity. Because the event reads Last Barcode after a delay rather than carrying an immutable per-scan snapshot, overlapping scans are treated as ambiguous.

A generic scanner fallback is accepted only when exactly one counter increment is pending. Multiple increments without matching ESPHome events are treated as ambiguous and are never auto-saved. This is intentionally fail-safe rather than guessing which barcode belongs to which count.

A scan session requires a valid barcode, a zero weight at or below the configured threshold after the scan, a later positive reading from the selected stable-weight sensor, and a known local product or successful Open Food Facts lookup.

A non-zero weight at scan time does not count as the portion: the coordinator waits for zero and then a new positive stable reading. Tare remains a physical action; no tare BLE command is assumed.

Unknown products remain pending so a manual catalogue item with the same barcode can resolve the session. A pending session with an already captured positive weight does not expire while waiting for the manual product. Pending sessions are currently memory-only and are lost on Home Assistant restart. Only one active session is supported; additional scans while it is pending are rejected to prevent accidental cross-association.

## 11. Alternative product search

The integration exposes a search_openfoodfacts action for text-based alternatives when a barcode lookup does not find a product. It uses Open Food Facts' legacy full-text endpoint, returns a bounded list of normalized product candidates, and does not insert candidates into the local catalogue. The user must explicitly select a candidate and add it through the add_food action. Missing or invalid nutrient fields remain NULL.
