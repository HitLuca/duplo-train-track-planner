# Trenino Duplo · Costruttore di percorsi

Web app che, dati i pezzi che hai (binari Duplo "Optimized" stampati in 3D), trova il percorso chiuso più lungo e tante varianti.
Pezzi e percorsi salvati restano in un database SQLite.

## Avvio con Docker

```bash
docker compose up -d --build
```

Poi apri http://localhost:8080

- Il database sta nel volume Docker `trenino-data` (file `/data/trenino.db` nel container), quindi sopravvive a riavvii e ricostruzioni.
- Per fermare: `docker compose down` (i dati restano). Per cancellare anche i dati: `docker compose down -v`.
- Backup del database: `docker cp trenino:/data/trenino.db ./backup.db`

## Avvio senza Docker

```bash
python3 server.py
```

Il database finisce in `data/trenino.db`. Serve solo Python 3, nessuna libreria da installare. Il server è necessario: la pagina da sola non calcola più nulla.

## Struttura

Il frontend mostra soltanto: tutta l'elaborazione avviene nel backend Python.

- `backend/pieces.py`: catalogo dei pezzi (misure, etichette, colori) e costanti angolari
- `backend/geometry.py`: percorso dei pezzi, verifica di chiusura/ponti/incroci/collisioni, ingombro
- `backend/generate.py`: generatori di percorsi chiusi (anelli, otto) e mosse per allungarli
- `backend/search.py`: ricerca a tempo, in parallelo su più processi, e scelta dei percorsi da mostrare
- `backend/render.py`: dati pronti da disegnare (forme dei pezzi già in coordinate SVG, numeri, istruzioni di montaggio, percorso del treno)
- `backend/db.py`: SQLite (inventario, spazio, percorsi salvati)
- `server.py`: serve `app/` e l'API JSON
- `app/`: `index.html`, `style.css`, `app.js` — chiede i dati all'API e li trasforma in SVG

## API

| Metodo | Percorso | Cosa fa |
|---|---|---|
| GET | `/api/catalog` | pezzi, gruppi, colori e icone |
| GET/PUT | `/api/inventory` | pezzi posseduti e spazio disponibile |
| POST | `/api/search` | avvia una ricerca (`inv`, `room`, `depth`: fast/normal/deep, `previous` per "Cerca ancora") |
| GET | `/api/search/{id}` | avanzamento; a fine ricerca le miniature dei percorsi |
| GET | `/api/search/{id}/{i}` | vista completa di un percorso trovato |
| POST | `/api/search/{id}/{i}/save` | salva il percorso con un nome |
| GET | `/api/layouts` | percorsi salvati (miniature) |
| GET/PATCH/DELETE | `/api/layouts/{id}` | vista completa, rinomina, elimina |

## Test

```bash
python3 -m unittest
```
