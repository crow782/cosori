# Food Diary — installazione isolata e rimozione sicura

Questo documento descrive la procedura prevista per la prima installazione su Home Assistant OS. Il prototipo non è ancora una release installabile: non copiare il codice sulla macchina principale finché non è stata pubblicata una release verificata.

## Cosa viene installato

- Un solo componente custom: `custom_components/food_diary/`.
- Un config entry chiamato Food Diary.
- Entità diagnostiche con prefisso generato da Home Assistant.
- Servizi/azioni nel dominio `food_diary`.
- Database dedicato: `<config>/food_diary/food_diary.db`.
- Risorsa frontend servita sotto `/food_diary/` quando l'integrazione è caricata.

Non vengono modificati:
- firmware ESPHome o configurazioni del dispositivo;
- entità sorgenti dello scanner o della bilancia;
- automazioni, script, scene o dashboard esistenti;
- Recorder o database interno di Home Assistant;
- file `configuration.yaml` e package già presenti.

La risorsa dashboard sarà aggiunta manualmente dall'utente, soltanto dopo aver verificato il funzionamento base. Non verrà sovrascritta una dashboard esistente.

## Prima installazione sulla macchina principale

1. Creare un backup completo di Home Assistant da Impostazioni → Sistema → Backup e verificare che il backup sia disponibile.
2. Installare il pacchetto ufficiale/release, non il branch di sviluppo.
3. Riavviare Home Assistant soltanto se richiesto dal metodo di installazione.
4. Aggiungere Food Diary da Impostazioni → Dispositivi e servizi → Aggiungi integrazione.
5. Selezionare le tre entità sorgenti corrette. La procedura non modifica le entità selezionate.
6. Lasciare la registrazione automatica disattivata per la prima verifica; controllare gli stati diagnostici e i servizi.
7. Verificare che il database venga creato esclusivamente in `<config>/food_diary/`.
8. Attivare la registrazione automatica soltanto dopo aver verificato tara, lettura barcode e peso stabile.
9. Aggiungere la risorsa Aurora alla dashboard solo quando la card è stata validata sul frontend della versione Core installata.

## Rimozione

1. Disattivare prima la registrazione automatica e annullare eventuali scansioni pendenti.
2. Rimuovere Food Diary da Impostazioni → Dispositivi e servizi → integrazione Food Diary.
3. Verificare che le entità diagnostiche e i servizi non siano più disponibili.
4. Rimuovere manualmente la risorsa Lovelace `/food_diary/food-diary-card.js`, se era stata aggiunta.
5. Rimuovere la cartella `custom_components/food_diary/` tramite lo stesso metodo con cui era stata installata.
6. Riavviare Home Assistant.
7. Verificare il log di avvio e che le altre integrazioni continuino a caricarsi.

**I dati non vengono cancellati automaticamente.** Il database `<config>/food_diary/food_diary.db` resta disponibile per un'eventuale reinstallazione. Se si desidera eliminarlo, farlo soltanto dopo aver esportato o salvato i dati e dopo aver verificato il percorso esatto. Non usare comandi di cancellazione generici sulla directory `/config`.

## Limiti e garanzie

Una custom integration opera nello stesso processo Home Assistant delle altre integrazioni: nessun componente Python può garantire rischio zero. La strategia riduce il rischio con directory, servizi, entità e database dedicati, nessuna modifica automatica alla configurazione esistente, test d'installazione/rimozione su istanza separata e conservazione dei dati in disinstallazione.

Prima di una release stabile sono obbligatori:
- test su una istanza Home Assistant OS di prova;
- installazione, setup, reload, unload e rimozione;
- verifica che l'unload non lasci task, listener o servizi attivi;
- verifica del backup e ripristino del database;
- verifica di log puliti e compatibilità con la versione Core dichiarata.

Fino al completamento di questi test, il progetto resta sperimentale e non va installato sulla macchina principale.
