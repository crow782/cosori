# Registro di sviluppo — Food Diary Dashboard

## Fase 0 — Mockup principale
Creato `index.html` come anteprima statica responsive in stile Aurora. I dati sono fittizi; la pagina non usa API Home Assistant.

## Fase 1 — Specifica visuale
Creato `DESIGN.md` con layout, palette, requisiti responsive, distinzione tra peso live e porzione registrata, e principi per nutrienti sconosciuti.

## Fase 2 — Flussi UX e storico
Aggiunto `flows.html` con tre aree di progettazione:
- registrazione manuale di una porzione da catalogo, con quantità, pasto, data/ora e anteprima;
- form separato per creare una scheda alimento, con barcode e nutrienti facoltativi;
- storico dimostrativo a 7 giorni/mese, totali, media e riepilogo per giorno.

Le azioni di salvataggio non persistono dati: mostrano un messaggio esplicito che ricorda che si tratta di un prototipo.

## Scelte UX fissate
- Il prodotto (catalogo) e la porzione consumata (diario) sono entità distinte.
- Il pasto è scelto nella registrazione, non nella scheda alimento.
- Il peso è espresso in grammi; energia in kcal.
- Nutrienti mancanti rimangono non disponibili e non vengono convertiti in zero.
- La settimana inizia lunedì; il fuso definitivo sarà quello configurato in Home Assistant.
- **Giorni senza registrazioni:** rappresentati come "nessun dato", non come zero kcal.
- **Media giornaliera:** calcolata solo sui giorni con almeno una registrazione.
- **Totale periodo:** somma di tutte le registrazioni nell'intervallo.
- Nei grafici i giorni senza dati devono avere una rappresentazione distinta da un giorno con registrazioni e totale zero.
- Nessun obiettivo calorico viene presunto o mostrato se non configurato.

## Verifiche
- File HTML e CSS scritti senza librerie esterne.
- Non è stata eseguita una prova browser automatizzata né una verifica su dispositivi reali.
- Non è stata eseguita alcuna connessione a Home Assistant.
- Nessun file in `homeassistant/packages/` o `esphome/` è stato modificato.

## Prossimo passo
Definire il contratto tra UI e servizi dell'integrazione sperimentale, poi verificare backend e rendering. Solo dopo i test backend si potrà costruire la dashboard Lovelace effettiva.
