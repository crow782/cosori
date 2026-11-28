# Food Diary Dashboard — Aurora Design System

> Concept grafico e prototipo statico. I dati dell'anteprima sono dimostrativi e non provengono da Home Assistant. Nessuna configurazione attiva viene modificata.

## Direzione visiva
- Superfici glass/dark, trasparenze moderate, blur leggero, bordi sottili e angoli arrotondati.
- Fondo profondo con gradienti radiali blu/viola e teal.
- Accenti Aurora: viola #8b78d5, ambra #d99a5b, teal #55aebc, blu #5687bd.
- Tipografia di sistema, titoli compatti, valori calorici in evidenza e icone MDI.
- Animazioni discrete e rispetto di prefers-reduced-motion.
- Responsive per contenitore, senza dipendenze esterne nel mockup.

## Layout
1. Header con titolo, data e navigazione giorno/settimana/mese.
2. Hero calorico con totale, indicatore di progresso e riepiloghi settimana/mese.
3. Macronutrienti: proteine, carboidrati e grassi.
4. Stato Cosori, peso stabile, scanner GM67 e sessione.
5. Azioni rapide: scansione, ricerca archivio, inserimento manuale, nuovo alimento.
6. Diario giornaliero raggruppato per colazione, pranzo, cena e spuntino.
7. Ultima acquisizione con alimento, peso, kcal e stato.
8. Archivio alfabetico ricercabile.

## Responsive
- Desktop: riepilogo in alto, diario principale e pannello laterale.
- Tablet: griglia adattiva a due colonne.
- Smartphone: una colonna, riepilogo compatto e azioni rapide accessibili.
- Nessuna larghezza fissa; controlli e card si adattano al contenitore.

## UX e dati
- Separare calorie del periodo e calorie dell'ultimo prodotto.
- Distinguere peso live della bilancia dal peso già registrato.
- Barcode non riconosciuto o dati nutrizionali incompleti non devono causare perdita della pesata.
- Inserimento manuale: alimento, peso, pasto, riepilogo e conferma.
- Catalogo minimalista, alfabetico e ricercabile; form prodotto separato dal form pasto.
- Nutrienti sconosciuti non vanno presentati come zero.
- Settimana lunedì–domenica; date nel fuso configurato in Home Assistant.

## Evoluzione UX — inserimento e storico
È stato aggiunto `flows.html` come seconda tavola di prototipazione:
- form porzione con alimento da archivio, grammi, pasto, data/ora e anteprima;
- form separato per nuovo alimento, con barcode e valori nutrizionali facoltativi;
- storico con selezione 7 giorni/mese, totale, media e dettaglio per giorno.

Le azioni di salvataggio sono dimostrative e non persistono dati.

### Regole definitive per i riepiloghi
- Un giorno senza registrazioni è **senza dati**, non equivale a zero kcal.
- La media giornaliera si calcola solo sui giorni con almeno una registrazione.
- Il totale del periodo è la somma di tutte le registrazioni presenti nell'intervallo.
- Nei grafici, i giorni senza dati devono essere distinguibili dai giorni con registrazioni che totalizzano zero kcal.
- Non mostrare obiettivi calorici non configurati.

## Accessibilità e prestazioni — criteri da mantenere
- Etichette esplicite per tutti i campi e focus visibile da tastiera.
- Feedback tramite regioni `aria-live` per anteprime e validazione.
- Contrasto e leggibilità da verificare su browser/dispositivi reali.
- Evitare dipendenze JS esterne; animazioni non essenziali e rispetto di `prefers-reduced-motion`.
- Sui tablet meno recenti limitare blur, ombre pesanti e aggiornamenti grafici continui.

## Stato
- [x] Direzione visiva definita.
- [x] Mockup HTML autonomo e responsive.
- [x] Regole statistiche per giorni senza dati e media confermate.
- [ ] Verifica visuale su HA desktop/tablet/mobile.
- [ ] Mappatura su entità e azioni reali.
- [ ] Scelta tra card native e custom card.
- [ ] Test accessibilità e contrasto su istanza reale.

Il mockup non è installabile e non chiama servizi Home Assistant. L'implementazione futura dovrà usare esclusivamente entità e azioni realmente disponibili. Tutto resta isolato in homeassistant/prototypes/; non modificare package, firmware o dashboard attive.
