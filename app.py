import base64
import io
import json
import re
import tempfile
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
import streamlit.components.v1 as components

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
# 🛠️ FUNCIONES DE UTILIDAD Y PARSER DE DATOS
# =====================================================================
def obtener_valor_columna(row, nombres_posibles, defecto=""):
    """Extrae un valor de la fila probando múltiples nombres de columna sin importar mayúsculas, minúsculas o espacios."""
    cols_row = {str(k).strip().lower(): k for k in row.index}
    for nombre in nombres_posibles:
        nombre_clean = nombre.strip().lower()
        if nombre_clean in cols_row:
            real_col = cols_row[nombre_clean]
            val = row[real_col]
            if (
                pd.notna(val)
                and str(val).strip() != ""
                and str(val).strip().lower() not in ["none", "nan", "null"]
            ):
                return str(val).strip()
    return defecto


def renderizar_reproductor_video(link_url):
    """Renderiza un reproductor multimedia compatible con Google Drive, YouTube y video directo."""
    if not link_url or not isinstance(link_url, str) or not link_url.startswith("http"):
        st.info("ℹ️ No hay enlace de video cargado para este encuentro.")
        return

    link_url = link_url.strip()

    drive_match = re.search(r"(?:file/d/|id=)([\w-]+)", link_url)
    is_drive_folder = (
        "drive.google.com/drive/folders" in link_url
        or "drive.google.com/drive/u/" in link_url
    )

    if "drive.google.com" in link_url and drive_match and not is_drive_folder:
        file_id = drive_match.group(1)
        embed_url = f"https://drive.google.com/file/d/{file_id}/preview"

        iframe_code = f"""
        <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; border-radius: 12px; border: 1px solid #ff5500; box-shadow: 0 4px 15px rgba(255, 85, 0, 0.25);">
            <iframe src="{embed_url}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allow="autoplay" allowfullscreen></iframe>
        </div>
        """
        components.html(iframe_code, height=380)
    elif (
        "youtube.com" in link_url
        or "youtu.be" in link_url
        or link_url.endswith((".mp4", ".mov", ".m4v", ".webm"))
    ):
        try:
            st.video(link_url)
        except Exception:
            st.warning("⚠️ No se pudo reproducir el video directamente.")
    else:
        st.info("📁 El enlace guardado corresponde a una carpeta de almacenamiento o recurso externo.")


# =====================================================================
# 🔗 CONEXIONES Y SERVICIOS GOOGLE (CON CACHÉ ANTI-BLOQUEOS)
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


@st.cache_data(ttl=60)
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
            st.cache_data.clear()
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


def inicializar_pestanas_jugadores():
    client = obtener_cliente_sheets()
    if not client:
        st.error("❌ No se pudo conectar con Google Sheets.")
        return

    try:
        sheet = client.open_by_key(CONFIG_SHEET_ID)

        headers_historico = [
            "ID_Partido",
            "Fecha",
            "Equipo",
            "Rival",
            "Jugador",
            "Dorsal",
            "Minutos_Jugados",
            "Participaciones_Totales",
            "Goles",
            "Asistencias",
            "Remates_Totales",
            "Remates_A_Puerta",
            "Centros",
            "Pases_Intentados",
            "Pases_Completados",
            "Recuperaciones",
            "Duelos_Def_Ganados",
            "Foto_URL",
        ]
        try:
            ws_hist = sheet.worksheet("HISTORICO_PARTIDOS")
        except Exception:
            ws_hist = sheet.add_worksheet(
                title="HISTORICO_PARTIDOS", rows=100, cols=20
            )
            ws_hist.append_row(headers_historico)

        headers_acumulado = [
            "Jugador",
            "Equipo",
            "Dorsal",
            "Partidos_Jugados",
            "Minutos_Totales",
            "Goles_Totales",
            "Asistencias_Totales",
            "Remates_Totales",
            "Remates_A_Puerta",
            "Efectividad_Remate_%",
            "Pases_Completados",
            "Precision_Pase_%",
            "Recuperaciones_Totales",
            "Foto_URL",
        ]
        try:
            ws_acum = sheet.worksheet("ACUMULADO_TEMPORADA")
        except Exception:
            ws_acum = sheet.add_worksheet(
                title="ACUMULADO_TEMPORADA", rows=100, cols=20
            )
            ws_acum.append_row(headers_acumulado)

        st.cache_data.clear()
        st.success(
            "✅ Pestañas 'HISTORICO_PARTIDOS' y 'ACUMULADO_TEMPORADA' listadas y creadas correctamente en Google Sheets."
        )
    except Exception as e:
        st.error(f"❌ Error al inicializar pestañas: {e}")


def procesar_foto_jugador_base64(file_obj):
    try:
        img = Image.open(io.BytesIO(file_obj.getvalue()))
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((180, 180))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=55)
        img_bytes = buf.getvalue()

        b64_str = base64.b64encode(img_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        st.error(f"❌ Error al procesar imagen: {e}")
        return None


# =====================================================================
# 📊 GENERADORES NATIVOS Y MAPA DE CALOR MANUAL
# =====================================================================
def generar_mapa_calor_manual(matriz_3x3, nombre_jugador):
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    fig.patch.set_facecolor("#1b4332")
    ax.set_facecolor("#1b4332")

    line_col = "#ffffff"
    ax.plot([0, 100, 100, 0, 0], [0, 0, 100, 100, 0], color=line_col, lw=2)
    ax.plot([50, 50], [0, 100], color=line_col, lw=1.5)
    ax.plot([0, 16, 16, 0], [25, 25, 75, 75], color=line_col, lw=1.2)
    ax.plot([100, 84, 84, 100], [25, 25, 75, 75], color=line_col, lw=1.2)

    centro_circulo = plt.Circle((50, 50), 12, color=line_col, fill=False, lw=1.2)
    ax.add_artist(centro_circulo)

    ax.imshow(
        matriz_3x3,
        cmap="YlOrRd",
        alpha=0.65,
        extent=[0, 100, 0, 100],
        origin="lower",
        interpolation="gaussian",
    )

    plt.title(
        f"MAPA DE INFLUENCIA Y CALOR TÁCTICO: {nombre_jugador.upper()}",
        color="white",
        fontsize=8.5,
        weight="bold",
        pad=8,
    )
    plt.xlim(-2, 102)
    plt.ylim(-2, 102)
    plt.axis("off")

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


def generar_grafico_resumen_pagina2(datos, equipo_local, equipo_visita):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.5, 3.2))
    fig.patch.set_facecolor("#0D0D0D")

    ax1.set_facecolor("#0D0D0D")
    try:
        pos_l = float(
            str(datos.get("pos_local", "45.3")).replace("%", "").strip() or 45.3
        )
        pos_v = float(
            str(datos.get("pos_visita", "54.7")).replace("%", "").strip() or 54.7
        )
    except Exception:
        pos_l, pos_v = 45.3, 54.7

    sizes = [pos_l, pos_v]
    colors = ["#FF5500", "#00E5FF"]
    labels = [f"{equipo_local}\n{pos_l}%", f"{equipo_visita}\n{pos_v}%"]

    wedges, texts, autotexts = ax1.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.72,
        textprops=dict(color="white", fontsize=8, weight="bold"),
    )
    for t in texts:
        t.set_color("white")
        t.set_fontsize(8)
        t.set_weight("bold")
    for at in autotexts:
        at.set_color("black")
        at.set_fontsize(8)
        at.set_weight("bold")

    centre_circle = plt.Circle((0, 0), 0.52, fc="#0D0D0D")
    ax1.add_artist(centre_circle)
    ax1.set_title(
        "POSESIÓN DE BALÓN (%)", color="white", fontsize=9.5, weight="bold", pad=8
    )

    ax2.set_facecolor("#0D0D0D")
    try:
        g_l = int(datos.get("goles_local", 4))
        g_v = int(datos.get("goles_visita", 2))
        r_l = int(datos.get("remates_local", 20))
        r_v = int(datos.get("remates_visita", 34))
    except Exception:
        g_l, g_v, r_l, r_v = 4, 2, 20, 34

    metricas = ["Remates Totales", "Goles Concretados"]
    x = np.arange(len(metricas))
    width = 0.35

    ax2.bar(
        x - width / 2, [r_l, g_l], width, label=equipo_local, color="#FF5500"
    )
    ax2.bar(
        x + width / 2, [r_v, g_v], width, label=equipo_visita, color="#00E5FF"
    )

    ax2.set_title(
        "EFECTIVIDAD OFENSIVA", color="white", fontsize=9.5, weight="bold", pad=8
    )
    ax2.set_xticks(x)
    ax2.set_xticklabels(metricas, color="white", fontsize=8, weight="bold")
    ax2.tick_params(colors="white")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["bottom"].set_color("#333333")
    ax2.spines["left"].set_color("#333333")

    for bar in ax2.patches:
        h = bar.get_height()
        if h > 0:
            ax2.annotate(
                f"{int(h)}",
                (bar.get_x() + bar.get_width() / 2, h),
                ha="center",
                va="bottom",
                color="white",
                fontsize=8,
                weight="bold",
                xytext=(0, 2),
                textcoords="offset points",
            )

    ax2.legend(
        loc="upper right",
        facecolor="#0D0D0D",
        edgecolor="#FF5500",
        labelcolor="white",
        fontsize=7.5,
    )

    plt.tight_layout()
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

    fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw=dict(polar=True))
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
    plt.ylim(0, 120)

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
    ax.fill(angulos, val_loc, color="#FF5500", alpha=0.35)

    ax.plot(
        angulos,
        val_vis,
        linewidth=2.0,
        linestyle="--",
        color="#00E5FF",
        label=equipo_visita,
    )
    ax.fill(angulos, val_vis, color="#00E5FF", alpha=0.15)

    labels_loc = [
        f"{g_loc:.0f} Goles",
        f"{pos_l:.1f}%",
        f"{prec_l:.0f}%",
        f"{rem_loc:.0f} Rem",
    ]
    for ang, val, txt in zip(angulos[:-1], val_loc[:-1], labels_loc):
        ax.text(
            ang,
            min(112, val + 14),
            txt,
            color="#FF5500",
            size=8.5,
            weight="bold",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.2",
                facecolor="#0D0D0D",
                edgecolor="#FF5500",
                lw=0.8,
            ),
        )

    plt.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.20),
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
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    fig.patch.set_facecolor("#1b4332")
    ax.set_facecolor("#1b4332")

    line_col = "#ffffff"
    ax.plot([0, 100, 100, 0, 0], [0, 0, 100, 100, 0], color=line_col, lw=2)
    ax.plot([0, 100], [50, 50], color=line_col, lw=1)
    ax.plot([18, 82, 82, 18, 18], [100, 100, 68, 68, 100], color=line_col, lw=1.5)
    ax.plot([35, 65, 65, 35, 35], [100, 100, 88, 88, 100], color=line_col, lw=1)
    ax.plot([42, 58], [100, 100], color="#FF5500", lw=4)

    np.random.seed(42)
    rem_l = int(datos.get("remates_local", 20))
    gol_l = int(datos.get("goles_local", 4))

    x_gol_l = np.random.uniform(43, 57, gol_l)
    y_gol_l = np.random.uniform(91, 98, gol_l)
    ax.scatter(
        x_gol_l,
        y_gol_l,
        color="#FF5500",
        s=150,
        edgecolors="white",
        linewidth=1.8,
        zorder=5,
        label=f"Goles ({gol_l})",
    )

    x_rem_l = np.random.uniform(22, 78, max(0, rem_l - gol_l))
    y_rem_l = np.random.uniform(65, 96, max(0, rem_l - gol_l))
    ax.scatter(
        x_rem_l,
        y_rem_l,
        color="#FFD166",
        s=65,
        alpha=0.85,
        edgecolors="#1b4332",
        zorder=4,
        label=f"Remates Fuera / Salvados ({max(0, rem_l - gol_l)})",
    )

    plt.title(
        f"MAPA TÁCTICO DE REMATES DE {equipo_local.upper()}",
        color="white",
        fontsize=10,
        weight="bold",
        pad=12,
    )
    plt.xlim(-5, 105)
    plt.ylim(50, 105)
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
    fig, ax = plt.subplots(figsize=(8, 3.2))
    fig.patch.set_facecolor("#0D0D0D")
    ax.set_facecolor("#0D0D0D")

    tercios = ["Tercio Defensivo", "Tercio Medio", "Tercio Ofensivo"]
    pases_totales = [29, 30, 28]
    pases_exitosos = [16, 24, 14]
    porcentajes = [55, 80, 50]

    y_pos = np.arange(len(tercios))

    ax.barh(
        y_pos,
        pases_totales,
        align="center",
        color="#222222",
        edgecolor="#FF5500",
        height=0.42,
        label="Pases Intentados",
    )
    ax.barh(
        y_pos,
        pases_exitosos,
        align="center",
        color="#FF5500",
        height=0.42,
        label="Pases Completados",
    )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(tercios, color="white", fontsize=9, weight="bold")
    ax.invert_yaxis()
    ax.set_xlim(0, 42)
    ax.set_xlabel(
        f"Volumen y Precisión de Pase: {equipo_local}",
        color="#AAAAAA",
        fontsize=8,
    )
    ax.tick_params(colors="white")

    for i, (tot, eff, pct) in enumerate(
        zip(pases_totales, pases_exitosos, porcentajes)
    ):
        ax.text(
            tot + 1.2,
            i,
            f"{eff}/{tot} ({pct}%)",
            color="#FF5500",
            va="center",
            weight="bold",
            fontsize=9,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#333333")
    ax.spines["left"].set_color("#FF5500")

    plt.legend(
        loc="upper right",
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


# =====================================================================
# 🤖 MOTOR ACCUS-IA HÍBRIDO (REGEX + VISION)
# =====================================================================
def parse_hudl_stats_regex(texto_crudo):
    stats = {}
    txt_norm = re.sub(r"\s+", " ", texto_crudo)

    p_shots = re.search(r"(?:Shots|Remates|Disparos)\s+(\d+)", txt_norm, re.IGNORECASE)
    p_ontarget = re.search(r"(?:On Target|A Puerta|Al Arco)\s+(\d+)", txt_norm, re.IGNORECASE)
    p_crosses = re.search(r"(?:Crosses|Centros)\s+(\d+)", txt_norm, re.IGNORECASE)
    p_passes = re.search(r"(?:Successful Passes|Pases Exitosos|Pases Completados)\s+(\d+)", txt_norm, re.IGNORECASE)
    p_tot_passes = re.search(r"(?:Passes|Pases Totales|Pases Intentados)\s+(\d+)", txt_norm, re.IGNORECASE)
    p_goles = re.search(r"(?:Goals|Goles)\s+(\d+)", txt_norm, re.IGNORECASE)
    p_asist = re.search(r"(?:Assists|Asistencias)\s+(\d+)", txt_norm, re.IGNORECASE)

    if p_shots: stats["remates_totales"] = int(p_shots.group(1))
    if p_ontarget: stats["remates_a_puerta"] = int(p_ontarget.group(1))
    if p_crosses: stats["centros"] = int(p_crosses.group(1))
    if p_passes: stats["pases_completados"] = int(p_passes.group(1))
    if p_tot_passes: stats["pases_intentados"] = int(p_tot_passes.group(1))
    if p_goles: stats["goles"] = int(p_goles.group(1))
    if p_asist: stats["asistencias"] = int(p_asist.group(1))

    return stats


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
        1. Extrae con precisión las estadísticas numéricas colectivas del encuentro.
        2. Realiza un análisis táctico profesional basado estricta y únicamente en los datos numéricos encontrados.

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
            "focos_entrenamiento": ["Foco entrenamiento 1", "Foco entrenamiento 2", "Foco entrenamiento 3"]
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


def extraer_datos_jugador_gemini(files_jugador):
    try:
        if "GEMINI_API_KEY" not in st.secrets:
            st.error("⚠️ No se encontró GEMINI_API_KEY.")
            return None

        texto_acumulado = ""
        if pdfplumber:
            for file_obj in files_jugador:
                file_bytes = file_obj.getvalue()
                try:
                    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                        for page in pdf.pages:
                            texto_acumulado += (page.extract_text() or "") + "\n"
                except Exception:
                    pass

        stats_regex = parse_hudl_stats_regex(texto_acumulado)

        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)

        contents = []
        for file_obj in files_jugador:
            file_bytes = file_obj.getvalue()
            contents.append(
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type="application/pdf",
                )
            )

        prompt = """
        Actúa como especialista en analítica de datos deportivos de AccuSport Colombia.
        Analiza VISUALMENTE las páginas de los reportes PDF adjuntos (reportes de tagueo de Hudl/Focus).

        MAPPING BILINGÜE OBLIGATORIO DE MÉTRICAS (HUDL / FOCUS):
        - "Goals" o "Goles" -> extrae en "goles"
        - "Assists" o "Asistencias" -> extrae en "asistencias"
        - "Shots" o "Remates Totales" -> extrae en "remates_totales"
        - "On Target" o "A Puerta" -> extrae el número entero de disparos a puerta en "remates_a_puerta"
        - "Crosses" o "Centros" -> extrae en "centros"
        - "Passes" o "Pases" -> extrae el total intentado en "pases_intentados"
        - "Successful Passes" o "Pases Exitosos" -> extrae el número de pases completados en "pases_completados"
        - "Recoveries" / "Tackles" / "Recuperaciones" -> extrae en "recuperaciones"
        - "Duels Won" / "Duelos Defensivos" -> extrae en "duelos_def_ganados"

        REGLAS CRÍTICAS:
        1. SUMA los valores numéricos de todas las páginas y archivos adjuntos si hay más de uno.
        2. Si ves "Passes: 10" y "Successful Passes: 6 (60%)", entonces "pases_intentados" = 10 y "pases_completados" = 6.
        3. Si ves "Crosses: 8", entonces "centros" = 8.
        4. "minutos": Pon 0 (se configurará manualmente por el usuario).

        Responde en formato JSON estricto con la siguiente estructura exacta:
        {
            "jugador": "Barrero",
            "dorsal": "13",
            "minutos": 0,
            "participaciones": 51,
            "goles": 0,
            "asistencias": 0,
            "remates_totales": 2,
            "remates_a_puerta": 0,
            "centros": 8,
            "pases_intentados": 10,
            "pases_completados": 6,
            "recuperaciones": 0,
            "duelos_def_ganados": 0
        }
        """
        contents.append(prompt)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        res_json = json.loads(response.text)

        for k, v in stats_regex.items():
            if v > 0:
                res_json[k] = v

        return res_json
    except Exception as e:
        st.error(f"❌ Error al procesar reporte del jugador con AccusIA: {e}")
        return None


def generar_scouting_cualitativo_jugador(data_jugador):
    try:
        if "GEMINI_API_KEY" not in st.secrets:
            return {
                "puntos_fuertes": [
                    "Buen volumen de participación ofensiva",
                    "Constante búsqueda de asociación en ataque",
                ],
                "aspectos_mejorar": [
                    "Incrementar efectividad en la definición",
                    "Optimizar perfilamiento en duelo individual",
                ],
                "conclusion_scouting": "Jugador dinámico con constante vocación ofensiva y aporte en la construcción de juego.",
            }

        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)

        prompt = f"""
        Actúa como Senior Scout y Analista de Rendimiento Individual para AccuSport Colombia.
        Elabora un diagnóstico técnico del jugador {data_jugador.get('Jugador', data_jugador.get('jugador', 'Jugador'))} con base en sus métricas reales de partido:
        - Participaciones Totales: {data_jugador.get('Participaciones_Totales', data_jugador.get('participaciones', 0))}
        - Goles: {data_jugador.get('Goles', data_jugador.get('goles', 0))}, Asistencias: {data_jugador.get('Asistencias', data_jugador.get('asistencias', 0))}
        - Remates Totales: {data_jugador.get('Remates_Totales', data_jugador.get('remates_totales', 0))} (A Puerta: {data_jugador.get('Remates_A_Puerta', data_jugador.get('remates_a_puerta', 0))})
        - Pases Completados: {data_jugador.get('Pases_Completados', data_jugador.get('pases_completados', 0))} de {data_jugador.get('Pases_Intentados', data_jugador.get('pases_intentados', 0))}
        - Centros al Área: {data_jugador.get('Centros', data_jugador.get('centros', 0))}

        REGLA DE ORO: Analiza SOLAMENTE los números provistos arriba. No inventes falencias que contradigan las métricas reales.

        Responde en JSON estricto:
        {{
            "puntos_fuertes": ["Fortaleza 1", "Fortaleza 2"],
            "aspectos_mejorar": ["Aspecto a trabajar 1", "Aspecto a trabajar 2"],
            "conclusion_scouting": "Resumen técnico de 2-3 líneas sobre el rol y desempeño del jugador."
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
        return json.loads(response.text)
    except Exception:
        return {
            "puntos_fuertes": [
                "Intensidad y alto volumen de participación",
                "Compromiso directo en la gestación ofensiva",
            ],
            "aspectos_mejorar": [
                "Efectividad final en disparo a puerta",
                "Consistencia en la toma de decisiones bajo presión",
            ],
            "conclusion_scouting": "Rendimiento sumamente activo que genera permanente sensación de peligro y continuidad en ataque.",
        }


def procesar_e_ingresar_jugador_db(
    data_jugador, fecha, equipo, rival, mins_override=None
):
    client = obtener_cliente_sheets()
    if not client:
        return False

    try:
        sheet = client.open_by_key(CONFIG_SHEET_ID)

        ws_hist = sheet.worksheet("HISTORICO_PARTIDOS")
        id_partido = f"MATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        nom = data_jugador.get("jugador", "Desconocido").strip()
        dor = str(data_jugador.get("dorsal", "0")).strip()

        mins = (
            int(mins_override)
            if mins_override is not None
            else int(data_jugador.get("minutos", 0))
        )
        part = int(data_jugador.get("participaciones", 0))
        gol = int(data_jugador.get("goles", 0))
        asis = int(data_jugador.get("asistencias", 0))
        rem_t = int(data_jugador.get("remates_totales", 0))
        rem_p = int(data_jugador.get("remates_a_puerta", 0))
        cent = int(data_jugador.get("centros", 0))
        pas_i = int(data_jugador.get("pases_intentados", 0))
        pas_c = int(data_jugador.get("pases_completados", 0))
        rec = int(data_jugador.get("recuperaciones", 0))
        duel = int(data_jugador.get("duelos_def_ganados", 0))

        foto_url = ""
        try:
            ws_acum = sheet.worksheet("ACUMULADO_TEMPORADA")
            records_acum = ws_acum.get_all_records()
            for r in records_acum:
                match_nom = (
                    str(r.get("Jugador", "")).strip().lower() == nom.lower()
                )
                match_dor = str(r.get("Dorsal", "")).strip() == dor
                match_eq = (
                    str(r.get("Equipo", "")).strip().lower()
                    == equipo.strip().lower()
                )

                if (match_nom or (match_dor and match_eq)) and r.get("Foto_URL"):
                    foto_url = r.get("Foto_URL", "")
                    break
        except Exception:
            pass

        fila_hist = [
            id_partido,
            fecha,
            equipo,
            rival,
            nom,
            dor,
            mins,
            part,
            gol,
            asis,
            rem_t,
            rem_p,
            cent,
            pas_i,
            pas_c,
            rec,
            duel,
            foto_url,
        ]
        ws_hist.append_row(fila_hist)

        ws_acum = sheet.worksheet("ACUMULADO_TEMPORADA")
        df_hist = pd.DataFrame(ws_hist.get_all_records())

        if not df_hist.empty and "Jugador" in df_hist.columns:
            df_hist["Jugador"] = df_hist["Jugador"].astype(str).str.strip()
            df_jug = df_hist[
                df_hist["Jugador"].str.lower() == nom.lower()
            ].copy()

            if df_jug.empty and "Dorsal" in df_hist.columns:
                df_jug = df_hist[
                    (df_hist["Dorsal"].astype(str).str.strip() == dor)
                    & (
                        df_hist["Equipo"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        == equipo.strip().lower()
                    )
                ].copy()

            pj = len(df_jug)
            m_tot = int(
                pd.to_numeric(
                    df_jug["Minutos_Jugados"], errors="coerce"
                ).sum()
            )
            g_tot = int(pd.to_numeric(df_jug["Goles"], errors="coerce").sum())
            a_tot = int(
                pd.to_numeric(df_jug["Asistencias"], errors="coerce").sum()
            )
            rt_tot = int(
                pd.to_numeric(df_jug["Remates_Totales"], errors="coerce").sum()
            )
            rp_tot = int(
                pd.to_numeric(df_jug["Remates_A_Puerta"], errors="coerce").sum()
            )
            efec_r = f"{round((rp_tot / max(1, rt_tot)) * 100, 1)}%"
            pc_tot = int(
                pd.to_numeric(
                    df_jug["Pases_Completados"], errors="coerce"
                ).sum()
            )
            pi_tot = int(
                pd.to_numeric(
                    df_jug["Pases_Intentados"], errors="coerce"
                ).sum()
            )
            prec_p = f"{round((pc_tot / max(1, pi_tot)) * 100, 1)}%"
            rec_tot = int(
                pd.to_numeric(df_jug["Recuperaciones"], errors="coerce").sum()
            )

            cell_found = None
            try:
                records = ws_acum.get_all_records()
                for idx, r in enumerate(records, start=2):
                    r_nom = str(r.get("Jugador", "")).strip().lower()
                    r_dor = str(r.get("Dorsal", "")).strip()
                    r_eq = str(r.get("Equipo", "")).strip().lower()

                    if r_nom == nom.lower() or (
                        r_dor == dor and r_eq == equipo.strip().lower()
                    ):
                        cell_found = idx
                        break
            except Exception:
                cell_found = None

            fila_acum = [
                nom,
                equipo,
                dor,
                pj,
                m_tot,
                g_tot,
                a_tot,
                rt_tot,
                rp_tot,
                efec_r,
                pc_tot,
                prec_p,
                rec_tot,
                foto_url,
            ]

            if cell_found:
                ws_acum.update(f"A{cell_found}:N{cell_found}", [fila_acum])
            else:
                ws_acum.append_row(fila_acum)

        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ Error al actualizar Google Sheets: {e}")
        return False


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
        "|": "-",
        "рего": "pero",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
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
# 📑 GENERADOR FPDF CON MARCA EN EL PIE DE PÁGINA
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


def generar_pdf_6_paginas(
    data, buf_radar=None, buf_shot=None, buf_pases=None, buf_p2_resumen=None
):
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

    # PÁGINA 2: ANÁLISIS GENERAL CON GRÁFICO RESUMEN INTEGRADO
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Análisis general del partido", ln=True)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, f"{eq_loc} vs {eq_vis} - {fec_str}", ln=True)
    pdf.ln(2)

    pdf.set_fill_color(*DARK)
    pdf.rect(12, pdf.get_y(), 186, 18, "F")
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*WHITE)
    pdf.set_x(12)
    pdf.cell(
        0,
        12,
        f"{eq_loc}  {data.get('goles_local', 4)} - {data.get('goles_visita', 2)}  {eq_vis}",
        ln=True,
        align="C",
    )
    pdf.ln(8)

    pdf.set_fill_color(*GRAY_BG)
    y_cards = pdf.get_y()
    w_card = 43

    pdf.rect(12, y_cards, w_card, 16, "F")
    pdf.rect(59, y_cards, w_card, 16, "F")
    pdf.rect(106, y_cards, w_card, 16, "F")
    pdf.rect(153, y_cards, 45, 16, "F")

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*TEXT_DARK)

    pdf.set_y(y_cards + 2)
    pdf.set_x(12)
    pdf.cell(w_card, 4, "POSESIÓN", align="C")
    pdf.set_x(59)
    pdf.cell(w_card, 4, "REMATES", align="C")
    pdf.set_x(106)
    pdf.cell(w_card, 4, "GOLES", align="C")
    pdf.set_x(153)
    pdf.cell(45, 4, "PRECISIÓN PASE", align="C", ln=True)

    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*ORANGE)
    pdf.set_x(12)
    pdf.cell(w_card, 6, f"{data.get('pos_local', '45.3%')}", align="C")
    pdf.set_x(59)
    pdf.cell(w_card, 6, f"{data.get('remates_local', '20')}", align="C")
    pdf.set_x(106)
    pdf.cell(w_card, 6, f"{data.get('goles_local', '4')}", align="C")
    pdf.set_x(153)
    pdf.cell(
        45, 6, f"{data.get('precision_pase_local', '60%')}", align="C", ln=True
    )
    pdf.ln(8)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 5, "Lectura Táctica General:", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(
        0, 4.5, sanitizar_texto(data.get("lectura_general", "Sin datos."))
    )
    pdf.ln(4)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(0, 5, "Conclusiones Clave del Encuentro:", ln=True)
    pdf.set_font("Helvetica", "", 9.5)
    for conc in data.get("conclusiones", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 4.5, sanitizar_texto(f"- {conc}"))
        pdf.ln(1)

    if buf_p2_resumen:
        try:
            pdf.ln(2)
            pdf.image(buf_p2_resumen, x=15, y=pdf.get_y(), w=180)
            pdf.set_x(12)
        except Exception:
            pass

    # PÁGINA 3: COMPARATIVO Y RADAR
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
    pdf.ln(4)

    if buf_radar:
        try:
            pdf.image(buf_radar, x=38, y=42, w=134)
            pdf.set_y(185)
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
        0, 6, f"Mapa de remates de {eq_loc} en campo rival", ln=True
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

    # PÁGINA 5: PASE Y CIRCULACIÓN NATIVA POR TERCIOS
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Posesión y circulación por tercios", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(
        0, 6, f"Desempeño de pases y construcción de {eq_loc}", ln=True
    )
    pdf.ln(5)

    if buf_pases:
        try:
            pdf.image(buf_pases, x=15, y=45, w=180)
            pdf.set_y(150)
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

    # PÁGINA 6: CONCLUSIONES Y NOTA INSTITUCIONAL DE CIERRE
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Conclusiones y seguimiento", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 6, "Síntesis técnica e hitos clave", ln=True)
    pdf.ln(6)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Aspectos a conservar:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for asp in data.get("aspectos_conservar", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"- {asp}"))
        pdf.ln(1)

    pdf.ln(2)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Aspectos a corregir:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for asp in data.get("aspectos_corregir", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"- {asp}"))
        pdf.ln(1)

    pdf.ln(2)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Focos sugeridos para entrenamiento:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for foc in data.get("focos_entrenamiento", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"- {foc}"))
        pdf.ln(1)

    pdf.ln(10)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        4.5,
        sanitizar_texto(
            "Este análisis táctico fue elaborado por el equipo de analistas de video de AccuSport Colombia con el soporte tecnológico de AccusIA."
        ),
        align="C",
    )

    return bytes(pdf.output())


# =====================================================================
# 🎴 GENERADOR PDF: FICHA INDIVIDUAL EXPANDIDA (2 PÁGINAS)
# =====================================================================
def generar_pdf_ficha_partido_jugador(data_jug, buf_mapa_calor=None):
    pdf = PDFReporteFocus()
    pdf.set_margins(12, 12, 12)

    ORANGE = (255, 85, 0)
    DARK = (13, 13, 13)
    WHITE = (255, 255, 255)
    GRAY_BG = (245, 245, 247)
    TEXT_DARK = (30, 30, 30)

    # --- PÁGINA 1: FICHA DE PARTIDO Y METRICAS ---
    pdf.add_page()
    pdf.set_fill_color(*DARK)
    pdf.rect(12, 12, 186, 35, "F")

    foto_b64 = data_jug.get("Foto_URL", "")
    nom_jug = data_jug.get("Jugador", data_jug.get("jugador", "Jugador")).strip()
    dor_jug = data_jug.get("Dorsal", data_jug.get("dorsal", "0")).strip()

    if not foto_b64:
        try:
            df_acum_temp = obtener_datos_pestana("ACUMULADO_TEMPORADA")
            if not df_acum_temp.empty and "Jugador" in df_acum_temp.columns:
                match_r = df_acum_temp[
                    df_acum_temp["Jugador"].astype(str).str.strip().str.lower()
                    == nom_jug.lower()
                ]
                if not match_r.empty:
                    foto_b64 = match_r.iloc[0].get("Foto_URL", "")
        except Exception:
            pass

    if foto_b64 and "base64," in foto_b64:
        try:
            raw_b64 = foto_b64.split("base64,")[1]
            img_data = base64.b64decode(raw_b64)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".jpg"
            ) as tmp_img:
                tmp_img.write(img_data)
                tmp_img_path = tmp_img.name
            pdf.image(tmp_img_path, x=15, y=14, w=30, h=30)
        except Exception:
            pdf.rect(15, 14, 30, 30, "D")
    else:
        pdf.set_fill_color(30, 30, 30)
        pdf.rect(15, 14, 30, 30, "F")

    pdf.set_xy(50, 16)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 8, sanitizar_texto(f"#{dor_jug} {nom_jug}"), ln=True)

    pdf.set_x(50)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.cell(
        0,
        5,
        sanitizar_texto(
            f"Equipo: {data_jug.get('Equipo', 'N/A')}  |  Rival: {data_jug.get('Rival', 'N/A')}"
        ),
        ln=True,
    )

    pdf.set_x(50)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(
        0,
        5,
        sanitizar_texto(
            f"Fecha: {data_jug.get('Fecha', 'N/A')}  |  Reporte de Partido Individual"
        ),
        ln=True,
    )

    pdf.ln(18)

    pdf.set_fill_color(*GRAY_BG)
    y_cards = pdf.get_y()
    w_card = 43

    pdf.rect(12, y_cards, w_card, 18, "F")
    pdf.rect(59, y_cards, w_card, 18, "F")
    pdf.rect(106, y_cards, w_card, 18, "F")
    pdf.rect(153, y_cards, 45, 18, "F")

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*TEXT_DARK)

    pdf.set_y(y_cards + 2)
    pdf.set_x(12)
    pdf.cell(w_card, 4, "PARTICIPACIONES", align="C")
    pdf.set_x(59)
    pdf.cell(w_card, 4, "MINUTOS JUGADOS", align="C")
    pdf.set_x(106)
    pdf.cell(w_card, 4, "REMATES (A PUERTA)", align="C")
    pdf.set_x(153)
    pdf.cell(45, 4, "PASES COMPLETADOS", align="C", ln=True)

    mins_raw = data_jug.get("Minutos_Jugados", data_jug.get("minutos", 0))
    mins_val = f"{mins_raw} min" if int(mins_raw or 0) > 0 else "--"

    pas_c = data_jug.get("Pases_Completados", data_jug.get("pases_completados", 0))
    pas_i = data_jug.get("Pases_Intentados", data_jug.get("pases_intentados", 0))

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*ORANGE)
    pdf.set_x(12)
    pdf.cell(
        w_card,
        7,
        f"{data_jug.get('Participaciones_Totales', data_jug.get('participaciones', 0))}",
        align="C",
    )
    pdf.set_x(59)
    pdf.cell(w_card, 7, mins_val, align="C")
    pdf.set_x(106)
    pdf.cell(
        w_card,
        7,
        f"{data_jug.get('Remates_Totales', data_jug.get('remates_totales', 0))} ({data_jug.get('Remates_A_Puerta', data_jug.get('remates_a_puerta', 0))})",
        align="C",
    )
    pdf.set_x(153)
    pdf.cell(
        45,
        7,
        f"{pas_c}/{pas_i}",
        align="C",
        ln=True,
    )

    pdf.ln(10)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, "Acciones Totales en el Partido", ln=True)
    pdf.ln(2)

    stats_tabla = [
        (
            "Goles Concretados",
            str(data_jug.get("Goles", data_jug.get("goles", 0))),
        ),
        (
            "Asistencias de Gol",
            str(data_jug.get("Asistencias", data_jug.get("asistencias", 0))),
        ),
        (
            "Centros al Área",
            str(data_jug.get("Centros", data_jug.get("centros", 0))),
        ),
        (
            "Recuperaciones de Balón",
            str(
                data_jug.get(
                    "Recuperaciones", data_jug.get("recuperaciones", 0)
                )
            ),
        ),
        (
            "Duelos Defensivos Ganados",
            str(
                data_jug.get(
                    "Duelos_Def_Ganados", data_jug.get("duelos_def_ganados", 0)
                )
            ),
        ),
    ]

    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    pdf.set_x(12)
    pdf.cell(130, 5, " Métrica Evaluada", 1, 0, "L", fill=True)
    pdf.cell(56, 5, " Total Registrado", 1, 1, "C", fill=True)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*TEXT_DARK)
    for var, val in stats_tabla:
        pdf.set_x(12)
        pdf.cell(130, 5, f" {sanitizar_texto(var)}", 1, 0, "L")
        pdf.cell(56, 5, f" {sanitizar_texto(val)}", 1, 1, "C")

    pdf.ln(6)

    if buf_mapa_calor:
        try:
            curr_y = pdf.get_y()
            pdf.image(buf_mapa_calor, x=30, y=curr_y, w=150)
            pdf.set_y(curr_y + 85)
        except Exception:
            pass

    # --- PÁGINA 2: ANÁLISIS CUALITATIVO Y SCOUTING ---
    pdf.add_page()
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 10, "Diagnóstico Técnico y Scouting (AccusIA)", ln=True)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(
        0, 6, f"Evaluación de rendimiento para {nom_jug}", ln=True
    )
    pdf.ln(6)

    scout_data = generar_scouting_cualitativo_jugador(data_jug)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Puntos Fuertes Destacados:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for pf in scout_data.get("puntos_fuertes", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"- {pf}"))
        pdf.ln(1)

    pdf.ln(2)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Aspectos Clave a Desarrollar:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for am in scout_data.get("aspectos_mejorar", []):
        pdf.set_x(12)
        pdf.multi_cell(0, 5, sanitizar_texto(f"- {am}"))
        pdf.ln(1)

    pdf.ln(4)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Conclusión General del Analista:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(12)
    pdf.multi_cell(
        0,
        5,
        sanitizar_texto(
            scout_data.get("conclusion_scouting", "Jugador en desarrollo.")
        ),
    )

    pdf.ln(12)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        4.5,
        sanitizar_texto(
            "Reporte individual generado con la tecnología de seguimiento de partidos Focus by AccuSport."
        ),
        align="C",
    )

    return bytes(pdf.output())


# =====================================================================
# 📚 GENERADOR PDF: DOSSIER DE TEMPORADA (HISTÓRICO)
# =====================================================================
def generar_pdf_dossier_temporada(data_acum, df_historico):
    pdf = PDFReporteFocus()
    pdf.add_page()
    pdf.set_margins(12, 12, 12)

    ORANGE = (255, 85, 0)
    DARK = (13, 13, 13)
    WHITE = (255, 255, 255)
    GRAY_BG = (245, 245, 247)
    TEXT_DARK = (30, 30, 30)

    pdf.set_fill_color(*DARK)
    pdf.rect(12, 12, 186, 35, "F")

    foto_b64 = data_acum.get("Foto_URL", "")
    if foto_b64 and "base64," in foto_b64:
        try:
            raw_b64 = foto_b64.split("base64,")[1]
            img_data = base64.b64decode(raw_b64)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".jpg"
            ) as tmp_img:
                tmp_img.write(img_data)
                tmp_img_path = tmp_img.name
            pdf.image(tmp_img_path, x=15, y=14, w=30, h=30)
        except Exception:
            pdf.rect(15, 14, 30, 30, "D")

    pdf.set_xy(50, 16)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*ORANGE)
    pdf.cell(
        0,
        8,
        sanitizar_texto(
            f"DOSSIER: #{data_acum.get('Dorsal', '0')} {data_acum.get('Jugador', 'Jugador')}"
        ),
        ln=True,
    )

    pdf.set_x(50)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.cell(
        0,
        5,
        sanitizar_texto(f"Equipo: {data_acum.get('Equipo', 'N/A')}"),
        ln=True,
    )

    pdf.set_x(50)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(0, 5, "Consolidado Acumulado de Temporada", ln=True)

    pdf.ln(18)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, "Totales Acumulados de Carrera", ln=True)
    pdf.ln(2)

    stats_acum = [
        ("Partidos Jugados (MP)", str(data_acum.get("Partidos_Jugados", 0))),
        ("Minutos Acumulados", str(data_acum.get("Minutos_Totales", 0))),
        ("Goles Totales", str(data_acum.get("Goles_Totales", 0))),
        ("Asistencias Totales", str(data_acum.get("Asistencias_Totales", 0))),
        (
            "Efectividad de Remate (%)",
            str(data_acum.get("Efectividad_Remate_%", "0%")),
        ),
        ("Precision de Pase (%)", str(data_acum.get("Precision_Pase_%", "0%"))),
    ]

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    pdf.set_x(12)
    pdf.cell(130, 6, " Métrica de Carrera / Temporada", 1, 0, "L", fill=True)
    pdf.cell(56, 6, " Acumulado", 1, 1, "C", fill=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*TEXT_DARK)
    for var, val in stats_acum:
        pdf.set_x(12)
        pdf.cell(130, 6, f" {sanitizar_texto(var)}", 1, 0, "L")
        pdf.cell(56, 6, f" {sanitizar_texto(val)}", 1, 1, "C")

    pdf.ln(8)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, "Historial de Encuentros Disputados", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    pdf.set_x(12)
    pdf.cell(25, 6, "Fecha", 1, 0, "C", fill=True)
    pdf.cell(45, 6, "Rival", 1, 0, "L", fill=True)
    pdf.cell(30, 6, "Part. Totales", 1, 0, "C", fill=True)
    pdf.cell(25, 6, "Goles", 1, 0, "C", fill=True)
    pdf.cell(30, 6, "Remates (P)", 1, 0, "C", fill=True)
    pdf.cell(31, 6, "Pases (C)", 1, 1, "C", fill=True)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*TEXT_DARK)

    if not df_historico.empty:
        for idx, row in df_historico.iterrows():
            pdf.set_x(12)
            pdf.cell(
                25, 5, sanitizar_texto(str(row.get("Fecha", ""))), 1, 0, "C"
            )
            pdf.cell(
                45, 5, sanitizar_texto(str(row.get("Rival", ""))), 1, 0, "L"
            )
            pdf.cell(
                30,
                5,
                sanitizar_texto(str(row.get("Participaciones_Totales", 0))),
                1,
                0,
                "C",
            )
            pdf.cell(
                25, 5, sanitizar_texto(str(row.get("Goles", 0))), 1, 0, "C"
            )
            pdf.cell(
                30,
                5,
                f"{row.get('Remates_Totales',0)} ({row.get('Remates_A_Puerta',0)})",
                1,
                0,
                "C",
            )
            pdf.cell(
                31,
                5,
                f"{row.get('Pases_Completados',0)}/{row.get('Pases_Intentados',0)}",
                1,
                1,
                "C",
            )

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
                    rival = obtener_valor_columna(
                        row,
                        [
                            "Rival",
                            "rival",
                            "RIVAL",
                            "Equipo Rival",
                            "Contrincante",
                            "Rival/Torneo",
                        ],
                        "Rival Desconocido",
                    )
                    fecha_str = obtener_valor_columna(
                        row, ["Fecha", "fecha", "FECHA", "Fecha_Partido"], "S/F"
                    )
                    link_drive = obtener_valor_columna(
                        row,
                        ["Link", "link", "LINK", "Url", "URL", "Drive", "Link_Drive"],
                        "",
                    )

                    with st.container(border=True):
                        st.markdown(f"## 🆚 {rival}")
                        st.markdown(f"📅 **Fecha:** {fecha_str}")

                        # 🎥 REPRODUCTOR DE VIDEO EMBEBIDO
                        renderizar_reproductor_video(link_drive)

                        # 📥 BOTÓN DE DESCARGA / ACCESO DIRECTO
                        if link_drive and "http" in link_drive:
                            st.write("")
                            st.link_button(
                                "📥 ABRIR EN GOOGLE DRIVE / DESCARGAR REPORTE Y VIDEO",
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
                "📄 Generar Reporte Colectivo PDF (Tagueo CSV / PDF)",
                "👤 Ingestar Tagueo Individual de Jugador (PDF)",
                "📑 Exportar PDF Individual de Jugador",
                "📸 Cargar Foto de Jugador (Perfil / Scouting)",
                "🛠️ Inicializar Base de Datos de Jugadores",
                "📈 Tablero de Control Financiero (Balance)",
                "🛡️ 1. Añadir Equipo (GLOBAL)",
                "👤 2. Agregar Jugador / Papá a un Equipo",
                "📆 3. Programar Grabación / Subir Video + CALENDAR",
                "💰 4. Registrar Cobro Mensual (Clubes VIP)",
                "👁️ Auditar Hojas de Excel en Vivo",
            ],
        )
        st.write("---")

        if opcion_admin == "📄 Generar Reporte Colectivo PDF (Tagueo CSV / PDF)":
            st.write("#### 📊 Generador de Reportes Colectivos Focus")

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
                "🚀 GENERAR Y DESCARGAR PDF REPORTE FOCUS",
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
                buf_p2_resumen = generar_grafico_resumen_pagina2(
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
                    data_pdf, buf_radar, buf_shot, buf_pases, buf_p2_resumen
                )
                st.download_button(
                    label="📥 DESCARGAR REPORTE FINAL EN PDF",
                    data=pdf_bytes,
                    file_name=f"Reporte_{eq_local}_vs_{eq_visita}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

        elif opcion_admin == "👤 Ingestar Tagueo Individual de Jugador (PDF)":
            st.write("#### 📥 Ingesta Automática de Tagueo Individual")
            st.write(
                "Sube los archivos PDF del tagueo de un jugador (puedes seleccionar varios a la vez, ej. `Barrero.pdf` y `Barrero 2.pdf`). AccusIA inspeccionará visualmente las páginas y actualizará la base de datos."
            )

            files_jugador = st.file_uploader(
                "Selecciona los reportes PDF del jugador:",
                type=["pdf"],
                accept_multiple_files=True,
            )

            col_j1, col_j2, col_j3, col_j4 = st.columns([2, 2, 2, 1.5])
            with col_j1:
                eq_j = st.text_input("Equipo / Categoría:", value="Fortaleza 2017 B")
            with col_j2:
                riv_j = st.text_input("Rival del Encuentro:", value="Aurinegro")
            with col_j3:
                fec_j = st.text_input("Fecha:", value="12/09/2026")
            with col_j4:
                mins_manual = st.number_input("Min. Jugados:", value=60, step=5)

            if st.button("🚀 INGESTAR METRICAS A GOOGLE SHEETS", use_container_width=True):
                if files_jugador:
                    with st.spinner("AccusIA está analizando las métricas del reporte..."):
                        json_data = extraer_datos_jugador_gemini(files_jugador)

                        if json_data:
                            exito = procesar_e_ingresar_jugador_db(
                                json_data, fec_j, eq_j, riv_j, mins_override=mins_manual
                            )
                            if exito:
                                st.success(
                                    f"✨ ¡Datos de **{json_data.get('jugador', 'Jugador')}** ingresados e integrados correctamente en Google Sheets!"
                                )
                                st.json(json_data)
                else:
                    st.warning("⚠️ Sube al menos un reporte PDF del jugador.")

        elif opcion_admin == "📑 Exportar PDF Individual de Jugador":
            st.write("#### 📄 Exportador de Reportes por Jugador")

            df_acum = obtener_datos_pestana("ACUMULADO_TEMPORADA")
            if not df_acum.empty and "Jugador" in df_acum.columns:
                lista_jug = df_acum["Jugador"].unique().tolist()
                jug_sel = st.selectbox("Selecciona un Jugador:", lista_jug)

                tipo_rep = st.radio(
                    "Tipo de Reporte a Generar:",
                    ["Ficha del Último Partido", "Dossier Consolidado de Temporada"],
                )

                st.write("---")
                st.write("🔥 **Configuración del Mapa de Calor Táctico (3x3)**")
                st.caption(
                    "Ajusta la intensidad de participación del jugador por zona (0 = Sin presencia, 10 = Máxima actividad):"
                )

                c_d1, c_d2, c_d3 = st.columns(3)
                with c_d1:
                    def_izq = st.slider("Defensivo Izquierdo", 0, 10, 2)
                with c_d2:
                    def_cen = st.slider("Defensivo Centro", 0, 10, 3)
                with c_d3:
                    def_der = st.slider("Defensivo Derecho", 0, 10, 2)

                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1:
                    med_izq = st.slider("Medio Izquierdo", 0, 10, 5)
                with c_m2:
                    med_cen = st.slider("Medio Centro", 0, 10, 8)
                with c_m3:
                    med_der = st.slider("Medio Derecho", 0, 10, 6)

                c_a1, c_a2, c_a3 = st.columns(3)
                with c_a1:
                    atk_izq = st.slider("Ofensivo Izquierdo", 0, 10, 7)
                with c_a2:
                    atk_cen = st.slider("Ofensivo Centro", 0, 10, 9)
                with c_a3:
                    atk_der = st.slider("Ofensivo Derecho", 0, 10, 4)

                matriz_3x3 = np.array(
                    [
                        [def_izq, def_cen, def_der],
                        [med_izq, med_cen, med_der],
                        [atk_izq, atk_cen, atk_der],
                    ]
                )

                st.write("---")
                if st.button("🚀 GENERAR REPORTE EN PDF", use_container_width=True):
                    df_hist = obtener_datos_pestana("HISTORICO_PARTIDOS")
                    row_acum = df_acum[df_acum["Jugador"] == jug_sel].iloc[0].to_dict()
                    df_jug_hist = df_hist[df_hist["Jugador"] == jug_sel]

                    buf_heat = generar_mapa_calor_manual(matriz_3x3, jug_sel)

                    if tipo_rep == "Ficha del Último Partido":
                        if not df_jug_hist.empty:
                            last_match = df_jug_hist.iloc[-1].to_dict()
                            pdf_bytes = generar_pdf_ficha_partido_jugador(
                                last_match, buf_heat
                            )
                            st.download_button(
                                label="📥 DESCARGAR FICHA DE PARTIDO PDF",
                                data=pdf_bytes,
                                file_name=f"Partido_{jug_sel.replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )
                        else:
                            st.warning("No hay partidos registrados para este jugador.")
                    else:
                        pdf_bytes = generar_pdf_dossier_temporada(
                            row_acum, df_jug_hist
                        )
                        st.download_button(
                            label="📥 DESCARGAR DOSSIER ACUMULADO PDF",
                            data=pdf_bytes,
                            file_name=f"Dossier_{jug_sel.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
            else:
                st.info("ℹ️ Aún no hay jugadores registrados en la pestaña `ACUMULADO_TEMPORADA`.")

        elif opcion_admin == "📸 Cargar Foto de Jugador (Perfil / Scouting)":
            st.write("#### 📸 Cargar Fotografía Oficial de Perfil")
            st.write(
                "Sube la foto del jugador para vincularla directamente a Google Sheets."
            )

            foto_file = st.file_uploader(
                "Selecciona imagen del jugador (JPG / PNG):", type=["jpg", "jpeg", "png"]
            )

            col_f1, col_f2, col_f3 = st.columns([2, 1, 2])
            with col_f1:
                nom_foto = st.text_input("Nombre Completo del Jugador:")
            with col_f2:
                dor_foto = st.text_input("Dorsal / #:", value="13")
            with col_f3:
                eq_foto = st.text_input("Equipo / Categoría:", value="Fortaleza 2017 B")

            if st.button("💾 GUARDAR FOTO EN GOOGLE SHEETS", use_container_width=True):
                if foto_file and (nom_foto or dor_foto):
                    with st.spinner("Procesando y optimizando imagen..."):
                        b64_foto = procesar_foto_jugador_base64(foto_file)

                        if b64_foto:
                            client = obtener_cliente_sheets()
                            if client:
                                sheet = client.open_by_key(CONFIG_SHEET_ID)
                                ws_acum = sheet.worksheet("ACUMULADO_TEMPORADA")
                                try:
                                    records = ws_acum.get_all_records()
                                    target_row = None
                                    for idx, r in enumerate(records, start=2):
                                        r_nom = str(r.get("Jugador", "")).strip().lower()
                                        r_dor = str(r.get("Dorsal", "")).strip()
                                        r_eq = str(r.get("Equipo", "")).strip().lower()

                                        if (nom_foto and r_nom == nom_foto.strip().lower()) or (
                                            r_dor == dor_foto.strip() and r_eq == eq_foto.strip().lower()
                                        ):
                                            target_row = idx
                                            break

                                    if target_row:
                                        ws_acum.update_cell(target_row, 14, b64_foto)
                                        st.cache_data.clear()
                                        st.success(
                                            f"📸 Foto de **{nom_foto or ('#' + dor_foto)}** guardada correctamente en Google Sheets."
                                        )
                                    else:
                                        ws_acum.append_row([
                                            nom_foto.strip(),
                                            eq_foto.strip(),
                                            dor_foto.strip(),
                                            0, 0, 0, 0, 0, 0, "0%", 0, "0%", 0,
                                            b64_foto
                                        ])
                                        st.cache_data.clear()
                                        st.success(
                                            f"📸 Foto de **{nom_foto or ('#' + dor_foto)}** guardada e inicializada en la base de datos."
                                        )
                                except Exception as e:
                                    st.error(f"Error al actualizar celda: {e}")
                else:
                    st.warning("⚠️ Completa al menos el nombre o dorsal del jugador y selecciona una foto.")

        elif opcion_admin == "🛠️ Inicializar Base de Datos de Jugadores":
            st.write("#### 🛠️ Configuración de Estructura Individual")
            st.write(
                "Haz clic en el botón para verificar y crear automáticamente las pestañas de rendimiento individual en tu Google Sheet."
            )
            if st.button(
                "🚀 CREAR PESTAÑAS EN GOOGLE SHEETS", use_container_width=True
            ):
                inicializar_pestanas_jugadores()

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
                "Selecciona tabla:",
                [
                    "USUARIOS",
                    "PARTIDOS",
                    "HISTORICO_PARTIDOS",
                    "ACUMULADO_TEMPORADA",
                    "PAGOS_MENSUALES",
                ],
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
