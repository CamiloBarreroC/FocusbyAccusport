import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
import streamlit.components.v1 as components

# =====================================================================
# 📝 CONFIGURACIÓN INICIAL - CON EL ID DE TU GOOGLE SHEET APLICADO
# =====================================================================
CONFIG_SHEET_ID = "1wJi3hOQaeIDY--OcFOxsy-ycb-uyATDpqIGvMYvHPg4" 
# =====================================================================

st.set_page_config(page_title="Focus by Accusport", page_icon="⚽", layout="centered")

# Inicializar estados de sesión
if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False
if "nombre_admin" not in st.session_state:
    st.session_state["nombre_admin"] = ""
if "ver_galeria" not in st.session_state:
    st.session_state["ver_galeria"] = False
if "equipo_activo" not in st.session_state:
    st.session_state["equipo_activo"] = ""

@st.cache_resource
def conectar_google_sheets():
    try:
        secrets_gcp = st.secrets["gcp_service_account"]
        creds_dict = json.loads(secrets_gcp) if isinstance(secrets_gcp, str) else dict(secrets_gcp)
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Error crítico de conexión con Google Cloud: {e}")
        return None

def obtener_datos_pestana(nombre_pestana):
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open_by_key(CONFIG_SHEET_ID)
            worksheet = sheet.worksheet(nombre_pestana)
            datos = worksheet.get_all_records()
            df = pd.DataFrame(datos)
            if not df.empty:
                df.columns = df.columns.astype(str).str.strip()
            return df
        except Exception as e:
            # Si la pestaña de pagos mensuales no existe todavía, creamos un DF vacío seguro
            return pd.DataFrame()
    return pd.DataFrame()

# 🚀 FUNCIONES DE ESCRITURA DIRECTA DESDE LA APP HACIA LAS 3 PESTAÑAS
def agregar_fila_excel(nombre_pestana, lista_datos):
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open_by_key(CONFIG_SHEET_ID)
            worksheet = sheet.worksheet(nombre_pestana)
            worksheet.append_row(lista_datos)
            return True
        except Exception as e:
            st.error(f"❌ Error al escribir en la pestaña '{nombre_pestana}': {e}")
            return False
    return False

# --- DISEÑO DEL PORTAL WEB ---
st.title("⚽ Focus by Accusport")
st.subheader("Portal Oficial de Grabaciones y Gestión Deportiva")
st.write("---")

tab_padres, tab_admin = st.tabs(["📅 Calendario para Padres", "🔒 Control Administrativo"])

# =====================================================================
# SECCIÓN 1: INTERFAZ DE PADRES (CALENDARIO IMPECABLE)
# =====================================================================
with tab_padres:
    if st.session_state["ver_galeria"]:
        equipo = st.session_state["equipo_activo"]
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
                        if es_fecha_futura:
                            st.markdown(f"🗓️ **PRÓXIMO ENCUENTRO PROGRAMADO**")
                        elif estatus == "listo":
                            st.markdown(f"✅ **PARTIDO GRABADO Y DISPONIBLE**")
                        else:
                            st.markdown(f"⏳ **PARTIDO EN PROCESO DE EDICIÓN**")
                            
                        st.markdown(f"## 🆚 vs {rival}")
                        st.markdown(f"📅 **Fecha:** {fecha_str}")
                        st.write("---")
                        
                        if es_fecha_futura:
                            st.info("🎯 Este partido está programado en la agenda.")
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
                                    st.link_button("📺 VER REPRODUCCIÓN", link_drive, use_container_width=True)
                        else:
                            st.info("🕒 Procesando archivos multimedia...")
            else:
                st.info(f"ℹ️ No hay partidos en la agenda de este equipo.")
    else:
        st.write("### 🔍 Selecciona tu Categoría")
        df_partidos_init = obtener_datos_pestana("PARTIDOS")
        if not df_partidos_init.empty and "Equipo" in df_partidos_init.columns:
            df_partidos_init["Equipo"] = df_partidos_init["Equipo"].astype(str).str.strip()
            lista_equipos = sorted([eq for eq in df_partidos_init["Equipo"].unique() if eq])
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
    
    if not st.session_state["admin_autenticado"]:
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
        st.success(f"🔓 Consola Activa: Conectado como **{st.session_state['nombre_admin']}**")
        if st.button("🔒 Cerrar Sesión del Panel"):
            st.session_state["admin_autenticado"] = False
            st.session_state["nombre_admin"] = ""
            st.rerun()
            
        st.write("---")
        
        # 📊 MENÚ DE OPCIONES DEL SUPER ADMINISTRADOR (ERP)
        opcion_admin = st.selectbox(
            "⚙️ ¿Qué acción deseas realizar hoy?",
            [
                "📈 Tablero de Control Financiero (Balance)",
                "⚽ Registrar Partido y Recaudo",
                "💰 Registrar Cobro Mensual (Equipos Suscritos)",
                "👤 Agregar Nuevo Jugador / Papá",
                "👁️ Auditar Hojas de Excel en Vivo"
            ]
        )
        st.write("---")
        
        # 💰 1. TABLERO DE CONTROL FINANCIERO (RESUMEN EN TIEMPO REAL)
        if opcion_admin == "📈 Tablero de Control Financiero (Balance)":
            st.write("#### 📊 Balance General de Caja Focus")
            
            df_p = obtener_datos_pestana("PARTIDOS")
            df_m = obtener_datos_pestana("PAGOS_MENSUALES")
            
            # Cálculo de Recaudo por Partidos
            total_partidos = 0
            if not df_p.empty and "Recaudado" in df_p.columns:
                df_p["Recaudado"] = pd.to_numeric(df_p["Recaudado"], errors="coerce").fillna(0)
                total_partidos = df_p["Recaudado"].sum()
                
            # Cálculo de Recaudo por Suscripciones Mensuales
            total_mensualidades = 0
            if not df_m.empty and "Monto" in df_m.columns:
                df_m["Monto"] = pd.to_numeric(df_m["Monto"], errors="coerce").fillna(0)
                # Solo sumamos las que digan "Pagado"
                if "Estado" in df_m.columns:
                    total_mensualidades = df_m[df_m["Estado"] == "Pagado"]["Monto"].sum()
            
            # Métricas en Bloques Visuales Elegantes
            col1, col2, col3 = st.columns(3)
            col1.metric("💵 Recaudo por Partidos", f"${total_partidos:,.0f} COP")
            col2.metric("💳 Mensualidades Cobradas", f"${total_mensualidades:,.0f} COP")
            col3.metric("🏆 Ingresos Totales Focus", f"${(total_partidos + total_mensualidades):,.0f} COP", delta="En Crecimiento")
            
        # ⚽ 2. FORMULARIO: REGISTRAR PARTIDO Y RECAUDO
        elif opcion_admin == "⚽ Registrar Partido y Recaudo":
            st.write("#### 📝 Cargar Encuentro y Plata Recaudada")
            
            fecha_sel = st.date_input("Fecha del Partido:", datetime.now())
            df_u = obtener_datos_pestana("USUARIOS")
            lista_eq = sorted(list(df_u["Equipo"].unique())) if not df_u.empty else ["Fortaleza2017-b"]
            
            equipo_sel = st.selectbox("Categoría / Equipo:", lista_eq)
            rival_sel = st.text_input("Rival o Descripción del Clip:", placeholder="Ej: Millonarios FC")
            estatus_sel = st.selectbox("Estatus del Video:", ["Listo", "Procesando"])
            link_sel = st.text_input("Enlace de Video de Google Drive:")
            
            # 🔥 NUEVO CAMPO FINANCIERO: Cuánto se hizo en este partido
            recaudo_sel = st.number_input("Monto Recaudado por este Partido ($ COP):", min_value=0, value=0, step=10000)
            
            if st.button("💾 Registrar Partido", use_container_width=True):
                if rival_sel and link_sel:
                    fecha_str = fecha_sel.strftime("%d/%m/%Y")
                    exito = agregar_fila_excel("PARTIDOS", [equipo_sel, fecha_str, rival_sel, estatus_sel, link_sel, recaudo_sel])
                    if exito:
                        st.success("⚽ ¡Partido y recaudo financiero agendados correctamente!")
                        st.balloons()
                else:
                    st.error("⚠️ Completa el rival y el link de Drive.")

        # 💰 3. FORMULARIO: REGISTRAR SUSCRIPCIÓN MENSUAL DE EQUIPOS
        elif opcion_admin == "💰 Registrar Cobro Mensual (Equipos Suscritos)":
            st.write("#### 💳 Control de Mensualidades de Clubes VIP")
            st.write("Registra los pagos fijos de los equipos que te contratan por meses completos.")
            
            df_u = obtener_datos_pestana("USUARIOS")
            lista_eq_m = sorted(list(df_u["Equipo"].unique())) if not df_u.empty else ["Fortaleza2017-b"]
            
            equipo_m = st.selectbox("Selecciona el Equipo:", lista_eq_m)
            mes_m = st.selectbox("Mes de Cobertura:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            monto_m = st.number_input("Valor de la Mensualidad ($ COP):", min_value=0, value=350000, step=50000)
            estado_m = st.selectbox("Estado del Pago:", ["Pagado", "Pendiente"])
            
            if st.button("💾 Guardar Registro Mensual", use_container_width=True):
                exito = agregar_fila_excel("PAGOS_MENSUALES", [equipo_m, mes_m, monto_m, estado_m])
                if exito:
                    st.success(f"💳 ¡Mensualidad del mes de {mes_m} para {equipo_m} registrada con éxito!")
                    st.balloons()

        # 👤 4. FORMULARIO: AGREGAR NUEVO JUGADOR / PAPÁ DESDE LA APP
        elif opcion_admin == "👤 Agregar Nuevo Jugador / Papá":
            st.write("#### 📝 Registro de Nuevos Clientes (Directorio)")
            st.write("Ingresa un nuevo alumno para alimentar tu base de datos de usuarios sin abrir Excel.")
            
            nombre_papa = st.text_input("Nombre Completo del Papá / Acudiente:")
            nombre_hijo = st.text_input("Nombre Completo del Jugador (Hijo):")
            
            # Permitir escribir una categoría nueva o elegir una existente
            df_u = obtener_datos_pestana("USUARIOS")
            lista_eq_u = list(df_u["Equipo"].unique()) if not df_u.empty else []
            
            opcion_eq = st.radio("¿El equipo ya existe?", ["Elegir un equipo existente", "Crear una nueva categoría/equipo"])
            if opcion_eq == "Elegir un equipo existente" and lista_eq_u:
                equipo_u = st.selectbox("Selecciona el Equipo:", sorted(lista_eq_u))
            else:
                equipo_u = st.text_input("Escribe el nombre de la nueva categoría:", placeholder="Ej: SantaFe-2015")
                
            if st.button("💾 Guardar Cliente en Base de Datos", use_container_width=True):
                if nombre_papa and nombre_hijo and equipo_u:
                    exito = agregar_fila_excel("USUARIOS", [nombre_papa.strip(), nombre_hijo.strip(), equipo_u.strip()])
                    if exito:
                        st.success(f"👤 ¡{nombre_hijo} asignado a {equipo_u} guardado con éxito!")
                else:
                    st.error("⚠️ Por favor rellena todos los campos.")

        # 👁️ 5. INSPECCIÓN TRADICIONAL DE TABLAS
        elif opcion_admin == "👁️ Auditar Hojas de Excel en Vivo":
            tabla_sel = st.radio("Elige la base de datos a auditar:", ["USUARIOS", "PARTIDOS", "PAGOS_MENSUALES"])
            df_audit = obtener_datos_pestana(tabla_sel)
            if not df_audit.empty:
                st.write(f"**Mostrando {len(df_audit)} filas de la pestaña {tabla_sel}:**")
                st.dataframe(df_audit, use_container_width=True)
            else:
                st.warning(f"⚠️ La pestaña '{tabla_sel}' está vacía o no tiene registros aún.")
