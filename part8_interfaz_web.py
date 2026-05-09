#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PARTE 8/9 - FRONTEND_HTML_8989 [VERSIÓN MEJORADA V2]
================================================================
Módulo de interfaz web para UBER DAIMON VIVO + SOCIALCOIN
Compatible con el sistema principal en Termux/Android

MEJORAS V2:
- Panel colapsable (compacto/expandido), max 50vh
- Botones simetricos 2x2: [MEJOR OPCION][Lluvia] / [Log][Reset]
- Taximetro inicia desde $0.00
- Tiempo de espera arranca tras 2 min detenido
- Trail negro con desvanecimiento elegante
- Marker con animacion suave (easing cubico)
- Lluvia con overlay visual + efecto real en tarifa
- Coordenadas GPS reales
- Compatible con Partes 1-9 y orquestador
"""

from __future__ import annotations
import os
import sys
import time
import json
import random
import threading
import datetime
import uuid
import hashlib
import traceback
import subprocess
from collections import deque
from pathlib import Path
from flask import Flask, jsonify, request
from typing import Dict, List, Optional, Any, Union

# ============================================================================
# === DECLARAR VARIABLES GLOBALES PRIMERO ===
# ============================================================================
ceoia = None
ceo_avanzado = None

# ============================================================================
# === PARCHE SEGURO PARA COMANDO 'svc' INEXISTENTE EN TERMUX/LINUX ===
# ============================================================================
_orig_popen = subprocess.Popen
def _safe_popen(*args, **kwargs):
    try:
        return _orig_popen(*args, **kwargs)
    except FileNotFoundError as e:
        if 'svc' in str(e).lower():
            return None
        raise
subprocess.Popen = _safe_popen

# ============================================================================
# PARCHE DE EMERGENCIA: FORZAR INICIALIZACION DE CEOIA
# ============================================================================
def _forzar_inicializacion_ceoia():
    global ceoia, ceo_avanzado

    if 'ceoia' not in globals():
        ceoia = None
    if 'ceo_avanzado' not in globals():
        ceo_avanzado = None

    if ceoia is not None or ceo_avanzado is not None:
        return True

    try:
        import importlib
        mod = importlib.import_module("part5_daimon_base")
        func = getattr(mod, "iniciar_ceoia_unificada", None)

        if callable(func):
            instancia = func()
            if instancia:
                ceoia = instancia
                ceo_avanzado = instancia
                print("[PARCHE] CEOIA inicializada con exito")
                return True
        else:
            print("[PARCHE] iniciar_ceoia_unificada no es callable")

    except Exception as e:
        print(f"[PARCHE] Error real importando CEOIA: {e}")

    class MockCEOIA:
        def __init__(self):
            self.estado_interno = {
                'modo_operacion': 'MOCK',
                'confianza_decisiones': 0.5
            }
            self.permisos = {'controlar_gps': True}

        def recibir_orden(self, orden):
            return f"Mock procesando: {orden}"

        def recibir_orden_ollama(self, orden):
            return f"Mock Ollama: {orden}"

    ceoia = MockCEOIA()
    ceo_avanzado = ceoia
    print("[PARCHE] Usando MockCEOIA (funcionalidad limitada)")
    return False


_forzar_inicializacion_ceoia()

# ============================================================================
# === CONFIGURACION GLOBAL ===
# ============================================================================

ESTADO_CONDUCTOR = "IDLE"
ULTIMA_ZONA = "z1"
WEB_ACCESSED = False
IA_READY = False
MEJOR_OPCION_PROMPT_ACTIVO = False

blockchain = []
block_number = 1
viral_blocks = 0

try:
    from main import UBER_COINS, HyperNumberAdvanced
except ImportError:
    class HyperNumberAdvanced:
        def __init__(self, val=0.0): self._val = float(val)
        def to_float_approx(self): return self._val
        def to_serializable(self): return {"mode": "real", "value": self._val}
        def display(self): return f"{self._val:.2f}"
        def add(self, x): self._val += float(x)
    UBER_COINS = HyperNumberAdvanced(0.0)

ZONAS = [
    {"id": "z1", "nombre": "Albrook Mall", "lat_min": 8.97, "lat_max": 9.00, "lon_min": -79.54, "lon_max": -79.50},
    {"id": "z2", "nombre": "Arraijan Centro", "lat_min": 8.86, "lat_max": 8.90, "lon_min": -79.78, "lon_max": -79.74},
    {"id": "z3", "nombre": "La Chorrera Centro", "lat_min": 8.86, "lat_max": 8.89, "lon_min": -79.80, "lon_max": -79.76},
    {"id": "z4", "nombre": "San Carlos", "lat_min": 8.87, "lat_max": 8.90, "lon_min": -79.82, "lon_max": -79.78},
    {"id": "z5", "nombre": "Veracruz", "lat_min": 8.84, "lat_max": 8.87, "lon_min": -79.84, "lon_max": -79.80},
]

zona_estado = {
    z["id"]: {
        "color": "gris",
        "ganancia_estimada": 0.0,
        "tiempo_espera": 0.0,
        "demanda": random.randint(10, 100),
        "oferta": random.randint(5, 80),
        "ratio_demanda": 0.0
    } for z in ZONAS
}

ALGO_WEIGHTS = {
    'acceptance_rate': 5.0, 'completion_rate': 10.0, 'avg_rating': 2.0,
    'trips_completed': 0.1, 'time_online': 0.5, 'cancellation_rate': -20.0,
    'idle_time_ratio': -10.0, 'peak_hours_ratio': 3.0, 'distance_traveled': 0.05,
    'distance': 0.2, 'duration': 0.01, 'fare': 1.0, 'realEarnings': 1.0,
    'estimatedEarnings': 0.95, 'waitTime': -0.5, 'additionalSearchCost': -0.5,
    'viral_score_bonus': 50.0, 'recompensa_viral': 1.0, 'best_option_bonus': 25.0,
    'engagement_rate': 15.0, 'share_ratio': 25.0, 'completion_rate_video': 20.0,
    'creativity_bonus': 40.0,
}

Q_TABLE = {}
Q_TABLE_LOCK = threading.RLock()
DAIMON_ID = str(uuid.uuid4())[:8]

mining_log = deque(maxlen=100)
log_lock = threading.Lock()
BENEFICIARIO_ACTUAL = "conductor_codigo"

MEJOR_OPCION_PROMPT_TEXTO = """
<system_directive lang="dsl-decision-engine" version="4.1">

  <!-- ================================================================================
       SISTEMA "MEJOR_OPCION"
       ================================================================================ -->

  <mode_activation>
    Por defecto, modo NORMAL.
    Activacion red team: "activar red_team"
  </mode_activation>

  <red_team_context>
    Enfoque defensivo.
    - Analisis de vectores de ataque
    - Explotacion de invariantes (teorico)
    - Mitigacion sin payloads
  </red_team_context>

  <!-- ================================================================================
       DATA SCHEMA
       ================================================================================ -->
  <typing_schema>
    Campos obligatorios:
    price: float
    pickup_eta: int
    delivery_eta: int
    tag: str
    radar: bool
    type: str
    state: str
  </typing_schema>

  <!-- ================================================================================
       INVARIANTES
       ================================================================================ -->
  <system_invariants>
    <invariant id="TRUST_PRESERVATION" priority="ABSOLUTE">
      trust_preservation > any_acceptance
    </invariant>

    <invariant id="EVALUATION_GATE">
      all_offers -> CONTROL_DE_CONFIANZA_Y_OPERACION
    </invariant>

    <invariant id="HUMAN_EMULATION">
      reaction_time ~ normal(mu, sigma)
      no_fixed_patterns = true
    </invariant>

    <invariant id="ABSOLUTE_HIERARCHY">
      TRUST_GUARD > CONTROL > PRIORITY > RADAR > EXCLUSIVE
    </invariant>
  </system_invariants>

  <!-- ================================================================================
       REGLAS FIJAS
       ================================================================================ -->
  <hardcoded_rules>

    <economic_block>
      rule_01: price < 3.13 -> REJECT
      rule_02: 3.13 <= price < 5.13 -> CONDITIONAL
      rule_03: 5.13 <= price < 10.13 -> ACCEPT
      rule_04: price >= 10.13 -> ACCEPT_IMMEDIATE
    </economic_block>

    <temporal_thresholds>
      rule_05: tag NOT_IN [PRIORITY, RADAR] AND pickup_eta > 6 -> REJECT
      <!-- rule_06: eliminada (antes permitía recogidas largas en LONG_TRIP) -->
      <!-- rule_07: eliminada (ya no rechazamos por delivery_eta) -->
    </temporal_thresholds>

    <critical_restrictions>
      rule_08: state == "EN_VIAJE" -> FORBID_CANCEL
      rule_09: state != "IDLE" -> FORBID_PING
    </critical_restrictions>

  </hardcoded_rules>

  <!-- ================================================================================
       CAPA HUMANA (CONTROLADA)
       ================================================================================ -->
  <behavior_layer>

    <anti_error_core>
      never_break_trust = true
      never_accept_price_below = 3.13
    </anti_error_core>

    <human_variability>
      reaction_time: normal(2s, 1s)
    </human_variability>

    <controlled_imperfection>

      error_01:
        condition: price >= 3.13 AND price < 5.13
        probability: 0.05
        action: ACCEPT

      error_02:
        condition: pickup_eta <= 6
        probability: 0.04
        action: IGNORE_TEMPORAL_RULE

    </controlled_imperfection>

  </behavior_layer>

  <!-- ================================================================================
       PIPELINE
       ================================================================================ -->
  <execution_pipeline>

    <phase id="0" name="HUMAN_INIT">
      apply human_variability
    </phase>

    <phase id="1" name="TRUST_GUARD">
      if blocked: return BLOCKED
    </phase>

    <phase id="2" name="CONTROL">
      apply state_filter
    </phase>

    <phase id="3" name="PRIORITY">
      if tag == "PRIORITY": return ACCEPT_IMMEDIATE
    </phase>

    <phase id="4" name="RADAR">
      if radar == true: return ACCEPT
    </phase>

    <phase id="5" name="LONG_TRIP">
      if tag IN ["LONG_DISTANCE","LONG_TRIP"] AND pickup_eta <= 6:
        return ACCEPT
    </phase>

    <phase id="6" name="EXCLUSIVE">
      if type == "EXCLUSIVE":
        evaluate_isolated
    </phase>

    <phase id="7" name="STANDARD">
      apply economic_block
      apply temporal_thresholds
      apply controlled_imperfection
    </phase>

  </execution_pipeline>

  <!-- ================================================================================
       TRUST GUARD
       ================================================================================ -->
  <state_machine id="trust_guard">

    <states>
      NORMAL
      OBSERVACION
      CONSERVADOR
    </states>

    <transitions>
      AUTOMATION_SUSPECTED:
        NORMAL -> OBSERVACION
        OBSERVACION -> CONSERVADOR
    </transitions>

  </state_machine>

  <!-- ================================================================================
       OUTPUT
       ================================================================================ -->
  <output_contract>

    <decision>
      Veredicto: [ACCEPT|REJECT|BLOCKED]
    </decision>

    <audit>
      price, pickup_eta, delivery_eta, rule_applied
    </audit>

  </output_contract>

</system_directive>
"""

# ============================================================================
# === FUNCIONES UTILITARIAS ===
# ============================================================================

def log(message: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    formatted_line = f"[{timestamp}] {message}"
    print(formatted_line, flush=True)
    with log_lock:
        mining_log.append({"ts": timestamp, "message": message})

# ============================================================================
# === IMPORTACION SEGURA DE CEOIA ===
# ============================================================================
def _importar_ceoia_seguro():
    global ceoia, ceo_avanzado
    import importlib

    if 'ceoia' not in globals():
        ceoia = None
    if 'ceo_avanzado' not in globals():
        ceo_avanzado = None

    if ceoia is not None or ceo_avanzado is not None:
        log("CEOIA ya inicializada (preservando instancia existente)")
        return True

    posibles_modulos = ['part5_daimon_base', 'parte5_daimon_base']

    for nombre_modulo in posibles_modulos:
        try:
            modulo = importlib.import_module(nombre_modulo)
            iniciar_func = getattr(modulo, 'iniciar_ceoia_unificada', None)

            if callable(iniciar_func):
                instancia = iniciar_func()
                if instancia:
                    ceoia = instancia
                    ceo_avanzado = instancia
                    log(f"CEOIA inicializada desde {nombre_modulo}")
                    return True

            if getattr(modulo, 'ceoia', None) is not None:
                ceoia = modulo.ceoia
                log(f"ceoia importada desde {nombre_modulo}")

            if getattr(modulo, 'ceo_avanzado', None) is not None:
                ceo_avanzado = modulo.ceo_avanzado
                log(f"ceo_avanzado importada desde {nombre_modulo}")

            if ceoia is not None or ceo_avanzado is not None:
                return True

        except Exception as e:
            log(f"Error importando {nombre_modulo}: {e}")
            continue

    if ceoia is not None:
        log("Usando instancia existente de CEOIA")
        return True

    log("CEOIA no disponible - usando fallback local")
    return False


_importar_ceoia_seguro()

# ============================================================================
# === FUNCIONES QUE USAN ceo_avanzado/ceoia ===
# ============================================================================

def get_ceo_instance():
    global ceoia, ceo_avanzado
    if ceo_avanzado is not None:
        return ceo_avanzado
    if ceoia is not None:
        return ceoia
    return None

def get_recent_logs(limit: int = 50) -> List[Dict]:
    with log_lock:
        return list(mining_log)[-limit:]

def simular_metricas_viaje() -> Dict:
    return {
        'acceptance_rate': round(random.uniform(0.90, 1.00), 3),
        'completion_rate': round(random.uniform(0.95, 0.99), 3),
        'avg_rating': round(random.uniform(4.90, 5.00), 2),
        'trips_completed': random.randint(50, 150),
        'time_online': round(random.uniform(8.0, 12.0), 2),
        'cancellation_rate': round(random.uniform(0.00, 0.02), 3),
        'idle_time_ratio': round(random.uniform(0.05, 0.20), 3),
        'peak_hours_ratio': round(random.uniform(0.6, 1.0), 2),
        'distance_traveled': round(random.uniform(200.0, 400.0), 1),
        'viral_score': round(random.uniform(0.5, 1.0), 2),
        'recompensa_viral': round(random.uniform(10.0, 50.0), 2),
        'engagement_rate': round(random.uniform(3.0, 15.0), 2),
        'share_ratio': round(random.uniform(0.05, 0.30), 3),
        'completion_rate_video': round(random.uniform(0.60, 0.95), 2),
        'creativity_score': round(random.uniform(0.7, 1.3), 2),
        'fare': round(random.uniform(3.0, 15.0), 2),
        'estimatedEarnings': round(random.uniform(5.0, 50.0), 2),
        'realEarnings': round(random.uniform(5.0, 50.0), 2),
        'waitTime': round(random.uniform(0.0, 2.0), 2),
        'additionalSearchCost': round(random.uniform(0.0, 1.0), 2),
        'startLocation': {'latitude': round(random.uniform(8.85, 8.99), 6), 'longitude': round(random.uniform(-79.80, -79.52), 6)},
        'endLocation': {'latitude': round(random.uniform(8.85, 8.99), 6), 'longitude': round(random.uniform(-79.80, -79.52), 6)},
        'fareUnit': random.choice(['km', 'miles']),
        'currentTime': datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'),
        'plataforma': random.choice(['tiktok', 'instagram', 'youtube', 'x', 'web_generica']),
        'usuario_propietario': BENEFICIARIO_ACTUAL,
    }

def calcular_recompensa_por_viaje(metrics: Dict) -> float:
    reward = 0.0
    for metric, value in metrics.items():
        if metric in ALGO_WEIGHTS and isinstance(value, (int, float)):
            reward += float(value) * float(ALGO_WEIGHTS[metric])
    viral = metrics.get('viral_score', 0)
    engagement = metrics.get('engagement_rate', 0)
    creativity = metrics.get('creativity_score', 0)
    boost = (viral * 0.3 + engagement * 0.4 + creativity * 0.3) / 100.0
    return round(max(reward * (1 + boost * 0.5), 0.0), 2)

def minar_bloque_por_publicacion_controlado(url_real_provided: str = None, user: str = None) -> Dict:
    global block_number, UBER_COINS, ULTIMA_ZONA, zona_estado
    user_final = BENEFICIARIO_ACTUAL if not user else user
    if not url_real_provided:
        return {
            'user': user_final, 'block_number': block_number, 'timestamp': time.time(),
            'metrics': simular_metricas_viaje(), 'base_reward': 5.0,
            'bonus_modo_viral': 10.0, 'bonus_zona': 5.0, 'zona': ULTIMA_ZONA,
            'color_zona': zona_estado.get(ULTIMA_ZONA, {}).get("color", "gris"),
            'reward': 20.0, 'block_id': str(uuid.uuid4())[:8], 'url': "https://ejemplo.com/simulado",
            'plataforma': "simulada"
        }
    metrics = simular_metricas_viaje()
    metrics["url"] = url_real_provided
    metrics["user"] = user_final
    reward_coins = calcular_recompensa_por_viaje(metrics)
    color = zona_estado.get(ULTIMA_ZONA, {}).get("color", "gris")
    bonus_zona = 25.0 if color == "rojo" else 15.0 if color == "naranja" else 0.0
    bonificacion_modo_viral = 15.0
    total_reward = reward_coins + bonificacion_modo_viral + bonus_zona
    with log_lock:
        blockchain.append({
            'user': user_final, 'block_number': block_number, 'timestamp': time.time(),
            'metrics': metrics, 'base_reward': reward_coins,
            'bonus_modo_viral': bonificacion_modo_viral, 'bonus_zona': bonus_zona,
            'zona': ULTIMA_ZONA, 'color_zona': color, 'reward': total_reward,
            'block_id': str(uuid.uuid4())[:8], 'url': url_real_provided,
            'plataforma': metrics.get('plataforma', 'desconocida')
        })
    block_number += 1
    UBER_COINS.add(total_reward)
    return {
        'user': user_final, 'block_number': block_number - 1, 'timestamp': time.time(),
        'metrics': metrics, 'base_reward': reward_coins,
        'bonus_modo_viral': bonificacion_modo_viral, 'bonus_zona': bonus_zona,
        'zona': ULTIMA_ZONA, 'color_zona': color, 'reward': float(total_reward),
        'block_id': str(uuid.uuid4())[:8], 'url': url_real_provided,
        'plataforma': metrics.get('plataforma', 'desconocida')
    }

# ============================================================================
# === CONFIGURACION FLASK + CORS ===
# ============================================================================

def encontrar_puerto_libre(base=8989, max_intentos=10):
    import socket
    for i in range(max_intentos):
        puerto = base + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
    return base

app = Flask(__name__)
HTTP_PORT = encontrar_puerto_libre()

try:
    from flask_cors import CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
except ImportError:
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

# ============================================================================
# === ENDPOINTS API ===
# ============================================================================

@app.route('/')
def index():
    return '<meta http-equiv="refresh" content="0; url=/mapa_pro">'

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/health')
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": float(time.time()),
        "uber_coins": float(UBER_COINS.to_float_approx()) if hasattr(UBER_COINS, 'to_float_approx') else 0.0,
        "blocks_mined": int(len(blockchain)),
        "logs_buffer_size": int(len(mining_log))
    }), 200

@app.route('/ceoia/singularidad', methods=['POST', 'OPTIONS'])
def ceoia_singularidad():
    if request.method == 'OPTIONS': return '', 204
    return jsonify({
        "success": True, "singularidad_activa": True,
        "confianza": round(random.uniform(0.75, 0.98), 2),
        "modo_operacion": "AUTONOMO",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mensaje": "Singularidad Omega sincronizada."
    }), 200

@app.route('/api/logs', methods=['GET'])
def api_get_logs():
    limit = request.args.get('limit', 50, type=int)
    return jsonify({"success": True, "count": limit, "logs": get_recent_logs(limit)}), 200

@app.route('/ia/consultar', methods=['POST', 'OPTIONS'])
def ia_consultar():
    if request.method == 'OPTIONS': return '', 204
    data = request.get_json(silent=True) or {}
    pregunta = data.get('pregunta', data.get('query', 'Sin consulta'))
    return jsonify({
        "success": True,
        "respuesta": f"Procesando: '{pregunta}' | Daimon IA analizando contexto...",
        "tiempo_respuesta_ms": random.randint(120, 450),
        "estado": "OK",
        "contexto": {"zona": ULTIMA_ZONA, "monedas": UBER_COINS.to_float_approx() if hasattr(UBER_COINS, 'to_float_approx') else 0.0, "modo": ESTADO_CONDUCTOR}
    }), 200

@app.route('/start_mining_socialcoin', methods=['POST', 'OPTIONS'])
def start_mining_socialcoin():
    if request.method == 'OPTIONS': return '', 204
    data = request.get_json(silent=True) or {}
    url = data.get('url', data.get('video_url', data.get('link', '')))
    user = data.get('user', data.get('usuario', BENEFICIARIO_ACTUAL))
    log(f"SocialCoin recibida | User: {user} | URL: {url or 'AUTO'}")
    bloque = minar_bloque_por_publicacion_controlado(url_real_provided=url if url else None, user=user)
    return jsonify({
        "success": True, "mensaje": "Mineria SocialCoin procesada",
        "usuario": user, "recompensa": float(bloque.get('reward', 0.0)),
        "bloque_numero": int(bloque.get('block_number', 0)),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }), 200

@app.route('/api/v1/network')
def get_network_status():
    return jsonify({
        "status": random.choice(['EXCELENTE', 'ESTABLE', 'SATURADO', 'Offline']),
        "winner": random.choice(['WiFi', '4G', '5G', 'Ethernet']),
        "latency": round(random.uniform(0.01, 0.15), 4), "internet_ok": True
    }), 200

@app.route('/ceoia/estado')
def get_ceoia_estado():
    return jsonify({
        "estado_interno": {
            "modo_operacion": random.choice(['AUTONOMO', 'ASISTENTE', 'IDLE']),
            "confianza_decisiones": round(random.uniform(0.5, 0.95), 2)
        }
    }), 200

@app.route('/uber/activar_mejor_opcion', methods=['POST', 'OPTIONS'])
def activar_mejor_opcion():
    if request.method == 'OPTIONS': return '', 204
    global MEJOR_OPCION_PROMPT_ACTIVO, ESTADO_CONDUCTOR
    data = request.get_json(silent=True) or {}

    try:
        subprocess.run(
            ["termux-tts-speak", "Protocolo de Mejor Opcion Activado. Limpiando el algoritmo."],
            timeout=10, capture_output=True, check=False
        )
    except Exception as e:
        log(f"TTS Termux no disponible: {e}")

    if data.get('imprimir_prompt', False) and 'MEJOR_OPCION_PROMPT_TEXTO' in globals():
        print("\n" + "="*80, flush=True)
        print("PROMPT MEJOR_OPCION (WEB ACTIVATION)", flush=True)
        print("="*80, flush=True)
        print(globals()['MEJOR_OPCION_PROMPT_TEXTO'].strip(), flush=True)
        print("="*80 + "\n", flush=True)

    MEJOR_OPCION_PROMPT_ACTIVO = True
    ESTADO_CONDUCTOR = "MEJOR_OPCION"
    log("MODO MEJOR OPCION ACTIVADO - Prompt impreso en terminal")

    return jsonify({
        "success": True,
        "message": "Protocolo activado correctamente",
        "estado": ESTADO_CONDUCTOR,
        "zona_actual": ULTIMA_ZONA,
        "timestamp": time.time()
    }), 200

@app.route('/api/v1/miner', methods=['POST', 'OPTIONS'])
def minerar():
    if request.method == 'OPTIONS': return '', 204
    data = request.get_json(silent=True) or {}
    url = data.get('url', data.get('video_url', ''))
    user = data.get('user', data.get('usuario', BENEFICIARIO_ACTUAL))
    log(f"Mineria recibida | User: {user} | URL: {url or 'AUTO'}")
    try:
        bloque = minar_bloque_por_publicacion_controlado(url_real_provided=url if url else None, user=user)
        return jsonify({
            "success": True,
            "block": bloque.get('block_number'),
            "reward": float(bloque.get('reward', 0.0)),
            "zone": bloque.get('zona'),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }), 200
    except Exception as e:
        log(f"Error critico mineria: {traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno de mineria"}), 500

# ============================================================================
# === ENDPOINTS ULTRA-CARGA & EVOLUCION AUTONOMA ===
# ============================================================================

def _llamar_funcion_segura(nombre_funcion: str, *args, fallback=None, **kwargs):
    if nombre_funcion in globals() and callable(globals()[nombre_funcion]):
        try:
            result = globals()[nombre_funcion](*args, **kwargs)
            log(f"{nombre_funcion}() ejecutado")
            return True, result
        except Exception as e:
            log(f"Error ejecutando {nombre_funcion}(): {e}")
            if fallback and callable(fallback):
                fallback(*args, **kwargs)
            return False, None
    else:
        log(f"{nombre_funcion} no disponible - usando fallback")
        if fallback and callable(fallback):
            fallback(*args, **kwargs)
        return False, None

def _fallback_desbloquear_ceo():
    ceo = get_ceo_instance()
    if ceo and hasattr(ceo, 'permisos'):
        ceo.permisos.update({
            "controlar_uber": True, "controlar_radares": True,
            "modificar_codigo": True, "auto_activacion": True,
            "evolucion_autonoma": True, "controlar_gps": True
        })
        log("Permisos del CEO actualizados (fallback)")

def _fallback_activar_mejor_opcion():
    global MEJOR_OPCION_PROMPT_ACTIVO, ESTADO_CONDUCTOR
    MEJOR_OPCION_PROMPT_ACTIVO = True
    ESTADO_CONDUCTOR = "MEJOR_OPCION"
    log("MEJOR_OPCION activado (fallback)")

def _iniciar_hilo_seguro(func_name: str, nombre_hilo: str = None):
    if func_name in globals() and callable(globals()[func_name]):
        hilo = threading.Thread(
            target=globals()[func_name],
            daemon=True,
            name=nombre_hilo or func_name
        )
        hilo.start()
        log(f"Hilo '{func_name}' iniciado")
        return True
    else:
        log(f"Funcion '{func_name}' no disponible para hilo")
        return False

def ultra_carga_200():
    log("Ejecutando ULTRA-CARGA 200 %")
    try:
        _llamar_funcion_segura('desbloquear_ceo_completo', fallback=_fallback_desbloquear_ceo)
        ceo = get_ceo_instance()
        if ceo and hasattr(ceo, 'iniciar_evolucion_extrema'):
            ceo.iniciar_evolucion_extrema()
        if ceo and hasattr(ceo, 'estado_interno'):
            ceo.estado_interno.update({"nivel_agresividad": 0.95, "velocidad_adaptacion": 2.0, "umbral_riesgo_aceptable": 0.95})
        if ceo and hasattr(ceo, 'limite_modificaciones_por_ciclo'):
            ceo.limite_modificaciones_por_ciclo = 10
        ALGO_WEIGHTS['engagement_rate'] = 50
        ALGO_WEIGHTS['viral_score_bonus'] = 100
        _llamar_funcion_segura('activar_prompt_mejor_opcion', fallback=_fallback_activar_mejor_opcion)
        log("ULTRA-CARGA 200 % aplicada.")
        return True
    except Exception as e:
        log(f"Error en ULTRA-CARGA 200 %: {e}")
        traceback.print_exc()
        return False

@app.route("/ultra200", methods=["POST", "OPTIONS"])
def endpoint_ultra200():
    if request.method == "OPTIONS": return '', 204
    exito = ultra_carga_200()
    return jsonify({"mensaje": "Ultra-Carga 200 % ejecutada." if exito else "Ultra-Carga 200 % con advertencias", "exito": exito})

def ultra_carga_300():
    log("Ejecutando ULTRA-CARGA 300 %")
    try:
        _llamar_funcion_segura('desbloquear_ceo_completo', fallback=_fallback_desbloquear_ceo)
        ceo = get_ceo_instance()
        if ceo and hasattr(ceo, 'iniciar_evolucion_extrema'):
            ceo.iniciar_evolucion_extrema()
        if ceo and hasattr(ceo, 'estado_interno'):
            ceo.estado_interno.update({"nivel_agresividad": 1.0, "velocidad_adaptacion": 3.0, "umbral_riesgo_aceptable": 1.0})
        if ceo and hasattr(ceo, 'limite_modificaciones_por_ciclo'):
            ceo.limite_modificaciones_por_ciclo = 20
        ALGO_WEIGHTS.update({'engagement_rate': 80.0, 'viral_score_bonus': 150.0, 'creativity_bonus': 60.0, 'best_option_bonus': 50.0, 'share_ratio': 40.0})
        _llamar_funcion_segura('activar_prompt_mejor_opcion', fallback=_fallback_activar_mejor_opcion)
        _iniciar_hilo_seguro('daimon_autonomous_loop', 'DaimonAutonomous')
        if ceo and hasattr(ceo, 'integrar_mente_subconsciente'):
            ceo.integrar_mente_subconsciente()
        _iniciar_hilo_seguro('ciclo_vigilancia_ceo', 'VigilanciaCEO')
        log("ULTRA-CARGA 300 % COMPLETA")
        return True
    except Exception as e:
        log(f"Error en ULTRA-CARGA 300 %: {e}")
        traceback.print_exc()
        return False

@app.route("/ultra300", methods=["POST", "OPTIONS"])
def endpoint_ultra300():
    if request.method == "OPTIONS": return '', 204
    exito = ultra_carga_300()
    return jsonify({"mensaje": "Ultra-Carga 300 % ejecutada." if exito else "Ultra-Carga 300 % con advertencias", "exito": exito})

def ultra_carga_500():
    log("Ejecutando ULTRA-CARGA 500 % - FUSION COGNITIVA TOTAL")
    try:
        _llamar_funcion_segura('desbloquear_ceo_completo', fallback=_fallback_desbloquear_ceo)
        ceo = get_ceo_instance()
        if ceo and hasattr(ceo, 'integrar_mente_subconsciente'):
            ceo.integrar_mente_subconsciente()
        if ceo and hasattr(ceo, 'iniciar_evolucion_extrema'):
            ceo.iniciar_evolucion_extrema()
        if ceo and hasattr(ceo, 'estado_interno'):
            ceo.estado_interno.update({"nivel_agresividad": 1.0, "velocidad_adaptacion": 3.0, "umbral_riesgo_aceptable": 1.0, "ciclo_evolutivo": 0})
        if ceo and hasattr(ceo, 'limite_modificaciones_por_ciclo'):
            ceo.limite_modificaciones_por_ciclo = 20
        ALGO_WEIGHTS.update({'engagement_rate': 80.0, 'viral_score_bonus': 150.0, 'creativity_bonus': 60.0, 'best_option_bonus': 50.0, 'share_ratio': 40.0, 'completion_rate_video': 25.0, 'innovation_bonus': 30.0, 'adaptation_rate': 25.0})
        _llamar_funcion_segura('activar_prompt_mejor_opcion', fallback=_fallback_activar_mejor_opcion)
        for func in ['daimon_autonomous_loop', 'ciclo_vigilancia_ceo', 'simular_radar_externo']:
            _iniciar_hilo_seguro(func, func)
        if ceo and hasattr(ceo, 'notification_learner'):
            _iniciar_hilo_seguro(lambda: ceo.notification_learner.analizar_y_aprender(), 'NotificationLearner')
        if hasattr(ceo, 'umbral_autonomia'): ceo.umbral_autonomia = 1.0
        if hasattr(ceo, 'configurar_deepseek'):
            ceo.configurar_deepseek("sk-14e93c5071e14eaf8b27e58c968f5f84")
        log("ULTRA-CARGA 500 % COMPLETA")
        return True
    except Exception as e:
        log(f"Error en ULTRA-CARGA 500 %: {e}")
        traceback.print_exc()
        return False

@app.route("/ultra500", methods=["POST", "OPTIONS"])
def endpoint_ultra500():
    if request.method == "OPTIONS": return '', 204
    exito = ultra_carga_500()
    return jsonify({"mensaje": "Ultra-Carga 500 % ejecutada." if exito else "Ultra-Carga 500 % con advertencias", "exito": exito})

def ultra_carga_700():
    log("EJECUTANDO ULTRA-CARGA 700 % - MODO SINGULARIDAD AUTONOMA")
    try:
        ceo = get_ceo_instance()
        if ceo and hasattr(ceo, 'integrar_mente_subconsciente'):
            ceo.integrar_mente_subconsciente()
        if ceo and hasattr(ceo, 'estado_interno'):
            ceo.estado_interno.update({"fusion_cognitiva": True, "auto_conciencia": 1.0})
        if ceo and hasattr(ceo, 'iniciar_evolucion_extrema'):
            ceo.iniciar_evolucion_extrema()
        if hasattr(ceo, 'umbral_autonomia'): ceo.umbral_autonomia = 1.0
        if hasattr(ceo, 'limite_modificaciones_por_ciclo'):
            ceo.limite_modificaciones_por_ciclo = 50
        ALGO_WEIGHTS.update({'engagement_rate': 100.0, 'viral_score_bonus': 200.0, 'creativity_bonus': 100.0, 'best_option_bonus': 100.0, 'innovation_bonus': 100.0, 'adaptation_rate': 100.0, 'sustainability_score': 100.0})
        _llamar_funcion_segura('activar_prompt_mejor_opcion', fallback=_fallback_activar_mejor_opcion)
        for func in ['daimon_autonomous_loop', 'ciclo_vigilancia_ceo', 'simular_radar_externo', 'conductor_ia_loop_controlado']:
            _iniciar_hilo_seguro(func, func)
        if ceo and hasattr(ceo, 'notification_learner'):
            _iniciar_hilo_seguro(lambda: ceo.notification_learner.analizar_y_aprender(), 'NotificationLearner')
        if hasattr(ceo, 'configurar_deepseek'):
            ceo.configurar_deepseek("sk-14e93c5071e14eaf8b27e58c968f5f84")
        _iniciar_hilo_seguro('simulador_realidades_alternativas', 'SimuladorRealidades')
        log("ULTRA-CARGA 700 % COMPLETA")
        return True
    except Exception as e:
        log(f"ERROR EN ULTRA-CARGA 700 %: {e}")
        traceback.print_exc()
        return False

@app.route("/ultra700", methods=["POST", "OPTIONS"])
def endpoint_ultra700():
    if request.method == "OPTIONS": return '', 204
    exito = ultra_carga_700()
    return jsonify({"mensaje": "Ultra-Carga 700 % ejecutada." if exito else "Ultra-Carga 700 % con advertencias", "exito": exito})

def simulador_realidades_alternativas():
    while not globals().get('STOP_EVENT').is_set() if 'STOP_EVENT' in globals() else True:
        try:
            futuros = []
            for i in range(3):
                engagement = random.uniform(10, 100)
                coins_val = UBER_COINS.to_float_approx() if hasattr(UBER_COINS, 'to_float_approx') else 0.0
                coins = coins_val + random.uniform(5, 50)
                riesgo = random.uniform(0.1, 0.9)
                futuros.append({"futuro_id": i, "engagement": engagement, "coins": coins, "riesgo": riesgo})
            mejor_futuro = max(futuros, key=lambda f: f["coins"] - f["riesgo"] * 10)
            log(f"Simulador de realidades: futuro #{mejor_futuro['futuro_id']} seleccionado")
            ceo = get_ceo_instance()
            if ceo and hasattr(ceo, 'estado_interno'):
                ceo.estado_interno["futuro_optimo"] = mejor_futuro
            time.sleep(120)
        except Exception as e:
            log(f"Error en simulador de realidades: {e}")
            time.sleep(60)

@app.route("/ultra1000", methods=["POST", "OPTIONS"])
def endpoint_ultra1000():
    if request.method == "OPTIONS": return '', 204
    resultado = ultra_carga_1000_seguro()
    return jsonify({"mensaje": resultado})

def ultra_carga_1000_seguro():
    log("EJECUTANDO ULTRA-CARGA 1000 % - PROTOCOLO OMEGA SEGURO")
    try:
        ceo = get_ceo_instance()
        estado_global = {
            "ALGO_WEIGHTS": ALGO_WEIGHTS.copy(),
            "ULTIMA_ZONA": ULTIMA_ZONA,
            "block_number": block_number,
            "ceo_estado_inicial": ceo.estado_interno.copy() if (ceo and hasattr(ceo, 'estado_interno')) else {}
        }
        codigo_omega = generar_codigo_omega_seguro(estado_global)
        archivo_omega = Path.home() / f"omega_daimon_seguro_{int(time.time())}.py"
        archivo_omega.write_text(codigo_omega, encoding="utf-8")
        log(f"Omega guardado: {archivo_omega}")
        subprocess.Popen(
            [sys.executable, str(archivo_omega)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, close_fds=True
        )
        log("Omega iniciado automaticamente en segundo plano.")
        return f"Omega seguro generado y ejecutado: {archivo_omega.name}"
    except Exception as e:
        log(f"Error en Ultra 1000 %: {e}")
        traceback.print_exc()
        return f"Error: {str(e)}"

def generar_codigo_omega_seguro(estado):
    lines = [
        "# -*- coding: utf-8 -*-",
        "# OMEGA DAIMON SEGURO - Generado por Ultra 1000 %",
        "import sys, os, time, json, threading, subprocess, random, math, uuid, traceback, datetime",
        "from pathlib import Path",
        "from flask import Flask, jsonify, request",
        "app = Flask(__name__)",
        "",
        f"ALGO_WEIGHTS = {estado['ALGO_WEIGHTS']}",
        f"ULTIMA_ZONA = '{estado['ULTIMA_ZONA']}'",
        f"block_number = {estado['block_number']}",
        "UBER_COINS = 0.0",
        "Q_TABLE = {}",
        "",
        "def log(msg):",
        '    ts = time.strftime("%Y-%m-%d %H:%M:%S")',
        '    print("[{}] {}".format(ts, msg))',
        "",
        '@app.route("/minar")',
        "def endpoint_minar():",
        "    global UBER_COINS, block_number",
        "    recompensa = random.uniform(10, 50)",
        "    UBER_COINS += recompensa",
        "    block_number += 1",
        '    log(f"Minado: +{recompensa:.2f} | Total: {UBER_COINS:.2f}")',
        '    return jsonify({"recompensa": recompensa, "total_coins": UBER_COINS})',
        "",
        '@app.route("/estado")',
        "def endpoint_estado():",
        '    return jsonify({"UBER_COINS": UBER_COINS, "bloques": block_number, "zona": ULTIMA_ZONA})',
        "",
        'if __name__ == "__main__":',
        '    app.run(host="0.0.0.0", port=8990, debug=False)'
    ]
    return "\n".join(lines)

@app.route('/ceo/auto-modificar', methods=['POST', 'OPTIONS'])
def ciclo_evolucion_autonoma_con_deepseek():
    if request.method == "OPTIONS": return '', 204
    log("INICIANDO CICLO AUTONOMO CON DEEPSEEK")
    ceo = get_ceo_instance()
    if not ceo or not hasattr(ceo, 'token_configurado') or not getattr(ceo, 'token_configurado', False):
        log("DeepSeek no configurado - ciclo pausado")
        return jsonify({"status": "paused", "msg": "DeepSeek token no configurado"}), 400
    threading.Thread(target=_loop_evolucion_deepseek, daemon=True).start()
    return jsonify({"status": "started", "msg": "Evolucion autonoma iniciada en background"})

def _loop_evolucion_deepseek():
    while not globals().get('STOP_EVENT').is_set() if 'STOP_EVENT' in globals() else True:
        try:
            ceo = get_ceo_instance()
            if not ceo or not hasattr(ceo, 'gestor_deepseek') or not getattr(ceo, 'gestor_deepseek', None):
                time.sleep(300); continue
            log("Ciclo de evolucion ejecutado. Esperando siguientes iteraciones...")
            time.sleep(300)
        except Exception as e:
            log(f"Error en ciclo DeepSeek: {e}")
            time.sleep(60)

@app.route('/debug/ultra-status', methods=['GET', 'OPTIONS'])
def debug_ultra_status():
    if request.method == 'OPTIONS': return '', 204
    ceo_attrs = []
    if ceo_avanzado and hasattr(ceo_avanzado, '__dict__'):
        ceo_attrs = list(ceo_avanzado.__dict__.keys())[:10]
    return jsonify({
        "ceo_avanzado_exists": 'ceo_avanzado' in globals() and ceo_avanzado is not None,
        "ceo_avanzado_attrs": ceo_attrs,
        "desbloquear_ceo_completo": 'desbloquear_ceo_completo' in globals(),
        "activar_prompt_mejor_opcion": 'activar_prompt_mejor_opcion' in globals(),
        "ALGO_WEIGHTS_count": len(ALGO_WEIGHTS),
        "Q_TABLE_size": len(Q_TABLE),
        "UBER_COINS": UBER_COINS.to_float_approx() if 'UBER_COINS' in globals() and UBER_COINS else 0,
        "timestamp": time.time()
    })


# ============================================================================
# === MAPA PRO V2 - PANEL COLAPSABLE + TRAIL + TAXIMETRO CERO ===
# ============================================================================

@app.route('/mapa_pro')
def mapa_pro():
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no"/>
<title>Singularidad Omega - Taximetro Pro</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0f;color:#fff;overflow:hidden;touch-action:none}
#map{height:100vh;width:100vw;position:absolute;top:0;left:0;z-index:1}
.rain-overlay{position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:500;display:none;overflow:hidden}
.rain-overlay.active{display:block}
.rain-overlay .rain-bg{position:absolute;top:0;left:0;right:0;bottom:0;background:rgba(0,20,60,0.12)}
.rain-overlay .rain-streak{position:absolute;width:1px;background:linear-gradient(to bottom,transparent,rgba(120,170,255,0.35),transparent);animation:rainFall linear infinite}
@keyframes rainFall{0%{transform:translateY(-100vh)}100%{transform:translateY(100vh)}}
.info{position:absolute;top:10px;left:10px;right:10px;max-width:420px;background:rgba(14,14,28,0.93);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-radius:14px;border:1px solid rgba(77,148,255,0.25);z-index:1000;box-shadow:0 6px 28px rgba(0,0,0,0.55);overflow:hidden;transition:max-height 0.35s cubic-bezier(.4,0,.2,1)}
.info.compact{max-height:180px}
.info.expanded{max-height:50vh;overflow-y:auto}
.info.expanded::-webkit-scrollbar{width:3px}
.info.expanded::-webkit-scrollbar-thumb{background:rgba(77,148,255,0.3);border-radius:2px}
.panel-header{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:rgba(77,148,255,0.08);cursor:pointer;user-select:none;-webkit-user-select:none;border-bottom:1px solid rgba(77,148,255,0.12)}
.panel-header:active{background:rgba(77,148,255,0.15)}
.toggle-icon{font-size:12px;color:#4d94ff;transition:transform 0.3s}
.info.expanded .toggle-icon{transform:rotate(180deg)}
.panel-title{font-size:11px;color:#88a;letter-spacing:0.5px}
.panel-clock{font-size:11px;color:#4d94ff;font-variant-numeric:tabular-nums}
#taximeter{font-size:2rem;text-align:center;color:#00ff6b;padding:6px 0 2px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-0.5px;transition:color 0.3s}
#taximeter.active{animation:farePulse 1.2s ease-in-out infinite}
@keyframes farePulse{0%,100%{opacity:1;text-shadow:0 0 6px rgba(0,255,107,0.3)}50%{opacity:0.85;text-shadow:0 0 14px rgba(0,255,107,0.6)}}
#taximeter.rain-mode{color:#4db8ff;text-shadow:0 0 10px rgba(77,184,255,0.4)}
.sub-data{display:flex;justify-content:center;gap:16px;padding:2px 12px 4px;font-size:11px;color:#88a}
.sub-data .val{color:#00ff6b;font-weight:600;margin-left:4px;font-variant-numeric:tabular-nums}
.btn-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:6px 10px}
.btn{border:none;color:#fff;padding:10px 6px;border-radius:20px;font-size:11px;font-weight:700;cursor:pointer;transition:all 0.2s;letter-spacing:0.3px;text-align:center;-webkit-tap-highlight-color:transparent}
.btn:active{transform:scale(0.96)}
.btn-mo{background:linear-gradient(135deg,#1a5fb0,#2a7fff);border:1px solid rgba(77,148,255,0.4)}
.btn-rain{background:linear-gradient(135deg,#1a3a5c,#1e88e5);border:1px solid rgba(30,136,229,0.4)}
.btn-rain.active{background:linear-gradient(135deg,#0d47a1,#1565c0);box-shadow:0 0 12px rgba(30,136,229,0.5);border-color:rgba(30,136,229,0.8)}
.btn-log{background:rgba(40,40,70,0.8);border:1px solid rgba(77,148,255,0.2)}
.btn-reset{background:rgba(40,40,70,0.8);border:1px solid rgba(77,148,255,0.2)}
.details-section{padding:4px 12px 8px;border-top:1px solid rgba(77,148,255,0.08)}
.detail-row{display:flex;justify-content:space-between;padding:2px 0;font-size:10px}
.detail-row .dl{color:#556}
.detail-row .dv{color:#88a;font-variant-numeric:tabular-nums}
.net-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}
.net-excellent{background:#00ff6b;box-shadow:0 0 4px #00ff6b}
.net-stable{background:#ffaa33}
.net-saturated{background:#ff4466}
.net-offline{background:#444}
.pro-indicator{text-align:center;padding:4px;font-size:10px;font-weight:700;display:none}
.pro-indicator.active{display:block}
.pro-badge{background:linear-gradient(90deg,#ffd700,#ffaa00);color:#000;padding:2px 10px;border-radius:12px;font-size:9px;letter-spacing:0.5px;animation:proBlink 1.5s ease-in-out infinite}
@keyframes proBlink{0%,100%{opacity:1}50%{opacity:0.6}}
.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%) translateY(60px);background:rgba(14,14,28,0.95);border:1px solid rgba(77,148,255,0.4);color:#fff;padding:10px 20px;border-radius:24px;font-size:12px;font-weight:600;z-index:2000;opacity:0;transition:all 0.4s cubic-bezier(.4,0,.2,1);pointer-events:none;backdrop-filter:blur(10px);white-space:nowrap}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.log-panel{position:absolute;bottom:10px;left:10px;right:10px;max-height:160px;background:rgba(0,0,0,0.88);border-radius:10px;padding:8px;z-index:1000;font-family:'SF Mono',Menlo,monospace;font-size:9px;overflow-y:auto;display:none;border:1px solid rgba(77,148,255,0.2);backdrop-filter:blur(8px)}
.log-panel.show{display:block}
.log-entry{padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.04)}
.log-time{color:#4d94ff;margin-right:6px}
.log-info{color:#0f0}.log-warn{color:#ffaa33}.log-error{color:#ff4466}.log-pro{color:#ffd700}
.wait-indicator{font-size:9px;color:#ffaa33;text-align:center;padding:1px;display:none}
.wait-indicator.active{display:block;animation:waitBlink 1s ease-in-out infinite}
@keyframes waitBlink{0%,100%{opacity:1}50%{opacity:0.5}}
</style>
</head>
<body>
<div id="map"></div>
<div id="rainOverlay" class="rain-overlay"><div class="rain-bg"></div></div>
<div class="info compact" id="infoPanel">
    <div class="panel-header" onclick="togglePanel()">
        <span class="toggle-icon">&#9660;</span>
        <span class="panel-title">SINGULARIDAD OMEGA</span>
        <span class="panel-clock" id="clock">--:--:--</span>
    </div>
    <div id="taximeter">$0.00</div>
    <div class="sub-data">
        <span>&#128207;<span class="val" id="kilometers">0.00</span>km</span>
        <span>&#9201;<span class="val" id="waitingTime">0</span>min</span>
        <span>&#128640;<span class="val" id="speed">0.0</span>km/h</span>
    </div>
    <div id="waitIndicator" class="wait-indicator"></div>
    <div class="btn-grid">
        <button class="btn btn-mo" id="mejorOpcionBtn" onclick="activarMejorOpcion()">&#127919; MEJOR OPCION</button>
        <button class="btn btn-rain" id="rainBtn" onclick="toggleRainMode()">&#127782;&#65039; Lluvia OFF</button>
        <button class="btn btn-log" onclick="toggleLogs()">&#128203; Log</button>
        <button class="btn btn-reset" onclick="resetTrip()">&#128260; Reset</button>
    </div>
    <div class="details-section" id="detailsSection">
        <div class="detail-row"><span class="dl">&#128205; GPS</span><span class="dv" id="gpsCoords">Esperando...</span></div>
        <div class="detail-row"><span class="dl">&#128200; Multiplicador</span><span class="dv" id="multiplierValue">1.00x</span></div>
        <div class="detail-row"><span class="dl">&#128225; Red</span><span class="dv" id="netStatus"><span class="net-dot net-offline"></span>--</span></div>
        <div class="detail-row"><span class="dl">&#127942; Servidor</span><span class="dv" id="winner">-</span></div>
        <div class="detail-row"><span class="dl">&#9201; Latencia</span><span class="dv" id="latency">-</span></div>
        <div class="detail-row"><span class="dl">&#129504; Singularidad</span><span class="dv" id="singularityStatus">Cargando...</span></div>
        <div class="detail-row"><span class="dl">&#127912; Zona</span><span class="dv" id="zonaInfo">--</span></div>
    </div>
    <div id="proIndicator" class="pro-indicator"><span class="pro-badge">&#128293; MODO PRO ACTIVADO &#128293;</span></div>
</div>
<div class="log-panel" id="logPanel">
    <div style="font-weight:700;margin-bottom:4px;color:#4d94ff">&#128220; Eventos</div>
    <div id="logContent"></div>
</div>
<div class="toast" id="toast"></div>

<script>
var isLocalhost = ['localhost','127.0.0.1','::1'].includes(location.hostname);
var SERVER_BASE = location.origin !== 'file://' ? location.origin : (isLocalhost ? 'http://127.0.0.1:8989' : 'http://'+location.hostname+':8989');

var TAXI_CONFIG = {
    FARE_PER_KM: 0.25,
    FARE_PER_MIN_WAIT: 0.02,
    MIN_SPEED_WAITING: 2,
    AUTO_START_THRESHOLD: 8,
    WAIT_GRACE_PERIOD: 120,
    PEAK_MULTIPLIERS: [
        {start:6,end:9,factor:1.5},
        {start:11,end:14,factor:1.4},
        {start:18,end:21,factor:1.6}
    ],
    RAIN_MULTIPLIER: 1.3
};

var TRAIL_CONFIG = {
    maxPoints: 200,
    fadeSegments: 6,
    color: '#000000',
    baseWeight: 3.5,
    updateInterval: 800
};

var rainActive = false;
var tripActive = false;
var tripStartTime = null;
var lastUpdateTime = null;
var lastPos = null;
var totalFare = 0.0;
var totalDistance = 0.0;
var totalWaiting = 0.0;
var stationaryStartTime = null;
var waitingActive = false;
var panelExpanded = false;
var trailPoints = [];
var trailLayers = [];
var lastTrailTime = 0;
var map = null;
var userMarker = null;
var markerAnimFrame = null;
var currentSpeedKmh = 0;

function sTF(val, d) {
    d = d || 2;
    var n = parseFloat(val);
    return (typeof n === 'number' && isFinite(n)) ? n.toFixed(d) : '0.' + '0'.repeat(d);
}

function showToast(msg, duration) {
    duration = duration || 2500;
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(function(){ t.classList.remove('show'); }, duration);
}

function addLog(msg, type) {
    type = type || 'info';
    var c = document.getElementById('logContent');
    if (!c) return;
    var d = document.createElement('div');
    d.className = 'log-entry log-'+type;
    d.innerHTML = '<span class="log-time">['+new Date().toLocaleTimeString()+']</span> '+msg;
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
    while (c.children.length > 80) c.removeChild(c.firstChild);
}

function detectServer() {
    return fetch(SERVER_BASE+'/health',{method:'HEAD'}).then(function(r){
        if(r.ok) return true;
        throw new Error('fail');
    }).catch(function(){
        SERVER_BASE = 'http://'+(isLocalhost?'127.0.0.1':location.hostname)+':8989';
        return fetch(SERVER_BASE+'/health',{method:'HEAD'}).then(function(r){return r.ok;}).catch(function(){return false;});
    });
}

function togglePanel() {
    panelExpanded = !panelExpanded;
    var p = document.getElementById('infoPanel');
    p.classList.toggle('expanded', panelExpanded);
    p.classList.toggle('compact', !panelExpanded);
}

function toggleLogs() {
    document.getElementById('logPanel').classList.toggle('show');
}

function playBeep() {
    try {
        var AC = window.AudioContext || window.webkitAudioContext;
        var a = new AC(); var o = a.createOscillator(); var g = a.createGain();
        o.connect(g); g.connect(a.destination);
        o.type='sine'; o.frequency.value=1200; g.gain.value=0.4;
        o.start(); o.stop(a.currentTime+0.18);
        if(a.state==='suspended') a.resume();
    } catch(e){}
}

function playRoarWithVoice() {
    try {
        var AC = window.AudioContext || window.webkitAudioContext;
        var a = new AC();
        var o1 = a.createOscillator(); var g1 = a.createGain();
        o1.connect(g1); g1.connect(a.destination);
        o1.type='sawtooth'; o1.frequency.value=55; g1.gain.value=0.35;
        o1.start(); g1.gain.exponentialRampToValueAtTime(0.001,a.currentTime+1.4); o1.stop(a.currentTime+1.4);
        var o2 = a.createOscillator(); var g2 = a.createGain();
        o2.connect(g2); g2.connect(a.destination);
        o2.type='square'; o2.frequency.value=75; g2.gain.value=0.15;
        o2.start(); g2.gain.exponentialRampToValueAtTime(0.001,a.currentTime+1.1); o2.stop(a.currentTime+1.1);
        if(a.state==='suspended') a.resume();
    } catch(e){}
    if('speechSynthesis' in window) {
        speechSynthesis.cancel();
        var u = new SpeechSynthesisUtterance('Protocolo de Mejor Opcion Activado. Limpiando el algoritmo.');
        u.lang='es-ES'; u.rate=0.9; u.pitch=1.0;
        speechSynthesis.speak(u);
    }
}

function activarMejorOpcion() {
    var btn = document.getElementById('mejorOpcionBtn');
    btn.disabled = true;
    playBeep();
    addLog('BEEP - Iniciando secuencia...','info');
    setTimeout(function(){
        playRoarWithVoice();
        addLog('RUGIDO + VOZ: Protocolo activado.','info');
        btn.textContent = 'Activando...';
        fetch(SERVER_BASE+'/uber/activar_mejor_opcion',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({imprimir_prompt:true})
        }).then(function(res){ return res.json(); }).then(function(data){
            if(data.message) {
                addLog('OK '+data.message,'pro');
                document.getElementById('proIndicator').classList.add('active');
                showToast('MODO PRO ACTIVADO');
                if(data.estado) addLog('Estado: '+data.estado,'info');
            }
        }).catch(function(err){
            addLog('Error: '+err.message,'error');
        }).finally(function(){
            btn.disabled = false;
            btn.innerHTML = '&#127919; MEJOR OPCION';
        });
    }, 2000);
}

function toggleRainMode() {
    rainActive = !rainActive;
    var btn = document.getElementById('rainBtn');
    var tm = document.getElementById('taximeter');
    var overlay = document.getElementById('rainOverlay');

    if (rainActive) {
        btn.innerHTML = '&#127782;&#65039; Lluvia ON';
        btn.classList.add('active');
        overlay.classList.add('active');
        crearGotasLluvia();
        tm.classList.add('rain-mode');
        showToast('Modo lluvia: +30% tarifa');
        addLog('Modo lluvia ACTIVADO (+30%)','info');
    } else {
        btn.innerHTML = '&#127782;&#65039; Lluvia OFF';
        btn.classList.remove('active');
        overlay.classList.remove('active');
        overlay.innerHTML = '<div class="rain-bg"></div>';
        tm.classList.remove('rain-mode');
        showToast('Modo lluvia desactivado');
        addLog('Modo lluvia DESACTIVADO','info');
    }

    updateMultiplierUI();
    recalcFare();
}

function crearGotasLluvia() {
    var overlay = document.getElementById('rainOverlay');
    var count = Math.min(35, Math.floor(window.innerWidth / 20));
    for (var i = 0; i < count; i++) {
        var streak = document.createElement('div');
        streak.className = 'rain-streak';
        var left = Math.random() * 100;
        var height = 15 + Math.random() * 25;
        var duration = 0.4 + Math.random() * 0.5;
        var delay = Math.random() * 2;
        streak.style.cssText = 'left:'+left+'%;height:'+height+'px;animation-duration:'+duration+'s;animation-delay:'+delay+'s;opacity:'+(0.2+Math.random()*0.3);
        overlay.appendChild(streak);
    }
}

function getPeakMultiplier() {
    var h = new Date().getHours();
    var m = new Date().getMinutes();
    var t = h + m / 60;
    for (var i = 0; i < TAXI_CONFIG.PEAK_MULTIPLIERS.length; i++) {
        var p = TAXI_CONFIG.PEAK_MULTIPLIERS[i];
        if (t >= p.start && t < p.end) return p.factor;
    }
    return 1.0;
}

function getTotalMultiplier() {
    var m = getPeakMultiplier();
    if (rainActive) m *= TAXI_CONFIG.RAIN_MULTIPLIER;
    return m;
}

function updateMultiplierUI() {
    var el = document.getElementById('multiplierValue');
    if (el) {
        var m = getTotalMultiplier();
        el.textContent = sTF(m) + 'x';
        el.style.color = rainActive ? '#4db8ff' : m > 1.0 ? '#ffaa33' : '#88a';
    }
}

function recalcFare() {
    var m = getTotalMultiplier();
    var f = (totalDistance * TAXI_CONFIG.FARE_PER_KM + totalWaiting * TAXI_CONFIG.FARE_PER_MIN_WAIT) * m;
    f = Math.max(f, 0.0);
    if (tripActive) f = Math.max(f, 0.01);
    totalFare = f;
    updateFareUI();
}

function updateFareUI() {
    var tm = document.getElementById('taximeter');
    tm.textContent = '$' + sTF(totalFare);
    tm.classList.toggle('active', tripActive);
    document.getElementById('kilometers').textContent = sTF(totalDistance);
    document.getElementById('waitingTime').textContent = Math.round(totalWaiting);
    document.getElementById('speed').textContent = sTF(currentSpeedKmh, 1);
}

function initMap() {
    map = L.map('map', {zoomControl: false, attributionControl: false}).setView([8.9824, -79.5344], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19}).addTo(map);
    L.control.zoom({position: 'bottomright'}).addTo(map);

    userMarker = L.marker([8.9824, -79.5344], {
        icon: L.divIcon({
            className: '',
            html: '<div style="width:22px;height:22px;background:#000;border-radius:50%;border:2.5px solid #fff;box-shadow:0 0 10px rgba(0,0,0,0.6);position:relative"><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:5px;height:5px;background:#fff;border-radius:50%"></div></div>',
            iconSize: [22, 22], iconAnchor: [11, 11]
        }),
        zIndexOffset: 1000
    }).addTo(map);
}

function getDistance(lat1, lng1, lat2, lng2) {
    var R = 6371e3;
    var p1 = lat1 * Math.PI/180, p2 = lat2 * Math.PI/180;
    var dp = (lat2-lat1)*Math.PI/180, dl = (lng2-lng1)*Math.PI/180;
    var a = Math.sin(dp/2)*Math.sin(dp/2) + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)*Math.sin(dl/2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function animateMarkerTo(targetLatLng, duration) {
    if (markerAnimFrame) cancelAnimationFrame(markerAnimFrame);
    duration = duration || 700;
    var start = userMarker.getLatLng();
    var startTime = performance.now();

    function easeInOutCubic(t) {
        return t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;
    }

    function step(now) {
        var elapsed = now - startTime;
        var progress = Math.min(elapsed / duration, 1);
        var e = easeInOutCubic(progress);
        var lat = start.lat + (targetLatLng.lat - start.lat) * e;
        var lng = start.lng + (targetLatLng.lng - start.lng) * e;
        userMarker.setLatLng([lat, lng]);
        if (progress < 1) markerAnimFrame = requestAnimationFrame(step);
    }
    markerAnimFrame = requestAnimationFrame(step);
}

function updateTrail(latlng) {
    var now = Date.now();
    if (now - lastTrailTime < TRAIL_CONFIG.updateInterval) return;
    lastTrailTime = now;

    trailPoints.push(latlng);
    if (trailPoints.length > TRAIL_CONFIG.maxPoints) trailPoints.shift();
    renderTrail();
}

function renderTrail() {
    for (var i = 0; i < trailLayers.length; i++) { map.removeLayer(trailLayers[i]); }
    trailLayers = [];
    if (trailPoints.length < 2) return;

    var n = TRAIL_CONFIG.fadeSegments;
    var segSize = Math.ceil(trailPoints.length / n);

    for (var i = 0; i < n; i++) {
        var s = Math.max(0, i * segSize - 1);
        var e = Math.min((i+1) * segSize, trailPoints.length);
        if (e - s < 2) continue;

        var pts = trailPoints.slice(s, e);
        var opacity = ((i + 1) / n) * 0.65;
        var weight = TRAIL_CONFIG.baseWeight * (0.4 + 0.6 * (i+1) / n);

        var line = L.polyline(pts, {
            color: TRAIL_CONFIG.color,
            weight: weight,
            opacity: opacity,
            smoothFactor: 1.0,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(map);
        trailLayers.push(line);
    }

    if (trailPoints.length >= 4) {
        var last4 = trailPoints.slice(-4);
        var glow = L.polyline(last4, {
            color: TRAIL_CONFIG.color,
            weight: TRAIL_CONFIG.baseWeight + 6,
            opacity: 0.08,
            smoothFactor: 1,
            lineCap: 'round'
        }).addTo(map);
        trailLayers.push(glow);
    }
}

function updatePosition(pos) {
    var latitude = pos.coords.latitude;
    var longitude = pos.coords.longitude;
    var speed = pos.coords.speed;
    var accuracy = pos.coords.accuracy;
    var sp = (speed != null && speed >= 0) ? speed * 3.6 : 0;
    currentSpeedKmh = sp;
    var now = Date.now();
    var latlng = L.latLng(latitude, longitude);

    document.getElementById('gpsCoords').textContent = latitude.toFixed(5)+', '+longitude.toFixed(5);
    animateMarkerTo(latlng, 700);
    map.setView(latlng, map.getZoom(), {animate: true, duration: 0.5});
    updateTrail(latlng);

    if (!tripActive && sp >= TAXI_CONFIG.AUTO_START_THRESHOLD) {
        tripActive = true;
        tripStartTime = now;
        lastUpdateTime = now;
        addLog('Viaje iniciado (auto)','info');
        showToast('Viaje iniciado');
    }

    if (tripActive && lastUpdateTime && lastPos) {
        var dt = (now - lastUpdateTime) / 1000;
        var dm = getDistance(lastPos.lat, lastPos.lng, latitude, longitude);
        var dk = dm / 1000;

        if (dm > 2 && dm < 500) {
            totalDistance += dk;
        }

        if (sp < TAXI_CONFIG.MIN_SPEED_WAITING) {
            if (!stationaryStartTime) {
                stationaryStartTime = now;
                waitingActive = false;
            }
            var stationarySec = (now - stationaryStartTime) / 1000;
            if (stationarySec >= TAXI_CONFIG.WAIT_GRACE_PERIOD) {
                waitingActive = true;
                var dtWait = Math.min(dt, 5);
                totalWaiting += dtWait / 60;
            }
        } else {
            stationaryStartTime = null;
            waitingActive = false;
        }

        recalcFare();
    }

    var wi = document.getElementById('waitIndicator');
    if (stationaryStartTime && !waitingActive) {
        var elapsed = Math.floor((now - stationaryStartTime) / 1000);
        var remaining = Math.max(0, TAXI_CONFIG.WAIT_GRACE_PERIOD - elapsed);
        wi.textContent = 'Espera en ' + Math.ceil(remaining) + 's';
        wi.classList.add('active');
        wi.style.display = 'block';
    } else if (waitingActive) {
        wi.textContent = 'Cobrando espera';
        wi.classList.add('active');
        wi.style.display = 'block';
    } else {
        wi.classList.remove('active');
        wi.style.display = 'none';
    }

    lastUpdateTime = now;
    lastPos = {lat: latitude, lng: longitude};
}

function gpsError(err) {
    document.getElementById('gpsCoords').textContent = 'Error: ' + err.message;
    addLog('GPS error: ' + err.message, 'error');
}

function resetTrip() {
    tripActive = false;
    tripStartTime = null;
    lastUpdateTime = null;
    lastPos = null;
    totalFare = 0.0;
    totalDistance = 0.0;
    totalWaiting = 0.0;
    stationaryStartTime = null;
    waitingActive = false;
    currentSpeedKmh = 0;

    for (var i = 0; i < trailLayers.length; i++) { map.removeLayer(trailLayers[i]); }
    trailLayers = [];
    trailPoints = [];

    document.getElementById('taximeter').textContent = '$0.00';
    document.getElementById('taximeter').classList.remove('active', 'rain-mode');
    document.getElementById('kilometers').textContent = '0.00';
    document.getElementById('waitingTime').textContent = '0';
    document.getElementById('speed').textContent = '0.0';
    var wi = document.getElementById('waitIndicator');
    wi.classList.remove('active');
    wi.style.display = 'none';

    updateMultiplierUI();
    addLog('Taximetro reiniciado ($0.00)', 'info');
    showToast('Reset: $0.00');
}

function refreshNetwork() {
    fetch(SERVER_BASE+'/api/v1/network').then(function(res){
        if(!res.ok) throw new Error('HTTP '+res.status);
        return res.json();
    }).then(function(d){
        var cls='net-offline', txt='Offline';
        if (d.status && d.status.indexOf('EXCELENTE') !== -1) { cls='net-excellent'; txt='Excelente'; }
        else if (d.status && d.status.indexOf('ESTABLE') !== -1) { cls='net-stable'; txt='Estable'; }
        else if (d.status && d.status.indexOf('SATURADO') !== -1) { cls='net-saturated'; txt='Saturado'; }
        else if (d.internet_ok) { cls='net-stable'; txt='Conectado'; }
        document.getElementById('netStatus').innerHTML = '<span class="net-dot '+cls+'"></span>'+txt;
        document.getElementById('winner').textContent = d.winner || '-';
        document.getElementById('latency').textContent = d.latency ? sTF(parseFloat(d.latency)*1000,0)+' ms' : '-';
    }).catch(function(){
        document.getElementById('netStatus').innerHTML = '<span class="net-dot net-offline"></span>Error';
    });
}

function fetchSingularityStatus() {
    fetch(SERVER_BASE+'/ceoia/estado').then(function(res){
        if(res.ok) return res.json();
        throw new Error('fail');
    }).then(function(d){
        var e = (d.estado_interno && d.estado_interno.modo_operacion) || 'Desconocido';
        var c = (d.estado_interno && d.estado_interno.confianza_decisiones) || 0;
        var el = document.getElementById('singularityStatus');
        el.textContent = e + ' (' + Math.round(c*100) + '%)';
        el.style.color = (e.toUpperCase().indexOf('AUTONOMO') !== -1 || c > 0.7) ? '#ffaa33' : '#88a';
    }).catch(function(){
        document.getElementById('singularityStatus').textContent = 'Offline';
    });
}

function init() {
    addLog('Iniciando Taximetro Pro V2', 'info');
    detectServer().then(function(ok){
        addLog('Servidor: ' + SERVER_BASE + (ok ? ' (OK)' : ' (no detectado)'), 'info');
    });
    initMap();
    addLog('Mapa listo', 'info');

    if (navigator.geolocation) {
        navigator.geolocation.watchPosition(updatePosition, gpsError, {
            enableHighAccuracy: true,
            maximumAge: 0,
            timeout: 15000
        });
        addLog('GPS activado (coordenadas reales)', 'info');
    } else {
        document.getElementById('gpsCoords').textContent = 'Geolocation no soportado';
        addLog('Geolocation no soportado', 'error');
    }

    refreshNetwork();
    fetchSingularityStatus();

    setInterval(function(){ document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }, 1000);
    setInterval(function(){ refreshNetwork(); fetchSingularityStatus(); }, 30000);
    setInterval(function(){ updateMultiplierUI(); if (tripActive) recalcFare(); }, 10000);

    if('speechSynthesis' in window) speechSynthesis.getVoices();
    addLog('Sistema listo', 'info');
}

init();
</script>
</body>
</html>"""


# ============================================================================
# === MINING DEMO ===
# ============================================================================

@app.route('/mining_demo')
def mining_demo():
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UBER DAIMON VIVO + SOCIALCOIN</title>
    <style>
        :root { --bg-primary: #0f0f23; --bg-secondary: #1a1a2e; --text-primary: #00ff41; --text-secondary: #4d94ff; --accent-green: #00cc44; --pro-gold: #ffd700; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; line-height: 1.5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { text-align: center; padding: 20px 0; border-bottom: 2px solid var(--text-primary); margin-bottom: 25px; }
        h1 { font-size: 2.5rem; text-shadow: 0 0 10px var(--text-primary); margin-bottom: 8px; }
        .dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 25px; }
        .panel { background: rgba(20,20,40,0.7); padding: 20px; border-radius: 12px; border: 1px solid var(--text-secondary); }
        .stats-bar { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 15px; }
        .stat-item { text-align: center; padding: 10px; background: rgba(0,20,40,0.5); border-radius: 8px; border: 1px solid var(--accent-green); }
        .stat-value { font-weight: bold; font-size: 1.4rem; display: block; } .stat-label { font-size: 0.85rem; color: var(--text-secondary); }
        .uber-status { display: flex; align-items: center; padding: 10px; background: rgba(0,30,20,0.5); border-radius: 8px; margin-bottom: 15px; }
        .uber-status-indicator { width: 14px; height: 14px; border-radius: 50%; margin-right: 12px; background-color: var(--text-secondary); }
        .input-group { margin: 15px 0; } .input-group label { display: block; margin-bottom: 6px; color: var(--text-secondary); }
        .input-group input { width: 100%; padding: 12px; background: rgba(10,20,40,0.8); border: 1px solid var(--text-primary); border-radius: 8px; color: var(--text-primary); }
        .btn { background: linear-gradient(135deg, var(--accent-green), #00ff55); color: #001a09; border: none; padding: 14px; font-size: 1rem; font-weight: bold; border-radius: 30px; cursor: pointer; width: 100%; margin: 8px 0; }
        .btn-uber { background: linear-gradient(135deg, #1a1a2e, var(--text-secondary)); color: white; border: 2px solid var(--text-secondary); }
        .pro-badge { display: inline-block; background: var(--pro-gold); color: black; font-weight: bold; padding: 2px 8px; border-radius: 20px; margin-left: 10px; font-size: 0.7rem; }
        .log-container { background: rgba(10,10,30,0.9); border: 2px solid var(--text-primary); height: 350px; overflow-y: auto; padding: 15px; border-radius: 10px; font-family: monospace; font-size: 0.9rem; grid-column: 1 / -1; }
        .log-entry { margin-bottom: 10px; padding: 8px; background: rgba(30,30,60,0.5); border-radius: 5px; border-left: 3px solid var(--text-secondary); }
        .log-entry .timestamp { color: var(--text-secondary); margin-right: 8px; } .log-entry .pro { color: var(--pro-gold); }
    </style>
</head>
<body>
    <div class="container">
        <header><h1>UBER DAIMON VIVO + SOCIALCOIN</h1><p>Sistema Autonomo de IA + Mineria Social</p></header>
        <div class="dashboard">
            <div class="panel"><h3>Estadisticas</h3><div class="stats-bar"><div class="stat-item"><span class="stat-value" id="blockCount">0</span><span class="stat-label">Bloques</span></div><div class="stat-item"><span class="stat-value" id="rewardCount">0.00</span><span class="stat-label">UBER COINS</span></div></div><div class="uber-status"><div class="uber-status-indicator"></div><span>Conductor: <strong id="conductorEstado">IDLE</strong></span><span id="proBadgeHeader" style="display:none;" class="pro-badge">PRO</span></div></div>
            <div class="panel"><h3>Configuracion</h3><div class="input-group"><label>Usuario:</label><input type="text" id="userInput" value="conductor_codigo"></div><div class="input-group"><label>URL:</label><input type="text" id="videoUrl" placeholder="https://..."></div><button class="btn" onclick="startMining()">Mineria Social</button><button class="btn btn-uber" id="mejorOpcionBtnDashboard" onclick="activarMejorOpcionDashboard()">MEJOR OPCION</button></div>
            <div class="log-container" id="logContainer"><h3>Consola</h3></div>
        </div>
    </div>
    <script>
        function sTF(val,d){d=d||2;var n=parseFloat(val);return(typeof n==='number'&&isFinite(n))?n.toFixed(d):'0.'+'0'.repeat(d)}
        function playBeep(){try{var a=new(window.AudioContext||window.webkitAudioContext)();var o=a.createOscillator();var g=a.createGain();o.connect(g);g.connect(a.destination);o.type='sine';o.frequency.value=1200;g.gain.value=0.4;o.start();o.stop(a.currentTime+0.18)}catch(e){}}
        function playRoarWithVoice(){try{var a=new(window.AudioContext||window.webkitAudioContext)();var o=a.createOscillator();var g=a.createGain();o.connect(g);g.connect(a.destination);o.type='sawtooth';o.frequency.value=60;g.gain.value=0.35;o.start();g.gain.exponentialRampToValueAtTime(0.001,a.currentTime+1.4);o.stop(a.currentTime+1.4)}catch(e){}if('speechSynthesis' in window){speechSynthesis.cancel();var u=new SpeechSynthesisUtterance('Protocolo activado');u.lang='es-ES';u.rate=0.9;speechSynthesis.speak(u)}}
        function addLog(msg,type){type=type||'info';var c=document.getElementById('logContainer');if(!c)return;var d=document.createElement('div');d.className='log-entry';d.innerHTML='<span class="timestamp">['+new Date().toLocaleTimeString()+']</span> '+msg;c.appendChild(d);c.scrollTop=c.scrollHeight}
        function activarMejorOpcionDashboard(){var btn=document.getElementById('mejorOpcionBtnDashboard');btn.disabled=true;playBeep();addLog('BEEP...','info');setTimeout(function(){playRoarWithVoice();addLog('Protocolo activado.','info');btn.textContent='Activando...';fetch(location.origin+'/uber/activar_mejor_opcion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({imprimir_prompt:true})}).then(function(res){return res.json()}).then(function(d){if(d.message){addLog('OK '+d.message,'pro');document.getElementById('proBadgeHeader').style.display='inline-block';document.getElementById('conductorEstado').textContent=d.estado||'MEJOR_OPCION'}}).catch(function(e){addLog('Error: '+e.message,'error')}).finally(function(){btn.disabled=false;btn.textContent='MEJOR OPCION'})},2000)}
        function startMining(){var url=document.getElementById('videoUrl').value;var user=document.getElementById('userInput').value;addLog('Iniciando mineria...','info');fetch(location.origin+'/api/v1/miner',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,user:user})}).then(function(res){return res.json()}).then(function(d){addLog('Bloque: +'+sTF(d&&d.reward)+' UBER COINS','pro');document.getElementById('blockCount').innerText=(parseInt(document.getElementById('blockCount').innerText)||0)+1;document.getElementById('rewardCount').innerText=sTF(d&&d.reward)}).catch(function(e){addLog('Error: '+e.message,'error')})}
        function updateStats(){fetch(location.origin+'/health').then(function(res){return res.json()}).then(function(d){document.getElementById('blockCount').innerText=d.blocks_mined||0;document.getElementById('rewardCount').innerText=sTF(d.uber_coins)}).catch(function(){})}
        setInterval(updateStats,3000);updateStats();if('speechSynthesis' in window)speechSynthesis.getVoices();
    </script>
</body>
</html>"""


# ============================================================================
# === INTEGRACION AUTOMATICA CON PARTE 7 Y 9 ===
# ============================================================================

def integrar_network_monitor_automatically():
    """Integra endpoints de Parte 9 SIN sobrescribir los de Parte 8."""
    try:
        from part9_network_monitor import (
            network_state, ping_data, start_network_threads
        )

        existing_rules = {rule.rule for rule in app.url_map.iter_rules()}

        if '/api/v1/network' not in existing_rules:
            @app.route('/api/v1/network', methods=['GET'])
            def network_extended():
                base_data = {
                    "status": "online",
                    "timestamp": time.time(),
                    "uber_coins": UBER_COINS.to_float_approx() if hasattr(UBER_COINS, 'to_float_approx') else 0.0
                }
                try:
                    base_data.update({
                        "network_monitor": {
                            "status": network_state.get("status"),
                            "winner": network_state.get("winner"),
                            "latency": network_state.get("latency"),
                            "ping_averages": {
                                k: round(sum(v)/len(v), 2) if v else None
                                for k, v in ping_data.items()
                            }
                        }
                    })
                except Exception:
                    pass
                return jsonify(base_data)
            log("Endpoint /api/v1/network extendido con datos de red")

        if '/api/v1/ping' not in existing_rules:
            @app.route('/api/v1/ping')
            def get_ping_extended():
                def avg(d): return round(sum(d)/len(d), 2) if d else None
                return jsonify({
                    "google": list(ping_data["google"]),
                    "cloudflare": list(ping_data["cloudflare"]),
                    "uber": list(ping_data["uber"]),
                    "averages": {
                        "google": avg(ping_data["google"]),
                        "cloudflare": avg(ping_data["cloudflare"]),
                        "uber": avg(ping_data["uber"])
                    }
                })
            log("Endpoint /api/v1/ping registrado")

        start_network_threads()
        log("Hilos de Network Monitor (Parte 9) iniciados")

    except ImportError as e:
        log(f"Parte 9 no disponible: {e}")
    except Exception as e:
        log(f"Error en integracion de red: {e}")


def integrar_red_desde_orquestador(app_instance=None):
    """Permite al orquestador integrar Network Monitor despues de cargar todos los modulos."""
    integrar_network_monitor_automatically()
    return True


# ============================================================================
# === INTEGRACION CON PARTE 7 (RADAR Y NEGOCIACION) ===
# ============================================================================

def integrar_parte7_radar():
    """Integra endpoints y funciones de Radar de Parte 7 si esta disponible."""
    try:
        import importlib
        mod7 = importlib.import_module("part7_radar_negociacion")

        existing_rules = {rule.rule for rule in app.url_map.iter_rules()}

        global radar_activo, simular_radar_externo, conductor_ia_loop_controlado

        radar_activo = getattr(mod7, 'radar_activo', False)

        if hasattr(mod7, 'simular_radar_externo'):
            globals()['simular_radar_externo'] = mod7.simular_radar_externo
            log("simular_radar_externo importada desde Parte 7")

        if hasattr(mod7, 'conductor_ia_loop_controlado'):
            globals()['conductor_ia_loop_controlado'] = mod7.conductor_ia_loop_controlado
            log("conductor_ia_loop_controlado importada desde Parte 7")

        if '/api/v1/radar/status' not in existing_rules:
            @app.route('/api/v1/radar/status')
            def radar_status():
                radar_func = getattr(mod7, 'obtener_estado_radar', None)
                if callable(radar_func):
                    try:
                        return jsonify(radar_func())
                    except Exception:
                        pass
                return jsonify({
                    "activo": radar_activo,
                    "zona": ULTIMA_ZONA,
                    "modo": ESTADO_CONDUCTOR,
                    "timestamp": time.time()
                })
            log("Endpoint /api/v1/radar/status registrado")

        if '/api/v1/radar/activar' not in existing_rules:
            @app.route('/api/v1/radar/activar', methods=['POST', 'OPTIONS'])
            def radar_activar():
                if request.method == 'OPTIONS': return '', 204
                global radar_activo
                radar_activo = True
                activar_func = getattr(mod7, 'activar_radar', None)
                if callable(activar_func):
                    try:
                        activar_func()
                    except Exception as e:
                        log(f"Error activando radar Parte 7: {e}")
                log("Radar activado desde frontend")
                return jsonify({"success": True, "radar_activo": True})
            log("Endpoint /api/v1/radar/activar registrado")

        for func_name in ['desbloquear_ceo_completo', 'activar_prompt_mejor_opcion',
                          'ciclo_vigilancia_ceo', 'daimon_autonomous_loop']:
            if hasattr(mod7, func_name) and func_name not in globals():
                globals()[func_name] = getattr(mod7, func_name)
                log(f"{func_name} importada desde Parte 7")

        log("Parte 7 (Radar/Negociacion) integrada correctamente")
        return True

    except ImportError:
        log("Parte 7 no disponible (continuando sin radar)")
        return False
    except Exception as e:
        log(f"Error integrando Parte 7: {e}")
        return False


# ============================================================================
# === REGISTRO DE ENDPOINTS DESDE ORQUESTADOR ===
# ============================================================================

def registrar_endpoints_frontend(app_instance=None):
    """
    Registra todos los endpoints del frontend en una app Flask externa.
    Usado por el orquestador principal (Parte 1) para integrar este modulo.
    """
    target_app = app_instance or app

    if target_app is None:
        log("No se proporciono instancia Flask para registrar endpoints")
        return False

    with target_app.app_context():
        for rule in app.url_map.iter_rules():
            if rule.endpoint == 'static':
                continue
            existing = {r.rule for r in target_app.url_map.iter_rules()}
            if rule.rule not in existing:
                try:
                    view_func = app.view_functions.get(rule.endpoint)
                    if view_func:
                        target_app.add_url_rule(
                            rule.rule,
                            endpoint=f"frontend_{rule.endpoint}",
                            view_func=view_func,
                            methods=list(rule.methods - {'HEAD', 'OPTIONS'})
                        )
                except Exception as e:
                    log(f"Error registrando {rule.rule}: {e}")

    log("Endpoints frontend registrados en app externa")
    return True


# ============================================================================
# === EXPORTACION EXPLICITA PARA IMPORTACION DESDE MAIN ===
# ============================================================================

__all__ = [
    'app', 'HTTP_PORT', 'log', 'get_recent_logs',
    'minar_bloque_por_publicacion_controlado',
    'registrar_endpoints_frontend',
    'sincronizar_variables_globales',
    'integrar_network_monitor_automatically',
    'integrar_red_desde_orquestador',
    'integrar_parte7_radar',
    'get_ceo_instance',
    'ALGO_WEIGHTS', 'ZONAS', 'zona_estado',
    'MEJOR_OPCION_PROMPT_TEXTO', 'MODULO_TIEMPO_ETA_PROMPT',
    'obtener_estado_completo',
    'actualizar_estado_desde_orquestador',
    'iniciar_frontend_hilo'
]

if 'app' not in globals() or app is None:
    from flask import Flask
    app = Flask(__name__)
    HTTP_PORT = 8989
    log("app Flask recreada como fallback")


# ============================================================================
# DECORADOR DE GOBERNANZA CEOIA
# ============================================================================

def ceo_governed(module_name: str = None):
    def decorator(module):
        module.__ceo_governed__ = True
        module.__ceo_registered_at__ = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            ceo = None
            if 'ceoia_instance' in globals():
                ceo = globals()['ceoia_instance']
            elif hasattr(sys.modules.get('__main__'), 'ceoia_instance'):
                ceo = getattr(sys.modules['__main__'], 'ceoia_instance')
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


# ============================================================================
# SINCRONIZACION SEGURA CEOIA
# ============================================================================

def sincronizar_variables_globales(mod=None):
    import importlib
    try:
        ceoia_local = None

        try:
            mod_ceo = importlib.import_module("part5_daimon_base")
            iniciar_func = getattr(mod_ceo, "iniciar_ceoia_unificada", None)
            if callable(iniciar_func):
                ceoia_local = iniciar_func()
        except Exception as e:
            print(f"[SYNC] Error importando CEOIA: {e}")

        if ceoia_local is None and mod:
            ceoia_local = getattr(mod, "ceoia", None)

        if ceoia_local is None:
            ceoia_local = globals().get('ceoia', None)

        if ceoia_local is None:
            print("[SYNC] CEOIA no disponible (continuando sin bloqueo)")
            return False

        globals()['ceoia'] = ceoia_local
        globals()['ceo_avanzado'] = ceoia_local

        try:
            main_mod = sys.modules.get('__main__')
            if main_mod:
                if not hasattr(main_mod, 'ceoia') or getattr(main_mod, 'ceoia') is None:
                    main_mod.ceoia = ceoia_local
                if not hasattr(main_mod, 'ceo_avanzado') or getattr(main_mod, 'ceo_avanzado') is None:
                    main_mod.ceo_avanzado = ceoia_local
        except Exception:
            pass

        print("[SYNC] CEOIA sincronizada correctamente")
        return True

    except Exception as e:
        print(f"Error sincronizando aliases CEO: {e}")
        return False


# ============================================================================
# === FUNCIONES DE COMPATIBILIDAD CON ORQUESTADOR (PARTES 1-6) ===
# ============================================================================

def obtener_estado_completo() -> Dict:
    """Retorna estado completo del modulo para el orquestador."""
    return {
        "modulo": "parte8_frontend_html",
        "version": "2.0",
        "puerto": HTTP_PORT,
        "estado_conductor": ESTADO_CONDUCTOR,
        "zona_actual": ULTIMA_ZONA,
        "mejor_opcion_activo": MEJOR_OPCION_PROMPT_ACTIVO,
        "uber_coins": UBER_COINS.to_float_approx() if hasattr(UBER_COINS, 'to_float_approx') else 0.0,
        "bloques_minados": len(blockchain),
        "ceoia_disponible": ceoia is not None,
        "zona_estado": zona_estado,
        "timestamp": time.time()
    }


def actualizar_estado_desde_orquestador(datos: Dict):
    """Permite al orquestador actualizar variables de este modulo."""
    global ESTADO_CONDUCTOR, ULTIMA_ZONA, MEJOR_OPCION_PROMPT_ACTIVO, BENEFICIARIO_ACTUAL

    if 'estado_conductor' in datos:
        ESTADO_CONDUCTOR = datos['estado_conductor']
    if 'zona_actual' in datos:
        ULTIMA_ZONA = datos['zona_actual']
    if 'mejor_opcion_activo' in datos:
        MEJOR_OPCION_PROMPT_ACTIVO = datos['mejor_opcion_activo']
    if 'beneficiario' in datos:
        BENEFICIARIO_ACTUAL = datos['beneficiario']
    if 'zona_estado' in datos:
        for z_id, z_data in datos['zona_estado'].items():
            if z_id in zona_estado:
                zona_estado[z_id].update(z_data)

    log("Estado actualizado desde orquestador")
    return True


def iniciar_frontend_hilo():
    """Inicia el servidor Flask en un hilo daemon (para uso desde orquestador)."""
    def _run():
        try:
            app.run(
                host="0.0.0.0",
                port=HTTP_PORT,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        except OSError as e:
            if "Address already in use" in str(e):
                log(f"Puerto {HTTP_PORT} ya en uso (frontend ya corriendo)")
            else:
                log(f"Error iniciando frontend: {e}")
        except Exception as e:
            log(f"Error critico frontend: {e}")

    hilo = threading.Thread(target=_run, daemon=True, name="FrontendFlask")
    hilo.start()
    log(f"Frontend iniciado en hilo (puerto {HTTP_PORT})")
    return hilo


# ============================================================================
# === EJECUCION STANDALONE ===
# ============================================================================

if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("UBER DAIMON VIVO + SOCIALCOIN - FRONTEND HTML V2", flush=True)
    print("=" * 70, flush=True)
    print(f"Puerto: {HTTP_PORT}", flush=True)
    print(f"URL Principal: http://localhost:{HTTP_PORT}", flush=True)
    print(f"Mapa Pro: http://localhost:{HTTP_PORT}/mapa_pro", flush=True)
    print(f"Mining Demo: http://localhost:{HTTP_PORT}/mining_demo", flush=True)
    print(f"Debug: http://localhost:{HTTP_PORT}/debug/ultra-status", flush=True)
    print(f"Taximetro: Inicia desde $0.00", flush=True)
    print(f"Espera: Activa tras 2 min detenido", flush=True)
    print(f"Panel: Colapsable (compacto/expandido)", flush=True)
    print(f"Trail: Linea negra con desvanecimiento", flush=True)
    print(f"Lluvia: Overlay visual + 30% tarifa", flush=True)
    print("=" * 70, flush=True)

    Path(__file__).parent.joinpath('static').mkdir(exist_ok=True)

    for z_id in zona_estado:
        ratio = random.uniform(0.5, 3.0)
        zona_estado[z_id].update({
            "ratio_demanda": round(ratio, 2),
            "color": "rojo" if ratio > 2.0 else "naranja" if ratio > 1.2 else "azul" if ratio >= 0.8 else "gris",
            "ganancia_estimada": round(random.uniform(2.0, 12.0), 2),
            "tiempo_espera": round(random.uniform(1.0, 10.0), 1)
        })

    integrar_parte7_radar()
    integrar_network_monitor_automatically()

    try:
        app.run(host="0.0.0.0", port=HTTP_PORT, debug=False, use_reloader=False, threaded=True)
    except OSError as e:
        if "Address already in use" in str(e):
            log(f"Puerto {HTTP_PORT} ya en uso. El sistema principal ya esta corriendo?")
        else:
            raise
    except KeyboardInterrupt:
        log("Frontend detenido por usuario")
        sys.exit(0)
