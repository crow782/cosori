# Food Diary – proposta architettura dati

> Stato: **proposta tecnica + primo prototipo SQLite isolato**. Il livello dati è stato aggiunto in `homeassistant/prototypes/food_diary_sqlite/`; non è ancora un'integrazione Home Assistant e non è installabile. I test sono scritti ma non ancora eseguiti. Il package esistente resta separato e invariato.

## 1. Decisione proposta

Usare una piccola **integrazione custom Home Assistant** (custom_components/food_diary) con database **SQLite locale** dedicato, usando il modulo SQLite della libreria standard Python.

Perché:
- il diario contiene record multipli e deve poter essere interrogato per intervallo di date;
- il catalogo prodotti richiede ricerca, ordinamento e controllo duplicati;
- gli helper input_text hanno limiti di lunghezza e non sono un database;
- il recorder di Home Assistant è pensato per lo storico degli stati, non come archivio applicativo modificabile;
- SQLite non richiede un servizio esterno, cloud, container aggiuntivi o dipendenze Python di terze parti.

Percorso dati proposto: /config/food_diary/food_diary.db. La cartella deve essere inclusa nei backup di Home Assistant. Il database non va committato nel repository.

## 2. Modello dati

### Tabella foods – catalogo alimenti

Campi proposti:
- id: identificatore interno stabile;
- name: descrizione obbligatoria;
- brand: marca facoltativa;
- barcode: facoltativo, univoco quando presente;
- nutrienti per 100 g: energy_kcal, protein_g, carbohydrates_g, sugars_g, fat_g, saturated_fat_g, fiber_g, salt_g;
- source: openfoodfacts oppure manual;
- created_at, updated_at.

I valori nutrizionali mancanti restano NULL (sconosciuti), mai convertiti automaticamente in zero. La ricerca e la lista saranno ordinate per nome in modo alfabetico, senza distinzione tra maiuscole e minuscole.

### Tabella entries – diario delle porzioni

Campi proposti:
- id: identificatore univoco della registrazione;
- food_id: collegamento al prodotto, se presente;
- food_name_snapshot e brand_snapshot: descrizione conservata al momento del consumo;
- barcode_snapshot: barcode usato, se disponibile;
- weight_g: peso effettivo in grammi;
- meal_type: breakfast, lunch, dinner, snack;
- consumed_at: data e ora locali con offset/fuso gestito in modo esplicito;
- nutrienti della porzione calcolati al momento del salvataggio;
- nutrienti per 100 g usati nel calcolo (snapshot);
- source: scansione, selezione catalogo o inserimento manuale;
- created_at, updated_at.

Lo snapshot è fondamentale: una modifica futura al prodotto nel catalogo non deve cambiare il contenuto nutrizionale dei pasti già registrati.

## 3. Operazioni che l'integrazione dovrà offrire

Servizi Home Assistant con validazione e risposte/eventi di esito:
- aggiungere o aggiornare un alimento;
- cercare/listare alimenti, con ordinamento alfabetico;
- registrare una porzione associandola a un pasto;
- correggere una registrazione;
- eliminare una registrazione con ID esplicito;
- ottenere voci e totali per giorno/intervallo;
- ottenere aggregazioni giornaliere per settimana e mese;
- esportare i dati in CSV (da valutare per la prima versione).

Le operazioni di scrittura devono essere idempotenti dove possibile e validate: peso positivo, pasto ammesso, barcode non duplicato, valori numerici non negativi.

## 4. Flusso barcode + Open Food Facts

1. ESPHome invia barcode e peso stabile a Home Assistant.
2. L'integrazione cerca prima il barcode nel catalogo locale.
3. Se presente, usa il record locale senza chiamata di rete.
4. Se assente, Home Assistant interroga Open Food Facts.
5. Se OFF restituisce dati utilizzabili, il prodotto viene salvato nel catalogo locale.
6. La porzione viene proposta/registrata secondo la modalità scelta nell'interfaccia; la prima versione deve rendere chiaro se il salvataggio è automatico o richiede conferma.
7. Se OFF non trova il prodotto o mancano nutrienti, barcode e peso restano disponibili per associazione manuale o creazione prodotto. Non si scarta la pesata.

Da definire nella prova: conferma prima del salvataggio automatico, comportamento di doppia scansione e timeout della sessione.

## 5. Flusso manuale

- Selezionare un alimento dal catalogo ordinato per descrizione.
- Acquisire il peso stabile Cosori oppure digitare il peso.
- Selezionare il pasto.
- Visualizzare una stima dei nutrienti disponibili.
- Confermare la registrazione.

Il mini-form nuovo alimento salva prima il prodotto nel catalogo; successivamente lo rende immediatamente selezionabile per la porzione.

## 6. Statistiche

Le statistiche devono essere query sul database, non contatori cumulativi da azzerare:
- totale del giorno selezionato e subtotali per pasto;
- somma e media giornaliera della settimana;
- somma e media giornaliera del mese;
- conteggio dei giorni con registrazioni, per non confondere giorni senza dati con zero calorie.

Settimana proposta: lunedì–domenica. Le date devono essere calcolate nel fuso orario configurato in Home Assistant, evitando errori a mezzanotte e nei cambi di ora legale.

## 7. Interfaccia Home Assistant

La prima scelta è mantenere la UI il più possibile nativa:
- sensori per totali e stato della sessione;
- servizi dell'integrazione per scrittura e operazioni;
- helper Lovelace solo per i campi temporanei dei moduli, non come archivio;
- elenco prodotti dinamico ordinato alfabeticamente.

Prima di decidere le card, verificare un prototipo per selezione/ricerca dinamica del catalogo. Se le card native non consentono una buona ricerca o la modifica delle righe, valutare una sola custom card HACS, documentandone installazione e aggiornamenti. Non aggiungere dipendenze solo per estetica.

## 8. Backup, migrazione e sicurezza

- Il file SQLite risiede in /config/food_diary/ ed è incluso nei backup.
- Prevedere esportazione CSV e un controllo d'integrità SQLite.
- Nessun database reale, barcode personali o segreti nel repository.
- L'integrazione valida tutti i dati ricevuti dai servizi e non espone endpoint HTTP non autenticati.
- Il package homeassistant/packages/food_diary.yaml attuale resta intatto durante lo sviluppo.
- La migrazione dal contatore kcal esistente va fatta solo dopo test e con possibilità di tornare indietro.

## 9. Prototipo tecnico – stato aggiornato

Il prototipo SQLite indipendente si trova in `homeassistant/prototypes/food_diary_sqlite/`. Il livello dati non importa moduli Home Assistant e non è installabile come integrazione.

Funzioni attualmente presenti:
- catalogo alimenti con barcode univoco, ricerca alfabetica, inserimento, modifica e cancellazione;
- registrazione e cancellazione delle porzioni;
- snapshot dei dati nutrizionali e del nome prodotto al momento del consumo;
- aggiornamento parziale dei nutrienti senza cancellare i campi non specificati; passare esplicitamente `None` per cancellare un singolo valore;
- riepilogo `period_summary(period, anchor_date, timezone_name)` per giorno, settimana e mese;
- raggruppamento locale per data e pasto, settimana lunedì–domenica;
- somme dei nutrienti noti, mantenendo `None` se tutti i valori del gruppo sono sconosciuti.

Per i riepiloghi, i confini giorno/settimana/mese vengono calcolati nel fuso IANA indicato (ad esempio `Europe/Rome`) e convertiti in UTC per la query. I record vengono poi raggruppati nuovamente per data locale. Questo è necessario per gestire correttamente mezzanotte e cambi dell'ora legale.

Il registro completo dello sviluppo, il contratto dei metodi, i comandi di test e le verifiche ancora da fare sono in `homeassistant/prototypes/food_diary_sqlite/DEVELOPMENT_LOG.md`.

**Stato di verifica:** i test automatici sono stati aggiornati per coprire modifiche parziali e aggregazioni, incluso il cambio all'ora legale. Non sono ancora stati eseguiti. Il prototipo non deve essere considerato collaudato.

## 10. Criteri di accettazione

Prima di costruire tutta la dashboard:
1. implementare lo scheletro dell'integrazione e lo schema SQLite;
2. testare creazione/ricerca prodotto e registrazione di due porzioni;
3. riavviare Home Assistant e verificare che catalogo e diario siano presenti;
4. modificare il prodotto e verificare che lo snapshot della vecchia porzione non cambi;
5. correggere ed eliminare una porzione;
6. verificare aggregazioni giorno/settimana/mese e cambio di data;
7. verificare backup/ripristino su una copia di prova.

Solo dopo questi test si definiscono le entità definitive e si realizza la dashboard Lovelace.

## 11. Questioni ancora aperte

- La registrazione da scansione sarà automatica o richiederà conferma? Proposta: automatica solo quando prodotto e nutrienti sono riconosciuti; altrimenti resta in sospeso per intervento.
- Il pasto sarà suggerito in base all'ora e modificabile? Proposta: sì.
- Per prodotti senza energia ma con altri nutrienti, consentire registrazione e statistiche parziali? Proposta: sì, senza inventare kcal.
- Serve supporto per quantità diverse dai grammi (ml/unità)? Fuori dalla prima versione, salvo necessità concreta.

---
Questa architettura è una proposta da verificare su una copia/ambiente di test. Non modifica il package attuale e non implica che l'integrazione sia già stata sviluppata.
