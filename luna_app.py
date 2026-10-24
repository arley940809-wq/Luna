# luna_app.py — Luna como página web con chat (Streamlit)
#
# Qué es: la misma Luna de Colab, pero con pantalla de chat con burbujas,
# como WhatsApp o como esta app. Se publica gratis en Streamlit Cloud.
#
# Cómo publicarla (desde el teléfono):
#   1. Crea una cuenta en github.com (si no tienes).
#   2. Crea un repositorio nuevo (por ejemplo "luna") y sube estos 2 archivos:
#      luna_app.py y requirements.txt
#   3. Entra a share.streamlit.io, toca "New app", elige tu repositorio
#      y el archivo luna_app.py, y toca "Deploy".
#   4. Abre el enlace que te da Streamlit, pega tu llave en la barra lateral
#      y chatea con Luna. Ese enlace lo puede abrir también Betsy.
#
# La llave se crea gratis en https://aistudio.google.com (botón "Get API Key").
# Nunca la escribas dentro del código: se pega en la barra lateral al abrir la app.

import os

import streamlit as st
from google import genai
from google.genai import types

# ---- Configura aquí a tu asistente ----
NOMBRE = "Luna"  # <-- cambia el nombre por el que quieras (tú y Betsy eligen)
PERSONALIDAD = (
    "Eres una asistente amable, paciente y divertida. "
    "Hablas en español sencillo. Ayudas a practicar inglés, "
    "recuerdas lo importante de tu usuario y siempre preguntas "
    "antes de hacer algo delicado."
)
ARCHIVO_MEMORIA = "memoria.txt"
MODELO = "gemini-3.6-flash"  # modelo actual gratis de Google


# ---- Memoria: el cuaderno de la asistente ----
def leer_memoria():
    """Lee lo que la asistente recuerda de ti (o avisa si aún no sabe nada)."""
    if os.path.exists(ARCHIVO_MEMORIA):
        with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
            return f.read()
    return "Todavía no sé nada de ti."


def guardar_memoria(texto):
    """Guarda un dato nuevo en el cuaderno de memoria."""
    with open(ARCHIVO_MEMORIA, "a", encoding="utf-8") as f:
        f.write("- " + texto + "\n")


# ---- Página ----
st.set_page_config(page_title="Luna", page_icon="🌙")
st.title("🌙 Luna")

# ---- Barra lateral: llave y memoria ----
with st.sidebar:
    st.header("Ajustes")
    llave = st.text_input(
        "Tu llave de Google (gratis, de AI Studio)",
        type="password",
        help="Se crea en aistudio.google.com. Solo vive en tu sesión, no se guarda en el código.",
    )
    st.subheader("Lo que Luna recuerda")
    st.write(leer_memoria())
    if os.path.exists(ARCHIVO_MEMORIA):
        with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
            contenido = f.read()
        st.download_button(
            "Descargar memoria.txt",
            contenido,
            file_name="memoria.txt",
            help="Guarda la memoria en tu teléfono para no perderla.",
        )

if not llave:
    st.info(
        "Pega tu llave de Google en la barra lateral para empezar. "
        "Se crea gratis en aistudio.google.com (botón 'Get API Key')."
    )
    st.stop()

# ---- Conexión con Luna ----
# Nota: se abre una conexión nueva en cada mensaje. Antes la conexión se
# guardaba abierta entre mensajes y Streamlit la cerraba, lo que daba el
# error "client has been closed" y Luna dejaba de responder.
def responder_con_luna():
    """Pregunta a Luna usando todo el historial de esta conversación."""
    cliente = genai.Client(api_key=llave)
    historial = []
    for m in st.session_state.mensajes:
        rol = "user" if m["rol"] == "user" else "model"
        historial.append(
            types.Content(
                role=rol,
                parts=[types.Part.from_text(text=m["texto"])],
            )
        )
    resp = cliente.models.generate_content(
        model=MODELO,
        contents=historial,
        config=types.GenerateContentConfig(
            system_instruction=PERSONALIDAD
            + "\n\nEsto es lo que recuerdas de tu usuario:\n"
            + leer_memoria(),
        ),
    )
    return resp.text


if "mensajes" not in st.session_state:
    st.session_state.mensajes = [
        {
            "rol": "assistant",
            "texto": (
                f"¡Hola, soy {NOMBRE}! Escribe abajo para chatear conmigo.\n\n"
                "Si me dices algo que empiece con **'recuerda que'**, lo guardo en mi memoria. "
                "Escribe **'memoria'** para ver lo que recuerdo de ti."
            ),
        }
    ]

# ---- Conversación ----
for m in st.session_state.mensajes:
    with st.chat_message(m["rol"]):
        st.markdown(m["texto"])

if texto := st.chat_input("Escribe tu mensaje..."):
    st.session_state.mensajes.append({"rol": "user", "texto": texto})
    with st.chat_message("user"):
        st.markdown(texto)

    if texto.lower().startswith("recuerda que"):
        dato = texto[len("recuerda que"):].strip()
        if dato:
            guardar_memoria(dato)
            respuesta = "Listo, ya lo guardé en mi memoria."
        else:
            respuesta = "Dime qué quieres que recuerde, por ejemplo: recuerda que mi esposa es Betsy"
    elif texto.lower() == "memoria":
        respuesta = "Esto es lo que recuerdo de ti:\n\n" + leer_memoria()
    else:
        try:
            respuesta = responder_con_luna()
        except Exception as e:
            respuesta = f"Hubo un problema al responder: {e}\n\nRevisa tu llave y tu conexión."

    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta})
    with st.chat_message("assistant"):
        st.markdown(respuesta)
