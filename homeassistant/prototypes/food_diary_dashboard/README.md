# Food Diary Dashboard — prototipi grafici

Questa directory contiene esclusivamente prototipi HTML statici del diario alimentare. Non sono dashboard Lovelace e non si collegano a Home Assistant.

## Anteprima
- [index.html](index.html): vista principale, riepilogo, dispositivi, pasti e catalogo.
- [flows.html](flows.html): flussi UX di inserimento manuale, creazione alimento e consultazione storico.
- [DESIGN.md](DESIGN.md): specifica visuale e principi UX.

Aprire i file HTML in un browser moderno. Non richiedono librerie o risorse esterne.

## Limiti
I dati sono dimostrativi. Le azioni di conferma mostrano esplicitamente che non scrivono dati reali. I pulsanti e i selettori servono a valutare gerarchia e comportamento dell'interfaccia, non a simulare un backend funzionante.

## Regole di isolamento
Non copiare questi file nella configurazione attiva di Home Assistant. Prima dell'implementazione occorre verificare le API dell'integrazione sperimentale, completare i test del motore SQLite e mappare solo entità/azioni realmente disponibili. Il prototipo non modifica package, firmware o dashboard attive.
