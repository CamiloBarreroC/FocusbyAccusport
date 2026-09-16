import io
import json
import re
from datetime import datetime, timedelta

from fpdf import FPDF
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread
import pandas as pd
from PIL import Image
import streamlit as st

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# =====================================================================
# 📝 CONFIGURACIÓN INICIAL Y CENTRAL DE BRANDING
# =====================================================================
CONFIG_SHEET_ID = "1wJi3hOQaeIDY--OcFOxsy-ycb-uyATDpqIGvMYvHPg4"
FOCUS_CALENDAR_DEFAULT = "c_3df55a2bb225d2a2d2054496334a5d7c7f9afca3f9099aea782b278fd9f45472@group.calendar.google.com"
PATH_LOGO_FOCUS = "IMG-20260521-WA0004.jpg"

st.set_page_config(
    page_title="Focus by Accusport", page_icon="⚽", layout="centered"
)

# 🎨 INYECCIÓN DE ESTILOS CSS BLACK & ORANGE CYBER-TECH
st.markdown(
    """
    <style>
    .stApp {
        background-color: #000000 !important;
        color: #f8fafc !important;
    }
    div[data-testid="stContainer"] {
        background-color: #0d0d0d !important;
        border: 1px solid #ff5500 !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 20px rgba(255, 85, 0, 0.15) !important;
        padding: 25px !important;
        margin-bottom: 20px !important;
    }
    button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #ff5500 0%, #cc4400 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        box-shadow: 0 0 10px rgba(255, 85, 0, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    button:hover {
        background: linear-gradient(135deg, #ff7722 0%, #ff5500 100%) !important;
        box-shadow: 0 0 20px rgba(255, 85, 0, 0.6) !important;
        transform: translateY(-2px) !important;
    }
    button[data-baseweb="tab"] {
        color: #888888 !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    button[aria-selected="true"] {
        color: #ff5500 !important;
        border-bottom-color: #ff5500 !important;
    }
    div[data-baseweb="select"], input, textarea {
        background-color: #0d0d0d !important;
        color: white !important;
        border: 1px solid #333333 !important;
    }
    .stAlert {
        background-color: #0d0d0d !important;
        color: #cbd5e1 !important;
        border-left: 5px solid #ff5500 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

for key, default in [
    ("admin_autenticado", False),
    ("nombre_admin", ""),
    ("ver_galeria", False),
    ("equipo_activo", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# =====================================================================
# 🔗 CONEXIONES Y SERVICIOS (GOOGLE SHEETS Y CALENDAR)
# =====================================================================
@st.cache_resource
def conectar_google_services():
    try:
        secrets_gcp = st.secrets["gcp_service_account"]
        creds_dict = (
            json.loads(secrets_gcp)
            if isinstance(secrets_gcp, str)
            else dict(secrets_gcp)
        )
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/calendar",
        ]
        return Credentials.from_service_account_info(creds_dict, scopes=scopes)
    except Exception as e:
        st.error(f"⚠️ Error crítico de conexión con Google Cloud: {e}")
        return None


def obtener_cliente_sheets():
    creds = conectar_google_services()
    return gspread.authorize(creds) if creds else None


def obtener_servicio_calendar():
    creds = conectar_google_services()
    return build("calendar", "v3", credentials=creds) if creds else None


def obtener_datos_pestana(nombre_pestana):
    client = obtener_cliente_sheets()
    if client:
        try:
            sheet = client.open_by_key(CONFIG_SHEET_ID)
            worksheet = sheet.worksheet(nombre_pestana)
            datos = worksheet.get_all_records()
            df = pd.DataFrame(datos)
            if not df.empty:
                df.columns = df.columns.astype(str).str.strip()
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def agregar_fila_excel(nombre_pestana, lista_datos):
    client = obtener_cliente_sheets()
    if client:
        try:
            sheet = client.open_by_key(CONFIG_SHEET_ID)
            worksheet = sheet.worksheet(nombre_pestana)
            worksheet.append_row(lista_datos)
            return True
        except Exception as e:
            st.error(f"❌ Error al escribir en Excel: {e}")
            return False
    return False


def crear_evento_google_calendar(calendar_id, titulo, fecha_dt, equipo):
    service = obtener_servicio_calendar()
    if service:
        try:
            start_time = datetime.combine(
                fecha_dt, datetime.min.time()
            ) + timedelta(hours=8)
            end_time = start_time + timedelta(hours=2)
            event = {
                "summary": f"🎥 FOCUS: {equipo} vs {titulo}",
                "description": f"Grabación programada desde el panel Focus para la categoría {equipo}.",
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "America/Bogota",
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "America/Bogota",
                },
            }
            cal_destino = (
                FOCUS_CALENDAR_DEFAULT
                if calendar_id.lower() == "primary"
                else calendar_id
            )
            service.events().insert(
                calendarId=cal_destino, body=event
            ).execute()
            return True
        except Exception:
            return False
    return False


# =====================================================================
# 📑 PROCESAMIENTO MULTI-ARCHIVO (PDF Y CSV) Y GENERADOR DE REPORTE
# =====================================================================
def sanitizar_texto(texto):
    """Limpia caracteres fuera del mapa Latin-1 para evitar colapsos en FPDF."""
    if not isinstance(texto, str):
        return str(texto)
    reemplazos = {
        "•": "-", "✔": "[OK]", "✖": "[X]", "🎯": ">", "⚽": "", "🎥": "",
        "⚡": "", "🚀": "", "📥": "", "📊": "", "🛡️": "", "👤": "", "📆": "",
        "💰": "", "👁️": "", "🔑": "", "⚙️": "", "🚨": "", "🛠️": "", "👋": "",
        "✅": "", "⏳": "", "✨": "", "💥": "", "🏆": "", "💵": "", "💳": ""
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    return texto.encode("latin-1", "ignore").decode("latin-1")


def obtener_bytes_shot_chart(file_obj):
    """Convierte el archivo del Shot Chart (sea PDF o PNG/JPG) a bytes de imagen."""
    if file_obj is None:
        return None

    nombre = file_obj.name.lower()
    if nombre.endswith(".pdf"):
        if pdfplumber is None:
            st.error("Instala pdfplumber en requirements.txt para procesar el PDF del Shot Chart.")
            return None
        try:
            with pdfplumber.open(io.BytesIO(file_obj.getvalue())) as pdf:
                page = pdf.pages[0]
                im = page.to_image(resolution=200).original
                img_byte_arr = io.BytesIO()
                im.save(img_byte_arr, format="PNG")
                img_byte_arr.seek(0)
                return img_byte_arr
        except Exception as e:
            st.error(f"Error procesando la imagen del PDF: {e}")
            return None
    else:
        return file_obj


def procesar_archivos_tagueo(lista_archivos):
    """Procesa uno o múltiples archivos CSV/PDF del software de tagueo."""
    if not lista_archivos:
        return {}

    if not isinstance(lista_archivos, list):
        lista_archivos = [lista_archivos]

    datos = {}
    texto_consolidado = ""

    for file_obj in lista_archivos:
        nombre = file_obj.name.lower()
        file_bytes = file_obj.getvalue()

        if nombre.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(file_bytes))
                for _, row in df.iterrows():
                    clave = str(row.iloc[0]).strip().lower()
                    val_local = row.iloc[1] if len(row) > 1 else 0
                    val_visita = row.iloc[2] if len(row) > 2 else 0

                    if "possession" in clave:
                        datos["pos_local"] = str(val_local)
                        datos["pos_visita"] = str(val_visita)
                    elif "shots" in clave and "target" not in clave:
                        datos["remates_local"] = val_local
                        datos["remates_visita"] = val_visita
                    elif "goals" in clave:
                        datos["goles_local"] = val_local
                        datos["goles_visita"] = val_visita
                    elif "passes" in clave and "successful" not in clave:
                        datos["pases_local"] = val_local
                        datos["pases_visita"] = val_visita
                    elif "successful passes" in clave:
                        datos["pases_exitosos_local"] = val_local
                        datos["pases_exitosos_visita"] = val_visita
            except Exception as e:
                st.error(f"Error en CSV {nombre}: {e}")

        elif nombre.endswith(".pdf") and pdfplumber:
            try:
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    for p in pdf.pages:
                        txt = p.extract_text()
                        if txt:
                            texto_consolidado += "\n" + txt
            except Exception as e:
                st.error(f"Error al leer PDF {nombre}: {e}")

    if texto_consolidado:
        pos_m = re.search(
            r"Possession\s*%?\s*\|\s*([\d.]+%\??)\s*\|\s*([\d.]+%\??)",
            texto_consolidado,
            re.IGNORECASE,
        )
        if pos_m:
            datos["pos_local"] = pos_m.group(1)
            datos["pos_visita"] = pos_m.group(2)

        goles_m = re.search(
            r"Goals\s*\|\s*(\d+)\s*\|\s*(\d+)", texto_consolidado, re.IGNORECASE
        )
        if goles_m:
            datos["goles_local"] = int(goles_m.group(1))
            datos["goles_visita"] = int(goles_m.group(2))

        shots_m = re.search(
            r"Shots\s*\|\s*(\d+)\s*\|\s*(\d+)", texto_consolidado, re.IGNORECASE
        )
        if shots_m:
            datos["remates_local"] = int(shots_m.group(1))
            datos["remates_visita"] = int(shots_m.group(2))

        pases_m = re.search(
            r"Passes\s*\|\s*(\d+)\s*\|\s*(\d+)", texto_consolidado, re.IGNORECASE
        )
        if pases_m:
            datos["pases_local"] = int(pases_m.group(1))
            datos["pases_visita"] = int(pases_m.group(2))

        sp_m = re.search(
            r"Successful Passes\s*\|\s*(\d+)\s*\|\s*(\d+)",
            texto_consolidado,
            re.IGNORECASE,
        )
        if sp_m:
            datos["pases_exitosos_local"] = int(sp_m.group(1))
            datos["pases_exitosos_visita"] = int(sp_m.group(2))

    return datos


class PDFReporteFocus(FPDF):

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(128, 128, 128)
            self.cell(
                0,
                10,
                f"FOCUS by AccuSport | Reporte de análisis                      Página {self.page_no()}",
                align="C",
            )


def generar_pdf_6_paginas(data):
    pdf = PDFReporteFocus()
    pdf.set_auto_page_break(auto=True, margin=15)

    ORANGE = (255, 85, 0)
    DARK = (13, 13, 13)
    WHITE = (255, 255, 255)
    GRAY_BG = (245, 245, 247)
    TEXT_DARK = (30, 30, 30)

    eq_loc = sanitizar_texto(data["equipo_local"])
    eq_vis = sanitizar_texto(data["equipo_visita"])
    fec_str = sanitizar_texto(data["fecha"])

    # PÁGINA 1: PORTADA
    pdf.add_page()
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 210, 297, "F")

    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*WHITE)
    pdf.set_y(80)
    pdf.cell(0, 15, "FOCUS", ln=True, align="C")

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 8, "by AccuSport", ln=True, align="C")

    pdf.ln(25)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 10, "REPORTE DE ANÁLISIS DE PARTIDO", ln=True, align="C")

    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(
        0,
        12,
        f"{eq_loc.upper()} {data['goles_local']} - {data['goles_visita']} {eq_vis.upper()}",
        ln=True,
        align="C",
    )

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(0, 8, f"{fec_str}", ln=True, align="C")

    pdf.set_y(240)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(
        0,
        5,
        "Análisis basado en reportes de tagueo oficial",
        ln=True,
        align="C",
    )
    pdf.cell(0, 5, "Documento preparado por FOCUS by AccuSport", ln=True, align="C")

    # PÁGINA 2: ANÁLISIS GENERAL
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Análisis general del partido", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(
        0,
        6,
        f"{eq_loc} vs {eq_vis} - {fec_str}",
        ln=True,
    )
    pdf.ln(5)

    pdf.set_fill_color(*GRAY_BG)
    pdf.rect(10, pdf.get_y(), 190, 25, "F")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*DARK)
    pdf.cell(
        0,
        15,
        f"{eq_loc}  {data['goles_local']} - {data['goles_visita']}  {eq_vis}",
        ln=True,
        align="C",
    )
    pdf.ln(15)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Lectura general:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 5, sanitizar_texto(data.get("lectura_general", "Sin datos registrados."))
    )
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Tres conclusiones rápidas:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for conc in data.get("conclusiones", []):
        pdf.cell(0, 6, f"- {sanitizar_texto(conc)}", ln=True)

    # PÁGINA 3: COMPARATIVO GENERAL
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Comparativo general", ln=True)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, "Volumen, posesión y acciones de partido", ln=True)
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    pdf.cell(90, 8, " Variable", 1, 0, "L", fill=True)
    pdf.cell(50, 8, f" {eq_loc}", 1, 0, "C", fill=True)
    pdf.cell(50, 8, f" {eq_vis}", 1, 1, "C", fill=True)

    stats_tabla = [
        ("Posesión (%)", data.get("pos_local", "45%"), data.get("pos_visita", "55%")),
        ("Remates", data.get("remates_local", "20"), data.get("remates_visita", "34")),
        ("Goles", data.get("goles_local", "5"), data.get("goles_visita", "2")),
        ("Pases", data.get("pases_local", "91"), data.get("pases_visita", "111")),
        ("Pases Exitosos", data.get("pases_exitosos_local", "55"), data.get("pases_exitosos_visita", "73")),
    ]

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    for var, v1, v2 in stats_tabla:
        pdf.cell(90, 7, f" {sanitizar_texto(var)}", 1, 0, "L")
        pdf.cell(50, 7, f" {sanitizar_texto(v1)}", 1, 0, "C")
        pdf.cell(50, 7, f" {sanitizar_texto(v2)}", 1, 1, "C")

    # PÁGINA 4: ATAQUE Y DEFINICIÓN (SHOT CHART)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Ataque y definición", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, "Producción ofensiva y distribución temporal", ln=True)
    pdf.ln(5)

    if data.get("img_shot_chart"):
        try:
            pdf.image(data["img_shot_chart"], x=20, y=50, w=170)
            pdf.set_y(180)
        except Exception as e:
            pdf.cell(0, 10, f"[Error al renderizar imagen: {e}]", ln=True)
    else:
        pdf.cell(0, 10, "[Mapa de remates no adjuntado]", ln=True)

    # PÁGINA 5: POSESIÓN Y PASE
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Posesión y pase", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, "Calidad de circulación y desempeño por tercios", ln=True)
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Precisión de pase por tercios:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        6,
        "- Tercio Defensivo: 55% precisión (29 intentos / 16 exitosos)",
        ln=True,
    )
    pdf.cell(
        0,
        6,
        "- Tercio Medio: 80% precisión (30 intentos / 24 exitosos)",
        ln=True,
    )
    pdf.cell(
        0,
        6,
        "- Tercio Ofensivo: 50% precisión (28 intentos / 14 exitosos)",
        ln=True,
    )

    # PÁGINA 6: CONCLUSIONES Y FOCOS DE TRABAJO
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Conclusiones y focos de trabajo", ln=True)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, "Síntesis técnica para seguimiento del equipo", ln=True)
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Aspectos a conservar:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for asp in data.get("aspectos_conservar", []):
        pdf.cell(0, 6, f"[OK] {sanitizar_texto(asp)}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Aspectos a corregir:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for asp in data.get("aspectos_corregir", []):
        pdf.cell(0, 6, f"[X] {sanitizar_texto(asp)}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Focos sugeridos para entrenamiento:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for foc in data.get("focos_entrenamiento", []):
        pdf.cell(0, 6, f"> {sanitizar_texto(foc)}", ln=True)

    return bytes(pdf.output())


# =====================================================================
# 📐 LOGO Y CABECERA
# =====================================================================
_, col_logo_center, _ = st.columns([1, 4, 1])
with col_logo_center:
    try:
        st.image(PATH_LOGO_FOCUS, use_container_width=True)
    except Exception:
        st.markdown(
            "<h1 style='text-align:center; margin:0; font-size:45px; letter-spacing:-1px; color:#ffffff;'>⚡ FO<span style='color:#ff5500;'>CUS</span></h1>",
            unsafe_allow_html=True,
        )

st.write("---")
tab_padres, tab_admin = st.tabs(
    ["📺 Focus Play (Familias)", "🔒 Control Administrativo"]
)

# =====================================================================
# SECCIÓN 1: INTERFAZ DE PADRES (FOCUS PLAY)
# =====================================================================
with tab_padres:
    if st.session_state.get("ver_galeria", False):
        equipo = st.session_state.get("equipo_activo", "")
        if st.button("⬅️ Cambiar de Categoría"):
            st.session_state["ver_galeria"] = False
            st.session_state["equipo_activo"] = ""
            st.rerun()

        st.write(f"### 🎬 Catálogo de Videos y Reportes: **{equipo}**")
        st.write("---")

        df_partidos = obtener_datos_pestana("PARTIDOS")
        if not df_partidos.empty and "Equipo" in df_partidos.columns:
            df_partidos["Equipo"] = (
                df_partidos["Equipo"].astype(str).str.strip()
            )
            partidos_filtrados = df_partidos[
                df_partidos["Equipo"] == equipo
            ].copy()

            if not partidos_filtrados.empty:
                for idx, row in partidos_filtrados.iterrows():
                    rival = row.get("Rival", "Rival Desconocido")
                    fecha_str = row.get("Fecha", "S/F")
                    link_drive = row.get("Link", "")

                    with st.container(border=True):
                        st.markdown(f"## 🆚 {rival}")
                        st.markdown(f"📅 **Fecha:** {fecha_str}")
                        if link_drive and "http" in link_drive:
                            st.link_button(
                                "📥 VER / DESCARGAR REPORTE Y VIDEO",
                                link_drive,
                                use_container_width=True,
                            )
            else:
                st.info(
                    "ℹ️ No hay videos cargados ni filmaciones programadas para este equipo todavía."
                )
    else:
        st.write("### 🔍 Ingresa a Focus Play")
        df_p_init = obtener_datos_pestana("PARTIDOS")
        df_u_init = obtener_datos_pestana("USUARIOS")
        set_equipos = set()
        if not df_p_init.empty and "Equipo" in df_p_init.columns:
            set_equipos.update(
                df_p_init["Equipo"].astype(str).str.strip().unique()
            )
        if not df_u_init.empty and "Equipo" in df_u_init.columns:
            set_equipos.update(
                df_u_init["Equipo"].astype(str).str.strip().unique()
            )

        lista_equipos = sorted([eq for eq in set_equipos if eq and eq != "None"])
        if lista_equipos:
            equipo_seleccionado = st.selectbox(
                "Selecciona tu Equipo / Categoría:",
                ["-- Elige tu categoría --"] + lista_equipos,
            )
            if equipo_seleccionado != "-- Elige tu categoría --":
                if st.button(
                    "🚀 ENTRAR A MI GALERÍA DE STREAMING",
                    use_container_width=True,
                ):
                    st.session_state["equipo_activo"] = equipo_seleccionado
                    st.session_state["ver_galeria"] = True
                    st.rerun()

# =====================================================================
# SECCIÓN 2: CONTROL ADMINISTRATIVO & GENERADOR DE PDF
# =====================================================================
with tab_admin:
    st.write("### 🔑 Centro de Mando Focus")

    if not st.session_state.get("admin_autenticado", False):
        usuario_admin = (
            st.text_input("Usuario Operativo:", key="user_adm").strip().lower()
        )
        clave_admin = st.text_input(
            "Contraseña de Seguridad:", type="password", key="pass_adm"
        )
        if st.button("Autenticar Servidor", key="btn_admin_login"):
            if "admins" in st.secrets:
                dict_admins = st.secrets["admins"]
                if usuario_admin in dict_admins and clave_admin == str(
                    dict_admins[usuario_admin]
                ):
                    st.session_state["admin_autenticado"] = True
                    st.session_state["nombre_admin"] = usuario_admin.capitalize()
                    st.rerun()
                else:
                    st.error("❌ Credenciales inválidas.")
    else:
        st.success(
            f"🔓 Conectado como **{st.session_state.get('nombre_admin', 'Admin')}**"
        )

        opcion_admin = st.selectbox(
            "⚙️ ¿Qué acción deseas realizar hoy?",
            [
                "📄 Generar Reporte de Análisis PDF (Tagueo CSV / PDF)",
                "📈 Tablero de Control Financiero (Balance)",
                "🛡️ 1. Añadir Equipo (GLOBAL)",
                "👤 2. Agregar Jugador / Papá a un Equipo",
                "📆 3. Programar Grabación / Subir Video + CALENDAR",
                "💰 4. Registrar Cobro Mensual (Clubes VIP)",
                "👁️ Auditar Hojas de Excel en Vivo",
            ],
        )
        st.write("---")

        if opcion_admin == "📄 Generar Reporte de Análisis PDF (Tagueo CSV / PDF)":
            st.write("#### 📊 Generador de Reportes de 6 Páginas Focus")

            col_doc, col_img = st.columns(2)
            with col_doc:
                archivos_tagueo = st.file_uploader(
                    "1. Archivos de Tagueo (PDFs o CSV):",
                    type=["csv", "pdf"],
                    accept_multiple_files=True,
                )
            with col_img:
                archivo_img_raw = st.file_uploader(
                    "2. Mapa Shot Chart (PDF, PNG o JPG):",
                    type=["png", "jpg", "jpeg", "pdf"],
                )

            col_e1, col_e2, col_f = st.columns(3)
            with col_e1:
                eq_local = st.text_input("Equipo Local:", value="Fortaleza 2017 B")
            with col_e2:
                eq_visita = st.text_input("Equipo Visitante:", value="Aurinegro")
            with col_f:
                fecha_p = st.text_input("Fecha:", value="12 de septiembre de 2026")

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                g_local = st.number_input("Goles Local:", min_value=0, value=5)
            with col_g2:
                g_visita = st.number_input("Goles Visitante:", min_value=0, value=2)

            lectura_gen = st.text_area(
                "Lectura General del Partido:",
                value="Fortaleza 2017 B ganó 5-2 combinando dos rasgos decisivos: alta eficiencia ofensiva y solidez defensiva.",
            )

            conc_1 = st.text_input(
                "Conclusión 1:",
                value="La diferencia del partido estuvo más asociada a la eficacia que al volumen.",
            )
            conc_2 = st.text_input(
                "Conclusión 2:",
                value="El mejor registro de pase apareció en el tercio medio: 80% de precisión.",
            )
            conc_3 = st.text_input(
                "Conclusión 3:",
                value="La estructura defensiva limitó al rival a solo 2 goles en 34 remates.",
            )

            asp_cons = st.text_area(
                "Aspectos a conservar (separados por coma):",
                value="Definición eficiente, Inicio de partido arrollador, Defensa y marca sólida",
            )
            asp_corr = st.text_area(
                "Aspectos a corregir (separados por coma):",
                value="Control del volumen rival, Salida bajo presión, Conexión en último tercio",
            )
            foc_ent = st.text_area(
                "Focos de entrenamiento (separados por coma):",
                value="Sostener el bloque defensivo, Salida y progresión rápida, Conexión en último tercio",
            )

            if st.button("🚀 GENERAR Y DESCARGAR PDF DE 6 PÁGINAS", use_container_width=True):
                datos_extraidos = (
                    procesar_archivos_tagueo(archivos_tagueo) if archivos_tagueo else {}
                )
                img_shot_chart = obtener_bytes_shot_chart(archivo_img_raw)

                data_pdf = {
                    "equipo_local": eq_local,
                    "equipo_visita": eq_visita,
                    "fecha": fecha_p,
                    "goles_local": g_local,
                    "goles_visita": g_visita,
                    "lectura_general": lectura_gen,
                    "conclusiones": [conc_1, conc_2, conc_3],
                    "aspectos_conservar": [
                        x.strip() for x in asp_cons.split(",") if x.strip()
                    ],
                    "aspectos_corregir": [
                        x.strip() for x in asp_corr.split(",") if x.strip()
                    ],
                    "focos_entrenamiento": [
                        x.strip() for x in foc_ent.split(",") if x.strip()
                    ],
                    "img_shot_chart": img_shot_chart,
                    **datos_extraidos,
                }

                pdf_bytes = generar_pdf_6_paginas(data_pdf)
                st.download_button(
                    label="📥 DESCARGAR REPORTE FINAL EN PDF",
                    data=pdf_bytes,
                    file_name=f"Reporte_{eq_local}_vs_{eq_visita}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

        elif opcion_admin == "🛡️ 1. Añadir Equipo (GLOBAL)":
            nuevo_equipo = st.text_input("Nombre Único del Equipo:")
            if st.button("🚀 CREAR EQUIPO") and nuevo_equipo:
                exito = agregar_fila_excel(
                    "PARTIDOS",
                    [
                        nuevo_equipo,
                        datetime.now().strftime("%d/%m/%Y"),
                        "Bienvenida",
                        "Listo",
                        "https://drive.google.com",
                        0,
                    ],
                )
                if exito:
                    st.success(f"Equipo {nuevo_equipo} creado con éxito.")

        elif opcion_admin == "👤 2. Agregar Jugador / Papá a un Equipo":
            nombre_papa = st.text_input("Nombre Completo del Papá / Acudiente:")
            nombre_hijo = st.text_input("Nombre Completo del Jugador (Hijo):")
            equipo_u = st.text_input("Categoría / Equipo:")
            if st.button("💾 Guardar Cliente", use_container_width=True):
                if nombre_papa and nombre_hijo:
                    exito = agregar_fila_excel(
                        "USUARIOS", [nombre_papa.strip(), nombre_hijo.strip(), equipo_u]
                    )
                    if exito:
                        st.success(f"👤 Jugador {nombre_hijo} guardado con éxito.")

        elif opcion_admin == "📆 3. Programar Grabación / Subir Video + CALENDAR":
            fecha_sel = st.date_input("Fecha del Encuentro:", datetime.now())
            equipo_sel = st.text_input("Categoría / Equipo Destino:", value="Fortaleza 2017 B")
            rival_sel = st.text_input("Nombre del Rival:")
            link_sel = st.text_input("Enlace Google Drive del Video / Reporte PDF:")
            if st.button("💾 Publicar Partido", use_container_width=True):
                if rival_sel:
                    fecha_str = fecha_sel.strftime("%d/%m/%Y")
                    exito = agregar_fila_excel(
                        "PARTIDOS",
                        [equipo_sel, fecha_str, rival_sel, "Listo", link_sel, 0],
                    )
                    if exito:
                        crear_evento_google_calendar(
                            FOCUS_CALENDAR_DEFAULT, rival_sel, fecha_sel, equipo_sel
                        )
                        st.success("✅ Guardado y agendado en Google Calendar.")

        elif opcion_admin == "💰 4. Registrar Cobro Mensual (Clubes VIP)":
            equipo_m = st.text_input("Equipo:")
            mes_m = st.selectbox("Mes Cobrado:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            monto_m = st.number_input("Monto ($ COP):", value=350000)
            if st.button("💾 Guardar Cobro", use_container_width=True):
                exito = agregar_fila_excel("PAGOS_MENSUALES", [equipo_m, mes_m, monto_m, "Pagado"])
                if exito:
                    st.success("💳 Registrado en tesorería.")

        elif opcion_admin == "👁️ Auditar Hojas de Excel en Vivo":
            tabla_sel = st.radio(
                "Selecciona tabla:", ["USUARIOS", "PARTIDOS", "PAGOS_MENSUALES"]
            )
            df_audit = obtener_datos_pestana(tabla_sel)
            st.dataframe(df_audit, use_container_width=True)

# =====================================================================
# 🦶 FOOTER BRANDING
# =====================================================================
st.write("---")
st.markdown(
    """
    <div style='text-align:center;'>
        <span style='color:#555555; font-size:10px; font-weight:800;'>POWERED BY</span><br>
        <span style='color:#ffffff; font-size:14px; font-weight:900;'>ACCU<span style='color:#ff5500;'>SPORT</span></span>
    </div>
""",
    unsafe_allow_html=True,
)
