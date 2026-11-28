

## Evoluzione prototipo grafico — inserimento e storico
- [x] Aggiunta tavola `homeassistant/prototypes/food_diary_dashboard/flows.html` con form di registrazione porzione e scelta del pasto.
- [x] Aggiunto form separato per nuovo alimento, con barcode e nutrienti facoltativi.
- [x] Aggiunta vista storico dimostrativa con intervallo 7 giorni/mese, totali, media e dettaglio giornaliero.
- [x] Aggiunti feedback accessibili, focus visibile, layout mobile e rispetto di `prefers-reduced-motion` nel prototipo.
- [x] Documentati limiti e decisioni aperte in `README.md`, `DESIGN.md` e `DEVELOPMENT_LOG.md`.
- [ ] Verificare rendering su browser desktop e smartphone/tablet reali.
- [ ] Confermare trattamento dei giorni senza dati e denominatore della media.
- [ ] Collegare i form ai servizi dell'integrazione solo dopo test backend e definizione del contratto API.

Anteprima flussi: [flows.html](../prototypes/food_diary_dashboard/flows.html). È una demo statica, non collegata a Home Assistant e non salva registrazioni.
