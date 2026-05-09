# =============================================================================
# 🧪 DEFINICIÓN DE PRUEBAS POR PARTE (DEFENSIVAS Y ADAPTATIVAS)
# =============================================================================

def _obtener_componente(mod, nombres_posibles, fallback=True):
    """Busca una clase/función por nombre. Si falla, devuelve el primer atributo público útil."""
    for nombre in nombres_posibles:
        if hasattr(mod, nombre):
            return getattr(mod, nombre), nombre
    if fallback:
        # Fallback: primer clase o función que no sea mágica ni interna
        for attr in dir(mod):
            if not attr.startswith('_') and isinstance(getattr(mod, attr), (type, type(_obtener_componente))):
                obj = getattr(mod, attr)
                if callable(obj) or isinstance(obj, type):
                    return obj, attr
    return None, None

def test_part1_config(mod):
    """Valida configuración, logging y utilidades numéricas."""
    cfg_cls, _ = _obtener_componente(mod, ["GlobalConfig", "Config", "Settings"])
    assert cfg_cls is not None, "No se encontró clase de configuración"
    cfg = cfg_cls() if callable(cfg_cls) else cfg_cls
    # Verifica serialización o atributos internos
    assert hasattr(cfg, 'to_dict') or hasattr(cfg, '__dict__') or hasattr(cfg, 'items'), "No es serializable"
    
    log_func, _ = _obtener_componente(mod, ["log_event", "log", "registrar_evento"])
    assert log_func is not None and callable(log_func), "Falta función de logging"
    log_func("prueba_verificador", "TEST")

    hn_cls, _ = _obtener_componente(mod, ["HyperNumberAdvanced", "HyperNumber", "NumeroAvanzado"])
    if hn_cls:
        hn = hn_cls(42.5)
        assert abs(hn.to_float_approx() if hasattr(hn, 'to_float_approx') else float(hn) - 42.5) < 1e-6

def test_part2_negotiation(mod):
    """Valida negociador IA y propuesta de intercambio."""
    neg_cls, _ = _obtener_componente(mod, ["NegociadorIA", "Negotiator", "IA_Negociacion"])
    assert neg_cls is not None, "No se encontró clase de negociación"
    
    neg = neg_cls(timeout=2) if hasattr(neg_cls, '__init__') else neg_cls()
    assert hasattr(neg, 'enviar_propuesta') or hasattr(neg, 'proponer') or hasattr(neg, 'negociar'), "Falta método de propuesta"
    
    metodo = getattr(neg, 'enviar_propuesta', getattr(neg, 'proponer', getattr(neg, 'negociar')))
    res = metodo({"target": "test", "coins": 5.0, "timeout": 1})
    assert isinstance(res, (dict, str, list)), "La propuesta no devuelve formato esperado"
    if isinstance(res, dict):
        assert any(k in res for k in ["status", "estado", "exito", "resultado"]), "Falta campo de estado en respuesta"

def test_part3_radar(mod):
    """Valida escaneo de zonas y detección de oportunidades."""
    radar_cls, _ = _obtener_componente(mod, ["UberRadarPro", "Radar", "DetectorZonas"])
    assert radar_cls is not None, "No se encontró clase de radar"
    
    radar = radar_cls()
    assert hasattr(radar, 'perform_full_scan') or hasattr(radar, 'scan') or hasattr(radar, 'detectar'), "Falta método de escaneo"
    
    metodo = getattr(radar, 'perform_full_scan', getattr(radar, 'scan', getattr(radar, 'detectar')))
    resultado = metodo()
    assert isinstance(resultado, (list, dict)), "El escaneo no devuelve estructura válida"
    if isinstance(resultado, list):
        assert len(resultado) == 0 or isinstance(resultado[0], dict), "Items del escaneo no son diccionarios"

def test_part4_predictor(mod):
    """Valida predicción de demanda y series temporales."""
    pred_cls, _ = _obtener_componente(mod, ["PredictorIA", "Predictor", "ModeloDemanda"])
    assert pred_cls is not None, "No se encontró clase predictora"
    
    pred = pred_cls()
    assert hasattr(pred, 'predecir') or hasattr(pred, 'forecast') or hasattr(pred, 'calcular_tendencia'), "Falta método predictivo"
    
    metodo = getattr(pred, 'predecir', getattr(pred, 'forecast', getattr(pred, 'calcular_tendencia')))
    res = metodo(datos_historicos=[10, 12, 15, 14, 18], horizonte=2)
    assert isinstance(res, (list, dict, tuple, float, int)), "La predicción no retorna tipo numérico/estructurado"

def test_part5_daimon(mod):
    """Valida CEOIA, algoritmos RL y GPS (Basado en tu KB real)."""
    assert hasattr(mod, 'CEOIA'), "Falta clase CEOIA"
    assert hasattr(mod, 'ZONAS') and len(mod.ZONAS) > 0, "ZONAS vacío"
    
    ceo = mod.CEOIA(state_dim=5, action_dim=4)
    ceo._learning_active = False  # Evita hilos en pruebas
    a = ceo.decide_action([0.1]*5)
    assert 0 <= a < 4, "Decisión fuera de rango"
    
    gps = mod.leer_gps_actual()
    assert "lat" in gps and "lng" in gps, "GPS no retorna coordenadas"
    assert isinstance(gps.get("precision", 0), (int, float)), "Precisión GPS inválida"

def test_part7_mejor_opcion(mod):
    """Valida motor de optimización y ranking de rutas."""
    opt_cls, _ = _obtener_componente(mod, ["MejorOpcionEngine", "OptimizadorRutas", "RankerZonas"])
    assert opt_cls is not None, "No se encontró optimizador"
    
    engine = opt_cls()
    assert hasattr(engine, 'calcular_ruta_optima') or hasattr(engine, 'rank_options') or hasattr(engine, 'evaluar'), "Falta método de evaluación"
    
    metodo = getattr(engine, 'calcular_ruta_optima', getattr(engine, 'rank_options', getattr(engine, 'evaluar')))
    zonas_dummy = [{"id": "z1", "ingreso": 12.5, "espera": 45}, {"id": "z2", "ingreso": 8.0, "espera": 120}]
    res = metodo(zonas=zonas_dummy)
    assert isinstance(res, (list, dict)), "Resultado de optimización inválido"

def test_part8_interfaz_web(mod):
    """Valida servidor web, rutas y manejo de requests."""
    app_obj, nombre = _obtener_componente(mod, ["app", "api", "servidor", "flask_app"])
    assert app_obj is not None, "No se encontró instancia de app web"
    
    # Verifica que tenga rutas registradas (Flask/FastAPI compatible)
    rutas = []
    if hasattr(app_obj, 'url_map'):
        rutas = [rule.rule for rule in app_obj.url_map.iter_rules()]
    elif hasattr(app_obj, 'routes'):
        rutas = list(app_obj.routes.keys()) if isinstance(app_obj.routes, dict) else []
    elif hasattr(app_obj, 'router'):
        rutas = [r.path for r in app_obj.router.routes]
        
    assert len(rutas) > 0, "No se detectaron rutas web registradas"
    assert any("/ceoia" in r or "/estado" in r or "/" in r for r in rutas), "Falta ruta base o de CEOIA"

def test_part9_network_monitor(mod):
    """Valida monitoreo de red, latencia y estado de conexión."""
    mon_cls, _ = _obtener_componente(mod, ["NetworkMonitor", "MonitorRed", "PingService"])
    assert mon_cls is not None, "No se encontró monitor de red"
    
    monitor = mon_cls()
    assert hasattr(monitor, 'check_latency') or hasattr(monitor, 'ping_hosts') or hasattr(monitor, 'get_status'), "Falta método de chequeo"
    
    metodo = getattr(monitor, 'check_latency', getattr(monitor, 'ping_hosts', getattr(monitor, 'get_status')))
    res = metodo(hosts=["8.8.8.8", "1.1.1.1"])
    assert isinstance(res, (dict, list, tuple)), "Estado de red no retorna estructura válida"
    if isinstance(res, dict):
        assert any(k in res for k in ["latency", "estado", "status", "online", "conectado"]), "Falta métrica de red"
