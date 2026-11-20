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

Il database finisce in `data/trenino.db`. Serve solo Python 3, nessuna libreria da installare.

## Struttura

- `app/index.html`: tutta l'interfaccia, con la geometria dei pezzi e la ricerca dei percorsi (gira nel browser, in un Web Worker)
- `server.py`: serve la pagina e una piccola API JSON (`/api/inventory`, `/api/layouts`) su SQLite
