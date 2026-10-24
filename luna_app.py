# luna_app.py — Luna como página web con chat (Streamlit)
#
# Qué es: la misma Luna de Colab, pero con pantalla de chat con burbujas,
# como WhatsApp o como esta app. Se publica gratis en Streamlit Cloud.
#
# Memoria permanente: lo que aprende Luna ya no vive en un archivo del
# servidor (que se borra cuando la app se duerme), sino en una base de
# datos gratis de Supabase. Así recuerda para siempre, aunque la app se
# reinicie. La conexión se guarda en los Secrets de Streamlit, nunca en
# el código: SUPABASE_URL y SUPABASE_ANON_KEY.
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

import requests
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
ARCHIVO_MEMORIA = "memoria.txt"  # nombre del archivo al descargar la memoria
MODELO = "gemini-3.6-flash"  # modelo actual gratis de Google


# ---- Memoria permanente (base de datos Supabase) ----
def _supabase():
    """Devuelve (url, llave) desde los Secrets de Streamlit, o None si faltan."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
    except Exception:
        return None
    if not url or not key:
        return None
    return url.rstrip("/"), key


def leer_memoria():
    """Lee lo que Luna recuerda de ti desde la base de datos."""
    sb = _supabase()
    if not sb:
        return "Todavía no sé nada de ti."
    url, key = sb
    try:
        r = requests.get(
            f"{url}/rest/v1/memoria?select=texto&order=id.asc",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        if r.status_code != 200:
            return "Todavía no sé nada de ti."
        filas = r.json()
        if not filas:
            return "Todavía no sé nada de ti."
        return "\n".join("- " + f["texto"] for f in filas)
    except Exception:
        return "Todavía no sé nada de ti."


def guardar_memoria(texto):
    """Guarda un dato nuevo en la base de datos. Devuelve True si quedó guardado."""
    sb = _supabase()
    if not sb:
        return False
    url, key = sb
    try:
        r = requests.post(
            f"{url}/rest/v1/memoria",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={"texto": texto},
            timeout=20,
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


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
    if not _supabase():
        st.warning(
            "Falta conectar la base de datos: agrega SUPABASE_URL y "
            "SUPABASE_ANON_KEY en los Secrets de la app en Streamlit Cloud."
        )
    st.subheader("Lo que Luna recuerda")
    memoria_texto = leer_memoria()
    st.write(memoria_texto)
    if memoria_texto != "Todavía no sé nada de ti.":
        st.download_button(
            "Descargar memoria.txt",
            memoria_texto,
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
            if guardar_memoria(dato):
                respuesta = "Listo, ya lo guardé en mi memoria."
            else:
                respuesta = (
                    "No pude guardarlo en mi memoria permanente. "
                    "Revisa la conexión e inténtalo de nuevo."
                )
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
