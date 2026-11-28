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

## Stato
- [x] Direzione visiva definita.
- [x] Mockup HTML autonomo e responsive.
- [ ] Verifica visuale su HA desktop/tablet/mobile.
- [ ] Mappatura su entità e azioni reali.
- [ ] Scelta tra card native e custom card.
- [ ] Test accessibilità e contrasto su istanza reale.

Il mockup non è installabile e non chiama servizi Home Assistant. L'implementazione futura dovrà usare esclusivamente entità e azioni realmente disponibili. Tutto resta isolato in homeassistant/prototypes/; non modificare package, firmware o dashboard attive.
