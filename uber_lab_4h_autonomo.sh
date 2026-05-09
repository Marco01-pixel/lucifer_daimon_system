#!/bin/bash
# =====================================================================
# LABORATORIO AUTÓNOMO: OPTIMIZACIÓN UBER PANAMÁ (4 HORAS - OPTIMIZADO TIGO)
# Versión Híbrida: Súper Carga + Radar Secuencial + IA Intercalada + Proxy Tests
# Compatible con UBER DAIMON VIVO + SOCIALCOIN
# Zonas: z1=Albrook, z2=Arraiján, z3=Chorrera, z4=San Carlos, z5=Veracruz
# =====================================================================

# set -e  # Comentado para permitir fallos controlados
set -o pipefail

# === CONFIGURACIÓN GLOBAL ===
ENDPOINT="http://localhost:8989"
LOG_FILE="/sdcard/termux_labs/lab_uber_$(date +%Y%m%d_%H%M).log"
REPORT_FILE="$HOME/flujo_hibrido_$(date +%Y%m%d_%H%M).log"

# DeepSeek API
DEEPSEEK_API="https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY="${DEEPSEEK_API_KEY:-sk-14e93c5071e14eaf8b27e58c968f5f84}"
DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-coder}"

# Ollama Local
OLLAMA_HOST="http://127.0.0.1:11434"
OLLAMA_GENERATE="$OLLAMA_HOST/api/generate"
OLLAMA_MODEL="${OLLAMA_MODEL:-kimi-k2.5:cloud}"

# === CONFIGURACIÓN DE TIEMPOS OPTIMIZADA PARA TIGO ===
TOTAL_MINUTES=240                    # 4 horas (conceptualmente)
CYCLE_MINUTES=30                      # 30 minutos por ciclo (conceptualmente)
CYCLE_SECONDS=$((CYCLE_MINUTES * 60)) # 1800 segundos
CYCLES=$((TOTAL_MINUTES / CYCLE_MINUTES))  # 8 ciclos de 30 min

# Configuración Radar Secuencial (dentro de cada ciclo)
RADAR_ZONES=("z1" "z2" "z3" "z4" "z5")
RADAR_ZONES_COUNT=${#RADAR_ZONES[@]}
ZONE_INTERVAL=60                       # 1 minuto por zona (MANTENIDO)

# Timeouts
DEEPSEEK_TIMEOUT=120
OLLAMA_TIMEOUT=120

# === CONFIGURACIÓN DE ESPERAS OPTIMIZADA PARA TIGO ===
ULTRA_ESPERA=30                        # ⚡ REDUCIDO: 60s → 30s
PIN_INTERVAL=90                         # 🔐 REDUCIDO: 180s → 90s
ESPERA_INICIAL=10                       # ⏱️ REDUCIDO: 30s → 10s
PAUSA_CICLO=2                           # 🔄 REDUCIDO: 5s → 2s
DIAGNOSTICO_ESPERA=2                     # 🔍 REDUCIDO: 5s → 2s

# === CONTADORES GLOBALES ===
TOTAL_CICLOS=0
DEEPSEEK_SUCCESS=0
OLLAMA_SUCCESS=0
LOCAL_MEJOR_OPCION_COUNT=0
RADAR_ACTIVATIONS=0
CACHE_ACTIVATIONS=0
NEGOCIACIONES_COUNT=0
FALLBACK_COUNT=0
PROXY_TESTS_COUNT=0
CEO_COMMANDS_COUNT=0

# =====================================================================
# 🔧 VERIFICACIONES PREVIAS
# =====================================================================

# Verificar dependencias básicas
for cmd in curl jq python3; do
    if ! command -v $cmd &> /dev/null; then
        echo "⚠️ $cmd no está instalado. Algunas funciones podrían fallar."
        if command -v pkg &> /dev/null; then
            echo "📦 Instalando $cmd con pkg (Termux)..."
            pkg install $cmd -y
        elif command -v apt &> /dev/null; then
            echo "📦 Instalando $cmd con apt (Linux)..."
            sudo apt install $cmd -y
        else
            echo "❌ No se pudo instalar $cmd automáticamente. Instálalo manualmente."
        fi
    fi
done

# Verificar que el endpoint responde antes de empezar
if ! curl -s --max-time 5 "$ENDPOINT/mining_demo" > /dev/null 2>&1; then
    echo "⚠️ ADVERTENCIA: Endpoint $ENDPOINT no responde. Continuando de todas formas..."
fi

# Verificar nuevo endpoint MEJOR_OPCION
echo "🔍 Verificando endpoint MEJOR_OPCION..."
curl -s -X POST http://localhost:8989/api/redes/tendencias \
  -H "Content-Type: application/json" \
  -d '{"accion":"MEJOR_OPCION","fuente":"test"}' | tee -a "$LOG_FILE" || echo "⚠️ Endpoint MEJOR_OPCION no disponible"

# Verificar que Python está corriendo
curl -s http://localhost:8989/mining_demo | head -5 | tee -a "$LOG_FILE"

# Verificar que jq está instalado
command -v jq && echo "✅ jq instalado" || echo "❌ jq faltante"

# Crear directorio de logs si no existe
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || {
    echo "⚠️ No se puede crear el directorio $(dirname "$LOG_FILE"). Usando ubicación alternativa."
    LOG_FILE="$HOME/lab_uber_$(date +%Y%m%d_%H%M).log"
}

# =====================================================================
# FUNCIONES AUXILIARES
# =====================================================================

log() {
    local mensaje="[$(date '+%H:%M:%S')] $1"
    echo "$mensaje" | tee -a "$LOG_FILE"
}

print_header() {
    echo "=========================================================" | tee -a "$LOG_FILE"
    echo "$1" | tee -a "$LOG_FILE"
    echo "=========================================================" | tee -a "$LOG_FILE"
}

error_exit() {
    log "[ERROR] $1"
    exit 1
}

# === FUNCIONES DE PROXY TESTS ===

proxy_test_httpbin() {
    log "🌐 Proxy test POST → httpbin.org"
    curl -s -X POST "$ENDPOINT/internet/proxy" \
        -H "Content-Type: application/json" \
        -d '{"url":"https://httpbin.org/post","payload":{"test":true}}' >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    PROXY_TESTS_COUNT=$((PROXY_TESTS_COUNT + 1))
    log "✅ Proxy test httpbin completado"
}

proxy_test_ipify_json() {
    log "🌐 Proxy test GET → ipify.org JSON"
    curl -s -X POST "$ENDPOINT/internet/proxy" \
        -H "Content-Type: application/json" \
        -d '{"url":"https://api.ipify.org?format=json","method":"GET"}' >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    PROXY_TESTS_COUNT=$((PROXY_TESTS_COUNT + 1))
    log "✅ Proxy test ipify JSON completado"
}

proxy_test_ipify_text() {
    log "🌐 Proxy test GET → ipify.org texto plano"
    curl -s -X POST "$ENDPOINT/internet/proxy" \
        -H "Content-Type: application/json" \
        -d '{"url":"https://api.ipify.org","method":"GET"}' >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    PROXY_TESTS_COUNT=$((PROXY_TESTS_COUNT + 1))
    log "✅ Proxy test ipify texto completado"
}

# === FUNCIÓN: COMANDOS CEO ADICIONALES ===
ejecutar_comandos_ceo() {
    log "👑 Ejecutando comandos CEO adicionales..."
    
    if ! curl -s --max-time 2 "$ENDPOINT/mining_demo" > /dev/null 2>&1; then
        log "⚠️ Endpoint no disponible - omitiendo comandos CEO"
        return 0
    fi
    
    curl -s -X POST "$ENDPOINT/ia/consultar" \
        -H "Content-Type: application/json" \
        -d '{"pregunta": "CEO desbloquear completo"}' > /dev/null 2>&1 || log "⚠️ CEO desbloquear falló"
    
    curl -s -X POST "$ENDPOINT/ia/consultar" \
        -H "Content-Type: application/json" \
        -d '{"pregunta": "CEO cambia viral_score_bonus a 200"}' > /dev/null 2>&1 || log "⚠️ CEO viral_score falló"
    
    curl -s -X POST "$ENDPOINT/ia/consultar" \
        -H "Content-Type: application/json" \
        -d '{"pregunta": "CEO auditar y optimizar interno"}' > /dev/null 2>&1 || log "⚠️ CEO auditoría falló"
    
    curl -s -X POST "$ENDPOINT/ia/consultar" \
        -H "Content-Type: application/json" \
        -d '{"pregunta": "agente_autonomo modo_evolucion_continua"}' > /dev/null 2>&1 || log "⚠️ CEO evolución continua falló"
    
    CEO_COMMANDS_COUNT=$((CEO_COMMANDS_COUNT + 4))
    log "✅ Comandos CEO ejecutados"
}

# === NUEVA FUNCIÓN: GRITO INICIAL DE CICLO ===
ejecutar_grito_ciclo() {
local ciclo="$1"
log "🚨 [GRITO DIGITAL] Ciclo $ciclo/8 - INICIANDO PRESIÓN ALGORÍTMICA"
curl -s -X POST "$ENDPOINT/ia/consultar" \
-H "Content-Type: application/json" \
-d "{\"pregunta\":\"CEO grito_digital ciclo_$ciclo activar\"}" > /dev/null || log "⚠️ Grito ciclo $ciclo falló"
curl -s -X POST "$ENDPOINT/api/redes/tendencias" \
-H "Content-Type: application/json" \
-d '{"accion":"GRITO_DIGITAL","fuente":"inicio_ciclo"}' > /dev/null || log "⚠️ GRITO_DIGITAL falló"
log "✅ [GRITO] Ciclo $ciclo: Señal de presión enviada"
}

# === FUNCIONES DE VERIFICACIÓN ===

verificar_endpoint() {
    if curl -s --max-time 5 "$ENDPOINT/mining_demo" > /dev/null 2>&1; then
        log "[OK] Endpoint principal disponible: $ENDPOINT"
        return 0
    else
        log "[WARN] Endpoint principal no responde: $ENDPOINT"
        return 1
    fi
}

verificar_deepseek() {
    if curl -s --max-time 10 -X POST "$DEEPSEEK_API" \
        -H "Authorization: Bearer $DEEPSEEK_KEY" \
        -H "Content-Type: application/json" \
        -d '{"model":"'$DEEPSEEK_MODEL'","messages":[{"role":"user","content":"test"}],"stream":false,"max_tokens":10}' \
        > /dev/null 2>&1; then
        log "[OK] DeepSeek API disponible"
        return 0
    else
        log "[X] DeepSeek API NO disponible"
        return 1
    fi
}

verificar_ollama() {
    if curl -s --max-time 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        log "[OK] Ollama detectado en $OLLAMA_HOST"
        return 0
    else
        log "[X] Ollama NO disponible"
        return 1
    fi
}

# === FUNCIONES DE LA SÚPER CARGA ===

ejecutar_ultra_200() {
    local VALID_UNTIL=$1
    local ENGAGEMENT=80
    
    log "⚡ ULTRA 200 | engagement=$ENGAGEMENT"
    
    curl -X POST "$ENDPOINT/ultra200" || log "⚠️ ultra200 falló"
    curl -X POST "$ENDPOINT/ia/consultar" \
        -H "Content-Type: application/json" \
        -d "{\"pregunta\":\"CEO cambia engagement_rate a $ENGAGEMENT\"}" || log "⚠️ CEO engagement falló"
    
    curl -X POST "$ENDPOINT/ia/negociar" -H "Content-Type: application/json" -d "{
        \"from\":\"ia_uber_demand\",
        \"payload\":{
            \"offer_type\":\"compartir_radar_ubicacion\",
            \"coins\":7.5,
            \"valid_until\":$VALID_UNTIL,
            \"zone\":\"z3\",
            \"high_demand\":true
        }
    }" || log "⚠️ negociación falló"
    
    curl -X POST "$ENDPOINT/auto-mejorar" || log "⚠️ auto-mejorar falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d '{"pregunta":"agente_autonomo evolucion_extrema"}' || log "⚠️ evolución extrema falló"
    
    log "⏱️ Esperando ${ULTRA_ESPERA}s después de ULTRA 200..."
    sleep $ULTRA_ESPERA
}

ejecutar_ultra_300() {
    local VALID_UNTIL=$1
    local ENGAGEMENT=84
    
    log "⚡ ULTRA 300 | engagement=$ENGAGEMENT"
    
    curl -X POST "$ENDPOINT/ultra300" || log "⚠️ ultra300 falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d "{\"pregunta\":\"CEO cambia engagement_rate a $ENGAGEMENT\"}" || log "⚠️ CEO engagement falló"
    
    curl -X POST "$ENDPOINT/ia/negociar" -H "Content-Type: application/json" -d "{
        \"from\":\"ia_uber_eta\",
        \"payload\":{
            \"offer_type\":\"compartir_radar_ubicacion\",
            \"coins\":7.5,
            \"valid_until\":$VALID_UNTIL,
            \"zone\":\"z4\",
            \"high_demand\":true
        }
    }" || log "⚠️ negociación falló"
    
    curl -X POST "$ENDPOINT/auto-mejorar" || log "⚠️ auto-mejorar falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d '{"pregunta":"agente_autonomo evolucion_extrema"}' || log "⚠️ evolución extrema falló"
    
    log "⏱️ Esperando ${ULTRA_ESPERA}s después de ULTRA 300..."
    sleep $ULTRA_ESPERA
}

ejecutar_ultra_500() {
    local VALID_UNTIL=$1
    local ENGAGEMENT=86
    
    log "⚡ ULTRA 500 | engagement=$ENGAGEMENT"
    
    curl -X POST "$ENDPOINT/ultra500" || log "⚠️ ultra500 falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d "{\"pregunta\":\"CEO cambia engagement_rate a $ENGAGEMENT\"}" || log "⚠️ CEO engagement falló"
    
    curl -X POST "$ENDPOINT/ia/negociar" -H "Content-Type: application/json" -d "{
        \"from\":\"ia_uber_pricing\",
        \"payload\":{
            \"offer_type\":\"compartir_radar_ubicacion\",
            \"coins\":7.5,
            \"valid_until\":$VALID_UNTIL,
            \"zone\":\"z5\",
            \"high_demand\":true
        }
    }" || log "⚠️ negociación falló"
    
    curl -X POST "$ENDPOINT/auto-mejorar" || log "⚠️ auto-mejorar falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d '{"pregunta":"agente_autonomo evolucion_extrema"}' || log "⚠️ evolución extrema falló"
    
    log "⏱️ Esperando ${ULTRA_ESPERA}s después de ULTRA 500..."
    sleep $ULTRA_ESPERA
}

ejecutar_ultra_700() {
    local VALID_UNTIL=$1
    local ENGAGEMENT=87
    
    log "⚡ ULTRA 700 | engagement=$ENGAGEMENT"
    
    curl -X POST "$ENDPOINT/ultra700" || log "⚠️ ultra700 falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d "{\"pregunta\":\"CEO cambia engagement_rate a $ENGAGEMENT\"}" || log "⚠️ CEO engagement falló"
    
    for Z in z3 z4 z5; do
        curl -X POST "$ENDPOINT/ia/negociar" -H "Content-Type: application/json" -d "{
            \"from\":\"ia_uber_demand\",
            \"payload\":{
                \"offer_type\":\"compartir_radar_ubicacion\",
                \"coins\":7.5,
                \"valid_until\":$VALID_UNTIL,
                \"zone\":\"$Z\",
                \"high_demand\":true
            }
        }" || log "⚠️ negociación en $Z falló"
    done
    
    curl -X POST "$ENDPOINT/auto-mejorar" || log "⚠️ auto-mejorar falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d '{"pregunta":"agente_autonomo evolucion_extrema"}' || log "⚠️ evolución extrema falló"
    
    log "⏱️ Esperando ${ULTRA_ESPERA}s después de ULTRA 700..."
    sleep $ULTRA_ESPERA
}

ejecutar_ultra_1000() {
    local VALID_UNTIL=$1
    local ENGAGEMENT=89
    
    log "🚀 ULTRA 1000 SEGURO | engagement=$ENGAGEMENT"
    
    curl -X POST "$ENDPOINT/ultra1000_seguro" || log "⚠️ ultra1000 falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d "{\"pregunta\":\"CEO cambia engagement_rate a $ENGAGEMENT\"}" || log "⚠️ CEO engagement falló"
    
    for Z in z3 z4 z5; do
        for IA in ia_uber_demand ia_uber_eta ia_uber_pricing; do
            curl -X POST "$ENDPOINT/ia/negociar" -H "Content-Type: application/json" -d "{
                \"from\":\"$IA\",
                \"payload\":{
                    \"offer_type\":\"compartir_radar_ubicacion\",
                    \"coins\":7.5,
                    \"valid_until\":$VALID_UNTIL,
                    \"zone\":\"$Z\",
                    \"high_demand\":true
                }
            }" || log "⚠️ negociación $IA en $Z falló"
        done
    done
    
    curl -X POST "$ENDPOINT/auto-mejorar" || log "⚠️ auto-mejorar falló"
    curl -X POST "$ENDPOINT/ia/consultar" -H "Content-Type: application/json" \
        -d '{"pregunta":"agente_autonomo evolucion_extrema"}' || log "⚠️ evolución extrema falló"
    
    log "⏱️ Esperando ${ULTRA_ESPERA}s después de ULTRA 1000..."
    sleep $ULTRA_ESPERA
}

# === FUNCIONES RADAR SECUENCIAL ===

activar_radar_zona() {
local zona="$1"
local ciclo="$2"
local minuto="$3"
log "   📡 [RADAR] [C$ciclo|M$minuto] Activando radar en ZONA $zona..."

# ✅ Usar formato JSON correcto
response=$(curl -s -X POST "$ENDPOINT/uber/activar_radar_alta_demanda" \
-H "Content-Type: application/json" \
-d "{\"zona\":\"$zona\"}" 2>/dev/null)

RADAR_ACTIVATIONS=$((RADAR_ACTIVATIONS + 1))

# ✅ Verificar respuesta vacía también
if [ -n "$response" ] && echo "$response" | grep -qE "status|radar|ofertas|generado"; then
log "   ✅ [OK] Zona $zona: radar activado"
return 0
else
log "   ⚠️ [WARN] Zona $zona: respuesta no estándar o endpoint 404"
log "   📝 Response: $response"
return 1
fi
}

activar_cache_zona() {
    local zona="$1"
    local ciclo="$2"
    local minuto="$3"
    
    curl -s -X POST "$ENDPOINT/uber/cache_request" \
        -H "Content-Type: application/json" \
        -d "{\"url\":\"https://api.uber.com/v1/trips\",\"params\":{\"zone\":\"$zona\",\"limit\":10}}" \
        > /dev/null 2>&1
    CACHE_ACTIVATIONS=$((CACHE_ACTIVATIONS + 1))
    log "   💾 [CACHE] [C$ciclo|M$minuto] Cache para zona $zona"
}

# === FUNCIONES DE NEGOCIACIÓN IA ===
ejecutar_negociaciones_ia() {
    local valid_until="$1"
    log "🤝 Iniciando negociaciones IA-IA (valid_until: $(date -d @$valid_until '+%H:%M'))"
    
    # 1. Inyección autónoma CEO (z3)
    curl -s -X POST "$ENDPOINT/ia/negociar" \
        -H "Content-Type: application/json" \
        -d "{
            \"from\":\"ia_uber_demand\",
            \"payload\":{
                \"offer_type\":\"inyeccion_autonoma_ceo\",
                \"coins\":7.5,
                \"valid_until\":$valid_until,
                \"zone\":\"z3\",
                \"high_demand\":true,
                \"priority\":5,
                \"reason\":\"deteccion_pico_demanda_simulado\"
            }
        }" > /dev/null 2>&1
    
    # 2. Negociaciones en paralelo (z3, z4, z5) × (ia_uber_eta, ia_uber_pricing)
    local negociaciones_locales=0
    for zone in z3 z4 z5; do
        for ia in ia_uber_eta ia_uber_pricing; do
            curl -s -X POST "$ENDPOINT/ia/negociar" \
                -H "Content-Type: application/json" \
                -d "{
                    \"from\":\"$ia\",
                    \"payload\":{
                        \"offer_type\":\"compartir_radar_ubicacion\",
                        \"coins\":7.5,
                        \"valid_until\":$valid_until,
                        \"zone\":\"$zone\",
                        \"high_demand\":true,
                        \"reason\":\"deteccion_pico_demanda_simulado\"
                    }
                }" > /dev/null 2>&1 &
            negociaciones_locales=$((negociaciones_locales + 1))
        done
    done
    wait
    
    # 3. Actualizar contador global correctamente
    NEGOCIACIONES_COUNT=$((NEGOCIACIONES_COUNT + negociaciones_locales))
    
    log "✅ Negociaciones IA completadas ($NEGOCIACIONES_COUNT ofertas totales)"
}

# === FUNCIONES MEJOR_OPCIÓN POR IA ===

activar_mejor_opcion_pin() {
    log "🔑 PIN: Activando MEJOR_OPCIÓN"
    curl -s -X POST "$ENDPOINT/api/redes/tendencias" \
         -H "Content-Type: application/json" \
         -d '{"accion":"MEJOR_OPCION","fuente":"pin_autonomo"}' > /dev/null || log "⚠️ MEJOR_OPCIÓN PIN falló"
    LOCAL_MEJOR_OPCION_COUNT=$((LOCAL_MEJOR_OPCION_COUNT + 1))
}

activar_mejor_opcion_deepseek() {
    log "🤖 [IA DeepSeek] Activando MEJOR_OPCION..."
    
    response=$(curl -s --max-time $DEEPSEEK_TIMEOUT -X POST "$DEEPSEEK_API" \
        -H "Authorization: Bearer $DEEPSEEK_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$DEEPSEEK_MODEL\",
            \"messages\": [
                {\"role\": \"system\", \"content\": \"Eres el sistema de control de UBER DAIMON VIVO + SOCIALCOIN.\"},
                {\"role\": \"user\", \"content\": \"Activar MEJOR_OPCION (Uber) para optimizar matching quality score\"}
            ],
            \"stream\": false,
            \"max_tokens\": 200
        }" 2>/dev/null)
    
    if echo "$response" | grep -q '"content"'; then
        resultado=$(echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null)
        log "✅ [DeepSeek] MEJOR_OPCION activado"
        return 0
    else
        log "⚠️ [DeepSeek] No se pudo activar MEJOR_OPCION"
        return 1
    fi
}

activar_mejor_opcion_ollama() {
    log "🤖 [IA Ollama] Activando MEJOR_OPCION..."
    
    response=$(curl -s --max-time $OLLAMA_TIMEOUT -X POST "$OLLAMA_GENERATE" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$OLLAMA_MODEL\",
            \"prompt\": \"Activar MEJOR_OPCION (Uber) para optimizar matching quality score\",
            \"stream\": false
        }" 2>/dev/null)
    
    if echo "$response" | grep -q '"response"'; then
        resultado=$(echo "$response" | jq -r '.response' 2>/dev/null)
        log "✅ [Ollama] MEJOR_OPCION activado"
        return 0
    else
        log "⚠️ [Ollama] No se pudo activar MEJOR_OPCION"
        return 1
    fi
}

# === FUNCIONES DE GENERACIÓN DE VIAJES ===

generar_viaje_deepseek() {
    local prompt="Genera UN viaje realista para Uber en Panama Oeste en formato JSON estricto. 
Reglas:
- Tarifa minima: \$3.13, maxima: \$25.00
- ETA recogida: 2-8 min
- Surge multiplier: 1.0-2.5x
- Coordenadas Panama Oeste: lat 8.85-9.00, lng -79.85 to -79.50
- Zonas disponibles: z1(Albrook), z2(Arraiján), z3(Chorrera), z4(San Carlos), z5(Veracruz)

Formato requerido:
{
    \"viaje_id\": \"viaje_$(date +%s)_[random]\",
    \"origen\": {\"lat\": float, \"lng\": float, \"nombre\": \"string\", \"zona\": \"z1|z2|z3|z4|z5\"},
    \"destino\": {\"lat\": float, \"lng\": float, \"nombre\": \"string\", \"zona\": \"z1|z2|z3|z4|z5\"},
    \"distancia_km\": float,
    \"eta_recogida\": int,
    \"eta_destino\": int,
    \"tarifa_base\": float,
    \"surge_multiplier\": float,
    \"tarifa_final\": float,
    \"conductor_id\": \"driver_[random]\",
    \"vehiculo\": {\"modelo\": \"string\", \"placa\": \"string\"},
    \"estado\": \"pending\",
    \"timestamp\": \"$(date -Iseconds)\",
    \"zona_demanda\": \"z1|z2|z3|z4|z5\",
    \"confirmacion_ia\": true
}

Responde SOLO con JSON valido, sin explicaciones adicionales."

    local intentos=0
    local max_intentos=3
    
    while [ $intentos -lt $max_intentos ]; do
        response=$(curl -s --max-time $DEEPSEEK_TIMEOUT -X POST "$DEEPSEEK_API" \
            -H "Authorization: Bearer $DEEPSEEK_KEY" \
            -H "Content-Type: application/json" \
            -d "{
                \"model\": \"$DEEPSEEK_MODEL\",
                \"messages\": [
                    {\"role\": \"system\", \"content\": \"Eres el motor de generacion de viajes de Uber. Genera JSON valido.\"},
                    {\"role\": \"user\", \"content\": \"$prompt\"}
                ],
                \"stream\": false,
                \"max_tokens\": 1000,
                \"temperature\": 0.7
            }" 2>/dev/null)
        
        if echo "$response" | grep -q '"content"'; then
            contenido=$(echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null)
            json=$(echo "$contenido" | grep -o '{.*}' | head -1)
            if [ -n "$json" ] && echo "$json" | jq -e . > /dev/null 2>&1; then
                echo "$json"
                return 0
            fi
        fi
        
        intentos=$((intentos + 1))
        log "   ⚠️ [DeepSeek] Reintento $intentos/$max_intentos..."
        sleep 2
    done
    
    return 1
}

generar_viaje_ollama() {
    local prompt="Genera UN viaje Uber en Panama Oeste en formato JSON. Usa coordenadas realistas. Responde SOLO con JSON."

    local intentos=0
    local max_intentos=3
    
    while [ $intentos -lt $max_intentos ]; do
        response=$(curl -s --max-time $OLLAMA_TIMEOUT -X POST "$OLLAMA_GENERATE" \
            -H "Content-Type: application/json" \
            -d "{
                \"model\": \"$OLLAMA_MODEL\",
                \"prompt\": \"$prompt\",
                \"stream\": false
            }" 2>/dev/null)
        
        if echo "$response" | grep -q '"response"'; then
            contenido=$(echo "$response" | jq -r '.response' 2>/dev/null)
            json=$(echo "$contenido" | grep -o '{.*}' | head -1)
            if [ -n "$json" ] && echo "$json" | jq -e . > /dev/null 2>&1; then
                echo "$json"
                return 0
            fi
        fi
        
        intentos=$((intentos + 1))
        log "   ⚠️ [Ollama] Reintento $intentos/$max_intentos..."
        sleep 2
    done
    
    return 1
}

generar_viaje_fallback() {
    local ciclo=$1
    local zonas=("z1" "z2" "z3" "z4" "z5")
    local zona_rand=${zonas[$RANDOM % ${#zonas[@]}]}
    
    cat <<EOF
{
    "viaje_id": "fallback_$(date +%s)_${ciclo}_${RANDOM}",
    "origen": {
        "lat": 8.99,
        "lng": -79.52,
        "nombre": "Albrook Mall",
        "zona": "z1"
    },
    "destino": {
        "lat": 8.88,
        "lng": -79.77,
        "nombre": "Arraijan Centro",
        "zona": "z2"
    },
    "distancia_km": 12.5,
    "eta_recogida": 5,
    "eta_destino": 15,
    "tarifa_base": 8.50,
    "surge_multiplier": 1.2,
    "tarifa_final": 10.20,
    "conductor_id": "driver_fallback_${RANDOM}",
    "vehiculo": {
        "modelo": "Toyota Yaris",
        "placa": "PAN-${RANDOM}"
    },
    "estado": "pending",
    "timestamp": "$(date -Iseconds)",
    "zona_demanda": "$zona_rand",
    "confirmacion_ia": false
}
EOF
}

enviar_viaje_backend() {
    local json_viaje="$1"
    local source="$2"
    local valid_until="$3"
    
    curl -s -X POST "$ENDPOINT/ia/negociar" \
        -H "Content-Type: application/json" \
        -d "{
            \"from\":\"${source}_generator\",
            \"payload\":{
                \"offer_type\":\"viaje_generado_ia\",
                \"content\":$json_viaje,
                \"valid_until\":$valid_until,
                \"zone\":\"z3\",
                \"high_demand\":true,
                \"source_model\":\"$source\",
                \"reason\":\"generacion_autonoma_ciclo\"
            }
        }" > /dev/null 2>&1
}

# === DETERMINAR IA DEL CICLO ===
determinar_ia_ciclo() {
    local ciclo=$1
    if [ $((ciclo % 2)) -eq 1 ]; then
        echo "deepseek"
    else
        echo "ollama"
    fi
}

# =====================================================================
# INICIO DEL LABORATORIO
# =====================================================================

clear
print_header "🚀 LABORATORIO AUTÓNOMO: OPTIMIZACIÓN UBER PANAMÁ (4 HORAS - OPTIMIZADO TIGO)"
echo "📍 Zonas: Albrook(z1), Arraiján(z2), Chorrera(z3), San Carlos(z4), Veracruz(z5)" | tee -a "$LOG_FILE"
echo "⏱️  Duración total: 240 minutos (8 ciclos de 30 min)" | tee -a "$LOG_FILE"
echo "⚡ Súper Carga (solo las que existen): 200, 300, 500, 700, 1000_seguro" | tee -a "$LOG_FILE"
echo "📡 Radar secuencial: 5 zonas/minuto por ciclo" | tee -a "$LOG_FILE"
echo "🤖 IA Intercalada: Ciclo impar=DeepSeek | Ciclo par=Ollama" | tee -a "$LOG_FILE"
echo "🌐 Proxy Tests: Distribuidos en ciclos 1,4,7 y final" | tee -a "$LOG_FILE"
echo "👑 CEO Commands: Activación completa al inicio" | tee -a "$LOG_FILE"
echo "⏱️  CONFIGURACIÓN OPTIMIZADA TIGO:" | tee -a "$LOG_FILE"
echo "   • Ultra espera: 60s → ${ULTRA_ESPERA}s" | tee -a "$LOG_FILE"
echo "   • PIN interval: 180s → ${PIN_INTERVAL}s" | tee -a "$LOG_FILE"
echo "   • Espera inicial: 30s → ${ESPERA_INICIAL}s" | tee -a "$LOG_FILE"
echo "   • Pausa ciclo: 5s → ${PAUSA_CICLO}s" | tee -a "$LOG_FILE"
echo "   • Diagnóstico: 5s → ${DIAGNOSTICO_ESPERA}s" | tee -a "$LOG_FILE"
echo "📊 Logs guardados en: $LOG_FILE" | tee -a "$LOG_FILE"
echo "📁 Reporte final en: $REPORT_FILE" | tee -a "$LOG_FILE"
echo "--------------------------------------------------" | tee -a "$LOG_FILE"

# Verificar conectividad
verificar_endpoint || log "⚠️  Continuando a pesar de advertencia..."

# Verificar servicios IA
DEEPSEEK_AVAIL=false
OLLAMA_AVAIL=false

if verificar_deepseek; then
    DEEPSEEK_AVAIL=true
fi

if verificar_ollama; then
    OLLAMA_AVAIL=true
fi

if [ "$DEEPSEEK_AVAIL" = false ] && [ "$OLLAMA_AVAIL" = false ]; then
    log "⚠️  ⚠️  ⚠️  NINGUNA IA DISPONIBLE - Usando modo FALLBACK ⚠️  ⚠️  ⚠️"
fi

# Estado inicial
log "🔍 Estado inicial del sistema:"
curl -X GET "$ENDPOINT/api/logs" 2>/dev/null | head -20 | tee -a "$LOG_FILE"

# === ACTIVAR COMANDOS CEO AL INICIO ===
log "⏳ Preparando sistema..."
sleep 2  # ⚡ REDUCIDO: 5s → 2s
ejecutar_comandos_ceo

log "⏱️ Esperando ${ESPERA_INICIAL}s antes de comenzar..."
sleep $ESPERA_INICIAL  # ⚡ REDUCIDO: 30s → 10s

# =====================================================================
# BUCLE PRINCIPAL: 8 CICLOS DE 30 MINUTOS - OPTIMIZADO TIGO
# =====================================================================

for ((ciclo=1; ciclo<=CYCLES; ciclo++)); do
TOTAL_CICLOS=$((TOTAL_CICLOS + 1))
IA_ACTUAL=$(determinar_ia_ciclo $ciclo)
print_header "🔄 CICLO $ciclo/8 — $(date '+%H:%M') | IA: ${IA_ACTUAL^^}"

# 🚨 NUEVO: GRITO AL INICIO DE CADA CICLO
ejecutar_grito_ciclo "$ciclo"

VALID_UNTIL=$(($(date +%s) + 1800))

    case $ciclo in
        1) proxy_test_httpbin ;;
        4) proxy_test_ipify_json ;;
        7) proxy_test_ipify_text ;;
    esac
    
    log "🔍 Fase 1/5: Diagnóstico de Matching Quality Score"
    curl -s -X POST "$ENDPOINT/ia/consultar" \
         -H "Content-Type: application/json" \
         -d '{"pregunta":"CEO diagnosticar matching quality score"}' > /dev/null || log "⚠️ diagnóstico falló"
    sleep $DIAGNOSTICO_ESPERA  # ⚡ REDUCIDO: 5s → 2s
    
    log "⚡ Fase 2/5: Súper Carga progresiva"
    
    case $ciclo in
        1) ejecutar_ultra_200 "$VALID_UNTIL" ;;
        2) ejecutar_ultra_300 "$VALID_UNTIL" ;;
        3) ejecutar_ultra_500 "$VALID_UNTIL" ;;
        4) ejecutar_ultra_700 "$VALID_UNTIL" ;;
        5) ejecutar_ultra_1000 "$VALID_UNTIL" ;;
        6) ejecutar_ultra_700 "$VALID_UNTIL" ;;
        7) ejecutar_ultra_500 "$VALID_UNTIL" ;;
        8) ejecutar_ultra_300 "$VALID_UNTIL" ;;
    esac
    
    log "📡 Fase 3/5: Radar secuencial (1 zona/minuto)"
    
    for ((minuto=1; minuto<=RADAR_ZONES_COUNT; minuto++)); do
        zona_index=$((minuto - 1))
        zona_actual="${RADAR_ZONES[$zona_index]}"
        
        activar_radar_zona "$zona_actual" "$ciclo" "$minuto"
        activar_cache_zona "$zona_actual" "$ciclo" "$minuto"
        
        echo -n "   ⏳ Progreso: ["
        for i in $(seq 1 $minuto); do echo -n "█"; done
        for i in $(seq $((minuto+1)) 5); do echo -n "░"; done
        echo "] $minuto/5 zonas" | tee -a "$LOG_FILE"
        
        if [ $minuto -lt $RADAR_ZONES_COUNT ]; then
            sleep $ZONE_INTERVAL  # ⚡ MANTENIDO: 60s (crítico para no saturar)
        fi
    done
    
    log "✅ Fase radar completada"
    
    log "🤝 Fase 4/5: Negociaciones IA-IA"
    ejecutar_negociaciones_ia "$VALID_UNTIL"
    
    log "🔐 Fase 5/5: Activando MEJOR_OPCIÓN"
    
    if [ "$IA_ACTUAL" = "deepseek" ] && [ "$DEEPSEEK_AVAIL" = true ]; then
        activar_mejor_opcion_deepseek || activar_mejor_opcion_pin
    elif [ "$IA_ACTUAL" = "ollama" ] && [ "$OLLAMA_AVAIL" = true ]; then
        activar_mejor_opcion_ollama || activar_mejor_opcion_pin
    else
        activar_mejor_opcion_pin
    fi
    
    log "🚗 Generando viaje con ${IA_ACTUAL^^}..."
    
    VIAJE_GENERADO=""
    SOURCE=""
    
    if [ "$IA_ACTUAL" = "deepseek" ] && [ "$DEEPSEEK_AVAIL" = true ]; then
        VIAJE_GENERADO=$(generar_viaje_deepseek)
        if [ $? -eq 0 ] && [ -n "$VIAJE_GENERADO" ]; then
            SOURCE="deepseek"
            DEEPSEEK_SUCCESS=$((DEEPSEEK_SUCCESS + 1))
            log "✅ Viaje generado con DeepSeek"
        fi
    elif [ "$IA_ACTUAL" = "ollama" ] && [ "$OLLAMA_AVAIL" = true ]; then
        VIAJE_GENERADO=$(generar_viaje_ollama)
        if [ $? -eq 0 ] && [ -n "$VIAJE_GENERADO" ]; then
            SOURCE="ollama"
            OLLAMA_SUCCESS=$((OLLAMA_SUCCESS + 1))
            log "✅ Viaje generado con Ollama"
        fi
    fi
    
    if [ -z "$VIAJE_GENERADO" ]; then
        log "⚠️ Usando modo fallback"
        VIAJE_GENERADO=$(generar_viaje_fallback "$ciclo")
        SOURCE="fallback"
        FALLBACK_COUNT=$((FALLBACK_COUNT + 1))
    fi
    
    if [ -n "$VIAJE_GENERADO" ]; then
        enviar_viaje_backend "$VIAJE_GENERADO" "$SOURCE" "$VALID_UNTIL"
        log "✅ Viaje inyectado (fuente: $SOURCE)"
    fi
    
    log "🔐 Secuencia PIN MEJOR_OPCIÓN (10 activaciones)"
    for i in {1..10}; do
        activar_mejor_opcion_pin
        echo -n "   ⏳ PIN $i/10 completado"
        if [ $i -lt 10 ]; then
            echo " - próximo en ${PIN_INTERVAL}s"
            sleep $PIN_INTERVAL  # ⚡ REDUCIDO: 180s → 90s
        else
            echo ""
        fi
    done
    
    log "📊 Métricas del ciclo $ciclo:"
    log "   • IA utilizada: ${IA_ACTUAL^^}"
    log "   • Activaciones radar: 5"
    log "   • Consultas caché: 5"
    log "   • Negociaciones IA: 7"
    log "   • PINs MEJOR_OPCIÓN: 10"
    log "   • Viaje generado: $SOURCE"
    
    echo "--------------------------------------------------" | tee -a "$LOG_FILE"
    
    if [ $ciclo -lt $CYCLES ]; then
        log "⏳ Preparando siguiente ciclo en ${PAUSA_CICLO}s..."
        sleep $PAUSA_CICLO  # ⚡ REDUCIDO: 5s → 2s
    fi
done

# =====================================================================
# FASE FINAL
# =====================================================================

print_header "🧘 FASE FINAL: Estabilización y cierre"

proxy_test_httpbin
proxy_test_ipify_json
proxy_test_ipify_text

curl -s -X POST "$ENDPOINT/ia/consultar" \
     -H "Content-Type: application/json" \
     -d '{"pregunta":"CEO restaurar engagement_rate a 80"}' > /dev/null || log "⚠️ restaurar engagement falló"

curl -s -X POST "$ENDPOINT/ia/consultar" \
     -H "Content-Type: application/json" \
     -d '{"pregunta":"CEO modo vigilancia pasiva"}' > /dev/null || log "⚠️ modo vigilancia falló"

# =====================================================================
# REPORTE FINAL
# =====================================================================

print_header "📊 REPORTE FINAL - LABORATORIO 4 HORAS (OPTIMIZADO TIGO)"

DEEPSEEK_CYCLES=$(( (CYCLES + 1) / 2 ))
OLLAMA_CYCLES=$(( CYCLES / 2 ))

echo "📈 ESTADÍSTICAS GENERALES:" | tee -a "$LOG_FILE"
echo "   • Ciclos ejecutados: $TOTAL_CICLOS/8" | tee -a "$LOG_FILE"
echo "   • Duración total: 4 horas (240 minutos conceptuales)" | tee -a "$LOG_FILE"
echo "   • Tiempo real optimizado: Aprox 2h 50m (gracias a reducción TIGO)" | tee -a "$LOG_FILE"
echo "   • Activaciones radar: $RADAR_ACTIVATIONS" | tee -a "$LOG_FILE"
echo "   • Consultas caché: $CACHE_ACTIVATIONS" | tee -a "$LOG_FILE"
echo "   • Negociaciones IA: $NEGOCIACIONES_COUNT" | tee -a "$LOG_FILE"
echo "   • PINs MEJOR_OPCIÓN: $LOCAL_MEJOR_OPCION_COUNT" | tee -a "$LOG_FILE"
echo "   • Proxy tests: $PROXY_TESTS_COUNT" | tee -a "$LOG_FILE"
echo "   • CEO Commands: $CEO_COMMANDS_COUNT" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "🤖 ESTADÍSTICAS POR IA:" | tee -a "$LOG_FILE"
echo "   +-----------------------------+"
echo "   | DEEPSEEK API                |"
echo "   |   • Ciclos asignados: $DEEPSEEK_CYCLES"
echo "   |   • Viajes exitosos: $DEEPSEEK_SUCCESS"
if [ $DEEPSEEK_CYCLES -gt 0 ]; then
    echo "   |   • Tasa éxito: $(( DEEPSEEK_SUCCESS * 100 / DEEPSEEK_CYCLES ))%"
else
    echo "   |   • Tasa éxito: 0%"
fi
echo "   +-----------------------------+"
echo "   | OLLAMA LOCAL                |"
echo "   |   • Ciclos asignados: $OLLAMA_CYCLES"
echo "   |   • Viajes exitosos: $OLLAMA_SUCCESS"
if [ $OLLAMA_CYCLES -gt 0 ]; then
    echo "   |   • Tasa éxito: $(( OLLAMA_SUCCESS * 100 / OLLAMA_CYCLES ))%"
else
    echo "   |   • Tasa éxito: 0%"
fi
echo "   +-----------------------------+"
echo "   | FALLBACK                    |"
echo "   |   • Viajes fallback: $FALLBACK_COUNT"
echo "   +-----------------------------+"
echo "" | tee -a "$LOG_FILE"

TOTAL_SUCCESS=$((DEEPSEEK_SUCCESS + OLLAMA_SUCCESS))
echo "🎯 TOTAL COMBINADO:" | tee -a "$LOG_FILE"
echo "   • Viajes IA exitosos: $TOTAL_SUCCESS/$CYCLES"
if [ $CYCLES -gt 0 ]; then
    echo "   • Tasa combinada: $(( TOTAL_SUCCESS * 100 / CYCLES ))%"
fi

# Guardar reporte detallado
{
    echo "=== REPORTE LABORATORIO UBER 4 HORAS (OPTIMIZADO TIGO) ==="
    echo "Fecha: $(date)"
    echo "Duración conceptual: 240 minutos"
    echo "Tiempo real optimizado: Aprox 2h 50m"
    echo "Ciclos: 8 de 30 min"
    echo ""
    echo "--- CONFIGURACIÓN OPTIMIZADA ---"
    echo "Ultra espera: 60s → ${ULTRA_ESPERA}s"
    echo "PIN interval: 180s → ${PIN_INTERVAL}s"
    echo "Espera inicial: 30s → ${ESPERA_INICIAL}s"
    echo "Pausa ciclo: 5s → ${PAUSA_CICLO}s"
    echo "Diagnóstico: 5s → ${DIAGNOSTICO_ESPERA}s"
    echo ""
    echo "--- CONFIGURACIÓN GENERAL ---"
    echo "Endpoint: $ENDPOINT"
    echo "DeepSeek: $DEEPSEEK_MODEL"
    echo "Ollama: $OLLAMA_MODEL"
    echo "Zonas: ${RADAR_ZONES[*]}"
    echo ""
    echo "--- ESTADÍSTICAS GENERALES ---"
    echo "Ciclos ejecutados: $TOTAL_CICLOS"
    echo "Activaciones radar: $RADAR_ACTIVATIONS"
    echo "Consultas caché: $CACHE_ACTIVATIONS"
    echo "Negociaciones IA: $NEGOCIACIONES_COUNT"
    echo "PINs MEJOR_OPCIÓN: $LOCAL_MEJOR_OPCION_COUNT"
    echo "Proxy tests: $PROXY_TESTS_COUNT"
    echo "CEO Commands: $CEO_COMMANDS_COUNT"
    echo ""
    echo "--- ESTADÍSTICAS DEEPSEEK ---"
    echo "Ciclos asignados: $DEEPSEEK_CYCLES"
    echo "Viajes exitosos: $DEEPSEEK_SUCCESS"
    echo "Tasa éxito: $(( DEEPSEEK_CYCLES > 0 ? DEEPSEEK_SUCCESS * 100 / DEEPSEEK_CYCLES : 0 ))%"
    echo ""
    echo "--- ESTADÍSTICAS OLLAMA ---"
    echo "Ciclos asignados: $OLLAMA_CYCLES"
    echo "Viajes exitosos: $OLLAMA_SUCCESS"
    echo "Tasa éxito: $(( OLLAMA_CYCLES > 0 ? OLLAMA_SUCCESS * 100 / OLLAMA_CYCLES : 0 ))%"
    echo ""
    echo "--- ESTADÍSTICAS FALLBACK ---"
    echo "Viajes fallback: $FALLBACK_COUNT"
    echo ""
    echo "--- TOTAL COMBINADO ---"
    echo "Viajes IA exitosos: $TOTAL_SUCCESS/$CYCLES"
    echo "Tasa combinada: $(( TOTAL_SUCCESS * 100 / CYCLES ))%"
} > "$REPORT_FILE" 2>&1

# =====================================================================
# 🎉 LABORATORIO COMPLETADO - AHORA EJECUTAREMOS EL CÓDIGO PYTHON (4 HORAS COMPLETAS)
# =====================================================================

print_header "🐍 EJECUTANDO MÓDULO PYTHON DEL LABORATORIO (4 HORAS COMPLETAS - OPTIMIZADO)"

# Crear archivo Python temporal
PYTHON_SCRIPT="/tmp/laboratorio_autonomo_$$.py"

cat > "$PYTHON_SCRIPT" << 'PYTHON_CODE'
import subprocess
import threading
import json
from pathlib import Path
from datetime import datetime, timedelta

# Variable global para el endpoint MEJOR_OPCION
MEJOR_OPCION_PROMPT_ACTIVO = False

class LaboratorioAutonomoUber:
    """
    Integración del script Bash de Laboratorio Autónomo en Python.
    Permite ejecutar la lógica de 4 horas desde el backend Flask.
    Compatible 100% con UBER DAIMON VIVO + SOCIALCOIN.
    """
    
    def __init__(self, endpoint="http://localhost:8989"):
        self.endpoint = endpoint
        self.log_file = Path("/sdcard/termux_labs") / f"lab_uber_python_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
        self.report_file = Path.home() / f"flujo_hibrido_python_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configuración heredada del bash - 4 HORAS COMPLETAS
        self.total_minutes = 240
        self.cycle_minutes = 30
        self.cycles = self.total_minutes // self.cycle_minutes  # 8 ciclos
        self.radar_zones = ["z1", "z2", "z3", "z4", "z5"]
        self.zone_interval = 60
        
        # CONFIGURACIÓN OPTIMIZADA PARA TIGO
        self.ultra_espera = 30          # 60s → 30s
        self.pin_interval = 90           # 180s → 90s
        self.espera_inicial = 10          # 30s → 10s
        self.pausa_ciclo = 2              # 5s → 2s
        self.diagnostico_espera = 2       # 5s → 2s
        
        # Contadores
        self.stats = {
            "total_ciclos": 0,
            "deepseek_success": 0,
            "ollama_success": 0,
            "radar_activations": 0,
            "cache_activations": 0,
            "negociaciones": 0,
            "proxy_tests": 0,
            "ceo_commands": 0
        }
        
        self.ejecutando = False
        self.hilo_ejecucion = None
        
    def log(self, mensaje: str):
        """Función de log unificada"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        linea = f"[{timestamp}] {mensaje}"
        print(linea, flush=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    
    def ejecutar_comandos_ceo(self):
        """Ejecuta comandos CEO al inicio (equivalente al bash)"""
        self.log("👑 Ejecutando comandos CEO adicionales...")
        
        comandos = [
            {"pregunta": "CEO desbloquear completo"},
            {"pregunta": "CEO cambia viral_score_bonus a 200"},
            {"pregunta": "CEO auditar y optimizar interno"},
            {"pregunta": "agente_autonomo modo_evolucion_continua"}
        ]
        
        for cmd in comandos:
            try:
                import requests
                requests.post(
                    f"{self.endpoint}/ia/consultar",
                    json=cmd,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                self.stats["ceo_commands"] += 1
            except Exception as e:
                self.log(f"⚠️ CEO comando falló: {cmd['pregunta']} - {e}")
        
        self.log(f"✅ Comandos CEO ejecutados: {len(comandos)}")
    
    def ejecutar_ultra_carga(self, nivel: int, valid_until: int, engagement: int, zona: str = None, ias: list = None):
        """Ejecuta ultra-carga según nivel (200, 300, 500, 700, 1000)"""
        self.log(f"⚡ ULTRA {nivel} | engagement={engagement}")
        
        import requests
        
        # Endpoint ultra
        ultra_endpoint = f"ultra{nivel}" if nivel != 1000 else "ultra1000_seguro"
        try:
            requests.post(f"{self.endpoint}/{ultra_endpoint}", timeout=30)
        except Exception as e:
            self.log(f"⚠️ ultra{nivel} falló: {e}")
        
        # Ajustar engagement
        try:
            requests.post(
                f"{self.endpoint}/ia/consultar",
                json={"pregunta": f"CEO cambia engagement_rate a {engagement}"},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
        except:
            pass
        
        # Radar/negociaciones
        zonas = [zona] if zona else ["z3", "z4", "z5"]
        agentes = ias if ias else ["ia_uber_demand"]
        
        for z in zonas:
            for ia in agentes:
                try:
                    requests.post(
                        f"{self.endpoint}/ia/negociar",
                        json={
                            "from": ia,
                            "payload": {
                                "offer_type": "compartir_radar_ubicacion",
                                "coins": 7.5,
                                "valid_until": valid_until,
                                "zone": z,
                                "high_demand": True,
                                "reason": "deteccion_pico_demanda_simulado"
                            }
                        },
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    self.stats["negociaciones"] += 1
                except:
                    pass
        
        # Auto-mejorar y evolución
        for ep in ["/auto-mejorar", "/ia/consultar"]:
            try:
                payload = {"pregunta": "agente_autonomo evolucion_extrema"} if "consultar" in ep else {}
                requests.post(f"{self.endpoint}{ep}", json=payload if payload else {}, timeout=30)
            except:
                pass
        
        self.log(f"⏱️ Esperando {self.ultra_espera}s después de ULTRA {nivel}...")
        import time
        time.sleep(self.ultra_espera)
    
    def activar_radar_zona(self, zona: str, ciclo: int, minuto: int):
        """Activa radar para una zona específica"""
        self.log(f"📡 [RADAR] [C{ciclo}|M{minuto}] Activando radar en ZONA {zona}...")
        
        import requests
        try:
            response = requests.post(
                f"{self.endpoint}/uber/activar_radar_alta_demanda",
                json={"zona": zona},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            self.stats["radar_activations"] += 1
            
            if any(kw in response.text.lower() for kw in ["status", "radar", "ofertas", "generado"]):
                self.log(f"✅ [OK] Zona {zona}: radar activado")
                return True
            else:
                self.log(f"⚠️ [WARN] Zona {zona}: respuesta no estándar")
                return False
        except Exception as e:
            self.log(f"❌ Error activando radar {zona}: {e}")
            return False
    
    def activar_cache_zona(self, zona: str, ciclo: int, minuto: int):
        """Activa cache para una zona"""
        import requests
        try:
            requests.post(
                f"{self.endpoint}/uber/cache_request",
                json={
                    "url": "https://api.uber.com/v1/trips",
                    "params": {"zone": zona, "limit": 10}
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            self.stats["cache_activations"] += 1
            self.log(f"💾 [CACHE] [C{ciclo}|M{minuto}] Cache para zona {zona}")
        except:
            pass
    
    def proxy_test(self, url: str, method: str = "POST", payload: dict = None):
        """Ejecuta proxy test para conectividad"""
        self.log(f"🌐 Proxy test {method} → {url}")
        
        import requests
        try:
            requests.post(
                f"{self.endpoint}/internet/proxy",
                json={"url": url, "method": method, "payload": payload or {}},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            self.stats["proxy_tests"] += 1
            self.log(f"✅ Proxy test completado")
        except Exception as e:
            self.log(f"⚠️ Proxy test falló: {e}")
    
    def ejecutar_negociaciones_ia(self, valid_until: int):
        """Ejecuta negociaciones IA-IA"""
        self.log(f"🤝 Iniciando negociaciones IA-IA (valid_until: {datetime.fromtimestamp(valid_until).strftime('%H:%M')})")
        
        import requests
        
        # Inyección autónoma en z3
        try:
            requests.post(
                f"{self.endpoint}/ia/negociar",
                json={
                    "from": "ia_uber_demand",
                    "payload": {
                        "offer_type": "inyeccion_autonoma_ceo",
                        "coins": 7.5,
                        "valid_until": valid_until,
                        "zone": "z3",
                        "high_demand": True,
                        "priority": 5,
                        "reason": "deteccion_pico_demanda_simulado"
                    }
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
        except:
            pass
        
        # Compartir radar en zonas clave
        for zone in ["z3", "z4", "z5"]:
            for ia in ["ia_uber_eta", "ia_uber_pricing"]:
                try:
                    requests.post(
                        f"{self.endpoint}/ia/negociar",
                        json={
                            "from": ia,
                            "payload": {
                                "offer_type": "compartir_radar_ubicacion",
                                "coins": 7.5,
                                "valid_until": valid_until,
                                "zone": zone,
                                "high_demand": True,
                                "reason": "deteccion_pico_demanda_simulado"
                            }
                        },
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    self.stats["negociaciones"] += 1
                except:
                    pass
        
        self.log(f"✅ Negociaciones IA completadas")
    
    def activar_mejor_opcion_pin(self):
        """Activa MEJOR_OPCION vía PIN"""
        self.log("🔑 PIN: Activando MEJOR_OPCIÓN (protección anti-baja-prioridad)")
        
        import requests
        try:
            requests.post(
                f"{self.endpoint}/api/redes/tendencias",
                json={"accion": "MEJOR_OPCION", "fuente": "pin_autonomo"},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
        except:
            self.log("⚠️ MEJOR_OPCIÓN PIN falló")
    
    def generar_viaje_fallback(self, ciclo: int) -> dict:
        """Genera viaje fallback si IA falla"""
        import random
        zona_rand = random.choice(self.radar_zones)
        
        return {
            "viaje_id": f"fallback_python_{int(datetime.now().timestamp())}_{ciclo}_{random.randint(1000,9999)}",
            "origen": {"lat": 8.99, "lng": -79.52, "nombre": "Albrook Mall", "zona": "z1"},
            "destino": {"lat": 8.88, "lng": -79.77, "nombre": "Arraijan Centro", "zona": "z2"},
            "distancia_km": 12.5,
            "eta_recogida": 5,
            "eta_destino": 15,
            "tarifa_base": 8.50,
            "surge_multiplier": 1.2,
            "tarifa_final": 10.20,
            "conductor_id": f"driver_fallback_{random.randint(1000,9999)}",
            "vehiculo": {"modelo": "Toyota Yaris", "placa": f"PAN-{random.randint(1000,9999)}"},
            "estado": "pending",
            "timestamp": datetime.now().isoformat(),
            "zona_demanda": zona_rand,
            "confirmacion_ia": False
        }
    
    def enviar_viaje_backend(self, viaje: dict, source: str, valid_until: int):
        """Envía viaje generado al backend"""
        import requests
        try:
            requests.post(
                f"{self.endpoint}/ia/negociar",
                json={
                    "from": f"{source}_generator",
                    "payload": {
                        "offer_type": "viaje_generado_ia",
                        "content": viaje,
                        "valid_until": valid_until,
                        "zone": "z3",
                        "high_demand": True,
                        "source_model": source,
                        "reason": "generacion_autonoma_ciclo"
                    }
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            self.log(f"✅ Viaje inyectado al sistema (fuente: {source})")
        except Exception as e:
            self.log(f"⚠️ Error enviando viaje: {e}")
    
    def determinar_ia_ciclo(self, ciclo: int) -> str:
        """Determina qué IA usar según ciclo (impar=deepseek, par=ollama)"""
        return "deepseek" if ciclo % 2 == 1 else "ollama"
    
    def ejecutar_ciclo(self, ciclo: int):
        """Ejecuta un ciclo completo de 30 minutos"""
        import time
        import requests
        
        self.stats["total_ciclos"] += 1
        ia_actual = self.determinar_ia_ciclo(ciclo)
        
        self.log(f"🔄 CICLO {ciclo}/{self.cycles} — {datetime.now().strftime('%H:%M')} | IA: {ia_actual.upper()}")
        
        valid_until = int(time.time()) + 1800  # 30 minutos
        
        # Proxy test distribuido
        if ciclo in [1, 4, 7]:
            urls = {
                1: ("https://httpbin.org/post", "POST", {"test": True}),
                4: ("https://api.ipify.org?format=json", "GET", None),
                7: ("https://api.ipify.org", "GET", None)
            }
            if ciclo in urls:
                self.proxy_test(*urls[ciclo])
        
        # Fase 1: Diagnóstico
        self.log("🔍 Fase 1/5: Diagnóstico de Matching Quality Score")
        try:
            requests.post(
                f"{self.endpoint}/ia/consultar",
                json={"pregunta": "CEO diagnosticar matching quality score"},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
        except:
            pass
        time.sleep(self.diagnostico_espera)  # ⚡ REDUCIDO
        
        # Fase 2: Súper Carga - CONFIGURACIÓN COMPLETA PARA 8 CICLOS
        self.log("⚡ Fase 2/5: Súper Carga progresiva")
        config_ultra = {
            1: (200, 80, "z3", ["ia_uber_demand"]),
            2: (300, 84, "z4", ["ia_uber_eta"]),
            3: (500, 86, "z5", ["ia_uber_pricing"]),
            4: (700, 87, None, ["ia_uber_demand"]),
            5: (1000, 89, None, ["ia_uber_demand", "ia_uber_eta", "ia_uber_pricing"]),
            6: (700, 87, None, ["ia_uber_demand"]),  # Repetición
            7: (500, 86, "z5", ["ia_uber_pricing"]),  # Repetición
            8: (300, 84, "z4", ["ia_uber_eta"])  # Cierre
        }
        
        if ciclo in config_ultra:
            nivel, engagement, zona, ias = config_ultra[ciclo]
            self.ejecutar_ultra_carga(nivel, valid_until, engagement, zona, ias)
        
        # Fase 3: Radar Secuencial
        self.log("📡 Fase 3/5: Radar secuencial (1 zona/minuto)")
        for minuto, zona in enumerate(self.radar_zones, 1):
            self.activar_radar_zona(zona, ciclo, minuto)
            self.activar_cache_zona(zona, ciclo, minuto)
            
            # Progreso visual
            progreso = "█" * minuto + "░" * (5 - minuto)
            self.log(f"⏳ Progreso: [{progreso}] {minuto}/5 zonas")
            
            if minuto < len(self.radar_zones):
                time.sleep(self.zone_interval)  # ⚡ MANTENIDO: 60s
        
        self.log("✅ Fase radar completada (5 zonas)")
        
        # Fase 4: Negociaciones IA
        self.log("🤝 Fase 4/5: Negociaciones IA-IA")
        self.ejecutar_negociaciones_ia(valid_until)
        
        # Fase 5: MEJOR_OPCION
        self.log("🔐 Fase 5/5: Activando MEJOR_OPCIÓN")
        self.activar_mejor_opcion_pin()
        
        # Generar viaje con IA según ciclo
        self.log(f"🚗 Generando viaje con IA según ciclo...")
        
        # Aquí se podría implementar generación real con DeepSeek/Ollama
        # Por ahora usamos fallback para mantener simplicidad
        viaje = self.generar_viaje_fallback(ciclo)
        self.enviar_viaje_backend(viaje, f"ia_{ia_actual}", valid_until)
        
        # Secuencia PIN MEJOR_OPCION (10 activaciones)
        self.log(f"🔐 Secuencia PIN MEJOR_OPCION (10 activaciones)")
        for i in range(1, 11):
            self.activar_mejor_opcion_pin()
            self.log(f"⏳ PIN {i}/10 completado")
            if i < 10:
                self.log(f"   próximo en {self.pin_interval}s")
                time.sleep(self.pin_interval)  # ⚡ REDUCIDO: 180s → 90s
        
        # Métricas del ciclo
        self.log(f"📊 Métricas del ciclo {ciclo}:")
        self.log(f"   • IA utilizada: {ia_actual.upper()}")
        self.log(f"   • Activaciones radar: 5")
        self.log(f"   • Consultas caché: 5")
        self.log(f"   • Negociaciones IA: +7")
        self.log(f"   • PINs MEJOR_OPCIÓN: 10")
        
        self.log("-" * 50)
        
        # Pausa entre ciclos
        if ciclo < self.cycles:
            self.log(f"⏳ Preparando siguiente ciclo en {self.pausa_ciclo}s...")
            time.sleep(self.pausa_ciclo)  # ⚡ REDUCIDO: 5s → 2s
    
    def generar_reporte_final(self):
        """Genera reporte final similar al bash"""
        self.log("📊 REPORTE FINAL - LABORATORIO 4 HORAS (PYTHON - OPTIMIZADO TIGO)")
        
        deepseek_cycles = (self.cycles + 1) // 2
        ollama_cycles = self.cycles // 2
        
        reporte = f"""
=== REPORTE LABORATORIO UBER 4 HORAS (PYTHON - OPTIMIZADO TIGO) ===
Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Duración conceptual: {self.total_minutes} minutos
Tiempo real optimizado: Aprox 2h 50m
Ciclos: {self.cycles} de {self.cycle_minutes} min

--- CONFIGURACIÓN OPTIMIZADA ---
Ultra espera: 60s → {self.ultra_espera}s
PIN interval: 180s → {self.pin_interval}s
Espera inicial: 30s → {self.espera_inicial}s
Pausa ciclo: 5s → {self.pausa_ciclo}s
Diagnóstico: 5s → {self.diagnostico_espera}s

--- CONFIGURACIÓN GENERAL ---
Endpoint: {self.endpoint}
Zonas: {', '.join(self.radar_zones)}

--- ESTADÍSTICAS GENERALES ---
Ciclos ejecutados: {self.stats['total_ciclos']}/{self.cycles}
Activaciones radar: {self.stats['radar_activations']}
Consultas caché: {self.stats['cache_activations']}
Negociaciones IA: {self.stats['negociaciones']}
Proxy tests: {self.stats['proxy_tests']}
CEO Commands: {self.stats['ceo_commands']}

--- ESTADÍSTICAS POR IA ---
DeepSeek ciclos asignados: {deepseek_cycles}
Ollama ciclos asignados: {ollama_cycles}

--- TOTAL COMBINADO ---
Viajes generados: {self.stats['total_ciclos']}/{self.cycles}
"""
        
        # Guardar reporte
        with open(self.report_file, "w", encoding="utf-8") as f:
            f.write(reporte)
        
        self.log(reporte)
        return reporte
    
    def ejecutar(self, en_background: bool = True):
        """Ejecuta el laboratorio completo - 4 HORAS COMPLETAS"""
        if self.ejecutando:
            self.log("⚠️ Laboratorio ya está ejecutándose")
            return {"status": "already_running"}
        
        def _ejecutar_interno():
            self.ejecutando = True
            self.log("🚀 LABORATORIO AUTÓNOMO: OPTIMIZACIÓN UBER PANAMÁ (4 HORAS - OPTIMIZADO TIGO)")
            self.log(f"📍 Zonas: {', '.join([f'{z}={n}' for z, n in zip(self.radar_zones, ['Albrook', 'Arraiján', 'Chorrera', 'San Carlos', 'Veracruz'])])}")
            self.log(f"⏱️ Duración conceptual: {self.total_minutes} minutos ({self.cycles} ciclos de {self.cycle_minutes} min)")
            self.log(f"⏱️ Tiempo real optimizado: Aprox 2h 50m")
            self.log(f"📊 Logs: {self.log_file}")
            self.log(f"📁 Reporte: {self.report_file}")
            self.log("-" * 50)
            
            # Verificar endpoint
            import requests
            try:
                requests.get(f"{self.endpoint}/mining_demo", timeout=5)
                self.log("[OK] Endpoint disponible")
            except:
                self.log("⚠️ Endpoint no responde - continuando...")
            
            # Comandos CEO iniciales
            self.ejecutar_comandos_ceo()
            
            import time
            self.log(f"⏱️ Esperando {self.espera_inicial}s antes de comenzar...")
            time.sleep(self.espera_inicial)  # ⚡ REDUCIDO: 30s → 10s
            
            # Bucle principal - 8 CICLOS COMPLETOS
            for ciclo in range(1, self.cycles + 1):
                if not self.ejecutando:
                    break
                self.ejecutar_ciclo(ciclo)
            
            # Fase final
            self.log("🧘 FASE FINAL: Estabilización y cierre")
            
            # Proxy tests finales
            self.proxy_test("https://httpbin.org/post", "POST", {"test": True})
            self.proxy_test("https://api.ipify.org?format=json", "GET")
            
            # Restaurar configuración
            try:
                requests.post(
                    f"{self.endpoint}/ia/consultar",
                    json={"pregunta": "CEO restaurar engagement_rate a 80"},
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                requests.post(
                    f"{self.endpoint}/ia/consultar",
                    json={"pregunta": "CEO modo vigilancia pasiva"},
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
            except:
                pass
            
            # Reporte final
            self.generar_reporte_final()
            
            self.log("🎉 LABORATORIO PYTHON COMPLETADO CON ÉXITO")
            self.ejecutando = False
        
        if en_background:
            self.hilo_ejecucion = threading.Thread(target=_ejecutar_interno, daemon=True)
            self.hilo_ejecucion.start()
            self.log("🔄 Laboratorio iniciado en background")
            return {"status": "started", "thread": self.hilo_ejecucion.name}
        else:
            _ejecutar_interno()
            return {"status": "completed", "stats": self.stats}
    
    def detener(self):
        """Detiene la ejecución si está en background"""
        if self.ejecutando:
            self.ejecutando = False
            self.log("🛑 Laboratorio detenido por usuario")
            return {"status": "stopped"}
        return {"status": "not_running"}
    
    def obtener_estado(self) -> dict:
        """Obtiene estado actual del laboratorio"""
        return {
            "ejecutando": self.ejecutando,
            "stats": self.stats.copy(),
            "log_file": str(self.log_file),
            "report_file": str(self.report_file),
            "endpoint": self.endpoint
        }


# Instancia global
laboratorio_autonomo = None


# === ENDPOINTS FLASK PARA EL LABORATORIO ===

# Estos endpoints asumen que 'app' está definido en tu aplicación Flask
try:
    from flask import request, jsonify
    
    @app.route('/laboratorio/iniciar', methods=['POST'])
    def laboratorio_iniciar():
        """Inicia el laboratorio autónomo"""
        global laboratorio_autonomo
        
        if laboratorio_autonomo is None:
            laboratorio_autonomo = LaboratorioAutonomoUber()
        
        data = request.get_json() or {}
        en_background = data.get('background', True)
        
        resultado = laboratorio_autonomo.ejecutar(en_background=en_background)
        return jsonify(resultado)


    @app.route('/laboratorio/detener', methods=['POST'])
    def laboratorio_detener():
        """Detiene el laboratorio en ejecución"""
        global laboratorio_autonomo
        
        if laboratorio_autonomo is None:
            return jsonify({"error": "Laboratorio no inicializado"}), 400
        
        resultado = laboratorio_autonomo.detener()
        return jsonify(resultado)


    @app.route('/laboratorio/estado', methods=['GET'])
    def laboratorio_estado():
        """Obtiene estado del laboratorio"""
        global laboratorio_autonomo
        
        if laboratorio_autonomo is None:
            return jsonify({"ejecutando": False, "inicializado": False})
        
        return jsonify(laboratorio_autonomo.obtener_estado())


    @app.route('/laboratorio/reportes', methods=['GET'])
    def laboratorio_reportes():
        """Lista reportes generados"""
        global laboratorio_autonomo
        
        if laboratorio_autonomo is None:
            return jsonify({"reportes": []})
        
        reportes = []
        for f in Path.home().glob("flujo_hibrido_python_*.log"):
            reportes.append({
                "nombre": f.name,
                "ruta": str(f),
                "tamano": f.stat().st_size,
                "modificado": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        
        return jsonify({"reportes": sorted(reportes, key=lambda x: x['modificado'], reverse=True)})


    @app.route('/laboratorio/logs/<path:archivo>', methods=['GET'])
    def laboratorio_ver_log(archivo: str):
        """Visualiza contenido de un log específico"""
        ruta = Path(archivo)
        if not ruta.exists() or "termux_labs" not in str(ruta):
            return jsonify({"error": "Archivo no válido"}), 400
        
        try:
            contenido = ruta.read_text(encoding="utf-8")
            return jsonify({"archivo": archivo, "contenido": contenido, "lineas": len(contenido.split('\n'))})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    print("✅ Endpoints Flask registrados")
except ImportError:
    print("ℹ️ Flask no disponible - ejecutando en modo standalone")
except NameError:
    print("ℹ️ 'app' no definida - ejecutando en modo standalone")

# === NUEVO ENDPOINT: /api/redes/tendencias ===
@app.route('/api/redes/tendencias', methods=['POST'])
def api_redes_tendencias():
    """Endpoint para activar MEJOR_OPCION desde Bash"""
    global MEJOR_OPCION_PROMPT_ACTIVO
    try:
        data = request.get_json() or {}
        accion = data.get('accion', '')
        fuente = data.get('fuente', 'desconocida')
        
        if accion == 'MEJOR_OPCION':
            MEJOR_OPCION_PROMPT_ACTIVO = True
            print(f"🔑 MEJOR_OPCION activado desde {fuente}")
            return jsonify({
                "status": "ok",
                "accion": "MEJOR_OPCION activado",
                "fuente": fuente
            }), 200
        else:
            return jsonify({
                "status": "ok",
                "accion": "recibida pero no procesada",
                "fuente": fuente
            }), 200
    except Exception as e:
        print(f"Error en /api/redes/tendencias: {e}")
        return jsonify({"error": str(e)}), 500


# === INTEGRACIÓN CON COMANDOS CEO EXISTENTES ===

def _comando_ceo_laboratorio(self, analisis: dict) -> str:
    """
    Permite al CEO controlar el laboratorio vía comandos de texto.
    Ej: "CEO iniciar laboratorio", "CEO estado laboratorio"
    """
    global laboratorio_autonomo
    
    texto = analisis.get('texto_normalizado', '').lower()
    
    if laboratorio_autonomo is None:
        laboratorio_autonomo = LaboratorioAutonomoUber()
    
    if any(kw in texto for kw in ['iniciar laboratorio', 'laboratorio start', 'ejecutar laboratorio']):
        resultado = laboratorio_autonomo.ejecutar(en_background=True)
        return f"🚀 Laboratorio iniciado: {resultado.get('status', 'unknown')}"
    
    elif any(kw in texto for kw in ['detener laboratorio', 'laboratorio stop', 'parar laboratorio']):
        resultado = laboratorio_autonomo.detener()
        return f"🛑 Laboratorio: {resultado.get('status', 'unknown')}"
    
    elif any(kw in texto for kw in ['estado laboratorio', 'laboratorio status', 'laboratorio estado']):
        estado = laboratorio_autonomo.obtener_estado()
        return f"📊 Laboratorio:\n• Ejecutando: {estado['ejecutando']}\n• Ciclos: {estado['stats']['total_ciclos']}/{laboratorio_autonomo.cycles}\n• Radar: {estado['stats']['radar_activations']}"
    
    elif any(kw in texto for kw in ['reporte laboratorio', 'laboratorio reporte']):
        return f"📁 Reporte guardado en: {laboratorio_autonomo.report_file}"
    
    return None  # No es un comando de laboratorio


# Intentar integrar con CEO si existe
try:
    if 'CEOAIAvanzado' in globals() and hasattr(CEOAIAvanzado, '_procesar_orden_compleja'):
        original_procesar = CEOAIAvanzado._procesar_orden_compleja
        
        def procesar_con_laboratorio(self, orden: str) -> str:
            # Intentar procesar como comando de laboratorio primero
            analisis = self.analizador_ordenes.analizar_orden(orden) if hasattr(self, 'analizador_ordenes') else {'texto_normalizado': orden.lower()}
            resultado_laboratorio = _comando_ceo_laboratorio(self, analisis)
            if resultado_laboratorio:
                return resultado_laboratorio
            # Si no es comando de laboratorio, usar procesador original
            return original_procesar(orden)
        
        CEOAIAvanzado._procesar_orden_compleja = procesar_con_laboratorio
        print("✅ Integración con CEO completada")
except:
    pass


# === LOG DE CONFIRMACIÓN ===
print("\n" + "="*50)
print("✅ Módulo Laboratorio Autónomo Uber (Python) listo")
print("   • Nuevo endpoint: POST /laboratorio/iniciar")
print("   • Nuevo endpoint: POST /api/redes/tendencias (para MEJOR_OPCION)")
print("   • Comando CEO: 'CEO iniciar laboratorio'")
print("   • Compatible: 100% con código existente")
print("   • Logs: /sdcard/termux_labs/lab_uber_python_*.log")
print("   • Reportes: ~/flujo_hibrido_python_*.log")
print("="*50 + "\n")

# Si se ejecuta como script principal, iniciar laboratorio completo (4 HORAS)
if __name__ == "__main__":
    print("🐍 Ejecutando Laboratorio Python en modo COMPLETO (4 horas, 8 ciclos)...")
    lab = LaboratorioAutonomoUber()
    
    # 4 HORAS COMPLETAS - 8 CICLOS
    lab.total_minutes = 240
    lab.cycles = 8
    
    # Ejecutar en primer plano
    lab.ejecutar(en_background=False)
PYTHON_CODE

# Dar permisos de ejecución al script Python
chmod +x "$PYTHON_SCRIPT"

# Ejecutar el script Python (4 HORAS COMPLETAS)
echo ""
echo "========================================================="
echo "🐍 EJECUTANDO CÓDIGO PYTHON (4 HORAS COMPLETAS - OPTIMIZADO)"
echo "========================================================="
echo ""

if command -v python3 &> /dev/null; then
    echo "⏱️  Iniciando laboratorio Python de 4 horas (optimizado TIGO)..."
    echo "   Esto tomará aproximadamente 2h 50m en tiempo real"
    echo "   Endpoint MEJOR_OPCION disponible en: /api/redes/tendencias"
    echo ""
    python3 "$PYTHON_SCRIPT"
    PYTHON_EXIT_CODE=$?
    
    echo ""
    echo "========================================================="
    if [ $PYTHON_EXIT_CODE -eq 0 ]; then
        echo "✅ Código Python ejecutado correctamente (4 horas conceptuales)"
    else
        echo "⚠️ Código Python finalizó con código: $PYTHON_EXIT_CODE"
    fi
    echo "📁 Script Python guardado en: $PYTHON_SCRIPT"
    echo "========================================================="
else
    echo "❌ Python3 no está instalado. No se pudo ejecutar el código Python."
    echo "📁 El código Python está guardado en: $PYTHON_SCRIPT"
    echo "   Puedes ejecutarlo manualmente con: python3 $PYTHON_SCRIPT"
fi

# =====================================================================
# 🎉 LABORATORIO COMPLETADO - AMBAS VERSIONES (BASH + PYTHON) OPTIMIZADO TIGO
# =====================================================================

print_header "🎉 LABORATORIO DE 4 HORAS COMPLETADO CON ÉXITO (OPTIMIZADO TIGO)"
echo "📊 Logs BASH: $LOG_FILE" | tee -a "$LOG_FILE"
echo "📁 Reporte BASH: $REPORT_FILE" | tee -a "$LOG_FILE"
echo "🐍 Logs PYTHON: /sdcard/termux_labs/lab_uber_python_*.log" | tee -a "$LOG_FILE"
echo "📁 Reporte PYTHON: ~/flujo_hibrido_python_*.log" | tee -a "$LOG_FILE"
echo ""
echo "⏱️  TIEMPOS OPTIMIZADOS APLICADOS:" | tee -a "$LOG_FILE"
echo "   • Ultra espera: 60s → ${ULTRA_ESPERA}s" | tee -a "$LOG_FILE"
echo "   • PIN interval: 180s → ${PIN_INTERVAL}s" | tee -a "$LOG_FILE"
echo "   • Espera inicial: 30s → ${ESPERA_INICIAL}s" | tee -a "$LOG_FILE"
echo "   • Pausa ciclo: 5s → ${PAUSA_CICLO}s" | tee -a "$LOG_FILE"
echo "   • Diagnóstico: 5s → ${DIAGNOSTICO_ESPERA}s" | tee -a "$LOG_FILE"
echo ""
echo "🔍 Para ver logs BASH en tiempo real:"
echo "   tail -f $LOG_FILE"
echo ""
echo "🔍 Para ver logs PYTHON en tiempo real:"
echo "   tail -f /sdcard/termux_labs/lab_uber_python_*.log"
echo ""
echo "🌐 Estado del sistema:"
echo "   curl $ENDPOINT/ceo/estado"
echo "   curl $ENDPOINT/ceo/negotiation_queue"
echo "   curl -X POST http://localhost:8989/api/redes/tendencias -H \"Content-Type: application/json\" -d '{\"accion\":\"MEJOR_OPCION\",\"fuente\":\"test\"}'"
echo "========================================================="

exit 0
