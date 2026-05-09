#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PARTE 2/9 - SISTEMA DE NEGOCIACION AI (CORREGIDO + REPUTACION AVANZADA)
Agentes + Reputacion Multi-dimensional + Teoria de Juegos + Anti-Fraude
Compatible con Termux/Android - Python 3.6+
"""

from __future__ import annotations
import os
import sys
import json
import time
import uuid
import random
import copy
import math
import threading
import hashlib
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from collections import deque, defaultdict
from abc import ABC, abstractmethod

# ================================================================================
# SECCION 1: IMPORTACIONES Y CONFIGURACION FALLBACK (CORREGIDO)
# ================================================================================

# --- BLOQUE: FUNCION DE ANALISIS DE PROMPT ---
def analizar_prompt_mejor_opcion(prompt, contexto):
    """Procesa el prompt con el modulo de negociacion integrado."""
    orch = get_orchestrator()
    if not orch:
        return {
            "exito": False,
            "error": "orquestador no inicializado",
            "timestamp_procesamiento": time.time()
        }
    agents_available = len(orch.agents)
    strategies = set()
    for agent in orch.agents.values():
        if isinstance(agent, StrategicAgent):
            strategies.add(agent.strategy.name)
    avg_rep = 0.0
    if orch.agents:
        avg_rep = sum(
            orch.reputation_system.get_reputation(a)
            for a in orch.agents
        ) / max(len(orch.agents), 1)
    recommended = "colaborativa"
    if avg_rep < 0.4:
        recommended = "competitiva"
    elif avg_rep > 0.7:
        recommended = "colaborativa"
    elif strategies:
        recommended = "moderada"
    return {
        "exito": True,
        "estrategia_recomendada": recommended,
        "umbral_aceptacion": 0.75,
        "agentes_disponibles": agents_available,
        "estrategias_activas": list(strategies),
        "reputacion_promedio": round(avg_rep, 3),
        "timestamp_procesamiento": time.time()
    }

# --- BLOQUE: IMPORTACION DESDE PART1 ---
# Flag para saber si usamos clases importadas o fallback
_USING_IMPORTED_CLASSES = False

try:
    from part1_config import (
        GlobalConfig, log_event, log_banner,
        NegotiationStatus, AgentRole, UtilityProfile,
        Offer, NegotiationMessage, NegotiationSession,
        GeoLocation, PriceEstimate, TimeEstimate, RadarOpportunity
    )
    _USING_IMPORTED_CLASSES = True
    # VERIFICAR que UtilityProfile tenga calculate_advanced_utility
    if not hasattr(UtilityProfile, 'calculate_advanced_utility'):
        raise ImportError("UtilityProfile importado no tiene calculate_advanced_utility")
except ImportError as e:
    print("[WARN] No se pudo importar symbiosis_parte1: {}".format(e))
    print("[WARN] Usando fallback interno...")
    _USING_IMPORTED_CLASSES = False

    # --- BLOQUE: FALLBACK GLOBALCONFIG ---
    class GlobalConfig:
        IS_TERMUX = True
        RL_LEARNING_RATE = 0.1
        RL_DISCOUNT_FACTOR = 0.9
        RL_EXPLORATION_EPSILON = 0.1
        MAX_CONCURRENT_NEGOTIATIONS = 5
        MAX_ROUNDS = 10
        REPUTATION_DECAY = 0.99
        LOG_VERBOSE = True
        SESSION_TIMEOUT_SECONDS = 300

    def log_event(msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print("[{}][{}] {}".format(timestamp, level, msg))

    def log_banner(msg, emoji=""):
        print("=" * 60)
        print("{} {}".format(emoji, msg))
        print("=" * 60)

    # --- BLOQUE: FALLBACK ENUMS ---
    class NegotiationStatus(Enum):
        PENDING = auto()
        ACTIVE = auto()
        ACCEPTED = auto()
        REJECTED = auto()
        EXPIRED = auto()
        DISPUTED = auto()
        ENFORCED = auto()

    class AgentRole(Enum):
        INITIATOR = auto()
        RESPONDER = auto()
        ARBITER = auto()
        WITNESS = auto()

    # --- BLOQUE: FALLBACK UTILITYPROFILE (CORREGIDO - CON METODO COMPLETO) ---
    class UtilityProfile:
        def __init__(self, **kwargs):
            self.price_weight = kwargs.get('price_weight', 0.5)
            self.time_weight = kwargs.get('time_weight', 0.2)
            self.quality_weight = kwargs.get('quality_weight', 0.2)
            self.reputation_weight = kwargs.get('reputation_weight', 0.05)
            self.flexibility_weight = kwargs.get('flexibility_weight', 0.05)
            self.min_acceptable_price = kwargs.get('min_acceptable_price', 50.0)
            self.max_acceptable_price = kwargs.get('max_acceptable_price', 150.0)
            self.required_quality_level = kwargs.get('required_quality_level', 3)

        def calculate_utility(self, offer):
            """Calculo basico de utilidad."""
            price_range = self.max_acceptable_price - self.min_acceptable_price
            if price_range <= 0:
                return 0.5
            price_score = 1.0 - (offer.price - self.min_acceptable_price) / price_range
            return max(0.0, min(1.0, price_score * self.price_weight + 0.3))

        def calculate_advanced_utility(self, offer_data, reputation_score=0.5):
            """
            Calculo avanzado de utilidad con multiples dimensiones.
            METODO CRITICO - usado por StrategicAgent.
            """
            price = float(offer_data.get('price', 0))
            delivery_time = float(offer_data.get('delivery_time', 0))
            quality = int(offer_data.get('quality_level', 3))
            rep = float(offer_data.get('counterparty_reputation', reputation_score))
            flexibility = float(offer_data.get('flexibility_score', 0.5))
            
            pw = self.price_weight
            tw = self.time_weight
            qw = self.quality_weight
            rw = self.reputation_weight
            fw = self.flexibility_weight
            
            # Normalizar pesos
            total_weight = pw + tw + qw + rw + fw
            if total_weight > 0:
                pw, tw, qw, rw, fw = pw/total_weight, tw/total_weight, qw/total_weight, rw/total_weight, fw/total_weight
            
            # Calcular utilidad por componente
            price_range = self.max_acceptable_price - self.min_acceptable_price
            if price_range > 0:
                price_util = max(0.0, min(1.0,
                    1.0 - (price - self.min_acceptable_price) / price_range))
            else:
                price_util = 0.5
            
            time_util = max(0.0, min(1.0, 1.0 - (delivery_time / 60)))
            quality_util = quality / 5.0
            rep_util = max(0.0, min(1.0, rep))
            flex_util = max(0.0, min(1.0, flexibility))
            
            # Combinar
            total = (pw * price_util + 
                     tw * time_util + 
                     qw * quality_util +
                     rw * rep_util + 
                     fw * flex_util)
            
            if math.isnan(total) or math.isinf(total):
                return 0.0
            return max(0.0, min(1.0, total))

    # --- BLOQUE: FALLBACK OFFER (CORREGIDO - PARAMETROS OPCIONALES ANADIDOS) ---
    class Offer:
        def __init__(self, price=0.0, delivery_time=24.0,
                     quality_level=3, proposed_by="",
                     rationale="", concessions_made=None,
                     proposed_at=None):
            self.price = price
            self.delivery_time = delivery_time
            self.quality_level = quality_level
            self.proposed_by = proposed_by
            self.rationale = rationale
            # Usar None como default para evitar mutable default argument bug
            self.concessions_made = concessions_made if concessions_made is not None else []
            self.proposed_at = proposed_at

        def clone_with_changes(self, **kwargs):
            data = {
                'price': self.price,
                'delivery_time': self.delivery_time,
                'quality_level': self.quality_level,
                'proposed_by': self.proposed_by,
                'rationale': self.rationale,
                'concessions_made': list(self.concessions_made),
                'proposed_at': self.proposed_at
            }
            data.update(kwargs)
            return Offer(**data)

    # --- BLOQUE: FALLBACK NEGOTIATIONMESSAGE ---
    class NegotiationMessage:
        def __init__(self, **kwargs):
            self.negotiation_id = kwargs.get('negotiation_id', '')
            self.round_number = kwargs.get('round_number', 0)
            self.sender_id = kwargs.get('sender_id', '')
            self.receiver_id = kwargs.get('receiver_id', '')
            self.message_type = kwargs.get('message_type', 'INFO')
            self.structured_content = kwargs.get('structured_content', None)
            self.timestamp = kwargs.get('timestamp', datetime.now(timezone.utc))

    # --- BLOQUE: FALLBACK NEGOTIATIONSESSION ---
    class NegotiationSession:
        def __init__(self, agent_a_id="", agent_b_id="",
                     domain="", item_description="",
                     base_terms=None,
                     status=None,
                     max_rounds=10):
            if status is None:
                status = NegotiationStatus.PENDING
            self.session_id = str(uuid.uuid4())
            self.agent_a_id = agent_a_id
            self.agent_b_id = agent_b_id
            self.domain = domain
            self.item_description = item_description
            self.base_terms = base_terms or {}
            self.status = status
            self.max_rounds = max_rounds
            self.current_round = 0
            self.offers_history = []
            self.messages = []
            self.final_offer = None
            self.final_utility_a = 0.0
            self.final_utility_b = 0.0
            self.agreement_timestamp = None
            self.created_at = datetime.now(timezone.utc)
            self.timeout_seconds = 300

        def get_last_offer(self):
            return self.offers_history[-1] if self.offers_history else None

        def is_expired(self):
            if self.created_at:
                elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
                return elapsed > self.timeout_seconds
            return False

    class GeoLocation:
        pass

    class PriceEstimate:
        pass

    class TimeEstimate:
        pass

    class RadarOpportunity:
        pass


# --- BLOQUE: PATCH PARA CLASES IMPORTADAS SIN calculate_advanced_utility ---
if _USING_IMPORTED_CLASSES:
    # Si la clase importada no tiene el metodo, agregarlo dinamicamente
    if not hasattr(UtilityProfile, 'calculate_advanced_utility'):
        def _patch_calculate_advanced_utility(self, offer_data, reputation_score=0.5):
            """Patch para UtilityProfile importado sin calculate_advanced_utility."""
            price = float(offer_data.get('price', 0))
            delivery_time = float(offer_data.get('delivery_time', 0))
            quality = int(offer_data.get('quality_level', 3))
            rep = float(offer_data.get('counterparty_reputation', reputation_score))
            flexibility = float(offer_data.get('flexibility_score', 0.5))
            
            pw = getattr(self, 'price_weight', 0.5)
            tw = getattr(self, 'time_weight', 0.2)
            qw = getattr(self, 'quality_weight', 0.2)
            rw = getattr(self, 'reputation_weight', 0.05)
            fw = getattr(self, 'flexibility_weight', 0.05)
            
            price_range = (getattr(self, 'max_acceptable_price', 150.0) - 
                          getattr(self, 'min_acceptable_price', 50.0))
            if price_range > 0:
                price_util = max(0.0, min(1.0,
                    1.0 - (price - getattr(self, 'min_acceptable_price', 50.0)) / price_range))
            else:
                price_util = 0.5
            
            time_util = max(0.0, min(1.0, 1.0 - (delivery_time / 60)))
            quality_util = quality / 5.0
            rep_util = max(0.0, min(1.0, rep))
            flex_util = max(0.0, min(1.0, flexibility))
            
            total = (pw * price_util + tw * time_util + qw * quality_util +
                     rw * rep_util + fw * flex_util)
            
            if math.isnan(total) or math.isinf(total):
                return 0.0
            return max(0.0, min(1.0, total))
        
        # Aplicar patch
        UtilityProfile.calculate_advanced_utility = _patch_calculate_advanced_utility
        print("[WARN] UtilityProfile importado parcheado con calculate_advanced_utility")

    # --- BLOQUE: PATCH PARA OFFER IMPORTADO SIN concessions_made/proposed_at ---
    if not hasattr(Offer.__init__, '_patched_for_concessions'):
        _orig_offer_init = Offer.__init__
        
        def _patched_offer_init(self, price=0.0, delivery_time=24.0,
                                quality_level=3, proposed_by="",
                                rationale="", concessions_made=None,
                                proposed_at=None, **kwargs):
            # Llamar al init original con args que soporta
            try:
                _orig_offer_init(self, price=price, delivery_time=delivery_time,
                                quality_level=quality_level, proposed_by=proposed_by,
                                rationale=rationale)
            except TypeError as e:
                # Si original ya acepta estos params, pasar todo
                if 'concessions_made' not in str(e) and 'proposed_at' not in str(e):
                    raise
                _orig_offer_init(self, price=price, delivery_time=delivery_time,
                                quality_level=quality_level, proposed_by=proposed_by,
                                rationale=rationale, **kwargs)
                # Si original acepta kwargs, ya seteo todo
                if hasattr(self, 'concessions_made') and hasattr(self, 'proposed_at'):
                    return
            
            # Agregar atributos faltantes si no existen
            if not hasattr(self, 'concessions_made'):
                self.concessions_made = concessions_made if concessions_made is not None else []
            if not hasattr(self, 'proposed_at'):
                self.proposed_at = proposed_at
        
        _patched_offer_init._patched_for_concessions = True
        Offer.__init__ = _patched_offer_init
        print("[WARN] Offer importado parcheado con concessions_made/proposed_at")
        
        # Tambien parchear clone_with_changes si no existe o es incompatible
        if not hasattr(Offer, 'clone_with_changes'):
            def _patched_clone_with_changes(self, **kwargs):
                data = {
                    'price': self.price,
                    'delivery_time': self.delivery_time,
                    'quality_level': self.quality_level,
                    'proposed_by': self.proposed_by,
                    'rationale': self.rationale,
                    'concessions_made': list(getattr(self, 'concessions_made', [])),
                    'proposed_at': getattr(self, 'proposed_at', None)
                }
                data.update(kwargs)
                return Offer(**data)
            
            Offer.clone_with_changes = _patched_clone_with_changes
            print("[WARN] Offer importado parcheado con clone_with_changes")


# --- BLOQUE: EXPORTS PUBLICOS ---
__all__ = [
    'analizar_prompt_mejor_opcion',
    'NegotiationOrchestrator', 'NegotiationAgent', 'StrategicAgent',
    'RuleBasedAgent', 'LightweightAgent', 'LLMBasedAgent', 'RLBasedAgent',
    'ReputationSystem', 'ReputationGovernor', 'TrustScoreCalculator',
    'FraudDetector', 'VerifiableCredential', 'BadgeSystem',
    'get_orchestrator', 'create_orchestrator', 'init_negotiation_system',
    'initiate_negotiation', 'get_system_report', 'get_ceo_metrics',
    'apply_ceo_directive', 'register_agent_sync', 'register_agent',
    'NegotiationStrategy', 'ConcessionType', 'TrustLevel',
    'ReputationDimension', 'FeedbackType',
    'AdvancedConcessionEngine', 'OpponentModeler', 'ParetoNashEvaluator',
    'calculate_nash_product', 'calculate_pareto_gain',
    'calculate_bargaining_power',
]

# ================================================================================
# SECCION 2: ALGORITMOS DE REPUTACION AVANZADA
# ================================================================================

# --- BLOQUE: ENUMS DE REPUTACION ---
class ReputationDimension(Enum):
    HONESTY = auto()
    DELIVERY = auto()
    QUALITY = auto()
    COMMUNICATION = auto()
    RESPONSIVENESS = auto()
    PROFESSIONALISM = auto()


class FeedbackType(Enum):
    POSITIVE = 1
    NEUTRAL = 0
    NEGATIVE = -1


class TrustLevel(Enum):
    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4
    ELITE = 5


# --- BLOQUE: DATA CLASSES DE REPUTACION ---
@dataclass
class Review:
    review_id: str
    reviewer_id: str
    reviewee_id: str
    transaction_id: str
    rating: float
    feedback_type: FeedbackType
    dimensions: Dict[str, float]
    comment: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    verified: bool = False
    helpful_count: int = 0


@dataclass
class TrustScore:
    entity_id: str
    overall_score: float = 0.5
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    total_reviews: int = 0
    positive_reviews: int = 0
    negative_reviews: int = 0
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    confidence: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decay_factor: float = 1.0


# --- BLOQUE: TEMPORAL DECAY ---
class TemporalDecay:
    @staticmethod
    def exponential(initial_value: float, time_elapsed_days: float,
                    half_life_days: float = 90.0) -> float:
        if half_life_days <= 0:
            return initial_value
        return initial_value * math.pow(0.5, time_elapsed_days / half_life_days)

    @staticmethod
    def linear(initial_value: float, time_elapsed_days: float,
               max_decay_days: float = 365.0) -> float:
        if max_decay_days <= 0:
            return initial_value
        return initial_value * max(0.0, 1.0 - time_elapsed_days / max_decay_days)

    @staticmethod
    def step_decay(initial_value: float, time_elapsed_days: float,
                   periods: Optional[List[Tuple[float, float]]] = None) -> float:
        if periods is None:
            periods = [(30, 0.9), (90, 0.8), (180, 0.6), (365, 0.4)]
        factor = 1.0
        for days, decay in periods:
            if time_elapsed_days >= days:
                factor = decay
        return initial_value * factor

    @staticmethod
    def recency_bias(reviews: List[Tuple[float, datetime]],
                     current_time: Optional[datetime] = None) -> float:
        if not reviews or current_time is None:
            return 1.0
        weights = []
        for rating, timestamp in reviews:
            days_ago = (current_time - timestamp).total_seconds() / 86400
            if days_ago <= 7:
                w = 1.5
            elif days_ago <= 30:
                w = 1.3
            elif days_ago <= 90:
                w = 1.1
            elif days_ago <= 180:
                w = 1.0
            elif days_ago <= 365:
                w = 0.8
            else:
                w = 0.5
            weights.append(w * rating)
        return sum(weights) / len(weights) if weights else 1.0


# --- BLOQUE: FEEDBACK AGGREGATOR ---
class FeedbackAggregator:
    @staticmethod
    def simple_average(ratings: List[float]) -> float:
        return sum(ratings) / len(ratings) if ratings else 0.0

    @staticmethod
    def weighted_average(ratings: List[float], weights: List[float]) -> float:
        if not ratings or not weights or len(ratings) != len(weights):
            return 0.0
        total_weight = sum(weights)
        if total_weight <= 0:
            return 0.0
        return sum(r * w for r, w in zip(ratings, weights)) / total_weight

    @staticmethod
    def bayesian_average(ratings: List[float], prior_mean: float = 3.0,
                         prior_count: int = 10) -> float:
        if not ratings:
            return prior_mean
        return (prior_count * prior_mean + sum(ratings)) / (prior_count + len(ratings))

    @staticmethod
    def trimmed_mean(ratings: List[float], trim_percent: float = 10.0) -> float:
        if len(ratings) < 4:
            return sum(ratings) / len(ratings) if ratings else 0.0
        sorted_r = sorted(ratings)
        trim = max(1, min(int(len(ratings) * trim_percent / 100), len(ratings) // 4))
        trimmed = sorted_r[trim:-trim] if trim > 0 else sorted_r
        return sum(trimmed) / len(trimmed) if trimmed else 0.0


# --- BLOQUE: FRAUD DETECTOR ---
class FraudDetector:
    def __init__(self) -> None:
        self.suspicious_entities: Set[str] = set()

    # --- BLOQUE: DETECCION SYBIL ---
    def detect_sybil_attack(self, reviewer_id: str, reviews: List[Review],
                            entity_reviews: Dict[str, List[Review]]) -> float:
        suspicion = 0.0
        reviewer_reviews = [r for r in reviews if r.reviewer_id == reviewer_id]
        if not reviewer_reviews:
            return 0.0
        # Volumen excesivo
        if len(reviewer_reviews) > 50:
            suspicion += 0.2
        ratings = [r.rating for r in reviewer_reviews]
        # Varianza extremadamente baja
        if len(ratings) >= 3:
            avg = sum(ratings) / len(ratings)
            variance = sum((r - avg) ** 2 for r in ratings) / len(ratings)
            if variance < 0.1:
                suspicion += 0.3
        # Timestamps demasiado cercanos
        timestamps = sorted([r.timestamp for r in reviewer_reviews])
        if len(timestamps) >= 2:
            diffs = [
                (timestamps[i + 1] - timestamps[i]).total_seconds() / 3600
                for i in range(len(timestamps) - 1)
            ]
            rapid_count = sum(1 for d in diffs if d < 0.5)
            if rapid_count / len(diffs) > 0.7:
                suspicion += 0.25
        # Rating extremo
        avg_rating = sum(ratings) / len(ratings) if ratings else 3.0
        if avg_rating > 4.8 or avg_rating < 1.5:
            suspicion += 0.15
        # Comentarios cortos
        short_ratio = sum(1 for r in reviewer_reviews if len(r.comment) < 10)
        if short_ratio / len(reviewer_reviews) > 0.5:
            suspicion += 0.1
        return min(1.0, suspicion)

    # --- BLOQUE: DETECCION COLUSION ---
    def detect_collusion(self, entity_a: str, entity_b: str,
                         reviews: List[Review]) -> float:
        suspicion = 0.0
        ab_reviews = [
            r for r in reviews
            if (r.reviewer_id == entity_a and r.reviewee_id == entity_b)
            or (r.reviewer_id == entity_b and r.reviewee_id == entity_a)
        ]
        if len(ab_reviews) < 2:
            return 0.0
        entity_reviews = [
            r for r in reviews
            if entity_a in (r.reviewer_id, r.reviewee_id)
            or entity_b in (r.reviewer_id, r.reviewee_id)
        ]
        # Proporcion cruzada excesiva
        if entity_reviews and len(ab_reviews) / len(entity_reviews) > 0.8:
            suspicion += 0.3
        # Rating cruzado vs otros
        avg_ab = sum(r.rating for r in ab_reviews) / len(ab_reviews) if ab_reviews else 3.0
        other = [r for r in entity_reviews if r not in ab_reviews]
        avg_other = sum(r.rating for r in other) / len(other) if other else 3.0
        if avg_ab - avg_other > 1.0:
            suspicion += 0.3
        return min(1.0, suspicion)

    def adjust_rating_for_fraud(self, rating: float, fraud_score: float) -> float:
        """
        CORREGIDO: Penaliza ratings positivos con fraude alto en lugar de suavizarlos.
        Un rating alto con fraude alto se reduce. Un rating bajo con fraude alto
        se suaviza ligeramente hacia el centro (posible sabotaje).
        """
        if fraud_score <= 0.0:
            return max(1.0, min(5.0, rating))
        
        if rating >= 3.0:
            # Rating positivo con fraude: penalizar (reducir)
            adjusted = rating - (rating - 3.0) * fraud_score * 0.5
        else:
            # Rating negativo con fraude: podria ser sabotaje, suavizar hacia neutro
            adjusted = rating + (3.0 - rating) * fraud_score * 0.3
        
        return max(1.0, min(5.0, adjusted))


# --- BLOQUE: TRUST SCORE CALCULATOR ---
class TrustScoreCalculator:
    def __init__(self, half_life_days: float = 90.0,
                 decay_model: str = "exponential") -> None:
        self.half_life_days = half_life_days
        self.decay_model = decay_model
        self.dimensions: Dict[str, float] = {
            "honesty": 0.25, "delivery": 0.25, "quality": 0.2,
            "communication": 0.15, "responsiveness": 0.1, "professionalism": 0.05
        }
        self.fraud_detector = FraudDetector()

    # --- BLOQUE: CALCULO PRINCIPAL ---
    def calculate_trust_score(self, entity_id: str, reviews: List[Review],
                              entity_reviews: Dict[str, List[Review]],
                              all_reviews: List[Review]) -> TrustScore:
        score = TrustScore(entity_id=entity_id)
        if not reviews:
            return score
        now = datetime.now(timezone.utc)
        # --- BLOQUE: DECAY TEMPORAL ---
        decayed: List[Tuple[Review, float]] = []
        for r in reviews:
            days = (now - r.timestamp).total_seconds() / 86400
            if self.decay_model == "exponential":
                weight = TemporalDecay.exponential(1.0, days, self.half_life_days)
            elif self.decay_model == "linear":
                weight = TemporalDecay.linear(1.0, days, self.half_life_days * 4)
            else:
                weight = TemporalDecay.step_decay(1.0, days)
            decayed.append((r, weight))
        # --- BLOQUE: FRAUD SCORES ---
        fraud_scores: List[float] = [
            self.fraud_detector.detect_sybil_attack(
                r.reviewer_id, reviews, entity_reviews
            )
            for r in reviews
        ]
        # --- BLOQUE: SCORES POR DIMENSION ---
        dimension_scores: Dict[str, float] = {}
        for dim, dim_weight in self.dimensions.items():
            dim_vals = [
                (r.dimensions.get(dim, 0.0), w, fraud_scores[i])
                for i, (r, w) in enumerate(decayed)
                if dim in r.dimensions
            ]
            if dim_vals:
                adjusted = [
                    self.fraud_detector.adjust_rating_for_fraud(val / 5.0, fraud)
                    for val, _, fraud in dim_vals
                ]
                weights = [w * (1.0 - fraud) for _, w, fraud in dim_vals]
                total_w = sum(weights)
                if total_w > 0:
                    dimension_scores[dim] = FeedbackAggregator.weighted_average(
                        adjusted, weights
                    )
                else:
                    dimension_scores[dim] = sum(adjusted) / len(adjusted)
        # --- BLOQUE: SCORE GLOBAL ---
        score.dimension_scores = dimension_scores
        score.overall_score = sum(
            self.dimensions.get(d, 0.1) * s for d, s in dimension_scores.items()
        )
        score.total_reviews = len(reviews)
        score.positive_reviews = sum(1 for r in reviews if r.rating >= 4.0)
        score.negative_reviews = sum(1 for r in reviews if r.rating <= 2.0)
        score.trust_level = self._get_trust_level(score.overall_score, len(reviews))
        score.confidence = min(1.0, len(reviews) / 50.0)
        score.decay_factor = (
            sum(w for _, w in decayed) / len(decayed) if decayed else 1.0
        )
        return score

    def _get_trust_level(self, score: float, num_reviews: int) -> TrustLevel:
        if num_reviews < 3:
            return TrustLevel.UNTRUSTED
        if score >= 0.9 and num_reviews >= 50:
            return TrustLevel.ELITE
        if score >= 0.8 and num_reviews >= 20:
            return TrustLevel.VERY_HIGH
        if score >= 0.7:
            return TrustLevel.HIGH
        if score >= 0.5:
            return TrustLevel.MEDIUM
        return TrustLevel.LOW


# --- BLOQUE: VERIFIABLE CREDENTIAL ---
class VerifiableCredential:
    def __init__(self) -> None:
        self.credentials: Dict[str, Dict] = {}
        self.revoked: Set[str] = set()

    def issue(self, holder_id: str, claim_type: str, claim_value: Any,
              issuer_id: str = "system", expiry_days: int = 365) -> str:
        # CORREGIDO: Usar f-string con formato correcto para evitar colisiones
        unique_input = "{}|{}|{}|{}".format(
            holder_id, claim_type, issuer_id, uuid.uuid4()
        )
        cred_id = hashlib.sha256(unique_input.encode()).hexdigest()[:16]
        self.credentials[cred_id] = {
            "id": cred_id,
            "holder": holder_id,
            "type": claim_type,
            "value": claim_value,
            "issuer": issuer_id,
            "expires": (
                datetime.now(timezone.utc) + timedelta(days=expiry_days)
            ).isoformat(),
            "revoked": False
        }
        return cred_id

    def verify(self, cred_id: str) -> Tuple[bool, str]:
        if cred_id not in self.credentials:
            return False, "No encontrada"
        c = self.credentials[cred_id]
        if c["revoked"] or cred_id in self.revoked:
            return False, "Revocada"
        try:
            expires_dt = datetime.fromisoformat(c["expires"])
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_dt:
                return False, "Expirada"
        except (ValueError, TypeError):
            return False, "Fecha invalida"
        return True, "Valida"

    def revoke(self, cred_id: str) -> bool:
        if cred_id in self.credentials:
            self.revoked.add(cred_id)
            self.credentials[cred_id]["revoked"] = True
            return True
        return False


# --- BLOQUE: BADGE SYSTEM ---
class BadgeSystem:
    BADGES = {
        "verified_identity": {"name": "Identidad Verificada", "icon": "V"},
        "top_performer": {"name": "Top Performer", "icon": "T"},
        "quick_responder": {"name": "Respuesta Rapida", "icon": "R"},
        "trusted": {"name": "Confiable", "icon": "C"},
        "newcomer": {"name": "Recien Llegado", "icon": "N"},
        "sybil_resistant": {"name": "Resistente a Sybil", "icon": "S"}
    }

    @staticmethod
    def check(entity_id: str, score: TrustScore,
              verified_attrs: Set[str]) -> List[str]:
        badges: List[str] = []
        if "identity_verified" in verified_attrs:
            badges.append("verified_identity")
        if score.total_reviews >= 50 and score.overall_score >= 0.9:
            badges.append("top_performer")
        if score.dimension_scores.get("responsiveness", 0) > 0.8:
            badges.append("quick_responder")
        if score.total_reviews >= 100 and score.overall_score >= 0.9:
            badges.append("trusted")
        if score.total_reviews < 10:
            badges.append("newcomer")
        if "sybil_resistant" in verified_attrs:
            badges.append("sybil_resistant")
        return badges



# ================================================================================
# SECCION 3: SISTEMA DE REPUTACION MEJORADO
# ================================================================================

class ReputationSystem:
    def __init__(self, half_life_days: float = 90.0,
                 decay_model: str = "exponential",
                 enable_advanced: bool = True) -> None:
        self.reputations: Dict[str, Dict[str, Any]] = {}
        self.transaction_history: Dict[str, List[Dict]] = defaultdict(list)
        self._lock = threading.RLock()
        self.enable_advanced = enable_advanced
        if enable_advanced:
            self.calculator = TrustScoreCalculator(half_life_days, decay_model)
            self.vc_system = VerifiableCredential()
            self.badge_system = BadgeSystem()
            self.advanced_scores: Dict[str, TrustScore] = {}
            self.reviews: Dict[str, List[Review]] = defaultdict(list)
            self.all_reviews: List[Review] = []
            self.verified_attrs: Dict[str, Set[str]] = defaultdict(set)

    # --- BLOQUE: REGISTRO DE AGENTE ---
    def register_agent(self, agent_id: str,
                       initial_reputation: float = 0.5) -> None:
        with self._lock:
            if agent_id not in self.reputations:
                self.reputations[agent_id] = {
                    'score': initial_reputation,
                    'successful_negotiations': 0,
                    'failed_negotiations': 0,
                    'disputed_negotiations': 0,
                    'total_value_transacted': 0.0,
                    'joined_at': datetime.now(timezone.utc),
                    'last_updated': datetime.now(timezone.utc)
                }
            if self.enable_advanced and agent_id not in self.advanced_scores:
                self.advanced_scores[agent_id] = TrustScore(
                    entity_id=agent_id, overall_score=initial_reputation
                )

    # --- BLOQUE: ACTUALIZACION DE REPUTACION ---
    def update_reputation(self, agent_id: str, outcome: str, value: float = 0.0,
                          counterpart_rating: Optional[float] = None,
                          review_data: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            if agent_id not in self.reputations:
                self.register_agent(agent_id)
            rep = self.reputations[agent_id]
            # --- BLOQUE: AJUSTE POR OUTCOME ---
            if outcome == 'success':
                rep['successful_negotiations'] += 1
                delta = 0.1 * (1 - rep['score']) * (1 + value / 1000)
                rep['score'] = min(1.0, rep['score'] + delta)
            elif outcome == 'failure':
                rep['failed_negotiations'] += 1
                rep['score'] = max(0.0, rep['score'] - 0.05 * rep['score'])
            elif outcome in ('dispute_resolved', 'dispute_lost'):
                rep['disputed_negotiations'] += 1
                penalty = 0.02 if outcome == 'dispute_resolved' else 0.15
                rep['score'] = max(0.0, rep['score'] - penalty * rep['score'])
            rep['total_value_transacted'] += value
            # --- BLOQUE: DECAY TEMPORAL CORREGIDO ---
            # CORRECCION: Usar last_updated en lugar de joined_at para el decay
            # Esto evita que agentes antiguos pero activos pierdan reputacion constantemente
            now = datetime.now(timezone.utc)
            last_update = rep.get('last_updated', rep['joined_at'])
            days_since_update = (now - last_update).total_seconds() / 86400.0
            if days_since_update > 0:
                rep['score'] *= (GlobalConfig.REPUTATION_DECAY ** days_since_update)
            rep['last_updated'] = now
            # --- BLOQUE: REVIEW AVANZADA ---
            if self.enable_advanced and review_data:
                self._process_review(agent_id, review_data)

    def _process_review(self, agent_id: str,
                        review_data: Dict[str, Any]) -> None:
        """Crea y procesa una review dentro del lock existente."""
        rating_val = review_data.get('rating', 4.0)
        review = Review(
            review_id=str(uuid.uuid4())[:8],
            reviewer_id=review_data.get('reviewer_id', 'system'),
            reviewee_id=agent_id,
            transaction_id=review_data.get('transaction_id', str(uuid.uuid4())),
            rating=rating_val,
            feedback_type=(
                FeedbackType.POSITIVE if rating_val >= 4
                else FeedbackType.NEGATIVE
            ),
            dimensions=review_data.get('dimensions', {
                'honesty': 4.0, 'delivery': 4.0, 'quality': 4.0
            }),
            comment=review_data.get('comment', ''),
            timestamp=datetime.now(timezone.utc)
        )
        self.all_reviews.append(review)
        self.reviews[agent_id].append(review)
        self.advanced_scores[agent_id] = self.calculator.calculate_trust_score(
            agent_id, self.reviews[agent_id], self.reviews, self.all_reviews
        )

    # --- BLOQUE: CONSULTAS ---
    def get_reputation(self, agent_id: str) -> float:
        with self._lock:
            if agent_id not in self.reputations:
                self.register_agent(agent_id)
            if self.enable_advanced and agent_id in self.advanced_scores:
                return self.advanced_scores[agent_id].overall_score
            return self.reputations[agent_id]['score']

    def get_trust_level(self, agent_id: str) -> TrustLevel:
        with self._lock:
            if not self.enable_advanced:
                return TrustLevel.MEDIUM
            if agent_id not in self.advanced_scores:
                self.register_agent(agent_id)
            return self.advanced_scores[agent_id].trust_level

    def get_reputation_profile(self, agent_id: str) -> Dict[str, Any]:
        with self._lock:
            if agent_id not in self.reputations:
                self.register_agent(agent_id)
            base = dict(self.reputations[agent_id])
            if self.enable_advanced and agent_id in self.advanced_scores:
                score = self.advanced_scores[agent_id]
                base.update({
                    'trust_level': score.trust_level.name,
                    'dimension_scores': score.dimension_scores,
                    'confidence': score.confidence,
                    'decay_factor': score.decay_factor,
                    'badges': self.badge_system.check(
                        agent_id, score,
                        self.verified_attrs.get(agent_id, set())
                    )
                })
            return base

    def get_advanced_score(self, agent_id: str) -> Optional[TrustScore]:
        if not self.enable_advanced:
            return None
        with self._lock:
            if agent_id not in self.advanced_scores:
                self.register_agent(agent_id)
            return self.advanced_scores[agent_id]

    # --- BLOQUE: SUBMIT REVIEW EXTERNO ---
    def submit_review(self, reviewer_id: str, reviewee_id: str,
                      transaction_id: str, rating: float,
                      dimensions: Dict[str, float],
                      comment: str = "") -> Optional[Review]:
        if not self.enable_advanced:
            return None
        with self._lock:
            # --- BLOQUE: VALIDACION ANTI-FRAUD ---
            fraud_score = self.calculator.fraud_detector.detect_sybil_attack(
                reviewer_id,
                self.reviews.get(reviewee_id, []),
                self.reviews
            )
            if fraud_score > 0.7:
                log_event(
                    "Review rechazada por posible fraude: {:.2f}".format(fraud_score),
                    "WARN"
                )
                return None
            review = Review(
                review_id=str(uuid.uuid4())[:8],
                reviewer_id=reviewer_id,
                reviewee_id=reviewee_id,
                transaction_id=transaction_id,
                rating=rating,
                feedback_type=(
                    FeedbackType.POSITIVE if rating >= 4
                    else FeedbackType.NEGATIVE
                ),
                dimensions=dimensions,
                comment=comment,
                timestamp=datetime.now(timezone.utc)
            )
            self.all_reviews.append(review)
            self.reviews[reviewee_id].append(review)
            if reviewee_id in self.advanced_scores:
                self.advanced_scores[reviewee_id] = (
                    self.calculator.calculate_trust_score(
                        reviewee_id, self.reviews[reviewee_id],
                        self.reviews, self.all_reviews
                    )
                )
            return review

    def issue_credential(self, holder_id: str, claim_type: str,
                         claim_value: Any, issuer_id: str = "system") -> Optional[str]:
        if not self.enable_advanced:
            return None
        cred_id = self.vc_system.issue(holder_id, claim_type, claim_value, issuer_id)
        self.verified_attrs[holder_id].add(claim_type)
        return cred_id

    def detect_fraud_risk(self, agent_id: str,
                          context_reviews: Optional[List[Review]] = None) -> float:
        if not self.enable_advanced:
            return 0.0
        with self._lock:
            reviews = context_reviews or self.reviews.get(agent_id, [])
            return self.calculator.fraud_detector.detect_sybil_attack(
                agent_id, reviews, self.reviews
            )



# ================================================================================
# SECCION 4: GOBERNANZA DINAMICA DE REPUTACION
# ================================================================================

class ReputationGovernor:
    def __init__(self, reputation_system: ReputationSystem,
                 ceo_callback: Optional[Callable[[str, Any], None]] = None) -> None:
        self.rep_system = reputation_system
        self.ceo_callback = ceo_callback
        self._lock = threading.RLock()
        self._config: Dict[str, Any] = {
            "enable_advanced": True,
            "half_life_days": 90.0,
            "decay_model": "exponential",
            "global_fraud_threshold": 0.6,
            "auto_adjust_enabled": False,
            "auto_adjust_metrics": {
                "min_success_rate": 0.7,
                "max_fraud_incidents": 5,
                "check_interval_seconds": 300
            }
        }
        self._agent_overrides: Dict[str, Dict[str, Any]] = {}
        self._audit_log: deque = deque(maxlen=1000)
        self._scheduled_changes: List[Dict[str, Any]] = []
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_scheduler = threading.Event()
        self._config_cache: Dict[str, Any] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl_seconds = 5
        log_event("ReputationGovernor inicializado", "GOV")

    # --- BLOQUE: CONSULTA DE CONFIG ---
    def get_config(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            base = dict(self._config)
            if agent_id and agent_id in self._agent_overrides:
                base.update(self._agent_overrides[agent_id])
            return base

    def get_effective_fraud_threshold(self, agent_id: str) -> float:
        config = self.get_config(agent_id)
        return config.get(
            "fraud_threshold",
            config.get("global_fraud_threshold", 0.6)
        )

    def is_advanced_enabled(self) -> bool:
        with self._lock:
            return self._config.get("enable_advanced", True)

    # --- BLOQUE: COMANDOS CEO ---
    def ceo_toggle_advanced(self, enable: bool,
                            reason: str = "") -> Dict[str, Any]:
        with self._lock:
            old_value = self._config["enable_advanced"]
            if old_value == enable:
                return {
                    "success": False,
                    "message": "Ya esta en ese estado",
                    "changed": False
                }
            self._config["enable_advanced"] = enable
            self._log_change("toggle_advanced", {
                "old": old_value, "new": enable, "reason": reason
            })
            if hasattr(self.rep_system, 'enable_advanced'):
                self.rep_system.enable_advanced = enable
            self._invalidate_cache()
            if self.ceo_callback:
                try:
                    self.ceo_callback(
                        "reputation_advanced_toggled",
                        {"enabled": enable, "reason": reason}
                    )
                except Exception:
                    pass
            log_event(
                "CEO: Modo avanzado {} | {}".format(
                    'ACTIVADO' if enable else 'DESACTIVADO', reason
                ),
                "GOV"
            )
            return {
                "success": True, "changed": True,
                "new_value": enable, "reason": reason
            }

    def ceo_set_decay_params(self, half_life_days: Optional[float] = None,
                              decay_model: Optional[str] = None,
                              reason: str = "") -> Dict[str, Any]:
        with self._lock:
            changes: Dict[str, Any] = {}
            if half_life_days is not None and half_life_days > 0:
                old = self._config["half_life_days"]
                self._config["half_life_days"] = half_life_days
                changes["half_life_days"] = {"old": old, "new": half_life_days}
            if decay_model is not None and decay_model in (
                "exponential", "linear", "step"
            ):
                old = self._config["decay_model"]
                self._config["decay_model"] = decay_model
                changes["decay_model"] = {"old": old, "new": decay_model}
            if not changes:
                return {
                    "success": False,
                    "message": "No se especificaron cambios validos",
                    "changed": False
                }
            self._log_change("set_decay_params", {
                "changes": changes, "reason": reason
            })
            if hasattr(self.rep_system, 'calculator') and self.rep_system.calculator:
                if half_life_days is not None:
                    self.rep_system.calculator.half_life_days = half_life_days
                if decay_model is not None:
                    self.rep_system.calculator.decay_model = decay_model
            self._invalidate_cache()
            if self.ceo_callback:
                try:
                    self.ceo_callback("decay_params_updated", {
                        "changes": changes, "reason": reason
                    })
                except Exception:
                    pass
            log_event(
                "CEO: Parametros de decay actualizados | {}".format(reason),
                "GOV"
            )
            return {
                "success": True, "changed": True,
                "changes": changes, "reason": reason
            }

    def ceo_set_fraud_threshold(self, threshold: float,
                                 agent_id: Optional[str] = None,
                                 reason: str = "") -> Dict[str, Any]:
        if not (0.0 <= threshold <= 1.0):
            return {
                "success": False,
                "message": "Threshold debe estar entre 0.0 y 1.0",
                "changed": False
            }
        with self._lock:
            if agent_id:
                if agent_id not in self._agent_overrides:
                    self._agent_overrides[agent_id] = {}
                old = self._agent_overrides[agent_id].get(
                    "fraud_threshold",
                    self._config["global_fraud_threshold"]
                )
                self._agent_overrides[agent_id]["fraud_threshold"] = threshold
                scope = "agente {}".format(agent_id)
            else:
                old = self._config["global_fraud_threshold"]
                self._config["global_fraud_threshold"] = threshold
                scope = "global"
            self._log_change("set_fraud_threshold", {
                "old": old, "new": threshold,
                "scope": scope, "reason": reason
            })
            self._invalidate_cache()
            self._propagate_fraud_threshold(agent_id, threshold)
            if self.ceo_callback:
                try:
                    self.ceo_callback("fraud_threshold_updated", {
                        "threshold": threshold,
                        "agent_id": agent_id,
                        "reason": reason
                    })
                except Exception:
                    pass
            log_event(
                "CEO: Fraud threshold {} ajustado a {:.2f} | {}".format(
                    scope, threshold, reason
                ),
                "GOV"
            )
            return {
                "success": True, "changed": True,
                "scope": scope, "old_value": old,
                "new_value": threshold
            }

    # --- BLOQUE: CAMBIOS PROGRAMADOS ---
    def ceo_schedule_change(self, change_type: str, params: Dict[str, Any],
                             execute_at: datetime,
                             reason: str = "") -> Dict[str, Any]:
        with self._lock:
            change_id = str(uuid.uuid4())[:8]
            self._scheduled_changes.append({
                "id": change_id,
                "type": change_type,
                "params": params,
                "execute_at": execute_at,
                "reason": reason,
                "status": "pending",
                "created_at": datetime.now(timezone.utc)
            })
            self._log_change("schedule_change", {
                "change_id": change_id, "type": change_type,
                "execute_at": execute_at.isoformat(), "reason": reason
            })
            self._ensure_scheduler_running()
            log_event(
                "CEO: Cambio programado #{} para {} | {}".format(
                    change_id, execute_at.isoformat(), change_type
                ),
                "GOV"
            )
            return {
                "success": True, "change_id": change_id,
                "execute_at": execute_at.isoformat()
            }

    def ceo_enable_auto_adjust(self, enable: bool,
                                metrics: Optional[Dict[str, Any]] = None,
                                reason: str = "") -> Dict[str, Any]:
        with self._lock:
            old = self._config["auto_adjust_enabled"]
            if old == enable:
                return {
                    "success": False,
                    "message": "Ya esta en ese estado",
                    "changed": False
                }
            self._config["auto_adjust_enabled"] = enable
            if metrics:
                self._config["auto_adjust_metrics"].update(metrics)
            self._log_change("toggle_auto_adjust", {
                "old": old, "new": enable,
                "metrics": metrics, "reason": reason
            })
            if enable:
                self._ensure_scheduler_running()
            if self.ceo_callback:
                try:
                    self.ceo_callback("auto_adjust_toggled", {
                        "enabled": enable, "reason": reason
                    })
                except Exception:
                    pass
            log_event(
                "CEO: Auto-ajuste {} | {}".format(
                    'ACTIVADO' if enable else 'DESACTIVADO', reason
                ),
                "GOV"
            )
            return {"success": True, "changed": True, "enabled": enable}

    # --- BLOQUE: CONSULTAS DE AUDITORIA ---
    def get_audit_log(self, limit: int = 50,
                      filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            logs = list(self._audit_log)
            if filter_type:
                logs = [l for l in logs if l.get("type") == filter_type]
            return logs[-limit:]

    def get_scheduled_changes(self, only_pending: bool = True) -> List[Dict[str, Any]]:
        with self._lock:
            changes = self._scheduled_changes
            if only_pending:
                changes = [c for c in changes if c["status"] == "pending"]
            return sorted(changes, key=lambda x: x["execute_at"])

    def cancel_scheduled_change(self, change_id: str,
                                reason: str = "") -> bool:
        with self._lock:
            for change in self._scheduled_changes:
                if change["id"] == change_id and change["status"] == "pending":
                    change["status"] = "cancelled"
                    change["cancelled_at"] = datetime.now(timezone.utc)
                    change["cancel_reason"] = reason
                    self._log_change("cancel_scheduled_change", {
                        "change_id": change_id, "reason": reason
                    })
                    log_event(
                        "CEO: Cambio #{} cancelado | {}".format(
                            change_id, reason
                        ),
                        "GOV"
                    )
                    return True
        return False

    def shutdown(self) -> None:
        """Detiene el scheduler de forma limpia."""
        self._stop_scheduler.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        log_event("ReputationGovernor scheduler detenido", "GOV")

    # --- BLOQUE: METODOS INTERNOS ---
    def _log_change(self, change_type: str, details: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": change_type,
            "details": details,
            "actor": "CEO"
        }
        self._audit_log.append(entry)

    def _invalidate_cache(self) -> None:
        self._config_cache = {}
        self._cache_timestamp = 0

    def _propagate_fraud_threshold(self, agent_id: Optional[str],
                                    threshold: float) -> None:
        pass

    def _ensure_scheduler_running(self) -> None:
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        self._stop_scheduler.clear()
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self._scheduler_thread.start()
        log_event("Scheduler de gobernanza iniciado", "GOV")

    def _scheduler_loop(self) -> None:
        while not self._stop_scheduler.is_set():
            now = datetime.now(timezone.utc)
            with self._lock:
                for change in self._scheduled_changes:
                    if (change["status"] == "pending"
                            and now >= change["execute_at"]):
                        self._execute_scheduled_change(change)
                if self._config["auto_adjust_enabled"]:
                    self._check_auto_adjust_conditions()
            # Espera interrumpible
            self._stop_scheduler.wait(timeout=60)

    def _execute_scheduled_change(self, change: Dict[str, Any]) -> None:
        change_id = change["id"]
        change_type = change["type"]
        params = change["params"]
        reason = change.get("reason", "Cambio programado")
        try:
            if change_type == "toggle_advanced":
                self.ceo_toggle_advanced(
                    params.get("enable", True),
                    "{} [programado]".format(reason)
                )
            elif change_type == "set_decay_params":
                self.ceo_set_decay_params(
                    params.get("half_life_days"),
                    params.get("decay_model"),
                    "{} [programado]".format(reason)
                )
            elif change_type == "set_fraud_threshold":
                self.ceo_set_fraud_threshold(
                    params.get("threshold", 0.6),
                    params.get("agent_id"),
                    "{} [programado]".format(reason)
                )
            change["status"] = "executed"
            change["executed_at"] = datetime.now(timezone.utc).isoformat()
            log_event(
                "Cambio programado #{} ejecutado exitosamente".format(
                    change_id
                ),
                "GOV"
            )
        except Exception as e:
            change["status"] = "failed"
            change["error"] = str(e)
            log_event(
                "ERROR ejecutando cambio #{}: {}".format(change_id, e),
                "ERROR"
            )

    def _check_auto_adjust_conditions(self) -> None:
        pass

    def apply_config_to_agent(self, agent: Any, agent_id: str) -> None:
        config = self.get_config(agent_id)
        if hasattr(agent, 'fraud_threshold') and "fraud_threshold" in config:
            agent.fraud_threshold = config["fraud_threshold"]
        if hasattr(agent, 'reputation_system'):
            if hasattr(agent.reputation_system, 'enable_advanced'):
                agent.reputation_system.enable_advanced = config.get(
                    "enable_advanced", True
                )
        if hasattr(agent, 'governor') and agent.governor is None:
            agent.governor = self


# ================================================================================
# SECCION 5: ALGORITMOS DE NEGOCIACION (TEORIA DE JUEGOS)
# ================================================================================

# --- BLOQUE: ENUMS DE NEGOCIACION ---
class NegotiationStrategy(Enum):
    HARDLINE = auto()
    MODERATE = auto()
    ACCOMMODATING = auto()
    COMPETITIVE = auto()
    COLLABORATIVE = auto()
    RANDOM = auto()


class ConcessionType(Enum):
    PRICE_REDUCTION = auto()
    TIME_EXTENSION = auto()
    QUALITY_ADJUSTMENT = auto()
    PAYMENT_TERMS = auto()
    CANCELLATION_POLICY = auto()
    MIXED = auto()


@dataclass
class NegotiationStateAdvanced:
    round_number: int = 0
    current_offer: Optional[Dict[str, Any]] = None
    opponent_offer: Optional[Dict[str, Any]] = None
    my_utilities_history: List[float] = field(default_factory=list)
    concessions_made: List[float] = field(default_factory=list)
    time_elapsed: float = 0.0


@dataclass
class NegotiationResultAdvanced:
    success: bool
    final_offer: Optional[Dict[str, Any]] = None
    my_final_utility: float = 0.0
    opponent_final_utility: float = 0.0
    mutual_gain: float = 0.0
    rounds_used: int = 0
    pareto_optimal: bool = False
    nash_equilibrium_reached: bool = False


# --- BLOQUE: FUNCIONES DE TEORIA DE JUEGOS ---
def calculate_nash_product(my_utility: float, opponent_utility: float,
                           epsilon: float = 0.01) -> float:
    return (my_utility + epsilon) * (opponent_utility + epsilon)


def calculate_pareto_gain(initial_utilities: Tuple[float, float],
                          final_utilities: Tuple[float, float]) -> Tuple[bool, float]:
    my_gain = final_utilities[0] - initial_utilities[0]
    opp_gain = final_utilities[1] - initial_utilities[1]
    total_gain = my_gain + opp_gain
    no_sacrifice = my_gain > -0.1 and opp_gain > -0.1
    return no_sacrifice and total_gain > 0, total_gain


def calculate_bargaining_power(my_reservation_value: float, my_ideal_value: float,
                               time_pressure: float,
                               alternatives_count: int) -> float:
    improvement_potential = (
        (my_ideal_value - my_reservation_value) / max(my_ideal_value, 0.01)
    )
    time_factor = 1.0 - (time_pressure * 0.5)
    alt_factor = min(1.0, math.log2(alternatives_count + 1) / 3)
    return max(0.0, min(1.0,
        improvement_potential * 0.4 + time_factor * 0.3 + alt_factor * 0.3
    ))


def sigmoid_temperature(t: float, temperature: float = 0.5) -> float:
    return 1.0 / (1.0 + math.exp(-t / max(temperature, 0.001)))


# --- BLOQUE: CONCESSION ENGINE ---
class AdvancedConcessionEngine:
    @staticmethod
    def calculate_concession_amount(round_number: int, max_rounds: int,
                                     strategy: NegotiationStrategy,
                                     remaining_utility_gap: float,
                                     time_pressure: float) -> float:
        progress = round_number / max(max_rounds, 1)
        if strategy == NegotiationStrategy.HARDLINE:
            if progress < 0.6:
                factor = 0.05
            elif progress < 0.8:
                factor = 0.15
            else:
                factor = 0.30
            return factor * remaining_utility_gap
        elif strategy == NegotiationStrategy.MODERATE:
            return progress * 0.20 * remaining_utility_gap
        elif strategy == NegotiationStrategy.ACCOMMODATING:
            return min(0.4, progress * 0.35 * remaining_utility_gap)
        elif strategy == NegotiationStrategy.COMPETITIVE:
            return 0.10 * remaining_utility_gap * (1 + time_pressure * 0.2)
        elif strategy == NegotiationStrategy.COLLABORATIVE:
            return (progress * 0.25 + 0.1) * remaining_utility_gap
        return random.uniform(0.1, 0.35) * remaining_utility_gap

    @staticmethod
    def determine_concession_type(strategy: NegotiationStrategy,
                                   opponent_focus: str,
                                   my_strengths: List[str]) -> ConcessionType:
        focus_map = {
            'price': ConcessionType.PRICE_REDUCTION,
            'time': ConcessionType.TIME_EXTENSION,
            'quality': ConcessionType.QUALITY_ADJUSTMENT
        }
        if strategy == NegotiationStrategy.COLLABORATIVE:
            for s in my_strengths:
                if s != opponent_focus and s in focus_map:
                    return focus_map[s]
        return focus_map.get(
            opponent_focus,
            ConcessionType.PRICE_REDUCTION
            if random.random() > 0.5 else ConcessionType.MIXED
        )


# --- BLOQUE: OPPONENT MODELER ---
class OpponentModeler:
    def __init__(self) -> None:
        self.strategy: Optional[NegotiationStrategy] = None
        self.price_trend: str = "stable"
        self.concession_rate: float = 0.0
        self.focus: str = "price"
        self._price_history: List[float] = []

    def update(self, opponent_offers: List[Dict[str, Any]]) -> None:
        if len(opponent_offers) < 2:
            return
        prices = [
            o.get('price', 0) for o in opponent_offers if o.get('price')
        ]
        if len(prices) >= 2:
            avg_change = sum(
                prices[i + 1] - prices[i]
                for i in range(len(prices) - 1)
            ) / (len(prices) - 1)
            self.price_trend = (
                'increasing' if avg_change > 0 else 'decreasing'
            )
            self.concession_rate = abs(avg_change)
            if avg_change > 2:
                self.strategy = NegotiationStrategy.HARDLINE
            elif avg_change > 0:
                self.strategy = NegotiationStrategy.MODERATE
            else:
                self.strategy = NegotiationStrategy.ACCOMMODATING
            self._price_history = prices
            times = [
                o.get('delivery_time', 0)
                for o in opponent_offers if o.get('delivery_time')
            ]
            if len(times) >= 2:
                self.focus = (
                    'time' if (max(times) - min(times)) > 10 else 'price'
                )

    def adapt_strategy(self, current_strategy: NegotiationStrategy,
                       learning_rate: float) -> NegotiationStrategy:
        if not self.strategy:
            return current_strategy
        counter_map: Dict[NegotiationStrategy, NegotiationStrategy] = {
            NegotiationStrategy.HARDLINE: NegotiationStrategy.COLLABORATIVE,
            NegotiationStrategy.MODERATE: NegotiationStrategy.MODERATE,
            NegotiationStrategy.ACCOMMODATING: NegotiationStrategy.COMPETITIVE,
            NegotiationStrategy.COMPETITIVE: NegotiationStrategy.COLLABORATIVE
        }
        adapted = counter_map.get(self.strategy, current_strategy)
        return adapted if learning_rate > 0.5 else current_strategy


# --- BLOQUE: PARETO-NASH EVALUATOR ---
class ParetoNashEvaluator:
    @staticmethod
    def is_pareto_optimal(price: float, min_acceptable: float,
                          max_acceptable: float) -> bool:
        mid = (min_acceptable + max_acceptable) / 2
        return abs(price - mid) <= (max_acceptable - min_acceptable) * 0.15

    @staticmethod
    def evaluate_decision(utility: float, reservation_utility: float,
                          remaining_rounds: int,
                          opponent_profile: Optional[Dict[str, Any]] = None
                          ) -> Tuple[bool, str]:
        if utility >= reservation_utility:
            if remaining_rounds <= 1:
                return True, "Aceptar: ultima ronda, utilidad suficiente"
            return True, "Aceptar: win-win probable"
        if remaining_rounds <= 1 and utility >= reservation_utility - 0.15:
            return True, "Aceptar: ultima oportunidad, utilidad marginal"
        if utility < reservation_utility - 0.2:
            return False, "Rechazar: utilidad muy por debajo de reserva"
        return False, "Contra-ofertar: espacio para mejora"


# ================================================================================
# SECCION 6: AGENTE BASE DE NEGOCIACION
# ================================================================================

class NegotiationAgent(ABC):
    def __init__(self, agent_id: str, role: AgentRole,
                 utility_profile: UtilityProfile,
                 reputation_system: ReputationSystem) -> None:
        self.agent_id = agent_id
        self.role = role
        self.utility_profile = utility_profile
        self.reputation_system = reputation_system
        self.governor: Optional[ReputationGovernor] = None
        self.active_sessions: Dict[str, NegotiationSession] = {}
        self.session_history: deque = deque(maxlen=1000)
        self.total_negotiations = 0
        self.successful_negotiations = 0
        self.config = GlobalConfig

    # --- BLOQUE: GOBERNANZA ---
    def update_governance(self) -> None:
        """Actualiza configuracion del agente desde el gobernador."""
        if self.governor:
            self.governor.apply_config_to_agent(self, self.agent_id)

    async def _debug(self, session: NegotiationSession, offer: Offer,
                     action: str) -> None:
        if not self.config.LOG_VERBOSE:
            return
        log_banner("{} - {}".format(self.agent_id, action), emoji="R")
        log_event("ID {} | Ronda {}".format(
            session.session_id[:8], session.current_round + 1
        ))
        rationale_preview = (
            offer.rationale[:40] if offer.rationale else "N/A"
        )
        log_event("${:.2f} | {}".format(offer.price, rationale_preview))

    @abstractmethod
    async def generate_offer(self, session: NegotiationSession,
                             context: Dict[str, Any]) -> Offer:
        pass

    @abstractmethod
    async def evaluate_offer(self, offer: Offer,
                             session: NegotiationSession
                             ) -> Tuple[bool, float, Optional[Offer]]:
        pass

    # --- BLOQUE: NEGOCIACION AUTONOMA (STANDALONE) ---
    async def negotiate(self, session: NegotiationSession
                        ) -> NegotiationStatus:
        """
        Loop de negociacion autonomo para uso standalone.
        El orquestador NO usa este metodo; usa generate_offer/evaluate_offer
        directamente para evitar doble-loop.
        """
        self.active_sessions[session.session_id] = session
        try:
            while session.status == NegotiationStatus.ACTIVE:
                # --- VALIDACION DE TERMINACION ---
                if (session.is_expired()
                        or session.current_round >= session.max_rounds):
                    session.status = (
                        NegotiationStatus.EXPIRED
                        if session.is_expired()
                        else NegotiationStatus.REJECTED
                    )
                    break
                
                last_offer = session.get_last_offer()
                
                if last_offer is None:
                    # --- PRIMERA OFERTA ---
                    offer = await self.generate_offer(session, {})
                    await self._send_offer(session, offer)
                    await self._debug(session, offer, "OFERTA INICIAL")
                    session.current_round += 1
                    
                elif last_offer.proposed_by == self.agent_id:
                    # --- ESPERANDO RESPUESTA ---
                    await asyncio.sleep(
                        0.5 if self.config.IS_TERMUX else 1
                    )
                    continue
                    
                else:
                    # --- EVALUAR OFERTA DEL OPONENTE ---
                    accept, utility, counter = await self.evaluate_offer(
                        last_offer, session
                    )
                    if accept:
                        session.final_offer = last_offer
                        session.status = NegotiationStatus.ACCEPTED
                        if self.role == AgentRole.INITIATOR:
                            session.final_utility_a = utility
                        else:
                            session.final_utility_b = utility
                        session.agreement_timestamp = datetime.now(timezone.utc)
                        self.reputation_system.update_reputation(
                            self.agent_id, 'success', last_offer.price
                        )
                        log_event(
                            "{} ACEPTA oferta ${:.2f}".format(
                                self.agent_id, last_offer.price
                            )
                        )
                        return NegotiationStatus.ACCEPTED
                    elif counter and session.current_round < session.max_rounds:
                        await self._send_offer(session, counter)
                        await self._debug(session, counter, "CONTRAOFERTA")
                        session.current_round += 1
                    else:
                        session.status = NegotiationStatus.REJECTED
                        self.reputation_system.update_reputation(
                            self.agent_id, 'failure', 0
                        )
                        log_event("{} RECHAZA".format(self.agent_id))
                        return NegotiationStatus.REJECTED
                        
            return session.status
            
        finally:
            self.active_sessions.pop(session.session_id, None)

    async def _send_offer(self, session: NegotiationSession,
                          offer: Offer) -> None:
        offer.proposed_by = self.agent_id
        offer.proposed_at = datetime.now(timezone.utc)
        session.offers_history.append(offer)
        receiver_id = (
            session.agent_b_id
            if self.agent_id == session.agent_a_id
            else session.agent_a_id
        )
        session.messages.append(NegotiationMessage(
            negotiation_id=session.session_id,
            round_number=session.current_round,
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=(
                "OFFER" if len(session.offers_history) == 1
                else "COUNTER_OFFER"
            ),
            structured_content=offer
        ))



# ================================================================================
# SECCION 7: AGENTES ESPECIALIZADOS
# ================================================================================

# --- BLOQUE: STRATEGIC AGENT ---
class StrategicAgent(NegotiationAgent):
    def __init__(self, agent_id: str, role: AgentRole,
                 utility_profile: UtilityProfile,
                 reputation_system: ReputationSystem,
                 strategy: NegotiationStrategy = NegotiationStrategy.COLLABORATIVE,
                 reservation_utility: float = 0.6,
                 learning_rate: float = 0.15,
                 governor: Optional[ReputationGovernor] = None) -> None:
        super().__init__(agent_id, role, utility_profile, reputation_system)
        self.strategy = strategy
        self.reservation_utility = reservation_utility
        self.learning_rate = learning_rate
        self.concession_engine = AdvancedConcessionEngine()
        self.opponent_model = OpponentModeler()
        self.advanced_state = NegotiationStateAdvanced()
        self.offers_sent_history: List[Dict[str, Any]] = []
        self._base_fraud_threshold = 0.6
        self.fraud_threshold = self._base_fraud_threshold
        self.governor = governor
        if self.governor:
            self.governor.apply_config_to_agent(self, agent_id)
            self._base_fraud_threshold = (
                self.governor.get_effective_fraud_threshold(agent_id)
            )
            self.fraud_threshold = self._base_fraud_threshold

    async def generate_offer(self, session: NegotiationSession,
                             context: Dict[str, Any]) -> Offer:
        # --- BLOQUE: CALCULO DE PODER Y PRESION ---
        time_pressure = min(
            1.0, session.current_round / max(session.max_rounds, 1)
        )
        bargaining_power = calculate_bargaining_power(
            self.utility_profile.min_acceptable_price,
            self.utility_profile.max_acceptable_price,
            time_pressure, random.randint(1, 3)
        )
        base_price = (
            (self.utility_profile.min_acceptable_price
             + self.utility_profile.max_acceptable_price) / 2
        )
        adjustment = 1.0 - (bargaining_power * 0.15)
        offer_dict: Dict[str, Any] = {
            'price': base_price * adjustment,
            'delivery_time': 24.0,
            'quality_level': self.utility_profile.required_quality_level,
            'proposed_by': self.agent_id,
            'rationale': "Estrategia {} | Poder: {:.2f}".format(
                self.strategy.name, bargaining_power
            )
        }
        self.advanced_state.current_offer = offer_dict
        self.offers_sent_history.append(offer_dict)
        return Offer(**offer_dict)

    async def evaluate_offer(self, offer: Offer,
                             session: NegotiationSession
                             ) -> Tuple[bool, float, Optional[Offer]]:
        # --- BLOQUE: VALIDACION ANTI-FRAUD ---
        if self.reputation_system.enable_advanced:
            fraud_risk = self.reputation_system.detect_fraud_risk(
                offer.proposed_by
            )
            if fraud_risk > self.fraud_threshold:
                log_event(
                    "Oferta rechazada por riesgo de fraude: {:.2f}".format(
                        fraud_risk
                    ),
                    "WARN"
                )
                return False, 0.0, None
        # --- BLOQUE: CALCULO DE UTILIDAD ---
        offer_dict: Dict[str, Any] = {
            'price': offer.price,
            'delivery_time': offer.delivery_time,
            'quality_level': offer.quality_level,
            'counterparty_reputation': (
                self.reputation_system.get_reputation(offer.proposed_by)
            )
        }
        utility = self.utility_profile.calculate_advanced_utility(offer_dict)
        remaining_rounds = session.max_rounds - session.current_round
        accept, reason = ParetoNashEvaluator.evaluate_decision(
            utility, self.reservation_utility, remaining_rounds
        )
        if accept:
            return True, utility, None
        # --- BLOQUE: GENERACION DE CONTRAOFERTA ---
        self.opponent_model.update([offer_dict])
        adapted_strategy = self.opponent_model.adapt_strategy(
            self.strategy, self.learning_rate
        )
        concession_factor = self.concession_engine.calculate_concession_amount(
            session.current_round, session.max_rounds, adapted_strategy,
            max(0, 1.0 - utility),
            min(1.0, session.current_round / max(session.max_rounds, 1))
        )
        if self.role == AgentRole.INITIATOR:
            new_price = offer.price * (1 - concession_factor * 0.2)
        else:
            new_price = offer.price * (1 + concession_factor * 0.2)
        counter = offer.clone_with_changes(
            price=new_price,
            concessions_made=offer.concessions_made + [
                "STRAT_{:.2f}".format(concession_factor)
            ]
        )
        return False, utility, counter


# --- BLOQUE: RULE-BASED AGENT ---
class RuleBasedAgent(NegotiationAgent):
    def __init__(self, agent_id: str, role: AgentRole,
                 utility_profile: UtilityProfile,
                 reputation_system: ReputationSystem,
                 strategy: str = "compromising") -> None:
        super().__init__(agent_id, role, utility_profile, reputation_system)
        self.strategy = strategy
        self.concession_rate: Dict[str, float] = {
            'aggressive': 0.05,
            'compromising': 0.15,
            'conservative': 0.25
        }
        self.min_utility_threshold: Dict[str, float] = {
            'aggressive': 0.8,
            'compromising': 0.6,
            'conservative': 0.4
        }

    async def generate_offer(self, session: NegotiationSession,
                             context: Dict[str, Any]) -> Offer:
        base_price = (
            (self.utility_profile.min_acceptable_price
             + self.utility_profile.max_acceptable_price) / 2
        )
        counterparty = (
            session.agent_b_id if self.role == AgentRole.INITIATOR
            else session.agent_a_id
        )
        rep = self.reputation_system.get_reputation(counterparty)
        trust_adjustment = 1.0 - (rep - 0.5) * 0.2
        return Offer(
            price=base_price * trust_adjustment,
            delivery_time=24.0,
            quality_level=self.utility_profile.required_quality_level,
            proposed_by=self.agent_id,
            rationale="Estrategia {}".format(self.strategy)
        )

    async def evaluate_offer(self, offer: Offer,
                             session: NegotiationSession
                             ) -> Tuple[bool, float, Optional[Offer]]:
        utility = self.utility_profile.calculate_utility(offer)
        threshold = self.min_utility_threshold.get(self.strategy, 0.6)
        if utility >= threshold:
            return True, utility, None
        if session.current_round < session.max_rounds - 1:
            last_own = next(
                (o for o in reversed(session.offers_history)
                 if o.proposed_by == self.agent_id),
                None
            )
            if last_own:
                rate = self.concession_rate.get(self.strategy, 0.15)
                concession = last_own.price * rate
                if self.role == AgentRole.INITIATOR:
                    new_price = last_own.price - concession
                else:
                    new_price = last_own.price + concession
                counter = offer.clone_with_changes(
                    price=new_price,
                    concessions_made=last_own.concessions_made + [
                        "price:{:+.2f}".format(concession)
                    ]
                )
                return False, utility, counter
        return False, utility, None


# --- BLOQUE: LIGHTWEIGHT AGENT ---
class LightweightAgent(NegotiationAgent):
    def __init__(self, agent_id: str, role: AgentRole,
                 utility_profile: UtilityProfile,
                 reputation_system: ReputationSystem) -> None:
        super().__init__(agent_id, role, utility_profile, reputation_system)
        self.base_concession = 0.12
        self.patience = random.randint(3, 5)

    async def generate_offer(self, session: NegotiationSession,
                             context: Dict[str, Any]) -> Offer:
        mid = (
            (self.utility_profile.min_acceptable_price
             + self.utility_profile.max_acceptable_price) / 2
        )
        variance = (
            (self.utility_profile.max_acceptable_price
             - self.utility_profile.min_acceptable_price) * 0.1
        )
        price = mid + random.uniform(-variance, variance)
        return Offer(
            price=price,
            delivery_time=24.0,
            quality_level=self.utility_profile.required_quality_level,
            proposed_by=self.agent_id,
            rationale="Lightweight heuristic"
        )

    async def evaluate_offer(self, offer: Offer,
                             session: NegotiationSession
                             ) -> Tuple[bool, float, Optional[Offer]]:
        utility = self.utility_profile.calculate_utility(offer)
        if utility >= 0.65 or session.current_round >= self.patience:
            return True, utility, None
        if session.current_round < session.max_rounds - 1:
            progress = session.current_round / max(session.max_rounds, 1)
            concession = self.base_concession * (1 + progress)
            if self.role == AgentRole.INITIATOR:
                new_price = offer.price * (1 - concession)
            else:
                new_price = offer.price * (1 + concession)
            counter = offer.clone_with_changes(
                price=new_price,
                concessions_made=offer.concessions_made + [
                    "LW_{}".format(session.current_round)
                ]
            )
            return False, utility, counter
        return False, utility, None


# --- BLOQUE: LLM-BASED AGENT ---
class LLMBasedAgent(NegotiationAgent):
    def __init__(self, agent_id: str, role: AgentRole,
                 utility_profile: UtilityProfile,
                 reputation_system: ReputationSystem,
                 api_key: Optional[str] = None) -> None:
        super().__init__(agent_id, role, utility_profile, reputation_system)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.conversation_history: Dict[str, List[Dict]] = defaultdict(list)

    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        # --- BLOQUE: SIMULACION LLM ---
        await asyncio.sleep(0.5)
        return {
            "price": random.uniform(
                self.utility_profile.min_acceptable_price * 1.1,
                self.utility_profile.max_acceptable_price * 0.9
            ),
            "delivery_time": random.uniform(12, 48),
            "quality_level": random.randint(3, 5),
            "rationale": "Oferta estrategica basada en analisis de mercado",
            "expected_counter": "Reduccion de 10-15% en precio"
        }

    async def generate_offer(self, session: NegotiationSession,
                             context: Dict[str, Any]) -> Offer:
        response = await self._call_llm("generate")
        return Offer(
            price=response.get('price', 100.0),
            delivery_time=response.get('delivery_time', 24.0),
            quality_level=response.get('quality_level', 3),
            proposed_by=self.agent_id,
            rationale=response.get('rationale', '')
        )

    async def evaluate_offer(self, offer: Offer,
                             session: NegotiationSession
                             ) -> Tuple[bool, float, Optional[Offer]]:
        response = await self._call_llm("evaluate")
        decision = response.get('decision', 'REJECT')
        utility = response.get('utility_score', 0.5)
        if decision == 'ACCEPT':
            return True, utility, None
        elif (decision == 'COUNTER'
              and session.current_round < session.max_rounds - 1):
            counter_data = response.get('counter_offer', {})
            counter = offer.clone_with_changes(
                price=counter_data.get('price', offer.price * 0.9),
                delivery_time=counter_data.get(
                    'delivery_time', offer.delivery_time
                )
            )
            return False, utility, counter
        return False, utility, None


# --- BLOQUE: RL-BASED AGENT ---
class RLBasedAgent(NegotiationAgent):
    def __init__(self, agent_id: str, role: AgentRole,
                 utility_profile: UtilityProfile,
                 reputation_system: ReputationSystem) -> None:
        super().__init__(agent_id, role, utility_profile, reputation_system)
        self.q_table: Dict[Tuple, Dict[str, float]] = {}
        self.learning_rate = self.config.RL_LEARNING_RATE
        self.discount = self.config.RL_DISCOUNT_FACTOR
        self.epsilon = self.config.RL_EXPLORATION_EPSILON
        self.episode_history: List[Dict] = []

    # --- BLOQUE: ESTADO Y ACCIONES ---
    def _get_state(self, session: NegotiationSession) -> Tuple:
        last_offer = session.get_last_offer()
        if not last_offer:
            return (0, 0.0, 0.0)
        own_utility = self.utility_profile.calculate_utility(last_offer)
        return (
            session.current_round,
            round(own_utility, 1),
            round(1.0 - own_utility, 1)
        )

    def _get_action_space(self, state: Tuple) -> List[str]:
        return [
            'ACCEPT', 'REJECT', 'SMALL_CONCESSION',
            'LARGE_CONCESSION', 'INNOVATIVE_OFFER'
        ]

    def _choose_action(self, state: Tuple) -> str:
        if random.random() < self.epsilon:
            return random.choice(self._get_action_space(state))
        if state not in self.q_table:
            self.q_table[state] = {
                a: 0.0 for a in self._get_action_space(state)
            }
        return max(self.q_table[state], key=self.q_table[state].get)

    # --- BLOQUE: GENERACION Y EVALUACION ---
    async def generate_offer(self, session: NegotiationSession,
                             context: Dict[str, Any]) -> Offer:
        state = self._get_state(session)
        action = self._choose_action(state)
        base_price = (
            (self.utility_profile.min_acceptable_price
             + self.utility_profile.max_acceptable_price) / 2
        )
        modifiers: Dict[str, float] = {
            'ACCEPT': 1.0, 'REJECT': 1.2,
            'SMALL_CONCESSION': 0.95, 'LARGE_CONCESSION': 0.85,
            'INNOVATIVE_OFFER': 1.1
        }
        return Offer(
            price=base_price * modifiers.get(action, 1.0),
            delivery_time=24.0,
            quality_level=self.utility_profile.required_quality_level,
            proposed_by=self.agent_id,
            rationale="Accion RL: {}".format(action)
        )

    async def evaluate_offer(self, offer: Offer,
                             session: NegotiationSession
                             ) -> Tuple[bool, float, Optional[Offer]]:
        state = self._get_state(session)
        action = self._choose_action(state)
        utility = self.utility_profile.calculate_utility(offer)
        if action == 'ACCEPT' and utility >= 0.5:
            self._update_q_value(state, action, utility * 10, None)
            return True, utility, None
        elif action in ('SMALL_CONCESSION', 'LARGE_CONCESSION'):
            concession = (
                0.1 if action == 'SMALL_CONCESSION' else 0.2
            )
            counter = offer.clone_with_changes(
                price=offer.price * (1 - concession),
                concessions_made=offer.concessions_made + [
                    "RL_{}".format(action)
                ]
            )
            self.episode_history.append({
                'state': state, 'action': action, 'offer': offer
            })
            return False, utility, counter
        else:
            reward = -1.0 if utility > 0.6 else 0.5
            self._update_q_value(state, action, reward, None)
            return False, utility, None

    def _update_q_value(self, state: Tuple, action: str, reward: float,
                        next_state: Optional[Tuple]) -> None:
        if state not in self.q_table:
            self.q_table[state] = {
                a: 0.0 for a in self._get_action_space(state)
            }
        current_q = self.q_table[state][action]
        if next_state and next_state in self.q_table:
            max_next_q = max(self.q_table[next_state].values())
        else:
            max_next_q = 0.0
        self.q_table[state][action] = current_q + self.learning_rate * (
            reward + self.discount * max_next_q - current_q
        )


# ================================================================================
# SECCION 8: ORQUESTADOR DE NEGOCIACIONES
# ================================================================================

class NegotiationOrchestrator:
    def __init__(self, enable_advanced_reputation: bool = True,
                 governor: Optional[ReputationGovernor] = None) -> None:
        # --- BLOQUE: RESOLUCION DE REPUTATION SYSTEM ---
        # Si se pasa un governor, usar su rep_system para consistencia
        if governor and hasattr(governor, 'rep_system'):
            self.reputation_system = governor.rep_system
        else:
            self.reputation_system = ReputationSystem(
                enable_advanced=enable_advanced_reputation
            )
        self.governor = governor or ReputationGovernor(self.reputation_system)
        self.active_sessions: Dict[str, NegotiationSession] = {}
        self.completed_sessions: deque = deque(maxlen=10000)
        self.agents: Dict[str, NegotiationAgent] = {}
        self._pending_queue: Optional[asyncio.Queue] = None
        self.config = GlobalConfig
        self.system_metrics: Dict[str, Any] = {
            'total_negotiations': 0,
            'successful_negotiations': 0,
            'avg_negotiation_time': 0.0
        }

    def _get_queue(self) -> asyncio.Queue:
        """Lazy init de Queue dentro de contexto async."""
        if self._pending_queue is None:
            self._pending_queue = asyncio.Queue()
        return self._pending_queue

    # --- BLOQUE: REGISTRO DE AGENTES ---
    def register_agent(self, agent: NegotiationAgent) -> None:
        self.agents[agent.agent_id] = agent
        self.reputation_system.register_agent(agent.agent_id)
        if hasattr(agent, 'governor'):
            if not agent.governor:
                agent.governor = self.governor
            agent.governor.apply_config_to_agent(agent, agent.agent_id)
        log_event("Agente registrado: {} ({})".format(
            agent.agent_id, type(agent).__name__
        ))

    # --- BLOQUE: INICIACION DE NEGOCIACION ---
    async def initiate_negotiation(self, initiator_id: str,
                                    responder_id: str, domain: str,
                                    item_description: str,
                                    base_terms: Dict[str, Any]
                                    ) -> Optional[NegotiationSession]:
        if initiator_id not in self.agents or responder_id not in self.agents:
            log_event("Agente no encontrado", "ERROR")
            return None
        if len(self.active_sessions) >= self.config.MAX_CONCURRENT_NEGOTIATIONS:
            log_event("Limite de negociaciones concurrentes", "WARN")
            return None
        session = NegotiationSession(
            agent_a_id=initiator_id,
            agent_b_id=responder_id,
            domain=domain,
            item_description=item_description,
            base_terms=base_terms,
            status=NegotiationStatus.ACTIVE,
            max_rounds=self.config.MAX_ROUNDS
        )
        # Asignar timeout desde config
        if hasattr(self.config, 'SESSION_TIMEOUT_SECONDS'):
            session.timeout_seconds = self.config.SESSION_TIMEOUT_SECONDS
        self.active_sessions[session.session_id] = session
        self.system_metrics['total_negotiations'] += 1
        log_event("Negociacion iniciada: {} | {} <-> {}".format(
            session.session_id[:8], initiator_id, responder_id
        ))
        asyncio.create_task(self._run_negotiation(session))
        return session

    # --- BLOQUE: LOOP PRINCIPAL DE NEGOCIACION ---
    async def _run_negotiation(self, session: NegotiationSession) -> None:
        """
        Orquesta la negociacion turn-by-turn.
        NO usa agent.negotiate() para evitar doble-loop.
        Llama generate_offer/evaluate_offer directamente.
        """
        agent_a = self.agents.get(session.agent_a_id)
        agent_b = self.agents.get(session.agent_b_id)
        if not agent_a or not agent_b:
            session.status = NegotiationStatus.REJECTED
            self._finalize_session(session, time.time())
            return
        start_time = time.time()

        # --- BLOQUE: OFERTA INICIAL ---
        try:
            initial_offer = await agent_a.generate_offer(session, {})
            initial_offer.proposed_by = agent_a.agent_id
            initial_offer.proposed_at = datetime.now(timezone.utc)
            session.offers_history.append(initial_offer)
        except Exception as e:
            log_event("Error generando oferta inicial: {}".format(e), "ERROR")
            session.status = NegotiationStatus.REJECTED
            self._finalize_session(session, start_time)
            return

        session.current_round = 1

        # --- BLOQUE: LOOP DE RONDAS ---
        while session.status == NegotiationStatus.ACTIVE:
            if session.current_round > session.max_rounds:
                session.status = NegotiationStatus.REJECTED
                break
            if session.is_expired():
                session.status = NegotiationStatus.EXPIRED
                break
            # Seguridad contra overflow
            if len(session.offers_history) > session.max_rounds * 2 + 5:
                log_event("Overflow de ofertas - corte de seguridad", "WARN")
                session.status = NegotiationStatus.EXPIRED
                break

            last_offer = session.get_last_offer()
            if not last_offer:
                break

            # Determinar evaluador (quien no propuso la ultima oferta)
            if last_offer.proposed_by == agent_a.agent_id:
                evaluator = agent_b
                proposer = agent_a
            else:
                evaluator = agent_a
                proposer = agent_b

            # Actualizar gobernanza del evaluador
            if hasattr(evaluator, 'update_governance'):
                try:
                    evaluator.update_governance()
                except Exception:
                    pass

            # --- BLOQUE: EVALUACION ---
            try:
                accept, utility, counter = await evaluator.evaluate_offer(
                    last_offer, session
                )
            except Exception as e:
                log_event("Error evaluando oferta: {}".format(e), "ERROR")
                session.status = NegotiationStatus.REJECTED
                break

            if accept:
                # --- BLOQUE: ACUERDO ---
                session.final_offer = last_offer
                session.status = NegotiationStatus.ACCEPTED
                if evaluator.role == AgentRole.INITIATOR:
                    session.final_utility_a = utility
                else:
                    session.final_utility_b = utility
                session.agreement_timestamp = datetime.now(timezone.utc)
                self.reputation_system.update_reputation(
                    agent_a.agent_id, 'success', last_offer.price
                )
                self.reputation_system.update_reputation(
                    agent_b.agent_id, 'success', last_offer.price
                )
                log_event("Acuerdo: ${:.2f} | {} rondas".format(
                    last_offer.price, session.current_round
                ))
                break
            elif counter:
                # --- BLOQUE: CONTRAOFERTA ---
                counter.proposed_by = evaluator.agent_id
                counter.proposed_at = datetime.now(timezone.utc)
                session.offers_history.append(counter)
                session.current_round += 1
            else:
                # --- BLOQUE: RECHAZO ---
                session.status = NegotiationStatus.REJECTED
                self.reputation_system.update_reputation(
                    evaluator.agent_id, 'failure', 0
                )
                log_event("Negociacion rechazada por {}".format(
                    evaluator.agent_id
                ))
                break

            await asyncio.sleep(
                0.2 if self.config.IS_TERMUX else 0.5
            )

        # --- BLOQUE: FINALIZACION ---
        self._finalize_session(session, start_time)

    def _finalize_session(self, session: NegotiationSession,
                          start_time: float) -> None:
        """Registra metricas y limpia sesion."""
        negotiation_time = time.time() - start_time
        if session.status == NegotiationStatus.ACCEPTED:
            self.system_metrics['successful_negotiations'] += 1
        else:
            log_event("Negociacion fallida: {}".format(
                session.status.name
            ))
        self.active_sessions.pop(session.session_id, None)
        self.completed_sessions.append(session)
        # Actualizar promedio de tiempo
        total = self.system_metrics['total_negotiations']
        if total > 0:
            prev_avg = self.system_metrics['avg_negotiation_time']
            self.system_metrics['avg_negotiation_time'] = (
                (prev_avg * (total - 1)) + negotiation_time
            ) / total
        else:
            self.system_metrics['avg_negotiation_time'] = negotiation_time

    # --- BLOQUE: REPORTES ---
    def get_system_report(self) -> Dict[str, Any]:
        return {
            "metrics": dict(self.system_metrics),
            "active_sessions": len(self.active_sessions),
            "completed_sessions": len(self.completed_sessions),
            "agents": len(self.agents)
        }

    def get_governance_report(self) -> Dict[str, Any]:
        return {
            "governor_config": self.governor.get_config(),
            "scheduled_changes": self.governor.get_scheduled_changes(),
            "recent_audit": self.governor.get_audit_log(limit=10),
            "system_metrics": dict(self.system_metrics)
        }

    def shutdown(self) -> None:
        """Detiene componentes del orquestador."""
        self.governor.shutdown()
        log_event("NegotiationOrchestrator detenido", "OK")


# ================================================================================
# SECCION 9: API PUBLICA Y COMPATIBILIDAD CON ORQUESTADOR
# ================================================================================

_orchestrator_instance: Optional[NegotiationOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator() -> Optional[NegotiationOrchestrator]:
    """Obtiene la instancia global del orquestador de negociaciones."""
    return _orchestrator_instance


def create_orchestrator(enable_advanced_reputation: bool = True,
                        governor: Optional[ReputationGovernor] = None
                        ) -> NegotiationOrchestrator:
    """Crea y registra la instancia global del orquestador."""
    global _orchestrator_instance
    with _orchestrator_lock:
        if _orchestrator_instance is None:
            _orchestrator_instance = NegotiationOrchestrator(
                enable_advanced_reputation=enable_advanced_reputation,
                governor=governor
            )
            log_event("Orquestador global creado y registrado", "OK")
        return _orchestrator_instance


def init_negotiation_system(enable_advanced: bool = True
                            ) -> NegotiationOrchestrator:
    """
    Inicializa el sistema completo de negociacion.
    Crea orquestador, gobernador y asegura consistencia de rep_system.
    """
    rep_system = ReputationSystem(enable_advanced=enable_advanced)
    governor = ReputationGovernor(
        reputation_system=rep_system,
        ceo_callback=lambda event, data: log_event(
            "CEO notified: {} | {}".format(event, data), "GOV"
        )
    )
    orchestrator = create_orchestrator(
        enable_advanced_reputation=enable_advanced,
        governor=governor
    )
    return orchestrator


# --- BLOQUE: HELPER PARA COROUTINES ---
def _run_coroutine_safely(coro: Any) -> Any:
    """
    Ejecuta una coroutine desde contexto sincrono (Python 3.6+).
    CORREGIDO: Mejor manejo de loops anidados y timeout.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # Ya hay un loop corriendo - usar concurrent.futures para evitar deadlock
        import concurrent.futures
        
        def _run_in_executor() -> Any:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_executor)
            try:
                return future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                log_event("Timeout ejecutando coroutine en thread pool", "ERROR")
                return None
    else:
        # Sin loop corriendo - usar directamente
        if loop is None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        except Exception as e:
            log_event("Error en coroutine: {}".format(e), "ERROR")
            return None



# --- BLOQUE: FUNCIONES PUBLICAS PARA FLUJOENGINE ---
def initiate_negotiation(initiator_id: str, responder_id: str,
                         domain: str, item_description: str,
                         base_terms: Dict[str, Any]
                         ) -> Optional[NegotiationSession]:
    """
    Inicia una negociacion de forma sincrona.
    Wrapper para FlujoEngine que maneja el loop async internamente.
    Retorna siempre NegotiationSession o None (nunca Task).
    
    Si el orquestador no esta inicializado, lo crea automaticamente
    llamando a init_negotiation_system() de forma segura.
    """
    orch = get_orchestrator()
    if not orch:
        with _orchestrator_lock:          # doble verificacion bajo lock
            orch = get_orchestrator()
            if not orch:
                orch = init_negotiation_system(enable_advanced=True)
                log_event(
                    "Orquestador no estaba inicializado - se ha creado automaticamente.",
                    "WARN"
                )
    try:
        coro = orch.initiate_negotiation(
            initiator_id, responder_id, domain,
            item_description, base_terms
        )
        return _run_coroutine_safely(coro)
    except Exception as e:
        log_event("Error iniciando negociacion: {}".format(e), "ERROR")
        return None


def get_system_report() -> Dict[str, Any]:
    """Obtiene reporte del sistema de negociacion."""
    orch = get_orchestrator()
    if not orch:
        return {"error": "orquestador no inicializado"}
    return orch.get_system_report()


def get_ceo_metrics() -> Dict[str, Any]:
    """Expone metricas de negociacion al CEOIA. Funcion sincrona segura."""
    orch = get_orchestrator()
    if not orch:
        return {
            "success_rate": 0.0,
            "avg_wait_time": 0.0,
            "active_sessions": 0,
            "reputation_avg": 0.0,
            "error": "orquestador no inicializado"
        }
    total = orch.system_metrics.get('total_negotiations', 1)
    success = orch.system_metrics.get('successful_negotiations', 0)
    agent_count = max(len(orch.agents), 1)
    rep_sum = sum(
        orch.reputation_system.get_reputation(a) for a in orch.agents
    )
    return {
        "success_rate": success / max(total, 1),
        "avg_wait_time": orch.system_metrics.get('avg_negotiation_time', 0),
        "active_sessions": len(orch.active_sessions),
        "reputation_avg": rep_sum / agent_count,
        "total_negotiations": total,
        "successful_negotiations": success,
        "agent_count": len(orch.agents)
    }


def apply_ceo_directive(directives: Dict[str, Any]) -> Dict[str, Any]:
    """Recibe ajustes del CEOIA. Funcion sincrona segura para FlujoEngine."""
    orch = get_orchestrator()
    result: Dict[str, Any] = {
        "applied": [],
        "failed": [],
        "orchestrator_ready": orch is not None
    }
    if not orch:
        result["error"] = "orchestrator no inicializado"
        return result
    # --- BLOQUE: FRAUD THRESHOLD ---
    if "fraud_threshold" in directives:
        try:
            for agent in orch.agents.values():
                if hasattr(agent, 'fraud_threshold'):
                    agent.fraud_threshold = directives["fraud_threshold"]
            result["applied"].append("fraud_threshold")
        except Exception as e:
            result["failed"].append("fraud_threshold: {}".format(e))
    # --- BLOQUE: ENABLE ADVANCED ---
    if "enable_advanced" in directives:
        try:
            if hasattr(orch.reputation_system, 'enable_advanced'):
                orch.reputation_system.enable_advanced = directives[
                    "enable_advanced"
                ]
            result["applied"].append("enable_advanced")
        except Exception as e:
            result["failed"].append("enable_advanced: {}".format(e))
    # --- BLOQUE: DECAY PARAMS ---
    if "half_life_days" in directives and hasattr(orch, 'governor'):
        try:
            orch.governor.ceo_set_decay_params(
                half_life_days=directives["half_life_days"],
                reason="CEO directive"
            )
            result["applied"].append("half_life_days")
        except Exception as e:
            result["failed"].append("half_life_days: {}".format(e))
    # --- BLOQUE: DECAY MODEL ---
    if "decay_model" in directives and hasattr(orch, 'governor'):
        try:
            orch.governor.ceo_set_decay_params(
                decay_model=directives["decay_model"],
                reason="CEO directive"
            )
            result["applied"].append("decay_model")
        except Exception as e:
            result["failed"].append("decay_model: {}".format(e))
    return result


def register_agent_sync(agent_id: str, role: str = "INITIATOR",
                        min_price: float = 50.0,
                        max_price: float = 150.0) -> bool:
    """Registra un agente ligero de forma sincrona para FlujoEngine."""
    orch = get_orchestrator()
    if not orch:
        return False
    role_enum = (
        AgentRole.INITIATOR if role == "INITIATOR"
        else AgentRole.RESPONDER
    )
    profile = UtilityProfile(
        min_acceptable_price=min_price,
        max_acceptable_price=max_price
    )
    agent = LightweightAgent(
        agent_id, role_enum, profile, orch.reputation_system
    )
    orch.register_agent(agent)
    return True


# Alias para compatibilidad con FlujoEngine
register_agent = register_agent_sync


# ================================================================================
# SECCION 10: ESPERA Y UTILIDADES ASINCRONAS
# ================================================================================

async def _wait_for_completion(session: NegotiationSession) -> None:
    """Espera a que una sesion de negociacion termine con timeout."""
    timeout = 30 if GlobalConfig.IS_TERMUX else 60
    start = time.time()
    while True:
        await asyncio.sleep(0.5)
        if session.status in (
            NegotiationStatus.ACCEPTED,
            NegotiationStatus.REJECTED,
            NegotiationStatus.EXPIRED
        ):
            break
        if time.time() - start > timeout:
            log_event("TIMEOUT FORZADO - CERRANDO SESION", "WARN")
            session.status = NegotiationStatus.EXPIRED
            break
        if len(session.offers_history) > 50:
            log_event("Overflow de negociacion - corte de seguridad", "WARN")
            session.status = NegotiationStatus.EXPIRED
            break


# ================================================================================
# SECCION 11: DEMOSTRACION
# ================================================================================

async def run_negotiation_demo() -> None:
    log_banner("INICIANDO SISTEMA NEGOCIACION - SYMBIOSIS-TERMUX", "GOV")

    orchestrator = init_negotiation_system(enable_advanced=True)

    # --- BLOQUE: PERFILES ---
    profile_buyer = UtilityProfile(
        price_weight=0.5, time_weight=0.2, quality_weight=0.2,
        reputation_weight=0.05, flexibility_weight=0.05,
        min_acceptable_price=50.0, max_acceptable_price=150.0,
        required_quality_level=4
    )
    profile_seller = UtilityProfile(
        price_weight=0.4, time_weight=0.15, quality_weight=0.25,
        reputation_weight=0.1, flexibility_weight=0.1,
        min_acceptable_price=80.0, max_acceptable_price=200.0,
        required_quality_level=3
    )

    # --- BLOQUE: AGENTES ---
    buyer = LightweightAgent(
        "BUYER_001", AgentRole.INITIATOR, profile_buyer,
        orchestrator.reputation_system
    )
    seller = LightweightAgent(
        "SELLER_001", AgentRole.RESPONDER, profile_seller,
        orchestrator.reputation_system
    )
    strategic_buyer = StrategicAgent(
        "STRATEGIC_BUYER", AgentRole.INITIATOR, profile_buyer,
        orchestrator.reputation_system,
        strategy=NegotiationStrategy.COLLABORATIVE,
        reservation_utility=0.6,
        governor=orchestrator.governor
    )
    strategic_seller = StrategicAgent(
        "STRATEGIC_SELLER", AgentRole.RESPONDER, profile_seller,
        orchestrator.reputation_system,
        strategy=NegotiationStrategy.MODERATE,
        reservation_utility=0.55,
        governor=orchestrator.governor
    )

    orchestrator.register_agent(buyer)
    orchestrator.register_agent(seller)
    orchestrator.register_agent(strategic_buyer)
    orchestrator.register_agent(strategic_seller)

    # --- BLOQUE: NEGOCIACIONES ---
    session = await orchestrator.initiate_negotiation(
        "BUYER_001", "SELLER_001", "ride_hailing",
        "Viaje premium", {'distance_km': 15.5}
    )
    if session:
        await _wait_for_completion(session)

    session2 = await orchestrator.initiate_negotiation(
        "STRATEGIC_BUYER", "STRATEGIC_SELLER", "ride_hailing",
        "Viaje Premium Estrategico", {'distance_km': 20.0}
    )
    if session2:
        await _wait_for_completion(session2)

    # --- BLOQUE: REPORTES ---
    log_banner("PERFILES DE REPUTACION + GOBERNANZA", "R")
    for agent_id in [
        "BUYER_001", "SELLER_001",
        "STRATEGIC_BUYER", "STRATEGIC_SELLER"
    ]:
        profile = orchestrator.reputation_system.get_reputation_profile(
            agent_id
        )
        trust_level = (
            orchestrator.reputation_system.get_trust_level(agent_id).name
            if orchestrator.reputation_system.enable_advanced
            else "N/A"
        )
        badges = profile.get('badges', [])
        fraud_threshold = orchestrator.governor.get_effective_fraud_threshold(
            agent_id
        )
        log_event(
            "{}: Score={:.2f} | Nivel={} | "
            "FraudThresh={:.2f} | Badges={}".format(
                agent_id, profile['score'], trust_level,
                fraud_threshold,
                ', '.join(badges) if badges else "Ninguno"
            )
        )

    gov_report = orchestrator.get_governance_report()
    log_event(
        "Config global: enable_advanced={} | decay={}".format(
            gov_report['governor_config'].get('enable_advanced'),
            gov_report['governor_config'].get('decay_model')
        )
    )

    log_banner("RESULTADO FINAL", "R")
    report = orchestrator.get_system_report()
    log_event("Negociaciones totales: {}".format(
        report['metrics']['total_negotiations']
    ))
    log_event("Exitosas: {}".format(
        report['metrics']['successful_negotiations']
    ))


# ================================================================================
# SECCION 12: REGISTRO CEOIA Y PUNTO DE ENTRADA
# ================================================================================

# --- BLOQUE: DECORADOR CEO GOVERNED ---
def ceo_governed(module_name: str = None):
    def decorator(module):
        module.__ceo_governed__ = True
        module.__ceo_registered_at__ = datetime.now(timezone.utc).isoformat()
        try:
            ceo = _find_ceo_instance()
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


def _find_ceo_instance() -> Any:
    """Busca la instancia de CEOIA en los contextos disponibles."""
    try:
        if 'ceoia_instance' in globals():
            return globals()['ceoia_instance']
    except Exception:
        pass
    try:
        main_module = sys.modules.get('__main__')
        if main_module and hasattr(main_module, 'ceoia_instance'):
            return getattr(main_module, 'ceoia_instance')
    except Exception:
        pass
    return None


def _try_ceo_register() -> None:
    """Intenta registrar el modulo con CEOIA."""
    try:
        ceo = _find_ceo_instance()
        if ceo and hasattr(ceo, 'register_module'):
            ceo.register_module(
                name="core_negotiation",
                module_ref=sys.modules[__name__],
                capabilities=["negotiation", "reputation", "governance"]
            )
            log_event("core_negotiation registrado con CEOIA", "OK")
    except Exception as e:
        log_event("CEOIA no disponible: {}".format(e), "DEBUG")


def _auto_register_with_ceo() -> None:
    """Intenta registrar el modulo con CEOIA al cargar."""
    try:
        _try_ceo_register()
    except Exception as e:
        log_event("CEO no disponible aun: {}".format(e), "DEBUG")


_auto_register_with_ceo()


# --- BLOQUE: PUNTO DE ENTRADA ---
if __name__ == "__main__":
    if GlobalConfig.IS_TERMUX:
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        asyncio.run(run_negotiation_demo())
    except AttributeError:
        # Python 3.6 no tiene asyncio.run
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_negotiation_demo())
        loop.close()
    except KeyboardInterrupt:
        log_event("Interrupcion por usuario", "WARN")
    except Exception as e:
        log_event("Error critico: {}".format(e), "ERROR")
        if GlobalConfig.LOG_VERBOSE:
            import traceback
            traceback.print_exc()
    finally:
        # Limpieza del orquestador
        orch = get_orchestrator()
        if orch:
            orch.shutdown()

