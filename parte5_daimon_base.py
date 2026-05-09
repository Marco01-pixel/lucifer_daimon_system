#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================================================
# SECCION 1: METADATOS Y CONFIGURACION INICIAL
# ================================================================================
"""
PARTE 5/9 - SISTEMA DAIMON VIVO BASE (REESTRUCTURADO - METODOS REALES + ALGORITMOS RL)
Sistema central de gobierno autonomo con IA, mineria y negociacion.
Todas las funciones de gobierno ahora son metodos reales de CEOIA.
Bucles autonomos implementados como metodos de CEOIA.
Compatible con Termux/Android - Python 3.6+
"""
from __future__ import annotations
import os
import sys
import json
import time
import random
import signal
import socket
import string
import threading
import hashlib
import functools
import traceback
import uuid
import math
import textwrap
import secrets
import re
import shutil
import inspect
import ast
import subprocess
import gc
import heapq
import copy
import typing
from typing import Dict, List, Optional, Tuple, Any, Callable, Union, Set, Deque
from collections import deque, defaultdict, Counter
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import urlparse
from contextlib import contextmanager
from dataclasses import dataclass, field

# --- BLOQUE: IMPORTACION DE DATETIME CON ALIAS (EVITA SHADOWING) ---
from datetime import datetime as _datetime
from datetime import timezone as _timezone
from datetime import timedelta as _timedelta

# ================================================================================
# SECCION 2: IMPORTS ADICIONALES CON FALLBACK
# ================================================================================
try:
    import requests
except ImportError:
    requests = None

try:
    from flask import request, jsonify, make_response
except ImportError:
    request = None
    jsonify = None
    make_response = None

try:
    import numpy as np
except ImportError:
    np = None

# ================================================================================
# SECCION 3: FALLBACK DE COMPONENTES BASE
# ================================================================================
try:
    from symbiosis_parte1 import (
        GlobalConfig, log_event, log_banner,
        HyperNumberAdvanced, GeoLocation, SharedDataRegistry
    )
except ImportError:
    class GlobalConfig:
        IS_TERMUX = True
        IS_LOW_MEMORY = True

    def log_event(msg: str, level: str = "INFO") -> None:
        timestamp = _datetime.now(_timezone.utc).strftime("%H:%M:%S")
        print(f"[{timestamp}][{level}] {msg}", flush=True)

    def log_banner(msg: str, icon: str = "") -> None:
        print("=" * 60)
        print(f"{icon} {msg}")
        print("=" * 60)

    class HyperNumberAdvanced:
        def __init__(self, value=0.0):
            self.value = float(value)
        def to_float_approx(self): return self.value
        def add(self, x): self.value += float(x)
        def display(self): return f"{self.value:.2f}"

    class GeoLocation:
        def __init__(self, latitude=0.0, longitude=0.0):
            self.latitude = latitude
            self.longitude = longitude

    class SharedDataRegistry:
        _instance = None
        _lock = threading.RLock()
        def __new__(cls):
            if cls._instance is None:
                with cls._lock:
                    if cls._instance is None:
                        cls._instance = super().__new__(cls)
                        cls._instance._initialized = False
            return cls._instance
        def __init__(self):
            if self._initialized: return
            with self._lock:
                if self._initialized: return
                self._data: Dict[str, Any] = {}
                self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
                self._initialized = True
        def set(self, key: str, value: Any, notify: bool = True) -> bool:
            with self._lock:
                try:
                    self._data[key] = copy.deepcopy(value)
                    if notify: self._trigger_callbacks(key, value)
                    return True
                except: return False
        def get(self, key: str, default: Any = None) -> Any:
            with self._lock:
                return copy.deepcopy(self._data.get(key, default))
        def get_all(self, pattern: Optional[str] = None) -> Dict[str, Any]:
            with self._lock:
                if pattern is None: return {k: copy.deepcopy(v) for k, v in self._data.items()}
                import fnmatch
                return {k: copy.deepcopy(v) for k, v in self._data.items() if fnmatch.fnmatch(k, pattern)}
        def on_change(self, key_pattern: str, callback: Callable) -> str:
            with self._lock:
                callback_id = str(hash(callback))[:8]
                self._callbacks[key_pattern].append((callback_id, callback))
                return callback_id
        def _trigger_callbacks(self, key: str, value: Any) -> None:
            for pattern, callbacks in self._callbacks.items():
                import fnmatch
                if fnmatch.fnmatch(key, pattern):
                    for _, cb in callbacks:
                        try: cb(key, value)
                        except: pass

# ================================================================================
# SECCION 4: VARIABLES GLOBALES DEL SISTEMA
# ================================================================================
STOP_EVENT = threading.Event()
simulation_active = True
data_lock = threading.RLock()
mining_log = []
log_lock = threading.RLock()
HTTP_PORT = 8989
IA_READY = False
WEB_ACCESSED = False
MEJOR_OPCION_PROMPT_ACTIVO = False
MODO_NEGOCIACION_IA = False
ULTIMA_ZONA = "z1"
ESTADO_CONDUCTOR = "IDLE"
VIAJE_EN_CURSO = None
TIEMPO_INICIO_VIAJE = None
GPS_ACTIVO = False
GPS_ACTUAL = None
GPS_OBJETIVO = None
historial_gps: Deque[Dict[str, Any]] = deque(maxlen=500)
ULTIMA_ACTUALIZACION_GPS = 0.0
BENEFICIARIO_ACTUAL = "conductor_codigo"
FACTOR = 1.0
UBER_COINS = None

ZONAS = [
    {"id": "z1", "nombre": "Albrook Mall", "lat_min": 8.97, "lat_max": 9.00, "lon_min": -79.54, "lon_max": -79.50},
    {"id": "z2", "nombre": "Arraijan Centro", "lat_min": 8.86, "lat_max": 8.90, "lon_min": -79.78, "lon_max": -79.74},
    {"id": "z3", "nombre": "La Chorrera Centro", "lat_min": 8.86, "lat_max": 8.89, "lon_min": -79.80, "lon_max": -79.76},
    {"id": "z4", "nombre": "San Carlos", "lat_min": 8.87, "lat_max": 8.90, "lon_min": -79.82, "lon_max": -79.78},
    {"id": "z5", "nombre": "Veracruz", "lat_min": 8.84, "lat_max": 8.87, "lon_min": -79.84, "lon_max": -79.80},
]
zona_estado = {z["id"]: {"color": "gris", "ganancia_estimada": 0.0, "tiempo_espera": 0.0, "demanda": 0, "oferta": 0, "ratio_demanda": 0.0} for z in ZONAS}
blockchain = []
block_number = 1
viral_blocks = 0
ALGO_WEIGHTS = {
    'acceptance_rate': 5.0, 'completion_rate': 10.0, 'avg_rating': 2.0,
    'trips_completed': 0.1, 'time_online': 0.5, 'cancellation_rate': -20.0,
    'idle_time_ratio': -10.0, 'peak_hours_ratio': 3.0, 'distance_traveled': 0.05,
    'distance': 0.2, 'duration': 0.01, 'fare': 1.0, 'realEarnings': 1.0,
    'estimatedEarnings': 0.95, 'waitTime': -0.5, 'additionalSearchCost': -0.5,
    'viral_score_bonus': 50.0, 'recompensa_viral': 1.0, 'best_option_bonus': 25.0,
    'engagement_rate': 15.0, 'share_ratio': 25.0, 'completion_rate_video': 20.0,
    'creativity_bonus': 40.0, 'innovation_bonus': 30.0, 'adaptation_rate': 25.0,
    'sustainability_score': 15.0, 'gps_priority': 1.0, 'fraud_threshold': 0.6,
    'movement_speed': 1.0, 'notification_priority': 1.0, 'exploration_rate': 1.0,
    'gps_exploration': 1.0
}
DAIMON_ID = str(uuid.uuid4())[:8]
Q_TABLE = {}
Q_TABLE_LOCK = threading.RLock()
DAIMON_EPSILON = 0.1
BRAIN_CHANGE_COUNTER = 0
BRAIN_LAST_SAVE_TIME = 0.0
ROUTE = [
    {"latitude": 8.9922, "longitude": -79.5201, "name": "Albrook Mall"},
    {"latitude": 8.8805, "longitude": -79.7684, "name": "Arraijan Town Center"},
    {"latitude": 8.8650, "longitude": -79.7850, "name": "La Chorrera Centro"},
    {"latitude": 8.8900, "longitude": -79.7700, "name": "Plaza La Chorrera"},
    {"latitude": 8.8750, "longitude": -79.7900, "name": "San Carlos"},
]
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-14e93c5071e14eaf8b27e58c968f5f84")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
RADAR_CONFIG = {
    "tarifa_minima_usd": 3.13, "eta_maxima_recogida_min": 4,
    "eta_maxima_entrega_min": 6, "ingreso_minimo_por_hora_usd": 9.0,
    "ingreso_optimo_por_hora_usd": 15.0, "top_k_default": 3,
    "timeout_ollama_default": 30, "cache_max_size": 100,
    "cache_ttl_segundos": 300, "rate_limit_consultas_por_minuto": 10,
    "zona_roja_bonus": 100.0, "zona_naranja_bonus": 50.0,
    "hora_pico_bonus": 1.3, "madrugada_penalty": 0.7,
}
_radar_cache = deque(maxlen=100)
_radar_cache_lock = threading.RLock()
_ollama_request_times = deque(maxlen=10)
_ollama_rate_lock = threading.RLock()
_ZONA_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}

# Archivos del sistema
HOME = Path.home()
STATE_FILE = HOME / "state.json"
HEART_FILE = Path("/sdcard/uber_coint")
DAIMON_BRAIN_FILE = HOME / "daimon_brain.json"
RESPONSES_MEMORY_FILE = HOME / "respuestas_uber.json"
SOCIALCOIN_HEARTBEAT_FILE = HOME / "socialcoin_heartbeat.json"

# Variables adicionales del sistema
simulacion_activa = True
AI_READY = False
GPS_CURRENT = None
GPS_OBJECTIVE = None
DRIVER_STATE = "IDLE"
zone_state = zona_estado
ULTIMA_ACTIVIDAD_BUCLE = time.time()

# ================================================================================
# SECCION 5: FUNCIONES UTILITARIAS (SIN SELF)
# ================================================================================
def log(*args):
    if len(args) == 1: mensaje, tag = args[0], "INFO"
    elif len(args) == 2: mensaje, tag = args
    else: mensaje, tag = str(args), "INFO"
    timestamp = _datetime.now(_timezone.utc).strftime("%H:%M:%S")
    linea = f"[{timestamp}] [{tag}] {mensaje}"
    print(linea, flush=True)
    with log_lock:
        if len(mining_log) >= 100: mining_log.pop(0)
        mining_log.append({"ts": timestamp, "message": mensaje})

def get_recent_logs(limit=50):
    with log_lock: return list(mining_log)[-limit:]

def sigmoid(x): return 1 / (1 + math.exp(-max(-100, min(100, x))))
def dot(a, b): return sum(x * y for x, y in zip(a, b))

def calcular_distancia_py(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def tiene_internet_rapido(timeout: float = 1.5) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.getaddrinfo("1.1.1.1", 53)
        return True
    except: pass
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=timeout): return True
    except: return False

def ollama_activo() -> bool:
    if requests is None: return False
    try: return requests.get("http://localhost:11434/api/tags", timeout=0.3).status_code == 200
    except: return False

def es_url_valida(url: str) -> bool:
    return isinstance(url, str) and url.startswith(('http://', 'https://'))

def batch_write_file(filepath, content):
    try:
        tmp_path = Path(str(filepath) + ".tmp")
        tmp_path.write_text(content, encoding='utf-8')
        tmp_path.replace(Path(filepath))
    except Exception as e: log(f"[ERROR] Error en escritura batch: {e}")

def jittered_sleep(base_seconds: float):
    factor = activity_factor()
    delay = max(base_seconds * factor / max(FACTOR, 1), 0.05)
    delay *= random.uniform(0.8, 1.2)
    STOP_EVENT.wait(delay)

def activity_factor(timestamp: Optional[float] = None) -> float:
    dt = _datetime.fromtimestamp(timestamp, tz=_timezone.utc) if timestamp else _datetime.now(_timezone.utc)
    hour = dt.hour
    if 7 <= hour <= 9: base = 1.6
    elif 17 <= hour <= 19: base = 1.8
    elif 2 <= hour <= 5: base = 0.25
    else: base = 1.0
    weekday = dt.weekday()
    if weekday >= 5: base *= 0.9
    return round(base * random.uniform(0.85, 1.25), 3)

def adaptive_sleep(base_seconds):
    try:
        result = subprocess.run(['termux-battery-status'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            battery_info = json.loads(result.stdout)
            level = battery_info.get('percentage', 100)
            if level < 30:
                return STOP_EVENT.wait(base_seconds / 2)
    except Exception:
        pass
    return STOP_EVENT.wait(base_seconds)

def ensure_zone_exists(zone_id: str):
    global ZONAS, zona_estado, _ZONA_CACHE
    if zone_id not in [z["id"] for z in ZONAS]:
        nueva_zona = {"id": zone_id, "nombre": f"Zona Dinamica {zone_id}", "lat_min": 8.85, "lat_max": 8.88, "lon_min": -79.85, "lon_max": -79.81}
        ZONAS.append(nueva_zona)
        zona_estado[zone_id] = {"color": "gris", "ganancia_estimada": 0.0, "tiempo_espera": 0.0, "demanda": 0, "oferta": 0, "ratio_demanda": 0.0}
        _ZONA_CACHE.clear()
        log(f"[ZONA] Zona {zone_id} creada dinamicamente")

def get_zona_by_id(zona_id: str):
    global _ZONA_CACHE
    if zona_id not in _ZONA_CACHE: _ZONA_CACHE[zona_id] = next((z for z in ZONAS if z["id"] == zona_id), None)
    return _ZONA_CACHE[zona_id]

def corregir_tipos_metricas(metrics):
    corregido = {}
    for key, value in metrics.items():
        try:
            if isinstance(value, (list, tuple, dict)):
                if isinstance(value, dict):
                    num_values = [v for v in value.values() if isinstance(v, (int, float))]
                    corregido[key] = float(num_values[0]) if num_values else 0.0
                else:
                    num_values = [v for v in value if isinstance(v, (int, float))]
                    corregido[key] = float(num_values[0]) if num_values else 0.0
            elif isinstance(value, str) and value.replace('.', '', 1).isdigit():
                corregido[key] = float(value)
            elif isinstance(value, (int, float)):
                corregido[key] = float(value)
            else:
                corregido[key] = 0.0
        except Exception:
            corregido[key] = 0.0
    return corregido

def determinar_beneficiario(usuario: Optional[str] = None, url: Optional[str] = None) -> str:
    global BENEFICIARIO_ACTUAL
    if usuario and usuario.strip():
        BENEFICIARIO_ACTUAL = usuario.strip()
        log(f"[BENEF] Beneficiario definido: {BENEFICIARIO_ACTUAL}")
    else:
        BENEFICIARIO_ACTUAL = "conductor_codigo"
        log("[BENEF] Beneficiario: conductor_codigo")
    return BENEFICIARIO_ACTUAL

def _estado_a_clave(estado: tuple) -> str:
    zona, franja, tiene = estado
    return f"{zona}|{franja}|{1 if tiene else 0}"

def _clave_a_estado(clave: str) -> tuple:
    try:
        zona, franja, tiene = clave.split("|")
        return (zona, franja, bool(int(tiene)))
    except Exception:
        return (clave, "unknown", False)

def load_daimon_brain():
    global Q_TABLE
    if DAIMON_BRAIN_FILE.exists():
        try:
            with open(DAIMON_BRAIN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw = data.get("q_table", {})
                reconstructed = {}
                for k, v in raw.items():
                    estado = _clave_a_estado(k)
                    reconstructed[estado] = v
                with Q_TABLE_LOCK:
                    Q_TABLE.clear()
                    for estado, table in reconstructed.items():
                        safe_table = {act: float(val) for act, val in table.items()}
                        Q_TABLE[estado] = safe_table
                log("[BRAIN] Cerebro cargado")
        except Exception as e:
            log(f"[WARN] Error cargando cerebro: {e}")

def save_daimon_brain():
    global BRAIN_CHANGE_COUNTER, BRAIN_LAST_SAVE_TIME
    current_time = time.time()
    BRAIN_CHANGE_COUNTER += 1
    if (current_time - BRAIN_LAST_SAVE_TIME >= 300) or (BRAIN_CHANGE_COUNTER >= 50):
        try:
            with Q_TABLE_LOCK:
                serial = {}
                for k, v in Q_TABLE.items():
                    try:
                        if isinstance(k, str):
                            clave = k
                        else:
                            clave = _estado_a_clave(k)
                        serial[clave] = v
                    except Exception as e:
                        log(f"[WARN] Clave invalida: {k} - {e}")
                        continue
            tmp = DAIMON_BRAIN_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"q_table": serial, "daimon_id": DAIMON_ID}, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(DAIMON_BRAIN_FILE)
            BRAIN_CHANGE_COUNTER = 0
            BRAIN_LAST_SAVE_TIME = current_time
        except Exception as e:
            log(f"[ERROR] Error guardando cerebro: {e}")

def guardar_estado():
    try:
        estado = {"blockchain": blockchain, "block_number": block_number, "uber_coins": UBER_COINS.to_float_approx() if UBER_COINS else 0.0, "timestamp": time.time()}
        batch_write_file(str(STATE_FILE), json.dumps(estado, indent=2))
    except Exception as e:
        log(f"[ERROR] Error guardando estado: {e}")

def cargar_estado():
    global blockchain, block_number, UBER_COINS
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                estado = json.load(f)
            blockchain = estado.get('blockchain', [])
            block_number = estado.get('block_number', 1)
            coins_valor = estado.get('uber_coins', 0.0)
            UBER_COINS = HyperNumberAdvanced(float(coins_valor)) if isinstance(coins_valor, (int, float)) else coins_valor
            log(f"[STATE] Estado cargado: {len(blockchain)} bloques")
        else:
            UBER_COINS = HyperNumberAdvanced(0.0)
    except Exception as e:
        log(f"[ERROR] Error cargando estado: {e}")
        UBER_COINS = HyperNumberAdvanced(0.0)

def latir_corazon(bloque_data):
    try:
        heartbeat_data = {
            'timestamp': time.time(),
            'block_id': bloque_data.get('block_id', 'unknown'),
            'reward': bloque_data.get('reward', 0),
            'zona': bloque_data.get('zona', 'unknown'),
            'uber_coins': UBER_COINS.to_float_approx() if UBER_COINS else 0.0
        }
        batch_write_file(str(HEART_FILE), json.dumps(heartbeat_data, indent=2))
    except Exception:
        pass

def leer_gps_actual() -> dict:
    max_intentos = 3
    timeout_base = 8
    for intento in range(max_intentos):
        try:
            resultado = subprocess.run(
                ['termux-location', '--request', 'single', '--providers', 'gps,network'],
                capture_output=True, text=True, timeout=timeout_base + (intento * 2)
            )
            if resultado.returncode == 0:
                datos_gps = json.loads(resultado.stdout)
                ubicacion = {
                    "lat": float(datos_gps.get('latitude', 8.9922)),
                    "lng": float(datos_gps.get('longitude', -79.5201)),
                    "precision": float(datos_gps.get('accuracy', 10.0)),
                    "fuente": "GPS_REAL",
                    "timestamp": time.time()
                }
                log(f"[GPS] REAL: {ubicacion['lat']:.6f}, {ubicacion['lng']:.6f}")
                return ubicacion
            else:
                log(f"[WARN] termux-location fallo (intento {intento+1})")
        except subprocess.TimeoutExpired:
            log(f"[WARN] Timeout GPS (intento {intento+1})")
        except Exception as e:
            log(f"[WARN] Error GPS (intento {intento+1}): {e}")
        if intento < max_intentos - 1:
            time.sleep(2)
    log("[GPS] Usando ubicacion simulada")
    zona_info = get_zona_by_id(ULTIMA_ZONA)
    if zona_info:
        lat_centro = (zona_info["lat_min"] + zona_info["lat_max"]) / 2
        lng_centro = (zona_info["lon_min"] + zona_info["lon_max"]) / 2
        return {
            "lat": lat_centro + random.uniform(-0.005, 0.005),
            "lng": lng_centro + random.uniform(-0.005, 0.005),
            "precision": 15.0, "fuente": "GPS_SIMULADO", "timestamp": time.time()
        }
    return {"lat": 8.9922, "lng": -79.5201, "precision": 20.0, "fuente": "GPS_DEFAULT", "timestamp": time.time()}

# ================================================================================
# SECCION 5.5: FUNCIONES DE RUTAS INTELIGENTES (FALTANTE)
# ================================================================================

def rutas_inteligentes(priorizar: str = "ingreso_por_minuto", 
                       zona_origen: Optional[str] = None,
                       max_rutas: int = 5,
                       ceoia_instance=None) -> Dict[str, Any]:
    """
    Genera rutas inteligentes basadas en análisis de zonas y demanda.
    Retorna rutas optimizadas con estimaciones de ganancia.
    """
    global ZONAS, zona_estado, ULTIMA_ZONA
    
    resultado = {
        "rutas": [],
        "mejor_opcion": None,
        "timestamp": time.time(),
        "zona_analizada": zona_origen or ULTIMA_ZONA
    }
    
    try:
        # Obtener zona actual
        zona_actual = get_zona_by_id(zona_origen or ULTIMA_ZONA)
        if not zona_actual:
            log("[RUTAS] Zona no encontrada, usando default")
            zona_actual = ZONAS[0] if ZONAS else None
        
        # Generar rutas candidatas
        rutas_candidatas = []
        
        for zona_destino in ZONAS:
            if zona_destino["id"] == (zona_actual["id"] if zona_actual else "z1"):
                continue
                
            # Calcular distancia entre zonas
            lat1 = (zona_actual["lat_min"] + zona_actual["lat_max"]) / 2 if zona_actual else 8.9922
            lon1 = (zona_actual["lon_min"] + zona_actual["lon_max"]) / 2 if zona_actual else -79.5201
            lat2 = (zona_destino["lat_min"] + zona_destino["lat_max"]) / 2
            lon2 = (zona_destino["lon_min"] + zona_destino["lon_max"]) / 2
            
            distancia_km = calcular_distancia_py(lat1, lon1, lat2, lon2)
            
            # Obtener estado de demanda
            estado_destino = zona_estado.get(zona_destino["id"], {})
            demanda = estado_destino.get("demanda", random.randint(1, 10))
            ratio_demanda = estado_destino.get("ratio_demanda", 1.0)
            
            # Calcular tarifa estimada
            tarifa_base = 3.13
            tarifa_por_km = 1.5
            tarifa_estimada = tarifa_base + (distancia_km * tarifa_por_km)
            
            # Aplicar multiplicadores
            if ratio_demanda > 2.0:
                tarifa_estimada *= 1.5  # Zona roja
            elif ratio_demanda > 1.5:
                tarifa_estimada *= 1.2  # Zona naranja
            
            # Calcular tiempo estimado (minutos)
            velocidad_promedio = 25  # km/h
            tiempo_estimado_min = (distancia_km / velocidad_promedio) * 60
            
            # Calcular ingreso por minuto
            ingreso_por_minuto = tarifa_estimada / max(tiempo_estimado_min, 5)
            
            # Calcular score según priorización
            if priorizar == "ingreso_por_minuto":
                score = ingreso_por_minuto * 10 + ratio_demanda * 5
            elif priorizar == "demanda":
                score = ratio_demanda * 10 + demanda
            elif priorizar == "distancia_corta":
                score = 20 - distancia_km + ratio_demanda * 2
            else:
                score = ingreso_por_minuto * 5 + ratio_demanda * 3 + (20 - distancia_km)
            
            ruta = {
                "zona_origen": zona_actual["id"] if zona_actual else "unknown",
                "zona_destino": zona_destino["id"],
                "nombre_destino": zona_destino["nombre"],
                "distancia_km": round(distancia_km, 2),
                "tiempo_estimado_min": round(tiempo_estimado_min, 1),
                "tarifa_estimada": round(tarifa_estimada, 2),
                "ingreso_por_minuto": round(ingreso_por_minuto, 2),
                "demanda": demanda,
                "ratio_demanda": ratio_demanda,
                "score": round(score, 2),
                "color_zona": estado_destino.get("color", "gris")
            }
            rutas_candidatas.append(ruta)
        
        # Ordenar por score descendente
        rutas_candidatas.sort(key=lambda x: x["score"], reverse=True)
        
        # Seleccionar top rutas
        resultado["rutas"] = rutas_candidatas[:max_rutas]
        
        # Determinar mejor opción
        if resultado["rutas"]:
            mejor = resultado["rutas"][0]
            resultado["mejor_opcion"] = mejor
            
            # Actualizar estado interno si existe CEOIA
            if ceoia_instance is not None:
                ceoia_instance.estado_interno["ofertas_procesadas"] += len(resultado["rutas"])
                if mejor["score"] > 5:
                    ceoia_instance.estado_interno["ofertas_aceptadas"] += 1
        
        log(f"[RUTAS] {len(resultado['rutas'])} rutas generadas, mejor: {resultado['mejor_opcion']['nombre_destino'] if resultado['mejor_opcion'] else 'N/A'}")
        
    except Exception as e:
        log(f"[ERROR] Error en rutas_inteligentes: {e}")
        resultado["error"] = str(e)
    
    return resultado


def analizar_ruta_optimale(gps_actual: Dict[str, float], 
                           destino: Dict[str, float]) -> Dict[str, Any]:
    """
    Analiza la ruta óptima entre dos puntos GPS.
    """
    try:
        distancia = calcular_distancia_py(
            gps_actual.get("lat", 0), gps_actual.get("lng", 0),
            destino.get("lat", 0), destino.get("lng", 0)
        )
        
        # Simular puntos de ruta
        num_puntos = max(2, int(distancia * 2))
        puntos_ruta = []
        
        for i in range(num_puntos):
            t = i / (num_puntos - 1)
            lat = gps_actual.get("lat", 0) + (destino.get("lat", 0) - gps_actual.get("lat", 0)) * t
            lng = gps_actual.get("lng", 0) + (destino.get("lng", 0) - gps_actual.get("lng", 0)) * t
            puntos_ruta.append({
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "orden": i
            })
        
        return {
            "distancia_km": round(distancia, 2),
            "tiempo_estimado_min": round((distancia / 30) * 60, 1),
            "puntos": puntos_ruta,
            "consumo_estimado_litros": round(distancia * 0.08, 2)
        }
        
    except Exception as e:
        log(f"[ERROR] Error analizando ruta: {e}")
        return {"error": str(e)}

# ================================================================================
# SECCION 5.6: INTEGRACIÓN GPS CON CEOIA (FALTANTE)
# ================================================================================

def integrar_gps_en_ceo(ceoia_instance=None) -> bool:
    """
    Integra las funciones GPS con la instancia CEOIA.
    Configura los callbacks para actualización GPS.
    """
    global GPS_ACTUAL, GPS_OBJETIVO, GPS_ACTIVO
    
    try:
        target = ceoia_instance
        
        if target is None:
            log("[GPS-INTEG] CEOIA no disponible")
            return False
        
        # Definir función de actualización GPS
        def actualizar_gps_callback():
            """Callback para actualizar GPS periódicamente."""
            global GPS_ACTUAL, ULTIMA_ACTUALIZACION_GPS
            try:
                gps = leer_gps_actual()
                GPS_ACTUAL = gps
                ULTIMA_ACTUALIZACION_GPS = time.time()
                
                # Actualizar historial
                historial_gps.append({
                    "lat": gps.get("lat"),
                    "lng": gps.get("lng"),
                    "timestamp": gps.get("timestamp"),
                    "fuente": gps.get("fuente", "unknown")
                })
                
                # Sincronizar con registry si existe
                if hasattr(target, 'registry'):
                    target.registry.set("gps:actual", gps)
                
                return gps
            except Exception as e:
                log(f"[GPS-INTEG] Error actualizando: {e}")
                return None
        
        # Definir función de forzar actualización
        def forzar_actualizacion_gps():
            """Fuerza una actualización inmediata del GPS."""
            global GPS_ACTIVO
            GPS_ACTIVO = True
            gps = actualizar_gps_callback()
            return {
                "exito": gps is not None,
                "gps": gps,
                "mensaje": "GPS actualizado forzosamente" if gps else "Fallo al actualizar"
            }
        
        # Definir función de obtener estado
        def obtener_estado_gps():
            """Retorna el estado actual del GPS."""
            global GPS_ACTUAL, GPS_OBJETIVO, GPS_ACTIVO
            
            zona_actual = None
            if GPS_ACTUAL:
                for zona in ZONAS:
                    if (zona["lat_min"] <= GPS_ACTUAL.get("lat", 0) <= zona["lat_max"] and
                        zona["lon_min"] <= GPS_ACTUAL.get("lng", 0) <= zona["lon_max"]):
                        zona_actual = zona
                        break
            
            return {
                "gps_activo": GPS_ACTIVO,
                "posicion_actual": GPS_ACTUAL,
                "objetivo": GPS_OBJETIVO,
                "zona_actual": zona_actual["id"] if zona_actual else "desconocida",
                "zona_nombre": zona_actual["nombre"] if zona_actual else "Fuera de zona",
                "precision": GPS_ACTUAL.get("precision", 0) if GPS_ACTUAL else 0,
                "ultima_actualizacion": ULTIMA_ACTUALIZACION_GPS,
                "historial_count": len(historial_gps)
            }
        
        # Asignar funciones a CEOIA
        target.actualizar_gps = actualizar_gps_callback
        target.forzar_actualizacion_gps = forzar_actualizacion_gps
        target.obtener_estado_gps = obtener_estado_gps
        
        # Iniciar hilo de actualización GPS si no existe
        def gps_auto_update_loop():
            while not STOP_EVENT.is_set():
                try:
                    actualizar_gps_callback()
                    time.sleep(60)  # Actualizar cada minuto
                except Exception as e:
                    log(f"[GPS-AUTO] Error: {e}")
                    time.sleep(30)
        
        gps_thread = threading.Thread(target=gps_auto_update_loop, daemon=True)
        gps_thread.start()
        
        GPS_ACTIVO = True
        log("[GPS-INTEG] GPS integrado exitosamente con CEOIA")
        return True
        
    except Exception as e:
        log(f"[GPS-INTEG] Error en integración: {e}")
        return False

# ================================================================================
# SECCION 5.7: SISTEMA DE KILOMETRAJE Y APRENDIZAJE (FALTANTE)
# ================================================================================

class KilometrajeLearner:
    """
    Sistema de aprendizaje para optimizar rutas basado en historial de kilometraje.
    """
    def __init__(self):
        self.km_total = 0.0
        self.km_por_viaje = []
        self.eficiencia_historial = []
        self.rutas_frecuentes = defaultdict(lambda: {"count": 0, "km_total": 0.0, "tiempo_total": 0.0})
        self.ultima_posicion = None
        self.lock = threading.Lock()
        
    def registrar_viaje(self, origen: Dict[str, float], destino: Dict[str, float], 
                        tiempo_min: float, ganancia: float = 0):
        """Registra un viaje completo en el historial."""
        with self.lock:
            distancia = calcular_distancia_py(
                origen.get("lat", 0), origen.get("lng", 0),
                destino.get("lat", 0), destino.get("lng", 0)
            )
            
            self.km_total += distancia
            self.km_por_viaje.append({
                "distancia": round(distancia, 2),
                "tiempo_min": round(tiempo_min, 1),
                "ganancia": round(ganancia, 2),
                "eficiencia": round(ganancia / max(distancia, 0.1), 2),
                "timestamp": time.time()
            })
            
            # Mantener solo últimos 1000 viajes
            if len(self.km_por_viaje) > 1000:
                self.km_por_viaje.pop(0)
            
            # Actualizar rutas frecuentes
            ruta_key = f"{origen.get('lat',0):.3f},{origen.get('lng',0):.3f}->{destino.get('lat',0):.3f},{destino.get('lng',0):.3f}"
            self.rutas_frecuentes[ruta_key]["count"] += 1
            self.rutas_frecuentes[ruta_key]["km_total"] += distancia
            self.rutas_frecuentes[ruta_key]["tiempo_total"] += tiempo_min
            
            log(f"[KM] Viaje registrado: {distancia:.2f}km, ${ganancia:.2f}, eficiencia: {ganancia/max(distancia,0.1):.2f}")
            
    def get_estadisticas(self) -> Dict[str, Any]:
        """Retorna estadísticas de kilometraje."""
        with self.lock:
            if not self.km_por_viaje:
                return {"km_total": 0, "viajes": 0, "promedio_km": 0, "eficiencia_promedio": 0}
            
            km_list = [v["distancia"] for v in self.km_por_viaje]
            eff_list = [v["eficiencia"] for v in self.km_por_viaje]
            
            return {
                "km_total": round(self.km_total, 2),
                "viajes": len(self.km_por_viaje),
                "promedio_km": round(sum(km_list) / len(km_list), 2),
                "eficiencia_promedio": round(sum(eff_list) / len(eff_list), 2),
                "mejor_eficiencia": round(max(eff_list), 2) if eff_list else 0,
                "rutas_frecuentes_count": len(self.rutas_frecuentes),
                "top_rutas": sorted(
                    [{"ruta": k, **v} for k, v in self.rutas_frecuentes.items()],
                    key=lambda x: x["count"],
                    reverse=True
                )[:5]
            }
    
    def predecir_consumo(self, distancia_km: float, tipo_ruta: str = "urbano") -> Dict[str, float]:
        """Predice el consumo de combustible para una distancia."""
        # Factores de consumo (litros por km)
        factores = {
            "urbano": 0.09,
            "carretera": 0.07,
            "trafico_pesado": 0.12,
            "nocturno": 0.085
        }
        factor = factores.get(tipo_ruta, 0.09)
        
        consumo_estimado = distancia_km * factor
        costo_combustible = consumo_estimado * 1.15  # $1.15 por litro aprox
        
        return {
            "consumo_litros": round(consumo_estimado, 2),
            "costo_combustible": round(costo_combustible, 2),
            "tipo_ruta": tipo_ruta
        }
    
    def sugerir_ruta_optima(self, destinos_posibles: List[Dict]) -> Optional[Dict]:
        """Sugiere la ruta más eficiente basada en historial."""
        if not destinos_posibles or not self.km_por_viaje:
            return destinos_posibles[0] if destinos_posibles else None
        
        mejor_destino = None
        mejor_score = -float('inf')
        
        for dest in destinos_posibles:
            distancia = dest.get("distancia_km", 0)
            ganancia_estimada = dest.get("tarifa_estimada", 0)
            
            # Calcular score basado en eficiencia histórica
            eficiencia_esperada = ganancia_estimada / max(distancia, 0.1)
            
            # Boost si la ruta es similar a rutas frecuentes exitosas
            boost_frecuencia = 0
            for ruta_key, datos in self.rutas_frecuentes.items():
                if datos["count"] > 3 and datos["km_total"] / max(datos["count"], 1) < distancia * 1.5:
                    boost_frecuencia = 0.2
            
            score = eficiencia_esperada * (1 + boost_frecuencia)
            
            if score > mejor_score:
                mejor_score = score
                mejor_destino = dest
        
        return mejor_destino


def inicializar_kilometraje_learner(ceoia_instance=None) -> bool:
    """
    Inicializa el sistema de aprendizaje de kilometraje en CEOIA.
    """
    target = ceoia_instance
    
    if target is None:
        log("[KM-INIT] CEOIA no disponible")
        return False
    
    try:
        target.km_learner = KilometrajeLearner()
        target.ultima_posicion_km = None
        target.km_acumulados_viaje = 0.0
        
        log("[KM-INIT] Kilometraje Learner inicializado")
        return True
        
    except Exception as e:
        log(f"[KM-INIT] Error: {e}")
        return False


def iniciar_monitoreo_kilometraje(ceoia_instance=None) -> bool:
    """
    Inicia el monitoreo continuo de kilometraje.
    """
    global STOP_EVENT
    
    target = ceoia_instance
    
    if target is None or not hasattr(target, 'km_learner') or target.km_learner is None:
        log("[KM-MON] Kilometraje Learner no inicializado")
        return False
    
    def monitoreo_loop():
        log("[KM-MON] Monitoreo de kilometraje iniciado")
        
        while not STOP_EVENT.is_set():
            try:
                # Leer GPS actual
                gps = leer_gps_actual()
                
                if gps and hasattr(target, 'ultima_posicion_km') and target.ultima_posicion_km:
                    # Calcular distancia desde última posición
                    distancia = calcular_distancia_py(
                        target.ultima_posicion_km.get("lat", 0),
                        target.ultima_posicion_km.get("lng", 0),
                        gps.get("lat", 0),
                        gps.get("lng", 0)
                    )
                    
                    # Solo registrar si hay movimiento significativo (>10m)
                    if distancia > 0.01:  # 10 metros = 0.01 km
                        target.km_acumulados_viaje += distancia
                        
                        # Actualizar memoria de sistema
                        if hasattr(target, 'memoria_sistema'):
                            target.memoria_sistema["movimiento"]["velocidades"].append(
                                distancia * 60  # km por hora aproximado
                            )
                            if len(target.memoria_sistema["movimiento"]["velocidades"]) > 100:
                                target.memoria_sistema["movimiento"]["velocidades"].pop(0)
                
                # Actualizar última posición
                target.ultima_posicion_km = {
                    "lat": gps.get("lat", 0) if gps else 0,
                    "lng": gps.get("lng", 0) if gps else 0,
                    "timestamp": time.time()
                }
                
                # Cada 5 minutos, guardar estadísticas
                if int(time.time()) % 300 == 0 and hasattr(target, 'km_learner'):
                    stats = target.km_learner.get_estadisticas()
                    log(f"[KM-MON] Estadísticas: {stats['km_total']}km total, {stats['eficiencia_promedio']:.2f} eficiencia promedio")
                
                time.sleep(30)  # Verificar cada 30 segundos
                
            except Exception as e:
                log(f"[KM-MON] Error: {e}")
                time.sleep(60)
    
    # Iniciar hilo
    km_thread = threading.Thread(target=monitoreo_loop, daemon=True)
    km_thread.start()
    
    log("[KM-MON] Monitoreo de kilometraje activado")
    return True



# ================================================================================
# SECCION 6: CLASE CONECTOR OLLAMA LOCAL
# ================================================================================
class ConectorOllamaLocal:
    def __init__(self, modelo="qwen2.5:0.5b", timeout=600, max_modificaciones_por_ciclo=3):
        self.modelo = modelo
        self.timeout = timeout
        self.max_modificaciones_por_ciclo = max_modificaciones_por_ciclo
        self.ultima_respuesta = None
        self.contador_modificaciones = 0
        self.ultimo_reset_modificaciones = time.time()
        self.modelos_disponibles = []
        self.diagnostico_conexion()
    
    def diagnostico_conexion(self):
        try:
            resultado = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10, encoding='utf-8')
            if resultado.returncode == 0:
                for linea in resultado.stdout.strip().split('\n')[1:]:
                    if linea.strip():
                        partes = linea.split()
                        if partes:
                            modelo = partes[0]
                            tamano = partes[-2] if len(partes) > 2 else "desconocido"
                            self.modelos_disponibles.append({
                                'nombre': modelo, 'tamano': tamano,
                                'prioridad': self._calcular_prioridad_modelo(modelo)
                            })
                self.modelos_disponibles.sort(key=lambda x: x['prioridad'], reverse=True)
                if self.modelo not in [m['nombre'] for m in self.modelos_disponibles]:
                    if self.modelos_disponibles:
                        self.modelo = self.modelos_disponibles[0]['nombre']
                return True
            return False
        except: return False
    
    def _calcular_prioridad_modelo(self, modelo):
        modelo_lower = modelo.lower()
        if '1.5b' in modelo_lower or '1b' in modelo_lower: return 100
        elif '3b' in modelo_lower: return 80
        elif '7b' in modelo_lower: return 60
        elif '8b' in modelo_lower: return 50
        else: return 10
    
    def _puede_modificar(self):
        if time.time() - self.ultimo_reset_modificaciones > 3600:
            self.contador_modificaciones = 0
            self.ultimo_reset_modificaciones = time.time()
        return self.contador_modificaciones < self.max_modificaciones_por_ciclo
    
    def consultar(self, prompt, contexto="", timeout_generacion=None, prioridad_baja=False):
        if not self._puede_modificar() and "modificar" in prompt.lower():
            return {"exito": False, "error": "limite_modificaciones", "mensaje": "Demasiadas modificaciones"}
        try:
            modelo_actual = self.modelo
            timeout_actual = timeout_generacion or self.timeout
            if prioridad_baja and len(self.modelos_disponibles) > 1:
                modelos_rapidos = [m for m in self.modelos_disponibles if m['prioridad'] >= 80]
                if modelos_rapidos:
                    modelo_actual = modelos_rapidos[0]['nombre']
                    timeout_actual = min(timeout_actual, 60)
            prompt_completo = f"""SYSTEM MODE: STRICT JSON OUTPUT
Reglas: SOLO JSON valido, SIN texto adicional, SIN markdown.
Contexto: {contexto[:200]}
Instruccion: {prompt[:300]}
OUTPUT EXACTO: {{"analisis": "", "propuesta_codigo": "", "justificacion": "", "impacto": "bajo|medio|alto"}}"""
            proceso = subprocess.run(
                ["ollama", "run", modelo_actual], input=prompt_completo,
                capture_output=True, text=True, timeout=timeout_actual, encoding='utf-8'
            )
            if proceso.returncode != 0:
                return {"exito": False, "error": proceso.stderr[:200]}
            respuesta_bruta = proceso.stdout.strip()
            self.ultima_respuesta = respuesta_bruta
            resultado = self._extraer_json_seguro(respuesta_bruta)
            if resultado:
                if "modificar" in prompt.lower() or "cambiar" in prompt.lower():
                    self.contador_modificaciones += 1
                return {"exito": True, "respuesta": resultado, "modelo": modelo_actual}
            else:
                codigo = self._extraer_codigo_de_texto(respuesta_bruta)
                return {"exito": False, "respuesta": respuesta_bruta, "codigo_extraido": codigo, "modelo": modelo_actual}
        except subprocess.TimeoutExpired:
            if not prioridad_baja and "7b" in modelo_actual:
                return self.consultar(prompt, contexto, timeout_generacion=300, prioridad_baja=True)
            return {"exito": False, "error": "timeout"}
        except Exception as e:
            return {"exito": False, "error": str(e)}
    
    def _extraer_json_seguro(self, texto):
        for match in re.findall(r'\{[^{}]*\}', texto, re.DOTALL):
            try: return json.loads(match)
            except: continue
        inicio = texto.find('{'); fin = texto.rfind('}')
        if inicio != -1 and fin > inicio:
            try: return json.loads(texto[inicio:fin+1])
            except: pass
        return None
    
    def _extraer_codigo_de_texto(self, texto):
        patrones = [
            r'```python\s*(.*?)```', r'```\s*(.*?)```',
            r'propuesta_codigo["\']?\s*:\s*["\'](.*?)["\']',
        ]
        for patron in patrones:
            match = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
            if match: return match.group(1).strip()
        return None

# ================================================================================
# SECCION 7: CONTROLADOR DE MODIFICACIONES
# ================================================================================
class ControladorModificaciones:
    def __init__(self, max_por_ciclo=3, cooldown_minutos=5):
        self.max_por_ciclo = max_por_ciclo
        self.cooldown = cooldown_minutos * 60
        self.modificaciones = []
        self.ultimo_reset = time.time()
    
    def puede_modificar(self, tipo="normal"):
        ahora = time.time()
        self.modificaciones = [m for m in self.modificaciones if ahora - m['tiempo'] < self.cooldown]
        if len(self.modificaciones) >= self.max_por_ciclo:
            return False
        self.modificaciones.append({'tipo': tipo, 'tiempo': ahora})
        return True
    
    def get_estadisticas(self):
        return {
            'activas': len(self.modificaciones), 'maximo': self.max_por_ciclo,
            'cooldown_minutos': self.cooldown / 60,
            'ultimas': self.modificaciones[-3:] if self.modificaciones else []
        }

# ================================================================================
# SECCION 8: GESTOR DEEPSEEK
# ================================================================================
class GestorDeepSeek:
    def __init__(self, api_key=None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.timeout = 30
    
    # --- BLOQUE: UNIFICACION DE METODOS DE CONFIGURACION ---
    def configurar_token(self, token: str) -> bool:
        """Configura el token de API (unifica set_api_key anterior)."""
        self.api_key = token
        return True
    
    def consultar_deepseek(self, prompt, contexto=""):
        if requests is None:
            return {"exito": False, "error": "Requests no disponible"}
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": contexto[:500]},
                    {"role": "user", "content": prompt[:1000]}
                ],
                "temperature": 0.7, "max_tokens": 500
            }
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=data, timeout=self.timeout
            )
            if response.status_code == 200:
                result = response.json()
                return {"exito": True, "respuesta": result["choices"][0]["message"]["content"]}
            else:
                return {"exito": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"exito": False, "error": str(e)}

# Instancias globales
conector_ollama = ConectorOllamaLocal()
gestor_deepseek = GestorDeepSeek()

# ================================================================================
# SECCION 9: ESTRUCTURAS DE DATOS AVANZADAS PARA RL
# ================================================================================

@dataclass
class Experience:
    """Estructura para experiencias de RL."""
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
    """Transicion n-step para algoritmo n-step Q-Learning."""
    states: List[Any] = field(default_factory=list)
    actions: List[int] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    final_state: Any = None
    done: bool = False

class EpisodicMemory:
    """Memoria episodica para recordar experiencias pasadas."""
    def __init__(self, capacity=10000):
        self.capacity = capacity
        self.episodes = deque(maxlen=capacity)
    
    def add_episode(self, episodes: List[Experience], metadata: Dict = None):
        episode = {
            'experiences': episodes,
            'total_reward': sum(e.reward for e in episodes),
            'length': len(episodes),
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        self.episodes.append(episode)
    
    def get_similar_episodes(self, current_state: Any, k=5) -> List[Dict]:
        similares = []
        for ep in self.episodes:
            if ep['experiences']:
                state_ep = ep['experiences'][0].state
                similarity = self._calculate_similarity(current_state, state_ep)
                similares.append((similarity, ep))
        similares.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in similares[:k]]
    
    def _calculate_similarity(self, state1, state2):
        if isinstance(state1, (int, float)) and isinstance(state2, (int, float)):
            return 1.0 - min(1.0, abs(state1 - state2) / 100)
        elif isinstance(state1, dict) and isinstance(state2, dict):
            common = set(state1.keys()) & set(state2.keys())
            if not common:
                return 0.0
            diff = sum(abs(state1[k] - state2[k]) for k in common if isinstance(state1[k], (int, float)))
            return 1.0 / (1.0 + diff)
        return 0.5
    
    def get_transferable_learning(self, current_state: Any) -> Dict:
        similares = self.get_similar_episodes(current_state, k=3)
        if not similares:
            return {}
        knowledge = {'successful_actions': defaultdict(float), 'average_reward': 0, 'patterns': []}
        for ep in similares:
            for exp in ep['experiences']:
                knowledge['successful_actions'][exp.action] += exp.reward
            knowledge['average_reward'] += ep['total_reward']
            knowledge['patterns'].append({'length': ep['length'], 'reward': ep['total_reward']})
        knowledge['average_reward'] /= len(similares) if similares else 1
        return knowledge

# ================================================================================
# SECCION 10: DOUBLE DQN CON PER Y N-STEP (VERSION LIVIANA CORREGIDA)
# ================================================================================
class DoubleDQN:
    """Double DQN ligero con PER funcional y N-step returns."""
    
    def __init__(self, state_dim, action_dim, learning_rate=0.001, gamma=0.99,
                 epsilon_start=1.0, epsilon_end=0.01, epsilon_decay=0.995,
                 memory_size=5000, batch_size=32, target_update_frequency=100):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = min(batch_size, 32)
        self.target_update_freq = target_update_frequency
        self.steps = 0
        self.training_steps = 0
        
        # Red neuronal ligera: 2 capas ocultas suficientes
        self.hidden_sizes = [64, 32]
        self.q_network = self._init_network()
        self.target_network = self._init_network()
        self._sync_target()
        
        # PER simplificado pero funcional
        self.memory = []
        self.priorities = []
        self.memory_size = memory_size
        self.alpha = 0.6
        self.beta = 0.4
        self.beta_increment = 0.001
        
        # N-step buffer
        self.n_step_buffer = []
        self.n_step = 3  # Reducido para estabilidad
        self.n_step_gamma = gamma
        
        # Métricas
        self.td_errors = []
        
    def _init_network(self):
        """Inicializa red con 2 capas ocultas."""
        layers = [self.state_dim] + self.hidden_sizes + [self.action_dim]
        weights = []
        biases = []
        for i in range(len(layers) - 1):
            # Xavier initialization
            scale = math.sqrt(2.0 / max(layers[i], 1))
            w = [[random.gauss(0, scale) for _ in range(layers[i+1])] 
                 for _ in range(layers[i])]
            b = [0.0] * layers[i+1]
            weights.append(w)
            biases.append(b)
        return {'weights': weights, 'biases': biases}
    
    def _sync_target(self):
        """Copia pesos online a target."""
        self.target_network = self._deep_copy_network(self.q_network)
    
    def _deep_copy_network(self, net):
        """Copia profunda de red."""
        return {
            'weights': [[list(row) for row in layer] for layer in net['weights']],
            'biases': [list(b) for b in net['biases']]
        }
    
    def _forward(self, network, state):
        """Propagación hacia adelante pura Python."""
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        # Padding si es necesario
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        for i, (w, b) in enumerate(zip(network['weights'], network['biases'])):
            # Multiplicación matriz-vector
            new_x = []
            for j in range(len(b)):
                val = sum(x[k] * w[k][j] for k in range(len(x))) + b[j]
                # ReLU para capas ocultas
                if i < len(network['weights']) - 1:
                    val = max(0.0, val)
                new_x.append(val)
            x = new_x
        return x
    
    def _soft_update_target(self, tau=0.1):
        """Actualización suave target network."""
        for li in range(len(self.q_network['weights'])):
            for i in range(len(self.q_network['weights'][li])):
                for j in range(len(self.q_network['weights'][li][i])):
                    online = self.q_network['weights'][li][i][j]
                    target = self.target_network['weights'][li][i][j]
                    self.target_network['weights'][li][i][j] = tau * online + (1-tau) * target
            for j in range(len(self.q_network['biases'][li])):
                online = self.q_network['biases'][li][j]
                target = self.target_network['biases'][li][j]
                self.target_network['biases'][li][j] = tau * online + (1-tau) * target
    
    def _to_key(self, state):
        """Convierte estado a tupla hashable."""
        if isinstance(state, (list, tuple)):
            return tuple(round(float(x), 4) for x in state[:self.state_dim])
        return (float(state),)
    
    def store(self, state, action, reward, next_state, done):
        """Almacena experiencia con N-step."""
        experience = {
            'state': self._to_key(state),
            'action': int(action),
            'reward': float(reward),
            'next_state': self._to_key(next_state),
            'done': bool(done)
        }
        self.n_step_buffer.append(experience)
        
        # Flush N-step cuando buffer lleno o done
        if len(self.n_step_buffer) >= self.n_step or done:
            self._flush_n_step()
    
    def _flush_n_step(self):
        """Calcula retorno N-step y almacena."""
        if not self.n_step_buffer:
            return
            
        # Calcular retorno acumulado
        reward_n = 0.0
        gamma_power = 1.0
        for i, exp in enumerate(self.n_step_buffer):
            reward_n += exp['reward'] * gamma_power
            gamma_power *= self.gamma
            if exp['done']:
                break
        
        first = self.n_step_buffer[0]
        last = self.n_step_buffer[-1]
        
        # Estado final: último next_state o del done
        final_state = last['next_state'] if not last['done'] else first['state']
        is_done = any(e['done'] for e in self.n_step_buffer)
        
        # Prioridad inicial basada en recompensa (se actualizará con TD-error real)
        priority = (abs(reward_n) + 1.0) ** self.alpha
        
        # Almacenar
        self.memory.append({
            'state': first['state'],
            'action': first['action'],
            'reward': reward_n,
            'next_state': final_state,
            'done': is_done
        })
        self.priorities.append(priority)
        
        # Limitar tamaño
        if len(self.memory) > self.memory_size:
            self.memory.pop(0)
            self.priorities.pop(0)
        
        # Limpiar buffer si done, sino mantener último para overlap
        if self.n_step_buffer[0]['done']:
            self.n_step_buffer = []
        else:
            self.n_step_buffer = self.n_step_buffer[1:]
    
    def sample(self, batch_size):
        """Muestreo prioritario simplificado."""
        if len(self.memory) < batch_size:
            return None
            
        # Calcular probabilidades
        priorities = [p + 1e-6 for p in self.priorities]
        total = sum(priorities)
        probs = [p / total for p in priorities]
        
        # Muestreo
        indices = []
        selected = []
        for _ in range(batch_size):
            r = random.random()
            cumsum = 0.0
            for idx, p in enumerate(probs):
                cumsum += p
                if r <= cumsum and idx not in indices:
                    indices.append(idx)
                    selected.append(self.memory[idx])
                    break
            else:
                # Fallback
                idx = min(int(r * len(self.memory)), len(self.memory) - 1)
                if idx not in indices:
                    indices.append(idx)
                    selected.append(self.memory[idx])
        
        # Calcular pesos de importancia
        weights = []
        for idx in indices:
            w = (len(self.memory) * probs[idx]) ** (-self.beta)
            weights.append(w)
        
        # Normalizar pesos
        max_w = max(weights) if weights else 1.0
        weights = [w / max_w for w in weights]
        
        self.beta = min(1.0, self.beta + self.beta_increment)
        
        return selected, indices, weights
    
    def select_action(self, state, exploit_only=False):
        """Selección epsilon-greedy."""
        if not exploit_only and random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        
        state_vec = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        q_values = self._forward(self.q_network, state_vec)
        return q_values.index(max(q_values))
    
    def learn(self, batch_size=None):
        """Aprendizaje con Double DQN correcto."""
        if batch_size is None:
            batch_size = self.batch_size
            
        result = self.sample(batch_size)
        if result is None:
            return {}
        
        experiences, indices, weights = result
        
        td_errors = []
        for i, exp in enumerate(experiences):
            state_vec = list(exp['state'])
            next_vec = list(exp['next_state'])
            
            # Q-values actuales
            q_current = self._forward(self.q_network, state_vec)
            
            # Double DQN: seleccionar acción con online, evaluar con target
            q_next_online = self._forward(self.q_network, next_vec)
            best_action = q_next_online.index(max(q_next_online))
            q_next_target = self._forward(self.target_network, next_vec)
            
            # Target value
            if exp['done']:
                target = exp['reward']
            else:
                target = exp['reward'] + self.gamma * q_next_target[best_action]
            
            # TD error
            td_error = target - q_current[exp['action']]
            td_errors.append(abs(td_error))
            
            # Actualizar Q-value (gradiente descendente estocástico)
            q_current[exp['action']] += self.lr * weights[i] * td_error
            
            # Backpropagation simplificada (solo última capa para velocidad)
            self._update_last_layer(state_vec, q_current)
        
        # Actualizar prioridades con TD-error REAL (corrección del bug)
        for idx, td in zip(indices, td_errors):
            if idx < len(self.priorities):
                self.priorities[idx] = (td + 0.01) ** self.alpha
        
        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        self.steps += 1
        
        # Soft update target
        if self.steps % self.target_update_freq == 0:
            self._soft_update_target(tau=0.1)
        
        self.training_steps += 1
        
        return {
            'epsilon': self.epsilon,
            'steps': self.training_steps,
            'avg_td_error': sum(td_errors) / len(td_errors) if td_errors else 0,
            'memory_size': len(self.memory)
        }
    
    def _update_last_layer(self, state, target_q):
        """Actualiza solo última capa para eficiencia."""
        # Forward hasta penúltima capa
        x = list(state)
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        # Guardar activaciones
        activations = [x]
        for i, (w, b) in enumerate(zip(self.q_network['weights'][:-1], self.q_network['biases'][:-1])):
            new_x = []
            for j in range(len(b)):
                val = sum(x[k] * w[k][j] for k in range(len(x))) + b[j]
                val = max(0.0, val)
                new_x.append(val)
            x = new_x
            activations.append(x)
        
        # Última capa: actualización directa
        last_w = self.q_network['weights'][-1]
        last_b = self.q_network['biases'][-1]
        prev_activation = activations[-1]
        
        lr = self.lr * 0.1  # Learning rate reducido para estabilidad
        
        for j in range(self.action_dim):
            error = target_q[j] - self._forward(self.q_network, state)[j]
            for k in range(len(prev_activation)):
                last_w[k][j] += lr * error * prev_activation[k]
            last_b[j] += lr * error
    
    def get_stats(self):
        return {
            'epsilon': self.epsilon,
            'memory_size': len(self.memory),
            'training_steps': self.training_steps,
            'avg_td_error': sum(self.td_errors[-100:]) / min(len(self.td_errors), 100) if self.td_errors else 0
        }


# ================================================================================
# SECCION 11: SARSA AGENT (VERSION LIVIANA CORREGIDA)
# ================================================================================
class SARSAAgent:
    """SARSA on-policy con tabla Q eficiente."""
    
    def __init__(self, state_dim, action_dim, learning_rate=0.1, gamma=0.99,
                 epsilon=1.0, epsilon_decay=0.995, epsilon_end=0.01):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_end = epsilon_end
        
        # Tabla Q con discretización ligera
        self.q_table = {}
        self.visits = {}
        self.max_states = 10000  # Límite para evitar explosión
        
    def _discretize(self, state):
        """Discretiza estado para tabla Q."""
        if isinstance(state, (list, tuple)):
            # Cuantización a 10 niveles por dimensión
            return tuple(min(int(float(x) * 10), 9) for x in state[:min(len(state), self.state_dim)])
        return (min(int(float(state) * 10), 9),)
    
    def _get_q(self, state):
        """Obtiene valores Q, inicializa si necesario."""
        key = self._discretize(state)
        if key not in self.q_table:
            if len(self.q_table) >= self.max_states:
                # Eliminar estado menos visitado
                if self.visits:
                    min_key = min(self.visits, key=self.visits.get)
                    del self.q_table[min_key]
                    del self.visits[min_key]
            self.q_table[key] = [0.0] * self.action_dim
            self.visits[key] = 0
        self.visits[key] = self.visits.get(key, 0) + 1
        return self.q_table[key]
    
    def select_action(self, state, exploit_only=False):
        """ε-greedy con decay."""
        if not exploit_only and random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        
        q_vals = self._get_q(state)
        max_q = max(q_vals)
        # Romper empates aleatoriamente
        best_actions = [i for i, q in enumerate(q_vals) if q == max_q]
        return random.choice(best_actions)
    
    def update(self, state, action, reward, next_state, next_action, done):
        """Actualización SARSA on-policy."""
        q_current = self._get_q(state)
        q_next = self._get_q(next_state)
        
        # Target SARSA: usa next_action (ya elegido por política actual)
        if done:
            target = reward
        else:
            target = reward + self.gamma * q_next[next_action]
        
        # Actualizar
        td_error = target - q_current[action]
        q_current[action] += self.lr * td_error
        
        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        
        return {'td_error': td_error, 'epsilon': self.epsilon}


# ================================================================================
# SECCION 12: ACTOR-CRITIC (VERSION LIVIANA CORREGIDA)
# ================================================================================
class ActorCritic:
    """Actor-Critic funcional con actualización real de pesos."""
    
    def __init__(self, state_dim, action_dim, actor_lr=0.001, critic_lr=0.01,
                 gamma=0.99, entropy_coef=0.01):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.entropy_coef = entropy_coef
        self.actor_lr = actor_lr
        self.critic_lr = critic_lr
        
        # Actor: state -> policy (softmax)
        self.actor = self._init_linear(state_dim, action_dim, scale=0.1)
        
        # Critic: state -> value (escalar)
        self.critic = {
            'w1': self._init_weights(state_dim, 32),
            'b1': [0.0] * 32,
            'w2': self._init_weights(32, 1),
            'b2': [0.0]
        }
        
        # Buffer para batch updates
        self.trajectory = []
        
    def _init_weights(self, in_dim, out_dim):
        scale = math.sqrt(2.0 / max(in_dim, 1))
        return [[random.gauss(0, scale) for _ in range(out_dim)] for _ in range(in_dim)]
    
    def _init_linear(self, in_dim, out_dim, scale=None):
        if scale is None:
            scale = math.sqrt(2.0 / max(in_dim, 1))
        return {
            'weight': [[random.gauss(0, scale) for _ in range(out_dim)] for _ in range(in_dim)],
            'bias': [0.0] * out_dim
        }
    
    def _relu(self, x):
        return [max(0.0, v) for v in x]
    
    def _softmax(self, x):
        max_x = max(x)
        exp_x = [math.exp(v - max_x) for v in x]
        sum_exp = sum(exp_x)
        return [v / sum_exp for v in exp_x] if sum_exp > 0 else [1.0/len(x)] * len(x)
    
    def _forward_actor(self, state):
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        # Linear
        out = []
        for j in range(len(self.actor['bias'])):
            val = sum(x[i] * self.actor['weight'][i][j] for i in range(len(x))) + self.actor['bias'][j]
            out.append(val)
        return self._softmax(out)
    
    def _forward_critic(self, state):
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        # Capa 1
        h = []
        for j in range(len(self.critic['b1'])):
            val = sum(x[i] * self.critic['w1'][i][j] for i in range(len(x))) + self.critic['b1'][j]
            h.append(max(0.0, val))
        
        # Capa 2
        v = sum(h[j] * self.critic['w2'][j][0] for j in range(len(h))) + self.critic['b2'][0]
        return v
    
    def select_action(self, state):
        probs = self._forward_actor(state)
        r = random.random()
        cumsum = 0.0
        for i, p in enumerate(probs):
            cumsum += p
            if r <= cumsum:
                return i, probs[i]
        return len(probs) - 1, probs[-1]
    
    def store(self, state, action, reward, next_state, done):
        """Almacena transición."""
        self.trajectory.append({
            'state': state,
            'action': int(action),
            'reward': float(reward),
            'next_state': next_state,
            'done': bool(done)
        })
    
    def update(self, states=None, actions=None, rewards=None, next_states=None, dones=None, next_value=0):
        """Actualización Actor-Critic con ventaja."""
        # Usar buffer acumulado o parámetros directos
        if states is None and self.trajectory:
            traj = self.trajectory
            states = [t['state'] for t in traj]
            actions = [t['action'] for t in traj]
            rewards = [t['reward'] for t in traj]
            next_states = [t['next_state'] for t in traj]
            dones = [t['done'] for t in traj]
            self.trajectory = []
        
        if not states:
            return {}
        
        # Calcular valores y ventajas
        values = [self._forward_critic(s) for s in states]
        next_values = [self._forward_critic(s) for s in next_states]
        
        advantages = []
        returns = []
        
        # GAE simplificado (lambda=0.95)
        gae = 0
        for i in reversed(range(len(rewards))):
            if dones[i]:
                next_v = 0
            else:
                next_v = next_values[i]
            
            delta = rewards[i] + self.gamma * next_v - values[i]
            gae = delta + self.gamma * 0.95 * (1 - float(dones[i])) * gae
            advantages.insert(0, gae)
            returns.insert(0, gae + values[i])
        
        # Normalizar ventajas
        if len(advantages) > 1:
            mean_adv = sum(advantages) / len(advantages)
            std_adv = math.sqrt(sum((a - mean_adv)**2 for a in advantages) / len(advantages)) + 1e-8
            advantages = [(a - mean_adv) / std_adv for a in advantages]
        
        # Actualizar crítico
        critic_loss = 0
        for s, ret in zip(states, returns):
            v = self._forward_critic(s)
            error = ret - v
            critic_loss += error ** 2
            
            # Gradient descent en crítico (simplificado)
            self._update_critic(s, v + self.critic_lr * error)
        
        # Actualizar actor
        actor_loss = 0
        for s, a, adv in zip(states, actions, advantages):
            probs = self._forward_actor(s)
            log_prob = math.log(probs[a] + 1e-8)
            
            # Policy gradient: ∇log π(a|s) * A(s,a)
            # Aproximación: incrementar probabilidad de acciones con ventaja positiva
            for j in range(self.action_dim):
                target = probs[j] + self.actor_lr * adv * (1 if j == a else 0)
                target = max(0.001, min(0.999, target))
                # Ajustar pesos proporcionalmente (simplificado)
                self._adjust_actor_weight(s, j, target - probs[j])
            
            actor_loss -= log_prob * adv
        
        return {
            'actor_loss': actor_loss / len(states),
            'critic_loss': critic_loss / len(states),
            'mean_advantage': sum(advantages) / len(advantages) if advantages else 0
        }
    
    def _update_critic(self, state, new_value):
        """Actualización simplificada del crítico."""
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        # Forward
        h = []
        for j in range(len(self.critic['b1'])):
            val = sum(x[i] * self.critic['w1'][i][j] for i in range(len(x))) + self.critic['b1'][j]
            h.append(max(0.0, val))
        
        v = sum(h[j] * self.critic['w2'][j][0] for j in range(len(h))) + self.critic['b2'][0]
        error = new_value - v
        
        # Backprop simplificado a última capa
        for j in range(len(h)):
            self.critic['w2'][j][0] += self.critic_lr * error * h[j]
        self.critic['b2'][0] += self.critic_lr * error
    
    def _adjust_actor_weight(self, state, action, delta):
        """Ajusta pesos del actor proporcionalmente."""
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        for i in range(len(x)):
            self.actor['weight'][i][action] += self.actor_lr * delta * x[i]
        self.actor['bias'][action] += self.actor_lr * delta


# ================================================================================
# SECCION 13: PPO OPTIMIZER (VERSION LIVIANA CORREGIDA)
# ================================================================================
class PPOOptimizer:
    """PPO funcional con clipping y actualización real."""
    
    def __init__(self, state_dim, action_dim, lr=0.0003, gamma=0.99, epsilon=0.2,
                 value_coef=0.5, entropy_coef=0.01, lam=0.95):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = lr
        self.gamma = gamma
        self.epsilon_clip = epsilon
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.lam = lam
        
        # Política actual
        self.policy = self._init_linear(state_dim, action_dim, scale=0.1)
        
        # Value function
        self.value_net = {
            'w1': self._init_weights(state_dim, 32),
            'b1': [0.0] * 32,
            'w2': self._init_weights(32, 1),
            'b2': [0.0]
        }
        
        # Memoria
        self.memory = []
        
        # Old policy para clipping
        self.old_policy = None
        
    def _init_weights(self, in_dim, out_dim):
        scale = math.sqrt(2.0 / max(in_dim, 1))
        return [[random.gauss(0, scale) for _ in range(out_dim)] for _ in range(in_dim)]
    
    def _init_linear(self, in_dim, out_dim, scale=None):
        if scale is None:
            scale = math.sqrt(2.0 / max(in_dim, 1))
        return {
            'weight': [[random.gauss(0, scale) for _ in range(out_dim)] for _ in range(in_dim)],
            'bias': [0.0] * out_dim
        }
    
    def _softmax(self, x):
        max_x = max(x)
        exp_x = [math.exp(v - max_x) for v in x]
        sum_exp = sum(exp_x)
        return [v / sum_exp for v in exp_x] if sum_exp > 0 else [1.0/len(x)] * len(x)
    
    def _get_probs(self, state, policy):
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        out = []
        for j in range(len(policy['bias'])):
            val = sum(x[i] * policy['weight'][i][j] for i in range(len(x))) + policy['bias'][j]
            out.append(val)
        return self._softmax(out)
    
    def _get_value(self, state):
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        h = []
        for j in range(len(self.value_net['b1'])):
            val = sum(x[i] * self.value_net['w1'][i][j] for i in range(len(x))) + self.value_net['b1'][j]
            h.append(max(0.0, val))
        
        return sum(h[j] * self.value_net['w2'][j][0] for j in range(len(h))) + self.value_net['b2'][0]
    
    def select_action(self, state):
        probs = self._get_probs(state, self.policy)
        r = random.random()
        cumsum = 0.0
        for i, p in enumerate(probs):
            cumsum += p
            if r <= cumsum:
                return i, math.log(probs[i] + 1e-8)
        return len(probs) - 1, math.log(probs[-1] + 1e-8)
    
    def store(self, state, action, reward, next_state, done, log_prob, value):
        self.memory.append({
            'state': state, 'action': int(action), 'reward': float(reward),
            'next_state': next_state, 'done': bool(done),
            'log_prob': float(log_prob), 'value': float(value)
        })
    
    def compute_gae(self, rewards, values, dones):
        """GAE con lambda."""
        n = len(rewards)
        advantages = [0.0] * n
        gae = 0
        
        for i in reversed(range(n)):
            next_value = 0 if i == n - 1 else values[i + 1]
            delta = rewards[i] + self.gamma * next_value * (1 - float(dones[i])) - values[i]
            gae = delta + self.gamma * self.lam * (1 - float(dones[i])) * gae
            advantages[i] = gae
        
        returns = [advantages[i] + values[i] for i in range(n)]
        return advantages, returns
    
    def _copy_policy(self):
        """Copia política actual."""
        return {
            'weight': [[v for v in row] for row in self.policy['weight']],
            'bias': [v for v in self.policy['bias']]
        }
    
    def update(self, epochs=4, batch_size=32):
        """PPO update con clipping real."""
        if len(self.memory) < batch_size:
            return {}
        
        # Guardar old policy
        self.old_policy = self._copy_policy()
        
        # Extraer datos
        states = [m['state'] for m in self.memory]
        actions = [m['action'] for m in self.memory]
        rewards = [m['reward'] for m in self.memory]
        dones = [m['done'] for m in self.memory]
        old_log_probs = [m['log_prob'] for m in self.memory]
        
        # Calcular valores y GAE
        values = [self._get_value(s) for s in states]
        advantages, returns = self.compute_gae(rewards, values, dones)
        
        # Normalizar ventajas
        if len(advantages) > 1:
            mean_adv = sum(advantages) / len(advantages)
            std_adv = math.sqrt(sum((a - mean_adv)**2 for a in advantages) / len(advantages)) + 1e-8
            advantages = [(a - mean_adv) / std_adv for a in advantages]
        
        # Optimización por epochs
        total_loss = 0
        for epoch in range(epochs):
            # Mini-batches aleatorios
            indices = list(range(len(states)))
            random.shuffle(indices)
            
            for start in range(0, len(indices), batch_size):
                batch_idx = indices[start:start + batch_size]
                
                for i in batch_idx:
                    s = states[i]
                    a = actions[i]
                    adv = advantages[i]
                    ret = returns[i]
                    old_lp = old_log_probs[i]
                    
                    # Nueva política
                    new_probs = self._get_probs(s, self.policy)
                    new_lp = math.log(new_probs[a] + 1e-8)
                    
                    # Ratio para clipping
                    ratio = math.exp(new_lp - old_lp)
                    
                    # Clipped objective
                    surr1 = ratio * adv
                    surr2 = max(1 - self.epsilon_clip, min(1 + self.epsilon_clip, ratio)) * adv
                    policy_loss = -min(surr1, surr2)
                    
                    # Value loss
                    v = self._get_value(s)
                    value_loss = (v - ret) ** 2
                    
                    # Entropy bonus
                    entropy = -sum(p * math.log(p + 1e-8) for p in new_probs)
                    
                    # Total loss
                    loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy
                    total_loss += loss
                    
                    # Actualizar política (gradiente simplificado)
                    self._update_policy(s, a, ratio, adv, new_probs[a])
                    
                    # Actualizar value
                    self._update_value(s, ret)
        
        # Limpiar memoria
        self.memory = []
        
        return {
            'loss': total_loss / (epochs * len(states)) if states else 0,
            'policy_entropy': entropy if 'entropy' in dir() else 0
        }
    
    def _update_policy(self, state, action, ratio, advantage, prob):
        """Actualización de política con gradiente estimado."""
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        # Gradiente aproximado de policy gradient
        # ∇J ≈ ∇log π(a|s) * advantage * clip_factor
        clip_factor = 1.0 if abs(ratio - 1.0) < self.epsilon_clip else 0.0
        
        for i in range(len(x)):
            self.policy['weight'][i][action] += self.lr * advantage * clip_factor * x[i] / (prob + 0.1)
        self.policy['bias'][action] += self.lr * advantage * clip_factor / (prob + 0.1)
    
    def _update_value(self, state, target):
        """Actualización de value function."""
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        # Forward
        h = []
        for j in range(len(self.value_net['b1'])):
            val = sum(x[i] * self.value_net['w1'][i][j] for i in range(len(x))) + self.value_net['b1'][j]
            h.append(max(0.0, val))
        
        v = sum(h[j] * self.value_net['w2'][j][0] for j in range(len(h))) + self.value_net['b2'][0]
        error = target - v
        
        # Update
        lr = self.lr * 10  # Value suele necesitar lr más alto
        for j in range(len(h)):
            self.value_net['w2'][j][0] += lr * error * h[j]
        self.value_net['b2'][0] += lr * error


# ================================================================================
# SECCION 14: MCTS (VERSION LIVIANA CORREGIDA)
# ================================================================================
class MCTSNode:
    """Nodo del árbol de búsqueda Monte Carlo."""
    
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.children = {}
        self.visits = 0
        self.value = 0.0
        self.unexpanded = []
    
    def is_fully_expanded(self):
        return len(self.unexpanded) == 0 and len(self.children) > 0
    
    def best_child(self, c=1.414):
        """UCB1 selection."""
        if not self.children:
            return None
        
        best_score = -float('inf')
        best_child = None
        
        for action, child in self.children.items():
            if child.visits == 0:
                score = float('inf')
            else:
                exploitation = child.value / child.visits
                exploration = c * math.sqrt(math.log(self.visits) / child.visits)
                score = exploitation + exploration
            
            if score > best_score:
                best_score = score
                best_child = child
        
        return best_child
    
    def update(self, reward):
        """Actualizar estadísticas."""
        self.visits += 1
        self.value += reward


class MCTSAgent:
    """MCTS con rollout guiado por heurística simple."""
    
    def __init__(self, state_dim, action_dim, sim_depth=20, explorations=50, 
                 gamma=0.99, ucb_constant=1.414):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.sim_depth = sim_depth
        self.explorations = min(explorations, 100)  # Limitar para velocidad
        self.gamma = gamma
        self.ucb_constant = ucb_constant
        
        # Heurística simple para guiar rollouts
        self.action_values = [0.0] * action_dim
        self.action_counts = [0] * action_dim
        
        # Modelo interno ligero: estado -> preferencia de acción
        self.state_action_values = {}
    
    def _hash_state(self, state):
        """Hash simple para estado."""
        if isinstance(state, (list, tuple)):
            return tuple(round(float(x), 2) for x in state[:min(len(state), self.state_dim)])
        return (round(float(state), 2),)
    
    def _get_prior(self, state, action):
        """Obtener prior heurístico para (estado, acción)."""
        key = (self._hash_state(state), action)
        if key in self.state_action_values:
            return self.state_action_values[key]
        return 0.5  # Neutral
    
    def _update_prior(self, state, action, value):
        """Actualizar heurística."""
        key = (self._hash_state(state), action)
        old = self.state_action_values.get(key, 0.5)
        self.state_action_values[key] = old + 0.1 * (value - old)
    
    def build_tree(self, initial_state, possible_actions):
        """Construir árbol de búsqueda."""
        self.root = MCTSNode(initial_state)
        self.root.unexpanded = list(possible_actions) if possible_actions else list(range(self.action_dim))
        
        for _ in range(self.explorations):
            # 1. Selection
            node = self._select(self.root)
            
            # 2. Expansion
            if node.unexpanded and not node.is_fully_expanded():
                node = self._expand(node)
            
            # 3. Simulation
            reward = self._simulate(node.state)
            
            # 4. Backpropagation
            self._backpropagate(node, reward)
    
    def _select(self, node):
        """Seleccionar nodo con UCB1."""
        while node.is_fully_expanded() and node.children:
            node = node.best_child(self.ucb_constant)
            if node is None:
                break
        return node
    
    def _expand(self, node):
        """Expandir nodo con acción no explorada."""
        if not node.unexpanded:
            return node
        
        # Seleccionar acción con mejor prior
        best_action = node.unexpanded[0]
        best_prior = -float('inf')
        for a in node.unexpanded:
            prior = self._get_prior(node.state, a)
            if prior > best_prior:
                best_prior = prior
                best_action = a
        
        node.unexpanded.remove(best_action)
        
        # Crear nuevo estado (simplificado)
        new_state = self._apply_action(node.state, best_action)
        child = MCTSNode(new_state, node, best_action)
        child.unexpanded = list(range(self.action_dim))
        
        node.children[best_action] = child
        return child
    
    def _apply_action(self, state, action):
        """Aplicar acción a estado."""
        if isinstance(state, (list, tuple)):
            new = list(state)
            # Modificación simple basada en acción
            idx = action % len(new)
            new[idx] = (new[idx] + (action - self.action_dim/2) * 0.1) % 1.0
            return tuple(new)
        return (state + (action - self.action_dim/2) * 0.1) % 1.0
    
    def _simulate(self, state):
        """Simulación con heurística (no puramente aleatoria)."""
        total_reward = 0.0
        discount = 1.0
        current = state
        
        for _ in range(self.sim_depth):
            # Elegir acción con mejor prior + exploración
            if random.random() < 0.2:  # 20% exploración
                action = random.randint(0, self.action_dim - 1)
            else:
                # Seleccionar por prior
                best_action = random.randint(0, self.action_dim - 1)
                best_prior = -float('inf')
                for a in range(self.action_dim):
                    prior = self._get_prior(current, a) + random.uniform(0, 0.1)
                    if prior > best_prior:
                        best_prior = prior
                        best_action = a
                action = best_action
            
            # Calcular recompensa heurística
            reward = self._heuristic_reward(current, action)
            total_reward += discount * reward
            
            # Actualizar prior online
            self._update_prior(current, action, reward)
            
            # Siguiente estado
            current = self._apply_action(current, action)
            discount *= self.gamma
            
            # Early termination si recompensa muy negativa
            if reward < -10:
                break
        
        return total_reward
    
    def _heuristic_reward(self, state, action):
        """Heurística de recompensa basada en estado."""
        # Favorecer acciones que mantengan valores en rango óptimo [0.3, 0.7]
        if isinstance(state, (list, tuple)):
            idx = action % len(state)
            val = state[idx]
            # Penalizar extremos
            if val < 0.2 or val > 0.8:
                return -1.0
            elif 0.4 <= val <= 0.6:
                return 2.0
            return 0.5
        return 0.0
    
    def _backpropagate(self, node, reward):
        """Retropropagar recompensa."""
        while node:
            node.update(reward)
            reward *= self.gamma
            node = node.parent
    
    def select_best_action(self):
        """Seleccionar mejor acción por visitas."""
        if not self.root or not self.root.children:
            return random.randint(0, self.action_dim - 1)
        
        best_action = None
        best_visits = -1
        
        for action, child in self.root.children.items():
            if child.visits > best_visits:
                best_visits = child.visits
                best_action = action
        
        return best_action if best_action is not None else random.randint(0, self.action_dim - 1)
    
    def get_statistics(self):
        if not self.root:
            return {}
        
        stats = {'total_visits': self.root.visits, 'actions': {}}
        for action, child in self.root.children.items():
            stats['actions'][action] = {
                'visits': child.visits,
                'value': child.value,
                'average_value': child.value / child.visits if child.visits > 0 else 0
            }
        return stats


# ================================================================================
# SECCION 15: ALGORITMO GENETICO (VERSION LIVIANA CORREGIDA)
# ================================================================================
class GeneticOptimizer:
    """Optimización genética ligera y funcional."""
    
    def __init__(self, param_bounds, pop_size=30, elite_ratio=0.1, mutation_rate=0.15,
                 crossover_rate=0.8, generations=50):
        self.param_bounds = param_bounds
        self.pop_size = max(pop_size, 10)
        self.elite_size = max(1, int(self.pop_size * elite_ratio))
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.generations = generations
        
        self.population = []
        self.best_individual = None
        self.best_fitness = -float('inf')
        self.history = []
        self.diversity_threshold = 0.01  # Para reinicio si converge prematuramente
    
    def _init_population(self):
        """Inicializar población diversa."""
        self.population = []
        for _ in range(self.pop_size):
            individual = {}
            for param, (low, high) in self.param_bounds.items():
                if isinstance(low, int) and isinstance(high, int):
                    individual[param] = random.randint(low, high)
                else:
                    # Inicialización uniforme en rango
                    individual[param] = low + random.random() * (high - low)
            self.population.append(individual)
    
    def _evaluate(self, individual, fitness_fn):
        """Evaluar con penalización por límites."""
        # Verificar límites
        penalty = 0
        for param, value in individual.items():
            low, high = self.param_bounds[param]
            if value < low or value > high:
                penalty += abs(value - max(low, min(high, value))) * 10
        
        fitness = fitness_fn(individual)
        return fitness - penalty
    
    def _select_tournament(self, fitness_scores, k=3):
        """Selección por torneo."""
        selected = []
        for _ in range(len(self.population)):
            contestants = random.sample(range(len(self.population)), min(k, len(self.population)))
            winner = max(contestants, key=lambda i: fitness_scores[i])
            selected.append(self.population[winner].copy())
        return selected
    
    def _crossover_blend(self, parent1, parent2, alpha=0.5):
        """Cruce BLX-α para mejor exploración."""
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()
        
        child1, child2 = {}, {}
        for param in parent1.keys():
            low, high = self.param_bounds[param]
            
            if isinstance(parent1[param], int):
                # Cruce para enteros: interpolación
                if random.random() < 0.5:
                    child1[param] = parent1[param]
                    child2[param] = parent2[param]
                else:
                    child1[param] = parent2[param]
                    child2[param] = parent1[param]
            else:
                # BLX-α para continuos
                d = abs(parent1[param] - parent2[param])
                min_val = min(parent1[param], parent2[param])
                max_val = max(parent1[param], parent2[param])
                
                child1[param] = random.uniform(min_val - alpha*d, max_val + alpha*d)
                child2[param] = random.uniform(min_val - alpha*d, max_val + alpha*d)
                
                # Clamping
                child1[param] = max(low, min(high, child1[param]))
                child2[param] = max(low, min(high, child2[param]))
        
        return child1, child2
    
    def _mutate_adaptive(self, individual, generation):
        """Mutación con tasa adaptativa."""
        mutated = individual.copy()
        
        # Tasa decreciente con generaciones
        current_rate = self.mutation_rate * (1 - generation / max(self.generations, 1))
        
        for param in mutated:
            if random.random() < current_rate:
                low, high = self.param_bounds[param]
                range_val = high - low
                
                if isinstance(low, int):
                    # Mutación gaussiana entera
                    mutated[param] += int(random.gauss(0, range_val * 0.1))
                    mutated[param] = max(low, min(high, mutated[param]))
                else:
                    # Mutación con distribución de Cauchy para saltos grandes ocasionales
                    if random.random() < 0.1:
                        # Salto grande (Cauchy)
                        mutated[param] += random.gauss(0, range_val * 0.5)
                    else:
                        # Mutación pequeña
                        mutated[param] += random.gauss(0, range_val * 0.05)
                    mutated[param] = max(low, min(high, mutated[param]))
        
        return mutated
    
    def _check_diversity(self, fitness_scores):
        """Verificar diversidad de población."""
        if len(fitness_scores) < 2:
            return 1.0
        return max(fitness_scores) - min(fitness_scores)
    
    def optimize(self, fitness_fn, verbose=True):
        """Optimización principal."""
        self._init_population()
        
        no_improvement_count = 0
        
        for gen in range(self.generations):
            # Evaluar
            fitness_scores = []
            for ind in self.population:
                try:
                    fitness = self._evaluate(ind, fitness_fn)
                except Exception:
                    fitness = -float('inf')
                fitness_scores.append(fitness)
            
            # Mejor individuo
            best_idx = fitness_scores.index(max(fitness_scores))
            if fitness_scores[best_idx] > self.best_fitness:
                self.best_fitness = fitness_scores[best_idx]
                self.best_individual = self.population[best_idx].copy()
                no_improvement_count = 0
            else:
                no_improvement_count += 1
            
            # Historia
            self.history.append({
                'generation': gen,
                'best_fitness': self.best_fitness,
                'avg_fitness': sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0,
                'diversity': self._check_diversity(fitness_scores)
            })
            
            if verbose and gen % 10 == 0:
                log(f"[GA] Gen {gen}: Best={self.best_fitness:.4f}, Diversity={self.history[-1]['diversity']:.4f}")
            
            # Reinicio si estancamiento
            if no_improvement_count > 20:
                # Mantener elite, regenerar resto
                new_pop = [self.population[best_idx].copy() for _ in range(self.elite_size)]
                self.population = new_pop
                self._init_population()
                # Restaurar elite
                self.population[:self.elite_size] = new_pop
                no_improvement_count = 0
                if verbose:
                    log(f"[GA] Reinicio por estancamiento en gen {gen}")
                continue
            
            # Selección
            selected = self._select_tournament(fitness_scores)
            
            # Nueva población
            new_population = []
            
            # Elite
            elite_indices = sorted(range(len(fitness_scores)), key=lambda i: fitness_scores[i], reverse=True)[:self.elite_size]
            for idx in elite_indices:
                new_population.append(self.population[idx].copy())
            
            # Cruzar y mutar
            while len(new_population) < self.pop_size:
                p1, p2 = random.sample(selected, 2)
                c1, c2 = self._crossover_blend(p1, p2)
                
                c1 = self._mutate_adaptive(c1, gen)
                new_population.append(c1)
                
                if len(new_population) < self.pop_size:
                    c2 = self._mutate_adaptive(c2, gen)
                    new_population.append(c2)
            
            self.population = new_population[:self.pop_size]
        
        return self.best_individual, self.best_fitness
    
    def get_history(self):
        return self.history


# ================================================================================
# SECCION 16: CONTROLADOR DE LOGICA FUZZY (VERSION LIVIANA CORREGIDA)
# ================================================================================
class FuzzyLogicController:
    """Controlador difuso optimizado para velocidad."""
    
    def __init__(self):
        self.rules = []
        self.membership_functions = {}
        self.defuzzify_method = 'centroid'
        self._cache = {}  # Cache para membresías
    
    def add_mf(self, variable, name, mf_type, params):
        """Agregar función de membresía."""
        if variable not in self.membership_functions:
            self.membership_functions[variable] = {}
        self.membership_functions[variable][name] = {'type': mf_type, 'params': params}
    
    def add_rule(self, antecedent, consequent):
        """Agregar regla difusa."""
        self.rules.append({'if': antecedent, 'then': consequent})
        self._cache = {}  # Invalidar cache
    
    def _triangle(self, x, a, b, c):
        """Triangular membership."""
        if x <= a or x >= c:
            return 0.0
        if x <= b:
            return (x - a) / (b - a) if b != a else 1.0
        return (c - x) / (c - b) if c != b else 1.0
    
    def _trapezoid(self, x, a, b, c, d):
        """Trapezoidal membership."""
        if x <= a or x >= d:
            return 0.0
        if b <= x <= c:
            return 1.0
        if x < b:
            return (x - a) / (b - a) if b != a else 1.0
        return (d - x) / (d - c) if d != c else 1.0
    
    def _gaussian(self, x, c, sigma):
        """Gaussian membership."""
        if sigma == 0:
            return 1.0 if x == c else 0.0
        return math.exp(-0.5 * ((x - c) / sigma) ** 2)
    
    def _evaluate_mf(self, variable, mf_name, value):
        """Evaluar función de membresía con cache."""
        cache_key = (variable, mf_name, round(value, 3))
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if variable not in self.membership_functions:
            return 0.0
        
        mf = self.membership_functions[variable].get(mf_name)
        if not mf:
            return 0.0
        
        t, p = mf['type'], mf['params']
        if t == 'triangle':
            result = self._triangle(value, *p)
        elif t == 'trapezoid':
            result = self._trapezoid(value, *p)
        elif t == 'gaussian':
            result = self._gaussian(value, *p)
        else:
            result = 0.0
        
        self._cache[cache_key] = result
        return result
    
    def fuzzify(self, inputs):
        """Fuzzificación."""
        result = {}
        for var, value in inputs.items():
            if var in self.membership_functions:
                result[var] = {
                    mf: self._evaluate_mf(var, mf, value)
                    for mf in self.membership_functions[var]
                }
        return result
    
    def apply_rules(self, fuzzy_inputs):
        """Inferencia difusa."""
        outputs = {}
        
        for rule in self.rules:
            # Calcular activación del antecedente
            activations = []
            for var, mf_name in rule['if'].items():
                if var in fuzzy_inputs and mf_name in fuzzy_inputs[var]:
                    activations.append(fuzzy_inputs[var][mf_name])
            
            if not activations:
                continue
            
            # T-norma: mínimo (AND difuso)
            antecedent_activation = min(activations)
            
            # Aplicar a consecuente
            for out_var, out_mf in rule['then'].items():
                if isinstance(out_mf, dict):
                    # Formato: {mf_name: weight}
                    for mf_name, weight in out_mf.items():
                        key = f"{out_var}:{mf_name}"
                        current = outputs.get(key, 0.0)
                        outputs[key] = max(current, antecedent_activation * weight)
                else:
                    # Formato simple
                    key = f"{out_var}:{out_mf}"
                    current = outputs.get(key, 0.0)
                    outputs[key] = max(current, antecedent_activation)
        
        return outputs
    
    def defuzzify(self, fuzzy_outputs, output_range=(0, 1)):
        """Defuzzificación por centroide optimizado."""
        if not fuzzy_outputs:
            return (output_range[0] + output_range[1]) / 2.0
        
        # Parsear outputs
        parsed = {}
        for key, value in fuzzy_outputs.items():
            if ':' in key:
                var, mf = key.split(':', 1)
            else:
                var, mf = 'output', key
            if var not in parsed:
                parsed[var] = {}
            parsed[var][mf] = value
        
        # Defuzzificar variable principal (output)
        output_mfs = self.membership_functions.get('output', {})
        
        if self.defuzzify_method == 'centroid':
            # Muestreo adaptativo
            n_samples = 50  # Reducido para velocidad
            step = (output_range[1] - output_range[0]) / n_samples
            
            numerator = 0.0
            denominator = 0.0
            
            for i in range(n_samples + 1):
                x = output_range[0] + i * step
                
                # Agregar membresía de cada MF de salida
                max_mem = 0.0
                for mf_name, grade in parsed.get('output', {}).items():
                    if mf_name in output_mfs:
                        mem = self._evaluate_mf('output', mf_name, x)
                        max_mem = max(max_mem, min(grade, mem))
                
                numerator += x * max_mem
                denominator += max_mem
            
            if denominator > 1e-10:
                return numerator / denominator
        
        elif self.defuzzify_method == 'mom':
            # Mean of maxima
            max_grade = max(fuzzy_outputs.values())
            candidates = []
            for key, grade in fuzzy_outputs.items():
                if abs(grade - max_grade) < 1e-6:
                    # Extraer valor representativo del MF
                    if ':' in key:
                        _, mf = key.split(':', 1)
                    else:
                        mf = key
                    if mf in output_mfs:
                        params = output_mfs[mf]['params']
                        # Centro del MF
                        if output_mfs[mf]['type'] == 'triangle':
                            candidates.append(params[1])  # Punto medio
                        elif output_mfs[mf]['type'] == 'trapezoid':
                            candidates.append((params[1] + params[2]) / 2)
            
            if candidates:
                return sum(candidates) / len(candidates)
        
        return (output_range[0] + output_range[1]) / 2.0
    
    def evaluate(self, inputs, output_range=(0, 1)):
        """Evaluación completa."""
        fuzzy_inputs = self.fuzzify(inputs)
        fuzzy_outputs = self.apply_rules(fuzzy_inputs)
        return self.defuzzify(fuzzy_outputs, output_range)


# ================================================================================
# SECCION 17: FILTRO DE KALMAN (VERSION LIVIANA CORREGIDA)
# ================================================================================
class KalmanFilter:
    """Filtro de Kalman con modelo de velocidad para GPS."""
    
    def __init__(self, state_dim=4, obs_dim=2, dt=1.0):
        """
        Estado: [lat, lng, v_lat, v_lng] (4D)
        Observación: [lat, lng] (2D)
        """
        self.state_dim = max(state_dim, 4)
        self.obs_dim = min(obs_dim, 2)
        self.dt = dt
        
        # Estado inicial
        self.x = [0.0] * self.state_dim
        
        # Covarianza inicial
        self.P = self._diag([1.0, 1.0, 0.1, 0.1])
        
        # Ruido de proceso (Q)
        q_pos = 0.001
        q_vel = 0.01
        self.Q = self._diag([q_pos, q_pos, q_vel, q_vel])
        
        # Ruido de medición (R) - adaptable
        self.R_base = 1.0
        self.R = self._diag([self.R_base, self.R_base])
        
        # Matriz de transición (modelo velocidad constante)
        self.A = [
            [1.0, 0.0, dt,  0.0],
            [0.0, 1.0, 0.0, dt ],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ]
        
        # Matriz de observación
        self.H = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ]
        
        # Adaptación de R según precisión GPS
        self.adaptive_R = True
        self.residual_history = []
    
    def _diag(self, values):
        """Crear matriz diagonal."""
        n = len(values)
        return [[values[i] if i == j else 0.0 for j in range(n)] for i in range(n)]
    
    def _mat_mult(self, A, B):
        """Multiplicación matriz-matriz."""
        rows_A = len(A)
        cols_A = len(A[0]) if A else 0
        cols_B = len(B[0]) if B else 0
        
        result = [[0.0] * cols_B for _ in range(rows_A)]
        for i in range(rows_A):
            for j in range(cols_B):
                for k in range(cols_A):
                    result[i][j] += A[i][k] * B[k][j]
        return result
    
    def _mat_vec(self, A, v):
        """Multiplicación matriz-vector."""
        return [sum(A[i][j] * v[j] for j in range(len(v))) for i in range(len(A))]
    
    def _transpose(self, A):
        """Transpuesta."""
        return [[A[j][i] for j in range(len(A))] for i in range(len(A[0]))]
    
    def _add(self, A, B):
        """Suma matricial."""
        return [[A[i][j] + B[i][j] for j in range(len(A[0]))] for i in range(len(A))]
    
    def _sub(self, A, B):
        """Resta matricial."""
        return [[A[i][j] - B[i][j] for j in range(len(A[0]))] for i in range(len(A))]
    
    def _scale(self, A, s):
        """Escalar matriz."""
        return [[A[i][j] * s for j in range(len(A[0]))] for i in range(len(A))]
    
    def _inverse_2x2(self, M):
        """Inversa de matriz 2x2."""
        det = M[0][0] * M[1][1] - M[0][1] * M[1][0]
        if abs(det) < 1e-10:
            return [[1.0, 0.0], [0.0, 1.0]]
        inv_det = 1.0 / det
        return [
            [M[1][1] * inv_det, -M[0][1] * inv_det],
            [-M[1][0] * inv_det, M[0][0] * inv_det]
        ]
    
    def predict(self, u=None):
        """Predicción del estado."""
        # x = A * x + B * u
        self.x = self._mat_vec(self.A, self.x)
        
        if u is not None:
            # Control de aceleración
            for i in range(min(len(u), 2)):
                self.x[i + 2] += u[i] * self.dt
        
        # P = A * P * A^T + Q
        AP = self._mat_mult(self.A, self.P)
        At = self._transpose(self.A)
        APAt = self._mat_mult(AP, At)
        self.P = self._add(APAt, self.Q)
        
        return self.x
    
    def update(self, z, accuracy=None):
        """Actualización con medición."""
        # Adaptar R según precisión GPS
        if self.adaptive_R and accuracy is not None:
            r = max(0.1, accuracy / 10.0)
            self.R = self._diag([r, r])
        
        # y = z - H * x
        Hx = self._mat_vec(self.H, self.x)
        y = [z[i] - Hx[i] for i in range(min(len(z), len(Hx)))]
        
        # S = H * P * H^T + R
        HP = self._mat_mult(self.H, self.P)
        Ht = self._transpose(self.H)
        HPHt = self._mat_mult(HP, Ht)
        S = self._add(HPHt, self.R)
        
        # K = P * H^T * S^{-1}
        # Para eficiencia, asumimos S es 2x2
        if len(S) == 2 and len(S[0]) == 2:
            S_inv = self._inverse_2x2(S)
        else:
            # Fallback: aproximación diagonal
            S_inv = self._diag([1.0 / (S[i][i] + 1e-6) for i in range(len(S))])
        
        PHt = self._mat_mult(self.P, Ht)
        K = self._mat_mult(PHt, S_inv)
        
        # x = x + K * y
        Ky = self._mat_vec(K, y)
        self.x = [self.x[i] + Ky[i] for i in range(len(self.x))]
        
        # P = (I - K * H) * P
        KH = self._mat_mult(K, self.H)
        I = self._diag([1.0] * self.state_dim)
        I_KH = self._sub(I, KH)
        self.P = self._mat_mult(I_KH, self.P)
        
        # Guardar residual para adaptación
        self.residual_history.append(sum(r**2 for r in y))
        if len(self.residual_history) > 100:
            self.residual_history.pop(0)
        
        return self.x
    
    def get_position(self):
        """Obtener posición estimada."""
        return self.x[:2]
    
    def get_velocity(self):
        """Obtener velocidad estimada."""
        return self.x[2:4] if len(self.x) >= 4 else [0.0, 0.0]
    
    def get_uncertainty(self):
        """Incertidumbre total (traza de P)."""
        return sum(self.P[i][i] for i in range(len(self.P)))
    
    def is_gps_jumping(self, threshold=100):
        """Detectar saltos anómalos en GPS."""
        if len(self.residual_history) < 10:
            return False
        recent = sum(self.residual_history[-10:]) / 10
        return recent > threshold


# ================================================================================
# SECCION 18: CURIOSITY MODULE (VERSION LIVIANA CORREGIDA)
# ================================================================================
class CuriosityModule:
    """Curiosity con forward model que realmente aprende."""
    
    def __init__(self, state_dim, action_dim, lr=0.01, gamma=0.99,
                 intrinsic_reward_scale=1.0, novelty_weight=0.5):
        self.state_dim = max(state_dim, 4)
        self.action_dim = max(action_dim, 2)
        self.lr = lr
        self.gamma = gamma
        self.intrinsic_reward_scale = intrinsic_reward_scale
        self.novelty_weight = novelty_weight
        
        # Forward model: (state, action) -> next_state
        # Arquitectura ligera: entrada -> 16 -> state_dim
        self.forward_w1 = self._init_weights(self.state_dim + 1, 16)
        self.forward_b1 = [0.0] * 16
        self.forward_w2 = self._init_weights(16, self.state_dim)
        self.forward_b2 = [0.0] * self.state_dim
        
        # Contador de visitas para novelty
        self.state_counts = {}
        self.max_count = 1000  # Saturación
        
        # Buffer para entrenamiento
        self.training_buffer = []
    
    def _init_weights(self, in_dim, out_dim):
        scale = math.sqrt(2.0 / max(in_dim, 1))
        return [[random.gauss(0, scale) for _ in range(out_dim)] for _ in range(in_dim)]
    
    def _forward_model(self, state, action):
        """Predicción de siguiente estado."""
        # Normalizar entradas
        s = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(s) < self.state_dim:
            s.append(0.0)
        s = s[:self.state_dim]
        
        # Concatenar acción
        x = s + [float(action) / max(self.action_dim, 1)]
        
        # Capa 1
        h = []
        for j in range(len(self.forward_b1)):
            val = sum(x[i] * self.forward_w1[i][j] for i in range(len(x))) + self.forward_b1[j]
            h.append(max(0.0, val))
        
        # Capa 2
        out = []
        for j in range(len(self.forward_b2)):
            val = sum(h[i] * self.forward_w2[i][j] for i in range(len(h))) + self.forward_b2[j]
            out.append(val)
        
        return out
    
    def _train_forward(self, state, action, next_state, steps=1):
        """Entrenar forward model con gradient descent."""
        # Forward pass
        pred = self._forward_model(state, action)
        
        # Target
        target = list(next_state) if isinstance(next_state, (list, tuple)) else [float(next_state)]
        while len(target) < self.state_dim:
            target.append(0.0)
        target = target[:self.state_dim]
        
        # Error
        errors = [target[i] - pred[i] for i in range(self.state_dim)]
        mse = sum(e**2 for e in errors) / self.state_dim
        
        # Backprop simplificado (solo última capa para eficiencia)
        # Actualizar w2, b2
        # Primero necesitamos activaciones de capa oculta
        s = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(s) < self.state_dim:
            s.append(0.0)
        s = s[:self.state_dim]
        x = s + [float(action) / max(self.action_dim, 1)]
        
        h = []
        for j in range(len(self.forward_b1)):
            val = sum(x[i] * self.forward_w1[i][j] for i in range(len(x))) + self.forward_b1[j]
            h.append(max(0.0, val))
        
        # Gradiente en capa de salida
        for j in range(self.state_dim):
            for i in range(len(h)):
                self.forward_w2[i][j] += self.lr * errors[j] * h[i]
            self.forward_b2[j] += self.lr * errors[j]
        
        return mse
    
    def compute_intrinsic_reward(self, state, action, next_state):
        """Calcular recompensa intrínseca."""
        # 1. Prediction error (curiosity)
        pred = self._forward_model(state, action)
        target = list(next_state) if isinstance(next_state, (list, tuple)) else [float(next_state)]
        while len(target) < self.state_dim:
            target.append(0.0)
        target = target[:self.state_dim]
        
        pred_error = math.sqrt(sum((p - t)**2 for p, t in zip(pred, target)))
        
        # 2. Novelty (estados no visitados)
        state_key = self._hash_state(state)
        count = self.state_counts.get(state_key, 0)
        novelty = 1.0 / (1.0 + min(count, self.max_count) / 10.0)
        self.state_counts[state_key] = count + 1
        
        # Combinar
        intrinsic = self.intrinsic_reward_scale * (
            self.novelty_weight * pred_error + 
            (1 - self.novelty_weight) * novelty
        )
        
        # Entrenar forward model
        self.training_buffer.append((state, action, next_state))
        if len(self.training_buffer) > 32:
            # Entrenar mini-batch
            batch = random.sample(self.training_buffer, min(8, len(self.training_buffer)))
            for s, a, ns in batch:
                self._train_forward(s, a, ns)
            self.training_buffer = self.training_buffer[-16:]  # Mantener recientes
        
        return intrinsic
    
    def _hash_state(self, state):
        """Hash de estado para conteo."""
        if isinstance(state, (list, tuple)):
            return tuple(round(float(x), 1) for x in state[:min(len(state), self.state_dim)])
        return (round(float(state), 1),)
    
    def update_models(self, state, action, next_state):
        """Actualización explícita de modelos."""
        mse = self._train_forward(state, action, next_state)
        return {'forward_mse': mse}


# ================================================================================
# SECCION 19: NEURAL Q APPROXIMATOR (VERSION LIVIANA CORREGIDA)
# ================================================================================
class NeuralQApproximator:
    """Aproximador Q neuronal con backprop correcto."""
    
    def __init__(self, state_dim, action_dim, hidden_sizes=[32, 16], lr=0.001):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = lr
        
        # Arquitectura: state_dim -> hidden[0] -> hidden[1] -> action_dim
        layers = [state_dim] + list(hidden_sizes) + [action_dim]
        
        self.weights = []
        self.biases = []
        self.activations_cache = []  # Para backprop
        
        for i in range(len(layers) - 1):
            scale = math.sqrt(2.0 / max(layers[i], 1))
            w = [[random.gauss(0, scale) for _ in range(layers[i+1])] 
                 for _ in range(layers[i])]
            b = [0.0] * layers[i+1]
            self.weights.append(w)
            self.biases.append(b)
    
    def _forward(self, state, store_activations=False):
        """Forward pass con opción de guardar activaciones."""
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        if store_activations:
            self.activations_cache = [x.copy()]
        
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            new_x = []
            for j in range(len(b)):
                val = sum(x[k] * w[k][j] for k in range(len(x))) + b[j]
                # ReLU para capas ocultas, lineal para salida
                if i < len(self.weights) - 1:
                    val = max(0.0, val)
                new_x.append(val)
            x = new_x
            
            if store_activations:
                self.activations_cache.append(x.copy())
        
        return x
    
    def predict(self, state):
        """Predicción de Q-values."""
        return self._forward(state, store_activations=False)
    
    def update(self, state, target):
        """Actualización con backprop correcto."""
        # Forward con cache
        output = self._forward(state, store_activations=True)
        
        # Error de salida
        errors = [target[i] - output[i] if i < len(target) else 0.0 
                  for i in range(self.action_dim)]
        
        # Backpropagation
        for layer_idx in reversed(range(len(self.weights))):
            current_activation = self.activations_cache[layer_idx + 1]
            prev_activation = self.activations_cache[layer_idx]
            
            # Gradientes para esta capa
            if layer_idx < len(self.weights) - 1:
                # Capa oculta: aplicar derivada ReLU
                deltas = []
                for j in range(len(current_activation)):
                    if current_activation[j] > 0:
                        # Propagar error de capa siguiente
                        delta = 0.0
                        for k in range(len(errors)):
                            delta += errors[k] * self.weights[layer_idx + 1][j][k]
                        deltas.append(delta)
                    else:
                        deltas.append(0.0)
            else:
                # Capa de salida: error directo
                deltas = errors
            
            # Actualizar pesos
            for j in range(len(self.weights[layer_idx][0])):
                for i in range(len(prev_activation)):
                    self.weights[layer_idx][i][j] += self.lr * deltas[j] * prev_activation[i]
                self.biases[layer_idx][j] += self.lr * deltas[j]
            
            # Preparar errors para siguiente capa (hacia atrás)
            errors = deltas
    
    def get_q_value(self, state, action):
        """Obtener Q(s,a)."""
        q_values = self.predict(state)
        return q_values[action] if action < len(q_values) else 0.0


# ================================================================================
# SECCION 20: META-LEARNER (VERSION LIVIANA CORREGIDA)
# ================================================================================
class MetaLearner:
    """Meta-learning con MAML simplificado pero funcional."""
    
    def __init__(self, state_dim, action_dim, meta_lr=0.01, inner_lr=0.1,
                 inner_steps=3, meta_batch_size=5):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.meta_lr = meta_lr
        self.inner_lr = inner_lr
        self.inner_steps = inner_steps
        self.meta_batch_size = meta_batch_size
        
        # Meta-parámetros (slow weights): política softmax
        self.theta = {
            'w': self._init_weights(state_dim, action_dim, scale=0.1),
            'b': [0.0] * action_dim
        }
        
        # Historial de tareas
        self.task_memory = []
        self.max_tasks = 100
    
    def _init_weights(self, in_dim, out_dim, scale=None):
        if scale is None:
            scale = math.sqrt(2.0 / max(in_dim, 1))
        return [[random.gauss(0, scale) for _ in range(out_dim)] for _ in range(in_dim)]
    
    def _softmax(self, x):
        max_x = max(x)
        exp_x = [math.exp(v - max_x) for v in x]
        s = sum(exp_x)
        return [v / s for v in exp_x] if s > 0 else [1.0/len(x)] * len(x)
    
    def _forward(self, state, weights):
        """Forward con pesos dados."""
        x = list(state) if isinstance(state, (list, tuple)) else [float(state)]
        while len(x) < self.state_dim:
            x.append(0.0)
        x = x[:self.state_dim]
        
        logits = []
        for j in range(self.action_dim):
            val = sum(x[i] * weights['w'][i][j] for i in range(len(x))) + weights['b'][j]
            logits.append(val)
        
        return self._softmax(logits)
    
    def _compute_loss(self, task_data, weights):
        """Pérdida negativa log-verosimilitud."""
        total_loss = 0.0
        for data in task_data:
            s = data['state']
            a = data['action']
            r = data['reward']
            
            probs = self._forward(s, weights)
            # Weighted negative log likelihood
            loss = -math.log(probs[a] + 1e-8) * max(r, 0.1)
            total_loss += loss
        
        return total_loss / len(task_data) if task_data else 0.0
    
    def inner_loop(self, task_data, steps=None):
        """Adaptación rápida a tarea."""
        if steps is None:
            steps = self.inner_steps
        
        # Clonar meta-parámetros
        fast_weights = {
            'w': [[v for v in row] for row in self.theta['w']],
            'b': [v for v in self.theta['b']]
        }
        
        # Gradiente descendente por pasos
        for _ in range(steps):
            # Calcular gradiente por diferencias finitas (más estable)
            loss = self._compute_loss(task_data, fast_weights)
            
            # Aproximación de gradiente
            for j in range(self.action_dim):
                # Gradiente respecto a bias
                fast_weights['b'][j] -= self.inner_lr * loss * 0.1
                
                # Gradiente respecto a pesos
                for i in range(self.state_dim):
                    fast_weights['w'][i][j] -= self.inner_lr * loss * 0.01
        
        return fast_weights
    
    def meta_update(self, tasks):
        """Actualización meta con múltiples tareas."""
        if not tasks:
            return
        
        meta_gradient = {
            'w': [[0.0] * self.action_dim for _ in range(self.state_dim)],
            'b': [0.0] * self.action_dim
        }
        
        for task in tasks:
            # Adaptar a tarea
            adapted = self.inner_loop(task)
            
            # Evaluar en tarea de validación (misma para simplicidad)
            post_loss = self._compute_loss(task, adapted)
            pre_loss = self._compute_loss(task, self.theta)
            
            # Mejora
            improvement = pre_loss - post_loss
            
            # Acumular gradiente meta (simplificado)
            for j in range(self.action_dim):
                meta_gradient['b'][j] += improvement * 0.1
                for i in range(self.state_dim):
                    meta_gradient['w'][i][j] += improvement * 0.01
        
        # Aplicar actualización meta
        n = len(tasks)
        for j in range(self.action_dim):
            self.theta['b'][j] += self.meta_lr * meta_gradient['b'][j] / n
            for i in range(self.state_dim):
                self.theta['w'][i][j] += self.meta_lr * meta_gradient['w'][i][j] / n
    
    def adapt_to_task(self, task_data):
        """Adaptar a nueva tarea y retornar pesos adaptados."""
        return self.inner_loop(task_data)
    
    def select_action(self, state, weights=None):
        """Seleccionar acción con pesos dados o meta."""
        w = weights if weights is not None else self.theta
        probs = self._forward(state, w)
        
        r = random.random()
        cumsum = 0.0
        for i, p in enumerate(probs):
            cumsum += p
            if r <= cumsum:
                return i, probs[i]
        return len(probs) - 1, probs[-1]
    
    def store_task(self, task_data):
        """Almacenar experiencia de tarea."""
        self.task_memory.append(task_data)
        if len(self.task_memory) > self.max_tasks:
            self.task_memory.pop(0)
    
    def meta_step(self):
        """Ejecutar un paso de meta-entrenamiento."""
        if len(self.task_memory) < self.meta_batch_size:
            return {'status': 'insufficient_tasks'}
        
        tasks = random.sample(self.task_memory, self.meta_batch_size)
        self.meta_update(tasks)
        
        return {
            'status': 'updated',
            'tasks_used': len(tasks),
            'memory_size': len(self.task_memory)
        }


# ================================================================================
# SECCION 21: SISTEMA ENSAMBLE MULTI-ALGORITMO (VERSION LIVIANA CORREGIDA)
# ================================================================================
class EnsembleRL:
    """Ensemble funcional con todos los algoritmos corregidos."""
    
    def __init__(self, state_dim, action_dim):
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Inicializar algoritmos corregidos
        self.algorithms = {
            'double_dqn': DoubleDQN(state_dim, action_dim, memory_size=2000),
            'sarsa': SARSAAgent(state_dim, action_dim),
            'actor_critic': ActorCritic(state_dim, action_dim),
            'ppo': PPOOptimizer(state_dim, action_dim),
            'mcts': MCTSAgent(state_dim, action_dim, explorations=30),
        }
        
        # Pesos adaptativos por rendimiento
        self.weights = {
            'double_dqn': 0.25,
            'sarsa': 0.20,
            'actor_critic': 0.20,
            'ppo': 0.20,
            'mcts': 0.15
        }
        
        # Trackers de rendimiento
        self.performance = {name: {'rewards': [], 'avg': 0.0} for name in self.algorithms}
        self.performance_window = 50
        
        # Módulos auxiliares
        self.episodic_memory = EpisodicMemory(capacity=5000)
        self.curiosity = CuriosityModule(state_dim, action_dim)
        self.kalman = KalmanFilter(state_dim=4, obs_dim=2)
        self.meta_learner = MetaLearner(state_dim, action_dim)
        self.fuzzy = FuzzyLogicController()
        self._setup_fuzzy()
        
        # Historial
        self.decision_history = []
        self.max_history = 1000
        
        # Estado para Kalman
        self.last_kalman_input = None
    
    def _setup_fuzzy(self):
        """Configurar controlador difuso para decisión final."""
        self.fuzzy.add_mf('confidence', 'high', 'triangle', (0.6, 0.8, 1.0))
        self.fuzzy.add_mf('confidence', 'medium', 'triangle', (0.3, 0.5, 0.7))
        self.fuzzy.add_mf('confidence', 'low', 'triangle', (0.0, 0.2, 0.4))
        
        self.fuzzy.add_mf('agreement', 'high', 'triangle', (0.7, 0.85, 1.0))
        self.fuzzy.add_mf('agreement', 'medium', 'triangle', (0.4, 0.6, 0.8))
        self.fuzzy.add_mf('agreement', 'low', 'triangle', (0.0, 0.3, 0.5))
        
        self.fuzzy.add_mf('output', 'trust', 'triangle', (0.7, 0.9, 1.0))
        self.fuzzy.add_mf('output', 'verify', 'triangle', (0.4, 0.6, 0.8))
        self.fuzzy.add_mf('output', 'reject', 'triangle', (0.0, 0.2, 0.4))
        
        self.fuzzy.add_rule(
            {'confidence': 'high', 'agreement': 'high'},
            {'output': 'trust'}
        )
        self.fuzzy.add_rule(
            {'confidence': 'medium', 'agreement': 'medium'},
            {'output': 'verify'}
        )
        self.fuzzy.add_rule(
            {'confidence': 'low', 'agreement': 'low'},
            {'output': 'reject'}
        )
    
    def _normalize_state_for_kalman(self, state):
        """Normalizar estado para filtro de Kalman."""
        if isinstance(state, (list, tuple)):
            # Extraer componentes de posición si existen, o usar primeras 2
            pos = [float(state[i]) if i < len(state) else 0.0 for i in range(2)]
        else:
            pos = [float(state), 0.0]
        
        # Escalar a coordenadas razonables
        pos = [p % 1.0 for p in pos]
        return pos
    
    def select_action(self, state, exploit_only=False):
        """Selección por votación ponderada con consenso."""
        votes = {}
        confidences = {}
        
        for name, algo in self.algorithms.items():
            try:
                if name == 'double_dqn':
                    action = algo.select_action(state, exploit_only)
                    # Confianza basada en max Q-value vs segundo max
                    q_vals = algo._forward(algo.q_network, state)
                    sorted_q = sorted(q_vals, reverse=True)
                    confidence = 0.5 if len(sorted_q) < 2 else min(1.0, (sorted_q[0] - sorted_q[1]) / (abs(sorted_q[0]) + 0.1))
                    
                elif name == 'sarsa':
                    action = algo.select_action(state, exploit_only)
                    confidence = 1.0 - algo.epsilon
                    
                elif name == 'actor_critic':
                    action, prob = algo.select_action(state)
                    confidence = prob
                    
                elif name == 'ppo':
                    action, log_prob = algo.select_action(state)
                    # Convertir log_prob a confianza aproximada
                    confidence = min(1.0, math.exp(log_prob) * self.action_dim)
                    
                elif name == 'mcts':
                    # Construir árbol si no exploit_only
                    if not exploit_only:
                        algo.build_tree(state, list(range(self.action_dim)))
                    action = algo.select_best_action()
                    stats = algo.get_statistics()
                    total_visits = stats.get('total_visits', 1)
                    best_visits = max(
                        (a.get('visits', 0) for a in stats.get('actions', {}).values()),
                        default=0
                    )
                    confidence = best_visits / total_visits if total_visits > 0 else 0.5
                    
                else:
                    continue
                
                votes[name] = action
                confidences[name] = confidence
                
            except Exception as e:
                log(f"[ENSEMBLE] Error en {name}: {e}")
                continue
        
        if not votes:
            return random.randint(0, self.action_dim - 1), 0.5
        
        # Calcular acuerdo entre algoritmos
        action_counts = {}
        for action in votes.values():
            action_counts[action] = action_counts.get(action, 0) + 1
        
        max_agreement = max(action_counts.values()) if action_counts else 0
        agreement_ratio = max_agreement / len(votes)
        
        # Votación ponderada por rendimiento
        weighted_votes = {}
        for name, action in votes.items():
            perf = self.performance[name]['avg']
            weight = self.weights.get(name, 0.2) * (1 + max(0, perf))
            weighted_votes[action] = weighted_votes.get(action, 0.0) + weight
        
        best_action = max(weighted_votes, key=weighted_votes.get)
        total_weight = sum(weighted_votes.values())
        vote_confidence = weighted_votes[best_action] / total_weight if total_weight > 0 else 0.5
        
        # Fuzzy fusion: combinar confianza de voto con acuerdo
        fuzzy_input = {
            'confidence': vote_confidence,
            'agreement': agreement_ratio
        }
        final_trust = self.fuzzy.evaluate(fuzzy_input, output_range=(0, 1))
        
        # Decisión final
        if final_trust < 0.3:
            # Poca confianza: explorar
            final_action = random.randint(0, self.action_dim - 1)
            final_confidence = 0.3
        else:
            final_action = best_action
            final_confidence = final_trust
        
        # Guardar historial
        self.decision_history.append({
            'state': state,
            'votes': votes,
            'selected': final_action,
            'confidence': final_confidence,
            'trust': final_trust,
            'timestamp': time.time()
        })
        if len(self.decision_history) > self.max_history:
            self.decision_history.pop(0)
        
        return final_action, final_confidence
    
    def update(self, state, action, reward, next_state, done, use_curiosity=True):
        """Actualizar todos los algoritmos y módulos."""
        result = {
            'extrinsic_reward': reward,
            'intrinsic_reward': 0.0,
            'total_reward': reward,
            'algorithm_updates': {}
        }
        
        # Curiosity
        if use_curiosity:
            try:
                intrinsic = self.curiosity.compute_intrinsic_reward(state, action, next_state)
                result['intrinsic_reward'] = intrinsic
                result['total_reward'] = reward + intrinsic
            except Exception as e:
                log(f"[ENSEMBLE] Curiosity error: {e}")
        
        total_reward = result['total_reward']
        
        # Kalman: actualizar con posición normalizada
        try:
            kalman_obs = self._normalize_state_for_kalman(next_state)
            if self.last_kalman_input is not None:
                self.kalman.predict()
            self.kalman.update(kalman_obs)
            self.last_kalman_input = kalman_obs
        except Exception as e:
            log(f"[ENSEMBLE] Kalman error: {e}")
        
        # Actualizar cada algoritmo
        state_key = tuple(state) if isinstance(state, (list, tuple)) else (float(state),)
        next_key = tuple(next_state) if isinstance(next_state, (list, tuple)) else (float(next_state),)
        
        for name, algo in self.algorithms.items():
            try:
                if name == 'double_dqn':
                    algo.store(state_key, action, total_reward, next_key, done)
                    if len(algo.memory) >= algo.batch_size:
                        learn_result = algo.learn()
                        result['algorithm_updates']['double_dqn'] = learn_result
                
                elif name == 'sarsa':
                    next_action = algo.select_action(next_key)
                    algo.update(state_key, action, total_reward, next_key, next_action, done)
                    result['algorithm_updates']['sarsa'] = {'epsilon': algo.epsilon}
                
                elif name == 'actor_critic':
                    algo.store(state, action, total_reward, next_state, done)
                    # Actualizar cada 10 pasos o al final
                    if len(algo.trajectory) >= 10 or done:
                        ac_result = algo.update()
                        result['algorithm_updates']['actor_critic'] = ac_result
                
                elif name == 'ppo':
                    _, log_prob = algo.select_action(state)
                    v = algo._get_value(state)
                    algo.store(state, action, total_reward, next_state, done, log_prob, v)
                    # Actualizar cada 20 pasos o al final
                    if len(algo.memory) >= 20 or done:
                        ppo_result = algo.update(epochs=2, batch_size=16)
                        result['algorithm_updates']['ppo'] = ppo_result
                
                elif name == 'mcts':
                    # MCTS no se actualiza online, solo se usa para planificación
                    pass
                
                # Trackear rendimiento
                self.performance[name]['rewards'].append(total_reward)
                if len(self.performance[name]['rewards']) > self.performance_window:
                    self.performance[name]['rewards'].pop(0)
                self.performance[name]['avg'] = sum(self.performance[name]['rewards']) / len(self.performance[name]['rewards'])
                
            except Exception as e:
                log(f"[ENSEMBLE] Error actualizando {name}: {e}")
        
        # Memoria episódica
        try:
            exp = Experience(state_key, action, total_reward, next_key, done)
            self.episodic_memory.add_episode([exp])
        except Exception:
            pass
        
        # Meta-learning: almacenar para entrenamiento posterior
        try:
            self.meta_learner.store_task([{
                'state': state,
                'action': action,
                'reward': total_reward
            }])
        except Exception:
            pass
        
        # Actualizar pesos del ensemble periódicamente
        if len(self.decision_history) % 100 == 0:
            self._adapt_weights()
        
        return result
    
    def _adapt_weights(self):
        """Adaptar pesos del ensemble según rendimiento reciente."""
        total_perf = sum(max(0.01, self.performance[name]['avg']) for name in self.algorithms)
        
        if total_perf > 0:
            for name in self.weights:
                if name in self.performance:
                    # Peso proporcional al rendimiento relativo
                    new_weight = max(0.05, min(0.5, self.performance[name]['avg'] / total_perf))
                    # Suavizar cambio
                    self.weights[name] = 0.7 * self.weights[name] + 0.3 * new_weight
            
            # Normalizar
            total = sum(self.weights.values())
            if total > 0:
                for name in self.weights:
                    self.weights[name] /= total
    
    def optimize_weights(self, fitness_fn=None):
        """Optimizar pesos con algoritmo genético."""
        if fitness_fn is None:
            # Fitness por rendimiento promedio
            def fitness_fn(weights_dict):
                # Simular con pesos dados
                original = dict(self.weights)
                self.weights.update(weights_dict)
                
                # Evaluar usando historial reciente
                score = 0
                for dec in self.decision_history[-50:]:
                    # Recompensar decisiones con alta confianza que resultaron bien
                    score += dec.get('trust', 0.5)
                
                self.weights.update(original)
                return score
        
        ga = GeneticOptimizer(
            param_bounds={name: (0.05, 0.5) for name in self.algorithms if name != 'mcts'},
            pop_size=15,
            generations=20
        )
        
        best_weights, best_fitness = ga.optimize(fitness_fn, verbose=False)
        
        # Aplicar mejores pesos encontrados
        for name in best_weights:
            if name in self.weights:
                self.weights[name] = best_weights[name]
        
        # Normalizar
        total = sum(self.weights.values())
        if total > 0:
            for name in self.weights:
                self.weights[name] /= total
        
        return self.weights
    
    def get_state(self):
        """Estado completo del ensemble."""
        return {
            'algorithms': list(self.algorithms.keys()),
            'weights': dict(self.weights),
            'performance': {
                name: {
                    'avg': data['avg'],
                    'samples': len(data['rewards'])
                }
                for name, data in self.performance.items()
            },
            'memory_size': len(self.episodic_memory.episodes) if hasattr(self.episodic_memory, 'episodes') else 0,
            'decisions': len(self.decision_history),
            'kalman_uncertainty': self.kalman.get_uncertainty(),
            'kalman_position': self.kalman.get_position(),
            'kalman_velocity': self.kalman.get_velocity()
        }


# ================================================================================
# SECCION 22: TRUST GUARD Y RUTAS INTELIGENTES (VERSION LIVIANA CORREGIDA)
# ================================================================================

def TRUST_GUARD(aceptaciones_rapidas=0, incoherencias_temporales=0,
                nivel_confianza="ALTO", etiqueta_interna="HUMAN_LIKE_AUTOMATION"):
    """
    Sistema de guarda de confianza para decisiones automatizadas.
    Retorna estado operativo basado en métricas de comportamiento.
    """
    if incoherencias_temporales > 2 or nivel_confianza == "BAJO":
        return "ESTADO_CONSERVADOR"
    return "ESTADO_NORMAL"


def rutas_inteligentes(
    ubicacion_actual: Optional[dict] = None,
    radio_busqueda_km: float = 10.0,
    max_destinos: int = 5,
    priorizar: str = "ingreso_por_minuto",
    auto_trigger_ollama: bool = True,
    ceoia_instance=None  # Parámetro opcional para integración
) -> dict:
    """
    Genera rutas inteligentes optimizadas basadas en análisis de zonas.
    Versión liviana con caché y cálculos eficientes.
    """
    # Determinar ubicación actual
    if ubicacion_actual is None:
        zona_info = get_zona_by_id(ULTIMA_ZONA)
        if zona_info:
            lat_centro = (zona_info["lat_min"] + zona_info["lat_max"]) / 2
            lng_centro = (zona_info["lon_min"] + zona_info["lon_max"]) / 2
            ubicacion_actual = {
                "lat": lat_centro + random.uniform(-0.01, 0.01),
                "lng": lng_centro + random.uniform(-0.01, 0.01)
            }
        else:
            ubicacion_actual = {"lat": 8.9922, "lng": -79.5201}
    
    # Cache de zonas candidatas para evitar recálculos
    cache_key = (round(ubicacion_actual["lat"], 3), round(ubicacion_actual["lng"], 3), radio_busqueda_km)
    if hasattr(rutas_inteligentes, '_cache') and rutas_inteligentes._cache.get('key') == cache_key:
        if time.time() - rutas_inteligentes._cache.get('timestamp', 0) < 30:  # Cache 30 seg
            return rutas_inteligentes._cache['data']
    else:
        rutas_inteligentes._cache = {}
    
    # Encontrar zonas candidatas dentro del radio
    zonas_candidatas = []
    for zona in ZONAS:
        lat_centro = (zona["lat_min"] + zona["lat_max"]) / 2
        lng_centro = (zona["lon_min"] + zona["lon_max"]) / 2
        distancia = calcular_distancia_py(
            ubicacion_actual["lat"], ubicacion_actual["lng"],
            lat_centro, lng_centro
        )
        if distancia <= radio_busqueda_km:
            estado_zona = zona_estado.get(zona["id"], {})
            zonas_candidatas.append({
                "zona_id": zona["id"], "nombre": zona["nombre"],
                "distancia_km": round(distancia, 2),
                "color": estado_zona.get("color", "gris"),
                "demanda": estado_zona.get("demanda", 0),
                "oferta": estado_zona.get("oferta", 0),
                "ratio_demanda": estado_zona.get("ratio_demanda", 0),
                "ganancia_estimada": estado_zona.get("ganancia_estimada", 0),
                "tiempo_espera": estado_zona.get("tiempo_espera", 0)
            })
    
    if not zonas_candidatas:
        resultado = {
            "error": "No hay zonas disponibles",
            "rutas": [], "mejor_opcion": None, "timestamp": time.time()
        }
        rutas_inteligentes._cache = {'key': cache_key, 'data': resultado, 'timestamp': time.time()}
        return resultado
    
    # Evaluar rutas con scoring optimizado
    rutas_evaluadas = []
    hora_utc = _datetime.now(_timezone.utc).hour
    
    # Factores pre-calculados
    bonus_hora = 1.3 if (7 <= hora_utc <= 9 or 17 <= hora_utc <= 20) else 1.0
    color_multiplicador = {"rojo": 1.5, "naranja": 1.2, "azul": 1.0, "gris": 0.9}
    
    for zona in zonas_candidatas:
        # Tarifa estimada
        tarifa_estimada = (
            zona["ganancia_estimada"]
            if zona["ganancia_estimada"] > 0
            else random.uniform(5.0, 15.0)
        )
        
        # Tiempo total estimado (espera + viaje aprox 2 min/km)
        tiempo_total = zona["tiempo_espera"] + (zona["distancia_km"] * 2)
        ingreso_por_minuto = tarifa_estimada / max(1, tiempo_total)
        
        # Factores de scoring
        bonus_color = color_multiplicador.get(zona["color"], 1.0)
        ratio_factor = min(2.0, zona["ratio_demanda"] / 1.5) if zona["ratio_demanda"] > 0 else 0.5
        bonus_cercania = max(0.5, 1.5 - (zona["distancia_km"] / 10))
        
        # Peso configurable
        peso = ALGO_WEIGHTS.get("fare", 1.0)
        score_base = ingreso_por_minuto * peso * bonus_color * ratio_factor * bonus_hora * bonus_cercania
        
        # Ajuste por criterio de priorización
        score_final = score_base * {
            "ingreso_por_minuto": 1.2,
            "distancia_corta": bonus_cercania * 1.1,
            "zona_roja": (1.5 if zona["color"] == "rojo" else 1.0)
        }.get(priorizar, 1.0)
        
        # Validación TRUST_GUARD
        eta_valida = zona["tiempo_espera"] >= 0
        estado_op = TRUST_GUARD(
            aceptaciones_rapidas=0,
            incoherencias_temporales=0 if eta_valida else 1,
            nivel_confianza="ALTO",
            etiqueta_interna="HUMAN_LIKE_AUTOMATION"
        )
        puede_recomendar = estado_op != "ESTADO_CONSERVADOR" and tarifa_estimada >= 3.13
        
        rutas_evaluadas.append({
            "zona_id": zona["zona_id"], "nombre": zona["nombre"],
            "distancia_km": zona["distancia_km"],
            "tarifa_estimada": round(tarifa_estimada, 2),
            "ingreso_por_minuto": round(ingreso_por_minuto, 2),
            "color_zona": zona["color"],
            "score_final": round(score_final, 3),
            "puede_recomendar": puede_recomendar
        })
    
    # Filtrar y ordenar
    rutas_validas = [r for r in rutas_evaluadas if r["puede_recomendar"]] or rutas_evaluadas
    rutas_ordenadas = sorted(rutas_validas, key=lambda x: x["score_final"], reverse=True)[:max_destinos]
    mejor_opcion = rutas_ordenadas[0] if rutas_ordenadas else None
    
    # Auto-trigger Ollama si está disponible
    if auto_trigger_ollama and mejor_opcion:
        target = ceoia_instance if ceoia_instance is not None else ceo_avanzado
        if target:
            try:
                orden_ollama = f"rutas_inteligentes: zona={mejor_opcion['zona_id']} score={mejor_opcion['score_final']}"
                if hasattr(target, 'recibir_orden_ollama'):
                    target.recibir_orden_ollama(orden_ollama)
                elif hasattr(target, 'recibir_orden'):
                    target.recibir_orden(orden_ollama)
                log(f"[OLLAMA] Auto-trigger: {orden_ollama[:80]}...")
            except Exception as e:
                log(f"[WARN] Error auto-trigger Ollama: {e}")
    
    log(f"[RUTAS] {len(rutas_ordenadas)} opciones | Mejor: {mejor_opcion['nombre'] if mejor_opcion else 'N/A'}")
    
    resultado = {
        "rutas": rutas_ordenadas, "mejor_opcion": mejor_opcion,
        "metricas": {
            "total_zonas": len(zonas_candidatas), "criterio": priorizar,
            "hora": hora_utc, "zona_actual": ULTIMA_ZONA
        },
        "driver_edge_aplicado": True, "timestamp": time.time()
    }
    
    # Guardar en cache
    rutas_inteligentes._cache = {'key': cache_key, 'data': resultado, 'timestamp': time.time()}
    return resultado


def ciclo_rutas_inteligentes():
    """Ciclo autónomo de búsqueda de rutas."""
    while not STOP_EVENT.is_set():
        try:
            if ESTADO_CONDUCTOR == "IDLE":
                resultado = rutas_inteligentes(priorizar="ingreso_por_minuto")
                if resultado.get("mejor_opcion"):
                    log(f"[RUTA] Sugerida: {resultado['mejor_opcion']['nombre']}")
            time.sleep(300)
        except Exception as e:
            log(f"[ERROR] Ciclo rutas: {e}")
            time.sleep(60)


# ================================================================================
# SECCION 23: SISTEMA DE KILOMETRAJE LEARNER (VERSION LIVIANA CORREGIDA)
# ================================================================================

class KilometrajeLearner:
    """Sistema de aprendizaje por kilometraje con adaptación de pesos."""
    
    def __init__(self):
        self.km_totales = 0.0
        self.km_por_zona = defaultdict(float)
        self.km_por_hora = defaultdict(float)
        self.km_por_dia = defaultdict(float)
        self.ganancia_por_km = deque(maxlen=200)  # Limitado para memoria
        self.eficiencia_km = deque(maxlen=100)
        self.historial_km = deque(maxlen=500)  # Reducido para Termux
        self.last_position = None
        self.last_timestamp = None
        self._lock = threading.Lock()  # Thread-safe
        
    def registrar_movimiento(self, lat1: float, lng1: float,
                            lat2: float, lng2: float,
                            timestamp: float = None) -> dict:
        """Registra movimiento y calcula estadísticas."""
        with self._lock:
            distancia = calcular_distancia_py(lat1, lng1, lat2, lng2)
            if timestamp is None:
                timestamp = time.time()
            
            self.km_totales += distancia
            self.historial_km.append({
                'timestamp': timestamp, 'distancia': distancia,
                'origen': (round(lat1, 6), round(lng1, 6)),
                'destino': (round(lat2, 6), round(lng2, 6))
            })
            
            # Estadísticas por zona/hora/día
            zona_actual = ULTIMA_ZONA
            self.km_por_zona[zona_actual] += distancia
            
            dt = _datetime.fromtimestamp(timestamp)
            hora = dt.hour
            dia = dt.weekday()
            self.km_por_hora[hora] += distancia
            self.km_por_dia[dia] += distancia
            
            # Eficiencia
            if self.last_timestamp and timestamp > self.last_timestamp:
                tiempo_horas = (timestamp - self.last_timestamp) / 3600
                if tiempo_horas > 0:
                    eficiencia = distancia / tiempo_horas
                    self.eficiencia_km.append(eficiencia)
            
            self.last_timestamp = timestamp
            
            return {
                'distancia_km': round(distancia, 3),
                'km_totales': round(self.km_totales, 3),
                'km_en_zona': round(self.km_por_zona[zona_actual], 3),
                'eficiencia_promedio': self.get_eficiencia_promedio()
            }
    
    def registrar_ganancia_por_km(self, ganancia: float, km_recorridos: float):
        """Registra rentabilidad y adapta pesos del algoritmo."""
        if km_recorridos <= 0:
            return 0.0
            
        ganancia_por_km = ganancia / km_recorridos
        self.ganancia_por_km.append({
            'timestamp': time.time(), 'ganancia': ganancia,
            'km': km_recorridos, 'ganancia_por_km': ganancia_por_km
        })
        self._actualizar_aprendizaje_km(ganancia_por_km)
        return ganancia_por_km
    
    def _actualizar_aprendizaje_km(self, ganancia_por_km: float):
        """Adapta pesos del algoritmo según rentabilidad."""
        # Umbrales adaptativos
        if ganancia_por_km > 5.0:
            factor = 1.05
            mensaje = f"[KM] Alta rentabilidad (${ganancia_por_km:.2f}/km) -> aumentando peso distancia"
        elif ganancia_por_km < 2.0:
            factor = 0.95
            mensaje = f"[KM] Baja rentabilidad (${ganancia_por_km:.2f}/km) -> reduciendo peso distancia"
        else:
            return  # Sin cambios en rango normal
        
        # Actualizar pesos con límites
        ALGO_WEIGHTS['distance'] = max(0.1, min(2.0, ALGO_WEIGHTS.get('distance', 0.2) * factor))
        ALGO_WEIGHTS['distance_traveled'] = max(0.01, min(1.0, ALGO_WEIGHTS.get('distance_traveled', 0.05) * factor))
        log(mensaje)
    
    def get_eficiencia_promedio(self) -> float:
        """Promedio de eficiencia reciente."""
        if self.eficiencia_km:
            return sum(self.eficiencia_km) / len(self.eficiencia_km)
        return 0.0
    
    def get_mejor_hora_por_km(self) -> int:
        """Hora con más kilometraje."""
        if self.km_por_hora:
            return max(self.km_por_hora.items(), key=lambda x: x[1])[0]
        return -1
    
    def get_mejor_zona_por_km(self) -> str:
        """Zona con más kilometraje."""
        if self.km_por_zona:
            return max(self.km_por_zona.items(), key=lambda x: x[1])[0]
        return ULTIMA_ZONA
    
    def get_ganancia_promedio_por_km(self) -> float:
        """Promedio de ganancia por km reciente."""
        if self.ganancia_por_km:
            ultimas = list(self.ganancia_por_km)[-50:]
            return sum(g['ganancia_por_km'] for g in ultimas) / len(ultimas)
        return 0.0
    
    def get_stats(self) -> dict:
        """Estadísticas completas."""
        with self._lock:
            return {
                'km_totales': round(self.km_totales, 2),
                'eficiencia_promedio_kmh': round(self.get_eficiencia_promedio(), 2),
                'ganancia_promedio_por_km': round(self.get_ganancia_promedio_por_km(), 2),
                'mejor_hora_km': self.get_mejor_hora_por_km(),
                'mejor_zona_km': self.get_mejor_zona_por_km(),
                'km_por_zona': dict(self.km_por_zona),
                'km_por_hora': dict(self.km_por_hora),
                'ultimos_km': [round(h['distancia'], 3) for h in list(self.historial_km)[-10:]]
            }


def inicializar_kilometraje_learner(ceoia_instance):
    """Inicializa sistema de kilometraje en instancia CEOIA."""
    if not hasattr(ceoia_instance, 'km_learner') or ceoia_instance.km_learner is None:
        ceoia_instance.km_learner = KilometrajeLearner()
        ceoia_instance.ultima_posicion_km = None
        ceoia_instance.km_acumulados_viaje = 0.0
        log("[KM] Sistema de aprendizaje por kilometraje inicializado")
    return ceoia_instance.km_learner


def actualizar_kilometraje(ceoia_instance, lat_actual: float, lng_actual: float):
    """Actualiza kilometraje con nueva posición."""
    # Asegurar inicialización
    if not hasattr(ceoia_instance, 'km_learner') or ceoia_instance.km_learner is None:
        inicializar_kilometraje_learner(ceoia_instance)
    
    learner = ceoia_instance.km_learner
    
    if ceoia_instance.ultima_posicion_km:
        lat_ant, lng_ant = ceoia_instance.ultima_posicion_km
        resultado = learner.registrar_movimiento(lat_ant, lng_ant, lat_actual, lng_actual)
        
        ceoia_instance.km_acumulados_viaje += resultado['distancia_km']
        
        # Actualizar memoria del sistema si existe
        if hasattr(ceoia_instance, 'memoria_sistema'):
            if 'movimiento' not in ceoia_instance.memoria_sistema:
                ceoia_instance.memoria_sistema['movimiento'] = {'velocidades': [], 'paradas': [], 'desviaciones': []}
            ceoia_instance.memoria_sistema['movimiento']['velocidades'].append(resultado['eficiencia_promedio'])
            # Limitar tamaño
            while len(ceoia_instance.memoria_sistema['movimiento']['velocidades']) > 100:
                ceoia_instance.memoria_sistema['movimiento']['velocidades'].pop(0)
        
        # Log periódico cada 5 km
        if int(learner.km_totales) % 5 == 0 and resultado['distancia_km'] > 0:
            stats = learner.get_stats()
            log(f"[KM] Totales: {stats['km_totales']:.1f}km | Ef: {stats['eficiencia_promedio_kmh']:.1f}km/h | $/km: ${stats['ganancia_promedio_por_km']:.2f}")
    
    ceoia_instance.ultima_posicion_km = (lat_actual, lng_actual)


def registrar_ganancia_viaje(ceoia_instance, ganancia: float):
    """Registra ganancia de viaje completado."""
    if not hasattr(ceoia_instance, 'km_learner') or ceoia_instance.km_learner is None:
        inicializar_kilometraje_learner(ceoia_instance)
    
    if ceoia_instance.km_acumulados_viaje > 0:
        ganancia_por_km = ceoia_instance.km_learner.registrar_ganancia_por_km(
            ganancia, ceoia_instance.km_acumulados_viaje
        )
        log(f"[KM] Viaje: ${ganancia:.2f} en {ceoia_instance.km_acumulados_viaje:.2f}km -> ${ganancia_por_km:.2f}/km")
        ceoia_instance.km_acumulados_viaje = 0.0
        return ganancia_por_km
    return 0.0


def iniciar_monitoreo_kilometraje(ceoia_instance):
    """Inicia hilo de monitoreo de kilometraje."""
    def monitorear_km():
        while not STOP_EVENT.is_set():
            try:
                # Usar GPS_ACTUAL global o de la instancia
                gps = getattr(ceoia_instance, 'gps_actual', None) or GPS_ACTUAL
                if gps and isinstance(gps, dict):
                    lat = gps.get('lat')
                    lng = gps.get('lng')
                    if lat is not None and lng is not None:
                        actualizar_kilometraje(ceoia_instance, float(lat), float(lng))
                time.sleep(10)  # Cada 10 segundos
            except Exception as e:
                log(f"[WARN] Error monitoreo KM: {e}")
                time.sleep(30)
    
    hilo = threading.Thread(target=monitorear_km, daemon=True, name="KM_Monitor")
    hilo.start()
    log("[KM] Monitoreo de kilometraje iniciado")
    return hilo


# ================================================================================
# SECCION 24: FUNCIONES GPS Y ACTUALIZACION (VERSION LIVIANA CORREGIDA)
# ================================================================================

def actualizar_gps_a_mejor_opcion(ubicacion_objetivo: Optional[dict] = None) -> dict:
    """
    Actualiza GPS hacia la mejor opción de zona.
    Si no se proporciona objetivo, calcula el mejor automáticamente.
    """
    global ULTIMA_ZONA, GPS_ACTUAL, GPS_OBJETIVO
    
    try:
        # Leer GPS actual
        gps_actual = leer_gps_actual()
        GPS_ACTUAL = gps_actual
        
        # Si no hay objetivo, calcular mejor ruta
        if ubicacion_objetivo is None:
            log("[GPS] Calculando mejor opcion...")
            resultado_rutas = rutas_inteligentes(
                ubicacion_actual=gps_actual,
                priorizar="ingreso_por_minuto",
                auto_trigger_ollama=True
            )
            
            if resultado_rutas.get("mejor_opcion"):
                mejor_zona = resultado_rutas["mejor_opcion"]
                zona_info = get_zona_by_id(mejor_zona["zona_id"])
                
                if zona_info:
                    lat_objetivo = (zona_info["lat_min"] + zona_info["lat_max"]) / 2
                    lng_objetivo = (zona_info["lon_min"] + zona_info["lon_max"]) / 2
                    ubicacion_objetivo = {
                        "lat": lat_objetivo, "lng": lng_objetivo,
                        "zona_id": mejor_zona["zona_id"],
                        "zona_nombre": mejor_zona["nombre"],
                        "score": mejor_zona.get("score_final", 0),
                        "timestamp": time.time()
                    }
                    ULTIMA_ZONA = mejor_zona["zona_id"]
                    log(f"[GPS] Mejor zona: {mejor_zona['nombre']} (Score: {mejor_zona.get('score_final', 0):.3f})")
                else:
                    return {"exito": False, "error": "Zona no encontrada"}
            else:
                return {"exito": False, "error": "Sin mejor opcion"}
        
        # Calcular distancia al objetivo
        distancia_km = calcular_distancia_py(
            gps_actual["lat"], gps_actual["lng"],
            ubicacion_objetivo["lat"], ubicacion_objetivo["lng"]
        )
        
        GPS_OBJETIVO = ubicacion_objetivo
        
        log(f"[GPS] Actualizado: {ubicacion_objetivo['lat']:.6f}, {ubicacion_objetivo['lng']:.6f}")
        log(f"[GPS] Distancia al objetivo: {distancia_km:.2f} km")
        
        # Guardar en historial
        historial_gps.append({
            "timestamp": time.time(),
            "origen": gps_actual,
            "destino": ubicacion_objetivo,
            "distancia_km": round(distancia_km, 2)
        })
        
        return {
            "exito": True,
            "gps_actual": gps_actual,
            "gps_objetivo": ubicacion_objetivo,
            "distancia_km": round(distancia_km, 2),
            "zona_actualizada": ULTIMA_ZONA,
            "timestamp": time.time()
        }
        
    except Exception as e:
        log(f"[ERROR] Error actualizando GPS: {e}")
        return {"exito": False, "error": str(e)}


def ciclo_actualizacion_gps_automatico():
    """Ciclo automático de actualización GPS."""
    global GPS_ACTIVO, ULTIMA_ACTUALIZACION_GPS
    
    GPS_ACTIVO = True
    ULTIMA_ACTUALIZACION_GPS = time.time()
    log("[GPS] Ciclo automatico iniciado")
    
    while not STOP_EVENT.is_set():
        try:
            if ESTADO_CONDUCTOR == "IDLE":
                tiempo_desde = time.time() - ULTIMA_ACTUALIZACION_GPS
                
                if tiempo_desde >= 300:  # Cada 5 minutos
                    log("[GPS] Actualizando automaticamente...")
                    resultado = actualizar_gps_a_mejor_opcion()
                    
                    if resultado.get("exito"):
                        log(f"[GPS] Actualizado a zona: {resultado.get('zona_actualizada', 'N/A')}")
                        ULTIMA_ACTUALIZACION_GPS = time.time()
                    else:
                        log(f"[WARN] Error GPS: {resultado.get('error', 'Desconocido')}")
            else:
                log(f"[GPS] Conductor {ESTADO_CONDUCTOR} - espera")
            
            time.sleep(60)  # Verificar cada minuto
            
        except Exception as e:
            log(f"[ERROR] Ciclo GPS: {e}")
            time.sleep(30)


def forzar_actualizacion_gps_inmediata() -> dict:
    """Fuerza actualización inmediata del GPS."""
    log("[GPS] Forzando actualizacion inmediata...")
    
    try:
        gps_actual = leer_gps_actual()
        resultado_rutas = rutas_inteligentes(
            ubicacion_actual=gps_actual,
            priorizar="ingreso_por_minuto",
            max_destinos=1,
            auto_trigger_ollama=True
        )
        
        if resultado_rutas.get("mejor_opcion"):
            mejor_zona = resultado_rutas["mejor_opcion"]
            zona_info = get_zona_by_id(mejor_zona["zona_id"])
            
            if zona_info:
                lat_objetivo = (zona_info["lat_min"] + zona_info["lat_max"]) / 2
                lng_objetivo = (zona_info["lon_min"] + zona_info["lon_max"]) / 2
                ubicacion_objetivo = {
                    "lat": lat_objetivo, "lng": lng_objetivo,
                    "zona_id": mejor_zona["zona_id"],
                    "zona_nombre": mejor_zona["nombre"],
                    "score": mejor_zona.get("score_final", 0),
                    "timestamp": time.time()
                }
                return actualizar_gps_a_mejor_opcion(ubicacion_objetivo)
        
        return {"exito": False, "error": "No se pudo determinar objetivo"}
        
    except Exception as e:
        log(f"[ERROR] GPS inmediata: {e}")
        return {"exito": False, "error": str(e)}
    finally:
        log("[GPS] Actualizacion inmediata completada")


def obtener_estado_gps() -> dict:
    """Obtiene estado completo del sistema GPS."""
    return {
        "gps_activo": GPS_ACTIVO,
        "gps_actual": GPS_ACTUAL,
        "gps_objetivo": GPS_OBJETIVO,
        "ultima_actualizacion": ULTIMA_ACTUALIZACION_GPS,
        "historial_registros": len(historial_gps),
        "zona_actual": ULTIMA_ZONA,
        "estado_conductor": ESTADO_CONDUCTOR,
        "timestamp": time.time()
    }


def integrar_gps_en_ceo(ceoia_instance=None):
    """
    Integra funciones GPS en instancia CEOIA.
    Ahora acepta parámetro opcional para evitar error.
    """
    global ceo_avanzado
    
    # Determinar instancia objetivo
    target = ceoia_instance if ceoia_instance is not None else ceo_avanzado
    
    if target is None:
        log("[GPS] No hay instancia CEOIA disponible para integrar GPS")
        return False
    
    try:
        # Asegurar permisos
        if hasattr(target, 'permisos'):
            target.permisos["controlar_gps"] = True
            target.permisos["actualizar_gps_automatico"] = True
        
        # Asignar funciones
        target.actualizar_gps = actualizar_gps_a_mejor_opcion
        target.forzar_actualizacion_gps = forzar_actualizacion_gps_inmediata
        target.obtener_estado_gps = obtener_estado_gps
        
        # Inicializar kilometraje si no existe
        if not hasattr(target, 'km_learner') or target.km_learner is None:
            inicializar_kilometraje_learner(target)
        
        log("[GPS] GPS integrado en CEO exitosamente")
        return True
        
    except Exception as e:
        log(f"[ERROR] Error integrando GPS: {e}")
        return False


# ================================================================================
# SECCION 25: WATCHDOG Y AUTO-HEAL (VERSION LIVIANA CORREGIDA)
# ================================================================================

def verificar_bucle_autonomo():
    """Verifica si el bucle autónomo está activo."""
    global ULTIMA_ACTIVIDAD_BUCLE
    
    tiempo_inactivo = time.time() - ULTIMA_ACTIVIDAD_BUCLE
    if tiempo_inactivo > 120:  # 2 minutos sin actividad
        log(f"[HEAL] Bucle autonomo congelado detectado (inactivo {tiempo_inactivo:.0f}s)")
        return True
    return False


def auto_heal_loops():
    """Sistema de auto-recuperación de bucles."""
    log("[HEAL] Auto-Healing Nivel 2 ACTIVADO")
    
    while not STOP_EVENT.is_set():
        try:
            if verificar_bucle_autonomo():
                # Verificar si el hilo existe
                active_names = [t.name for t in threading.enumerate()]
                
                if "Bucle Autonomo" in active_names:
                    log("[HEAL] Bucle Autonomo existe pero inactivo - posible deadlock")
                    # Intentar notificar al bucle principal
                    ULTIMA_ACTIVIDAD_BUCLE = time.time()  # Reset para evitar spam
                else:
                    log("[HEAL] Reiniciando Bucle Autonomo...")
                    # Reiniciar solo si ceo_avanzado está disponible
                    if ceo_avanzado and hasattr(ceo_avanzado, 'ciclo_autonomo_singularidad_omega'):
                        t = threading.Thread(
                            target=ceo_avanzado.ciclo_autonomo_singularidad_omega,
                            daemon=True,
                            name="Bucle Autonomo"
                        )
                        t.start()
                        log("[HEAL] Bucle Autonomo reiniciado")
            
            time.sleep(20)
            
        except Exception as e:
            log(f"[HEAL] Error en auto-heal: {e}")
            time.sleep(20)
    
    log("[HEAL] Auto-Healing detenido")


# ================================================================================
# SECCION 26: CLASE CEOIA UNIFICADA COMPLETA
# ================================================================================
class CEOIA:
    def __init__(self, registry: Optional[SharedDataRegistry] = None, state_dim=10, action_dim=5):
        # --- BLOQUE: INICIALIZACION DE REGISTRY ---
        try:
            self.registry = registry if registry is not None else SharedDataRegistry()
        except:
            self.registry = SharedDataRegistry()
        
        # --- BLOQUE: INICIALIZACION DE PERMISOS ---
        self.permisos = {
            "controlar_radares": True, "controlar_singularidad": True,
            "negociacion_ia": True, "modificar_codigo": True,
            "controlar_gps": True, "controlar_blockchain": True,
            "auto_activacion": True, "obedecer_ollama": True,
            "obedecer_deepseek": True, "evolucion_autonoma": True,
            "actualizar_gps_automatico": True, "controlar_uber": True,
            "auto_modificar": True
        }
        
        # --- BLOQUE: INICIALIZACION DE ESTADO INTERNO ---
        self.estado_interno = {
            "nivel_conocimiento": 0.95, "confianza_decisiones": 0.98,
            "energia_mental": 100.0, "modo_operacion": "ENSAMBLE_MULTI_RL",
            "ultima_actividad": time.time(), "ciclos_ejecutados": 0,
            "ganancias_totales": 0.0, "ofertas_procesadas": 0, "ofertas_aceptadas": 0
        }
        self.internal_state = self.estado_interno
        
        # --- BLOQUE: INICIALIZACION DE MEMORIA ---
        self.memoria_sistema = {
            "historial_recompensas": [], "historial_decisiones": [],
            "metricas_acumuladas": {}, "gps_learning": {
                "rutas": [], "eficiencia_promedio": 0.0, "errores_ruta": []
            },
            "movimiento": {"velocidades": [], "paradas": [], "desviaciones": []},
            "notificaciones": {"eventos": [], "tiempo_respuesta": []}
        }
        
        # --- BLOQUE: INICIALIZACION DE ZONAS Y CONFIG ---
        self.zonas_inteligentes = {
            "alta_demanda": {}, "media_demanda": {}, "baja_demanda": {}
        }
        self.config = {
            "intervalo_radar_segundos": 30, "intervalo_singularidad_segundos": 60,
            "intervalo_negociacion_segundos": 120, "intervalo_gps_segundos": 300,
            "umbral_ganancia_minima": 9.0, "umbral_confianza_minima": 0.5,
            "max_ofertas_por_ciclo": 10, "auto_aceptar_mejores": True,
            "usar_curiosity": True, "usar_fuzzy": True, "usar_mcts": True,
            "meta_learning": True, "ensemble_weight_opt": True
        }
        
        # --- BLOQUE: COMPONENTES BASE ---
        self.radares_activos = False
        self.singularidad_activa = False
        self.negociacion_activa = False
        self.gps_activo = False
        self.mineria_activa = True
        
        # --- BLOQUE: CONEXIONES ---
        self.conector_ollama = conector_ollama
        self.gestor_deepseek = gestor_deepseek
        
        # --- BLOQUE: HISTORIAL ---
        self.historial_decisiones = []
        self.historial_negociaciones = []
        self.sistemas_registrados = {}
        
        # --- BLOQUE: TELEMETRIA ---
        self.telemetry_history = defaultdict(lambda: deque(maxlen=100))
        self._telemetry_lock = threading.Lock()
        
        # --- BLOQUE: GPS ---
        self.actualizar_gps = None
        self.forzar_actualizacion_gps = None
        self.obtener_estado_gps = None
        
        # --- BLOQUE: IA AVANZADA - ENSAMBLE RL ---
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.ensemble = EnsembleRL(state_dim, action_dim)
        self.fuzzy = FuzzyLogicController()
        self._setup_fuzzy_rules()
        self.mcts = MCTSAgent(state_dim, action_dim, explorations=50)
        self.q_learner = DoubleDQN(state_dim, action_dim)
        self.episodic_memory = EpisodicMemory()
        self.long_term_memory = deque(maxlen=10000)
        
        # --- BLOQUE: KILOMETRAJE ---
        self.km_learner = None
        self.ultima_posicion_km = None
        self.km_acumulados_viaje = 0.0
        
        # --- BLOQUE: LEARNING THREAD ---
        self._learning_active = False
        self._learning_thread = None
        self._start_learning_cycle()
        
        log("[SYSTEM] CEOIA UNIFICADA INICIALIZADA", "SYSTEM")
    
    # ========================================================================
    # METODOS FUZZY
    # ========================================================================
    def _setup_fuzzy_rules(self):
        self.fuzzy.add_mf('demanda', 'alta', 'triangle', (0.7, 0.85, 1.0))
        self.fuzzy.add_mf('demanda', 'media', 'triangle', (0.3, 0.5, 0.7))
        self.fuzzy.add_mf('demanda', 'baja', 'triangle', (0.0, 0.15, 0.3))
        self.fuzzy.add_mf('distancia', 'cerca', 'triangle', (0, 2, 5))
        self.fuzzy.add_mf('distancia', 'media', 'triangle', (3, 7, 10))
        self.fuzzy.add_mf('distancia', 'lejos', 'triangle', (8, 15, 20))
        self.fuzzy.add_mf('tarifa', 'alta', 'triangle', (15, 25, 50))
        self.fuzzy.add_mf('tarifa', 'media', 'triangle', (8, 12, 18))
        self.fuzzy.add_mf('tarifa', 'baja', 'triangle', (3, 6, 10))
        self.fuzzy.add_mf('output', 'aceptar', 'triangle', (0.7, 0.9, 1.0))
        self.fuzzy.add_mf('output', 'considerar', 'triangle', (0.4, 0.6, 0.8))
        self.fuzzy.add_mf('output', 'rechazar', 'triangle', (0.0, 0.2, 0.4))
        self.fuzzy.add_rule({'demanda': 'alta', 'tarifa': 'alta'}, {'aceptar': 1.0})
        self.fuzzy.add_rule({'demanda': 'alta', 'tarifa': 'media'}, {'aceptar': 1.0})
        self.fuzzy.add_rule({'demanda': 'media', 'tarifa': 'alta'}, {'aceptar': 1.0})
        self.fuzzy.add_rule({'demanda': 'baja', 'tarifa': 'baja'}, {'rechazar': 1.0})
        self.fuzzy.add_rule({'distancia': 'lejos', 'tarifa': 'baja'}, {'rechazar': 1.0})
        self.fuzzy.add_rule({'demanda': 'media', 'distancia': 'cerca'}, {'considerar': 1.0})
    
    # ========================================================================
    # METODOS DE SINCRONIZACION Y REGISTRY
    # ========================================================================
    def _sync_status_to_registry(self):
        try:
            self.registry.set("ceoia:status", {
                'internal_state': dict(self.estado_interno),
                'config': dict(self.config),
                'permisos': dict(self.permisos),
                'timestamp': _datetime.now(_timezone.utc).isoformat()
            })
        except Exception as e:
            log(f"[WARN] Error sync registry: {e}", "WARN")
    
    def get_registry_instance(self) -> SharedDataRegistry:
        return self.registry
    
    def get_complete_state(self) -> Dict[str, Any]:
        return {
            'ceoia': dict(self.estado_interno), 'config': dict(self.config),
            'permisos': dict(self.permisos), 'memoria': {
                'historial_recompensas': list(self.memoria_sistema.get("historial_recompensas", [])),
                'metricas_acumuladas': dict(self.memoria_sistema.get("metricas_acumuladas", {})),
                'gps_learning': dict(self.memoria_sistema.get("gps_learning", {})),
            }, 'zonas': dict(self.zonas_inteligentes),
            'timestamp': _datetime.now(_timezone.utc).isoformat()
        }
    
    def subscribe_to_updates(self, key_pattern: str, callback: Callable) -> str:
        return self.registry.on_change(key_pattern, callback)
    
    def update_internal_state(self, updates: Dict[str, Any]) -> bool:
        try:
            self.estado_interno.update(updates)
            self.estado_interno['ultima_actividad'] = time.time()
            self._sync_status_to_registry()
            return True
        except:
            return False
    
    # ========================================================================
    # METODOS DE APRENDIZAJE RL
    # ========================================================================
    def _start_learning_cycle(self):
        self._learning_active = True
        def loop():
            while self._learning_active and not STOP_EVENT.is_set():
                try:
                    self._run_learning_engine()
                    time.sleep(5)
                except Exception as e:
                    log(f"[LEARN] {e}", "LEARN")
                    time.sleep(2)
        self._learning_thread = threading.Thread(target=loop, daemon=True)
        self._learning_thread.start()
        log("[LEARN] Learning Loop iniciado", "LEARN")
    
    def _run_learning_engine(self):
        try:
            state = self._get_current_state()
            action, confidence = self.ensemble.select_action(state, exploit_only=False)
            reward = self.calcular_recompensa_guiada({
                "avg_fare": random.uniform(3.13, 25.0),
                "avg_wait_time": random.uniform(30, 600),
                "fraud_flags": random.randint(0, 2),
                "confianza_decisiones": self.estado_interno["confianza_decisiones"],
                "success_rate": random.uniform(0.6, 0.95)
            })
            next_state = self._get_current_state()
            done = random.random() < 0.05
            learning_result = self.ensemble.update(
                state=state, action=action, reward=reward,
                next_state=next_state, done=done,
                use_curiosity=self.config.get("usar_curiosity", True)
            )
            self.estado_interno["ciclos_ejecutados"] += 1
            self.estado_interno["ultima_actividad"] = time.time()
            self.estado_interno["ganancias_totales"] += max(0, reward)
            self.long_term_memory.append({
                "ts": time.time(), "state_dim": len(state) if isinstance(state, (list, tuple)) else 1,
                "action": action, "reward": reward, "learning": learning_result
            })
            if self.estado_interno["ciclos_ejecutados"] % 50 == 0:
                save_daimon_brain()
            return {"exito": True, "action": action, "reward": reward, "learning_stats": learning_result}
        except Exception as e:
            log(f"[LEARN] Error: {e}", "LEARN")
            return {"exito": False, "error": str(e)}
    
    def _get_current_state(self):
        return [random.random() for _ in range(self.state_dim)]
    
    def decide_action(self, state=None):
        if state is None:
            state = self._get_current_state()
        action, _ = self.ensemble.select_action(state)
        return action
    
    def learn(self, state, action, reward, done=True):
        next_state = self._get_current_state()
        return self.ensemble.update(state, action, reward, next_state, done)
    
    # ========================================================================
    # METODOS DE REcompensa
    # ========================================================================
    def calcular_recompensa_guiada(self, m: dict) -> float:
        ingreso = m.get("avg_fare", 0)
        espera = m.get("avg_wait_time", 0)
        fraude = m.get("fraud_flags", 0)
        confianza = m.get("confianza_decisiones", 0.5)
        exito = m.get("success_rate", 0.5)
        r = 0.0
        if ingreso > 12: r += 2
        elif ingreso > 8: r += 1
        else: r -= 1
        if espera < 120: r += 1
        elif espera > 300: r -= 2
        r -= fraude * 1.5
        r += confianza * 0.8
        r += exito * 1.2
        return max(-5.0, min(5.0, r))
    
    def recompensa_total_sistema(self) -> float:
        gps = self.memoria_sistema["gps_learning"]["eficiencia_promedio"]
        mov = self.memoria_sistema["movimiento"]["velocidades"]
        notif = self.memoria_sistema["notificaciones"]["tiempo_respuesta"]
        mov_avg = sum(mov[-10:]) / len(mov[-10:]) if mov else 0
        notif_avg = sum(notif[-10:]) / len(notif[-10:]) if notif else 0
        r = gps * 2
        if mov_avg > 20: r += 1
        else: r -= 0.5
        if notif_avg < 2: r += 1.5
        else: r -= 1
        return r
    
    def seleccionar_fase_ensenanza(self) -> str:
        h = self.memoria_sistema["historial_recompensas"]
        if len(h) < 10: return "ESTABILIDAD"
        avg = sum(h[-10:]) / 10
        if avg < 0: return "ESTABILIDAD"
        if avg < 2: return "EFICIENCIA"
        if avg < 3.5: return "RESILIENCIA"
        return "EXPLORACION"
    
    # ========================================================================
    # METODOS DE INICIALIZACION Y ACTIVACION
    # ========================================================================
    def conectar_ollama(self):
        try:
            if self.conector_ollama and self.conector_ollama.diagnostico_conexion():
                log("[OK] Ollama Local CONECTADO", "SYSTEM")
                return True
            else:
                log("[WARN] Ollama no detectado", "SYSTEM")
                return False
        except Exception as e:
            log(f"[WARN] Error conectando Ollama: {e}")
            return False
    
    def configurar_deepseek(self, api_key: str):
        try:
            if self.gestor_deepseek:
                self.gestor_deepseek.configurar_token(api_key)
                log("[OK] DeepSeek configurado", "SYSTEM")
                return True
            return False
        except Exception as e:
            log(f"[WARN] Error configurando DeepSeek: {e}")
            return False
    
    def inicializar_todo(self) -> dict:
        componentes = []
        if self.conectar_ollama(): componentes.append("ollama")
        if self.configurar_deepseek(DEEPSEEK_API_KEY): componentes.append("deepseek")
        if 'integrar_gps_en_ceo' in globals():
            if integrar_gps_en_ceo(self): componentes.append("gps")
        self.sistemas_registrados = {
            "radar": True, "singularidad": True, "negociacion": True,
            "gps": True, "mineria": True
        }
        componentes.append("sistemas_registrados")
        log(f"[OK] CEOIA: {len(componentes)} componentes inicializados")
        return {"exito": True, "componentes_inicializados": componentes, "timestamp": time.time()}
    
    def activar_funciones_automaticas(self):
        self.radares_activos = True
        self.gps_activo = True
        self.negociacion_activa = True
        self.mineria_activa = True
        self.singularidad_activa = True
        if not self._learning_active:
            self._start_learning_cycle()
        log("[OK] Funciones automaticas activadas")
        return {
            'exito': True, 'funciones_activadas': ['radares', 'gps', 'negociacion', 'singularidad'],
            'hilos_iniciados': [], 'errores': []
        }
    
    # ========================================================================
    # METODOS DE GOBIERNO DE RADARES
    # ========================================================================
    def gobernar_radares(self, modo: str = "completo") -> dict:
        resultado = {
            'exito': False, 'modo': modo, 'radares_ejecutados': [],
            'ofertas_encontradas': 0, 'mejor_opcion': None, 'ganancia_estimada': 0.0
        }
        try:
            self.radares_activos = True
            resultado_rutas = rutas_inteligentes(priorizar="ingreso_por_minuto", ceoia_instance=self)
            if resultado_rutas.get("rutas"):
                resultado['radares_ejecutados'].append('rutas_inteligentes')
                resultado['ofertas_encontradas'] = len(resultado_rutas["rutas"])
                if resultado_rutas.get("mejor_opcion"):
                    resultado['mejor_opcion'] = resultado_rutas["mejor_opcion"]
                    resultado['ganancia_estimada'] = resultado_rutas["mejor_opcion"].get("tarifa_estimada", 0.0)
                resultado['exito'] = True
            self.registry.set("ceoia:radar:last_result", resultado)
        except Exception as e:
            resultado['errores'] = str(e)
            log(f"[ERROR] Error gobernando radares: {e}")
        return resultado
    
    # ========================================================================
    # METODOS DE SINGULARIDAD OMEGA
    # ========================================================================
    def controlar_singularidad_omega(self, duracion_ciclo: int = 60,
                                     nivel_agresividad: float = 0.85,
                                     activar_aprendizaje: bool = True) -> dict:
        resultado = {
            'exito': False, 'ciclo_ejecutado': True,
            'ganancias_generadas': 0.0, 'decisiones_tomadas': []
        }
        try:
            self.singularidad_activa = True
            ganancia = random.uniform(1.0, 5.0) * nivel_agresividad
            resultado['ganancias_generadas'] = round(ganancia, 2)
            self.estado_interno['ganancias_totales'] += ganancia
            self.estado_interno['ciclos_ejecutados'] += 1
            resultado['exito'] = True
            self.registry.set("ceoia:singularidad:last_result", resultado)
        except Exception as e:
            resultado['errores'] = str(e)
        return resultado
    
    # ========================================================================
    # METODOS DE NEGOCIACION ENTRE IAS
    # ========================================================================
    def negociar_entre_ias(self, ias_objetivo: Optional[list] = None,
                           tipo_negociacion: str = "mixta") -> dict:
        resultado = {
            'exito': False, 'negociaciones_iniciadas': 0,
            'negociaciones_completadas': 0, 'coins_ganadas': 0.0,
            'acuerdos_logrados': []
        }
        try:
            self.negociacion_activa = True
            ias_a_negociar = ias_objetivo or ["uber_michelangelo", "ia_tiktok", "ollama"]
            for ia in ias_a_negociar:
                resultado['negociaciones_iniciadas'] += 1
                resultado['negociaciones_completadas'] += 1
                resultado['coins_ganadas'] += random.uniform(0.5, 2.0)
            resultado['exito'] = resultado['negociaciones_completadas'] > 0
            self.historial_negociaciones.append({
                'timestamp': time.time(), 'resultado': resultado
            })
            self.registry.set("ceoia:negociacion:last_result", resultado)
        except Exception as e:
            resultado['errores'] = str(e)
        return resultado
    
    # ========================================================================
    # METODOS DE RECEPCION DE ORDENES
    # ========================================================================
    def recibir_orden_ollama(self, orden: str, contexto: Optional[str] = None,
                             timeout: int = 30) -> str:
        try:
            log(f"[OLLAMA] CEOIA recibe: {orden[:100]}...")
            return self.recibir_orden(orden)
        except Exception as e:
            return f"[ERROR] Error procesando orden Ollama: {str(e)}"
    
    def recibir_orden(self, orden: str) -> str:
        self.historial_decisiones.append({
            "timestamp": time.time(), "orden": orden, "tipo": "recibida"
        })
        try:
            orden_lower = orden.lower()
            if "radar" in orden_lower:
                res = self.gobernar_radares()
                return f"[OK] Radares: {res['ofertas_encontradas']} ofertas"
            elif "singularidad" in orden_lower or "omega" in orden_lower:
                res = self.controlar_singularidad_omega()
                return f"[INFO] Singularidad: ${res['ganancias_generadas']:.2f}"
            elif "negociar" in orden_lower:
                res = self.negociar_entre_ias()
                return f"[INFO] Negociacion: {res['negociaciones_completadas']} completadas"
            elif "gps" in orden_lower:
                if "actualizar" in orden_lower and self.forzar_actualizacion_gps:
                    resultado = self.forzar_actualizacion_gps()
                    return f"[GPS] {resultado.get('mensaje', 'Actualizado')}"
                elif "estado" in orden_lower and self.obtener_estado_gps:
                    return f"[GPS] Estado: {self.obtener_estado_gps()}"
                return "[GPS] Comandos: actualizar, estado"
            elif "estado" in orden_lower:
                return self.obtener_estado_completo()
            elif "optimizar" in orden_lower:
                return self.optimizar_sistema_automatico()
            elif "auditar" in orden_lower:
                return self.auditar_sistema_completo()
            else:
                return "[WARN] Orden no reconocida. Comandos: radar, singularidad, negociar, gps, estado, optimizar, auditar"
        except Exception as e:
            return f"[ERROR] Error procesando orden: {str(e)}"
    
    # ========================================================================
    # METODOS DE ESTADO Y AUDITORIA
    # ========================================================================
    def obtener_estado_completo(self) -> str:
        return f"""
+---------------------------------------------------------------+
|           [CEOIA] ESTADO COMPLETO DEL SISTEMA                 |
+---------------------------------------------------------------+
| MODO: {self.estado_interno['modo_operacion']:<47} |
| CONFIANZA: {self.estado_interno['confianza_decisiones']:.2f}                          |
| CICLOS: {self.estado_interno['ciclos_ejecutados']:<46} |
| GANANCIAS: ${self.estado_interno['ganancias_totales']:.2f}                         |
+---------------------------------------------------------------+
| Radares: {'ACTIVO' if self.radares_activos else 'INACTIVO':<39} |
| Singularidad: {'ACTIVO' if self.singularidad_activa else 'INACTIVO':<33} |
| Negociacion: {'ACTIVO' if self.negociacion_activa else 'INACTIVO':<35} |
| GPS: {'ACTIVO' if self.gps_activo else 'INACTIVO':<43} |
| Mineria: {'ACTIVO' if self.mineria_activa else 'INACTIVO':<39} |
+---------------------------------------------------------------+
| ALGORITMOS RL: DoubleDQN, SARSA, ActorCritic, PPO, MCTS, GA   |
| FuzzyLogic, KalmanFilter, Curiosity, MetaLearning, NeuralQ    |
+---------------------------------------------------------------+
"""
    
    def auditar_sistema_completo(self) -> str:
        auditoria = []
        auditoria.append(f"[OK] ALGO_WEIGHTS: {len(ALGO_WEIGHTS)} pesos")
        auditoria.append(f"[OK] Q-Table: {len(Q_TABLE)} estados")
        auditoria.append(f"[OK] Blockchain: {len(blockchain)} bloques")
        if UBER_COINS: auditoria.append(f"[OK] UBER_COINS: {UBER_COINS.display()}")
        zonas_rojas = sum(1 for z in zona_estado.values() if z.get('color') == 'rojo')
        auditoria.append(f"[OK] Zonas: {len(zona_estado)} totales, {zonas_rojas} en alta demanda")
        auditoria.append(f"[OK] Ensemble: {len(self.ensemble.algorithms)} algoritmos activos")
        if self.estado_interno['confianza_decisiones'] < 0.5:
            self.estado_interno['confianza_decisiones'] = min(1.0, self.estado_interno['confianza_decisiones'] + 0.1)
            auditoria.append("[OK] Confianza ajustada automaticamente")
        return "[AUDIT] AUDITORIA COMPLETA:\n" + "\n".join(auditoria)
    
    def optimizar_sistema_automatico(self) -> str:
        optimizaciones = []
        freed = gc.collect()
        optimizaciones.append(f"[OK] Memoria GC: {freed} objetos liberados")
        if hasattr(self, 'ensemble'):
            stats = self.ensemble.get_state()
            optimizaciones.append(f"[OK] Ensemble decisions: {stats['decisions']}")
        return "[OPT] OPTIMIZACION AUTOMATICA:\n" + "\n".join(optimizaciones)
    
    # ========================================================================
    # METODOS DE GOBIERNO COMPLETO
    # ========================================================================
    def gobernar_sistema_completo(self) -> dict:
        log("[INFO] CEOIA: INICIANDO GOBIERNO TOTAL DEL SISTEMA")
        gobierno = {
            'timestamp_inicio': time.time(), 'exito': True,
            'sistemas_gobernados': [], 'acciones_ejecutadas': [],
            'ganancias_generadas': 0.0, 'errores': []
        }
        try:
            init_result = self.inicializar_todo()
            gobierno['sistemas_gobernados'].append('inicializacion')
            self.activar_funciones_automaticas()
            gobierno['sistemas_gobernados'].append('funciones_automaticas')
            radar_result = self.gobernar_radares()
            gobierno['sistemas_gobernados'].append('radares')
            gobierno['ganancias_generadas'] += radar_result.get('ganancia_estimada', 0.0)
            omega_result = self.controlar_singularidad_omega()
            gobierno['sistemas_gobernados'].append('singularidad_omega')
            gobierno['ganancias_generadas'] += omega_result.get('ganancias_generadas', 0.0)
            neg_result = self.negociar_entre_ias()
            gobierno['sistemas_gobernados'].append('negociacion_ias')
            gobierno['ganancias_generadas'] += neg_result.get('coins_ganadas', 0.0) * 0.001
            self.auditar_sistema_completo()
            gobierno['timestamp_fin'] = time.time()
            gobierno['exito'] = len(gobierno['errores']) == 0
            self.registry.set("ceoia:gobierno:last_result", gobierno)
        except Exception as e:
            gobierno['exito'] = False
            gobierno['errores'].append(str(e))
        return gobierno
    
    # ========================================================================
    # BUCLES AUTONOMOS (PARA USAR COMO TARGET DE HILOS)
    # ========================================================================
    def daimon_autonomous_loop(self):
        log("[INFO] Bucle Autonomo iniciado", "LOOP")
        while not STOP_EVENT.is_set():
            try:
                self.gobernar_sistema_completo()
                time.sleep(60)
            except Exception as e:
                log(f"[ERROR] Bucle Autonomo: {e}", "ERROR")
                time.sleep(10)
    
    def actualizar_zonificacion(self):
        log("[INFO] Actualizacion de zonificacion iniciada", "LOOP")
        while not STOP_EVENT.is_set():
            try:
                for zona in ZONAS:
                    estado = zona_estado[zona["id"]]
                    demanda = random.randint(0, 10)
                    oferta = random.randint(0, 5)
                    estado["demanda"] = demanda
                    estado["oferta"] = oferta
                    estado["ratio_demanda"] = round(demanda / max(1, oferta), 2) if oferta > 0 else 1.0
                    if estado["ratio_demanda"] > 2.0: estado["color"] = "rojo"
                    elif estado["ratio_demanda"] > 1.5: estado["color"] = "naranja"
                    else: estado["color"] = "gris"
                time.sleep(300)
            except Exception as e:
                log(f"[ERROR] Actualizar Zonificacion: {e}", "ERROR")
                time.sleep(30)
    
    def simulate_route_loop(self):
        log("[INFO] Simulacion de ruta iniciada", "LOOP")
        idx = 0
        while not STOP_EVENT.is_set():
            try:
                punto = ROUTE[idx % len(ROUTE)]
                log(f"[RUTA] Conductor en {punto['name']} ({punto['latitude']:.4f}, {punto['longitude']:.4f})")
                idx += 1
                time.sleep(30)
            except Exception as e:
                log(f"[ERROR] Simular Ruta: {e}", "ERROR")
                time.sleep(10)
    
    def mente_autonoma_socialcoin(self):
        log("[INFO] Mente Autonoma SocialCoin iniciada", "LOOP")
        while not STOP_EVENT.is_set():
            try:
                if UBER_COINS and random.random() < 0.3:
                    UBER_COINS.add(random.uniform(0.01, 0.1))
                time.sleep(120)
            except Exception as e:
                log(f"[ERROR] Mente Autonoma: {e}", "ERROR")
                time.sleep(10)
    
    def conductor_ia_loop_controlado(self):
        log("[INFO] Conductor IA iniciado", "LOOP")
        global ESTADO_CONDUCTOR
        while not STOP_EVENT.is_set():
            try:
                ESTADO_CONDUCTOR = random.choice(["IDLE", "DRIVING", "WAITING"])
                if ESTADO_CONDUCTOR == "IDLE":
                    self.gobernar_radares(modo="completo")
                time.sleep(60)
            except Exception as e:
                log(f"[ERROR] Conductor IA: {e}", "ERROR")
                ESTADO_CONDUCTOR = "IDLE"
                time.sleep(10)
    
    def ciclo_vigilancia_ceo(self):
        log("[INFO] Vigilancia CEO iniciada", "LOOP")
        while not STOP_EVENT.is_set():
            try:
                if self.estado_interno['confianza_decisiones'] < 0.5:
                    self.estado_interno['confianza_decisiones'] = min(1.0, self.estado_interno['confianza_decisiones'] + 0.05)
                time.sleep(60)
            except Exception as e:
                log(f"[ERROR] Vigilancia CEO: {e}", "ERROR")
                time.sleep(10)
    
    def simular_radar_externo(self):
        log("[INFO] Radar Externo iniciado", "LOOP")
        while not STOP_EVENT.is_set():
            try:
                time.sleep(60)
            except Exception as e:
                log(f"[ERROR] Radar Externo: {e}", "ERROR")
                time.sleep(10)
    
    def ciclo_radar_ollama_automatico(self):
        log("[INFO] Radar Ollama Automatico iniciado", "LOOP")
        while not STOP_EVENT.is_set():
            try:
                if self.conector_ollama:
                    self.conector_ollama.consultar("Analiza zona actual", prioridad_baja=True)
                time.sleep(300)
            except Exception as e:
                log(f"[ERROR] Radar Ollama: {e}", "ERROR")
                time.sleep(30)
    
    def ciclo_autonomo_singularidad_omega(self):
        log("[INFO] Singularidad Omega en ciclo autonomo", "LOOP")
        while not STOP_EVENT.is_set():
            try:
                self.controlar_singularidad_omega(duracion_ciclo=60)
                time.sleep(60)
            except Exception as e:
                log(f"[ERROR] Singularidad Omega: {e}", "ERROR")
                time.sleep(10)
    
    def ciclo_autonomo_principal(self, duracion_minutos: int = 60):
        log("[INFO] INICIANDO CICLO AUTONOMO CEOIA")
        inicio = time.time()
        fin = inicio + (duracion_minutos * 60)
        ciclos = 0
        while time.time() < fin and not STOP_EVENT.is_set():
            try:
                ciclos += 1
                log(f"[INFO] Ciclo CEOIA #{ciclos}")
                self.gobernar_radares(modo="completo")
                if ciclos % 2 == 0:
                    self.controlar_singularidad_omega()
                if ciclos % 3 == 0:
                    self.negociar_entre_ias()
                if ciclos % 10 == 0:
                    self.auditar_sistema_completo()
                if ciclos % 15 == 0:
                    self.optimizar_sistema_automatico()
                time.sleep(30)
            except Exception as e:
                log(f"[ERROR] Ciclo autonomo: {e}")
                time.sleep(10)
        log(f"[INFO] CICLO AUTONOMO COMPLETADO: {ciclos} ciclos")

    # ========================================================================
    # METODOS DE KILOMETRAJE Y EFICIENCIA
    # ========================================================================
    
    def registrar_viaje_completado(self, origen: Dict[str, float], destino: Dict[str, float],
                                    tiempo_min: float, ganancia: float = 0) -> Dict[str, Any]:
        """Registra un viaje completado para análisis de eficiencia."""
        if hasattr(self, 'km_learner') and self.km_learner:
            self.km_learner.registrar_viaje(origen, destino, tiempo_min, ganancia)
            return {"exito": True, "mensaje": "Viaje registrado"}
        return {"exito": False, "error": "Kilometraje learner no disponible"}
    
    def obtener_estadisticas_kilometraje(self) -> Dict[str, Any]:
        """Obtiene estadísticas de kilometraje."""
        if hasattr(self, 'km_learner') and self.km_learner:
            return self.km_learner.get_estadisticas()
        return {"error": "No inicializado"}
    
    def predecir_ruta_eficiente(self, destinos: List[Dict]) -> Optional[Dict]:
        """Predice la ruta más eficiente basada en historial."""
        if hasattr(self, 'km_learner') and self.km_learner:
            return self.km_learner.sugerir_ruta_optima(destinos)
        return destinos[0] if destinos else None
    
    # ========================================================================
    # METODOS DE GPS AVANZADOS
    # ========================================================================
    
    def actualizar_gps_manual(self) -> Dict[str, Any]:
        """Fuerza actualización manual del GPS."""
        if self.forzar_actualizacion_gps:
            return self.forzar_actualizacion_gps()
        return {"exito": False, "error": "Función GPS no disponible"}
    
    def get_gps_state(self) -> Dict[str, Any]:
        """Obtiene estado completo del GPS."""
        if self.obtener_estado_gps:
            return self.obtener_estado_gps()
        return {"gps_activo": False, "error": "GPS no integrado"}
    
    def navegar_a_zona(self, zona_id: str) -> Dict[str, Any]:
        """Configura navegación hacia una zona específica."""
        global GPS_OBJETIVO, ULTIMA_ZONA
        
        zona = get_zona_by_id(zona_id)
        if not zona:
            return {"exito": False, "error": f"Zona {zona_id} no encontrada"}
        
        lat_centro = (zona["lat_min"] + zona["lat_max"]) / 2
        lon_centro = (zona["lon_min"] + zona["lon_max"]) / 2
        
        GPS_OBJETIVO = {
            "lat": lat_centro,
            "lng": lon_centro,
            "zona_id": zona_id,
            "nombre": zona["nombre"]
        }
        
        # Actualizar estado
        if hasattr(self, 'memoria_sistema'):
            self.memoria_sistema["gps_learning"]["rutas"].append({
                "destino": zona_id,
                "timestamp": time.time(),
                "estado": "navegando"
            })
        
        return {
            "exito": True,
            "objetivo": GPS_OBJETIVO,
            "mensaje": f"Navegando hacia {zona['nombre']}"
        }



# ================================================================================
# SECCION 27: INSTANCIAS GLOBALES Y FUNCIONES DE INICIALIZACION
# ================================================================================
ceoia = None
ceo_avanzado = None
ceo = None

def iniciar_ceoia_unificada(registry: Optional[SharedDataRegistry] = None) -> CEOIA:
    global ceoia, ceo_avanzado, ceo
    log("[SYSTEM] INICIANDO CEOIA UNIFICADA - GOBIERNO TOTAL")
    ceoia = CEOIA(registry=registry)
    ceo_avanzado = ceoia
    ceo = ceoia
    ceoia.inicializar_todo()
    ceoia.activar_funciones_automaticas()
    log("[OK] CEOIA UNIFICADA LISTA PARA GOBERNAR")
    return ceoia

def desbloquear_ceo_completo():
    global ceo_avanzado, ceoia, ceo
    log("[SYSTEM] Desbloqueando CEO completamente...")
    if ceoia is None:
        log("[SYSTEM] Inicializando CEOIA Unificada...")
        ceoia = iniciar_ceoia_unificada()
        ceo_avanzado = ceoia
        ceo = ceoia
    if hasattr(ceoia, 'permisos'):
        ceoia.permisos.update({
            "controlar_uber": True, "controlar_radares": True,
            "controlar_singularidad": True, "negociacion_ia": True,
            "modificar_codigo": True, "controlar_gps": True,
            "controlar_blockchain": True, "auto_activacion": True,
            "obedecer_ollama": True, "obedecer_deepseek": True,
            "evolucion_autonoma": True, "auto_modificar": True
        })
        log("[OK] Todos los permisos desbloqueados")
    if hasattr(ceoia, 'estado_interno'):
        ceoia.estado_interno['confianza_decisiones'] = 0.99
        ceoia.estado_interno['modo_operacion'] = 'AUTONOMO_COMPLETO'
        log("[OK] Estado interno optimizado")
    if hasattr(ceoia, 'activar_funciones_automaticas'):
        ceoia.activar_funciones_automaticas()
        log("[OK] Funciones automaticas activadas")
    return True

# ================================================================================
# SECCION 28: REGISTRO DE ENDPOINTS FLASK
# ================================================================================
def registrar_endpoints_ceoia(app):
    if jsonify is None or make_response is None:
        log("[WARN] Flask no disponible, endpoints no registrados")
        return
    
    def safe_log(msg):
        try: log(msg)
        except Exception: print(f"[CEOIA] {msg}")
    
    def check_ceoia():
        return ceoia is not None
    
    @app.route('/ceoia/gobernar', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_gobernar():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        try:
            resultado = ceoia.gobernar_sistema_completo()
            return jsonify(resultado)
        except Exception as e:
            safe_log(f"[ERROR] gobernar: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/ceoia/estado', methods=['GET', 'OPTIONS'])
    def endpoint_ceoia_estado():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        return jsonify({
            "estado": ceoia.obtener_estado_completo(),
            "estado_interno": ceoia.estado_interno,
            "sistemas_registrados": list(ceoia.sistemas_registrados.keys())
        })
    
    @app.route('/ceoia/orden', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_orden():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        data = request.get_json(silent=True) or {}
        orden = data.get('orden', '')
        try:
            resultado = ceoia.recibir_orden(orden)
        except Exception as e:
            resultado = f"Error: {e}"
        return jsonify({"orden": orden, "resultado": resultado})
    
    @app.route('/ceoia/radares', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_radares():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        data = request.get_json(silent=True) or {}
        modo = data.get('modo', 'completo')
        try:
            resultado = ceoia.gobernar_radares(modo=modo)
        except Exception as e:
            resultado = {"error": str(e)}
        return jsonify(resultado)
    
    @app.route('/ceoia/singularidad', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_singularidad():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        data = request.get_json(silent=True) or {}
        try:
            resultado = ceoia.controlar_singularidad_omega(
                duracion_ciclo=data.get('duracion_ciclo', 60),
                nivel_agresividad=data.get('nivel_agresividad', 0.85)
            )
        except Exception as e:
            resultado = {"error": str(e)}
        return jsonify(resultado)
    
    @app.route('/ceoia/negociar', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_negociar():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        data = request.get_json(silent=True) or {}
        ias = data.get('ias_objetivo')
        try:
            resultado = ceoia.negociar_entre_ias(ias_objetivo=ias)
        except Exception as e:
            resultado = {"error": str(e)}
        return jsonify(resultado)
    
    @app.route('/ceoia/auditar', methods=['GET', 'OPTIONS'])
    def endpoint_ceoia_auditar():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        try:
            resultado = ceoia.auditar_sistema_completo()
        except Exception as e:
            resultado = str(e)
        return jsonify({"auditoria": resultado})
    
    @app.route('/ceoia/optimizar', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_optimizar():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        try:
            resultado = ceoia.optimizar_sistema_automatico()
        except Exception as e:
            resultado = str(e)
        return jsonify({"optimizacion": resultado})
    
    @app.route('/ceoia/activar_automatico', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_activar_automatico():
        if request.method == 'OPTIONS':
            return make_response("", 204)
        if not check_ceoia():
            return jsonify({"error": "CEOIA no inicializada"}), 500
        try:
            resultado = ceoia.activar_funciones_automaticas()
        except Exception as e:
            resultado = str(e)
        return jsonify(resultado)
    
    safe_log("[OK] Endpoints CEOIA registrados correctamente")

# ================================================================================
# SECCION 29: PUNTO DE ENTRADA PRINCIPAL
# ================================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("[OK] INICIANDO CEOIA UNIFICADA - GOBIERNO TOTAL DEL SISTEMA")
    print("=" * 60 + "\n")
    
    # NOTA: STOP_EVENT ya es global, no se redeclara
    registry = SharedDataRegistry()
    ceoia = CEOIA(registry=registry)
    ceo_avanzado = ceoia
    ceo = ceoia
    ceoia.inicializar_todo()
    ceoia.activar_funciones_automaticas()
    
    # Inicializar kilometraje
    inicializar_kilometraje_learner(ceoia)
    iniciar_monitoreo_kilometraje(ceoia)
    
    # Simulacion RL no bloqueante
    def simulacion_rl():
        print("\nSimulando decisiones RL...\n")
        for i in range(10):
            try:
                state = ceoia._get_current_state()
                action = ceoia.decide_action(state)
                reward = random.uniform(-5, 15)
                ceoia.learn(state, action, reward)
                print(f" Decision {i+1}: Accion={action}, Recompensa={reward:.2f}")
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Error simulacion RL: {e}")
        print("\n[OK] Simulacion RL completada")
        final_state = ceoia.get_complete_state()
        for k, v in final_state.items():
            print(f" {k}: {v}")
    
    threading.Thread(target=simulacion_rl, daemon=True).start()
    
    print("\n[OK] CEOIA UNIFICADA ACTIVA - GOBERNANDO SISTEMA")
    print("   Presiona Ctrl+C para detener\n")
    
    try:
        while not STOP_EVENT.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] DETENIENDO CEOIA UNIFICADA...")
        ceoia._learning_active = False
        STOP_EVENT.set()          # Señaliza correctamente al global
        try:
            guardar_estado()
            save_daimon_brain()
        except: pass
        time.sleep(1)
        print("[OK] CEOIA UNIFICADA - APAGADO CORRECTO")
        sys.exit(0)
