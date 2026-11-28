# TODO – Dashboard Food Diary

> Documento di pianificazione: **non è ancora una dashboard installabile**. Qui raccogliamo requisiti, flussi e decisioni da verificare prima di scrivere Lovelace YAML o modificare il package Home Assistant.

## Stato del design grafico

Prototipi autonomi in `homeassistant/prototypes/food_diary_dashboard/`:
- `DESIGN.md`: palette Aurora, layout, responsive, UX e regole statistiche.
- `index.html`: vista principale con riepilogo, dispositivi, pasti e archivio.
- `flows.html`: form di porzione, creazione alimento e consultazione storico.
- `README.md` e `DEVELOPMENT_LOG.md`: istruzioni e cronologia.

I dati sono fittizi; nessuna pagina chiama Home Assistant o persiste registrazioni. Non sono stati modificati package, firmware o dashboard attive.

### Decisioni statistiche confermate
- I giorni senza registrazioni sono "nessun dato", non zero kcal.
- La media giornaliera usa solo i giorni con almeno una registrazione.
- Il totale del periodo somma tutte le registrazioni nell'intervallo.
- Il grafico deve distinguere i giorni senza dati dai giorni con registrazioni ma totale zero.

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
- [ ] Assegnare la voce a colazione, pranzo, cena o spuntino.
- [ ] Modificare pasto durante l'inserimento.
- [ ] Mostrare voci giornaliere raggruppate per pasto e relativi subtotali.
- [ ] Correggere o eliminare voci.
- [ ] Conservare registrazioni dopo riavvio HA.
- [ ] Mantenere nutrienti sconosciuti come NULL/non disponibili.

### 2. Riepiloghi e consultazione
- [ ] Riepilogo del giorno selezionato.
- [ ] Totali giornalieri e aggregazioni settimanali/mensili.
- [ ] Navigazione tra giorno, settimana e mese.
- [ ] Visualizzare kcal e, se disponibili, macro e altri nutrienti.
- [x] Giorni senza registrazioni mostrati come "nessun dato", non come zero.
- [x] Media giornaliera calcolata esclusivamente sui giorni con almeno una registrazione.
- [x] Totale del periodo calcolato come somma di tutte le registrazioni.
- [ ] Distinguere visivamente nel grafico giorni senza dati e giorni con registrazioni ma totale zero.
- [ ] Gestire cambio mese/anno e settimane a cavallo tra mesi.

### 3. Archivio locale minimalista
- [ ] Catalogo prodotti distinto dal diario delle porzioni.
- [ ] Salvare prodotti trovati su OFF e prodotti inseriti manualmente.
- [ ] Barcode univoco quando disponibile; identificatore locale per prodotti senza barcode.
- [ ] Nome, marca facoltativa, barcode facoltativo, nutrienti per 100 g e fonte.
- [ ] Ricerca testuale e ordinamento alfabetico.
- [ ] Modifica e cancellazione prodotti con gestione dei riferimenti allo storico.

### 4. Inserimento manuale
- [ ] Selezione prodotto da archivio.
- [ ] Peso stabile Cosori precompilato se disponibile.
- [ ] Modifica manuale peso e pasto.
- [ ] Calcolo nutrienti porzione.
- [ ] Conferma esplicita prima del salvataggio.
- [ ] Inserimento possibile anche senza bilancia.

### 5. Nuovo alimento
- [ ] Nome obbligatorio; marca e barcode facoltativi.
- [ ] Nutrienti per 100 g facoltativi e parziali.
- [ ] Validazione numerica non negativa.
- [ ] Gestione barcode già presente.

### 6. Barcode e acquisizione
- [ ] Conservare pesata anche se OFF non trova il barcode.
- [ ] Associazione alternativa a prodotto esistente o nuovo alimento.
- [ ] Distinguere barcode sconosciuto, nutrienti mancanti ed errore rete.
- [ ] Gestire sessioni, timeout, annullamento e scansioni duplicate.

### 7. Dashboard Lovelace
- [ ] Riepilogo kcal, dispositivi, peso e sessione.
- [ ] Diario per pasto e archivio ricercabile.
- [ ] Form manuali e storico navigabile.
- [ ] Responsive e leggero su tablet datati.
- [ ] Preferire card native salvo beneficio concreto da custom card.

## Decisioni tecniche ancora aperte
- [ ] Verificare persistenza SQLite e backup nell'integrazione sperimentale.
- [ ] Definire contratto API UI/servizi e gestione errori.
- [ ] Verificare versione Python e Home Assistant effettive.
- [ ] Testare integrazione e query prima di collegare la dashboard.
- [ ] Verificare rendering, accessibilità e contrasto su dispositivi reali.

## Proposta di sviluppo
1. Completare test storage e integrazione.
2. Definire API e stati di acquisizione.
3. Collegare i form ai servizi reali.
4. Realizzare dashboard Lovelace.
5. Testare barcode, OFF, inserimento manuale, riavvio, periodi e fuso orario.

**Regola di lavoro:** tutti i prototipi restano isolati in `homeassistant/prototypes/`; non modificare package, firmware o dashboard attive prima della validazione.


## Contratto dati e collegamento dashboard
- [x] Creato `homeassistant/prototypes/food_diary_dashboard/DATA_CONTRACT.md` con modello dati, azioni HA presenti, flusso barcode/bilancia e responsabilità frontend.
- [x] Verificata la lista delle azioni realmente registrate nell'integrazione sperimentale.
- [x] Evidenziato il gap: `period_summary` non espone ancora media giornaliera né copertura dei nutrienti.
- [x] Aggiornato il mockup storico per mostrare un giorno senza registrazioni come N/D.
- [x] Estendere riepiloghi SQLite con copertura nutrienti e denominatore esplicito della media.
- [x] Aggiungere test per giornate senza dati, nutrienti kcal mancanti e medie.\n- [ ] Eseguire e verificare la matrice CI Python 3.10–3.13.
- [ ] Verificare versione Home Assistant Core e supporto frontend per risposte delle azioni.
- [ ] Scegliere card native con helper/script oppure custom Lovelace card.
- [ ] Collegare dashboard solo dopo test backend su istanza HA separata.

Contratto: [DATA_CONTRACT.md](../prototypes/food_diary_dashboard/DATA_CONTRACT.md).


## Compatibilità 2026 e distribuzione HACS

Ambiente di riferimento confermato: HA OS 18.4, Core 2026.11.3, Supervisor 2026.11.0, Frontend 20261028.8.

- [x] Definire obiettivo: integrazione completa, configurabile da UI e distribuibile tramite HACS/Marketplace.
- [x] Decidere repository pubblico dedicato, separato da `crow782/cosori`.
- [x] Decidere che il pacchetto includerà il pannello Aurora locale, per evitare una seconda installazione HACS.
- [x] Definire selettore ESPHome per sensore peso stabile e selettore ESPHome per device scanner.
- [ ] Implementare config flow reale e options flow con selettori nativi.
- [ ] Correggere lifecycle config entry e registrazione/rimozione servizi.
- [ ] Aggiungere identificatore scanner all'evento ESPHome e testare scansioni ripetute.
- [ ] Implementare coordinator per correlazione barcode/peso stabile/timeout.
- [ ] Implementare pannello frontend locale e registrazione con API pubbliche HA.
- [ ] Sostituire `strings.json` con traduzioni custom in `translations/en.json` e `translations/it.json`.
- [ ] Completare manifest HACS, `hacs.json`, issue tracker, codeowners, brand e release.
- [ ] Creare repository dedicato e trasferire solo il pacchetto validato.
- [ ] Testare più versioni Core 2026, hassfest, test integrazione e installazione/upgrade HACS.

Specifica: [HACS_ARCHITECTURE.md](../prototypes/food_diary_integration/HACS_ARCHITECTURE.md).
