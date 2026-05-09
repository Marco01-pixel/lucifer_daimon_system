#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UNIFICADOR MAESTRO - LUCIFER PROMETEO"""
import sys, os, time, threading, subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

def log(msg, tag="SETUP"):
    print(f"[{tag}] {msg}", flush=True)

def check_deps():
    log("Verificando entorno...")
    for pkg in ["requests", "numpy"]:
        try:
            __import__(pkg)
            log(f"✅ {pkg} OK")
        except ImportError:
            log(f"⚠️ {pkg} no instalado (opcional)", "WARN")

def load_module(file_name, mod_name):
    ruta = PROJECT_DIR / file_name
    if not ruta.exists():
        log(f"⚠️ {file_name} no encontrado", "WARN")
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location(mod_name, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
        log(f"✅ {mod_name} cargado")
        return mod
    except Exception as e:
        log(f"❌ Error cargando {mod_name}: {e}", "ERROR")
        return None

def main():
    log("="*60)
    log("🚀 INICIANDO SYMBIOSIS UNIFICADO")
    log("="*60)
    
    check_deps()
    
    # Cargar partes en orden
    partes = [
        ("part1_config.py", "symbiosis_parte1"),
        ("part2_negotiation.py", "symbiosis_parte2"),
        ("part3_radar.py", "symbiosis_parte3"),
        ("part4_predictor.py", "symbiosis_parte4"),
        ("parte5_daimon_base.py", "symbiosis_parte5"),
        ("part7_mejor_opcion.py", "symbiosis_parte7"),
        ("part8_interfaz_web.py", "symbiosis_parte8"),
        ("part9_network_monitor.py", "symbiosis_parte9"),
    ]
    
    cargados = []
    for archivo, nombre in partes:
        mod = load_module(archivo, nombre)
        if mod:
            cargados.append(nombre)
    
    log(f"\n✅ {len(cargados)}/{len(partes)} módulos cargados")
    
    # Buscar y ejecutar main() si existe
    for nombre in ["symbiosis_unified", "lucifer_prometeo", "symbiosis_parte5"]:
        if nombre in sys.modules:
            mod = sys.modules[nombre]
            if hasattr(mod, "main") and callable(mod.main):
                log(f"🚀 Ejecutando main() de {nombre}...")
                try:
                    mod.main()
                    return
                except Exception as e:
                    log(f"⚠️ Error en main(): {e}", "WARN")
    
    # Fallback: lanzar Flask si está disponible
    if "symbiosis_parte8" in sys.modules:
        web = sys.modules["symbiosis_parte8"]
        if hasattr(web, "app") and web.app:
            port = getattr(web, "HTTP_PORT", 8989)
            log(f"🌐 Iniciando servidor web en puerto {port}")
            web.app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
            return
    
    log("ℹ️  Sistema cargado. Manteniendo vivo...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("🛑 Detenido por usuario")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Interrupción manual")
        sys.exit(0)
