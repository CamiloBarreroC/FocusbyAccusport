import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import os
import time

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
# Coloca aquí el ID único de tu NUEVA hoja de cálculo exclusiva para FOCUS
FOCUS_SHEET_ID = "TU_NUEVO_SHEET_ID_DE_FOCUS_AQUÍ"

def conectar_focus_sheets():
    info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(eval(info), scopes=scope)
    return gspread.authorize(creds).open_by_key(FOCUS_SHEET_ID)

# Configuración estética de la app de cara al cliente
st.set_page_config(page_title="Focus by Accusport", layout="centered", page_icon="⚽")

# Estilos visuales atractivos mediante CSS
st.markdown("""
    <style>
    .main { background-color: #f7f9fc; }
    .focus-header { text-align: center; color: #0b132b; font-weight: bold; margin-bottom: 20px; }
    .card-pagado {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #2ec4b6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    .card-pendiente {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #e71d36;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    .badge-pagado { background-color: #e2f9f5; color: #2ec4b6; padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 12px; }
    .badge-pendiente { background-color: #ffe5e8; color: #e71d36; padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 12px; }
    .badge-status { background-color: #e2eafc; color: #3a86ff; padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-left: 5px; }
    </style>
""", unsafe_allow_html=True)

# Control de navegación interna
if 'focus_vista' not in st.session_state:
    st.session_state.focus_vista = "inicio"
    st.session_state.papa_doc = ""
    st.session_state.papa_nombre = ""
    st.session_state.hijo_nombre = ""

# --- VISTA 1: PANTALLA DE BIENVENIDA / INICIO ---
if st.session_state.focus_vista == "inicio":
    _, col_logo, _ = st.columns([1, 2, 1])
    with col_logo:
        if os.path.exists("logofocus.png"):
            st.image("logofocus.png", use_container_width=True)
        else:
            st.markdown("<h1 class='focus-header'>🎥 FOCUS <br><span style='font-size:18px; color:#555;'>by Accusport</span></h1>", unsafe_allow_html=True)
            
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 ACCESO EXCLUSIVO PADRES", type="primary", use_container_width=True):
        st.session_state.focus_vista = "login_padres"
        st.rerun()
        
    if st.button("🔑 INGRESO CONTROL ADMINISTRATIVO", use_container_width=True):
        st.session_state.focus_vista = "login_admin"
        st.rerun()

# --- VISTA 2: LOGIN EXCLUSIVO DE PADRES ---
elif st.session_state.focus_vista == "login_padres":
    st.markdown("<h2 style='text-align: center;'>⚽ Portal de Padres de Familia</h2>", unsafe_allow_html=True)
    st.write("Ingresa tu número de documento registrado para descargar los videos de tu hijo y revisar el calendario de partidos.")
    
    with st.form("form_login_padres"):
        doc_input = st.text_input("Número de Documento de Identidad").strip()
        btn_entrar = st.form_submit_button("INGRESAR AL PORTAL")
        
        if btn_entrar:
            if doc_input:
                try:
                    db = conectar_focus_sheets()
                    usuarios_data = db.worksheet("USUARIOS").get_all_records()
                    
                    user_found = None
                    for row in usuarios_data:
                        if str(row.get("Documento")).strip() == doc_input:
                            user_found = row
                            break
                    
                    if user_found:
                        st.session_state.focus_vista = "dashboard_padres"
                        st.session_state.papa_doc = doc_input
                        st.session_state.papa_nombre = user_found.get("Nombre_Papa", "Padre Registrado")
                        st.session_state.hijo_nombre = user_found.get("Hijo_Jugador", "Jugador")
                        st.rerun()
                    else:
                        st.error("⚠️ El número de documento no se encuentra registrado en el sistema Focus.")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")
            else:
                st.warning("Por favor, digita tu documento.")
                
    if st.button("Volver al Inicio"):
        st.session_state.focus_vista = "inicio"
        st.rerun()

# --- VISTA 3: DASHBOARD PÚBLICO PARA LOS PADRES ---
elif st.session_state.focus_vista == "dashboard_padres":
    st.markdown(f"<h2 style='color:#0b132b;'>¡Hola, {st.session_state.papa_nombre}! 👋</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#555; font-size:16px;'>Historial y cronograma de partidos de: <strong>{st.session_state.hijo_nombre}</strong></p>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("📋 **Mis Datos Registrados**")
        st.write(f"**Acudiente:** {st.session_state.papa_nombre}")
        st.write(f"**Deportista:** {st.session_state.hijo_nombre}")
        st.divider()
        if st.button("Salir del Portal", type="secondary", use_container_width=True):
            st.session_state.focus_vista = "inicio"
            st.session_state.papa_doc = ""
            st.rerun()

    try:
        db = conectar_focus_sheets()
        partidos_data = db.worksheet("PARTIDOS").get_all_records()
        
        mis_partidos = []
        for p in partidos_data:
            if str(p.get("Documento_Papa")).strip() == st.session_state.papa_doc:
                mis_partidos.append(p)
                
        if len(mis_partidos) == 0:
            st.info("⚽ No tienes registros de partidos asignados en este momento.")
        else:
            tab_grabados, tab_proximos = st.tabs(["🎥 Videos Grabados en la Nube", "📅 Próximas Grabaciones / Calendario"])
            
            # --- PADRES: VER VIDEOS GRABADOS ---
            with tab_grabados:
                hay_grabados = False
                for p in mis_partidos:
                    if str(p.get("Estatus_Grabacion")).strip().lower() == "grabado":
                        hay_grabados = True
                        pago = str(p.get("Estado_Pago")).strip().lower()
                        
                        if pago == "pagado":
                            st.markdown(f"""
                                <div class='card-pagado'>
                                    <span class='badge-pagado'>🟢 PAGADO</span>
                                    <span class='badge-status'>🎥 GRABADO</span>
                                    <h4 style='margin-top:10px; margin-bottom:5px; color:#0b132b;'>⚽ {p.get('Rival/Partido')}</h4>
                                    <p style='color:#777; font-size:13px; margin-bottom:15px;'>Fecha del encuentro: {p.get('Fecha')}</p>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            link_drive = str(p.get("Link_Download_Drive")).strip()
                            if link_drive and "http" in link_drive:
                                st.link_button(f"📥 DESCARGAR VIDEO - {p.get('Rival/Partido')}", link_drive, type="primary", use_container_width=True)
                            else:
                                st.info("El archivo de video se está subiendo a la nube. Estará disponible en breve.")
                            st.markdown("<br>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                                <div class='card-pendiente'>
                                    <span class='badge-pendiente'>🔴 PENDIENTE DE PAGO</span>
                                    <span class='badge-status'>🎥 GRABADO</span>
                                    <h4 style='margin-top:10px; margin-bottom:5px; color:#0b132b;'>⚽ {p.get('Rival/Partido')}</h4>
                                    <p style='color:#777; font-size:13px; margin-bottom:5px;'>Fecha del encuentro: {p.get('Fecha')}</p>
                                    <p style='color:#e71d36; font-size:13px; font-weight:bold;'>⚠️ El botón de descarga se habilitará automáticamente al confirmarse el pago en tesorería.</p>
                                </div>
                            """, unsafe_allow_html=True)
                            st.markdown("<br>", unsafe_allow_html=True)
                if not hay_grabados:
                    st.info("Aún no posees videos procesados en la plataforma.")
                    
            # --- PADRES: VER CALENDARIO ---
            with tab_proximos:
                hay_programados = False
                for p in mis_partidos:
                    if str(p.get("Estatus_Grabacion")).strip().lower() == "programado":
                        hay_programados = True
                        pago = str(p.get("Estado_Pago")).strip().lower()
                        badge_pago = "<span class='badge-pagado'>🟢 ABONADO</span>" if pago == "pagado" else "<span class='badge-pendiente'>🔴 PENDIENTE</span>"
                        
                        st.markdown(f"""
                            <div class='card-pagado' style='border-left: 6px solid #3a86ff;'>
                                {badge_pago}
                                <span class='badge-status' style='background-color:#e8f1f5; color:#3a86ff;'>📅 PROGRAMADO</span>
                                <h4 style='margin-top:10px; margin-bottom:5px; color:#0b132b;'>⚽ {p.get('Rival/Partido')}</h4>
                                <p style='color:#777; font-size:13px; margin-bottom:0px;'>📅 Fecha asignada para cobertura: <strong>{p.get('Fecha')}</strong></p>
                            </div>
                        """, unsafe_allow_html=True)
                if not hay_programados:
                    st.info("No hay partidos en la agenda de grabaciones para los próximos días.")
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")

# --- VISTA 4: AUTENTICACIÓN ADMINISTRATIVA ---
elif st.session_state.focus_vista == "login_admin":
    st.markdown("<h2 style='text-align: center;'>🔑 Acceso Administrativo - Focus</h2>", unsafe_allow_html=True)
    u_adm = st.text_input("Usuario Administrativo").lower().strip()
    p_adm = st.text_input("Contraseña de Acceso", type="password")
    
    if st.button("INGRESAR AL PANEL"):
        admins_focus = {"camilo": "Admin1", "diana": "Admin2"}
        if u_adm in admins_focus and p_adm == admins_focus[u_adm]:
            st.session_state.focus_vista = "panel_admin"
            st.rerun()
        else:
            st.error("Credenciales administrativas inválidas.")
            
    if st.button("Volver al Inicio"):
        st.session_state.focus_vista = "inicio"
        st.rerun()

# --- VISTA 5: PANEL DE CONTROL ADMINISTRATIVO EXCLUSIVO ---
elif st.session_state.focus_vista == "panel_admin":
    st.title("🛠️ Panel de Control - Focus Administrador")
    
    with st.sidebar:
        st.write("⚙️ **Sesión Admin Activa**")
        st.divider()
        if st.button("Cerrar Sesión Focus", type="primary", use_container_width=True):
            st.session_state.focus_vista = "inicio"
            st.rerun()

    t_adm_agenda, t_adm_padres, t_adm_control = st.tabs(["📅 Programar Partido", "👥 Registrar Padres", "⚡ Control de Grabaciones y Pagos"])

    # --- TAB ADMIN 1: AGENDAR/PROGRAMAR PARTIDOS ---
    with t_adm_agenda:
        st.subheader("📅 Programar nueva cobertura de grabación")
        try:
            db = conectar_focus_sheets()
            ws_u = db.worksheet("USUARIOS")
            padres_list = ws_u.get_all_records()
            
            opciones_padres = []
            for papa in padres_list:
                label = f"{papa.get('Nombre_Papa')} (Hijo: {papa.get('Hijo_Jugador')} - Doc: {papa.get('Documento')})"
                opciones_padres.append(label)
                
            if len(opciones_padres) == 0:
                st.warning("⚠️ Primero debes registrar padres de familia en la pestaña contigua para poder agendar partidos.")
            else:
                with st.form("form_add_partido"):
                    selected_papa_label = st.selectbox("Seleccionar Padre Acudiente", opciones_padres)
                    f_fecha = st.text_input("Fecha del Partido (DD/MM/AAAA u Hoy)")
                    f_rival = st.text_input("Partido / Nombre del Torneo y Rival (Ej: Accusport vs Nacional)")
                    f_grab = st.selectbox("Estatus Inicial de Grabación", ["Programado", "Grabado"])
                    f_pago = st.selectbox("Estado Inicial del Pago", ["Pendiente", "Pagado"])
                    f_link = st.text_input("Link de descarga de Google Drive (Dejar vacío si está programado)")
                    
                    btn_save_partido = st.form_submit_button("AGENDAR Y GUARDAR PARTIDO")
                    
                    if btn_save_partido:
                        partes = selected_papa_label.split("Doc: ")
                        doc_papa_final = partes[1].replace(")", "").strip()
                        
                        ws_p = db.worksheet("PARTIDOS")
                        ws_p.append_row([
                            doc_papa_final, f_fecha, f_rival, f_grab, f_pago, f_link
                        ])
                        st.success(f"✅ Partido contra '{f_rival}' agendado exitosamente.")
                        time.sleep(1); st.rerun()
        except Exception as e:
            st.error(f"Error en módulo de agenda: {e}")

    # --- TAB ADMIN 2: REGISTRAR NUEVOS USUARIOS/PADRES ---
    with t_adm_padres:
        st.subheader("👥 Registrar nuevo Padre de Familia / Usuario")
        with st.form("form_add_papa"):
            reg_doc = st.text_input("Número de Documento del Padre (Servirá de Login)").strip()
            reg_nombre = st.text_input("Nombre completo del Padre")
            reg_hijo = st.text_input("Nombre completo del Hijo / Deportista")
            reg_equipo = st.text_input("Categoría / Equipo al que pertenece")
            
            btn_save_papa = st.form_submit_button("REGISTRAR USUARIO PADRE")
            
            if btn_save_papa:
                if reg_doc and reg_nombre and reg_hijo:
                    try:
                        db = conectar_focus_sheets()
                        ws_u = db.worksheet("USUARIOS")
                        
                        rows_u_chk = ws_u.get_all_values()
                        existe_u = False
                        for row in rows_u_chk:
                            if len(row) > 0 and str(row[0]).strip() == reg_doc:
                                existe_u = True; break
                                
                        if existe_u:
                            st.error("❌ Este número de documento ya está registrado como un usuario de Focus.")
                        else:
                            ws_u.append_row([reg_doc, reg_nombre, reg_hijo, reg_equipo])
                            st.success(f"✅ Padre {reg_nombre} registrado con éxito en el sistema.")
                            time.sleep(1); st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("⚠️ Todos los campos son obligatorios para crear el usuario.")

    # --- TAB ADMIN 3: CONTROL INTERACTIVO DE ESTADOS Y LINKS ---
    with t_adm_control:
        st.subheader("⚡ Control Operativo de Grabaciones, Pagos y Carga de Links")
        try:
            db = conectar_focus_sheets()
            ws_p = db.worksheet("PARTIDOS")
            partidos_full = ws_p.get_all_values()
            
            if len(partidos_full) > 1:
                h_p = partidos_full[0]
                rows_p = partidos_full[1:]
                
                st.write("### 📜 Listado General de Agenda")
                st.dataframe(pd.DataFrame(rows_p, columns=h_p), use_container_width=True)
                st.divider()
                
                for i, r in enumerate(rows_rec if 'rows_rec' in locals() else rows_p):
                    row_sheet = i + 2  
                    
                    doc_p = r[0] if len(r) > 0 else "S/D"
                    fecha_p = r[1] if len(r) > 1 else "S/F"
                    rival_p = r[2] if len(r) > 2 else "Partido"
                    grab_p = r[3] if len(r) > 3 else "Programado"
                    pago_p = r[4] if len(r) > 4 else "Pendiente"
                    link_p = r[5] if len(r) > 5 else ""
                    
                    st.write(f"⚽ **{rival_p.upper()}** ({fecha_p}) | Papá ID: `{doc_p}`")
                    st.write(f"Estado de Grabación: `{grab_p}` | Estado de Pago: `{pago_p}`")
                    
                    c_b1, c_b2, c_in, c_b3 = st.columns([1, 1, 2.2, 0.8])
                    
                    if c_b1.button("🎥 GRABADO", key=f"f_grab_{i}"):
                        ws_p.update_cell(row_sheet, 4, "Grabado")
                        st.success("Grabación actualizada.")
                        time.sleep(0.5); st.rerun()
                        
                    if c_b2.button("🎥 PAGADO", key=f"f_pag_{i}"):
                        ws_p.update_cell(row_sheet, 5, "Pagado")
                        st.success("Pago verificado.")
                        time.sleep(0.5); st.rerun()
                        
                    new_link = c_in.text_input("Pegar Link Drive", value=link_p, key=f"f_lnk_in_{i}")
                    if c_b3.button("💾 LINK", key=f"f_lnk_btn_{i}"):
                        ws_p.update_cell(row_sheet, 6, new_link.strip())
                        st.success("Link guardado.")
                        time.sleep(0.5); st.rerun()
                    st.divider()
            else:
                st.info("No hay partidos registrados en la agenda del sistema actualmente.")
        except Exception as e:
            st.error(f"Error en panel interactivo: {e}")
