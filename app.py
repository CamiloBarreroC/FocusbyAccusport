import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build # 🚀 Librería oficial para Google Calendar
import pandas as pd
import json
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# =====================================================================
# 📝 CONFIGURACIÓN INICIAL - CON EL ID DE TU GOOGLE SHEET APLICADO
# =====================================================================
CONFIG_SHEET_ID = "1wJi3hOQaeIDY--OcFOxsy-ycb-uyATDpqIGvMYvHPg4" 
# =====================================================================

st.set_page_config(page_title="Focus by Accusport", page_icon="⚽", layout="centered")

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
        
        # 🔥 AGREGAMOS EL SCOPE DE GOOGLE CALENDAR A LA LLAVE SEGURA
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

# 🚀 NUEVA FUNCIÓN: Inyecta el partido directamente en tu Google Calendar real
def crear_evento_google_calendar(calendar_id, titulo, fecha_dt, equipo):
    service = obtener_servicio_calendar()
    if service:
        try:
            # Configuramos la hora de inicio (por defecto a las 8:00 AM si no se especifica otra)
            start_time = datetime.combine(fecha_dt, datetime.min.time()) + timedelta(hours=8)
            end_time = start_time + timedelta(hours=2) # Duración estimada: 2 horas
            
            event = {
                'summary': f"🎥 FOCUS: {equipo} vs {titulo}",
                'description': f'Grabación automatizada programada desde el panel Focus by Accusport para el equipo {equipo}.',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/Bogota',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/Bogota',
                },
            }
            # Guardamos el evento en Google Calendar
            service.events().insert(calendarId=calendar_id, body=event).execute()
            return True
        except Exception as e:
            st.warning(f"⚠️ Nota: No se pudo replicar en Google Calendar (Revisa si compartiste el calendario con el email del robot). Detalles: {e}")
            return False
    return False

# --- DISEÑO DEL PORTAL WEB ---
st.title("⚽ Focus by Accusport")
st.subheader("Portal Oficial de Grabaciones y Gestión Deportiva")
st.write("---")

tab_padres, tab_admin = st.tabs(["📅 Calendario para Padres", "🔒 Control Administrativo"])

# =====================================================================
# SECCIÓN 1: INTERFAZ DE PADRES
# =====================================================================
with tab_padres:
    if st.session_state.get("ver_galeria", False):
        equipo = st.session_state.get("equipo_activo", "")
        if st.button("⬅️ Volver a la lista de equipos"):
            st.session_state["ver_galeria"] = False
            st.session_state["equipo_activo"] = ""
            st.rerun()
            
        st.write(f"### 📅 Calendario de Encuentros: **{equipo}**")
        st.write("---")
        
        df_partidos = obtener_datos_pestana("PARTIDOS")
        if not df_partidos.empty and "Equipo" in df_partidos.columns:
            df_partidos["Equipo"] = df_partidos["Equipo"].astype(str).str.strip()
            partidos_filtrados = df_partidos[df_partidos["Equipo"] == equipo].copy()
            
            if not partidos_filtrados.empty:
                partidos_filtrados['Fecha_Datetime'] = pd.to_datetime(partidos_filtrados['Fecha'], errors='coerce', dayfirst=True)
                partidos_filtrados = partidos_filtrados.sort_values(by='Fecha_Datetime', ascending=False)
                
                for idx, row in partidos_filtrados.iterrows():
                    rival = row.get('Rival/Partido', 'Rival Desconocido')
                    fecha_str = row.get('Fecha', 'S/F')
                    estatus = str(row.get('Estatus_Grabacion', 'Procesando')).lower()
                    link_drive = str(row.get('Link_Download_Drive', '')).strip()
                    
                    es_fecha_futura = pd.notnull(row['Fecha_Datetime']) and row['Fecha_Datetime'].date() > datetime.now().date()
                    
                    with st.container(border=True):
                        if "bienvenidos a focus" in rival.lower():
                            st.markdown(f"✨ **BIENVENIDA OFICIAL A LA CATEGORÍA**")
                        elif es_fecha_futura:
                            st.markdown(f"🗓️ **PRÓXIMO ENCUENTRO PROGRAMADO**")
                        elif estatus == "listo":
                            st.markdown(f"✅ **PARTIDO GRABADO Y DISPONIBLE**")
                        else:
                            st.markdown(f"⏳ **PARTIDO EN PROCESO DE EDICIÓN**")
                            
                        st.markdown(f"## {rival if 'bienvenidos' in rival.lower() else '🆚 vs ' + rival}")
                        st.markdown(f"📅 **Fecha:** {fecha_str}")
                        st.write("---")
                        
                        if "bienvenidos a focus" in rival.lower():
                            st.info("👋 ¡Hola Familias! Bienvenidos al portal de Focus.")
                        elif es_fecha_futura:
                            st.info("🎯 Este encuentro está programado en la agenda Focus.")
                        elif estatus == "listo":
                            if link_drive and "drive.google.com" in link_drive:
                                video_id = None
                                try:
                                    if "/file/d/" in link_drive:
                                        video_id = link_drive.split("/file/d/")[1].split("/")[0]
                                    elif "id=" in link_drive:
                                        video_id = link_drive.split("id=")[1].split("&")[0]
                                    if video_id:
                                        embed_url = f"https://drive.google.com/file/d/{video_id}/preview"
                                        components.iframe(embed_url, height=450, scrolling=False)
                                        st.write("")
                                        st.link_button("📥 DESCARGAR VIDEO ORIGINAL", link_drive, use_container_width=True)
                                except Exception:
                                    st.link_button("📺 VER REPRODUCCIÓN EXTERNA", link_drive, use_container_width=True)
                        else:
                            st.info("🕒 Nuestro equipo técnico está procesando los archivos multimedia...")
            else:
                st.info(f"ℹ️ No hay partidos agendados.")
    else:
        st.write("### 🔍 Selecciona tu Categoría")
        df_p_init = obtener_datos_pestana("PARTIDOS")
        df_u_init = obtener_datos_pestana("USUARIOS")
        
        set_equipos = set()
        if not df_p_init.empty and "Equipo" in df_p_init.columns:
            set_equipos.update(df_p_init["Equipo"].astype(str).str.strip().unique())
        if not df_u_init.empty and "Equipo" in df_u_init.columns:
            set_equipos.update(df_u_init["Equipo"].astype(str).str.strip().unique())
            
        lista_equipos = sorted([eq for eq in set_equipos if eq and eq != "None"])
        if lista_equipos:
            equipo_seleccionado = st.selectbox("Selecciona tu Equipo / Categoría:", ["-- Selecciona un equipo --"] + lista_equipos)
            if equipo_seleccionado != "-- Selecciona un equipo --":
                if st.button("🚀 ABRIR CALENDARIO DEL EQUIPO", use_container_width=True):
                    st.session_state["equipo_activo"] = equipo_seleccionado
                    st.session_state["ver_galeria"] = True
                    st.rerun()

# =====================================================================
# SECCIÓN 2: INTERFAZ EN VIVO PARA CONTROL ADMINISTRATIVO (BÚNKER)
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
        if st.button("🔒 Cerrar Sesión del Panel"):
            st.session_state["admin_autenticado"] = False
            st.session_state["nombre_admin"] = ""
            st.rerun()
            
        st.write("---")
        
        opcion_admin = st.selectbox(
            "⚙️ ¿Qué acción deseas realizar hoy?",
            [
                "📈 Tablero de Control Financiero (Balance)",
                "📆 3. Registrar Partido + SINCRO GOOGLE CALENDAR", # 🚀 Opción repotenciada
                "🛡️ 1. Inicializar Nuevo Equipo / Categoría (GLOBAL)",
                "👤 2. Agregar Jugador / Papá a un Equipo (GRUPAL)",
                "💰 4. Registrar Cobro Mensual (Clubes VIP)",
                "👁️ Auditar Hojas de Excel en Vivo"
            ]
        )
        st.write("---")
        
        # TABLERO DE CONTROL
        if opcion_admin == "📈 Tablero de Control Financiero (Balance)":
            st.write("#### 📊 Balance General de Caja Focus")
            df_p = obtener_datos_pestana("PARTIDOS")
            df_m = obtener_datos_pestana("PAGOS_MENSUALES")
            
            total_partidos = 0
            if not df_p.empty and "Recaudado" in df_p.columns:
                df_p["Recaudado"] = pd.to_numeric(df_p["Recaudado"], errors="coerce").fillna(0)
                total_partidos = df_p["Recaudado"].sum()
                
            total_mensualidades = 0
            if not df_m.empty and "Monto" in df_m.columns:
                df_m["Monto"] = pd.to_numeric(df_m["Monto"], errors="coerce").fillna(0)
                if "Estado" in df_m.columns:
                    total_mensualidades = df_m[df_m["Estado"] == "Pagado"]["Monto"].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("💵 Recaudo Partidos / Goles", f"${total_partidos:,.0f} COP")
            col2.metric("💳 Mensualidades Cobradas", f"${total_mensualidades:,.0f} COP")
            col3.metric("🏆 Ingresos Totales Focus", f"${(total_partidos + total_mensualidades):,.0f} COP")
            
        # 🚀 OPCIÓN ULTRA-REPOTENCIADA CON SINCRO DE GOOGLE CALENDAR
        elif opcion_admin == "📆 3. Registrar Partido + SINCRO GOOGLE CALENDAR":
            st.write("#### 📝 Cargar Encuentro y Sincronizar Calendario Externo")
            
            # Campo clave para la Multiconexión de Calendarios
            st.info("💡 Puedes usar 'primary' para tu cuenta Accusport, o pegar el ID de cualquier otro calendario compartido.")
            calendar_id_input = st.text_input("ID del Google Calendar de Destino:", value="primary")
            
            st.write("---")
            fecha_sel = st.date_input("Fecha del Evento:", datetime.now())
            
            df_p_init = obtener_datos_pestana("PARTIDOS")
            df_u_init = obtener_datos_pestana("USUARIOS")
            set_eqs = set()
            if not df_p_init.empty and "Equipo" in df_p_init.columns:
                set_eqs.update(df_p_init["Equipo"].unique())
            if not df_u_init.empty and "Equipo" in df_u_init.columns:
                set_eqs.update(df_u_init["Equipo"].unique())
            lista_eq = sorted([e for e in set_eqs if e]) if set_eqs else ["Fortaleza2017-b"]
            
            equipo_sel = st.selectbox("Categoría / Equipo Destino:", lista_eq)
            rival_sel = st.text_input("Título del Video / Encuentro:", placeholder="Ej: vs Millonarios FC (Partido Completo)")
            estatus_sel = st.selectbox("Estatus de Publicación:", ["Listo", "Procesando"])
            link_sel = st.text_input("Enlace del Archivo de Video en Google Drive:", value="https://drive.google.com")
            recaudo_sel = st.number_input("Monto Recaudado por esta Venta ($ COP):", min_value=0, value=0, step=10000)
            
            # Checkbox inteligente para decidir si se envía a Google Calendar o no
            sincronizar_google = st.checkbox("⚡ ¿Replicar y agendar este partido en Google Calendar de forma automática?", value=True)
            
            if st.button("💾 Registrar Partido y Sincronizar", use_container_width=True):
                if rival_sel:
                    fecha_str = fecha_sel.strftime("%d/%m/%Y")
                    # 1. Guardamos en el Excel tradicional de los papás
                    exito_excel = agregar_fila_excel("PARTIDOS", [equipo_sel, fecha_str, rival_sel, estatus_sel, link_sel, recaudo_sel])
                    
                    if exito_excel:
                        st.success("✅ Guardado con éxito en la base de datos de los padres.")
                        
                        # 2. Si está activo, lo inyectamos en Google Calendar en vivo
                        if sincronizar_google:
                            with st.spinner("Sincronizando con Google Calendar en tiempo real..."):
                                crear_evento_google_calendar(calendar_id_input, rival_sel, fecha_sel, equipo_sel)
                            st.success(f"📅 ¡Evento replicado con éxito en el Google Calendar '{calendar_id_input}'!")
                        st.balloons()
                else:
                    st.error("⚠️ Completa el título del encuentro.")

        # 1. INICIALIZAR EQUIPO
        elif opcion_admin == "🛡️ 1. Inicializar Nuevo Equipo / Categoría (GLOBAL)":
            st.write("#### 🛡️ Alta de Categorías en la Plataforma Focus")
            nuevo_equipo_nombre = st.text_input("Nombre Único del Equipo / Categoría:", placeholder="Ej: Fortaleza2017-b").strip()
            if st.button("🚀 INICIALIZAR Y ACTIVAR EQUIPO", use_container_width=True):
                if nuevo_equipo_nombre:
                    fecha_hoy_str = datetime.now().strftime("%d/%m/%Y")
                    exito = agregar_fila_excel("PARTIDOS", [nuevo_equipo_nombre, fecha_hoy_str, "✨ ¡Bienvenidos a Focus por Accusport!", "Listo", "https://drive.google.com/file/d/1wJi3hOQaeIDY--OcFOxsy-ycb-uyATDpqIGvMYvHPg4/preview", 0])
                    if exito:
                        st.success(f"¡Excelente! El equipo **{nuevo_equipo_nombre}** ya está oficialmente activo.")
                        st.balloons()

        # 2. AGREGAR JUGADOR
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
            if st.button("💾 Guardar Cliente", use_container_width=True):
                if nombre_papa and nombre_hijo:
                    exito = agregar_fila_excel("USUARIOS", [nombre_papa.strip(), nombre_hijo.strip(), equipo_u])
                    if exito: st.success(f"👤 ¡Jugador {nombre_hijo} guardado!")

        # 4. REGISTRAR COBRO MENSUAL
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
            if st.button("💾 Guardar Registro Mensual", use_container_width=True):
                exito = agregar_fila_excel("PAGOS_MENSUALES", [equipo_m, mes_m, monto_m, estado_m])
                if exito: st.success(f"💳 Mensualidad de {mes_m} anotada.")

        # AUDITAR HOJAS
        elif opcion_admin == "👁️ Auditar Hojas de Excel en Vivo":
            tabla_sel = st.radio("Elige la base de datos a auditar:", ["USUARIOS", "PARTIDOS", "PAGOS_MENSUALES"])
            df_audit = obtener_datos_pestana(tabla_sel)
            if not df_audit.empty:
                st.write(f"**Mostrando {len(df_audit)} filas de la pestaña {tabla_sel}:**")
                st.dataframe(df_audit, use_container_width=True)
