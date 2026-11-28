# Food Diary Dashboard — prototipi grafici

Questa directory contiene esclusivamente prototipi HTML statici del diario alimentare. Non sono dashboard Lovelace e non si collegano a Home Assistant.

## Anteprima
- [index.html](index.html): vista principale, riepilogo, dispositivi, pasti e catalogo.
- [flows.html](flows.html): flussi di inserimento manuale, creazione alimento e consultazione storico.
- [DESIGN.md](DESIGN.md): specifica visuale e principi UX.
- [DATA_CONTRACT.md](DATA_CONTRACT.md): architettura, modello dati, azioni HA esistenti, semantica dei riepiloghi e flusso barcode/bilancia.
- [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md): cronologia delle fasi.

Aprire i file HTML in un browser moderno. Non richiedono librerie o risorse esterne.

## Regole statistiche
- I giorni senza registrazioni sono "nessun dato", non zero kcal.
- La media giornaliera esclude i giorni senza registrazioni.
- Nutrienti non disponibili restano null e non vengono convertiti in zero.
- Prima di mostrare medie complete, la UI deve segnalare eventuali registrazioni con kcal mancanti.

## Limiti
I dati sono dimostrativi. Le azioni di conferma mostrano esplicitamente che non scrivono dati reali. I pulsanti e i selettori servono a valutare gerarchia e comportamento dell'interfaccia, non a simulare un backend funzionante.

## Regole di isolamento
Non copiare questi file nella configurazione attiva di Home Assistant. Prima dell'implementazione occorre verificare le API dell'integrazione sperimentale, completare i test del motore SQLite e mappare solo entità/azioni realmente disponibili. Il prototipo non modifica package, firmware o dashboard attive.
