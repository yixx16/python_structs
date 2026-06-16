"""Geocodificacion con Nominatim (OpenStreetMap) usando solo la stdlib.

Convierte una direccion escrita en texto a coordenadas. Acota la busqueda a
Villavicencio para que "Cra 30" resuelva a la ciudad correcta.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CITY_SUFFIX = ", Villavicencio, Meta, Colombia"
USER_AGENT = "villavo-rutas/1.0 (proyecto-estructuras-de-datos)"


def geocode(address: str, timeout: float = 8.0) -> dict | None:
    """Devuelve {lat, lon, display_name} o None si no se encuentra."""
    address = (address or "").strip()
    if not address:
        return None
    query = address if "villavicencio" in address.lower() else address + CITY_SUFFIX
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "co",
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if not data:
        return None
    top = data[0]
    return {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "display_name": top.get("display_name", query),
    }
