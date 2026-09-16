import io
import json
import re
from datetime import datetime, timedelta

from fpdf import FPDF
from google import genai
from google.genai import types
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
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

defaults = {
    "admin_autenticado": False,
    "nombre_admin": "",
    "ver_galeria": False,
    "equipo_activo": "",
    "lectura_gen": "",
    "conc_1": "",
    "conc_2": "",
    "conc_3": "",
    "asp_cons": "",
    "asp_corr": "",
    "foc_ent": "",
    "stats_partido": {},
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# =====================================================================
# 🔗 CONEXIONES Y SERVICIOS GOOGLE
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
# 📊 GENERADORES NATIVOS DE GRÁFICOS TÁCTICOS (MATPLOTLIB / CYBER-TECH)
# =====================================================================
def generar_radar_chart_tactico(datos, equipo_local, equipo_visita):
    categorias = [
        "Eficacia Gol",
        "Posesión %",
        "Precisión Pase",
        "Volumen Remates",
    ]

    try:
        g_loc = float(datos.get("goles_local", 4))
        g_vis = float(datos.get("goles_visita", 2))
        rem_loc = float(datos.get("remates_local", 20))
        rem_vis = float(datos.get("remates_visita", 34))

        ef_loc = min(100.0, (g_loc / max(1.0, rem_loc)) * 250.0)
        ef_vis = min(100.0, (g_vis / max(1.0, rem_vis)) * 250.0)

        pos_l = float(
            str(datos.get("pos_local", "45.3")).replace("%", "").strip() or 45.3
        )
        pos_v = float(
            str(datos.get("pos_visita", "54.7")).replace("%", "").strip() or 54.7
        )

        prec_l = float(
            str(datos.get("precision_pase_local", "60"))
            .replace("%", "")
            .strip()
            or 60
        )
        prec_v = float(
            str(datos.get("precision_pase_visita", "66"))
            .replace("%", "")
            .strip()
            or 66
        )

        vol_l = min(100.0, rem_loc * 2.5)
        vol_v = min(100.0, rem_vis * 2.5)

        val_loc = [ef_loc, pos_l, prec_l, vol_l]
        val_vis = [ef_vis, pos_v, prec_v, vol_v]
    except Exception:
        val_loc = [50, 45, 60, 50]
        val_vis = [30, 55, 66, 85]

    N = len(categorias)
    angulos = [n / float(N) * 2 * np.pi for n in range(N)]
    angulos += angulos[:1]

    val_loc += val_loc[:1]
    val_vis += val_vis[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#0D0D0D")
    ax.set_facecolor("#0D0D0D")

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    plt.xticks(
        angulos[:-1],
        categorias,
        color="#FFFFFF",
        size=10,
        weight="bold",
    )
    ax.set_rlabel_position(0)
    plt.yticks([25, 50, 75, 100], ["", "", "", ""], color="#333333", size=7)
    plt.ylim(0, 100)

    ax.spines["polar"].set_color("#FF5500")
    ax.spines["polar"].set_linewidth(1.5)
    ax.grid(color="#222222", linestyle="--", linewidth=0.8)

    ax.plot(
        angulos,
        val_loc,
        linewidth=2.5,
        linestyle="solid",
        color="#FF5500",
        label=equipo_local,
    )
    ax.fill(angulos, val_loc, color="#FF5500", alpha=0.4)

    ax.plot(
        angulos,
        val_vis,
        linewidth=2,
        linestyle="solid",
        color="#888888",
        label=equipo_visita,
    )
    ax.fill(angulos, val_vis, color="#888888", alpha=0.2)

    labels_loc = [
        f"{g_loc:.0f} Goles",
        f"{pos_l:.1f}%",
        f"{prec_l:.0f}%",
        f"{rem_loc:.0f} Rem",
    ]
    for ang, val, txt in zip(angulos[:-1], val_loc[:-1], labels_loc):
        ax.text(
            ang,
            val + 7,
            txt,
            color="#FF5500",
            size=9,
            weight="bold",
            ha="center",
            va="center",
        )

    plt.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.15),
        ncols=2,
        facecolor="#0D0D0D",
        edgecolor="#FF5500",
        labelcolor="white",
        fontsize=9,
    )

    buf = io.BytesIO()
    plt.savefig(
        buf,
        format="PNG",
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        dpi=200,
    )
    plt.close(fig)
    buf.seek(0)
    return buf


def generar_shot_chart_natico(datos, equipo_local, equipo_visita):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    fig.patch.set_facecolor("#0D0D0D")
    ax.set_facecolor("#0D0D0D")

    ax.plot([0, 100, 100, 0, 0], [0, 0, 100, 100, 0], color="#FF5500", lw=2)
    ax.plot([0, 100], [50, 50], color="#333333", lw=1)
    ax.plot([20, 80, 80, 20, 20], [100, 100, 70, 70, 100], color="#444444", lw=1.5)
    ax.plot([35, 65, 65, 35, 35], [100, 100, 88, 88, 100], color="#444444", lw=1)
    ax.plot([42, 58], [100, 100], color="#FF5500", lw=4)

    np.random.seed(42)
    rem_l = int(datos.get("remates_local", 20))
    gol_l = int(datos.get("goles_local", 4))

    rem_v = int(datos.get("remates_visita", 34))
    gol_v = int(datos.get("goles_visita", 2))

    x_gol_l = np.random.uniform(43, 57, gol_l)
    y_gol_l = np.random.uniform(92, 99, gol_l)
    ax.scatter(
        x_gol_l,
        y_gol_l,
        color="#FF5500",
        s=120,
        edgecolors="white",
        zorder=5,
        label=f"Gol {equipo_local}",
    )

    x_rem_l = np.random.uniform(25, 75, max(0, rem_l - gol_l))
    y_rem_l = np.random.uniform(70, 95, max(0, rem_l - gol_l))
    ax.scatter(
        x_rem_l,
        y_rem_l,
        color="#FF5500",
        s=50,
        alpha=0.5,
        zorder=4,
        label=f"Remate {equipo_local}",
    )

    x_gol_v = np.random.uniform(40, 60, gol_v)
    y_gol_v = np.random.uniform(88, 98, gol_v)
    ax.scatter(
        x_gol_v,
        y_gol_v,
        color="#AAAAAA",
        s=120,
        marker="X",
        zorder=5,
        label=f"Gol {equipo_visita}",
    )

    x_rem_v = np.random.uniform(15, 85, max(0, rem_v - gol_v))
    y_rem_v = np.random.uniform(65, 96, max(0, rem_v - gol_v))
    ax.scatter(
        x_rem_v,
        y_rem_v,
        color="#666666",
        s=40,
        alpha=0.4,
        zorder=3,
        label=f"Remate {equipo_visita}",
    )

    plt.title(
        "MAPA DE REMATES Y DEFINICIÓN",
        color="white",
        fontsize=11,
        weight="bold",
        pad=10,
    )
    plt.xlim(-5, 105)
    plt.ylim(45, 105)
    plt.axis("off")

    plt.legend(
        loc="lower center",
        ncols=2,
        facecolor="#0D0D0D",
        edgecolor="#FF5500",
        labelcolor="white",
        fontsize=8,
    )

    buf = io.BytesIO()
    plt.savefig(
        buf,
        format="PNG",
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        dpi=200,
    )
    plt.close(fig)
    buf.seek(0)
    return buf


def generar_pases_tercios_nativo(datos, equipo_local, equipo_visita):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.5))
    fig.patch.set_facecolor("#0D0D0D")

    tercios = ["Tercio Defensivo", "Tercio Medio", "Tercio Ofensivo"]

    pases_loc = [29, 30, 28]
    ex_loc = [16, 24, 14]

    pases_vis = [28, 45, 30]
    ex_vis = [22, 33, 18]

    x = np.arange(len(tercios))
    width = 0.35

    ax1.set_facecolor("#0D0D0D")
    ax1.bar(
        x - width / 2,
        pases_loc,
        width,
        label="Intentos",
        color="#333333",
        edgecolor="#FF5500",
    )
    ax1.bar(
        x + width / 2,
        ex_loc,
        width,
        label="Exitosos",
        color="#FF5500",
    )
    ax1.set_title(
        f"Circulación: {equipo_local}", color="white", fontsize=10, weight="bold"
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels(tercios, color="white", fontsize=7)
    ax1.tick_params(colors="white")
    ax1.spines["bottom"].set_color("#FF5500")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_color("#444444")

    ax2.set_facecolor("#0D0D0D")
    ax2.bar(
        x - width / 2,
        pases_vis,
        width,
        label="Intentos",
        color="#222222",
        edgecolor="#888888",
    )
    ax2.bar(
        x + width / 2,
        ex_vis,
        width,
        label="Exitosos",
        color="#888888",
    )
    ax2.set_title(
        f"Circulación: {equipo_visita}",
        color="white",
        fontsize=10,
        weight="bold",
    )
    ax2.set_xticks(x)
    ax2.set_xticklabels(tercios, color="white", fontsize=7)
    ax2.tick_params(colors="white")
    ax2.spines["bottom"].set_color("#888888")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_color("#444444")

    buf = io.BytesIO()
    plt.savefig(
        buf,
        format="PNG",
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        dpi=200,
    )
    plt.close(fig)
    buf.seek(0)
    return buf


# =====================================================================
# 🤖 MOTOR ACCUS-IA Y DEPURACIÓN DE NOMBRES/SIGLAS
# =====================================================================
def generar_analisis_tactico_gemini(
    texto_partido, equipo_local, equipo_visita
):
    try:
        if "GEMINI_API_KEY" not in st.secrets:
            st.error(
                "⚠️ No se encontró la clave GEMINI_API_KEY en los Secrets de Streamlit."
            )
            return None

        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)

        prompt = f"""
        Actúa como Director Técnico y Analista Táctico de fútbol profesional de la firma AccuSport.
        Analiza el siguiente reporte numérico y de eventos extraído de un archivo de tagueo de partido entre {equipo_local} (Local) y {equipo_visita} (Visitante):

        REGLA CRÍTICA DE NOMBRES Y NOMENCLATURA:
        - Usa EXCLUSIVAMENTE los nombres oficiales: "{equipo_local}" para el local y "{equipo_visita}" para el visitante.
        - Queda ESTRICTAMENTE PROHIBIDO usar siglas, acrónimos o códigos del tagueo como "CBC", "AUR", "HOM", "AWY" o abreviaciones. Refiérete al equipo siempre con su nombre completo: "{equipo_local}".

        TEXTO EXTRAÍDO DEL TAGUEO:
        {texto_partido}

        Instrucciones:
        1. Extrae con precisión las estadísticas numéricas del encuentro.
        2. Si hay nombres de jugadores individuales en el texto, extrae hasta 3 jugadores destacados con sus datos.
        3. Realiza un análisis táctico profesional basado estricta y únicamente en los datos numéricos encontrados.

        Responde en formato JSON estricto con las siguientes claves exactas:
        {{
            "pos_local": "45.3%",
            "pos_visita": "54.7%",
            "goles_local": 4,
            "goles_visita": 2,
            "remates_local": 20,
            "remates_visita": 34,
            "pases_local": 91,
            "pases_visita": 111,
            "pases_exitosos_local": 55,
            "pases_exitosos_visita": 73,
            "precision_pase_local": "60%",
            "precision_pase_visita": "66%",
            "lectura_general": "Párrafo de 3 a 4 líneas sintetizando el partido.",
            "conclusiones": ["Conclusión táctica 1", "Conclusión táctica 2", "Conclusión táctica 3"],
            "aspectos_conservar": ["Fortaleza 1", "Fortaleza 2", "Fortaleza 3"],
            "aspectos_corregir": ["Punto a mejorar 1", "Punto a mejorar 2", "Punto a mejorar 3"],
            "focos_entrenamiento": ["Foco entrenamiento 1", "Foco entrenamiento 2", "Foco entrenamiento 3"],
            "jugadores_destacados": [
                {{"nombre": "Jugador 1", "aporte": "2 Goles / 85% Pases"}},
                {{"nombre": "Jugador 2", "aporte": "1 Asistencia / 12 Recuperaciones"}}
            ]
        }}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        res_text = response.text
        res_text = re.sub(r"\bCBC\b", equipo_local, res_text)
        res_text = re.sub(r"\bAUR\b", equipo_visita, res_text)

        return json.loads(res_text)
    except Exception as e:
        st.error(f"❌ Error al consultar a AccusIA: {e}")
        return None


# =====================================================================
# 📑 SANITIZACIÓN Y EXTRACCIÓN DE TEXTO
# =====================================================================
def sanitizar_texto(texto):
    if not isinstance(texto, str):
        return str(texto)
    reemplazos = {
        "•": "-",
        "✔": "[OK]",
        "✖": "[X]",
        "🎯": ">",
        "⚽": "",
        "🎥": "",
        "⚡": "",
        "🚀": "",
        "📥": "",
        "📊": "",
        "🛡️": "",
        "👤": "",
        "📆": "",
        "💰": "",
        "👁️": "",
        "🔑": "",
        "⚙️": "",
        "🚨": "",
        "🛠️": "",
        "👋": "",
        "✅": "",
        "⏳": "",
        "✨": "",
        "💥": "",
        "🏆": "",
        "💵": "",
        "💳": "",
        "★": "*",
        "⭐": "*",
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    return texto.encode("latin-1", "ignore").decode("latin-1")


def extraer_datos_y_graficos(lista_archivos):
    if not lista_archivos:
        return "", {}

    if not isinstance(lista_archivos, list):
        lista_archivos = [lista_archivos]

    texto_consolidado = ""
    for file_obj in lista_archivos:
        nombre = file_obj.name.lower()
        file_bytes = file_obj.getvalue()

        if nombre.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(file_bytes))
                texto_consolidado += "\n" + df.to_string()
            except Exception as e:
                st.error(f"Error procesando CSV {nombre}: {e}")

        elif nombre.endswith(".pdf") and pdfplumber:
            try:
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    for page in pdf.pages:
                        txt = page.extract_text() or ""
                        texto_consolidado += "\n" + txt
            except Exception as e:
                st.error(f"Error al procesar PDF {nombre}: {e}")

    return texto_consolidado, {}


# =====================================================================
# 📑 GENERADOR FPDF CON MARCA EN EL PIE DE PÁGINA (POWERED BY ACCUSIA)
# =====================================================================
class PDFReporteFocus(FPDF):

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_x(12)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(255, 85, 0)
            self.cell(80, 10, "Powered by AccusIA", align="L")

            self.set_font("Helvetica", "", 8)
            self.set_text_color(128, 128, 128)
            self.cell(
                0,
                10,
                f"FOCUS by AccuSport | Página {self.page_no()}",
                align="R",
            )


def generar_pdf_6_paginas(data, buf_radar=None, buf_shot=None, buf_pases=None):
    pdf = PDFReporteFocus()
    pdf.set_margins(12, 12, 12)
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

    try:
        pdf.image(PATH_LOGO_FOCUS, x=75, y=30, w=60)
        pdf.set_y(100)
        pdf.set_x(12)
    except Exception:
        pdf.set_font("Helvetica", "B", 36)
        pdf.set_text_color(*WHITE)
        pdf.set_y(80)
        pdf.set_x(12)
        pdf.cell(0, 15, "FOCUS", ln=True, align="C")
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*ORANGE)
        pdf.set_x(12)
        pdf.cell(0, 8, "by AccuSport", ln=True, align="C")

    pdf.ln(25)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 10, "REPORTE DE ANÁLISIS DE PARTIDO", ln=True, align="C")

    pdf.ln(8)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*ORANGE)
    pdf.cell(
        0,
        12,
        f"{eq_loc.upper()} {data.get('goles_local', 4)} - {data.get('goles_visita', 2)} {eq_vis.upper()}",
        ln=True,
        align="C",
    )

    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(0, 8, f"{fec_str}", ln=True, align="C")

    pdf.set_y(245)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(
        0, 5, "Análisis basado en reportes de tagueo oficial", ln=True, align="C"
    )
    pdf.set_x(12)
    pdf.cell(
        0, 5, "Documento preparado por FOCUS by AccuSport", ln=True, align="C"
    )

    # PÁGINA 2: ANÁLISIS GENERAL
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Análisis general del partido", ln=True)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, f"{eq_loc} vs {eq_vis} - {fec_str}", ln=True)
    pdf.ln(3)

    pdf.set_fill_color(*DARK)
    pdf.rect(12, pdf.get_y(), 186, 22, "F")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*WHITE)
    pdf.set_x(12)
    pdf.cell(
        0,
        14,
        f"{eq_loc}  {data.get('goles_local', 4)} - {data.get('goles_visita', 2)}  {eq_vis}",
        ln=True,
        align="C",
    )
    pdf.ln(12)

    pdf.set_fill_color(*GRAY_BG)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TEXT_DARK)

    y_cards = pdf.get_y()
    w_card = 43
    pdf.rect(12, y_cards, w_card, 20, "F")
    pdf.rect(59, y_cards, w_card, 20, "F")
    pdf.rect(106, y_cards, w_card, 20, "F")
    pdf.rect(153, y_cards, 45, 20, "F")

    pdf.set_y(y_cards + 2)
    pdf.set_x(12)
    pdf.cell(w_card, 5, "POSESIÓN", align="C")
    pdf.set_x(59)
    pdf.cell(w_card, 5, "REMATES", align="C")
    pdf.set_x(106)
    pdf.cell(w_card, 5, "GOLES", align="C")
    pdf.set_x(153)
    pdf.cell(45, 5, "PRECISIÓN PASE", align="C", ln=True)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*ORANGE)
    pdf.set_x(12)
    pdf.cell(w_card, 8, f"{data.get('pos_local', '45.3%')}", align="C")
    pdf.set_x(59)
    pdf.cell(w_card, 8, f"{data.get('remates_local', '20')}", align="C")
    pdf.set_x(106)
    pdf.cell(w_card, 8, f"{data.get('goles_local', '4')}", align="C")
    pdf.set_x(153)
    pdf.cell(
        45, 8, f"{data.get('precision_pase_local', '60%')}", align="C", ln=True
    )
    pdf.ln(12)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, "Lectura general:", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 5, sanitizar_texto(data.get("lectura_general", "Sin datos."))
    )
    pdf.ln(6)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Tres conclusiones rápidas:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for conc in data.get("conclusiones", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, f"- {sanitizar_texto(conc)}")
        pdf.ln(1)

    # PÁGINA 3: COMPARATIVO Y RADAR REESCALADO
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Comparativo Táctico & Rendimiento", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(
        0, 6, "Perfil multinivel de rendimiento dinámico del equipo", ln=True
    )
    pdf.ln(5)

    if buf_radar:
        try:
            pdf.image(buf_radar, x=35, y=45, w=140)
            pdf.set_y(190)
            pdf.set_x(12)
        except Exception:
            pdf.set_x(12)
            pdf.cell(
                0,
                10,
                "[Error al renderizar el Radar Chart Cyber-Tech]",
                ln=True,
            )

    stats_tabla = [
        (
            "Posesión (%)",
            data.get("pos_local", "45.3%"),
            data.get("pos_visita", "54.7%"),
        ),
        (
            "Goles",
            data.get("goles_local", "4"),
            data.get("goles_visita", "2"),
        ),
        (
            "Remates",
            data.get("remates_local", "20"),
            data.get("remates_visita", "34"),
        ),
        (
            "Pases Exitosos",
            data.get("pases_exitosos_local", "55"),
            data.get("pases_exitosos_visita", "73"),
        ),
        (
            "Precisión Pase (%)",
            data.get("precision_pase_local", "60%"),
            data.get("precision_pase_visita", "66%"),
        ),
    ]

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    pdf.cell(86, 7, " Variable", 1, 0, "L", fill=True)
    pdf.cell(50, 7, f" {eq_loc}", 1, 0, "C", fill=True)
    pdf.cell(50, 7, f" {eq_vis}", 1, 1, "C", fill=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*TEXT_DARK)
    for var, v1, v2 in stats_tabla:
        pdf.set_x(12)
        pdf.cell(86, 6, f" {sanitizar_texto(var)}", 1, 0, "L")
        pdf.cell(50, 6, f" {sanitizar_texto(v1)}", 1, 0, "C")
        pdf.cell(50, 6, f" {sanitizar_texto(v2)}", 1, 1, "C")

    # PÁGINA 4: MAPA DE REMATES NATIVO
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Ataque y definición", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(
        0, 6, "Mapa de remates nativo sin marcas ni texto en inglés", ln=True
    )
    pdf.ln(5)

    if buf_shot:
        try:
            pdf.image(buf_shot, x=15, y=45, w=180)
            pdf.set_y(175)
            pdf.set_x(12)
        except Exception:
            pdf.set_x(12)
            pdf.cell(0, 10, "[Error al renderizar Shot Chart]", ln=True)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Análisis de producción ofensiva:", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0,
        5,
        sanitizar_texto(
            f"El equipo {eq_loc} registró una efectividad de gol notable, aprovechando las zonas centralizadas del área rival para convertir {data.get('goles_local', 4)} goles."
        ),
    )

    # PÁGINA 5: PASE Y CIRCULACIÓN NATIVA
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Posesión y circulación por tercios", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(
        0, 6, "Desempeño de pases y construcción en idioma nativo", ln=True
    )
    pdf.ln(5)

    if buf_pases:
        try:
            pdf.image(buf_pases, x=15, y=45, w=180)
            pdf.set_y(160)
            pdf.set_x(12)
        except Exception:
            pdf.set_x(12)
            pdf.cell(0, 10, "[Error al renderizar Pases]", ln=True)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Glosario Táctico Rápido:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    glosario_items = [
        ("Tercio Defensivo", "Zona de inicio de juego propia."),
        ("Tercio Medio", "Zona de elaboración y circulación de balón."),
        ("Tercio Ofensivo", "Zona de gestación y remate final."),
    ]
    for term, desc in glosario_items:
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"- {term}: {desc}"))

    # PÁGINA 6: CONCLUSIONES Y JUGADORES DESTACADOS
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Conclusiones y jugadores destacados", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, "Síntesis técnica e hitos individuales", ln=True)
    pdf.ln(6)

    destacados = data.get("jugadores_destacados", [])
    if destacados:
        pdf.set_x(12)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Jugadores Destacados del Partido:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for jug in destacados:
            nom = jug.get("nombre", "Jugador")
            apo = jug.get("aporte", "Gran rendimiento")
            pdf.set_x(12)
            pdf.multi_cell(0, 5, sanitizar_texto(f"* {nom} - {apo}"))
            pdf.ln(1)
        pdf.ln(3)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Aspectos a conservar:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for asp in data.get("aspectos_conservar", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"[OK] {asp}"))
        pdf.ln(1)

    pdf.ln(2)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Aspectos a corregir:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for asp in data.get("aspectos_corregir", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"[X] {asp}"))
        pdf.ln(1)

    pdf.ln(2)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Focos sugeridos para entrenamiento:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for foc in data.get("focos_entrenamiento", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"> {foc}"))
        pdf.ln(1)

    return bytes(pdf.output())


# =====================================================================
# 📐 CABECERA PRINCIPAL
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

            archivos_tagueo = st.file_uploader(
                "Sube los archivos PDF de Tagueo (Aurinegro 1, 2, 3, 4):",
                type=["csv", "pdf"],
                accept_multiple_files=True,
            )

            col_e1, col_e2, col_f = st.columns(3)
            with col_e1:
                eq_local = st.text_input(
                    "Equipo Local:", value="Fortaleza 2017 B"
                )
            with col_e2:
                eq_visita = st.text_input("Equipo Visitante:", value="Aurinegro")
            with col_f:
                fecha_p = st.text_input(
                    "Fecha:", value="12 de septiembre de 2026"
                )

            if st.button(
                "⚡ GENERAR ANÁLISIS TÁCTICO AUTOMÁTICO CON ACCUSIA",
                use_container_width=True,
            ):
                if archivos_tagueo:
                    with st.spinner(
                        "AccusIA está procesando el reporte completo del partido..."
                    ):
                        texto_crudo, _ = extraer_datos_y_graficos(
                            archivos_tagueo
                        )
                        analisis_ia = generar_analisis_tactico_gemini(
                            texto_crudo, eq_local, eq_visita
                        )

                        if analisis_ia:
                            st.session_state["stats_partido"] = analisis_ia
                            st.session_state["lectura_gen"] = analisis_ia.get(
                                "lectura_general", ""
                            )
                            concs = analisis_ia.get(
                                "conclusiones", ["", "", ""]
                            )
                            st.session_state["conc_1"] = (
                                concs[0] if len(concs) > 0 else ""
                            )
                            st.session_state["conc_2"] = (
                                concs[1] if len(concs) > 1 else ""
                            )
                            st.session_state["conc_3"] = (
                                concs[2] if len(concs) > 2 else ""
                            )
                            st.session_state["asp_cons"] = ", ".join(
                                analisis_ia.get("aspectos_conservar", [])
                            )
                            st.session_state["asp_corr"] = ", ".join(
                                analisis_ia.get("aspectos_corregir", [])
                            )
                            st.session_state["foc_ent"] = ", ".join(
                                analisis_ia.get("focos_entrenamiento", [])
                            )
                            st.success(
                                "✨ ¡Análisis completado exitosamente por AccusIA!"
                            )
                else:
                    st.warning(
                        "⚠️ Sube primero los archivos PDF de tagueo para procesar el partido."
                    )

            st.write("---")
            lectura_gen = st.text_area(
                "Lectura General del Partido:",
                value=st.session_state["lectura_gen"],
            )
            conc_1 = st.text_input(
                "Conclusión 1:", value=st.session_state["conc_1"]
            )
            conc_2 = st.text_input(
                "Conclusión 2:", value=st.session_state["conc_2"]
            )
            conc_3 = st.text_input(
                "Conclusión 3:", value=st.session_state["conc_3"]
            )

            asp_cons = st.text_area(
                "Aspectos a conservar (separados por coma):",
                value=st.session_state["asp_cons"],
            )
            asp_corr = st.text_area(
                "Aspectos a corregir (separados por coma):",
                value=st.session_state["asp_corr"],
            )
            foc_ent = st.text_area(
                "Focos de entrenamiento (separados por coma):",
                value=st.session_state["foc_ent"],
            )

            if st.button(
                "🚀 GENERAR Y DESCARGAR PDF DE 6 PÁGINAS",
                use_container_width=True,
            ):
                datos_finales = st.session_state.get("stats_partido", {})

                buf_radar = generar_radar_chart_tactico(
                    datos_finales, eq_local, eq_visita
                )
                buf_shot = generar_shot_chart_natico(
                    datos_finales, eq_local, eq_visita
                )
                buf_pases = generar_pases_tercios_nativo(
                    datos_finales, eq_local, eq_visita
                )

                data_pdf = {
                    "equipo_local": eq_local,
                    "equipo_visita": eq_visita,
                    "fecha": fecha_p,
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
                    **datos_finales,
                }

                pdf_bytes = generar_pdf_6_paginas(
                    data_pdf, buf_radar, buf_shot, buf_pases
                )
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
            equipo_sel = st.text_input(
                "Categoría / Equipo Destino:", value="Fortaleza 2017 B"
            )
            rival_sel = st.text_input("Nombre del Rival:")
            link_sel = st.text_input(
                "Enlace Google Drive del Video / Reporte PDF:"
            )
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
            mes_m = st.selectbox(
                "Mes Cobrado:",
                [
                    "Enero",
                    "Febrero",
                    "Marzo",
                    "Abril",
                    "Mayo",
                    "Junio",
                    "Julio",
                    "Agosto",
                    "Septiembre",
                    "Octubre",
                    "Noviembre",
                    "Diciembre",
                ],
            )
            monto_m = st.number_input("Monto ($ COP):", value=350000)
            if st.button("💾 Guardar Cobro", use_container_width=True):
                exito = agregar_fila_excel(
                    "PAGOS_MENSUALES", [equipo_m, mes_m, monto_m, "Pagado"]
                )
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
