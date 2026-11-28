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
- **Scanner:** selezione diretta di una generica entità sensor che espone l'ultimo barcode, ad esempio `sensor.barcode_scanner_last_barcode`.
- Non si seleziona un device ESPHome scanner.
- Non è richiesto un identificatore scanner nel payload.
- Nessun firmware attivo è stato modificato.

Il firmware combinato continua anche a emettere `esphome.barcode_scanned`, ma il disegno runtime corrente prevede di leggere l'entità barcode selezionata.

### Scansioni consecutive dello stesso barcode

È il punto tecnico da risolvere prima di dichiarare completo il coordinator. Home Assistant distingue:
- `state_changed`: stato o attributi modificati;
- `state_reported`: l'entità riporta lo stesso stato senza variazioni.

Il coordinator dovrà ascoltare l'entità selezionata e valutare entrambi gli eventi. Va verificato se il text sensor ESPHome pubblica nuovamente il valore a ogni lettura identica. Se non lo fa, servirà un evento dedicato o un contatore/attributo di scansione nel firmware di sviluppo. Non basarsi su `last_changed` come identificatore di ogni scansione.

Riferimenti ufficiali:
- https://www.home-assistant.io/docs/configuration/events/
- https://www.home-assistant.io/docs/configuration/state_object

## 4. Stato del codice

### Integrazione HA prototipo

Percorso: `homeassistant/prototypes/food_diary_integration/custom_components/food_diary/`

Presenti:
- `manifest.json`
- `const.py`
- `config_flow.py`
- `__init__.py`
- `services.py`
- `services.yaml`
- `storage.py`
- `translations/en.json`
- `translations/it.json`

Config flow:
- selettore sensore peso ESPHome/device class weight;
- selettore generico sensor per barcode;
- validazione delle due entità nel registry;
- options flow per entità, pasto default, autosave, timeout, soglia zero e Open Food Facts paese/lingua/abilitazione;
- una sola config entry.

Runtime:
- inizializza SQLite nel percorso futuro `<config>/food_diary/food_diary.db`;
- registra le azioni CRUD e riepilogo al setup del config entry;
- operazioni SQLite eseguite nell'executor;
- rimuove le azioni al unload e ricarica l'integrazione al cambio opzioni.

Non ancora presenti:
- coordinator/state machine scanner-peso;
- listener dell'entità barcode;
- correlazione barcode/peso e gestione timeout/duplicati;
- lookup Open Food Facts nel runtime dell'integrazione;
- gestione sessione prodotto sconosciuto;
- entità diagnostiche;
- pannello Aurora connesso al backend.

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
2. **Coordinator**: listener dell'entità barcode selezionata, state_changed/state_reported, normalizzazione e validazione barcode, gestione letture identiche, entità unavailable e cambi opzioni.
3. **State machine peso**: zero stabile prima della scansione, barcode pendente, peso positivo stabile, conversione unità g/kg, timeout, peso negativo/non valido, sessione concorrente, annullamento e ripristino dopo errore.
4. **Lookup**: catalogo locale prima; Open Food Facts via client HTTP nativo HA/aiohttp, timeout, error handling, paese/lingua; non bloccare la pesata quando il barcode è sconosciuto.
5. **Persistenza e servizi**: integrazione coordinator-storage, selezione pasto, autosave e gestione prodotto sconosciuto.
6. **Test automatici**: unit test coordinator/state machine con fake hass e state/event bus; test config flow; test servizi e migrazioni.
7. **Diagnostica**: sensori leggeri per stato, ultimo barcode e stato acquisizione.
8. **Frontend**: collegare il mockup Aurora alle azioni e al flusso reale; valutare API pannello pubbliche e mantenere fallback Lovelace.
9. **Validazione**: hassfest, ruff, test HA Core versione minima e ultima release 2026, installazione/upgrade/unload su istanza HA di prova, backup/restore.
10. Solo dopo i gate: creare repository pubblico dedicato e preparare packaging HACS/Marketplace.

## 8. File attivi da non toccare in questa fase

- `homeassistant/packages/food_diary.yaml`
- firmware ESPHome attualmente installato, inclusi i file in `esphome/`
- secrets e configurazione attiva HA.

Qualsiasi esperimento sul firmware va fatto su una copia di sviluppo isolata. Non spostare i prototipi nel percorso attivo e non creare ancora il repository HACS pubblico.
