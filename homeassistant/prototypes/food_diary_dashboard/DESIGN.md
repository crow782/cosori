

## Evoluzione UX — inserimento e storico
È stato aggiunto `flows.html` come seconda tavola di prototipazione:
- form porzione con alimento da archivio, grammi, pasto, data/ora e anteprima;
- form separato per nuovo alimento, con barcode e valori nutrizionali facoltativi;
- storico con selezione 7 giorni/mese, totale, media e dettaglio per giorno.

Le azioni di salvataggio sono volutamente dimostrative e non persistono dati. Prima dell'implementazione occorre decidere il comportamento dei giorni senza registrazioni e il denominatore della media. Non mostrare obiettivi calorici non configurati.

## Accessibilità e prestazioni — criteri da mantenere
- Etichette esplicite per tutti i campi e focus visibile da tastiera.
- Feedback tramite regioni `aria-live` per anteprime e validazione.
- Contrasto e leggibilità da verificare su browser/dispositivi reali.
- Evitare dipendenze JS esterne; animazioni non essenziali e rispetto di `prefers-reduced-motion`.
- Sui tablet meno recenti limitare blur, ombre pesanti e aggiornamenti grafici continui.
