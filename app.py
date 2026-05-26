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

# Inicializar estados de sesión para el control de administradores
if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False
if "nombre_admin" not in st.session_state:
    st.session_state["nombre_admin"] = ""

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
            
            # 🔥 BLINDAJE: Limpia espacios invisibles de los títulos del Excel automáticamente
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
# SECCIÓN 1: INTERFAZ DESPLEGABLE POR EQUIPO PARA LOS PADRES
# =====================================================================
with tab_padres:
    st.write("### 🔍 Consulta tus partidos grabados")
    st.write("Selecciona tu equipo y busca el nombre del jugador para acceder a la cartelera de videos.")
    
    with st.spinner("Sincronizando cartelera deportiva..."):
        df_usuarios = obtener_datos_pestana("USUARIOS")
        df_partidos = obtener_datos_pestana("PARTIDOS")
        
    if not df_usuarios.empty:
        # Validar que existan las columnas clave antes de operar
        columnas_requeridas = ["Equipo", "Hijo_Jugador", "Documento", "Nombre_Papa"]
        columnas_faltantes = [col for col in columnas_requeridas if col not in df_usuarios.columns]
        
        if columnas_faltantes:
            st.error(f"🚨 Error en los títulos de tu Google Sheet. Falta o está mal escrita la columna: **{columnas_faltantes[0]}**")
            st.info("Revisa la fila 1 de tu pestaña 'USUARIOS' y asegúrate de escribir los títulos exactamente iguales.")
        else:
            # Limpieza de textos en las celdas
            df_usuarios["Equipo"] = df_usuarios["Equipo"].astype(str).str.strip()
            df_usuarios["Hijo_Jugador"] = df_usuarios["Hijo_Jugador"].astype(str).str.strip()
            
            # 1. Filtro dinámico de Equipos
            lista_equipos = sorted([eq for eq in df_usuarios["Equipo"].unique() if eq])
            equipo_seleccionado = st.selectbox("1. Selecciona el Equipo de tu Hijo:", ["-- Selecciona un equipo --"] + lista_equipos)
            
            if equipo_seleccionado != "-- Selecciona un equipo --":
                df_filtrado_equipo = df_usuarios[df_usuarios["Equipo"] == equipo_seleccionado]
                lista_hijos = sorted([hj for hj in df_filtrado_equipo["Hijo_Jugador"].unique() if hj])
                
                # 2. Filtro dinámico de Alumnos
                hijo_seleccionado = st.selectbox("2. Selecciona el Nombre del Jugador (Hijo):", ["-- Selecciona al jugador --"] + lista_hijos)
                
                if hijo_seleccionado != "-- Selecciona al jugador --":
                    st.write("")
                    if st.button("Buscar mis Grabaciones", key="btn_buscar_por_equipo"):
                        
                        usuario_info = df_filtrado_equipo[df_filtrado_equipo["Hijo_Jugador"] == hijo_seleccionado].iloc[0]
                        documento_interno = str(usuario_info["Documento"]).strip()
                        nombre_papa = usuario_info["Nombre_Papa"]
                        
                        st.success(f"¡Bienvenido(a) Familia de {hijo_seleccionado}!")
                        st.markdown(f"👨‍👦 **Acudiente Registrado:** {nombre_papa} | 🏟️ **Equipo:** {equipo_seleccionado}")
                        st.write("---")
                        
                        if not df_partidos.empty:
                            # Asegurar limpieza también en la tabla de partidos
                            if "Documento_Papa" in df_partidos.columns:
                                df_partidos["Documento_Papa"] = df_partidos["Documento_Papa"].astype(str).str.strip()
                                partidos_filtrados = df_partidos[df_partidos["Documento_Papa"] == documento_interno]
                                
                                if not partidos_filtrados.empty:
                                    st.write("#### 🎥 Partidos y Enlaces Disponibles:")
                                    
                                    for idx, row in partidos_filtrados.iterrows():
                                        rival = row.get('Rival/Partido', 'Desconocido')
                                        fecha = row.get('Fecha', 'S/F')
                                        estatus = row.get('Estatus_Grabacion', 'Procesando')
                                        pago = row.get('Estado_Pago', 'Pendiente')
                                        link_drive = row.get('Link_Download_Drive', '')
                                        
                                        with st.expander(f"📅 Partido vs {rival} ({fecha})"):
                                            st.write(f"**Estatus de la Grabación:** {estatus}")
                                            st.write(f"**Estado del Pago:** {pago}")
                                            
                                            if link_drive and str(link_drive).startswith("http"):
                                                st.markdown(f"🎨 **[📥 CLIC AQUÍ PARA VER Y DESCARGAR EL VIDEO]({link_drive})**")
                                            else:
                                                st.info("🕒 Este video se está procesando o está pendiente de facturación. El enlace se activará automáticamente.")
                                else:
                                    st.info("ℹ️ No se encontraron grabaciones asignadas a este jugador por el momento.")
                            else:
                                st.error("🚨 Falta la columna 'Documento_Papa' en la pestaña PARTIDOS.")
                        else:
                            st.info("ℹ️ No hay partidos registrados en el sistema general actualmente.")
    else:
        st.error("❌ La pestaña 'USUARIOS' del Excel está completamente vacía. Agrega al menos una fila con datos de prueba.")

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
                    st.error("❌ Credenciales inválidas. Inténtalo de nuevo o contacta al administrador del sistema.")
            else:
                st.error("🚨 Error del Servidor: No se encontró la base de credenciales '[admins]' en los Secrets de Streamlit.")
                
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
        
        with st.spinner("Sincronizando información con Google Drive..."):
            if opcion_tabla == "Ver Tabla de Usuarios (Papás)":
                df_adm_u = obtener_datos_pestana("USUARIOS")
                if not df_adm_u.empty:
                    st.write(f"**Total de registros encontrados:** {len(df_adm_u)} papás.")
                    st.dataframe(df_adm_u, use_container_width=True)
                else:
                    st.warning("⚠️ La pestaña 'USUARIOS' está vacía o sus columnas no coinciden con el formato.")
                    
            elif opcion_tabla == "Ver Tabla de Partidos (Grabaciones y Enlaces)":
                df_adm_p = obtener_datos_pestana("PARTIDOS")
                if not df_adm_p.empty:
                    st.write(f"**Total de registros encontrados:** {len(df_adm_p)} partidos/videos.")
                    st.dataframe(df_adm_p, use_container_width=True)
                else:
                    st.warning("⚠️ La pestaña 'PARTIDOS' está vacía o sus columnas no coinciden con el formato.")
