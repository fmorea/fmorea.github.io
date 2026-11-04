# Piattaforma Esami Telematici

Piattaforma telematica d'esame eseguibile direttamente da **GitHub Pages** (`fmorea.github.io`) o in locale.

## Caratteristiche Principali
- **Scansione Automatica Repository**: `index.html` scansiona automaticamente la cartella `quiz/` del repository GitHub alla ricerca dei file di verifica e legge classe, specializzazione, materia, scuola, periodo, anno, durata e soglia dal nome.
- **Ripasso con Materiali Didattici**: testo e pagine illustrate dei PDF vengono estratti in schede indipendenti, con miniature, navigazione, spiegazioni dei quesiti e lettura vocale in italiano con preferenza per una voce maschile installata, selezione della voce, pausa e controllo della velocità. La qualità dipende dalle voci disponibili nel browser o nel sistema. Le pagine si possono ingrandire con il pinch touch, lo slider, i pulsanti o i tasti `+`/`-` (rotellina con `Ctrl`); `0` ripristina la dimensione iniziale.
- **Compatibilità dei materiali**: browser obsoleti o privi del supporto WebP (come Internet Explorer) ricevono un avviso di aggiornamento e un collegamento diretto al PDF originale; se le schede statiche non sono disponibili, è mostrato il medesimo fallback al documento originale.
- **Percorso guidato**: prima si sceglie la classe, poi si sceglie se seguire una lezione o fare una simulazione d'esame.
- **Tempo Attivo in Piattaforma**: il tempo viene conteggiato solo mentre la pagina è visibile e attiva, salvato nel browser per il candidato e riportato nel certificato PDF.
- **Prova in anonimo**: nome e cognome sono facoltativi; lascia entrambi i campi vuoti per svolgere la prova e ottenere un certificato indicato come “Anonimo”. Se inserisci un solo dato, la piattaforma chiede di completare entrambi i campi.
- **Supporto Immagini Didattiche**: Possibilità di associare immagini a qualunque quesito via tag `[IMMAGINE] img/figura.png` o URL, visibili durante il test e nella scheda di revisione.
- **Scheda d'Esame Touch**: Mappa numerata delle domande, pulsanti VERO / FALSO, conto alla rovescia e controllo di sicurezza prima della consegna.
- **QR Code di Verifica e Spiegazione**: Al termine della prova viene generato un QR Code (a video e nel PDF) che codifica lo stato delle risposte fornite. Inquadrandolo con lo smartphone si apre la scheda di revisione con la spiegazione didattica di ogni singolo quesito.
- **Revisione Interattiva**: Schermata dedicata con filtri per visualizzare tutte le domande, solo gli errori commessi o le risposte corrette, con la motivazione di ciascuna soluzione.
- **Esportazione Scheda Risultati in PDF & Stampa Universale**: Generazione client-side del riepilogo con tabella esiti e QR Code (jsPDF su browser moderni + foglio stile `@media print` compatibile al 100% con Internet Explorer 9/10/11 per la stampa nativa in PDF).

## Convenzione Nomi File Quiz (`quiz/`)
I file nella cartella `quiz/` seguono la sintassi:
```
[CLASSE]_[SPECIALIZZAZIONE]_[MATERIA]_[SCUOLA]_[PERIODO]_[ANNO]-[Minuti]min-[Soglia]soglia.txt
```
Esempi:
- `quiz/3B_INF_Telecomunicazioni_IIS-LAGRANGE_trimestre_2026-2027-60min-55soglia.txt`
- `quiz/4A_ELE_TPSEE_IIS-LAGRANGE_trimestre_2026-2027-60min-55soglia.txt`

Il catalogo `appunti/manifest.json` collega la chiave classe-specializzazione-materia (in minuscolo, con `_` come separatore) al PDF originale. La 3B e la 3C utilizzano lo stesso PDF di telecomunicazioni. Il catalogo `appunti/slides/manifest.json` collega gli stessi corsi ai testi estratti e alle immagini WebP delle singole pagine.

Per rigenerare le schede dopo aver aggiornato un PDF, eseguire `python appunti/build_slides.py` con Poppler (`pdftotext` e `pdftoppm`), ImageMagick (`magick`) e il pacchetto Python `rapidocr_onnxruntime` installati. L'OCR integra il testo delle pagine scansionate quando è più completo del testo incorporato nel PDF. Per aggiornare solo i testi e riutilizzare le immagini WebP già generate, eseguire `python appunti/build_slides.py --reuse-images`. La piattaforma pubblicata utilizza i file statici generati, senza elaborare i PDF nel browser.

Il conteggio delle ore è locale al browser e al dispositivo: non è sincronizzato tra dispositivi né verificato da un server. Il tempo viene conteggiato a piattaforma aperta, in primo piano e con la finestra attiva.

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
