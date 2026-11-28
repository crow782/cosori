# Piano di integrazione: Cosori + GM67 + Home Assistant

> Stato: aggiornato con la rimozione del Bluetooth proxy, l'invio immediato del barcode, il ritorno dei dati nutrizionali al display tramite API ESPHome e il contatore kcal in Home Assistant. I firmware Cosori e scanner sono ancora configurazioni separate; **le modifiche non certificano una compilazione o una prova sul dispositivo.**

## 1. Obiettivo e hardware

Un unico ESP32 DevKit V1 deve gestire contemporaneamente:

- la bilancia Cosori CNS-R101S tramite BLE GATT;
- lo scanner barcode GM67 tramite UART;
- il display OLED SSD1306 tramite I²C;
- il pulsante fisico;
- la connessione Wi-Fi e l'API nativa ESPHome verso Home Assistant;
- il collegamento BLE GATT diretto della bilancia, senza Bluetooth proxy.

Home Assistant deve coordinare il diario alimentare, associare barcode e peso, interrogare Open Food Facts e conservare i dati del diario. L'ESP32 deve rimanere un nodo di acquisizione e interfaccia: niente chiamate HTTP verso servizi esterni e niente parsing nutrizionale sul microcontrollore.

### 1.1 Compatibilità della scheda

La configurazione attuale dichiara `board: esp32dev`, quindi è coerente con il classico ESP32 DevKit V1.

Il firmware scanner usa:
- UART2: TX GPIO17, RX GPIO16;
- I²C OLED: SDA GPIO21, SCL GPIO22;
- pulsante: GPIO25.

Questi GPIO sono normalmente utilizzabili su un DevKit V1 con modulo ESP32-WROOM-32. Prima del cablaggio definitivo va però verificata la sigla del modulo montato: alcune varianti ESP32-WROVER riservano GPIO16/17 alla PSRAM. Verificare anche che il pulsante non sia collegato a un circuito che imponga livelli anomali al boot.

Il file scanner attuale imposta `minimum_chip_revision: "3.0"`. Non va mantenuto automaticamente: occorre controllare la revisione del chip reale e verificare che sia almeno 3.0. In caso contrario la configurazione può impedire l'avvio; il requisito va rimosso o adattato se non è indispensabile.

## 2. Cosa fanno oggi i due firmware

### 2.1 Cosori

File: `esphome/cosori-cns-r101s.yaml`

- ESP-IDF, Wi-Fi con `power_save_mode: none`, API e OTA.
- BLE tracker con scansione attiva.
- Bluetooth proxy rimosso: non serve alla connessione BLE GATT diretta della bilancia.
- Un `ble_client` diretto verso il MAC della bilancia di test.
- Sottoscrizione alle notifiche GATT `0x1910 / 0x2C12`.
- Validazione dell'intestazione del pacchetto e decodifica del peso dai byte 7–8, big-endian, divisi per 10.
- Sensore Raw a 0,1 g e sensore Stable arrotondato al grammo, pubblicato dopo 1,5 secondi senza variazioni del grammo intero.
- Nessuna scrittura BLE verso la bilancia.

Il peso non è stato trovato nell'advertising o nello scan response durante i test passivi documentati nel README. Per ottenere il peso serve quindi mantenere la connessione GATT e la sottoscrizione NOTIFY.

### 2.2 Scanner GM67

File: `barcode.yaml` (e copia denominata `barcode scanner.yaml`).

- UART2 a 9600 baud, parsing delle righe ASCII terminate da CR.
- OLED SSD1306 su I²C e pulsante GPIO25.
- Configurazione GM67 tramite comandi UART.
- API ESPHome e OTA.
- La scansione pubblica subito l'evento `esphome.barcode_scanned` via API nativa ESPHome; non esegue richieste HTTP né parsing JSON sul microcontrollore.
- Espone inoltre l'azione API `show_food_result`, richiamata da Home Assistant per aggiornare il display con prodotto, peso, kcal della porzione e totale progressivo.

Il vecchio POST a `http://localhost` è stato rimosso: su ESP32 localhost avrebbe indicato il dispositivo stesso, non Home Assistant. Il firmware non contiene più i componenti `http_request` e `json` per il middleware.

### 2.3 Package Home Assistant esistente

File: `homeassistant/packages/food_diary.yaml`.

Il package:
- riceve `esphome.barcode_scanned`;
- conserva il barcode in `input_text.food_diary_pending_barcode`;
- abbina il barcode al primo peso stabile positivo;
- emette `esphome.food_diary_weight_ready`;
- interroga Open Food Facts tramite `rest_command` da Home Assistant;
- calcola i nutrienti della porzione a partire dai valori per 100 g.

Quindi la parte HTTP verso Open Food Facts resta in Home Assistant. Il risultato torna al display tramite un'azione personalizzata dell'API nativa ESPHome: nessun server HTTP intermedio e nessuna richiesta dal microcontrollore.

Nota: il README del package indica già la sequenza tare → scansione → aggiunta alimento; questa è anche la sequenza consigliata qui sotto.

## 3. Architettura raccomandata

```text
             ESP32 DevKit V1
  +--------------------------------------+
  | Cosori BLE GATT client               |
  |   -> peso raw                        |
  |   -> peso stabile                    |
  |                                      |
  | GM67 UART -> barcode                 |
  | OLED + pulsante                      |
  |                                      |
  | ESPHome Native API / Wi-Fi           |
  +-------------------+------------------+
                      |
                      | eventi e stati ESPHome
                      v
             Home Assistant
  +--------------------------------------+
  | macchina a stati del diario          |
  | associazione barcode + peso          |
  | rest_command Open Food Facts         |
  | parsing JSON e calcolo nutrienti     |
  | salvataggio diario / pasti           |
  +-------------------+------------------+
                      |
                      | HTTPS
                      v
               Open Food Facts
```

### Perché spostare HTTP su Home Assistant

1. Home Assistant ha già la connettività IP, il package e il comando REST per Open Food Facts.
2. L'ESP32 non deve gestire TLS, timeout HTTP, buffer della risposta e parsing JSON.
3. Il barcode può essere consegnato subito all'event bus: la lettura non resta bloccata in attesa di un server.
4. Le modifiche a API, campi JSON, ricerca alternativa o database non richiedono un nuovo firmware.
5. Il package può gestire retry, errori, prodotti mancanti e registrazione storica in modo più semplice.

Il canale consigliato è l'API nativa ESPHome con `homeassistant.event`, non un POST HTTP dall'ESP32. In Home Assistant va abilitata per quel dispositivo l'opzione **Allow the device to perform Home Assistant actions**.

Il package usa già `rest_command` e `response_variable` per Open Food Facts: non serve un middleware HTTP aggiuntivo sul microcontrollore. Un eventuale middleware dedicato su Home Assistant avrebbe senso solo se in futuro si volessero centralizzare più sorgenti o applicare logiche complesse non adatte alle automazioni YAML.

## 4. Sequenza operativa consigliata

Per associare senza ambiguità un prodotto al suo peso netto, la sequenza deve essere seriale: un prodotto per volta.

### Procedura normale

1. **Mettere il piatto o contenitore vuoto sulla bilancia.**
2. **Eseguire la tara fisica sulla bilancia Cosori.** Il firmware attuale non invia comandi di tara via BLE e non deve presumere di poterlo fare.
3. **Attendere che Home Assistant veda il peso stabile pari a zero** (o comunque il valore di tara previsto). Il sensore Stable applica già 1,5 s di stabilità; attendere questo aggiornamento evita di associare il barcode a un peso residuo della porzione precedente.
4. **Scansionare il barcode.** L'ESP32 pubblica immediatamente `esphome.barcode_scanned`; Home Assistant salva il barcode come elemento in attesa.
5. **Attendere la conferma di acquisizione del barcode da Home Assistant**, idealmente tramite uno stato/indicatore dedicato. Non è consigliabile affidarsi a un ritardo fisso come unica garanzia. Se in una prima versione non c'è ancora una conferma visibile, lasciare circa 1 secondo prima di aggiungere il cibo è una precauzione pratica, non una garanzia protocollare.
6. **Aggiungere il prodotto nel contenitore.**
7. **Non toccare il contenitore e attendere il peso stabile.** Il firmware pubblica il peso dopo 1,5 s senza variazioni del grammo intero, con controllo ogni 100 ms.
8. Home Assistant associa il primo peso stabile positivo al barcode in attesa, registra la porzione e avvia la richiesta Open Food Facts.
9. Attendere l'esito della ricerca. Se il prodotto non esiste o i dati nutrizionali mancano, mantenere il peso e il barcode disponibili per inserimento manuale/ricerca alternativa.
10. Solo dopo aver concluso o annullato la voce corrente, passare al prodotto successivo e ripetere la tara.

### Perché barcode prima del peso aggiunto

Il package attuale abbina il barcode in attesa al primo passaggio del sensore stabile sopra zero. Perciò il flusso naturale è tara → barcode → aggiunta alimento. Pesare prima e scansionare dopo non si adatta al trigger attuale: il peso potrebbe essere già positivo prima che esista un barcode in attesa e non generare un nuovo evento numerico.

La scansione prima dell'aggiunta evita anche che il peso di un prodotto precedente venga attribuito al barcode appena letto, purché la tara sia stata completata e il valore zero sia stato osservato.

### Timer e condizioni

| Fase | Attesa/condizione |
|---|---|
| Dopo tara | Aspettare il valore stabile di tara; il firmware usa 1,5 s + controllo massimo ogni 100 ms |
| Dopo scansione | Preferire conferma HA; circa 1 s è solo un margine provvisorio se non c'è ancora un feedback |
| Dopo aggiunta alimento | Aspettare il sensore Stable, non un timer separato |
| Tra prodotti | Nessun timer fisso necessario: serve completare/annullare la voce precedente e rifare la tara |

Non introdurre ritardi lunghi nel firmware per compensare l'elaborazione HTTP. L'ESP32 deve continuare a ricevere le notifiche BLE e a leggere la UART mentre Home Assistant lavora.

## 5. Condizioni di correttezza da rafforzare in Home Assistant

Il package attuale è un buon prototipo, ma l'associazione barcode/peso deve essere resa più robusta prima di usarla come diario affidabile.

- **Verifica dello zero dopo tara:** non armare una nuova voce finché la bilancia non ha pubblicato lo zero stabile.
- **Una sola voce pendente:** se arriva un secondo barcode mentre il primo è ancora in attesa, non sovrascrivere silenziosamente il primo. Segnalare errore o chiedere conferma.
- **Peso positivo successivo:** associare soltanto una nuova transizione a peso positivo avvenuta dopo l'acquisizione del barcode, non un valore positivo già presente.
- **Timeout di sessione:** se dopo la scansione non arriva un peso entro un intervallo configurabile (ad esempio 2 minuti), annullare/archiviare la sessione come incompleta e chiedere una nuova scansione.
- **Peso zero o negativo:** non registrare una porzione; gestire separatamente rimozione, tara o letture non valide.
- **Doppie notifiche:** evitare che lo stesso barcode o lo stesso peso stabile producano due registrazioni.
- **Ricerca asincrona:** la richiesta Open Food Facts parte dopo l'associazione barcode/peso. Il peso già acquisito non deve andare perso se l'API è lenta o non raggiungibile.
- **Conferma visibile:** distinguere almeno gli stati “in attesa barcode”, “barcode acquisito”, “in attesa peso”, “peso acquisito”, “ricerca prodotto”, “prodotto non trovato” ed “errore”.

Per una seconda fase, è preferibile sostituire la semplice variabile barcode pendente con una piccola macchina a stati e un identificativo progressivo della sessione. Questo protegge anche da eventi in ritardo o duplicati.

## 6. Risorse e stabilità ESP32

### Radio Wi-Fi/BLE

ESP32 classico condivide una sola risorsa radio 2,4 GHz tra Wi-Fi e Bluetooth. ESP-IDF gestisce la coesistenza tramite time-division multiplexing: Wi-Fi e BLE possono coesistere, ma non trasmettono/ricevono contemporaneamente sulla stessa radio.

Il carico HTTP e il parsing JSON sull'ESP32 sono quindi inutili: ridurli non elimina la condivisione radio, ma riduce il lavoro applicativo e le raffiche di traffico Wi-Fi.

### BLE client diretto, senza proxy

- Mantenere `esp32_ble_tracker` e il client `ble_client` diretto verso la Cosori: sono necessari per la connessione GATT e le notifiche del peso.
- Non configurare `bluetooth_proxy`: non serve né alla bilancia né allo scanner GM67 e aggiungerebbe carico e complessità senza beneficio per questo progetto.

### Scansione BLE

Mantenere inizialmente i parametri di scansione predefiniti del tracker, senza impostare intervalli e finestre aggressive.

### Logger e componenti

- Usare livello globale INFO nel firmware unificato.
- Attivare DEBUG solo temporaneamente per `cosori` o per il parser UART quando serve diagnosticare.
- Evitare log completi di ogni pacchetto BLE nel funzionamento normale.
- Mantenere `power_save_mode: none` durante i test di coesistenza.
- Non aggiungere componenti HTTP, server web o buffer JSON sul nodo.
- Conservare il display con un aggiornamento moderato; 250 ms è già sufficiente per un OLED di stato.
- Evitare di eseguire contemporaneamente più richieste o script lunghi sul microcontrollore.

## 7. Unificazione YAML: criteri

I due file non vanno concatenati. Devono diventare una sola configurazione ESPHome con una sola dichiarazione per ogni sezione di primo livello.

Sezioni da unificare:
- `esphome`: nome unico, friendly name, `compile_process_limit`; trasferire solo le automazioni di boot necessarie.
- `esp32`: una sola scheda `esp32dev`, framework ESP-IDF e opzioni SDK verificate.
- `logger`: un solo logger con livelli selettivi.
- `api`: una sola API con una sola chiave in secrets.
- `ota`: una sola configurazione OTA.
- `wifi`: una sola configurazione, con fallback AP e captive portal.
- `captive_portal`: una sola dichiarazione.
- `esp32_ble_tracker`, `ble_client`: mantenere la connessione BLE diretta Cosori; non aggiungere `bluetooth_proxy`.
- `uart`, `i2c`, `display`, `font`, `binary_sensor`, `script`, `select`, `switch`, `number`, `text_sensor`, `sensor`, `globals`, `interval`: unire le liste e i blocchi evitando ID duplicati.
- Rimuovere `http_request` e `json` dal firmware barcode se non rimane alcun altro uso.

Ulteriori correzioni prima della fusione:
1. Il firmware barcode deve emettere `esphome.barcode_scanned` appena il parser UART riconosce il barcode, senza attendere HTTP.
2. L'evento deve contenere almeno `barcode`; aggiungere eventualmente un contatore/session ID per identificare ogni scansione.
3. Aggiungere fallback AP alla configurazione Wi-Fi unificata.
4. Rimuovere il requisito `minimum_chip_revision: "3.0"` se la revisione reale del chip non lo soddisfa o se non è necessario.
5. Eliminare il placeholder Authorization e l'URL localhost, che non devono restare nel firmware.
6. Verificare che il file sorgente `barcode.yaml` usi solo `!secret api_encryption_key` e `!secret ota_password`; non copiare credenziali letterali.
7. Mantenere segreti solo in `secrets.yaml`, escluso da Git.

## 8. Piano di implementazione a fasi

L'ordine è intenzionale: dopo ogni fase si deve poter tornare a un firmware funzionante.

### Fase 0 — Baseline hardware
- Identificare il modulo montato sul DevKit V1 (WROOM-32 o altra variante).
- Verificare revisione chip e pin UART/I²C.
- Verificare alimentazione stabile: scanner GM67 e OLED non devono provocare cadute di tensione o reset dell'ESP32.
- Compilare e provare separatamente il firmware scanner attuale e quello Cosori.

### Fase 1 — Unificazione minima, senza proxy
- Unire le sezioni YAML e mantenere Cosori GATT + GM67 UART + OLED + pulsante.
- Non configurare il Bluetooth proxy.
- Eliminare completamente HTTP/JSON dal firmware barcode.
- Pubblicare l'evento barcode via API ESPHome.
- Conservare il sensore Raw e Stable della bilancia.
- Verificare compilazione, avvio, API, OTA, scansione barcode e peso per almeno alcune ore.

### Fase 2 — Diario Home Assistant
- Adeguare il package per la macchina a stati descritta sopra.
- Testare tare, scansione, aggiunta, peso stabile, lookup Open Food Facts e prodotto sconosciuto.
- Aggiungere feedback di acquisizione barcode e timeout.
- Testare due o più prodotti in sequenza e verificare che non ci siano associazioni incrociate.

### Fase 3 — Feedback nutrizionale sul display
- Dopo la risposta Open Food Facts, Home Assistant richiama `esphome.barcode_scanner_show_food_result`.
- Il display mostra peso, kcal della porzione e kcal cumulative.
- Il totale aumenta solo quando è disponibile un valore energetico e può essere azzerato con `input_button.food_diary_reset_total_kcal`.

### Fase 4 — Diario persistente e interfaccia
- Salvare ogni porzione come voce distinta, con data/ora, pasto, barcode, nome, peso e nutrienti.
- Aggiungere inserimento manuale e ricerca alternativa quando Open Food Facts non trova il codice.
- Implementare totali per pasto e giornata.
- Aggiungere una UI Home Assistant; il display OLED resta un feedback essenziale del dispositivo.

## 9. Criteri di accettazione

La fusione è pronta per l'uso quotidiano solo se:
- non si verificano reboot o blocchi durante scansione e pesatura;
- la bilancia mantiene la connessione GATT e pubblica il peso stabile;
- il GM67 non perde letture;
- un barcode viene associato esclusivamente alla pesata successiva alla tara e alla scansione;
- una richiesta Open Food Facts lenta/non disponibile non blocca l'acquisizione;
- una scansione doppia o una sessione incompleta non genera una voce alimentare errata;
- il dispositivo resta raggiungibile via API e OTA;
- la stabilità della connessione BLE diretta è stata verificata.

## 10. Riferimenti

- [ESPHome Native API](https://esphome.io/components/api/): azione `homeassistant.event` e autorizzazione del dispositivo a eseguire azioni Home Assistant.
- [ESP-IDF RF Coexistence (ESP32)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/coexist.html): condivisione della radio Wi-Fi/BLE e time-division multiplexing.
- [Home Assistant RESTful Command](https://www.home-assistant.io/integrations/rest_command/): richieste HTTP eseguite da Home Assistant e gestione della risposta con `response_variable`.

---
Documento di progettazione. Le raccomandazioni e la sequenza sono basate sui file correnti del repository e sulle osservazioni raccolte; la fusione, la compilazione e i test hardware devono ancora essere eseguiti.
