import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# =====================================================================
# 📝 CONFIGURACIÓN INICIAL - CON EL ID DE TU GOOGLE SHEET APLICADO
# =====================================================================
CONFIG_SHEET_ID = "1wJi3hOQaeIDY--OcFOxsy-ycb-uyATDpqIGvMYvHPg4" 
# =====================================================================

# Configuración visual de la pestaña del navegador
st.set_page_config(page_title="Focus by Accusport", page_icon="⚽", layout="centered")

# Inicializar estados de sesión para el flujo visual y administradores
if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False
if "nombre_admin" not in st.session_state:
    st.session_state["nombre_admin"] = ""
if "ver_galeria" not in st.session_state:
    st.session_state["ver_galeria"] = False
if "info_jugador_activo" not in st.session_state:
    st.session_state["info_jugador_activo"] = {}

# Función para conectar con Google Sheets de forma segura usando la llave de los Secrets
@st.cache_resource
def conectar_google_sheets():
    try:
        secrets_gcp = st.secrets["gcp_service_account"]
        if isinstance(secrets_gcp, str):
            creds_dict = json.loads(secrets_gcp)
        else:
            creds_dict = dict(secrets_gcp)
            
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"⚠️ Error crítico de conexión con Google Cloud: {e}")
        return None

# Función optimizada para traer los datos en vivo de una pestaña de Excel
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
            st.error(f"❌ Error al intentar leer la pestaña '{nombre_pestana}': {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- DISEÑO DEL PORTAL WEB ---
st.title("⚽ Focus by Accusport")
st.subheader("Portal Oficial de Grabaciones y Control Administrativo")
st.write("---")

# División de la aplicación en dos grandes pestañas interactivas
tab_padres, tab_admin = st.tabs(["👪 Ingreso Padres / Clientes", "🔒 Control Administrativo"])

# =====================================================================
# SECCIÓN 1: INTERFAZ DE PADRES (GALERÍA PREMIUM LIMPIA)
# =====================================================================
with tab_padres:
    
    # CASO INTERFAZ A: Modo Galería Activo (Filtros ocultos, solo tarjetas de video)
    if st.session_state["ver_galeria"]:
        info = st.session_state["info_jugador_activo"]
        
        # Botón elegante para regresar a la búsqueda
        if st.button("⬅️ Volver a la lista de equipos"):
            st.session_state["ver_galeria"] = False
            st.session_state["info_jugador_activo"] = {}
            st.rerun()
            
        st.write(f"### 🎬 Galería de Videos: **{info['hijo']}**")
        st.markdown(f"🏟️ **Equipo:** {info['equipo']} | 👨‍👦 **Acudiente:** {info['papa']}")
        st.write("---")
        
        with st.spinner("Cargando tus partidos grabados..."):
            df_partidos = obtener_datos_pestana("PARTIDOS")
            
        if not df_partidos.empty and "Documento_Papa" in df_partidos.columns:
            df_partidos["Documento_Papa"] = df_partidos["Documento_Papa"].astype(str).str.strip()
            partidos_filtrados = df_partidos[df_partidos["Documento_Papa"] == info["documento"]]
            
            if not partidos_filtrados.empty:
                st.write("Selecciona el partido que deseas reproducir:")
                
                # Grid de 2 columnas para distribución de tarjetas estilo catálogo
                cols = st.columns(2)
                
                for idx, (index_fila, row) in enumerate(partidos_filtrados.iterrows()):
                    rival = row.get('Rival/Partido', 'Rival Desconocido')
                    fecha = row.get('Fecha', 'S/F')
                    estatus = row.get('Estatus_Grabacion', 'Procesando')
                    link_drive = row.get('Link_Download_Drive', '')
                    
                    with cols[idx % 2]:
                        # Contenedor estético de la tarjeta
                        with st.container(border=True):
                            # Encabezado digital nativo (Adiós imágenes rotas externas)
                            st.markdown("🌐 **FOCUS MATCH CAM**")
                            st.write("---")
                            
                            st.markdown(f"### 🆚 {rival}")
                            st.markdown(f"📅 **Fecha del Encuentro:** {fecha}")
                            
                            # Filtro visual: Solo mostramos la disponibilidad de la filmación
                            if str(estatus).lower() == "listo":
                                st.markdown("🎥 **Video:** 🟢 Disponible Ahora")
                            else:
                                st.markdown("🎥 **Video:** ⏳ En Procesamiento Técnico")
                            
                            st.write("")
                            # Botón de acción directo
                            if link_drive and str(link_drive).startswith("http"):
                                st.link_button("📺 VER REPRODUCCIÓN / DESCARGAR", link_drive, use_container_width=True)
                            else:
                                st.info("🕒 El enlace se activará automáticamente cuando el video termine de subirse.")
            else:
                st.info("ℹ️ No se encontraron grabaciones asignadas a este jugador por el momento.")
        else:
            st.error("❌ No se pudo conectar a la tabla de partidos o falta la columna 'Documento_Papa'.")

    # CASO INTERFAZ B: Modo Filtros Activo (Ventana Inicial de Selección)
    else:
        st.write("### 🔍 Consulta tus partidos grabados")
        st.write("Selecciona tu equipo y busca el nombre del jugador para acceder a la cartelera de videos.")
        
        with st.spinner("Sincronizando cartelera deportiva..."):
            df_usuarios = obtener_datos_pestana("USUARIOS")
            
        if not df_usuarios.empty:
            df_usuarios["Equipo"] = df_usuarios["Equipo"].astype(str).str.strip()
            df_usuarios["Hijo_Jugador"] = df_usuarios["Hijo_Jugador"].astype(str).str.strip()
            
            columnas_requeridas = ["Equipo", "Hijo_Jugador", "Documento", "Nombre_Papa"]
            columnas_faltantes = [col for col in columnas_requeridas if col not in df_usuarios.columns]
            
            if columnas_faltantes:
                st.error(f"🚨 Títulos incorrectos en Excel. Falta la columna: **{columnas_faltantes[0]}**")
            else:
                # 1. Selector de Equipos
                lista_equipos = sorted([eq for eq in df_usuarios["Equipo"].unique() if eq])
                equipo_seleccionado = st.selectbox("1. Selecciona el Equipo de tu Hijo:", ["-- Selecciona un equipo --"] + lista_equipos)
                
                if equipo_seleccionado != "-- Selecciona un equipo --":
                    df_filtrado_equipo = df_usuarios[df_usuarios["Equipo"] == equipo_seleccionado]
                    lista_hijos = sorted([hj for hj in df_filtrado_equipo["Hijo_Jugador"].unique() if hj])
                    
                    # 2. Selector de Alumnos
                    hijo_seleccionado = st.selectbox("2. Selecciona el Nombre del Jugador (Hijo):", ["-- Selecciona al jugador --"] + lista_hijos)
                    
                    if hijo_seleccionado != "-- Selecciona al jugador --":
                        st.write("")
                        if st.button("🚀 ENTRAR A MI GALERÍA DE VIDEOS", use_container_width=True):
                            usuario_info = df_filtrado_equipo[df_filtrado_equipo["Hijo_Jugador"] == hijo_seleccionado].iloc[0]
                            
                            st.session_state["info_jugador_activo"] = {
                                "documento": str(usuario_info["Documento"]).strip(),
                                "hijo": hijo_seleccionado,
                                "equipo": equipo_seleccionado,
                                "papa": usuario_info["Nombre_Papa"]
                            }
                            st.session_state["ver_galeria"] = True
                            st.rerun()
        else:
            st.error("❌ La pestaña 'USUARIOS' está vacía. Añade datos en tu Google Sheet.")

# =====================================================================
# SECCIÓN 2: INTERFAZ EN VIVO PARA CONTROL ADMINISTRATIVO (BÚNKER)
# =====================================================================
with tab_admin:
    st.write("### 🔑 Centro de Mando Focus")
    
    if not st.session_state["admin_autenticado"]:
        st.write("Acceso restringido exclusivo para el equipo operativo de Focus by Accusport.")
        
        usuario_admin = st.text_input("Nombre de Usuario Administrativo:", key="user_adm").strip().lower()
        clave_admin = st.text_input("Contraseña de Seguridad:", type="password", key="pass_adm")
        
        if st.button("Autenticar Servidor", key="btn_admin_login"):
            if "admins" in st.secrets:
                dict_admins = st.secrets["admins"]
                if usuario_admin in dict_admins and clave_admin == str(dict_admins[usuario_admin]):
                    st.session_state["admin_autenticado"] = True
                    st.session_state["nombre_admin"] = usuario_admin.capitalize()
                    st.success("🔒 Acceso concedido. Cargando consola...")
                    st.rerun()
                else:
                    st.error("❌ Credenciales inválidas.")
            else:
                st.error("🚨 Error: No se encontró la sección '[admins]' en los Secrets.")
                
    else:
        st.success(f"🔓 Consola Activa: Conectado como **{st.session_state['nombre_admin']}**")
        
        if st.button("🔒 Cerrar Sesión del Panel"):
            st.session_state["admin_autenticado"] = False
            st.session_state["nombre_admin"] = ""
            st.rerun()
            
        st.write("---")
        st.write("#### 📊 Monitor de Base de Datos en Tiempo Real")
        
        opcion_tabla = st.radio(
            "Selecciona la base de datos que deseas auditar:", 
            ["Ver Tabla de Usuarios (Papás)", "Ver Tabla de Partidos (Grabaciones y Enlaces)"]
        )
        
        with st.spinner("Sincronizando información..."):
            if opcion_tabla == "Ver Tabla de Usuarios (Papás)":
                df_adm_u = obtener_datos_pestana("USUARIOS")
                if not df_adm_u.empty:
                    st.write(f"**Total de registros:** {len(df_adm_u)} papás.")
                    st.dataframe(df_adm_u, use_container_width=True)
            elif opcion_tabla == "Ver Tabla de Partidos (Grabaciones y Enlaces)":
                df_adm_p = obtener_datos_pestana("PARTIDOS")
                if not df_adm_p.empty:
                    st.write(f"**Total de registros:** {len(df_adm_p)} partidos.")
                    st.dataframe(df_adm_p, use_container_width=True)
