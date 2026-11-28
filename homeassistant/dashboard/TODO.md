# TODO – Dashboard Food Diary

> Documento di pianificazione: **non è ancora una dashboard installabile**. Qui raccogliamo requisiti, flussi e decisioni da verificare prima di scrivere Lovelace YAML o modificare il package Home Assistant.

## Stato del design grafico

È stato avviato un prototipo visuale autonomo in `homeassistant/prototypes/food_diary_dashboard/`:
- `DESIGN.md`: palette Aurora, gerarchia, comportamento responsive e principi UX.
- `index.html`: mockup statico responsive con riepilogo calorie, macro, dispositivi, azioni rapide, pasti, ultima acquisizione e archivio ricercabile.

Il mockup usa esclusivamente dati fittizi, non chiama Home Assistant e non è installabile. Non sono stati modificati package, firmware o dashboard attive. Restano da verificare rendering reale, accessibilità e mappatura sulle entità/azioni effettivamente implementate.

## Obiettivo

Realizzare in Home Assistant un diario alimentare semplice da usare, responsive su PC, tablet e telefono, collegato alla bilancia Cosori CNS-R101S e allo scanner GM67. La dashboard deve permettere sia la registrazione automatica tramite barcode + peso sia la gestione manuale quando la scansione o la ricerca del prodotto non riescono.

## Stato attuale – punto di partenza

Il package esistente è `homeassistant/packages/food_diary.yaml`.

Attualmente:
- riceve il barcode da `esphome.barcode_scanned`;
- associa il barcode al successivo peso stabile positivo di `sensor.cosori_weight_stable`;
- interroga Open Food Facts v3;
- calcola i nutrienti della porzione quando i dati sono disponibili;
- conserva l'ultimo risultato tramite helper e mantiene un contatore cumulativo di kcal azzerabile.

Non è ancora un diario storico: non registra una serie di pasti, non assegna gli alimenti a colazione/pranzo/cena/spuntino e non calcola riepiloghi per giorno, settimana o mese. Non esiste ancora un archivio locale consultabile dei prodotti né un flusso completo di inserimento manuale.

## Requisiti funzionali

### 1. Diario e pasti

- [ ] Registrare ogni alimento come voce autonoma, senza sovrascrivere la registrazione precedente.
- [ ] Associare ogni voce a data e ora.
- [ ] Assegnare la voce a una categoria: **colazione, pranzo, cena, spuntino**.
- [ ] Consentire di scegliere o modificare il pasto durante l'inserimento; valutare un valore predefinito suggerito in base all'orario, ma sempre modificabile.
- [ ] Mostrare le voci del giorno raggruppate per pasto.
- [ ] Mostrare il subtotale kcal di ogni pasto.
- [ ] Mostrare il totale giornaliero kcal.
- [ ] Consentire di correggere o eliminare una voce registrata per errore.
- [ ] Conservare le registrazioni anche dopo il riavvio di Home Assistant.
- [ ] Definire come gestire una voce con dati nutrizionali incompleti: non trasformare nutrienti sconosciuti in zero.

### 2. Riepiloghi e consultazione

- [ ] Riepilogo del giorno selezionato.
- [ ] Totali giornalieri e andamento/aggregazione settimanale.
- [ ] Totali giornalieri e aggregazione mensile.
- [ ] Selettore del periodo o navigazione tra giorno, settimana e mese.
- [ ] Visualizzare almeno kcal; valutare proteine, carboidrati, zuccheri, grassi, grassi saturi, fibre e sale.
- [ ] Stabilire chiaramente se i riepiloghi settimanali/mensili mostrano somme, medie giornaliere o entrambe.
- [ ] Gestire correttamente il cambio di mese/anno e le settimane a cavallo tra due mesi.

### 3. Archivio locale minimalista degli alimenti

- [ ] Creare un archivio locale dei prodotti conosciuti, distinto dal diario delle porzioni consumate.
- [ ] Salvare un prodotto quando viene trovato su Open Food Facts e quando viene inserito manualmente.
- [ ] Evitare duplicati: usare il barcode come identificatore quando disponibile; per prodotti senza barcode definire una chiave/id locale.
- [ ] Conservare almeno: descrizione/nome, marca facoltativa, barcode facoltativo, valori nutrizionali per 100 g e fonte dei dati.
- [ ] Conservare i valori mancanti come sconosciuti, non come zero.
- [ ] Consentire di consultare e selezionare i prodotti conosciuti dalla dashboard.
- [ ] Ordinare l'elenco alfabeticamente per descrizione/nome.
- [ ] Prevedere ricerca testuale/filtro per trovare rapidamente un prodotto.
- [ ] Valutare modifica e cancellazione dei prodotti salvati.
- [ ] Definire cosa succede se una nuova ricerca OFF restituisce dati diversi da quelli già salvati: aggiornamento automatico, confronto o conferma manuale.

### 4. Inserimento manuale di una pesata

Serve un percorso alternativo quando non si effettua la scansione o il barcode non viene letto.

- [ ] Permettere di selezionare un prodotto dall'archivio locale, ordinato per descrizione.
- [ ] Mostrare il peso stabile corrente della Cosori, se disponibile.
- [ ] Permettere di inserire o correggere manualmente il peso in grammi.
- [ ] Calcolare i nutrienti della porzione a partire dai valori per 100 g.
- [ ] Permettere di scegliere il pasto prima del salvataggio.
- [ ] Richiedere una conferma esplicita prima di aggiungere la voce al diario.
- [ ] Selezionare un prodotto senza barcode deve essere possibile.
- [ ] Se la bilancia non è disponibile, consentire comunque l'inserimento manuale del peso.

### 5. Mini-form per aggiungere un alimento

- [ ] Form con descrizione/nome obbligatorio.
- [ ] Marca facoltativa.
- [ ] Barcode facoltativo.
- [ ] Valori nutrizionali per 100 g: energia (kcal), proteine, carboidrati, zuccheri, grassi, grassi saturi, fibre e sale.
- [ ] Rendere chiaro quali campi sono facoltativi e consentire dati nutrizionali parziali.
- [ ] Validare che i valori numerici siano validi e non negativi.
- [ ] Salvare il nuovo prodotto nell'archivio locale e renderlo subito selezionabile.
- [ ] Se il barcode esiste già, avvisare e proporre di aprire/modificare il prodotto esistente invece di creare un duplicato.

### 6. Barcode non trovato o prodotto incompleto

- [ ] Se OFF non trova il barcode, mantenere barcode e peso acquisiti: non perdere la pesata.
- [ ] Proporre la ricerca alternativa per nome/descrizione, se tecnicamente sostenibile.
- [ ] Permettere di associare il barcode non riconosciuto a un prodotto già presente nell'archivio.
- [ ] Permettere di creare un nuovo alimento usando il barcode acquisito.
- [ ] Se OFF trova il prodotto ma non i valori nutrizionali necessari, consentire di completare i dati manualmente.
- [ ] Distinguere chiaramente: barcode non trovato, prodotto trovato senza nutrienti, errore di rete e dati validi.

### 7. Flusso automatico Cosori + GM67

- [ ] Mantenere il flusso attuale: tara del contenitore vuoto, scansione, aggiunta alimento, attesa del peso stabile.
- [ ] Rafforzare l'associazione barcode/peso con una macchina a stati: pronto, barcode acquisito, attesa peso, peso acquisito, ricerca prodotto, conferma/salvataggio, errore/annullamento.
- [ ] Non sovrascrivere silenziosamente un barcode ancora in attesa con una seconda scansione.
- [ ] Aggiungere timeout e possibilità di annullare/ripetere una sessione.
- [ ] Evitare registrazioni duplicate in caso di notifiche ripetute o automazioni riavviate.
- [ ] Gestire la pesata senza barcode usando il flusso manuale, senza bloccare la registrazione.
- [ ] Mantenere il display OLED come feedback essenziale; la gestione completa rimane nella dashboard Home Assistant.

### 8. Dashboard Lovelace

- [ ] Riprendere la direzione grafica del mockup Food Diary già discusso.
- [ ] Layout responsive per desktop, tablet e smartphone.
- [ ] Sezione riepilogo con kcal del giorno e indicatori settimanale/mensile.
- [ ] Sezione stato dispositivi: bilancia, peso stabile, scanner e stato della sessione.
- [ ] Sezione inserimento rapido: scansione automatica e inserimento manuale.
- [ ] Sezione pasto corrente con elenco alimenti e subtotali.
- [ ] Sezione archivio alimenti con ricerca e selezione alfabetica.
- [ ] Mini-form per nuovo alimento.
- [ ] Sezione storico con navigazione per data e riepiloghi.
- [ ] Conferme prima di cancellare voci o azzerare dati.
- [ ] Evitare dipendenze HACS non necessarie; prima valutare le card native. Se una custom card migliora davvero l'esperienza, documentare dipendenza e installazione.
- [ ] Tenere conto delle prestazioni dei tablet meno recenti: animazioni leggere e poche risorse.

## Decisioni tecniche da studiare prima di implementare

- [ ] **Persistenza del diario:** individuare una soluzione affidabile in Home Assistant per registrazioni multiple, interrogabili per data e non limitate alla lunghezza di un `input_text`. Valutare pro/contro di helper, file locale gestito da automazioni, integrazione dedicata o altra soluzione compatibile con backup e ripristino.
- [ ] **Archivio prodotti:** scegliere una struttura semplice e manutenibile per il catalogo locale, con ricerca, ordinamento e aggiornamento dei record. Evitare di usare un singolo helper testuale come database definitivo.
- [ ] **Modello dati:** definire separatamente prodotto, porzione consumata e pasto. La porzione deve conservare una fotografia dei valori nutrizionali usati al momento della registrazione, così eventuali aggiornamenti del catalogo non alterano lo storico.
- [ ] **Unità e calcoli:** standardizzare energia in kcal e quantità in grammi; verificare conversioni da kJ quando OFF non fornisce direttamente kcal.
- [ ] **Date e statistiche:** definire settimana (preferibilmente lunedì–domenica, da confermare), fuso orario e comportamento dei periodi incompleti.
- [ ] **Interfaccia:** verificare quali controlli sono realizzabili con card native e quali richiedono HACS o uno script/servizio dedicato.
- [ ] **Backup e manutenzione:** documentare dove risiedono i dati e come esportarli, ripristinarli e correggere eventuali record.
- [ ] **Sicurezza:** nessun token, password o dato personale nel repository; non esporre servizi di scrittura non protetti.

## Proposta di sviluppo per fasi

1. **Analisi e modello dati** – scegliere persistenza, struttura del catalogo e struttura delle registrazioni.
2. **Motore del diario** – registrazione multipla, pasti, correzione/cancellazione e totali giornalieri.
3. **Archivio alimenti** – salvataggio automatico OFF, inserimento manuale, ricerca e selezione alfabetica.
4. **Flussi di acquisizione** – integrare barcode/peso automatici e pesata manuale con gestione degli errori.
5. **Riepiloghi** – aggregazioni settimanali e mensili, nutrienti e navigazione temporale.
6. **Dashboard** – costruire la Lovelace sulla base delle entità e dei servizi realmente implementati.
7. **Test** – testare scansione valida, barcode sconosciuto, OFF non raggiungibile, prodotto senza nutrienti, pesata manuale, doppia scansione, timeout, riavvio HA, modifica/cancellazione e passaggio tra giorni/mesi.

## Criteri minimi per considerare pronta la prima versione

- Una pesata può essere registrata sia da barcode sia manualmente.
- Ogni voce è assegnata a un pasto e rimane nello storico dopo un riavvio.
- Un alimento nuovo può essere creato e riutilizzato in seguito senza ripetere l'inserimento.
- Le voci possono essere corrette o eliminate.
- Il totale giornaliero è corretto e non duplica le registrazioni.
- La dashboard mostra chiaramente stato dispositivi, pasto, alimenti e totale.
- Le funzioni non ancora implementate sono indicate come tali; nessun dato mancante viene presentato come zero.

## Fuori ambito per la prima versione

- Piani dietetici, obiettivi clinici o prescrizioni nutrizionali.
- Riconoscimento automatico degli alimenti da immagini.
- Sincronizzazione con servizi cloud diversi da Open Food Facts.
- Gestione multiutente o profili familiari, salvo necessità emersa durante la progettazione.

---

**Regola di lavoro:** prima definire e documentare il modello dati e i flussi; solo dopo creare la dashboard. La dashboard non deve basarsi su entità fittizie o su funzioni che il package non implementa ancora.


## Documento tecnico aggiunto

È stata preparata una proposta iniziale per la persistenza e il modello dati:

- [ARCHITECTURE.md](ARCHITECTURE.md) – proposta di integrazione custom Home Assistant con database SQLite locale, catalogo alimenti separato dal diario, snapshot nutrizionali, servizi e criteri di prova.

**Stato della decisione:** proposta documentata, non ancora implementata né collaudata. Il package attuale resta invariato. Il prossimo passo è realizzare un prototipo isolato dell'integrazione e verificare persistenza, query e backup prima di collegarlo al flusso Cosori/GM67.


## Prototipo SQLite isolato – primo avanzamento

Registro di sviluppo dettagliato: [`homeassistant/prototypes/food_diary_sqlite/DEVELOPMENT_LOG.md`](../prototypes/food_diary_sqlite/DEVELOPMENT_LOG.md). Include regole di isolamento, decisioni tecniche, API del prototipo, comandi di test e stato delle verifiche.

Cartella: `homeassistant/prototypes/food_diary_sqlite/`

- [x] Creata una cartella di prototipo separata dai package e dai firmware originali.
- [x] Aggiunto un livello dati Python indipendente da Home Assistant, basato su SQLite standard.
- [x] Aggiunto schema SQL leggibile.
- [x] Aggiunti test automatici per catalogo, barcode duplicati, snapshot nutrizionali, persistenza dopo riapertura, valori sconosciuti e integrità.
- [ ] Eseguire i test in un ambiente Python locale: i test aggiornati sono scritti ma non ancora eseguiti.
- [ ] Eseguire gli stessi test con la versione Python effettivamente usata dall'installazione Home Assistant.
- [x] Aggiungere query aggregate per giorno, settimana e mese nel prototipo isolato (somma nutrienti, dettaglio giornaliero e subtotali per pasto; settimana lunedì–domenica; fuso IANA).
- [x] Correggere l'aggiornamento parziale dei nutrienti: i campi omessi vengono preservati e solo i campi esplicitamente impostati a `None` vengono cancellati.
- [x] Documentare API, decisioni, comandi di test e stato delle verifiche in `homeassistant/prototypes/food_diary_sqlite/DEVELOPMENT_LOG.md`.
- [x] Aggiungere versionamento schema SQLite e migrazione v1→v2 per timestamp a precisione uniforme.
- [x] Aggiungere workflow GitHub Actions con matrice Python 3.10–3.13; [ ] verificare la prima esecuzione CI.
- [ ] Solo dopo i test, realizzare l'integrazione Home Assistant vera e propria.

**Prototipo integrazione Home Assistant separato:** `homeassistant/prototypes/food_diary_integration/`

- [x] Creato scheletro custom integration con config flow e manifest.
- [x] Aggiunte azioni per catalogo, barcode, registrazioni e riepiloghi.
- [x] Aggiunta copia autonoma dello storage SQLite e controllo CI per evitare divergenze.
- [x] Documentati esempi di chiamata azioni e limiti del prototipo.
- [ ] Eseguire CI GitHub e correggere eventuali errori.
- [ ] Verificare compatibilità con la versione Home Assistant Core effettivamente installata.
- [ ] Eseguire test runtime in istanza HA di prova prima di qualsiasi installazione reale.

**Nota di isolamento:** nessun file in `homeassistant/packages/` o `esphome/` è stato modificato. Il prototipo non è installabile e non deve essere copiato nella configurazione attiva.
