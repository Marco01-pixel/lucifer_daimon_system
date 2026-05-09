#!/usr/bin/env python3

import subprocess
import time
from datetime import datetime

# ==============================
# CONFIGURACIÓN
# ==============================

TUNNEL_NAME = "uber_tunel"
RESTART_DELAY = 5

# ==============================
# FUNCIONES
# ==============================

def log(msg):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{fecha}] {msg}", flush=True)

def iniciar_tunel():
    comando = [
        "cloudflared",
        "tunnel",
        "run",
        TUNNEL_NAME
    ]

    log(f"Iniciando túnel: {TUNNEL_NAME}")

    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    return proceso

# ==============================
# LOOP PRINCIPAL
# ==============================

while True:
    try:
        proceso = iniciar_tunel()

        # Leer logs en tiempo real
        for linea in proceso.stdout:
            print(linea.strip())

        codigo = proceso.wait()

        log(f"Tunnel detenido con código: {codigo}")

    except KeyboardInterrupt:
        log("Supervisor detenido manualmente")
        break

    except Exception as e:
        log(f"ERROR: {e}")

    log(f"Reiniciando en {RESTART_DELAY} segundos...")
    time.sleep(RESTART_DELAY)
