#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
# ================================================================================
# SECCION 1: METADATOS Y CONFIGURACION INICIAL
# ================================================================================
"""
PARTE 9/9 - ENRUTAMIENTO GPS + NETWORK MONITOR (INTEGRADO CON NUCLEO)
=====================================================================
Sistema de enrutamiento GPS en tiempo real y monitoreo de red.
Exporta estado para ser consumido por el nucleo principal (CEOIA).
Integrado con SharedDataRegistry (Parte 1), Dashboard HTML (Parte 8)
y modulos de inteligencia (Partes 2, 3, 4).
CORREGIDO para Termux: hilos robustos, sin zombies, ping nativo, lock de red.
"""

from __future__ import annotations
import math
import heapq
import random
import uuid
import time
import json
import sys
import os
import subprocess
import threading
import socket
import copy
import hashlib
import traceback
from typing import Dict, List, Optional, Tuple, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from collections import deque, defaultdict
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# ================================================================================
# SECCION 2: IMPORTACION DE PARTE 1 (REGISTRY Y CONFIG) CON FALLBACK
# ================================================================================
try:
    from part1_config import (
        GlobalConfig, log_event, log_banner, SharedDataRegistry
    )
    _PART1_AVAILABLE = True
except ImportError:
    _PART1_AVAILABLE = False

    class GlobalConfig:
        IS_TERMUX = True
        LOG_VERBOSE = True

    def log_event(msg: str, level: str = "INFO") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        print("[{}][{}] {}".format(ts, level, msg))

    def log_banner(msg: str, emoji: str = "") -> None:
        print("=" * 60)
        print("{} {}".format(emoji, msg))
        print("=" * 60)

    class SharedDataRegistry:
        """Fallback minimalista si Parte 1 no esta disponible."""
        _instance = None
        _lock = threading.RLock()

        def __new__(cls):
            if cls._instance is None:
                with cls._lock:
                    if cls._instance is None:
                        cls._instance = super(SharedDataRegistry, cls).__new__(cls)
                        cls._instance._initialized = False
            return cls._instance

        def __init__(self):
            if self._initialized: return
            with self._lock:
                if self._initialized: return
                self._data = {}
                self._callbacks = defaultdict(list)
                self._initialized = True

        def set(self, key, value, notify=True):
            with self._lock:
                self._data[key] = copy.deepcopy(value)
                if notify:
                    for pattern, cbs in self._callbacks.items():
                        if self._match(pattern, key):
                            for cb_id, cb in cbs:
                                try: cb(key, value)
                                except Exception: pass

        def get(self, key, default=None):
            with self._lock:
                return copy.deepcopy(self._data.get(key, default))

        def get_all(self, pattern=None):
            with self._lock:
                if pattern is None:
                    return {k: copy.deepcopy(v) for k, v in self._data.items()}
                return {k: copy.deepcopy(v) for k, v in self._data.items() if self._match(pattern, k)}

        def on_change(self, key_pattern, callback):
            with self._lock:
                cb_id = str(hash(callback))[:8]
                self._callbacks[key_pattern].append((cb_id, callback))
                return cb_id

        def _match(self, pattern, key):
            import fnmatch
            return fnmatch.fnmatch(key, pattern)


# ================================================================================
# SECCION 3: BANDERA DE APAGADO Y FUNCIONES DE ANALISIS PRINCIPAL
# ================================================================================
_network_monitor_shutdown = threading.Event()
_registry_sync_shutdown = threading.Event()

def stop_network_monitor():
    """Llama a esta funcion desde el orquestador al cerrar el sistema."""
    global _network_monitor_shutdown, _registry_sync_shutdown
    log_event("Deteniendo monitores de red y sync...", "NET")
    _network_monitor_shutdown.set()
    _registry_sync_shutdown.set()

def analizar_prompt_mejor_opcion(prompt: str, contexto: dict) -> dict:
    """Procesa el prompt con el monitor de red y enrutamiento, integrando Parts 2, 3, 4."""
    # --- BLOQUE: RECOLECCION DE CONTEXTO EXTERNO ---
    registry = SharedDataRegistry()
    radar_data = registry.get("radar:best_opportunity")
    prediction_data = registry.get("predictor:prediction:latest")
    negotiation_data = registry.get("negotiation:latest_result")
    
    # --- BLOQUE: ESTADO DE RED ACTUAL ---
    net_status = "SATURADO"
    latencia = 999.0
    with network_lock:
        net_status = network_state.get("status", "DESCONOCIDO")
        latencia = network_state.get("latency", 999.0)

    # --- BLOQUE: DECISION DE RUTA ---
    server_opt = "api.uber.com"
    with network_lock:
        server_opt = network_state.get("current", "api.uber.com")

    destino_recomendado = contexto.get("destino", "multiplaza")
    if radar_data and radar_data.get("demand_score", 0) > 7.0:
        destino_recomendado = radar_data.get("zone_id", destino_recomendado)
    elif prediction_data and prediction_data.get("demand_score", 0) > 7.5:
        destino_recomendado = prediction_data.get("cell", destino_recomendado)

    return {
        "exito": True,
        "estado_red": net_status,
        "latencia_promedio_ms": latencia,
        "servidor_optimo": server_opt,
        "destino_recomendado_ruta": destino_recomendado,
        "influencia_radar": radar_data is not None,
        "influencia_prediccion": prediction_data is not None,
        "timestamp_procesamiento": time.time()
    }


# ================================================================================
# SECCION 4: CONFIGURACION DE ENTORNO TERMUX
# ================================================================================
if hasattr(sys, 'setdefaultencoding'):
    sys.setdefaultencoding('utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

DEBUG = False
AUTO_MODE = True
IS_TERMUX = os.getenv('TERMUX_VERSION') is not None or 'com.termux' in os.getenv('PATH', '')

def log(msg: str, level: str = "INFO"):
    """Funcion de logging unificada."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = "[{}] [{}] {}".format(ts, level, msg)
    print(line, flush=True)
    try:
        log_dir = os.path.expanduser("~/x/logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "symbiosis_unified.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ================================================================================
# SECCION 5: ENUMS Y ESTRUCTURAS DE ENRUTAMIENTO
# ================================================================================
class RoutingAlgorithm(Enum):
    DIJKSTRA = auto()
    A_STAR = auto()
    BELLMAN_FORD = auto()
    FLOYD_WARSHALL = auto()
    GREEDY_BEST_FIRST = auto()
    BIDIRECTIONAL = auto()
    LIVE_TRAFFIC = auto()
    JOHNSON = auto()

class TrafficCondition(Enum):
    FREE = 1.0
    NORMAL = 0.7
    MODERATE = 0.5
    HEAVY = 0.3
    BLOCKED = 0.1

class OptimizationObjective(Enum):
    DISTANCE = "distance"
    TIME = "time"
    COST = "cost"
    BALANCED = "balanced"

@dataclass
class Coordinate:
    latitude: float
    longitude: float
    def distance_to(self, other: 'Coordinate') -> float:
        R = 6371.0
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

@dataclass
class Node:
    node_id: str
    coordinate: Coordinate
    name: str = ""
    node_type: str = "intersection"
    elevation: float = 0.0

@dataclass
class Edge:
    edge_id: str
    from_node: str
    to_node: str
    distance: float
    base_time: float
    speed_limit: float
    road_type: str = "local"
    toll_cost: float = 0.0
    traffic_multiplier: float = 1.0

@dataclass
class TrafficEvent:
    event_id: str
    edge_id: str
    condition: TrafficCondition
    start_time: datetime
    end_time: Optional[datetime] = None
    description: str = ""
    delay_minutes: float = 0.0

@dataclass
class Route:
    route_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    origin: Optional[Coordinate] = None
    destination: Optional[Coordinate] = None
    origin_node: Optional[str] = None
    destination_node: Optional[str] = None
    nodes: List[str] = field(default_factory=list)
    edges: List[str] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_time_minutes: float = 0.0
    total_cost: float = 0.0
    algorithm_used: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    waypoints: List[Coordinate] = field(default_factory=list)
    instructions: List[Dict[str, Any]] = field(default_factory=list)
    alternatives: List['Route'] = field(default_factory=list)
    
    def to_geojson(self) -> Dict[str, Any]:
        if not self.waypoints:
            return {"type": "FeatureCollection", "features": []}
        coords = [[wp.longitude, wp.latitude] for wp in self.waypoints]
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "route_id": self.route_id,
                    "distance_km": self.total_distance_km,
                    "time_min": self.total_time_minutes,
                    "cost": self.total_cost,
                    "algorithm": self.algorithm_used
                },
                "geometry": {"type": "LineString", "coordinates": coords}
            }]
        }


# ================================================================================
# SECCION 6: GPS EN TIEMPO REAL PARA TERMUX
# ================================================================================
class TermuxGPS:
    def __init__(self):
        self.last_location: Optional[Coordinate] = None
        self.last_update: Optional[datetime] = None
        self.is_available = self._check_termux_api()
        self.location_history: List[Coordinate] = []
        self.max_history = 100
    
    def _check_termux_api(self) -> bool:
        # --- BLOQUE: VERIFICACION ---
        try:
            result = subprocess.run(['which', 'termux-location'], 
                                  capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except Exception:
            return False
    
    def get_current_location(self) -> Optional[Coordinate]:
        # --- BLOQUE: LECTURA REAL ---
        if not self.is_available:
            return self._get_simulated_location()
        try:
            result = subprocess.run(
                ['termux-location', '-p', 'gps'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                lat, lon = data.get('latitude'), data.get('longitude')
                if lat and lon:
                    coord = Coordinate(latitude=lat, longitude=lon)
                    self.last_location = coord
                    self.last_update = datetime.now()
                    self.location_history.append(coord)
                    if len(self.location_history) > self.max_history:
                        self.location_history.pop(0)
                    return coord
        except Exception:
            pass
        return self._get_simulated_location()
    
    def _get_simulated_location(self) -> Coordinate:
        # --- BLOQUE: SIMULACION ---
        locations = [
            (9.0285, -79.5325), (9.0392, -79.5189), (9.0381, -79.4798),
            (9.0167, -79.5167), (8.9736, -79.5528), (8.9518, -79.6534)
        ]
        idx = int(time.time() / 60) % len(locations)
        return Coordinate(latitude=locations[idx][0], longitude=locations[idx][1])
    
    def get_speed_kmh(self) -> float:
        if len(self.location_history) < 2:
            return 0.0
        last = self.location_history[-1]
        prev = self.location_history[-2]
        dist = last.distance_to(prev)
        time_diff = 5
        if time_diff > 0:
            return (dist / time_diff) * 3600
        return 0.0


# ================================================================================
# SECCION 7: PUNTOS DE INTERES EN PANAMA
# ================================================================================
PANAMA_LOCATIONS = {
    "costa_verde": {"name": "Costa Verde", "lat": 9.0285, "lon": -79.5325, "type": "shopping"},
    "westland_mall": {"name": "Westland Mall", "lat": 9.0392, "lon": -79.5189, "type": "shopping"},
    "albrook_mall": {"name": "Albrook Mall", "lat": 8.9736, "lon": -79.5528, "type": "shopping"},
    "tocumen_airport": {"name": "Tocumen Airport", "lat": 9.0714, "lon": -79.3835, "type": "airport"},
    "panama_pacifico": {"name": "Panama Pacifico", "lat": 8.9148, "lon": -79.5996, "type": "airport"},
    "arraijan_tc": {"name": "Arraijan Town Center", "lat": 8.9518, "lon": -79.6534, "type": "shopping"},
    "multiplaza": {"name": "Multiplaza Pacifica", "lat": 9.0381, "lon": -79.4798, "type": "shopping"},
    "metromall": {"name": "Metromall", "lat": 9.0742, "lon": -79.4259, "type": "shopping"}
}


# ================================================================================
# SECCION 8: GRAFO DE RUTAS (RED VIAL DE PANAMA)
# ================================================================================
class RouteGraph:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self.adjacency: Dict[str, List[str]] = defaultdict(list)
        self.reverse_adjacency: Dict[str, List[str]] = defaultdict(list)
        self._spatial_index: Dict[str, List[str]] = defaultdict(list)
        self._grid_size = 0.5
    
    def add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node
        cell = self._get_spatial_cell(node.coordinate)
        self._spatial_index[cell].append(node.node_id)
    
    def add_edge(self, edge: Edge, bidirectional: bool = True) -> None:
        self.edges[edge.edge_id] = edge
        self.adjacency[edge.from_node].append(edge.edge_id)
        self.reverse_adjacency[edge.to_node].append(edge.edge_id)
        if bidirectional:
            rev = Edge(
                edge_id="{}_rev".format(edge.edge_id),
                from_node=edge.to_node, to_node=edge.from_node,
                distance=edge.distance, base_time=edge.base_time,
                speed_limit=edge.speed_limit, road_type=edge.road_type,
                toll_cost=edge.toll_cost, traffic_multiplier=edge.traffic_multiplier
            )
            self.edges[rev.edge_id] = rev
            self.adjacency[rev.from_node].append(rev.edge_id)
            self.reverse_adjacency[rev.to_node].append(rev.edge_id)
    
    def _get_spatial_cell(self, coord: Coordinate) -> str:
        lat_cell = int(coord.latitude / self._grid_size)
        lon_cell = int(coord.longitude / self._grid_size)
        return "{},{}".format(lat_cell, lon_cell)
    
    def get_nearby_nodes(self, coord: Coordinate, radius_km: float = 5.0) -> List[Tuple[str, float]]:
        # --- BLOQUE: BUSQUEDA ESPACIAL ---
        candidates = set()
        cell_radius = int(radius_km / (self._grid_size * 111)) + 1
        center_cell = self._get_spatial_cell(coord)
        lat0, lon0 = map(int, center_cell.split(','))
        for dlat in range(-cell_radius, cell_radius + 1):
            for dlon in range(-cell_radius, cell_radius + 1):
                cell = "{},{}".format(lat0 + dlat, lon0 + dlon)
                candidates.update(self._spatial_index.get(cell, []))
        nearby = []
        for node_id in candidates:
            node = self.nodes[node_id]
            dist = coord.distance_to(node.coordinate)
            if dist <= radius_km:
                nearby.append((node_id, dist))
        return sorted(nearby, key=lambda x: x[1])
    
    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)
    
    def get_edge(self, edge_id: str) -> Optional[Edge]:
        return self.edges.get(edge_id)
    
    def get_outgoing_edges(self, node_id: str) -> List[Edge]:
        return [self.edges[eid] for eid in self.adjacency.get(node_id, []) if eid in self.edges]
    
    def get_incoming_edges(self, node_id: str) -> List[Edge]:
        return [self.edges[eid] for eid in self.reverse_adjacency.get(node_id, []) if eid in self.edges]

def generate_panama_network() -> RouteGraph:
    # --- BLOQUE: GENERACION DE NODOS ---
    graph = RouteGraph()
    for loc_id, loc_data in PANAMA_LOCATIONS.items():
        node = Node(
            node_id=loc_id,
            coordinate=Coordinate(latitude=loc_data["lat"], longitude=loc_data["lon"]),
            name=loc_data["name"], node_type=loc_data["type"]
        )
        graph.add_node(node)
    intermediate = [
        ("via_espana", "Via Espana", 8.9833, -79.5333),
        ("transistmica", "Transistmica", 9.0167, -79.5167),
        ("corredor_norte", "Corredor Norte", 9.0500, -79.4500),
        ("corredor_sur", "Corredor Sur", 9.0000, -79.5167),
        ("centenario", "Puente Centenario", 9.0333, -79.6500),
        ("americas", "Puente de las Americas", 8.9500, -79.5667),
        ("via_porras", "Via Porras", 8.9833, -79.5167),
        ("tumba_muerto", "Tumba Muerto", 9.0333, -79.5000),
        ("via_brasil", "Via Brasil", 9.0500, -79.4833),
        ("cinquetenario", "Cincuentenario", 9.0667, -79.4167)
    ]
    for nid, name, lat, lon in intermediate:
        node = Node(node_id=nid, coordinate=Coordinate(latitude=lat, longitude=lon), name=name)
        graph.add_node(node)
    # --- BLOQUE: GENERACION DE ARISTAS ---
    conns = [
        ("costa_verde", "westland_mall", 2.1, 40, "local", 0),
        ("costa_verde", "via_espana", 5.5, 50, "arterial", 0),
        ("westland_mall", "transistmica", 3.8, 50, "arterial", 0),
        ("westland_mall", "tumba_muerto", 4.2, 60, "arterial", 0),
        ("albrook_mall", "americas", 2.5, 50, "arterial", 0),
        ("albrook_mall", "corredor_sur", 3.0, 70, "highway", 1.5),
        ("albrook_mall", "centenario", 8.5, 80, "highway", 2.0),
        ("tocumen_airport", "corredor_norte", 5.0, 90, "highway", 2.5),
        ("tocumen_airport", "cinquetenario", 3.5, 60, "arterial", 0),
        ("tocumen_airport", "via_brasil", 12.0, 80, "highway", 2.0),
        ("panama_pacifico", "centenario", 12.0, 80, "highway", 2.5),
        ("panama_pacifico", "arraijan_tc", 8.0, 60, "arterial", 0),
        ("arraijan_tc", "centenario", 6.0, 70, "highway", 1.5),
        ("arraijan_tc", "americas", 10.0, 60, "arterial", 0),
        ("multiplaza", "via_brasil", 2.0, 50, "arterial", 0),
        ("multiplaza", "tumba_muerto", 3.5, 60, "arterial", 0),
        ("multiplaza", "corredor_norte", 4.0, 70, "highway", 1.0),
        ("metromall", "cinquetenario", 3.0, 50, "arterial", 0),
        ("metromall", "corredor_norte", 4.5, 70, "highway", 1.5),
        ("via_espana", "via_porras", 1.5, 40, "local", 0),
        ("via_porras", "transistmica", 4.0, 50, "arterial", 0),
        ("transistmica", "tumba_muerto", 3.0, 60, "arterial", 0),
        ("tumba_muerto", "via_brasil", 2.5, 50, "arterial", 0),
        ("via_brasil", "corredor_norte", 3.0, 70, "highway", 1.0),
        ("corredor_norte", "cinquetenario", 5.0, 80, "highway", 1.5),
        ("corredor_sur", "americas", 4.0, 60, "arterial", 0),
        ("americas", "centenario", 5.0, 70, "highway", 1.5),
        ("centenario", "arraijan_tc", 6.0, 70, "highway", 1.5),
        ("costa_verde", "tumba_muerto", 6.0, 50, "arterial", 0),
        ("albrook_mall", "via_espana", 7.0, 50, "arterial", 0),
        ("westland_mall", "corredor_norte", 5.5, 70, "highway", 1.5),
        ("multiplaza", "metromall", 8.0, 60, "arterial", 0),
        ("metromall", "tocumen_airport", 5.0, 70, "highway", 1.0),
        ("panama_pacifico", "albrook_mall", 18.0, 80, "highway", 3.0)
    ]
    for frm, to, dist, spd, rtype, toll in conns:
        if frm in graph.nodes and to in graph.nodes:
            base_time = (dist / spd) * 60
            edge = Edge(
                edge_id="E_{}_{}".format(frm, to), from_node=frm, to_node=to,
                distance=dist, base_time=base_time, speed_limit=spd,
                road_type=rtype, toll_cost=toll
            )
            graph.add_edge(edge, bidirectional=True)
    return graph


# ================================================================================
# SECCION 9: TRAFFIC MANAGER
# ================================================================================
class TrafficManager:
    def __init__(self):
        self.events: Dict[str, TrafficEvent] = {}
        self.condition_history: Dict[str, List[Tuple[datetime, TrafficCondition]]] = defaultdict(list)
    
    def cleanup_expired_events(self) -> None:
        now = datetime.now(timezone.utc)
        to_delete = [eid for eid, ev in self.events.items() if ev.end_time and ev.end_time <= now]
        for eid in to_delete:
            del self.events[eid]
    
    def add_event(self, event: TrafficEvent) -> None:
        self.cleanup_expired_events()
        self.events[event.event_id] = event
        self.condition_history[event.edge_id].append((event.start_time, event.condition))
    
    def remove_event(self, event_id: str) -> None:
        if event_id in self.events:
            event = self.events.pop(event_id)
    
    def get_current_condition(self, edge_id: str) -> TrafficCondition:
        # --- BLOQUE: EVALUACION HORARIA ---
        now = datetime.now(timezone.utc)
        current_hour = (now.hour - 5) % 24
        if 6 <= current_hour <= 9 or 16 <= current_hour <= 19:
            base = TrafficCondition.HEAVY
        elif 11 <= current_hour <= 14:
            base = TrafficCondition.MODERATE
        elif 22 <= current_hour or current_hour <= 5:
            base = TrafficCondition.FREE
        else:
            base = TrafficCondition.NORMAL
        for ev in self.events.values():
            if ev.edge_id == edge_id and (ev.end_time is None or ev.end_time > now):
                if ev.start_time <= now:
                    return ev.condition
        return base
    
    def get_multiplier(self, edge_id: str) -> float:
        return self.get_current_condition(edge_id).value
    
    def simulate_accident(self, edge_id: str, duration_minutes: int = 30) -> TrafficEvent:
        event = TrafficEvent(
            event_id=str(uuid.uuid4())[:8], edge_id=edge_id,
            condition=TrafficCondition.BLOCKED,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=duration_minutes),
            description="Accidente simulado", delay_minutes=duration_minutes
        )
        self.add_event(event)
        return event


# ================================================================================
# SECCION 10: ROUTING ENGINE Y ALGORITMOS
# ================================================================================
class RoutingEngine:
    def __init__(self, graph: RouteGraph, traffic_manager: Optional[TrafficManager] = None):
        self.graph = graph
        self.traffic = traffic_manager or TrafficManager()
        self.cache: Dict[tuple, Route] = {}
        self.cache_max_size = 100
        self.cache_hits = 0
        self.cache_misses = 0
        self.fw_precomputer = None
    
    def _cache_get(self, key: tuple) -> Optional[Route]:
        if key in self.cache:
            self.cache_hits += 1
            return copy.deepcopy(self.cache[key])
        self.cache_misses += 1
        return None
    
    def _cache_set(self, key: tuple, route: Route) -> None:
        if len(self.cache) >= self.cache_max_size:
            first = next(iter(self.cache))
            del self.cache[first]
        self.cache[key] = copy.deepcopy(route)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0
        return {"size": len(self.cache), "hits": self.cache_hits, "misses": self.cache_misses, "hit_rate": hit_rate}
    
    def find_route(self, origin: Coordinate, destination: Coordinate,
                  algorithm: RoutingAlgorithm = RoutingAlgorithm.A_STAR,
                  objective: OptimizationObjective = OptimizationObjective.TIME,
                  avoid_tolls: bool = False, avoid_highways: bool = False,
                  use_cache: bool = True) -> Optional[Route]:
        # --- BLOQUE: RESOLUCION DE NODOS Y CACHE ---
        origin_nodes = self.graph.get_nearby_nodes(origin, radius_km=5.0)
        dest_nodes = self.graph.get_nearby_nodes(destination, radius_km=5.0)
        if not origin_nodes or not dest_nodes:
            return None
        origin_node, dest_node = origin_nodes[0][0], dest_nodes[0][0]
        cache_key = (origin_node, dest_node, algorithm.name, objective.name, avoid_tolls, avoid_highways)
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached: return cached
        # --- BLOQUE: SELECCION DE ALGORITMO ---
        if algorithm == RoutingAlgorithm.A_STAR:
            path, edges = self._a_star(origin_node, dest_node, destination, objective, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.LIVE_TRAFFIC:
            path, edges = self._dijkstra_with_traffic(origin_node, dest_node, objective, avoid_tolls, avoid_highways)
        else:
            path, edges = self._a_star(origin_node, dest_node, destination, objective, avoid_tolls, avoid_highways)
        
        if not path: return None
        route = self._build_route(path, edges, origin, destination, algorithm.name, objective)
        if use_cache: self._cache_set(cache_key, route)
        return route
    
    def _heuristic(self, node_id: str, target: Coordinate, objective: OptimizationObjective) -> float:
        node = self.graph.nodes.get(node_id)
        if not node: return 0.0
        dist_km = node.coordinate.distance_to(target)
        if objective == OptimizationObjective.TIME: return (dist_km / 50) * 60
        elif objective == OptimizationObjective.COST: return dist_km * 0.15
        return dist_km
    
    def _edge_cost(self, edge: Edge, objective: OptimizationObjective, avoid_tolls: bool, avoid_highways: bool) -> float:
        # --- BLOQUE: FILTROS Y COSTO ---
        if avoid_tolls and edge.toll_cost > 0: return float('inf')
        if avoid_highways and edge.road_type == "highway": return float('inf')
        traffic_mult = self.traffic.get_multiplier(edge.edge_id)
        actual_time = edge.base_time * (2 - traffic_mult)
        penalty = 0.9 if edge.road_type == "highway" else (1.2 if edge.road_type == "residential" else 1.0)
        if objective == OptimizationObjective.DISTANCE: return edge.distance * penalty
        elif objective == OptimizationObjective.TIME: return actual_time * penalty
        elif objective == OptimizationObjective.COST: return edge.toll_cost + (actual_time * 0.02)
        return 0.4 * edge.distance + 0.4 * actual_time + 0.2 * edge.toll_cost

    def _a_star(self, origin: str, dest: str, target: Coordinate, objective: OptimizationObjective, avoid_tolls: bool, avoid_highways: bool):
        # --- BLOQUE: A* SEARCH ---
        open_set = [(0.0, 0, origin)]
        g_score, f_score, came_from, visited = {origin: 0.0}, {origin: self._heuristic(origin, target, objective)}, {}, set()
        counter = 0
        while open_set:
            f, _, current = heapq.heappop(open_set)
            if current == dest: break
            if current in visited: continue
            visited.add(current)
            for edge in self.graph.get_outgoing_edges(current):
                neighbor = edge.to_node
                if neighbor in visited: continue
                cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
                if cost == float('inf'): continue
                tentative_g = g_score.get(current, 0.0) + cost
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, target, objective)
                    came_from[neighbor] = (current, edge.edge_id)
                    counter += 1
                    heapq.heappush(open_set, (f_score[neighbor], counter, neighbor))
        if dest not in came_from and dest != origin: return [], []
        path_nodes, path_edges, cur = [], [], dest
        while cur != origin:
            path_nodes.append(cur)
            prev, eid = came_from.get(cur, (None, None))
            if prev is None: break
            path_edges.append(eid)
            cur = prev
        path_nodes.append(origin)
        path_nodes.reverse()
        path_edges.reverse()
        return path_nodes, path_edges
    
    def _dijkstra(self, *args, **kwargs):
        return self._a_star(*args[:3], *args[3:])
    def _bidirectional(self, *args, **kwargs):
        return self._a_star(*args[:3], *args[3:])
    def _dijkstra_with_traffic(self, *args, **kwargs):
        return self._dijkstra(*args)
    def _bellman_ford(self, *args, **kwargs):
        return self._a_star(*args[:3], *args[3:])
    def _floyd_warshall(self, origin, dest, objective, avoid_tolls, avoid_highways):
        if self.fw_precomputer is None:
            self.fw_precomputer = FloydWarshallPrecomputer(self.graph, objective)
            self.fw_precomputer.compute(avoid_tolls, avoid_highways)
        path_nodes = self.fw_precomputer.get_path(origin, dest)
        if not path_nodes: return [], []
        path_edges = []
        for i in range(len(path_nodes)-1):
            u, v = path_nodes[i], path_nodes[i+1]
            for e in self.graph.get_outgoing_edges(u):
                if e.to_node == v: path_edges.append(e.edge_id); break
        return path_nodes, path_edges
    def _johnson(self, *args, **kwargs):
        return self._dijkstra(*args)
    def _greedy_best_first(self, origin: str, dest: str, target: Coordinate, avoid_tolls: bool, avoid_highways: bool):
        path, visited, current = [origin], set([origin]), origin
        while current != dest:
            best, best_h, best_edge = None, float('inf'), None
            for edge in self.graph.get_outgoing_edges(current):
                neighbor = edge.to_node
                if neighbor in visited: continue
                h = self._heuristic(neighbor, target, OptimizationObjective.DISTANCE)
                if h < best_h: best_h, best, best_edge = h, neighbor, edge.edge_id
            if best is None: break
            path.append(best); visited.add(best); current = best
        if current != dest: return [], []
        edges = [best_edge] if best_edge else []
        return path, edges
    
    def _build_route(self, path_nodes: List[str], path_edges: List[str], origin: Coordinate,
                     destination: Coordinate, algorithm: str, objective: OptimizationObjective) -> Route:
        # --- BLOQUE: CONSTRUCCION DE RUTA ---
        route = Route(origin=origin, destination=destination, origin_node=path_nodes[0], destination_node=path_nodes[-1],
                      nodes=path_nodes, edges=path_edges, algorithm_used=algorithm)
        total_dist, total_time, total_cost, waypoints = 0.0, 0.0, 0.0, [origin]
        for eid in path_edges:
            edge = self.graph.get_edge(eid)
            if edge:
                total_dist += edge.distance
                mult = self.traffic.get_multiplier(eid)
                total_time += edge.base_time * (2 - mult)
                total_cost += edge.toll_cost
                dest_node = self.graph.get_node(edge.to_node)
                if dest_node: waypoints.append(dest_node.coordinate)
        waypoints.append(destination)
        route.total_distance_km, route.total_time_minutes, route.total_cost, route.waypoints = total_dist, total_time, total_cost, waypoints
        return route

class FloydWarshallPrecomputer:
    def __init__(self, graph: RouteGraph, objective: OptimizationObjective):
        self.graph, self.objective = graph, objective
        self.dist = defaultdict(lambda: defaultdict(lambda: float('inf')))
        self.next_node = defaultdict(lambda: defaultdict(lambda: None))
        self.computed = False
    
    def compute(self, avoid_tolls: bool, avoid_highways: bool) -> bool:
        nodes = list(self.graph.nodes.keys())
        if not nodes: return False
        for i in nodes: self.dist[i][i] = 0.0
        for edge in self.graph.edges.values():
            if avoid_tolls and edge.toll_cost > 0: continue
            if avoid_highways and edge.road_type == "highway": continue
            cost = edge.distance if self.objective == OptimizationObjective.DISTANCE else edge.base_time
            if cost < self.dist[edge.from_node][edge.to_node]:
                self.dist[edge.from_node][edge.to_node] = cost
                self.next_node[edge.from_node][edge.to_node] = edge.to_node
        for k in nodes:
            for i in nodes:
                if self.dist[i][k] == float('inf'): continue
                for j in nodes:
                    if self.dist[k][j] == float('inf'): continue
                    nd = self.dist[i][k] + self.dist[k][j]
                    if nd < self.dist[i][j]:
                        self.dist[i][j] = nd
                        self.next_node[i][j] = self.next_node[i][k]
        self.computed = True
        return True
    
    def get_path(self, origin: str, dest: str) -> List[str]:
        if not self.computed or self.dist[origin][dest] == float('inf'): return []
        path = [origin]
        while path[-1] != dest:
            nxt = self.next_node[path[-1]][dest]
            if nxt is None: return []
            path.append(nxt)
        return path


# ================================================================================
# SECCION 11: NETWORK MONITOR (PING, LATENCIA, SELECCION DE SERVIDOR)
# ================================================================================
ping_data = {"google": deque(maxlen=10), "cloudflare": deque(maxlen=10), "uber": deque(maxlen=10)}
network_state = {"current": None, "latency": None, "status": None, "fail_count": 0, "winner": None, "top_servers": [], "last_check": None}
network_lock = threading.Lock()
SERVERS = ["api.uber.com", "tc2.uber.com", "cn-geo1.uber.com", "1.1.1.1", "www.google.com", "cloudflare.com"]
PING_WEIGHT, HTTP_WEIGHT = 0.35, 0.65
THRESHOLD_EXCELLENT, THRESHOLD_STABLE, THRESHOLD_CRITICAL = 0.30, 0.50, 1.0
_has_ping = None
_network_monitor_started = False
_network_monitor_pid = None

def _is_ping_available() -> bool:
    global _has_ping
    if _has_ping is None:
        try:
            subprocess.run(['ping', '-c', '1', '127.0.0.1'], capture_output=True, timeout=1, check=False)
            _has_ping = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _has_ping = False
    return _has_ping

def check_internet(timeout=2.0) -> bool:
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=timeout): return True
    except Exception: pass
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=timeout): return True
    except Exception: return False

def measure_ping(host: str, timeout=1) -> float:
    if not _is_ping_available(): return 1000.0
    try:
        result = subprocess.run(["ping", "-c", "1", "-W", str(timeout), host], capture_output=True, text=True, timeout=timeout+1)
        if result.returncode == 0 and "time=" in result.stdout:
            for p in result.stdout.split():
                if "time=" in p: return float(p.split("=")[1])
    except Exception: pass
    try:
        start = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, 53 if host.replace('.', '').isdigit() else 443))
        return round((time.time() - start) * 1000, 2)
    except Exception: return 1000.0

def measure_http_latency(url: str, timeout=2.0) -> float:
    try:
        import requests
        if not url.startswith(('http://', 'https://')): url = "https://{}".format(url)
        start = time.time()
        requests.get(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "Symbiosis/3.1"})
        return round(time.time() - start, 3)
    except ImportError:
        domain = url.replace('https://', '').replace('http://', '').split('/')[0]
        return measure_ping(domain) / 1000
    except Exception: return 2.0

def calculate_score(ping_ms, http_s):
    return (ping_ms * PING_WEIGHT) + (http_s * 1000 * HTTP_WEIGHT)

def classify_network_state(latency):
    if latency < THRESHOLD_EXCELLENT: return "EXCELENTE"
    elif latency < THRESHOLD_STABLE: return "ESTABLE"
    return "SATURADO"

def reset_mobile_data_termux():
    if not IS_TERMUX: return False
    try:
        log("Reiniciando datos moviles...", "WARN")
        subprocess.run(["svc", "data", "disable"], timeout=5, capture_output=True, check=False)
        time.sleep(3)
        subprocess.run(["svc", "data", "enable"], timeout=5, capture_output=True, check=False)
        log("Datos moviles reiniciados", "INFO")
        return True
    except FileNotFoundError:
        log("Comando 'svc' no disponible", "WARN")
        return False
    except Exception as e:
        log("Error reset datos: {}".format(e), "ERROR")
        return False

def ping_loop():
    log("ping_loop thread started", "DEBUG")
    while not _network_monitor_shutdown.is_set():
        try:
            def do_ping(host, key):
                lat = measure_ping(host)
                if lat < 1000: ping_data[key].append(round(lat, 2))
            do_ping("8.8.8.8", "google")
            do_ping("1.1.1.1", "cloudflare")
            do_ping("api.uber.com", "uber")
        except Exception as e:
            log("ping_loop error: {}".format(e), "ERROR")
        for _ in range(5):
            if _network_monitor_shutdown.is_set(): return
            time.sleep(0.2)

def smart_network_loop():
    log("smart_network_loop thread started", "DEBUG")
    global network_state
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="NetMonitor")
    try:
        while not _network_monitor_shutdown.is_set():
            if hasattr(sys, 'is_finalizing') and sys.is_finalizing(): break
            try:
                # --- BLOQUE: VERIFICACION DE INTERNET ---
                if not check_internet():
                    with network_lock:
                        network_state.update({"status": "SIN_CONEXION", "last_check": time.time()})
                    for _ in range(5):
                        if _network_monitor_shutdown.is_set(): return
                        time.sleep(1)
                    continue
                # --- BLOQUE: MEDICION DE SERVIDORES ---
                results = []
                for server in SERVERS:
                    ping_ms, http_s = measure_ping(server), measure_http_latency(server)
                    score = calculate_score(ping_ms, http_s)
                    results.append({"server": server, "ping_ms": round(ping_ms, 2), "http_s": http_s, "score": round(score, 3)})
                results.sort(key=lambda x: x["score"])
                with network_lock:
                    network_state["top_servers"] = [r["server"] for r in results[:3]]
                if len(results) >= 2:
                    best1, best2 = results[0]["server"], results[1]["server"]
                    t1_val, t2_val = 2.0, 2.0
                    try:
                        if not _network_monitor_shutdown.is_set():
                            future1 = executor.submit(measure_http_latency, best1, 3.0)
                            t1_val = future1.result(timeout=4)
                    except (RuntimeError, FuturesTimeoutError, Exception) as e:
                        pass
                    try:
                        if not _network_monitor_shutdown.is_set():
                            future2 = executor.submit(measure_http_latency, best2, 3.0)
                            t2_val = future2.result(timeout=4)
                    except (RuntimeError, FuturesTimeoutError, Exception) as e:
                        pass
                    winner = best1 if t1_val <= t2_val else best2
                    final_latency = t1_val if winner == best1 else t2_val
                    estado = classify_network_state(final_latency)
                    with network_lock:
                        network_state.update({"current": winner, "latency": round(final_latency, 3), "status": estado, "winner": winner, "last_check": time.time()})
                    if final_latency > THRESHOLD_CRITICAL: reset_mobile_data_termux()
            except Exception as e:
                if "shutdown" in str(e).lower(): break
                log("smart_network_loop error: {}".format(e), "ERROR")
            for _ in range(2):
                if _network_monitor_shutdown.is_set(): return
                time.sleep(1)
    finally:
        executor.shutdown(wait=False)
        log("smart_network_loop thread stopped gracefully", "INFO")


# ================================================================================
# SECCION 12: SINCRONIZACION CON REGISTRY (PARTE 1, 5) Y MODULOS (2, 3, 4)
# ================================================================================
def registry_sync_loop():
    """Sube estado de red/GPS al Registry y baja datos de Parts 2, 3, 4."""
    log("registry_sync_loop iniciada para integracion inter-modulos", "INFO")
    registry = SharedDataRegistry()
    while not _registry_sync_shutdown.is_set():
        try:
            # --- BLOQUE: SUBIR ESTADO AL REGISTRY ---
            with network_lock:
                net_copy = copy.deepcopy(network_state)
            registry.set("network:state", net_copy)
            
            _, gps, _, _ = initialize_routing_components()
            loc = gps.get_current_location()
            if loc:
                registry.set("gps:current_location", {"lat": loc.latitude, "lon": loc.longitude, "speed_kmh": gps.get_speed_kmh(), "ts": time.time()})
            
            # --- BLOQUE: BAJAR DATOS DE PARTES 2, 3, 4 (EJEMPLO) ---
            # Parte 3: Radar
            radar_best = registry.get("radar:best_opportunity")
            if radar_best:
                # Ajustar destino recomendado en el estado del sistema
                registry.set("routing:suggested_destination", radar_best.get("zone_id", "multiplaza"))
                
            # Parte 4: Predictor
            prediction_latest = registry.get("predictor:prediction:latest")
            if prediction_latest:
                registry.set("routing:predicted_demand_zone", prediction_latest.get("cell", ""))
                
        except Exception as e:
            log("Error en registry_sync_loop: {}".format(e), "ERROR")
        
        for _ in range(10):
            if _registry_sync_shutdown.is_set(): return
            time.sleep(1)


def start_background_monitors():
    """Inicia los hilos de monitoreo de red, ping y sync (solo una vez por proceso)."""
    global _network_monitor_started, _network_monitor_pid
    current_pid = os.getpid()
    if _network_monitor_started and _network_monitor_pid == current_pid:
        log("Network monitors already started in this process, skipping", "DEBUG")
        return
    try:
        t1 = threading.Thread(target=ping_loop, daemon=False, name="NetworkPing")
        t1.start()
        log("Hilo ping_loop creado (PID={}, alive={})".format(current_pid, t1.is_alive()), "INFO")
        
        t2 = threading.Thread(target=smart_network_loop, daemon=False, name="NetworkUltra")
        t2.start()
        log("Hilo smart_network_loop creado (PID={}, alive={})".format(current_pid, t2.is_alive()), "INFO")
        
        t3 = threading.Thread(target=registry_sync_loop, daemon=True, name="RegistrySync")
        t3.start()
        log("Hilo registry_sync_loop creado (alive={})".format(t3.is_alive()), "INFO")
        
        _network_monitor_started = True
        _network_monitor_pid = current_pid
        log("Hilos de monitoreo de red y sync iniciados", "INFO")
    except Exception as e:
        log("Error al crear hilos: {}".format(traceback.format_exc()), "ERROR")

start_background_monitors()


# ================================================================================
# SECCION 13: FUNCIONES EXPORTABLES PARA EL NUCLEO Y PART 8 (HTML)
# ================================================================================
_routing_engine = None
_gps = None
_traffic = None
_graph = None

def initialize_routing_components():
    global _routing_engine, _gps, _traffic, _graph
    if _graph is None: _graph = generate_panama_network()
    if _traffic is None: _traffic = TrafficManager()
    if _routing_engine is None: _routing_engine = RoutingEngine(_graph, _traffic)
    if _gps is None: _gps = TermuxGPS()
    return _routing_engine, _gps, _traffic, _graph

def get_network_monitor_instance() -> Dict[str, Any]:
    with network_lock:
        net_copy = network_state.copy()
    return {
        "driver_state": {"lat": None, "lon": None, "last_update": None},
        "network_state": net_copy,
        "ping_data": {k: list(v) for k, v in ping_data.items()},
        "is_termux": IS_TERMUX
    }

def get_gps_location() -> Optional[Coordinate]:
    _, gps, _, _ = initialize_routing_components()
    return gps.get_current_location()

def get_route_between_coords(origin: Coordinate, destination: Coordinate,
                             algorithm: str = "A_STAR", objective: str = "TIME",
                             avoid_tolls: bool = False, avoid_highways: bool = False) -> Optional[Dict]:
    engine, _, _, _ = initialize_routing_components()
    algo = RoutingAlgorithm[algorithm.upper()]
    obj = OptimizationObjective[objective.upper()]
    route = engine.find_route(origin, destination, algo, obj, avoid_tolls, avoid_highways)
    if not route: return None
    return {
        "distance_km": route.total_distance_km,
        "time_min": route.total_time_minutes,
        "cost": route.total_cost,
        "waypoints": [(wp.latitude, wp.longitude) for wp in route.waypoints],
        "geojson": route.to_geojson()
    }

def export_estado_para_nucleo() -> Dict[str, Any]:
    """Exporta estado consolidado para el CEOIA (Parte 5)."""
    with network_lock:
        net_st = copy.deepcopy(network_state)
    _, gps, _, _ = initialize_routing_components()
    loc = gps.get_current_location()
    return {
        "network_status": net_st.get("status", "DESCONOCIDO"),
        "latency_ms": net_st.get("latency", 999.0),
        "optimal_server": net_st.get("winner"),
        "gps": {"lat": loc.latitude, "lon": loc.longitude} if loc else None,
        "internet_available": check_internet(),
        "timestamp": time.time()
    }

def get_metricas_ceo() -> Dict[str, Any]:
    """Metricas especificas para el CEOIA."""
    with network_lock:
        return {
            "network_status": network_state.get("status", "DESCONOCIDO"),
            "latency": network_state.get("latency", 999.0),
            "server": network_state.get("current"),
            "internet": check_internet()
        }


# ================================================================================
# SECCION 14: SERVIDOR FLASK PARA DASHBOARD HTML (PARTE 8)
# ================================================================================
FLASK_AVAILABLE = False
app = None
HTTP_PORT = 8989
try:
    from flask import Flask, request, jsonify, make_response
    app = Flask(__name__)
    FLASK_AVAILABLE = True
except ImportError:
    pass

def register_network_endpoints(flask_app=None, logger=None):
    global app
    if flask_app is not None:
        app = flask_app
    elif app is None:
        log("Flask no disponible, no se pueden registrar endpoints", "WARN")
        return
    _log = logger if logger else log
    
    @app.route('/api/v1/ping', methods=['GET'])
    def get_ping():
        def avg(d): return round(sum(d)/len(d), 2) if d else None
        return jsonify({
            "google": list(ping_data["google"]),
            "cloudflare": list(ping_data["cloudflare"]),
            "uber": list(ping_data["uber"]),
            "averages": {"google": avg(ping_data["google"]), "cloudflare": avg(ping_data["cloudflare"]), "uber": avg(ping_data["uber"])}
        })
    
    @app.route('/api/v1/network', methods=['GET'])
    def get_network():
        with network_lock:
            cur = network_state.get("current")
            status = network_state.get("status")
            latency = network_state.get("latency")
            last = network_state.get("last_check")
        return jsonify({
            "status": status,
            "winner": cur,
            "latency": latency,
            "last_check": last,
            "internet_ok": check_internet()
        })
    
    @app.route('/api/v1/gps/current', methods=['GET'])
    def api_gps():
        gps_loc = get_gps_location()
        if gps_loc:
            return jsonify({"success": True, "latitude": gps_loc.latitude, "longitude": gps_loc.longitude,
                            "speed_kmh": TermuxGPS().get_speed_kmh()})
        return jsonify({"success": False, "error": "GPS no disponible"}), 503
    
    @app.route('/api/v1/route', methods=['POST'])
    def api_route():
        data = request.get_json(silent=True) or {}
        try:
            orig = Coordinate(data.get('origin_lat', 9.0), data.get('origin_lon', -79.5))
            dest = Coordinate(data.get('dest_lat', 8.98), data.get('dest_lon', -79.52))
            algo = data.get('algorithm', 'A_STAR')
            obj = data.get('objective', 'TIME')
            route = get_route_between_coords(orig, dest, algo, obj,
                                             data.get('avoid_tolls', False),
                                             data.get('avoid_highways', False))
            if route:
                return jsonify({"success": True, "route": route})
            return jsonify({"success": False, "error": "No se encontro ruta"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # --- BLOQUE: ENDPOINTS ESPECIFICOS PARA PARTE 8 (HTML DASHBOARD) ---
    @app.route('/api/v1/dashboard/network_widget', methods=['GET'])
    def api_dashboard_net():
        """Datos ligeros para el widget de red del dashboard HTML."""
        with network_lock:
            return jsonify({
                "status": network_state.get("status", "DESCONOCIDO"),
                "latency": network_state.get("latency", 999.0),
                "server": network_state.get("current"),
                "top_servers": network_state.get("top_servers", [])[:3],
                "internet": check_internet()
            })

    @app.route('/api/v1/dashboard/map_data', methods=['GET'])
    def api_dashboard_map():
        """Datos de GPS y Ruta para el mapa del dashboard HTML."""
        loc = get_gps_location()
        route_data = None
        if loc:
            dest_coord = Coordinate(9.0381, -79.4798) # Destino por defecto (Multiplaza)
            # Intentar obtener destino sugerido del Registry (Parte 3/4)
            registry = SharedDataRegistry()
            suggested = registry.get("routing:suggested_destination")
            if suggested and suggested in PANAMA_LOCATIONS:
                d = PANAMA_LOCATIONS[suggested]
                dest_coord = Coordinate(d["lat"], d["lon"])
            route_data = get_route_between_coords(loc, dest_coord)
        return jsonify({
            "gps": {"lat": loc.latitude, "lon": loc.longitude} if loc else None,
            "route": route_data
        })

    _log("Endpoints de red, enrutamiento y dashboard HTML registrados", "INFO")


# ================================================================================
# SECCION 15: PUNTO DE ENTRADA
# ================================================================================
if __name__ == "__main__":
    log("Iniciando sistema de enrutamiento GPS y Network Monitor", "INFO")
    engine, gps, traffic, _ = initialize_routing_components()
    log("Red vial: {} nodos, {} aristas".format(len(engine.graph.nodes), len(engine.graph.edges)), "INFO")
    if FLASK_AVAILABLE:
        register_network_endpoints()
        port = 8990
        log("Servidor API en http://0.0.0.0:{}".format(port), "INFO")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
    else:
        while True:
            loc = gps.get_current_location()
            if loc:
                print("GPS: {:.4f}, {:.4f}".format(loc.latitude, loc.longitude))
            time.sleep(5)
