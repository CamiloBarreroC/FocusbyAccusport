import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pandas as pd
import json
import re
from datetime import datetime, timedelta

# =====================================================================
# 📝 CONFIGURACIÓN INICIAL Y CENTRAL DE BRANDING (TUS LOGOS REALES)
# =====================================================================
CONFIG_SHEET_ID = "1wJi3hOQaeIDY--OcFOxsy-ycb-uyATDpqIGvMYvHPg4" 

# 🚀 ID MAESTRO DE TU GOOGLE CALENDAR FOCUS BY ACCUSPORT:
FOCUS_CALENDAR_DEFAULT = "c_3df55a2bb225d2a2d2054496334a5d7c7f9afca3f9099aea782b278fd9f45472@group.calendar.google.com"

# 🖼️ RUTAS EXACTAS DE LOS ARCHIVOS EN TU REPOSITORIO:
PATH_LOGO_FOCUS = "IMG-20260521-WA0004.jpg" 
PATH_LOGO_ACCUSPORT = "logonew.png"
# =====================================================================

st.set_page_config(page_title="Focus by Accusport", page_icon="⚽", layout="centered")

# 🎨 INYECCIÓN MAESTRA DE DISEÑO: BLACK & ORANGE CYBER-TECH
st.markdown("""
    <style>
    /* Fondo global negro absoluto */
    .stApp {
        background-color: #000000 !important;
        color: #f8fafc !important;
    }
    
    /* Personalización estética de tarjetas y contenedores */
    div[data-testid="stContainer"] {
        background-color: #0d0d0d !important;
        border: 1px solid #ff5500 !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 20px rgba(255, 85, 0, 0.15) !important;
        padding: 25px !important;
        margin-bottom: 20px !important;
    }
    
    /* Botones Premium Naranja Tech */
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
    
    /* Pestañas (Tabs) Estilo Cyberpunk */
    button[data-baseweb="tab"] {
        color: #888888 !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    button[aria-selected="true"] {
        color: #ff5500 !important;
        border-bottom-color: #ff5500 !important;
    }
    
    /* Ajuste de inputs y selectores oscuros */
    div[data-baseweb="select"], input {
        background-color: #0d0d0d !important;
        color: white !important;
        border: 1px solid #333333 !important;
    }
    
    /* Alertas info estilizadas en modo oscuro */
    .stAlert {
        background-color: #0d0d0d !important;
        color: #cbd5e1 !important;
        border-left: 5px solid #ff5500 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Inicialización segura de estados de sesión
if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False
if "nombre_admin" not in st.session_state:
    st.session_state["nombre_admin"] = ""
if "ver_galeria" not in st.session_state:
    st.session_state["ver_galeria"] = False
if "equipo_activo" not in st.session_state:
    st.session_state["equipo_activo"] = ""

@st.cache_resource
def conectar_google_services():
    try:
        secrets_gcp = st.secrets["gcp_service_account"]
        creds_dict = json.loads(secrets_gcp) if isinstance(secrets_gcp, str) else dict(secrets_gcp)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/calendar"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return creds
    except Exception as e:
        st.error(f"⚠️ Error crítico de conexión con Google Cloud: {e}")
        return None

def obtener_cliente_sheets():
    creds = conectar_google_services()
    return gspread.authorize(creds) if creds else None

def obtener_servicio_calendar():
    creds = conectar_google_services()
    return build('calendar', 'v3', credentials=creds) if creds else None

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
            start_time = datetime.combine(fecha_dt, datetime.min.time()) + timedelta(hours=8)
            end_time = start_time + timedelta(hours=2)
            event = {
                'summary': f"🎥 FOCUS: {equipo} vs {titulo}",
                'description': f'Grabación programada desde el panel Focus para la categoría {equipo}.',
                'start': {'dateTime': start_time.isoformat(), 'timeZone': 'America/Bogota'},
                'end': {'dateTime': end_time.isoformat(), 'timeZone': 'America/Bogota'},
            }
            cal_destino = FOCUS_CALENDAR_DEFAULT if calendar_id.lower() == "primary" else calendar_id
            service.events().insert(calendarId=cal_destino, body=event).execute()
            return True
        except Exception:
            return False
    return False

# =====================================================================
# 📐 CABECERA DE MARCA - SOLO LOGO FOCUS CENTRADO
# =====================================================================
_, col_logo_center, _ = st.columns([1, 4, 1])
with col_logo_center:
    try:
        st.image(PATH_LOGO_FOCUS, use_container_width=True)
    except Exception:
        st.markdown("<h1 style='text-align:center; margin:0; font-size:45px; letter-spacing:-1px; color:#ffffff;'>⚡ FO<span style='color:#ff5500;'>CUS</span></h1>", unsafe_allow_html=True)

st.write("---")

tab_padres, tab_admin = st.tabs(["📺 Focus Play (Familias)", "🔒 Control Administrativo"])

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
        st.write("Accesos a las transmisiones en HD, clips de goles o contenidos programados:")
        st.write("---")
        
        df_partidos = obtener_datos_pestana("PARTIDOS")
        if not df_partidos.empty and "Equipo" in df_partidos.columns:
            df_partidos["Equipo"] = df_partidos["Equipo"].astype(str).str.strip()
            partidos_filtrados = df_partidos[df_partidos["Equipo"] == equipo].copy()
            
            if not partidos_filtrados.empty:
                partidos_filtrados['Fecha_Datetime'] = pd.to_datetime(partidos_filtrados['Fecha'], errors='coerce', dayfirst=True)
                partidos_filtrados = partidos_filtrados.sort_values(by='Fecha_Datetime', ascending=False)
                
                for idx, row in partidos_filtrados.iterrows():
                    # DETECTOR UNIVERSAL DE DATOS
                    rival = "Rival Desconocido"
                    fecha_str = "S/F"
                    estatus = "procesando"
                    link_drive = ""

                    for col in row.index:
                        col_lower = str(col).lower()
                        col_val_str = str(row[col]).strip()

                        if "rival" in col_lower or "partido" in col_lower:
                            rival = col_val_str
                        elif "fecha" in col_lower:
                            fecha_str = col_val_str
                        elif "estatus" in col_lower or "estado" in col_lower or "grabacion" in col_lower:
                            estatus = col_val_str.lower()

                        if "link" in col_lower or "drive" in col_lower or "download" in col_lower or "enlace" in col_lower or "url" in col_lower:
                            if col_val_str.lower().startswith("http"):
                                link_drive = col_val_str
                    
                    if not link_drive:
                        for val in row.values:
                            val_str = str(val).strip()
                            if val_str.lower().startswith("http") or "drive.google.com" in val_str:
                                link_drive = val_str
                                break

                    es_fecha_futura = pd.notnull(row['Fecha_Datetime']) and row['Fecha_Datetime'].date() > datetime.now().date()
                    
                    texto_rival_limpio = rival.strip()
                    if texto_rival_limpio.lower().startswith("vs "):
                        texto_rival_limpio = texto_rival_limpio[3:].strip()
                    elif texto_rival_limpio.lower().startswith("vs"):
                        texto_rival_limpio = texto_rival_limpio[2:].strip()
                    
                    with st.container(border=True):
                        if "bienvenidos a focus" in rival.lower() or rival.lower() == "focus":
                            st.markdown(f"✨ <span style='color:#ff5500; font-weight:700;'>BIENVENIDA OFICIAL A TU GALERÍA</span>", unsafe_allow_html=True)
                            st.markdown(f"## Focus")
                        elif es_fecha_futura:
                            st.markdown(f"🎥 <span style='color:#ff5500; font-weight:700;'>COBERTURA EN VIVO PROGRAMADA</span>", unsafe_allow_html=True)
                            st.markdown(f"## 🆚 {texto_rival_limpio}")
                        elif estatus == "listo":
                            st.markdown(f"✅ <span style='color:#00ff66; font-weight:700;'>TRANSMISIÓN DISPONIBLE EN ALTA DEFINICIÓN</span>", unsafe_allow_html=True)
                            st.markdown(f"## 🆚 {texto_rival_limpio}")
                        else:
                            st.markdown(f"⏳ <span style='color:#ffaa00; font-weight:700;'>VIDEO EN PROCESO DE EDICIÓN MULTIMEDIA</span>", unsafe_allow_html=True)
                            st.markdown(f"## 🆚 {texto_rival_limpio}")
                            
                        st.markdown(f"📅 **Fecha del Encuentro:** {fecha_str}")
                        st.write("---")
                        
                        if "bienvenidos a focus" in rival.lower() or rival.lower() == "focus":
                            st.info("👋 ¡Hola Familias! Bienvenidos a su plataforma Focus.")
                        elif es_fecha_futura:
                            st.info("🎯 Nuestro equipo técnico ya tiene agendado este partido. Las cámaras de Accusport estarán listas en la cancha.")
                        elif estatus == "listo":
                            if link_drive and "drive.google.com" in link_drive:
                                video_id = None
                                file_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', link_drive)
                                id_match = re.search(r'id=([a-zA-Z0-9_-]+)', link_drive)
                                
                                if file_match:
                                    video_id = file_match.group(1)
                                elif id_match:
                                    video_id = id_match.group(1)
                                
                                if video_id:
                                    embed_url = f"https://drive.google.com/file/d/{video_id}/preview"
                                    try:
                                        st.iframe(embed_url, height=450)
                                    except AttributeError:
                                        st.components.v1.iframe(embed_url, height=450, scrolling=False)
                                    st.write("")
                                    st.link_button("📥 DESCARGAR VIDEO ORIGINAL (HD)", link_drive, width='stretch')
                                else:
                                    st.link_button("📺 ABRIR CARPETA DE VIDEOS EN DRIVE", link_drive, width='stretch')
                            elif link_drive:
                                st.link_button("📺 VER TRANSMISIÓN EN VIVO", link_drive, width='stretch')
                            else:
                                st.warning("⚠️ No se ha adjuntado un enlace válido para este partido.")
                        else:
                            st.info("🕒 Los realizadores audiovisuales están procesando y optimizando el video de este partido. ¡Disponible muy pronto!")
            else:
                st.info(f"ℹ️ No hay videos cargados ni filmaciones programadas para este equipo todavía.")
        else:
            st.error("❌ Error de comunicación con la tabla multimedia.")
    else:
        st.write("### 🔍 Ingresa a Focus Play")
        st.write("Selecciona tu categoría para acceder a la videoteca exclusiva de partidos.")
        
        df_p_init = obtener_datos_pestana("PARTIDOS")
        df_u_init = obtener_datos_pestana("USUARIOS")
        
        set_equipos = set()
        if not df_p_init.empty and "Equipo" in df_p_init.columns:
            set_equipos.update(df_p_init["Equipo"].astype(str).str.strip().unique())
        if not df_u_init.empty and "Equipo" in df_u_init.columns:
            set_equipos.update(df_u_init["Equipo"].astype(str).str.strip().unique())
            
        lista_equipos = sorted([eq for eq in set_equipos if eq and eq != "None"])
        if lista_equipos:
            equipo_seleccionado = st.selectbox("Selecciona tu Equipo / Categoría:", ["-- Elige tu categoría --"] + lista_equipos)
            if equipo_seleccionado != "-- Elige tu categoría --":
                if st.button("🚀 ENTRAR A MI GALERÍA DE STREAMING", width='stretch'):
                    st.session_state["equipo_activo"] = equipo_seleccionado
                    st.session_state["ver_galeria"] = True
                    st.rerun()
        else:
            st.error("❌ Registra un equipo desde el panel de control para activar el ingreso de familias.")

# =====================================================================
# SECCIÓN 2: INTERFAZ EN VIVO PARA CONTROL ADMINISTRATIVO
# =====================================================================
with tab_admin:
    st.write("### 🔑 Centro de Mando Focus")
    
    if not st.session_state.get("admin_autenticado", False):
        usuario_admin = st.text_input("Usuario Operativo:", key="user_adm").strip().lower()
        clave_admin = st.text_input("Contraseña de Seguridad:", type="password", key="pass_adm")
        if st.button("Autenticar Servidor", key="btn_admin_login"):
            if "admins" in st.secrets:
                dict_admins = st.secrets["admins"]
                if usuario_admin in dict_admins and clave_admin == str(dict_admins[usuario_admin]):
                    st.session_state["admin_autenticado"] = True
                    st.session_state["nombre_admin"] = usuario_admin.capitalize()
                    st.rerun()
                else:
                    st.error("❌ Credenciales inválidas.")
    else:
        st.success(f"🔓 Consola Activa: Conectado como **{st.session_state.get('nombre_admin', 'Admin')}**")
        
        with st.expander("🔗 SINCRONIZAR AGENDA WITH GOOGLE CALENDAR (CELULAR)", expanded=False):
            st.write("Vincula el calendario corporativo de Focus directamente a las pantallas de tus dispositivos.")
            if FOCUS_CALENDAR_DEFAULT:
                url_sincro_fijo = f"https://calendar.google.com/calendar/render?cid={FOCUS_CALENDAR_DEFAULT}"
                st.link_button("💥 VINCULAR ESTE CALENDARIO A MI GOOGLE CALENDAR PERSONAL", url_sincro_fijo, width='stretch')
        
        if st.button("🔒 Cerrar Sesión del Panel"):
            st.session_state["admin_autenticado"] = False
            st.session_state["nombre_admin"] = ""
            st.rerun()
            
        st.write("---")
        
        opcion_admin = st.selectbox(
            "⚙️ ¿Qué acción deseas realizar hoy?",
            [
                "📈 Tablero de Control Financiero (Balance)",
                "🛡️ 1. Añadir Equipo (GLOBAL)",
                "👤 2. Agregar Jugador / Papá a un Equipo (GRUPAL)",
                "📆 3. Programar Grabación / Subir Video + GOOGLE CALENDAR",
                "💰 4. Registrar Cobro Mensual (Clubes VIP)",
                "👁️ Auditar Hojas de Excel en Vivo"
            ]
        )
        st.write("---")
        
        # TABLERO DE CONTROL FINANCIERO
        if opcion_admin == "📈 Tablero de Control Financiero (Balance)":
            st.write("#### 📊 Balance General de Caja Focus")
            df_p = obtener_datos_pestana("PARTIDOS")
            df_m = obtener_datos_pestana("PAGOS_MENSUALES")
            
            total_partidos = 0
            col_dinero = [c for c in df_p.columns if "recaudo" in str(c).lower() or "recaudado" in str(c).lower()]
            if not df_p.empty and col_dinero:
                df_p[col_dinero[0]] = pd.to_numeric(df_p[col_dinero[0]], errors="coerce").fillna(0)
                total_partidos = df_p[col_dinero[0]].sum()
                
            total_mensualidades = 0
            if not df_m.empty and "Monto" in df_m.columns:
                df_m["Monto"] = pd.to_numeric(df_m["Monto"], errors="coerce").fillna(0)
                if "Estado" in df_m.columns:
                    total_mensualidades = df_m[df_m["Estado"] == "Pagado"]["Monto"].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("💵 Recaudo Partidos / Goles", f"${total_partidos:,.0f} COP")
            col2.metric("💳 Mensualidades Cobradas", f"${total_mensualidades:,.0f} COP")
            col3.metric("🏆 Ingresos Totales Focus", f"${(total_partidos + total_mensualidades):,.0f} COP")
            
        # 1. AÑADIR EQUIPO (GLOBAL)
        elif opcion_admin == "🛡️ 1. Añadir Equipo (GLOBAL)":
            st.write("#### 🛡️ Registrar y Activar un Nuevo Equipo en Focus")
            nuevo_equipo_nombre = st.text_input("Nombre Único del Equipo / Categoría:", placeholder="Ej: Fortaleza2017-b").strip()
            if st.button("🚀 CREAR Y ACTIVAR EQUIPO EN LA RED", width='stretch'):
                if nuevo_equipo_nombre:
                    fecha_hoy_str = datetime.now().strftime("%d/%m/%Y")
                    exito = agregar_fila_excel("PARTIDOS", [nuevo_equipo_nombre, fecha_hoy_str, "Focus", "Listo", "https://drive.google.com/file/d/1wJi3hOQaeIDY--OcFOxsy-ycb-uyATDpqIGvMYvHPg4/preview", 0])
                    if exito:
                        st.success(f"¡Golazo! El equipo **{nuevo_equipo_nombre}** ya está oficialmente creado y activo en internet.")
                        st.balloons()
                else:
                    st.error("⚠️ Por favor escribe el nombre de la categoría antes de guardarla.")

        # 2. AGREGAR JUGADOR (GRUPAL)
        elif opcion_admin == "👤 2. Agregar Jugador / Papá a un Equipo (GRUPAL)":
            st.write("#### 📝 Registro de Clientes en Directorio")
            nombre_papa = st.text_input("Nombre Completo del Papá / Acudiente:")
            nombre_hijo = st.text_input("Nombre Completo del Jugador (Hijo):")
            df_p_init = obtener_datos_pestana("PARTIDOS")
            df_u_init = obtener_datos_pestana("USUARIOS")
            set_eqs = set()
            if not df_p_init.empty and "Equipo" in df_p_init.columns: set_eqs.update(df_p_init["Equipo"].unique())
            if not df_u_init.empty and "Equipo" in df_u_init.columns: set_eqs.update(df_u_init["Equipo"].unique())
            lista_eq_u = sorted([e for e in set_eqs if e]) if set_eqs else ["Fortaleza2017-b"]
            equipo_u = st.selectbox("Asignar al Equipo / Categoría:", lista_eq_u)
            if st.button("💾 Guardar Cliente", width='stretch'):
                if nombre_papa and nombre_hijo:
                    exito = agregar_fila_excel("USUARIOS", [nombre_papa.strip(), nombre_hijo.strip(), equipo_u])
                    if exito: st.success(f"👤 ¡Jugador {nombre_hijo} guardado con éxito!")

        # 3. PROGRAMAR GRABACIÓN / SUBIR VIDEO (OPERATIVO)
        elif opcion_admin == "📆 3. Programar Grabación / Subir Video + GOOGLE CALENDAR":
            st.write("#### 📝 Control Operativo: Agendar Próximas Filmaciones o Publicar Videos")
            st.write(f"📢 *Sincronización vinculada automáticamente al calendario de Focus:* `{FOCUS_CALENDAR_DEFAULT}`")
            st.write("---")
            
            fecha_sel = st.date_input("Fecha del Encuentro:", datetime.now())
            
            df_p_init = obtener_datos_pestana("PARTIDOS")
            df_u_init = obtener_datos_pestana("USUARIOS")
            set_eqs = set()
            if not df_p_init.empty and "Equipo" in df_p_init.columns: set_eqs.update(df_p_init["Equipo"].unique())
            if not df_u_init.empty and "Equipo" in df_u_init.columns: set_eqs.update(df_u_init["Equipo"].unique())
            lista_eq = sorted([e for e in set_eqs if e]) if set_eqs else ["Fortaleza2017-b"]
            equipo_sel = st.selectbox("Categoría / Equipo Destino:", lista_eq)
            
            rival_nombre_libre = st.text_input("Nombre del Rival (Texto Libre):", placeholder="Ej: Millonarios FC, Ecopetrol")
            
            producto_formato_cerrado = st.selectbox(
                "Tipo de Contenido / Producto Focus (Catálogo Comercial):",
                [
                    "🎥 Partido Completo (Servicio Colectivo)",
                    "⚽ Solo Goles del Equipo (Servicio Colectivo)",
                    "📊 Reporte de Scouting VIP (Upselling Individual)",
                    "🔥 Video de Goles Personalizado (Upselling Individual)"
                ]
            )
            
            estatus_sel = st.selectbox("Estatus del Video:", ["Listo", "Procesando"])
            link_sel = st.text_input("Enlace del Archivo en Google Drive:", value="https://drive.google.com")
            recaudo_sel = st.number_input("Monto Recaudado por esta Venta ($ COP):", min_value=0, value=0, step=10000)
            
            sincronizar_google = st.checkbox("⚡ ¿Replicar y agendar este partido en los Google Calendars automáticamente?", value=True)
            
            if st.button("💾 Procesar y Publicar en la Plataforma", width='stretch'):
                if rival_nombre_libre:
                    titulo_combinado_final = f"{rival_nombre_libre} - {producto_formato_cerrado}"
                    fecha_str = fecha_sel.strftime("%d/%m/%Y")
                    
                    exito_excel = agregar_fila_excel("PARTIDOS", [equipo_sel, fecha_str, titulo_combinado_final, estatus_sel, link_sel, recaudo_sel])
                    
                    if exito_excel:
                        st.success("✅ Guardado con éxito en el sistema de streaming para las familias.")
                        if sincronizar_google:
                            crear_evento_google_calendar(FOCUS_CALENDAR_DEFAULT, titulo_combinado_final, fecha_sel, equipo_sel)
                            st.success("📅 Alerta enviada con éxito a tu Google Calendar operativo.")
                        st.balloons()
                else:
                    st.error("⚠️ Por favor escribe el nombre del rival.")

        # 4. REGISTRAR COBRO MENSUAL (VIP)
        elif opcion_admin == "💰 4. Registrar Cobro Mensual (Clubes VIP)":
            st.write("#### 💳 Control de Mensualidades de Clubes VIP")
            df_p_init = obtener_datos_pestana("PARTIDOS")
            df_u_init = obtener_datos_pestana("USUARIOS")
            set_eqs = set()
            if not df_p_init.empty and "Equipo" in df_p_init.columns: set_eqs.update(df_p_init["Equipo"].unique())
            if not df_u_init.empty and "Equipo" in df_u_init.columns: set_eqs.update(df_u_init["Equipo"].unique())
            lista_eq_m = sorted([e for e in set_eqs if e]) if set_eqs else ["Fortaleza2017-b"]
            equipo_m = st.selectbox("Selecciona el Equipo:", lista_eq_m)
            mes_m = st.selectbox("Mes Cobrado:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            monto_m = st.number_input("Monto de la Mensualidad ($ COP):", min_value=0, value=350000, step=50000)
            estado_m = st.selectbox("Estado de Caja:", ["Pagado", "Pendiente"])
            if st.button("💾 Guardar Registro Mensual", width='stretch'):
                exito = agregar_fila_excel("PAGOS_MENSUALES", [equipo_m, mes_m, monto_m, estado_m])
                if exito: st.success("💳 Mensualidad anotada con éxito en la tesorería.")

        # AUDITAR HOJAS
        elif opcion_admin == "👁️ Auditar Hojas de Excel en Vivo":
            tabla_sel = st.radio("Elige la base de datos a auditar:", ["USUARIOS", "PARTIDOS", "PAGOS_MENSUALES"])
            df_audit = obtener_datos_pestana(tabla_sel)
            if not df_audit.empty:
                st.write(f"**Mostrando {len(df_audit)} filas de la pestaña {tabla_sel}:**")
                st.dataframe(df_audit, use_container_width=True)

# =====================================================================
# 🦶 PIE DE PÁGINA (FOOTER) - ESCUDO DE MARCA ULTRA-PREMIUM CONTRA ERRORES
# =====================================================================
st.write("---") 
_, col_footer_center, _ = st.columns([2, 1, 2])
with col_footer_center:
    try:
        st.image(PATH_LOGO_ACCUSPORT, width=65)
    except Exception:
        # 🔥 ESCUDO ACTIVO: Renderiza un logotipo digital impecable si la imagen se corrompe
        st.markdown("""
            <div style='text-align:center; margin-top:-5px;'>
                <span style='color:#555555; font-size:10px; font-weight:800; letter-spacing:2px; display:block; margin-bottom:1px;'>POWERED BY</span>
                <span style='color:#ffffff; font-size:14px; font-weight:900; letter-spacing:1px;'>ACCU<span style='color:#ff5500;'>SPORT</span></span>
            </div>
        """, unsafe_allow_html=True)
