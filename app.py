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
        # Validamos si la estructura viene como texto plano o como diccionario directo
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
            return pd.DataFrame(datos)
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
# SECCIÓN 1: INTERFAZ EN VIVO PARA LOS PADRES DE FAMILIA
# =====================================================================
with tab_padres:
    st.write("### 🔍 Consulta tus partidos grabados")
    st.write("Ingresa tu documento de identidad registrado para ver los videos de tu hijo y el estado de tu cuenta.")
    
    documento_input = st.text_input("Número de Documento del Padre:", key="doc_padre").strip()
    
    if st.button("Buscar mis Grabaciones", key="btn_buscar"):
        if not documento_input:
            st.warning("⚠️ Por favor, escribe un número de documento válido antes de buscar.")
        else:
            with st.spinner("Buscando en la base de datos de Focus..."):
                df_usuarios = obtener_datos_pestana("USUARIOS")
                df_partidos = obtener_datos_pestana("PARTIDOS")
                
                if not df_usuarios.empty:
                    # Estandarizamos el texto para evitar fallos por espacios o ceros iniciales
                    df_usuarios["Documento"] = df_usuarios["Documento"].astype(str).str.strip()
                    usuario_encontrado = df_usuarios[df_usuarios["Documento"] == documento_input]
                    
                    if not usuario_encontrado.empty:
                        # Extraemos la información del usuario del Excel
                        nombre_papa = usuario_encontrado.iloc[0]["Nombre_Papa"]
                        hijo = usuario_encontrado.iloc[0]["Hijo_Jugador"]
                        equipo = usuario_encontrado.iloc[0]["Equipo"]
                        
                        st.success(f"¡Bienvenido(a), {nombre_papa}!")
                        st.markdown(f"🏃‍♂️ **Hijo / Jugador:** {hijo} | 🏟️ **Equipo:** {equipo}")
                        st.write("---")
                        
                        # Buscamos y filtramos sus partidos correspondientes
                        if not df_partidos.empty:
                            df_partidos["Documento_Papa"] = df_partidos["Documento_Papa"].astype(str).str.strip()
                            partidos_filtrados = df_partidos[df_partidos["Documento_Papa"] == documento_input]
                            
                            if not partidos_filtrados.empty:
                                st.write("#### 🎥 Tus Partidos y Enlaces Disponibles:")
                                
                                for idx, row in partidos_filtrados.iterrows():
                                    with st.expander(f"📅 Partido vs {row['Rival/Partido']} ({row['Fecha']})"):
                                        st.write(f"**Estatus del Video:** {row['Estatus_Grabacion']}")
                                        st.write(f"**Estado del Pago:** {row['Estado_Pago']}")
                                        
                                        link_drive = row['Link_Download_Drive']
                                        # Verificamos si ya hay un enlace real cargado en el Excel
                                        if link_drive and str(link_drive).startswith("http"):
                                            st.markdown(f"🎨 **[📥 CLIC AQUÍ PARA VER Y DESCARGAR EL VIDEO]({link_drive})**")
                                        else:
                                            st.info("🕒 La grabación se está procesando o está pendiente de pago. El enlace aparecerá aquí automáticamente.")
                            else:
                                st.info("ℹ️ No se encontraron partidos asignados a este documento por el momento.")
                        else:
                            st.info("ℹ️ No hay partidos cargados en el sistema general.")
                    else:
                        st.error("❌ El número de documento ingresado no se encuentra registrado en nuestra base de datos actual.")
                else:
                    st.error("❌ Error de comunicación interna: No se pudo verificar la lista de usuarios.")

# =====================================================================
# SECCIÓN 2: INTERFAZ EN VIVO PARA CONTROL ADMINISTRATIVO (BÚNKER)
# =====================================================================
with tab_admin:
    st.write("### 🔑 Centro de Mando Focus")
    
    # Caso A: El administrador NO ha iniciado sesión todavía (Muestra el formulario)
    if not st.session_state["admin_autenticado"]:
        st.write("Acceso restringido exclusivo para el equipo operativo de Focus by Accusport.")
        
        usuario_admin = st.text_input("Nombre de Usuario Administrativo:", key="user_adm").strip().lower()
        clave_admin = st.text_input("Contraseña de Seguridad:", type="password", key="pass_adm")
        
        if st.button("Autenticar Servidor", key="btn_admin_login"):
            if "admins" in st.secrets:
                dict_admins = st.secrets["admins"]
                
                # Comprobamos de manera segura si el usuario existe y si la clave coincide al 100%
                if usuario_admin in dict_admins and clave_admin == str(dict_admins[usuario_admin]):
                    st.session_state["admin_autenticado"] = True
                    st.session_state["nombre_admin"] = usuario_admin.capitalize()
                    st.success("🔒 Acceso concedido. Cargando consola...")
                    st.rerun() # Forzamos recarga inmediata para desbloquear el panel visual
                else:
                    st.error("❌ Credenciales inválidas. Inténtalo de nuevo o contacta al administrador del sistema.")
            else:
                st.error("🚨 Error del Servidor: No se encontró la base de credenciales '[admins]' en los Secrets de Streamlit.")
                
    # Caso B: El administrador YA inició sesión con éxito (Muestra las herramientas de control)
    else:
        st.success(f"🔓 Consola Activa: Conectado como **{st.session_state['nombre_admin']}**")
        
        # Botón directo para salir del búnker
        if st.button("🔒 Cerrar Sesión del Panel"):
            st.session_state["admin_autenticado"] = False
            st.session_state["nombre_admin"] = ""
            st.rerun()
            
        st.write("---")
        st.write("#### 📊 Monitor de Base de Datos en Tiempo Real")
        
        # Selector de datos para auditar el Google Sheet directamente desde Streamlit
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
