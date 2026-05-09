#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ================================================================================
# SECCION 0: METADATOS DEL MODULO
# ================================================================================
"""
PARTE 3/9 - UBER RADAR PRO + API CLIENT (CORREGIDO Y EXPORTABLE)
=================================================================
Sistema de deteccion de demanda en tiempo real con integracion Uber API v1.2
Compatible con Termux/Android - Python 3.6+
Exporta estado y funciones para el nucleo CEOIA.

INCLUYE MODULO DE ENRUTAMIENTO GPS SIMULADO (SECCIONES 12-17)
"""

# ================================================================================
# SECCION 1: IMPORTACIONES UNIFICADAS
# ================================================================================
from __future__ import annotations
import os
import sys
import json
import time
import hmac
import base64
import hashlib
import secrets
import threading
import warnings
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import deque, defaultdict
import urllib.parse
import urllib.request
import ssl
import socket
import math
import random
import heapq

# --- BLOQUE: IMPORTACION SEGURA DE REQUESTS ---
try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _requests = None
    _REQUESTS_AVAILABLE = False

# ================================================================================
# SECCION 2: IMPORTACION DE CONFIGURACION Y ESTRUCTURAS BASE (CON FALLBACK)
# ================================================================================
try:
    from part1_config import (
        GlobalConfig, log_event, log_banner,
        GeoLocation, PriceEstimate, TimeEstimate, RadarOpportunity
    )
    _PART1_AVAILABLE = True
except ImportError:
    _PART1_AVAILABLE = False

    # --- BLOQUE: FALLBACK GLOBALCONFIG ---
    class GlobalConfig:
        IS_TERMUX = True
        LOG_VERBOSE = True

    # --- BLOQUE: FALLBACK GEOLOCATION ---
    @dataclass
    class GeoLocation:
        latitude: float
        longitude: float
        def to_dict(self) -> Dict[str, float]:
            return {"latitude": self.latitude, "longitude": self.longitude}
        def is_valid(self) -> bool:
            return (-90 <= self.latitude <= 90) and (-180 <= self.longitude <= 180)
        def distance_to(self, other: 'GeoLocation') -> float:
            R = 6371.0
            lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
            lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c

    # --- BLOQUE: FALLBACK PRICEESTIMATE ---
    @dataclass
    class PriceEstimate:
        product_id: str
        display_name: str
        estimate: str
        low_estimate: float = 0.0
        high_estimate: float = 0.0
        surge_multiplier: float = 1.0
        duration: int = 0
        distance: float = 0.0
        @property
        def is_surge(self) -> bool:
            return self.surge_multiplier > 1.0
        @property
        def average_estimate(self) -> float:
            return (self.low_estimate + self.high_estimate) / 2

    # --- BLOQUE: FALLBACK TIMEESTIMATE ---
    @dataclass
    class TimeEstimate:
        product_id: str
        display_name: str
        estimate: int

    # --- BLOQUE: FALLBACK RADAROPPORTUNITY ---
    @dataclass
    class RadarOpportunity:
        opportunity_id: str
        timestamp: datetime
        zone_id: str
        zone_name: str
        location: GeoLocation
        demand_score: float
        supply_count: int
        request_count: int
        avg_fare: float
        surge_multiplier: float
        estimated_earnings: float
        hourly_rate_potential: float
        avg_pickup_time: int
        avg_trip_duration: int
        time_to_hotspot: int
        priority_score: float
        predicted_demand_30min: float
        prediction_confidence: float
        recommendation: str
        def to_dict(self) -> Dict[str, Any]:
            return {
                "opportunity_id": self.opportunity_id,
                "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
                "zone_id": self.zone_id,
                "zone_name": self.zone_name,
                "location": self.location.to_dict() if hasattr(self.location, 'to_dict') else asdict(self.location),
                "demand_score": self.demand_score,
                "supply_count": self.supply_count,
                "request_count": self.request_count,
                "avg_fare": self.avg_fare,
                "surge_multiplier": self.surge_multiplier,
                "estimated_earnings": self.estimated_earnings,
                "hourly_rate_potential": self.hourly_rate_potential,
                "avg_pickup_time": self.avg_pickup_time,
                "avg_trip_duration": self.avg_trip_duration,
                "time_to_hotspot": self.time_to_hotspot,
                "priority_score": self.priority_score,
                "predicted_demand_30min": self.predicted_demand_30min,
                "prediction_confidence": self.prediction_confidence,
                "recommendation": self.recommendation
            }

    # --- BLOQUE: FALLBACK LOGGING ---
    def log_event(text: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print("[{}] [{}] {}".format(timestamp, level, text), flush=True)

    def log_banner(title: str, icon: str = ""):
        log_event("{}\n{} {}\n{}".format("="*40, icon, title, "="*40))

# ================================================================================
# SECCION 3: CONFIGURACION DE CREDENCIALES UBER (VALIDA ENTORNO + SANDBOX)
# ================================================================================
class UberConfig:
    """Configuracion centralizada con validacion flexible y modo sandbox para Termux."""
    SANDBOX_BASE = "https://sandbox-api.uber.com/v1.2"
    PRODUCTION_BASE = "https://api.uber.com/v1.2"
    AUTH_BASE = "https://auth.uber.com/oauth/v2"
    REQUIRED_SCOPES = ["request", "history", "profile", "places", "ride_widgets"]
    SANDBOX_CLIENT_ID = "sandbox_client_id_dev"
    SANDBOX_CLIENT_SECRET = "sandbox_secret_dev_12345"
    SANDBOX_TOKEN = "sandbox_token_dev_abcdef"

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        # --- BLOQUE: INICIALIZACION ---
        self.config_override = config_override or {}
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.server_token: Optional[str] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.redirect_uri: str = ""
        self.sandbox_mode: bool = False
        self.base_url: str = ""
        self.is_fallback_active: bool = False
        self._load_from_env()
        self._apply_overrides()
        self._validate_with_fallback()
        mode = "SANDBOX_FALLBACK" if self.is_fallback_active else ("SANDBOX" if self.sandbox_mode else "PRODUCCION")
        log_event("UberConfig: modo={}, fallback={}".format(mode, self.is_fallback_active), "CONFIG")

    def _load_from_env(self) -> None:
        # --- BLOQUE: CARGA DE ENTORNO ---
        self.client_id = os.getenv("UBER_CLIENT_ID")
        self.client_secret = os.getenv("UBER_CLIENT_SECRET")
        self.server_token = os.getenv("UBER_SERVER_TOKEN")
        self.access_token = os.getenv("UBER_ACCESS_TOKEN")
        self.refresh_token = os.getenv("UBER_REFRESH_TOKEN")
        self.redirect_uri = os.getenv("UBER_REDIRECT_URI", "http://localhost:8989/callback")
        sandbox_env = os.getenv("UBER_SANDBOX", "true").lower()
        self.sandbox_mode = sandbox_env in ("true", "1", "yes", "on")

    def _apply_overrides(self) -> None:
        # --- BLOQUE: APLICACION DE OVERRIDES ---
        override_map = {
            "client_id": "client_id", "client_secret": "client_secret",
            "server_token": "server_token", "access_token": "access_token",
            "refresh_token": "refresh_token", "redirect_uri": "redirect_uri",
            "sandbox_mode": "sandbox_mode", "base_url": "base_url"
        }
        for env_key, attr_key in override_map.items():
            if env_key in self.config_override:
                setattr(self, attr_key, self.config_override[env_key])

    def _validate_with_fallback(self) -> None:
        # --- BLOQUE: VALIDACION Y FALLBACK ---
        missing = []
        if not self.client_id:
            missing.append("UBER_CLIENT_ID")
        if not self.client_secret:
            missing.append("UBER_CLIENT_SECRET")
        has_tokens = bool(self.access_token or self.server_token)
        if not has_tokens:
            missing.append("UBER_ACCESS_TOKEN o UBER_SERVER_TOKEN")
        
        if self.sandbox_mode or not missing:
            self.base_url = self.SANDBOX_BASE if self.sandbox_mode else self.PRODUCTION_BASE
            if missing and not self.is_fallback_active:
                log_event("Activando fallback sandbox: faltan {}".format(", ".join(missing)), "WARN")
                self.is_fallback_active = True
            if self.is_fallback_active:
                self.client_id = self.client_id or self.SANDBOX_CLIENT_ID
                self.client_secret = self.client_secret or self.SANDBOX_CLIENT_SECRET
                self.access_token = self.access_token or self.SANDBOX_TOKEN
                self.server_token = self.server_token or self.SANDBOX_TOKEN
                self.base_url = self.SANDBOX_BASE
        elif missing:
            raise ValueError(
                "Faltan credenciales requeridas: {}. ".format(", ".join(missing)) +
                "Para desarrollo en Termux, establezca UBER_SANDBOX=true " +
                "o proporcione tokens reales en variables de entorno."
            )
        else:
            self.base_url = self.PRODUCTION_BASE

    def get_auth_headers(self) -> Dict[str, str]:
        # --- BLOQUE: CONSTRUCCION DE HEADERS ---
        headers = {
            "Content-Type": "application/json",
            "Accept-Language": "en_US",
            "User-Agent": "Symbiosis-Radar/1.0 (Termux)"
        }
        if self.is_fallback_active:
            headers["X-Sandbox-Mode"] = "true"
            headers["X-Fallback-Active"] = "true"
        if self.access_token:
            headers["Authorization"] = "Bearer {}".format(self.access_token)
        elif self.server_token:
            headers["Authorization"] = "Token {}".format(self.server_token)
        else:
            headers["Authorization"] = "Bearer {}".format(self.SANDBOX_TOKEN)
        return headers

    def is_production_ready(self) -> bool:
        return not self.is_fallback_active and not self.sandbox_mode and bool(
            self.client_id and self.client_secret and (self.access_token or self.server_token)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sandbox_mode": self.sandbox_mode,
            "is_fallback_active": self.is_fallback_active,
            "base_url": self.base_url,
            "redirect_uri": self.redirect_uri,
            "production_ready": self.is_production_ready()
        }

# ================================================================================
# SECCION 4: EXCEPCIONES PERSONALIZADAS
# ================================================================================
class RadarError(Exception):
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code

class AuthenticationError(RadarError):
    def __init__(self, message: str = "Autenticacion fallida"):
        super().__init__(message, code="AUTH_ERROR")

class PermissionError(RadarError):
    def __init__(self, message: str = "Permiso denegado"):
        super().__init__(message, code="PERM_ERROR")

class SurgePricingError(RadarError):
    def __init__(self, message: str = "Surge pricing activo"):
        super().__init__(message, code="SURGE_ERROR")

class ValidationError(RadarError):
    def __init__(self, message: str = "Datos invalidos"):
        super().__init__(message, code="VALID_ERROR")

class RateLimitError(RadarError):
    def __init__(self, message: str = "Rate limit excedido", retry_after: Optional[int] = None):
        super().__init__(message, code="RATE_LIMIT")
        self.retry_after = retry_after

class TimeoutError(RadarError):
    def __init__(self, message: str = "Timeout de conexion"):
        super().__init__(message, code="TIMEOUT")

class ConnectionError(RadarError):
    def __init__(self, message: str = "Error de conexion"):
        super().__init__(message, code="CONN_ERROR")

class APIError(RadarError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message, code="API_ERROR")
        self.status_code = status_code

# ================================================================================
# SECCION 5: CLIENTE API UBER - CONEXION REAL CON FALLBACK TERMUX
# ================================================================================
class UberAPIClient:
    def __init__(self, config: UberConfig, timeout: int = 30, max_retries: int = 3):
        # --- BLOQUE: INICIALIZACION ---
        self.config = config
        self.timeout = timeout
        self.max_retries = max_retries
        self._request_times: deque = deque(maxlen=100)
        self._rate_lock = threading.RLock()
        self.max_requests_per_minute = 60
        self._products_cache: Dict[str, Tuple[List[Any], float]] = {}
        self._cache_ttl = 300
        self._last_error: Optional[Exception] = None

    def _check_rate_limit(self) -> bool:
        # --- BLOQUE: VALIDACION DE RATE LIMIT ---
        with self._rate_lock:
            now = time.time()
            while self._request_times and (now - self._request_times[0]) > 60.0:
                self._request_times.popleft()
            if len(self._request_times) >= self.max_requests_per_minute:
                return False
            self._request_times.append(now)
            return True

    def _wait_for_rate_limit(self) -> None:
        # --- BLOQUE: ESPERA ACTIVA DE RATE LIMIT ---
        attempts = 0
        while not self._check_rate_limit():
            wait_time = min(2 ** attempts, 10)
            log_event("Rate limit: esperando {}s".format(wait_time), "RATELIMIT")
            time.sleep(wait_time)
            attempts += 1
            if attempts >= 5:
                raise RateLimitError("No se pudo obtener slot de rate limit despues de 5 intentos")

    def _make_request(self, method: str, endpoint: str,
                      params: Optional[Dict] = None, data: Optional[Dict] = None,
                      timeout: Optional[int] = None) -> Dict[str, Any]:
        # --- BLOQUE: ROUTING DE REQUEST ---
        timeout = timeout or self.timeout
        self._wait_for_rate_limit()
        url = "{}{}".format(self.config.base_url, endpoint)
        headers = self.config.get_auth_headers()
        if _REQUESTS_AVAILABLE:
            return self._make_request_requests(method, url, params, data, headers, timeout)
        return self._make_request_urllib(method, url, params, data, headers, timeout)

    def _make_request_requests(self, method: str, url: str,
                               params: Optional[Dict], data: Optional[Dict],
                               headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
        # --- BLOQUE: REQUEST CON LIBRERIA EXTERNA ---
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = _requests.request(
                    method=method.upper(), url=url, params=params,
                    json=data if method.upper() in ("POST", "PUT", "PATCH") else None,
                    headers=headers, timeout=timeout
                )
                self._handle_http_status(response.status_code, response)
                return response.json() if response.content else {}
            except _requests.exceptions.Timeout:
                last_exception = TimeoutError("Timeout en intento {}".format(attempt + 1))
            except _requests.exceptions.ConnectionError:
                last_exception = ConnectionError("Error de conexion en intento {}".format(attempt + 1))
            except _requests.exceptions.RequestException as e:
                status = getattr(e, "response", None)
                code = status.status_code if status else None
                last_exception = APIError("Error HTTP: {}".format(e), code)
            except json.JSONDecodeError as e:
                last_exception = APIError("Error parseando JSON: {}".format(e))
            time.sleep(1.0 * (attempt + 1))
        raise last_exception or APIError("Error desconocido en request")

    def _make_request_urllib(self, method: str, url: str,
                             params: Optional[Dict], data: Optional[Dict],
                             headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
        # --- BLOQUE: REQUEST CON STDLIB URLLIB ---
        query_url = url
        if params:
            query_url += "?" + urllib.parse.urlencode(params)
        req_data = None
        if method.upper() in ("POST", "PUT", "PATCH") and data is not None:
            req_data = json.dumps(data).encode("utf-8")
            headers["Content-Length"] = str(len(req_data))
        req = urllib.request.Request(query_url, data=req_data, headers=headers, method=method.upper())
        context = ssl._create_unverified_context()
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
                    content = response.read().decode("utf-8")
                    self._handle_http_status_urllib(response.status, dict(response.headers), content)
                    return json.loads(content) if content else {}
            except urllib.error.HTTPError as e:
                content = e.read().decode("utf-8") if e.fp else ""
                self._handle_http_status_urllib(e.code, dict(e.headers), content)
                last_exception = APIError("HTTP {}: {}".format(e.code, e.reason), e.code)
            except urllib.error.URLError as e:
                last_exception = ConnectionError("URL error: {}".format(e.reason))
            except json.JSONDecodeError as e:
                last_exception = APIError("Error parseando JSON: {}".format(e))
            except Exception as e:
                last_exception = APIError("Error inesperado: {}".format(e))
            time.sleep(1.0 * (attempt + 1))
        raise last_exception or APIError("Error desconocido en request urllib")

    def _handle_http_status(self, status: int, response) -> None:
        # --- BLOQUE: MANEJO DE STATUS CODES (REQUESTS) ---
        if status == 401:
            raise AuthenticationError("Token invalido, expirado o credenciales incorrectas")
        elif status == 403:
            raise PermissionError("Acceso denegado: verificar scopes y permisos de la aplicacion")
        elif status == 409:
            try:
                error_data = response.json() if hasattr(response, "json") else {}
                raise SurgePricingError(error_data.get("message", "Surge pricing activo en esta zona"))
            except (json.JSONDecodeError, AttributeError):
                raise SurgePricingError("Surge pricing activo")
        elif status == 422:
            raise ValidationError("Parametros invalidos o datos mal formados en la request")
        elif status == 429:
            retry_after = None
            if hasattr(response, "headers") and "Retry-After" in response.headers:
                retry_after = int(response.headers["Retry-After"])
            raise RateLimitError("Rate limit de API excedido", retry_after)
        elif status >= 500:
            raise APIError("Error interno del servidor Uber: {}".format(status), status)

    def _handle_http_status_urllib(self, status: int, headers: Dict, content: str) -> None:
        # --- BLOQUE: MANEJO DE STATUS CODES (URLLIB) ---
        if status == 401:
            raise AuthenticationError("Token invalido, expirado o credenciales incorrectas")
        elif status == 403:
            raise PermissionError("Acceso denegado: verificar scopes y permisos de la aplicacion")
        elif status == 409:
            try:
                error_data = json.loads(content) if content else {}
                raise SurgePricingError(error_data.get("message", "Surge pricing activo en esta zona"))
            except json.JSONDecodeError:
                raise SurgePricingError("Surge pricing activo")
        elif status == 422:
            raise ValidationError("Parametros invalidos o datos mal formados en la request")
        elif status == 429:
            retry_after = int(headers.get("Retry-After", 0)) or None
            raise RateLimitError("Rate limit de API excedido", retry_after)
        elif status >= 500:
            raise APIError("Error interno del servidor Uber: {}".format(status), status)

    def get_products(self, location: GeoLocation) -> List[Dict]:
        # --- BLOQUE: CONSULTA DE PRODUCTOS ---
        cache_key = "{:.4f},{:.4f}".format(location.latitude, location.longitude)
        if cache_key in self._products_cache:
            products, timestamp = self._products_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return products
        params = {"latitude": location.latitude, "longitude": location.longitude}
        data = self._make_request("GET", "/products", params=params)
        products = data.get("products", [])
        self._products_cache[cache_key] = (products, time.time())
        return products

    def get_price_estimates(self, start: GeoLocation, end: GeoLocation) -> List[PriceEstimate]:
        # --- BLOQUE: CONSULTA DE ESTIMACIONES DE PRECIO ---
        params = {
            "start_latitude": start.latitude, "start_longitude": start.longitude,
            "end_latitude": end.latitude, "end_longitude": end.longitude
        }
        data = self._make_request("GET", "/estimates/price", params=params)
        estimates = []
        for est in data.get("prices", []):
            estimate_str = est.get("estimate", "$0-0")
            low, high = 0.0, 0.0
            try:
                clean = estimate_str.replace("$", "").replace("EUR", "").replace("GBP", "").strip()
                if "-" in clean:
                    parts = clean.split("-")
                    low = float(parts[0].strip())
                    high = float(parts[1].strip())
                else:
                    low = high = float(clean)
            except (ValueError, IndexError, AttributeError):
                log_event("Warning: no se pudo parsear estimate '{}'".format(estimate_str), "WARN")
            estimates.append(PriceEstimate(
                product_id=est.get("product_id", ""),
                display_name=est.get("display_name", "Unknown"),
                estimate=estimate_str,
                low_estimate=low, high_estimate=high,
                surge_multiplier=est.get("surge_multiplier", 1.0),
                duration=est.get("duration", 0), distance=est.get("distance", 0.0)
            ))
        return estimates

    def get_time_estimates(self, location: GeoLocation) -> List[TimeEstimate]:
        # --- BLOQUE: CONSULTA DE ESTIMACIONES DE TIEMPO ---
        params = {"start_latitude": location.latitude, "start_longitude": location.longitude}
        data = self._make_request("GET", "/estimates/time", params=params)
        return [
            TimeEstimate(
                product_id=t.get("product_id", ""),
                display_name=t.get("display_name", "Unknown"),
                estimate=t.get("estimate", 0)
            )
            for t in data.get("times", [])
        ]

    def clear_cache(self) -> None:
        with self._rate_lock:
            self._products_cache.clear()
            self._request_times.clear()
        log_event("Cache de UberAPIClient limpiado", "CACHE")

    def get_last_error(self) -> Optional[Exception]:
        return self._last_error

# ================================================================================
# SECCION 6: SISTEMA DE ZONAS INTELIGENTE
# ================================================================================
class ZoneSystem:
    def __init__(self, api_client: UberAPIClient):
        # --- BLOQUE: INICIALIZACION ---
        self.api = api_client
        self.zones: Dict[str, Dict] = {}
        self._zone_lock = threading.RLock()
        self.zone_centers = {
            "z1_albrook": GeoLocation(8.9850, -79.5200),
            "z2_arraijan": GeoLocation(8.8800, -79.7600),
            "z3_chorrera": GeoLocation(8.8750, -79.7850),
            "z4_san_carlos": GeoLocation(8.8850, -79.8000),
            "z5_veracruz": GeoLocation(8.8550, -79.8200),
            "z6_costa_del_este": GeoLocation(9.0000, -79.4800),
            "z7_panama_pacifico": GeoLocation(8.9167, -79.6000),
        }
        self.typical_destinations = {
            "z1_albrook": GeoLocation(8.9950, -79.5100),
            "z2_arraijan": GeoLocation(8.8900, -79.7500),
            "z3_chorrera": GeoLocation(8.8850, -79.7750),
            "z4_san_carlos": GeoLocation(8.8950, -79.7900),
            "z5_veracruz": GeoLocation(8.8650, -79.8100),
            "z6_costa_del_este": GeoLocation(9.0100, -79.4700),
            "z7_panama_pacifico": GeoLocation(8.9267, -79.5900),
        }

    def scan_zone(self, zone_id: str) -> Dict[str, Any]:
        # --- BLOQUE: ESCANEO INDIVIDUAL DE ZONA ---
        center = self.zone_centers.get(zone_id)
        if not center:
            raise ValueError("Zona desconocida: {}".format(zone_id))
        destination = self.typical_destinations.get(zone_id, center)
        try:
            products = self.api.get_products(center)
            price_estimates = self.api.get_price_estimates(center, destination)
            time_estimates = self.api.get_time_estimates(center)
            demand_metrics = self._calculate_demand_metrics(products, price_estimates, time_estimates)
            zone_data = {
                "zone_id": zone_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "center": asdict(center),
                "products_available": len(products),
                "demand_metrics": demand_metrics
            }
            with self._zone_lock:
                self.zones[zone_id] = zone_data
            return zone_data
        except Exception as e:
            return {
                "zone_id": zone_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "available": False
            }

    def _calculate_demand_metrics(self, products: List[Dict],
                                  price_estimates: List[PriceEstimate],
                                  time_estimates: List[TimeEstimate]) -> Dict[str, Any]:
        # --- BLOQUE: CALCULO DE METRICAS DE DEMANDA ---
        if not price_estimates or not time_estimates:
            return {"demand_score": 0.0, "supply_level": "unknown", "surge_detected": False}
        surge_products = [pe for pe in price_estimates if getattr(pe, 'surge_multiplier', 1.0) > 1.0]
        surge_detected = len(surge_products) > 0
        max_surge = max((getattr(pe, 'surge_multiplier', 1.0) for pe in surge_products), default=1.0)
        avg_eta = sum(getattr(te, 'estimate', 300) for te in time_estimates) / len(time_estimates)
        
        if avg_eta < 180:
            supply_level = "high"
            demand_score = 3.0
        elif avg_eta < 300:
            supply_level = "medium"
            demand_score = 5.0
        elif avg_eta < 480:
            supply_level = "low"
            demand_score = 7.0
        else:
            supply_level = "critical"
            demand_score = 9.0
            
        if surge_detected:
            demand_score = min(10.0, demand_score * max_surge)
        valid_estimates = [pe for pe in price_estimates if hasattr(pe, 'low_estimate') and hasattr(pe, 'high_estimate')]
        avg_fare = sum((pe.low_estimate + pe.high_estimate) / 2 for pe in valid_estimates) / len(valid_estimates) if valid_estimates else 0.0
        return {
            "demand_score": round(demand_score, 2),
            "supply_level": supply_level,
            "surge_detected": surge_detected,
            "max_surge_multiplier": max_surge,
            "average_eta_seconds": int(avg_eta),
            "average_eta_min": int(avg_eta // 60),
            "average_fare": round(avg_fare, 2),
            "products_count": len(products),
            "price_estimates_count": len(price_estimates)
        }

    def find_hotspots(self, min_demand_score: float = 7.0) -> List[Dict]:
        # --- BLOQUE: BUSQUEDA DE HOTSPOTS ---
        hotspots = []
        with self._zone_lock:
            for zone_id, data in self.zones.items():
                metrics = data.get("demand_metrics", {})
                if metrics.get("demand_score", 0) >= min_demand_score:
                    hotspots.append({"zone_id": zone_id, "center": data.get("center"), **metrics})
        return sorted(hotspots, key=lambda x: x.get("demand_score", 0), reverse=True)

# ================================================================================
# SECCION 7: RADAR PRO - SISTEMA COMPLETO (CON EXPORTACION DE ESTADO)
# ================================================================================
class UberRadarPro:
    def __init__(self, config: Optional[UberConfig] = None):
        # --- BLOQUE: INICIALIZACION ---
        self.config = config or UberConfig()
        self.api = UberAPIClient(self.config)
        self.zones = ZoneSystem(self.api)
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._opportunities: deque = deque(maxlen=100)
        self._opportunity_lock = threading.RLock()
        self._on_opportunity: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self.scan_interval = 60
        self.hot_zones_only = False
        self.min_demand_score = 6.0

    def start_monitoring(self):
        # --- BLOQUE: INICIO DE MONITOREO ---
        if self._running:
            return
        self._running = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()

    def stop_monitoring(self):
        # --- BLOQUE: DETENCION DE MONITOREO ---
        self._running = False
        if self._scan_thread:
            self._scan_thread.join(timeout=5)

    def _scan_loop(self):
        # --- BLOQUE: LOOP DE ESCANEO CONTINUO ---
        while self._running:
            try:
                self.perform_full_scan()
            except Exception as e:
                if self._on_error:
                    self._on_error(e)
            time.sleep(self.scan_interval)

    def perform_full_scan(self) -> List[RadarOpportunity]:
        # --- BLOQUE: ESCANEO COMPLETO DE ZONAS ---
        opportunities = []
        for zone_id in self.zones.zone_centers.keys():
            try:
                zone_data = self.zones.scan_zone(zone_id)
                if "error" in zone_data:
                    continue
                metrics = zone_data.get("demand_metrics", {})
                demand_score = metrics.get("demand_score", 0)
                if demand_score < self.min_demand_score and self.hot_zones_only:
                    continue
                opp = self._create_opportunity(zone_data)
                opportunities.append(opp)
                with self._opportunity_lock:
                    self._opportunities.append(opp)
                if self._on_opportunity:
                    self._on_opportunity(opp)
            except Exception as e:
                if self._on_error:
                    self._on_error(e)
        return opportunities

    def _create_opportunity(self, zone_data: Dict) -> RadarOpportunity:
        # --- BLOQUE: GENERACION DE OPORTUNIDAD ---
        metrics = zone_data.get("demand_metrics", {})
        avg_fare = metrics.get("average_fare", 0)
        surge = metrics.get("max_surge_multiplier", 1.0)
        base_trips_per_hour = 3
        supply_factor = {"high": 1.0, "medium": 0.8, "low": 0.6, "critical": 0.4}.get(
            metrics.get("supply_level", "medium"), 0.8)
        adjusted_trips = base_trips_per_hour * supply_factor * surge
        hourly_potential = avg_fare * adjusted_trips
        priority = (metrics.get("demand_score", 0) * 10 + (surge - 1) * 50 + min(hourly_potential, 50))
        center = zone_data.get("center", {})
        location = GeoLocation(
            latitude=center.get("latitude", 0),
            longitude=center.get("longitude", 0)
        )
        timestamp_raw = zone_data.get("timestamp", datetime.now(timezone.utc).isoformat())
        try:
            timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(timezone.utc)
        return RadarOpportunity(
            opportunity_id="opp_{}_{}".format(zone_data['zone_id'], int(time.time())),
            timestamp=timestamp,
            zone_id=zone_data["zone_id"],
            zone_name=zone_data["zone_id"].replace("_", " ").title(),
            location=location,
            demand_score=metrics.get("demand_score", 0),
            supply_count=0,
            request_count=0,
            avg_fare=avg_fare,
            surge_multiplier=surge,
            estimated_earnings=avg_fare * 0.75,
            hourly_rate_potential=hourly_potential,
            avg_pickup_time=metrics.get("average_eta_seconds", 300),
            avg_trip_duration=900,
            time_to_hotspot=0,
            priority_score=round(priority, 2),
            predicted_demand_30min=0.0,
            prediction_confidence=0.0,
            recommendation=""
        )

    def get_best_opportunities(self, top_n: int = 5) -> List[RadarOpportunity]:
        with self._opportunity_lock:
            sorted_opps = sorted(self._opportunities, key=lambda x: x.priority_score, reverse=True)
            return sorted_opps[:top_n]

    def get_zone_recommendation(self) -> Optional[Dict]:
        # --- BLOQUE: RECOMENDACION DE ZONA ---
        hotspots = self.zones.find_hotspots(min_demand_score=self.min_demand_score)
        if not hotspots:
            return None
        best = hotspots[0]
        return {
            "recommended_zone": best["zone_id"],
            "demand_score": best["demand_score"],
            "surge_multiplier": best.get("max_surge_multiplier", 1.0),
            "estimated_pickup_time_min": best.get("average_eta_min", 5),
            "reason": "Alta demanda ({}/10) con surge x{}".format(best['demand_score'], best.get('max_surge_multiplier', 1.0))
        }

    def set_opportunity_callback(self, callback: Callable[[RadarOpportunity], None]):
        self._on_opportunity = callback

    def set_error_callback(self, callback: Callable[[Exception], None]):
        self._on_error = callback

    def export_estado(self) -> Dict[str, Any]:
        # --- BLOQUE: EXPORTACION DE ESTADO INTERNO ---
        with self._opportunity_lock:
            opps = list(self._opportunities)[-20:]
        zones_data = {}
        with self.zones._zone_lock:
            for zid, zdata in self.zones.zones.items():
                zones_data[zid] = {
                    "timestamp": zdata.get("timestamp"),
                    "demand_metrics": zdata.get("demand_metrics", {}),
                    "available": "error" not in zdata
                }
        return {
            "running": self._running,
            "scan_interval": self.scan_interval,
            "hot_zones_only": self.hot_zones_only,
            "min_demand_score": self.min_demand_score,
            "ultimas_oportunidades": [opp.to_dict() for opp in opps],
            "estado_zonas": zones_data,
            "recomendacion_actual": self.get_zone_recommendation(),
            "config": {
                "sandbox_mode": self.config.sandbox_mode,
                "base_url": self.config.base_url
            }
        }

    def set_scan_interval(self, seconds: int) -> None:
        self.scan_interval = max(10, seconds)

    def set_min_demand_score(self, score: float) -> None:
        self.min_demand_score = max(0, min(10, score))

    def set_hot_zones_only(self, enabled: bool) -> None:
        self.hot_zones_only = enabled

    def force_scan(self) -> List[RadarOpportunity]:
        return self.perform_full_scan()

# ================================================================================
# SECCION 8: SINGLETON GLOBAL PARA EL NUCLEO
# ================================================================================
_radar_instance: Optional[UberRadarPro] = None
_radar_lock = threading.Lock()

def get_radar_instance() -> UberRadarPro:
    global _radar_instance
    with _radar_lock:
        if _radar_instance is None:
            try:
                _radar_instance = UberRadarPro()
            except Exception as e:
                log_event("Error creando radar: {}".format(e), "ERROR")
                _radar_instance = None
                raise
        return _radar_instance

def exportar_estado_radar() -> Dict[str, Any]:
    radar = get_radar_instance()
    return radar.export_estado()

def iniciar_radar() -> None:
    radar = get_radar_instance()
    radar.start_monitoring()

def detener_radar() -> None:
    radar = get_radar_instance()
    radar.stop_monitoring()

def forzar_escaneo_radar() -> List[Dict]:
    radar = get_radar_instance()
    opps = radar.force_scan()
    return [opp.to_dict() for opp in opps]

def establecer_intervalo_escaneo(segundos: int) -> None:
    radar = get_radar_instance()
    radar.set_scan_interval(segundos)

def establecer_umbral_demanda(puntaje: float) -> None:
    radar = get_radar_instance()
    radar.set_min_demand_score(puntaje)

def obtener_recomendacion_zona() -> Optional[Dict]:
    radar = get_radar_instance()
    return radar.get_zone_recommendation()

# ================================================================================
# SECCION 9: REGISTRO CEOIA Y GOBERNANZA
# ================================================================================
def ceo_governed(module_name: str = None):
    # --- BLOQUE: DECORADOR CEO GOVERNED ---
    def decorator(module):
        module.__ceo_governed__ = True
        module.__ceo_registered_at__ = datetime.now(timezone.utc).isoformat()
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

def _auto_register_with_ceo() -> None:
    # --- BLOQUE: AUTO REGISTRO AL CARGAR ---
    try:
        ceo = None
        if 'ceoia_instance' in globals():
            ceo = globals()['ceoia_instance']
        elif hasattr(sys.modules.get('__main__'), 'ceoia_instance'):
            ceo = getattr(sys.modules['__main__'], 'ceoia_instance')
        if ceo and hasattr(ceo, 'register_module'):
            ceo.register_module(
                name="core_radar",
                module_ref=sys.modules[__name__],
                capabilities=["radar", "routing", "demand_detection", "gps"]
            )
            log_event("core_radar registrado con CEOIA", "OK")
    except Exception as e:
        log_event("CEOIA no disponible para radar: {}".format(e), "DEBUG")

_auto_register_with_ceo()

# ================================================================================
# SECCION 10: FUNCIONES DE DEMOSTRACION Y PRUEBAS
# ================================================================================
def demo_radar():
    # --- BLOQUE: CONFIGURACION DE DEMO ---
    print("=" * 80)
    print("UBER RADAR PRO v3.0 - Demostracion")
    print("=" * 80)

    missing_vars = [v for v in ["UBER_CLIENT_ID", "UBER_CLIENT_SECRET", "UBER_ACCESS_TOKEN"] if not os.getenv(v)]
    if missing_vars:
        print("\n[WARN] Faltan variables de entorno: {}".format(", ".join(missing_vars)))
        print("\nPara usar el radar real, configura:")
        print("  export UBER_CLIENT_ID='tu_client_id'")
        print("  export UBER_CLIENT_SECRET='tu_client_secret'")
        print("  export UBER_ACCESS_TOKEN='tu_access_token'")
        print("  export UBER_SANDBOX='true'")
        print("\n[INFO] Ejecutando en modo SIMULADO con datos de prueba...")
        _run_demo_simulation()
        return

    # --- BLOQUE: EJECUCION REAL ---
    try:
        radar = get_radar_instance()
        print("\n[OK] Configuracion valida")
        print("   Modo: {}".format('SANDBOX' if radar.config.sandbox_mode else 'PRODUCCION'))
        print("   Endpoint: {}".format(radar.config.base_url))

        def on_opportunity(opp):
            print("\n[OPPORTUNITY] NUEVA OPORTUNIDAD DETECTADA")
            print("   Zona: {}".format(opp.zone_name))
            print("   Score de demanda: {}/10".format(opp.demand_score))
            print("   Surge: x{}".format(opp.surge_multiplier))
            print("   Tarifa promedio: ${:.2f}".format(opp.avg_fare))
            print("   Potencial/hora: ${:.2f}".format(opp.hourly_rate_potential))
            print("   Prioridad: {}".format(opp.priority_score))

        radar.set_opportunity_callback(on_opportunity)
        print("\n[SCAN] Iniciando escaneo manual de zonas...")
        for zone_id in list(radar.zones.zone_centers.keys())[:3]:
            print("\nEscaneando {}...".format(zone_id))
            zone_data = radar.zones.scan_zone(zone_id)
            if "error" in zone_data:
                print("    [WARN] Error: {}".format(zone_data['error']))
            else:
                metrics = zone_data.get("demand_metrics", {})
                print("    [OK] Productos: {}".format(metrics.get('products_count', 0)))
                print("    [METRIC] Score demanda: {}/10".format(metrics.get('demand_score', 0)))
                print("    [SURGE] Detectado: {}".format(metrics.get('surge_detected', False)))
                print("    [ETA] Promedio: {} min".format(metrics.get('average_eta_min', 0)))
        
        rec = radar.get_zone_recommendation()
        if rec:
            print("\n" + "=" * 80)
            print("RECOMENDACION DEL SISTEMA")
            print("=" * 80)
            print("\n[RECOMMENDED] Mejor zona: {}".format(rec['recommended_zone']))
            print("   Score: {}/10".format(rec['demand_score']))
            print("   Surge: x{}".format(rec['surge_multiplier']))
            print("   Razon: {}".format(rec['reason']))
        else:
            print("\n[WARN] No hay zonas con demanda suficiente")
    except Exception as e:
        print("\n[ERROR] {}".format(e))
        import traceback
        traceback.print_exc()
        print("\n[INFO] Ejecutando fallback de simulacion...")
        _run_demo_simulation()

def _run_demo_simulation():
    # --- BLOQUE: SIMULACION DE PRUEBA ---
    print("\n" + "=" * 80)
    print("MODO SIMULACION - Datos de prueba para Panama")
    print("=" * 80)
    test_zones = [
        {"zone_id": "z1_albrook", "demand": 8.5, "surge": 1.3, "eta": 4},
        {"zone_id": "z2_arraijan", "demand": 6.2, "surge": 1.0, "eta": 7},
        {"zone_id": "z6_costa_del_este", "demand": 9.1, "surge": 1.8, "eta": 3},
    ]
    for z in test_zones:
        print("\n[ZONE] {}".format(z['zone_id'].replace('_', ' ').title()))
        print("   [DEMAND] {}/10".format(z['demand']))
        print("   [SURGE] x{}".format(z['surge']))
        print("   [ETA] {} min".format(z['eta']))
        if z['demand'] >= 7.0:
            print("   [HOT] ZONA CALIENTE!")
    best = max(test_zones, key=lambda x: x['demand'])
    print("\n[RECOMMENDED] {}".format(best['zone_id'].replace('_', ' ').title()))
    print("   Razon: Maxima demanda ({}/10) + surge x{}".format(best['demand'], best['surge']))

# ================================================================================
# SECCION 11: PUNTO DE ENTRADA PRINCIPAL
# ================================================================================
if __name__ == "__main__":
    try:
        demo_radar()
        print("\n[ACTIVE] SISTEMA ACTIVO - MONITOREO CONTINUO")
        print("Presiona CTRL+C para salir\n")
        radar = get_radar_instance()
        radar.start_monitoring()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Sistema detenido manualmente")
        try:
            radar = get_radar_instance()
            radar.stop_monitoring()
        except Exception:
            pass

# ================================================================================
# SECCION 12: MODULO DE ENRUTAMIENTO GPS - CONSTANTES Y COORDENADAS
# ================================================================================
PANAMA_LOCATIONS = {
    "z1": {"name": "Albrook Mall", "lat": 8.9774, "lon": -79.5445},
    "z2": {"name": "Arraijan Centro", "lat": 8.8860, "lon": -79.7700},
    "z3": {"name": "La Chorrera", "lat": 8.8800, "lon": -79.7833},
    "z4": {"name": "San Carlos", "lat": 8.8830, "lon": -79.8000},
    "z5": {"name": "Veracruz", "lat": 8.8600, "lon": -79.8200},
    "z6": {"name": "Panama Centro", "lat": 8.9825, "lon": -79.5210},
    "z7": {"name": "Tocumen", "lat": 9.1167, "lon": -79.3833},
    "z8": {"name": "Aeropuerto PTY", "lat": 9.0714, "lon": -79.3833},
    "z9": {"name": "Costa del Este", "lat": 9.0000, "lon": -79.4667},
    "z10": {"name": "Clayton", "lat": 9.0000, "lon": -79.5500}
}

# ================================================================================
# SECCION 13: CLASE COORDINATE
# ================================================================================
class Coordinate:
    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude

    def distance_to(self, other: 'Coordinate') -> float:
        # --- BLOQUE: CALCULO HAVERSINE ---
        R = 6371.0
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def __repr__(self):
        return "Coordinate({}, {})".format(self.latitude, self.longitude)

# ================================================================================
# SECCION 14: CLASE GPSSIMULATOR
# ================================================================================
class GPSSimulator:
    def __init__(self, initial_zone: str = "z1"):
        # --- BLOQUE: INICIALIZACION ---
        self.current_zone = initial_zone
        self.current_location = Coordinate(
            PANAMA_LOCATIONS[initial_zone]["lat"],
            PANAMA_LOCATIONS[initial_zone]["lon"]
        )
        self.last_location = self.current_location
        self.last_update = time.time()
        self._active = True
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        # --- BLOQUE: INICIO DE SIMULACION ---
        if self._thread and self._thread.is_alive():
            return
        self._active = True
        def _move():
            while self._active:
                time.sleep(1.0)
                with self._lock:
                    self._update_position()
        self._thread = threading.Thread(target=_move, daemon=True)
        self._thread.start()

    def _update_position(self):
        # --- BLOQUE: ACTUALIZACION DE POSICION ---
        if random.random() < 0.3:
            posibles = [z for z in PANAMA_LOCATIONS.keys() if z != self.current_zone]
            if posibles:
                new_zone = random.choice(posibles)
                self.current_zone = new_zone
                self.last_location = self.current_location
                self.current_location = Coordinate(
                    PANAMA_LOCATIONS[new_zone]["lat"],
                    PANAMA_LOCATIONS[new_zone]["lon"]
                )
        else:
            lat_var = random.uniform(-0.005, 0.005)
            lon_var = random.uniform(-0.005, 0.005)
            self.last_location = self.current_location
            self.current_location = Coordinate(
                self.current_location.latitude + lat_var,
                self.current_location.longitude + lon_var
            )

    def get_current_location(self) -> Coordinate:
        with self._lock:
            return self.current_location

    def stop(self):
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)

# ================================================================================
# SECCION 15: CLASE TRAFFICSIMULATOR
# ================================================================================
class TrafficSimulator:
    def __init__(self):
        # --- BLOQUE: INICIALIZACION ---
        self.traffic_data = defaultdict(lambda: {"congestion": random.uniform(0.2, 1.0), "accident": False})
        self._active = True
        self._thread: Optional[threading.Thread] = None

    def start(self):
        # --- BLOQUE: INICIO DE ACTUALIZACION ---
        if self._thread and self._thread.is_alive():
            return
        self._active = True
        def _update():
            while self._active:
                time.sleep(30.0)
                for key in list(self.traffic_data.keys()):
                    self.traffic_data[key]["congestion"] = random.uniform(0.2, 1.0)
                    self.traffic_data[key]["accident"] = random.random() < 0.05
        self._thread = threading.Thread(target=_update, daemon=True)
        self._thread.start()

    def get_traffic(self, origin: str, destination: str) -> Dict:
        key = "{}-{}".format(origin, destination)
        return self.traffic_data[key]

    def stop(self):
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)

# ================================================================================
# SECCION 16: CLASE NETWORKMONITOR
# ================================================================================
class NetworkMonitor:
    def __init__(self):
        # --- BLOQUE: INICIALIZACION ---
        self.network_state = {
            "status": "EXCELENTE",
            "latency": 0.02,
            "packet_loss": 0.0,
            "timestamp": time.time()
        }
        self._active = True
        self._thread: Optional[threading.Thread] = None

    def start(self):
        # --- BLOQUE: INICIO DE MONITOREO ---
        if self._thread and self._thread.is_alive():
            return
        self._active = True
        def _monitor():
            while self._active:
                time.sleep(10)
                self._simulate_network_conditions()
        self._thread = threading.Thread(target=_monitor, daemon=True)
        self._thread.start()

    def _simulate_network_conditions(self):
        # --- BLOQUE: SIMULACION DE CONDICIONES ---
        r = random.random()
        if r < 0.7:
            status, latency, loss = "EXCELENTE", random.uniform(0.01, 0.05), 0.0
        elif r < 0.9:
            status, latency, loss = "ESTABLE", random.uniform(0.05, 0.15), random.uniform(0.0, 0.02)
        else:
            status, latency, loss = "INESTABLE", random.uniform(0.15, 0.5), random.uniform(0.02, 0.1)
        self.network_state = {"status": status, "latency": latency, "packet_loss": loss, "timestamp": time.time()}

    def get_state(self) -> Dict:
        return self.network_state

    def stop(self):
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)

# ================================================================================
# SECCION 17: CLASE ROUTINGGRAPH
# ================================================================================
class RoutingGraph:
    def __init__(self):
        # --- BLOQUE: INICIALIZACION Y CONSTRUCCION ---
        self.nodes = list(PANAMA_LOCATIONS.keys())
        self.edges = defaultdict(dict)
        self._build_graph()

    def _build_graph(self):
        # --- BLOQUE: GENERACION DE EDGES ---
        for i, zone_a in enumerate(self.nodes):
            coord_a = Coordinate(PANAMA_LOCATIONS[zone_a]["lat"], PANAMA_LOCATIONS[zone_a]["lon"])
            for zone_b in self.nodes[i+1:]:
                coord_b = Coordinate(PANAMA_LOCATIONS[zone_b]["lat"], PANAMA_LOCATIONS[zone_b]["lon"])
                dist = coord_a.distance_to(coord_b)
                time_min = (dist / 40.0) * 60 if dist < 20 else (dist / 60.0) * 60
                self.edges[zone_a][zone_b] = {"distance": dist, "time_min": time_min}
                self.edges[zone_b][zone_a] = {"distance": dist, "time_min": time_min}

    def heuristic(self, node: str, goal: str) -> float:
        coord1 = Coordinate(PANAMA_LOCATIONS[node]["lat"], PANAMA_LOCATIONS[node]["lon"])
        coord2 = Coordinate(PANAMA_LOCATIONS[goal]["lat"], PANAMA_LOCATIONS[goal]["lon"])
        return coord1.distance_to(coord2)

    def get_route(self, origin: str, destination: str, objective: str = "TIME") -> Tuple[List[str], float, float]:
        # --- BLOQUE: ALGORITMO A* ---
        if origin == destination:
            return [origin], 0.0, 0.0
        open_set = [(0.0, origin)]
        g_score = {n: float('inf') for n in self.nodes}
        g_score[origin] = 0.0
        parent: Dict[str, str] = {}
        while open_set:
            current_cost, current = heapq.heappop(open_set)
            if current == destination:
                path = []
                node = destination
                while node in parent:
                    path.append(node)
                    node = parent[node]
                path.append(origin)
                path.reverse()
                return path, g_score[destination], g_score[destination]
            for neighbor, attr in self.edges[current].items():
                cost = attr["time_min"] if objective == "TIME" else attr["distance"]
                tentative = g_score[current] + cost
                if tentative < g_score[neighbor]:
                    parent[neighbor] = current
                    g_score[neighbor] = tentative
                    heapq.heappush(open_set, (tentative + self.heuristic(neighbor, destination), neighbor))
        return [], float('inf'), float('inf')

# ================================================================================
# SECCION 18: API DE ENRUTAMIENTO GLOBAL (LAZY INIT)
# ================================================================================
_gps: Optional[GPSSimulator] = None
_traffic: Optional[TrafficSimulator] = None
_graph: Optional[RoutingGraph] = None
_network: Optional[NetworkMonitor] = None
_initialized = False
_routing_lock = threading.Lock()

def initialize_routing_components() -> Tuple[Any, Optional[GPSSimulator], Optional[TrafficSimulator], Optional[RoutingGraph]]:
    # --- BLOQUE: INICIALIZACION PEREZOSA ---
    global _gps, _traffic, _graph, _network, _initialized
    with _routing_lock:
        if not _initialized:
            _graph = RoutingGraph()
            _gps = GPSSimulator()
            _traffic = TrafficSimulator()
            _network = NetworkMonitor()
            _initialized = True
    return sys.modules[__name__], _gps, _traffic, _graph

def start_background_monitors() -> None:
    # --- BLOQUE: INICIO SEGURO DE HILOS ---
    initialize_routing_components()
    if _gps:
        _gps.start()
    if _traffic:
        _traffic.start()
    if _network:
        _network.start()

def get_network_monitor_instance() -> Optional[NetworkMonitor]:
    return _network

def get_route_between_coords(origin: Coordinate, destination: Coordinate,
                             algorithm: str = "A_STAR", objective: str = "TIME") -> Optional[Dict]:
    # --- BLOQUE: CONSULTA DE RUTA ---
    global _graph
    if not _graph:
        initialize_routing_components()
    if not _graph:
        return None
    
    min_dist_orig = float('inf')
    orig_zone = None
    for zone, loc in PANAMA_LOCATIONS.items():
        coord = Coordinate(loc["lat"], loc["lon"])
        d = origin.distance_to(coord)
        if d < min_dist_orig:
            min_dist_orig = d
            orig_zone = zone
            
    min_dist_dest = float('inf')
    dest_zone = None
    for zone, loc in PANAMA_LOCATIONS.items():
        coord = Coordinate(loc["lat"], loc["lon"])
        d = destination.distance_to(coord)
        if d < min_dist_dest:
            min_dist_dest = d
            dest_zone = zone
            
    path, total_cost, total_min = _graph.get_route(orig_zone, dest_zone, objective)
    if not path:
        return None
    distance_sum = sum(_graph.edges[path[i]][path[i+1]]["distance"] for i in range(len(path)-1))
    return {
        "path": path,
        "distance_km": distance_sum if objective == "DISTANCE" else total_cost,
        "time_min": total_min,
        "algorithm": algorithm,
        "objective": objective
    }

# ================================================================================
# SECCION 19: FUNCION PRINCIPAL DE ANALISIS DE PROMPT (ORQUESTADOR)
# ================================================================================
def analizar_prompt_mejor_opcion(prompt: str, contexto: dict) -> dict:
    """
    Procesa el prompt con el radar y el sistema de rutas.
    Compatible con Orquestador Parte 1 y Parte 5.
    """
    # --- BLOQUE: INICIALIZACION Y CONTEXTO ---
    initialize_routing_components()
    zones_input = contexto.get("zones", [])
    origin_str = contexto.get("origin", "z1")
    destination_str = contexto.get("destination", "z6")
    
    # --- BLOQUE: PROCESAMIENTO DE RADAR ---
    try:
        radar = get_radar_instance()
        estado = radar.export_estado()
        recomendacion = estado.get("recomendacion_actual")
        oportunidades = estado.get("ultimas_oportunidades", [])
        
        # Forzar escaneo si no hay datos
        if not oportunidades and not radar._running:
            forzar_escaneo_radar()
            estado = radar.export_estado()
            oportunidades = estado.get("ultimas_oportunidades", [])
            recomendacion = estado.get("recomendacion_actual")
    except Exception as e:
        recomendacion = None
        oportunidades = []
        log_event("Error en radar para prompt: {}".format(e), "WARN")

    # --- BLOQUE: PROCESAMIENTO DE RUTAS ---
    ruta_optima = None
    try:
        if _graph:
            loc_orig = PANAMA_LOCATIONS.get(origin_str, PANAMA_LOCATIONS["z1"])
            loc_dest = PANAMA_LOCATIONS.get(destination_str, PANAMA_LOCATIONS["z6"])
            coord_orig = Coordinate(loc_orig["lat"], loc_orig["lon"])
            coord_dest = Coordinate(loc_dest["lat"], loc_dest["lon"])
            ruta_optima = get_route_between_coords(coord_orig, coord_dest, objective="TIME")
    except Exception as e:
        log_event("Error calculando ruta para prompt: {}".format(e), "WARN")

    # --- BLOQUE: DECISION Y SALIDA ---
    mejor_zona = "z6_costa_del_este"
    demanda_estimada = 7.5
    surge = False
    
    if recomendacion:
        mejor_zona = recomendacion.get("recommended_zone", mejor_zona)
        demanda_estimada = recomendacion.get("demand_score", demanda_estimada)
        surge = recomendacion.get("surge_multiplier", 1.0) > 1.0
    elif oportunidades:
        mejor_opp = max(oportunidades, key=lambda x: x.get("priority_score", 0))
        mejor_zona = mejor_opp.get("zone_id", mejor_zona)
        demanda_estimada = mejor_opp.get("demand_score", demanda_estimada)
        surge = mejor_opp.get("surge_multiplier", 1.0) > 1.0

    return {
        "exito": True,
        "zonas_analizadas": len(zones_input) if zones_input else len(PANAMA_LOCATIONS),
        "mejor_zona": mejor_zona,
        "demanda_estimada": demanda_estimada,
        "surge_detected": surge,
        "ruta_optima": ruta_optima,
        "oportunidades_detectadas": len(oportunidades),
        "timestamp_procesamiento": time.time()
    }

# ================================================================================
# SECCION 20: EXPORTS PUBLICOS
# ================================================================================
__all__ = [
    'UberConfig', 'UberAPIClient', 'ZoneSystem', 'UberRadarPro',
    'Coordinate', 'GPSSimulator', 'TrafficSimulator', 'NetworkMonitor', 'RoutingGraph',
    'get_radar_instance', 'exportar_estado_radar', 'iniciar_radar', 'detener_radar',
    'forzar_escaneo_radar', 'establecer_intervalo_escaneo', 'establecer_umbral_demanda',
    'obtener_recomendacion_zona', 'analizar_prompt_mejor_opcion',
    'initialize_routing_components', 'start_background_monitors',
    'get_network_monitor_instance', 'get_route_between_coords',
    'RadarError', 'AuthenticationError', 'PermissionError', 'SurgePricingError',
    'ValidationError', 'RateLimitError', 'TimeoutError', 'ConnectionError', 'APIError'
]

# ================================================================================
# FIN DEL MODULO
# ================================================================================
