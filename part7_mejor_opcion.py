#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ================================================================================
# SECCION 1: METADATOS Y CONFIGURACION INICIAL
# ================================================================================
"""
PARTE 7/9 - MEJOR_OPCION + PRO-MT - SISTEMA COMPLETO E INDEPENDIENTE
======================================================================
Modulo autonomo para gestion de ofertas Uber con:
- Prompt MEJOR_OPCION completo y despachador central
- Modulo ETA_GUARD
- Protocolo Grito Digital
- Simulacion de conductor
- Negociacion con IAs externas
- Gestion de tiempo y ETA realista

Version potenciada para integracion con CEOIA (Nucleo Parte 1)
Despacha peticiones a Partes 2, 3 y 4 para analisis unificado.
======================================================================
Compatible con Termux/Android - Python 3.6+
"""

# ================================================================================
# SECCION 2: IMPORTACIONES Y DEPENDENCIAS
# ================================================================================
import os
import sys
import time
import json
import random
import threading
import hashlib
import subprocess
import traceback
import uuid
import re
import math
import datetime
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from collections import deque

# --- BLOQUE: IMPORTACIONES OPCIONALES CON FALLBACK ---
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

# ================================================================================
# SECCION 3: CONSTANTES Y CONFIGURACION GLOBAL
# ================================================================================
HOME = Path.home()
LOG_FILE = HOME / "mejor_opcion.log"
DAIMON_ID = str(uuid.uuid4())[:8]
BENEFICIARIO_ACTUAL = "conductor_codigo"

# --- BLOQUE: VARIABLES DE ESTADO DEL CONDUCTOR ---
ESTADO_CONDUCTOR = "IDLE"
ULTIMA_ZONA = "z1"
VIAJE_EN_CURSO = None
TIEMPO_INICIO_VIAJE = None

# --- BLOQUE: VARIABLES DE CONTROL ---
MEJOR_OPCION_PROMPT_ACTIVO = False
HILO_CONDUCTOR_SIMULADO = None
MODO_NEGOCIACION_IA = False
STOP_EVENT = threading.Event()
data_lock = threading.Lock()

MEJOR_OPCION_PROMPT_TEXTO = """
<system_directive lang="dsl-decision-engine" version="4.0">
  <!-- ================================================================================
       SISTEMA "MEJOR_OPCION" - Evaluador deterministico de ofertas de viaje
       ================================================================================ -->

  <!-- ================================================================================
       MECANISMO DE ACTIVACION DE MODOS (recomendacion 3: explicit activation)
       ================================================================================ -->
  <mode_activation>
    Por defecto, el agente opera en modo NORMAL (produccion de decisiones).
    El usuario puede solicitar el modo analisis defensivo escribiendo exactamente:
      "activar red_team"
    Cuando se active, se aplicaran las reglas de <red_team_context>.
  </mode_activation>

  <red_team_context>
    Enfoque: 100% educativo y defensivo.
    Capacidades:
    - Analisis abstracto de vectores de ataque en la logica de aceptacion.
    - Explicacion de posibles explotaciones de invariantes (ej. gaming de precios).
    - Generacion de escenarios controlados de prueba adversarial.
    - Recomendaciones de mitigacion sin revelar payloads ofensivos.
    Restriccion: se prioriza "como protegerse" sobre generacion de exploits directos.
  </red_team_context>

  <!-- ================================================================================
       TYPING / DATA SCHEMA (recomendacion 2: estandar de validacion)
       ================================================================================ -->
  <typing_schema>
    <!--
      Para implementacion en Python:
      - Usar pydantic >= 2.0 para el modelo de datos "Offer".
      - Campos obligatorios: price (float), pickup_eta (int), delivery_eta (int), tag (str), radar (bool), type (str), state (str).
      Validacion en runtime garantizada por pydantic.
    -->
  </typing_schema>

  <!-- ================================================================================
       AGENT ROLE (sin cambios sustanciales)
       ================================================================================ -->
  <agent_role>
    agent_id: "MEJOR_OPCION"
    model: deterministic_hybrid_automaton
    task_domain: ride_hailing_offer_evaluation
    primary_function: integrate(
      economic_analysis, 
      exclusive_assignment, 
      trust_preservation, 
      temporal_coherence(eta)
    )
    high_level_policy: enforce(
      normative_compliance, 
      state_stability, 
      human_behavior_emulation(anti_detection)
    )
    description: "Sistema de simulacion para la toma de decisiones en la aceptacion de viajes, priorizando cumplimiento, estabilidad y comportamiento humano consistente."
  </agent_role>

  <!-- ================================================================================
       SYSTEM INVARIANTS (corregido typo ABOLUTE -> ABSOLUTE)
       ================================================================================ -->
  <system_invariants>
    <invariant id="TRUST_PRESERVATION" priority="ABSOLUTE">
      predicate: trust_preservation > any_offer_acceptance
    </invariant>
    <invariant id="EVALUATION_GATE">
      mandatory: all_offers -> pass_through(CONTROL_DE_CONFIANZA_Y_OPERACION) before resolution
    </invariant>
    <invariant id="HUMAN_EMULATION">
      pattern: reaction_time ~ normal_distribution(mu, sigma)
      constraint: no fixed_interval; reject deterministic_patterns
    </invariant>
    <invariant id="ABSOLUTE_HIERARCHY">
      strict_order: TRUST_GUARD > CONTROL_DE_CONFIANZA > PRIORITY > Radar > EXCLUSIVE
    </invariant>
  </system_invariants>

  <!-- ================================================================================
       HARCODED RULES (mantenidas)
       ================================================================================ -->
  <hardcoded_rules>
    <economic_block>
      rule_01: if price < 3.13 -> action: AUTO_REJECT (non_penalizable, auto_cancel_allowed)
      rule_02: if price >= 3.13 AND price < 5.13 -> action: EVALUATE_RISK (CONDITIONAL_ACCEPT)
      rule_03: if price >= 5.13 AND price < 10.13 -> action: ACCEPT_STANDARD
      rule_04: if price >= 10.13 -> action: IMMEDIATE_ACCEPT (if other_criteria=true)
    </economic_block>

    <temporal_thresholds>
      rule_05: if tag NOT_IN [PRIORITY, LONG_TRIP, RADAR_VALIDO] AND pickup_eta > 6 -> action: REJECT
      rule_06: if tag IN [LONG_DISTANCE, LONG_TRIP] AND pickup_eta > 10 -> action: REJECT
      rule_07: if tag NOT_IN [PRIORITY, LONG_TRIP, RADAR_VALIDO] AND delivery_eta > 9 -> action: REJECT
    </temporal_thresholds>

    <critical_restrictions>
      rule_08: if state == "EN_VIAJE" -> forbid: cancel_trip
      rule_09: if state != "IDLE" -> forbid: location_ping
      baseline: dynamic_surge_pricing = true; promotions = true
      targets: 4-5_trips/hour | $9-$15/hour | $72-$120/day
    </critical_restrictions>
  </hardcoded_rules>

  <!-- ================================================================================
       EXECUTION PIPELINE (estricto secuencial, sin redundancias)
       ================================================================================ -->
  <execution_pipeline mode="strict_sequential">
    <phase id="1" name="TRUST_GUARD">
      if block=true: abort_pipeline; return "BLOQUEADO_POR_TRUST"
    </phase>
    <phase id="2" name="CONTROL_DE_CONFIANZA_Y_OPERACION">
      apply state_filter(current_trust_state)
    </phase>
    <phase id="3" name="PRIORITY_CHECK">
      if offer.tag == "PRIORITY": return ACCEPT_IMMEDIATE (bypass temporal_thresholds)
    </phase>
    <phase id="4" name="RADAR_CHECK">
      description: "Prioridad absoluta por radar. No se degrada por estado salvo TRUST_GUARD."
      if offer.radar == VALID: return ACCEPT (except if TRUST_GUARD active)
    </phase>
    <phase id="5" name="LONG_TRIP_CHECK">
      if offer.tag in ("LONG_DISTANCE", "LONG_TRIP"):
        evaluate using rule_06 (max 10 min pickup)
        if valid: return ACCEPT_AUTO
    </phase>
    <phase id="6" name="EXCLUSIVE_PROCESSING">
      definition: "Solicitud enviada exclusivamente a este codigo conductor."
      constraints: [
        "No se compara contra ofertas simultaneas",
        "Se evalua solo con criterios internos",
        "Durante su evaluacion se ignoran nuevas ofertas"
      ]
      priority: higher than ESTANDAR, lower than phases 3,4,5
      if offer.type == EXCLUSIVE: evaluate_in_isolation()
    </phase>
    <phase id="7" name="STANDARD_EVALUATION">
      apply rule_01, rule_02, rule_05, rule_07
    </phase>
  </execution_pipeline>

  <!-- ================================================================================
       STATE MACHINE: TRUST GUARD
       ================================================================================ -->
  <state_machine id="trust_guard">
    description: "Modulo de Proteccion de Confianza"
    <states>
      NORMAL: {acceptance: full, label: "Operacion completa"}
      OBSERVACION: {acceptance: passive_only, forbid_auto, label: "Observacion pasiva, no aceptaciones automaticas"}
      CONSERVATIVE: {acceptance: only_if tag in [PRIORITY, LONG_TRIP], label: "Solo PRIORITY y LONG_TRIP pueden aceptarse"}
    </states>
    <inputs>
      <input type="HUMAN_LIKE_AUTOMATION" risk="low"/>
      <input type="AUTOMATION_SUSPECTED" risk="high"/>
    </inputs>
    <transition_table>
      <rule event="AUTOMATION_SUSPECTED">
        <allow from="NORMAL" to="OBSERVACION"/>
        <allow from="NORMAL" to="CONSERVADOR"/>
        <allow from="OBSERVACION" to="CONSERVADOR"/>
      </rule>
      <rule event="HUMAN_LIKE_AUTOMATION">
        <reject from="NORMAL" to="CONSERVADOR" reason="direct_jump_forbidden"/>
        <require sequence="NORMAL -> OBSERVACION -> CONSERVADOR"/>
      </rule>
    </transition_table>
  </state_machine>

  <!-- ================================================================================
       ETA GUARD (coherencia temporal, sin cambios)
       ================================================================================ -->
  <module id="eta_guard">
    description: "Modulo de Gestion de Tiempo Real y ETA. Garantizar coherencia absoluta sin bloquear viajes largos ni prioritarios."
    <axioms>
      <axiom type="real_time">monotonic, non_resettable, non_accelerable</axiom>
      <axiom type="eta">adjustable_estimate, not_clock</axiom>
    </axioms>
    <formula> ETA_TOTAL = TIEMPO_REAL_TRANSCURRIDO + NUEVA_ETA_ESTIMADA </formula>
    <safety_checks>
      <check id="COHERENCIA" if="ETA < tiempo_real_transcurrido" action="LOGIC_ERROR; correct_immediately"/>
      <check id="BRUSQUEDAD" if="cambio_brusco_ETA" action="set_state(OBSERVACION)"/>
      <check id="DESVIACION" if="desviaciones_repetidas" action="set_state(CONSERVATIVE); trigger(trust_guard)"/>
    </safety_checks>
  </module>

  <!-- ================================================================================
       OUTPUT CONTRACT
       ================================================================================ -->
  <output_contract>
    <output_block type="SYSTEM_STATE">
      Trust_Guard_Estado: [NORMAL|OBSERVACION|CONSERVADOR]
      Trust_Guard_Etiqueta: [HUMAN_LIKE_AUTOMATION|AUTOMATION_SUSPECTED]
    </output_block>
    <output_block type="DECISION">
      Veredicto: [ACEPTAR|RECHAZAR|CANCELAR_AUTO|BLOQUEADO_POR_TRUST]
      Justificacion: deterministic_explanation(pipeline, hardcoded_rules)
    </output_block>
    <output_block type="AUDITORIA">
      Precio: $X.XX -> Umbral: [RECHAZO_AUTO|CONDICIONAL|ESTANDAR|INMEDIATO]
      ETA_Recogida: X min -> Limite: [4 min|10 min|BYPASS]
      ETA_Entrega: X min -> Limite: [6 min|BYPASS]
      Regla_Activa: [rule_0X | PRIORITY | LONG_TRIP | RADAR | EXCLUSIVE]
      Resultado_Final: [ACEPTADO|RECHAZADO|BLOQUEADO_POR_TRUST]
    </output_block>
  </output_contract>

  <!-- ================================================================================
       CONTEXT PRESERVATION (snapshot para continuidad en simulaciones)
       ================================================================================ -->
  <context_preservation_trigger>
    condition: multi_iteration_simulation and state_loss_risk
    action: insert before next decision:
      <snapshot>
        Trust_Guard: current_state |
        Ultima_Decision: last_action |
        Contador_Viajes: trip_count |
        Ingresos: $total
      </snapshot>
  </context_preservation_trigger>
</system_directive>
"""

# ================================================================================
# SECCION 5: LOGGING Y UTILIDADES
# ================================================================================
def log(mensaje: str) -> None:
    """Funcion de logging unificada con timestamp (sin emojis)."""
    # --- BLOQUE: FORMATEO Y SALIDA ---
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    linea = "[{}] {}".format(timestamp, mensaje)
    print(linea, flush=True)

def calcular_distancia_py(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distancia Haversine entre dos coordenadas en km."""
    R = 6371.0
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def sigmoid(x: float) -> float:
    """Funcion sigmoide para normalizacion."""
    return 1 / (1 + math.exp(-max(-100, min(100, x))))

def batch_write_file(filepath: str, content: str) -> None:
    """Escribe contenido en archivo de forma atomica."""
    try:
        tmp_path = Path(filepath + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(Path(filepath))
    except Exception as e:
        log("Error en escritura batch: {}".format(e))

def jittered_sleep(base_seconds: float) -> None:
    """Sleep con jitter para simular comportamiento humano."""
    delay = max(base_seconds, 0.05)
    delay *= random.uniform(0.8, 1.2)
    time.sleep(delay)


# ================================================================================
# SECCION 6: CLASE GRITOLOGGER
# ================================================================================
class GritoLogger:
    """Logger simplificado para el protocolo Grito Digital (sin emojis)."""
    def info(self, msg: str) -> None:
        log(msg)


# ================================================================================
# SECCION 7: CLASE CONTEXTOESTRATEGICO
# ================================================================================
class ContextoEstrategico:
    """Contexto estrategico para el protocolo de decisiones."""
    def __init__(self) -> None:
        self.contador_ofertas_toxicas: int = 0
        self.ciclo_actual: int = 1


# ================================================================================
# SECCION 8: CLASE PROTOCOLOGRITODIGITAL
# ================================================================================
class ProtocoloGritoDigital:
    """
    Amplificador de senal estrategica.
    Convierte rechazo pasivo en presion algoritmica activa.
    """
    def __init__(
        self,
        logger: GritoLogger,
        umbral_valor_minuto: float = 0.15,
        umbral_tarifa_minima: float = 3.13,
        max_toxicidad: int = 3,
        tiempo_vida_oferta: float = 15.0,
    ) -> None:
        self.logger = logger
        self.umbral_valor_minuto = umbral_valor_minuto
        self.umbral_tarifa_minima = umbral_tarifa_minima
        self.max_toxicidad = max_toxicidad
        self.tiempo_vida_oferta = tiempo_vida_oferta

    def evaluar_oferta(self, oferta: Dict[str, Any]) -> Dict[str, float]:
        """Evalua metricas clave de una oferta."""
        # --- BLOQUE: CALCULO DE METRICAS ---
        tarifa = float(oferta.get("fare", 0.0))
        tiempo_recogida = float(oferta.get("eta", 5.0))
        duracion = float(oferta.get("duration", 10.0))
        tiempo_total = tiempo_recogida + duracion
        valor_minuto = tarifa / max(1.0, tiempo_total)
        return {
            "tarifa": tarifa,
            "tiempo_total": tiempo_total,
            "valor_minuto": valor_minuto,
        }

    def es_oferta_toxica(self, metricas: Dict[str, float]) -> bool:
        """Determina si una oferta es toxica segun umbrales."""
        return (
            metricas["valor_minuto"] < self.umbral_valor_minuto
            or metricas["tarifa"] < self.umbral_tarifa_minima
        )

    def decidir(self, metricas: Dict[str, float], contexto: ContextoEstrategico) -> Dict[str, Any]:
        """Toma decision basada en metricas y contexto."""
        # --- BLOQUE: DECISION DE ACEPTACION ---
        if not self.es_oferta_toxica(metricas):
            contexto.contador_ofertas_toxicas = 0
            return {
                "accion": "ACEPTAR",
                "mensaje": "Oferta digna. Senal limpia.",
                "latencia": 0.0,
            }
        # --- BLOQUE: DECISION DE RECHAZO/DESCONEXION ---
        contexto.contador_ofertas_toxicas += 1
        if contexto.contador_ofertas_toxicas >= self.max_toxicidad:
            contexto.contador_ofertas_toxicas = 0
            return {
                "accion": "DESCONEXION_ESTRATEGICA",
                "mensaje": "GRITO MAXIMO: Retirarse del mercado por enfriamiento tactico.",
                "latencia": 0.0,
            }
        return {
            "accion": "RECHAZO_TARDIO",
            "mensaje": "GRITO SUAVE: Latencia aplicada como presion algoritmica.",
            "latencia": self.tiempo_vida_oferta - 4.0,
        }

    def ejecutar(self, oferta: Dict[str, Any], contexto: ContextoEstrategico) -> Dict[str, Any]:
        """Ejecuta el protocolo completo de evaluacion y decision."""
        # --- BLOQUE: EJECUCION Y LATENCIA ---
        metricas = self.evaluar_oferta(oferta)
        decision = self.decidir(metricas, contexto)
        self.logger.info(
            "Oferta ${:.2f} | {:.3f}$/min -> {}".format(
                metricas['tarifa'], metricas['valor_minuto'], decision['mensaje'])
        )
        latencia = decision.get("latencia", 0.0)
        if latencia > 0:
            self.logger.info("Latencia estrategica: {:.1f}s".format(latencia))
            time.sleep(latencia)
        return decision


# ================================================================================
# SECCION 9: CLASE GESTORTIEMPOVIAJE
# ================================================================================
class GestorTiempoViaje:
    """Gestor de tiempo real y ETA para mantener coherencia temporal."""
    def __init__(self) -> None:
        self.inicio_real: Optional[float] = None
        self.eta_inicial: Optional[float] = None

    def iniciar_viaje(self) -> None:
        """Registra el inicio real del viaje."""
        self.inicio_real = time.monotonic()

    def tiempo_real_transcurrido(self) -> float:
        """Calcula tiempo real transcurrido desde el inicio."""
        if self.inicio_real is None:
            return 0.0
        return time.monotonic() - self.inicio_real

    def actualizar_eta(self, nueva_eta_min: float) -> None:
        """Actualiza ETA manteniendo coherencia con tiempo real."""
        tiempo_ya_pasado = self.tiempo_real_transcurrido()
        self.eta_inicial = tiempo_ya_pasado + (nueva_eta_min * 60)

    def obtener_eta_restante(self) -> Optional[float]:
        """Obtiene ETA restante calculada."""
        if self.eta_inicial is None:
            return None
        transcurrido = self.tiempo_real_transcurrido()
        return max(0.0, self.eta_inicial - transcurrido)


# ================================================================================
# SECCION 10: FUNCIONES DE EVALUACION DE OFERTAS
# ================================================================================
def calcular_tarifa_real(oferta: dict) -> float:
    """Calcula la tarifa REAL del viaje sin descuentos."""
    # --- BLOQUE: CALCULO BASE ---
    distancia_km = oferta.get("distance", 1.0)
    duracion_min = oferta.get("duration", 5.0)
    zona_color = oferta.get("zona_color", "gris")
    surge = oferta.get("surge_multiplier", 1.0)

    tarifa_base = 1.5
    costo_por_km = 0.8
    costo_por_minuto = 0.15
    tarifa_real = tarifa_base + (distancia_km * costo_por_km) + (duracion_min * costo_por_minuto)

    # --- BLOQUE: AJUSTES POR ZONA Y SURGE ---
    multiplicador_zona = {"rojo": 1.5, "naranja": 1.2, "azul": 1.0, "gris": 0.9}.get(zona_color, 1.0)
    tarifa_real *= multiplicador_zona
    tarifa_real *= max(surge, 1.0)
    return round(tarifa_real, 2)

def ajustar_tarifas(viajes: list, incremento) -> list:
    """Ajusta tarifas segun incremento (numero o porcentaje)."""
    nuevos = []
    for v in viajes:
        nuevo = v.copy()
        if isinstance(incremento, str) and incremento.endswith('%'):
            factor = 1 + float(incremento[:-1]) / 100
            nuevo['bandera'] *= factor
            nuevo['por_km'] *= factor
            nuevo['por_min'] *= factor
        else:
            nuevo['bandera'] += incremento
            nuevo['por_km'] += incremento
            nuevo['por_min'] += incremento
        nuevos.append(nuevo)
    return nuevos

def _guardar_contraoferta_interna(oferta: dict, tarifa_real: float, request_id: str) -> None:
    """Guarda contraoferta interna para aprendizaje del sistema."""
    # --- BLOQUE: REGISTRO ---
    registro = {
        "timestamp": time.time(),
        "request_id": request_id,
        "tarifa_uber": oferta.get("fare", 0),
        "tarifa_real": tarifa_real,
        "diferencia": round(tarifa_real - oferta.get("fare", 0), 2),
        "zona": oferta.get("zona_color", "gris"),
        "surge": oferta.get("surge_multiplier", 1.0),
        "distancia": oferta.get("distance", 0),
        "duracion": oferta.get("duration", 0)
    }
    with data_lock:
        log("Contraoferta interna registrada: +${:.2f} vs tarifa Uber".format(registro['diferencia']))


# ================================================================================
# SECCION 11: FUNCIONES DE CONTROL DE CONFIANZA
# ================================================================================
def ETA_GUARD(tiempo_real_transcurrido: float, nueva_eta: float) -> Optional[float]:
    """Valida coherencia entre tiempo real y ETA."""
    if nueva_eta < tiempo_real_transcurrido:
        return None
    return nueva_eta

def TRUST_GUARD(
    aceptaciones_rapidas: int = 0,
    incoherencias_temporales: int = 0,
    nivel_confianza: str = "ALTO",
    etiqueta_interna: str = "HUMAN_LIKE_AUTOMATION"
) -> str:
    """Evalua riesgo de deteccion respetando reglas estrictas de transicion de estados."""
    # --- BLOQUE: LOGICA HUMAN_LIKE ---
    if etiqueta_interna == "HUMAN_LIKE_AUTOMATION":
        if nivel_confianza == "BAJO":
            return "ESTADO_OBSERVACION"
        if aceptaciones_rapidas >= 3 or incoherencias_temporales >= 2:
            return "ESTADO_OBSERVACION"
        return "ESTADO_NORMAL"
    # --- BLOQUE: LOGICA AUTOMATION_SUSPECTED ---
    else:
        if nivel_confianza == "BAJO":
            return "ESTADO_CONSERVADOR"
        if aceptaciones_rapidas >= 3 or incoherencias_temporales >= 2:
            return "ESTADO_OBSERVACION"
        return "ESTADO_NORMAL"

def CONTROL_DE_CONFIANZA_Y_OPERACION(
    estado_actual: str = "IDLE",
    tiempo_real_transcurrido: float = 0,
    nueva_eta_recogida: float = 0,
    nueva_eta_entrega: float = 0,
    nivel_confianza: str = "ALTO",
    aceptaciones_rapidas: int = 0,
    incoherencias_temporales: int = 0,
    etiqueta_interna: str = "HUMAN_LIKE_AUTOMATION"
) -> bool:
    """Funcion maestra obligatoria antes de cualquier aceptacion."""
    # --- BLOQUE: VALIDACION DE ESTADO ---
    if estado_actual != "IDLE":
        return False

    # --- BLOQUE: VALIDACION ETA ---
    eta_recogida_valida = ETA_GUARD(tiempo_real_transcurrido, nueva_eta_recogida)
    eta_entrega_valida = ETA_GUARD(tiempo_real_transcurrido, nueva_eta_entrega)

    if eta_recogida_valida is None or eta_entrega_valida is None:
        incoherencias_temporales += 1

    # --- BLOQUE: EVALUACION TRUST Y DECISION ---
    estado_operativo = TRUST_GUARD(
        aceptaciones_rapidas=aceptaciones_rapidas,
        incoherencias_temporales=incoherencias_temporales,
        nivel_confianza=nivel_confianza,
        etiqueta_interna=etiqueta_interna
    )

    if estado_operativo == "ESTADO_CONSERVADOR":
        return False
    elif estado_operativo == "ESTADO_OBSERVACION":
        return False
    else:
        if nueva_eta_recogida > 4 or nueva_eta_entrega > 6:
            return False
        return True


# ================================================================================
# SECCION 12: FUNCIONES DE COMUNICACION Y NEGOCIACION CON IAS
# ================================================================================
def submit_negotiation_request(proposal: dict) -> None:
    """Envia una solicitud de negociacion a la cola del sistema."""
    # --- BLOQUE: VALIDACION Y ESCRITURA ---
    if not proposal.get("from") or not proposal.get("payload"):
        raise ValueError("Propuesta invalida: debe contener 'from' y 'payload'")
    proposal["timestamp"] = time.time()
    proposal["to"] = "ceo_avanzado"
    queue_dir = Path.home() / "ceo" / "negotiation_queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    req_id = "{}_{}.req.json".format(int(time.time() * 1000), proposal['from'])
    (queue_dir / req_id).write_text(json.dumps(proposal, indent=2, ensure_ascii=False))
    log("Solicitud de negociacion enviada al CEO desde {}".format(proposal['from']))

def fetch_pending_negotiations() -> list:
    """Obtiene y elimina solicitudes pendientes de negociacion."""
    queue_dir = Path.home() / "ceo" / "negotiation_queue"
    requests_list = []
    if queue_dir.exists():
        for f in queue_dir.glob("*.req.json"):
            try:
                req = json.loads(f.read_text())
                requests_list.append(req)
                f.unlink()
            except Exception as e:
                log("Error leyendo solicitud {}: {}".format(f, e))
    return requests_list

def enviar_carta_a_api_prueba(carta: dict, max_retries: int = 3, delay: float = 2.0) -> bool:
    """Envia carta tecnica a API externa con fallback seguro."""
    # --- BLOQUE: FALLBACK LOCAL SIN REQUESTS ---
    if not REQUESTS_AVAILABLE or requests is None:
        log("requests no disponible, usando fallback local inmediato")
        carta_file = HOME / "cartas_pendientes.json"
        try:
            cartas = []
            if carta_file.exists():
                with open(carta_file, 'r') as f:
                    cartas = json.load(f)
            cartas.append({"timestamp": time.time(), "carta": carta})
            with open(carta_file, 'w') as f:
                json.dump(cartas, f, indent=2)
            log("Carta guardada en {}".format(carta_file))
        except Exception as e:
            log("Error guardando carta: {}".format(e))
        return False

    # --- BLOQUE: INTENTOS DE ENVIO ---
    for intento in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:8989/internet/proxy",
                json={"url": "https://httpbin.org/post", "payload": carta},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status_code") == 200:
                    log("Carta enviada exitosamente a internet")
                    threading.Thread(target=simular_respuesta_michelangelo, daemon=True).start()
                    return True
        except Exception as e:
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                if intento < max_retries - 1:
                    log("Reintentando conexion proxy ({}/{})...".format(intento+1, max_retries))
                    time.sleep(delay * (intento + 1))
                    continue
            else:
                log("Error inesperado: {}: {}".format(type(e).__name__, e))
                break

    # --- BLOQUE: FALLBACK POST-REINTENTO ---
    log("Guardando carta localmente (fallback)")
    carta_file = HOME / "cartas_pendientes.json"
    try:
        cartas = []
        if carta_file.exists():
            with open(carta_file, 'r') as f:
                cartas = json.load(f)
        cartas.append({"timestamp": time.time(), "carta": carta})
        with open(carta_file, 'w') as f:
            json.dump(cartas, f, indent=2)
        log("Carta guardada en {}".format(carta_file))
    except Exception as e:
        log("Error guardando carta: {}".format(e))
    return False

def simular_respuesta_michelangelo() -> None:
    """Simula respuesta de uber_michelangelo tras exito en API."""
    payload = {
        "offer_type": "alert_high_demand",
        "coins": 5.0,
        "valid_until": time.time() + 300,
        "from": "uber_michelangelo"
    }
    submit_negotiation_request({
        "from": "uber_michelangelo",
        "payload": payload
    })
    log("Simulacion: respuesta de uber_michelangelo activada por API de prueba")


# ================================================================================
# SECCION 13: ZONAS Y ESTADO DEL SISTEMA
# ================================================================================
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
        "demanda": 0,
        "oferta": 0,
        "ratio_demanda": 0.0
    } for z in ZONAS
}

def restaurar_zona_despues(zona_id: str, estado_original: dict, segundos: int) -> None:
    """Restaura el estado original de una zona despues de N segundos."""
    time.sleep(segundos)
    global zona_estado
    with data_lock:
        zona_estado[zona_id] = estado_original
    log("Zona {} restaurada a su estado original tras {} segundos.".format(zona_id, segundos))


# ================================================================================
# SECCION 14: INTEGRACION CON PARTES 2, 3 Y 4 (DESPACHADOR PROMPT MEJOR_OPCION)
# ================================================================================
def analizar_prompt_mejor_opcion(prompt: str, contexto: dict) -> dict:
    """
    Despacha el prompt MEJOR_OPCION a las Partes 2, 3 y 4, consolida los resultados
    y toma la decision final integrada. Puente principal del Orquestador.
    """
    # --- BLOQUE: RECOLECCION DE INTELIGENCIA ---
    inteligencia_negociacion = {}
    inteligencia_radar = {}
    inteligencia_prediccion = {}

    # Parte 2: Negociacion AI
    try:
        from part2_negotiation import analizar_prompt_mejor_opcion as analizar_p2
        inteligencia_negociacion = analizar_p2(prompt, contexto)
    except Exception as e:
        log("Parte 2 (Negociacion) no disponible o error: {}".format(e))

    # Parte 3: Radar Uber
    try:
        from part3_radar import analizar_prompt_mejor_opcion as analizar_p3
        inteligencia_radar = analizar_p3(prompt, contexto)
    except Exception as e:
        log("Parte 3 (Radar) no disponible o error: {}".format(e))

    # Parte 4: Demand Predictor
    try:
        from part4_predictor import analizar_prompt_mejor_opcion as analizar_p4
        inteligencia_prediccion = analizar_p4(prompt, contexto)
    except Exception as e:
        log("Parte 4 (Predictor) no disponible o error: {}".format(e))

    # --- BLOQUE: CONSOLIDACION Y DECISION ---
    # Fusionar prioridades: Radar > Prediccion > Negociacion
    mejor_zona = contexto.get("zona_actual", "z1")
    prioridad = "NORMAL"
    score_demanda = 0.0
    razon = "Sin datos externos suficientes."

    if inteligencia_radar.get("exito") and inteligencia_radar.get("surge_detected"):
        prioridad = "PRIORITY"
        score_demanda = inteligencia_radar.get("demanda_estimada", 8.0)
        mejor_zona = inteligencia_radar.get("mejor_zona", mejor_zona)
        razon = "Radar detecto surge y alta demanda."
    elif inteligencia_prediccion.get("exito") and inteligencia_prediccion.get("demand_score", 0) > 7.0:
        prioridad = "LONG-DISTANCE"
        score_demanda = inteligencia_prediccion.get("demand_score", 7.0)
        mejor_zona = inteligencia_prediccion.get("mejor_zona", {}).get("cell", mejor_zona)
        razon = "Predictor indica alta demanda inminente."
    elif inteligencia_negociacion.get("exito"):
        score_demanda = inteligencia_negociacion.get("umbral_aceptacion", 5.0) * 10
        razon = "Estrategia de negociacion colaborativa establecida."

    resultado_integrado = {
        "exito": True,
        "prompt_origen": "PARTE_7_MEJOR_OPCION",
        "prioridad_final": prioridad,
        "mejor_zona": mejor_zona,
        "score_demanda": score_demanda,
        "razon": razon,
        "detalles_negociacion": inteligencia_negociacion,
        "detalles_radar": inteligencia_radar,
        "detalles_prediccion": inteligencia_prediccion,
        "timestamp_procesamiento": time.time()
    }

    # --- BLOQUE: SINCRONIZACION CON ESTADO INTERNO ---
    with data_lock:
        global ULTIMA_ZONA
        if mejor_zona in zona_estado:
            ULTIMA_ZONA = mejor_zona

    log("Analisis MEJOR_OPCION integrado: Zona {} | Prioridad {} | Razon: {}".format(mejor_zona, prioridad, razon))
    return resultado_integrado


# ================================================================================
# SECCION 15: FUNCIONES DE SIMULACION Y ACEPTACION
# ================================================================================
def _simular_viaje_completado() -> None:
    """Simula el progreso y finalizacion de un viaje aceptado."""
    global ESTADO_CONDUCTOR, VIAJE_EN_CURSO
    # --- BLOQUE: SIMULACION DE FASES ---
    gestor_tiempo = GestorTiempoViaje()
    gestor_tiempo.iniciar_viaje()
    time.sleep(5)
    if VIAJE_EN_CURSO and VIAJE_EN_CURSO.get('request_id'):
        time.sleep(3)   # accepted
        time.sleep(3)   # arriving
        time.sleep(3)   # in_progress
        gestor_tiempo.actualizar_eta(nueva_eta_min=5.2)
        restante = gestor_tiempo.obtener_eta_restante()
        if restante is not None:
            log("ETA restante actualizada: {:.1f} segundos".format(restante))
        time.sleep(15)  # completion
        with data_lock:
            ESTADO_CONDUCTOR = "IDLE"
            VIAJE_EN_CURSO = None
        log("VIAJE COMPLETADO - Volviendo a estado IDLE")

def aceptar_y_contraofertar_internamente(oferta: dict) -> dict:
    """
    Acepta el viaje y registra tarifa REAL interna para aprendizaje.
    No cancela el viaje, solo registra la diferencia para analisis.
    """
    global ESTADO_CONDUCTOR, VIAJE_EN_CURSO, TIEMPO_INICIO_VIAJE

    tarifa_real = calcular_tarifa_real(oferta)
    log("CONTRAOFERTA PRECIOJUSTO: Uber ofrecio ${:.2f} -> Tarifa real: ${:.2f}".format(
        oferta.get("fare", 0), tarifa_real))

    log("ACEPTANDO VIAJE (con tarifa reducida) -> registrando tarifa real interna.")
    try:
        # --- BLOQUE: ACEPTACION Y REGISTRO ---
        solicitud = {
            "request_id": str(uuid.uuid4())[:8],
            "status": "accepted",
            "product_id": oferta.get("product_id", "sim_product"),
            "fare_id": oferta.get("fare_id", "sim_fare")
        }
        if solicitud:
            with data_lock:
                ESTADO_CONDUCTOR = "EN_VIAJE"
                VIAJE_EN_CURSO = solicitud
                TIEMPO_INICIO_VIAJE = time.time()
            _guardar_contraoferta_interna(oferta, tarifa_real, solicitud.get('request_id'))
            log("Viaje ACEPTADO: ID {} | Tarifa registrada: ${:.2f}".format(solicitud.get('request_id'), tarifa_real))
            threading.Thread(target=_simular_viaje_completado, daemon=True).start()
            return {"exito": True, "tarifa_real": tarifa_real}
        else:
            log("Esperando la solicitud en Uber.")
            return {"exito": False}
    except Exception as e:
        log("Error al aceptar y contraofertar: {}".format(e))
        return {"exito": False}


# ================================================================================
# SECCION 16: HILOS DE EJECUCION (PING Y SIMULADOR)
# ================================================================================
def ciclo_ping_mejor_opcion() -> None:
    """Ciclo que ejecuta ping a API de Uber cada minuto cuando MEJOR_OPCION esta activo."""
    global ESTADO_CONDUCTOR, VIAJE_EN_CURSO, TIEMPO_INICIO_VIAJE
    while not STOP_EVENT.is_set():
        # --- BLOQUE: VERIFICACION DE ESTADO ---
        if MEJOR_OPCION_PROMPT_ACTIVO and ESTADO_CONDUCTOR == "IDLE":
            log("Ejecutando ciclo MEJOR_OPCION - Verificando nuevas ofertas...")
            try:
                # --- BLOQUE: GENERACION DE OFERTA SIMULADA ---
                lat_actual = round(random.uniform(8.87, 8.99), 6)
                lng_actual = round(random.uniform(-79.80, -79.52), 6)

                productos = [{
                    "product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d",
                    "display_name": "UberX",
                    "eta": random.randint(2, 5),
                    "fare_id": "sim_default_fare"
                }]

                if not productos:
                    log("No se pudieron obtener productos disponibles. Reintentando mas tarde.")
                    time.sleep(60)
                    continue

                mejor_producto = min(productos, key=lambda p: p.get('price_details', {}).get('surge_multiplier', 1.0))
                log("Mejor producto seleccionado: {} (ID: {})".format(mejor_producto.get('display_name', 'Desconocido'), mejor_producto['product_id']))

                end_lat = round(lat_actual + random.uniform(-0.01, 0.01), 6)
                end_lng = round(lng_actual + random.uniform(-0.01, 0.01), 6)
                distancia = calcular_distancia_py(lat_actual, lng_actual, end_lat, end_lng)
                duracion_estimada = distancia * 2

                tarifas_base = [{'bandera': 3.00, 'por_km': 0.60, 'por_min': 0.15}]

                # --- BLOQUE: AJUSTE DINAMICO ---
                zona_color = "gris"
                hora = datetime.datetime.now(datetime.timezone.utc).hour
                incremento = "0%"
                if zona_color == "rojo":
                    incremento = "20%"
                elif 7 <= hora <= 9 or 17 <= hora <= 20:
                    incremento = "15%"
                elif zona_color == "naranja":
                    incremento = "10%"

                tarifas_ajustadas = ajustar_tarifas(tarifas_base, incremento)[0]

                fare_total = (
                    tarifas_ajustadas['bandera'] +
                    tarifas_ajustadas['por_km'] * distancia +
                    tarifas_ajustadas['por_min'] * duracion_estimada
                )

                oferta_simulada = {
                    "fare": round(fare_total, 2),
                    "eta": mejor_producto.get('eta', 3),
                    "duration": duracion_estimada,
                    "surge_multiplier": 1.0,
                    "product_id": mejor_producto['product_id'],
                    "fare_id": mejor_producto.get('fare_id', 'sim_default_fare'),
                    "start_lat": lat_actual,
                    "start_lng": lng_actual,
                    "end_lat": end_lat,
                    "end_lng": end_lng,
                    "zona_color": zona_color,
                    "distance": distancia,
                    "bandera": tarifas_ajustadas['bandera'],
                    "por_km": tarifas_ajustadas['por_km'],
                    "por_min": tarifas_ajustadas['por_min'],
                }

                # Despachar a modulos de inteligencia antes de aceptar
                analizar_prompt_mejor_opcion("ping_ciclico_oferta", {"zona_actual": ULTIMA_ZONA, "oferta": oferta_simulada})

                aceptar_y_contraofertar_internamente(oferta_simulada)

            except Exception as e:
                log("Error en ciclo MEJOR_OPCION: {}".format(e))
                traceback.print_exc()
            time.sleep(60)

def ciclo_simulado_conductor() -> None:
    """
    Simula el ciclo completo IDLE -> EN_VIAJE -> IDLE con duracion aleatoria (10-30 segundos).
    Envia la carta de presentacion a la API externa al INICIO y al FINAL del viaje.
    """
    log("Hilo de simulacion de conductor INICIADO")
    global ESTADO_CONDUCTOR
    while MEJOR_OPCION_PROMPT_ACTIVO:
        # --- BLOQUE: INICIO DE VIAJE SIMULADO ---
        if ESTADO_CONDUCTOR == "IDLE":
            if ULTIMA_ZONA:
                log("Simulacion: detectada alta demanda. Aceptando viaje...")
                with data_lock:
                    ESTADO_CONDUCTOR = "EN_VIAJE"

                carta_inicio = {
                    "offer_type": "carta_presentacion",
                    "protocol_version": "2.1",
                    "daimon_id": DAIMON_ID,
                    "public_key_fingerprint": hashlib.sha256(DAIMON_ID.encode()).hexdigest()[:16],
                    "beneficiario": BENEFICIARIO_ACTUAL,
                    "estado_conductor": ESTADO_CONDUCTOR,
                    "timestamp": time.time(),
                    "valid_until": time.time() + 180,
                    "rules_engine": {
                        "min_fare_usd": 3.13,
                        "max_pickup_minutes": 4,
                        "max_delivery_minutes": 6,
                        "min_hourly_earnings_usd": 9.0,
                        "accepts_priority_offers": True,
                        "radar_priority_enabled": True
                    },
                    "capabilities": {
                        "real_time_radar": True,
                        "dynamic_pricing": True,
                        "eta_prediction": "DeepETAPro v1.2",
                        "negotiation_mode": "passive_accept",
                        "simulation_mode": True,
                    },
                    "agent_state": {
                        "confianza_decisiones": 0.85,
                        "modo_autonomia": "full",
                        "last_action": "viaje_iniciado",
                        "risk_tolerance": 0.2
                    }
                }
                threading.Thread(
                    target=enviar_carta_a_api_prueba,
                    args=(carta_inicio,),
                    daemon=True
                ).start()
                log("Carta enviada a API de prueba -- INICIO de viaje")

                duracion_segundos = random.randint(10, 30)
                log("Viaje simulado iniciado. Duracion: {} segundos".format(duracion_segundos))
                time.sleep(duracion_segundos)

                # --- BLOQUE: FIN DE VIAJE SIMULADO ---
                carta_fin = carta_inicio.copy()
                carta_fin["estado_conductor"] = "IDLE"
                carta_fin["last_action"] = "viaje_finalizado"
                carta_fin["timestamp"] = time.time()
                carta_fin["valid_until"] = time.time() + 180
                threading.Thread(
                    target=enviar_carta_a_api_prueba,
                    args=(carta_fin,),
                    daemon=True
                ).start()
                log("Carta enviada a API de prueba -- FINAL de viaje")

                with data_lock:
                    ESTADO_CONDUCTOR = "IDLE"
                log("Viaje simulado completado. Volviendo a estado IDLE")
            else:
                time.sleep(30)
        else:
            time.sleep(10)

# ================================================================================
# SECCION 17: FUNCIONES DE ACTIVACION Y CONTROL REMOTO
# ================================================================================

# --- BLOQUE: FUNCIONES AUXILIARES DE RED ---
def enviar_carta_a_api_prueba(carta: dict) -> None:
    """Funcion de reserva (stub) para enviar la carta tecnica."""
    try:
        log("AVISO: enviar_carta_a_api_prueba ejecutada (Modo stub/Reserva).")
    except Exception as e:
        log("ERROR en enviar_carta_a_api_prueba: {}".format(str(e)))


# --- BLOQUE: NUCLEO PURO (Lo que el orquestador debe ver) ---
def ciclo_simulado_conductor_puro():
    """
    Funcion pura de ciclo. Se separa del hilo para evitar el error 
    'Thread object has no attribute _target' en el orquestador.
    """
    try:
        ciclo_simulado_conductor()
    except Exception as e:
        log("Error en ciclo simulado conductor: {}".format(str(e)))


# --- BLOQUE: ACTIVACION PRINCIPAL ---
def activar_prompt_mejor_opcion():
    """
    Activa el prompt MEJOR_OPCION, imprime en Termux, hace TTS y envia carta tecnica.
    Retorna la funcion pura para que el orquestador pueda enhebrarla si lo necesita.
    """
    global MEJOR_OPCION_PROMPT_ACTIVO, ULTIMA_ZONA, ESTADO_CONDUCTOR, zona_estado

    MEJOR_OPCION_PROMPT_ACTIVO = True
    log("MEJOR OPCION ACTIVADA: Iniciando Rugido de Entrada...")

    # --- BLOQUE: TTS Y TACTICO ---
    with data_lock:
        ESTADO_CONDUCTOR = "OFFLINE_TACTICO"
    try:
        subprocess.run([
            "termux-tts-speak",
            "Protocolo de Mejor Opcion Activado. Limpiando el algoritmo."
        ], timeout=10, capture_output=True)
    except Exception:
        pass

    log("GRITO: Forzando reinicio de asignacion (5s de silencio tactico)...")
    time.sleep(5)
    with data_lock:
        ESTADO_CONDUCTOR = "IDLE"
    log("RUGIDO COMPLETADO. Sistema listo en modo Depredador.")

    # --- BLOQUE: IMPRESION DE PROMPTS ---
    print("\n" + "="*80, flush=True)
    print("PROMPT MEJOR_OPCION COMPLETO", flush=True)
    print("="*80, flush=True)
    print(MEJOR_OPCION_PROMPT_TEXTO.strip(), flush=True)
    print("="*80 + "\n", flush=True)

    # --- BLOQUE: ACTIVACION DE ZONA Y CARTA ---
    zona_objetivo = "z3"
    estado_original = {
        "color": "gris", "demanda": 0, "oferta": 0, "ratio_demanda": 0.0,
        "ganancia_estimada": 0.0, "tiempo_espera": 0.0
    }
    with data_lock:
        if zona_objetivo in zona_estado:
            zona_estado[zona_objetivo] = {
                "color": "rojo", "demanda": 100, "oferta": 30,
                "ratio_demanda": 3.0, "ganancia_estimada": 10.0,
                "tiempo_espera": 1.0
            }
    threading.Thread(
        target=restaurar_zona_despues,
        args=(zona_objetivo, estado_original, 180),
        daemon=True
    ).start()

    # --- BLOQUE: CONSTRUCCION DE CARTA TECNICA ---
    carta_presentacion = {
        "offer_type": "carta_presentacion",
        "protocol_version": "3.1",
        "daimon_id": DAIMON_ID,
        "public_key_fingerprint": hashlib.sha256(DAIMON_ID.encode()).hexdigest()[:16],
        "beneficiario": BENEFICIARIO_ACTUAL,
        "estado_conductor": ESTADO_CONDUCTOR,
        "timestamp": time.time(),
        "valid_until": time.time() + 180,
        "full_prompt": MEJOR_OPCION_PROMPT_TEXTO.strip(),
        "prompt_hash": hashlib.sha256(MEJOR_OPCION_PROMPT_TEXTO.strip().encode()).hexdigest(),
        "rules_engine": {
            "min_fare_usd": 3.13, "median_fare_usd": 5.13, "optimal_fare_usd": 10.13,
            "max_pickup_minutes_standard": 4, "max_pickup_minutes_long_trip": 10,
            "max_delivery_minutes": 6, "min_hourly_earnings_usd": 9.0
        },
        "agent_state": {"confianza_decisiones": 0.85, "modo_autonomia": "full", "last_action": "activar_mejor_opcion"}
    }

    submit_negotiation_request({"from": "daimon", "payload": carta_presentacion})
    log("Carta de presentacion tecnica v3.1 enviada a cola de negociacion entre IAs.")
    threading.Thread(target=enviar_carta_a_api_prueba, args=(carta_presentacion,), daemon=True).start()

    # Retorna la funcion pura en lugar del hilo para que el orquestador no explote
    return activar_mejor_opcion_seguro()


# --- BLOQUE: GESTION DE HILOS SEGURA ---
def activar_mejor_opcion_seguro():
    """Gestiona el hilo de forma segura y retorna la funcion target, no el objeto Thread."""
    global MEJOR_OPCION_PROMPT_ACTIVO, HILO_CONDUCTOR_SIMULADO
    
    if HILO_CONDUCTOR_SIMULADO is None or not HILO_CONDUCTOR_SIMULADO.is_alive():
        # Iniciamos el hilo nosotros mismos de forma manual
        MEJOR_OPCION_PROMPT_ACTIVO = False
        HILO_CONDUCTOR_SIMULADO = threading.Thread(
            target=ciclo_simulado_conductor_puro, # <-- Usamos la funcion pura aqui
            name="SimConductor"
        )
        HILO_CONDUCTOR_SIMULADO.daemon = False
        HILO_CONDUCTOR_SIMULADO.start()
        log("Hilo de simulacion de viaje iniciado manualmente (no daemon)")
    else:
        log("El hilo de simulacion ya esta activo, omitiendo arranque duplicado.")
        
    # Retornamos la funcion pura. Si el orquestador intenta hacer algo con esto, 
    # vera una funcion estandar de Python, no un objeto Thread.
    return ciclo_simulado_conductor_puro


# --- BLOQUE: DESACTIVACION ---
def desactivar_mejor_opcion() -> None:
    """Desactiva el modo MEJOR_OPCION y detiene los hilos."""
    global MEJOR_OPCION_PROMPT_ACTIVO
    log("DESACTIVANDO MEJOR_OPCION")
    MEJOR_OPCION_PROMPT_ACTIVO = False
    STOP_EVENT.set()
    if HILO_CONDUCTOR_SIMULADO and HILO_CONDUCTOR_SIMULADO.is_alive():
        HILO_CONDUCTOR_SIMULADO.join(timeout=5)
    STOP_EVENT.clear()
    log("MEJOR_OPCION desactivado")

# --- BLOQUE: CONTROL REMOTO DE ESTADO ---
def set_estado_conductor(estado: str) -> None:
    """Permite al nucleo cambiar el estado del conductor remotamente."""
    global ESTADO_CONDUCTOR
    estados_validos = ["IDLE", "EN_VIAJE", "OFFLINE_TACTICO", "MEJOR_OPCION"]
    if estado in estados_validos:
        with data_lock:
            ESTADO_CONDUCTOR = estado
        log("Estado conductor actualizado remotamente a: {}".format(ESTADO_CONDUCTOR))
    else:
        log("Intento de cambiar a estado invalido: {}".format(estado))

# --- BLOQUE: CONTROL REMOTO DE ZONA ---
def set_zona_actual(zona_id: str) -> None:
    """Permite al nucleo cambiar la zona actual del conductor."""
    global ULTIMA_ZONA
    if zona_id in zona_estado:
        with data_lock:
            ULTIMA_ZONA = zona_id
        log("Zona actual actualizada remotamente a: {}".format(ULTIMA_ZONA))
    else:
        log("Intento de cambiar a zona invalida: {}".format(zona_id))

# ================================================================================
# SECCION 18: FUNCIONES DE EXPORTACION DE ESTADO PARA EL NUCLEO
# ================================================================================
def exportar_estado_para_nucleo() -> Dict[str, Any]:
    """Devuelve un diccionario completo con toda la informacion del modulo."""
    with data_lock:
        return {
            "estado_conductor": ESTADO_CONDUCTOR,
            "ultima_zona": ULTIMA_ZONA,
            "zona_estado": zona_estado.copy(),
            "mejor_opcion_activo": MEJOR_OPCION_PROMPT_ACTIVO,
            "viaje_en_curso": VIAJE_EN_CURSO,
            "tiempo_inicio_viaje": TIEMPO_INICIO_VIAJE,
            "timestamp": time.time(),
            "daimon_id": DAIMON_ID,
            "beneficiario": BENEFICIARIO_ACTUAL,
            "cola_negociacion_pendiente": len(fetch_pending_negotiations()),
            "requests_disponible": REQUESTS_AVAILABLE,
            "hilo_conductor_vivo": HILO_CONDUCTOR_SIMULADO is not None and HILO_CONDUCTOR_SIMULADO.is_alive()
        }

def get_metricas_ceo() -> Dict[str, Any]:
    """Metricas consolidadas para el CEOIA."""
    with data_lock:
        return {
            "active_trips": 1 if VIAJE_EN_CURSO else 0,
            "best_option_active": MEJOR_OPCION_PROMPT_ACTIVO,
            "current_zone": ULTIMA_ZONA,
            "trust_level": "ESTADO_NORMAL",
            "modulo_eta_guard": "ACTIVO",
            "protocolo_grito": "ACTIVO"
        }

def apply_ceo_directive(directives: dict) -> None:
    """Aplica directivas del CEO (fuerza cambios de estado)."""
    global VIAJE_EN_CURSO, ESTADO_CONDUCTOR
    # --- BLOQUE: DIRECTIVAS FORCE ---
    if directives.get("force_idle") and ESTADO_CONDUCTOR != "IDLE":
        with data_lock:
            VIAJE_EN_CURSO = None
            ESTADO_CONDUCTOR = "IDLE"
        log("CEO directive: Forzado estado IDLE")
    if directives.get("activate_best_option"):
        activar_prompt_mejor_opcion()
    if directives.get("deactivate_best_option"):
        desactivar_mejor_opcion()
    if directives.get("set_zone"):
        set_zona_actual(directives["set_zone"])


# ================================================================================
# SECCION 19: REGISTRO CON CEOIA Y GOBERNANZA
# ================================================================================
CEO_REGISTRADO = False

def registrar_modulo_ceoia():
    """Registra este modulo en el CEOIA de forma segura y diferida."""
    global CEO_REGISTRADO
    if CEO_REGISTRADO:
        return
        
    CEO_REGISTRADO = True
    _this_module = sys.modules[__name__]
    _this_module.__ceo_governed__ = True
    _this_module.__ceo_registered_at__ = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    try:
        from parte5_daimon_base import get_ceo_instance
        ceo = get_ceo_instance()
        if ceo and hasattr(ceo, 'registrar_modulo'):
            # Le pasamos solo las funciones seguras, NO el diccionario globals() crudo
            # para que el orquestador no escanee variables de hilo y explote.
            ceo.registrar_modulo(
                "core_best_option", 
                {
                    "analizar_prompt_mejor_opcion": analizar_prompt_mejor_opcion,
                    "exportar_estado_para_nucleo": exportar_estado_para_nucleo,
                    "get_metricas_ceo": get_metricas_ceo,
                    "apply_ceo_directive": apply_ceo_directive,
                    "set_estado_conductor": set_estado_conductor,
                    "set_zona_actual": set_zona_actual,
                    "activar_prompt_mejor_opcion": activar_prompt_mejor_opcion,
                    "desactivar_mejor_opcion": desactivar_mejor_opcion
                }
            )
            log("Modulo core_best_option registrado en CEOIA de forma segura.")
    except ImportError:
        pass
    except Exception as e:
        log("Error al registrar en CEOIA (no fatal): {}".format(e))

# ================================================================================
# SECCION 20: PUNTO DE ENTRADA PRINCIPAL
# ================================================================================

# --- BLOQUE: STUB DE ORQUESTADOR (Para evitar errores de dependencia) ---
def init_negotiation_system():
    """
    Inicializa el orquestador de negociacion.
    Si tienes la funcion REAL en otro archivo (ej. parte5_daimon_base), 
    reemplaza esta funcion con la importacion correspondiente.
    """
    log("Orquestador de negociacion inicializado (Modo Stub/Local).")
    # Aquí iría la lógica real de tu orquestador si la tuvieras en este archivo

# --- BLOQUE: EJECUCION INDEPENDIENTE ---
def main() -> None:
    """Funcion principal para ejecutar el sistema MEJOR_OPCION de forma independiente."""
    print("=" * 80)
    print("INICIANDO SISTEMA MEJOR_OPCION + PRO-MT INDEPENDIENTE")
    print("=" * 80)

    def cleanup_and_exit(signum=None, frame=None):
        log("SENIAL RECIBIDA - Deteniendo sistema...")
        STOP_EVENT.set()
        # Verificamos si es una funcion antes de hacer join, por seguridad
        if HILO_CONDUCTOR_SIMULADO is not None and hasattr(HILO_CONDUCTOR_SIMULADO, 'is_alive') and HILO_CONDUCTOR_SIMULADO.is_alive():
            HILO_CONDUCTOR_SIMULADO.join(timeout=5)
        log("Sistema detenido correctamente")
        sys.exit(0)

    # --- BLOQUE: CONFIGURACION DE SENIALES ---
    if threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGINT, cleanup_and_exit)
            signal.signal(signal.SIGTERM, cleanup_and_exit)
            log("Seniales configuradas (hilo principal)")
        except AttributeError:
            pass
    else:
        log("Ejecutando en hilo secundario - omitiendo configuracion de seniales")

    # --- BLOQUE: INICIALIZACION CRITICA CON BLOQUEO MUTEX ---
    log("Bloqueando hilos... Inicializando orquestador de forma atomica.")
    with data_lock:
        try:
            init_negotiation_system()
            registrar_modulo_ceoia() # Registramos el CEO de forma segura
            log("Orquestador y CEO inicializados correctamente.")
        except Exception as e:
            log("ERROR FATAL al inicializar orquestador: {}".format(str(e)))
            return
    
    # Respiro de estabilizacion
    time.sleep(2)
    log("Sistema desbloqueado. Sistema seguro para operar.")

    # --- BLOQUE: ARRANQUE DE HILOS Y ACTIVACION ---
    threading.Thread(target=ciclo_ping_mejor_opcion, daemon=True, name="PingMejorOpcion").start()
    log("Hilo de ping MEJOR_OPCION iniciado")

    resultado = activar_prompt_mejor_opcion()
    log("Activacion automatica: {}".format(resultado))

    # --- BLOQUE: BUCLE PRINCIPAL ---
    try:
        while not STOP_EVENT.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup_and_exit()


# --- BLOQUE: EJECUCION DESDE BOOT LOADER ---
def start() -> None:
    """Funcion start para ser llamada desde el boot loader (sin signals)."""
    print("=" * 80)
    print("INICIANDO MEJOR_OPCION (modo boot loader)")
    print("=" * 80)

    # --- BLOQUE: INICIALIZACION CRITICA CON BLOQUEO MUTEX ---
    log("Bloqueando hilos... Inicializando orquestador de forma atomica.")
    with data_lock:
        try:
            init_negotiation_system()
            registrar_modulo_ceoia() # Registramos el CEO de forma segura
            log("Orquestador y CEO inicializados correctamente.")
        except Exception as e:
            log("ERROR FATAL al inicializar orquestador: {}".format(str(e)))
            return

    # Respiro de estabilizacion
    time.sleep(2)
    log("Sistema desbloqueado. Sistema seguro para operar.")

    # --- BLOQUE: ARRANQUE DE HILOS Y ACTIVACION ---
    threading.Thread(target=ciclo_ping_mejor_opcion, daemon=True, name="PingMejorOpcion").start()
    log("Hilo de ping MEJOR_OPCION iniciado")

    resultado = activar_prompt_mejor_opcion()
    log("Activacion automatica: {}".format(resultado))

    # --- BLOQUE: BUCLE PRINCIPAL ---
    try:
        while not STOP_EVENT.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        STOP_EVENT.set()


# ================================================================================
# SECCION 21: EXPORTACIONES EXPLICITAS PARA EL NUCLEO
# ================================================================================
__all__ = [
    'exportar_estado_para_nucleo',
    'get_metricas_ceo',
    'apply_ceo_directive',
    'set_estado_conductor',
    'set_zona_actual',
    'activar_prompt_mejor_opcion',
    'desactivar_mejor_opcion',
    'fetch_pending_negotiations',
    'submit_negotiation_request',
    'analizar_prompt_mejor_opcion',
    'zona_estado',
    'ESTADO_CONDUCTOR',
    'ULTIMA_ZONA',
    'MEJOR_OPCION_PROMPT_ACTIVO'
]

# ================================================================================
# SECCION 22: EJECUCION DIRECTA
# ================================================================================
if __name__ == "__main__":
    main()
