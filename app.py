import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import streamlit.components.v1 as components

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
if "equipo_activo" not in st.session_state:
    st.session_state["equipo_activo"] = ""

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
st.subheader("Portal Oficial de Grabaciones Deportivas")
st.write("---")

# División de la aplicación en dos grandes pestañas interactivas
tab_padres, tab_admin = st.tabs(["👪 Galería para Padres", "🔒 Control Administrativo"])

# =====================================================================
# SECCIÓN 1: INTERFAZ DE PADRES (BÚSQUEDA DIRECTA POR EQUIPO)
# =====================================================================
with tab_padres:
    
    # CASO INTERFAZ A: Modo Galería Activo (Muestra los videos del equipo seleccionado)
    if st.session_state["ver_galeria"]:
        equipo = st.session_state["equipo_activo"]
        
        if st.button("⬅️ Volver a la lista de equipos"):
            st.session_state["ver_galeria"] = False
            st.session_state["equipo_activo"] = ""
            st.rerun()
            
        st.write(f"### 🎬 Cartelera de Videos: **{equipo}**")
        st.write("Disfruta de las grabaciones y resúmenes directamente aquí abajo:")
        st.write("---")
        
        with st.spinner("Cargando partidos de la categoría..."):
            df_partidos = obtener_datos_pestana("PARTIDOS")
            
        if not df_partidos.empty and "Equipo" in df_partidos.columns:
            df_partidos["Equipo"] = df_partidos["Equipo"].astype(str).str.strip()
            # Filtramos todos los partidos que pertenezcan a este equipo
            partidos_filtrados = df_partidos[df_partidos["Equipo"] == equipo]
            
            if not partidos_filtrados.empty:
                for index_fila, row in partidos_filtrados.iterrows():
                    rival = row.get('Rival/Partido', 'Rival Desconocido')
                    fecha = row.get('Fecha', 'S/F')
                    estatus = row.get('Estatus_Grabacion', 'Procesando')
                    link_drive = str(row.get('Link_Download_Drive', '')).strip()
                    
                    with st.container(border=True):
                        st.markdown(f"### 🆚 {rival}")
                        st.markdown(f"📅 **Fecha del Encuentro:** {fecha}")
                        
                        if str(estatus).lower() == "listo":
                            st.markdown("🎥 **Estatus:** 🟢 Disponible en Alta Definición")
                            
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
                                    else:
                                        st.warning("⚠️ El enlace de Drive no tiene un formato válido de archivo.")
                                        st.link_button("🔗 Abrir enlace alternativo", link_drive, use_container_width=True)
                                except Exception as e:
                                    st.link_button("📺 VER VIDEO (Enlace Externo)", link_drive, use_container_width=True)
                            else:
                                st.warning("⚠️ Falta el enlace del video en la base de datos.")
                        else:
                            st.markdown("🎥 **Estatus:** ⏳ En Procesamiento Técnico")
                            st.info("🕒 Este video se está procesando por nuestro equipo técnico. El reproductor aparecerá aquí automáticamente.")
            else:
                st.info(f"ℹ️ No se encontraron grabaciones cargadas para el equipo {equipo} por el momento.")
        else:
            st.error("❌ No se pudo conectar a la tabla de partidos o falta la columna 'Equipo' en la pestaña PARTIDOS.")

    # CASO INTERFAZ B: Modo Filtros Activo (Selector inicial de equipos)
    else:
        st.write("### 🔍 Consulta los partidos de tu equipo")
        st.write("Selecciona la categoría deportiva para acceder al catálogo exclusivo de reproducciones.")
        
        with st.spinner("Sincronizando categorías disponibles..."):
            df_partidos_init = obtener_datos_pestana("PARTIDOS")
            
        if not df_partidos_init.empty and "Equipo" in df_partidos_init.columns:
            df_partidos_init["Equipo"] = df_partidos_init["Equipo"].astype(str).str.strip()
            
            # Sacamos la lista de equipos que ya tienen partidos registrados
            lista_equipos = sorted([eq for eq in df_partidos_init["Equipo"].unique() if eq])
            
            equipo_seleccionado = st.selectbox("Selecciona tu Equipo / Categoría:", ["-- Selecciona un equipo --"] + lista_equipos)
            
            if equipo_seleccionado != "-- Selecciona un equipo --":
                st.write("")
                if st.button("🚀 ENTRAR A LA GALERÍA DEL EQUIPO", use_container_width=True):
                    st.session_state["equipo_activo"] = equipo_seleccionado
                    st.session_state["ver_galeria"] = True
                    st.rerun()
        else:
            st.error("❌ La pestaña 'PARTIDOS' está vacía o la columna 'Equipo' está mal escrita. Agrega al menos un partido en tu Google Sheet para activar el menú.")

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
            ["Ver Tabla de Usuarios (Mapeo Informativo)", "Ver Tabla de Partidos (Control de Videos)"]
        )
        
        with st.spinner("Sincronizando información..."):
            if opcion_tabla == "Ver Tabla de Usuarios (Mapeo Informativo)":
                df_adm_u = obtener_datos_pestana("USUARIOS")
                if not df_adm_u.empty:
                    st.write(f"**Total de alumnos registrados:** {len(df_adm_u)} jugadores.")
                    st.dataframe(df_adm_u, use_container_width=True)
            elif opcion_tabla == "Ver Tabla de Partidos (Control de Videos)":
                df_adm_p = obtener_datos_pestana("PARTIDOS")
                if not df_adm_p.empty:
                    st.write(f"**Total de grabaciones montadas:** {len(df_adm_p)} videos.")
                    st.dataframe(df_adm_p, use_container_width=True)
