"""Servidor FastAPI: expone el motor de grafos y sirve el frontend web."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.engine import Graph
from app.geocode import geocode

ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = ROOT / "data" / "graph.json"
WEB_DIR = ROOT / "web"

app = FastAPI(title="Villavo Rutas", version="1.0")

# El grafo se carga una sola vez al arrancar (~0.1s, ~10k nodos).
graph = Graph.load(GRAPH_PATH)


class Point(BaseModel):
    lat: float
    lon: float


class RouteRequest(BaseModel):
    origin: Point
    dest: Point
    algorithm: str = "dijkstra"


def _snap(p: Point) -> dict:
    node = graph.nearest_node(p.lon, p.lat)
    return {"node": node, "snapped": graph.node_latlon(node)}


@app.get("/api/meta")
def meta():
    return {
        "place": graph.place,
        "center": graph.center,
        "bounds": graph.bounds,
        "nodes": len(graph.coord),
        "edges": len(graph._poly),
    }


@app.get("/api/geocode")
def api_geocode(q: str = Query(..., min_length=1)):
    hit = geocode(q)
    if not hit:
        raise HTTPException(404, detail="Direccion no encontrada")
    node = graph.nearest_node(hit["lon"], hit["lat"])
    return {
        "lat": hit["lat"],
        "lon": hit["lon"],
        "display_name": hit["display_name"],
        "node": node,
        "snapped": graph.node_latlon(node),
    }


@app.get("/api/nearest")
def api_nearest(lat: float, lon: float):
    node = graph.nearest_node(lon, lat)
    return {"node": node, "snapped": graph.node_latlon(node)}


@app.post("/api/route")
def api_route(req: RouteRequest):
    if req.algorithm not in ("dijkstra", "a_star"):
        raise HTTPException(400, detail="algorithm debe ser 'dijkstra' o 'a_star'")
    origin = _snap(req.origin)
    dest = _snap(req.dest)
    result = graph.route(origin["node"], dest["node"], req.algorithm)
    payload = result.to_dict()
    payload["origin"] = origin
    payload["dest"] = dest
    return payload


# Frontend ------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
