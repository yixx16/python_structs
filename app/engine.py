"""Motor de grafos y algoritmos de caminos minimos.

Carga el grafo horneado (data/graph.json) en estructuras de Python puro y
ejecuta Dijkstra y A* grabando el ORDEN de exploracion, para que el frontend
pueda animar la busqueda paso a paso sobre el mapa.

Sin dependencias de osmnx / networkx / shapely.
"""
from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass
from pathlib import Path

EARTH_RADIUS_M = 6_371_000.0


def haversine(lon1, lat1, lon2, lat2):
    """Distancia en metros entre dos puntos (lon/lat en grados)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass
class RouteResult:
    found: bool
    algorithm: str
    explored: list   # polilineas [[lat,lon],...] en orden de exploracion
    path: list       # polilineas [[lat,lon],...] de origen a destino
    iterations: int  # nodos extraidos de la cola de prioridad
    distance_km: float
    time_min: float

    def to_dict(self):
        return {
            "found": self.found,
            "stats": {
                "algorithm": self.algorithm,
                "iterations": self.iterations,
                "explored": len(self.explored),
                "path_edges": len(self.path),
                "distance_km": round(self.distance_km, 3),
                "time_min": round(self.time_min, 2),
            },
            "explored": self.explored,
            "path": self.path,
        }


class Graph:
    """Grafo dirigido en memoria con listas de adyacencia."""

    def __init__(self, baked: dict):
        self.place = baked["place"]
        self.center = baked["center"]
        self.bounds = baked["bounds"]

        # nodos: id(int) -> (lon, lat)
        self.coord = {int(n): (xy[0], xy[1]) for n, xy in baked["nodes"].items()}
        self.node_ids = list(self.coord.keys())

        # aristas: indices paralelos para acceso rapido
        self._poly = []     # polilinea [[lat,lon],...] (orden de Leaflet)
        self._length = []   # metros
        self._weight = []   # segundos de viaje (length / velocidad)
        self.adj = {n: [] for n in self.coord}  # u -> [(v, edge_idx), ...]

        max_speed_kmh = 1
        for u, v, length, maxspeed, coords in baked["edges"]:
            u, v = int(u), int(v)
            if u not in self.coord or v not in self.coord:
                continue
            if coords is None:
                lon_u, lat_u = self.coord[u]
                lon_v, lat_v = self.coord[v]
                poly = [[lat_u, lon_u], [lat_v, lon_v]]
            else:
                poly = [[lat, lon] for lon, lat in coords]
            speed_mps = max(maxspeed, 1) / 3.6
            idx = len(self._poly)
            self._poly.append(poly)
            self._length.append(float(length))
            self._weight.append(float(length) / speed_mps)
            self.adj[u].append((v, idx))
            max_speed_kmh = max(max_speed_kmh, maxspeed)

        # cota superior de velocidad -> heuristica admisible para A*
        self._max_speed_mps = max_speed_kmh / 3.6

    @classmethod
    def load(cls, path: str | Path) -> "Graph":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    # ------------------------------------------------------------------ utils
    def nearest_node(self, lon: float, lat: float) -> int:
        """Nodo mas cercano a un punto (busqueda lineal sobre ~10k nodos)."""
        best, best_d = None, float("inf")
        for n, (nlon, nlat) in self.coord.items():
            d = (nlon - lon) ** 2 + (nlat - lat) ** 2
            if d < best_d:
                best, best_d = n, d
        return best

    def node_latlon(self, node: int):
        lon, lat = self.coord[node]
        return [lat, lon]

    def _reconstruct(self, prev_edge, prev_node, orig, dest):
        """Reconstruye la ruta origen->destino con sus metricas."""
        path_polys, dist, time = [], 0.0, 0.0
        cur = dest
        while cur != orig and cur in prev_node:
            e = prev_edge[cur]
            path_polys.append(self._poly[e])
            dist += self._length[e]
            time += self._weight[e]
            cur = prev_node[cur]
        path_polys.reverse()
        return path_polys, dist / 1000.0, time / 60.0

    # -------------------------------------------------------------- algoritmos
    def dijkstra(self, orig: int, dest: int) -> RouteResult:
        dist = {orig: 0.0}
        prev_node, prev_edge = {}, {}
        visited = set()
        explored = []
        pq = [(0.0, orig)]
        iters = 0

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            iters += 1
            if u != orig and u in prev_edge:
                explored.append(self._poly[prev_edge[u]])
            if u == dest:
                break
            for v, e in self.adj[u]:
                nd = d + self._weight[e]
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev_node[v] = u
                    prev_edge[v] = e
                    heapq.heappush(pq, (nd, v))

        return self._finish("dijkstra", orig, dest, visited, explored,
                            prev_edge, prev_node, iters)

    def a_star(self, orig: int, dest: int) -> RouteResult:
        dlon, dlat = self.coord[dest]

        def h(node):
            lon, lat = self.coord[node]
            return haversine(lon, lat, dlon, dlat) / self._max_speed_mps

        g = {orig: 0.0}
        prev_node, prev_edge = {}, {}
        visited = set()
        explored = []
        pq = [(h(orig), orig)]
        iters = 0

        while pq:
            _, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            iters += 1
            if u != orig and u in prev_edge:
                explored.append(self._poly[prev_edge[u]])
            if u == dest:
                break
            for v, e in self.adj[u]:
                tentative = g[u] + self._weight[e]
                if tentative < g.get(v, float("inf")):
                    g[v] = tentative
                    prev_node[v] = u
                    prev_edge[v] = e
                    heapq.heappush(pq, (tentative + h(v), v))

        return self._finish("a_star", orig, dest, visited, explored,
                            prev_edge, prev_node, iters)

    def _finish(self, algo, orig, dest, visited, explored, prev_edge,
                prev_node, iters):
        found = dest in visited
        if found:
            path, dist_km, time_min = self._reconstruct(prev_edge, prev_node,
                                                         orig, dest)
        else:
            path, dist_km, time_min = [], 0.0, 0.0
        return RouteResult(found, algo, explored, path, iters, dist_km, time_min)

    def route(self, orig: int, dest: int, algorithm: str) -> RouteResult:
        if algorithm == "a_star":
            return self.a_star(orig, dest)
        return self.dijkstra(orig, dest)
