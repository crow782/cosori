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
- Prima della scrittura mostrare riepilogo e conferma; la registrazione automatica dopo peso stabile potrà essere abilitata come preferenza solo dopo aver verificato il flusso end-to-end.
- La bilancia non esegue tara via BLE secondo le verifiche attuali: la tara è un'operazione fisica.

## 6. Responsabilità del frontend

La dashboard deve:
- chiamare le azioni dell'integrazione e visualizzare le risposte;
- mantenere stati di caricamento, errore, nessun risultato e conferma;
- non duplicare le formule di aggregazione;
- non trasformare `null` in 0;
- inviare data/ora con offset esplicito o lasciare che l'integrazione usi il proprio orologio configurato;
- ricaricare il riepilogo dopo ogni aggiunta, modifica o cancellazione.

Decisione frontend ancora da prendere: card Lovelace native con helper/script di appoggio oppure custom Lovelace card. Per una UI Aurora con ricerca dinamica, risultati delle azioni e form ricchi, una custom card dedicata è probabilmente più lineare; va però verificato il meccanismo frontend supportato dalla versione Home Assistant installata prima di scrivere codice.

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
