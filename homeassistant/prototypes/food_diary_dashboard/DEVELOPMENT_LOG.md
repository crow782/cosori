# Registro di sviluppo — Food Diary Dashboard

## Fase 0 — Mockup principale
Creato `index.html` come anteprima statica responsive in stile Aurora. I dati sono fittizi; la pagina non usa API Home Assistant.

## Fase 1 — Specifica visuale
Creato `DESIGN.md` con layout, palette, requisiti responsive, distinzione tra peso live e porzione registrata, e principi per nutrienti sconosciuti.

## Fase 2 — Flussi UX e storico
Aggiunto `flows.html` con registrazione manuale porzione, creazione scheda alimento e storico dimostrativo. Le azioni di salvataggio non persistono dati. Il grafico ora distingue visivamente il giorno senza registrazioni.

## Fase 3 — Decisioni statistiche confermate
- I giorni senza registrazioni sono "nessun dato", non zero kcal.
- La media giornaliera esclude i giorni senza registrazioni.
- Il totale periodo somma tutte le registrazioni nell'intervallo.
- I nutrienti sconosciuti restano null, mai zero.
- Le registrazioni con kcal mancanti richiedono un indicatore di copertura, per non presentare una media parziale come completa.

## Fase 4 — Contratto dati
Creato `DATA_CONTRACT.md` dopo aver verificato il codice reale di storage e delle azioni Home Assistant. Il documento separa le funzioni già implementate dalle estensioni ancora necessarie:
- catalogo e registrazioni sono entità distinte;
- le registrazioni mantengono snapshot di alimento e nutrienti;
- le azioni attualmente registrate sono elencate con input/output;
- il flusso scanner/bilancia è modellato a stati;
- è evidenziato il gap tra riepilogo attuale e media/coverage che la UI dovrà mostrare;
- la scelta tra card Lovelace native e custom card resta aperta fino alla verifica della versione HA e delle API frontend.

## Verifiche e limiti
- I file HTML/CSS non usano librerie esterne.
- Non è stata eseguita una prova browser automatizzata né una verifica su dispositivi reali.
- Non è stata eseguita alcuna connessione a Home Assistant.
- Le unit test SQLite non sono state eseguite in questo passaggio.
- La copia storage dell'integrazione e il modulo SQLite autonomo risultano allo stesso SHA Git al momento della verifica.
- Nessun file in `homeassistant/packages/` o `esphome/` è stato modificato.

## Prossimo passo
Estendere e testare il contratto riepiloghi nel backend (coverage nutrienti e media con denominatore esplicito), quindi verificare l'integrazione su una istanza HA di prova. Dopo aver conosciuto la versione Home Assistant effettiva, scegliere il frontend e collegare le viste.
