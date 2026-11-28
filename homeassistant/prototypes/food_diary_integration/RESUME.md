# Food Diary — punto di ripresa del progetto

Ultimo aggiornamento documentale: 2026-11-28  
Repository: https://github.com/crow782/cosori  
Branch: `waage+scanner`

> Questo file è il punto di ingresso per riprendere il lavoro in una nuova sessione. Leggere prima questo documento, poi i file indicati. Il progetto è sperimentale: non installarlo nell'istanza Home Assistant attiva.

## 1. Ambiente e vincoli

Ambiente Home Assistant comunicato dall'utente:
- Home Assistant OS 18.4
- Core 2026.11.3
- Supervisor 2026.11.0
- Frontend 20261028.8

Vincoli permanenti:
- compatibilità più ampia possibile con le release Core 2026;
- usare API pubbliche e documentate di Home Assistant;
- evitare dipendenze runtime esterne o poco mantenute;
- non modificare package HA o firmware attivi prima di test e approvazione;
- mantenere tutto il lavoro sperimentale sotto homeassistant/prototypes/;
- non committare segreti, credenziali, database o dati personali;
- non dichiarare test superati senza output CI o test effettivamente eseguiti.

## 2. Decisioni funzionali già confermate

- Diario alimentare, non gestione dieta/ricette.
- Pasti: colazione, pranzo, cena, spuntino.
- Totali giornalieri, settimanali e mensili.
- Settimana da lunedì a domenica, fuso Home Assistant.
- Catalogo locale minimalista e alfabetico degli alimenti già scansionati o inseriti.
- Barcode non trovato: ricerca alternativa e inserimento manuale.
- Open Food Facts come fonte di lookup, con possibilità di disabilitarlo.
- Separare scheda alimento da porzione consumata.
- Ogni registrazione conserva uno snapshot dei nutrienti; modifiche future al catalogo non cambiano lo storico.
- Nutrienti ignoti restano NULL/None, mai zero.
- Giorni senza registrazioni = nessun dato, non zero kcal.
- Media kcal solo sui giorni con dati kcal noti; copertura parziale deve essere indicata.
- Registrazione automatica quando il peso diventa stabile.
- Tara fisica prima della scansione; la bilancia non ha un comando BLE di tara verificato.
- Un solo prodotto pendente per sessione.
- UI Aurora-inspired, responsive e leggera anche su tablet datati.

Flusso previsto:
1. piatto vuoto e tara fisica;
2. attendere zero stabile;
3. scansione barcode;
4. ricerca prima nel catalogo locale, poi Open Food Facts se abilitato;
5. attendere peso positivo stabile;
6. associare barcode e peso;
7. registrare automaticamente se il prodotto è noto; se ignoto, mantenere la sessione e consentire inserimento/ricerca manuale.

## 3. Decisione corrente scanner e bilancia

La configurazione del prototipo è entity-based:
- **Bilancia:** selezione di un'entità sensor ESPHome con device class weight. Selezionare il sensore stabile, non il peso raw.
- **Barcode:** selezione diretta dell'entità sensor `sensor.barcode_scanner_last_barcode` o equivalente.
- **Contatore scansioni:** selezione diretta dell'entità sensor `sensor.barcode_scanner_scan_count` o equivalente; il contatore incrementa a ogni lettura, anche se il barcode è identico.
- Non si seleziona un device ESPHome scanner.
- Non è richiesto un identificatore scanner nel payload.
- Nessun firmware attivo è stato modificato.

Il firmware combinato continua anche a emettere `esphome.barcode_scanned`, ma il disegno runtime corrente prevede di leggere l'entità barcode selezionata.

### Scansioni consecutive dello stesso barcode

Verifica reale comunicata dall'utente:
- `sensor.barcode_scanner_last_barcode` mantiene l'ultimo codice e non cambia quando viene letto nuovamente lo stesso prodotto;
- `sensor.barcode_scanner_scan_count` avanza a ogni scansione, comprese quelle ripetute;
- la cronologia del barcode mostra il valore dell'ultimo aggiornamento, mentre il contatore registra tutte le letture.

Decisione: usare il contatore come trigger e il sensore barcode come dato:
1. ascoltare `state_changed` soltanto sull'entità selezionata per il contatore;
2. a ogni aggiornamento del contatore, acquisire il valore corrente dell'entità barcode selezionata;
3. creare una nuova sessione anche se il testo barcode è identico alla lettura precedente;
4. verificare l'ordine di pubblicazione dei due sensori, evitando di associare il nuovo conteggio a un barcode precedente. Se necessario, differire la lettura al successivo ciclo dell'event loop o usare una breve coalescenza che non perda incrementi ravvicinati.

Non serve usare `state_reported` come trigger primario e non serve modificare il firmware attivo. `last_changed` del barcode non è un identificatore di scansione.
 
## 4. Stato del codice

### Integrazione HA prototipo

Percorso: `homeassistant/prototypes/food_diary_integration/custom_components/food_diary/`

Presenti:
- `manifest.json`
- `const.py`
- `config_flow.py`
- `__init__.py`
- `coordinator.py`
- `acquisition.py`
- `sensor.py`
- `services.py`
- `services.yaml`
- `storage.py`
- `test_acquisition.py`
- `translations/en.json`
- `translations/it.json`

Config flow:
- selettore sensore peso ESPHome/device class weight;
- selettore generico sensor per barcode;
- selettore generico sensor per contatore scansioni;
- validazione delle tre entità nel registry;
- options flow per le tre entità, pasto default, autosave, timeout, soglia zero e Open Food Facts paese/lingua/abilitazione;
- una sola config entry.

Runtime presente come prototipo, da validare:
- inizializza SQLite nel percorso `<config>/food_diary/food_diary.db`;
- registra azioni CRUD, riepilogo e controllo sessione pendente;
- esegue le operazioni SQLite nell'executor;
- coordinator con listener del contatore e del sensore peso selezionati;
- evento `esphome.barcode_scanned` gated dal contatore, più fallback entity-based per scanner generici;
- correlazione barcode/peso con baseline zero, timeout, sessione singola e protezione dai salvataggi doppi;
- lookup Open Food Facts v3 con sessione aiohttp condivisa di Home Assistant;
- sessione prodotto sconosciuto risolvibile aggiungendo alimento con lo stesso barcode;
- azioni `save_pending`, `discard_pending`, `get_status`, `search_openfoodfacts`;
- sensori diagnostici per stato, ultimo barcode, ultimo peso stabile e scan count;
- test unitari puri per parsing barcode/peso, baseline e burst del contatore, soglia zero e parsing nutrienti OFF v1/v3.

Non ancora presenti:
- pannello Aurora connesso al backend;
- test di integrazione Home Assistant/config flow/servizi;

### Storage SQLite

Percorso: `homeassistant/prototypes/food_diary_sqlite/`

Presenti:
- schema e storage SQLite standard library;
- CRUD alimenti e registrazioni;
- snapshot nutrizionali;
- riepiloghi day/week/month;
- timezone IANA e settimana lunedì;
- copertura nutrienti, giorni con kcal note e media giornaliera;
- test unitari scritti.

La copia `storage.py` inclusa nell'integrazione deve rimanere identica a quella standalone. La CI controlla questa condizione.

### Dashboard

Percorso: `homeassistant/prototypes/food_diary_dashboard/`

Presenti:
- `index.html`, `flows.html`: mockup statici, dati demo;
- `DESIGN.md`;
- `DATA_CONTRACT.md`;
- `DEVELOPMENT_LOG.md`.

Non è una dashboard Lovelace e non comunica con Home Assistant.

## 5. Documentazione da leggere

1. Questo file: punto di ripresa.
2. `README.md`: stato e limiti dell'integrazione.
3. `HACS_ARCHITECTURE.md`: struttura repository dedicato, Marketplace/HACS, pannello, compatibilità e gate di rilascio.
4. `../food_diary_dashboard/DATA_CONTRACT.md`: modello dati, azioni, riepiloghi e flusso di acquisizione.
5. `../food_diary_dashboard/DEVELOPMENT_LOG.md`: cronologia completa, comprese decisioni storiche poi superate.
6. `../food_diary_sqlite/DEVELOPMENT_LOG.md`: storage, test e limiti.

Le fasi storiche 6 e 7 del DEVELOPMENT_LOG dashboard descrivono la precedente selezione del device scanner ESPHome e il progetto di aggiungere un ID al payload. Sono superate dalla decisione entity-based documentata nella fase 9 e nei documenti aggiornati.

## 6. CI e stato dei test

Workflow: `.github/workflows/food-diary-prototype.yml`

Controlla:
- compilazione sintattica Python;
- JSON manifest e traduzioni;
- identità delle due copie storage.py;
- unit test SQLite con Python 3.12.

È stato corretto il PYTHONPATH per consentire ai test, scoperti dalla cartella tests, di importare storage.py dalla directory padre.

La CI **non** esegue:
- hassfest;
- test config flow/options flow;
- test setup/unload dell'integrazione;
- test coordinator o eventi ESPHome;
- test frontend;
- test su HA OS o dispositivo fisico.

Al momento della stesura non è stato verificato un risultato CI completato. Non dichiarare i test superati finché non viene letto il run GitHub Actions.

Comando locale per SQLite, dalla directory del prototipo:
```bash
PYTHONPATH=. python -m unittest discover -s tests -v
python -m py_compile storage.py tests/test_storage.py
```

## 7. Prossimi lavori, nell'ordine

1. **Verifica statica del config flow** rispetto alle API pubbliche di Core 2026.11.3: selector, entity registry, OptionsFlow, setup/unload e traduzioni.
2. **Coordinator**: prototipo implementato; testare eventi ESPHome, fallback entity-only, counter reset, scansioni ravvicinate, scanner non ESPHome, errori/unavailable e unload.
3. **State machine peso**: zero stabile prima della scansione, barcode pendente, peso positivo stabile, conversione unità g/kg, timeout, peso negativo/non valido, sessione concorrente, annullamento e ripristino dopo errore.
4. **Lookup**: lookup barcode OFF v3 e ricerca testuale alternativa legacy implementati; aggiungere test HTTP mock e verificare parametri paese/lingua, status 404, timeout e rate-limit.
5. **Persistenza e servizi**: collegamento coordinator-storage presente; aggiungere test servizi, gestione errori DB e persistenza delle sessioni pendenti.
6. **Test automatici**: unit test coordinator/state machine con fake hass e state/event bus; test config flow; test servizi e migrazioni. La CI attuale esegue solo test SQLite e acquisition.
7. **Diagnostica**: sensori base implementati; verificare naming, unique_id e stati in HA.
8. **Frontend**: collegare il mockup Aurora alle azioni e al flusso reale; valutare API pannello pubbliche e mantenere fallback Lovelace.
9. **Validazione**: hassfest, ruff, test HA Core versione minima e ultima release 2026, installazione/upgrade/unload su istanza HA di prova, backup/restore.
10. Solo dopo i gate: creare repository pubblico dedicato e preparare packaging HACS/Marketplace.

## 8. File attivi da non toccare in questa fase

- `homeassistant/packages/food_diary.yaml`
- firmware ESPHome attualmente installato, inclusi i file in `esphome/`
- secrets e configurazione attiva HA.

Qualsiasi esperimento sul firmware va fatto su una copia di sviluppo isolata. Non spostare i prototipi nel percorso attivo e non creare ancora il repository HACS pubblico.


## 9. Aggiornamento runtime — 2026-11-28

Sono stati aggiunti:
- acquisition.py: normalizzazione barcode, conversione peso in grammi, stato sessione con obbligo zero seguito da peso positivo, parser Open Food Facts con nutrienti ignoti mantenuti None;
- coordinator.py: ascolto state_changed del contatore e del sensore peso; ascolto evento esphome.barcode_scanned; lookup catalogo locale/Open Food Facts; sessione singola; timeout; salvataggio con lock; callback quando viene inserito manualmente un alimento;
- sensor.py: sensori diagnostici;
- azioni save_pending, discard_pending e get_status;
- test_acquisition.py: test standard-library per barcode, unità peso, baseline zero e parser OFF;
- workflow CI esteso ai test acquisition.

Dettaglio firmware accertato leggendo esphome/cosori-barcode-integrated.yaml: su ogni valore di barcode_raw, ESPHome incrementa e pubblica scan_count, poi pubblica last_barcode, quindi dopo 300 ms invia esphome.barcode_scanned con il barcode. Il coordinatore usa il contatore come guardia e il payload evento come conferma solo se esiste un unico incremento pendente e coincide con Last Barcode; per scanner generici senza evento usa fallback a 800 ms solo se è arrivato un singolo incremento. Più incrementi senza eventi corrispondenti sono marcati ambigui e non vengono salvati automaticamente.

Limiti noti:
- il coordinator non è ancora testato dentro HA Core;
- la sessione pendente è in RAM e si perde a riavvio HA;
- un solo prodotto/sessione alla volta;
- una scansione iniziata mentre un'altra sessione è ancora pendente viene rifiutata con stato session_busy;
- il fallback per scanner generici non può ricostruire barcode intermedi se più scansioni avvengono prima della lettura; in tal caso non salva;
- il firmware attivo non è stato modificato.

Open Food Facts API decision (2026-11-28): barcode lookup migrated to current v3 product API and parser reads the v3 aggregated nutrition structure only when it is per 100 g. The alternative text search still uses the legacy full-text endpoint, because the official docs state that full-text search is not available in v2/v3. A custom User-Agent is sent. See the official API docs linked in the development notes.


Race safeguard: the firmware event lambda reads the current Last Barcode after its 300 ms delay. It may not preserve the first code if another scan occurs during that delay. The coordinator now accepts only one pending counter increment and requires the event barcode to match the selected barcode entity. More than one overlapping increment is rejected as ambiguous; no guess-based autosave.


Riferimenti API ufficiali Open Food Facts consultati:
- Product lookup v3: https://openfoodfacts.github.io/documentation/docs/Product-Opener/v3/products/get-api-v3-product-code/
- Search full-text legacy: https://openfoodfacts.github.io/documentation/docs/Product-Opener/v2/search/get-search/
- Panoramica versioni API e stato v2/v3: https://openfoodfacts.github.io/openfoodfacts-server/api/


Ultimo aggiornamento tecnico: il parser del contatore è stato estratto in una funzione pura e i test coprono baseline iniziale, incremento singolo, burst, reset e valore non valido. Il setup dell'integrazione ora pulisce listener, servizi e riferimenti se il setup del coordinator o della piattaforma sensori fallisce.

### Comandi locali per i test (dalla root del repository)

```bash
python -m compileall -q homeassistant/prototypes/food_diary_integration/custom_components/food_diary homeassistant/prototypes/food_diary_sqlite
node --check homeassistant/prototypes/food_diary_integration/custom_components/food_diary/www/food-diary-card.js
PYTHONPATH=homeassistant/prototypes/food_diary_integration/custom_components python -m unittest discover -s homeassistant/prototypes/food_diary_integration/custom_components/food_diary -p 'test_*.py' -v
PYTHONPATH=homeassistant/prototypes/food_diary_sqlite python -m unittest discover -s homeassistant/prototypes/food_diary_sqlite/tests -v
cmp homeassistant/prototypes/food_diary_sqlite/storage.py homeassistant/prototypes/food_diary_integration/custom_components/food_diary/storage.py
```

I test acquisition caricano direttamente il modulo puro senza importare il package Home Assistant; per questo non richiedono Home Assistant installato. I test config flow, servizi e coordinator richiederanno invece un ambiente HA/pytest dedicato.

## 10. Aurora card prototype

A dependency-free custom Lovelace card is now present at custom_components/food_diary/www/food-diary-card.js. It uses the documented Home Assistant custom-card contract and hass.callService return responses; it calls get_dashboard_data, get_status, add_entry, add_food, delete_entry, search_openfoodfacts, save_pending and discard_pending. It displays day/week/month totals, missing-data days, partial nutrient coverage, meal entries, scanner status, manual portion/product forms and Open Food Facts alternatives.

The integration serves the asset at /food_diary/food-diary-card.js using the HTTP static-path API. The user must still add the resource once in Settings → Dashboards → Resources (module type); automatic Lovelace resource registration was deliberately avoided because no stable public registration API was identified. Example dashboard YAML is in homeassistant/prototypes/food_diary_dashboard/dashboard.yaml. The card and static route have not been tested in HA Core 2026.11.3.

## 11. Sessione pendente persistente — decisione confermata e implementata

L'utente ha confermato il ripristino delle sessioni scanner incomplete dopo riavvio/reload HA. Implementazione su schema SQLite v3:
- tabella pending_sessions con un solo slot attivo; conserva session_id, barcode, created_at, expires_at, updated_at;
- retention fissa 24 ore; il timeout configurabile per attesa peso rimane separato;
- il peso misurato e zero_seen NON vengono persistiti come dati affidabili;
- al ripristino si recupera il barcode e si prova a risolvere il prodotto dal catalogo locale; la sessione torna in stato restored_waiting_for_zero oppure unknown_product;
- dopo restart è obbligatorio effettuare una nuova tara/zero e una nuova pesata stabile positiva. Non si salva mai usando il peso precedente al riavvio;
- se il prodotto è sconosciuto, il barcode resta disponibile per inserimento manuale/ricerca OFF;
- scadenza 24h, timeout pesata, annullamento e salvataggio completato eliminano il record;
- creazione della registrazione e cancellazione della sessione pendente sono nella stessa transazione SQLite, evitando un doppio salvataggio se HA si arresta tra le due operazioni;
- migrazione da schema v2 a v3 automatica, senza cancellare catalogo o storico;
- test aggiunti per persistenza/reopen, singola sessione, delete condizionale, validazione scadenza e completamento atomico.

La sessione non viene eliminata da async_stop: un reload dell'integrazione deve poterla ripristinare. La risorsa Lovelace continua a richiedere l'aggiunta manuale una tantum.

## 12. Cosa resta da fare

1. Attendere ed esaminare il risultato del workflow GitHub Actions (Python compileall, JavaScript syntax check, JSON, copie storage, test SQLite e test acquisition).
2. Eseguire i test di integrazione dentro Home Assistant Core 2026.11.3, soprattutto migrazione DB v2→v3, ripristino dopo riavvio, timeout, annullamento e salvataggio atomico.
3. Verificare un caso reale: scansione nota con peso in attesa → riavvio HA → sessione ripristinata senza peso → nuova tara → nuova pesata → una sola registrazione.
4. Verificare un caso sconosciuto: scansione → riavvio → barcode ancora presente → inserimento manuale alimento → nuova tara/pesata → una sola registrazione.
5. Solo dopo questi test considerare il prototipo pronto per una copia di prova isolata; non installarlo ancora nell'istanza HA attiva.


## 10. Persistenza sessione pendente — verifica 2026-11-28

Verifica del codice sul branch:
- `pending_sessions` è creata da `storage.py` (schema v3);
- `_async_begin_scan` genera session_id e scadenza di 24 ore, poi chiama `_async_persist_session`;
- `async_start` richiama `_async_restore_pending_session`;
- il ripristino elimina record scaduti/non validi e richiede sempre una nuova tara/zero e una nuova pesata;
- `add_entry(..., pending_session_id=...)` inserisce la registrazione e cancella la sessione nella stessa transazione SQLite;
- discard e scadenza 24h eliminano la sessione;
- reload/unload mantiene il record persistente.

Correzione tecnica 2026-11-28 (commit `16ca945abb8bf5bad2658ca963717cad42c94f96`):
- il timeout breve di acquisizione peso non deve cancellare la sessione;
- ora imposta `weight_timeout` e conserva il barcode fino alla scadenza retention di 24 ore;
- eventuali dati peso precedenti al timeout o al riavvio non vengono ripristinati né considerati attendibili.

Limiti residui:
- persistenza coordinator non ancora coperta da test automatici con Home Assistant/fake hass;
- verificare crash tra creazione in memoria e completamento dell'INSERT SQLite;
- verificare che una sessione sconosciuta ripristinata possa essere completata con inserimento manuale e nuova pesata;
- verificare compatibilità runtime su Home Assistant Core 2026.11.3.


Nota di verifica: la persistenza delle sessioni è implementata sia nello storage sia nel coordinator. Non va più elencata tra i componenti mancanti; resta da aggiungere una suite di test runtime per il coordinator.


CI dispatch note (2026-11-28): the workflow definition has also been added to the default branch `main` (commit `dfa83e924b1aae10160961aa0a67ae0f07924552`) so GitHub's manual workflow dispatch control is available. The feature branch retains the same workflow. Select `waage+scanner` as the ref when manually running it.


## CI run #46178929795 — analisi e correzione (2026-11-28)

Esecuzione su commit `40621c9051227e81b1c0c51957cee4eb84e49bec`:
- compileall Python: OK;
- node --check card Aurora: OK;
- JSON manifest/traduzioni: OK;
- cmp copie storage: OK;
- SQLite: 17 test passati, 5 errori;
- acquisition: saltato perché il passo precedente è fallito.

Causa unica dei cinque errori: `PendingScanSessionPersistenceTests` non definiva `setUp`, quindi `self.store` e `self.db_path` non esistevano. Corretto aggiungendo `setUp` con database temporaneo dedicato e `tearDown` per cleanup.

Correzione commit: `fca1e59589dd06d4601b5f848e5e97bbfb77e971`.

La correzione è stata riletta su GitHub. Non è ancora disponibile una nuova run associata al commit di correzione: occorre rilanciare manualmente il workflow sul branch `waage+scanner`. Non dichiarare la CI verde finché il nuovo run non termina con successo.

## Aggiornamento acquisizione peso — 2026-11-28

Dopo la prima CI verde (run #46179491988, commit 70c86d0), la revisione del flusso ha individuato un rischio: un valore positivo già acquisito poteva rimanere valido se il sensore diventava `unknown`/`unavailable` o comunicava un valore negativo prima del completamento della ricerca prodotto.

Correzione applicata in `acquisition.py`:
- lettura `None`/unavailable o negativa invalida il peso precedentemente acquisito;
- invalida anche la vecchia baseline zero: per riprendere serve una nuova tara/lettura zero e poi un nuovo peso positivo;
- un valore negativo non può essere interpretato come tara.

Correzione coordinatore:
- il timeout breve resta attivo anche mentre si attende una nuova tara, non soltanto durante l'attesa del peso positivo.

Test aggiunti in `test_acquisition.py`:
- unavailable dopo un peso positivo;
- valore negativo prima della tara;
- valore negativo dopo un peso positivo;
- nuova lettura positiva dopo unavailable, che non salva senza nuova tara;
- valore esattamente pari alla soglia zero.

Aggiornata anche `HACS_ARCHITECTURE.md`: la sessione barcode è persistente in SQLite per 24 ore; il peso e la baseline non sono ripristinati.

Commit di codice di questa correzione: `428dbcc6` (coordinator), con modifiche precedenti a `acquisition.py` e `test_acquisition.py`.

**Verifica ancora necessaria:** il run CI #3 verde precede queste modifiche. GitHub non ha avviato automaticamente un nuovo workflow per i commit via connettore; rilanciare manualmente `Food Diary prototype checks` sul branch `waage+scanner`. Non dichiarare ancora verdi i nuovi test. I test runtime Home Assistant e hardware restano da fare.

Nota CI successiva (Run #4, 2026-11-28):
- run #46180187991 sul commit `7fbff597436cced9132ede81bfe7bafb2a2dd49c`: success;
- compileall, Node syntax, JSON, copie SQLite: tutti OK;
- 22 test SQLite e 26 test acquisizione superati.
- Dopo aver letto i log, ho aggiunto un ulteriore test esplicito: una lettura positiva successiva a `unavailable` non deve essere salvabile finché non viene osservata una nuova tara. Questo test è successivo al Run #4 e richiede una nuova esecuzione CI.

## Concorrenza scadenza sessione — 2026-11-28

Revisione del coordinatore dopo CI Run #5:
- individuata una race tra callback di scadenza retention 24h e operazioni save/discard;
- `_async_expire_persisted_session` ora acquisisce lo stesso `_save_lock` usato da save/discard/creazione;
- la riga SQLite viene eliminata prima di cancellare lo stato in memoria;
- se la cancellazione SQLite fallisce, la sessione resta disponibile e il coordinatore passa a `storage_error`, senza perdere il barcode pendente.

Commit: `33d282729079299c8ae706047384a309a65fbb8c`.

La modifica è pubblicata ma non ancora verificata dalla CI. I test attuali non esercitano il coordinatore HA né questa concorrenza; prossimo lavoro: introdurre un test harness per coordinator con fake Home Assistant o ambiente pytest-homeassistant-custom-component, poi estendere la CI. Non dichiarare questo caso testato fino a quando il test non viene eseguito.


## Coordinator: concorrenza e recupero — aggiornamento successivo a CI Run #5

Modifiche pubblicate sul branch `waage+scanner`:
- le ricerche prodotto e gli aggiornamenti catalogo sono associati all'identità della sessione che li ha avviati; una risposta asincrona tardiva non può aggiornare una nuova sessione che usa lo stesso barcode;
- gli errori di lookup di una sessione ormai superata non contaminano lo stato della sessione corrente;
- l'annullamento elimina prima la riga SQLite e solo dopo pulisce la sessione in memoria; se SQLite fallisce, barcode e sessione restano disponibili per il recupero;
- il salvataggio verifica nuovamente la scadenza delle 24 ore dentro `_save_lock`: una sessione già scaduta non viene salvata anche se il callback di scadenza è in coda;
- se la persistenza iniziale fallisce, viene tentata la pulizia dell'eventuale record parzialmente creato.

È stata aggiunta `test_coordinator.py` con un fake Home Assistant minimale per coprire:
- ripristino senza riutilizzare peso o tara precedenti;
- doppio evento barcode identico consumato una sola volta;
- burst di incrementi del contatore rifiutato come ambiguo;
- due richieste di salvataggio simultanee con una sola registrazione;
- errore SQLite durante discard e scadenza, mantenendo la sessione recuperabile;
- blocco del salvataggio dopo la scadenza;
- lookup catalogo tardivo che non aggiorna una sessione sostitutiva.

Il fake HA verifica l'orchestrazione del coordinatore, non sostituisce i test di integrazione con Home Assistant Core 2026.11.3. La nuova suite non è ancora stata eseguita da GitHub Actions: avviare manualmente `Food Diary prototype checks` selezionando il branch `waage+scanner`. Non usare "Re-run all jobs" sul vecchio run #5: serve una nuova esecuzione sul commit più recente.

Restano da verificare in ambiente HA reale/fisico: eventi e tempi reali ESPHome, config flow/options flow, setup/unload, API dei servizi, frontend, migrazione e recupero dopo crash. Nessuna modifica è stata fatta al firmware attivo o ai package HA attivi.


## Recupero SQLite e suite coordinator — aggiornamento

Ulteriori protezioni aggiunte dopo la prima suite fake-HA:
- se la lettura della sessione pendente fallisce per un errore SQLite, l'integrazione segnala `storage_error` e non elimina né sovrascrive il record;
- timestamp o ID corrotti vengono rilevati; il record viene rimosso solo se la cancellazione SQLite riesce;
- se la ricerca del prodotto nel catalogo fallisce per errore SQLite, il barcode pendente resta in memoria e lo stato diventa `storage_error`, invece di essere classificato erroneamente come prodotto sconosciuto;
- la risoluzione dopo inserimento manuale gestisce allo stesso modo gli errori di lettura SQLite.

La suite `test_coordinator.py` ora copre anche:
- sessione persistita attraverso unload e ripristinata da una nuova istanza del coordinatore;
- errori SQLite durante restore e lookup catalogo;
- burst di due incrementi del contatore rifiutato senza associare un barcode arbitrario.

Tutti questi test sono inclusi automaticamente dal workflow perché usa il pattern `test_*.py`. Non sono ancora stati eseguiti: avviare una nuova run manuale sul branch `waage+scanner`. Il run #5 verde riguarda un commit precedente e non verifica queste modifiche.
