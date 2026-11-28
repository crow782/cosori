# Registro di sviluppo — Food Diary Dashboard

## Fase 0 — Mockup principale
Creato `index.html` come anteprima statica responsive in stile Aurora. I dati sono fittizi; la pagina non usa API Home Assistant.

## Fase 1 — Specifica visuale
Creato `DESIGN.md` con layout, palette, requisiti responsive, distinzione tra peso live e porzione registrata, e principi per nutrienti sconosciuti.

## Fase 2 — Flussi UX e storico
Aggiunto `flows.html` con registrazione manuale porzione, creazione scheda alimento e storico dimostrativo. Le azioni di salvataggio non persistono dati. Il grafico ora distingue visivamente il giorno senza registrazioni.

## Fase 3 — Decisioni statistiche confermate
- I giorni senza registrazioni sono "nessun dato", non zero kcal.
- La media giornaliera esclude i giorni senza registrazioni.
- Il totale periodo somma tutte le registrazioni nell'intervallo.
- I nutrienti sconosciuti restano null, mai zero.
- Le registrazioni con kcal mancanti richiedono un indicatore di copertura, per non presentare una media parziale come completa.

## Fase 4 — Contratto dati
Creato `DATA_CONTRACT.md` dopo aver verificato il codice reale di storage e delle azioni Home Assistant. Il documento separa le funzioni già implementate dalle estensioni ancora necessarie:
- catalogo e registrazioni sono entità distinte;
- le registrazioni mantengono snapshot di alimento e nutrienti;
- le azioni attualmente registrate sono elencate con input/output;
- il flusso scanner/bilancia è modellato a stati;
- è evidenziato il gap tra riepilogo attuale e media/coverage che la UI dovrà mostrare;
- la scelta tra card Lovelace native e custom card resta aperta fino alla verifica della versione HA e delle API frontend.

## Verifiche e limiti
- I file HTML/CSS non usano librerie esterne.
- Non è stata eseguita una prova browser automatizzata né una verifica su dispositivi reali.
- Non è stata eseguita alcuna connessione a Home Assistant.
- Le unit test SQLite non sono state eseguite in questo passaggio.
- La copia storage dell'integrazione e il modulo SQLite autonomo risultano allo stesso SHA Git al momento della verifica.
- Nessun file in `homeassistant/packages/` o `esphome/` è stato modificato.

## Prossimo passo
Estendere e testare il contratto riepiloghi nel backend (coverage nutrienti e media con denominatore esplicito), quindi verificare l'integrazione su una istanza HA di prova. Dopo aver conosciuto la versione Home Assistant effettiva, scegliere il frontend e collegare le viste.

## Fase 5 — Copertura nutrienti e media giornaliera nel prototipo SQLite
- Aggiunta copertura per nutriente: conteggio valori noti/mancanti e flag di completezza.
- Aggiunti `days_with_energy_data`, `average_days_count` e `average_daily_energy_kcal` alla risposta `period_summary`.
- I giorni senza registrazioni non entrano nella media; i giorni con tutte le kcal sconosciute non possono contribuire a una media kcal.
- Le giornate con almeno una kcal nota ma altre voci senza kcal mantengono il totale parziale, marcato come incompleto dalla copertura.
- Aggiornata anche la copia `storage.py` inclusa nell'integrazione: i due file devono restare sincronizzati.
- Aggiunti test per media su giorni con kcal note, giornate con kcal completamente sconosciute e copertura parziale.

**Stato:** modifiche committate, ma non ancora validate da esecuzione locale o CI. Non dichiarare i test superati finché GitHub Actions non completa la matrice.


## Fase 6 — Compatibilità Home Assistant e distribuzione HACS

L'utente ha confermato l'ambiente di riferimento:
- Home Assistant OS 18.4
- Core 2026.11.3
- Supervisor 2026.11.0
- Frontend 20261028.8

Decisioni:
- puntare alla compatibilità con più release 2026, fissando la versione minima soltanto dopo una matrice di test;
- usare config flow e options flow con selettori nativi HA;
- selezionare il sensore ESPHome della bilancia (device class weight) e il device ESPHome dello scanner;
- evitare inserimento manuale di MAC BLE/GATT e dipendenze esterne non necessarie;
- distribuire integrazione e pannello Aurora in un repository HACS dedicato, separato dal repository Cosori;
- pannello locale incluso nel pacchetto, senza CDN/framework di nicchia; fallback Lovelace nativo se il pannello non risulta compatibile.

Creato `homeassistant/prototypes/food_diary_integration/HACS_ARCHITECTURE.md` con struttura repository, requisiti HACS/Marketplace, configurazione dispositivi, runtime, compatibilità e gate di rilascio.

Verifica del firmware combinato: il sensore da selezionare per il peso è `Cosori Weight Stable`; il barcode è attualmente inviato come evento `esphome.barcode_scanned` con il solo campo `barcode`. Per distinguere più dispositivi, l'evento dovrà includere un identificatore stabile del nodo. Nessun firmware è stato modificato in questa fase.

Nota: il prototipo config flow corrente è incompleto (schema UI non implementato) e il manifest non soddisfa ancora i requisiti di pubblicazione HACS. Il prototipo non è installabile e non va presentato come pronto.

Nessun package o firmware attivo è stato modificato. Nessun test su Home Assistant reale è stato eseguito.


## Fase 7 — Configurazione guidata iniziale

Implementati nel prototipo:
- config flow con selettore del sensore ESPHome di classe `weight`;
- selettore del device ESPHome usato come scanner;
- validazione lato backend rispetto a entity registry e device registry;
- options flow per cambiare sensore/scanner e configurare pasto predefinito, salvataggio automatico, timeout, soglia zero e Open Food Facts;
- traduzioni in inglese e italiano sotto `translations/`;
- registrazione delle azioni HA spostata nel ciclo di vita del config entry; le azioni vengono rimosse allo scaricamento;
- ricaricamento dell'integrazione quando cambiano le opzioni.

**Limite bloccante noto:** il firmware ESPHome attuale emette `esphome.barcode_scanned` con il solo campo `barcode`. Per filtrare le scansioni in base al device selezionato serve aggiungere un identificatore stabile del nodo nel payload e verificarne la corrispondenza col device registry. Il firmware attivo non è stato modificato.

**Validazione:** il codice è stato scritto su GitHub, ma non è stato eseguito dentro Home Assistant 2026.11.3; non sono ancora passati hassfest, test config flow, test d'integrazione o test su dispositivo.


## Fase 8 — Controlli automatici del prototipo

Aggiunto `.github/workflows/food-diary-prototype.yml`:
- compilazione sintattica Python;
- validazione JSON di manifest e traduzioni;
- confronto tra le due copie di `storage.py`;
- esecuzione degli unit test SQLite con Python 3.12.

Il workflow è stato aggiunto al branch, ma non è stata ancora osservata un'esecuzione completata: non dichiarare i controlli superati fino al risultato GitHub Actions.


## Fase 9 — Correzione del flusso scanner e handoff

La configurazione effettiva del prototipo è ora entity-based:
- bilancia: entità sensor ESPHome con device class weight;
- scanner: entità sensor generica che pubblica l'ultimo barcode, ad esempio sensor.barcode_scanner_last_barcode;
- il device selector ESPHome dello scanner e l'identificatore scanner nel payload non sono più richiesti;
- il firmware attivo non è stato modificato.

I punti delle fasi 6 e 7 che descrivono la selezione del device scanner e il payload con ID nodo sono decisioni storiche superate da questa scelta. Il codice attuale è la fonte per la configurazione; README, HACS architecture e DATA_CONTRACT sono stati riallineati.

### Ripetizione dello stesso barcode

La documentazione Home Assistant distingue:
- state_changed: stato o attributi sono cambiati;
- state_reported: l'entità ha riportato nuovamente lo stato senza variazioni.

Il coordinator dovrà valutare entrambi gli eventi per l'entità selezionata. Non è ancora verificato che il text sensor ESPHome ripubblichi ogni scansione identica; se non lo fa, servirà un evento dedicato o un contatore nel firmware di sviluppo. Riferimenti: https://www.home-assistant.io/docs/configuration/events/ e https://www.home-assistant.io/docs/configuration/state_object.

### Controllo CI

Corretto il workflow per impostare PYTHONPATH alla directory SQLite durante unittest discovery: il test importa storage.py dalla directory padre e senza questo path la discovery dalla cartella tests potrebbe non risolvere il modulo. La modifica è preventiva; non equivale a un test eseguito. La workflow controlla Python 3.12, JSON, compilazione, sincronizzazione delle copie e unit test SQLite. Non esegue hassfest né test Home Assistant.

### Stato esatto al momento della pausa

- Config flow/options flow scritti; non caricati su HA.
- Storage SQLite e azioni CRUD/summary presenti; test non ancora confermati da CI.
- Coordinator scanner/peso: non implementato.
- Open Food Facts nel runtime integrazione: non implementato.
- Sensori diagnostici: non implementati.
- Pannello Aurora reale collegato al backend: non implementato; esistono solo mockup HTML statici.
- HACS/Marketplace: architettura documentata, repository dedicato non creato.
- Nessun package HA attivo o firmware attivo modificato.

Per riprendere, seguire homeassistant/prototypes/food_diary_integration/RESUME.md.


## Fase 10 — Contatore scansioni GM67 confermato dall'utente

L'utente ha confermato sul dispositivo:
- `sensor.barcode_scanner_last_barcode` mantiene l'ultimo barcode; una scansione identica non cambia lo stato e non crea un nuovo punto nella cronologia.
- `sensor.barcode_scanner_scan_count` avanza a ogni scansione, comprese quelle ripetute.

Decisione aggiornata:
- selezionare tre entità: sensore peso stabile, sensore ultimo barcode e contatore scansioni;
- ascoltare `state_changed` sul contatore;
- leggere il barcode dall'entità last_barcode a ogni trigger;
- non usare `state_reported` come meccanismo primario per dedurre una nuova scansione;
- gestire e testare l'ordine di pubblicazione per evitare di leggere un barcode vecchio quando il contatore è già avanzato.

Nessuna modifica al firmware attivo. La modifica del config flow resta prototipale e deve essere testata con HA Core 2026.11.3.