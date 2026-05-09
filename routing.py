#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
ENRUTAMIENTO GPS - SERVIDOR PRINCIPAL UNIFICADO
================================================
SYMBIOSIS ROUTING ENGINE + NETWORK MONITOR INTEGRADO
Sistema completamente automático - GPS en tiempo real
Red vial de Panamá con monitoreo continuo + API Flask

✅ Funcionalidades integradas:
   • Motor de enrutamiento A*/Dijkstra/Bellman-Ford/Floyd-Warshall/Greedy/Bidireccional/LiveTraffic/Johnson
   • GPS en tiempo real vía termux-location
   • Gestión de tráfico dinámico con eventos simulados
   • Cache de rutas para optimización de rendimiento
   • API REST completa con Flask (puerto auto-detectado)
   • Monitoreo de red inteligente con auto-reconexión
   • Proxy seguro para consultas externas
   • Compatibilidad total con Termux/Android

Autor: MiniMax Agent + Symbiosis Team
Version: 3.2.0 - Servidor Principal Unificado con Todos los Algoritmos
"""

from __future__ import annotations
import math, heapq, random, uuid, time, json, sys, os, subprocess, threading, socket, copy, hashlib, traceback
from typing import Dict, List, Optional, Tuple, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from collections import deque, defaultdict
from abc import ABC, abstractmethod

# ============================================================================
# CONFIGURACIÓN TERMUX Y ENTORNO
# ============================================================================
if hasattr(sys, 'setdefaultencoding'):
    sys.setdefaultencoding('utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

DEBUG = False
AUTO_MODE = True
IS_TERMUX = os.getenv('TERMUX_VERSION') is not None or 'com.termux' in os.getenv('PATH', '')

# ============================================================================
# ENUMS Y CONSTANTES DEL MOTOR DE RUTAS
# ============================================================================

class RoutingAlgorithm(Enum):
    """Algoritmos de enrutamiento disponibles."""
    DIJKSTRA = auto()
    A_STAR = auto()
    BELLMAN_FORD = auto()
    FLOYD_WARSHALL = auto()
    GREEDY_BEST_FIRST = auto()
    BIDIRECTIONAL = auto()
    LIVE_TRAFFIC = auto()
    JOHNSON = auto()  # NUEVO: Para grafos sparse con pesos negativos

class TrafficCondition(Enum):
    """Condiciones de tráfico."""
    FREE = 1.0
    NORMAL = 0.7
    MODERATE = 0.5
    HEAVY = 0.3
    BLOCKED = 0.1

class OptimizationObjective(Enum):
    """Objetivos de optimización."""
    DISTANCE = "distance"
    TIME = "time"
    COST = "cost"
    BALANCED = "balanced"

# ============================================================================
# ESTRUCTURAS DE DATOS GEOESPACIALES
# ============================================================================

@dataclass
class Coordinate:
    """Coordenada geográfica simple."""
    latitude: float
    longitude: float
    
    def distance_to(self, other: 'Coordinate') -> float:
        """Distancia Haversine en km."""
        R = 6371.0
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

@dataclass
class Node:
    """Nodo en el grafo de rutas."""
    node_id: str
    coordinate: Coordinate
    name: str = ""
    node_type: str = "intersection"
    elevation: float = 0.0

@dataclass
class Edge:
    """Arista (camino) entre nodos."""
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
    """Evento de tráfico que afecta una arista."""
    event_id: str
    edge_id: str
    condition: TrafficCondition
    start_time: datetime
    end_time: Optional[datetime] = None
    description: str = ""
    delay_minutes: float = 0.0

@dataclass
class Route:
    """Ruta calculada entre dos puntos."""
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
        """Exporta ruta como GeoJSON para visualización."""
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

# ============================================================================
# GPS EN TIEMPO REAL PARA TERMUX
# ============================================================================

class TermuxGPS:
    """
    Obtiene coordenadas GPS en tiempo real usando termux-location.
    Requiere: pkg install termux-api
    """
    
    def __init__(self):
        self.last_location: Optional[Coordinate] = None
        self.last_update: Optional[datetime] = None
        self.is_available = self._check_termux_api()
        self.location_history: List[Coordinate] = []
        self.max_history = 100
    
    def _check_termux_api(self) -> bool:
        """Verifica si termux-api está instalado."""
        try:
            result = subprocess.run(['which', 'termux-location'], 
                                  capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except:
            return False
    
    def get_current_location(self) -> Optional[Coordinate]:
        """
        Obtiene la ubicación actual usando GPS.
        Retorna None si no está disponible o falla.
        """
        if not self.is_available:
            return self._get_simulated_location()
        
        try:
            result = subprocess.run(
                ['termux-location', '-p', 'gps'],
                capture_output=True,
                text=True,
                timeout=10
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
                    
        except subprocess.TimeoutExpired:
            pass
        except json.JSONDecodeError:
            pass
        except Exception:
            pass
        
        return self._get_simulated_location()
    
    def _get_simulated_location(self) -> Coordinate:
        """Ubicación simulada con movimiento realista por Panamá."""
        import time as t
        
        locations = [
            (9.0285, -79.5325),   # Costa Verde
            (9.0392, -79.5189),   # Westland
            (9.0381, -79.4798),   # Multiplaza
            (9.0167, -79.5167),   # Transístmica
            (8.9736, -79.5528),   # Albrook
            (8.9518, -79.6534),   # Arraiján
        ]
        
        idx = int(t.time() / 60) % len(locations)
        return Coordinate(latitude=locations[idx][0], longitude=locations[idx][1])
    
    def get_speed_kmh(self) -> float:
        """Estima velocidad actual basada en historial."""
        if len(self.location_history) < 2:
            return 0.0
        
        last = self.location_history[-1]
        prev = self.location_history[-2]
        
        dist = last.distance_to(prev)
        time_diff = 5  # segundos entre actualizaciones
        
        if time_diff > 0:
            return (dist / time_diff) * 3600
        return 0.0

# ============================================================================
# PUNTOS DE INTERÉS EN PANAMÁ
# ============================================================================

PANAMA_LOCATIONS = {
    "costa_verde": {"name": "Costa Verde", "lat": 9.0285, "lon": -79.5325, "type": "shopping"},
    "westland_mall": {"name": "Westland Mall", "lat": 9.0392, "lon": -79.5189, "type": "shopping"},
    "albrook_mall": {"name": "Albrook Mall", "lat": 8.9736, "lon": -79.5528, "type": "shopping"},
    "tocumen_airport": {"name": "Aeropuerto Internacional de Tocumen", "lat": 9.0714, "lon": -79.3835, "type": "airport"},
    "panama_pacifico": {"name": "Aeropuerto Internacional Panamá Pacífico", "lat": 8.9148, "lon": -79.5996, "type": "airport"},
    "arraijan_tc": {"name": "Arraiján Town Center", "lat": 8.9518, "lon": -79.6534, "type": "shopping"},
    "multiplaza": {"name": "Multiplaza Pacífica", "lat": 9.0381, "lon": -79.4798, "type": "shopping"},
    "metromall": {"name": "Metromall", "lat": 9.0742, "lon": -79.4259, "type": "shopping"}
}

# ============================================================================
# GRAFO DE RUTAS
# ============================================================================

class RouteGraph:
    """Grafo dirigido para enrutamiento con múltiples atributos por arista."""
    
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self.adjacency: Dict[str, List[str]] = defaultdict(list)
        self.reverse_adjacency: Dict[str, List[str]] = defaultdict(list)
        self._spatial_index: Dict[str, List[str]] = defaultdict(list)
        self._grid_size = 0.5
    
    def add_node(self, node: Node) -> None:
        """Añade un nodo al grafo."""
        self.nodes[node.node_id] = node
        cell = self._get_spatial_cell(node.coordinate)
        self._spatial_index[cell].append(node.node_id)
    
    def add_edge(self, edge: Edge, bidirectional: bool = True) -> None:
        """Añade una arista al grafo."""
        self.edges[edge.edge_id] = edge
        self.adjacency[edge.from_node].append(edge.edge_id)
        self.reverse_adjacency[edge.to_node].append(edge.edge_id)
        
        if bidirectional:
            reverse_edge = Edge(
                edge_id=f"{edge.edge_id}_rev",
                from_node=edge.to_node,
                to_node=edge.from_node,
                distance=edge.distance,
                base_time=edge.base_time,
                speed_limit=edge.speed_limit,
                road_type=edge.road_type,
                toll_cost=edge.toll_cost,
                traffic_multiplier=edge.traffic_multiplier
            )
            self.edges[reverse_edge.edge_id] = reverse_edge
            self.adjacency[reverse_edge.from_node].append(reverse_edge.edge_id)
            self.reverse_adjacency[reverse_edge.to_node].append(reverse_edge.edge_id)
    
    def _get_spatial_cell(self, coord: Coordinate) -> str:
        """Obtiene la celda del índice espacial."""
        lat_cell = int(coord.latitude / self._grid_size)
        lon_cell = int(coord.longitude / self._grid_size)
        return f"{lat_cell},{lon_cell}"
    
    def get_nearby_nodes(self, coord: Coordinate, radius_km: float = 5.0) -> List[Tuple[str, float]]:
        """Obtiene nodos cercanos a una coordenada."""
        candidates = set()
        cell_radius = int(radius_km / (self._grid_size * 111)) + 1
        center_cell = self._get_spatial_cell(coord)
        lat0, lon0 = map(int, center_cell.split(','))
        
        for dlat in range(-cell_radius, cell_radius + 1):
            for dlon in range(-cell_radius, cell_radius + 1):
                cell = f"{lat0 + dlat},{lon0 + dlon}"
                candidates.update(self._spatial_index.get(cell, []))
        
        nearby = []
        for node_id in candidates:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                dist = coord.distance_to(node.coordinate)
                if dist <= radius_km:
                    nearby.append((node_id, dist))
        return sorted(nearby, key=lambda x: x[1])
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Obtiene un nodo por ID."""
        return self.nodes.get(node_id)
    
    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Obtiene una arista por ID."""
        return self.edges.get(edge_id)
    
    def get_outgoing_edges(self, node_id: str) -> List[Edge]:
        """Obtiene todas las aristas salientes de un nodo."""
        return [self.edges[eid] for eid in self.adjacency.get(node_id, []) if eid in self.edges]
    
    def get_incoming_edges(self, node_id: str) -> List[Edge]:
        """Obtiene todas las aristas entrantes a un nodo."""
        return [self.edges[eid] for eid in self.reverse_adjacency.get(node_id, []) if eid in self.edges]

# ============================================================================
# GENERADOR DE RED VIAL DE PANAMÁ
# ============================================================================

def generate_panama_network() -> RouteGraph:
    """Genera red vial con ubicaciones reales de Panamá."""
    graph = RouteGraph()
    
    # Agregar nodos para cada ubicación importante
    for loc_id, loc_data in PANAMA_LOCATIONS.items():
        node = Node(
            node_id=loc_id,
            coordinate=Coordinate(latitude=loc_data["lat"], longitude=loc_data["lon"]),
            name=loc_data["name"],
            node_type=loc_data["type"]
        )
        graph.add_node(node)
    
    # Agregar nodos intermedios
    intermediate_nodes = [
        ("via_espana", "Vía España", 8.9833, -79.5333),
        ("transistmica", "Transístmica", 9.0167, -79.5167),
        ("corredor_norte", "Corredor Norte", 9.0500, -79.4500),
        ("corredor_sur", "Corredor Sur", 9.0000, -79.5167),
        ("centenario", "Puente Centenario", 9.0333, -79.6500),
        ("americas", "Puente de las Américas", 8.9500, -79.5667),
        ("via_porras", "Vía Porras", 8.9833, -79.5167),
        ("tumba_muerto", "Tumba Muerto", 9.0333, -79.5000),
        ("via_brasil", "Vía Brasil", 9.0500, -79.4833),
        ("cinquetenario", "Cincuentenario", 9.0667, -79.4167)
    ]
    
    for node_id, name, lat, lon in intermediate_nodes:
        node = Node(
            node_id=node_id,
            coordinate=Coordinate(latitude=lat, longitude=lon),
            name=name,
            node_type="intersection"
        )
        graph.add_node(node)
    
    # Definir conexiones
    connections = [
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
    
    for from_id, to_id, dist, speed, road_type, toll in connections:
        if from_id in graph.nodes and to_id in graph.nodes:
            base_time = (dist / speed) * 60
            edge = Edge(
                edge_id=f"E_{from_id}_{to_id}",
                from_node=from_id,
                to_node=to_id,
                distance=dist,
                base_time=base_time,
                speed_limit=speed,
                road_type=road_type,
                toll_cost=toll
            )
            graph.add_edge(edge, bidirectional=True)
    
    return graph

# ============================================================================
# MOTOR DE TRÁFICO EN TIEMPO REAL
# ============================================================================

class TrafficManager:
    """Gestiona eventos de tráfico y condiciones dinámicas."""
    
    def __init__(self):
        self.events: Dict[str, TrafficEvent] = {}
        self.condition_history: Dict[str, List[Tuple[datetime, TrafficCondition]]] = defaultdict(list)
    
    def cleanup_expired_events(self) -> None:
        """Limpia eventos expirados."""
        now = datetime.now(timezone.utc)
        to_delete = [
            eid for eid, ev in self.events.items()
            if ev.end_time and ev.end_time <= now
        ]
        for eid in to_delete:
            del self.events[eid]
    
    def add_event(self, event: TrafficEvent) -> None:
        """Añade un evento de tráfico."""
        self.cleanup_expired_events()
        self.events[event.event_id] = event
        self._update_edge_condition(event.edge_id, event.condition, event.start_time)
    
    def remove_event(self, event_id: str) -> None:
        """Elimina un evento de tráfico."""
        if event_id in self.events:
            event = self.events.pop(event_id)
            self._recalculate_edge_condition(event.edge_id)
    
    def get_current_condition(self, edge_id: str) -> TrafficCondition:
        """Obtiene la condición actual de una arista."""
        now = datetime.now(timezone.utc)
        current_hour = (now.hour - 5) % 24
        
        if 6 <= current_hour <= 9:
            base_condition = TrafficCondition.HEAVY
        elif 16 <= current_hour <= 19:
            base_condition = TrafficCondition.HEAVY
        elif 11 <= current_hour <= 14:
            base_condition = TrafficCondition.MODERATE
        elif 22 <= current_hour or current_hour <= 5:
            base_condition = TrafficCondition.FREE
        else:
            base_condition = TrafficCondition.NORMAL
        
        for event in self.events.values():
            if event.edge_id == edge_id:
                if event.end_time is None or event.end_time > now:
                    if event.start_time <= now:
                        return event.condition
        
        return base_condition
    
    def get_multiplier(self, edge_id: str) -> float:
        """Obtiene el multiplicador de tiempo para una arista."""
        condition = self.get_current_condition(edge_id)
        return condition.value
    
    def simulate_accident(self, edge_id: str, duration_minutes: int = 30) -> TrafficEvent:
        """Simula un accidente en una arista."""
        event = TrafficEvent(
            event_id=str(uuid.uuid4())[:8],
            edge_id=edge_id,
            condition=TrafficCondition.BLOCKED,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=duration_minutes),
            description="Accidente simulado",
            delay_minutes=duration_minutes
        )
        self.add_event(event)
        return event
    
    def _update_edge_condition(self, edge_id: str, condition: TrafficCondition, timestamp: datetime) -> None:
        """Registra cambio de condición."""
        self.condition_history[edge_id].append((timestamp, condition))
    
    def _recalculate_edge_condition(self, edge_id: str) -> None:
        """Recalcula condición de una arista tras eliminar evento."""
        pass

# ============================================================================
# CACHE DE RUTAS
# ============================================================================

class RouteCache:
    """Cache para rutas calculadas."""
    
    def __init__(self, max_size: int = 100):
        self.cache: Dict[tuple, Route] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def get(self, key: tuple) -> Optional[Route]:
        """Obtiene ruta del cache."""
        if key in self.cache:
            self.hits += 1
            return copy.deepcopy(self.cache[key])
        self.misses += 1
        return None
    
    def set(self, key: tuple, route: Route) -> None:
        """Guarda ruta en cache."""
        if len(self.cache) >= self.max_size:
            first_key = next(iter(self.cache))
            del self.cache[first_key]
        self.cache[key] = copy.deepcopy(route)
    
    def clear(self) -> None:
        """Limpia el cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas del cache."""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate
        }

# ============================================================================
# PRECOMPUTADOR FLOYD-WARSHALL (PARA CONSULTAS RÁPIDAS)
# ============================================================================

class FloydWarshallPrecomputer:
    """
    Precomputa todas las rutas más cortas entre todos los pares de nodos.
    Útil para consultas instantáneas cuando el grafo no cambia frecuentemente.
    """
    
    def __init__(self, graph: RouteGraph, objective: OptimizationObjective = OptimizationObjective.TIME):
        self.graph = graph
        self.objective = objective
        self.dist_matrix: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: float('inf')))
        self.next_matrix: Dict[str, Dict[str, Optional[str]]] = defaultdict(lambda: defaultdict(lambda: None))
        self.is_computed = False
        self.compute_time_ms = 0.0
    
    def compute(self, avoid_tolls: bool = False, avoid_highways: bool = False) -> bool:
        """
        Ejecuta Floyd-Warshall para todos los pares de nodos.
        Complejidad: O(V³) - recomendado para grafos densos o precomputación.
        """
        if self.is_computed:
            return True
        
        start = time.time()
        nodes = list(self.graph.nodes.keys())
        n = len(nodes)
        
        if n == 0:
            return False
        
        # Inicializar matrices
        for i in nodes:
            self.dist_matrix[i][i] = 0.0
            self.next_matrix[i][i] = None
        
        # Cargar aristas iniciales
        for edge_id, edge in self.graph.edges.items():
            if avoid_tolls and edge.toll_cost > 0:
                continue
            if avoid_highways and edge.road_type == "highway":
                continue
            
            cost = self._edge_cost_simple(edge)
            u, v = edge.from_node, edge.to_node
            
            if cost < self.dist_matrix[u][v]:
                self.dist_matrix[u][v] = cost
                self.next_matrix[u][v] = v
        
        # Algoritmo Floyd-Warshall principal
        for k in nodes:
            for i in nodes:
                if self.dist_matrix[i][k] == float('inf'):
                    continue
                for j in nodes:
                    if self.dist_matrix[k][j] == float('inf'):
                        continue
                    
                    new_dist = self.dist_matrix[i][k] + self.dist_matrix[k][j]
                    if new_dist < self.dist_matrix[i][j]:
                        self.dist_matrix[i][j] = new_dist
                        self.next_matrix[i][j] = self.next_matrix[i][k]
        
        self.compute_time_ms = (time.time() - start) * 1000
        self.is_computed = True
        log(f"✅ Floyd-Warshall precomputado: {n} nodos en {self.compute_time_ms:.1f}ms", "INFO")
        return True
    
    def _edge_cost_simple(self, edge: Edge) -> float:
        """Costo simplificado para Floyd-Warshall."""
        if self.objective == OptimizationObjective.DISTANCE:
            return edge.distance
        elif self.objective == OptimizationObjective.TIME:
            return edge.base_time
        elif self.objective == OptimizationObjective.COST:
            return edge.toll_cost + edge.base_time * 0.02
        else:
            return 0.4 * edge.distance + 0.4 * edge.base_time + 0.2 * edge.toll_cost
    
    def get_path(self, origin: str, destination: str) -> List[str]:
        """Reconstruye el camino precomputado entre dos nodos."""
        if not self.is_computed:
            return []
        
        if self.dist_matrix[origin][destination] == float('inf'):
            return []
        
        path = [origin]
        current = origin
        
        while current != destination:
            next_node = self.next_matrix[current][destination]
            if next_node is None:
                return []
            path.append(next_node)
            current = next_node
        
        return path
    
    def get_distance(self, origin: str, destination: str) -> float:
        """Obtiene la distancia precomputada."""
        if not self.is_computed:
            return float('inf')
        return self.dist_matrix[origin].get(destination, float('inf'))
    
    def invalidate(self) -> None:
        """Invalida el precomputo cuando el grafo cambia."""
        self.is_computed = False
        self.dist_matrix.clear()
        self.next_matrix.clear()

# ============================================================================
# MOTOR DE ENRUTAMIENTO PRINCIPAL
# ============================================================================

class RoutingEngine:
    """Motor de enrutamiento con múltiples algoritmos."""
    
    def __init__(self, graph: RouteGraph, traffic_manager: Optional[TrafficManager] = None):
        self.graph = graph
        self.traffic = traffic_manager or TrafficManager()
        self.cache = RouteCache()
        self.fw_precomputer: Optional[FloydWarshallPrecomputer] = None
    
    def find_route(self, origin: Coordinate, destination: Coordinate,
                  algorithm: RoutingAlgorithm = RoutingAlgorithm.A_STAR,
                  objective: OptimizationObjective = OptimizationObjective.TIME,
                  avoid_tolls: bool = False, avoid_highways: bool = False,
                  use_cache: bool = True) -> Optional[Route]:
        """Encuentra la mejor ruta entre dos puntos."""
        
        origin_nodes = self.graph.get_nearby_nodes(origin, radius_km=5.0)
        dest_nodes = self.graph.get_nearby_nodes(destination, radius_km=5.0)
        
        if not origin_nodes or not dest_nodes:
            return None
        
        origin_node = origin_nodes[0][0]
        dest_node = dest_nodes[0][0]
        
        if use_cache:
            cache_key = (origin_node, dest_node, algorithm.name, objective.name, 
                        avoid_tolls, avoid_highways)
            cached_route = self.cache.get(cache_key)
            if cached_route:
                return cached_route
        
        # Seleccionar algoritmo
        if algorithm == RoutingAlgorithm.DIJKSTRA:
            path, edges = self._dijkstra(origin_node, dest_node, objective, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.A_STAR:
            path, edges = self._a_star(origin_node, dest_node, destination, objective, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.GREEDY_BEST_FIRST:
            path, edges = self._greedy_best_first(origin_node, dest_node, destination, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.BIDIRECTIONAL:
            path, edges = self._bidirectional(origin_node, dest_node, destination, objective, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.LIVE_TRAFFIC:
            path, edges = self._dijkstra_with_traffic(origin_node, dest_node, objective, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.BELLMAN_FORD:
            path, edges = self._bellman_ford(origin_node, dest_node, objective, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.FLOYD_WARSHALL:
            path, edges = self._floyd_warshall(origin_node, dest_node, objective, avoid_tolls, avoid_highways)
        elif algorithm == RoutingAlgorithm.JOHNSON:
            path, edges = self._johnson(origin_node, dest_node, objective, avoid_tolls, avoid_highways)
        else:
            path, edges = self._a_star(origin_node, dest_node, destination, objective, avoid_tolls, avoid_highways)
        
        if not path:
            return None
        
        route = self._build_route(path, edges, origin, destination, algorithm.name, objective)
        
        if use_cache:
            cache_key = (origin_node, dest_node, algorithm.name, objective.name,
                        avoid_tolls, avoid_highways)
            self.cache.set(cache_key, route)
        
        return route
    
    def _heuristic(self, node_id: str, target: Coordinate, 
                   objective: OptimizationObjective = OptimizationObjective.TIME) -> float:
        """Heurística mejorada y consistente."""
        node = self.graph.nodes.get(node_id)
        if not node:
            return 0.0
        
        dist_km = node.coordinate.distance_to(target)
        
        if objective == OptimizationObjective.TIME:
            avg_speed = 50
            return (dist_km / avg_speed) * 60
        elif objective == OptimizationObjective.COST:
            return dist_km * 0.15
        else:
            return dist_km
    
    def _edge_cost(self, edge: Edge, objective: OptimizationObjective,
                   avoid_tolls: bool, avoid_highways: bool) -> float:
        """Calcula el costo de una arista."""
        if avoid_tolls and edge.toll_cost > 0:
            return float('inf')
        if avoid_highways and edge.road_type == "highway":
            return float('inf')
        
        traffic_mult = self.traffic.get_multiplier(edge.edge_id)
        actual_time = edge.base_time * (2 - traffic_mult)
        
        penalty = 1.0
        if edge.road_type == "highway":
            penalty *= 0.9
        elif edge.road_type == "residential":
            penalty *= 1.2
        
        if objective == OptimizationObjective.DISTANCE:
            return edge.distance * penalty
        elif objective == OptimizationObjective.TIME:
            return actual_time * penalty
        elif objective == OptimizationObjective.COST:
            return edge.toll_cost + (actual_time * 0.02)
        else:
            return 0.4 * edge.distance + 0.4 * actual_time + 0.2 * edge.toll_cost
    
    # =====================================================================
    # DIJKSTRA
    # =====================================================================
    def _dijkstra(self, origin: str, destination: str, objective: OptimizationObjective,
                  avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """Implementación de Dijkstra para costo mínimo."""
        pq = [(0.0, origin)]
        distances = {origin: 0.0}
        previous = {origin: (None, None)}
        visited = set()
        
        while pq:
            current_cost, current_node = heapq.heappop(pq)
            if current_node in visited:
                continue
            visited.add(current_node)
            
            if current_node == destination:
                break
            
            for edge in self.graph.get_outgoing_edges(current_node):
                neighbor = edge.to_node
                if neighbor in visited:
                    continue
                
                edge_cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
                if edge_cost == float('inf'):
                    continue
                
                new_cost = current_cost + edge_cost
                if neighbor not in distances or new_cost < distances[neighbor]:
                    distances[neighbor] = new_cost
                    previous[neighbor] = (current_node, edge.edge_id)
                    heapq.heappush(pq, (new_cost, neighbor))
        
        return self._reconstruct_path(previous, destination)
    
    # =====================================================================
    # A* (A-STAR)
    # =====================================================================
    def _a_star(self, origin: str, destination: str, target_coord: Coordinate,
                objective: OptimizationObjective, avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """Implementación de A* con heurística euclidiana."""
        g_scores = {origin: 0.0}
        f_scores = {origin: self._heuristic(origin, target_coord, objective)}
        previous = {origin: (None, None)}
        pq = [(f_scores[origin], 0.0, origin)]
        visited = set()
        counter = 0
        
        while pq:
            f, g, current = heapq.heappop(pq)
            if current == destination:
                break
            if current in visited:
                continue
            visited.add(current)
            
            for edge in self.graph.get_outgoing_edges(current):
                neighbor = edge.to_node
                if neighbor in visited:
                    continue
                
                edge_cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
                if edge_cost == float('inf'):
                    continue
                
                tentative_g = g + edge_cost
                h = self._heuristic(neighbor, target_coord, objective)
                f = tentative_g + h
                
                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    f_scores[neighbor] = f
                    previous[neighbor] = (current, edge.edge_id)
                    counter += 1
                    heapq.heappush(pq, (f, counter, neighbor))
        
        return self._reconstruct_path(previous, destination)
    
    # =====================================================================
    # GREEDY BEST-FIRST SEARCH
    # =====================================================================
    def _greedy_best_first(self, origin: str, destination: str, target_coord: Coordinate,
                           avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """Greedy Best-First Search - Solo usa heurística."""
        pq = [(0.0, origin)]
        previous = {origin: (None, None)}
        visited = set()
        
        while pq:
            h, current = heapq.heappop(pq)
            if current == destination:
                break
            if current in visited:
                continue
            visited.add(current)
            
            for edge in self.graph.get_outgoing_edges(current):
                neighbor = edge.to_node
                if neighbor in visited:
                    continue
                
                edge_cost = self._edge_cost(edge, OptimizationObjective.TIME, avoid_tolls, avoid_highways)
                if edge_cost == float('inf'):
                    continue
                
                if neighbor not in previous:
                    previous[neighbor] = (current, edge.edge_id)
                    h_score = self._heuristic(neighbor, target_coord)
                    heapq.heappush(pq, (h_score, neighbor))
        
        return self._reconstruct_path(previous, destination)
    
    # =====================================================================
    # BIDIRECTIONAL SEARCH
    # =====================================================================
    def _bidirectional(self, origin: str, destination: str, target_coord: Coordinate,
                       objective: OptimizationObjective, avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """Búsqueda bidireccional - desde ambos extremos."""
        forward_pq = [(0.0, origin)]
        forward_dist = {origin: 0.0}
        forward_prev = {origin: (None, None)}
        
        backward_pq = [(0.0, destination)]
        backward_dist = {destination: 0.0}
        backward_prev = {destination: (None, None)}
        
        visited_forward = set()
        visited_backward = set()
        meeting_node = None
        
        while forward_pq and backward_pq:
            if forward_pq:
                f_cost, f_node = heapq.heappop(forward_pq)
                if f_node not in visited_forward:
                    visited_forward.add(f_node)
                    if f_node in visited_backward:
                        meeting_node = f_node
                        break
                    
                    for edge in self.graph.get_outgoing_edges(f_node):
                        neighbor = edge.to_node
                        edge_cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
                        if edge_cost == float('inf'):
                            continue
                        new_cost = f_cost + edge_cost
                        if neighbor not in forward_dist or new_cost < forward_dist[neighbor]:
                            forward_dist[neighbor] = new_cost
                            forward_prev[neighbor] = (f_node, edge.edge_id)
                            heapq.heappush(forward_pq, (new_cost, neighbor))
            
            if backward_pq:
                b_cost, b_node = heapq.heappop(backward_pq)
                if b_node not in visited_backward:
                    visited_backward.add(b_node)
                    if b_node in visited_forward:
                        meeting_node = b_node
                        break
                    
                    for edge in self.graph.get_incoming_edges(b_node):
                        neighbor = edge.from_node
                        edge_cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
                        if edge_cost == float('inf'):
                            continue
                        new_cost = b_cost + edge_cost
                        if neighbor not in backward_dist or new_cost < backward_dist[neighbor]:
                            backward_dist[neighbor] = new_cost
                            backward_prev[neighbor] = (b_node, edge.edge_id)
                            heapq.heappush(backward_pq, (new_cost, neighbor))
        
        if meeting_node is None:
            return [], []
        
        path_forward, edges_forward = self._reconstruct_path(forward_prev, meeting_node)
        
        path_backward = []
        edges_backward = []
        current = meeting_node
        while backward_prev.get(current, (None, None))[0] is not None:
            prev, edge_id = backward_prev[current]
            path_backward.append(current)
            edges_backward.append(edge_id)
            current = prev
        path_backward.append(destination)
        path_backward.reverse()
        edges_backward.reverse()
        
        return path_forward + path_backward[1:], edges_forward + edges_backward
    
    # =====================================================================
    # DIJKSTRA CON TRÁFICO EN TIEMPO REAL
    # =====================================================================
    def _dijkstra_with_traffic(self, origin: str, destination: str, objective: OptimizationObjective,
                                avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """Dijkstra con datos de tráfico dinámicos."""
        pq = [(0.0, origin)]
        distances = {origin: 0.0}
        previous = {origin: (None, None)}
        visited = set()
        nodes_visited = 0
        
        while pq:
            current_cost, current_node = heapq.heappop(pq)
            if current_node in visited:
                continue
            visited.add(current_node)
            nodes_visited += 1
            
            if nodes_visited % 20 == 0:
                self.traffic.cleanup_expired_events()
            
            if current_node == destination:
                break
            
            for edge in self.graph.get_outgoing_edges(current_node):
                neighbor = edge.to_node
                if neighbor in visited:
                    continue
                
                edge_cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
                if edge_cost == float('inf'):
                    continue
                
                new_cost = current_cost + edge_cost
                if neighbor not in distances or new_cost < distances[neighbor]:
                    distances[neighbor] = new_cost
                    previous[neighbor] = (current_node, edge.edge_id)
                    heapq.heappush(pq, (new_cost, neighbor))
        
        return self._reconstruct_path(previous, destination)
    
    # =====================================================================
    # BELLMAN-FORD (NUEVO - Detecta ciclos negativos)
    # =====================================================================
    def _bellman_ford(self, origin: str, destination: str, objective: OptimizationObjective,
                      avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """
        Algoritmo Bellman-Ford con terminación temprana.
        
        BENEFICIOS:
        - Funciona con pesos negativos (útil para incentivos de ruta)
        - Detecta ciclos negativos (alerta de rutas problemáticas)
        - Terminación temprana cuando no hay cambios (optimización)
        
        Complejidad: O(V*E) peor caso, pero O(E) en práctica con terminación temprana.
        """
        n = len(self.graph.nodes)
        distances = {node_id: float('inf') for node_id in self.graph.nodes}
        distances[origin] = 0.0
        previous = {origin: (None, None)}
        
        # Obtener todas las aristas válidas
        all_edges = []
        for edge in self.graph.edges.values():
            cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
            if cost != float('inf'):
                all_edges.append((edge.from_node, edge.to_node, cost, edge.edge_id))
        
        # Relajación con terminación temprana
        for i in range(n - 1):
            updated = False
            for u, v, cost, edge_id in all_edges:
                if distances[u] != float('inf') and distances[u] + cost < distances[v]:
                    distances[v] = distances[u] + cost
                    previous[v] = (u, edge_id)
                    updated = True
            
            # Terminación temprana: si no hubo cambios, terminamos
            if not updated:
                log(f"✅ Bellman-Ford terminación temprana en iteración {i+1}/{n-1}", "DEBUG")
                break
        
        # Verificar ciclos negativos (solo si llegamos al destino)
        if distances[destination] != float('inf'):
            for u, v, cost, edge_id in all_edges:
                if distances[u] != float('inf') and distances[u] + cost < distances[v]:
                    log(f"⚠️ Bellman-Ford detectó ciclo negativo alcanzable desde {origin}", "WARN")
                    # Aún así retornamos la ruta, pero con advertencia
                    break
        
        if distances[destination] == float('inf'):
            return [], []
        
        return self._reconstruct_path(previous, destination)
    
    # =====================================================================
    # FLOYD-WARSHALL (NUEVO - Todos los pares)
    # =====================================================================
    def _floyd_warshall(self, origin: str, destination: str, objective: OptimizationObjective,
                        avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """
        Algoritmo Floyd-Warshall para caminos más cortos entre todos los pares.
        
        BENEFICIOS:
        - Precomputa todas las rutas: consultas O(1) después
        - Útil para múltiples consultas rápidas en el mismo grafo
        - Mejor para grafos densos donde V³ < V*(E log V)
        
        Usa el precomputador FloydWarshallPrecomputer para eficiencia.
        """
        # Inicializar o reutilizar precomputador
        if self.fw_precomputer is None or not self.fw_precomputer.is_computed:
            self.fw_precomputer = FloydWarshallPrecomputer(self.graph, objective)
            self.fw_precomputer.compute(avoid_tolls, avoid_highways)
        
        # Obtener el camino precomputado
        path_nodes = self.fw_precomputer.get_path(origin, destination)
        
        if not path_nodes:
            return [], []
        
        # Reconstruir aristas del camino
        path_edges = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            # Encontrar la arista correspondiente
            for edge in self.graph.get_outgoing_edges(u):
                if edge.to_node == v:
                    path_edges.append(edge.edge_id)
                    break
        
        return path_nodes, path_edges
    
    # =====================================================================
    # JOHNSON'S ALGORITHM (NUEVO - Optimizado para sparse graphs)
    # =====================================================================
    def _johnson(self, origin: str, destination: str, objective: OptimizationObjective,
                 avoid_tolls: bool, avoid_highways: bool) -> Tuple[List[str], List[str]]:
        """
        Algoritmo de Johnson: Bellman-Ford + Dijkstra para grafos sparse.
        
        BENEFICIOS:
        - O(V² log V + VE) - mejor que Floyd-Warshall para grafos sparse
        - Soporta pesos negativos (reweighting)
        - Ideal cuando E << V² (redes viales típicas)
        
        Pasos:
        1. Añadir nodo fuente ficticio con aristas de peso 0
        2. Ejecutar Bellman-Ford para obtener potenciales h[v]
        3. Reweight aristas: w'(u,v) = w(u,v) + h[u] - h[v] (todos positivos)
        4. Ejecutar Dijkstra desde cada nodo relevante
        """
        nodes = list(self.graph.nodes.keys())
        n = len(nodes)
        
        if n == 0:
            return [], []
        
        # Paso 1: Calcular potenciales usando Bellman-Ford desde nodo ficticio
        h = {node: 0.0 for node in nodes}  # Potenciales (inicialmente 0)
        
        # Añadir nodo ficticio 's' con aristas de peso 0 a todos
        # Ejecutar una pasada de Bellman-Ford
        for _ in range(n):
            updated = False
            for edge in self.graph.edges.values():
                cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
                if cost == float('inf'):
                    continue
                
                u, v = edge.from_node, edge.to_node
                if h[u] + cost < h[v]:
                    h[v] = h[u] + cost
                    updated = True
            
            if not updated:
                break
        
        # Verificar ciclos negativos
        for edge in self.graph.edges.values():
            cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
            if cost == float('inf'):
                continue
            u, v = edge.from_node, edge.to_node
            if h[u] + cost < h[v]:
                log(f"⚠️ Johnson detectó ciclo negativo", "WARN")
                # Fallback a Dijkstra estándar
                return self._dijkstra(origin, destination, objective, avoid_tolls, avoid_highways)
        
        # Paso 2: Reweight aristas
        def reweighted_cost(edge: Edge) -> float:
            cost = self._edge_cost(edge, objective, avoid_tolls, avoid_highways)
            if cost == float('inf'):
                return float('inf')
            return cost + h[edge.from_node] - h[edge.to_node]
        
        # Paso 3: Ejecutar Dijkstra desde el origen con aristas reweighted
        pq = [(0.0, origin)]
        distances = {origin: 0.0}
        previous = {origin: (None, None)}
        visited = set()
        
        while pq:
            current_cost, current_node = heapq.heappop(pq)
            if current_node in visited:
                continue
            visited.add(current_node)
            
            if current_node == destination:
                break
            
            for edge in self.graph.get_outgoing_edges(current_node):
                neighbor = edge.to_node
                if neighbor in visited:
                    continue
                
                edge_cost = reweighted_cost(edge)
                if edge_cost == float('inf') or edge_cost < 0:
                    # No debería pasar con reweighting correcto
                    continue
                
                new_cost = current_cost + edge_cost
                if neighbor not in distances or new_cost < distances[neighbor]:
                    distances[neighbor] = new_cost
                    previous[neighbor] = (current_node, edge.edge_id)
                    heapq.heappush(pq, (new_cost, neighbor))
        
        return self._reconstruct_path(previous, destination)
    
    # =====================================================================
    # RECONSTRUCCIÓN DE CAMINO
    # =====================================================================
    def _reconstruct_path(self, previous: Dict[str, Tuple[str, str]], destination: str) -> Tuple[List[str], List[str]]:
        """Reconstruye el camino desde el diccionario de previos."""
        path_nodes = []
        path_edges = []
        current = destination
        
        if destination not in previous:
            return [], []
        
        while current is not None:
            path_nodes.append(current)
            if current in previous and previous[current][0] is not None:
                _, edge_id = previous[current]
                path_edges.append(edge_id)
            else:
                break
            current = previous.get(current, (None, None))[0]
        
        path_nodes.reverse()
        path_edges.reverse()
        return path_nodes, path_edges
    
    # =====================================================================
    # CONSTRUCCIÓN DE RUTA
    # =====================================================================
    def _build_route(self, path_nodes: List[str], path_edges: List[str], origin: Coordinate,
                     destination: Coordinate, algorithm: str, objective: OptimizationObjective) -> Route:
        """Construye un objeto Route completo."""
        route = Route(
            origin=origin,
            destination=destination,
            origin_node=path_nodes[0] if path_nodes else None,
            destination_node=path_nodes[-1] if path_nodes else None,
            nodes=path_nodes,
            edges=path_edges,
            algorithm_used=algorithm
        )
        
        total_distance = 0.0
        total_time = 0.0
        total_cost = 0.0
        waypoints = [origin]
        
        for edge_id in path_edges:
            edge = self.graph.get_edge(edge_id)
            if edge:
                total_distance += edge.distance
                traffic_mult = self.traffic.get_multiplier(edge_id)
                total_time += edge.base_time * (2 - traffic_mult)
                total_cost += edge.toll_cost
                
                dest_node = self.graph.get_node(edge.to_node)
                if dest_node:
                    waypoints.append(dest_node.coordinate)
        
        waypoints.append(destination)
        route.total_distance_km = total_distance
        route.total_time_minutes = total_time
        route.total_cost = total_cost
        route.waypoints = waypoints
        route.instructions = self._generate_instructions(path_nodes, path_edges)
        
        return route
    
    # =====================================================================
    # GENERACIÓN DE INSTRUCCIONES
    # =====================================================================
    def _generate_instructions(self, nodes: List[str], edges: List[str]) -> List[Dict[str, Any]]:
        """Genera instrucciones paso a paso para la ruta."""
        instructions = []
        if not nodes:
            return instructions
        
        start_node = self.graph.get_node(nodes[0])
        instructions.append({
            "type": "start",
            "text": f"Iniciar en {start_node.name if start_node else 'ubicación actual'}",
            "distance_km": 0,
            "time_min": 0
        })
        
        for i, edge_id in enumerate(edges):
            edge = self.graph.get_edge(edge_id)
            if not edge:
                continue
            end_node = self.graph.get_node(edge.to_node)
            if not end_node:
                continue
            
            if i == 0:
                maneuver = "head"
            elif i == len(edges) - 1:
                maneuver = "arrive"
            else:
                maneuver = "continue"
            
            instructions.append({
                "type": maneuver,
                "text": f"Continuar por {edge.road_type}",
                "node": edge.to_node,
                "street": end_node.name or "Carretera",
                "distance_km": edge.distance,
                "time_min": edge.base_time,
                "instruction": self._get_turn_instruction(maneuver, edge)
            })
        
        return instructions
    
    def _get_turn_instruction(self, maneuver: str, edge: Edge) -> str:
        """Genera instrucción de giro."""
        road_types = {
            "highway": "autopista",
            "arterial": "avenida principal",
            "local": "calle local",
            "residential": "residencial"
        }
        road_name = road_types.get(edge.road_type, "carretera")
        
        if maneuver == "start":
            return f"Dirígete por {road_name}"
        elif maneuver == "arrive":
            return f"Llega a tu destino en {road_name}"
        else:
            return f"Continúa por {road_name} ({edge.distance:.1f} km)"

# ============================================================================
# NETWORK MONITOR - VARIABLES GLOBALES
# ============================================================================
driver_state = {"lat": None, "lon": None, "last_update": None}
ping_data = {"google": deque(maxlen=10), "cloudflare": deque(maxlen=10), "uber": deque(maxlen=10)}
network_state = {"current": None, "latency": None, "status": None, "fail_count": 0, "winner": None, "top_servers": [], "last_check": None}
SERVERS = ["api.uber.com", "tc2.uber.com", "cn-geo1.uber.com", "1.1.1.1", "www.google.com", "cloudflare.com"]
PING_WEIGHT, HTTP_WEIGHT = 0.35, 0.65
THRESHOLD_EXCELLENT, THRESHOLD_STABLE, THRESHOLD_CRITICAL = 0.30, 0.50, 1.0
API_KEY = os.getenv("MINI_UBER_KEY", "123456")

# ============================================================================
# LOGGING UNIFICADO
# ============================================================================
def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    try:
        ld = os.path.expanduser("~/x/logs")
        os.makedirs(ld, exist_ok=True)
        with open(os.path.join(ld, "symbiosis_unified.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

# ============================================================================
# FUNCIONES DE RED
# ============================================================================
def check_internet(timeout=2.0):
    try:
        socket.setdefaulttimeout(timeout)
        socket.getaddrinfo("1.1.1.1", 53)
        return True
    except:
        pass
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
            return True
    except:
        return False

def measure_ping(host: str, timeout=1):
    try:
        result = subprocess.run(["ping", "-c", "1", "-W", str(timeout), host], capture_output=True, text=True, timeout=timeout+1)
        if result.returncode == 0 and "time=" in result.stdout:
            for p in result.stdout.split():
                if "time=" in p:
                    return float(p.split("=")[1])
    except:
        pass
    try:
        start = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, 53 if host.replace('.','').isdigit() else 443))
        return round((time.time() - start) * 1000, 2)
    except:
        return 1000.0

def measure_http_latency(url: str, timeout=2.0):
    try:
        import requests
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        start = time.time()
        requests.get(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "Symbiosis/3.1"})
        return round(time.time() - start, 3)
    except ImportError:
        return measure_ping(url.replace('https://','').replace('http://','').split('/')[0]) / 1000
    except:
        return 2.0

def calculate_score(ping_ms, http_s):
    return (ping_ms * PING_WEIGHT) + (http_s * 1000 * HTTP_WEIGHT)

def classify_network_state(latency):
    if latency < THRESHOLD_EXCELLENT:
        return "🟢 EXCELENTE"
    elif latency < THRESHOLD_STABLE:
        return "🟡 ESTABLE"
    return "🔴 SATURADO"

def reset_mobile_data_termux():
    if not IS_TERMUX:
        return False
    try:
        log("🔄 Reiniciando datos móviles...", "WARN")
        subprocess.run(["svc", "data", "disable"], timeout=5, capture_output=True, check=False)
        time.sleep(3)
        subprocess.run(["svc", "data", "enable"], timeout=5, capture_output=True, check=False)
        log("✅ Datos móviles reiniciados", "INFO")
        return True
    except FileNotFoundError:
        log("⚠️ Comando 'svc' no disponible", "WARN")
        return False
    except Exception as e:
        log(f"❌ Error reset datos: {e}", "ERROR")
        return False

# ============================================================================
# LOOPS DE FONDO - NETWORK MONITOR
# ============================================================================
def ping_loop():
    while True:
        try:
            def do_ping(host, key):
                lat = measure_ping(host)
                if lat < 1000:
                    ping_data[key].append(round(lat, 2))
            do_ping("8.8.8.8", "google")
            do_ping("1.1.1.1", "cloudflare")
            do_ping("api.uber.com", "uber")
        except Exception as e:
            log(f"ping_loop error: {e}", "WARN")
        time.sleep(1)

def smart_network_loop_ultra():
    global network_state
    while True:
        try:
            if not check_internet():
                network_state.update({"status": "SIN_CONEXION", "last_check": time.time()})
                time.sleep(5)
                continue
            results = []
            for server in SERVERS:
                ping_ms = measure_ping(server)
                http_s = measure_http_latency(server)
                score = calculate_score(ping_ms, http_s)
                results.append({"server": server, "ping_ms": round(ping_ms,2), "http_s": http_s, "score": round(score,3)})
            results.sort(key=lambda x: x["score"])
            network_state["top_servers"] = [r["server"] for r in results[:3]]
            if len(results) >= 2:
                best1, best2 = results[0]["server"], results[1]["server"]
                parallel = {}
                def test_server(server, key):
                    try:
                        parallel[key] = measure_http_latency(server, timeout=3.0)
                    except:
                        parallel[key] = 2.0
                t1 = threading.Thread(target=test_server, args=(best1, "t1"))
                t2 = threading.Thread(target=test_server, args=(best2, "t2"))
                t1.start(); t2.start()
                t1.join(timeout=4); t2.join(timeout=4)
                t1_val, t2_val = parallel.get("t1", 2.0), parallel.get("t2", 2.0)
                winner = best1 if t1_val <= t2_val else best2
                final_latency = t1_val if winner == best1 else t2_val
                estado = classify_network_state(final_latency)
                network_state.update({"current": winner, "latency": round(final_latency,3),
                                     "status": estado.replace("🟢 ","").replace("🟡 ","").replace("🔴 ",""),
                                     "winner": winner, "last_check": time.time()})
                log(f"🏆 GANADOR: {winner} ({final_latency:.3f}s) | {estado}")
                if final_latency > THRESHOLD_CRITICAL:
                    reset_mobile_data_termux()
        except Exception as e:
            log(f"smart_network_loop error: {e}", "ERROR")
        time.sleep(2)

# ============================================================================
# SISTEMA AUTOMÁTICO DE ENRUTAMIENTO (para ejecución directa)
# ============================================================================
def format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    return f"{seconds/3600:.1f}h"

def print_header():
    """Imprime cabecera del sistema."""
    print("\n" + "=" * 60)
    print("   SYMBIOSIS - SISTEMA DE ENRUTAMIENTO GPS AUTOMÁTICO")
    print("   Red Vial de Panamá - Monitoreo Continuo")
    print("=" * 60)
    print("📍 Ubicaciones configuradas:")
    for loc_id, loc_data in PANAMA_LOCATIONS.items():
        print(f"   • {loc_data['name']}")
    print("=" * 60)
    print("🚀 Iniciando sistema automático...")
    print("   Presiona Ctrl+C para detener\n")

def auto_routing_system():
    """Sistema principal completamente automático."""
    
    print_header()
    
    # Inicializar componentes
    gps = TermuxGPS()
    graph = generate_panama_network()
    traffic = TrafficManager()
    engine = RoutingEngine(graph, traffic)
    
    # Estadísticas
    iteration = 0
    start_time = time.time()
    routes_calculated = 0
    
    # Destinos predefinidos
    destinations = []
    for loc_id, loc_data in PANAMA_LOCATIONS.items():
        destinations.append({
            "id": loc_id,
            "name": loc_data["name"],
            "coord": Coordinate(latitude=loc_data["lat"], longitude=loc_data["lon"]),
            "type": loc_data["type"]
        })
    
    print("📍 INICIANDO MONITOREO GPS...\n")
    
    try:
        while True:
            iteration += 1
            
            # Limpiar pantalla (opcional)
            if iteration % 10 == 0:
                os.system('clear 2>/dev/null || cls 2>/dev/null')
                print_header()
            
            # Obtener ubicación actual
            current_location = gps.get_current_location()
            speed = gps.get_speed_kmh()
            
            # Limpiar eventos expirados
            traffic.cleanup_expired_events()
            
            # Mostrar estado actual
            elapsed = time.time() - start_time
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ITERACIÓN {iteration} | Uptime: {format_time(elapsed)}")
            print("-" * 60)
            
            if current_location:
                # Encontrar ubicación conocida más cercana
                nearest = None
                min_dist = float('inf')
                for dest in destinations:
                    dist = current_location.distance_to(dest["coord"])
                    if dist < min_dist:
                        min_dist = dist
                        nearest = dest
                
                print(f"📍 GPS: {current_location.latitude:.4f}, {current_location.longitude:.4f}")
                if speed > 0:
                    print(f"🚗 Velocidad: {speed:.1f} km/h")
                if nearest and min_dist < 1.0:
                    print(f"📍 Cerca de: {nearest['name']} ({min_dist*1000:.0f}m)")
                else:
                    print(f"📍 Ubicación: En movimiento")
                
                print(f"\n🎯 RUTAS DISPONIBLES:")
                print("-" * 40)
                
                # Calcular rutas a todos los destinos usando diferentes algoritmos
                algorithms_to_test = [
                    (RoutingAlgorithm.A_STAR, "⭐ A*"),
                    (RoutingAlgorithm.DIJKSTRA, "🔵 Dijkstra"),
                    (RoutingAlgorithm.BELLMAN_FORD, "🟣 Bellman-Ford"),
                    (RoutingAlgorithm.BIDIRECTIONAL, "🟢 Bidireccional"),
                ]
                
                for dest in destinations:
                    # Usar A* como algoritmo principal
                    route = engine.find_route(
                        current_location, dest["coord"],
                        algorithm=RoutingAlgorithm.A_STAR,
                        objective=OptimizationObjective.TIME
                    )
                    
                    routes_calculated += 1
                    
                    if route:
                        # Determinar mejor ruta (más cercana)
                        if dest["id"] == "costa_verde":
                            icon = "🏠"
                        elif dest["type"] == "airport":
                            icon = "✈️"
                        else:
                            icon = "🛍️"
                        
                        # Calcular tiempo estimado de llegada
                        eta = datetime.now() + timedelta(minutes=route.total_time_minutes)
                        
                        print(f"  {icon} {dest['name']}:")
                        print(f"     📏 {route.total_distance_km:.1f} km | ⏱️ {route.total_time_minutes:.0f} min | 💰 ${route.total_cost:.2f}")
                        print(f"     🕐 ETA: {eta.strftime('%H:%M')}")
                    else:
                        print(f"  ❌ {dest['name']}: Sin ruta disponible")
                
                # Demostración de algoritmos avanzados cada 5 iteraciones
                if iteration % 5 == 0:
                    print(f"\n🔬 DEMOSTRACIÓN ALGORITMOS AVANZADOS:")
                    print("-" * 40)
                    
                    test_dest = destinations[0]  # Costa Verde
                    
                    # Floyd-Warshall
                    start_fw = time.time()
                    fw_route = engine.find_route(
                        current_location, test_dest["coord"],
                        algorithm=RoutingAlgorithm.FLOYD_WARSHALL,
                        objective=OptimizationObjective.TIME
                    )
                    fw_time = (time.time() - start_fw) * 1000
                    
                    if fw_route:
                        print(f"  📊 Floyd-Warshall: {fw_route.total_distance_km:.1f}km en {fw_time:.1f}ms")
                    
                    # Johnson
                    start_j = time.time()
                    j_route = engine.find_route(
                        current_location, test_dest["coord"],
                        algorithm=RoutingAlgorithm.JOHNSON,
                        objective=OptimizationObjective.TIME
                    )
                    j_time = (time.time() - start_j) * 1000
                    
                    if j_route:
                        print(f"  📊 Johnson: {j_route.total_distance_km:.1f}km en {j_time:.1f}ms")
                
                # Simular eventos de tráfico aleatorios
                if iteration % 8 == 0:
                    edges = list(graph.edges.keys())
                    if edges:
                        random_edge = random.choice(edges)
                        duration = random.choice([5, 10, 15, 30])
                        traffic.simulate_accident(random_edge, duration_minutes=duration)
                        edge_obj = graph.get_edge(random_edge)
                        if edge_obj:
                            from_node = graph.get_node(edge_obj.from_node)
                            to_node = graph.get_node(edge_obj.to_node)
                            if from_node and to_node:
                                print(f"\n  ⚠️ TRÁFICO: Accidente en {from_node.name} → {to_node.name}")
                                print(f"     Duración estimada: {duration} minutos")
                
                # Mostrar estadísticas del cache
                if iteration % 5 == 0:
                    stats = engine.cache.get_stats()
                    print(f"\n📊 Cache: {stats['size']} rutas | Hit rate: {stats['hit_rate']:.0%}")
            
            else:
                print("⚠️ GPS no disponible - esperando señal...")
            
            print(f"\n🔄 Próxima actualización en 5 segundos...")
            print("=" * 60)
            
            # Esperar para siguiente iteración
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("   SISTEMA DETENIDO POR EL USUARIO")
        print("=" * 60)
        
        # Estadísticas finales
        elapsed = time.time() - start_time
        stats = engine.cache.get_stats()
        
        print(f"\n📊 ESTADÍSTICAS FINALES:")
        print(f"   Tiempo total: {format_time(elapsed)}")
        print(f"   Iteraciones: {iteration}")
        print(f"   Rutas calculadas: {routes_calculated}")
        print(f"   Cache hits: {stats['hits']}")
        print(f"   Cache misses: {stats['misses']}")
        print(f"   Hit rate: {stats['hit_rate']:.1%}")
        print(f"   Rutas por segundo: {routes_calculated/elapsed:.1f}")
        print("\n✅ Sistema finalizado correctamente")

# ============================================================================
# FLASK APP + ENDPOINTS API
# ============================================================================
def encontrar_puerto_libre(base=8989, max_intentos=10):
    for i in range(max_intentos):
        puerto = base + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
    return base

# Inicializar Flask
try:
    from flask import Flask, request, jsonify, make_response
    app = Flask(__name__)
    HTTP_PORT = encontrar_puerto_libre()
    FLASK_AVAILABLE = True
except ImportError:
    app = None
    HTTP_PORT = 8989
    FLASK_AVAILABLE = False
    log("⚠️ Flask no disponible - modo solo terminal", "WARN")

if FLASK_AVAILABLE:
    # CORS automático
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, x-api-key, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return response

    # Rutas públicas (sin API key)
    PUBLIC_ROUTES = {
        "/", "/favicon.ico", "/health", "/api/v1/route", "/api/v1/gps/current",
        "/api/v1/gps/update", "/api/v1/traffic", "/api/v1/network", "/api/v1/ping",
        "/api/v1/pin", "/api/v1/driver/live", "/api/v1/address", "/internet/proxy"
    }

    @app.before_request
    def security_check():
        if request.method == "OPTIONS":
            return make_response("", 200)
        if request.path in PUBLIC_ROUTES:
            return
        key = request.headers.get("x-api-key")
        if key != API_KEY:
            log(f"🔒 Acceso denegado a {request.path}", "WARN")
            return make_response(jsonify({"error": "Forbidden", "status": 403}), 403)

    # === ENDPOINTS GPS Y ENRUTAMIENTO ===
    
    @app.route('/api/v1/route', methods=['POST', 'OPTIONS'])
    def api_calculate_route():
        if request.method == 'OPTIONS':
            return make_response("", 200)
        try:
            data = request.get_json(silent=True) or {}
            origin = Coordinate(data.get('origin_lat', 9.0), data.get('origin_lon', -79.5))
            destination = Coordinate(data.get('dest_lat', 8.98), data.get('dest_lon', -79.52))
            algorithm = RoutingAlgorithm[data.get('algorithm', 'A_STAR').upper()]
            objective = OptimizationObjective[data.get('objective', 'TIME').upper()]
            avoid_tolls = data.get('avoid_tolls', False)
            avoid_highways = data.get('avoid_highways', False)
            graph = generate_panama_network()
            traffic = TrafficManager()
            engine = RoutingEngine(graph, traffic)
            route = engine.find_route(origin, destination, algorithm, objective, avoid_tolls, avoid_highways)
            if route:
                return jsonify({"success": True, "route": route.to_geojson(), "distance_km": route.total_distance_km,
                               "time_min": route.total_time_minutes, "cost": route.total_cost,
                               "instructions": route.instructions})
            return jsonify({"success": False, "error": "No se encontró ruta"}), 404
        except Exception as e:
            log(f"Error en /api/v1/route: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/v1/gps/current', methods=['GET'])
    def api_get_gps():
        gps = TermuxGPS()
        loc = gps.get_current_location()
        if loc:
            return jsonify({"success": True, "latitude": loc.latitude, "longitude": loc.longitude,
                           "speed_kmh": gps.get_speed_kmh(), "source": "real" if gps.is_available else "simulated"})
        return jsonify({"success": False, "error": "GPS no disponible"}), 503

    @app.route('/api/v1/gps/update', methods=['POST', 'OPTIONS'])
    def api_update_gps():
        if request.method == 'OPTIONS':
            return make_response("", 200)
        global driver_state
        data = request.get_json(silent=True) or {}
        lat, lon = data.get('lat'), data.get('lon')
        if lat is not None and lon is not None:
            try:
                driver_state.update({"lat": float(lat), "lon": float(lon), "last_update": time.strftime('%H:%M:%S')})
                log(f"📍 Ubicación actualizada: {lat:.6f}, {lon:.6f}")
                return jsonify({"success": True, "location": driver_state})
            except ValueError:
                return jsonify({"success": False, "error": "lat/lon deben ser números"}), 400
        return jsonify({"success": False, "error": "Faltan parámetros lat/lon"}), 400

    @app.route('/api/v1/traffic', methods=['GET'])
    def api_get_traffic():
        traffic = TrafficManager()
        graph = generate_panama_network()
        edges = list(graph.edges.keys())[:10]
        conditions = {eid: traffic.get_current_condition(eid).name for eid in edges}
        return jsonify({"success": True, "edge_conditions": conditions, "timestamp": time.time()})

    # === ENDPOINTS NETWORK MONITOR ===
    
    @app.route("/api/v1/ping")
    def get_ping():
        def avg(d): return round(sum(d)/len(d), 2) if d else None
        return jsonify({
            "google": list(ping_data["google"]), "cloudflare": list(ping_data["cloudflare"]), "uber": list(ping_data["uber"]),
            "averages": {"google": avg(ping_data["google"]), "cloudflare": avg(ping_data["cloudflare"]), "uber": avg(ping_data["uber"])}
        })

    @app.route("/api/v1/network")
    def get_network():
        return jsonify({
            "status": network_state.get("status"), "winner": network_state.get("winner"),
            "latency": network_state.get("latency"), "last_check": network_state.get("last_check"),
            "internet_ok": check_internet()
        })

    @app.route("/api/v1/network/detailed")
    def get_network_detailed():
        return jsonify({
            "current_state": network_state, "top_servers": network_state.get("top_servers", []),
            "ping_history": {k: list(v) for k, v in ping_data.items()},
            "config": {"servers": SERVERS, "weights": {"ping": PING_WEIGHT, "http": HTTP_WEIGHT},
                      "thresholds": {"excellent": THRESHOLD_EXCELLENT, "stable": THRESHOLD_STABLE, "critical": THRESHOLD_CRITICAL}}
        })

    @app.route("/api/v1/driver/live")
    def get_driver_live():
        return jsonify({**driver_state, "network_status": network_state.get("status"),
                       "current_server": network_state.get("winner"), "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')})

    @app.route("/api/v1/address")
    def get_address():
        lat = request.args.get("lat", driver_state.get("lat"))
        lon = request.args.get("lon", driver_state.get("lon"))
        if lat is None or lon is None:
            return jsonify({"error": "Faltan parámetros lat/lon"}), 400
        try:
            import requests
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
            r = requests.get(url, headers={"User-Agent": "Symbiosis/3.1"}, timeout=5)
            r.raise_for_status()
            data = r.json()
            return jsonify({"lat": float(lat), "lon": float(lon), "address": data.get("display_name"),
                           "components": data.get("address", {}), "osm_id": data.get("osm_id")})
        except ImportError:
            return jsonify({"error": "requests no instalado"}), 503
        except Exception as e:
            log(f"Geocoding error: {e}", "WARN")
            return jsonify({"error": "geocoding falló", "details": str(e)}), 500

    # === ENDPOINT PROXY SEGURO ===
    
    @app.route("/internet/proxy", methods=["POST", "OPTIONS", "GET"])
    def internet_proxy():
        if request.method == "OPTIONS":
            return make_response("", 200)
        if request.method == "GET":
            return jsonify({"status": "active", "mode": "simulated", "message": "Proxy listo", "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')})
        data = request.get_json(silent=True) or {}
        url = data.get('url', '')
        method = data.get('method', 'GET').upper()
        headers = data.get('headers', {})
        payload = data.get('payload', data.get('data', {}))
        log(f"🌐 Proxy request: {method} {url or 'sin URL'}")
        if not url or data.get('simulate', True):
            return jsonify({"success": True, "simulated": True, "response": {"status": "ok", "data": "Respuesta simulada", "proxy_mode": "safe"}, "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')}), 200
        try:
            import requests
            if not url.startswith('https://'):
                return jsonify({"error": "Solo URLs HTTPS permitidas"}), 400
            allowed = ['api.reques.in', 'api.github.com', 'jsonplaceholder.typicode.com']
            domain = url.split('/')[2] if '//' in url else url.split('/')[0]
            if not any(ad in domain for ad in allowed):
                return jsonify({"error": f"Dominio no permitido: {domain}"}), 403
            start = time.time()
            resp = requests.request(method, url, headers=headers, json=payload if payload else None, timeout=10)
            latency = round(time.time() - start, 3)
            return jsonify({"success": True, "simulated": False, "status_code": resp.status_code, "latency_ms": latency,
                           "response": resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text[:2000],
                           "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')}), resp.status_code
        except ImportError:
            return jsonify({"error": "requests no instalado, usando modo simulado"}), 503
        except Exception as e:
            log(f"Proxy error: {e}", "ERROR")
            return jsonify({"error": str(e), "fallback": "simulated"}), 500

    # === ENDPOINTS UTILITARIOS ===
    
    @app.route('/health')
    def health_check():
        return jsonify({"status": "ok", "timestamp": time.time(), "gps_available": TermuxGPS()._check_termux_api(),
                       "network_status": network_state.get("status"), "internet_ok": check_internet()})

    @app.route('/')
    def index():
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Enrutamiento GPS - Servidor Principal</title>
        <style>body{{font-family:system-ui,sans-serif;background:#0a0a0f;color:#fff;padding:20px}}.card{{background:rgba(20,20,35,0.9);padding:20px;border-radius:12px;margin:10px 0;border:1px solid #4d94ff40}}.btn{{background:#2a5fb0;color:white;padding:10px 20px;border:none;border-radius:24px;cursor:pointer;margin:5px}}</style></head><body>
        <h1>🗺️ ENRUTAMIENTO GPS - SERVIDOR PRINCIPAL</h1>
        <div class="card"><h3>📡 Estado del Sistema</h3><p id="status">Cargando...</p></div>
        <div class="card"><h3>🔧 Endpoints Disponibles</h3>
        <ul><li>POST /api/v1/route - Calcular ruta</li><li>GET /api/v1/gps/current - Obtener GPS</li>
        <li>POST /api/v1/gps/update - Actualizar ubicación</li><li>GET /api/v1/traffic - Estado de tráfico</li>
        <li>GET /api/v1/network - Estado de red</li><li>GET /api/v1/ping - Historial de ping</li>
        <li>POST /internet/proxy - Proxy seguro</li></ul></div>
        <div class="card"><h3>🚀 Acciones Rápidas</h3>
        <button class="btn" onclick="fetch('/health').then(r=>r.json()).then(d=>document.getElementById('status').textContent=JSON.stringify(d,null,2))">🔄 Verificar Estado</button>
        <button class="btn" onclick="fetch('/api/v1/gps/current').then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">📍 Obtener GPS</button>
        </div><script>fetch('/health').then(r=>r.json()).then(d=>document.getElementById('status').textContent=JSON.stringify(d,null,2));</script></body></html>"""

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

# ============================================================================
# INICIALIZACIÓN Y PUNTO DE ENTRADA
# ============================================================================
def start_network_threads():
    threading.Thread(target=ping_loop, daemon=True, name="NetworkPing").start()
    threading.Thread(target=smart_network_loop_ultra, daemon=True, name="NetworkUltraPro").start()
    log("🚀 Hilos de monitoreo de red iniciados")

def main():
    global app, HTTP_PORT
    log("🚀 INICIANDO ENRUTAMIENTO GPS - SERVIDOR PRINCIPAL UNIFICADO")
    log("=" * 70)
    
    # Inicializar componentes
    gps = TermuxGPS()
    graph = generate_panama_network()
    traffic = TrafficManager()
    engine = RoutingEngine(graph, traffic)
    
    log(f"✅ Motor de enrutamiento inicializado")
    log(f"✅ GPS: {'Disponible' if gps.is_available else 'Simulado (termux-api no instalado)'}")
    log(f"✅ Red vial: {len(graph.nodes)} nodos, {len(graph.edges)} aristas")
    
    # Iniciar monitoreo de red si Flask está disponible
    if FLASK_AVAILABLE:
        start_network_threads()
        log(f"✅ Flask disponible - Servidor en http://0.0.0.0:{HTTP_PORT}")
        log(f"🔗 Acceso web: http://localhost:{HTTP_PORT}")
        log(f"🔑 API Key para rutas protegidas: {API_KEY}")
    
    # Si se ejecuta directamente sin argumentos, iniciar modo automático
    if len(sys.argv) == 1 and not FLASK_AVAILABLE:
        log("ℹ️  Ejecutando en modo terminal (sin Flask)")
        auto_routing_system()
    elif FLASK_AVAILABLE:
        log("🌐 Iniciando servidor Flask...")
        try:
            app.run(host="0.0.0.0", port=HTTP_PORT, debug=False, use_reloader=False, threaded=True)
        except OSError as e:
            if "Address already in use" in str(e):
                log(f"⚠️ Puerto {HTTP_PORT} ocupado, buscando alternativo...")
                nuevo_puerto = encontrar_puerto_libre(9000)
                if nuevo_puerto:
                    log(f"🔄 Reintentando en puerto {nuevo_puerto}")
                    app.run(host="0.0.0.0", port=nuevo_puerto, debug=False, use_reloader=False, threaded=True)
                else:
                    log("❌ No se encontró puerto disponible")
            else:
                raise
    else:
        log("❌ Flask no disponible y no hay argumentos - usando modo terminal")
        auto_routing_system()

def cleanup_and_exit(signum=None, frame=None):
    log("🛑 Recibida señal de terminación - Limpiando recursos...")
    if FLASK_AVAILABLE:
        # Flask maneja su propia limpieza
        pass
    log("✅ Sistema detenido limpiamente")
    if signum is not None:
        sys.exit(0)

# Configurar señales de terminación
try:
    import signal
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)
except:
    pass

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================
if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("🗺️  ENRUTAMIENTO GPS - SERVIDOR PRINCIPAL", flush=True)
    print("=" * 70, flush=True)
    print(f"📡 Puerto API: {HTTP_PORT}", flush=True)
    print(f"🌐 URL: http://localhost:{HTTP_PORT}", flush=True)
    print(f"🔐 API Key: {API_KEY} (para endpoints protegidos)", flush=True)
    print(f"📱 Termux: {'✅ Detectado' if IS_TERMUX else '❌ No detectado'}", flush=True)
    print("=" * 70, flush=True)
    
    try:
        main()
    except KeyboardInterrupt:
        cleanup_and_exit()
    except Exception as e:
        log(f"❌ ERROR CRÍTICO: {e}", "ERROR")
        traceback.print_exc()
        cleanup_and_exit()
