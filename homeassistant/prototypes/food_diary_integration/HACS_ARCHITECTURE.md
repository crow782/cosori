# Food Diary — architettura di distribuzione Marketplace (catalogo HACS)

> Specifica di destinazione. Il codice in `homeassistant/prototypes/` resta sperimentale: questo documento non certifica l'integrazione come installabile.

## 1. Obiettivo

Distribuire Food Diary come integrazione completa per Home Assistant OS, installabile dal Marketplace integrato di Home Assistant 2026.11+ (catalogo e strumenti di pubblicazione HACS), configurabile interamente dalla UI e utilizzabile senza modificare `configuration.yaml`.

Versione di riferimento per lo sviluppo: Home Assistant Core 2026.11.3, Supervisor 2026.11.0, OS 18.4, Frontend 20261028.8. L'obiettivo è supportare il maggior numero possibile di release Core 2026, non soltanto la versione di riferimento.

## 2. Distribuzione: repository dedicato

La destinazione sarà un repository GitHub pubblico dedicato, ad esempio `crow782/food-diary`, separato da `crow782/cosori`.

Motivi:
- HACS/Marketplace installa una singola integrazione per repository e cerca il componente in `custom_components/<domain>/` alla radice.
- Il repository Cosori contiene firmware ESPHome, prototipi, documentazione e file di configurazione che non devono essere distribuiti insieme all'integrazione.
- Un repository dedicato consente release, versioni, issue tracker e CI indipendenti.

Struttura prevista:

```text
food-diary/
├── custom_components/
│   └── food_diary/
│       ├── __init__.py
│       ├── config_flow.py
│       ├── const.py
│       ├── manifest.json
│       ├── storage.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── services.py
│       ├── translations/
│       │   ├── en.json
│       │   └── it.json
│       ├── www/
│       │   └── food-diary-panel.js
│       └── brand/
│           └── icon.png
├── tests/
├── .github/workflows/
├── hacs.json
├── README.md
├── LICENSE
└── CHANGELOG.md
```

Il repository Cosori rimane la sede di sviluppo e documentazione finché il repository dedicato non sarà creato e validato. Non spostare o cancellare i prototipi durante questa fase.

## 3. Marketplace / catalogo HACS

Su Home Assistant 2026.11 e successivi l'utente installa dal menu **Impostazioni → Marketplace**: non deve installare la vecchia integrazione HACS separatamente. Il nome HACS resta rilevante per il catalogo, il file `hacs.json` e gli strumenti di validazione/pubblicazione.

Il repository pubblico dedicato dovrà avere:
- un solo componente sotto `custom_components/food_diary/`;
- `manifest.json` completo con `domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners`, `config_flow` e `iot_class`;
- `hacs.json` alla radice;
- README, licenza, changelog e release GitHub versionate;
- traduzioni esterne in `translations/en.json` e `translations/it.json` (non `strings.json` nel pacchetto custom pubblicato);
- icona e brand propri, senza marchi Home Assistant;
- workflow di validazione HACS e controlli automatici.

Il prototipo ha già le traduzioni in `translations/en.json` e `translations/it.json`. Il manifest attuale è presente, ma dovrà essere ricontrollato e completato secondo i requisiti HACS al momento della creazione del repository dedicato.

## 4. Interfaccia inclusa nell'integrazione

Per evitare due installazioni HACS separate, la prima versione pubblicabile includerà il pannello Aurora direttamente nel pacchetto dell'integrazione:
- file JavaScript locale incluso in `custom_components/food_diary/www/`;
- registrazione statica con l'API asincrona di Home Assistant;
- registrazione del pannello tramite l'integrazione `panel_custom` e le sue API pubbliche;
- nessun CDN, analytics, font remoto o framework frontend di nicchia a runtime;
- interfaccia responsive desktop/tablet/mobile, con modalità alleggerita e `prefers-reduced-motion`.

Il pannello è una vista dell'integrazione, non un backend alternativo: tutte le operazioni e le statistiche restano in Python/SQLite. Se la registrazione del pannello dovesse richiedere API non stabili, il fallback sarà una dashboard Lovelace basata su entità e azioni native, non una dipendenza non mantenuta.

## 5. Configurazione guidata

Un solo config entry locale per il diario, con Options Flow per cambiare le impostazioni dopo l'installazione. Il prototipo ora implementa i selettori e la validazione iniziale; il flusso non è ancora testato su Home Assistant.

### Dispositivi

- **Bilancia:** entity selector filtrato su entità `sensor`, integrazione ESPHome e device class `weight`. L'utente sceglie il sensore di peso stabile, non inserisce MAC BLE o UUID GATT.
- **Scanner:** entity selector generico sul dominio `sensor`; l'utente seleziona direttamente l'entità che pubblica l'ultimo barcode, ad esempio `sensor.barcode_scanner_last_barcode`. Non è richiesto un device selector né un identificatore aggiuntivo nel firmware.
- **Barcode:** il runtime leggerà l'entità selezionata. Ascoltare gli eventi `state_changed` e valutare `state_reported` per gli aggiornamenti ripetuti senza variazione del valore. Verificare che ESPHome pubblichi ogni scansione identica; non assumere che `last_changed` cambi a ogni lettura. Se l'entità non viene aggiornata a ogni scansione, introdurre un evento dedicato o un attributo contatore nel firmware di sviluppo.

Per il firmware Cosori attuale, la selezione prevista è il sensore `Cosori Weight Stable` e il device ESPHome `Cosori Food Diary`. Non usare il sensore peso raw per la registrazione automatica.

### Opzioni utente

- pasto predefinito, modificabile per ogni registrazione;
- salvataggio automatico quando barcode e peso stabile sono associati (abilitato secondo la preferenza già espressa);
- timeout di attesa peso e soglia di zero;
- lookup Open Food Facts abilitabile/disabilitabile;
- preferenze paese/lingua per la ricerca;
- comportamento quando il barcode non esiste: inserimento manuale o scelta alternativa;
- selezione di un diverso sensore peso o sensore barcode senza reinstallare l'integrazione.

La tara resta fisica: l'integrazione non deve inviare comandi BLE di tara alla Cosori, perché il protocollo verificato finora non la supporta.

## 6. Architettura runtime

- Config entry e Options Flow per configurazione e migrazioni.
- Coordinator per correlare evento scanner e peso stabile, gestire timeout, duplicati e sessione pendente.
- SQLite con database in `<config>/food_diary/`, mai dentro la cartella dell'integrazione.
- Operazioni SQLite sincrone eseguite fuori dall'event loop.
- Entità diagnostiche leggere per stato integrazione, ultimo barcode e stato acquisizione; i dati storici restano in azioni/risposte strutturate, non in attributi enormi di sensori.
- Azioni HA per CRUD catalogo, registrazioni e riepiloghi.
- Snapshot nutrienti per ogni porzione; valori sconosciuti restano null.
- Migrazioni versionate e backup/restore documentati.

## 7. Compatibilità e dipendenze

Principi:
- usare API pubbliche documentate di Home Assistant;
- nessuna dipendenza Python esterna se la standard library e Home Assistant sono sufficienti;
- non importare moduli interni del frontend o di altre integrazioni;
- nessun accesso diretto al database Recorder di Home Assistant;
- niente Node.js, npm o compilazione frontend sul sistema dell'utente;
- distribuire il JavaScript già pronto nel repository/release;
- non dipendere da HACS come runtime: HACS è solo il canale di installazione/aggiornamento.

La versione minima Core sarà fissata dopo una matrice di test sulle release 2026, non dedotta dalla sola versione 2026.11.3. Ogni release deve testare almeno la versione minima dichiarata e la versione stabile più recente disponibile al momento del rilascio.

## 8. Test e criteri di rilascio

Prima della release:
1. unit test storage e migrazioni SQLite;
2. test config flow e options flow;
3. test listener dell'entità barcode selezionata, `state_changed`/`state_reported`, scansioni identiche, timeout e perdita/ripristino entità;
4. test sensore peso in grammi/chilogrammi, zero, valori non validi e perdita entità;
5. test azioni HA e risposte strutturate;
6. test pannello con frontend HA, aggiornamento stati, errori e mobile;
7. hassfest, ruff/format e validazione HACS;
8. prova installazione/aggiornamento/rimozione su istanza HA OS di test;
9. prova backup e ripristino del database.

Nessuna versione sarà marcata stabile finché questi controlli non saranno superati. Il firmware e il package attivi dell'utente resteranno separati fino alla validazione end-to-end.


## 9. Nota specifica per Home Assistant 2026.11.3

L'installazione utente prevista è Marketplace integrato. La pubblicazione del repository continua a seguire i requisiti del catalogo HACS/Marketplace. La vecchia custom integration `hacs` non va installata né aggiunta come dipendenza dell'integrazione Food Diary.
