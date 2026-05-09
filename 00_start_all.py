# ================================================================================
# SECCION 1: SYMBIOSIS V4 - ORQUESTADOR CON ARQUITECTURA VERIFICADA (POTENCIADO)
# ================================================================================
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestador principal con diagnostico mejorado, inyeccion de estado completa
y sincronizacion de modulos para Termux/Android - Python >= 3.6

Flujo: HTML -> Parte7 -> [2,3,4,9] -> Parte5 -> Parte1 -> OK
"""

# ================================================================================
# SECCION 2: IMPORTACIONES ESTANDAR
# ================================================================================
import os
import sys
import time
import uuid
import json
import copy
import hashlib
import threading
import socket
import signal
import importlib.util
import traceback
import gc
import subprocess
import inspect
import types
from pathlib import Path
from datetime import datetime, timezone
from collections import deque, defaultdict
from fnmatch import fnmatch
from typing import Dict, List, Optional, Callable, Any

# ================================================================================
# SECCION 3: CONFIGURACION GLOBAL Y DEBUG
# ================================================================================
DEBUG = os.getenv("SYMBIOSIS_DEBUG", "0").lower() in ("1", "true", "yes")
PROJECT_ROOT = Path(__file__).parent.resolve()
LOG_DIR = Path.home() / "x" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "symbiosis_unified.log"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SYSTEM_STATE = {
    "started_at": None,
    "modules_preloaded": [],
    "main_module": None,
    "port": 8989,
    "shutdown": False,
    "global_monitor": None,
    "global_watchdog": None,
    "debug_enabled": DEBUG,
    "prompt_distributor": None,
}

# ================================================================================
# SECCION 4: LOG SEGURO CON DIAGNOSTICO EXTENDIDO
# ================================================================================
_log_lock = threading.RLock()

def log(msg, level="INFO", module="ORCH"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{module}] [{level}] {msg}"
    try:
        with _log_lock:
            print(line, flush=True)
            if DEBUG or level in ("ERROR", "WARN", "DEBUG"):
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
    except Exception as e:
        print(f"[LOG] Error al registrar: {e}", flush=True)

# ================================================================================
# SECCION 5: ANSI COLORS (SOPORTE TERMUX)
# ================================================================================
def is_termux():
    return os.getenv('TERMUX_VERSION') is not None or 'com.termux' in os.getenv('PATH', '')

def _termux_supports_ansi() -> bool:
    term = os.getenv('TERM', '')
    if 'xterm' in term.lower() or 'screen' in term.lower():
        return True
    if os.getenv('COLORTERM') or os.getenv('FORCE_COLOR'):
        return True
    return False

ANSI_SUPPORT = _termux_supports_ansi()

if ANSI_SUPPORT:
    C_RESET = "\033[0m"
    C_GREEN, C_YELLOW, C_RED, C_CYAN = "\033[92m", "\033[93m", "\033[91m", "\033[96m"
else:
    C_RESET = C_GREEN = C_YELLOW = C_RED = C_CYAN = ""

LED_ON = f"{C_GREEN}[OK]{C_RESET}" if ANSI_SUPPORT else "[+]"
LED_OFF = f"{C_RED}[-]{C_RESET}" if ANSI_SUPPORT else "[-]"
THREAD_OK = f"{C_GREEN}[OK]{C_RESET}" if ANSI_SUPPORT else "[OK]"
THREAD_WAIT = f"{C_YELLOW}[--]{C_RESET}" if ANSI_SUPPORT else "[--]"

# ================================================================================
# SECCION 6: ESTADOS DE MODULO
# ================================================================================
class ModuleStatus:
    NOT_LOADED = "NOT_LOADED"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    ERROR = "ERROR"
    STOPPED = "STOPPED"
    RESURRECTING = "RESURRECTING"
    FALLIDO = "FALLIDO"

# ================================================================================
# SECCION 7: MAPA DE ARCHIVOS A MODULOS
# ================================================================================
FILE_TO_MODULE_MAP = {
    "00_START_ALL.py": "orchestrator",
    "part1_config.py": "core_config",
    "part2_negotiation.py": "core_negotiation",
    "part3_radar.py": "core_radar",
    "part4_predictor.py": "core_predictor",
    "parte5_daimon_base.py": "core_daimon",
    "part6_main.py": "main_system",
    "part7_mejor_opcion.py": "core_best_option",
    "part8_interfaz_web.py": "frontend_web",
    "part9_network_monitor.py": "network_monitor",
    "lucifer_prometeo.py": "main_system",
}

# ================================================================================
# SECCION 8: MAPA DE NOMBRES DE HILO A MODULO
# ================================================================================
THREAD_NAME_TO_MODULE = {
    "Config": "core_config", "config": "core_config", "CoreConfig": "core_config",
    "core_config": "core_config", "Settings": "core_config",
    "Negotiat": "core_negotiation", "negot": "core_negotiation", "Negoci": "core_negotiation",
    "Negoti": "core_negotiation", "Negotia": "core_negotiation", "Negociac": "core_negotiation",
    "negocia": "core_negotiation", "_scheduler": "core_negotiation", "scheduler": "core_negotiation",
    "NegotiationScheduler": "core_negotiation",
    "Radar": "core_radar", "radar": "core_radar", "Scan": "core_radar", "scan": "core_radar",
    "search": "core_radar", "Busca": "core_radar", "Search": "core_radar",
    "GPSSimulator": "core_radar", "TrafficSimulator": "core_radar", "NetworkMonitor": "core_radar",
    "_gps._thread": "core_radar", "_traffic._thread": "core_radar", "_network._thread": "core_radar",
    "_gps_thread": "core_radar", "_traffic_thread": "core_radar", "_network_thread": "core_radar",
    "GPS_Simulator": "core_radar", "Traffic_Simulator": "core_radar", "RadarGPS": "core_radar",
    "RadarTraffic": "core_radar", "RadarNetwork": "core_radar", "radar_scan": "core_radar",
    "RadarScan": "core_radar", "_scan_thread": "core_radar",
    "Predict": "core_predictor", "predict": "core_predictor", "Predic": "core_predictor",
    "predic": "core_predictor", "Analiz": "core_predictor", "analiz": "core_predictor",
    "ML": "core_predictor", "ml": "core_predictor", "Model": "core_predictor", "model": "core_predictor",
    "ThreadMonitor": "core_predictor", "RegistrySync": "core_predictor", "CEOListener": "core_predictor",
    "TrainingThread": "core_predictor", "PredictorThread": "core_predictor", "PredictMonitor": "core_predictor",
    "Registry": "core_predictor", "SyncThread": "core_predictor", "CEOListerner": "core_predictor",
    "_thread_monitor": "core_predictor", "_registry_sync": "core_predictor",
    "_ceo_listener": "core_predictor", "_training": "core_predictor",
    "Daimon": "core_daimon", "daimon": "core_daimon", "Daemon": "core_daimon", "daemon": "core_daimon",
    "Demon": "core_daimon", "demon": "core_daimon", "Base": "core_daimon", "Espiritu": "core_daimon",
    "Espirit": "core_daimon", "Spirit": "core_daimon", "Daim": "core_daimon",
    "Singularidad": "core_daimon", "CEO": "core_daimon", "Bucle Autonomo": "core_daimon",
    "Mente Autonoma": "core_daimon", "AutonomousLoop": "core_daimon", "DaimonThread": "core_daimon",
    "Singularity": "core_daimon", "CoreDaimon": "core_daimon",
    "_singularidad": "core_daimon", "_ceo": "core_daimon", "_bucle": "core_daimon", "_mente": "core_daimon",
    "Best": "core_best_option", "best": "core_best_option", "Option": "core_best_option",
    "option": "core_best_option", "Mejor": "core_best_option", "mejor": "core_best_option",
    "Opcion": "core_best_option", "opcion": "core_best_option", "Choice": "core_best_option",
    "choice": "core_best_option", "Eval": "core_best_option", "eval": "core_best_option",
    "Evalu": "core_best_option",
    "Web": "frontend_web", "web": "frontend_web", "Frontend": "frontend_web",
    "frontend": "frontend_web", "Http": "frontend_web", "http": "frontend_web",
    "Flask": "frontend_web", "flask": "frontend_web", "API": "frontend_web", "api": "frontend_web",
    "Interface": "frontend_web", "interface": "frontend_web", "Interfaz": "frontend_web",
    "interfaz": "frontend_web", "UI": "frontend_web", "ui": "frontend_web",
    "HTML": "frontend_web", "html": "frontend_web", "Serve": "frontend_web", "serve": "frontend_web",
    "Request": "frontend_web", "request": "frontend_web",
    "Network": "network_monitor", "network": "network_monitor", "Net": "network_monitor",
    "net": "network_monitor", "Ping": "network_monitor", "ping": "network_monitor",
    "Connection": "network_monitor", "connection": "network_monitor", "Internet": "network_monitor",
    "internet": "network_monitor", "Conect": "network_monitor", "Conex": "network_monitor",
    "Ultra": "network_monitor", "ultra": "network_monitor",
    "NetMonitor": "network_monitor", "NetMonitor_0": "network_monitor",
    "NetworkPing": "network_monitor", "NetworkMonitor": "network_monitor",
    "NetPing": "network_monitor", "PingThread": "network_monitor",
    "_net_monitor": "network_monitor", "_ping": "network_monitor",
    "TunnelGuard": "network_monitor", "tunnelguard": "network_monitor",
    "Tunnel": "network_monitor", "tunnel": "network_monitor",
    "NetKeepAlive": "network_monitor", "netkeepalive": "network_monitor",
    "MainCore": "main_system", "Lucifer": "main_system", "lucifer": "main_system",
    "Promete": "main_system", "promete": "main_system", "Main": "main_system", "main": "main_system",
    "Symbiosis": "main_system", "symbiosis": "main_system", "System": "main_system",
    "system": "main_system", "Bucle": "main_system", "bucle": "main_system",
    "Loop": "main_system", "loop": "main_system",
    "Orch": "orchestrator", "orch": "orchestrator", "Orches": "orchestrator",
    "Health": "orchestrator", "health": "orchestrator", "Monitor": "orchestrator",
    "monitor": "orchestrator", "Display": "orchestrator", "display": "orchestrator",
    "Initial": "orchestrator", "initial": "orchestrator", "Startup": "orchestrator",
    "startup": "orchestrator", "Conductor": "orchestrator", "conductor": "orchestrator",
    "Vigilanc": "orchestrator", "vigilanc": "orchestrator", "Singular": "orchestrator",
    "singular": "orchestrator", "Mente": "orchestrator", "mente": "orchestrator",
    "Autonom": "orchestrator", "autonom": "orchestrator", "HealthLoop": "orchestrator",
    "MonitorDisplay": "orchestrator", "InitialScan": "orchestrator",
    "_health_loop": "orchestrator", "_monitor": "orchestrator",
    "FlujoEngine": "orchestrator", "flujo": "orchestrator",
}

# ================================================================================
# SECCION 9: DETECCION DE HILOS EFIMEROS
# ================================================================================
def is_ephemeral_thread(name: str, target=None) -> bool:
    ephemeral_prefixes = ("Thread-", "Dummy-")
    ephemeral_keywords = (
        "process_request", "_resurrect", "werkzeug", "waitress",
        "gunicorn", "ThreadPool", "PoolWorker-", "ProcessPool",
        "QueueHandler", "Socke", "Select", "Epoll", "Selector",
        "TimeoutWatcher_", "Procesador_",
    )
    if name.startswith(ephemeral_prefixes):
        if "(" in name and ")" in name:
            inner = name[name.find("(")+1:name.find(")")]
            if inner and not inner.startswith(("Thread-", "Dummy-")):
                return any(kw in inner for kw in ephemeral_keywords)
        return True
    if any(kw in name for kw in ephemeral_keywords):
        return True
    return False

# ================================================================================
# SECCION 10: REPARACION Y ASEGURAMIENTO DE CORE_CONFIG
# ================================================================================
def ensure_core_config_ready() -> bool:
    try:
        import core_config
        required_attrs = {
            'modules_preloaded': [],
            'SYSTEM_STATE': {},
            'DEFAULT_LOCATION': {"latitude": 8.9833, "longitude": -79.5167},
            'DEFAULT_ZONES': [
                {"latitude": 8.9850, "longitude": -79.5200},
                {"latitude": 8.8800, "longitude": -79.7600},
                {"latitude": 8.8750, "longitude": -79.7850},
            ],
            'DEFAULT_NEGOTIATION_ARGS': {
                "initiator_id": "orchestrator",
                "responder_id": "daimon",
                "domain": "ride_hailing",
                "item_description": "best_option",
                "base_terms": {"urgency": "normal"},
            },
            'MODULOS_CRITICOS': [
                "core_best_option", "core_negotiation",
                "core_radar", "core_predictor",
            ],
            'DEBUG': False,
            'VERSION': '4.0.0',
            'ALGO_WEIGHTS': {},
            'Q_TABLE': {},
            'UBER_COINS': None,
            'STOP_EVENT': None,
            'zona_estado': {},
        }
        for attr, default_value in required_attrs.items():
            if not hasattr(core_config, attr):
                setattr(core_config, attr, default_value)
                log(f"[CONFIG] Atributo {attr} inicializado con valor por defecto", "DEBUG")
        if hasattr(core_config, 'modules_preloaded'):
            if not isinstance(core_config.modules_preloaded, list):
                core_config.modules_preloaded = []
        if 'core_config' not in core_config.modules_preloaded:
            core_config.modules_preloaded.append('core_config')
        return True
    except ImportError:
        log("[CONFIG] core_config no importable, creando modulo minimo", "WARN")
        return _create_minimal_core_config()
    except Exception as e:
        log(f"[CONFIG] Error asegurando core_config: {e}", "ERROR")
        return _create_minimal_core_config()

def _create_minimal_core_config() -> bool:
    if 'core_config' not in sys.modules:
        mod = types.ModuleType('core_config')
        mod.modules_preloaded = ['core_config']
        mod.SYSTEM_STATE = {}
        mod.DEFAULT_LOCATION = {"latitude": 8.9833, "longitude": -79.5167}
        mod.DEFAULT_ZONES = []
        mod.DEFAULT_NEGOTIATION_ARGS = {}
        mod.MODULOS_CRITICOS = []
        mod.DEBUG = False
        mod.VERSION = '4.0.0'
        mod.ALGO_WEIGHTS = {}
        mod.Q_TABLE = {}
        mod.UBER_COINS = None
        mod.STOP_EVENT = None
        mod.zona_estado = {}
        sys.modules['core_config'] = mod
        log("[FALLBACK] Modulo core_config minimo creado", "WARN")
    return True

# ================================================================================
# SECCION 11: SHARED DATA REGISTRY (SINGLETON)
# ================================================================================
class SharedDataRegistry:
    _instance = None
    _init_lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self._data: Dict[str, Any] = {}
            self._callbacks: Dict[str, List[tuple]] = defaultdict(list)
            self._initialized = True

    def set(self, key: str, value: Any, notify: bool = True) -> bool:
        with self._init_lock:
            try:
                self._data[key] = copy.deepcopy(value)
                if notify:
                    # COPIAR callbacks bajo lock, ejecutar FUERA del lock
                    callbacks_to_run = self._collect_matching_callbacks(key)
                else:
                    callbacks_to_run = []
                return True
            except Exception:
                return False
        # Ejecutar callbacks FUERA del lock para evitar deadlock
        for cb in callbacks_to_run:
            try:
                cb(key, value)
            except Exception:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        with self._init_lock:
            return copy.deepcopy(self._data.get(key, default))

    def on_change(self, key_pattern: str, callback: Callable) -> str:
        with self._init_lock:
            cid = f"{key_pattern}_{uuid.uuid4().hex[:6]}"
            self._callbacks[key_pattern].append((cid, callback))
            return cid

    def _collect_matching_callbacks(self, key: str) -> List[Callable]:
        """COPIA callbacks coincidentes bajo lock. NUNCA ejecuta aquí."""
        matching = []
        for pattern, callbacks in list(self._callbacks.items()):
            if fnmatch(key, pattern):
                for _, cb in callbacks:
                    matching.append(cb)
        return matching

    def _trigger_callbacks(self, key: str, value: Any) -> None:
        """VERSIÓN SEGURA: Ejecuta callbacks FUERA del lock."""
        callbacks_to_run = self._collect_matching_callbacks(key)
        for cb in callbacks_to_run:
            try:
                cb(key, value)
            except Exception:
                pass

    def has(self, key: str) -> bool:
        with self._init_lock:
            return key in self._data

    def keys(self) -> List[str]:
        with self._init_lock:
            return list(self._data.keys())


# ================================================================================
# SECCION 12: PROMPT PAYLOAD
# ================================================================================
class PromptPayload:
    def __init__(self, prompt_text: str, flujo_id: Optional[str] = None):
        self.flujo_id = flujo_id or f"flujo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.prompt_text = prompt_text.strip()
        self.prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.origen = "core_best_option"
        self.destinos = ["core_negotiation", "core_radar", "core_predictor", "network_monitor"]
        self.estado = "pendiente"
        self.resultados: Dict[str, Any] = {}
        self.completado = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flujo_id": self.flujo_id,
            "prompt_text": self.prompt_text,
            "prompt_hash": self.prompt_hash,
            "timestamp": self.timestamp,
            "origen": self.origen,
            "destinos": self.destinos,
            "estado": self.estado,
            "resultados": self.resultados,
            "completado": self.completado,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptPayload':
        obj = cls.__new__(cls)
        obj.flujo_id = data.get("flujo_id")
        obj.prompt_text = data.get("prompt_text", "")
        obj.prompt_hash = data.get("prompt_hash")
        obj.timestamp = data.get("timestamp")
        obj.origen = data.get("origen")
        obj.destinos = data.get("destinos", [])
        obj.estado = data.get("estado", "pendiente")
        obj.resultados = data.get("resultados", {})
        obj.completado = data.get("completado", False)
        return obj

# ================================================================================
# SECCION 13: PROMPT DISTRIBUTOR
# ================================================================================
class PromptDistributor:
    def __init__(self, registry: Optional[SharedDataRegistry] = None):
        self.registry = registry or SharedDataRegistry()
        self.flujos_activos: Dict[str, PromptPayload] = {}
        self._lock = threading.RLock()
        self._callbacks_resultado: Dict[str, Callable] = {}

    def distribuir_prompt(self, prompt_text: str,
                          callback_completado: Optional[Callable] = None,
                          timeout_segundos: float = 120.0) -> str:
        payload = PromptPayload(prompt_text)
        with self._lock:
            self.flujos_activos[payload.flujo_id] = payload
            if callback_completado:
                self._callbacks_resultado[payload.flujo_id] = callback_completado
        for destino in payload.destinos:
            clave = f"mejor_opcion:{destino}:{payload.flujo_id}"
            self.registry.set(clave, {
                "flujo_id": payload.flujo_id,
                "prompt": payload.prompt_text,
                "prompt_hash": payload.prompt_hash,
                "origen": payload.origen,
                "timestamp": payload.timestamp,
                "requiere_respuesta": True,
            })
        for destino in payload.destinos:
            patron = f"mejor_opcion:{destino}:{payload.flujo_id}:resultado"
            self.registry.on_change(
                patron,
                lambda k, v, fid=payload.flujo_id, dst=destino:
                    self._on_resultado_recibido(fid, dst, v)
            )
        threading.Thread(
            target=self._vigilar_timeout,
            args=(payload.flujo_id, timeout_segundos),
            daemon=True,
            name=f"TimeoutWatcher_{payload.flujo_id[:8]}",
        ).start()
        return payload.flujo_id

    def _on_resultado_recibido(self, flujo_id: str, modulo: str, resultado: Dict[str, Any]):
        with self._lock:
            if flujo_id not in self.flujos_activos:
                return
            payload = self.flujos_activos[flujo_id]
            payload.resultados[modulo] = resultado
            if len(payload.resultados) >= len(payload.destinos):
                payload.estado = "completado"
                payload.completado = True
                self._enviar_a_daimon(payload)
                if flujo_id in self._callbacks_resultado:
                    try:
                        self._callbacks_resultado[flujo_id](payload)
                    except Exception:
                        pass
                    del self._callbacks_resultado[flujo_id]
                del self.flujos_activos[flujo_id]

    def _enviar_a_daimon(self, payload: PromptPayload):
        clave = f"daimon:entrada:{payload.flujo_id}"
        self.registry.set(clave, {
            "tipo": "resultado_mejor_opcion",
            "flujo_id": payload.flujo_id,
            "prompt_hash": payload.prompt_hash,
            "resultados_modulos": payload.resultados,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "requiere_ack": True,
        })

    def _vigilar_timeout(self, flujo_id: str, timeout: float):
        time.sleep(timeout)
        with self._lock:
            if flujo_id in self.flujos_activos:
                payload = self.flujos_activos[flujo_id]
                payload.estado = "timeout"
                self._enviar_a_daimon(payload)
                if flujo_id in self._callbacks_resultado:
                    try:
                        self._callbacks_resultado[flujo_id](payload)
                    except Exception:
                        pass
                    del self._callbacks_resultado[flujo_id]
                del self.flujos_activos[flujo_id]

    def obtener_estado_flujo(self, flujo_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if flujo_id in self.flujos_activos:
                return self.flujos_activos[flujo_id].to_dict()
            return None

# ================================================================================
# SECCION 14: MODULO PROCESADOR (BASE PARA MODULOS DESTINO)
# ================================================================================
class ModuloProcesador:
    def __init__(self, nombre_modulo: str, registry: Optional[SharedDataRegistry] = None):
        self.nombre_modulo = nombre_modulo
        self.registry = registry or SharedDataRegistry()
        self._procesando: Dict[str, bool] = {}
        patron = f"mejor_opcion:{nombre_modulo}:*"
        self.registry.on_change(patron, self._on_prompt_recibido)

    def _on_prompt_recibido(self, clave: str, datos: Dict[str, Any]):
        flujo_id = datos.get("flujo_id")
        if not flujo_id or not datos.get("requiere_respuesta"):
            return
        if flujo_id in self._procesando:
            return
        self._procesando[flujo_id] = True
        threading.Thread(
            target=self._procesar_en_background,
            args=(flujo_id, datos),
            daemon=True,
            name=f"Procesador_{self.nombre_modulo}_{flujo_id[:8]}",
        ).start()

    def _procesar_en_background(self, flujo_id: str, datos: Dict[str, Any]):
        try:
            resultado = self.procesar_prompt(datos.get("prompt", ""), datos)
        except Exception as e:
            resultado = {"error": str(e), "exito": False}
        finally:
            self._procesando.pop(flujo_id, None)
            clave_res = f"mejor_opcion:{self.nombre_modulo}:{flujo_id}:resultado"
            self.registry.set(clave_res, {
                "flujo_id": flujo_id,
                "modulo": self.nombre_modulo,
                "resultado": resultado,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "exito": "error" not in resultado,
            })

    def procesar_prompt(self, prompt: str, contexto: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Debe implementarse en subclase")

# ================================================================================
# SECCION 15: PROCESADORES CONCRETOS POR MODULO
# ================================================================================
class RadarProcesador(ModuloProcesador):
    def __init__(self, registry=None):
        super().__init__("core_radar", registry)

    def procesar_prompt(self, prompt: str, contexto: Dict[str, Any]) -> Dict[str, Any]:
        mod = sys.modules.get("core_radar")
        if mod:
            for fn_name in ("analizar_prompt_mejor_opcion", "procesar_mejor_opcion",
                            "evaluar_prompt", "obtener_recomendacion_zona"):
                if hasattr(mod, fn_name):
                    try:
                        return getattr(mod, fn_name)(prompt, contexto)
                    except TypeError:
                        try:
                            return getattr(mod, fn_name)()
                        except Exception:
                            continue
        return {
            "zonas_analizadas": 0,
            "mejor_zona": "desconocida",
            "demanda_estimada": 0.0,
            "surge_detected": False,
            "modulo_disponible": mod is not None,
            "timestamp_procesamiento": time.time(),
        }

class PredictorProcesador(ModuloProcesador):
    def __init__(self, registry=None):
        super().__init__("core_predictor", registry)

    def procesar_prompt(self, prompt: str, contexto: Dict[str, Any]) -> Dict[str, Any]:
        mod = sys.modules.get("core_predictor")
        if mod:
            for fn_name in ("analizar_prompt_mejor_opcion", "predecir_mejor_opcion",
                            "evaluar_prompt", "predict_demand"):
                if hasattr(mod, fn_name):
                    try:
                        return getattr(mod, fn_name)(prompt, contexto)
                    except TypeError:
                        try:
                            return getattr(mod, fn_name)()
                        except Exception:
                            continue
        return {
            "prediccion_demanda_30min": 0.0,
            "confianza": 0.0,
            "factores_influyentes": [],
            "modulo_disponible": mod is not None,
            "timestamp_procesamiento": time.time(),
        }

class NegotiationProcesador(ModuloProcesador):
    def __init__(self, registry=None):
        super().__init__("core_negotiation", registry)

    def procesar_prompt(self, prompt: str, contexto: Dict[str, Any]) -> Dict[str, Any]:
        mod = sys.modules.get("core_negotiation")
        if mod:
            for fn_name in ("analizar_prompt_mejor_opcion", "negociar_mejor_opcion",
                            "evaluar_prompt", "initiate_negotiation"):
                if hasattr(mod, fn_name):
                    try:
                        return getattr(mod, fn_name)(prompt, contexto)
                    except TypeError:
                        try:
                            return getattr(mod, fn_name)()
                        except Exception:
                            continue
        return {
            "estrategia_recomendada": "sin_datos",
            "umbral_aceptacion": 0.0,
            "agentes_disponibles": 0,
            "modulo_disponible": mod is not None,
            "timestamp_procesamiento": time.time(),
        }

class NetworkProcesador(ModuloProcesador):
    def __init__(self, registry=None):
        super().__init__("network_monitor", registry)

    def procesar_prompt(self, prompt: str, contexto: Dict[str, Any]) -> Dict[str, Any]:
        mod = sys.modules.get("network_monitor")
        if mod:
            for fn_name in ("analizar_prompt_mejor_opcion", "evaluar_red",
                            "evaluar_prompt", "get_network_status"):
                if hasattr(mod, fn_name):
                    try:
                        return getattr(mod, fn_name)(prompt, contexto)
                    except TypeError:
                        try:
                            return getattr(mod, fn_name)()
                        except Exception:
                            continue
        return {
            "estado_red": "DESCONOCIDO",
            "latencia_promedio_ms": 0.0,
            "servidor_optimo": "sin_datos",
            "modulo_disponible": mod is not None,
            "timestamp_procesamiento": time.time(),
        }

# ================================================================================
# SECCION 16: RECEPTOR DAIMON (PARTE 5)
# ================================================================================
class DaimonReceptor:
    def __init__(self, registry: Optional[SharedDataRegistry] = None,
                 ceo_callback: Optional[Callable] = None):
        self.registry = registry or SharedDataRegistry()
        self.ceo_callback = ceo_callback
        self._suscribir_a_entradas()

    def _suscribir_a_entradas(self):
        self.registry.on_change("daimon:entrada:*", self._on_entrada_recibida)

    def _on_entrada_recibida(self, clave: str, datos: Dict[str, Any]):
        if datos.get("tipo") != "resultado_mejor_opcion":
            return
        flujo_id = clave.split(":")[-1] if ":" in clave else None
        resultado_ceo = self._procesar_con_ceo(datos)
        if flujo_id and datos.get("requiere_ack"):
            self._enviar_ack_nucleo(flujo_id, resultado_ceo)

    def _procesar_con_ceo(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        resultados = datos.get("resultados_modulos", {})
        if self.ceo_callback:
            try:
                return self.ceo_callback(datos)
            except Exception:
                pass
        ceo_mod = sys.modules.get("core_daimon")
        if ceo_mod and hasattr(ceo_mod, 'ceo_avanzado') and ceo_mod.ceo_avanzado:
            try:
                return ceo_mod.ceo_avanzado(datos)
            except Exception:
                pass
        return {
            "decision_ceo": "APROBADO",
            "confianza_global": 0.92,
            "modulos_consultados": len(resultados),
            "modulos_exitosos": sum(1 for r in resultados.values() if r.get("exito", True)),
            "timestamp_procesamiento": datetime.now(timezone.utc).isoformat(),
        }

    def _enviar_ack_nucleo(self, flujo_id: str, resultado_ceo: Dict[str, Any]):
        clave = f"nucleo:ack:{flujo_id}"
        self.registry.set(clave, {
            "flujo_id": flujo_id,
            "status": "OK",
            "resultado_ceo": resultado_ceo,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "procesado": True,
        })

# ================================================================================
# SECCION 17: NUCLEO RECEPTOR (PARTE 1)
# ================================================================================
class NucleoReceptor:
    def __init__(self, registry: Optional[SharedDataRegistry] = None):
        self.registry = registry or SharedDataRegistry()
        self.acks_recibidos: Dict[str, Dict] = {}
        self._suscribir_a_acks()

    def _suscribir_a_acks(self):
        self.registry.on_change("nucleo:ack:*", self._on_ack_recibido)

    def _on_ack_recibido(self, clave: str, datos: Dict[str, Any]):
        flujo_id = clave.split(":")[-1] if ":" in clave else None
        if flujo_id:
            self.acks_recibidos[flujo_id] = datos
            self._responder_ok_final(flujo_id)

    def _responder_ok_final(self, flujo_id: str):
        clave = f"mejor_opcion:respuesta_final:{flujo_id}"
        self.registry.set(clave, {
            "flujo_id": flujo_id,
            "respuesta": "OK",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def verificar_respuesta(self, flujo_id: str, timeout: float = 30.0) -> bool:
        inicio = time.time()
        while time.time() - inicio < timeout:
            if flujo_id in self.acks_recibidos:
                return True
            time.sleep(0.1)
        return False

# ================================================================================
# SECCION 18: FLUJO ENGINE
# ================================================================================
DEFAULT_LOCATION = {"latitude": 8.9833, "longitude": -79.5167}
DEFAULT_ZONES = [
    {"latitude": 8.9850, "longitude": -79.5200},
    {"latitude": 8.8800, "longitude": -79.7600},
    {"latitude": 8.8750, "longitude": -79.7850},
]
DEFAULT_NEGOTIATION_ARGS = {
    "initiator_id": "orchestrator",
    "responder_id": "daimon",
    "domain": "ride_hailing",
    "item_description": "best_option",
    "base_terms": {"urgency": "normal"},
}

class FlujoEngine:
    def __init__(self, log_fn=None):
        self.log = log_fn or log
        self._module_cache: Dict[str, Any] = {}
        self._call_order = [
            ("core_radar", [
                "iniciar_radar", "forzar_escaneo_radar",
                "obtener_recomendacion_zona", "exportar_estado_radar",
            ]),
            ("core_predictor", [
                "predict_demand", "predict_multiple_zones",
                "get_system_status", "get_ceo_metrics",
                "ingest_real_time_data",
            ]),
            ("core_negotiation", [
                "initiate_negotiation", "get_system_report",
                "get_ceo_metrics", "register_agent",
            ]),
            ("core_best_option", [
                "procesar_prompt_completo", "run_best_option",
                "evaluate_offers", "run",
            ]),
        ]
        self._args_defaults = {
            "core_predictor.predict_demand": {"location": DEFAULT_LOCATION},
            "core_predictor.predict_multiple_zones": {"zones": DEFAULT_ZONES},
            "core_negotiation.initiate_negotiation": DEFAULT_NEGOTIATION_ARGS,
        }

    def load_modules(self):
        for mod_name, _ in self._call_order:
            if mod_name in sys.modules:
                self._module_cache[mod_name] = sys.modules[mod_name]
                self.log(f"[FLUJO] Cache cargado: {mod_name}", "OK")
            else:
                self.log(f"[FLUJO] Modulo no importado: {mod_name}", "WARN")

    def _find_instances_in_module(self, module) -> List[tuple]:
        instances = []
        for name in dir(module):
            if name.startswith('__'):
                continue
            try:
                obj = getattr(module, name)
                if (hasattr(obj, '__class__') and
                    not isinstance(obj, type) and
                    not inspect.isfunction(obj) and
                    not inspect.ismethod(obj) and
                    not inspect.ismodule(obj) and
                    obj.__class__.__name__ not in ('module', 'type')):
                    methods = [m for m in dir(obj) if not m.startswith('_') and callable(getattr(obj, m, None))]
                    if methods:
                        instances.append((name, obj, methods))
            except Exception:
                continue
        return instances

    def _find_callables_in_module(self, module, func_name: str):
        if hasattr(module, func_name):
            obj = getattr(module, func_name)
            if callable(obj) and not inspect.isclass(obj):
                is_bound = inspect.ismethod(obj)
                return obj, is_bound, f"modulo.{func_name}"
        instances = self._find_instances_in_module(module)
        for inst_name, inst, methods in instances:
            if func_name in methods or hasattr(inst, func_name):
                target = getattr(inst, func_name)
                if callable(target):
                    return target, True, f"{inst_name}.{func_name}"
        candidates = [
            f"get_{func_name.split('_')[0]}",
            f"get_{func_name.split('_')[0]}_instance",
            "get_instance", "get_orchestrator",
            "get_radar_instance", "get_predictor_instance",
        ]
        for cand in candidates:
            if hasattr(module, cand):
                try:
                    getter = getattr(module, cand)
                    if callable(getter):
                        inst = getter()
                        if inst and hasattr(inst, func_name):
                            target = getattr(inst, func_name)
                            if callable(target):
                                return target, True, f"{cand}() -> {func_name}"
                except Exception:
                    continue
        return None, None, None

    def _call_with_signature(self, target: Callable, is_bound: bool,
                              context_data: Optional[Dict], mod_name: str,
                              func_name: str, source: str):
        try:
            sig = inspect.signature(target)
            params = list(sig.parameters.items())
            if is_bound and params and params[0][0] in ('self', 'cls'):
                params = params[1:]
            param_names = [p[0] for p in params]
            has_defaults = {p[0]: p[1].default != inspect.Parameter.empty for p in params}
            required = [p for p in params if not has_defaults.get(p[0], False)]
            call_kwargs = {}
            default_map_key = f"{mod_name}.{func_name}"
            if default_map_key in self._args_defaults:
                for key, val in self._args_defaults[default_map_key].items():
                    if key in param_names and key not in call_kwargs:
                        call_kwargs[key] = val
            if context_data is not None:
                if 'context_data' in param_names:
                    call_kwargs['context_data'] = context_data
                elif 'data' in param_names:
                    call_kwargs['data'] = context_data
                elif 'zones' in param_names and isinstance(context_data, list):
                    call_kwargs['zones'] = context_data
                elif len(required) == 1 and required[0][0] not in call_kwargs:
                    call_kwargs[required[0][0]] = context_data
            missing = [p[0] for p in required if p[0] not in call_kwargs]
            if missing:
                module = sys.modules.get(mod_name)
                if module:
                    for miss in list(missing):
                        val = getattr(module, 'DEFAULT_LOCATION', None) or \
                              getattr(module, 'default_location', None)
                        if val:
                            call_kwargs[miss] = val
                            missing.remove(miss)
                if missing:
                    raise ValueError(f"Argumentos requeridos faltantes: {missing}")
            result = target(**call_kwargs)
            return True, result, None
        except Exception as e:
            return False, None, str(e)

    def execute_chain(self, context_data: Optional[Dict] = None) -> Dict[str, Any]:
        results = {
            "modulos_ejecutados": [],
            "errores": [],
            "fallback_activo": False,
            "outputs": {},
        }
        self.load_modules()
        for mod_name, func_candidates in self._call_order:
            module = self._module_cache.get(mod_name)
            if not module:
                err = f"{mod_name}: no en sys.modules"
                results["errores"].append(err)
                self.log(f"[FLUJO] {err}", "WARN")
                continue
            executed = False
            for func_name in func_candidates:
                target, is_bound, source = self._find_callables_in_module(module, func_name)
                if target is None:
                    continue
                success, output, error = self._call_with_signature(
                    target, is_bound, context_data, mod_name, func_name, source
                )
                if success:
                    results["modulos_ejecutados"].append(f"{mod_name}.{func_name}")
                    results["outputs"][f"{mod_name}.{func_name}"] = output
                    executed = True
                    self.log(f"[FLUJO] {mod_name}.{func_name} OK <- {source}", "OK")
                    break
                else:
                    self.log(f"[FLUJO] {mod_name}.{func_name} ERROR: {error}", "ERROR")
                    results["errores"].append(f"{mod_name}.{func_name}: {error}")
            if not executed:
                msg = f"{mod_name}: no se encontro funcion conocida"
                results["errores"].append(msg)
                self.log(f"[FLUJO] {msg}", "WARN")
        failed = len([e for e in results["errores"]
                      if "no se encontro" in e or "no en sys.modules" in e])
        if failed > len(self._call_order) * 0.6:
            results["fallback_activo"] = True
            self.log("[FLUJO] Umbral de fallos superado. Activando fallback CEO queue.", "WARN")
            self._send_to_ceo_fallback(context_data)
        return results

    def _send_to_ceo_fallback(self, context_data):
        try:
            from core_negotiation import send_to_ceo_queue
            send_to_ceo_queue("fallback", context_data)
            self.log("[FLUJO] Resultado enviado a cola de negociacion (fallback)", "INFO")
        except Exception as e:
            self.log(f"[FLUJO] Fallback CEO fallo: {e}", "ERROR")

# ================================================================================
# SECCION 19: WATCHDOG AVANZADO
# ================================================================================
class ThreadWatchdogAdvanced:
    def __init__(self, check_interval: float = 3.0):
        self.check_interval = check_interval
        self.threads: Dict[str, dict] = {}
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.monitor_thread: Optional[threading.Thread] = None

    def register_thread_advanced(
        self, module_name: str, thread_name: str, thread_obj: threading.Thread,
        factory: Optional[Callable] = None, is_critical: bool = True,
        max_restarts: int = 10, restart_delay: float = 2.0
    ) -> Optional[str]:
        if is_ephemeral_thread(thread_name):
            return None
        thread_id = f"{module_name}_{thread_name}_{uuid.uuid4().hex[:8]}"
        with self.lock:
            self.threads[thread_id] = {
                "id": thread_id, "name": thread_name, "module": module_name,
                "thread": thread_obj, "factory": factory, "is_critical": is_critical,
                "max_restarts": max_restarts, "restart_delay": restart_delay,
                "restart_count": 0, "last_heartbeat": datetime.now(timezone.utc),
                "status": "alive",
            }
        log(f"[WATCHDOG] +{thread_name} -> {module_name}", "REGISTER")
        return thread_id

    def send_heartbeat(self, thread_id: str):
        with self.lock:
            if thread_id in self.threads:
                self.threads[thread_id]["last_heartbeat"] = datetime.now(timezone.utc)

    def _resurrect_thread(self, thread_id: str):
        with self.lock:
            info = self.threads.get(thread_id)
            if not info:
                return
            if info["restart_count"] >= info["max_restarts"]:
                info["status"] = "failed"
                return
            factory = info.get("factory")
            if not factory:
                info["status"] = "failed"
                return
            info["restart_count"] += 1
            info["status"] = "restarting"
            log(f"[WATCHDOG] Resucitando {info['name']}", "RESURRECT")
        time.sleep(info["restart_delay"])
        try:
            new_thread = factory()
            with self.lock:
                if thread_id in self.threads:
                    self.threads[thread_id]["thread"] = new_thread
                    self.threads[thread_id]["status"] = "alive"
                    self.threads[thread_id]["last_heartbeat"] = datetime.now(timezone.utc)
            log(f"[WATCHDOG] {info['name']} resucitado", "SUCCESS")
        except Exception as e:
            log(f"[WATCHDOG] Error: {info['name']}: {e}", "ERROR")

    def start_monitoring(self):
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        self.stop_event.clear()
        def loop():
            log("[WATCHDOG] Monitor iniciado", "MONITOR")
            while not self.stop_event.is_set():
                self._check_all_threads()
                self.stop_event.wait(self.check_interval)
        self.monitor_thread = threading.Thread(target=loop, daemon=True)
        self.monitor_thread.start()

    def _check_all_threads(self):
        with self.lock:
            for tid, info in list(self.threads.items()):
                if not info["thread"].is_alive() and info["is_critical"]:
                    threading.Thread(
                        target=self._resurrect_thread, args=(tid,), daemon=True
                    ).start()

    def stop_monitoring(self):
        self.stop_event.set()

# ================================================================================
# SECCION 20: WATCHDOG GLOBAL (SINGLETON)
# ================================================================================
_global_watchdog: Optional[ThreadWatchdogAdvanced] = None

def set_global_watchdog(watchdog: ThreadWatchdogAdvanced):
    global _global_watchdog
    _global_watchdog = watchdog
    SYSTEM_STATE["global_watchdog"] = watchdog

def get_global_watchdog() -> Optional[ThreadWatchdogAdvanced]:
    return _global_watchdog

# ================================================================================
# SECCION 21: MONITOR DE ESTADO V4
# ================================================================================
class ModuleThreadMonitor:
    _instance: Optional['ModuleThreadMonitor'] = None
    _lock: threading.RLock = threading.RLock()

    def __new__(cls):
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
            self._modules: Dict[str, Dict[str, Any]] = {}
            self._thread_registry: Dict[str, List[dict]] = {}
            self._log_fn: Callable = self._default_log
            self._watchdog: Optional[ThreadWatchdogAdvanced] = None
            self._persistent_threads = set()
            self._unknown_threads: List[tuple] = []
            self._initialized = True
            self._log("Monitor V4 inicializado", "INFO")

    def set_logger(self, fn):
        self._log_fn = fn

    def set_watchdog(self, wd):
        self._watchdog = wd

    def _default_log(self, msg, level="INFO"):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MONITOR] [{level}] {msg}", flush=True)

    def _log(self, msg, level="INFO"):
        self._log_fn(msg, level)

    def register_module(self, name, ref=None, status=ModuleStatus.LOADING):
        with self._lock:
            if name not in self._modules:
                self._modules[name] = {
                    "name": name, "status": status, "thread_count": 0,
                    "active_threads": 0, "dead_threads": 0, "error_msg": "",
                }
                self._thread_registry[name] = []
                self._log(f"Modulo registrado: {name}", "INFO")
                return True
        return False

    def update_module_status(self, name, status, error_msg=""):
        with self._lock:
            if name in self._modules:
                self._modules[name]["status"] = status
                self._modules[name]["error_msg"] = error_msg

    def infer_module_from_thread_name(self, thread_name: str) -> str:
        name_lower = thread_name.lower()
        for key, mod in THREAD_NAME_TO_MODULE.items():
            key_lower = key.lower()
            if key_lower in name_lower or name_lower in key_lower:
                return mod
        return "unknown"

    def global_thread_scan(self):
        alive_count = 0
        unknown_threads = []
        unknown_alive = 0
        unknown_dead = 0
        log("[SCAN] === INICIANDO ESCANEO DE HILOS ===", "DEBUG")
        for thread in threading.enumerate():
            t_name = thread.name
            if is_ephemeral_thread(t_name):
                continue
            alive_count += 1
            is_alive = thread.is_alive()
            mod_name = self._detect_module_from_thread(thread)
            if not mod_name:
                mod_name = self.infer_module_from_thread_name(t_name)
            already_registered = False
            for mod_n, entries in self._thread_registry.items():
                for e in entries:
                    if e["thread"] is thread:
                        already_registered = True
                        break
                if already_registered:
                    break
            if not already_registered:
                if mod_name == "unknown":
                    if is_alive:
                        unknown_alive += 1
                    else:
                        unknown_dead += 1
                    unknown_threads.append((t_name, is_alive, self._get_thread_frames(thread)))
                    log(f"[UNKNOWN] Hilo: '{t_name}' | Vivo: {is_alive}", "DEBUG")
                else:
                    self.register_thread(mod_name, thread, t_name, persistent=True)
                    log(f"[SCAN] + {mod_name}/{t_name} (vivo: {is_alive})", "INFO")
        self._unknown_threads = unknown_threads
        log(f"[SCAN] Total activos: {alive_count} | Unknown: {unknown_alive} vivos, {unknown_dead} muertos", "INFO")
        return alive_count

    def _detect_module_from_thread(self, thread: threading.Thread) -> Optional[str]:
        try:
            frame = sys._current_frames().get(thread.ident, None)
            if frame is None:
                return None
            while frame:
                fname = os.path.basename(frame.f_code.co_filename)
                if fname in FILE_TO_MODULE_MAP:
                    return FILE_TO_MODULE_MAP[fname]
                frame = frame.f_back
        except Exception:
            pass
        return None

    def _get_thread_frames(self, thread: threading.Thread) -> str:
        try:
            frame = sys._current_frames().get(thread.ident, None)
            if frame is None:
                return "no_frames"
            files = []
            while frame:
                fname = os.path.basename(frame.f_code.co_filename)
                func = frame.f_code.co_name
                files.append(f"{fname}:{func}")
                frame = frame.f_back
            return "|".join(files[:5])
        except Exception:
            return "error"

    def register_thread(self, mod_name, thread, t_name=None, persistent=False):
        if not isinstance(thread, threading.Thread):
            return False
        name = t_name or thread.name
        if is_ephemeral_thread(name):
            return False
        with self._lock:
            if mod_name not in self._modules:
                self.register_module(mod_name, status=ModuleStatus.ACTIVE)
            if persistent:
                self._persistent_threads.add(name)
            for e in self._thread_registry[mod_name]:
                if e["thread"] is thread:
                    return True
            self._thread_registry[mod_name].append({
                "thread": thread, "name": name, "persistent": persistent,
            })
            self._clean_dead_threads(mod_name)
            self._update_counts(mod_name)
            return True

    def _clean_dead_threads(self, mod):
        cleaned = []
        for e in self._thread_registry[mod]:
            th = e["thread"]
            if th.is_alive() or e["name"] in self._persistent_threads:
                cleaned.append(e)
        self._thread_registry[mod] = cleaned

    def _update_counts(self, mod):
        entries = self._thread_registry.get(mod, [])
        alive = sum(1 for e in entries if e["thread"].is_alive())
        dead = sum(1 for e in entries
                   if not e["thread"].is_alive() and e["name"] in self._persistent_threads)
        self._modules[mod]["thread_count"] = len(entries)
        self._modules[mod]["active_threads"] = alive
        self._modules[mod]["dead_threads"] = dead
        self._modules[mod]["status"] = "ACTIVE" if alive > 0 else "IDLE"

    def render_module_line(self, name, mx=20):
        if name not in self._modules:
            return f"{LED_OFF} {name:<{mx}} [NO]"
        m = self._modules[name]
        ts = f"{m['active_threads']}/{m['thread_count']}"
        status = "ACTIVO" if m["active_threads"] > 0 else "IDLE"
        warn = THREAD_OK if m["dead_threads"] == 0 else THREAD_WAIT
        return f"{LED_ON} {name:<{mx}} [{status}] hilos: {ts} {warn}"

    def render_full_display(self):
        lines = []
        total_alive = 0
        total_dead = 0
        for name in sorted(self._modules.keys()):
            self._update_counts(name)
            lines.append(self.render_module_line(name))
            total_alive += self._modules[name]["active_threads"]
            total_dead += self._modules[name]["dead_threads"]
        lines.append("-" * 60)
        lines.append(f"Total: {total_alive} vivos | {total_dead} caidos")
        if self._unknown_threads:
            lines.append(f"[DEBUG] Unknown: {[(t[0], t[1]) for t in self._unknown_threads]}")
        return "\n".join(lines)

# ================================================================================
# SECCION 22: PARCHEO DE THREADING
# ================================================================================
_original_thread_start = threading.Thread.start

def _patch_threading_with_monitor(monitor, watchdog):
    def _patched_start(self):
        tname = self.name or "unnamed"
        if is_ephemeral_thread(tname):
            return _original_thread_start(self)
        mod = _detect_caller_module()
        if not mod:
            mod = monitor.infer_module_from_thread_name(tname)
        if mod == "unknown":
            log(f"[PATCH] Hilo no clasificado: '{tname}'", "WARN")
        else:
            monitor.register_thread(mod, self, tname, persistent=True)
        return _original_thread_start(self)
    threading.Thread.start = _patched_start
    log("Thread.start parcheado (V4-Debug)", "MONITOR")

def _detect_caller_module() -> Optional[str]:
    try:
        frame = sys._getframe(2)
        for _ in range(10):
            if frame is None:
                break
            fname = os.path.basename(frame.f_code.co_filename)
            if fname in FILE_TO_MODULE_MAP:
                return FILE_TO_MODULE_MAP[fname]
            frame = frame.f_back
    except Exception:
        pass
    return None

# ================================================================================
# SECCION 23: INYECCION DE ESTADO MEJORADA
# ================================================================================
def inject_orchestrator_state_enhanced(module):
    if module is None:
        return False
    critical_globals = [
        'ceo_avanzado', 'ceoia', 'SYSTEM_STATE', 'STOP_EVENT',
        'zona_estado', 'ALGO_WEIGHTS', 'Q_TABLE', 'UBER_COINS',
        'log', 'log_lock', 'data_lock', 'monitor',
    ]
    for var_name in critical_globals:
        if var_name in globals():
            setattr(module, var_name, globals()[var_name])
    util_functions = [
        'calcular_distancia_py', 'sigmoid', 'batch_write_file',
        'jittered_sleep', 'activity_factor', 'is_termux',
    ]
    for func_name in util_functions:
        if func_name in globals() and callable(globals()[func_name]):
            setattr(module, func_name, globals()[func_name])
    setattr(module, '__orchestrator_injected__', True)
    setattr(module, '__injection_timestamp__', time.time())
    log(f"[INJECT] Estado inyectado en {getattr(module, '__name__', 'unknown')}", "DEBUG")
    return True

def inject_orchestrator_state(module):
    return inject_orchestrator_state_enhanced(module)

# ================================================================================
# SECCION 24: SISTEMA DE READY CALLBACKS
# ================================================================================
_module_ready_callbacks: List[tuple] = []
_module_initialized: Dict[str, bool] = {}

def register_module_ready_callback(module_name: str, callback: Callable):
    _module_ready_callbacks.append((module_name, callback))
    log(f"[READY] Callback registrado para {module_name}", "DEBUG")

def notify_module_ready(module_name: str):
    _module_initialized[module_name] = True
    log(f"[READY] Modulo {module_name} notificado como listo", "INFO")
    to_execute = [(name, cb) for name, cb in _module_ready_callbacks if name == module_name]
    for name, callback in to_execute:
        try:
            callback()
            log(f"[READY] Callback ejecutado para {name}", "DEBUG")
        except Exception as e:
            log(f"[ERROR] Callback fallido para {name}: {e}", "ERROR")

def wait_for_modules(module_names: List[str], timeout: float = 30.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if all(_module_initialized.get(m, False) for m in module_names):
            return True
        time.sleep(0.1)
    log(f"[WARN] Timeout esperando modulos: {module_names}", "WARN")
    return False

# ================================================================================
# SECCION 25: SAFE MODULE GLOBALS
# ================================================================================
class SafeModuleGlobals(dict):
    CRITICAL_FALLBACKS = {
        'modules_preloaded': [],
        'SYSTEM_STATE': {},
        'DEBUG': False,
        'VERSION': '4.0.0',
        'DEFAULT_LOCATION': {"latitude": 8.9833, "longitude": -79.5167},
        'DEFAULT_ZONES': [],
        'DEFAULT_NEGOTIATION_ARGS': {},
        'MODULOS_CRITICOS': [],
        'ALGO_WEIGHTS': {},
        'Q_TABLE': {},
        'UBER_COINS': None,
        'ceo_avanzado': None,
        'ceoia': None,
        'STOP_EVENT': None,
        'zona_estado': {},
    }

    def __init__(self, original_globals, module_name):
        super().__init__(original_globals)
        self._original = original_globals
        self._module_name = module_name
        for key, value in self.CRITICAL_FALLBACKS.items():
            if key not in self:
                self[key] = value

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            if key in self.CRITICAL_FALLBACKS:
                fallback = self.CRITICAL_FALLBACKS[key]
                if isinstance(fallback, (list, dict)):
                    return copy.deepcopy(fallback)
                return fallback
            raise

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if key in self._original:
            self._original[key] = value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

# ================================================================================
# SECCION 26: INYECCION DE ATRIBUTOS CRITICOS EN CORE_CONFIG
# ================================================================================
def _inject_core_config_defaults(mod):
    defaults = {
        'modules_preloaded': [],
        'SYSTEM_STATE': {},
        'DEBUG': False,
        'VERSION': '4.0.0',
        'DEFAULT_LOCATION': {"latitude": 8.9833, "longitude": -79.5167},
        'DEFAULT_ZONES': [
            {"latitude": 8.9850, "longitude": -79.5200},
            {"latitude": 8.8800, "longitude": -79.7600},
            {"latitude": 8.8750, "longitude": -79.7850},
        ],
        'DEFAULT_NEGOTIATION_ARGS': {
            "initiator_id": "orchestrator",
            "responder_id": "daimon",
            "domain": "ride_hailing",
            "item_description": "best_option",
            "base_terms": {"urgency": "normal"},
        },
        'MODULOS_CRITICOS': [
            "core_best_option", "core_negotiation",
            "core_radar", "core_predictor",
        ],
        'ALGO_WEIGHTS': {},
        'Q_TABLE': {},
        'UBER_COINS': None,
        'ceo_avanzado': None,
        'ceoia': None,
        'STOP_EVENT': None,
        'zona_estado': {},
        'log': log,
        'log_lock': _log_lock,
        'data_lock': threading.RLock(),
    }
    for attr, value in defaults.items():
        if not hasattr(mod, attr):
            try:
                setattr(mod, attr, value)
                log(f"[INJECT] {attr} inyectado en core_config", "DEBUG")
            except Exception as e:
                log(f"[WARN] No se pudo inyectar {attr}: {e}", "WARN")
    if not hasattr(mod, 'modules_preloaded') or not isinstance(mod.modules_preloaded, list):
        mod.modules_preloaded = []
    if 'core_config' not in mod.modules_preloaded:
        mod.modules_preloaded.append('core_config')

# ================================================================================
# SECCION 27: PRECARGA CON DIAGNOSTICO EXTENDIDO
# ================================================================================
def preload_module_with_diagnostics(filename, module_name, critical=True, monitor=None):
    filepath = PROJECT_ROOT / filename
    log(f"[LOAD] Iniciando carga: {filename} -> {module_name}", "DEBUG")
    if not filepath.exists():
        log(f"[ERROR] Archivo no encontrado: {filepath}", "ERROR")
        if monitor:
            monitor.update_module_status(module_name, ModuleStatus.ERROR, "No encontrado")
        return not critical
    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None:
            raise ImportError(f"No se pudo crear spec para {module_name}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        log(f"[LOAD] Spec creado para {module_name}", "DEBUG")
        if module_name == "core_config":
            _inject_core_config_defaults(mod)
        inject_orchestrator_state_enhanced(mod)
        log(f"[LOAD] Estado inyectado en {module_name}", "DEBUG")
        spec.loader.exec_module(mod)
        log(f"[LOAD] Modulo ejecutado: {module_name}", "INFO")
        _verify_module_components(mod, module_name)
        notify_module_ready(module_name)
        SYSTEM_STATE["modules_preloaded"].append(module_name)
        if monitor:
            monitor.register_module(module_name, mod, ModuleStatus.ACTIVE)
            SYSTEM_STATE["global_monitor"] = monitor
            mod.GLOBAL_MONITOR = monitor
            mod.GLOBAL_WATCHDOG = _global_watchdog
        _inject_activity_thread(module_name, mod, monitor)
        return True
    except ImportError as e:
        log(f"[ERROR] Import fallido en {filename}: {e}", "ERROR")
        if monitor:
            monitor.update_module_status(module_name, ModuleStatus.ERROR, f"ImportError: {e}")
        return not critical
    except AttributeError as e:
        log(f"[ERROR] Atributo faltante en {filename}: {e}", "ERROR")
        if monitor:
            monitor.update_module_status(module_name, ModuleStatus.ERROR, f"AttributeError: {e}")
        return not critical
    except Exception as e:
        log(f"[ERROR] Error inesperado en {filename}: {e}", "ERROR")
        if DEBUG:
            traceback.print_exc()
        if monitor:
            monitor.update_module_status(module_name, ModuleStatus.ERROR, str(e)[:100])
        return not critical

def _verify_module_components(mod, module_name: str):
    expected = {
        "core_radar": ["UberRadarPro", "get_radar_instance", "iniciar_radar"],
        "core_predictor": ["UberDemandPredictor", "get_predictor", "DemandSample"],
        "core_negotiation": ["NegotiationOrchestrator", "StrategicAgent", "ReputationSystem"],
        "core_daimon": ["CEOIA", "iniciar_ceoia_unificada", "integrar_gps_en_ceo"],
        "core_best_option": ["activar_prompt_mejor_opcion", "procesar_prompt_completo"],
        "frontend_web": ["app", "registrar_endpoints_frontend"],
    }
    expected_funcs = expected.get(module_name, [])
    missing = [f for f in expected_funcs if not hasattr(mod, f)]
    if missing:
        log(f"[WARN] {module_name} falta: {missing}", "WARN")
    else:
        log(f"[OK] {module_name} tiene todos los componentes esperados", "INFO")

def preload_module(filename, module_name, critical=True, monitor=None):
    return preload_module_with_diagnostics(filename, module_name, critical, monitor)

def cargar_modulo_seguro(nombre_modulo, ruta_archivo):
    try:
        if nombre_modulo == 'core_config':
            ensure_core_config_ready()
        spec = importlib.util.spec_from_file_location(nombre_modulo, ruta_archivo)
        if spec is None:
            raise ImportError(f"No se pudo crear spec para {nombre_modulo}")
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nombre_modulo] = modulo
        if hasattr(modulo, 'SYSTEM_STATE'):
            try:
                import core_config
                modulo.SYSTEM_STATE = getattr(core_config, 'SYSTEM_STATE', {})
            except ImportError:
                pass
        spec.loader.exec_module(modulo)
        if not hasattr(modulo, 'modules_preloaded'):
            modulo.modules_preloaded = []
        log(f"[OK] Modulo {nombre_modulo} cargado correctamente", "INFO")
        return True
    except Exception as e:
        log(f"[ERROR] Error cargando {nombre_modulo}: {e}", "ERROR")
        if nombre_modulo == 'core_config':
            return ensure_core_config_ready()
        return False

# ================================================================================
# SECCION 28: SINCRONIZACION POST-CARGA CON REGISTRY
# ================================================================================
def sync_modules_with_registry(modules_list: List[str]):
    try:
        registry = SharedDataRegistry()
        for mod_name in modules_list:
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                if hasattr(mod, 'subscribe_to_updates'):
                    try:
                        mod.subscribe_to_updates("ceoia:*", lambda k, v: log(f"[REG] {k} actualizado", "DEBUG"))
                    except Exception:
                        pass
                status_key = f"module:{mod_name}:status"
                registry.set(status_key, {
                    "loaded": True,
                    "timestamp": time.time(),
                    "functions": [f for f in dir(mod) if not f.startswith('_') and callable(getattr(mod, f))],
                })
                log(f"[SYNC] {mod_name} sincronizado con Registry", "DEBUG")
    except Exception as e:
        log(f"[WARN] Error sincronizando con Registry: {e}", "WARN")

# ================================================================================
# SECCION 29: INYECCION DE HILOS DE ACTIVIDAD
# ================================================================================
def _inject_activity_thread(module_name, mod, monitor):
    if module_name == "core_best_option":
        _start_best_option_orchestrator(mod, monitor)
    elif module_name == "core_predictor":
        _start_predictor_heartbeat(mod, monitor)
    elif module_name == "core_negotiation":
        _start_negotiation_heartbeat(mod, monitor)
    elif module_name == "frontend_web":
        _start_frontend_activity(mod, monitor)

def _start_best_option_orchestrator(mod, monitor):
    PING_INTERVAL = 30
    if hasattr(mod, "activar_prompt_mejor_opcion") and not getattr(mod, "MEJOR_OPCION_PROMPT_ACTIVO", False):
        try:
            mod.activar_prompt_mejor_opcion()
            log("[ORCH] Modulo core_best_option activado con cadena completa", "OK")
        except Exception as e:
            log(f"[ORCH] Error activando best_option: {e}", "WARN")

    def _actividad():
        while not SYSTEM_STATE.get("shutdown", False):
            try:
                if hasattr(mod, "procesar_prompt_completo"):
                    mod.procesar_prompt_completo()
                elif hasattr(mod, "activar_prompt_mejor_opcion"):
                    mod.activar_prompt_mejor_opcion()
                log("[ORCH] Ciclo de procesamiento completo ejecutado", "INFO")
            except Exception as e:
                log(f"[ORCH] Error en ciclo: {e}", "WARN")
            for _ in range(PING_INTERVAL):
                if SYSTEM_STATE.get("shutdown", False):
                    break
                time.sleep(1)

    t = threading.Thread(target=_actividad, name="best_option_full_cycle", daemon=True)
    t.start()
    if monitor:
        monitor.register_thread("core_best_option", t, persistent=True)
    if _global_watchdog:
        _global_watchdog.register_thread_advanced(
            "core_best_option", "best_option_full_cycle", t,
            is_critical=False, max_restarts=3,
        )
    log("[CARTA] Hilo de orquestacion activado para core_best_option", "OK")

def _start_predictor_heartbeat(mod, monitor):
    def _latido():
        while not SYSTEM_STATE.get("shutdown", False):
            try:
                if hasattr(mod, "ping"):
                    mod.ping()
            except Exception:
                pass
            time.sleep(10)
    t = threading.Thread(target=_latido, name="predictor_heartbeat", daemon=True)
    t.start()
    if monitor:
        monitor.register_thread("core_predictor", t, persistent=True)
    if _global_watchdog:
        _global_watchdog.register_thread_advanced(
            "core_predictor", "predictor_heartbeat", t,
            is_critical=False, max_restarts=3,
        )
    log("[HEARTBEAT] Hilo de latido inyectado en core_predictor", "OK")

def _start_negotiation_heartbeat(mod, monitor):
    def _latido():
        while not SYSTEM_STATE.get("shutdown", False):
            try:
                if hasattr(mod, "ping"):
                    mod.ping()
            except Exception:
                pass
            time.sleep(10)
    t = threading.Thread(target=_latido, name="negotiation_heartbeat", daemon=True)
    t.start()
    if monitor:
        monitor.register_thread("core_negotiation", t, persistent=True)
    if _global_watchdog:
        _global_watchdog.register_thread_advanced(
            "core_negotiation", "negotiation_heartbeat", t,
            is_critical=False, max_restarts=3,
        )
    log("[HEARTBEAT] Hilo de latido inyectado en core_negotiation", "OK")

def _start_frontend_activity(mod, monitor):
    PING_INTERVAL = 30
    import urllib.request  # ← MOVIDO FUERA DEL LOOP
    
    def _actividad():
        while not SYSTEM_STATE.get("shutdown", False):
            try:
                urllib.request.urlopen("http://127.0.0.1:8989/health", timeout=2)
            except Exception:
                pass
            for _ in range(PING_INTERVAL):
                if SYSTEM_STATE.get("shutdown", False):
                    break
                time.sleep(1)
    
    t = threading.Thread(target=_actividad, name="frontend_warmer", daemon=True)
    t.start()
    if monitor:
        monitor.register_thread("frontend_web", t, persistent=True)
    if _global_watchdog:
        _global_watchdog.register_thread_advanced(
            "frontend_web", "frontend_warmer", t,
            is_critical=False, max_restarts=3,
        )
    log("[CARTA] Hilo de actividad cada 30s inyectado en frontend_web", "OK")


# ================================================================================
# SECCION 30: UTILIDADES DE SISTEMA
# ================================================================================
def wait_for_port(port, host="127.0.0.1", timeout=20):
    start = time.time()
    while time.time() - start < timeout and not SYSTEM_STATE["shutdown"]:
        s = None
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
            return True
        except socket.timeout:
            pass
        except OSError:
            # Puerto no disponible, reintentar
            pass
        except Exception:
            # Error no recuperable, abortar
            break
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        time.sleep(0.5)
    return False


def health_loop(interval=30):
    while not SYSTEM_STATE["shutdown"]:
        try:
            main_mod = SYSTEM_STATE.get("main_module")
            if main_mod is not None and hasattr(main_mod, 'STOP_EVENT'):
                if main_mod.STOP_EVENT.is_set():
                    SYSTEM_STATE["shutdown"] = True
                    break
        except Exception as e:
            log(f"[HEALTH LOOP] Error: {e}", "ERROR")
        time.sleep(interval)


# ================================================================================
# SECCION 31: SYSTEM GUARD (MEMORIA)
# ================================================================================
class SystemGuard:
    def __init__(self, min_available_mb: float = 300.0):
        self.min_available_mb = min_available_mb

    def _get_mem(self) -> Dict[str, float]:
        r = {
            "available_mb": 0.0,
            "total_mb": 0.0,
            "used_percent": 100.0,
            "error": True,
        }
        # Intento 1: /proc/meminfo (Linux/Android/Termux)
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        r["available_mb"] = int(line.split()[1]) / 1024.0
                    elif line.startswith("MemTotal:"):
                        r["total_mb"] = int(line.split()[1]) / 1024.0
                if r["total_mb"] > 0:
                    r["used_percent"] = (
                        (r["total_mb"] - r["available_mb"]) / r["total_mb"]
                    ) * 100.0
                    r["error"] = False
                    return r
        except FileNotFoundError:
            log("[GUARD] /proc/meminfo no disponible, intentando alternativa", "DEBUG")
        except PermissionError:
            log("[GUARD] Sin permiso para /proc/meminfo, intentando alternativa", "DEBUG")
        except Exception as e:
            log(f"[GUARD] Error leyendo /proc/meminfo: {e}", "DEBUG")

        # Intento 2: psutil (si está instalado)
        try:
            import psutil
            mem = psutil.virtual_memory()
            r["available_mb"] = mem.available / (1024 * 1024)
            r["total_mb"] = mem.total / (1024 * 1024)
            r["used_percent"] = mem.percent
            r["error"] = False
            log("[GUARD] Memoria obtenida via psutil", "DEBUG")
            return r
        except ImportError:
            pass
        except Exception as e:
            log(f"[GUARD] Error con psutil: {e}", "DEBUG")

        # Intento 3: subprocess con free (Termux/Linux)
        try:
            import subprocess
            result = subprocess.run(
                ["free", "-m"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 4:
                            r["total_mb"] = float(parts[1])
                            r["available_mb"] = float(parts[3])
                            if r["total_mb"] > 0:
                                r["used_percent"] = (
                                    (r["total_mb"] - r["available_mb"]) / r["total_mb"]
                                ) * 100.0
                            r["error"] = False
                            log("[GUARD] Memoria obtenida via free", "DEBUG")
                            return r
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"[GUARD] Error con free: {e}", "DEBUG")

        # Fallback: valores conservadores indicando fallo
        log("[GUARD] No se pudo leer memoria del sistema", "WARN")
        return r

    def check_and_release(self) -> bool:
        m = self._get_mem()
        if m.get("error", True):
            log("[GUARD] No se pudo determinar memoria disponible, asumiendo OK", "WARN")
            return False

        log(
            f"[GUARD] Mem: {m['available_mb']:.0f}MB / "
            f"{m['total_mb']:.0f}MB ({m['used_percent']:.1f}%)",
            "INFO",
        )

        if m["available_mb"] < self.min_available_mb:
            log("[GUARD] Memoria baja, liberando...", "WARN")
            gc.collect()
            # Verificar si gc.collect() ayudó
            m_after = self._get_mem()
            if not m_after.get("error", True):
                freed = m["available_mb"] - m_after["available_mb"]
                log(
                    f"[GUARD] Post-GC: {m_after['available_mb']:.0f}MB "
                    f"(delta: {freed:+.0f}MB)",
                    "INFO",
                )
            return True

        return False



# ================================================================================
# SECCION 32: GUARDIAS DE RED Y TUNEL
# ================================================================================
class NetworkKeepAlive:
    def __init__(self, interval=15.0, target="1.1.1.1", port=53):
        self.interval = interval
        self.target = target
        self.port = port
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="NetKeepAlive")
        self.thread.start()
        log(f"[NET] KeepAlive hacia {self.target}:{self.port}", "SYSTEM")

    def _loop(self):
        while self.running and not SYSTEM_STATE["shutdown"]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2.0)
                s.sendto(b"\x00", (self.target, self.port))
                s.close()
            except Exception as e:
                log(f"[NET] Error: {e}", "ERROR")
            time.sleep(self.interval)

    def stop(self):
        self.running = False

class TunnelGuard:
    def __init__(self, cmd: str, check_interval=20.0):
        self.cmd = cmd
        self.check_interval = check_interval
        self.process = None
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor, daemon=True, name="TunnelGuard")
        self.thread.start()
        log("[TUNNEL] Monitor iniciado", "NET")

    def _monitor(self):
        while self.running and not SYSTEM_STATE["shutdown"]:
            if not self.process or self.process.poll() is not None:
                log("[TUNNEL] Reiniciando...", "WARN")
                try:
                    self.process = subprocess.Popen(
                        self.cmd, shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True,
                    )
                    log(f"[TUNNEL] PID: {self.process.pid}", "OK")
                except Exception as e:
                    log(f"[TUNNEL] Error: {e}", "ERROR")
            time.sleep(self.check_interval)

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()

class AndroidForegroundGuard:
    def __init__(self):
        self.acquired = False

    def acquire(self):
        if os.getenv("TERMUX_VERSION"):
            try:
                subprocess.run([
                    "termux-notification", "--ongoing", "--id", "1",
                    "--title", "Symbiosis System",
                    "--content", "Ejecucion activa",
                    "--priority", "high",
                ], check=True)
                self.acquired = True
                log("[GUARD] Notificacion activa", "SYSTEM")
            except Exception as e:
                log(f"[GUARD] Error: {e}", "ERROR")

    def release(self):
        if self.acquired:
            try:
                subprocess.run(["termux-notification", "--remove", "--id", "1"], check=True)
            except Exception as e:
                log(f"[GUARD] Error: {e}", "ERROR")
            self.acquired = False

# ================================================================================
# SECCION 33: SAFE THREAD CON REINTENTOS
# ================================================================================
def safe_thread(name, target, monitor=None, module_name="unknown",
                restart_delay=2, max_retries=10, persistent=True):
    def wrapper():
        retries = 0
        while not SYSTEM_STATE["shutdown"]:
            try:
                target()
                retries = 0
            except Exception as e:
                retries += 1
                log(f"[THREAD CRASH] {name}: {e}", "ERROR", module_name)
                if retries >= max_retries:
                    break
                time.sleep(restart_delay)

    def factory():
        t = threading.Thread(target=wrapper, name=name, daemon=True)
        t.start()
        return t

    t = factory()
    if _global_watchdog:
        _global_watchdog.register_thread_advanced(
            module_name, name, t,
            factory=factory, is_critical=persistent,
        )
    if monitor:
        monitor.register_thread(module_name, t, name, persistent=persistent)
    return t

# ================================================================================
# SECCION 34: REGISTRO AUTOMATICO DE HILOS
# ================================================================================
DYNAMIC_THREAD_MAP = {
    "tunnelguard": "network_monitor",
    "netkeepalive": "network_monitor",
    "tunnelguard_0": "network_monitor",
    "healthloop": "orchestrator",
    "monitorloop": "orchestrator",
    "initialscan": "orchestrator",
    "registrysync": "core_predictor",
    "ceolistener": "core_daimon",
}

class ThreadAutoRegistry:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._registry = {}
                    cls._instance._initialized = True
        return cls._instance

    def register(self, thread: threading.Thread, module_name: str, critical: bool = True):
        with self._lock:
            self._registry[thread.name] = {
                "thread": thread,
                "module": module_name,
                "critical": critical,
                "status": "active",
                "pid": os.getpid(),
            }

    def auto_detect_and_register(self, thread: threading.Thread) -> Optional[str]:
        t_name = thread.name.lower()
        for key, mod in DYNAMIC_THREAD_MAP.items():
            if key in t_name:
                self.register(thread, mod)
                return mod
        try:
            for fr in inspect.stack():
                fname = os.path.basename(fr.filename).lower()
                if "radar" in fname:
                    return self._reg_or_return(thread, "core_radar")
                if "predict" in fname:
                    return self._reg_or_return(thread, "core_predictor")
                if "negotiat" in fname:
                    return self._reg_or_return(thread, "core_negotiation")
                if "tunnel" in fname or "network" in fname:
                    return self._reg_or_return(thread, "network_monitor")
                if "orch" in fname or "start_all" in fname:
                    return self._reg_or_return(thread, "orchestrator")
        except Exception:
            pass
        self.register(thread, "unknown", critical=False)
        return "unknown"

    def _reg_or_return(self, thread, module):
        self.register(thread, module)
        return module

    def sync_all_alive_threads(self) -> List[str]:
        registered = []
        with self._lock:
            current_names = set(self._registry.keys())
            for t in threading.enumerate():
                if t.is_alive() and not t.name.startswith(("Dummy-", "Thread-")):
                    if t.name not in current_names:
                        mod = self.auto_detect_and_register(t)
                        registered.append(t.name)
        return registered

    def get_module_for_thread(self, t_name: str) -> str:
        with self._lock:
            entry = self._registry.get(t_name)
            return entry["module"] if entry else "unknown"

# ================================================================================
# SECCION 35: INICIALIZACION DEL FLUJO MEJOR_OPCION
# ================================================================================
def inicializar_procesadores_mejor_opcion() -> bool:
    try:
        ensure_core_config_ready()
        registry = SharedDataRegistry()
        distribuidor = PromptDistributor(registry)
        SYSTEM_STATE["prompt_distributor"] = distribuidor
        log("[OK] PromptDistributor registrado", "INFO")
        procesadores_registrados = []
        for nombre_modulo, clase_proc in [
            ("core_radar", RadarProcesador),
            ("core_predictor", PredictorProcesador),
            ("core_negotiation", NegotiationProcesador),
            ("network_monitor", NetworkProcesador),
        ]:
            try:
                clase_proc(registry)
                procesadores_registrados.append(nombre_modulo)
                log(f"[OK] Procesador para {nombre_modulo} registrado", "INFO")
            except Exception as e:
                log(f"[WARN] Procesador para {nombre_modulo} fallo: {e}", "WARN")
        daimon_receptor = DaimonReceptor(registry)
        nucleo_receptor = NucleoReceptor(registry)
        log(f"[OK] Flujo MEJOR_OPCION completamente inicializado ({len(procesadores_registrados)} procesadores)", "INFO")
        return True
    except Exception as e:
        log(f"[ERROR] Fallo en inicializar_procesadores_mejor_opcion: {e}", "ERROR")
        if DEBUG:
            traceback.print_exc()
        return False

# ================================================================================
# SECCION 36: FUNCIONES DE INTEGRACION PARA CADA PARTE
# ================================================================================
def integrar_negotiation_con_mejor_opcion(registry=None):
    return NegotiationProcesador(registry)

def integrar_radar_con_mejor_opcion(registry=None):
    return RadarProcesador(registry)

def integrar_predictor_con_mejor_opcion(registry=None):
    return PredictorProcesador(registry)

def integrar_network_con_mejor_opcion(registry=None):
    return NetworkProcesador(registry)

def integrar_daimon_con_mejor_opcion(registry=None, ceo_callback=None):
    return DaimonReceptor(registry, ceo_callback)

def integrar_nucleo_con_mejor_opcion(registry=None):
    return NucleoReceptor(registry)

# ================================================================================
# SECCION 37: FUNCION PRINCIPAL PARA ACTIVAR FLUJO DESDE HTML
# ================================================================================
def activar_flujo_mejor_opcion_completo(
    prompt_text: str,
    callback_final: Optional[Callable[[Dict], None]] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    registry = SharedDataRegistry()
    distribuidor = SYSTEM_STATE.get("prompt_distributor") or PromptDistributor(registry)
    nucleo = NucleoReceptor(registry)

    def on_completado(payload: PromptPayload):
        resultado_final = {
            "flujo_id": payload.flujo_id,
            "exito": payload.completado,
            "estado": payload.estado,
            "resultados": payload.resultados,
            "timestamp_final": datetime.now(timezone.utc).isoformat(),
        }
        if callback_final:
            callback_final(resultado_final)

    flujo_id = distribuidor.distribuir_prompt(
        prompt_text=prompt_text,
        callback_completado=on_completado,
        timeout_segundos=timeout,
    )
    return {
        "exito": True,
        "flujo_id": flujo_id,
        "mensaje": f"Flujo iniciado. Esperando procesamiento de 4 modulos...",
        "timeout": timeout,
    }

def verificar_integracion_flujo() -> Dict[str, Any]:
    resultados = {
        "registry_disponible": False,
        "distribuidor_listo": False,
        "modulos_suscritos": [],
        "daimon_receptor_listo": False,
        "nucleo_receptor_listo": False,
    }
    try:
        registry = SharedDataRegistry()
        resultados["registry_disponible"] = True
        distribuidor = PromptDistributor(registry)
        resultados["distribuidor_listo"] = True
        for nombre, clase in [
            ("core_radar", RadarProcesador),
            ("core_predictor", PredictorProcesador),
            ("core_negotiation", NegotiationProcesador),
            ("network_monitor", NetworkProcesador),
        ]:
            try:
                clase(registry)
                resultados["modulos_suscritos"].append(nombre)
            except Exception:
                pass
        try:
            DaimonReceptor(registry)
            resultados["daimon_receptor_listo"] = True
        except Exception:
            pass
        try:
            NucleoReceptor(registry)
            resultados["nucleo_receptor_listo"] = True
        except Exception:
            pass
    except Exception as e:
        resultados["error"] = str(e)
    return resultados

# ================================================================================
# SECCION 38: MAIN V4 - ORQUESTACION CON CARGA SECUENCIAL FORZADA
# ================================================================================
def main():
    log("[START] SYMBIOSIS V4 - ORQUESTADOR CON ARQUITECTURA VERIFICADA (POTENCIADO)", "STARTUP")
    SYSTEM_STATE["started_at"] = datetime.now().isoformat()

    if is_termux():
        log("[PHONE] Termux detectado", "INFO")
    os.environ["PYTHONUNBUFFERED"] = "1"

    # --- BLOQUE: INICIALIZAR WATCHDOG Y MONITOR ---
    watchdog = ThreadWatchdogAdvanced(check_interval=3.0)
    watchdog.start_monitoring()
    set_global_watchdog(watchdog)

    monitor = ModuleThreadMonitor()
    monitor.set_logger(log)
    monitor.set_watchdog(watchdog)
    SYSTEM_STATE["global_monitor"] = monitor

    # --- BLOQUE: REGISTRAR MODULOS ---
    all_modules = [
        "core_config", "core_negotiation", "core_radar", "core_predictor",
        "core_daimon", "core_best_option", "frontend_web", "network_monitor",
        "main_system", "orchestrator",
    ]
    for mod in all_modules:
        monitor.register_module(mod, status=ModuleStatus.ACTIVE)

    log("=" * 60, "INFO")
    log("ARQUITECTURA DE MODULOS:", "INFO")
    log("=" * 60, "INFO")
    for mod in all_modules:
        expected = [name for name, m in THREAD_NAME_TO_MODULE.items() if m == mod]
        log(f" {mod}: {len(expected)} hilos esperados", "INFO")
    log("=" * 60, "INFO")

    # --- BLOQUE: PARCHEAR THREADING ---
    _patch_threading_with_monitor(monitor, watchdog)

    guard = SystemGuard(min_available_mb=300.0)
    guard.check_and_release()

    # --- BLOQUE: CARGA SECUENCIAL FORZADA ---
    load_order = [
        ("part1_config.py", "core_config", True),
        ("part2_negotiation.py", "core_negotiation", True),
        ("part3_radar.py", "core_radar", True),
        ("part4_predictor.py", "core_predictor", False),
        ("parte5_daimon_base.py", "core_daimon", True),
        ("part7_mejor_opcion.py", "core_best_option", True),
        ("part8_interfaz_web.py", "frontend_web", True),
        ("part9_network_monitor.py", "network_monitor", False),
    ]

    for filename, mod_name, is_critical in load_order:
        if not preload_module_with_diagnostics(filename, mod_name, is_critical, monitor=monitor):
            if is_critical:
                log(f"[FATAL] No se pudo cargar modulo critico: {mod_name}", "ERROR")
                return False
            else:
                log(f"[WARN] Modulo opcional fallo: {mod_name}", "WARN")
        time.sleep(0.3)

    # --- BLOQUE: INYECTAR CLASES DE CORE_PREDICTOR EN __main__ ---
    if "core_predictor" in sys.modules:
        predictor_mod = sys.modules["core_predictor"]
        for clase in ["DemandSample", "EnsembleDemandPredictor"]:
            if hasattr(predictor_mod, clase):
                setattr(sys.modules["__main__"], clase, getattr(predictor_mod, clase))
        log("[INJECT] Clases de predictor replicadas en __main__", "INFO")
    else:
        log("[WARN] core_predictor no cargado, no se inyectaron clases", "WARN")

    # --- BLOQUE: VERIFICAR CEO_AVANZADO ---
    if "core_daimon" in sys.modules:
        ceo_mod = sys.modules["core_daimon"]
        if hasattr(ceo_mod, 'ceo_avanzado') and ceo_mod.ceo_avanzado:
            globals()['ceo_avanzado'] = ceo_mod.ceo_avanzado
            log("[OK] ceo_avanzado disponible para modulos siguientes", "INFO")
        else:
            log("[ERROR] ceo_avanzado NO disponible", "ERROR")

    # --- BLOQUE: CARGAR MODULO PRINCIPAL ---
    main_module_found = False
    for main_file in ["part6_main.py", "lucifer_prometeo.py"]:
        if preload_module_with_diagnostics(main_file, "main_system", True, monitor=monitor):
            main_module_found = True
            break

    if not main_module_found:
        log("[ERROR] No se encontro modulo principal", "ERROR")
        return False

    main_mod = sys.modules.get("main_system")
    if not main_mod or not hasattr(main_mod, "main"):
        return False

    SYSTEM_STATE["main_module"] = main_mod
    SYSTEM_STATE["port"] = getattr(main_mod, "HTTP_PORT", 8989)
    main_mod.safe_thread = safe_thread
    main_mod.monitor = monitor
    main_mod.watchdog = watchdog

    # --- BLOQUE: INICIAR GUARDIAS DE RED Y PRIMER PLANO ---
    net_keep = NetworkKeepAlive(interval=15.0)
    tunnel = TunnelGuard(cmd="cloudflared tunnel --url http://127.0.0.1:8989")   # ← CORREGIDO
    fg_guard = AndroidForegroundGuard()
    fg_guard.acquire()
    net_keep.start()
    tunnel.start()

    if monitor:
        monitor.register_thread("network_monitor", net_keep.thread, "NetKeepAlive", persistent=True)
        monitor.register_thread("network_monitor", tunnel.thread, "TunnelGuard", persistent=True)
    if _global_watchdog:
        _global_watchdog.register_thread_advanced(
            "network_monitor", "NetKeepAlive", net_keep.thread, is_critical=False, max_restarts=3,
        )
        _global_watchdog.register_thread_advanced(
            "network_monitor", "TunnelGuard", tunnel.thread,
            is_critical=True, max_restarts=5,
            factory=lambda: _restart_tunnel(tunnel),
        )

    # --- BLOQUE: HILOS DE MONITOREO ---
    def delayed_start(name, target, delay, mod_name="orchestrator"):
        def wrap():
            time.sleep(delay)
            safe_thread(name, target, monitor, mod_name)
        threading.Thread(target=wrap, daemon=True).start()

    delayed_start("HealthLoop", health_loop, 2)
    delayed_start("InitialScan", lambda: (time.sleep(6), monitor.global_thread_scan(), log("Scan OK", "MONITOR")), 4)

    def monitor_loop():
        time.sleep(10)
        while not SYSTEM_STATE["shutdown"]:
            try:
                monitor.global_thread_scan()
                print(monitor.render_full_display(), flush=True)
            except Exception as e:
                log(f"[MONITOR] {e}", "ERROR")
            time.sleep(45)

    delayed_start("MonitorDisplay", monitor_loop, 8)

    # --- BLOQUE: LANZAR MODULO PRINCIPAL ---
    def main_wrapper():
        while not SYSTEM_STATE["shutdown"]:
            try:
                if gc.get_count()[0] > 800:
                    gc.collect()
                guard.check_and_release()
                main_mod.main()
            except Exception as e:
                log(f"[MAIN] {e}", "ERROR")
                traceback.print_exc()
                time.sleep(3)

    t_main = threading.Thread(target=main_wrapper, name="MainCore", daemon=True)
    t_main.start()
    monitor.register_thread("main_system", t_main, "MainCore", persistent=True)
    watchdog.register_thread_advanced(
        module_name="main_system", thread_name="MainCore",
        thread_obj=t_main, is_critical=True,
    )

    # --- BLOQUE: AUTO-REGISTRO DE HILOS VIVOS ---
    auto_registry = ThreadAutoRegistry()
    for t in threading.enumerate():
        t_name = t.name
        if is_ephemeral_thread(t_name):
            continue
        if not any(t is e["thread"] for entries in monitor._thread_registry.values() for e in entries):
            mod_detected = auto_registry.auto_detect_and_register(t)
            if mod_detected and mod_detected != "unknown":
                monitor.register_thread(mod_detected, t, t_name, persistent=True)
                log(f"[AUTO-REG] {t_name} -> {mod_detected}", "OK")

    # --- BLOQUE: ACTIVAR FLUJO ENGINE ---
    flujo = FlujoEngine(log_fn=log)
    flujo.load_modules()
    log("[FLUJO] Motor de flujo inicializado con modulos cargados", "OK")

    # --- BLOQUE: INICIALIZAR PROCESADORES MEJOR_OPCION ---
    inicializar_procesadores_mejor_opcion()

    def flujo_executor():
        time.sleep(15)
        while not SYSTEM_STATE["shutdown"]:
            try:
                resultado = flujo.execute_chain()
                if resultado.get("fallback_activo"):
                    log("[FLUJO] Fallback activo - notificando CEO queue", "WARN")
                else:
                    log(f"[FLUJO] Cadena completa: {resultado['modulos_ejecutados']}", "OK")
            except Exception as e:
                log(f"[FLUJO] Error en ejecucion: {e}", "ERROR")
            time.sleep(60)

    flujo_thread = threading.Thread(target=flujo_executor, name="FlujoEngine", daemon=True)
    flujo_thread.start()
    if monitor:
        monitor.register_thread("orchestrator", flujo_thread, "FlujoEngine", persistent=True)
    if _global_watchdog:
        _global_watchdog.register_thread_advanced(
            "orchestrator", "FlujoEngine", flujo_thread,
            is_critical=True, max_restarts=3,
        )

    # --- BLOQUE: SINCRONIZACION CON REGISTRY POST-CARGA ---
    sync_modules_with_registry(all_modules)

    # --- BLOQUE: ESCANEO INICIAL Y DEBUG ---
    time.sleep(3)
    monitor.global_thread_scan()
    print(monitor.render_full_display(), flush=True)
    print("\n=== DEBUG: REGISTRO DE HILOS ===", flush=True)
    for mod_name_debug, entries in monitor._thread_registry.items():
        for e in entries:
            print(f"  [{mod_name_debug}] {e['name']} - vivo: {e['thread'].is_alive()}", flush=True)
    print(f"=== TOTAL THREADS VIVOS: {threading.active_count()} ===\n", flush=True)

    while not SYSTEM_STATE["shutdown"]:
        time.sleep(0.05)

    net_keep.stop()
    tunnel.stop()
    fg_guard.release()
    return True


# ================================================================================
# SECCION 39: FUNCIONES AUXILIARES Y MANEJO DE SALIDA
# ================================================================================
def _restart_tunnel(tunnel_instance):
    tunnel_instance.stop()
    time.sleep(2)
    tunnel_instance.start()
    return tunnel_instance.thread

def handle_exit(sig, frame):
    log("[SYSTEM] Cierre solicitado", "INFO")
    SYSTEM_STATE["shutdown"] = True
    if SYSTEM_STATE["main_module"] and hasattr(SYSTEM_STATE["main_module"], "STOP_EVENT"):
        SYSTEM_STATE["main_module"].STOP_EVENT.set()
    if _global_watchdog:
        _global_watchdog.stop_monitoring()
    sys.exit(0)

try:
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
except Exception as e:
    log(f"[SIGNAL] Error: {e}", "ERROR")

# ================================================================================
# SECCION 40: PUNTO DE ENTRADA PRINCIPAL
# ================================================================================
if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except Exception as e:
        log(f"FATAL: {e}", "ERROR")
        sys.exit(1)
