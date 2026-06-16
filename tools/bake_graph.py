"""Hornea un grafo de OSMnx (.pkl) a un JSON liviano y autocontenido.

El runtime de la app NO depende de osmnx/networkx/shapely: solo lee el JSON
que produce este script. Ejecutar una sola vez (o cuando cambie la ciudad):

    .venv/Scripts/python tools/bake_graph.py grafo_villavo.pkl data/graph.json
"""
import json
import pickle
import sys
from pathlib import Path

DEFAULT_MAXSPEED = 40  # km/h cuando OSM no informa el limite


def clean_maxspeed(raw):
    """OSM entrega maxspeed como lista, str, o None. Normaliza a int (km/h)."""
    if raw is None:
        return DEFAULT_MAXSPEED
    if isinstance(raw, list):
        speeds = []
        for s in raw:
            try:
                speeds.append(int(str(s).split()[0]))
            except (ValueError, IndexError):
                pass
        return min(speeds) if speeds else DEFAULT_MAXSPEED
    try:
        return int(str(raw).split()[0])
    except (ValueError, IndexError):
        return DEFAULT_MAXSPEED


def edge_geometry(data, node_xy, u, v):
    """Devuelve la polilinea [[lon,lat],...] de la arista.

    Usa la geometria de shapely si existe (calles curvas); si no, una recta
    entre los dos nodos.
    """
    geom = data.get("geometry")
    if geom is not None:
        try:
            return [[round(x, 6), round(y, 6)] for x, y in geom.coords]
        except Exception:
            pass
    return [node_xy[u], node_xy[v]]


def main(pkl_path, out_path):
    print(f"Cargando {pkl_path} ...")
    with open(pkl_path, "rb") as f:
        G = pickle.load(f)

    print(f"  {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

    # Nodos: id -> [lon, lat]
    node_xy = {}
    xs, ys = [], []
    for n, d in G.nodes(data=True):
        lon, lat = round(d["x"], 6), round(d["y"], 6)
        node_xy[n] = [lon, lat]
        xs.append(lon)
        ys.append(lat)

    # Aristas: [u, v, length_m, maxspeed_kmh, geometry|null]
    edges = []
    straight = 0
    for u, v, data in G.edges(data=True):
        if u not in node_xy or v not in node_xy:
            continue
        length = round(float(data.get("length", 0.0)), 2)
        maxspeed = clean_maxspeed(data.get("maxspeed"))
        geom = data.get("geometry")
        if geom is not None:
            coords = edge_geometry(data, node_xy, u, v)
        else:
            coords = None  # el runtime reconstruye la recta desde node_xy
            straight += 1
        edges.append([u, v, length, maxspeed, coords])

    center = [round((min(ys) + max(ys)) / 2, 6), round((min(xs) + max(xs)) / 2, 6)]
    bounds = [[min(ys), min(xs)], [max(ys), max(xs)]]  # [[S,W],[N,E]]

    baked = {
        "place": G.graph.get("name", "Villavicencio, Colombia"),
        "crs": G.graph.get("crs", "epsg:4326"),
        "center": center,
        "bounds": bounds,
        "nodes": {str(n): xy for n, xy in node_xy.items()},
        "edges": edges,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(baked, f, separators=(",", ":"))

    size_mb = out.stat().st_size / 1_048_576
    print(f"Listo -> {out}  ({size_mb:.2f} MB)")
    print(f"  aristas rectas (sin geometria): {straight}/{len(edges)}")
    print(f"  centro: {center}")


if __name__ == "__main__":
    pkl = sys.argv[1] if len(sys.argv) > 1 else "grafo_villavo.pkl"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/graph.json"
    main(pkl, out)
