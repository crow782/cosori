# Food Diary SQLite – registro di sviluppo

Questo file registra le fasi del prototipo per rendere il lavoro riprendibile in futuro, anche da un'altra sessione o da un altro sviluppatore.

## Regole di isolamento

- Branch di lavoro: `waage+scanner`.
- Tutto il codice sperimentale resta in `homeassistant/prototypes/food_diary_sqlite/`.
- Non copiare il prototipo in `custom_components` e non installarlo nel sistema Home Assistant attivo.
- Non modificare `homeassistant/packages/food_diary.yaml` né i firmware in `esphome/` durante questa fase.
- Non committare database reali, backup, credenziali, token o dati personali.
- Ogni fase deve riportare esplicitamente se i test sono stati eseguiti oppure soltanto scritti.

## Fase 0 – base del prototipo

**Obiettivo:** verificare il modello di persistenza prima di sviluppare l'integrazione Home Assistant.

**File:**
- `storage.py`: accesso al database tramite la libreria standard Python `sqlite3`.
- `schema.sql`: schema SQL leggibile.
- `tests/test_storage.py`: test automatici.
- `README.md`: istruzioni e limiti.

**Modello:**
- `foods` contiene il catalogo locale, con barcode facoltativo e univoco.
- `entries` contiene una riga per ogni porzione consumata.
- Ogni porzione conserva nome, marca e valori nutrizionali usati al momento della registrazione.
- I nutrienti sconosciuti sono rappresentati da SQL NULL / Python None.
- I timestamp vengono normalizzati in UTC.

## Fase 1 – correzione aggiornamento parziale e aggregazioni

**Interventi:**

1. Corretto `update_food`: quando viene aggiornato un solo nutriente, gli altri valori già memorizzati vengono mantenuti. Un campo passato esplicitamente a `None` viene invece cancellato.
2. Aggiunto `period_summary(period, anchor_date, timezone_name)`.
3. Supportati i periodi `day`, `week` e `month`.
4. La settimana inizia lunedì.
5. I confini dei periodi sono calcolati nel fuso IANA richiesto, ad esempio `Europe/Rome`, e poi convertiti in UTC per interrogare il database.
6. Il raggruppamento giornaliero viene effettuato dopo la conversione nel fuso locale: ciò evita errori al cambio di giorno e gestisce i giorni di 23/25 ore durante l'ora legale.
7. Il riepilogo restituisce conteggio voci, giorni con registrazioni, totali per periodo, dettagli per giorno e subtotali per pasto.
8. Se un nutriente è sconosciuto in tutte le voci del gruppo, il risultato resta `None`, non zero.
9. I nomi di fuso non validi e i periodi non supportati producono un errore di validazione.

**Test aggiunti:**
- aggiornamento parziale di un nutriente senza perdere gli altri;
- cancellazione esplicita di un nutriente con `None`;
- riepilogo giornaliero attraverso il cambio all'ora legale in Italia del 29 marzo 2026;
- settimana lunedì–domenica;
- riepilogo mensile;
- conservazione di nutrienti sconosciuti come `None`;
- rifiuto di un periodo non supportato.

**Stato test:** i test sono stati aggiunti al file, ma in questa fase non sono stati eseguiti. Non considerare il codice collaudato. Eseguire i comandi riportati sotto in un ambiente Python locale prima di qualsiasi installazione.

## Come eseguire i test

Dalla directory `homeassistant/prototypes/food_diary_sqlite/`:

```bash
python --version
python -m unittest discover -s tests -v
```

Requisito: Python 3.10 o superiore (il codice usa annotazioni di tipo moderne e `zoneinfo`; Home Assistant usa una propria versione Python che dovrà essere verificata separatamente).

Per un controllo sintattico aggiuntivo:

```bash
python -m py_compile storage.py tests/test_storage.py
```

I test creano un database temporaneo sotto la directory temporanea gestita da Python. Non puntare mai i test al database della configurazione Home Assistant.

## Contratto attuale di period_summary

Esempio:

```python
summary = store.period_summary(
    "week",
    "2026-11-25",
    "Europe/Rome",
)
```

Campi principali restituiti:
- `period`: day, week o month;
- `timezone`: fuso IANA usato;
- `start_date`: primo giorno incluso;
- `end_date_exclusive`: primo giorno escluso;
- `entry_count`: numero di porzioni;
- `days_with_entries`: numero di date locali con almeno una porzione;
- `totals`: somma dei nutrienti noti nel periodo;
- `by_day`: dettaglio giornaliero con conteggio, totali e `by_meal`.

I subtotali sono somme, non medie. Una futura UI potrà calcolare e mostrare anche medie giornaliere, ma dovrà dividerle per il numero di giorni con registrazioni (o dichiarare esplicitamente un diverso denominatore).

## Problemi e verifiche ancora aperti

- [ ] Eseguire tutti i test in Python locale.
- [ ] Verificare il comportamento con la versione Python della versione Home Assistant effettivamente installata.
- [ ] Valutare test per febbraio bisestile, passaggio dicembre/gennaio e periodi senza registrazioni.
- [ ] Valutare aggiornamento/migrazione dello schema con versionamento esplicito prima di rilasciare l'integrazione.
- [ ] Aggiungere query per medie giornaliere e statistiche per singolo pasto solo quando i requisiti UI saranno definiti.
- [ ] Implementare test di backup/ripristino SQLite.
- [ ] Solo dopo, iniziare l'integrazione custom isolata in una cartella prototipo distinta.

## Stato dei file originali

Il lavoro descritto in questo registro riguarda esclusivamente la cartella del prototipo. Il package attivo e il firmware ESPHome non fanno parte di questa fase e non devono essere considerati modificati.

## Fase 2 – precisione timestamp, migrazione e CI

**Motivazione:** le aggregazioni usano intervalli UTC con estremi inclusivi/esclusivi. Per evitare ordinamenti ambigui e perdita di precisione, i nuovi timestamp vengono salvati sempre con sei cifre decimali.

**Interventi:**
1. `_now()` e `_timestamp()` ora conservano i microsecondi.
2. Incrementata la versione dello schema SQLite a 2 tramite `PRAGMA user_version`.
3. All'apertura, un database versione 1 viene migrato normalizzando i timestamp delle registrazioni già presenti a UTC con sei cifre decimali. Questo evita che le righe storiche al confine di mezzanotte vengano escluse dai nuovi intervalli.
4. Database con una versione superiore a quella supportata vengono rifiutati esplicitamente.
5. `period_summary` rifiuta un `datetime` passato al posto di una `date`, per evitare date con orario implicito.
6. Aggiornato `schema.sql` alla versione 2.

**Test aggiunti:**
- conservazione dei microsecondi e conversione in UTC;
- migrazione di un database versione 1 con timestamp al secondo;
- verifica che una registrazione esattamente sul confine sia inclusa dopo la migrazione;
- riepilogo vuoto;
- separazione dicembre/gennaio;
- febbraio bisestile;
- rifiuto di un oggetto `datetime` come `anchor_date`;
- verifica della versione schema.

**CI aggiunta:** `.github/workflows/food-diary-prototype-tests.yml` esegue compilazione e unit test su Python 3.10, 3.11, 3.12 e 3.13 quando cambiano i file del prototipo, sulle pull request pertinenti o manualmente da GitHub Actions.

**Stato test:** i test sono stati aggiunti e la workflow CI è stata committata, ma al momento della documentazione l'API GitHub non mostra ancora alcuna esecuzione. Quindi i test non sono da considerare superati.

## Passaggio successivo

Prima di creare il componente Home Assistant vero e proprio:
- attendere/verificare una esecuzione CI;
- controllare i risultati della matrice Python;
- fissare la versione minima di Home Assistant supportata e la modalità d'installazione (HACS/manuale) in base alla versione Core effettiva;
- solo dopo creare il componente sperimentale in una cartella separata, senza copiarlo nella configurazione attiva.
