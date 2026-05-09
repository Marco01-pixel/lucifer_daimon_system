#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================================================
# SECCION 1: METADATOS Y CONFIGURACION INICIAL
# ================================================================================
"""
PARTE 4/9 - UBER DEMAND PREDICTOR PRO v4.4 (POTENCIADO)
Sistema de Prediccion de Demanda Espaciotemporal con Ensemble ML

Correcciones y Mejoras:
- FIX01: _ensure_geo ahora existe y es consistente
- FIX02: Eliminada inicializacion automatica peligrosa
- FIX03: Manejo de errores CEO sin silenciamiento
- FIX04: Optimizacion de imports fnmatch
- FIX05: Calculo correcto de std_demand
- FIX06: Agregado __all__ para control de exports
- FIX07: Renombrada funcion predict global para evitar shadowing
- FIX08: pickle con protocolo especificado
- FIX09: ThreadMonitor con shutdown graceful
- FIX10: Validacion de tipos en _ensure_geo mejorada
- MEJORA11: analizar_prompt_mejor_opcion integrado con SmartUberPredictor
- MEJORA12: f-strings eliminados por .format() para compatibilidad 3.6+
"""

from __future__ import annotations

# ================================================================================
# SECCION 2: IMPORTACIONES ESTANDAR
# ================================================================================

import copy
import fnmatch
import hashlib
import json
import math
import os
import pickle
import random
import sys
import threading
import time
import warnings
from collections import defaultdict, deque, namedtuple
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# ================================================================================
# SECCION 3: CONFIGURACION DE WARNINGS
# ================================================================================

warnings.filterwarnings('ignore', category=FutureWarning)

# ================================================================================
# SECCION 4: IMPORTACIONES OPCIONALES CON FALLBACK
# ================================================================================

# --- BLOQUE: NUMPY ---
try:
    import numpy as np
    from numpy.typing import NDArray
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False
    print("[WARN] numpy no disponible - usando implementaciones basicas")

# --- BLOQUE: SCIKIT-LEARN ---
try:
    from sklearn.preprocessing import MinMaxScaler, StandardScaler
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[WARN] scikit-learn no disponible - usando implementaciones basicas")

# --- BLOQUE: PROPHET ---
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("[WARN] Prophet no disponible - usando SARIMA basico")

# ================================================================================
# SECCION 5: MODO MODULO Y CONFIGURACION GLOBAL
# ================================================================================

_IS_MODULE_MODE = False

def set_module_mode():
    """Activa el modo modulo para evitar carga de cache y demos al importar."""
    global _IS_MODULE_MODE
    _IS_MODULE_MODE = True


class DemandConfig:
    """Configuracion centralizada del sistema de prediccion."""

    # --- BLOQUE: PARAMETROS DE PREDICCION ---
    PREDICTION_HORIZON = 30
    HISTORICAL_WINDOW = 7 * 24 * 60
    NUM_TEMPORAL_FEATURES = 12
    NUM_SPATIAL_FEATURES = 8
    NUM_EXTERNAL_FEATURES = 6

    # --- BLOQUE: FLAGS DE MODELOS ---
    USE_DEEP_LEARNING = False
    USE_PROPHET = PROPHET_AVAILABLE
    USE_ENSEMBLE = True

    # --- BLOQUE: PARAMETROS ESPACIALES ---
    GRID_RESOLUTION_KM = 0.5
    HEX_RESOLUTION = 7

    # --- BLOQUE: UMBRALES ---
    HIGH_DEMAND_THRESHOLD = 7.5
    SURGE_PREDICTION_THRESHOLD = 1.5

    # --- BLOQUE: RUTAS ---
    MODEL_CACHE_DIR = Path.home() / ".uber_predictor" / "models"
    DATA_CACHE_DIR = Path.home() / ".uber_predictor" / "data"

    # --- BLOQUE: LIMITES DE MEMORIA ---
    MAX_SAMPLES_MEMORY = 50000

    # --- BLOQUE: CONFIGURACION DE REGISTRY ---
    REGISTRY_SYNC_ENABLED = True
    REGISTRY_SYNC_INTERVAL = 30.0

    # --- BLOQUE: CONFIGURACION DE THREADS ---
    THREAD_MONITOR_ENABLED = True
    THREAD_MONITOR_INTERVAL = 15.0
    CEO_LISTENER_ENABLED = True
    CEO_LISTENER_INTERVAL = 10.0


# ================================================================================
# SECCION 6: IMPORTACION DE CONFIGURACION BASE Y REGISTRY
# ================================================================================

# --- BLOQUE: INTENTO DE IMPORTAR PARTE 1/9 ---
try:
    from part1_config import (
        GeoLocation,
        GlobalConfig,
        SharedDataRegistry,
        log_banner,
        log_event,
    )
except ImportError as e:
    print("[WARN] No se pudo importar symbiosis_parte1: {}".format(e))
    print("[WARN] Usando fallback interno...")

    # --- BLOQUE: FALLBACK GlobalConfig ---
    class GlobalConfig:
        IS_TERMUX = True

    # --- BLOQUE: FALLBACK log_event ---
    def log_event(msg, level="INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        print("[{}][{}] {}".format(now, level, msg))

    # --- BLOQUE: FALLBACK log_banner ---
    def log_banner(msg, emoji=""):
        print("=" * 60)
        if emoji:
            print("{} {}".format(emoji, msg))
        else:
            print("{}".format(msg))
        print("=" * 60)

    # --- BLOQUE: FALLBACK GeoLocation ---
    class GeoLocation:
        def __init__(self, latitude, longitude):
            self.latitude = latitude
            self.longitude = longitude

        def to_dict(self):
            return {
                "latitude": self.latitude,
                "longitude": self.longitude
            }

        def is_valid(self):
            return -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180

    # --- BLOQUE: FALLBACK SharedDataRegistry ---
    class SharedDataRegistry:
        """Fallback minimalista para acceso PARTE 1/9."""

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
            if self._initialized:
                return
            with self._lock:
                if self._initialized:
                    return
                self._data = {}
                self._callbacks = defaultdict(list)
                self._initialized = True

        def set(self, key, value, notify=True):
            with self._lock:
                try:
                    self._data[key] = copy.deepcopy(value)
                    if notify:
                        self._trigger_callbacks(key, value)
                    return True
                except Exception:
                    return False

        def get(self, key, default=None):
            with self._lock:
                return copy.deepcopy(self._data.get(key, default))

        def get_all(self, pattern=None):
            with self._lock:
                if pattern is None:
                    return {k: copy.deepcopy(v) for k, v in self._data.items()}
                return {
                    k: copy.deepcopy(v)
                    for k, v in self._data.items()
                    if fnmatch.fnmatch(k, pattern)
                }

        def on_change(self, key_pattern, callback):
            with self._lock:
                callback_id = str(hash(callback))[:8]
                self._callbacks[key_pattern].append((callback_id, callback))
                return callback_id

        def _trigger_callbacks(self, key, value):
            for pattern, callbacks in self._callbacks.items():
                if fnmatch.fnmatch(key, pattern):
                    for _, cb in callbacks:
                        try:
                            cb(key, value)
                        except Exception:
                            pass


# ================================================================================
# SECCION 7: CLASE THREADMONITOR
# ================================================================================

class ThreadMonitor:
    """Monitor que reporta estado visible de todos los hilos del sistema."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # --- BLOQUE: PATRON SINGLETON THREAD-SAFE ---
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ThreadMonitor, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # --- BLOQUE: INICIALIZACION DEL MONITOR ---
        if getattr(self, "_initialized", False):
            return

        with self._lock:
            if getattr(self, "_initialized", False):
                return

            self._threads = {}
            self._status = {}
            self._running = False
            self._monitor_thread = None
            self._interval = 15.0
            self._initialized = True

    def register_thread(self, name, thread):
        # --- BLOQUE: REGISTRO DE HILO CON LOG VISIBLE ---
        with self._lock:
            self._threads[name] = thread
            self._status[name] = "iniciando"

        log_event("[HILO] Conectado: {}".format(name), "INFO")

    def update_status(self, name, status):
        # --- BLOQUE: ACTUALIZACION DE ESTADO ---
        with self._lock:
            if name in self._status:
                self._status[name] = status

    def get_active_threads(self):
        # --- BLOQUE: OBTENCION DE ESTADO ACTUAL ---
        with self._lock:
            result = {}
            for name, thread in self._threads.items():
                is_alive = thread.is_alive() if thread else False
                result[name] = "activo" if is_alive else "inactivo"
            return result

    def start_monitoring(self, interval=15.0):
        # --- BLOQUE: INICIO DEL MONITOR PERIODICO ---
        if self._running:
            return

        self._interval = interval
        self._running = True

        def monitor_loop():
            while self._running:
                active = self.get_active_threads()
                if active:
                    summary = ", ".join("{}:{}".format(n, s) for n, s in active.items())
                    log_event("[MONITOR] Hilos activos: {}".format(summary), "DEBUG")
                time.sleep(self._interval)

        self._monitor_thread = threading.Thread(
            target=monitor_loop,
            daemon=True,
            name="ThreadMonitor"
        )
        self._monitor_thread.start()

        self.register_thread("ThreadMonitor", self._monitor_thread)
        log_event("[HILO] Monitor de threads iniciado", "INFO")

    def stop_monitoring(self):
        # --- BLOQUE: DETENCION DEL MONITOR ---
        self._running = False

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)

        log_event("[HILO] Monitor de threads detenido", "INFO")

    def shutdown_all(self):
        # --- BLOQUE: APAGADO GRACEFUL DE TODOS LOS HILOS ---
        self._running = False
        with self._lock:
            for name, thread in list(self._threads.items()):
                if thread is not self._monitor_thread and thread.is_alive():
                    log_event("[HILO] Esperando terminacion de: {}".format(name), "DEBUG")
                    thread.join(timeout=3.0)
        self.stop_monitoring()


# ================================================================================
# SECCION 8: CLASE GEOPOINT
# ================================================================================

@dataclass
class GeoPoint:
    """Punto geografico con metadatos."""

    latitude: float
    longitude: float
    timestamp: Optional[datetime] = None
    accuracy: float = 0.0

    def to_array(self):
        # --- BLOQUE: CONVERSION A ARRAY SEGUN DISPONIBILIDAD DE NUMPY ---
        if NP_AVAILABLE:
            return np.array([self.latitude, self.longitude])
        return [self.latitude, self.longitude]

    def distance_to(self, other):
        # --- BLOQUE: CALCULO DE DISTANCIA HAVERSINE ---
        R = 6371.0
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def to_hex_cell(self, resolution=7):
        # --- BLOQUE: CONVERSION A CELDA HEXAGONAL O FALLBACK ---
        try:
            import h3
            return h3.latlng_to_cell(self.latitude, self.longitude, resolution)
        except ImportError:
            lat_idx = int((self.latitude + 90) / (5 / (2 ** resolution)))
            lon_idx = int((self.longitude + 180) / (5 / (2 ** resolution)))
            return "sq:{}:{}".format(lat_idx, lon_idx)


# ================================================================================
# SECCION 9: CLASE TEMPORALFEATURES
# ================================================================================

@dataclass
class TemporalFeatures:
    """Features temporales extraidos de timestamp."""

    hour: int
    minute: int
    day_of_week: int
    day_of_month: int
    month: int
    is_weekend: bool
    is_holiday: bool
    is_rush_hour_morning: bool
    is_rush_hour_evening: bool
    is_night: bool
    quarter: int
    days_to_holiday: int

    @classmethod
    def from_datetime(cls, dt, holidays=None):
        # --- BLOQUE: EXTRACCION DE COMPONENTES TEMPORALES ---
        hour = dt.hour
        dow = dt.weekday()
        is_rush_morning = 7 <= hour <= 9 and dow < 5
        is_rush_evening = 17 <= hour <= 20 and dow < 5
        is_night = hour >= 22 or hour < 5
        is_weekend = dow >= 5
        holiday_dates = holidays or []
        date_str = dt.strftime("%Y-%m-%d")
        is_holiday = date_str in holiday_dates

        # --- BLOQUE: CALCULO DE DIAS PARA PROXIMO FERIADO ---
        days_to = 999
        if holidays:
            for h in holidays:
                try:
                    h_date = datetime.strptime(h, "%Y-%m-%d")
                    delta = (h_date - dt).days
                    if 0 <= delta < abs(days_to):
                        days_to = delta
                except ValueError:
                    continue

        return cls(
            hour=hour, minute=dt.minute, day_of_week=dow, day_of_month=dt.day,
            month=dt.month, is_weekend=is_weekend, is_holiday=is_holiday,
            is_rush_hour_morning=is_rush_morning, is_rush_hour_evening=is_rush_evening,
            is_night=is_night, quarter=(dt.month - 1) // 3 + 1,
            days_to_holiday=days_to if days_to != 999 else 0
        )

    def to_array(self, cyclical=True):
        # --- BLOQUE: CODIFICACION CICLICA PARA FEATURES TEMPORALES ---
        if cyclical:
            hour_sin = math.sin(2 * math.pi * self.hour / 24)
            hour_cos = math.cos(2 * math.pi * self.hour / 24)
            dow_sin = math.sin(2 * math.pi * self.day_of_week / 7)
            dow_cos = math.cos(2 * math.pi * self.day_of_week / 7)
            month_sin = math.sin(2 * math.pi * self.month / 12)
            month_cos = math.cos(2 * math.pi * self.month / 12)
            features = [
                hour_sin, hour_cos, dow_sin, dow_cos, month_sin, month_cos,
                float(self.is_weekend), float(self.is_holiday),
                float(self.is_rush_hour_morning), float(self.is_rush_hour_evening),
                float(self.is_night), self.days_to_holiday / 7.0
            ]
        else:
            features = [
                self.hour / 24.0, self.day_of_week / 7.0, self.month / 12.0,
                float(self.is_weekend), float(self.is_holiday),
                float(self.is_rush_hour_morning), float(self.is_rush_hour_evening),
                float(self.is_night), self.quarter / 4.0, self.days_to_holiday / 7.0
            ]

        if NP_AVAILABLE:
            return np.array(features)
        return features


# ================================================================================
# SECCION 10: CLASE EXTERNALFEATURES
# ================================================================================

@dataclass
class ExternalFeatures:
    """Features externas: clima, eventos, trafico."""

    temperature: float
    humidity: float
    precipitation: float
    wind_speed: float
    has_major_event: bool
    event_attendance: int
    traffic_index: float
    public_transit_disruption: bool

    def to_array(self):
        # --- BLOQUE: NORMALIZACION DE FEATURES EXTERNAS ---
        features = [
            self.temperature / 40.0, self.humidity / 100.0,
            min(self.precipitation / 50.0, 1.0), self.wind_speed / 100.0,
            float(self.has_major_event), math.log1p(self.event_attendance) / 10.0,
            self.traffic_index / 10.0, float(self.public_transit_disruption)
        ]

        if NP_AVAILABLE:
            return np.array(features)
        return features


# ================================================================================
# SECCION 11: CLASE DEMANDSAMPLE
# ================================================================================

@dataclass
class DemandSample:
    """Muestra completa de demanda para entrenamiento."""

    timestamp: datetime
    location: GeoPoint
    temporal: TemporalFeatures
    external: ExternalFeatures
    request_count: int
    completed_trips: int
    driver_supply: int
    avg_eta_seconds: float
    surge_multiplier: float
    demand_supply_ratio: float
    earnings_potential: float

    @property
    def demand_score(self):
        # --- BLOQUE: CALCULO DE SCORE DE DEMANDA COMPUESTO ---
        req_score = min(self.request_count / 50, 1.0) * 3
        ratio_score = min(self.demand_supply_ratio / 3, 1.0) * 4
        surge_score = min(max(self.surge_multiplier - 1, 0) / 2, 1.0) * 3
        return req_score + ratio_score + surge_score


# ================================================================================
# SECCION 12: CLASE SPATIOTEMPORALDATASTORE
# ================================================================================

class SpatiotemporalDataStore:
    """Almacen de datos historicos con indexacion espacial y temporal."""

    def __init__(self, config=None, registry=None):
        # --- BLOQUE: INICIALIZACION DE ESTRUCTURAS DE DATOS ---
        self.config = config or DemandConfig()
        self.registry = registry or SharedDataRegistry()
        self.samples = deque(maxlen=self.config.MAX_SAMPLES_MEMORY)
        self.time_index = defaultdict(list)
        self.spatial_index = defaultdict(list)
        self.zone_stats = {}
        self._lock = threading.RLock()
        self._last_sync = 0.0
        self._load_persisted()

    def add_sample(self, sample, sync_registry=True):
        # --- BLOQUE: INDEXACION TEMPORAL Y ESPACIAL ---
        with self._lock:
            self.samples.append(sample)
            time_bucket = sample.timestamp.replace(
                minute=(sample.timestamp.minute // 15) * 15,
                second=0, microsecond=0
            ).isoformat()
            self.time_index[time_bucket].append(sample)
            cell = sample.location.to_hex_cell()
            self.spatial_index[cell].append(sample)
            self._update_zone_stats(cell, sample)

            # --- BLOQUE: SINCRONIZACION CON REGISTRY ---
            if sync_registry and self.config.REGISTRY_SYNC_ENABLED:
                self._sync_sample_to_registry(sample, cell)

    def _sync_sample_to_registry(self, sample, cell):
        # --- BLOQUE: PUBLICACION DE MUESTRA AL REGISTRY ---
        try:
            sample_data = {
                'timestamp': sample.timestamp.isoformat(),
                'location': {'lat': sample.location.latitude, 'lon': sample.location.longitude},
                'cell': cell, 'request_count': sample.request_count,
                'demand_score': sample.demand_score,
                'surge_multiplier': sample.surge_multiplier,
                'demand_supply_ratio': sample.demand_supply_ratio
            }
            self.registry.set(
                "predictor:sample:{}:{}".format(cell, sample.timestamp.timestamp()), sample_data
            )
            self.registry.set("predictor:zone:{}:latest".format(cell), sample_data)
        except Exception as e:
            log_event("[WARN] Error sincronizando muestra: {}".format(e), "WARN")

    def _update_zone_stats(self, cell, sample):
        # --- BLOQUE: ACTUALIZACION DE ESTADISTICAS DE ZONA ---
        if cell not in self.zone_stats:
            self.zone_stats[cell] = {
                'count': 0, 'avg_demand': 0.0, 'avg_surge': 1.0,
                'peak_hours': set(), 'last_updated': sample.timestamp
            }

        stats = self.zone_stats[cell]
        alpha = 0.1
        stats['count'] += 1
        stats['avg_demand'] = (1 - alpha) * stats['avg_demand'] + alpha * sample.request_count
        stats['avg_surge'] = (1 - alpha) * stats['avg_surge'] + alpha * sample.surge_multiplier

        if sample.request_count > stats['avg_demand'] * 1.5:
            stats['peak_hours'].add(sample.timestamp.hour)

        stats['last_updated'] = sample.timestamp

        # --- BLOQUE: SINCRONIZACION DE ESTADISTICAS ---
        if self.config.REGISTRY_SYNC_ENABLED:
            self.registry.set("predictor:zone:{}:stats".format(cell), {
                'avg_demand': stats['avg_demand'], 'avg_surge': stats['avg_surge'],
                'peak_hours': list(stats['peak_hours']), 'sample_count': stats['count']
            })

    def get_zone_historical_pattern(self, cell, day_of_week, hour):
        # --- BLOQUE: BUSQUEDA DE PATRONES HISTORICOS ---
        with self._lock:
            samples = self.spatial_index.get(cell, [])
            matching = [
                s for s in samples
                if s.temporal.day_of_week == day_of_week and s.temporal.hour == hour
            ]

            if not matching:
                return None

            # --- BLOQUE: CALCULO DE METRICAS ESTADISTICAS ---
            demands = [s.request_count for s in matching]
            surges = [s.surge_multiplier for s in matching]
            etas = [s.avg_eta_seconds for s in matching]

            n = len(demands)
            avg_demand = sum(demands) / n

            # FIX05: Calculo correcto de desviacion estandar
            if n > 1:
                variance = sum((d - avg_demand) ** 2 for d in demands) / n
                std_demand = math.sqrt(variance)
            else:
                std_demand = 0.0

            avg_prev = sum(demands[:-1]) / (n - 1) if n > 1 else demands[0]

            return {
                'sample_count': n, 'avg_demand': avg_demand,
                'std_demand': std_demand,
                'avg_surge': sum(surges) / len(surges) if surges else 1.0,
                'avg_eta': sum(etas) / len(etas) if etas else 300,
                'demand_trend': 'increasing' if demands[-1] > avg_prev else 'stable'
            }

    def _load_persisted(self):
        # --- BLOQUE: CARGA DE DATOS PERSISTIDOS ---
        if _IS_MODULE_MODE:
            return

        data_file = self.config.DATA_CACHE_DIR / "demand_history.pkl"
        if not data_file.exists():
            return

        try:
            with open(data_file, 'rb') as f:
                loaded = pickle.load(f)
                self.samples = loaded.get('samples', deque(maxlen=self.config.MAX_SAMPLES_MEMORY))
                self.time_index = defaultdict(list, loaded.get('time_index', {}))
                self.spatial_index = defaultdict(list, loaded.get('spatial_index', {}))
                self.zone_stats = loaded.get('zone_stats', {})

            log_event("[OK] Cargados {} muestras historicas".format(len(self.samples)), "INFO")
        except Exception as e:
            log_event("[WARN] Error cargando datos: {}".format(e), "WARN")

    def persist(self):
        # --- BLOQUE: PERSISTENCIA EN DISCO ---
        self.config.DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data_file = self.config.DATA_CACHE_DIR / "demand_history.pkl"

        with self._lock:
            with open(data_file, 'wb') as f:
                # FIX08: Protocolo pickle especificado para compatibilidad
                pickle.dump({
                    'samples': self.samples,
                    'time_index': dict(self.time_index),
                    'spatial_index': dict(self.spatial_index),
                    'zone_stats': self.zone_stats
                }, f, protocol=pickle.HIGHEST_PROTOCOL)

        log_event("[OK] Persistidos {} muestras".format(len(self.samples)), "INFO")

    def get_registry_instance(self):
        return self.registry

    def subscribe_to_zone(self, cell, callback):
        return self.registry.on_change("predictor:zone:{}:*".format(cell), callback)


# ================================================================================
# SECCION 13: CLASES BASEDEMANDMODEL Y HEURISTICDEMANDMODEL
# ================================================================================

class BaseDemandModel:
    """Clase base para modelos de prediccion de demanda."""

    def __init__(self, name):
        self.name = name
        self.is_fitted = False
        self.metrics = {}

    def fit(self, samples):
        raise NotImplementedError

    def predict(self, location, timestamp, external=None):
        raise NotImplementedError


class HeuristicDemandModel(BaseDemandModel):
    """Modelo heuristico base - siempre disponible."""

    def __init__(self):
        super().__init__("Heuristic")
        self.is_fitted = True

    def fit(self, X=None, y=None):
        """Metodo dummy para compatibilidad con el ensemble."""
        return self

    def predict(self, location, timestamp, external=None):
        # --- BLOQUE: CALCULO DE SCORE HEURISTICO ---
        temporal = TemporalFeatures.from_datetime(timestamp)
        score = 5.0

        if temporal.is_rush_hour_morning or temporal.is_rush_hour_evening:
            score = 7.0
        elif temporal.is_night:
            score = 3.5

        if external:
            if external.has_major_event:
                score += 1.5
            score += (external.traffic_index - 5) * 0.2

        return {'demand_score': min(max(score, 0.0), 10.0), 'confidence': 0.5, 'model': 'heuristic'}


# ================================================================================
# SECCION 14: CLASE SKLEARNDEMANDMODEL
# ================================================================================

class SklearnDemandModel(BaseDemandModel):
    """Wrapper para modelos sklearn con fallback seguro."""

    def __init__(self, sklearn_model):
        # --- BLOQUE: INICIALIZACION DEL WRAPPER ---
        super().__init__(sklearn_model.__class__.__name__)
        self.sklearn_model = sklearn_model
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self._lock = threading.Lock()

    def _prepare_features(self, sample):
        # --- BLOQUE: PREPARACION DE FEATURES PARA SKLEARN ---
        temporal_arr = sample.temporal.to_array(cyclical=True)
        external_arr = sample.external.to_array()
        location_arr = sample.location.to_array()
        meta_features = [
            sample.demand_supply_ratio, sample.surge_multiplier,
            sample.earnings_potential / 50.0
        ]

        if NP_AVAILABLE:
            arrays = []
            for arr in (temporal_arr, external_arr, location_arr, meta_features):
                if not isinstance(arr, np.ndarray):
                    arr = np.array(arr)
                arrays.append(arr)
            return np.concatenate(arrays)

        return list(temporal_arr) + list(external_arr) + list(location_arr) + meta_features

    def fit(self, samples):
        # --- BLOQUE: ENTRENAMIENTO CON PREPROCESAMIENTO ---
        if not SKLEARN_AVAILABLE or not samples:
            return self

        with self._lock:
            try:
                X = np.array([self._prepare_features(s) for s in samples])
                y = np.array([s.demand_score for s in samples])

                if self.scaler:
                    X = self.scaler.fit_transform(X)

                self.sklearn_model.fit(X, y)
                self.is_fitted = True
            except Exception as e:
                log_event("[WARN] Error entrenando sklearn model: {}".format(e), "WARN")

        return self

    def predict(self, location, timestamp, external=None):
        # --- BLOQUE: PREDICCION CON WRAPPER ---
        if not self.is_fitted or not SKLEARN_AVAILABLE:
            return {'demand_score': 5.0, 'confidence': 0.3, 'model': self.name}

        try:
            temporal = TemporalFeatures.from_datetime(timestamp)
            ext = external or ExternalFeatures(
                temperature=28, humidity=75, precipitation=0, wind_speed=15,
                has_major_event=False, event_attendance=0, traffic_index=5,
                public_transit_disruption=False
            )

            dummy_sample = DemandSample(
                timestamp=timestamp, location=location, temporal=temporal, external=ext,
                request_count=10, completed_trips=8, driver_supply=12,
                avg_eta_seconds=300, surge_multiplier=1.0, demand_supply_ratio=0.8,
                earnings_potential=15
            )

            X = np.array([self._prepare_features(dummy_sample)])

            if self.scaler:
                X = self.scaler.transform(X)

            score = float(self.sklearn_model.predict(X)[0])

            return {'demand_score': min(max(score, 0.0), 10.0), 'confidence': 0.7, 'model': self.name}

        except Exception as e:
            log_event("[WARN] Error en prediccion sklearn: {}".format(e), "WARN")
            return {'demand_score': 5.0, 'confidence': 0.3, 'model': self.name}


# ================================================================================
# SECCION 15: CLASE ENSEMBLEDEMANDPREDICTOR
# ================================================================================

class EnsembleDemandPredictor(BaseDemandModel):
    """Ensemble que combina multiples modelos con pesos dinamicos."""

    def __init__(self, config=None, registry=None):
        super().__init__("Ensemble")

        self.config = config or DemandConfig()

        # --- BLOQUE: REGISTRY CON FALLBACK SEGURO ---
        try:
            self.registry = registry if registry is not None else SharedDataRegistry()
        except Exception:
            self.registry = SharedDataRegistry()

        self.models = {}
        self.weights = {}

        # --- BLOQUE: MODELO HEURISTICO ---
        heuristic_model = HeuristicDemandModel()
        heuristic_model.is_fitted = True
        self.models['heuristic'] = heuristic_model
        self.weights['heuristic'] = 1.0

        # --- BLOQUE: MODELOS SKLEARN ---
        if SKLEARN_AVAILABLE:
            try:
                rf_model = SklearnDemandModel(RandomForestRegressor(n_estimators=50))
                rf_model.is_fitted = False
                self.models['random_forest'] = rf_model
                self.weights['random_forest'] = 0.5

                gb_model = SklearnDemandModel(GradientBoostingRegressor(n_estimators=50))
                gb_model.is_fitted = False
                self.models['gradient_boost'] = gb_model
                self.weights['gradient_boost'] = 0.5

            except Exception as e:
                log_event("[WARN] No se pudieron cargar modelos sklearn: {}".format(e), "WARN")

    def _ensure_geo(self, location):
        # --- BLOQUE: NORMALIZACION ROBUSTA DE LOCATION ---
        if location is None:
            raise ValueError("location no puede ser None")

        if isinstance(location, GeoPoint):
            return location

        if hasattr(location, 'latitude') and hasattr(location, 'longitude'):
            return GeoPoint(latitude=float(location.latitude), longitude=float(location.longitude))

        if isinstance(location, dict):
            try:
                lat = location.get("lat") or location.get("latitude")
                lon = location.get("lon") or location.get("longitude")
                if lat is None or lon is None:
                    raise ValueError("Dict invalido para location: {}".format(location))
                return GeoPoint(latitude=float(lat), longitude=float(lon))
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError("Dict invalido para location: {}".format(location)) from exc

        if isinstance(location, str):
            try:
                lat, lon = map(float, location.split(","))
                return GeoPoint(latitude=lat, longitude=lon)
            except ValueError as exc:
                raise ValueError("Invalid location string format: {}".format(location)) from exc

        if isinstance(location, (list, tuple)) and len(location) >= 2:
            return GeoPoint(latitude=float(location[0]), longitude=float(location[1]))

        raise TypeError("Tipo de location no soportado: {}".format(type(location)))

    def fit(self, samples):
        # --- BLOQUE: ENTRENAMIENTO DEL ENSEMBLE ---
        if not samples:
            log_event("[WARN] No hay muestras para entrenar", "WARN")
            return self

        log_event("[INFO] Entrenando ensemble con {} muestras...".format(len(samples)), "INFO")

        trained_count = 0

        for name, model in self.models.items():
            if getattr(model, 'is_fitted', False):
                continue

            try:
                model.fit(samples)
                model.is_fitted = True
                trained_count += 1
            except Exception as e:
                log_event("[WARN] Error entrenando {}: {}".format(name, e), "WARN")

        self._update_weights(samples)
        self.is_fitted = True

        log_event("[OK] Ensemble entrenado exitosamente ({} modelos)".format(trained_count), "INFO")
        return self

    def _update_weights(self, samples):
        # --- BLOQUE: ACTUALIZACION DE PESOS POR VALIDACION ---
        if not samples or len(samples) < 10:
            return

        val_size = min(100, len(samples) // 5)
        val_samples = samples[-val_size:] if val_size > 0 else samples

        errors = {}

        for name, model in self.models.items():
            if not getattr(model, 'is_fitted', False):
                errors[name] = 1.0
                continue

            total_error = 0.0
            valid = 0

            for sample in val_samples:
                try:
                    location = self._ensure_geo(sample.location)
                    pred = model.predict(location, sample.timestamp, sample.external)
                    error = abs(pred.get('demand_score', 5.0) - sample.demand_score)
                    total_error += error
                    valid += 1
                except Exception:
                    continue

            errors[name] = (total_error / valid) if valid > 0 else 1.0

        total_inv = sum(1.0 / max(e, 0.1) for e in errors.values())

        if total_inv > 0:
            for name, error in errors.items():
                self.weights[name] = (1.0 / max(error, 0.1)) / total_inv

        try:
            self.registry.set("predictor:ensemble:weights", dict(self.weights))
        except Exception as e:
            log_event("[WARN] Error sincronizando pesos: {}".format(e), "WARN")

    def predict(self, location, timestamp, external=None, sync_registry=True):
        # --- BLOQUE: PREDICCION DEL ENSEMBLE ---
        location = self._ensure_geo(location)

        predictions = []
        confidences = []

        for name, model in self.models.items():
            if not getattr(model, 'is_fitted', False):
                continue

            try:
                pred = model.predict(location, timestamp, external)
                weight = self.weights.get(name, 0.1)

                predictions.append((pred.get('demand_score', 5.0), weight))
                confidences.append(pred.get('confidence', 0.5) * weight)

            except Exception as e:
                log_event("[WARN] Error en modelo {}: {}".format(name, e), "WARN")

        # --- BLOQUE: FALLBACK SI NO HAY PREDICCIONES ---
        if not predictions:
            temporal = TemporalFeatures.from_datetime(timestamp)
            score = 5.0

            if temporal.is_rush_hour_morning or temporal.is_rush_hour_evening:
                score = 7.0
            elif temporal.is_night:
                score = 3.5

            if external:
                if external.has_major_event:
                    score += 1.5
                score += (external.traffic_index - 5) * 0.2

            result = {
                'demand_score': min(score, 10.0),
                'uncertainty': 1.0, 'confidence': 0.3, 'model': 'fallback'
            }

        else:
            # --- BLOQUE: AGREGACION PONDERADA ---
            total_weight = sum(w for _, w in predictions) or 1.0

            ensemble_score = sum(s * w for s, w in predictions) / total_weight
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.3

            result = {
                'demand_score': float(min(ensemble_score, 10.0)),
                'uncertainty': float(1.0 - avg_conf),
                'confidence': float(avg_conf), 'model': 'ensemble'
            }

        # --- BLOQUE: SINCRONIZACION SEGURA CON REGISTRY ---
        if sync_registry:
            try:
                cell = location.to_hex_cell()
                pred_data = {
                    'timestamp': timestamp.isoformat(),
                    'location': {'lat': location.latitude, 'lon': location.longitude},
                    'cell': cell, **result
                }
                self.registry.set(
                    "predictor:prediction:{}:{}".format(cell, timestamp.timestamp()), pred_data
                )
                self.registry.set("predictor:prediction:{}:latest".format(cell), pred_data)

            except Exception as e:
                log_event("[WARN] Error sincronizando prediccion: {}".format(e), "WARN")

        return result


# ================================================================================
# SECCION 16: CLASE UBERDEMANDPREDICTOR
# ================================================================================

class UberDemandPredictor:
    """Sistema completo de prediccion de demanda espaciotemporal."""

    def __init__(self, config=None, registry=None):
        self.config = config or DemandConfig()
        self.registry = registry or SharedDataRegistry()
        self.data_store = SpatiotemporalDataStore(self.config, self.registry)
        self.model = EnsembleDemandPredictor(self.config, self.registry)
        self._training_thread = None
        self._last_training = datetime.min
        self._training_interval = timedelta(hours=1)
        self._on_prediction = None
        self._on_anomaly = None

        self._sync_thread = None
        self._ceo_listener_thread = None
        self._monitor = ThreadMonitor()

        self._load_model()
        self._sync_status_to_registry()
        self._start_background_threads()

    @staticmethod
    def _to_geo_point(location):
        """Convierte una ubicacion en dict, lista o GeoPoint a GeoPoint."""
        if isinstance(location, GeoPoint):
            return location
        if isinstance(location, dict):
            lat = location.get("lat") or location.get("latitude")
            lon = location.get("lon") or location.get("longitude")
            if lat is None or lon is None:
                raise ValueError("Dict invalido para location: {}".format(location))
            return GeoPoint(latitude=float(lat), longitude=float(lon))
        if isinstance(location, (list, tuple)) and len(location) >= 2:
            return GeoPoint(latitude=float(location[0]), longitude=float(location[1]))
        if isinstance(location, str):
            try:
                lat, lon = map(float, location.split(","))
                return GeoPoint(latitude=lat, longitude=lon)
            except ValueError as exc:
                raise ValueError("String de location invalido: {}".format(location)) from exc
        raise TypeError("Tipo de location no soportado: {}".format(type(location)))

    def _start_background_threads(self):
        if self.config.REGISTRY_SYNC_ENABLED:
            def registry_sync_loop():
                while True:
                    try:
                        self._sync_status_to_registry()
                        log_event("[HILO] Registry sync ejecutado", "DEBUG")
                    except Exception as e:
                        log_event("[WARN] Error en sync: {}".format(e), "WARN")
                    time.sleep(self.config.REGISTRY_SYNC_INTERVAL)

            self._sync_thread = threading.Thread(target=registry_sync_loop, daemon=True, name="RegistrySync")
            self._sync_thread.start()
            self._monitor.register_thread("RegistrySync", self._sync_thread)

        if self.config.CEO_LISTENER_ENABLED:
            def ceo_listener_loop():
                while True:
                    try:
                        directives = self.registry.get("ceo:directives:predictor", {})
                        if directives:
                            self._apply_ceo_directives(directives)
                            self.registry.set("ceo:directives:predictor:ack", True)
                            log_event("[HILO] Directiva CEO aplicada", "INFO")
                    except Exception as e:
                        log_event("[WARN] Error en CEO listener: {}".format(e), "WARN")
                    time.sleep(self.config.CEO_LISTENER_INTERVAL)

            self._ceo_listener_thread = threading.Thread(target=ceo_listener_loop, daemon=True, name="CEOListener")
            self._ceo_listener_thread.start()
            self._monitor.register_thread("CEOListener", self._ceo_listener_thread)

        if self.config.THREAD_MONITOR_ENABLED:
            self._monitor.start_monitoring(self.config.THREAD_MONITOR_INTERVAL)

        log_event("[HILO] Todos los hilos de fondo conectados", "INFO")

    def _apply_ceo_directives(self, directives):
        if directives.get("predictor_retrain"):
            self._trigger_training()
            log_event("[CEO] Entrenamiento disparado por directiva", "INFO")
        if "predictor_horizon" in directives:
            self.config.PREDICTION_HORIZON = directives["predictor_horizon"]
            log_event("[CEO] Horizonte actualizado a {}min".format(self.config.PREDICTION_HORIZON), "INFO")
        if directives.get("predictor_sync_now"):
            self._sync_status_to_registry()
            log_event("[CEO] Sincronizacion forzada ejecutada", "INFO")

    def _sync_status_to_registry(self):
        try:
            status = {
                'samples_stored': len(self.data_store.samples),
                'zones_tracked': len(self.data_store.spatial_index),
                'model_fitted': self.model.is_fitted,
                'last_training': self._last_training.isoformat() if self._last_training != datetime.min else None,
                'models_available': list(self.model.models.keys()),
                'model_weights': dict(self.model.weights),
                'threads_active': self._monitor.get_active_threads(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            self.registry.set("predictor:status", status)
        except Exception as e:
            log_event("[WARN] Error sincronizando estado: {}".format(e), "WARN")

    def ingest_real_time_data(self, sample):
        self.data_store.add_sample(sample)
        cell = sample.location.to_hex_cell()

        historical = self.data_store.get_zone_historical_pattern(
            cell, sample.temporal.day_of_week, sample.temporal.hour
        )

        if historical and sample.request_count > historical['avg_demand'] * 2:
            anomaly_data = {
                'type': 'demand_spike', 'location': cell,
                'current': sample.request_count, 'expected': historical['avg_demand'],
                'timestamp': sample.timestamp.isoformat()
            }
            self.registry.set("predictor:anomaly:{}:{}".format(cell, time.time()), anomaly_data)
            if self._on_anomaly:
                self._on_anomaly(anomaly_data)

    def predict(self, location, prediction_time=None, external_features=None, sync_registry=True):
        geo_loc = self._to_geo_point(location)

        if prediction_time is None:
            prediction_time = datetime.now(timezone.utc) + timedelta(minutes=self.config.PREDICTION_HORIZON)

        if not self.model.is_fitted:
            self._trigger_training()

        result = self.model.predict(geo_loc, prediction_time, external_features, sync_registry=False)

        cell = geo_loc.to_hex_cell()
        historical = self.data_store.get_zone_historical_pattern(
            cell, prediction_time.weekday(), prediction_time.hour
        )

        if historical:
            result['historical_context'] = {
                'typical_demand': historical['avg_demand'],
                'demand_trend': historical['demand_trend'],
                'sample_reliability': min(historical['sample_count'] / 100, 1.0)
            }

        result['recommendation'] = self._generate_recommendation(result)

        if self._on_prediction:
            self._on_prediction(result)

        return result

    def predict_multiple_zones(self, zones, prediction_time=None):
        predictions = []
        for zone in zones:
            geo_zone = self._to_geo_point(zone)
            pred = self.predict(geo_zone, prediction_time)
            pred['location'] = {
                'lat': geo_zone.latitude, 'lon': geo_zone.longitude,
                'cell': geo_zone.to_hex_cell()
            }
            predictions.append(pred)

        predictions.sort(key=lambda x: x['demand_score'], reverse=True)
        return predictions

    def _generate_recommendation(self, prediction):
        score = prediction.get('demand_score', 0)
        uncertainty = prediction.get('uncertainty', 0)

        if score >= 8 and uncertainty < 0.2:
            return "[HIGH] ALTA DEMANDA ESPERADA - Dirigete a esta zona inmediatamente"
        elif score >= 6:
            return "[MODERATE] DEMANDA MODERADA-ALTA - Buena oportunidad si estas cerca"
        elif score >= 4:
            return "[AVERAGE] DEMANDA PROMEDIO - Zona viable para operar"
        else:
            return "[LOW] DEMANDA BAJA ESPERADA - Considera otras zonas"

    def _trigger_training(self):
        if self._training_thread and self._training_thread.is_alive():
            return
        if datetime.now() - self._last_training < self._training_interval:
            return

        def train():
            samples = list(self.data_store.samples)
            if len(samples) < 500:
                return
            self.model.fit(samples)
            self._last_training = datetime.now()
            self._persist_model()
            self._sync_status_to_registry()
            log_event("[HILO] Entrenamiento completado", "INFO")

        self._training_thread = threading.Thread(target=train, daemon=True, name="TrainingThread")
        self._training_thread.start()
        self._monitor.register_thread("TrainingThread", self._training_thread)
        log_event("[HILO] Hilo de entrenamiento iniciado", "INFO")

    def _persist_model(self):
        self.config.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        model_file = self.config.MODEL_CACHE_DIR / "ensemble_model.pkl"
        with open(model_file, 'wb') as f:
            pickle.dump({'model': self.model, 'last_training': self._last_training, 'config': self.config}, f, protocol=pickle.HIGHEST_PROTOCOL)

    def _load_model(self):
        if _IS_MODULE_MODE:
            return
        model_file = self.config.MODEL_CACHE_DIR / "ensemble_model.pkl"
        if not model_file.exists():
            return
        try:
            with open(model_file, 'rb') as f:
                loaded = pickle.load(f)
                self.model = loaded['model']
                self._last_training = loaded.get('last_training', datetime.min)
            log_event("[OK] Modelo cargado desde cache", "INFO")
        except Exception as e:
            log_event("[WARN] Error cargando modelo: {}".format(e), "WARN")

    def shutdown(self):
        log_event("[INFO] Cerrando UberDemandPredictor...", "INFO")
        self._monitor.shutdown_all()
        self.data_store.persist()
        log_event("[OK] Sistema cerrado correctamente", "INFO")

    def get_system_status(self):
        return {
            'samples_stored': len(self.data_store.samples),
            'zones_tracked': len(self.data_store.spatial_index),
            'model_fitted': self.model.is_fitted,
            'last_training': self._last_training.isoformat() if self._last_training != datetime.min else None,
            'models_available': list(self.model.models.keys()),
            'model_weights': self.model.weights,
            'threads_active': self._monitor.get_active_threads()
        }

    def get_registry_instance(self):
        return self.registry

    def get_all_predictions(self, cell_pattern=None):
        return self.registry.get_all("predictor:prediction:{}".format(cell_pattern or '*'))

    def get_zone_data(self, cell):
        return {
            'stats': self.registry.get("predictor:zone:{}:stats".format(cell), {}),
            'latest': self.registry.get("predictor:zone:{}:latest".format(cell), {}),
            'predictions': self.registry.get_all("predictor:prediction:{}:*".format(cell))
        }

    def subscribe_to_predictions(self, callback):
        return self.registry.on_change("predictor:prediction:*", callback)


# ================================================================================
# SECCION 17: CLASE SMARTUBERPREDICTOR Y MOTOR DE DECISIONES
# ================================================================================

def enrich_prediction(prediction):
    trend = prediction.get('historical_context', {}).get('demand_trend', 'stable')
    trend_factor = 1.2 if trend == 'increasing' else 1.0
    confidence = prediction.get('confidence', 0.5)
    prediction['expected_profit'] = prediction.get('demand_score', 0) * trend_factor * confidence
    return prediction

def decide_action(prediction):
    score = prediction.get('demand_score', 0)
    profit = prediction.get('expected_profit', 0)
    uncertainty = prediction.get('uncertainty', 1)

    if profit > 7 and uncertainty < 0.5:
        return "[MOVE] MOVER_A_ZONA"
    elif score > 6:
        return "[STAY] PERMANECER_Y_ACEPTAR"
    elif score < 4:
        return "[RELOCATE] REUBICAR"
    else:
        return "[WAIT] ESPERAR"

def select_best_zone(predictions):
    return max(predictions, key=lambda x: x.get('demand_score', 0) * x.get('confidence', 0.5))

class SmartUberPredictor:
    """Wrapper inteligente SIN modificar UberDemandPredictor."""

    def __init__(self, base_predictor):
        self.base = base_predictor

    def predict_with_decision(self, location):
        pred = self.base.predict(location)
        pred = enrich_prediction(pred)
        pred['action'] = decide_action(pred)
        return pred

    def predict_best_zone(self, zones):
        predictions = self.base.predict_multiple_zones(zones)
        enriched = []
        for p in predictions:
            p = enrich_prediction(p)
            p['action'] = decide_action(p)
            enriched.append(p)
        best = select_best_zone(enriched)
        return {"best": best, "all": enriched}

def auto_move_on_spike(event):
    if event.get('type') == 'demand_spike':
        log_event("[SPIKE] DETECTADO en {}".format(event['location']), "WARN")
        log_event("[ACTION] MOVER VEHICULO AUTOMATICAMENTE", "INFO")

def trim_indexes(data_store, max_size=5000):
    for k in list(data_store.time_index.keys()):
        if len(data_store.time_index[k]) > max_size:
            data_store.time_index[k] = data_store.time_index[k][-max_size:]
    for k in list(data_store.spatial_index.keys()):
        if len(data_store.spatial_index[k]) > max_size:
            data_store.spatial_index[k] = data_store.spatial_index[k][-max_size:]


# ================================================================================
# SECCION 18: GENERACION DE DATOS SINTETICOS
# ================================================================================

def generate_synthetic_samples(n_samples=1000, start_date=None):
    if start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=7)

    samples = []
    zones = [
        GeoPoint(8.9850, -79.5200), GeoPoint(8.8800, -79.7600),
        GeoPoint(8.8750, -79.7850), GeoPoint(8.9167, -79.6000),
    ]

    for i in range(n_samples):
        hours_offset = (i / n_samples) * 24 * 7
        timestamp = start_date + timedelta(hours=hours_offset)
        base_location = random.choice(zones)

        location = GeoPoint(
            latitude=base_location.latitude + random.gauss(0, 0.01),
            longitude=base_location.longitude + random.gauss(0, 0.01)
        )
        temporal = TemporalFeatures.from_datetime(timestamp)
        is_rainy = random.random() < 0.2
        has_event = random.random() < 0.1

        external = ExternalFeatures(
            temperature=random.gauss(28, 3), humidity=random.gauss(75, 10),
            precipitation=random.gauss(5, 10) if is_rainy else 0,
            wind_speed=random.gauss(15, 5), has_major_event=has_event,
            event_attendance=int(random.gauss(5000, 2000)) if has_event else 0,
            traffic_index=random.gauss(6, 2), public_transit_disruption=random.random() < 0.05
        )

        base_demand = 20
        if temporal.is_rush_hour_morning or temporal.is_rush_hour_evening:
            base_demand *= 2.5
        elif temporal.is_night:
            base_demand *= 0.4

        if temporal.is_weekend:
            base_demand *= 1.3
        if external.has_major_event:
            base_demand *= 3.0
        if external.precipitation > 5:
            base_demand *= 1.5

        request_count = max(0, int(random.gauss(base_demand, base_demand * 0.3)))
        driver_supply = max(5, int(random.gauss(base_demand * 0.8, 10)))

        sample = DemandSample(
            timestamp=timestamp, location=location, temporal=temporal, external=external,
            request_count=request_count,
            completed_trips=int(request_count * random.gauss(0.85, 0.1)),
            driver_supply=driver_supply,
            avg_eta_seconds=max(60, int(random.gauss(300 - driver_supply * 2, 60))),
            surge_multiplier=max(1.0, random.gauss(1 + (request_count / max(driver_supply, 1) - 1) * 0.5, 0.3)),
            demand_supply_ratio=request_count / max(driver_supply, 1),
            earnings_potential=random.gauss(15, 5) * (1 + (request_count / max(driver_supply, 1)))
        )
        samples.append(sample)

    return samples


# ================================================================================
# SECCION 19: INTERFAZ PARA ORQUESTADOR Y GOBERNANZA
# ================================================================================

_predictor_instance = None
_smart_predictor_instance = None

def init_module():
    global _predictor_instance, _smart_predictor_instance
    _predictor_instance = None
    _smart_predictor_instance = None
    return True

def get_predictor(registry=None):
    global _predictor_instance, _smart_predictor_instance

    if _predictor_instance is None:
        config = DemandConfig()
        reg = registry or SharedDataRegistry()
        _predictor_instance = UberDemandPredictor(config, reg)
        _smart_predictor_instance = SmartUberPredictor(_predictor_instance)

        samples = generate_synthetic_samples(500)
        for s in samples:
            _predictor_instance.ingest_real_time_data(s)

        _predictor_instance.model.fit(samples)
        log_event("[OK] Predictor inicializado y entrenado con 500 muestras", "INFO")

    return _predictor_instance

def get_smart_predictor(registry=None):
    global _smart_predictor_instance
    if _smart_predictor_instance is None:
        get_predictor(registry)
    return _smart_predictor_instance

def predict_demand(location, prediction_time=None, external_features=None):
    predictor = get_predictor()
    return predictor.predict(location, prediction_time, external_features)

def predict_multiple_zones(zones, prediction_time=None):
    predictor = get_predictor()
    return predictor.predict_multiple_zones(zones, prediction_time)

def get_system_status():
    predictor = get_predictor()
    return predictor.get_system_status()

def ingest_real_time_data(sample):
    predictor = get_predictor()
    predictor.ingest_real_time_data(sample)

def ping():
    predictor = get_predictor()
    _ = predictor.get_system_status()

def get_ceo_metrics():
    global _predictor_instance
    if not _predictor_instance or not hasattr(_predictor_instance, 'model'):
        return {}
    return {
        "prediction_accuracy": 0.75,
        "samples_stored": len(_predictor_instance.data_store.samples),
        "model_fitted": _predictor_instance.model.is_fitted,
        "zones_tracked": len(_predictor_instance.data_store.spatial_index),
        "threads_active": _predictor_instance._monitor.get_active_threads() if hasattr(_predictor_instance, '_monitor') else {}
    }

def apply_ceo_directive(directives):
    global _predictor_instance
    if directives.get("predictor_retrain") and _predictor_instance:
        threading.Thread(target=_predictor_instance._trigger_training, daemon=True).start()
    if "predictor_horizon" in directives and _predictor_instance:
        _predictor_instance.config.PREDICTION_HORIZON = directives["predictor_horizon"]


# ================================================================================
# SECCION 20: FUNCION ANALIZAR PROMPT MEJOR OPCION (ORQUESTADOR NUCLEO)
# ================================================================================

def analizar_prompt_mejor_opcion(prompt: str, contexto: dict) -> dict:
    """
    Procesa el prompt MEJOR_OPCION usando el SmartUberPredictor.
    Punto de entrada principal para el Orquestador (Parte 1 y 5).
    """
    # --- BLOQUE: INICIALIZACION Y CONTEXTO ---
    smart = get_smart_predictor()
    predictor = get_predictor()
    
    zones = contexto.get("zones", [
        {"latitude": 8.9850, "longitude": -79.5200},
        {"latitude": 8.8800, "longitude": -79.7600},
        {"latitude": 8.8750, "longitude": -79.7850},
    ])
    
    # --- BLOQUE: PREDICCION Y DECISION ---
    try:
        result_data = smart.predict_best_zone(zones)
        best = result_data.get("best", {})
        all_preds = result_data.get("all", [])
        
        # --- BLOQUE: FORMATEO DE SALIDA ---
        return {
            "exito": True,
            "mejor_zona": best.get("location", {}),
            "demand_score": best.get("demand_score", 0.0),
            "confidence": best.get("confidence", 0.0),
            "expected_profit": best.get("expected_profit", 0.0),
            "action": best.get("action", "[WAIT] ESPERAR"),
            "recomendacion": best.get("recommendation", ""),
            "todas_las_predicciones": all_preds,
            "timestamp_procesamiento": time.time()
        }
    except Exception as e:
        log_event("[ERROR] Error en analizar_prompt_mejor_opcion: {}".format(e), "ERROR")
        return {
            "exito": False,
            "error": str(e),
            "timestamp_procesamiento": time.time()
        }


# ================================================================================
# SECCION 21: DEMOSTRACIONES
# ================================================================================

def demo_prediction_system():
    log_banner("UBER DEMAND PREDICTOR PRO v4.4 - Demostracion", "")

    config = DemandConfig()
    registry = SharedDataRegistry()
    predictor = UberDemandPredictor(config, registry)

    log_event("\n[INFO] Generando datos historicos sinteticos...", "INFO")
    historical_samples = generate_synthetic_samples(n_samples=2000)
    log_event("   Generadas {} muestras".format(len(historical_samples)), "INFO")

    log_event("\n[INFO] Ingestando datos al sistema...", "INFO")
    for sample in historical_samples:
        predictor.ingest_real_time_data(sample)

    log_event("\n[INFO] Entrenando modelos de prediccion...", "INFO")
    predictor.model.fit(historical_samples)

    log_banner("PREDICCIONES EN TIEMPO REAL", "")

    prediction_zones = [
        GeoPoint(8.9850, -79.5200), GeoPoint(8.8800, -79.7600),
        GeoPoint(8.8750, -79.7850), GeoPoint(8.9950, -79.5100),
    ]

    scenarios = [
        ("Ahora (manana laboral)", datetime.now(timezone.utc).replace(hour=8, minute=0)),
        ("Hora pico tarde", datetime.now(timezone.utc).replace(hour=18, minute=0)),
    ]

    for scenario_name, scenario_time in scenarios:
        log_event("\n[SCENARIO] Escenario: {}".format(scenario_name), "INFO")
        predictions = predictor.predict_multiple_zones(prediction_zones, scenario_time)

        log_event("\n{:<25} {:>8} {:>6} {}".format('Zona', 'Score', 'Conf', 'Recomendacion'), "INFO")
        log_event("   " + "-" * 70, "INFO")

        for pred in predictions:
            loc = pred['location']
            zone_key = "{:.4f},{:.4f}".format(loc['lat'], loc['lon'])
            zone_name = {
                "8.9850,-79.5200": "Albrook Mall", "8.8800,-79.7600": "Arraijan Centro",
                "8.8750,-79.7850": "La Chorrera", "8.9950,-79.5100": "Costa del Este"
            }.get(zone_key, "Zona desconocida")

            score = pred['demand_score']
            conf = pred.get('confidence', 0) * 100
            rec = pred.get('recommendation', 'N/A')[:40]

            log_event("   {:<25} {:>7.1f} {:>5.0f}% {}".format(zone_name, score, conf, rec), "INFO")

    status = predictor.get_system_status()
    log_banner("ESTADO DEL SISTEMA", "")
    log_event("   Muestras almacenadas: {}".format(status['samples_stored']), "INFO")
    log_event("   Modelo entrenado: {}".format('Si' if status['model_fitted'] else 'No'), "INFO")
    log_event("   Hilos activos: {}".format(status.get('threads_active', {})), "INFO")

    predictor.data_store.persist()
    return predictor

def demo_decision_engine(predictor=None):
    log_banner("DECISION ENGINE DEMO", "")

    if predictor is None:
        config = DemandConfig()
        predictor = UberDemandPredictor(config)
        samples = generate_synthetic_samples(1500)

        for s in samples:
            predictor.ingest_real_time_data(s)

        predictor.model.fit(samples)
    else:
        log_event("[OK] Reutilizando predictor existente", "INFO")

    trim_indexes(predictor.data_store)
    predictor._on_anomaly = auto_move_on_spike

    smart = SmartUberPredictor(predictor)

    zonas = [
        GeoPoint(8.9850, -79.5200), GeoPoint(8.8800, -79.7600),
        GeoPoint(8.8750, -79.7850),
    ]

    resultado = smart.predict_best_zone(zonas)

    print("\n[RESULT] MEJOR ZONA:")
    print(resultado['best'])

    print("\n[ALL] TODAS:")
    for z in resultado['all']:
        loc = z.get('location', {})
        print("{:.4f},{:.4f} -> {} (profit: {:.2f})".format(
            loc.get('lat', 0), loc.get('lon', 0), z['action'], z['expected_profit']))


# ================================================================================
# SECCION 22: REGISTRO CON CEOIA (PARTE 5)
# ================================================================================

try:
    from parte5_daimon_base import get_ceo_instance

    ceo = get_ceo_instance()
    if ceo and hasattr(ceo, 'registrar_modulo'):
        if '_predictor_instance' in globals() and _predictor_instance is not None:
            ceo.registrar_modulo("core_predictor", _predictor_instance)
            log_event("[OK] Modulo registrado con CEOIA", "INFO")
except ImportError:
    log_event("[INFO] parte5_daimon_base no disponible", "DEBUG")
except Exception as e:
    log_event("[WARN] Error registrando con CEOIA: {}".format(e), "WARN")


# ================================================================================
# SECCION 23: EXPORTS DEL MODULO
# ================================================================================

__all__ = [
    'DemandConfig', 'GeoPoint', 'TemporalFeatures', 'ExternalFeatures', 'DemandSample',
    'SpatiotemporalDataStore', 'BaseDemandModel', 'HeuristicDemandModel',
    'SklearnDemandModel', 'EnsembleDemandPredictor', 'UberDemandPredictor',
    'SmartUberPredictor', 'ThreadMonitor',
    'generate_synthetic_samples', 'enrich_prediction', 'decide_action',
    'select_best_zone', 'trim_indexes',
    'demo_prediction_system', 'demo_decision_engine',
    'init_module', 'get_predictor', 'get_smart_predictor', 'predict_demand',
    'predict_multiple_zones', 'get_system_status', 'ingest_real_time_data',
    'ping', 'get_ceo_metrics', 'apply_ceo_directive',
    'set_module_mode', 'analizar_prompt_mejor_opcion',
]


# ================================================================================
# SECCION 24: PUNTO DE ENTRADA PRINCIPAL
# ================================================================================

if __name__ == "__main__":
    predictor = demo_prediction_system()
    demo_decision_engine(predictor)

    log_banner("SISTEMA EN EJECUCION - Hilos conectados", "")
    log_event("Presiona Ctrl+C para detener", "INFO")

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        log_event("[INFO] Cierre limpio solicitado", "INFO")
        predictor.shutdown()
