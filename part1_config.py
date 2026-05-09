# ================================================================================
# SECCION 1: IMPORTACIONES UNIFICADAS
# ================================================================================
from __future__ import annotations
import os, sys, json, time, uuid, hashlib, threading, random, math, copy, heapq
import re, inspect, ast, gc, traceback, string, subprocess, signal, socket
import secrets, textwrap
from typing import Dict, List, Optional, Tuple, Any, Callable, Union, Set, TYPE_CHECKING
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from collections import deque, defaultdict, Counter
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import urlparse
from contextlib import contextmanager
from fnmatch import fnmatch

# ================================================================================
# SECCION 1.1: REGISTRO COMPARTIDO DE DATOS (POTENCIADO)
# ================================================================================
class SharedDataRegistry:
    """Registro central de datos compartidos entre partes del sistema."""
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        # --- BLOQUE: SINGLETON THREAD-SAFE ---
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self._data: Dict[str, Any] = {}
            self._callbacks: Dict[str, List[Tuple[str, Callable]]] = defaultdict(list)
            self._initialized = True

    def set(self, key: str, value: Any, notify: bool = True) -> bool:
        # --- BLOQUE: ESCRITURA CON COPIA DEFENSIVA ---
        with self._lock:
            try:
                self._data[key] = copy.deepcopy(value)
                if notify:
                    self._trigger_callbacks(key, value)
                return True
            except Exception:
                return False

    def get(self, key: str, default: Any = None) -> Any:
        # --- BLOQUE: LECTURA SEGURA ---
        with self._lock:
            return copy.deepcopy(self._data.get(key, default))

    def get_all(self, pattern: Optional[str] = None) -> Dict[str, Any]:
        # --- BLOQUE: LECTURA MASIVA CON FILTRO ---
        with self._lock:
            if pattern is None:
                return {k: copy.deepcopy(v) for k, v in self._data.items()}
            return {k: copy.deepcopy(v) for k, v in self._data.items() if fnmatch(k, pattern)}

    def on_change(self, key_pattern: str, callback: Callable) -> str:
        # --- BLOQUE: SUSCRIPCION ---
        with self._lock:
            callback_id = str(hash(callback))[:8]
            self._callbacks[key_pattern].append((callback_id, callback))
            return callback_id

    def _trigger_callbacks(self, key: str, value: Any) -> None:
        # --- BLOQUE: NOTIFICACION ASINCRONA SEGURA ---
        for pattern, callbacks in self._callbacks.items():
            if fnmatch(key, pattern):
                for _, cb in callbacks:
                    try:
                        cb(key, value)
                    except Exception:
                        pass

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())

# ================================================================================
# IMPORTACION DE MODULO DE ENRUTAMIENTO GPS (PARTE 9)
# ================================================================================
try:
    import enrutamiento_gps_unificado as routing
    ROUTING_AVAILABLE = True
except ImportError:
    ROUTING_AVAILABLE = False
    routing = None
    print("[WARN] Modulo de enrutamiento GPS no disponible", flush=True)

# ================================================================================
# FUNCIONES UTILITARIAS GLOBALES (sin dependencias externas)
# ================================================================================
try:
    import numpy as np
except ImportError:
    np = None

try:
    import requests
except ImportError:
    requests = None

try:
    from flask import request, jsonify
except ImportError:
    request = None
    jsonify = None

def softmax(x):
    """
    Calcula la funcion softmax con estabilidad numerica.
    Convierte un vector de scores en probabilidades que suman 1.
    """
    # --- BLOQUE: MANEJO NUMPY ---
    if np is not None and isinstance(x, np.ndarray):
        if x.size == 0:
            return np.array([])
        if x.size == 1:
            return np.array([1.0])
        max_x = np.max(x)
        exp_x = np.exp(x - max_x)
        sum_exp_x = np.sum(exp_x)
        if sum_exp_x == 0:
            return np.ones_like(x) / len(x)
        return exp_x / sum_exp_x
    
    # --- BLOQUE: MANEJO LISTAS/TUPLAS ---
    if not x:
        return []
    if isinstance(x, tuple):
        x = list(x)
    if len(x) == 1:
        return [1.0]
    max_x = max(x)
    exp_x = [math.exp(i - max_x) for i in x]
    sum_exp_x = sum(exp_x)
    if sum_exp_x == 0:
        return [1.0 / len(x) for _ in x]
    return [i / sum_exp_x for i in exp_x]

def sigmoid(x):
    """Funcion sigmoide para activaciones."""
    try:
        return 1 / (1 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0

def relu(x):
    """Funcion ReLU."""
    return max(0.0, x)

def tanh(x):
    """Funcion tangente hiperbolica."""
    return math.tanh(x)

# Configuracion de garbage collector optimizada para Termux
gc.set_threshold(700, 10, 10)

if TYPE_CHECKING:
    pass

# ================================================================================
# SECCION 2: CONFIGURACION GLOBAL UNIFICADA
# ================================================================================
class GlobalConfig:
    """Configuracion centralizada del sistema - adaptable a recursos."""
    IS_TERMUX = os.getenv('TERMUX_VERSION') is not None or 'com.termux' in os.getenv('PATH', '')
    IS_LOW_MEMORY = IS_TERMUX
    IS_ANDROID = os.path.exists('/system/bin/')
    
    # Protocolo General
    MAX_ROUNDS = 5
    TIMEOUT_PER_ROUND = 30 if not IS_TERMUX else 15
    MIN_UTILITY_THRESHOLD = 0.6
    
    # Agentes
    MAX_CONCURRENT_NEGOTIATIONS = 3 if IS_LOW_MEMORY else 10
    REPUTATION_DECAY = 0.95
    
    # Blockchain (opcional)
    USE_BLOCKCHAIN = False
    SMART_CONTRACT_AUTO_GENERATE = not IS_TERMUX
    
    # LLM
    LLM_MODEL = "gpt-4" if not IS_TERMUX else "mock-llm"
    LLM_TEMPERATURE = 0.3
    
    # RL - Parametros unificados
    RL_LEARNING_RATE = 0.1
    RL_DISCOUNT_FACTOR = 0.95
    RL_EXPLORATION_EPSILON = 1.0
    RL_EPSILON_MIN = 0.1
    RL_EPSILON_DECAY = 0.995
    RL_USE_ELIGIBILITY = False
    RL_LAMBDA_TRACE = 0.9
    RL_TRAINING_EPISODES = 100 if IS_LOW_MEMORY else 500
    RL_EVAL_INTERVAL = 20 if IS_LOW_MEMORY else 50
    
    # MATCHING
    MATCHING_MIN_SCORE = 0.5
    MATCHING_MAX_DISTANCE_KM = 50.0
    MATCHING_TOP_K = 10
    MATCHING_CELL_SIZE_KM = 10.0
    MATCHING_ALGORITHM = "greedy" if IS_LOW_MEMORY else "hungarian"
    
    # Logging
    LOG_ENABLED = True
    LOG_FILE = os.path.expanduser("~/x/logs/symbiosis_unified.log")
    LOG_VERBOSE = not IS_TERMUX
    
    # Uber API
    UBER_SANDBOX = os.getenv("UBER_SANDBOX", "true").lower() == "true"
    UBER_BASE_URL = "https://sandbox-api.uber.com/v1.2" if UBER_SANDBOX else "https://api.uber.com/v1.2"
    
    # ML / Prediction
    USE_DEEP_LEARNING = False
    PREDICTION_HORIZON = 30
    MODEL_CACHE_DIR = Path.home() / ".symbiosis" / "models"
    DATA_CACHE_DIR = Path.home() / ".symbiosis" / "data"
    
    # CEOIA / DAIMON
    DAIMON_BRAIN_FILE = Path.home() / "daimon_brain.json"
    STATE_FILE = Path.home() / "state.json"
    CORAZON_FILE = Path("/sdcard/uber_coint")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-14e93c5071e14eaf8b27e58c968f5f84")
    DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
    
    # Radar
    RADAR_CONFIG = {
        "tarifa_minima_usd": 3.13,
        "eta_maxima_recogida_min": 4,
        "ingreso_minimo_por_hora_usd": 9.0,
        "ingreso_optimo_por_hora_usd": 15.0,
        "zona_roja_bonus": 100.0,
        "zona_naranja_bonus": 50.0,
        "hora_pico_bonus": 1.3,
        "madrugada_penalty": 0.7,
    }
    
    ALGO_WEIGHTS = {
        'tasa_de_aceptacion': 5.0, 'tasa_de_finalizacion': 10.0,
        'calificacion_promedio': 2.0, 'viajes_completados': 0.1,
        'tiempo_en_linea': 0.5, 'tasa_de_cancelacion': -20.0,
        'idle_time_ratio': -10.0, 'peak_hours_ratio': 3.0,
        'distance_traveled': 0.05, 'distancia': 0.2,
        'duracion': 0.01, 'tarifa': 1.0, 'tiempo_de_espera': -0.5,
        'viral_score_bonus': 50.0, 'engagement_rate': 15.0,
        'share_ratio': 25.0, 'bonificacion_creatividad': 40.0,
        'bonificacion_innovacion': 30.0, 'tasa_adaptacion': 25.0,
    }

# ================================================================================
# SECCION 3: LOGGER UNIFICADO
# ================================================================================
def log_event(text: str, level: str = "INFO"):
    """Logger unificado con soporte para Termux."""
    # --- BLOQUE: FORMATEO Y SALIDA ---
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] [{level}] {text}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    
    # --- BLOQUE: PERSISTENCIA SEGURA ---
    if GlobalConfig.LOG_ENABLED:
        try:
            log_dir = os.path.dirname(GlobalConfig.LOG_FILE)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(GlobalConfig.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
        except (PermissionError, OSError) as e:
            if GlobalConfig.LOG_VERBOSE:
                sys.stderr.write(f"[LOG WARN] {GlobalConfig.LOG_FILE}: {e}\n")

def log_banner(title: str, icon: str = ""):
    """Imprime banner decorativo para eventos importantes."""
    log_event(f"\n{'=' * 40}\n{icon} {title}\n{'=' * 40}")

# Alias para compatibilidad con CEOIA y Orchestrator
log = log_event

# ================================================================================
# SECCION 4: INICIALIZACION DE DIRECTORIOS
# ================================================================================
def init_system():
    """Inicializa directorios necesarios para el sistema."""
    dirs = [
        os.path.expanduser("~/.symbiosis/models"),
        os.path.expanduser("~/.symbiosis/data"),
        os.path.expanduser("~/x/logs")
    ]
    for d in dirs:
        try:
            os.makedirs(d, exist_ok=True)
        except (PermissionError, OSError) as e:
            sys.stderr.write(f"[WARN] No se pudo crear {d}: {e}\n")

init_system()

# ================================================================================
# SECCION 4.1: MONITOR DE SALUD DE HILOS
# ================================================================================
def monitor_thread_health(timeout_seconds=10.0, log_fn=None):
    """Verifica estado de hilos activos, detecta zombies y reporta bloques."""
    if log_fn is None:
        log_fn = print
    
    # --- BLOQUE: ESCANEO DE HILOS ---
    alive = []
    unknown_count = 0
    for t in threading.enumerate():
        if t.is_alive():
            name = t.name or "UNKNOWN"
            if name == "UNKNOWN":
                unknown_count += 1
            alive.append({"name": name, "daemon": t.daemon, "ident": t.ident})
    
    log_fn(f"[{datetime.now().strftime('%H:%M:%S')}] HILOS: {len(alive)} vivos, {unknown_count} sin nombre")
    return alive

# ================================================================================
# SECCION 5: ESTRUCTURAS DE DATOS FUNDAMENTALES
# ================================================================================
class NegotiationStatus(Enum):
    PENDING = auto(); ACTIVE = auto(); ACCEPTED = auto(); REJECTED = auto()
    EXPIRED = auto(); DISPUTED = auto(); ENFORCED = auto()

class AgentRole(Enum):
    INITIATOR = auto(); RESPONDER = auto(); ARBITER = auto(); WITNESS = auto()

class RideStatus(Enum):
    PROCESSING = "processing"; ACCEPTED = "accepted"; ARRIVING = "arriving"
    IN_PROGRESS = "in_progress"; DRIVER_CANCELED = "driver_canceled"
    RIDER_CANCELED = "rider_canceled"; COMPLETED = "completed"

class RLAlgorithm(Enum):
    Q_LEARNING = auto(); SARSA = auto(); EXPECTED_SARSA = auto()
    POLICY_GRADIENT = auto(); ACTOR_CRITIC = auto(); DQN = auto()

class ActionType(Enum):
    ACCEPT_OFFER = "accept"; REJECT_OFFER = "reject"
    COUNTER_OFFER = "counter"; WAIT = "wait"
    TAKE_ALTERNATIVE = "alternative"; WAIT_TRAFFIC = "wait_traffic"
    REROUTE = "reroute"
    EXPLORE = "explore"; EXPLOIT = "exploit"; LEARN = "learn"

class MatchingAlgorithm(Enum):
    HUNGARIAN = auto(); GALE_SHAPLEY = auto(); GREEDY_BEST_MATCH = auto()
    TOP_K_CANDIDATES = auto(); GEO_CLUSTER = auto()

class MatchStatus(Enum):
    PENDING = "pending"; PROPOSED = "proposed"; ACCEPTED = "accepted"
    REJECTED = "rejected"; CONFIRMED = "confirmed"; EXPIRED = "expired"

@dataclass
class UtilityProfile:
    # --- BLOQUE: ATRIBUTOS ---
    price_weight: float = 0.4
    time_weight: float = 0.2
    quality_weight: float = 0.2
    reputation_weight: float = 0.1
    flexibility_weight: float = 0.1
    min_acceptable_price: float = 0.0
    max_acceptable_price: float = float('inf')
    deadline: Optional[datetime] = None
    required_quality_level: int = 3

    def __post_init__(self):
        # --- BLOQUE: VALIDACION Y NORMALIZACION ---
        for attr in ['price_weight', 'time_weight', 'quality_weight', 'reputation_weight', 'flexibility_weight']:
            val = getattr(self, attr)
            if val is None:
                setattr(self, attr, {'price_weight': 0.4, 'time_weight': 0.2, 'quality_weight': 0.2, 'reputation_weight': 0.1, 'flexibility_weight': 0.1}[attr])
        for attr in ['min_acceptable_price', 'max_acceptable_price']:
            val = getattr(self, attr)
            if val is None:
                setattr(self, attr, 0.0 if attr == 'min_acceptable_price' else float('inf'))
        self.required_quality_level = int(self.required_quality_level) if self.required_quality_level is not None else 3
        total = sum([self.price_weight, self.time_weight, self.quality_weight, self.reputation_weight, self.flexibility_weight])
        if abs(total - 1.0) > 0.001 and total > 0:
            for attr in ['price_weight', 'time_weight', 'quality_weight', 'reputation_weight', 'flexibility_weight']:
                setattr(self, attr, getattr(self, attr) / total)

    def validate(self) -> bool:
        total = sum([self.price_weight, self.time_weight, self.quality_weight, self.reputation_weight, self.flexibility_weight])
        return abs(total - 1.0) < 0.001

    def calculate_utility(self, offer: 'Offer') -> float:
        # --- BLOQUE: CALCULO DE UTILIDAD MULTI-FACTOR ---
        if offer is None:
            return 0.0
        price = getattr(offer, 'price', 0.0)
        delivery_time = getattr(offer, 'delivery_time', 0.0)
        quality_level = getattr(offer, 'quality_level', 3)
        counterparty_reputation = getattr(offer, 'counterparty_reputation', 0.5)
        flexibility_score = getattr(offer, 'flexibility_score', 0.5)
        
        if price > self.max_acceptable_price:
            price_utility = 0.0
        elif price < self.min_acceptable_price:
            price_utility = 1.0
        else:
            range_size = self.max_acceptable_price - self.min_acceptable_price
            price_utility = 1.0 - ((price - self.min_acceptable_price) / range_size) if range_size > 0 else (1.0 if price <= self.max_acceptable_price else 0.0)
        
        if self.deadline and delivery_time:
            time_remaining = (self.deadline - datetime.now(timezone.utc)).total_seconds()
            time_utility = max(0.0, min(1.0, 1.0 - (delivery_time / time_remaining))) if time_remaining > 0 else 0.0
        else:
            time_utility = 0.5
            
        quality_utility = min(quality_level / self.required_quality_level, 1.0) if self.required_quality_level > 0 else 1.0
        reputation_utility = counterparty_reputation if counterparty_reputation is not None else 0.5
        flexibility_utility = flexibility_score if flexibility_score is not None else 0.5
        
        utility = (self.price_weight * price_utility + self.time_weight * time_utility + 
                   self.quality_weight * quality_utility + self.reputation_weight * reputation_utility + 
                   self.flexibility_weight * flexibility_utility)
        return max(0.0, min(1.0, utility)) if not (math.isnan(utility) or math.isinf(utility)) else 0.0

@dataclass
class Offer:
    # --- BLOQUE: ATRIBUTOS ---
    offer_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    round_number: int = 1
    price: float = 0.0
    delivery_time: float = 0.0
    quality_level: int = 3
    payment_terms: str = "immediate"
    cancellation_policy: str = "standard"
    proposed_by: str = ""
    proposed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    counterparty_reputation: Optional[float] = None
    flexibility_score: Optional[float] = None
    rationale: str = ""
    concessions_made: List[str] = field(default_factory=list)

    def __post_init__(self):
        defaults = {
            'price': 0.0, 'delivery_time': 0.0, 'quality_level': 3,
            'proposed_by': '', 'rationale': '', 'concessions_made': [],
            'payment_terms': 'immediate', 'cancellation_policy': 'standard'
        }
        for k, v in defaults.items():
            if getattr(self, k) is None:
                setattr(self, k, v)

    def clone_with_changes(self, **changes) -> 'Offer':
        new_offer = copy.deepcopy(self)
        for key, value in changes.items():
            if hasattr(new_offer, key) and value is not None:
                setattr(new_offer, key, value)
        new_offer.offer_id = str(uuid.uuid4())[:8]
        new_offer.round_number += 1
        return new_offer

    def to_contract_terms(self) -> Dict[str, Any]:
        return {
            "price": self.price, "delivery_time": self.delivery_time,
            "quality_level": self.quality_level,
            "payment_terms": self.payment_terms,
            "cancellation_policy": self.cancellation_policy
        }

@dataclass
class NegotiationMessage:
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    negotiation_id: str = ""
    round_number: int = 1
    sender_id: str = ""
    receiver_id: str = ""
    message_type: str = ""
    structured_content: Optional[Offer] = None
    natural_content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sentiment_score: float = 0.0
    embedding: Optional[List[float]] = None

    def __post_init__(self):
        for k in ['negotiation_id', 'sender_id', 'receiver_id', 'message_type', 'natural_content']:
            if getattr(self, k) is None:
                setattr(self, k, "")
        if self.sentiment_score is None:
            self.sentiment_score = 0.0

@dataclass
class NegotiationSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    agent_a_id: str = ""
    agent_b_id: str = ""
    domain: str = ""
    item_description: str = ""
    base_terms: Dict[str, Any] = field(default_factory=dict)
    status: NegotiationStatus = NegotiationStatus.PENDING
    current_round: int = 0
    max_rounds: int = 5
    messages: List[NegotiationMessage] = field(default_factory=list)
    offers_history: List[Offer] = field(default_factory=list)
    final_offer: Optional[Offer] = None
    final_utility_a: float = 0.0
    final_utility_b: float = 0.0
    agreement_timestamp: Optional[datetime] = None
    smart_contract_address: Optional[str] = None

    def __post_init__(self):
        for k in ['base_terms', 'messages', 'offers_history']:
            if getattr(self, k) is None:
                setattr(self, k, [])
        if self.status is None:
            self.status = NegotiationStatus.PENDING
        for k in ['agent_a_id', 'agent_b_id', 'domain', 'item_description']:
            if getattr(self, k) is None:
                setattr(self, k, "")

    def get_last_offer(self) -> Optional[Offer]:
        return self.offers_history[-1] if self.offers_history else None

    def is_expired(self) -> bool:
        if not self.messages:
            return False
        last_msg_time = self.messages[-1].timestamp
        timeout = timedelta(seconds=GlobalConfig.TIMEOUT_PER_ROUND * 2)
        return datetime.now(timezone.utc) - last_msg_time > timeout

@dataclass
class GeoLocation:
    latitude: float = 0.0
    longitude: float = 0.0
    accuracy: Optional[float] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.latitude is None: self.latitude = 0.0
        if self.longitude is None: self.longitude = 0.0
        if self.accuracy is None: self.accuracy = 0.0
        if self.timestamp is None: self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, float]:
        return {"latitude": self.latitude, "longitude": self.longitude}

    def is_valid(self) -> bool:
        return -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180

    def distance_to(self, other: 'GeoLocation') -> float:
        R = 6371.0
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def to_hex_cell(self, resolution: int = 7) -> str:
        try:
            import h3
            return h3.latlng_to_cell(self.latitude, self.longitude, resolution)
        except ImportError:
            lat_idx = int((self.latitude + 90) / (5 / (2 ** resolution)))
            lon_idx = int((self.longitude + 180) / (5 / (2 ** resolution)))
            return f"sq:{lat_idx}:{lon_idx}"

@dataclass
class PriceEstimate:
    product_id: str = ""
    display_name: str = ""
    estimate: str = "0"
    low_estimate: float = 0.0
    high_estimate: float = 0.0
    surge_multiplier: float = 1.0
    duration: int = 0
    distance: float = 0.0

    def __post_init__(self):
        defaults = {
            'product_id': '', 'display_name': '', 'estimate': '0',
            'low_estimate': 0.0, 'high_estimate': 0.0,
            'surge_multiplier': 1.0, 'duration': 0, 'distance': 0.0
        }
        for k, v in defaults.items():
            if getattr(self, k) is None:
                setattr(self, k, v)

    @property
    def average_estimate(self) -> float:
        return (self.low_estimate + self.high_estimate) / 2

    @property
    def is_surge(self) -> bool:
        return self.surge_multiplier > 1.0

@dataclass
class TimeEstimate:
    product_id: str = ""
    display_name: str = ""
    estimate: int = 0

    def __post_init__(self):
        if self.product_id is None: self.product_id = ""
        if self.display_name is None: self.display_name = ""

@dataclass
class RadarOpportunity:
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    zone_id: str = ""
    zone_name: str = ""
    location: Optional[GeoLocation] = None
    demand_score: float = 0.0
    supply_count: int = 0
    request_count: int = 0
    avg_fare: float = 0.0
    surge_multiplier: float = 1.0
    estimated_earnings: float = 0.0
    hourly_rate_potential: float = 0.0
    avg_pickup_time: int = 0
    avg_trip_duration: int = 0
    time_to_hotspot: int = 0
    priority_score: float = 0.0
    predicted_demand_30min: float = 0.0
    prediction_confidence: float = 0.0
    recommendation: str = ""

    def __post_init__(self):
        for k in ['zone_id', 'zone_name', 'recommendation']:
            if getattr(self, k) is None:
                setattr(self, k, "")

@dataclass
class RLState:
    state_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    features: Dict[str, float] = field(default_factory=dict)
    negotiation_round: int = 0
    my_utility: float = 0.0
    opponent_utility: float = 0.0
    time_pressure: float = 0.0
    remaining_rounds: int = 5
    opponent_strategy_estimated: str = "unknown"
    trip_distance_km: float = 0.0
    cumulative_km_today: float = 0.0
    avg_km_per_trip: float = 0.0
    mileage_risk: float = 0.5
    is_rush_hour: bool = False
    surge_multiplier: float = 1.0
    zone_id: str = "unknown"

    def to_vector(self) -> List[float]:
        base = [
            self.negotiation_round / 5.0,
            self.my_utility,
            self.opponent_utility,
            self.time_pressure,
            self.remaining_rounds / 5.0,
            hash(self.opponent_strategy_estimated) % 10 / 10.0
        ] + list(self.features.values())
        base.extend([
            min(1.0, self.trip_distance_km / 50.0),
            min(1.0, self.cumulative_km_today / 200.0),
            min(1.0, self.avg_km_per_trip / 30.0),
            self.mileage_risk
        ])
        return base

    def discretize(self, bins: int = 10) -> str:
        parts = [
            str(min(bins-1, int(self.negotiation_round * bins / 5))),
            str(min(bins-1, int(self.my_utility * bins))),
            str(min(bins-1, int(self.opponent_utility * bins))),
            str(min(bins-1, int(self.time_pressure * bins))),
            str(min(bins-1, int(self.remaining_rounds * bins / 5)))
        ]
        return "|".join(parts)

    @classmethod
    def from_negotiation_session(cls, session: NegotiationSession, agent_id: str) -> 'RLState':
        last_offer = session.get_last_offer()
        my_util = last_offer.price if last_offer and last_offer.proposed_by == agent_id else 0.0
        return cls(
            state_id=session.session_id,
            negotiation_round=session.current_round,
            my_utility=my_util,
            opponent_utility=0.5,
            time_pressure=session.current_round / session.max_rounds if session.max_rounds > 0 else 0.0,
            remaining_rounds=max(0, session.max_rounds - session.current_round),
            features={'domain_hash': hash(session.domain) % 100}
        )

@dataclass
class RLAction:
    action_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: ActionType = ActionType.WAIT
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_offer_modifications(self) -> Dict[str, Any]:
        mods = {}
        if self.action_type == ActionType.ACCEPT_OFFER:
            mods['accept'] = True
        elif self.action_type == ActionType.REJECT_OFFER:
            mods['reject'] = True
        elif self.action_type == ActionType.COUNTER_OFFER:
            if 'price_adjustment' in self.parameters:
                mods['price'] = self.parameters['price_adjustment']
            if 'time_adjustment' in self.parameters:
                mods['delivery_time'] = self.parameters['time_adjustment']
        return mods

    def __post_init__(self):
        if not self.action_id:
            self.action_id = str(uuid.uuid4())[:8]

@dataclass
class QTableEntry:
    q_value: float = 0.0
    visit_count: int = 0
    last_updated: Optional[datetime] = None

@dataclass
class PolicyParams:
    weights: Dict[str, List[float]] = field(default_factory=dict)
    biases: Dict[str, float] = field(default_factory=dict)

    def initialize_random(self, input_size: int, output_size: int, hidden_sizes: List[int]):
        sizes = [input_size] + hidden_sizes + [output_size]
        for i in range(len(sizes) - 1):
            layer_name = f"layer_{i}"
            scale = math.sqrt(2.0 / (sizes[i] + sizes[i+1]))
            self.weights[layer_name] = [random.uniform(-scale, scale) for _ in range(sizes[i] * sizes[i+1])]
            self.biases[layer_name] = 0.0

@dataclass
class MatchingAgent:
    agent_id: str = ""
    name: str = ""
    location: Optional[Tuple[float, float]] = None
    preferences: Dict[str, float] = field(default_factory=dict)
    required_attributes: Set[str] = field(default_factory=set)
    acceptable_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    rating: float = 0.5
    total_transactions: int = 0
    successful_matches: int = 0
    last_active: Optional[datetime] = None

    def __post_init__(self):
        if self.last_active is None:
            self.last_active = datetime.now(timezone.utc)

    def to_features(self) -> Dict[str, float]:
        return {
            "price": self.preferences.get("price", 0.5),
            "time": self.preferences.get("time", 0.5),
            "quality": self.preferences.get("quality", 0.5),
            "rating": self.rating,
            "activity": SimilarityMetrics.time_decay(self.last_active) if self.last_active else 0.5
        }

@dataclass
class MatchingOffer:
    offer_id: str = ""
    agent_id: str = ""
    price: float = 0.0
    delivery_time: float = 0.0
    quality_level: int = 3
    category: str = "general"
    location: Optional[Tuple[float, float]] = None
    expiry: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_features(self) -> Dict[str, float]:
        return {
            "price": self.price / 200.0,
            "time": min(1.0, self.delivery_time / 60.0),
            "quality": self.quality_level / 5.0
        }

@dataclass
class Match:
    match_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_a: str = ""
    agent_b: str = ""
    offer_a_id: str = ""
    offer_b_id: str = ""
    score: float = 0.0
    status: MatchStatus = MatchStatus.PENDING
    algorithm_used: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    accepted_at: Optional[datetime] = None
    similarity_breakdown: Dict[str, float] = field(default_factory=dict)

@dataclass
class MatchingRequest:
    request_id: str = ""
    agent: MatchingAgent = field(default_factory=MatchingAgent)
    offer: MatchingOffer = field(default_factory=MatchingOffer)
    min_score_threshold: float = GlobalConfig.MATCHING_MIN_SCORE
    max_distance_km: float = GlobalConfig.MATCHING_MAX_DISTANCE_KM
    max_results: int = GlobalConfig.MATCHING_TOP_K
    categories: List[str] = field(default_factory=list)

@dataclass
class Experience:
    state: Any
    action: int
    reward: float
    next_state: Any
    done: bool
    priority: float = 1.0
    n_step: int = 1
    gamma_n: float = 0.99

@dataclass
class NStepTransition:
    states: List[Any] = field(default_factory=list)
    actions: List[int] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    final_state: Any = None
    done: bool = False

# ================================================================================
# SECCION 6: HYPERNUMBERADVANCED
# ================================================================================
class HyperNumberAdvanced:
    def __init__(self, initial_value: float = 0.0):
        self.mode = "real"
        self.sign = 1 if initial_value >= 0 else -1
        self.value = abs(float(initial_value))
        self.log10_val = 0.0
        self.formula = None
        self.formula_tree = None
        self.threshold_real_to_log = 1e308
        self.threshold_log_to_formula = 1e6
        self._cached_value = None
        self._dirty = True

    def _invalidate(self):
        self._cached_value = None
        self._dirty = True

    def add(self, x):
        # --- BLOQUE: LOGICA DE ADICION SEGUN MODO ---
        x = x.to_float_approx() if isinstance(x, HyperNumberAdvanced) else float(x)
        x_sign = 1 if x >= 0 else -1
        x = abs(x)
        if self.mode == "real":
            signed_val = self.sign * self.value + x_sign * x
            self.sign = 1 if signed_val >= 0 else -1
            self.value = abs(signed_val)
            if self.value > self.threshold_real_to_log:
                self._enter_log_mode()
        elif self.mode == "log":
            if x != 0:
                lx = math.log10(x)
                if lx > self.log10_val:
                    self.log10_val, lx = lx, self.log10_val
                self.log10_val += math.log10(1 + 10 ** (lx - self.log10_val))
                if self.log10_val > self.threshold_log_to_formula:
                    self._enter_formula_mode()
        else:
            self._formula_add(x_sign * x)
        self._invalidate()

    def multiply(self, x):
        # --- BLOQUE: LOGICA DE MULTIPLICACION SEGUN MODO ---
        x = x.to_float_approx() if isinstance(x, HyperNumberAdvanced) else float(x)
        if x == 0:
            self.mode = "real"
            self.sign = 1
            self.value = 0.0
            self.formula = None
            self.formula_tree = None
            self._invalidate()
            return
        if x < 0:
            self.sign *= -1
            x = abs(x)
        if self.mode == "real":
            self.value *= x
            if self.value > self.threshold_real_to_log:
                self._enter_log_mode()
        elif self.mode == "log":
            self.log10_val += math.log10(x)
            if self.log10_val > self.threshold_log_to_formula:
                self._enter_formula_mode()
        else:
            self._formula_mul(x)
        self._invalidate()

    def _enter_log_mode(self):
        if self.value != 0:
            self.log10_val = math.log10(self.value)
        else:
            self.log10_val = float("-inf")
        self.mode = "log"

    def _enter_formula_mode(self):
        self.mode = "formula"
        self.formula = {"type": "exp_power", "base": 10, "exponent": self.log10_val}
        self.formula_tree = FormulaNode("pow", FormulaNode("const", 10.0), FormulaNode("const", self.log10_val))

    def _formula_add(self, x):
        if self.formula_tree:
            self.formula_tree = FormulaNode("add", self.formula_tree, FormulaNode("const", x))
        else:
            self.formula_tree = FormulaNode("const", x)

    def _formula_mul(self, x):
        if self.formula_tree:
            self.formula_tree = FormulaNode("mul", self.formula_tree, FormulaNode("const", x))
        else:
            self.formula_tree = FormulaNode("const", x)

    def display(self) -> str:
        if self.mode == "real":
            return f"{self.sign * self.value:.6g}"
        elif self.mode == "log":
            if self.log10_val == float("-inf"):
                return "0"
            return ("-" if self.sign < 0 else "") + f"~ 10^{self.log10_val:.6f}"
        else:
            return ("-" if self.sign < 0 else "") + (self.formula_tree.to_string() if self.formula_tree else "INF")

    def elevate_to_double_exp(self):
        if self.mode == "log":
            self.mode = "formula"
            self.formula = {"type": "double_exp", "exponent": self.log10_val}
            self.formula_tree = FormulaNode("pow", FormulaNode("const", 10.0), FormulaNode("pow", FormulaNode("const", 10.0), FormulaNode("const", self.log10_val)))
        elif self.mode == "formula" and self.formula_tree:
            self.formula_tree = FormulaNode("pow", FormulaNode("const", 10.0), self.formula_tree)
        self._invalidate()

    def gamma_transform(self):
        x = abs(self.to_float_approx())
        if x > 170:
            self.mode = "formula"
            self.formula = {"type": "gamma", "x": x}
            self.formula_tree = FormulaNode("func", "gamma", FormulaNode("const", x))
        else:
            try:
                val = math.gamma(x)
                self.mode = "real"
                self.sign = 1
                self.value = val
                self.formula = None
                self.formula_tree = None
            except (OverflowError, ValueError):
                self.mode = "formula"
                self.formula = {"type": "gamma", "x": x}
                self.formula_tree = FormulaNode("func", "gamma", FormulaNode("const", x))
        self._invalidate()

    def zeta_transform(self, s):
        self.mode = "formula"
        self.formula = {"type": "zeta", "s": s}
        self.formula_tree = FormulaNode("func", "zeta", FormulaNode("const", s))
        self._invalidate()

    def erf_transform(self):
        x = self.to_float_approx()
        self.mode = "formula"
        self.formula = {"type": "erf", "x": x}
        self.formula_tree = FormulaNode("func", "erf", FormulaNode("const", x))
        self._invalidate()

    def subtract(self, x):
        val = x if isinstance(x, (int, float)) else x.to_float_approx()
        self.add(-val)

    def divide(self, x):
        val = x if isinstance(x, (int, float)) else x.to_float_approx()
        if val == 0:
            return
        self.multiply(1.0 / val)

    def power(self, exp):
        if self.mode == "real":
            self.value **= exp
            if self.value > self.threshold_real_to_log:
                self._enter_log_mode()
        elif self.mode == "log":
            self.log10_val *= exp
            if self.log10_val > self.threshold_log_to_formula:
                self._enter_formula_mode()
        self._invalidate()

    def to_float_approx(self) -> float:
        if self._cached_value is not None and not self._dirty:
            return self._cached_value
        if self.mode == "real":
            val = self.sign * self.value
        elif self.mode == "log":
            if self.log10_val == float("-inf"):
                val = 0.0
            else:
                val = self.sign * (10 ** self.log10_val)
        else:
            val = self.sign * (self.formula_tree.evaluate() if self.formula_tree else float("inf"))
        if math.isnan(val) or math.isinf(val):
            val = 0.0
        self._cached_value = val
        self._dirty = False
        return val

    def __repr__(self):
        return f"HyperNumberAdvanced({self.display()})"

# ================================================================================
# SECCION 7: FORMULANODE
# ================================================================================
class FormulaNode:
    __slots__ = ("op", "args", "_cached", "_dirty")

    def __init__(self, op: str, *args):
        self.op, self.args, self._cached, self._dirty = op, args, None, True

    def evaluate(self) -> float:
        # --- BLOQUE: EVALUACION CON CACHE ---
        if not self._dirty and self._cached is not None:
            return self._cached
        try:
            if self.op == "const":
                val = float(self.args[0])
            elif self.op == "add":
                val = self.args[0].evaluate() + self.args[1].evaluate()
            elif self.op == "mul":
                val = self.args[0].evaluate() * self.args[1].evaluate()
            elif self.op == "pow":
                val = self.args[0].evaluate() ** self.args[1].evaluate()
            elif self.op == "log":
                x_val = self.args[0].evaluate()
                base_arg = self.args[1]
                base_val = base_arg if isinstance(base_arg, (int, float)) else base_arg.evaluate()
                val = math.log(x_val, base_val) if base_val > 0 and x_val > 0 else float("inf")
            elif self.op == "exp":
                val = math.exp(self.args[0].evaluate())
            elif self.op == "neg":
                val = -self.args[0].evaluate()
            elif self.op == "func":
                fname, x = self.args[0], self.args[1].evaluate()
                val = {"gamma": lambda x: math.gamma(x), "zeta": lambda x: _zeta_real(x), "erf": lambda x: math.erf(x)}.get(fname, lambda x: float("inf"))(x)
            else:
                raise ValueError(f"Operacion desconocida: {self.op}")
        except Exception:
            val = float("inf")
        self._cached, self._dirty = val, False
        return val

    def simplify(self):
        # --- BLOQUE: SIMPLIFICACION ALGEBRAICA ---
        if self.op in ("add", "mul", "pow"):
            a, b = (arg.simplify() if isinstance(arg, FormulaNode) else arg for arg in self.args)
            if hasattr(a, 'op') and hasattr(b, 'op') and a.op == "const" and b.op == "const":
                return FormulaNode("const", {"add": lambda: a.args[0]+b.args[0], "mul": lambda: a.args[0]*b.args[0], "pow": lambda: a.args[0]**b.args[0]}[self.op]())
            if self.op == "add" and ((hasattr(a, 'op') and a.op == "const" and a.args[0] == 0) or (hasattr(b, 'op') and b.op == "const" and b.args[0] == 0)):
                return b if (hasattr(a, 'op') and a.op == "const" and a.args[0] == 0) else a
            if self.op == "mul" and ((hasattr(a, 'op') and a.op == "const" and a.args[0] == 1) or (hasattr(b, 'op') and b.op == "const" and b.args[0] == 1)):
                return b if (hasattr(a, 'op') and a.op == "const" and a.args[0] == 1) else a
            return FormulaNode(self.op, a, b)
        if self.op == "neg" and hasattr(self.args[0], 'simplify'):
            a = self.args[0].simplify()
            return FormulaNode("const", -a.args[0]) if hasattr(a, 'op') and a.op == "const" else FormulaNode("neg", a)
        return self

    def to_string(self):
        # --- BLOQUE: REPRESENTACION EN STRING ---
        if self.op == "const":
            return str(self.args[0])
        if self.op in ("add", "mul", "pow"):
            return "(" + self.args[0].to_string() + {"add": " + ", "mul": " * ", "pow": " ^ "}[self.op] + self.args[1].to_string() + ")"
        if self.op == "log":
            base_str = self.args[1].to_string() if isinstance(self.args[1], FormulaNode) else str(self.args[1])
            return "log_" + base_str + "(" + self.args[0].to_string() + ")"
        if self.op == "exp":
            return "exp(" + self.args[0].to_string() + ")"
        if self.op == "neg":
            return "-(" + self.args[0].to_string() + ")"
        if self.op == "func":
            return self.args[0] + "(" + self.args[1].to_string() + ")"
        return "?"

    def to_serializable(self):
        return {"op": self.op, "args": [a.to_serializable() if isinstance(a, FormulaNode) else a for a in self.args]}

    @classmethod
    def from_serializable(cls, data):
        if data is None:
            return None
        op, args = data["op"], []
        for a in data["args"]:
            args.append(cls.from_serializable(a) if isinstance(a, dict) else a)
        return cls(op, *args)

def _zeta_real(s: float, max_iter: Optional[int] = None) -> float:
    if s <= 1:
        return float("inf")
    max_iter = max_iter or (1000 if GlobalConfig.IS_LOW_MEMORY else 10000)
    acc = 0.0
    for k in range(1, max_iter):
        term = 1.0 / (k ** s)
        if term < 1e-10:
            break
        acc += term
    return acc

# ================================================================================
# SECCION 8: SIMILARITY METRICS
# ================================================================================
class SimilarityMetrics:
    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        cosine = dot_product / (norm_a * norm_b)
        return (cosine + 1) / 2

    @staticmethod
    def euclidean_distance(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 1.0
        squared_sum = sum((a - b) ** 2 for a, b in zip(vec_a, vec_b))
        distance = math.sqrt(squared_sum)
        max_distance = math.sqrt(len(vec_a))
        return min(1.0, distance / max_distance)

    @staticmethod
    def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def weighted_similarity(features_a: Dict[str, float], features_b: Dict[str, float], weights: Dict[str, float]) -> float:
        if not features_a or not features_b:
            return 0.0
        total_weight, weighted_sum = 0.0, 0.0
        for feature, weight in weights.items():
            if feature in features_a and feature in features_b:
                diff = abs(features_a[feature] - features_b[feature])
                sim = 1.0 - min(1.0, diff)
                weighted_sum += weight * sim
                total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    @staticmethod
    def geographic_proximity(loc_a: Optional[Tuple[float, float]], loc_b: Optional[Tuple[float, float]], max_distance_km: float = 100.0) -> float:
        if loc_a is None or loc_b is None:
            return 0.5
        lat1, lon1 = math.radians(loc_a[0]), math.radians(loc_a[1])
        lat2, lon2 = math.radians(loc_b[0]), math.radians(loc_b[1])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = 6371.0 * c
        return max(0.0, 1.0 - (distance / max_distance_km))

    @staticmethod
    def time_decay(last_active: datetime, half_life_days: float = 30.0) -> float:
        if last_active is None:
            return 0.5
        age = (datetime.now(timezone.utc) - last_active).total_seconds()
        half_life_seconds = half_life_days * 24 * 3600
        return math.pow(0.5, age / half_life_seconds)

# ================================================================================
# SECCION 9: GEO MATCHER
# ================================================================================
class GeoMatcher:
    def __init__(self, cell_size_km: float = None):
        self.cell_size_km = cell_size_km if cell_size_km is not None else GlobalConfig.MATCHING_CELL_SIZE_KM
        self.cell_size_lat = self.cell_size_km / 111.0
        self.cell_size_lon = self.cell_size_km / 85.0

    def _get_cell(self, lat: float, lon: float) -> Tuple[int, int]:
        return (int(lat / self.cell_size_lat), int(lon / self.cell_size_lon))

    def cluster_agents(self, agents: List[Tuple[str, float, float]]) -> Dict[Tuple[int, int], List[str]]:
        clusters: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        for agent_id, lat, lon in agents:
            cell = self._get_cell(lat, lon)
            clusters[cell].append(agent_id)
        return clusters

    def find_nearby(self, agent_id: str, lat: float, lon: float, all_agents: Dict[str, Tuple[float, float]], radius_km: float = 20.0) -> List[Tuple[str, float]]:
        candidates = []
        for other_id, (other_lat, other_lon) in all_agents.items():
            if other_id == agent_id:
                continue
            dlat = math.radians(other_lat - lat)
            dlon = math.radians(other_lon - lon)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(other_lat)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = 6371.0 * c
            if distance <= radius_km:
                candidates.append((other_id, distance))
        candidates.sort(key=lambda x: x[1])
        return candidates

# ================================================================================
# SECCION 10: TOP-K CANDIDATES
# ================================================================================
class TopKCandidates:
    def __init__(self, k: int = None):
        self.k = k if k is not None else GlobalConfig.MATCHING_TOP_K

    def find_top_k(self, query: Dict[str, float], candidates: List[Tuple[str, Dict[str, float]]], weights: Optional[Dict[str, float]] = None) -> List[Tuple[str, float]]:
        # --- BLOQUE: BUSQUEDA HEAP OPTIMIZADA ---
        if weights is None:
            weights = {k: 1.0 for k in query.keys()}
        heap: List[Tuple[float, str]] = []
        for candidate_id, features in candidates:
            score = self._calculate_score(query, features, weights)
            if len(heap) < self.k:
                heapq.heappush(heap, (-score, candidate_id))
            elif score > -heap[0][0]:
                heapq.heappushpop(heap, (-score, candidate_id))
        results = [(candidate_id, -score) for score, candidate_id in heap]
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _calculate_score(self, query: Dict[str, float], features: Dict[str, float], weights: Dict[str, float]) -> float:
        total_weight, weighted_sum = 0.0, 0.0
        for feature, query_val in query.items():
            if feature in features:
                weight = weights.get(feature, 1.0)
                diff = abs(query_val - features[feature])
                sim = 1.0 - min(1.0, diff)
                weighted_sum += weight * sim
                total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

# ================================================================================
# SECCION 11: HUNGARIAN ALGORITHM
# ================================================================================
class HungarianAlgorithm:
    def __init__(self):
        self.n = 0
        self.m = 0
        self.cost_matrix = []
        self.assignment = []

    def solve(self, similarity_matrix: List[List[float]], maximize: bool = True) -> Tuple[List[Tuple[int, int]], float]:
        # --- BLOQUE: VALIDACION Y PREPARACION ---
        if not similarity_matrix or not similarity_matrix[0]:
            return [], 0.0
        self.n = len(similarity_matrix)
        self.m = len(similarity_matrix[0])
        if maximize:
            max_val = max(max(row) for row in similarity_matrix)
            self.cost_matrix = [[max_val - val for val in row] for row in similarity_matrix]
        else:
            self.cost_matrix = [row[:] for row in similarity_matrix]
        size = max(self.n, self.m)
        self._pad_matrix(size)
        self._hungarian()
        
        # --- BLOQUE: EXTRACCION DE RESULTADOS ---
        matches = []
        total_cost = 0.0
        for i in range(self.n):
            if self.assignment[i] < self.m:
                matches.append((i, self.assignment[i]))
                total_cost += similarity_matrix[i][self.assignment[i]]
        return matches, total_cost if maximize else -total_cost

    def _pad_matrix(self, size: int) -> None:
        for i in range(size):
            if i < len(self.cost_matrix):
                while len(self.cost_matrix[i]) < size:
                    self.cost_matrix[i].append(float('inf'))
            else:
                self.cost_matrix.append([float('inf')] * size)
        while len(self.cost_matrix) < size:
            self.cost_matrix.append([float('inf')] * size)

    def _hungarian(self) -> None:
        # --- BLOQUE: ALGORITMO PRINCIPAL ---
        n = len(self.cost_matrix)
        u = [0.0] * (n + 1)
        v = [0.0] * (n + 1)
        p = [0] * (n + 1)
        way = [0] * (n + 1)
        for i in range(1, n + 1):
            p[0] = i
            j0 = 0
            minv = [float('inf')] * (n + 1)
            used = [False] * (n + 1)
            while True:
                used[j0] = True
                i0 = p[j0]
                delta = float('inf')
                j1 = 0
                for j in range(1, n + 1):
                    if not used[j]:
                        cur = self.cost_matrix[i0 - 1][j - 1] - u[i0] - v[j]
                        if cur < minv[j]:
                            minv[j] = cur
                            way[j] = j0
                        if minv[j] < delta:
                            delta = minv[j]
                            j1 = j
                for j in range(n + 1):
                    if used[j]:
                        u[p[j]] += delta
                        v[j] -= delta
                    else:
                        minv[j] -= delta
                j0 = j1
                if p[j0] == 0:
                    break
            while True:
                j1 = way[j0]
                p[j0] = p[j1]
                j0 = j1
                if j0 == 0:
                    break
        self.assignment = [p[j] - 1 for j in range(1, n + 1)]

# ================================================================================
# SECCION 12: GALE-SHAPLEY
# ================================================================================
class GaleShapley:
    def __init__(self):
        self.men_preferences, self.women_preferences = {}, {}
        self.men_engaged, self.women_engaged = {}, {}

    def solve(self, men: List[str], women: List[str], men_prefs: Dict[str, List[str]], women_prefs: Dict[str, List[str]]) -> Dict[str, str]:
        # --- BLOQUE: INICIALIZACION ---
        self.men_preferences, self.women_preferences = men_prefs, women_prefs
        for man in men:
            self.men_engaged[man] = None
        for woman in women:
            self.women_engaged[woman] = None
        women_rank = {w: {m: r for r, m in enumerate(prefs)} for w, prefs in women_prefs.items()}
        free_men, next_proposal = deque(men), {man: 0 for man in men}
        
        # --- BLOQUE: ITERACION DE PROPUESTAS ---
        while free_men:
            man = free_men.popleft()
            if man not in men_prefs or next_proposal[man] >= len(men_prefs[man]):
                continue
            woman = men_prefs[man][next_proposal[man]]
            next_proposal[man] += 1
            if self.women_engaged[woman] is None:
                self.men_engaged[man], self.women_engaged[woman] = woman, man
            else:
                current = self.women_engaged[woman]
                if women_rank[woman][man] < women_rank[woman][current]:
                    self.men_engaged[man], self.women_engaged[woman] = woman, man
                    self.men_engaged[current] = None
                    free_men.append(current)
                else:
                    free_men.append(man)
        return {m: w for m, w in self.men_engaged.items() if w is not None}

# ================================================================================
# SECCION 13: MATCHING ENGINE
# ================================================================================
class MatchingEngine:
    def __init__(self):
        self.hungarian, self.gale_shapley = HungarianAlgorithm(), GaleShapley()
        self.greedy_min_score = GlobalConfig.MATCHING_MIN_SCORE
        self.top_k = TopKCandidates()
        self.geo_matcher = GeoMatcher()
        self.agent_features: Dict[str, Dict[str, float]] = {}
        self.match_count, self.total_score = 0, 0.0
        self.algorithm_usage: Dict[str, int] = defaultdict(int)

    def compute_similarity(self, agent_a: MatchingAgent, agent_b: MatchingAgent, weights: Optional[Dict[str, float]] = None) -> Tuple[float, Dict[str, float]]:
        # --- BLOQUE: DESGLOSE DE SIMILITUD ---
        if weights is None:
            weights = {"price": 0.3, "time": 0.2, "quality": 0.2, "rating": 0.15, "location": 0.15}
        breakdown = {}
        if agent_a.preferences and agent_b.preferences:
            breakdown["preferences"] = SimilarityMetrics.weighted_similarity(agent_a.preferences, agent_b.preferences, {"price": 0.5, "time": 0.3, "quality": 0.2})
        breakdown["rating"] = 1.0 - abs(agent_a.rating - agent_b.rating)
        if agent_a.location and agent_b.location:
            breakdown["location"] = SimilarityMetrics.geographic_proximity(agent_a.location, agent_b.location, max_distance_km=50.0)
        breakdown["recency"] = (SimilarityMetrics.time_decay(agent_a.last_active) + SimilarityMetrics.time_decay(agent_b.last_active)) / 2
        total = sum(weights.get(k, 0) * v for k, v in breakdown.items())
        return total, breakdown

    def match_single(self, request: MatchingRequest, candidates: List[MatchingAgent]) -> List[Match]:
        # --- BLOQUE: MATCHING INDIVIDUAL ---
        matches = []
        for candidate in candidates:
            if candidate.agent_id == request.agent.agent_id:
                continue
            if candidate.location and request.agent.location:
                if SimilarityMetrics.geographic_proximity(request.agent.location, candidate.location, max_distance_km=request.max_distance_km) < 0.1:
                    continue
            score, breakdown = self.compute_similarity(request.agent, candidate)
            if score >= request.min_score_threshold:
                matches.append(Match(agent_a=request.agent.agent_id, agent_b=candidate.agent_id, score=score, similarity_breakdown=breakdown, algorithm_used="single_query"))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:request.max_results]

    def match_batch(self, requests: List[MatchingRequest], algorithm: MatchingAlgorithm = None) -> Dict[str, List[Match]]:
        # --- BLOQUE: SELECCION DE ALGORITMO ---
        if algorithm is None:
            algorithm = MatchingAlgorithm[GlobalConfig.MATCHING_ALGORITHM.upper()] if GlobalConfig.MATCHING_ALGORITHM.upper() in MatchingAlgorithm.__members__ else MatchingAlgorithm.GREEDY_BEST_MATCH
        results: Dict[str, List[Match]] = {}
        if algorithm == MatchingAlgorithm.HUNGARIAN and len(requests) > 5 and not GlobalConfig.IS_LOW_MEMORY:
            return self._match_hungarian(requests)
        elif algorithm == MatchingAlgorithm.GALE_SHAPLEY:
            return self._match_gale_shapley(requests)
        for req in requests:
            matches = self.match_single(req, [r.agent for r in requests])
            results[req.request_id] = matches
        return results

    def _match_hungarian(self, requests: List[MatchingRequest]) -> Dict[str, List[Match]]:
        n = len(requests)
        similarity_matrix = [[0.0 if i == j else self.compute_similarity(req_a.agent, req_b.agent)[0] for j, req_b in enumerate(requests)] for i, req_a in enumerate(requests)]
        matches, total_score = self.hungarian.solve(similarity_matrix, maximize=True)
        results = {req.request_id: [] for req in requests}
        for i, j in matches:
            if i < len(requests) and j < len(requests):
                req_a, req_b = requests[i], requests[j]
                score, breakdown = self.compute_similarity(req_a.agent, req_b.agent)
                match = Match(agent_a=req_a.agent.agent_id, agent_b=req_b.agent.agent_id, score=score, similarity_breakdown=breakdown, algorithm_used="HUNGARIAN")
                results[req_a.request_id].append(match)
                results[req_b.request_id].append(match)
                self.match_count += 1
                self.total_score += score
                self.algorithm_usage["HUNGARIAN"] += 1
        return results

    def _match_gale_shapley(self, requests: List[MatchingRequest]) -> Dict[str, List[Match]]:
        agents_a = [r for i, r in enumerate(requests) if i % 2 == 0]
        agents_b = [r for i, r in enumerate(requests) if i % 2 == 1]
        prefs_a = {r.agent.agent_id: [a.agent.agent_id for a in agents_b] for r in agents_a}
        prefs_b = {r.agent.agent_id: [a.agent.agent_id for a in agents_a] for r in agents_b}
        result = self.gale_shapley.solve([a.agent.agent_id for a in agents_a], [b.agent.agent_id for b in agents_b], prefs_a, prefs_b)
        results = {req.request_id: [] for req in requests}
        for agent_a_id, agent_b_id in result.items():
            match = Match(agent_a=agent_a_id, agent_b=agent_b_id, algorithm_used="GALE_SHAPLEY")
            results[next((r.request_id for r in requests if r.agent.agent_id == agent_a_id), None)] = [match]
        self.algorithm_usage["GALE_SHAPLEY"] += 1
        return results

    def get_recommendations(self, agent_id: str, top_k: int = None) -> List[Tuple[str, float]]:
        if agent_id not in self.agent_features:
            return []
        query_features = self.agent_features[agent_id]
        all_candidates = [(aid, features) for aid, features in self.agent_features.items() if aid != agent_id]
        return self.top_k.find_top_k(query_features, all_candidates)

    def update_features(self, agent_id: str, features: Dict[str, float]) -> None:
        self.agent_features[agent_id] = features

# ================================================================================
# SECCION 14: POLITICAS DE EXPLORACION (RL)
# ================================================================================
class ExplorationPolicy:
    @staticmethod
    def epsilon_greedy(epsilon: float, q_values: List[float], num_actions: int) -> int:
        if random.random() < epsilon:
            return random.randint(0, num_actions - 1)
        if not q_values:
            return 0
        return q_values.index(max(q_values))

    @staticmethod
    def softmax(q_values: List[float], temperature: float) -> int:
        if not q_values or all(v == 0 for v in q_values):
            return random.randint(0, len(q_values) - 1)
        max_q = max(q_values)
        temp = max(temperature, 0.001)
        exp_values = [math.exp((v - max_q) / temp) for v in q_values]
        total = sum(exp_values)
        if total == 0:
            return random.randint(0, len(q_values) - 1)
        probs = [ev / total for ev in exp_values]
        cumsum, r = 0.0, random.random()
        for i, p in enumerate(probs):
            cumsum += p
            if r <= cumsum:
                return i
        return len(probs) - 1

    @staticmethod
    def ucb(q_values: List[float], visit_counts: List[int], total_visits: int, c: float = 1.414) -> int:
        if not q_values or not visit_counts:
            return 0
        if 0 in visit_counts:
            return visit_counts.index(0)
        ucb_values = []
        for q, n in zip(q_values, visit_counts):
            if n > 0:
                bonus = c * math.sqrt(math.log(max(total_visits, 1)) / n)
                ucb_values.append(q + bonus)
            else:
                ucb_values.append(float('inf'))
        return ucb_values.index(max(ucb_values))

# ================================================================================
# SECCION 15: Q-LEARNING TABULAR (Sistema Unificado)
# ================================================================================
class QLearningAgent:
    def __init__(self, learning_rate: float = None, discount_factor: float = None,
                 epsilon: float = None, epsilon_min: float = None, epsilon_decay: float = None,
                 use_eligibility: bool = None, lambda_trace: float = None):
        self.learning_rate = learning_rate if learning_rate is not None else GlobalConfig.RL_LEARNING_RATE
        self.discount_factor = discount_factor if discount_factor is not None else GlobalConfig.RL_DISCOUNT_FACTOR
        self.epsilon = epsilon if epsilon is not None else GlobalConfig.RL_EXPLORATION_EPSILON
        self.epsilon_min = epsilon_min if epsilon_min is not None else GlobalConfig.RL_EPSILON_MIN
        self.epsilon_decay = epsilon_decay if epsilon_decay is not None else GlobalConfig.RL_EPSILON_DECAY
        self.use_eligibility = use_eligibility if use_eligibility is not None else GlobalConfig.RL_USE_ELIGIBILITY
        self.lambda_trace = lambda_trace if lambda_trace is not None else GlobalConfig.RL_LAMBDA_TRACE
        self.q_table: Dict[str, Dict[str, QTableEntry]] = defaultdict(dict)
        self.eligibility: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.total_episodes, self.total_steps = 0, 0
        self.rewards_history: deque = deque(maxlen=1000)
        self.q_value_history: deque = deque(maxlen=100)

    def get_q_value(self, state: RLState, action: RLAction) -> float:
        state_key = state.discretize()
        return self.q_table[state_key].get(action.action_id, QTableEntry()).q_value if state_key in self.q_table else 0.0

    def get_max_q(self, state: RLState) -> Tuple[float, Optional[RLAction]]:
        state_key = state.discretize()
        if state_key not in self.q_table or not self.q_table[state_key]:
            return 0.0, None
        best_action_id = max(self.q_table[state_key].keys(), key=lambda a: self.q_table[state_key][a].q_value)
        return self.q_table[state_key][best_action_id].q_value, RLAction(action_id=best_action_id, action_type=ActionType[best_action_id.upper()] if best_action_id.upper() in ActionType.__members__ else ActionType.WAIT)

    def update(self, state: RLState, action: RLAction, reward: float, next_state: RLState, done: bool) -> float:
        # --- BLOQUE: ACTUALIZACION Q-TABLE ---
        state_key, action_id = state.discretize(), action.action_id
        current_q = self.get_q_value(state, action)
        max_next_q = 0.0 if done else self.get_max_q(next_state)[0]
        target_q = reward + self.discount_factor * max_next_q
        td_error = target_q - current_q
        if state_key not in self.q_table:
            self.q_table[state_key] = {}
        if action_id not in self.q_table[state_key]:
            self.q_table[state_key][action_id] = QTableEntry()
        entry = self.q_table[state_key][action_id]
        entry.q_value += self.learning_rate * td_error
        entry.visit_count += 1
        entry.last_updated = datetime.now(timezone.utc)
        if self.use_eligibility:
            self._update_eligibility(state_key, action_id, td_error)
        return td_error

    def _update_eligibility(self, state_key: str, action_id: str, td_error: float) -> None:
        for s in self.eligibility:
            for a in self.eligibility[s]:
                self.eligibility[s][a] *= self.discount_factor * self.lambda_trace
        self.eligibility[state_key][action_id] = 1.0

    def select_action(self, state: RLState, available_actions: List[RLAction], method: str = "epsilon_greedy") -> RLAction:
        if not available_actions:
            return RLAction(action_id="wait", action_type=ActionType.WAIT)
        q_values = [self.get_q_value(state, a) for a in available_actions]
        visit_counts = [self.q_table.get(state.discretize(), {}).get(a.action_id, QTableEntry()).visit_count for a in available_actions]
        idx = {
            "epsilon_greedy": lambda: ExplorationPolicy.epsilon_greedy(self.epsilon, q_values, len(available_actions)),
            "softmax": lambda: ExplorationPolicy.softmax(q_values, temperature=0.5),
            "ucb": lambda: ExplorationPolicy.ucb(q_values, visit_counts, sum(visit_counts)+1)
        }.get(method, lambda: q_values.index(max(q_values)) if q_values else 0)()
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        return available_actions[idx]

    def decay_epsilon(self, factor: float = None) -> None:
        self.epsilon = max(self.epsilon_min, self.epsilon * (factor or self.epsilon_decay))

    def get_policy(self, state: RLState, available_actions: List[RLAction]) -> Dict[RLAction, float]:
        q_values = [self.get_q_value(state, a) for a in available_actions]
        max_q = max(q_values) if q_values else 0
        exp_q = [math.exp(q - max_q) for q in q_values]
        total = sum(exp_q)
        probs = [eq / total for eq in exp_q]
        return {a: p for a, p in zip(available_actions, probs)}

    def save(self, filepath: str) -> None:
        data = {
            "q_table": {s: {a: {"q_value": e.q_value, "visit_count": e.visit_count} for a, e in actions.items()} for s, actions in self.q_table.items()},
            "epsilon": self.epsilon, "total_episodes": self.total_episodes, "total_steps": self.total_steps
        }
        with open(filepath, 'w') as f:
            json.dump(data, f)

    def load(self, filepath: str) -> None:
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.q_table = defaultdict(dict)
        for s, actions in data["q_table"].items():
            self.q_table[s] = {a: QTableEntry(q_value=e["q_value"], visit_count=e["visit_count"]) for a, e in actions.items()}
        self.epsilon = data.get("epsilon", self.epsilon_min)
        self.total_episodes = data.get("total_episodes", 0)
        self.total_steps = data.get("total_steps", 0)

# ================================================================================
# SECCION 16: POLICY GRADIENT (Sistema Unificado)
# ================================================================================
class PolicyGradientAgent:
    def __init__(self, learning_rate: float = 0.001, discount_factor: float = 0.95,
                 policy_params: Optional[PolicyParams] = None, hidden_sizes: List[int] = None):
        self.learning_rate, self.discount_factor = learning_rate, discount_factor
        self.params = policy_params or PolicyParams()
        if hidden_sizes is None:
            hidden_sizes = [16, 8] if GlobalConfig.IS_LOW_MEMORY else [32, 16]
        self.params.initialize_random(input_size=6, output_size=4, hidden_sizes=hidden_sizes)
        self.experience_buffer: List[Tuple[RLState, RLAction, float]] = []
        self.episode_rewards: List[float] = []
        self.gradient_history: deque = deque(maxlen=100)

    def forward(self, state: RLState) -> List[float]:
        features = state.to_vector()
        layer = "layer_0"
        weights = self.params.weights.get(layer, [0.0] * 24)
        bias = self.params.biases.get(layer, 0.0)
        output = sum(w * f for w, f in zip(weights[:len(features)], features)) + bias
        exp_out = math.exp(max(-50, min(50, output)))
        prob = exp_out / (1 + exp_out)
        return [math.log(max(1e-10, prob))]

    def select_action(self, state: RLState, available_actions: List[RLAction]) -> Tuple[RLAction, float]:
        if not available_actions:
            return RLAction(action_id="wait", action_type=ActionType.WAIT), 0.0
        preferences = [random.uniform(0, 1) for _ in available_actions]
        total = sum(preferences)
        probs = [p / total for p in preferences]
        r, cumsum = random.random(), 0.0
        for i, (action, prob) in enumerate(zip(available_actions, probs)):
            cumsum += prob
            if r <= cumsum:
                return action, math.log(max(1e-10, prob))
        return available_actions[-1], math.log(max(1e-10, probs[-1]))

    def store_experience(self, state: RLState, action: RLAction, reward: float) -> None:
        self.experience_buffer.append((state, action, reward))

    def compute_returns(self) -> List[float]:
        returns, G = [], 0.0
        for _, _, reward in reversed(self.experience_buffer):
            G = reward + self.discount_factor * G
            returns.insert(0, G)
        return returns

    def update(self) -> float:
        if len(self.experience_buffer) < 2:
            return 0.0
        returns = self.compute_returns()
        mean_return = sum(returns) / len(returns)
        std_return = math.sqrt(sum((r - mean_return)**2 for r in returns) / len(returns)) if len(returns) > 1 else 1.0
        normalized_returns = [(r - mean_return) / std_return if std_return > 0 else r for r in returns]
        loss = 0.0
        for (state, action, _), G in zip(self.experience_buffer, normalized_returns):
            loss -= G * 0.01
        layer = "layer_0"
        if layer in self.params.weights:
            for i in range(len(self.params.weights[layer])):
                self.params.weights[layer][i] += self.learning_rate * random.uniform(-0.01, 0.01)
        self.episode_rewards.append(sum(r for _, _, r in self.experience_buffer))
        self.experience_buffer.clear()
        return loss

    def reset_episode(self) -> None:
        self.experience_buffer.clear()

# ================================================================================
# SECCION 17: ACTOR-CRITIC (Sistema Unificado - Hibrido)
# ================================================================================
class ActorCriticAgent:
    def __init__(self, actor_lr: float = 0.001, critic_lr: float = 0.005,
                 discount_factor: float = 0.95, entropy_coef: float = 0.01):
        self.actor_lr, self.critic_lr, self.discount_factor, self.entropy_coef = actor_lr, critic_lr, discount_factor, entropy_coef
        self.actor = PolicyGradientAgent(learning_rate=actor_lr, discount_factor=discount_factor)
        self.value_table: Dict[str, float] = defaultdict(float)
        self.buffer: List[Tuple[RLState, RLAction, float, RLState]] = []

    def select_action(self, state: RLState, available_actions: List[RLAction]) -> Tuple[RLAction, float]:
        return self.actor.select_action(state, available_actions)

    def store_transition(self, state: RLState, action: RLAction, reward: float, next_state: RLState) -> None:
        self.buffer.append((state, action, reward, next_state))

    def update(self, done: bool) -> Tuple[float, float]:
        if len(self.buffer) < 1:
            return 0.0, 0.0
        actor_loss, critic_loss, G = 0.0, 0.0, 0.0
        for state, action, reward, next_state in reversed(self.buffer):
            state_key, next_state_key = state.discretize(), next_state.discretize()
            current_V, next_V = self.value_table.get(state_key, 0.0), (0.0 if done else self.value_table.get(next_state_key, 0.0))
            td_target = reward + self.discount_factor * next_V
            td_error = td_target - current_V
            self.value_table[state_key] = current_V + self.critic_lr * td_error
            advantage = td_error
            actor_loss = actor_loss - advantage * 0.01
            entropy_bonus = self.entropy_coef * random.uniform(0, 1)
            actor_loss -= entropy_bonus
            self.actor.learning_rate = max(0.0001, self.actor.learning_rate * 0.999)
        self.buffer.clear()
        return actor_loss, critic_loss

# ================================================================================
# SECCION 18: ENTORNO DE SIMULACION DE NEGOCIACION
# ================================================================================
class NegotiationEnvironment:
    def __init__(self, max_rounds: int = None, min_utility: float = 0.6, max_utility: float = 0.9):
        self.max_rounds = max_rounds if max_rounds is not None else GlobalConfig.MAX_ROUNDS
        self.min_utility, self.max_utility = min_utility, max_utility
        self.current_state: Optional[RLState] = None
        self.round_number = 0
        self.initial_my_utility, self.initial_opp_utility = 0.0, 0.0
        self.available_actions = [
            RLAction(action_id=a.name.lower(), action_type=a)
            for a in [ActionType.ACCEPT_OFFER, ActionType.REJECT_OFFER, ActionType.COUNTER_OFFER, ActionType.WAIT]
        ]

    def reset(self) -> RLState:
        # --- BLOQUE: REINICIO DE ESTADO ---
        self.round_number = 0
        self.initial_my_utility, self.initial_opp_utility = random.uniform(0.3, 0.6), random.uniform(0.3, 0.6)
        self.current_state = RLState(
            state_id=str(uuid.uuid4())[:8], negotiation_round=0,
            my_utility=self.initial_my_utility, opponent_utility=self.initial_opp_utility,
            time_pressure=0.0, remaining_rounds=self.max_rounds,
            features={"initial_my_util": self.initial_my_utility, "initial_opp_util": self.initial_opp_utility, "negotiation_power": random.uniform(0.3, 0.7)}
        )
        return self.current_state

    def step(self, action: RLAction) -> Tuple[RLState, float, bool]:
        if self.current_state is None:
            raise RuntimeError("Ambiente no inicializado. Llamar reset() primero.")
        self.round_number += 1
        next_state = self._compute_next_state(action)
        reward = self._calculate_reward(action, next_state)
        done = self._is_episode_done(action, next_state)
        self.current_state = next_state
        return next_state, reward, done

    def _compute_next_state(self, action: RLAction) -> RLState:
        state = self.current_state
        new_round = state.negotiation_round + 1
        remaining = max(0, self.max_rounds - new_round)
        changes = {
            ActionType.ACCEPT_OFFER: (random.uniform(0.05, 0.15), random.uniform(0.0, 0.1)),
            ActionType.COUNTER_OFFER: (random.uniform(-0.05, 0.1), random.uniform(-0.05, 0.1)),
            ActionType.WAIT: (-0.1, -0.05),
            ActionType.REJECT_OFFER: (-0.15, -0.1)
        }.get(action.action_type, (-0.1, -0.1))
        new_my_util = max(0.0, min(1.0, state.my_utility + changes[0]))
        new_opp_util = max(0.0, min(1.0, state.opponent_utility + changes[1]))
        new_time_pressure = min(1.0, state.time_pressure + 0.15)
        return RLState(
            state_id=str(uuid.uuid4())[:8], negotiation_round=new_round,
            my_utility=new_my_util, opponent_utility=new_opp_util,
            time_pressure=new_time_pressure, remaining_rounds=remaining,
            opponent_strategy_estimated=self._estimate_opponent_strategy(), features=state.features
        )

    def _calculate_reward(self, action: RLAction, next_state: RLState) -> float:
        reward = (next_state.my_utility - self.initial_my_utility) * 0.5
        if action.action_type == ActionType.ACCEPT_OFFER:
            if next_state.my_utility >= self.min_utility:
                reward += 1.0
            if next_state.my_utility >= self.max_utility * 0.8:
                reward += 1.0
            else:
                reward -= 0.5
        elif action.action_type == ActionType.REJECT_OFFER and self.current_state and self.current_state.my_utility >= self.min_utility:
            reward -= 0.5
        elif action.action_type == ActionType.WAIT:
            reward -= 0.2
        return reward

    def _is_episode_done(self, action: RLAction, next_state: RLState) -> bool:
        return action.action_type == ActionType.ACCEPT_OFFER or next_state.remaining_rounds <= 0 or next_state.my_utility < 0.2

    def _estimate_opponent_strategy(self) -> str:
        return random.choice(["hardline", "moderate", "accommodating", "competitive", "collaborative"])

# ================================================================================
# SECCION 19: ENTRENADOR RL
# ================================================================================
class RLTrainer:
    def __init__(self, agent: Any, environment: NegotiationEnvironment,
                 num_episodes: int = None, eval_interval: int = None):
        self.agent, self.environment = agent, environment
        self.num_episodes = num_episodes if num_episodes is not None else GlobalConfig.RL_TRAINING_EPISODES
        self.eval_interval = eval_interval if eval_interval is not None else GlobalConfig.RL_EVAL_INTERVAL
        self.episode_rewards: List[float] = []
        self.episode_lengths: List[int] = []
        self.eval_results: List[Dict[str, float]] = []
        self.best_reward, self.best_agent_state = float('-inf'), None

    def train(self) -> Dict[str, Any]:
        log_banner("ENTRENAMIENTO RL")
        log_event(f"Agente: {type(self.agent).__name__}", "TRAIN")
        log_event(f"Episodios: {self.num_episodes}", "TRAIN")
        for episode in range(1, self.num_episodes + 1):
            state = self.environment.reset()
            episode_reward, step_count, done = 0.0, 0, False
            if hasattr(self.agent, 'reset_episode'):
                self.agent.reset_episode()
            while not done:
                action = self.agent.select_action(state, self.environment.available_actions)
                next_state, reward, done = self.environment.step(action)
                if hasattr(self.agent, 'store_experience'):
                    self.agent.store_experience(state, action, reward)
                elif hasattr(self.agent, 'update') and hasattr(self.agent, 'q_table'):
                    self.agent.update(state, action, reward, next_state, done)
                episode_reward += reward
                step_count += 1
                state = next_state
            self.episode_rewards.append(episode_reward)
            self.episode_lengths.append(step_count)
            if hasattr(self.agent, 'decay_epsilon'):
                self.agent.decay_epsilon()
            if episode % 10 == 0 and GlobalConfig.LOG_VERBOSE:
                avg_reward = sum(self.episode_rewards[-10:]) / 10
                avg_length = sum(self.episode_lengths[-10:]) / 10
                epsilon = getattr(self.agent, 'epsilon', 'N/A')
                log_event(f"Ep {episode}: reward={avg_reward:.2f}, length={avg_length:.1f}, eps={epsilon if isinstance(epsilon, str) else epsilon:.3f}", "TRAIN")
            if episode % self.eval_interval == 0:
                eval_result = self._evaluate()
                self.eval_results.append(eval_result)
                if eval_result['avg_utility'] > self.best_reward:
                    self.best_reward = eval_result['avg_utility']
                    self.best_agent_state = copy.deepcopy(self.agent)
        return self._get_final_stats()

    def _evaluate(self, num_episodes: int = 20) -> Dict[str, float]:
        wins, total_utility, total_reward = 0, 0.0, 0.0
        old_epsilon = getattr(self.agent, 'epsilon', 0.0)
        if hasattr(self.agent, 'epsilon'):
            self.agent.epsilon = 0.0
        for _ in range(num_episodes):
            state = self.environment.reset()
            done, episode_reward = False, 0.0
            while not done:
                action = self.agent.select_action(state, self.environment.available_actions)
                next_state, reward, done = self.environment.step(action)
                episode_reward += reward
                state = next_state
            total_reward += episode_reward
            total_utility += state.my_utility
            if action.action_type == ActionType.ACCEPT_OFFER and state.my_utility >= 0.6:
                wins += 1
        if hasattr(self.agent, 'epsilon'):
            self.agent.epsilon = old_epsilon
        return {"win_rate": wins / num_episodes, "avg_utility": total_utility / num_episodes, "avg_reward": total_reward / num_episodes}

    def _get_final_stats(self) -> Dict[str, Any]:
        recent_rewards = self.episode_rewards[-100:]
        return {
            "total_episodes": len(self.episode_rewards),
            "avg_reward_final": sum(recent_rewards) / len(recent_rewards) if recent_rewards else 0,
            "max_reward": max(self.episode_rewards) if self.episode_rewards else 0,
            "min_reward": min(self.episode_rewards) if self.episode_rewards else 0,
            "best_eval_utility": self.best_reward,
            "q_table_size": len(self.agent.q_table) if hasattr(self.agent, 'q_table') else 0
        }

# ================================================================================
# SECCION 20: MILEAGE LEARNER
# ================================================================================
class MileageLearner:
    def __init__(self, bins=(8, 18, 30), min_samples=15, persistence_path=None):
        # --- BLOQUE: INICIALIZACION ---
        self.bins = bins
        self.min_samples = min_samples
        self.persistence_path = persistence_path or Path.home() / ".symbiosis" / "data" / "mileage_model.json"
        self.experience = defaultdict(lambda: deque(maxlen=200))
        self.efficiency = {}
        self.confidence = {}
        self.adaptive_lr_multipliers = {}
        self.total_records = 0
        self.last_update = None
        self._auto_load()
        log_event(f"MileageLearner inicializado: bins={bins}", "MILEAGE")

    def _get_bin(self, km: float) -> str:
        if km <= self.bins[0]: return "short_0_8"
        elif km <= self.bins[1]: return "medium_8_18"
        elif km <= self.bins[2]: return "long_18_30"
        return "very_long_30plus"

    def _normalize_features(self, features: Dict) -> Dict:
        return {
            'hour': features.get('hour', time.time() % 24),
            'zone': features.get('zone', 'unknown'),
            'surge': min(3.0, features.get('surge', 1.0)),
            'is_rush': features.get('is_rush_hour', False),
            'weather': features.get('weather', 'clear')[:10],
            'day_type': features.get('day_type', 'weekday')
        }

    def _calculate_efficiency(self, bin_key: str) -> Optional[float]:
        if bin_key not in self.experience or len(self.experience[bin_key]) < self.min_samples:
            return None
        recent = list(self.experience[bin_key])[-self.min_samples:]
        rewards = [r['reward'] for r in recent if isinstance(r.get('reward'), (int, float))]
        return sum(rewards) / len(rewards) if rewards else None

    def _update_confidence(self, bin_key: str) -> float:
        if bin_key not in self.experience: return 0.0
        count = len(self.experience[bin_key])
        confidence = min(1.0, math.log10(count + 1) / 3.0)
        recent = [r for r in self.experience[bin_key] if time.time() - r.get('ts', 0) < 86400]
        if recent:
            confidence *= 0.7 + 0.3 * (len(recent) / count)
        self.confidence[bin_key] = round(confidence, 3)
        return confidence

    def record(self, km: float, reward: float, features: Dict = None, metadata: Dict = None) -> Dict[str, Any]:
        # --- BLOQUE: REGISTRO DE EXPERIENCIA ---
        if not isinstance(km, (int, float)) or km < 0:
            return {'success': False, 'error': 'km_invalid'}
        bin_key = self._get_bin(km)
        normalized_features = self._normalize_features(features or {})
        experience_entry = {
            'reward': float(reward), 'km': float(km),
            'features': normalized_features,
            'metadata': metadata or {}, 'ts': time.time()
        }
        self.experience[bin_key].append(experience_entry)
        self.total_records += 1
        self.last_update = datetime.now(timezone.utc).isoformat()
        
        # --- BLOQUE: ACTUALIZACION DE EFICIENCIA ---
        updated = False
        if len(self.experience[bin_key]) >= self.min_samples:
            old_eff = self.efficiency.get(bin_key)
            new_eff = self._calculate_efficiency(bin_key)
            if new_eff is not None:
                self.efficiency[bin_key] = round(new_eff, 4)
                conf = self._update_confidence(bin_key)
                self.adaptive_lr_multipliers[bin_key] = round(1.0 + 0.5 * (1 - conf), 3)
                updated = True
                log_event(f"{bin_key}: eficiencia=${new_eff:.2f} | conf={conf:.0%}", "MILEAGE")
        if self.total_records % 50 == 0 or (updated and new_eff and (old_eff is None or abs(new_eff - old_eff) > 2.0)):
            self._auto_save()
        return {
            'success': True, 'bin': bin_key,
            'total_records': self.total_records,
            'updated': updated,
            'efficiency': self.efficiency.get(bin_key),
            'confidence': self.confidence.get(bin_key, 0)
        }

    def predict_profitability(self, km: float, context: Dict = None) -> Dict[str, Any]:
        # --- BLOQUE: PREDICCION CONTEXTUAL ---
        bin_key = self._get_bin(km)
        result = {
            'bin': bin_key, 'predicted_reward': None,
            'confidence': 0.0, 'recommendation': 'neutral', 'factors': {}
        }
        if bin_key not in self.efficiency or self.confidence.get(bin_key, 0) < 0.3:
            result['recommendation'], result['predicted_reward'] = 'consider', 5.0
            return result
        base_reward, confidence = self.efficiency[bin_key], self.confidence[bin_key]
        context_factor = 1.0
        if context:
            if context.get('is_rush_hour') and base_reward > 7:
                context_factor *= 1.15
                result['factors']['rush_hour_bonus'] = '+15%'
            surge = context.get('surge_multiplier', 1.0)
            if surge > 1.2:
                context_factor *= (1 + (surge - 1) * 0.5)
                result['factors']['surge_adjustment'] = f'x{surge:.2f}'
            if context.get('weather') in ['rain', 'storm']:
                context_factor *= 0.92
                result['factors']['weather_penalty'] = '-8%'
            if context.get('is_weekend'):
                weekend_factor = 1.05 if bin_key in ['medium_8_18', 'long_18_30'] else 0.95
                context_factor *= weekend_factor
                result['factors']['weekend_adjustment'] = f'{weekend_factor:.0%}'
        predicted = base_reward * context_factor
        result['predicted_reward'], result['confidence'] = round(predicted, 2), confidence
        threshold_accept = 8.0 if context.get('is_rush_hour') else 6.0
        if predicted >= threshold_accept and confidence >= 0.5:
            result['recommendation'] = 'accept'
        elif predicted <= 3.0 or confidence < 0.3:
            result['recommendation'] = 'reject'
        else:
            result['recommendation'] = 'consider'
        return result

    def get_adaptive_lr_multiplier(self, km: float) -> float:
        return self.adaptive_lr_multipliers.get(self._get_bin(km), 1.0)

    def get_bin_statistics(self) -> Dict[str, Dict]:
        stats = {}
        for bin_key in ["short_0_8", "medium_8_18", "long_18_30", "very_long_30plus"]:
            if bin_key in self.experience:
                records = list(self.experience[bin_key])
                rewards = [r['reward'] for r in records if isinstance(r.get('reward'), (int, float))]
                stats[bin_key] = {
                    'count': len(records),
                    'avg_reward': sum(rewards)/len(rewards) if rewards else None,
                    'confidence': self.confidence.get(bin_key, 0),
                    'lr_multiplier': self.adaptive_lr_multipliers.get(bin_key, 1.0)
                }
        return stats

    def _auto_save(self) -> bool:
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'version': '1.0', 'bins': self.bins,
                'min_samples': self.min_samples,
                'efficiency': self.efficiency,
                'confidence': self.confidence,
                'adaptive_lr_multipliers': self.adaptive_lr_multipliers,
                'total_records': self.total_records,
                'last_update': self.last_update,
                'experience_summary': {
                    bk: {'count': len(recs), 'avg_reward': self.efficiency.get(bk)}
                    for bk, recs in self.experience.items()
                }
            }
            tmp_path = Path(str(self.persistence_path) + ".tmp")
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self.persistence_path)
            log_event(f"MileageLearner guardado: {self.total_records} registros", "MILEAGE")
            return True
        except Exception as e:
            log_event(f"Error guardando MileageLearner: {e}", "MILEAGE_WARN")
            return False

    def _auto_load(self) -> bool:
        if not self.persistence_path.exists():
            return False
        try:
            with open(self.persistence_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('version') != '1.0':
                return False
            self.bins = tuple(data.get('bins', self.bins))
            self.min_samples = data.get('min_samples', self.min_samples)
            self.efficiency = data.get('efficiency', {})
            self.confidence = data.get('confidence', {})
            self.adaptive_lr_multipliers = data.get('adaptive_lr_multipliers', {})
            self.total_records = data.get('total_records', 0)
            self.last_update = data.get('last_update')
            log_event(f"MileageLearner cargado: {self.total_records} registros", "MILEAGE")
            return True
        except Exception as e:
            log_event(f"Error cargando MileageLearner: {e}", "MILEAGE_WARN")
            return False

    def to_dict(self) -> Dict:
        return {
            'bins': self.bins,
            'efficiency': self.efficiency,
            'confidence': self.confidence,
            'total_records': self.total_records,
            'statistics': self.get_bin_statistics()
        }

# ================================================================================
# SECCION 21: DECORADOR DE GOBERNANZA CEOIA
# ================================================================================
def ceo_governed(module_name: str = None):
    def decorator(module_or_instance):
        if callable(module_or_instance):
            module_or_instance.__ceo_governed__ = True
            module_or_instance.__ceo_registered_at__ = datetime.now(timezone.utc).isoformat()
            try:
                ceo = None
                if 'ceoia_instance' in globals():
                    ceo = globals()['ceoia_instance']
                elif hasattr(sys.modules.get('__main__'), 'ceoia_instance'):
                    ceo = getattr(sys.modules['__main__'], 'ceoia_instance')
                if ceo and hasattr(ceo, 'register_module'):
                    ceo.register_module(
                        name=module_name or module_or_instance.__name__,
                        module_ref=module_or_instance,
                        registered_at=module_or_instance.__ceo_registered_at__
                    )
            except Exception as e:
                if hasattr(module_or_instance, 'log'):
                    module_or_instance.log(f"No se pudo registrar con CEOIA: {e}", "WARN")
        else:
            module_or_instance.__ceo_governed__ = True
            module_or_instance.__ceo_registered_at__ = datetime.now(timezone.utc).isoformat()
        return module_or_instance
    return decorator

# ================================================================================
# SECCION 22: DOUBLE DQN (CEOIA - con numpy)
# ================================================================================
class DoubleDQN:
    def __init__(self, state_dim, action_dim, learning_rate=0.001, gamma=0.99,
                 epsilon_start=1.0, epsilon_end=0.01, epsilon_decay=0.995,
                 memory_size=10000, batch_size=32, target_update_frequency=100):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update_freq = target_update_frequency
        self.steps = 0
        self.training_steps = 0

        if np is not None:
            self.q_network = self._init_network(state_dim, action_dim)
            self.target_network = self._init_network(state_dim, action_dim)
            self.optimizer_state = self._init_optimizer_state()
        else:
            self.q_table = defaultdict(lambda: np.zeros(action_dim) if np is not None else [0.0] * action_dim)

        self.memory = deque(maxlen=memory_size)
        self.priorities = deque(maxlen=memory_size)
        self.alpha = 0.6
        self.beta = 0.4
        self.beta_increment = 0.001
        self.n_step_buffer = deque(maxlen=5)
        self.n_step = 5
        self.n_step_gamma = math.pow(gamma, self.n_step)
        self.loss_history = deque(maxlen=100)
        self.td_error_history = deque(maxlen=100)

    def _to_key(self, state):
        try:
            if np is not None and isinstance(state, np.ndarray):
                return tuple(state.flatten().tolist())
            elif isinstance(state, (list, tuple)):
                return tuple(state)
            return state
        except Exception:
            return str(state)

    def _init_network(self, state_dim, action_dim):
        if np is None: return {}
        return {
            'w1': np.random.randn(state_dim, 128) * np.sqrt(2.0 / state_dim),
            'b1': np.zeros(128),
            'w2': np.random.randn(128, 64) * np.sqrt(2.0 / 128),
            'b2': np.zeros(64),
            'w3': np.random.randn(64, 32) * np.sqrt(2.0 / 64),
            'b3': np.zeros(32),
            'w4': np.random.randn(32, action_dim) * np.sqrt(2.0 / 32),
            'b4': np.zeros(action_dim)
        }

    def _init_optimizer_state(self):
        if np is None: return {}
        network = self.q_network
        return {
            'm': {k: np.zeros_like(v) for k, v in network.items()},
            'v': {k: np.zeros_like(v) for k, v in network.items()},
            'beta1': 0.9, 'beta2': 0.999, 'epsilon': 1e-8, 't': 0
        }

    def _forward(self, network, x, training=False):
        if np is None:
            return np.zeros(self.action_dim) if np is not None else [0.0] * self.action_dim
        x = np.array(x).reshape(1, -1)
        z1 = np.dot(x, network['w1']) + network['b1']; a1 = np.maximum(0.1 * z1, z1)
        z2 = np.dot(a1, network['w2']) + network['b2']; a2 = np.maximum(0.1 * z2, z2)
        z3 = np.dot(a2, network['w3']) + network['b3']; a3 = np.maximum(0.1 * z3, z3)
        z4 = np.dot(a3, network['w4']) + network['b4']
        return z4.flatten()

    def _backward(self, network, x, target, learning_rate, use_adam=True):
        if np is None: return network
        x = np.array(x).reshape(1, -1)
        z1 = np.dot(x, network['w1']) + network['b1']; a1 = np.maximum(0.1 * z1, z1)
        z2 = np.dot(a1, network['w2']) + network['b2']; a2 = np.maximum(0.1 * z2, z2)
        z3 = np.dot(a2, network['w3']) + network['b3']; a3 = np.maximum(0.1 * z3, z3)
        z4 = np.dot(a3, network['w4']) + network['b4']
        output = z4.flatten()
        error = (output - target).reshape(-1, 1)
        
        grad_w4 = np.outer(a3.flatten(), error.flatten()); grad_b4 = error.flatten()
        grad_a3 = np.dot(network['w4'], error); grad_z3 = grad_a3.flatten() * np.where(z3.flatten() > 0, 1.0, 0.1)
        grad_w3 = np.outer(a2.flatten(), grad_z3); grad_b3 = grad_z3
        grad_a2 = np.dot(network['w3'], grad_z3.reshape(-1, 1)); grad_z2 = grad_a2.flatten() * np.where(z2.flatten() > 0, 1.0, 0.1)
        grad_w2 = np.outer(a1.flatten(), grad_z2); grad_b2 = grad_z2
        grad_a1 = np.dot(network['w2'], grad_z2.reshape(-1, 1)); grad_z1 = grad_a1.flatten() * np.where(z1.flatten() > 0, 1.0, 0.1)
        grad_w1 = np.outer(x.flatten(), grad_z1); grad_b1 = grad_z1
        
        grad_clip_value = 1.0
        grads = [grad_w1, grad_b1.reshape(1, -1), grad_w2, grad_b2.reshape(1, -1),
                grad_w3, grad_b3.reshape(1, -1), grad_w4, grad_b4.reshape(1, -1)]
        for grad in grads:
            np.clip(grad, -grad_clip_value, grad_clip_value, out=grad)
            
        if use_adam and hasattr(self, 'optimizer_state'):
            self._adam_update(network, {
                'w1': grad_w1, 'b1': grad_b1, 'w2': grad_w2, 'b2': grad_b2,
                'w3': grad_w3, 'b3': grad_b3, 'w4': grad_w4, 'b4': grad_b4
            }, learning_rate)
        else:
            network['w1'] -= learning_rate * grad_w1; network['b1'] -= learning_rate * grad_b1
            network['w2'] -= learning_rate * grad_w2; network['b2'] -= learning_rate * grad_b2
            network['w3'] -= learning_rate * grad_w3; network['b3'] -= learning_rate * grad_b3
            network['w4'] -= learning_rate * grad_w4; network['b4'] -= learning_rate * grad_b4
        return network

    def _adam_update(self, network, grads, learning_rate):
        state = self.optimizer_state
        state['t'] += 1
        t = state['t']
        for key in network.keys():
            if key not in grads: continue
            grad = grads[key]
            state['m'][key] = state['beta1'] * state['m'][key] + (1 - state['beta1']) * grad
            state['v'][key] = state['beta2'] * state['v'][key] + (1 - state['beta2']) * (grad ** 2)
            m_hat = state['m'][key] / (1 - state['beta1'] ** t)
            v_hat = state['v'][key] / (1 - state['beta2'] ** t)
            network[key] -= learning_rate * m_hat / (np.sqrt(v_hat) + state['epsilon'])

    def store(self, state, action, reward, next_state, done):
        experience = Experience(state, action, reward, next_state, done)
        self.memory.append(experience)
        priority = (abs(reward) + 0.01) ** self.alpha
        self.priorities.append(priority)
        self.n_step_buffer.append(experience)
        if len(self.n_step_buffer) >= self.n_step or done:
            self._flush_n_step()

    def _flush_n_step(self):
        if not self.n_step_buffer: return
        n = len(self.n_step_buffer)
        state = self.n_step_buffer[0].state
        action = self.n_step_buffer[0].action
        reward_n = 0.0
        for i, exp in enumerate(self.n_step_buffer):
            reward_n += exp.reward * (self.gamma ** i)
        final_state = self.n_step_buffer[-1].next_state
        done = self.n_step_buffer[-1].done
        experience_n = Experience(state, action, reward_n, final_state, done, n_step=n)
        if len(self.memory) > 0:
            self.memory[-1] = experience_n
            self.priorities[-1] = (abs(reward_n) + 0.01) ** self.alpha

    def sample(self, batch_size):
        if len(self.memory) < batch_size: return []
        if np is not None:
            priorities = np.array(list(self.priorities))
        else:
            priorities = [1.0] * len(self.memory)
        priorities = np.maximum(priorities, 1e-6)
        probs = priorities ** self.alpha
        probs_sum = np.sum(probs)
        if probs_sum > 0:
            probs = probs / probs_sum
        else:
            probs = np.ones(len(priorities)) / len(priorities)
        indices = np.random.choice(len(self.memory), batch_size, p=probs, replace=False)
        experiences = [self.memory[i] for i in indices]
        weights = (len(self.memory) * probs[indices]) ** (-self.beta)
        weights = weights / np.max(weights)
        self.beta = min(1.0, self.beta + self.beta_increment)
        return experiences, indices, weights

    def update_priorities(self, indices, td_errors):
        for idx, td in zip(indices, td_errors):
            priority = (abs(td) + 0.01) ** self.alpha
            if idx < len(self.priorities):
                self.priorities[idx] = priority

    def select_action(self, state, exploit_only=False):
        if not exploit_only and random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        if np is None:
            key = self._to_key(state)
            q_values = self.q_table.get(key, [0.0] * self.action_dim)
        else:
            q_values = self._forward(self.q_network, state, training=False)
        if np is not None:
            return int(np.argmax(q_values))
        else:
            return q_values.index(max(q_values)) if q_values else 0

    def get_q_values(self, state):
        if np is None:
            key = self._to_key(state)
            return self.q_table.get(key, [0.0] * self.action_dim)
        else:
            return self._forward(self.q_network, state, training=False)

    def learn(self, batch_size=None):
        # --- BLOQUE: APRENDIZAJE DQN ---
        if batch_size is None: batch_size = self.batch_size
        result = self.sample(batch_size)
        if not result or len(result) < 3: return {}
        experiences, indices, weights = result
        if not experiences: return {}
        losses = []
        td_errors_all = []
        for i, exp in enumerate(experiences):
            state, action, reward, next_state, done = exp.state, exp.action, exp.reward, exp.next_state, exp.done
            if np is not None:
                q_values_curr = self._forward(self.q_network, state, training=True)
                q_values_next_online = self._forward(self.q_network, next_state, training=False)
                q_values_next_target = self._forward(self.target_network, next_state, training=False)
                if not done:
                    best_action = int(np.argmax(q_values_next_online))
                    q_target = reward + self.gamma * q_values_next_target[best_action]
                else:
                    q_target = reward
                td_error = q_target - q_values_curr[action]
                target_q = q_values_curr.copy()
                target_q[action] = q_target
                effective_lr = self.lr * weights[i]
                self.q_network = self._backward(self.q_network, state, target_q, effective_lr)
                losses.append(td_error ** 2)
                td_errors_all.append(td_error)
            else:
                key = self._to_key(state)
                next_key = self._to_key(next_state)
                q_values = list(self.q_table.get(key, [0.0] * self.action_dim))
                next_q_values = list(self.q_table.get(next_key, [0.0] * self.action_dim))
                best_action = next_q_values.index(max(next_q_values)) if next_q_values else 0
                target = reward + self.gamma * next_q_values[best_action] * (1 - done)
                q_values[action] += self.lr * (target - q_values[action])
                self.q_table[key] = q_values
        if td_errors_all:
            self.update_priorities(indices, td_errors_all)
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        self.steps += 1
        if self.steps % self.target_update_freq == 0 and np is not None:
            self._soft_update_target(tau=1.0)
        if losses:
            avg_loss = np.mean(losses) if np is not None else 0
            self.loss_history.append(avg_loss)
        if td_errors_all:
            avg_td = np.mean(np.abs(td_errors_all)) if np is not None else 0
            self.td_error_history.append(avg_td)
        self.training_steps += 1
        return {
            'loss': np.mean(losses) if losses and np is not None else 0,
            'epsilon': self.epsilon, 'steps': self.training_steps,
            'avg_td_error': np.mean(np.abs(td_errors_all)) if td_errors_all and np is not None else 0
        }

    def _soft_update_target(self, tau=0.001):
        if np is None: return
        for key in self.q_network.keys():
            self.target_network[key] = tau * self.q_network[key] + (1 - tau) * self.target_network[key]

    def save_model(self, filepath):
        if np is None:
            import pickle
            with open(filepath, 'wb') as f: pickle.dump(dict(self.q_table), f)
        else:
            np.savez(filepath, q_network=self.q_network, target_network=self.target_network, optimizer_state=self.optimizer_state, epsilon=self.epsilon, steps=self.steps, training_steps=self.training_steps)

    def load_model(self, filepath):
        if np is None:
            import pickle
            with open(filepath, 'rb') as f: self.q_table.update(pickle.load(f))
        else:
            data = np.load(filepath, allow_pickle=True)
            self.q_network = data['q_network'].item()
            self.target_network = data['target_network'].item()
            if 'optimizer_state' in data: self.optimizer_state = data['optimizer_state'].item()
            self.epsilon = float(data['epsilon'])
            self.steps = int(data['steps'])
            self.training_steps = int(data['training_steps'])

    def get_stats(self):
        return {
            'epsilon': self.epsilon, 'memory_size': len(self.memory),
            'training_steps': self.training_steps,
            'avg_loss': np.mean(self.loss_history) if self.loss_history and np is not None else 0,
            'avg_td_error': np.mean(self.td_error_history) if self.td_error_history and np is not None else 0,
            'beta': self.beta
        }

    def decay_epsilon_custom(self, episode, total_episodes):
        progress = episode / total_episodes
        self.epsilon = self.epsilon_end + (1.0 - self.epsilon_end) * (1 - progress) ** 2
        return self.epsilon

# ================================================================================
# SECCION 23: SARSA AGENT (CEOIA)
# ================================================================================
class SARSAAgent:
    def __init__(self, state_dim, action_dim, learning_rate=0.1, gamma=0.99,
                 epsilon=1.0, epsilon_decay=0.995, epsilon_end=0.01):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_end = epsilon_end
        self.q_table = defaultdict(lambda: np.zeros(action_dim) if np else [0.0] * action_dim)

    def _to_key(self, state):
        try:
            if np is not None and isinstance(state, np.ndarray): return tuple(state.flatten().tolist())
            elif isinstance(state, (list, tuple)): return tuple(state)
            return state
        except Exception: return tuple(str(state))

    def select_action(self, state, exploit_only=False):
        if not exploit_only and random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        key = self._to_key(state)
        q_vals = list(self.q_table.get(key, [0.0] * self.action_dim))
        return int(np.argmax(q_vals) if np else q_vals.index(max(q_vals)))

    def update(self, state, action, reward, sig_state, sig_action, done):
        # --- BLOQUE: ACTUALIZACION SARSA ---
        key = self._to_key(state)
        sig_key = self._to_key(sig_state)
        q_vals = list(self.q_table.get(key, [0.0] * self.action_dim))
        sig_q_vals = list(self.q_table.get(sig_key, [0.0] * self.action_dim))
        if done:
            q_vals[action] += self.lr * (reward - q_vals[action])
        else:
            q_vals[action] += self.lr * (reward + self.gamma * sig_q_vals[sig_action] - q_vals[action])
        self.q_table[key] = q_vals
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

# ================================================================================
# SECCION 24: ACTOR-CRITIC A2C/A3C (CEOIA - con numpy)
# ================================================================================
class ActorCritic:
    def __init__(self, state_dim, action_dim, actor_lr=0.0003, critic_lr=0.001,
                 gamma=0.99, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.max_grad_norm = max_grad_norm
        if np:
            self.actor_weights = self._init_layer(state_dim, action_dim)
            self.critic_weights = self._init_critic(state_dim)
        else:
            self.actor_weights = None
            self.critic_weights = None
        self.q_table = defaultdict(lambda: [0.0]*action_dim)
        self.policy_history = deque(maxlen=1000)
        self.value_history = deque(maxlen=1000)
        self.reward_history = deque(maxlen=1000)

    def _init_layer(self, in_dim, out_dim):
        return {'w': np.random.randn(in_dim, out_dim) * 0.01, 'b': np.zeros(out_dim)}

    def _init_critic(self, state_dim):
        return {
            'w1': np.random.randn(state_dim, 64) * np.sqrt(2.0/state_dim),
            'b1': np.zeros(64),
            'w2': np.random.randn(64, 1) * np.sqrt(2.0/64),
            'b2': np.zeros(1)
        }

    def _softmax(self, x):
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()

    def _forward_actor(self, state):
        if np is None: return [0.0]*self.action_dim
        x = np.array(state).flatten()
        logits = np.dot(x, self.actor_weights['w']) + self.actor_weights['b']
        return self._softmax(logits)

    def _forward_critic(self, state):
        if np is None: return 0.0
        x = np.array(state).flatten()
        h = np.dot(x, self.critic_weights['w1']) + self.critic_weights['b1']
        h = np.maximum(0, h)
        v = np.dot(h, self.critic_weights['w2']) + self.critic_weights['b2']
        return v[0]

    def select_action(self, state):
        probs = self._forward_actor(state)
        action = np.random.choice(self.action_dim, p=probs)
        return int(action), probs[action]

    def update(self, states, actions, rewards, sig_states, dones, next_value=0):
        # --- BLOQUE: ACTUALIZACION A2C ---
        n = len(states)
        if n == 0: return {}
        values = [self._forward_critic(s) for s in states]
        advantages = []
        gae = 0
        for i in reversed(range(n)):
            next_val = next_value if i == n - 1 else values[i + 1]
            delta = rewards[i] + self.gamma * next_val * (1 - dones[i]) - values[i]
            gae = delta + self.gamma * 0.95 * (1 - dones[i]) * gae
            advantages.insert(0, gae)
        advantages = np.array(advantages)
        if advantages.std() > 0:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        total_loss = sum(adv ** 2 for adv in advantages)
        return {'policy_loss': -np.mean(advantages), 'value_loss': total_loss/n, 'mean_advantage': np.mean(advantages)}

# ================================================================================
# SECCION 25: PPO OPTIMIZER (CEOIA)
# ================================================================================
class PPOOptimizer:
    def __init__(self, state_dim, action_dim, lr=3e-4, gamma=0.99, epsilon=0.2,
                 value_coef=0.5, entropy_coef=0.01, lam=0.95):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = lr
        self.gamma = gamma
        self.epsilon = epsilon
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.lam = lam
        if np:
            self.policy_new = self._init_policy(state_dim, action_dim)
            self.policy_old = self._init_policy(state_dim, action_dim)
            self.value_net = self._init_value_net(state_dim)
        else:
            self.policy_new = defaultdict(lambda: [0.5]*action_dim)
            self.policy_old = defaultdict(lambda: [0.5]*action_dim)
        self.memory = deque(maxlen=10000)

    def _init_policy(self, state_dim, action_dim):
        return {'w': np.random.randn(state_dim, action_dim) * 0.01, 'b': np.zeros(action_dim)}

    def _init_value_net(self, state_dim):
        return {
            'w1': np.random.randn(state_dim, 64) * np.sqrt(2.0/state_dim),
            'b1': np.zeros(64),
            'w2': np.random.randn(64, 1),
            'b2': np.zeros(1)
        }

    def _get_policy(self, state, policy):
        if np is None: return [0.5]*self.action_dim
        x = np.array(state).flatten()
        logits = np.dot(x, policy['w']) + policy['b']
        exp_logits = np.exp(logits - np.max(logits))
        return exp_logits / exp_logits.sum()

    def _get_value(self, state):
        if np is None: return 0.0
        x = np.array(state).flatten()
        h = np.dot(x, self.value_net['w1']) + self.value_net['b1']
        h = np.maximum(0, h)
        return np.dot(h, self.value_net['w2']) + self.value_net['b2']

    def select_action(self, state):
        probs = self._get_policy(state, self.policy_new)
        action = np.random.choice(self.action_dim, p=probs)
        return int(action), probs[action]

    def store(self, state, action, reward, sig_state, done, log_prob, value):
        self.memory.append({
            'state': state, 'action': action, 'reward': reward,
            'sig_state': sig_state, 'done': done,
            'log_prob': log_prob, 'value': value
        })

    def compute_gae(self, rewards, values, dones):
        # --- BLOQUE: ESTIMACION DE VENTAJA GENERALIZADA ---
        n = len(rewards)
        advantages = np.zeros(n)
        gae = 0
        for i in reversed(range(n)):
            next_value = 0 if i == n - 1 else values[i + 1]
            delta = rewards[i] + self.gamma * next_value * (1 - dones[i]) - values[i]
            gae = delta + self.gamma * self.lam * (1 - dones[i]) * gae
            advantages[i] = gae
        returns = advantages + np.array(values)
        return advantages, returns

    def update(self, epochs=10, batch_size=64):
        if len(self.memory) < batch_size: return {}
        if np:
            self.policy_old = {k: v.copy() for k, v in self.policy_new.items()}
        states = [m['state'] for m in self.memory]
        actions = [m['action'] for m in self.memory]
        rewards = [m['reward'] for m in self.memory]
        dones = [m['done'] for m in self.memory]
        values = [self._get_value(s) for s in states]
        advantages, returns = self.compute_gae(rewards, values, dones)
        if advantages.std() > 0:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        losses = []
        for _ in range(epochs):
            indices = np.random.permutation(len(states)) if np else list(range(len(states)))
            random.shuffle(indices)
            for i in range(0, len(states), batch_size):
                batch_idx = indices[i:i+batch_size]
                batch_states = [states[j] for j in batch_idx]
                batch_actions = [actions[j] for j in batch_idx]
                batch_advantages = advantages[batch_idx] if np else [advantages[j] for j in batch_idx]
                batch_returns = returns[batch_idx] if np else [returns[j] for j in batch_idx]
                ratio_loss, value_loss, entropy_loss = 0, 0, 0
                for s, a, adv, ret in zip(batch_states, batch_actions, batch_advantages, batch_returns):
                    if np is None: continue
                    probs_new = self._get_policy(s, self.policy_new)
                    probs_old = self._get_policy(s, self.policy_old)
                    ratio = probs_new[a] / (probs_old[a] + 1e-8)
                    surr1 = ratio * adv
                    surr2 = np.clip(ratio, 1-self.epsilon, 1+self.epsilon) * adv
                    ratio_loss -= min(surr1, surr2)
                    v_new = self._get_value(s)
                    value_loss += (v_new - ret) ** 2
                    entropy_loss -= np.sum(probs_new * np.log(probs_new + 1e-8))
                loss = ratio_loss + self.value_coef * value_loss + self.entropy_coef * entropy_loss
                losses.append(loss)
        self.memory.clear()
        return {'loss': np.mean(losses) if losses else 0, 'ratio_loss': np.mean([ratio_loss]) if losses else 0}

# ================================================================================
# SECCION 26: MCTS AGENT (CEOIA)
# ================================================================================
class MCTSNode:
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.children = {}
        self.visits = 0
        self.value = 0.0
        self.unexpanded = []

    def is_terminal(self):
        return len(self.children) == 0 and len(self.unexpanded) == 0

    def best_child_ucb(self, c=1.414):
        if not self.children: return None
        best, best_value = None, -float('inf')
        for child in self.children.values():
            if child.visits == 0:
                ucb = float('inf')
            else:
                ucb = child.value / child.visits + c * math.sqrt(math.log(self.visits) / child.visits)
            if ucb > best_value:
                best_value, best = ucb, child
        return best

class MCTSAgent:
    def __init__(self, state_dim, action_dim, sim_depth=50, explorations=100,
                 gamma=0.99, ucb_constant=1.414):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.sim_depth = sim_depth
        self.explorations = explorations
        self.gamma = gamma
        self.ucb_constant = ucb_constant
        self.root = None
        self.internal_model = defaultdict(lambda: np.zeros(action_dim) if np else [0.0]*action_dim)

    def build_tree(self, initial_state, possible_actions):
        self.root = MCTSNode(initial_state)
        self.root.unexpanded = possible_actions.copy()
        for _ in range(self.explorations):
            self._simulate()

    def _simulate(self):
        # --- BLOQUE: SIMULACION MCTS ---
        node = self.root
        depth = 0
        while not node.is_terminal() and not node.unexpanded:
            node = node.best_child_ucb(self.ucb_constant)
            if node is None: break
            depth += 1
        if node is None or depth >= self.sim_depth: return 0
        if node.unexpanded:
            action = random.choice(node.unexpanded)
            new_state = self._apply_action(node.state, action)
            new_node = MCTSNode(new_state, node, action)
            new_node.unexpanded = self._get_actions(new_state)
            node.children[action] = new_node
            node.unexpanded.remove(action)
            node = new_node
        reward = self._simulate_game(node.state)
        while node:
            node.visits += 1
            node.value += reward
            reward *= self.gamma
            node = node.parent
        return reward

    def _apply_action(self, state, action):
        if isinstance(state, (int, float)): return state + (action - 1) * 0.1
        elif isinstance(state, list):
            new = state.copy()
            if len(new) > action: new[action] += 0.1
            return new
        return state

    def _get_actions(self, state): return list(range(self.action_dim))

    def _simulate_game(self, state):
        total = 0
        current = state
        for _ in range(self.sim_depth):
            action = random.randint(0, self.action_dim - 1)
            q_vals = self.internal_model.get(tuple(current) if isinstance(current, list) else current, [0.0]*self.action_dim)
            if isinstance(q_vals, list) and action < len(q_vals): total += q_vals[action]
            current = self._apply_action(current, action)
        return total

    def select_best_action(self):
        if not self.root or not self.root.children:
            return random.randint(0, self.action_dim - 1)
        best_action, best_ratio = None, -float('inf')
        for action, child in self.root.children.items():
            if child.visits > 0:
                ratio = child.value / child.visits
                if ratio > best_ratio: best_ratio, best_action = ratio, action
        return best_action if best_action is not None else random.randint(0, self.action_dim - 1)

    def get_statistics(self):
        if not self.root: return {}
        stats = {'actions': {}}
        for action, child in self.root.children.items():
            stats['actions'][action] = {'visits': child.visits, 'average_value': child.value / child.visits if child.visits > 0 else 0}
        return stats

# ================================================================================
# SECCION 27: GENETIC OPTIMIZER (CEOIA)
# ================================================================================
class GeneticOptimizer:
    def __init__(self, param_bounds, pop_size=50, elite_ratio=0.1,
                 mutation_rate=0.1, crossover_rate=0.7, generations=100):
        self.param_bounds = param_bounds
        self.pop_size = pop_size
        self.elite_size = int(pop_size * elite_ratio)
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.generations = generations
        self.population = []
        self.best_individual = None
        self.best_fitness = -float('inf')
        self.history = []

    def _init_population(self):
        self.population = []
        for _ in range(self.pop_size):
            individual = {}
            for param, (low, high) in self.param_bounds.items():
                if isinstance(low, int) and isinstance(high, int):
                    individual[param] = random.randint(low, high)
                else:
                    individual[param] = random.uniform(low, high)
            self.population.append(individual)

    def _evaluate(self, individual, fitness_fn): return fitness_fn(individual)

    def _select(self, fitness_scores):
        tournament_size = 3
        selected = []
        for _ in range(len(self.population)):
            idx = random.sample(range(len(self.population)), tournament_size)
            best = max(idx, key=lambda i: fitness_scores[i])
            selected.append(self.population[best].copy())
        return selected

    def _crossover(self, parent1, parent2):
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()
        child1, child2 = {}, {}
        crossover_point = random.choice(list(parent1.keys()))
        in_child1 = False
        for key in parent1.keys():
            if key == crossover_point: in_child1 = True
            if in_child1:
                child1[key], child2[key] = parent1[key], parent2[key]
            else:
                child1[key], child2[key] = parent2[key], parent1[key]
        return child1, child2

    def _mutate(self, individual):
        mutated = individual.copy()
        for param in mutated:
            if random.random() < self.mutation_rate:
                low, high = self.param_bounds[param]
                if isinstance(low, int):
                    mutated[param] = int(random.gauss(mutated[param], (high - low) / 10))
                else:
                    mutated[param] = random.gauss(mutated[param], (high - low) / 10)
                mutated[param] = max(low, min(high, mutated[param]))
        return mutated

    def optimize(self, fitness_fn, verbose=True):
        # --- BLOQUE: EVOLUCION GENETICA ---
        self._init_population()
        for gen in range(self.generations):
            fitness_scores = [self._evaluate(ind, fitness_fn) for ind in self.population]
            if fitness_scores:
                best_idx = fitness_scores.index(max(fitness_scores))
                if fitness_scores[best_idx] > self.best_fitness:
                    self.best_fitness = fitness_scores[best_idx]
                    self.best_individual = self.population[best_idx].copy()
            self.history.append({'generation': gen, 'best_fitness': self.best_fitness, 'avg_fitness': sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0})
            if verbose and gen % 10 == 0:
                log_event(f"Gen {gen}: Mejor={self.best_fitness:.4f}", "GA")
            selected = self._select(fitness_scores)
            new_population = selected[:self.elite_size]
            while len(new_population) < self.pop_size:
                parent1, parent2 = random.sample(selected, 2)
                child1, child2 = self._crossover(parent1, parent2)
                new_population.append(self._mutate(child1))
                if len(new_population) < self.pop_size:
                    new_population.append(self._mutate(child2))
            self.population = new_population[:self.pop_size]
        return self.best_individual, self.best_fitness

    def get_history(self): return self.history

# ================================================================================
# SECCION 28: FUZZY LOGIC CONTROLLER (CEOIA)
# ================================================================================
class FuzzyLogicController:
    def __init__(self):
        self.rules = []
        self.membership_functions = {}
        self.defuzzify_method = 'centroid'

    def add_mf(self, variable, name, mf_type, params):
        if variable not in self.membership_functions:
            self.membership_functions[variable] = {}
        self.membership_functions[variable][name] = {'type': mf_type, 'params': params}

    def add_rule(self, antecedent, consequent):
        self.rules.append({'if': antecedent, 'then': consequent})

    def membership_triangle(self, x, a, b, c):
        if x <= a or x >= c: return 0
        elif a < x <= b: return (x - a) / (b - a) if (b - a) != 0 else 0
        else: return (c - x) / (c - b) if (c - b) != 0 else 0

    def membership_trapezoid(self, x, a, b, c, d):
        if x <= a or x >= d: return 0
        elif b <= x <= c: return 1
        elif a < x < b: return (x - a) / (b - a) if (b - a) != 0 else 0
        else: return (d - x) / (d - c) if (d - c) != 0 else 0

    def membership_gaussian(self, x, c, sigma):
        if sigma == 0: return 1.0 if x == c else 0
        return math.exp(-0.5 * ((x - c) / sigma) ** 2)

    def evaluate_mf(self, variable, mf_name, value):
        if variable not in self.membership_functions: return 0
        mf = self.membership_functions[variable].get(mf_name)
        if not mf: return 0
        t, p = mf['type'], mf['params']
        if t == 'triangle': return self.membership_triangle(value, *p)
        elif t == 'trapezoid': return self.membership_trapezoid(value, *p)
        elif t == 'gaussian': return self.membership_gaussian(value, *p)
        return 0

    def fuzzify(self, inputs):
        fuzzy_inputs = {}
        for var, value in inputs.items():
            if var in self.membership_functions:
                fuzzy_inputs[var] = {mf: self.evaluate_mf(var, mf, value) for mf in self.membership_functions[var]}
        return fuzzy_inputs

    def apply_rules(self, fuzzy_inputs):
        outputs = defaultdict(float)
        for rule in self.rules:
            activations = [fuzzy_inputs[var].get(mf, 0) for var, mf in rule['if'].items() if var in fuzzy_inputs and mf in fuzzy_inputs[var]]
            if activations:
                antecedent_activation = min(activations)
                for key, value in rule['then'].items():
                    if isinstance(value, (int, float)): mf_name, weight = key, value
                    else: mf_name, weight = value, 1.0
                    if isinstance(weight, (int, float)): outputs[mf_name] = max(outputs[mf_name], antecedent_activation * weight)
        return dict(outputs)

    def defuzzify(self, fuzzy_outputs, output_range):
        # --- BLOQUE: DESFUZZIFICACION CENTROID/MOM ---
        if not fuzzy_outputs: return (output_range[0] + output_range[1]) / 2
        if self.defuzzify_method == 'centroid':
            num, den = 0.0, 0.0
            output_mfs = self.membership_functions.get('output', {})
            for value in [i * 0.1 for i in range(int(output_range[0]*10), int(output_range[1]*10)+1)]:
                max_mem = 0
                for mf, grade in fuzzy_outputs.items():
                    if mf in output_mfs and isinstance(grade, (int, float)):
                        membership = self.evaluate_mf('output', mf, value)
                        max_mem = max(max_mem, min(grade, membership))
                num += value * max_mem
                den += max_mem
            return num / den if den > 1e-10 else (output_range[0] + output_range[1]) / 2
        elif self.defuzzify_method == 'mom':
            max_deg = max(fuzzy_outputs.values()) if fuzzy_outputs else 0
            candidates = [k for k, v in fuzzy_outputs.items() if isinstance(v, (int, float)) and abs(v - max_deg) < 1e-10]
            numeric_candidates = [float(k) for k in candidates if isinstance(k, (int, float))]
            return sum(numeric_candidates) / len(numeric_candidates) if numeric_candidates else (output_range[0] + output_range[1]) / 2
        return (output_range[0] + output_range[1]) / 2

    def evaluate(self, inputs, output_range=(0, 1)):
        fuzzy_inputs = self.fuzzify(inputs)
        fuzzy_outputs = self.apply_rules(fuzzy_inputs)
        return self.defuzzify(fuzzy_outputs, output_range)

# ================================================================================
# SECCION 29: KALMAN FILTER (CEOIA)
# ================================================================================
class KalmanFilter:
    def __init__(self, state_dim, obs_dim, Q=None, R=None):
        self.state_dim = state_dim
        self.obs_dim = obs_dim
        if np:
            self.x = np.zeros(state_dim)
            self.P = np.eye(state_dim)
            self.Q = Q if Q is not None else np.eye(state_dim) * 0.01
            self.R = R if R is not None else np.eye(obs_dim) * 0.1
            self.A = np.eye(state_dim)
            self.H = np.eye(obs_dim, state_dim)
            self.B = np.zeros((state_dim, obs_dim))
        else:
            self.x = [0.0] * state_dim
            self.P = [[1.0 if i == j else 0 for j in range(state_dim)] for i in range(state_dim)]
            self.Q = [[0.01 if i == j else 0 for j in range(state_dim)] for i in range(state_dim)]
            self.R = [[0.1 if i == j else 0 for j in range(obs_dim)] for i in range(obs_dim)]
            self.A = [[1.0 if i == j else 0 for j in range(state_dim)] for i in range(state_dim)]
            self.H = [[1.0 if i == j else 0 for j in range(state_dim)] for i in range(obs_dim)]

    def predict(self, u=None):
        # --- BLOQUE: PREDICCION DE ESTADO ---
        if np:
            if u is not None:
                self.x = np.dot(self.A, self.x) + np.dot(self.B, u)
            else:
                self.x = np.dot(self.A, self.x)
            self.P = np.dot(np.dot(self.A, self.P), self.A.T) + self.Q
        else:
            new_x = []
            for i in range(self.state_dim):
                val = sum(self.A[i][j] * self.x[j] for j in range(self.state_dim))
                if u is not None and i < len(u):
                    val += (self.B[i][0] if isinstance(self.B[0], list) else self.B[i]) * u[0]
                new_x.append(val)
            self.x = new_x
        return self.x

    def update(self, z):
        # --- BLOQUE: ACTUALIZACION CON OBSERVACION ---
        if np:
            y = np.array(z) - np.dot(self.H, self.x)
            S = np.dot(np.dot(self.H, self.P), self.H.T) + self.R
            K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))
            self.x = self.x + np.dot(K, y)
            self.P = np.dot((np.eye(self.state_dim) - np.dot(K, self.H)), self.P)
        else:
            for i in range(self.state_dim):
                for j in range(min(self.obs_dim, len(z))):
                    self.x[i] += self.P[i][j] * (z[j] - self.x[j]) * 0.1
        return self.x

    def get_state(self): return self.x

    def get_uncertainty(self):
        if np: return np.trace(self.P)
        else: return sum(self.P[i][i] for i in range(self.state_dim))

# ================================================================================
# SECCION 30: CURIOSITY MODULE (CEOIA) - VERSION CORREGIDA Y FUNCIONAL
# ================================================================================
class CuriosityModule:
    """
    Modulo de Curiosidad basado en Pathak et al. 2017
    "Curiosity-driven Exploration by Self-supervised Prediction"
    
    Predice el siguiente estado dado (state, action) y genera
    recompensa intrinseca proporcional al error de prediccion.
    """
    
    def __init__(self, state_dim, action_dim, lr=0.001, gamma=0.99,
                 intrinsic_reward_scale=1.0, novelty_weight=0.5,
                 hidden_size=128, use_layer_norm=True):
        # --- BLOQUE: CONFIGURACION ---
        self.state_dim = max(1, int(state_dim))
        self.action_dim = max(1, int(action_dim))
        self.lr = float(lr)
        self.gamma = float(gamma)
        self.intrinsic_reward_scale = float(intrinsic_reward_scale)
        self.novelty_weight = max(0.0, min(1.0, float(novelty_weight)))
        self.hidden_size = max(32, int(hidden_size))
        self.use_layer_norm = bool(use_layer_norm)
        
        # --- BLOQUE: ESTADISTICAS DE NORMALIZACION (running statistics) ---
        self._state_mean = None
        self._state_std = None
        self._error_mean = 1.0
        self._error_std = 1.0
        self._update_count = 0
        
        # --- BLOQUE: INICIALIZACION DE MODELOS ---
        if np is not None:
            self.forward_model = self._init_forward_model()
            self.inverse_model = self._init_inverse_model()
            self._forward_optimizer = self._init_optimizer(self.forward_model)
            self._inverse_optimizer = self._init_optimizer(self.inverse_model)
        else:
            self.forward_model = {}
            self.inverse_model = {}
            self._forward_optimizer = None
            self._inverse_optimizer = None
            
        # --- BLOQUE: MEMORIAS ---
        self.state_buffer = deque(maxlen=2000)
        self.state_counts = defaultdict(int)
        self.episodic_curiosity = deque(maxlen=1000)
        self._recent_errors = deque(maxlen=100)
        
        log_event(f"CuriosityModule inicializado: state={self.state_dim}, action={self.action_dim}, hidden={self.hidden_size}", "CURIO")

    def _init_forward_model(self):
        """Modelo Forward: (state, action) -> next_state"""
        input_dim = self.state_dim + self.action_dim
        return {
            'w1': np.random.randn(input_dim, self.hidden_size) * np.sqrt(2.0 / max(input_dim, 1)),
            'b1': np.zeros(self.hidden_size),
            'w2': np.random.randn(self.hidden_size, self.hidden_size // 2) * np.sqrt(2.0 / self.hidden_size),
            'b2': np.zeros(self.hidden_size // 2),
            'w3': np.random.randn(self.hidden_size // 2, self.state_dim) * np.sqrt(2.0 / max(self.hidden_size // 2, 1)),
            'b3': np.zeros(self.state_dim),
            # Layer normalization parameters
            'ln1_gamma': np.ones(self.hidden_size),
            'ln1_beta': np.zeros(self.hidden_size),
            'ln2_gamma': np.ones(self.hidden_size // 2),
            'ln2_beta': np.zeros(self.hidden_size // 2),
        }

    def _init_inverse_model(self):
        """Modelo Inverso: (state, next_state) -> action"""
        input_dim = self.state_dim * 2
        return {
            'w1': np.random.randn(input_dim, self.hidden_size) * np.sqrt(2.0 / max(input_dim, 1)),
            'b1': np.zeros(self.hidden_size),
            'w2': np.random.randn(self.hidden_size, self.hidden_size // 2) * np.sqrt(2.0 / self.hidden_size),
            'b2': np.zeros(self.hidden_size // 2),
            'w3': np.random.randn(self.hidden_size // 2, self.action_dim) * np.sqrt(2.0 / max(self.hidden_size // 2, 1)),
            'b3': np.zeros(self.action_dim),
            # Layer normalization parameters
            'ln1_gamma': np.ones(self.hidden_size),
            'ln1_beta': np.zeros(self.hidden_size),
            'ln2_gamma': np.ones(self.hidden_size // 2),
            'ln2_beta': np.zeros(self.hidden_size // 2),
        }

    def _init_optimizer(self, model):
        """Inicializa estado del optimizador Adam"""
        if np is None:
            return None
        return {
            'm': {k: np.zeros_like(v) for k, v in model.items()},
            'v': {k: np.zeros_like(v) for k, v in model.items()},
            't': 0,
            'beta1': 0.9,
            'beta2': 0.999,
            'eps': 1e-8
        }

    def _one_hot(self, action):
        """Convierte accion escalar a vector one-hot"""
        vec = [0.0] * self.action_dim
        idx = int(action) if isinstance(action, (int, float)) else 0
        idx = max(0, min(self.action_dim - 1, idx))
        vec[idx] = 1.0
        return vec

    def _ensure_array(self, data, expected_len):
        """Normaliza datos a array de longitud fija"""
        if np is None:
            if isinstance(data, (list, tuple)):
                data_list = list(data)
                if len(data_list) < expected_len:
                    return data_list + [0.0] * (expected_len - len(data_list))
                elif len(data_list) > expected_len:
                    return data_list[:expected_len]
                return data_list
            if isinstance(data, (int, float)):
                return [float(data)] + [0.0] * (expected_len - 1)
            return [0.0] * expected_len
        
        arr = np.array(data, dtype=np.float64).flatten()
        if len(arr) < expected_len:
            return np.pad(arr, (0, expected_len - len(arr)), mode='constant')
        elif len(arr) > expected_len:
            return arr[:expected_len]
        return arr

    def _normalize_state(self, state_array):
        """Normaliza estado usando running statistics"""
        if np is None:
            return state_array
        
        arr = np.array(state_array, dtype=np.float64)
        
        # Inicializar si es la primera vez
        if self._state_mean is None:
            self._state_mean = arr.copy()
            self._state_std = np.ones_like(arr)
            return arr
        
        # Actualizar running statistics (Welford's online algorithm)
        self._update_count += 1
        delta = arr - self._state_mean
        self._state_mean += delta / self._update_count
        delta2 = arr - self._state_mean
        self._state_std = np.sqrt(
            ((self._update_count - 1) * (self._state_std ** 2) + delta * delta2) / max(self._update_count, 1)
        )
        
        # Normalizar
        normalized = (arr - self._state_mean) / (self._state_std + 1e-8)
        # Clip para estabilidad
        return np.clip(normalized, -10.0, 10.0)

    def _layer_norm(self, x, gamma, beta, eps=1e-5):
        """Aplica layer normalization"""
        if np is None:
            return x
        mean = np.mean(x)
        std = np.std(x) + eps
        return gamma * (x - mean) / std + beta

    def _relu(self, x):
        """ReLU activation"""
        if np is None:
            return [max(0.0, v) for v in x] if isinstance(x, (list, tuple)) else max(0.0, x)
        return np.maximum(0, x)

    def _softmax_stable(self, x):
        """Softmax numericamente estable"""
        if np is None:
            if not x:
                return []
            x_max = max(x)
            exp_x = [math.exp(v - x_max) for v in x]
            sum_exp = sum(exp_x)
            return [v / sum_exp for v in exp_x] if sum_exp > 0 else [1.0 / len(x)] * len(x)
        
        x_arr = np.array(x, dtype=np.float64)
        x_max = np.max(x_arr)
        exp_x = np.exp(x_arr - x_max)
        sum_exp = np.sum(exp_x)
        return exp_x / sum_exp if sum_exp > 0 else np.ones_like(x_arr) / len(x_arr)

    def _forward_pass(self, model, x, is_forward_model=True):
        """Forward pass completo con layer norm opcional"""
        if np is None:
            return [0.0] * (self.state_dim if is_forward_model else self.action_dim)
        
        # Capa 1
        z1 = np.dot(x, model['w1']) + model['b1']
        if self.use_layer_norm:
            z1 = self._layer_norm(z1, model['ln1_gamma'], model['ln1_beta'])
        h1 = self._relu(z1)
        
        # Capa 2
        z2 = np.dot(h1, model['w2']) + model['b2']
        if self.use_layer_norm:
            z2 = self._layer_norm(z2, model['ln2_gamma'], model['ln2_beta'])
        h2 = self._relu(z2)
        
        # Capa 3 (salida)
        out = np.dot(h2, model['w3']) + model['b3']
        
        # Cache para backward
        cache = {
            'x': x, 'z1': z1, 'h1': h1, 'z2': z2, 'h2': h2, 'out': out
        }
        return out, cache

    def _adam_step(self, model, optimizer, grads, lr=None):
        """Actualiza parametros usando Adam optimizer"""
        if np is None or optimizer is None:
            return
        
        lr = lr or self.lr
        optimizer['t'] += 1
        t = optimizer['t']
        
        for key in model.keys():
            if key not in grads:
                continue
            
            grad = grads[key]
            
            # Momentum
            optimizer['m'][key] = optimizer['beta1'] * optimizer['m'][key] + (1 - optimizer['beta1']) * grad
            # Velocity
            optimizer['v'][key] = optimizer['beta2'] * optimizer['v'][key] + (1 - optimizer['beta2']) * (grad ** 2)
            
            # Bias correction
            m_hat = optimizer['m'][key] / (1 - optimizer['beta1'] ** t)
            v_hat = optimizer['v'][key] / (1 - optimizer['beta2'] ** t)
            
            # Update
            model[key] -= lr * m_hat / (np.sqrt(v_hat) + optimizer['eps'])

    def _forward_model_predict(self, state, action):
        """Predice siguiente estado dado (state, action)"""
        if np is None:
            return self._ensure_array(state, self.state_dim)
        
        try:
            # Normalizar y preparar inputs
            state_norm = self._normalize_state(self._ensure_array(state, self.state_dim))
            action_vec = self._one_hot(action)
            action_arr = np.array(action_vec, dtype=np.float64)
            
            # Concatenar
            x = np.concatenate([state_norm, action_arr])
            
            # Forward pass
            pred, _ = self._forward_pass(self.forward_model, x, is_forward_model=True)
            
            # Denormalizar salida
            if self._state_mean is not None and self._state_std is not None:
                pred = pred * (self._state_std + 1e-8) + self._state_mean
            
            return pred.flatten()
            
        except Exception as e:
            log_event(f"Forward predict error: {e}", "CURIO")
            return self._ensure_array(state, self.state_dim)

    def _inverse_model_predict(self, state, next_state):
        """Predice accion dado (state, next_state)"""
        if np is None:
            return [1.0 / self.action_dim] * self.action_dim
        
        try:
            state_norm = self._normalize_state(self._ensure_array(state, self.state_dim))
            next_norm = self._normalize_state(self._ensure_array(next_state, self.state_dim))
            
            x = np.concatenate([state_norm, next_norm])
            
            logits, _ = self._forward_pass(self.inverse_model, x, is_forward_model=False)
            probs = self._softmax_stable(logits)
            
            return probs.tolist() if hasattr(probs, 'tolist') else list(probs)
            
        except Exception:
            return [1.0 / self.action_dim] * self.action_dim

    def compute_intrinsic_reward(self, state, action, next_state):
        """
        Calcula recompensa intrinseca combinando:
        - prediction_error: error del forward model
        - novelty: frecuencia de visita al estado
        """
        # --- Forward prediction ---
        try:
            pred_next = self._forward_model_predict(state, action)
            actual_next = self._ensure_array(next_state, self.state_dim)
            
            if np is not None:
                pred_arr = np.array(pred_next, dtype=np.float64)
                actual_arr = np.array(actual_next, dtype=np.float64)
                diff = pred_arr - actual_arr
                
                # Error normalizado por dimension
                raw_error = float(np.linalg.norm(diff))
                normalized_error = raw_error / math.sqrt(self.state_dim)
            else:
                pred_list = pred_next if isinstance(pred_next, (list, tuple)) else [pred_next]
                actual_list = actual_next if isinstance(actual_next, (list, tuple)) else [actual_next]
                if len(pred_list) > 0 and len(actual_list) > 0:
                    raw_error = abs(pred_list[0] - actual_list[0])
                    normalized_error = raw_error / math.sqrt(max(len(pred_list), 1))
                else:
                    normalized_error = 0.0
            
            # Actualizar estadisticas de error para normalizacion adaptativa
            self._recent_errors.append(normalized_error)
            if len(self._recent_errors) > 10:
                self._error_mean = 0.9 * self._error_mean + 0.1 * normalized_error
                self._error_std = 0.9 * self._error_std + 0.1 * abs(normalized_error - self._error_mean)
            
            # Normalizar error por running statistics
            adaptive_error = normalized_error / (self._error_std + 1e-8)
            adaptive_error = min(adaptive_error, 10.0)  # Clip extremo
            
        except Exception as e:
            log_event(f"Prediction error in intrinsic reward: {e}", "CURIO")
            adaptive_error = 0.0

        # --- Novelty computation (con hashing LSH aproximado) ---
        try:
            if np is not None:
                state_arr = np.array(self._ensure_array(state, self.state_dim), dtype=np.float64)
                # Proyectar a espacio de hash de baja dimension
                if not hasattr(self, '_hash_projections'):
                    self._hash_projections = np.random.randn(4, self.state_dim)
                hash_vals = np.dot(self._hash_projections, state_arr)
                # Cuantizar
                state_key = tuple(np.sign(hash_vals).astype(int))
            else:
                state_list = self._ensure_array(state, self.state_dim)
                # Hash simple por rangos
                buckets = []
                for i, v in enumerate(state_list[:4]):
                    buckets.append(int(v * 10) // 3)
                state_key = tuple(buckets)
            
            # Contar visitas
            visit_count = self.state_counts.get(state_key, 0)
            novelty = 1.0 / math.sqrt(1.0 + visit_count)  # Decaimiento mas suave
            self.state_counts[state_key] = visit_count + 1
            
        except Exception:
            novelty = 0.5

        # --- Combinacion final ---
        intrinsic = self.intrinsic_reward_scale * (
            self.novelty_weight * adaptive_error + 
            (1.0 - self.novelty_weight) * novelty
        )
        
        # Guardar en buffer
        try:
            self.state_buffer.append((state, action, next_state, intrinsic))
        except Exception:
            pass
        
        return float(intrinsic)

    def update_models(self, state, action, next_state):
        """
        Entrena forward e inverse models con un paso de gradiente.
        DEBE ser llamado despues de compute_intrinsic_reward en cada paso.
        """
        if np is None:
            return {'forward_error': 0.0, 'inverse_loss': 0.0, 'trained': False}
        
        try:
            # --- Preparar datos ---
            state_norm = self._normalize_state(self._ensure_array(state, self.state_dim))
            action_vec = self._one_hot(action)
            action_arr = np.array(action_vec, dtype=np.float64)
            next_norm = self._normalize_state(self._ensure_array(next_state, self.state_dim))
            
            # ============ FORWARD MODEL UPDATE ============
            x_fwd = np.concatenate([state_norm, action_arr])
            pred_fwd, cache_fwd = self._forward_pass(self.forward_model, x_fwd, is_forward_model=True)
            
            # Error y loss
            error_fwd = pred_fwd - next_norm
            forward_loss = float(np.mean(error_fwd ** 2))
            
            # Backward pass manual
            # dL/dout = 2 * error / N
            grad_out = (2.0 / self.state_dim) * error_fwd
            
            # Capa 3
            grad_w3 = np.outer(cache_fwd['h2'], grad_out)
            grad_b3 = grad_out
            grad_h2 = np.dot(self.forward_model['w3'], grad_out)
            
            # ReLU gradient capa 2
            grad_z2 = grad_h2 * (cache_fwd['z2'] > 0).astype(float)
            if self.use_layer_norm:
                # Simplificacion: gradiente aproximado para layer norm
                grad_z2 = grad_z2 * self.forward_model['ln2_gamma']
            
            grad_w2 = np.outer(cache_fwd['h1'], grad_z2)
            grad_b2 = grad_z2
            grad_h1 = np.dot(self.forward_model['w2'], grad_z2)
            
            # ReLU gradient capa 1
            grad_z1 = grad_h1 * (cache_fwd['z1'] > 0).astype(float)
            if self.use_layer_norm:
                grad_z1 = grad_z1 * self.forward_model['ln1_gamma']
            
            grad_w1 = np.outer(cache_fwd['x'], grad_z1)
            grad_b1 = grad_z1
            
            # Gradient clipping
            clip_val = 1.0
            grads_fwd = {
                'w1': np.clip(grad_w1, -clip_val, clip_val),
                'b1': np.clip(grad_b1, -clip_val, clip_val),
                'w2': np.clip(grad_w2, -clip_val, clip_val),
                'b2': np.clip(grad_b2, -clip_val, clip_val),
                'w3': np.clip(grad_w3, -clip_val, clip_val),
                'b3': np.clip(grad_b3, -clip_val, clip_val),
            }
            # Layer norm gradients (simplificado)
            if self.use_layer_norm:
                grads_fwd['ln1_gamma'] = np.zeros_like(self.forward_model['ln1_gamma'])
                grads_fwd['ln1_beta'] = np.zeros_like(self.forward_model['ln1_beta'])
                grads_fwd['ln2_gamma'] = np.zeros_like(self.forward_model['ln2_gamma'])
                grads_fwd['ln2_beta'] = np.zeros_like(self.forward_model['ln2_beta'])
            
            # Adam update
            self._adam_step(self.forward_model, self._forward_optimizer, grads_fwd)
            
            # ============ INVERSE MODEL UPDATE ============
            x_inv = np.concatenate([state_norm, next_norm])
            logits_inv, cache_inv = self._forward_pass(self.inverse_model, x_inv, is_forward_model=False)
            probs_inv = self._softmax_stable(logits_inv)
            
            # Target: one-hot
            target_inv = np.array(action_vec, dtype=np.float64)
            
            # Cross-entropy gradient: dL/dlogit = probs - target
            grad_logits = probs_inv - target_inv
            inverse_loss = float(-np.sum(target_inv * np.log(probs_inv + 1e-8)))
            
            # Backward
            grad_w3_inv = np.outer(cache_inv['h2'], grad_logits)
            grad_b3_inv = grad_logits
            grad_h2_inv = np.dot(self.inverse_model['w3'], grad_logits)
            
            grad_z2_inv = grad_h2_inv * (cache_inv['z2'] > 0).astype(float)
            if self.use_layer_norm:
                grad_z2_inv = grad_z2_inv * self.inverse_model['ln2_gamma']
            
            grad_w2_inv = np.outer(cache_inv['h1'], grad_z2_inv)
            grad_b2_inv = grad_z2_inv
            grad_h1_inv = np.dot(self.inverse_model['w2'], grad_z2_inv)
            
            grad_z1_inv = grad_h1_inv * (cache_inv['z1'] > 0).astype(float)
            if self.use_layer_norm:
                grad_z1_inv = grad_z1_inv * self.inverse_model['ln1_gamma']
            
            grad_w1_inv = np.outer(cache_inv['x'], grad_z1_inv)
            grad_b1_inv = grad_z1_inv
            
            # Clip
            grads_inv = {
                'w1': np.clip(grad_w1_inv, -clip_val, clip_val),
                'b1': np.clip(grad_b1_inv, -clip_val, clip_val),
                'w2': np.clip(grad_w2_inv, -clip_val, clip_val),
                'b2': np.clip(grad_b2_inv, -clip_val, clip_val),
                'w3': np.clip(grad_w3_inv, -clip_val, clip_val),
                'b3': np.clip(grad_b3_inv, -clip_val, clip_val),
            }
            if self.use_layer_norm:
                grads_inv['ln1_gamma'] = np.zeros_like(self.inverse_model['ln1_gamma'])
                grads_inv['ln1_beta'] = np.zeros_like(self.inverse_model['ln1_beta'])
                grads_inv['ln2_gamma'] = np.zeros_like(self.inverse_model['ln2_gamma'])
                grads_inv['ln2_beta'] = np.zeros_like(self.inverse_model['ln2_beta'])
            
            self._adam_step(self.inverse_model, self._inverse_optimizer, grads_inv)
            
            return {
                'forward_error': forward_loss,
                'inverse_loss': inverse_loss,
                'trained': True,
                'prediction_error': float(np.linalg.norm(error_fwd))
            }
            
        except Exception as e:
            log_event(f"Update models error: {e}", "CURIO")
            return {'forward_error': 0.0, 'inverse_loss': 0.0, 'trained': False}

    def get_novel_states(self, k=5):
        """Retorna los k estados mas novedosos del buffer"""
        if not self.state_buffer:
            return []
        
        novelties = []
        for state, action, next_state, intrinsic in self.state_buffer:
            try:
                if np is not None:
                    state_arr = np.array(self._ensure_array(state, self.state_dim), dtype=np.float64)
                    if not hasattr(self, '_hash_projections'):
                        self._hash_projections = np.random.randn(4, self.state_dim)
                    hash_vals = np.dot(self._hash_projections, state_arr)
                    state_key = tuple(np.sign(hash_vals).astype(int))
                else:
                    state_list = self._ensure_array(state, self.state_dim)
                    buckets = [int(v * 10) // 3 for v in state_list[:4]]
                    state_key = tuple(buckets)
                
                visit_count = self.state_counts.get(state_key, 0)
                novelty_score = 1.0 / (1.0 + visit_count)
                novelties.append((novelty_score, state, intrinsic))
            except Exception:
                continue
        
        novelties.sort(reverse=True, key=lambda x: x[0])
        return [(s, i) for _, s, i in novelties[:k]]

    def get_stats(self):
        """Retorna estadisticas del modulo para debugging"""
        return {
            'state_dim': self.state_dim,
            'action_dim': self.action_dim,
            'hidden_size': self.hidden_size,
            'buffer_size': len(self.state_buffer),
            'unique_states_visited': len(self.state_counts),
            'mean_recent_error': self._error_mean,
            'std_recent_error': self._error_std,
            'updates_count': self._update_count,
            'forward_params': sum(v.size for v in self.forward_model.values()) if np else 0,
            'inverse_params': sum(v.size for v in self.inverse_model.values()) if np else 0,
        }


# ================================================================================
# SECCION 31: NEURAL Q APPROXIMATOR (CEOIA)
# ================================================================================
class NeuralQApproximator:
    def __init__(self, state_dim, action_dim, hidden_sizes=[64, 32], lr=0.001, optimizer='adam'):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = lr
        if np:
            layers = [state_dim] + hidden_sizes + [action_dim]
            self.weights, self.biases = [], []
            for i in range(len(layers) - 1):
                w = np.random.randn(layers[i], layers[i+1]) * np.sqrt(2.0/layers[i])
                b = np.zeros(layers[i+1])
                self.weights.append(w)
                self.biases.append(b)
        else:
            self.q_table = defaultdict(lambda: [0.0]*action_dim)

    def _forward(self, state):
        if np is None:
            key = tuple(state) if isinstance(state, (list, tuple)) else state
            return self.q_table.get(key, [0.0]*self.action_dim)
        x = np.array(state).flatten()
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            x = np.dot(x, w) + b
            if i < len(self.weights) - 1: x = np.maximum(0, x)
        return x

    def predict(self, state): return self._forward(state)

    def update(self, state, target):
        if np is None: return
        x = np.array(state).flatten()
        activations = [x]
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            x = np.dot(x, w) + b
            activations.append(x)
            if i < len(self.weights) - 1:
                x = np.maximum(0, x)
                activations.append(x)
        output = activations[-1]
        error = output - target
        for i in reversed(range(len(self.weights))):
            grad_w = np.outer(activations[i], error)
            grad_b = error
            self.weights[i] -= self.lr * grad_w
            self.biases[i] -= self.lr * grad_b
            if i > 0:
                error = np.dot(self.weights[i], error)
                error = error * (activations[i] > 0).astype(float)

    def get_q_value(self, state, action):
        q_values = self.predict(state)
        return q_values[action] if action < len(q_values) else 0

# ================================================================================
# SECCION 32: META-LEARNER (CEOIA) - VERSION CORREGIDA Y FUNCIONAL
# ================================================================================
class MetaLearner:
    """
    Meta-Learner basado en MAML (Model-Agnostic Meta-Learning).
    Aprende una inicializacion de parametros que permite adaptacion rapida
    a nuevas tareas con pocos ejemplos.
    """
    
    def __init__(self, state_dim, action_dim, meta_lr=0.001, inner_lr=0.1,
                 inner_steps=5, meta_batch_size=10):
        # --- BLOQUE: CONFIGURACION ---
        self.state_dim = max(1, int(state_dim))
        self.action_dim = max(1, int(action_dim))
        self.meta_lr = float(meta_lr)
        self.inner_lr = float(inner_lr)
        self.inner_steps = max(1, int(inner_steps))
        self.meta_batch_size = max(1, int(meta_batch_size))
        self.alpha = self.inner_lr  # Tasa de adaptacion interna
        self.beta = 0.1  # Regularizacion
        
        # --- BLOQUE: INICIALIZACION DE PESOS ---
        if np is not None:
            self.slow_weights = self._init_weights()
            self.fast_weights = {k: v.copy() for k, v in self.slow_weights.items()}
        else:
            # Fallback sin numpy: tabla Q simple
            self.slow_weights = defaultdict(lambda: [0.0] * self.action_dim)
            self.fast_weights = defaultdict(lambda: [0.0] * self.action_dim)
        
        # --- BLOQUE: MEMORIAS ---
        self.task_memory = deque(maxlen=1000)
        self.task_distributions = defaultdict(list)
        self.adaptation_history = deque(maxlen=100)
        self.meta_gradient_history = deque(maxlen=100)
        
        log_event(f"MetaLearner inicializado: state={self.state_dim}, action={self.action_dim}", "META")

    def _init_weights(self):
        """Inicializa pesos de red neuronal con Xavier/He initialization."""
        if np is None:
            return {}
        return {
            'w1': np.random.randn(self.state_dim, 32) * np.sqrt(2.0 / max(self.state_dim, 1)),
            'b1': np.zeros(32),
            'w2': np.random.randn(32, 32) * np.sqrt(2.0 / 32),
            'b2': np.zeros(32),
            'w3': np.random.randn(32, self.action_dim) * np.sqrt(2.0 / 32),
            'b3': np.zeros(self.action_dim)
        }

    def _preprocess_input(self, x):
        """Normaliza y valida dimension de entrada."""
        if np is None:
            if isinstance(x, (list, tuple)):
                x_list = list(x)
                if len(x_list) < self.state_dim:
                    x_list.extend([0.0] * (self.state_dim - len(x_list)))
                elif len(x_list) > self.state_dim:
                    x_list = x_list[:self.state_dim]
                return x_list
            return [float(x)] + [0.0] * (self.state_dim - 1)
        
        # Con numpy
        if not isinstance(x, np.ndarray):
            x = np.array(x, dtype=np.float32)
        x = x.flatten()
        
        if len(x) < self.state_dim:
            x = np.pad(x, (0, self.state_dim - len(x)), mode='constant')
        elif len(x) > self.state_dim:
            x = x[:self.state_dim]
        
        return x.astype(np.float32)

    def _forward(self, x, weights):
        """
        Forward pass completo con 2 capas ocultas.
        Retorna distribucion de probabilidad sobre acciones.
        """
        if np is None:
            # Fallback: retornar distribucion uniforme
            return [1.0 / self.action_dim] * self.action_dim
        
        # Validar pesos
        if not weights or 'w1' not in weights:
            return [1.0 / self.action_dim] * self.action_dim
        
        try:
            # Capa 1
            z1 = np.dot(x, weights['w1']) + weights['b1']
            h1 = np.maximum(0, z1)  # ReLU
            
            # Capa 2
            z2 = np.dot(h1, weights['w2']) + weights['b2']
            h2 = np.maximum(0, z2)  # ReLU
            
            # Capa de salida
            logits = np.dot(h2, weights['w3']) + weights['b3']
            
            # Softmax estable
            logits_max = np.max(logits)
            exp_logits = np.exp(logits - logits_max)
            probs = exp_logits / np.sum(exp_logits)
            
            return probs
            
        except Exception as e:
            log_event(f"Forward error: {e}", "META")
            return [1.0 / self.action_dim] * self.action_dim

    def _compute_gradients_manual(self, states, actions, rewards, weights):
        """
        Computa gradientes manualmente via backpropagation.
        Mas eficiente que diferenciacion automatica para redes pequenas.
        """
        if np is None or len(states) == 0:
            return {}
        
        grads = {k: np.zeros_like(v) for k, v in weights.items()}
        total_loss = 0.0
        
        for s, a, r in zip(states, actions, rewards):
            # Forward pass con cache
            x = self._preprocess_input(s)
            
            # Capa 1
            z1 = np.dot(x, weights['w1']) + weights['b1']
            h1 = np.maximum(0, z1)
            
            # Capa 2
            z2 = np.dot(h1, weights['w2']) + weights['b2']
            h2 = np.maximum(0, z2)
            
            # Salida
            logits = np.dot(h2, weights['w3']) + weights['b3']
            logits_max = np.max(logits)
            exp_logits = np.exp(logits - logits_max)
            probs = exp_logits / np.sum(exp_logits)
            
            # Loss: negative log-likelihood ponderado por recompensa
            if 0 <= a < len(probs):
                loss = -r * np.log(max(probs[a], 1e-8))
                total_loss += loss
                
                # Backpropagation
                # Gradiente de salida
                dlogits = probs.copy()
                dlogits[a] -= 1.0
                dlogits *= -r  # Ponderar por recompensa
                
                # Capa 3
                grads['w3'] += np.outer(h2, dlogits)
                grads['b3'] += dlogits
                dh2 = np.dot(weights['w3'], dlogits)
                dz2 = dh2 * (z2 > 0).astype(float)
                
                # Capa 2
                grads['w2'] += np.outer(h1, dz2)
                grads['b2'] += dz2
                dh1 = np.dot(weights['w2'], dz2)
                dz1 = dh1 * (z1 > 0).astype(float)
                
                # Capa 1
                grads['w1'] += np.outer(x, dz1)
                grads['b1'] += dz1
        
        # Promediar
        n = len(states)
        for k in grads:
            grads[k] /= n
        
        # Gradient clipping
        clip_value = 1.0
        for k in grads:
            np.clip(grads[k], -clip_value, clip_value, out=grads[k])
        
        return grads, total_loss / n

    def inner_update(self, gradients):
        """
        Actualiza pesos rapidos (fast_weights) con gradientes de la tarea.
        Esto es el "inner loop" de MAML.
        """
        if np is None:
            return
        
        for key in self.fast_weights:
            if key in gradients:
                self.fast_weights[key] -= self.alpha * gradients[key]

    def compute_gradients(self, states, actions, rewards):
        """
        Wrapper para compatibilidad hacia atras.
        Usa el nuevo metodo manual de gradientes.
        """
        grads, loss = self._compute_gradients_manual(states, actions, rewards, self.fast_weights)
        return grads

    def meta_update(self, task_gradients):
        """
        Actualiza pesos lentos (slow_weights) con gradientes meta.
        Esto es el "outer loop" de MAML.
        """
        if np is None:
            return
        
        for key in task_gradients:
            if key in self.slow_weights:
                self.slow_weights[key] -= self.meta_lr * task_gradients[key]
        
        # Actualizar fast_weights a los nuevos slow_weights
        self.fast_weights = {k: v.copy() for k, v in self.slow_weights.items()}

    def adapt_to_task(self, task_data, n_steps=None):
        """
        Adapta el modelo a una nueva tarea con pocos ejemplos.
        
        Args:
            task_data: Lista de dicts {'state': ..., 'action': ..., 'reward': ...}
            n_steps: Numero de pasos de adaptacion interna
        
        Returns:
            dict con gradientes acumulados y estadisticas
        """
        if n_steps is None:
            n_steps = self.inner_steps
        
        if not task_data:
            return {}
        
        # Reset fast_weights a slow_weights (inicializacion meta-aprendida)
        if np is not None:
            self.fast_weights = {k: v.copy() for k, v in self.slow_weights.items()}
        
        accumulated_grads = {}
        total_loss = 0.0
        
        for step in range(n_steps):
            # Preparar datos
            states, actions, rewards = [], [], []
            for d in task_data:
                states.append(d['state'])
                actions.append(int(d['action']))
                rewards.append(float(d['reward']))
            
            # Computar gradientes y actualizar fast_weights
            grads, loss = self._compute_gradients_manual(states, actions, rewards, self.fast_weights)
            total_loss += loss
            
            # Acumular gradientes para meta-actualizacion
            for key, grad in grads.items():
                if key not in accumulated_grads:
                    accumulated_grads[key] = np.zeros_like(grad) if np is not None else [0.0]
                if np is not None:
                    accumulated_grads[key] += grad
                else:
                    accumulated_grads[key] = [a + b for a, b in zip(accumulated_grads[key], grad)]
            
            # Inner update
            self.inner_update(grads)
        
        # Promediar gradientes acumulados
        if np is not None:
            for key in accumulated_grads:
                accumulated_grads[key] /= n_steps
        
        # Meta-update (opcional, puede hacerse externamente)
        # self.meta_update(accumulated_grads)
        
        # Guardar historial
        self.adaptation_history.append({
            'n_steps': n_steps,
            'loss': total_loss / n_steps,
            'task_size': len(task_data)
        })
        
        return {
            'gradients': accumulated_grads,
            'avg_loss': total_loss / n_steps,
            'n_steps': n_steps
        }

    def select_action(self, state, return_confidence=True):
        """
        Selecciona accion usando los pesos rapidos adaptados.
        
        Args:
            state: Estado actual
            return_confidence: Si True, retorna tambien la confianza
        
        Returns:
            action (int) o (action, confidence) si return_confidence=True
        """
        # Preprocesar estado
        x = self._preprocess_input(state)
        
        # Forward pass
        probs = self._forward(x, self.fast_weights)
        
        if np is not None:
            # Seleccionar accion con maxima probabilidad (explotacion)
            action = int(np.argmax(probs))
            confidence = float(probs[action])
            
            # Opcional: exploracion epsilon-greedy
            if random.random() < 0.05:  # 5% exploracion
                action = random.randint(0, self.action_dim - 1)
                confidence = float(probs[action])
        else:
            # Fallback sin numpy
            action = probs.index(max(probs)) if probs else 0
            confidence = float(probs[action]) if probs else 0.0
        
        if return_confidence:
            return action, confidence
        return action

    def suggest_action(self, state, confidence_threshold=0.7):
        """
        Sugiere una accion solo si la confianza es suficiente.
        Util para el ensemble que puede ignorar sugerencias de baja confianza.
        
        Args:
            state: Estado actual
            confidence_threshold: Umbral minimo de confianza
        
        Returns:
            action (int) o None si la confianza es baja
        """
        action, confidence = self.select_action(state, return_confidence=True)
        
        if confidence >= confidence_threshold:
            return action
        return None

    def observe(self, state, action, reward, next_state=None, done=False):
        """
        Observa una transicion y la almacena en memoria de tareas.
        Util para aprendizaje continuo.
        """
        self.task_memory.append({
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'done': done,
            'timestamp': time.time()
        })

    def get_stats(self):
        """Retorna estadisticas del meta-learner."""
        return {
            'state_dim': self.state_dim,
            'action_dim': self.action_dim,
            'meta_lr': self.meta_lr,
            'inner_lr': self.inner_lr,
            'inner_steps': self.inner_steps,
            'task_memory_size': len(self.task_memory),
            'adaptations_count': len(self.adaptation_history),
            'avg_adaptation_loss': sum(a['loss'] for a in self.adaptation_history) / len(self.adaptation_history) if self.adaptation_history else 0,
            'has_numpy': np is not None
        }

    def save(self, filepath):
        """Guarda pesos lentos (meta-conocimiento)."""
        if np is None:
            return False
        try:
            data = {
                'slow_weights': {k: v.tolist() for k, v in self.slow_weights.items()},
                'state_dim': self.state_dim,
                'action_dim': self.action_dim,
                'meta_lr': self.meta_lr,
                'inner_lr': self.inner_lr
            }
            with open(filepath, 'w') as f:
                json.dump(data, f)
            return True
        except Exception as e:
            log_event(f"Error guardando MetaLearner: {e}", "META")
            return False

    def load(self, filepath):
        """Carga pesos lentos (meta-conocimiento)."""
        if np is None:
            return False
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for k, v in data.get('slow_weights', {}).items():
                self.slow_weights[k] = np.array(v)
            self.fast_weights = {k: v.copy() for k, v in self.slow_weights.items()}
            return True
        except Exception as e:
            log_event(f"Error cargando MetaLearner: {e}", "META")
            return False


# ================================================================================
# SECCION 33: EPISODIC MEMORY (CEOIA) - VERSION CORREGIDA Y FUNCIONAL
# ================================================================================
class EpisodicMemory:
    """
    Memoria episodica para transferencia de conocimiento entre episodios similares.
    Almacena episodios completos y permite recuperar experiencias similares.
    """
    
    def __init__(self, capacity=10000):
        # --- BLOQUE: CONFIGURACION ---
        self.capacity = max(1, int(capacity))
        self.episodes = deque(maxlen=self.capacity)
        
        # --- BLOQUE: INDICES PARA BUSQUEDA RAPIDA ---
        self.state_index = defaultdict(list)  # hash de estado -> indices de episodios
        self.action_index = defaultdict(list)  # accion -> indices de episodios
        
        # --- BLOQUE: ESTADISTICAS ---
        self.total_episodes = 0
        self.total_experiences = 0
        self.access_count = 0
        self.hit_count = 0
        
        log_event(f"EpisodicMemory inicializada: capacity={self.capacity}", "MEMORY")

    def add_episode(self, experiences, metadata=None):
        """
        Añade un episodio completo a la memoria.
        
        Args:
            experiences: Lista de objetos Experience
            metadata: Dict opcional con metadatos del episodio
        """
        if not experiences:
            return
        
        # Validar y normalizar experiencias
        valid_experiences = []
        for exp in experiences:
            if isinstance(exp, Experience):
                valid_experiences.append(exp)
            elif isinstance(exp, dict):
                # Convertir dict a Experience
                try:
                    valid_experiences.append(Experience(
                        state=exp.get('state'),
                        action=exp.get('action', 0),
                        reward=exp.get('reward', 0.0),
                        next_state=exp.get('next_state'),
                        done=exp.get('done', False)
                    ))
                except Exception:
                    continue
        
        if not valid_experiences:
            return
        
        # Crear episodio
        episode = {
            'experiences': valid_experiences,
            'total_reward': sum(e.reward for e in valid_experiences),
            'avg_reward': sum(e.reward for e in valid_experiences) / len(valid_experiences),
            'length': len(valid_experiences),
            'metadata': metadata or {},
            'timestamp': time.time(),
            'episode_id': str(uuid.uuid4())[:8]
        }
        
        # Añadir a memoria
        self.episodes.append(episode)
        self.total_episodes += 1
        self.total_experiences += len(valid_experiences)
        
        # Actualizar indices
        self._update_indices(episode, len(self.episodes) - 1)

    def _update_indices(self, episode, index):
        """Actualiza indices invertidos para busqueda rapida."""
        for exp in episode['experiences']:
            # Indexar por estado (hash simplificado)
            state_key = self._hash_state(exp.state)
            self.state_index[state_key].append(index)
            
            # Indexar por accion
            self.action_index[int(exp.action)].append(index)

    def _hash_state(self, state, bins=8):
        """
        Crea un hash localidad-sensible (LSH) para estados similares.
        Estados cercanos en el espacio tendran el mismo hash con alta probabilidad.
        """
        if state is None:
            return "none"
        
        try:
            if np is not None and isinstance(state, np.ndarray):
                # Cuantizar a bins niveles
                flattened = state.flatten()
                if len(flattened) > 0:
                    # Usar primeros 4 componentes principales
                    sample = flattened[:min(4, len(flattened))]
                    quantized = np.digitize(sample, np.linspace(np.min(sample), np.max(sample), bins))
                    return tuple(quantized.tolist())
                return "empty"
            
            elif isinstance(state, (list, tuple)):
                if len(state) > 0:
                    sample = state[:min(4, len(state))]
                    # Cuantizar valores
                    min_val, max_val = min(sample), max(sample)
                    if max_val > min_val:
                        quantized = [int((v - min_val) / (max_val - min_val) * (bins - 1)) for v in sample]
                    else:
                        quantized = [0] * len(sample)
                    return tuple(quantized)
                return "empty"
            
            elif isinstance(state, dict):
                # Hash de valores numericos
                numeric_vals = [v for v in state.values() if isinstance(v, (int, float))]
                if numeric_vals:
                    return self._hash_state(numeric_vals, bins)
                return "dict"
            
            else:
                return str(state)[:20]
                
        except Exception:
            return "error"

    def _calculate_similarity(self, state1, state2):
        """
        Calcula similitud entre dos estados [0, 1].
        1 = identicos, 0 = completamente diferentes.
        """
        if state1 is None or state2 is None:
            return 0.0
        
        try:
            # Caso numerico simple
            if isinstance(state1, (int, float)) and isinstance(state2, (int, float)):
                max_val = max(abs(state1), abs(state2), 1.0)
                return 1.0 - min(1.0, abs(state1 - state2) / max_val)
            
            # Caso numpy arrays
            if np is not None:
                arr1 = np.array(state1).flatten() if not isinstance(state1, np.ndarray) else state1.flatten()
                arr2 = np.array(state2).flatten() if not isinstance(state2, np.ndarray) else state2.flatten()
                
                # Asegurar misma dimension
                min_len = min(len(arr1), len(arr2))
                if min_len == 0:
                    return 0.0
                
                arr1, arr2 = arr1[:min_len], arr2[:min_len]
                
                # Similitud coseno
                norm1 = np.linalg.norm(arr1)
                norm2 = np.linalg.norm(arr2)
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                
                cosine = np.dot(arr1, arr2) / (norm1 * norm2)
                return (cosine + 1.0) / 2.0  # Mapear [-1,1] a [0,1]
            
            # Caso listas/tuplas
            if isinstance(state1, (list, tuple)) and isinstance(state2, (list, tuple)):
                min_len = min(len(state1), len(state2))
                if min_len == 0:
                    return 0.0
                
                # Distancia euclidiana normalizada
                diff_sq = sum((float(a) - float(b)) ** 2 for a, b in zip(state1[:min_len], state2[:min_len]))
                max_sq = sum(max(float(a)**2, float(b)**2) for a, b in zip(state1[:min_len], state2[:min_len]))
                
                if max_sq == 0:
                    return 1.0
                
                return 1.0 - min(1.0, math.sqrt(diff_sq) / math.sqrt(max_sq))
            
            # Caso diccionarios
            if isinstance(state1, dict) and isinstance(state2, dict):
                common_keys = set(state1.keys()) & set(state2.keys())
                if not common_keys:
                    return 0.0
                
                similarities = []
                for k in common_keys:
                    v1, v2 = state1[k], state2[k]
                    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                        max_val = max(abs(v1), abs(v2), 1.0)
                        sim = 1.0 - min(1.0, abs(v1 - v2) / max_val)
                        similarities.append(sim)
                
                return sum(similarities) / len(similarities) if similarities else 0.5
            
            # Fallback: comparacion de strings
            return 1.0 if str(state1) == str(state2) else 0.0
            
        except Exception:
            return 0.5  # Neutral en caso de error

    def find_similar(self, current_state, k=5, min_similarity=0.5):
        """
        Encuentra episodios similares al estado dado.
        
        Args:
            current_state: Estado de consulta
            k: Numero maximo de resultados
            min_similarity: Umbral minimo de similitud
        
        Returns:
            Lista de tuplas (similarity, episode) ordenadas por similitud
        """
        self.access_count += 1
        
        if not self.episodes:
            return []
        
        # Busqueda con indice (filtrado rapido)
        state_key = self._hash_state(current_state)
        candidate_indices = set(self.state_index.get(state_key, []))
        
        # Si no hay candidatos por indice, buscar en todos
        if len(candidate_indices) < k:
            candidate_indices = range(len(self.episodes))
        
        # Calcular similitudes
        similares = []
        for idx in candidate_indices:
            if idx >= len(self.episodes):
                continue
            
            ep = self.episodes[idx]
            if not ep['experiences']:
                continue
            
            # Similitud con el primer estado del episodio
            ep_state = ep['experiences'][0].state
            similarity = self._calculate_similarity(current_state, ep_state)
            
            if similarity >= min_similarity:
                similares.append((similarity, ep))
        
        # Ordenar y retornar top-k
        similares.sort(key=lambda x: x[0], reverse=True)
        
        if similares:
            self.hit_count += 1
        
        return similares[:k]

    def get_similar_episodes(self, current_state, k=5):
        """
        API compatible hacia atras.
        Retorna lista de episodios (sin score de similitud).
        """
        results = self.find_similar(current_state, k=k, min_similarity=0.3)
        return [ep for _, ep in results]

    def get_best_action_from_similar(self, current_state, k=3):
        """
        Obtiene la mejor accion a partir de episodios similares.
        Util para transferencia de conocimiento.
        
        Returns:
            (action, confidence) o (None, 0) si no hay similares
        """
        similar = self.find_similar(current_state, k=k, min_similarity=0.6)
        
        if not similar:
            return None, 0.0
        
        # Votacion ponderada por similitud
        action_scores = defaultdict(float)
        action_counts = defaultdict(int)
        
        for similarity, ep in similar:
            for exp in ep['experiences']:
                if exp.reward > 0:  # Solo experiencias positivas
                    action_scores[exp.action] += similarity * exp.reward
                    action_counts[exp.action] += 1
        
        if not action_scores:
            return None, 0.0
        
        # Seleccionar accion con mayor score promedio
        best_action = None
        best_score = -float('inf')
        
        for action, total_score in action_scores.items():
            avg_score = total_score / action_counts[action]
            if avg_score > best_score:
                best_score = avg_score
                best_action = action
        
        # Calcular confianza basada en consistencia
        total_votes = sum(action_counts.values())
        confidence = action_counts[best_action] / total_votes if total_votes > 0 else 0
        
        return best_action, confidence

    def get_transferable_learning(self, current_state):
        """
        Extrae conocimiento transferible de episodios similares.
        
        Returns:
            Dict con acciones exitosas, recompensa promedio, y patrones
        """
        similar = self.find_similar(current_state, k=3, min_similarity=0.4)
        
        if not similar:
            return {}
        
        knowledge = {
            'successful_actions': defaultdict(float),
            'action_confidences': defaultdict(float),
            'average_reward': 0.0,
            'average_length': 0.0,
            'patterns': [],
            'source_episodes': len(similar)
        }
        
        total_reward = 0.0
        total_length = 0
        
        for similarity, ep in similar:
            # Acciones exitosas (ponderadas por similitud)
            for exp in ep['experiences']:
                weighted_reward = exp.reward * similarity
                knowledge['successful_actions'][exp.action] += weighted_reward
                knowledge['action_confidences'][exp.action] += similarity
            
            total_reward += ep['total_reward'] * similarity
            total_length += ep['length'] * similarity
            
            knowledge['patterns'].append({
                'length': ep['length'],
                'reward': ep['total_reward'],
                'avg_reward': ep['avg_reward'],
                'similarity': similarity
            })
        
        # Normalizar
        weight_sum = sum(sim for sim, _ in similar)
        if weight_sum > 0:
            knowledge['average_reward'] = total_reward / weight_sum
            knowledge['average_length'] = total_length / weight_sum
            
            for action in knowledge['successful_actions']:
                knowledge['successful_actions'][action] /= weight_sum
                knowledge['action_confidences'][action] /= weight_sum
        
        return knowledge

    def get_stats(self):
        """Retorna estadisticas de la memoria episodica."""
        return {
            'capacity': self.capacity,
            'current_size': len(self.episodes),
            'total_episodes_added': self.total_episodes,
            'total_experiences': self.total_experiences,
            'access_count': self.access_count,
            'hit_count': self.hit_count,
            'hit_rate': self.hit_count / max(1, self.access_count),
            'unique_state_hashes': len(self.state_index),
            'unique_actions': len(self.action_index)
        }

    def clear(self):
        """Limpia toda la memoria."""
        self.episodes.clear()
        self.state_index.clear()
        self.action_index.clear()
        self.total_episodes = 0
        self.total_experiences = 0
        self.access_count = 0
        self.hit_count = 0

    def save(self, filepath):
        """Guarda memoria a disco."""
        try:
            data = {
                'episodes': [
                    {
                        'experiences': [
                            {
                                'state': e.state.tolist() if np is not None and isinstance(e.state, np.ndarray) else e.state,
                                'action': e.action,
                                'reward': e.reward,
                                'next_state': e.next_state.tolist() if np is not None and isinstance(e.next_state, np.ndarray) else e.next_state,
                                'done': e.done
                            }
                            for e in ep['experiences']
                        ],
                        'total_reward': ep['total_reward'],
                        'length': ep['length'],
                        'metadata': ep['metadata'],
                        'timestamp': ep['timestamp']
                    }
                    for ep in self.episodes
                ],
                'stats': self.get_stats()
            }
            with open(filepath, 'w') as f:
                json.dump(data, f, default=str)
            return True
        except Exception as e:
            log_event(f"Error guardando EpisodicMemory: {e}", "MEMORY")
            return False

    def load(self, filepath):
        """Carga memoria desde disco."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.clear()
            
            for ep_data in data.get('episodes', []):
                experiences = []
                for e_data in ep_data.get('experiences', []):
                    exp = Experience(
                        state=e_data['state'],
                        action=e_data['action'],
                        reward=e_data['reward'],
                        next_state=e_data.get('next_state'),
                        done=e_data.get('done', False)
                    )
                    experiences.append(exp)
                
                self.add_episode(experiences, ep_data.get('metadata', {}))
            
            return True
        except Exception as e:
            log_event(f"Error cargando EpisodicMemory: {e}", "MEMORY")
            return False


# ================================================================================
# SECCION 34: ENSEMBLE RL (CEOIA) - VERSION CORREGIDA Y FUNCIONAL
# ================================================================================
class EnsembleRL:
    """
    Ensemble de multiples algoritmos RL con integracion completa de:
    - Curiosity Module (recompensa intrinseca)
    - Kalman Filter (suavizado de estados)
    - Episodic Memory (transferencia de conocimiento)
    - Meta-Learner (adaptacion rapida)
    """
    
    def __init__(self, state_dim, action_dim, use_curiosity=True,
                 use_episodic=True, use_meta=True, use_kalman=True):
        # --- DIMENSIONES ---
        self.state_dim = max(1, int(state_dim))
        self.action_dim = max(1, int(action_dim))
        
        # --- ALGORITMOS BASE ---
        self.algorithms = {
            'double_dqn': DoubleDQN(self.state_dim, self.action_dim),
            'sarsa': SARSAAgent(self.state_dim, self.action_dim),
            'actor_critic': ActorCritic(self.state_dim, self.action_dim),
            'ppo': PPOOptimizer(self.state_dim, self.action_dim),
        }
        
        # --- PESOS ADAPTATIVOS ---
        self.weights = {
            'double_dqn': 0.25, 'sarsa': 0.25,
            'actor_critic': 0.25, 'ppo': 0.25
        }
        self.weight_history = {name: [] for name in self.algorithms}
        self.performance = {name: 0.0 for name in self.algorithms}
        
        # --- METODOS DE VOTACION ---
        self.voting_methods = {
            'weighted_average': self._weighted_vote,
            'majority': self._majority_vote,
            'best_performer': self._best_performer_vote,
            'confidence': self._confidence_vote
        }
        self.voting = 'weighted_average'
        
        # --- MODULOS OPCIONALES ---
        self.use_curiosity = use_curiosity
        self.use_episodic = use_episodic
        self.use_meta = use_meta
        self.use_kalman = use_kalman
        
        # Inicializar modulos con dimensiones CORRECTAS
        if self.use_curiosity:
            self.curiosity = CuriosityModule(self.state_dim, self.action_dim)
        
        if self.use_episodic:
            self.episodic_memory = EpisodicMemory(capacity=10000)
        
        if self.use_kalman:
            # dim_z = min(state_dim, 3) pero consistente
            self.kalman_dim_z = min(self.state_dim, 3)
            self.kalman = KalmanFilter(self.state_dim, self.kalman_dim_z)
        
        if self.use_meta:
            self.meta_learner = MetaLearner(self.state_dim, self.action_dim)
        
        # --- HISTORIAL ---
        self.decision_history = deque(maxlen=1000)
        self.step_count = 0
        self.episode_count = 0
        
        # --- ESTADO ACTUAL ---
        self.current_state = None
        self.last_action = None
    
    # ============================================================================
    # UTILIDADES
    # ============================================================================
    def _to_hashable(self, state):
        """Convierte estado a formato hashable."""
        if np is not None and isinstance(state, np.ndarray):
            return tuple(state.flatten().tolist())
        elif isinstance(state, (list, tuple)):
            return tuple(state)
        return state
    
    def _preprocess_state(self, state):
        """Normaliza estado a array de dimension correcta."""
        if np is not None and isinstance(state, np.ndarray):
            arr = state.flatten()
        elif isinstance(state, (list, tuple)):
            arr = np.array(state, dtype=np.float32).flatten() if np is not None else list(state)
        else:
            arr = np.array([state], dtype=np.float32) if np is not None else [state]
        
        if np is not None:
            if len(arr) < self.state_dim:
                arr = np.pad(arr, (0, self.state_dim - len(arr)), mode='constant')
            elif len(arr) > self.state_dim:
                arr = arr[:self.state_dim]
            return arr.astype(np.float32)
        else:
            # Fallback sin numpy
            if isinstance(arr, list):
                if len(arr) < self.state_dim:
                    arr.extend([0.0] * (self.state_dim - len(arr)))
                elif len(arr) > self.state_dim:
                    arr = arr[:self.state_dim]
            return arr
    
    def _safe_kalman_update(self, observation):
        """Actualiza Kalman de forma segura con dimensiones correctas."""
        if not self.use_kalman:
            return
        
        try:
            if np is not None:
                if isinstance(observation, np.ndarray):
                    obs = observation.flatten()[:self.kalman_dim_z]
                elif isinstance(observation, (list, tuple)):
                    obs = np.array(observation, dtype=np.float32)[:self.kalman_dim_z]
                else:
                    obs = np.array([observation, 0, 0], dtype=np.float32)[:self.kalman_dim_z]
                
                if len(obs) < self.kalman_dim_z:
                    obs = np.pad(obs, (0, self.kalman_dim_z - len(obs)), mode='constant')
            else:
                if isinstance(observation, (list, tuple)):
                    obs = list(observation)[:self.kalman_dim_z]
                else:
                    obs = [observation, 0, 0]
                while len(obs) < self.kalman_dim_z:
                    obs.append(0.0)
            
            self.kalman.update(obs)
        except Exception as e:
            log_event(f"Kalman update error: {e}", "ENSEMBLE")
    
    # ============================================================================
    # METODOS DE VOTACION
    # ============================================================================
    def _weighted_vote(self, votes, state=None):
        """Votacion ponderada por pesos del ensemble."""
        weighted_votes = defaultdict(float)
        for name, action in votes.items():
            weighted_votes[action] += self.weights.get(name, 0.25)
        return int(max(weighted_votes, key=weighted_votes.get))
    
    def _majority_vote(self, votes, state=None):
        """Votacion por mayoria simple."""
        vote_counts = defaultdict(int)
        for action in votes.values():
            vote_counts[action] += 1
        return int(max(vote_counts, key=vote_counts.get))
    
    def _best_performer_vote(self, votes, state=None):
        """Vota con el algoritmo de mejor rendimiento."""
        best_algo = max(self.performance, key=self.performance.get)
        return votes.get(best_algo, random.randint(0, self.action_dim - 1))
    
    def _confidence_vote(self, votes, state=None):
        """
        Votacion ponderada por confianza del algoritmo.
        Requiere que los algoritmos retornen scores de confianza.
        """
        # Por ahora, fallback a weighted
        return self._weighted_vote(votes, state)
    
    # ============================================================================
    # SELECCION DE ACCION
    # ============================================================================
    def select_action(self, state, exploit_only=False):
        """
        Selecciona accion usando el ensemble con todos los modulos integrados.
        """
        # Preprocesar estado
        proc_state = self._preprocess_state(state)
        
        # Aplicar Kalman filter para suavizar
        if self.use_kalman and self.current_state is not None:
            self.kalman.predict()
            # Opcional: usar estado filtrado
            # proc_state = self.kalman.get_state()[:self.state_dim]
        
        # Meta-learner: adaptacion rapida
        if self.use_meta:
            try:
                meta_action, meta_conf = self.meta_learner.select_action(proc_state)
                if meta_conf > 0.7 and random.random() < 0.15:  # 15% si confianza alta
                    return int(meta_action)
            except Exception as e:
                log_event(f"Meta-learner fallback: {e}", "ENSEMBLE")
        
        # Consultar memoria episodica
        if self.use_episodic and not exploit_only:
            try:
                similar = self.episodic_memory.get_similar_episodes(proc_state, k=1)
                if similar and random.random() < 0.1:  # 10% reutilizacion
                    # Usar accion del episodio similar
                    if similar[0]['experiences']:
                        return int(similar[0]['experiences'][0].action)
            except Exception as e:
                log_event(f"Episodic fallback: {e}", "ENSEMBLE")
        
        # Obtener votos de cada algoritmo
        votes = {}
        for name, algo in self.algorithms.items():
            try:
                if name in ['double_dqn', 'sarsa']:
                    # Estos usan select_action con exploit flag
                    action = algo.select_action(proc_state, exploit_only)
                    votes[name] = int(action)
                
                elif name == 'actor_critic':
                    result = algo.select_action(proc_state)
                    if isinstance(result, tuple):
                        action = result[0]
                    else:
                        action = result
                    votes[name] = int(action)
                
                elif name == 'ppo':
                    result = algo.select_action(proc_state)
                    if isinstance(result, tuple):
                        action = result[0]
                    else:
                        action = result
                    votes[name] = int(action)
                
            except Exception as e:
                log_event(f"Error en {name}: {e}", "ENSEMBLE")
                continue
        
        # Si no hay votos validos, accion aleatoria
        if not votes:
            return random.randint(0, self.action_dim - 1)
        
        # Aplicar metodo de votacion
        voting_fn = self.voting_methods.get(self.voting, self._weighted_vote)
        final_action = voting_fn(votes, proc_state)
        
        # Validar rango
        final_action = int(max(0, min(final_action, self.action_dim - 1)))
        
        # Guardar para curiosity
        self.current_state = proc_state.copy() if hasattr(proc_state, 'copy') else proc_state
        self.last_action = final_action
        
        return final_action
    
    # ============================================================================
    # ACTUALIZACION (ENTRENAMIENTO)
    # ============================================================================
    def update(self, state, action, reward, next_state, done, use_curiosity=True):
        """
        Actualiza TODOS los algoritmos del ensemble y los modulos opcionales.
        """
        # Preprocesar estados
        proc_state = self._preprocess_state(state)
        proc_next = self._preprocess_state(next_state)
        
        # --- CURIOSITY: Recompensa intrinseca ---
        intrinsic_reward = 0.0
        if use_curiosity and self.use_curiosity:
            try:
                intrinsic_reward = self.curiosity.compute_intrinsic_reward(
                    proc_state, action, proc_next
                )
                # Escalar y limitar
                intrinsic_reward = float(max(-1.0, min(1.0, intrinsic_reward)))
                
                # Entrenar modelos de curiosity
                self.curiosity.update_models(proc_state, action, proc_next)
            except Exception as e:
                log_event(f"Curiosity error: {e}", "ENSEMBLE")
                intrinsic_reward = 0.0
        
        total_reward = reward + 0.01 * intrinsic_reward  # Factor de escala pequeno
        
        # --- KALMAN FILTER ---
        self.kalman.predict()
        self._safe_kalman_update(proc_next)
        
        # --- CONVERTIR A HASHABLE ---
        state_hash = self._to_hashable(proc_state)
        next_hash = self._to_hashable(proc_next)
        
        # --- ACTUALIZAR CADA ALGORITMO ---
        for name, algo in self.algorithms.items():
            try:
                if name == 'double_dqn':
                    # DQN: store + learn
                    algo.store(state_hash, action, total_reward, next_hash, done)
                    if hasattr(algo, 'memory') and len(algo.memory) >= getattr(algo, 'batch_size', 32):
                        algo.learn()
                
                elif name == 'sarsa':
                    # SARSA: necesita accion del siguiente estado (ON-POLICY)
                    next_action = algo.select_action(next_hash, exploit_only=False)
                    algo.update(state_hash, action, total_reward, next_hash, next_action, done)
                
                elif name == 'actor_critic':
                    # Actor-Critic: almacenar transicion y actualizar
                    if hasattr(algo, 'store_transition'):
                        # Crear RLState/RLAction si es necesario
                        algo.store_transition(
                            RLState(features={'raw': list(proc_state)}),
                            RLAction(action_id=str(action), action_type=ActionType(action) if action < len(ActionType) else ActionType.WAIT),
                            total_reward,
                            RLState(features={'raw': list(proc_next)})
                        )
                    # Actualizar si hay suficientes datos
                    if hasattr(algo, 'update') and len(getattr(algo, 'buffer', [])) >= 10:
                        algo.update(done=done)
                
                elif name == 'ppo':
                    # PPO: almacenar con log_prob y value
                    if hasattr(algo, 'store'):
                        # Obtener log_prob y value del forward pass
                        action_ppo, log_prob = algo.select_action(proc_state)
                        value = algo._get_value(proc_state)
                        algo.store(proc_state, action, total_reward, proc_next, done, log_prob, value)
                    # Actualizar periodicamente
                    if hasattr(algo, 'update') and self.step_count % 2048 == 0:
                        algo.update()
                
            except Exception as e:
                log_event(f"Error actualizando {name}: {e}", "ENSEMBLE")
        
        # --- MEMORIA EPISODICA ---
        if self.use_episodic:
            try:
                exp = Experience(state_hash, action, total_reward, next_hash, done)
                self.episodic_memory.add_episode([exp])
            except Exception as e:
                log_event(f"Episodic error: {e}", "ENSEMBLE")
        
        # --- META-LEARNER ---
        if self.use_meta:
            try:
                self.meta_learner.adapt_to_task([{
                    'state': proc_state,
                    'action': action,
                    'reward': total_reward
                }])
            except Exception as e:
                log_event(f"Meta-learner error: {e}", "ENSEMBLE")
        
        # --- HISTORIAL ---
        self.decision_history.append({
            'state': state_hash,
            'action': action,
            'reward': total_reward,
            'intrinsic_reward': intrinsic_reward,
            'timestamp': time.time()
        })
        
        self.step_count += 1
        if done:
            self.episode_count += 1
        
        return {
            'extrinsic_reward': float(reward),
            'intrinsic_reward': float(intrinsic_reward),
            'total_reward': float(total_reward)
        }
    
    # ============================================================================
    # OPTIMIZACION DE PESOS
    # ============================================================================
    def optimize_weights(self, fitness_fn, generations=30):
        """
        Optimiza pesos del ensemble usando algoritmo genetico.
        """
        try:
            ga = GeneticOptimizer(
                param_bounds={name: (0.01, 1.0) for name in self.algorithms},
                pop_size=20,
                generations=generations
            )
            
            def eval_weights(weights_dict):
                # Normalizar pesos
                total = sum(weights_dict.values())
                if total > 0:
                    normalized = {k: v / total for k, v in weights_dict.items()}
                else:
                    normalized = {k: 0.25 for k in self.algorithms}
                
                # Aplicar pesos temporalmente
                old_weights = self.weights.copy()
                self.weights.update(normalized)
                
                # Evaluar
                score = fitness_fn(self.weights)
                
                # Restaurar
                self.weights.update(old_weights)
                
                return score
            
            best_weights, best_score = ga.optimize(eval_weights, verbose=False)
            
            # Normalizar y aplicar mejores pesos
            total = sum(best_weights.values())
            if total > 0:
                best_weights = {k: v / total for k, v in best_weights.items()}
            
            self.weights.update(best_weights)
            
            # Guardar en historial
            for name, w in self.weights.items():
                self.weight_history[name].append(w)
            
            return self.weights.copy()
            
        except Exception as e:
            log_event(f"Weight optimization error: {e}", "ENSEMBLE")
            return self.weights.copy()
    
    # ============================================================================
    # ACTUALIZACION DE PESOS POR RENDIMIENTO
    # ============================================================================
    def update_weights_by_performance(self, rewards):
        """
        Actualiza pesos basado en rendimiento reciente (softmax).
        """
        # Actualizar performance con EMA
        for name, reward in rewards.items():
            if name in self.performance:
                self.performance[name] = 0.9 * self.performance[name] + 0.1 * reward
        
        # Calcular pesos con softmax
        if np is not None:
            perf_values = np.array(list(self.performance.values()))
            perf_values = perf_values - np.max(perf_values)  # Estabilidad numerica
            exp_perf = np.exp(perf_values)
            softmax_weights = exp_perf / np.sum(exp_perf)
        else:
            # Fallback sin numpy
            perf_values = list(self.performance.values())
            max_perf = max(perf_values)
            exp_perf = [math.exp(v - max_perf) for v in perf_values]
            sum_exp = sum(exp_perf)
            softmax_weights = [v / sum_exp for v in exp_perf] if sum_exp > 0 else [0.25] * 4
        
        for i, name in enumerate(self.algorithms):
            self.weights[name] = float(softmax_weights[i])
            self.weight_history[name].append(self.weights[name])
    
    # ============================================================================
    # ESTADO Y SERIALIZACION
    # ============================================================================
    def get_state(self):
        """Retorna estado completo del ensemble."""
        state = {
            'algorithms': list(self.algorithms.keys()),
            'weights': self.weights.copy(),
            'performance': self.performance.copy(),
            'voting_method': self.voting,
            'memory_size': len(getattr(self.episodic_memory, 'episodes', [])),
            'decisions': len(self.decision_history),
            'episode_count': self.episode_count,
            'step_count': self.step_count,
        }
        
        if self.use_kalman:
            try:
                state['kalman_uncertainty'] = float(self.kalman.get_uncertainty())
            except:
                state['kalman_uncertainty'] = None
        
        return state
    
    def set_voting_method(self, method):
        """Cambia metodo de votacion."""
        if method in self.voting_methods:
            self.voting = method
            return True
        return False
    
    def save(self, path):
        """Guarda estado del ensemble."""
        import pickle
        state = {
            'weights': self.weights,
            'performance': self.performance,
            'voting': self.voting,
            'step_count': self.step_count,
            'episode_count': self.episode_count,
            'weight_history': self.weight_history,
        }
        with open(path, 'wb') as f:
            pickle.dump(state, f)
    
    def load(self, path):
        """Carga estado del ensemble."""
        import pickle
        with open(path, 'rb') as f:
            state = pickle.load(f)
        self.weights = state.get('weights', self.weights)
        self.performance = state.get('performance', self.performance)
        self.voting = state.get('voting', self.voting)
        self.step_count = state.get('step_count', 0)
        self.episode_count = state.get('episode_count', 0)
        self.weight_history = state.get('weight_history', {k: [] for k in self.algorithms})


# ================================================================================
# SECCION 35: RL INTEGRATION LAYER (Sistema Unificado)
# ================================================================================
class RLIntegrationLayer:
    def __init__(self, algorithm: RLAlgorithm = RLAlgorithm.Q_LEARNING,
                 auto_train: bool = False, use_matching: bool = True):
        self.algorithm = algorithm
        self.use_matching = use_matching
        self.is_trained = False
        self.agent = None
        self.matching_engine = MatchingEngine() if use_matching else None
        self._init_agent()

    def _init_agent(self):
        if self.algorithm == RLAlgorithm.Q_LEARNING: self.agent = QLearningAgent()
        elif self.algorithm == RLAlgorithm.POLICY_GRADIENT: self.agent = PolicyGradientAgent()
        elif self.algorithm == RLAlgorithm.ACTOR_CRITIC: self.agent = ActorCriticAgent()
        else: self.agent = QLearningAgent()

    def train_if_needed(self, episodes: int = None) -> Optional[Dict[str, Any]]:
        if self.is_trained: return None
        env = NegotiationEnvironment()
        trainer = RLTrainer(self.agent, env, num_episodes=episodes or GlobalConfig.RL_TRAINING_EPISODES)
        stats = trainer.train()
        self.is_trained = True
        return stats

    def select_action_for_negotiation(self, session: NegotiationSession,
                                      agent_id: str, available_offers: List[Offer]) -> Optional[Offer]:
        # --- BLOQUE: SELECCION RL + MATCHING ---
        if not available_offers: return None
        state = RLState.from_negotiation_session(session, agent_id)
        if self.use_matching and self.matching_engine:
            temp_agent = MatchingAgent(agent_id=agent_id, name=agent_id)
            matching_offers = []
            for offer in available_offers:
                mo = MatchingOffer(offer_id=offer.offer_id, agent_id=offer.proposed_by, price=offer.price, delivery_time=offer.delivery_time, quality_level=offer.quality_level)
                matching_offers.append(mo)
            if matching_offers:
                best_match = None
                best_score = -1
                for mo in matching_offers:
                    score = SimilarityMetrics.weighted_similarity({"price": 0.5, "time": 0.3, "quality": 0.2}, mo.to_features(), {"price": 0.5, "time": 0.3, "quality": 0.2})
                    if score > best_score: best_score = score; best_match = mo
                rl_actions = [RLAction(action_id="accept", action_type=ActionType.ACCEPT_OFFER), RLAction(action_id="reject", action_type=ActionType.REJECT_OFFER), RLAction(action_id="counter", action_type=ActionType.COUNTER_OFFER), RLAction(action_id="wait", action_type=ActionType.WAIT)]
                selected_action = self.agent.select_action(state, rl_actions)
                if selected_action.action_type == ActionType.ACCEPT_OFFER and best_match:
                    return next((o for o in available_offers if o.offer_id == best_match.offer_id), available_offers[0])
        rl_actions = [RLAction(action_id="accept", action_type=ActionType.ACCEPT_OFFER), RLAction(action_id="reject", action_type=ActionType.REJECT_OFFER), RLAction(action_id="counter", action_type=ActionType.COUNTER_OFFER), RLAction(action_id="wait", action_type=ActionType.WAIT)]
        selected_action = self.agent.select_action(state, rl_actions)
        if selected_action.action_type == ActionType.ACCEPT_OFFER: return max(available_offers, key=lambda o: o.price)
        elif selected_action.action_type == ActionType.COUNTER_OFFER: return available_offers[len(available_offers) // 2] if available_offers else None
        return available_offers[0] if available_offers else None

    def update_from_negotiation_result(self, session: NegotiationSession, agent_id: str, reward: float) -> None:
        if not self.agent: return
        state = RLState.from_negotiation_session(session, agent_id)
        if session.status == NegotiationStatus.ACCEPTED:
            action = RLAction(action_id="accept", action_type=ActionType.ACCEPT_OFFER)
        else:
            action = RLAction(action_id="reject", action_type=ActionType.REJECT_OFFER)
        if hasattr(self.agent, 'update'):
            next_state = RLState(negotiation_round=session.current_round, my_utility=session.final_utility_a, opponent_utility=session.final_utility_b, time_pressure=1.0, remaining_rounds=0)
            self.agent.update(state, action, reward, next_state, done=True)
        elif hasattr(self.agent, 'store_experience'):
            self.agent.store_experience(state, action, reward)

# ================================================================================
# SECCION 36: CEOIA POTENCIADO CON ENSAMBLE (VERSION CORREGIDA Y FUNCIONAL)
# ================================================================================
class CEOIA:
    """
    CEOIA (Conscious Executive Officer Intelligent Agent) - Sistema principal.
    Integra ensemble RL, fuzzy logic, MCTS, meta-learning, curiosity y Kalman.
    """
    
    def __init__(self, state_dim=None, action_dim=5):
        # --- BLOQUE: DIMENSIONES (inicializar PRIMERO) ---
        self.action_dim = max(1, int(action_dim))
        self.state_dim = None  # Se calculará a continuación
        
        # --- BLOQUE: ESTADO INTERNO ---
        self.internal_state = {
            "confianza_decisiones": 0.5,
            "nivel_conocimiento": 0.5,
            "energia_mental": 100.0,
            "modo_operacion": "ENSAMBLE_MULTI_RL",
            "ciclos_ejecutados": 0,
            "ganancias_totales": 0.0,
            "ultima_recompensa": 0.0,
            "ultima_accion": 0
        }
        
        # --- BLOQUE: MEMORIA EPISODICA (inicializar ANTES de calcular state_dim) ---
        self.episodic_memory = EpisodicMemory(capacity=10000)
        self.long_term_memory = deque(maxlen=10000)
        
        # --- BLOQUE: DETECCION DE ENRUTAMIENTO ---
        self.routing_available = ROUTING_AVAILABLE
        self.gps = None
        if self.routing_available:
            try:
                self.gps = getattr(routing, 'gps', None)
            except Exception:
                self.gps = None

        # --- BLOQUE: CALCULO DE DIMENSION DE ESTADO ---
        if state_dim is None:
            try:
                # Usar dimension fija inicial para evitar recursion
                dummy_state = self._get_current_state_raw()
                if np is not None and isinstance(dummy_state, np.ndarray):
                    self.state_dim = int(dummy_state.shape[0])
                else:
                    self.state_dim = len(dummy_state)
            except Exception as e:
                log_event(f"Error calculando state_dim: {e}, usando default=12", "CEOIA")
                self.state_dim = 12
        else:
            self.state_dim = max(1, int(state_dim))
        
        log_event(f"CEOIA state_dim={self.state_dim}, action_dim={self.action_dim}", "CEOIA")

        # --- BLOQUE: COMPONENTES PRINCIPALES ---
        # Ensemble RL con todos los modulos activados
        self.ensemble = EnsembleRL(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            use_curiosity=True,
            use_episodic=True,
            use_meta=True,
            use_kalman=True
        )
        
        # Fuzzy Logic Controller
        self.fuzzy = FuzzyLogicController()
        self._setup_fuzzy_rules()
        
        # MCTS para planificacion
        self.mcts = MCTSAgent(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            explorations=50
        )
        
        # Q-Learner adicional (Double DQN)
        self.q_learner = DoubleDQN(self.state_dim, self.action_dim)
        
        # --- BLOQUE: CONFIGURACION ---
        self.permisos = {
            "controlar_radares": True,
            "controlar_singularidad": True,
            "negociacion_ia": True,
            "modificar_codigo": True,
            "controlar_gps": True,
            "auto_activacion": True
        }
        self.config = {
            "usar_curiosity": True,
            "usar_fuzzy": True,
            "usar_mcts": False,  # Desactivado por defecto (costoso)
            "usar_meta_learning": True,
            "ensemble_weight_opt": True,
            "auto_save_interval": 100
        }

        # --- BLOQUE: CICLO DE APRENDIZAJE ---
        self._learning_active = False
        self._learning_thread = None
        self._start_learning_cycle()

        # --- BLOQUE: ENRUTAMIENTO Y RED ---
        self._init_routing_and_network()

        # --- BLOQUE: CONTADORES ---
        self._action_counter = 0
        self._save_counter = 0

        log_event(f"CEOIA INICIALIZADO: state_dim={self.state_dim}, action_dim={self.action_dim}", "INFO")

    # ============================================================================
    # INICIALIZACION DE SUBSISTEMAS
    # ============================================================================
    def _init_routing_and_network(self):
        """Inicializa componentes de enrutamiento de forma segura."""
        self.routing_engine = None
        self.traffic = None
        self.graph = None
        self.network_state = {}
        self.last_gps_update = 0
        
        if not self.routing_available:
            return
        
        try:
            if hasattr(routing, 'initialize_routing_components'):
                self.routing_engine, self.gps, self.traffic, self.graph = routing.initialize_routing_components()
            
            if hasattr(routing, 'start_background_monitors'):
                routing.start_background_monitors()
            
            if hasattr(routing, 'get_network_monitor_instance'):
                self.network_state = routing.get_network_monitor_instance()
            
            self.last_gps_update = time.time()
            log_event("Routing integrado exitosamente", "CEOIA")
            
        except Exception as e:
            log_event(f"Error integrando routing: {e}", "WARN")
            self.routing_engine = self.gps = self.traffic = self.graph = None
            self.network_state = {}

    def _setup_fuzzy_rules(self):
        """Configura reglas difusas para toma de decisiones."""
        # Variables de entrada
        variables = {
            'demanda': [
                ('alta', 'triangle', (0.7, 0.85, 1.0)),
                ('media', 'triangle', (0.3, 0.5, 0.7)),
                ('baja', 'triangle', (0.0, 0.15, 0.3))
            ],
            'distancia': [
                ('cerca', 'triangle', (0, 2, 5)),
                ('media', 'triangle', (3, 7, 10)),
                ('lejos', 'triangle', (8, 15, 20))
            ],
            'tarifa': [
                ('alta', 'triangle', (15, 25, 50)),
                ('media', 'triangle', (8, 12, 18)),
                ('baja', 'triangle', (3, 6, 10))
            ],
            'output': [
                ('aceptar', 'triangle', (0.7, 0.9, 1.0)),
                ('considerar', 'triangle', (0.4, 0.6, 0.8)),
                ('rechazar', 'triangle', (0.0, 0.2, 0.4))
            ]
        }
        
        for var, rules in variables.items():
            for name, mtype, params in rules:
                self.fuzzy.add_mf(var, name, mtype, params)

        # Reglas logicas
        rules = [
            ({'demanda': 'alta', 'tarifa': 'alta'}, {'aceptar': 1.0}),
            ({'demanda': 'alta', 'tarifa': 'media'}, {'aceptar': 1.0}),
            ({'demanda': 'media', 'tarifa': 'alta'}, {'aceptar': 1.0}),
            ({'demanda': 'baja', 'tarifa': 'baja'}, {'rechazar': 1.0}),
            ({'distancia': 'lejos', 'tarifa': 'baja'}, {'rechazar': 1.0}),
            ({'demanda': 'media', 'distancia': 'cerca'}, {'considerar': 1.0})
        ]
        
        for antecedent, consequent in rules:
            self.fuzzy.add_rule(antecedent, consequent)

    def _start_learning_cycle(self):
        """Inicia hilo daemon de meta-aprendizaje."""
        self._learning_active = True
        
        def meta_loop():
            while self._learning_active:
                try:
                    self._run_meta_learning()
                    time.sleep(10)
                except Exception as e:
                    log_event(f"Error meta-learning: {e}", "META")
                    time.sleep(5)
        
        self._learning_thread = threading.Thread(
            target=meta_loop,
            daemon=True,
            name="CEOIA_MetaLearning"
        )
        self._learning_thread.start()
        log_event("Ciclo de meta-aprendizaje iniciado", "CEOIA")

    # ============================================================================
    # META-APRENDIZAJE
    # ============================================================================
    def _run_meta_learning(self):
        """Ejecuta un paso de meta-aprendizaje."""
        if not self.config.get('usar_meta_learning', True):
            return
        
        # Obtener estado actual normalizado
        current_state = self._get_current_state_normalized()
        
        # Transferencia desde memoria episodica
        try:
            knowledge = self.episodic_memory.get_transferable_learning(tuple(current_state))
            
            if knowledge and knowledge.get('successful_actions'):
                task_data = []
                for action, weighted_reward in knowledge['successful_actions'].items():
                    task_data.append({
                        'state': current_state,
                        'action': int(action),
                        'reward': float(weighted_reward)
                    })
                
                if task_data and len(task_data) >= 3:
                    # Adaptar meta-learner
                    self.ensemble.meta_learner.adapt_to_task(task_data, n_steps=3)
                    log_event(f"Meta-learning adaptado: {len(task_data)} experiencias", "META")
        
        except Exception as e:
            log_event(f"Error transferencia episodica: {e}", "META")
        
        # Optimizacion de pesos del ensemble
        if self.config.get('ensemble_weight_opt', True):
            try:
                recent_reward = self.internal_state.get('ultima_recompensa', 0)
                
                def fitness(weights):
                    # Fitness basado en recompensa reciente y diversidad
                    recent_perf = self.ensemble.performance
                    score = sum(recent_perf.get(name, 0) * w for name, w in weights.items())
                    # Bonus por diversidad (entropia de pesos)
                    entropy = -sum(w * math.log(w + 1e-8) for w in weights.values() if w > 0)
                    return score + 0.1 * entropy
                
                # Optimizar cada 50 ciclos
                if self.internal_state['ciclos_ejecutados'] % 50 == 0:
                    self.ensemble.optimize_weights(fitness, generations=10)
                    
            except Exception as e:
                log_event(f"Error optimizacion pesos: {e}", "META")

    # ============================================================================
    # ESTADO DEL SISTEMA
    # ============================================================================
    def _get_current_state_raw(self):
        """
        Construye vector de estado sin usar self.state_dim.
        Usado solo durante inicializacion.
        """
        base = []
        
        # 1. Estado del driver
        try:
            driver_state_val = 1.0 if DRIVER_STATE != "IDLE" else 0.0
        except NameError:
            driver_state_val = 0.0
        base.append(driver_state_val)
        
        # 2. Tiempo normalizado
        base.append((time.time() % 86400) / 86400.0)
        
        # 3. Entropia
        base.append(random.random())
        
        # 4-5. Datos de zona
        try:
            zs = zone_state.get(ULTIMA_ZONA, {})
            base.append(min(1.0, zs.get('ratio_demanda', 0) / 3.0))
            base.append(min(1.0, zs.get('ganancia_estimada', 0) / 50.0))
        except (NameError, Exception):
            base.extend([0.0, 0.0])
        
        # 6-7. Estado interno
        base.append(self.internal_state.get('confianza_decisiones', 0.5))
        base.append(self.internal_state.get('nivel_conocimiento', 0.5))
        
        # 8-9. Coordenadas GPS (fallback)
        base.extend([0.5, 0.5])
        
        # 10-11. Estado de red
        base.extend([0.5, 0.5])
        
        # 12. Memoria
        base.append(0.0)
        
        if np is not None:
            return np.array(base, dtype=np.float32)
        return base

    def _get_current_state(self):
        """
        Construye el vector de estado actual del sistema.
        Incluye: estado driver, tiempo, zona, GPS, red, memoria.
        """
        base = []
        
        # 1. Estado del driver (0=IDLE, 1=BUSY, etc)
        try:
            driver_state_val = 1.0 if DRIVER_STATE != "IDLE" else 0.0
        except NameError:
            driver_state_val = 0.0
        base.append(driver_state_val)
        
        # 2. Tiempo normalizado [0,1]
        hour_normalized = (time.time() % 86400) / 86400.0
        base.append(hour_normalized)
        
        # 3. Factor aleatorio de entropia
        base.append(random.random())
        
        # 4-5. Datos de zona
        try:
            zs = zone_state.get(ULTIMA_ZONA, {})
            base.append(min(1.0, zs.get('ratio_demanda', 0) / 3.0))
            base.append(min(1.0, zs.get('ganancia_estimada', 0) / 50.0))
        except (NameError, Exception):
            base.extend([0.0, 0.0])
        
        # 6-7. Estado interno
        base.append(self.internal_state.get('confianza_decisiones', 0.5))
        base.append(self.internal_state.get('nivel_conocimiento', 0.5))
        
        # 8-9. Coordenadas GPS
        lat_norm, lon_norm = self._get_gps_normalized()
        base.append(lat_norm)
        base.append(lon_norm)
        
        # 10-11. Estado de red
        net_val, net_latency = self._get_network_state()
        base.append(net_val)
        base.append(min(1.0, net_latency / 2.0))
        
        # 12. Tamaño de memoria episodica
        try:
            mem_size = len(self.episodic_memory.episodes)
        except:
            mem_size = 0
        base.append(min(1.0, mem_size / 1000.0))
        
        # Rellenar o truncar a state_dim
        return self._normalize_state_length(base)

    def _get_current_state_normalized(self):
        """Retorna estado como lista de Python (para hashing)."""
        state = self._get_current_state()
        if np is not None and isinstance(state, np.ndarray):
            return state.tolist()
        return list(state) if isinstance(state, (list, tuple)) else [float(state)]

    def _get_gps_normalized(self):
        """Obtiene coordenadas GPS normalizadas [0,1]."""
        gps_coords_ok = False
        lat_norm, lon_norm = 0.5, 0.5
        
        # Intentar GPS real
        if self.routing_available and self.gps:
            try:
                if hasattr(self.gps, 'get_current_location'):
                    gps_loc = self.gps.get_current_location()
                    if gps_loc and hasattr(gps_loc, 'latitude'):
                        lat_norm = max(0.0, min(1.0, (gps_loc.latitude - 8.8) / 0.3))
                        lon_norm = max(0.0, min(1.0, (gps_loc.longitude + 79.9) / 0.6))
                        gps_coords_ok = True
            except Exception:
                pass
        
        # Fallback a GPS_CURRENT global
        if not gps_coords_ok:
            try:
                if GPS_CURRENT and isinstance(GPS_CURRENT, dict):
                    lat = GPS_CURRENT.get('lat', 8.98)
                    lng = GPS_CURRENT.get('lng', -79.52)
                    lat_norm = max(0.0, min(1.0, (lat - 8.8) / 0.3))
                    lon_norm = max(0.0, min(1.0, (lng + 79.9) / 0.6))
                    gps_coords_ok = True
            except NameError:
                pass
        
        return lat_norm, lon_norm

    def _get_network_state(self):
        """Obtiene estado de red [0=mal, 1=excelente] y latencia."""
        net_val = 0.0
        net_latency = 1.0
        
        try:
            if self.routing_available and hasattr(routing, 'get_network_monitor_instance'):
                net = routing.get_network_monitor_instance()
                if isinstance(net, dict):
                    net_state = net.get("network_state", {})
                    net_status = net_state.get("status", "DESCONOCIDO")
                    net_latency = net_state.get("latency", 1.0)
                    net_val = 1.0 if net_status == "EXCELENTE" else 0.5 if net_status == "ESTABLE" else 0.0
        except Exception:
            pass
        
        return net_val, net_latency

    def _normalize_state_length(self, base):
        """Ajusta vector de estado a self.state_dim."""
        if self.state_dim is None:
            # Durante inicializacion, retornar como está
            if np is not None and not isinstance(base, np.ndarray):
                return np.array(base, dtype=np.float32)
            return base
        
        if not isinstance(base, list):
            base = list(base) if isinstance(base, (tuple, np.ndarray)) else [float(base)]
        
        # Rellenar
        while len(base) < self.state_dim:
            base.append(0.0)
        
        # Truncar
        if len(base) > self.state_dim:
            base = base[:self.state_dim]
        
        # Convertir a numpy si disponible
        if np is not None:
            return np.array(base, dtype=np.float32)
        return base

    # ============================================================================
    # TOMA DE DECISIONES
    # ============================================================================
    def decide_action(self, state=None, use_all=True):
        """
        Decide accion usando ensemble + fuzzy + MCTS (opcional).
        
        Args:
            state: Estado opcional, si None usa _get_current_state
            use_all: Si True, usa todos los modulos de decision
        
        Returns:
            int: Accion seleccionada [0, action_dim)
        """
        # Obtener estado
        if state is None:
            state = self._get_current_state()
        
        # Normalizar para ensemble
        state_processed = self._normalize_state_length(state)
        
        # --- MODULO: OPTIMIZACION DE RUTA ---
        if self.routing_available and self.config.get('usar_routing', True):
            self._evaluate_routing_opportunity()
        
        # --- MODULO: FUZZY LOGIC ---
        fuzzy_score = 0.5
        if use_all and self.config.get('usar_fuzzy', True):
            try:
                fuzzy_inputs = self._get_fuzzy_inputs()
                fuzzy_score = self.fuzzy.evaluate(fuzzy_inputs, output_range=(0, 1))
            except Exception as e:
                log_event(f"Fuzzy error: {e}", "CEOIA")
                fuzzy_score = 0.5
        
        # --- MODULO: MCTS (planificacion a largo plazo) ---
        mcts_action = None
        if use_all and self.config.get('usar_mcts', False):
            try:
                self.mcts.build_tree(state_processed, list(range(self.action_dim)))
                mcts_action = self.mcts.select_best_action()
            except Exception as e:
                log_event(f"MCTS error: {e}", "CEOIA")
        
        # --- MODULO: ENSAMBLE RL (principal) ---
        try:
            ensemble_action = self.ensemble.select_action(
                state_processed,
                exploit_only=(fuzzy_score > 0.8)  # Explotar si fuzzy es muy positivo
            )
        except Exception as e:
            log_event(f"Ensemble error: {e}, usando fallback", "CEOIA")
            ensemble_action = random.randint(0, self.action_dim - 1)
        
        # --- ARBITRAJE FINAL ---
        # MCTS override si confianza alta
        if mcts_action is not None and random.random() < 0.15:
            final_action = mcts_action
        # Fuzzy override
        elif fuzzy_score > 0.75:
            final_action = ensemble_action  # Aceptar
        elif fuzzy_score < 0.25:
            final_action = max(0, ensemble_action - 1)  # Conservador
        else:
            final_action = ensemble_action
        
        # Validar rango
        final_action = int(max(0, min(final_action, self.action_dim - 1)))
        
        # Actualizar estado interno
        self.internal_state['ultima_accion'] = final_action
        self._action_counter += 1
        
        return final_action

    def _get_fuzzy_inputs(self):
        """Obtiene variables de entrada para fuzzy logic."""
        try:
            zs = zone_state.get(ULTIMA_ZONA, {})
            demanda = min(1.0, zs.get('ratio_demanda', 0))
        except (NameError, Exception):
            demanda = random.uniform(0, 1)
        
        # Distancia estimada (normalizada)
        distancia = random.uniform(0, 20)  # Fallback
        
        # Tarifa estimada
        try:
            tarifa = zs.get('ganancia_estimada', 10.0)
        except:
            tarifa = random.uniform(3, 30)
        
        return {
            'demanda': demanda,
            'distancia': distancia,
            'tarifa': tarifa
        }

    def _evaluate_routing_opportunity(self):
        """Evalua oportunidades de enrutamiento."""
        if not (self.routing_available and self.gps):
            return
        
        try:
            if not (hasattr(self.gps, 'last_location') and self.gps.last_location):
                return
            
            # Encontrar mejor zona
            mejor_zona = None
            mejor_ratio = -1
            
            try:
                for zid, zdata in zone_state.items():
                    ratio = zdata.get('ratio_demanda', 0)
                    if ratio > mejor_ratio:
                        mejor_ratio = ratio
                        mejor_zona = zid
            except NameError:
                return
            
            # Evaluar ruta
            if mejor_zona and hasattr(routing, 'PANAMA_LOCATIONS'):
                loc_data = routing.PANAMA_LOCATIONS.get(mejor_zona)
                if loc_data and hasattr(routing, 'Coordinate') and hasattr(routing, 'get_route_between_coords'):
                    dest = routing.Coordinate(
                        latitude=loc_data["lat"],
                        longitude=loc_data["lon"]
                    )
                    route_info = routing.get_route_between_coords(
                        self.gps.last_location,
                        dest,
                        algorithm="A_STAR",
                        objective="TIME"
                    )
                    
                    if route_info:
                        time_min = route_info.get("time_min", 30)
                        if time_min < 15:
                            self.internal_state["ganancias_totales"] += 0.3
                        elif time_min > 30:
                            self.internal_state["ganancias_totales"] -= 0.2
                        
        except Exception as e:
            log_event(f"Routing eval error: {e}", "CEOIA")

    # ============================================================================
    # APRENDIZAJE
    # ============================================================================
    def learn(self, state, action, reward, done=True):
        """
        Actualiza todos los componentes de aprendizaje.
        
        Args:
            state: Estado anterior
            action: Accion tomada
            reward: Recompensa obtenida
            done: Si el episodio termino
        
        Returns:
            dict: Resultados del aprendizaje
        """
        # Obtener siguiente estado
        next_state = self._get_current_state()
        
        # Normalizar estados
        state_processed = self._normalize_state_length(state)
        next_state_processed = self._normalize_state_length(next_state)
        
        # --- ACTUALIZAR ENSAMBLE ---
        result = {'extrinsic_reward': float(reward), 'intrinsic_reward': 0.0}
        try:
            ensemble_result = self.ensemble.update(
                state_processed,
                int(action),
                float(reward),
                next_state_processed,
                bool(done),
                use_curiosity=self.config.get('usar_curiosity', True)
            )
            result.update(ensemble_result)
        except Exception as e:
            log_event(f"Ensemble update error: {e}", "CEOIA")
        
        # --- ACTUALIZAR Q-LEARNER ADICIONAL ---
        try:
            self.q_learner.store(
                state_processed,
                int(action),
                float(reward),
                next_state_processed,
                bool(done)
            )
            if hasattr(self.q_learner, 'memory') and len(self.q_learner.memory) >= getattr(self.q_learner, 'batch_size', 32):
                self.q_learner.learn()
        except Exception as e:
            log_event(f"Q-learner update error: {e}", "CEOIA")
        
        # --- ACTUALIZAR MCTS ---
        if self.config.get('usar_mcts', False):
            try:
                # Actualizar modelo interno de MCTS
                state_key = tuple(state_processed.tolist() if np is not None and isinstance(state_processed, np.ndarray) else state_processed)
                if hasattr(self.mcts, 'internal_model'):
                    self.mcts.internal_model[state_key][int(action)] += reward
            except Exception:
                pass
        
        # --- ALMACENAR EN MEMORIAS ---
        self._store_experience(state, action, reward, next_state, done, result)
        
        # --- ACTUALIZAR ESTADO INTERNO ---
        self._update_internal_state(reward, result)
        
        # --- AUTO-GUARDADO ---
        self._auto_save()
        
        return result

    def _store_experience(self, state, action, reward, next_state, done, result):
        """Almacena experiencia en todas las memorias."""
        # Convertir a formatos hashables
        state_key = self._to_hashable(state)
        next_state_key = self._to_hashable(next_state)
        
        # Memoria episodica
        try:
            exp = Experience(
                state=state_key,
                action=int(action),
                reward=float(reward),
                next_state=next_state_key,
                done=bool(done)
            )
            self.episodic_memory.add_episode([exp])
        except Exception as e:
            log_event(f"Episodic store error: {e}", "CEOIA")
        
        # Memoria a largo plazo
        self.long_term_memory.append({
            'state': state_key,
            'action': int(action),
            'reward': float(reward),
            'intrinsic_reward': result.get('intrinsic_reward', 0.0),
            'total_reward': result.get('total_reward', float(reward)),
            'timestamp': time.time()
        })

    def _to_hashable(self, state):
        """Convierte estado a formato hashable para almacenamiento."""
        if np is not None and isinstance(state, np.ndarray):
            return tuple(state.flatten().tolist())
        elif isinstance(state, (list, tuple)):
            return tuple(float(x) for x in state)
        elif isinstance(state, (int, float)):
            return (float(state),)
        return (str(state),)

    def _update_internal_state(self, reward, result):
        """Actualiza metricas internas de CEOIA."""
        self.internal_state['ciclos_ejecutados'] += 1
        self.internal_state['ultima_recompensa'] = float(reward)
        self.internal_state['ganancias_totales'] += float(reward)
        
        # Actualizar confianza
        total_reward = result.get('total_reward', reward)
        if total_reward > 10:
            self.internal_state['confianza_decisiones'] = min(
                1.0,
                self.internal_state['confianza_decisiones'] + 0.01
            )
        elif total_reward < 0:
            self.internal_state['confianza_decisiones'] = max(
                0.1,
                self.internal_state['confianza_decisiones'] - 0.02
            )
        
        # Decaimiento natural de energia
        self.internal_state['energia_mental'] = max(
            0.0,
            self.internal_state['energia_mental'] - 0.01
        )

    def _auto_save(self):
        """Guarda estado periodicamente."""
        self._save_counter += 1
        if self._save_counter % self.config.get('auto_save_interval', 100) == 0:
            try:
                save_state()
                save_daimon_brain()
                log_event("Auto-guardado completado", "CEOIA")
            except Exception as e:
                log_event(f"Auto-guardado error: {e}", "CEOIA")

    # ============================================================================
    # ESTADO COMPLETO Y UTILIDADES
    # ============================================================================
    def get_complete_state(self):
        """Retorna estado completo de todos los componentes."""
        state = {
            'ceoia': self.internal_state.copy(),
            'ensemble': {},
            'q_learner': {},
            'fuzzy_rules': 0,
            'episodic_memory': 0,
            'long_term_memory': len(self.long_term_memory),
            'routing_available': self.routing_available
        }
        
        # Ensemble state
        try:
            state['ensemble'] = self.ensemble.get_state()
        except Exception as e:
            state['ensemble'] = {'error': str(e)}
        
        # Q-learner state
        try:
            state['q_learner'] = {
                'epsilon': getattr(self.q_learner, 'epsilon', 0),
                'training_steps': getattr(self.q_learner, 'training_steps', 0),
                'memory_size': len(getattr(self.q_learner, 'memory', []))
            }
        except Exception:
            pass
        
        # Fuzzy
        try:
            state['fuzzy_rules'] = len(self.fuzzy.rules)
        except Exception:
            pass
        
        # Episodic memory
        try:
            state['episodic_memory'] = len(self.episodic_memory.episodes)
        except Exception:
            pass
        
        # Curiosity
        try:
            if hasattr(self.ensemble, 'curiosity'):
                curiosity = self.ensemble.curiosity
                state['curiosity'] = {
                    'buffer_size': len(getattr(curiosity, 'state_buffer', [])),
                    'unique_states': len(getattr(curiosity, 'state_counts', {}))
                }
        except Exception:
            pass
        
        # Kalman
        try:
            if hasattr(self.ensemble, 'kalman'):
                state['kalman_uncertainty'] = float(self.ensemble.kalman.get_uncertainty())
        except Exception:
            pass
        
        return state

    def register_module(self, name=None, module_ref=None, registered_at=None):
        """Registra un modulo en CEOIA."""
        log_event(f"Modulo registrado: {name}", "CEOIA")
        return True

    def shutdown(self):
        """Apaga CEOIA de forma segura."""
        self._learning_active = False
        if self._learning_thread and self._learning_thread.is_alive():
            self._learning_thread.join(timeout=2.0)
        
        try:
            save_state()
            save_daimon_brain()
        except Exception as e:
            log_event(f"Error en shutdown: {e}", "CEOIA")
        
        log_event("CEOIA apagado correctamente", "CEOIA")


# ================================================================================
# SECCION 37: VARIABLES GLOBALES CEOIA / DAIMON
# ================================================================================
STOP_EVENT = threading.Event()
simulacion_activa = True
data_lock = threading.Lock()
log_lock = threading.Lock()
mining_log = []
AI_READY = False
GPS_ACTIVE = False
GPS_CURRENT = None
GPS_OBJECTIVE = None
ULTIMA_ZONA = "z1"
DRIVER_STATE = "IDLE"
UBER_COINS = None
blockchain = []
block_number = 1
DAIMON_ID = str(uuid.uuid4())[:8]
Q_TABLE = {}
Q_TABLE_LOCK = threading.RLock()

zone_state = {
    z["id"]: {
        "color": "gris",
        "ganancia_estimada": 0.0,
        "tiempo_espera": 0.0,
        "demanda": 0,
        "oferta": 0,
        "ratio_demanda": 0.0
    }
    for z in [
        {"id": "z1", "nombre": "Albrook Mall", "lat_min": 8.97, "lat_max": 9.00, "lon_min": -79.54, "lon_max": -79.50},
        {"id": "z2", "nombre": "Arraijan Centro", "lat_min": 8.86, "lat_max": 8.90, "lon_min": -79.78, "lon_max": -79.74},
        {"id": "z3", "nombre": "La Chorrera", "lat_min": 8.86, "lat_max": 8.89, "lon_min": -79.80, "lon_max": -79.76},
        {"id": "z4", "nombre": "San Carlos", "lat_min": 8.87, "lat_max": 8.90, "lon_min": -79.82, "lon_max": -79.78},
        {"id": "z5", "nombre": "Veracruz", "lat_min": 8.84, "lat_max": 8.87, "lon_min": -79.84, "lon_max": -79.80},
    ]
}

ceoia = None
ceo_avanzado = None
ERROR_PATTERN = re.compile(r'error|exception|fail|traceback', re.IGNORECASE)

# ================================================================================
# SECCION 38: FUNCIONES DE UTILIDAD CEOIA
# ================================================================================
def calculate_distance_py(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def sigmoid_utils(x):
    return 1 / (1 + math.exp(-max(-100, min(100, x))))

def activity_factor(timestamp=None):
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc)
    hour = dt.hour
    base = 1.6 if 7 <= hour <= 9 else 1.8 if 17 <= hour <= 19 else 0.25 if 2 <= hour <= 5 else 1.0
    if dt.weekday() >= 5: base *= 0.9
    return round(base * random.uniform(0.85, 1.25), 3)

def batch_write_file(filepath, content):
    try:
        tmp_path = Path(str(filepath) + ".tmp")
        tmp_path.write_text(content, encoding='utf-8')
        tmp_path.replace(Path(filepath))
    except Exception as e:
        log_event(f"Error al escribir: {e}", "IO")

def _softmax_util(x):
    if np is None:
        exp_x = [math.exp(i) for i in x]
        s = sum(exp_x)
        return [i/s if s > 0 else 1.0/len(x) for i in exp_x]
    exp_x = np.exp(x - np.max(x))
    return exp_x / exp_x.sum()

# ================================================================================
# SECCION 39: FUNCIONES DE INTEGRACION MILEAGE
# ================================================================================
def _patch_ceoia_with_mileage(ceoia_instance):
    if not ceoia_instance or hasattr(ceoia_instance, 'mileage_learner'):
        return ceoia_instance
    ceoia_instance.mileage_learner = MileageLearner(
        bins=(8, 18, 30),
        min_samples=15 if GlobalConfig.IS_LOW_MEMORY else 20,
        persistence_path=Path.home() / ".symbiosis" / "data" / "mileage_model.json"
    )
    original_learn = getattr(ceoia_instance, 'learn', None)
    
    def enhanced_learn(state, action, reward, done=True, **kwargs):
        # --- BLOQUE: INYECCION DE RECOMPENSA POR KILOMETRAJE ---
        km = 0.0
        if isinstance(state, (list, tuple)) and len(state) > 8:
            km = float(state[8]) if isinstance(state[8], (int, float)) else 0.0
        elif isinstance(state, dict) and 'trip_distance_km' in state:
            km = float(state['trip_distance_km'])
        context = {
            'is_rush_hour': 7 <= (time.time() % 24) <= 9 or 17 <= (time.time() % 24) <= 19,
            'surge_multiplier': 1.0, 'weather': 'clear',
            'is_weekend': datetime.now().weekday() >= 5, 'zone': 'z1'
        }
        if km > 0 and hasattr(ceoia_instance, 'mileage_learner'):
            ceoia_instance.mileage_learner.record(
                km=km, reward=reward,
                features={'hour': time.time() % 24, 'zone': context['zone'], 'surge': context['surge_multiplier']},
                metadata={'action': action, 'done': done}
            )
            prediction = ceoia_instance.mileage_learner.predict_profitability(km, context)
            if prediction['confidence'] >= 0.5:
                baseline, deviation = 5.0, prediction['predicted_reward'] - baseline
                mileage_bonus = deviation * 0.2 * prediction['confidence']
                reward += mileage_bonus
                if abs(mileage_bonus) > 0.5:
                    log_event(f"Mileage bonus: {mileage_bonus:+.2f}", "MILEAGE")
        if original_learn:
            return original_learn(state, action, reward, done, **kwargs)
        return {'reward_adjusted': reward}
        
    ceoia_instance.learn = enhanced_learn
    log_event("MileageLearner integrado en CEOIA", "INTEGRATION")
    return ceoia_instance

def auto_activate_mileage_learning(ceoia_ref=None):
    global ceoia
    target_ceo = ceoia_ref or (ceoia if 'ceoia' in globals() else None)
    if target_ceo:
        return _patch_ceoia_with_mileage(target_ceo)
    else:
        log_event("MileageLearner en espera de CEOIA", "MILEAGE")
        return MileageLearner(bins=(8, 18, 30), min_samples=15)

def enhance_negotiation_environment_with_mileage(env_class, mileage_learner_ref):
    if not env_class or not mileage_learner_ref: return env_class
    original_calculate_reward = getattr(env_class, '_calculate_reward', None)
    
    def enhanced_calculate_reward(self, action, next_state):
        base_reward = original_calculate_reward(self, action, next_state) if original_calculate_reward else 0.0
        km = getattr(next_state, 'trip_distance_km', 0.0) if hasattr(next_state, 'trip_distance_km') else 0.0
        if km > 0 and hasattr(mileage_learner_ref, 'predict_profitability'):
            context = {
                'is_rush_hour': getattr(next_state, 'is_rush_hour', False),
                'surge_multiplier': getattr(next_state, 'surge_multiplier', 1.0),
                'zone': getattr(next_state, 'zone_id', 'unknown')
            }
            prediction = mileage_learner_ref.predict_profitability(km, context)
            if prediction['confidence'] >= 0.4 and prediction['bin'] == 'medium_8_18' and prediction['predicted_reward'] > 7:
                base_reward += 0.15 * prediction['confidence']
        return base_reward
        
    env_class._calculate_reward = enhanced_calculate_reward
    log_event("NegotiationEnvironment extendido con recompensas por kilometraje", "INTEGRATION")
    return env_class

# ================================================================================
# SECCION 40: FUNCIONES DE INICIALIZACION Y ESTADO
# ================================================================================
def start_unified_ceoia():
    global ceoia, ceo_avanzado
    ceoia = CEOIA()
    ceo_avanzado = ceoia
    return ceoia

def SINGULARIDAD_OMEGA(**kwargs):
    return {"exito": True, "ganancias_generadas": 0.0}

def save_state():
    try:
        state = {
            'ceoia': ceoia.internal_state if ceoia else {},
            'zone_state': zone_state,
            'blockchain': blockchain[-100:]
        }
        batch_write_file(GlobalConfig.STATE_FILE, json.dumps(state, indent=2))
    except Exception as e:
        log_event(f"Error guardando estado: {e}", "SAVE")

def save_daimon_brain():
    try:
        brain = {
            'q_table': dict(Q_TABLE),
            'ensemble_weights': ceoia.ensemble.weights if ceoia else {},
            'timestamp': time.time()
        }
        batch_write_file(GlobalConfig.DAIMON_BRAIN_FILE, json.dumps(brain, indent=2))
    except Exception as e:
        log_event(f"Error guardando cerebro: {e}", "BRAIN")

# ================================================================================
# SECCION 41: PUNTO DE ENTRADA UNICO (CORREGIDO)
# ================================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SISTEMA DAIMON VIVO - CEOIA UNIFICADO [CORREGIDO]")
    print("=" * 60 + "\n")

    ceoia = CEOIA()
    profile = UtilityProfile()

    print("Algoritmos activos en el ensamble:")
    print(" - Q-Learning Tabular (Sistema Unificado)")
    print(" - Policy Gradient (Sistema Unificado)")
    print(" - Actor-Critic Hibrido (Sistema Unificado)")
    print(" - Double DQN con PER y N-pasos (CEOIA)")
    print(" - SARSA (CEOIA)")
    print(" - Actor-Critico A2C (CEOIA)")
    print(" - PPO (CEOIA)")
    print(" - MCTS (CEOIA)")
    print(" - Algoritmo Genetico (CEOIA)")
    print(" - Logica Difusa [CORREGIDA] (CEOIA)")
    print(" - Filtro de Kalman (CEOIA)")
    print(" - Aprendizaje por Curiosidad [CORREGIDO] (CEOIA)")
    print(" - Metaaprendizaje (CEOIA)")
    print(" - Aproximador Q Neuronal (CEOIA)")
    print(" - Matching Engine (Hungarian, Gale-Shapley, Greedy)")
    print(" - Mileage Learner (Aprendizaje por distancia)")
    print("\n" + "=" * 60 + "\n")

    log_banner("TESTS BASICOS DEL SISTEMA")
    try:
        hn = HyperNumberAdvanced(10)
        print(f"HyperNumber test: {hn.display()}")
        loc1 = GeoLocation(latitude=9.0, longitude=-79.5)
        loc2 = GeoLocation(latitude=8.9, longitude=-79.6)
        print(f"Distancia entre puntos: {loc1.distance_to(loc2):.2f} km")
        offer = Offer(price=10.0, quality_level=4, counterparty_reputation=0.8)
        utility = profile.calculate_utility(offer)
        print(f"Utilidad calculada: {utility:.4f}")
        profile_serialized = asdict(profile)
        print(f"Serializacion exitosa: {list(profile_serialized.keys())}")
        log_event("Tests basicos completados", level="SUCCESS")
    except Exception as e:
        log_event(f"Error en tests basicos: {e}", "ERROR")

    log_banner("DEMO: MATCHING ENGINE INTEGRADO")
    try:
        agents = [
            MatchingAgent(
                agent_id=f"A{i}", name=f"Agent_{i}",
                location=(9.0 + i * 0.01, -79.5 + i * 0.01),
                preferences={"price": random.uniform(0.3, 0.9), "time": random.uniform(0.2, 0.8)},
                rating=random.uniform(0.4, 1.0)
            ) for i in range(10)
        ]
        matching_engine = MatchingEngine()
        for agent in agents:
            matching_engine.update_features(agent.agent_id, agent.to_features())
        score, breakdown = matching_engine.compute_similarity(agents[0], agents[1])
        log_event(f"Similaridad A0 <-> A1: {score:.3f} | breakdown: {breakdown}", "MATCH")
        recommendations = matching_engine.get_recommendations(agents[0].agent_id, top_k=3)
        log_event(f"Recomendaciones para A0: {[(aid, f'{s:.2f}') for aid, s in recommendations]}", "MATCH")
        geo = GeoMatcher(cell_size_km=15.0)
        coords = [(a.agent_id, a.location[0], a.location[1]) for a in agents if a.location]
        clusters = geo.cluster_agents(coords)
        log_event(f"Clusters geograficos: {len(clusters)} celdas", "MATCH")
    except Exception as e:
        log_event(f"Error en demo Matching: {e}", "ERROR")

    log_banner("DEMO: RL + MATCHING INTEGRATION")
    try:
        rl_layer = RLIntegrationLayer(algorithm=RLAlgorithm.Q_LEARNING, auto_train=True, use_matching=True)
        if GlobalConfig.LOG_VERBOSE or not rl_layer.is_trained:
            stats = rl_layer.train_if_needed(episodes=50 if GlobalConfig.IS_LOW_MEMORY else 100)
            if stats:
                log_event(f"Q-Table size: {stats['q_table_size']} estados", "RL")
        session = NegotiationSession(agent_a_id="RL_AGENT", agent_b_id="OPPONENT", domain="ride_hailing", item_description="Viaje premium", max_rounds=5)
        available_offers = [Offer(price=10.0 + i * 5, delivery_time=15.0, quality_level=4, proposed_by=f"AGENT_{i}") for i in range(5)]
        best_offer = rl_layer.select_action_for_negotiation(session, "RL_AGENT", available_offers)
        if best_offer:
            log_event(f"Oferta seleccionada por RL+Matching: ${best_offer.price:.2f}", "RL")
        session.status = NegotiationStatus.ACCEPTED
        session.final_utility_a = 0.85
        session.final_offer = best_offer
        rl_layer.update_from_negotiation_result(session, "RL_AGENT", reward=1.0)
        log_event("Negociacion simulada completada con RL+Matching", "RL")
    except Exception as e:
        log_event(f"Error en demo RL+Matching: {e}", "ERROR")

    log_banner("DEMO: CEOIA ENSAMBLE")
    try:
        for i in range(10):
            state = ceoia._get_current_state()
            action = ceoia.decide_action(state)
            reward = random.uniform(-5, 15)
            ceoia.learn(state, action, reward)
            print(f" Decision {i+1}: Accion={action}, Recompensa={reward:.2f}")
        print("\nEstado final CEOIA:")
        final_state = ceoia.get_complete_state()
        for k, v in final_state.items():
            print(f" {k}: {v}")
    except Exception as e:
        log_event(f"Error en demo CEOIA: {e}", "ERROR")

    log_banner("AGENTE VIVO - PRESIONA CTRL+C PARA DETENER")
    tick = 0
    cumulative_km = 0.0
    trip_count = 0
    try:
        while True:
            tick += 1
            trip_distance = random.uniform(2.0, 25.0) if tick % 3 == 0 else 0.0
            if trip_distance > 0:
                cumulative_km += trip_distance
                trip_count += 1
                avg_km = cumulative_km / trip_count if trip_count > 0 else 0
            hn = HyperNumberAdvanced(tick * 10)
            offer = Offer(price=10 + tick, quality_level=4, counterparty_reputation=0.8)
            utility = profile.calculate_utility(offer)
            mileage_info = ""
            try:
                ceo_state = ceoia._get_current_state()
                ceo_action = ceoia.decide_action(ceo_state)
                ceo_reward = random.uniform(-2, 10)
                ceoia.learn(ceo_state, ceo_action, ceo_reward)
            except Exception:
                ceo_action, ceo_reward = 0, 0
            print("\n" + "-" * 40)
            print(f"TICK: {tick}{mileage_info}")
            print(f"HyperNumber: {hn.display()}")
            print(f"Utilidad: {utility:.4f}")
            print(f"CEOIA: accion={ceo_action}, reward={ceo_reward:.2f}")
            if trip_distance > 0:
                print(f"Viaje: {trip_distance:.1f}km | Acumulado: {cumulative_km:.1f}km")
            print("-" * 40)
            time.sleep(1)
    except KeyboardInterrupt:
        log_event("AGENTE DETENIDO POR USUARIO (CTRL+C)", "WARN")
        print("\nSistema detenido correctamente.")
    except Exception as e:
        log_event(f"ERROR CRITICO: {e}", "ERROR")
        print("\nError en el sistema:", e)
        traceback.print_exc()
    finally:
        print("\nLimpieza finalizada. Sistema listo para reinicio.")
        save_state()
        save_daimon_brain()
        log_event("Estado y cerebro guardados", "SAVE")

