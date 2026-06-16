# Villavo · Rutas

Visualizador web de **algoritmos de caminos mínimos** (Dijkstra y A\*) sobre la
malla vial real de Villavicencio, Colombia. La búsqueda se **anima paso a paso**
sobre un mapa interactivo: las calles exploradas se encienden en ámbar y la ruta
óptima se traza en cian.

> Reconstrucción del proyecto de Estructuras de Datos. Se conservó el **núcleo
> algorítmico** (Dijkstra / A\*) y se reemplazó la antigua interfaz de Tkinter por
> una interfaz web profesional con FastAPI + Leaflet.

## Arquitectura

```
grafo_villavo.pkl ──(una vez)──▶ data/graph.json ──▶ app/engine.py ──▶ app/server.py ──▶ web/
   (OSMnx 1.9.3)   tools/bake_graph.py   (liviano)    (Dijkstra/A*)       (FastAPI)      (Leaflet)
```

- **`app/engine.py`** — grafo en memoria (Python puro) + Dijkstra y A\* que graban
  el orden de exploración para poder animarlo. Sin osmnx/networkx en runtime.
- **`app/geocode.py`** — direcciones → coordenadas vía Nominatim (solo stdlib).
- **`app/server.py`** — API REST (FastAPI) y servidor de los estáticos.
- **`web/`** — interfaz: Leaflet + un renderer de canvas propio que anima miles
  de segmentos sin trabarse.
- **`tools/bake_graph.py`** — convierte el `.pkl` de OSMnx a `data/graph.json`.

## Puesta en marcha

```powershell
# 1. Entorno virtual + dependencias de runtime
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

# 2. (Solo si no existe data/graph.json) hornear el grafo
.\.venv\Scripts\python -m pip install -r tools/requirements-bake.txt
.\.venv\Scripts\python tools/bake_graph.py grafo_villavo.pkl data/graph.json

# 3. Arrancar
./run.ps1
```

Abre <http://localhost:8000>.

## Uso

1. Marca **origen** y **destino** con clic en el mapa (o escribe una dirección).
2. Elige el algoritmo: **Dijkstra** o **A\***.
3. Ajusta la velocidad y pulsa **Trazar ruta**.

El panel muestra distancia, tiempo estimado y cuántos nodos exploró cada
algoritmo — Dijkstra siempre explora más; A\*, guiado por su heurística, llega a
la **misma ruta óptima** visitando menos.

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET`  | `/api/meta` | centro, límites y tamaño del grafo |
| `GET`  | `/api/geocode?q=` | dirección → coordenadas + nodo más cercano |
| `GET`  | `/api/nearest?lat=&lon=` | nodo más cercano a un punto |
| `POST` | `/api/route` | `{origin, dest, algorithm}` → exploración + ruta |
