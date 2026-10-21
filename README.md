# Simulatore Quiz con Revisione e QR Code

Simulatore interattivo di quiz statico eseguibile direttamente da **GitHub Pages** (`fmorea.github.io`) o in locale.

## Caratteristiche Principali
- **Scheda d'Esame Touch**: Mappa numerata delle domande, pulsanti VERO / FALSO, conto alla rovescia e controllo di sicurezza prima della consegna.
- **QR Code di Verifica e Spiegazione**: Al termine della prova viene generato un QR Code (a video e nel PDF) che codifica lo stato delle risposte fornite. Inquadrandolo con lo smartphone si apre la scheda di revisione con la spiegazione didattica di ogni singolo quesito.
- **Revisione Interattiva**: Schermata dedicata con filtri per visualizzare tutte le domande, solo gli errori commessi o le risposte corrette, con la motivazione di ciascuna soluzione.
- **Validazione Formale Codice Fiscale**: Algoritmo ministeriale AdE con calcolo del carattere di controllo per evitare codici formalmente errati.
- **Esportazione Scheda Risultati in PDF**: Generazione lato client del riepilogo della prova con tabella esiti e QR Code per la consultazione mobile.
- **Caricamento Quesiti Flessibile**: Supporto diretto a banche dati integrate, file CSV o JSON (locali o remoti da repository GitHub) con campo per la spiegazione didattica del quesito.

## Come pubblicare su GitHub Pages
1. Apri la pagina del repository: `https://github.com/fmorea/fmorea.github.io`
2. Carica o committa i file `index.html` e `template_domande.csv`.
3. Vai su `https://fmorea.github.io` per visualizzare il simulatore attivo online!
