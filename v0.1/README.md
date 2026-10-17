# GeoLite

GeoLite è un atlante Streamlit per esplorare sismicità, minerali, clima e vulcanologia. Include un modello vulcanico 3D didattico e una mappa di eventi vulcanici NASA EONET. Il repository è distribuito con licenza MIT.

## Funzioni

- Feed sismico pubblico USGS quasi in tempo reale con magnitudo, profondità, luogo e coordinate.
- Mappa sismica interattiva con stato dei danni e marker geolocalizzati.
- Modello vulcanico 3D con cratere, strati, condotto, camera magmatica e versante; trascina per ruotare e usa la rotella per zoomare.
- Simulazione qualitativa controllata da forma del vulcano, pressione, gas e viscosità; non è una previsione né una valutazione di pericolo.
- Mappa delle attività vulcaniche aperte e geolocalizzate nel catalogo NASA EONET, con data e link alla fonte.
- Tabella e galleria con immagini autentiche dei minerali da Wikimedia Commons.
- Chat con Qwen 2.5 Coder 0.5B locale, con lingua selezionabile per UI e risposta AI.
- Filtri laterali per periodo e magnitudo minima.
- Dataset didattico di occorrenze minerali con immagini autentiche attribuite a Wikimedia Commons.
- Snapshot climatico tramite Open-Meteo, senza API key.
- Registrazione e accesso con username e password, senza email; gli account sono salvati localmente in SQLite.

## Installazione ed esecuzione

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Apri l'URL mostrato da Streamlit, normalmente `http://localhost:8501`.

Al primo accesso scegli **Registrati**, crea username e password, poi usa **Accedi** da quel momento in avanti. Gli account restano salvati anche dopo il riavvio dell'app. Gli username devono contenere 3-24 lettere, numeri, punti, trattini o underscore; le password 8-128 caratteri. Le password sono memorizzate come hash scrypt con salt univoco, mai in chiaro.

Puoi eliminare il tuo account dalla sezione dedicata nella barra laterale: per confermare servono la password attuale e una conferma esplicita. L'eliminazione rimuove definitivamente l'account dal database.

Non viene raccolta un'email e non c'è recupero email. Se dimentichi la password, puoi registrare un altro username oppure chiedere all'amministratore del server di reimpostare l'account nel database locale.

Per mantenere il database fuori dalla cartella del codice imposta `GEOBRAIN_DB_PATH` su un percorso persistente, ad esempio `/data/geobrain_users.sqlite3`. Il percorso deve trovarsi su un volume persistente del server. Il database e i file SQLite di journal sono esclusi da Git.

Per la chat, l'app usa localmente Qwen 2.5 Coder 0.5B tramite `ai/qwen_local.py`. Il modello viene caricato solo al primo messaggio e i pesi vengono scaricati al primo utilizzo. La vista vulcanologica non carica Qwen.

## Deployment

### Cloudflare

**Obiettivo V0.1:** eseguire GeoLite come container Docker Linux dietro un Cloudflare Worker con Cloudflare Containers (richiede il piano Workers Paid). Il Worker deve inoltrare richieste HTTP e WebSocket di Streamlit alla porta `8501`; Pages statico o un Worker Python semplice non sostituiscono il container.

Prima del deploy pubblico:

- Migrare gli account dal file SQLite locale a storage persistente Cloudflare (per esempio D1 o SQLite nel Durable Object). Il disco del container è effimero e viene ricreato quando l'istanza dorme o riparte: il database attuale non può restare sul filesystem del container.
- Rendere disponibili i pesi Qwen durante i cold start. Il modello da 0.5B può essere verificato su un container `standard-3` (2 vCPU, 8 GiB RAM); il piano offre anche istanze superiori. Misurare RAM e latenza reali prima di pubblicare.
- Provare login, WebSocket, cold start, persistenza account e richieste concorrenti sul deployment di staging.

Cloudflare Containers può ospitare l'immagine Docker di Streamlit e inoltrare WebSocket tramite il metodo `fetch()` del Container. Il disco locale del container non è persistente; gli account devono essere migrati prima di usare Cloudflare come hosting V0.1.

### Docker o VM

Installa le dipendenze in un virtualenv, configura le variabili d'ambiente e avvia `streamlit run app.py --server.address 0.0.0.0`.

## Modello di licensing

- `LICENSE`: MIT per il programma unificato.
- Le immagini dei minerali sono URL di anteprima Wikimedia Commons: prima di un deployment pubblico verifica attribuzione e licenza della singola immagine.
- Il nome e il marchio GeoLite possono essere protetti separatamente dal copyright del codice.

È perfettamente valido offrire una versione open source gratuita e una versione commerciale closed source: la condizione importante è mantenere separati i codici e rispettare le licenze dei dati e delle dipendenze.

## Struttura

```text
app.py
maps/       trasformazione dati per st.map()
data/       client API USGS/Open-Meteo e dataset minerali
auth/       autenticazione locale SQLite
ai/         adapter Qwen locale
tests/      test del percorso base
```
