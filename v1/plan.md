# GeoBrain — Piano di sviluppo v1

Versione professionale per specialisti di GeoLite (v0.1). La v0.1 resta intatta in
`../v0.1` e viene usata solo come riferimento per riscrivere il codice dentro `v1/`.

## Decisioni prese (2026-10-08)

- **Stack**: Streamlit + componente custom (Three.js, senza build step). Globi 3D,
  menu tasto destro e layout fisso vivono nel componente.
- **AI**: API esterna OpenAI-compatible. Chiavi inseribili dall'utente nell'app
  (popover «API AI» in topbar, salvate per-account su SQLite) oppure via variabili
  d'ambiente `GEOBRAIN_AI_*` (default Groq). Il Qwen locale di v0.1 è accantonato.
- **Vulcani**: dati eventi sempre da NASA EONET (come v0.1), ma con modelli 3D
  vulcanici rifatti da zero in modo realistico (terreno procedurale, sezioni).
- **Accessi**: autenticazione locale SQLite copiata da v0.1 (hash scrypt, nessuna email).

## Novità rispetto a v0.1

- Tutte le mappe piatte (folium) sostituite da **globi 3D**: un unico componente con
  modalità sismica, vulcani EONET, clima, modello vulcano 3D.
- **Tasto destro ovunque** (terremoti, vulcani, globo, anomalie climatiche)
  → "Chiedi all'AI" con contesto strutturato inviato alla chat.
- **Sismicità**: i terremoti si selezionano con click sul globo o da tendina
  (top-100 per magnitudo); la selezione è evidenziata da un anello pulsante e,
  **scorrendo sotto il globo**, un pannello mostra i minerali del dataset
  plausibili nel terreno di quel sito (ranking per vicinanza dei giacimenti
  noti + fascia di profondità focale, con motivazione per ciascun minerale).
- **Interfaccia**: globo ad altezza viewport (autoHeight), scroll di pagina
  consentito per i contenuti sotto il globo; scroll interno nei pannelli
  fissi (chat, dettagli).
- **Clima**: globo sferico con immagine termica SST NASA GIBS (MUR, aggiornamento
  ogni 2 giorni) + **correnti oceaniche OSCAR animate** su particelle.
- AI con prompt da geologo senior (sismologo/vulcanologo), risposte nella lingua dell'utente.

## Fonti dati (verificate il 2026-10-08)

| Dato | Fonte | Note |
|---|---|---|
| Terremoti | USGS GeoJSON feed | come v0.1 |
| Vulcani | NASA EONET v3 | come v0.1 |
| Globo base | NASA GIBS WMS | BlueMarble_Shaded_Relief + Reference_Features |
| Termica SST | NASA GIBS WMS | GHRSST_L4_MUR_Sea_Surface_Temperature, daily, dato fresco fino al giorno prima |
| Correnti | NASA GIBS WMS + colormaps | OSCAR zonal+meridional, composite 5 giorni; ultimo dato disponibile ~lug 2024 (viene etichettato in UI) |
| Minerali | dataset v0.1 (8 minerali con giacimento noto) | ranking didattico per sito/profondità |
| AI | API OpenAI-compatible | default Groq, modello configurabile; chiavi per-utente su SQLite |

## Architettura

```text
v1/
├── app.py                  # auth gate, topbar (sezioni + lingua + API AI + account),
│                           # selezione terremoti, pannello minerali nel terreno, chat AI
├── requirements.txt
├── .streamlit/config.toml
├── auth/
│   ├── __init__.py
│   ├── auth.py             # copiata da v0.1 (SQLite, scrypt)
│   └── user_settings.py    # impostazioni AI per-utente (tabella user_ai_settings)
├── ai/
│   ├── __init__.py
│   └── chat.py             # client API OpenAI-compatible + prompt esperti IT/EN,
│                           # configurazione runtime (set_ai_config) con priorità sulle env
├── data/
│   ├── __init__.py
│   ├── earthquakes.py      # USGS
│   ├── volcanoes.py        # EONET
│   ├── minerals.py         # dataset didattico + ranking "minerali nel terreno"
│   └── climate.py          # GIBS: texture globo + SST termica + decode OSCAR
├── globe_component/
│   ├── __init__.py         # wrapper Python (declare_component)
│   └── frontend/
│       ├── index.html      # import map, CSS tema scuro
│       ├── main.js         # scene Three.js per modalità + tasto destro + particelle
│       ├── vendor/         # three.module.js, OrbitControls.js, streamlit.js (offline)
│       └── assets/         # texture PNG scaricate a runtime da GIBS
└── tests/test_core.py
```

Contratto del componente: `globe_component.globes(spec: dict, key: str) -> dict | None`
- `spec`: mode, locale, labels, globe.textureUrl, earthquakes[], selectedId,
  volcanoes[], climate{textureUrl, currents[[lat,lon,u,v]...], showCurrents},
  volcanoModel{type, heightKm, baseRadiusKm, craterRadiusKm, showSection, sectionDepth},
  focus{lat,lon}.
- Ritorna eventi: `{"type":"ask_ai","context":{...}}` (tasto destro),
  `{"type":"select","context":{...}}` (click sinistro).
- Il tipo di edificio vulcanico viaggia come codice interno (`stratocone|shield|caldera`);
  le etichette tradotte vivono solo nell'UI (format_func del selectbox).

## Stato lavori

- [x] Scaffold progetto + vendor Three.js/Streamlit offline
- [x] Backend dati (USGS, EONET, GIBS, minerali) + client AI
- [x] Componente frontend (globi 3D, correnti, modelli vulcano, tasto destro)
- [x] app.py: layout fisso, navigazione sezioni, pannello AI
- [x] Test + verifica end-to-end (23 pytest + smoke AppTest su tutte le sezioni)

Aggiornamento 2026-10-09: completata la prima versione funzionante di `app.py`
(auth gate, topbar con 5 sezioni, layout fisso 100vh, pannello dettagli + chat AI
con streaming, gestione eventi ask_ai/select del componente, UI bilingue it/en).
Il componente supporta `spec.autoHeight` per riempire l'altezza disponibile;
`ai/chat.py` gestisce anche il contesto `volcano_model`. Avvio:
`../.venv/bin/python -m streamlit run app.py` (AI opzionale via `GEOBRAIN_AI_*`).

Aggiornamento 2026-10-10:
- Rimossa la sezione «Minerali» (galleria nel componente + ricerca Wikimedia):
  i minerali comparivano solo come galleria; ora vivono nel pannello «Minerali nel
  terreno» sotto il globo sismico.
- Terremoti selezionabili: tendina top-100 + click sul globo, anello di
  evidenza nel componente (`spec.selectedId`), pannello minerali agganciato
  alla selezione (ranking per distanza dai giacimenti noti + profondità focale).
- API key AI inseribili dall'utente: popover «API AI» in topbar, salvate per
  account su SQLite (`auth/user_settings.py`), priorità sulle variabili
  d'ambiente (`ai.chat.set_ai_config`).
- Fix modello vulcano: il selectbox del tipo usava le etichette tradotte come
  valori (in italiano `scudo` non corrispondeva mai al profilo `shield`): ora
  i valori sono codici interni con `format_func` per le etichette.
- Layout: scroll di pagina consentito (il globo resta ad altezza viewport con
  autoHeight, i contenuti sotto — pannello minerali — richiedono lo scroll).

Aggiornamento 2026-10-12 (fix bug da video «scorri sotto per i minerali»):
- Scroll impossibile verso il pannello minerali: `currentFrameHeight()` in
  `main.js` usava `window.parent.scrollY`, sempre 0 perché la pagina Streamlit
  scorre dentro `section.stMain` (overflow auto): a ogni scroll l'iframe
  cresceva e spingeva via i contenuti sotto. Ora la posizione dell'iframe è
  misurata rispetto al contenuto del contenitore di scroll reale.
- Sezione azzerata dagli eventi del componente: il rerun innescato da
  select/ask_ai del globo arriva con `section`/`locale` vuoti (widget il cui
  valore non è mai stato confermato dal client) → «TITLE_NONE» e sparizione di
  controlli e minerali (visibile nel video al cambio da globo). Ora
  `init_state` ripristina valori validi prima che i widget vengano istanziati.
- Pannello minerali ancorato al terremoto (`last_eq`): il click «Dettagli» su
  un minerale non collassa più il pannello sotto il globo.
- Verificato il crash `StreamlitWidgetAlreadyExistsError` del video: la
  selezione da globo viaggia su `pending_eq_select` e viene applicata prima
  dell'istanziazione del selectbox (nessuna scrittura su chiavi di widget
  già istanziati); eventi ripetuti deduplicati con `last_event_token`.

Aggiornamento 2026-10-14 (fix «l'AI non funziona»):
- Causa principale: il modello default Groq `llama-3.3-70b-versatile` è stato
  dismesso dal provider (deprecazione 2026-08-16) → errore HTTP per chiunque
  lasciasse il campo modello vuoto. Nuovo default: `openai/gpt-oss-120b`.
- `ai/chat.py`: mappa `DEPRECATED_MODEL_REPLACEMENTS` — i vecchi id dismessi
  vengono migrati automaticamente al sostituto corrente; `_error_detail()`
  include il messaggio d'errore del provider nei messaggi «HTTP ...».
- `app.py`: fix campi popover «API AI» stantii (valori vecchi visibili dopo
  «Rimuovi chiave» o cambio account): gotcha Streamlit `value=`+`key=` —
  il flag `_ai_inputs_reset` elimina le chiavi dei widget prima che vengano
  istanziati, così vengono ripopolati dalle impostazioni correnti.
- Verifiche: 24 pytest, smoke AppTest, test AppTest dedicato sulla rimozione
  chiave + sessione browser Playwright con mock OpenAI-compatible.

Aggiornamento 2026-10-14 (secondo round, «errore di rete» con chiave Kimi):
- Causa: impostazioni salvate con `base_url=kimi.ai` (sito web, non endpoint
  API, e senza schema) e modello «kimi k3» con spazio → la richiesta non
  partiva nemmeno e cadeva nel messaggio generico di errore di rete.
- `ai/chat.py`: `_normalize_base_url()` con schema https:// implicito, slash
  finali rimossi e alias dei domini più digitati (kimi.ai →
  https://api.moonshot.ai/v1, groq.com, openai.com, openrouter.ai,
  deepseek.com); nomi modello con spazi normalizzati a trattini in
  `ai_model_name()`; il messaggio di errore di rete riporta il motivo reale
  (DNS/SSL/URL invalido) invece del generico «errore di rete».
- Impostazioni dell'utente corrette sul DB: base URL Moonshot e modello
  `kimi-k2.6` (uno dei due disponibili sul suo account). Nota: la chiave
  salvata era valida ma l'account risulta sospeso dal provider per credito
  insufficiente (HTTP 429 con messaggio esplicito, ora mostrato in UI).
- `auth/auth.py`: `delete_account` ora cancella anche la riga
  `user_ai_settings` (prima restava orfana); avviso in
  `save_ai_settings` sul rischio di sovrascrittura con save parziali.
- Terzo round (sempre «errore di rete»/HTTP generici): l'utente aveva
  digitato `console.groq.com` come Base URL (sito della console, non
  endpoint API → 404). La normalizzazione ora riconosce il dominio radice
  di ciascun provider noto (anche via sottodomini senza path) e lo
  rimappa all'endpoint API corretto. Impostazioni utente corrette su Groq
  (`https://api.groq.com/openai/v1` + `openai/gpt-oss-120b`) e verificate
  con chat completion reale: risposta OK.
- Verifiche: 25 pytest + smoke AppTest; prova reale contro Moonshot con la
  chiave dell'utente (GET /models OK, chat completion 429 credito esaurito)
  e contro Groq (chat completion OK).

Aggiornamento 2026-10-16 (sezioni Correnti + Clima e pannello AI allargato):
- La vecchia sezione «Clima» (SST MUR + correnti OSCAR animate) è stata
  rinominata in «Correnti» (chiavi `currents` in SECTIONS/traduzioni/frontend,
  modalità componente `currents`; texture, particelle e chip invariati).
- Nuova sezione «Clima»: globo con le zone colorate per temperatura —
  layer GIBS `MERRA2_2m_Air_Temperature_Monthly` (temperatura aria a 2 m,
  copertura globale terra+oceano). `data/climate.py`: `heat_texture_url()`
  con gestione dell'extent a buchi del layer (TIME -3 mesi, poi -4, poi
  default = ultimo mese disponibile) e controllo PNG non vuoto
  (`_png_has_data`); didascalia con mese del dato + «non in tempo reale».
- Tasto destro «Chiedi all'AI» attivo anche nel nuovo clima: il contesto
  arriva come `kind="climate"` (prompt climatologo già esistente); nella
  sezione correnti il tasto destro sullo sfondo ora manda `kind="currents"`.
- Pannello AI allargato: colonna destra 0.32 → 0.40, area chat 430 → 520 px.
- Frontend: modalità `currents` gestita ovunque come la vecchia `climate`
  (texture, refresh correnti, advezione particelle, chip); overlay `climate`
  con etichetta termica + mese.
- Verifiche: 27 pytest (nuovi: `_first_of_month`, `_png_has_data`) + smoke
  AppTest su tutte le 5 sezioni; texture reale scaricata da GIBS
  (heat_2026-07-01_2048.png, dati verificati).

Aggiornamento 2026-10-16 (secondo round, lettura della mappa termica):
- Perché «tutto arancione/rosso»: la mappa mostra temperature ASSOLUTE con
  scala −53/+37 °C (colormap GIBS del layer in Kelvin 220–310): i 25-30 °C
  normali dei tropici e l'estate boreale (mese disponibile: luglio) cadono
  nella fascia calda della scala. Il riscaldamento globale (+1.2 °C di
  anomalia) NON è visibile su una mappa assoluta — servirebbe una mappa
  delle anomalie.
- Legenda colori nella sezione Clima: `_parse_colormap_legend()` in
  `data/climate.py` (gradiente CSS + estremi °C dal colormap GIBS reale,
  cache 24 h) renderizzata sotto i controlli.
- Fix risposte AI «fuori tema»: il system prompt citava le correnti OSCAR
  come esempio di dato non aggiornato e il modello le inseriva ovunque —
  esempio rimosso (regola resa generica); il ramo `climate` di
  `build_context_messages` ora è separato da `globe` e include mese del
  dato MERRA-2 + avvertenza «temperature assolute, arancione normale nei
  tropici»; il tasto destro nel clima passa `date` (nuovo campo `spec.heat`
  propagato dal frontend).
- Verifiche: 28 pytest (nuovo: `_parse_colormap_legend`) + smoke OK.

## Note aperte (non bloccanti)

- Nome prodotto: GeoLite (app) vs GeoBrain (cartella) — da decidere prima del deploy.
- Correnti OSCAR: GIBS ferma a ~lug 2024; va bene per mostrare le strutture di
  correnti maggiori, data sempre mostrata in UI.
- Dataset minerali: solo 8 minerali con giacimento noto; il ranking «minerali nel
  terreno» è didattico (giacitura tipica + profondità), non una mappatura reale
  del sottosuolo — la UI lo dichiara esplicitamente.
