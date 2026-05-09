#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================================================
# SECCION 1: METADATOS Y CONFIGURACION INICIAL
# ================================================================================
"""
PARTE 6/9 - SINGULARIDAD_OMEGA + NUCLEO SUPREMO + GOBIERNO MULTI-PARTE
Nucleo supremo de coordinacion + punto de entrada principal.
Gobierna al orquestador (Parte 00) y agrega estado de Partes 1-9.
Compatible Termux/Android - Python 3.6+
"""
import os
import sys
import time
import threading
import socket
import signal
import datetime
from datetime import timezone
import uuid
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import deque

# ================================================================================
# SECCION 2: IMPORTACION DE MODULOS CON FALLBACK (CORREGIDO)
# ================================================================================
sys.path.append(os.path.dirname(os.path.abspath(__file__)) if __file__ else str(Path.home()))

_imported = {}

def safe_import(module_name, symbols=None, aliases=None):
    """Importación segura con soporte para aliases (parte5 vs part5)."""
    try:
        # Intentar nombre principal
        module = __import__(module_name, fromlist=['*'])
    except ImportError:
        # Intentar alias si está definido
        if aliases and module_name in aliases:
            for alias in aliases[module_name]:
                try:
                    module = __import__(alias, fromlist=['*'])
                    break
                except ImportError:
                    continue
            else:
                return None  # Ningún alias funcionó
        else:
            return None
    except Exception:
        return None
    
    if module is None:
        return None
        
    if symbols is None:
        for sym in dir(module):
            if not sym.startswith('_'):
                _imported[sym] = getattr(module, sym)
    else:
        for sym in symbols:
            if hasattr(module, sym):
                _imported[sym] = getattr(module, sym)
    return sys.modules.get(module_name) or module

# Aliases para nombres inconsistentes
_MODULE_ALIASES = {
    'parte5_daimon_base': ['part5_daimon_base', 'parte5_daimon_base'],
    'part1_config': ['parte1_config', 'part1_config'],
}

safe_import('part1_config', [
    'GlobalConfig', 'log_event', 'log_banner', 'HyperNumberAdvanced',
    'GeoLocation', 'SharedDataRegistry'
], aliases=_MODULE_ALIASES)

safe_import('part2_negotiation', [
    'NegotiationAgent', 'NegotiationOrchestrator', 'ReputationSystem'
])

safe_import('part3_radar', ['UberRadarPro', 'ZoneSystem'])
safe_import('part4_predictor', ['UberDemandPredictor'])

# Parte 5 con alias para parte5/part5
safe_import('parte5_daimon_base', [
    'ConectorOllamaLocal', 'CEOIA', 'iniciar_ceoia_unificada',
    'iniciar_ceoia_con_integracion', 'integrar_gps_en_ceo',
    'actualizar_gps_a_mejor_opcion', 'forzar_actualizacion_gps_inmediata',
    'obtener_estado_gps', 'guardar_estado', 'save_daimon_brain',
    'log', 'UBER_COINS', 'ZONAS', 'zona_estado', 'ULTIMA_ZONA',
    'ESTADO_CONDUCTOR', 'GPS_ACTUAL', 'GPS_OBJETIVO', 'ALGO_WEIGHTS',
    'Q_TABLE', 'DAIMON_ID', 'HTTP_PORT', 'IA_READY', 'blockchain',
    'block_number', 'log_lock', 'mining_log'
], aliases=_MODULE_ALIASES)

safe_import('part7_mejor_opcion', [
    'activar_prompt_mejor_opcion', 'CONTROL_DE_CONFIANZA_Y_OPERACION',
    'TRUST_GUARD'
])

safe_import('part8_interfaz_web', ['app', 'registrar_endpoints_frontend'])

globals().update(_imported)

# ================================================================================
# SECCION 3: VARIABLES GLOBALES Y CONFIGURACION
# ================================================================================
STOP_EVENT = threading.Event()
simulation_active = True
data_lock = threading.Lock()
log_lock = threading.Lock()
mining_log = deque(maxlen=100)
HTTP_PORT = 8989
IA_READY = True
WEB_ACCESSED = False
MEJOR_OPCION_PROMPT_ACTIVO = False
HILO_CONDUCTOR_SIMULADO = None
MODO_NEGOCIACION_IA = False
ULTIMA_ZONA = "z1"
ESTADO_CONDUCTOR = "IDLE"
VIAJE_EN_CURSO = None
TIEMPO_INICIO_VIAJE = None
GPS_ACTIVO = False
GPS_ACTUAL = None
GPS_OBJETIVO = None
historial_gps = deque(maxlen=500)
ULTIMA_ACTUALIZACION_GPS = 0

ZONAS = [
    {"id": "z1", "nombre": "Albrook Mall", "lat_min": 8.97, "lat_max": 9.00, "lon_min": -79.54, "lon_max": -79.50},
    {"id": "z2", "nombre": "Arraijan Centro", "lat_min": 8.86, "lat_max": 8.90, "lon_min": -79.78, "lon_max": -79.74},
    {"id": "z3", "nombre": "La Chorrera Centro", "lat_min": 8.86, "lat_max": 8.89, "lon_min": -79.80, "lon_max": -79.76},
    {"id": "z4", "nombre": "San Carlos", "lat_min": 8.87, "lat_max": 8.90, "lon_min": -79.82, "lon_max": -79.78},
    {"id": "z5", "nombre": "Veracruz", "lat_min": 8.84, "lat_max": 8.87, "lon_min": -79.84, "lon_max": -79.80},
]
zona_estado = {z["id"]: {"color": "gris", "ganancia_estimada": 0.0, "tiempo_espera": 0.0,
                         "demanda": 0, "oferta": 0, "ratio_demanda": 0.0} for z in ZONAS}

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
    'sustainability_score': 15.0
}

DAIMON_ID = str(uuid.uuid4())[:8]
Q_TABLE = {}
Q_TABLE_LOCK = threading.RLock()
DAIMON_EPSILON = 0.1
BRAIN_CHANGE_COUNTER = 0
BRAIN_LAST_SAVE_TIME = 0

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-14e93c5071e14eaf8b27e58c968f5f84")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# ================================================================================
# SECCION 4: FUNCIONES UTILITARIAS BASE (CORREGIDO)
# ================================================================================
def log(msg, level="INFO"):
    """Función de logging segura para Termux."""
    try:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        lock = globals().get('log_lock')
        # Verificar que lock sea un contexto válido antes de usar 'with'
        if lock and hasattr(lock, '__enter__') and hasattr(lock, '__exit__'):
            with lock:
                print("[{0}] [{1}] {2}".format(timestamp, level, msg))
                sys.stdout.flush()
        else:
            # Fallback sin lock si no es un contexto válido
            print("[{0}] [{1}] {2}".format(timestamp, level, msg))
            sys.stdout.flush()
    except Exception:
        # Nunca permitir que un error de logging rompa la ejecución
        try:
            print("[LOG] " + str(msg))
            sys.stdout.flush()
        except Exception:
            pass  # Fallar silenciosamente en último recurso

# ================================================================================
# SECCION 5: INICIALIZACION DE VARIABLES CRITICAS (CORREGIDO)
# ================================================================================
def inicializar_variables():
    """Inicializa variables críticas con verificación de existencia."""
    global UBER_COINS, Q_TABLE, ALGO_WEIGHTS, ceo_avanzado, conector_ollama, gestor_deepseek
    
    # UBER_COINS con fallback seguro
    if 'UBER_COINS' not in globals() or globals().get('UBER_COINS') is None:
        if 'HyperNumberAdvanced' in globals():
            UBER_COINS = HyperNumberAdvanced(0.0)
        else:
            class _MinCoin:
                __slots__ = ('_val',)
                def __init__(self_inner, v=0.0): 
                    self_inner._val = float(v)
                def to_float_approx(self_inner): 
                    return self_inner._val
                def display(self_inner): 
                    return "{0:.2f}".format(self_inner._val)
                def add(self_inner, x): 
                    self_inner._val += float(x)
            UBER_COINS = _MinCoin(0.0)
        log("[OK] UBER_COINS inicializado")
    
    # Q_TABLE y ALGO_WEIGHTS con inicialización segura
    if not isinstance(globals().get('Q_TABLE'), dict):
        Q_TABLE = {}
    if not isinstance(globals().get('ALGO_WEIGHTS'), dict):
        ALGO_WEIGHTS = {"fare": 1.0, "engagement_rate": 15.0}
    
    # Variables opcionales con None explícito
    for var in ['ceo_avanzado', 'conector_ollama', 'gestor_deepseek', 
                'gobierno_supremo', 'app', 'monitor', 'safe_thread']:
        if var not in globals():
            globals()[var] = None

# ================================================================================
# SECCION 6: BUS DE GOBIERNO SUPREMO
# ================================================================================

class BusGobiernoSupremo:
    """Bus central de gobierno que controla al orquestador (Parte 00)
    y coordina todas las partes del sistema (1-9).
    La Parte 6 es el nucleo supremo: goberna al orquestador, no al reves."""

    PARTES_MONITORIZADAS = {
        "parte1": {"nombre": "Config/Base", "modulo": "part1_config", "critica": True},
        "parte2": {"nombre": "Negociacion", "modulo": "part2_negotiation", "critica": True},
        "parte3": {"nombre": "Radar", "modulo": "part3_radar", "critica": True},
        "parte4": {"nombre": "Predictor", "modulo": "part4_predictor", "critica": False},
        "parte5": {"nombre": "CEOIA/Daimon", "modulo": "parte5_daimon_base", "critica": True},
        "parte6": {"nombre": "Supremo (yo)", "modulo": "__main__", "critica": True},
        "parte7": {"nombre": "Mejor Opcion", "modulo": "part7_mejor_opcion", "critica": False},
        "parte8": {"nombre": "Interfaz Web", "modulo": "part8_interfaz_web", "critica": False},
        "parte9": {"nombre": "SocialCoin", "modulo": None, "critica": False},
    }

    def __init__(self):
        self.estado_partes = {}
        self.ordenes_pendientes = deque(maxlen=200)
        self.ordenes_ejecutadas = deque(maxlen=500)
        self.heartbeat_log = deque(maxlen=1000)
        self.override_orquestador = False
        self._lock = threading.RLock()
        self._inicializar_estado_partes()
        self._inicio = time.time()

    def _inicializar_estado_partes(self):
        for parte_id, info in self.PARTES_MONITORIZADAS.items():
            mod_name = info["modulo"]
            cargado = mod_name in sys.modules if mod_name else False
            self.estado_partes[parte_id] = {
                "nombre": info["nombre"],
                "modulo": mod_name,
                "critica": info["critica"],
                "cargada": cargado,
                "activa": False,
                "ultimo_heartbeat": 0.0,
                "errores_consecutivos": 0,
                "estado_reportado": "desconocido"
            }
        self.estado_partes["parte6"]["cargada"] = True
        self.estado_partes["parte6"]["activa"] = True

    def registrar_heartbeat(self, parte_id, estado=None):
        with self._lock:
            if parte_id in self.estado_partes:
                self.estado_partes[parte_id]["ultimo_heartbeat"] = time.time()
                self.estado_partes[parte_id]["activa"] = True
                self.estado_partes[parte_id]["errores_consecutivos"] = 0
                if estado:
                    self.estado_partes[parte_id]["estado_reportado"] = estado
                self.heartbeat_log.append({
                    "parte": parte_id, "timestamp": time.time(), "estado": estado
                })
                return True
            return False

    def reportar_error(self, parte_id, error_msg):
        with self._lock:
            if parte_id in self.estado_partes:
                self.estado_partes[parte_id]["errores_consecutivos"] += 1
                if self.estado_partes[parte_id]["errores_consecutivos"] > 5:
                    self.estado_partes[parte_id]["activa"] = False
                log("[GOV] Error " + parte_id + ": " + str(error_msg)[:80])
                return True
            return False

    def enviar_orden_a_orquestador(self, orden, prioridad="normal", payload=None):
        """Envia orden directa al orquestador (Parte 00)."""
        orden_data = {
            "id": str(uuid.uuid4())[:10],
            "origen": "parte6_supremo",
            "destino": "parte00_orquestador",
            "orden": orden,
            "prioridad": prioridad,
            "payload": payload or {},
            "timestamp": time.time(),
            "estado": "pendiente"
        }
        self.ordenes_pendientes.append(orden_data)
        log("[GOV] Orden al ORQUESTADOR: " + str(orden)[:60] + " (" + prioridad + ")")

        mod_orquestador = sys.modules.get('part00_start_all')
        if mod_orquestador and hasattr(mod_orquestador, 'recibir_orden_supremo'):
            try:
                mod_orquestador.recibir_orden_supremo(orden_data)
                orden_data["estado"] = "entregada"
            except Exception as e:
                log("[GOV] Error entregando al orquestador: " + str(e))
        else:
            orden_data["estado"] = "en_espera_orquestador"

        return orden_data

    def enviar_orden_a_parte(self, parte_destino, orden, prioridad="normal", payload=None):
        """Envia orden a una parte especifica (1-9)."""
        if parte_destino not in self.estado_partes:
            return {"exito": False, "error": "Parte desconocida"}
        info = self.estado_partes[parte_destino]
        mod_name = info["modulo"]
        if not mod_name or mod_name not in sys.modules:
            return {"exito": False, "error": "Modulo no cargado"}
        mod = sys.modules[mod_name]
        orden_data = {
            "id": str(uuid.uuid4())[:10], "origen": "parte6_supremo",
            "destino": parte_destino, "orden": orden, "prioridad": prioridad,
            "payload": payload or {}, "timestamp": time.time()
        }
        ejecutada = False
        if hasattr(mod, 'recibir_orden'):
            try:
                mod.recibir_orden(orden_data)
                ejecutada = True
            except Exception as e:
                log("[GOV] Error orden a " + parte_destino + ": " + str(e))
        if hasattr(mod, 'ceoia') and hasattr(mod.ceoia, 'recibir_orden'):
            try:
                mod.ceoia.recibir_orden(orden)
                ejecutada = True
            except Exception as e:
                log("[GOV] Error orden via CEOIA: " + str(e))
        if ejecutada:
            self.ordenes_ejecutadas.append(orden_data)
        return {"exito": ejecutada, "orden_id": orden_data["id"]}

    def broadcast_a_todas(self, orden, prioridad="normal", excluir=None):
        """Envia orden a todas las partes activas."""
        if excluir is None:
            excluir = ["parte6"]
        resultados = {}
        for parte_id, info in self.estado_partes.items():
            if parte_id in excluir:
                continue
            if info["activa"]:
                res = self.enviar_orden_a_parte(parte_id, orden, prioridad)
                resultados[parte_id] = res.get("exito", False)
        return resultados

    def activar_override_orquestador(self, activar=True):
        """Activa/desactiva modo override del orquestador."""
        self.override_orquestador = activar
        log("[GOV] Override orquestador: " + ("ACTIVADO" if activar else "DESACTIVADO"))
        return True

    def verificar_salud_sistema(self):
        """Verifica salud de todas las partes."""
        ahora = time.time()
        reporte = {"timestamp": ahora, "partes": {}, "criticas_ok": 0, "criticas_fallan": 0}
        for parte_id, info in self.estado_partes.items():
            tiempo_sin_heartbeat = ahora - info["ultimo_heartbeat"]
            esta_activa = info["activa"] and (not info["critica"] or tiempo_sin_heartbeat < 300)
            if not esta_activa and info["cargada"]:
                info["activa"] = False
            estado_salud = "ok" if esta_activa else ("inactiva" if not info["cargada"] else "posible_fallo")
            if info["critica"] and estado_salud != "ok":
                reporte["criticas_fallan"] += 1
            elif info["critica"]:
                reporte["criticas_ok"] += 1
            reporte["partes"][parte_id] = {
                "nombre": info["nombre"], "salud": estado_salud,
                "cargada": info["cargada"], "critica": info["critica"],
                "sin_heartbeat_seg": round(tiempo_sin_heartbeat, 0),
                "errores": info["errores_consecutivos"]
            }
        reporte["salud_global"] = "ok" if reporte["criticas_fallan"] == 0 else "degradado"
        reporte["uptime_seg"] = round(ahora - self._inicio, 0)
        return reporte

    def obtener_resumen_completo(self):
        """Retorna resumen completo del estado del sistema."""
        salud = self.verificar_salud_sistema()
        ceo = globals().get('ceo_avanzado')
        ceo_estado = {}
        if ceo and hasattr(ceo, 'estado_interno'):
            ceo_estado = dict(ceo.estado_interno)
        return {
            "gobierno_supremo": {
                "override_orquestador": self.override_orquestador,
                "ordenes_pendientes": len(self.ordenes_pendientes),
                "ordenes_ejecutadas": len(self.ordenes_ejecutadas),
                "uptime_seg": round(time.time() - self._inicio, 0)
            },
            "salud": salud,
            "ceoia": ceo_estado,
            "timestamp": time.time()
        }

# ================================================================================
# SECCION 7: AGREGACION DE ESTADO CROSS-PART
# ================================================================================

def agregar_estado_todas_partes():
    """Recopila estado de todas las partes disponibles (1-9)."""
    resultado = {"partes_disponibles": {}, "errores": [], "timestamp": time.time()}

    mapeo_extractores = {
        "parte1": lambda m: {"config": getattr(m, 'GlobalConfig', None) is not None},
        "parte2": lambda m: {"orchestrador": hasattr(m, 'NegotiationOrchestrator')},
        "parte3": lambda m: {"radar": hasattr(m, 'UberRadarPro')},
        "parte4": lambda m: {"predictor": hasattr(m, 'UberDemandPredictor')},
        "parte5": lambda m: _extraer_estado_parte5(m),
        "parte7": lambda m: {"mejor_opcion": hasattr(m, 'activar_prompt_mejor_opcion')},
        "parte8": lambda m: {"flask": hasattr(m, 'app')},
    }

    modulos_a_buscar = {
        "parte1": "part1_config", "parte2": "part2_negotiation",
        "parte3": "part3_radar", "parte4": "part4_predictor",
        "parte5": "parte5_daimon_base", "parte7": "part7_mejor_opcion",
        "parte8": "part8_interfaz_web",
    }

    for parte_id, mod_name in modulos_a_buscar.items():
        mod = sys.modules.get(mod_name)
        if mod is None:
            resultado["partes_disponibles"][parte_id] = {"estado": "no_cargada"}
            continue
        try:
            extractor = mapeo_extractores.get(parte_id)
            if extractor:
                resultado["partes_disponibles"][parte_id] = extractor(mod)
            else:
                resultado["partes_disponibles"][parte_id] = {"estado": "cargada_sin_extractor"}
        except Exception as e:
            resultado["partes_disponibles"][parte_id] = {"estado": "error", "error": str(e)}
            resultado["errores"].append(parte_id + ": " + str(e))

    ceo = globals().get('ceo_avanzado')
    if ceo:
        resultado["parte5_detalle"] = _extraer_estado_parte5_detallado(ceo)

    return resultado


def _extraer_estado_parte5(mod):
    ceo = getattr(mod, 'ceoia', None) or getattr(mod, 'ceo_avanzado', None) or globals().get('ceo_avanzado')
    if ceo is None:
        return {"ceoia": False}
    return {"ceoia": True, "tiene_ensemble": hasattr(ceo, 'ensemble')}


def _extraer_estado_parte5_detallado(ceo):
    detalle = {"id": DAIMON_ID}
    if hasattr(ceo, 'estado_interno'):
        detalle["estado_interno"] = dict(ceo.estado_interno)
    if hasattr(ceo, 'ensemble'):
        try:
            detalle["ensemble"] = ceo.ensemble.get_state()
        except Exception:
            detalle["ensemble"] = "error"
    if hasattr(ceo, 'permisos'):
        detalle["permisos_activos"] = [k for k, v in ceo.permisos.items() if v]
    if hasattr(ceo, 'km_learner') and ceo.km_learner:
        try:
            detalle["kilometraje"] = ceo.km_learner.get_stats()
        except Exception:
            detalle["kilometraje"] = "error"
    if hasattr(ceo, 'obtener_estado_integracion'):
        try:
            detalle["integracion"] = ceo.obtener_estado_integracion()
        except Exception:
            detalle["integracion"] = "no_disponible"
    return detalle

# ================================================================================
# SECCION 8: INYECCION DE ESTADO HACIA PARTE 1
# ================================================================================
def inyectar_estado_en_part1():
    mod_part1 = sys.modules.get('part1_config')
    if mod_part1 is None:
        log("[WARN] No se encontro modulo part1_config")
        return False
    atributos_seguros = [
        'STOP_EVENT', 'simulation_active', 'log', 'log_event', 'log_banner',
        'UBER_COINS', 'ZONAS', 'zona_estado', 'ULTIMA_ZONA', 'ESTADO_CONDUCTOR',
        'GPS_ACTUAL', 'GPS_OBJETIVO', 'ALGO_WEIGHTS', 'Q_TABLE', 'DAIMON_ID',
        'HTTP_PORT', 'IA_READY', 'blockchain', 'block_number'
    ]
    inyectadas = 0
    for attr in atributos_seguros:
        val = globals().get(attr)
        if val is not None:
            try:
                setattr(mod_part1, attr, val)
                inyectadas += 1
            except Exception:
                pass
    if not hasattr(mod_part1, 'log') or mod_part1.log is None:
        mod_part1.log = log
    ceo = globals().get('ceo_avanzado')
    if ceo:
        try:
            mod_part1.ceoia = ceo
            mod_part1.ceo_avanzado = ceo
        except Exception:
            pass
    log("[OK] Estado inyectado en part1_config: " + str(inyectadas) + " atributos seguros")
    return True

# ================================================================================
# SECCION 9: SINGULARIDAD_OMEGA Y CICLOS AUTONOMOS
# ================================================================================
def SINGULARIDAD_OMEGA(**kwargs):
    global ceo_avanzado
    if ceo_avanzado and hasattr(ceo_avanzado, 'controlar_singularidad_omega'):
        return ceo_avanzado.controlar_singularidad_omega(**kwargs)
    return {"exito": False, "alertas": ["CEO no disponible"], "ganancias_generadas": 0.0}


def ciclo_autonomo_singularidad_omega(duracion_total_minutos=120, intervalo_ciclo_segundos=60):
    log("[INFO] INICIANDO CICLO AUTONOMO SINGULARIDAD_OMEGA")
    start = time.time()
    end = start + duracion_total_minutos * 60
    ciclos = 0
    while time.time() < end and not STOP_EVENT.is_set():
        try:
            SINGULARIDAD_OMEGA(duracion_ciclo=intervalo_ciclo_segundos)
            ciclos += 1
            time.sleep(intervalo_ciclo_segundos)
        except Exception as e:
            log("[ERROR] Error en ciclo singularidad: " + str(e))
            time.sleep(10)
    log("[OK] Ciclo singularidad completado: " + str(ciclos) + " iteraciones")


def encontrar_puerto_libre(puerto_inicial=8989, max_intentos=20):
    for i in range(max_intentos):
        puerto = puerto_inicial + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", puerto)) != 0:
                    return puerto
        except Exception:
            continue
    return None

# ================================================================================
# SECCION 10: FLUJO MEJOR OPCION (DEGRADACION SEGURA)
# ================================================================================
def inicializar_flujo_mejor_opcion():
    """Inicializa flujo MEJOR_OPCION. Degrada seguro si las clases
    PromptDistributor/ModuloProcesador no existen en ninguna parte."""
    clases_disponibles = {
        'SharedDataRegistry': 'SharedDataRegistry' in globals(),
        'PromptDistributor': 'PromptDistributor' in globals(),
        'ModuloProcesador': 'ModuloProcesador' in globals(),
    }
    faltantes = [k for k, v in clases_disponibles.items() if not v]
    if faltantes:
        log("[WARN] Flujo MEJOR_OPCION: clases faltantes (" + ", ".join(faltantes) + "), modo fallback activo")
        return False
    try:
        registry = SharedDataRegistry()
        distribuidor = PromptDistributor(registry)
        log("[OK] Flujo MEJOR_OPCION inicializado con PromptDistributor")
        return True
    except Exception as e:
        log("[WARN] Flujo MEJOR_OPCION: error inicializando (" + str(e)[:60] + "), modo fallback")
        return False

# ================================================================================
# SECCION 11: GOBERNANZA DEL ORQUESTADOR PARTE 00
# ================================================================================
def gobernar_orquestador(accion, **kwargs):
    """Ejecuta accion de gobierno sobre el orquestador (Parte 00).
    La Parte 6 gobierna al orquestador, no al reves."""
    gov = globals().get('gobierno_supremo')
    if gov is None:
        return {"exito": False, "error": "Gobierno supremo no inicializado"}

    if accion == "verificar_salud":
        return gov.verificar_salud_sistema()
    elif accion == "resumen_completo":
        return gov.obtener_resumen_completo()
    elif accion == "override":
        return gov.activar_override_orquestador(kwargs.get("activar", True))
    elif accion == "orden":
        destino = kwargs.get("destino", "parte00_orquestador")
        orden = kwargs.get("orden", "")
        prioridad = kwargs.get("prioridad", "normal")
        if destino == "parte00_orquestador":
            return gov.enviar_orden_a_orquestador(orden, prioridad, kwargs.get("payload"))
        else:
            return gov.enviar_orden_a_parte(destino, orden, prioridad, kwargs.get("payload"))
    elif accion == "broadcast":
        return gov.broadcast_a_todas(kwargs.get("orden", ""), kwargs.get("prioridad", "normal"))
    elif accion == "agregar_estado":
        return agregar_estado_todas_partes()
    elif accion == "reiniciar_parte":
        parte = kwargs.get("parte")
        if parte:
            return _intentar_reiniciar_parte(parte)
        return {"exito": False, "error": "No se especifico parte"}
    else:
        return {"exito": False, "error": "Accion desconocida: " + str(accion)}


def _intentar_reiniciar_parte(parte_id):
    """Intenta reiniciar una parte fallida del sistema."""
    mod_name = {"parte1": "part1_config", "parte2": "part2_negotiation",
                "parte3": "part3_radar", "parte4": "part4_predictor",
                "parte5": "parte5_daimon_base", "parte7": "part7_mejor_opcion",
                "parte8": "part8_interfaz_web"}.get(parte_id)
    if not mod_name:
        return {"exito": False, "error": "Parte no tiene modulo asociado"}
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    safe_import(mod_name)
    recargada = mod_name in sys.modules
    gov = globals().get('gobierno_supremo')
    if gov and parte_id in gov.estado_partes:
        gov.estado_partes[parte_id]["cargada"] = recargada
        gov.estado_partes[parte_id]["activa"] = recargada
        gov.estado_partes[parte_id]["errores_consecutivos"] = 0
    log("[GOV] Reinicio " + parte_id + ": " + ("OK" if recargada else "FALLO"))
    return {"exito": recargada, "modulo": mod_name}

# ================================================================================
# SECCION 12: FUNCION PRINCIPAL - CORRECCIONES CRÍTICAS
# ================================================================================
def _safe_thread_fallback(name, target, monitor=None, module_name=None):
    """Fallback de safe_thread cuando el orquestador no lo inyecta."""
    # Verificar que target sea callable antes de crear el hilo
    if not callable(target):
        log("[WARN] _safe_thread_fallback: target no es callable: " + str(name))
        return None
    try:
        t = threading.Thread(target=target, daemon=True, name=name)
        t.start()
        if monitor and hasattr(monitor, 'register') and callable(monitor.register):
            try:
                monitor.register(name, t)
            except Exception:
                pass  # Fallar silenciosamente si el monitor falla
        return t
    except Exception as e:
        log("[WARN] Error creando hilo " + name + ": " + str(e))
        return None


def main():
    global HTTP_PORT, ceo_avanzado, conector_ollama, gestor_deepseek, app
    global UBER_COINS, ZONAS, zona_estado, ULTIMA_ZONA, gobierno_supremo

    try:
        log("[INFO] INICIANDO NUCLEO SUPREMO - PARTE 6/9")
        log("=" * 80)

        # Inicializar estructuras base si no existen
        if not globals().get('ZONAS'):
            ZONAS = [{"id": "z1", "nombre": "Albrook Mall", "lat_min": 8.97, "lat_max": 9.00, "lon_min": -79.54, "lon_max": -79.50}]
        if not globals().get('zona_estado'):
            zona_estado = {z["id"]: {"color": "gris", "demanda": 0, "oferta": 0, "ratio_demanda": 0.0} for z in ZONAS}
        ULTIMA_ZONA = globals().get('ULTIMA_ZONA') or "z1"

        inicializar_variables()

        # --- GOBIERNO SUPREMO ---
        gobierno_supremo = BusGobiernoSupremo()
        globals()['gobierno_supremo'] = gobierno_supremo
        log("[OK] Bus de Gobierno Supremo inicializado")

        # --- INYECCION A PARTE 1 ---
        inyectar_estado_en_part1()

        # --- FLUJO MEJOR OPCION (degradación segura) ---
        inicializar_flujo_mejor_opcion()

        # --- CONFIGURACION OLLAMA ---
        conector_ollama = None
        try:
            if 'ConectorOllamaLocal' in globals() and callable(globals()['ConectorOllamaLocal']):
                conector_ollama = ConectorOllamaLocal(modelo="qwen2.5:0.5b", timeout=120)
                if hasattr(conector_ollama, 'diagnostico_conexion') and conector_ollama.diagnostico_conexion():
                    log("[OK] Ollama Local CONECTADO")
                else:
                    conector_ollama = None
        except Exception as e:
            log("[WARN] Error Ollama: " + str(e))
            conector_ollama = None

        # --- CONFIGURACION DEEPSEEK ---
        gestor_deepseek = None
        try:
            class _SimpleDeepSeek:
                __slots__ = ('api_key',)
                def __init__(self_inner, api_key): 
                    self_inner.api_key = api_key
                def consultar_deepseek(self_inner, prompt, contexto="", max_tokens=500):
                    return {"exito": False, "respuesta": "DeepSeek modo basico"}
            gestor_deepseek = _SimpleDeepSeek(DEEPSEEK_API_KEY)
        except Exception:
            gestor_deepseek = None

        # --- INICIALIZACION CEO ---
        ceo_avanzado = None
        try:
            iniciar_fn = globals().get('iniciar_ceoia_con_integracion') or globals().get('iniciar_ceoia_unificada')
            if iniciar_fn and callable(iniciar_fn):
                ceo_avanzado = iniciar_fn()
                if ceo_avanzado:
                    globals()['ceoia'] = ceo_avanzado
                    mod_part1 = sys.modules.get('part1_config')
                    if mod_part1:
                        try:
                            mod_part1.ceoia = ceo_avanzado
                            mod_part1.ceo_avanzado = ceo_avanzado
                        except Exception:
                            pass
                    if conector_ollama and hasattr(ceo_avanzado, 'conectar_ollama') and callable(ceo_avanzado.conectar_ollama):
                        ceo_avanzado.conectar_ollama()
                    log("[OK] CEO IA UNIFICADA ACTIVA")
            else:
                log("[WARN] iniciar_ceoia_unificada no disponible")
        except Exception as e:
            log("[ERROR] Error CEO: " + str(e))
            ceo_avanzado = None

        # --- INTEGRACION GPS ---
        try:
            integrar_fn = globals().get('integrar_gps_en_ceo')
            if ceo_avanzado and integrar_fn and callable(integrar_fn):
                integrar_fn(ceo_avanzado)
                log("[OK] GPS integrado")
        except Exception as e:
            log("[WARN] Error GPS: " + str(e))

        # --- REGISTRAR CEO EN GOBIERNO ---
        if ceo_avanzado and gobierno_supremo:
            gobierno_supremo.registrar_heartbeat("parte5", "ceoia_activa")
            gobierno_supremo.estado_partes["parte5"]["activa"] = True

        # --- VERIFICACION COMPONENTES ---
        log("[INFO] COMPONENTES:")
        log("   - Gobierno Supremo: [OK]")
        log("   - CEO: [" + ("OK" if ceo_avanzado else "ERROR") + "]")
        log("   - Ollama: [" + ("OK" if conector_ollama else "NO") + "]")
        log("   - DeepSeek: [" + ("OK" if gestor_deepseek else "NO") + "]")

        # --- PUERTO ---
        HTTP_PORT = encontrar_puerto_libre(8989) or 9000
        log("[INFO] Puerto: " + str(HTTP_PORT))

        # --- SINCRONIZACION FRONTEND ---
        try:
            sync_fn = globals().get('sincronizar_variables_globales')
            if sync_fn and callable(sync_fn):
                sync_fn(sys.modules[__name__])
        except Exception:
            pass

        # ================================================================
        # SAFE_THREAD: INYECTADO O FALLBACK PROPIO
        # ================================================================
        safe_thread = globals().get('safe_thread')
        if not safe_thread or not callable(safe_thread):
            safe_thread = _safe_thread_fallback
        monitor = globals().get('monitor')

        if ceo_avanzado is None:
            log("[ERROR] CEO no inicializado, operando en modo degradado")

        # --- LANZAR HILOS DEL CEO ---
        if ceo_avanzado:
            hilos_info = [
                ("Bucle Autonomo", getattr(ceo_avanzado, 'daimon_autonomous_loop', None)),
                ("Actualizar Zonificacion", getattr(ceo_avanzado, 'actualizar_zonificacion', None)),
                ("Simular Ruta", getattr(ceo_avanzado, 'simulate_route_loop', None)),
                ("Mente Autonoma", getattr(ceo_avanzado, 'mente_autonoma_socialcoin', None)),
                ("Conductor IA", getattr(ceo_avanzado, 'conductor_ia_loop_controlado', None)),
                ("Vigilancia CEO", getattr(ceo_avanzado, 'ciclo_vigilancia_ceo', None)),
                ("Radar Externo", getattr(ceo_avanzado, 'simular_radar_externo', None)),
                ("Radar Ollama", getattr(ceo_avanzado, 'ciclo_radar_ollama_automatico', None)),
            ]
            for name, target in hilos_info:
                if target and callable(target):
                    safe_thread(name, target, monitor=monitor, module_name="main_system")

            omega_target = getattr(ceo_avanzado, 'ciclo_autonomo_singularidad_omega', None)
            if omega_target and callable(omega_target):
                safe_thread("Singularidad Omega", omega_target, monitor=monitor, module_name="main_system")

        # --- GOBERNAR AL ORQUESTADOR ---
        if gobierno_supremo and hasattr(gobierno_supremo, 'enviar_orden_a_orquestador'):
            gobierno_supremo.enviar_orden_a_orquestador(
                "NUCLEO_SUPREMO_ACTIVO",
                prioridad="alta",
                payload={"parte6_lista": True, "timestamp": time.time()}
            )

        # --- FLASK (NO BLOQUEANTE EN TERMUX) ---
        if 'app' in globals() and app:
            log("[INFO] Flask en puerto " + str(HTTP_PORT))
            # En Termux, ejecutar Flask en hilo separado para no bloquear
            def run_flask():
                try:
                    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False, use_reloader=False, threaded=True)
                except Exception as e:
                    log("[ERROR] Flask error: " + str(e))
            
            flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskServer")
            flask_thread.start()
            
            # Modificado: bucle de espera con captura de interrupción y finally que limpia
            try:
                while not STOP_EVENT.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                log("[WARN] Interrupción manual, parando...")
                STOP_EVENT.set()
            finally:
                cleanup_and_exit()
        else:
            log("[INFO] Flask no disponible, modo consola")
            try:
                while not STOP_EVENT.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                log("[WARN] Interrupción manual, parando...")
                STOP_EVENT.set()
            finally:
                cleanup_and_exit()

    except Exception as e:
        log("[ERROR] ERROR CRITICO: " + str(e))
        import traceback
        traceback.print_exc()
        STOP_EVENT.set()
    finally:
        # Asegurar que la limpieza siempre se ejecute, incluso si arriba no se capturó
        cleanup_and_exit()


# ================================================================================
# SECCION 13: LIMPIEZA Y SEÑALES (CORREGIDO - SIN LLAMAR A sys.exit)
# ================================================================================
_limpieza_realizada = False
_limpieza_lock = threading.Lock()

def cleanup_and_exit():
    """Limpieza segura. Se llama desde finally o manual. No usa sys.exit()."""
    global _limpieza_realizada, STOP_EVENT
    with _limpieza_lock:
        if _limpieza_realizada:
            return
        _limpieza_realizada = True

    log("[INFO] Ejecutando limpieza final...")
    STOP_EVENT.set()

    # Dar un breve plazo para que los hilos terminen
    time.sleep(0.5)

    # Guardar estado
    for fn_name in ['guardar_estado', 'save_daimon_brain']:
        fn = globals().get(fn_name)
        if fn and callable(fn):
            try:
                fn()
            except Exception as e:
                log(f"[WARN] Error en {fn_name}: {e}")

    # Detener hilos de red si están presentes
    for obj_name in ['net_keep', 'tunnel', 'fg_guard']:
        obj = globals().get(obj_name)
        if obj:
            try:
                if hasattr(obj, 'stop'):
                    obj.stop()
                elif hasattr(obj, 'release'):
                    obj.release()
            except Exception:
                pass

    log("[OK] Sistema detenido limpiamente")

# Manejador de señal mínimo: solo activa el evento y avisa
def _signal_handler(signum, frame):
    log("[INFO] Señal recibida, iniciando parada ordenada...")
    STOP_EVENT.set()

# Registrar señales con fallback para Termux
try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
except (ValueError, OSError) as e:
    log("[WARN] No se pudieron registrar señales: " + str(e))

# ================================================================================
# SECCION 14: DECORADOR DE GOBERNANZA CEOIA
# ================================================================================
def ceo_governed(module_name=None):
    def decorator(module):
        module.__ceo_governed__ = True
        module.__ceo_registered_at__ = datetime.datetime.now(timezone.utc).isoformat()
        try:
            ceo = globals().get('ceo_avanzado')
            if ceo and hasattr(ceo, 'register_module'):
                ceo.register_module(
                    name=module_name or module.__name__,
                    module_ref=module,
                    registered_at=module.__ceo_registered_at__
                )
        except Exception:
            pass
        return module
    return decorator

# ================================================================================
# SECCION 15: PUNTO DE ENTRADA PRINCIPAL
# ================================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("[OK] INICIANDO NUCLEO SUPREMO - PARTE 6/9")
    print("=" * 80)

    if 'STOP_EVENT' not in globals():
        STOP_EVENT = threading.Event()
    if 'HOME' not in globals():
        HOME = Path.home()

    try:
        main()
    except Exception as e:
        print("[ERROR] Error fatal: " + str(e))
        traceback.print_exc()
        cleanup_and_exit()
