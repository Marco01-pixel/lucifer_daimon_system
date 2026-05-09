#!/data/data/com.termux/files/usr/bin/bash
# start_ollama_optimized.sh - Inicio optimizado para Symbiosis

export OLLAMA_CONTEXT_LENGTH=1024
export OLLAMA_KEEP_ALIVE=30s
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_DEBUG=false

# Verificar si ya está corriendo
if pgrep -x "ollama" > /dev/null; then
    echo "✅ Ollama ya está activo"
else
    echo "🚀 Iniciando Ollama optimizado..."
    ollama serve > /sdcard/Download/ollama.log 2>&1 &
    sleep 3
fi

# Verificar salud del servidor
if curl -s http://127.0.0.1:11434/api/tags > /dev/null; then
    echo "✅ Ollama listo para Symbiosis"
else
    echo "❌ Error: Ollama no responde"
fi
