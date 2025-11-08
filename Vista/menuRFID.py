import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Persistencia.rfidPersistencia import obtenerActivoPorTag, vincularTagAActivo, cargarMapaRFID, tagDisponible
from Persistencia.lectoresRFIDPersistencia import cargarLectores, registrarLector, obtenerLector
from Persistencia.escaneosRFIDPersistencia import registrarEscaneo, cargarEscaneos
from Persistencia.activosPersistencia import cargarActivosDf

def app(usuario: str = ""):
    st.header("Integración RFID")
    st.caption("Lectura de etiquetas, vinculación con activos y registro de escaneos con fecha, hora y ubicación")

    # Lectores registrados
    df_lect = cargarLectores()
    with st.expander("Registrar lector", expanded=df_lect.empty):
        rid = st.text_input("Identificador del lector")
        tipo = st.selectbox("Tipo de lector", ["fijo","movil","serial","http"])
        c1, c2 = st.columns(2)
        with c1:
            lat = st.number_input("Latitud fija (opcional)", format="%.6f")
        with c2:
            lon = st.number_input("Longitud fija (opcional)", format="%.6f")
        zona = st.text_input("Zona/Ubicación")
        desc = st.text_input("Descripción")
        ip = st.text_input("IP/Endpoint (opcional)")
        meta = st.text_area("Metadatos (opcional)")
        if st.button("Guardar lector"):
            ok = registrarLector(rid, tipo, desc, lat if lat else None, lon if lon else None, zona, ip, meta)
            st.success("Lector registrado") if ok else st.error("Ya existe un lector con ese ID")

    df_lect = cargarLectores()
    if df_lect.empty:
        st.info("Agrega al menos un lector para continuar")
        return

    lector_ids = df_lect["reader_id"].tolist()
    lector_sel = st.selectbox("Lector activo", lector_ids)
    info_lector = obtenerLector(lector_sel) or {}
    tipo_lector = str(info_lector.get("tipo_lector","movil")).lower()

    st.subheader("Escaneo")
    with st.form("form_scan", clear_on_submit=True):
        tag = st.text_input("Entrada del lector (EPC / ID)", placeholder="Enfoca aquí y escanea")
        evento = st.selectbox("Clasificación del evento", ["scan","entrada","salida","ubicacion"])
        submitted = st.form_submit_button("Registrar escaneo")

    lat_in, lon_in = None, None
    if tipo_lector == "movil":
        st.markdown("### Ubicación del escaneo")
        if "lat_sel" not in st.session_state: st.session_state.lat_sel = None
        if "lon_sel" not in st.session_state: st.session_state.lon_sel = None
        center = [st.session_state.lat_sel or 9.75, st.session_state.lon_sel or -83.75]
        m = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")
        if st.session_state.lat_sel and st.session_state.lon_sel:
            folium.Marker([st.session_state.lat_sel, st.session_state.lon_sel]).add_to(m)
        map_r = st_folium(m, height=300, key="rfid_map")
        if map_r and map_r.get("last_clicked"):
            st.session_state.lat_sel = float(map_r["last_clicked"]["lat"])
            st.session_state.lon_sel = float(map_r["last_clicked"]["lng"])
        lat_in = st.session_state.lat_sel
        lon_in = st.session_state.lon_sel
    else:
        try:
            lat_in = float(info_lector.get("latitud")) if info_lector.get("latitud") not in (None,"") else None
            lon_in = float(info_lector.get("longitud")) if info_lector.get("longitud") not in (None,"") else None
        except Exception:
            lat_in, lon_in = None, None

    if submitted and tag.strip():
        id_unico = obtenerActivoPorTag(tag)
        if not id_unico:
            st.warning("Etiqueta sin vínculo con activo")
            df_act = cargarActivosDf()
            if df_act.empty:
                st.stop()
            opciones = (df_act["id_unico"] + " — " + df_act["modelo"]).tolist()
            destino = st.selectbox("Vincular a activo", opciones, key="link_select")
            if st.button("Vincular etiqueta"):
                elegido = destino.split(" — ")[0].strip()
                if tagDisponible(tag) and vincularTagAActivo(tag, elegido):
                    st.success(f"Tag {tag} vinculado a {elegido}")
                else:
                    st.error("El tag ya se encuentra vinculado")
            st.stop()

        zona = str(info_lector.get("zona",""))
        reg = registrarEscaneo(tag, lector_sel, tipo_lector, zona, lat_in, lon_in, usuario=usuario, evento=evento)
        st.success(f"Escaneo registrado para activo {reg['id_unico']}")

    st.subheader("Últimos escaneos")
    df_scan = cargarEscaneos().sort_values("id_scan", ascending=False).head(50)
    st.dataframe(df_scan, use_container_width=True)

    with st.expander("Mapa de tags ↔ activos"):
        st.dataframe(cargarMapaRFID(), use_container_width=True)