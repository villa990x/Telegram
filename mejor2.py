import sqlite3
import requests
from datetime import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pytz
import re

TOKEN = '7688814616:AAHa77JewKP7DRZdA_ZhVwIYXYnRrx9c5lo'

# Función para crear la base de datos y la tabla de precios
def crear_db():
    conn = sqlite3.connect('precios.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS precios (
            nombre TEXT PRIMARY KEY,
            precio REAL,
            fecha_actualizacion TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Función para actualizar los precios en la base de datos
def actualizar_precios_en_db():
    try:
        response = requests.get("https://magicloops.dev/api/loop/d364e7b7-11fc-443c-b44d-70f91dcddc8f/run")
        response.raise_for_status()
        data = response.text.split("\\n")

        precios = []
        for linea in data:
            partes = linea.split(", ")
            nombre = partes[0].split(": ")[1]
            precio = float(partes[1].split(": ")[1].replace(",", "."))
            fecha_actualizacion = partes[2].split(": ")[1]
            precios.append((nombre, precio, fecha_actualizacion))

        conn = sqlite3.connect('precios.db')
        c = conn.cursor()
        c.executemany('''
            INSERT INTO precios (nombre, precio, fecha_actualizacion)
            VALUES (?, ?, ?)
            ON CONFLICT(nombre) DO UPDATE SET
                precio=excluded.precio,
                fecha_actualizacion=excluded.fecha_actualizacion
        ''', precios)
        conn.commit()
        conn.close()
        print("✅ Precios actualizados correctamente.")
    except Exception as e:
        print(f"❌ Error al actualizar precios: {e}")

# Función para obtener precios desde la base de datos
def obtener_precio_desde_db(nombre):
    conn = sqlite3.connect('precios.db')
    c = conn.cursor()
    c.execute('SELECT precio, fecha_actualizacion FROM precios WHERE nombre = ?', (nombre,))
    resultado = c.fetchone()
    conn.close()
    return resultado

# Comando /actualizar para actualizar manualmente los precios
async def actualizar_precios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Actualizando precios, por favor espera...")
    try:
        actualizar_precios_en_db()
        await update.message.reply_text("✅ Precios actualizados correctamente.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al actualizar precios: {e}")

# Comando /precio
async def enviar_precio_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bcv = obtener_precio_desde_db("BCV")
    binance = obtener_precio_desde_db("Binance")

    if bcv and binance:
        mensaje = (
            f"💵 *Dólar BCV*: {bcv[0]:.2f} VES\n"
            f"💵 *Binance*: {binance[0]:.2f} VES\n"
            f"📅 BCV Última actualización: {bcv[1]}\n"
            f"📅 Binance Última actualización: {binance[1]}"
        )
    else:
        mensaje = "❌ No se encontraron los precios en la base de datos."

    await update.message.reply_text(mensaje, parse_mode="Markdown")

# Comando /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 ¡Bienvenido al bot TwoDolar!\n\n"
        "📌 Funciones disponibles:\n"
        "- Escribe 'precio' o 'dólar' para obtener los precios del dólar BCV y Binance.\n"
        "- Calculadora:\n"
        "  - Escribe `<monto>$bcv`,para calcular usando el dólar BCV.\n"
        "  - Escribe `<monto>$binance`, `<monto> $binance`,para calcular usando el dólar Binance.\n"
        "  - Escribe `<monto>ves bcv`, `<monto>ves binance`,para convertir bolívares a dólares.\n"
        "⌛️ El bot enviará automáticamente los precios del dólar a las 9:00 am y 3:00 pm.\n"
        "🤖 Autor del bot: @AngelVillax"
    )
    await update.message.reply_text(mensaje)

# Manejo de cálculos
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.lower()

    bcv = obtener_precio_desde_db("BCV")
    binance = obtener_precio_desde_db("Binance")

    if not bcv or not binance:
        await update.message.reply_text("❌ No se pudieron obtener los precios para realizar el cálculo.")
        return

    bcv_precio = bcv[0]
    binance_precio = binance[0]

    # Calculadora de dólares a bolívares
    match_bcv = re.match(r"^(\d+(\.\d+)?)\s?\$?\s?bcv$", message)
    match_binance = re.match(r"^(\d+(\.\d+)?)\s?\$?\s?binance$", message)

    # Calculadora de bolívares a dólares
    match_ves_bcv = re.match(r"^(\d+(\.\d+)?)\s?ves\s?bcv$", message)
    match_ves_binance = re.match(r"^(\d+(\.\d+)?)\s?ves\s?binance$", message)

    if match_bcv:
        monto = float(match_bcv.group(1))
        resultado = monto * bcv_precio
        respuesta = f"{monto} dólares equivalen a {resultado:.2f} VES (BCV)."
    elif match_binance:
        monto = float(match_binance.group(1))
        resultado = monto * binance_precio
        respuesta = f"{monto} dólares equivalen a {resultado:.2f} VES (Binance)."
    elif match_ves_bcv:
        monto = float(match_ves_bcv.group(1))
        resultado = monto / bcv_precio
        respuesta = f"{monto} VES equivalen a {resultado:.2f} dólares (BCV)."
    elif match_ves_binance:
        monto = float(match_ves_binance.group(1))
        resultado = monto / binance_precio
        respuesta = f"{monto} VES equivalen a {resultado:.2f} dólares (Binance)."
    else:
        respuesta = "⚠️ Formato no reconocido. Usa comandos como '100$ bcv' o '100ves bcv'."

    await update.message.reply_text(respuesta)

# Configuración principal del bot
def main():
    crear_db()  # Crear la base de datos al iniciar el bot

    application = Application.builder().token(TOKEN).build()

    # Tareas automáticas para actualizar los precios
    job_queue = application.job_queue
    job_queue.run_daily(actualizar_precios_en_db, time=time(9, 0, tzinfo=pytz.timezone('America/Caracas')))
    job_queue.run_daily(actualizar_precios_en_db, time=time(15, 0, tzinfo=pytz.timezone('America/Caracas')))

    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("actualizar", actualizar_precios_command))
    application.add_handler(CommandHandler("precio", enviar_precio_mensaje))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Iniciar el bot
    application.run_polling()

if __name__ == "__main__":
    main()
