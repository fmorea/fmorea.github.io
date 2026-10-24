# Piattaforma Esami Telematici

Piattaforma telematica d'esame eseguibile direttamente da **GitHub Pages** (`fmorea.github.io`) o in locale.

## Caratteristiche Principali
- **Scansione Automatica Repository**: `index.html` scansiona automaticamente la cartella `quiz/` del repository GitHub alla ricerca di file con metadati nel nome (es. `Materia-15min-90soglia.txt`).
- **Supporto Immagini Didattiche**: Possibilità di associare immagini a qualunque quesito via tag `[IMMAGINE] img/figura.png` o URL, visibili durante il test e nella scheda di revisione.
- **Scheda d'Esame Touch**: Mappa numerata delle domande, pulsanti VERO / FALSO, conto alla rovescia e controllo di sicurezza prima della consegna.
- **QR Code di Verifica e Spiegazione**: Al termine della prova viene generato un QR Code (a video e nel PDF) che codifica lo stato delle risposte fornite. Inquadrandolo con lo smartphone si apre la scheda di revisione con la spiegazione didattica di ogni singolo quesito.
- **Revisione Interattiva**: Schermata dedicata con filtri per visualizzare tutte le domande, solo gli errori commessi o le risposte corrette, con la motivazione di ciascuna soluzione.
- **Validazione Formale Codice Fiscale**: Algoritmo ministeriale AdE con calcolo del carattere di controllo per evitare codici formalmente errati.
- **Esportazione Scheda Risultati in PDF & Stampa Universale**: Generazione client-side del riepilogo con tabella esiti e QR Code (jsPDF su browser moderni + foglio stile `@media print` compatibile al 100% con Internet Explorer 9/10/11 per la stampa nativa in PDF).

## Convenzione Nomi File Quiz (`quiz/`)
I file nella cartella `quiz/` seguono la sintassi:
```
[NomeMateria]-[Minuti]min-[Soglia]soglia.txt
```
Esempi:
- `quiz/Patente_B-15min-90soglia.txt` → Materia: "Patente B", Durata: 15 min, Soglia: 90%
- `quiz/Sicurezza_Lavoro-10min-80soglia.txt` → Materia: "Sicurezza Lavoro", Durata: 10 min, Soglia: 80%

## Sintassi dei File Quiz `.txt`
All'interno del file di testo, i quesiti sono separati da `---` e definiti con tag intuitivi:
```txt
[DOMANDA] Il segnale con veicolo che sbanda indica strada scivolosa.
[RISPOSTA] VERO
[ARGOMENTO] Segnali di pericolo
[SPIEGAZIONE] Avverte di un tratto particolarmente sdrucciolevole con pioggia o ghiaccio.
[IMMAGINE] img/strada_sdrucciolevole.svg

---

[DOMANDA] Il limite sulle autostrade è di 150 km/h.
[RISPOSTA] FALSO
[ARGOMENTO] Limiti di velocità
[SPIEGAZIONE] Il limite generale per autovetture è di 130 km/h.
```

## Come pubblicare su GitHub Pages
1. Apri la repository: `https://github.com/fmorea/fmorea.github.io`
2. Committa o aggiorna `index.html`, la cartella `quiz/` e le immagini in `quiz/img/`.
3. Vai su `https://fmorea.github.io`: la piattaforma caricherà in autonomia i quiz presenti nel repository!
