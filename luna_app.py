# luna_app.py — Luna como página web con chat (Streamlit)
#
# Qué es: la misma Luna de Colab, pero con pantalla de chat con burbujas,
# como WhatsApp o como esta app. Se publica gratis en Streamlit Cloud.
#
# Perfiles con contraseña: Arley y Betsy, cada uno con su memoria privada
# más una memoria familiar compartida. Al abrir la app se elige el perfil
# y se escribe su contraseña. Las contraseñas se guardan en los Secrets
# de Streamlit (CLAVE_ARLEY y CLAVE_BETSY), nunca en el código.
#
# Memoria permanente: vive en una base de datos gratis de Supabase, tabla
# "memoria" con columna "perfil": 'arley', 'betsy' o 'familia'. La conexión
# se guarda en los Secrets de Streamlit, nunca en el código: SUPABASE_URL
# y SUPABASE_ANON_KEY.
#
# Llave de Google: fija en los Secrets (GOOGLE_API_KEY) para que nadie
# tenga que pegarla al abrir la app. Si no está, se puede pegar en la
# barra lateral por sesión. Se crea gratis en https://aistudio.google.com
# (botón "Get API Key"). Nunca la escribas dentro del código.
#
# Conversación guardada: el historial de chat de cada perfil se guarda en
# Supabase, tabla "conversacion" (perfil, rol, texto). Así, si cierras la
# app o te llaman en medio de un chat, al volver la conversación sigue
# donde quedó. Cada perfil ve solo su propio historial.
#
# Búsqueda en internet: Luna usa la herramienta de búsqueda de Google
# del mismo modelo (sin llave ni servicio nuevo). Cuando le preguntan
# algo actual (clima, noticias, resultados), busca y responde con las
# fuentes. Si la búsqueda falla, responde sin buscar para no quedarse
# callada.
#
# Cómo publicarla (desde el teléfono):
#   1. Crea una cuenta en github.com (si no tienes).
#   2. Crea un repositorio nuevo (por ejemplo "luna") y sube estos 2 archivos:
#      luna_app.py y requirements.txt
#   3. Entra a share.streamlit.io, toca "New app", elige tu repositorio
#      y el archivo luna_app.py, y toca "Deploy".
#   4. Abre el enlace que te da Streamlit, elige tu perfil, escribe tu
#      contraseña y chatea con Luna.

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
    "antes de hacer algo delicado. "
    "Cuando te pregunten algo que cambia con el tiempo (el clima de hoy, "
    "noticias, resultados de deportes, precios), busca en internet antes "
    "de responder y menciona de dónde sacaste la información. "
    "Si no encuentras nada, dilo claro, nunca inventes."
)
ARCHIVO_MEMORIA = "memoria.txt"  # nombre del archivo al descargar la memoria
MODELO = "gemini-3.6-flash"  # modelo actual gratis de Google
MODELO_RESPALDO = "gemini-3.8-flash"  # se usa solo si el principal está saturado

# Perfiles: nombre que se muestra y nombre del secreto con su contraseña.
PERFILES = {
    "arley": {"nombre": "Arley", "secreto": "CLAVE_ARLEY"},
    "betsy": {"nombre": "Betsy", "secreto": "CLAVE_BETSY"},
}


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


def _llave_fija():
    """Devuelve la llave de Google guardada en los Secrets, o '' si no está."""
    try:
        llave = st.secrets["GOOGLE_API_KEY"]
    except Exception:
        return ""
    return llave or ""


def _clave_perfil(perfil):
    """Devuelve la contraseña de un perfil desde los Secrets, o '' si falta."""
    try:
        clave = st.secrets[PERFILES[perfil]["secreto"]]
    except Exception:
        return ""
    return clave or ""


def leer_memoria(perfil):
    """Lee la memoria privada de un perfil y la familiar. Devuelve (privada, familiar)."""
    sb = _supabase()
    if not sb:
        return [], []
    url, key = sb
    try:
        r = requests.get(
            f"{url}/rest/v1/memoria?select=texto,perfil&perfil=in.({perfil},familia)&order=id.asc",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        if r.status_code != 200:
            return [], []
        privada, familiar = [], []
        for f in r.json():
            if f["perfil"] == "familia":
                familiar.append(f["texto"])
            else:
                privada.append(f["texto"])
        return privada, familiar
    except Exception:
        return []


def guardar_memoria(texto, perfil):
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
            json={"texto": texto, "perfil": perfil},
            timeout=20,
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


def leer_conversacion(perfil, limite=50):
    """Lee los últimos mensajes del historial de un perfil. Devuelve lista de dicts."""
    sb = _supabase()
    if not sb:
        return []
    url, key = sb
    try:
        r = requests.get(
            f"{url}/rest/v1/conversacion?select=rol,texto&perfil=eq.{perfil}&order=id.desc&limit={limite}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        if r.status_code != 200:
            return []
        return list(reversed(r.json()))
    except Exception:
        return []


def guardar_mensaje(perfil, rol, texto):
    """Guarda un mensaje del chat en la base de datos. Devuelve True si quedó guardado."""
    sb = _supabase()
    if not sb:
        return False
    url, key = sb
    try:
        r = requests.post(
            f"{url}/rest/v1/conversacion",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={"perfil": perfil, "rol": rol, "texto": texto},
            timeout=20,
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


def borrar_conversacion(perfil):
    """Borra todo el historial de chat de un perfil. Devuelve True si se borró."""
    sb = _supabase()
    if not sb:
        return False
    url, key = sb
    try:
        r = requests.delete(
            f"{url}/rest/v1/conversacion?perfil=eq.{perfil}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        return r.status_code in (200, 204)
    except Exception:
        return False


def formatear_memoria(privada, familiar):
    """Texto con las dos partes de la memoria, para mostrar o para Luna."""
    partes = []
    if privada:
        partes.append("Lo tuyo:\n" + "\n".join("- " + t for t in privada))
    if familiar:
        partes.append("Lo familiar:\n" + "\n".join("- " + t for t in familiar))
    return "\n\n".join(partes) if partes else "Todavía no sé nada de ti."


# ---- Página ----
st.set_page_config(page_title="Luna", page_icon="🌙")
st.title("🌙 Luna")

# ---- Entrada con contraseña ----
if "perfil" not in st.session_state:
    st.session_state.perfil = None
if "confirmar_borrar" not in st.session_state:
    st.session_state.confirmar_borrar = False

if not st.session_state.perfil:
    st.write("¿Quién eres?")
    perfil_elegido = st.radio(
        "Elige tu perfil",
        ["Arley", "Betsy"],
        horizontal=True,
    )
    clave_escrita = st.text_input("Tu contraseña", type="password")
    if st.button("Entrar"):
        codigo = "arley" if perfil_elegido == "Arley" else "betsy"
        clave_real = _clave_perfil(codigo)
        if not clave_real:
            st.error("Ese perfil todavía no tiene contraseña configurada en los Secrets.")
        elif clave_escrita == clave_real:
            st.session_state.perfil = codigo
            st.rerun()
        else:
            st.error("Contraseña incorrecta. Inténtalo de nuevo.")
    st.stop()

perfil = st.session_state.perfil
nombre_perfil = PERFILES[perfil]["nombre"]

# ---- Barra lateral: llave, memoria y sesión ----
with st.sidebar:
    st.header("Ajustes")
    st.write(f"Perfil: {nombre_perfil}")
    st.write("🌐 Puedo buscar en internet: pregúntame algo actual y lo busco.")
    if st.button("Cerrar sesión"):
        st.session_state.perfil = None
        st.session_state.pop("mensajes", None)
        st.rerun()
    llave_fija = _llave_fija()
    if llave_fija:
        st.success("Llave de Google guardada en la app ✓")
        llave = llave_fija
    else:
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
    privada, familiar = leer_memoria(perfil)
    st.subheader("Lo que Luna recuerda de ti")
    st.write(
        "\n".join("- " + t for t in privada)
        if privada
        else "Todavía no sé nada de ti."
    )
    st.subheader("Lo familiar")
    st.write(
        "\n".join("- " + t for t in familiar)
        if familiar
        else "Todavía no hay recuerdos familiares."
    )
    guardar_familiar = st.checkbox(
        "Guardar lo próximo como familiar (visible para ambos)",
        help="Si está activado, lo próximo que guardes con 'recuerda que' lo verá el otro perfil también. Desactívalo para volver a guardar solo para ti.",
    )
    texto_descarga = formatear_memoria(privada, familiar)
    if texto_descarga != "Todavía no sé nada de ti.":
        st.download_button(
            "Descargar memoria.txt",
            texto_descarga,
            file_name="memoria.txt",
            help="Guarda la memoria en tu teléfono para no perderla.",
        )
    st.subheader("Conversación")
    if not st.session_state.confirmar_borrar:
        if st.button("Borrar mi conversación"):
            st.session_state.confirmar_borrar = True
            st.rerun()
    else:
        st.warning("¿Borrar todo tu historial de chat? Esto no se puede deshacer.")
        if st.button("Sí, borrar todo"):
            borrar_conversacion(perfil)
            st.session_state.pop("mensajes", None)
            st.session_state.confirmar_borrar = False
            st.rerun()
        if st.button("Cancelar"):
            st.session_state.confirmar_borrar = False
            st.rerun()

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
def _generar_respuesta(modelo, con_busqueda=True):
    """Pide una respuesta a Luna con un modelo dado.

    Con con_busqueda=True, Luna puede buscar en internet con la
    herramienta de Google del propio modelo (sin llave ni servicio
    nuevo) y agrega las fuentes al final de su respuesta.
    """
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
    privada_actual, familiar_actual = leer_memoria(perfil)
    config = types.GenerateContentConfig(
        system_instruction=PERSONALIDAD
        + "\n\nEsto es lo que recuerdas de tu usuario:\n"
        + formatear_memoria(privada_actual, familiar_actual),
    )
    if con_busqueda:
        config.tools = [types.Tool(google_search=types.GoogleSearch())]
    resp = cliente.models.generate_content(
        model=modelo,
        contents=historial,
        config=config,
    )
    texto = resp.text
    # Fuentes de la búsqueda, si el modelo usó internet.
    try:
        chunks = resp.candidates[0].grounding_metadata.grounding_chunks
        fuentes = []
        for c in chunks or []:
            web = getattr(c, "web", None)
            if web and web.uri and web.uri not in [u for _, u in fuentes]:
                fuentes.append((web.title or web.uri, web.uri))
        if fuentes:
            texto += "\n\nFuentes:\n" + "\n".join(
                f"- [{t}]({u})" for t, u in fuentes
            )
    except Exception:
        pass
    return texto


def responder_con_luna():
    """Pregunta a Luna, con búsqueda en internet.

    Orden de intentos: modelo principal con búsqueda; si está saturado,
    modelo de respaldo con búsqueda; si la búsqueda falla, modelo
    principal sin búsqueda. Si todo falla, el error sube y el chat
    muestra el mensaje claro que corresponde.
    """
    try:
        return _generar_respuesta(MODELO, con_busqueda=True)
    except Exception as e:
        texto_error = str(e)
        if "503" in texto_error or "UNAVAILABLE" in texto_error:
            try:
                return _generar_respuesta(MODELO_RESPALDO, con_busqueda=True)
            except Exception:
                return _generar_respuesta(MODELO, con_busqueda=False)
        return _generar_respuesta(MODELO, con_busqueda=False)


if "mensajes" not in st.session_state:
    historial = leer_conversacion(perfil)
    if historial:
        st.session_state.mensajes = [
            {"rol": m["rol"], "texto": m["texto"]} for m in historial
        ]
    else:
        st.session_state.mensajes = [
            {
                "rol": "assistant",
                "texto": (
                    f"¡Hola, soy {NOMBRE}! Escribe abajo para chatear conmigo.\n\n"
                    "Si me preguntas algo actual (el clima de hoy, una noticia, un resultado), "
                    "lo busco en internet y te respondo con sus fuentes.\n\n"
                    "Si me dices algo que empiece con **'recuerda que'**, lo guardo en mi memoria. "
                    "Si activas 'Guardar como familiar' en la barra lateral, lo guardado lo veremos los dos. "
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
    guardar_mensaje(perfil, "user", texto)
    with st.chat_message("user"):
        st.markdown(texto)

    if texto.lower().startswith("recuerda que"):
        dato = texto[len("recuerda que"):].strip()
        if dato:
            destino = "familia" if guardar_familiar else perfil
            if guardar_memoria(dato, destino):
                respuesta = "Listo, ya lo guardé en mi memoria."
            else:
                respuesta = (
                    "No pude guardarlo en mi memoria permanente. "
                    "Revisa la conexión e inténtalo de nuevo."
                )
        else:
            respuesta = "Dime qué quieres que recuerde, por ejemplo: recuerda que mi esposa es Betsy"
    elif texto.lower() == "memoria":
        privada_actual, familiar_actual = leer_memoria(perfil)
        respuesta = "Esto es lo que recuerdo de ti:\n\n" + formatear_memoria(privada_actual, familiar_actual)
    else:
        try:
            respuesta = responder_con_luna()
        except Exception as e:
            texto_error = str(e)
            if "503" in texto_error or "UNAVAILABLE" in texto_error:
                respuesta = (
                    "El modelo de Google está saturado en este momento. "
                    "Espera un ratito y vuelve a escribir tu mensaje."
                )
            elif "401" in texto_error or "API key" in texto_error or "API_KEY" in texto_error:
                respuesta = (
                    "Parece que hay un problema con la llave de Google. "
                    "Revisa que siga guardada en la app."
                )
            else:
                respuesta = (
                    "Hubo un problema al responder. "
                    "Inténtalo de nuevo en un momento."
                )

    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta})
    guardar_mensaje(perfil, "assistant", respuesta)
    with st.chat_message("assistant"):
        st.markdown(respuesta)
