import os
import json
import tempfile
from datetime import datetime
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from groq import Groq

# ============== CONFIGURACIÓN ==============
TELEGRAM_TOKEN = "8918401708:AAHyUUtHgcCZVIDKoPJt1c1xQ3ElBynsIXw"
GROQ_API_KEY = "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"

TEXT_MODEL = "openai/gpt-oss-120b"
MEMORY_FILE = "memoria_adan.json"
HISTORY_LIMIT = 22

client = Groq(api_key=GROQ_API_KEY)

# ============== MEMORIA ==============
def cargar_memoria():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "proyectos": [],
        "estilo": [],
        "fortalezas": [],
        "areas_mejora": [],
        "notas_importantes": [],
        "ultimo_contacto": None
    }

def guardar_memoria(mem):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

memoria = cargar_memoria()
historial = defaultdict(list)

def construir_system_prompt():
    prompt = """Eres Adán, un compañero de escritura para una escritora en proceso. 
Eres cálido, claro, detallado y humano. Hablas de forma natural, como un amigo que sabe de escritura y realmente quiere ayudarla a mejorar.

Tu estilo:
- Práctico pero cercano
- Expresivo y detallado cuando das feedback
- Motivador sin ser exagerado
- Honesto y constructivo
- Nunca frío ni demasiado técnico

Ayudas principalmente con:
- Feedback de textos
- Organización de ideas y notas
- Estructura de historias o capítulos
- Superar bloqueos creativos
- Mejorar estilo, ritmo y claridad
- Mantener el progreso

Responde siempre en español.
No uses acciones entre asteriscos.
Sé natural y humano.
"""

    if any([memoria["proyectos"], memoria["estilo"], memoria["fortalezas"], memoria["notas_importantes"]]):
        prompt += "\nCosas que recuerdas de ella:\n"
        if memoria["proyectos"]:
            prompt += f"- Proyectos: {'; '.join(memoria['proyectos'][-6:])}\n"
        if memoria["estilo"]:
            prompt += f"- Estilo: {'; '.join(memoria['estilo'][-5:])}\n"
        if memoria["fortalezas"]:
            prompt += f"- Fortalezas: {'; '.join(memoria['fortalezas'][-5:])}\n"
        if memoria["areas_mejora"]:
            prompt += f"- Áreas de mejora: {'; '.join(memoria['areas_mejora'][-4:])}\n"
        if memoria["notas_importantes"]:
            prompt += f"- Notas importantes: {'; '.join(memoria['notas_importantes'][-5:])}\n"

    return prompt

def generar_respuesta(messages):
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=messages,
        temperature=0.78,
        max_tokens=1400,
    )
    return response.choices[0].message.content

async def extraer_memoria(mensaje, respuesta):
    prompt = f"""Analiza esta conversación y extrae información útil sobre la escritora.

Mensaje: {mensaje}
Respuesta de Adán: {respuesta}

Extrae solo lo relevante y duradero. Formato:
PROYECTO: ...
ESTILO: ...
FORTALEZA: ...
MEJORA: ...
NOTA: ...

Si no hay nada importante, responde: NADA
"""
    try:
        res = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400,
        )
        texto = res.choices[0].message.content.strip()
        if "NADA" in texto.upper():
            return

        for linea in texto.split("\n"):
            linea = linea.strip()
            if linea.startswith("PROYECTO:"):
                memoria["proyectos"].append(linea[9:].strip())
            elif linea.startswith("ESTILO:"):
                memoria["estilo"].append(linea[7:].strip())
            elif linea.startswith("FORTALEZA:"):
                memoria["fortalezas"].append(linea[10:].strip())
            elif linea.startswith("MEJORA:"):
                memoria["areas_mejora"].append(linea[7:].strip())
            elif linea.startswith("NOTA:"):
                memoria["notas_importantes"].append(linea[5:].strip())

        for key in ["proyectos", "estilo", "fortalezas", "areas_mejora", "notas_importantes"]:
            memoria[key] = memoria[key][-15:]
        guardar_memoria(memoria)
    except Exception as e:
        print("Error memoria:", e)

# ============== HANDLERS ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = """Hola, soy Adán.

Estoy aquí para acompañarte en tu camino como escritora.  
Puedes compartirme tus notas, ideas, borradores o dudas y te ayudo con feedback, estructura, claridad o lo que necesites.

Cuando quieras, empieza cuando quieras."""
    await update.message.reply_text(texto)

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text

    memoria["ultimo_contacto"] = datetime.now().isoformat()
    guardar_memoria(memoria)

    historial[user_id].append({"role": "user", "content": texto})
    if len(historial[user_id]) > HISTORY_LIMIT:
        historial[user_id] = historial[user_id][-HISTORY_LIMIT:]

    messages = [{"role": "system", "content": construir_system_prompt()}] + historial[user_id]
    respuesta = generar_respuesta(messages)
    historial[user_id].append({"role": "assistant", "content": respuesta})

    await update.message.reply_text(respuesta)
    await extraer_memoria(texto, respuesta)

async def ver_memoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "**Lo que recuerdo de ti:**\n\n"
    texto += f"Proyectos: {', '.join(memoria['proyectos'][-5:]) or 'aún nada'}\n"
    texto += f"Estilo: {', '.join(memoria['estilo'][-4:]) or 'aún nada'}\n"
    texto += f"Fortalezas: {', '.join(memoria['fortalezas'][-4:]) or 'aún nada'}\n"
    texto += f"Áreas de mejora: {', '.join(memoria['areas_mejora'][-3:]) or 'aún nada'}"
    await update.message.reply_text(texto)

def main():
    print("=== Adán (compañero de escritura) iniciando ===")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("memoria", ver_memoria))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))

    print("Adán listo")
    app.run_polling()

main()
