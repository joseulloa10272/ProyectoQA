import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import json
import pandas as pd

from Persistencia.geocercasPersistencia import (
    cargarGeocercas, guardarGeocerca, eliminarGeocerca,
    cargarAlertas, evaluar_geocercas_y_alertar, cargarPosiciones,
)

def _center_from_df(df: pd.DataFrame):
    if df.empty:
        return 9.933, -84.083
    lat = pd.to_numeric(df["latitud"], errors="coerce").dropna()
    lon = pd.to_numeric(df["longitud"], errors="coerce").dropna()
    if len(lat) and len(lon):
        return float(lat.mean()), float(lon.mean())
    return 9.933, -84.083

def _shape_from_draw(res):
    """Extrae la geometría del último dibujo hecho en el mapa (círculo o polígono)."""
    if not res:
        return None

    # Se toman las últimas figuras dibujadas por el usuario
    obj = res.get("last_active_drawing") or res.get("last_object") or res.get("last_circle") or res.get("last_polygon")
    
    if not obj:
        return None

    gj = obj if isinstance(obj, dict) else {}
    gtype = gj.get("type") or (gj.get("geometry", {}) or {}).get("type")

    if gtype == "Feature":  # a veces viene como Feature
        geom = gj.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates")
    else:
        geom = gj.get("geometry", gj)
        coords = geom.get("coordinates")

    if str(gtype).lower() == "polygon":
        # Coordina el polígono: [[lon, lat], [lon, lat], ...]
        verts = [[c[1], c[0]] for c in coords[0]]  # Convertimos a [lat, lon]
        return {"type": "polygon", "vertices": verts}

    if str(gtype).lower() == "circle":
        # Para círculos, obtenemos el centro y el radio
        props = gj.get("properties", {})
        center = props.get("center") or props.get("circle_center") or [gj.get("lat", 0), gj.get("lng", 0)]
        radius = props.get("radius") or props.get("circle_radius") or 0
        return {"type": "circle", "center": [float(center[0]), float(center[1])], "radius_m": float(radius)}

    return None

def app(usuario=""):
    st.header("Geocercas y alertas de movimiento")

    tabs = st.tabs(["Configurar", "Monitoreo"])

    with tabs[0]:
        df_pos = cargarPosiciones(sync_desde_activos=True)
        
        with st.form("form_geocerca"):
            st.subheader("Nueva geocerca")
            colI, colD = st.columns([2, 1])
            with colI:
                lat0, lon0 = _center_from_df(df_pos)
                m = folium.Map(location=[lat0, lon0], zoom_start=8, tiles="CartoDB positron")
                Draw(
                    draw_options={
                        "polyline": False, "rectangle": False, "marker": False,
                        "polygon": True, "circle": True, "circlemarker": False
                    },
                    edit_options={"edit": True, "remove": True}
                ).add_to(m)
                res = st_folium(m, height=480, width=800, key="geo_cfg")
            with colD:
                nombre = st.text_input("Nombre de la geocerca")
                activos_sel = st.multiselect("Activos a vigilar", df_pos["id_activo"].astype(str).unique().tolist())
                emails = st.text_input("Destinatarios de alerta (separados por coma)", help="Se enviará correo al dispararse la geocerca.")
                activa = st.toggle("Activa", value=True)
                shape = _shape_from_draw(res)

                st.caption("Dibuja un polígono o un círculo en el mapa y completa los campos.")
                submitted = st.form_submit_button("Guardar geocerca", use_container_width=True)

            if submitted:
              shape = _shape_from_draw(res)
              if not shape:
                  st.error("No se detectó una figura en el mapa; dibuja un círculo o polígono y vuelve a intentar.")
              elif not nombre.strip():
                  st.error("Asigna un nombre a la geocerca.")
              elif not activos_sel:
                  st.error("Selecciona al menos un activo para vigilar.")
              else:
                  reg = {
                      "id_geocerca": "",
                      "nombre": nombre.strip(),
                      "tipo": shape["type"],
                      "activos": activos_sel,
                      "emails": emails,
                      "shape_json": shape,
                      "activa": activa,
                      "creado_por": usuario or "admin"
                  }
                  out = guardarGeocerca(reg)
                  st.success(f"Geocerca '{out['nombre']}' guardada ({out['id_geocerca']}).")
                  
                  # Verificación de que los datos están guardados
                  st.write("Geocerca guardada:", out)
                  st.rerun()

        st.markdown("---")
        st.subheader("Geocercas registradas")
        df_geo = cargarGeocercas()
        if df_geo.empty:
            st.info("Aún no hay geocercas.")
        else:
            show = df_geo.copy()
            show["shape_json"] = show["shape_json"].astype(str).str.slice(0, 60) + "..."
            st.dataframe(show, use_container_width=True, hide_index=True)
            c1, c2 = st.columns(2)
            with c1:
                del_id = st.text_input("ID a eliminar")
                if st.button("Eliminar", type="secondary"):
                    if del_id.strip() and eliminarGeocerca(del_id.strip()):
                        st.success("Geocerca eliminada.")
                    else:
                        st.warning("ID no encontrado.")
            with c2:
                st.caption("Para activar/desactivar una geocerca edita el registro guardando el mismo ID.")
    
    # ============= TAB MONITOREO =============
    with tabs[1]:
        emitir = st.toggle("Enviar correos al disparar", value=True)

        df_pos = cargarPosiciones(sync_desde_activos=True)
        df_geo = cargarGeocercas()
        lat0, lon0 = _center_from_df(df_pos)

        # Mapa con geocercas y activos
        m = folium.Map(location=[lat0, lon0], zoom_start=8, tiles="CartoDB positron")
        # dibujar geocercas
        for _, g in df_geo.iterrows():
            sh = json.loads(g["shape_json"]) if isinstance(g["shape_json"], str) else g["shape_json"]
            if not isinstance(sh, dict):
                continue
            if sh.get("type") == "circle":
                center = sh.get("center", [0,0]); radius = float(sh.get("radius_m", 0))
                folium.Circle(location=center, radius=radius, color="#0d6efd", fill=True, fill_opacity=0.1,
                              tooltip=f"{g['nombre']} ({g['modo']})").add_to(m)
            elif sh.get("type") == "polygon":
                folium.Polygon(locations=sh.get("vertices", []), color="#198754", fill=True, fill_opacity=0.1,
                               tooltip=f"{g['nombre']} ({g['modo']})").add_to(m)

        # dibujar activos
        for _, r in df_pos.dropna(subset=["latitud", "longitud"]).iterrows():
            folium.Marker([float(r["latitud"]), float(r["longitud"])],
                          tooltip=f"{r['id_activo']}",
                          popup=folium.Popup(
                              f"<b>Activo:</b> {r['id_activo']}<br>"
                              f"<b>Cliente:</b> {r.get('cliente', '')}<br>"
                              f"<b>Contrato:</b> {r.get('contrato', '')}<br>"
                              f"<b>Estado:</b> {r.get('estado', '')}<br>"
                              f"<b>Actualizado:</b> {r.get('ultima_actualizacion', '')}", max_width=300)).add_to(m)

        st_folium(m, height=480, width=800, key="geo_mon")

        # Evaluación y panel de alertas
        alertas = evaluar_geocercas_y_alertar(enviar_correos=emitir)
        df_alert = cargarAlertas().sort_values("ts", ascending=False)
        if alertas:
            st.success(f"Se registraron {len(alertas)} alerta(s) en esta iteración.")
        st.subheader("Histórico de alertas")
        st.dataframe(df_alert, use_container_width=True, hide_index=True)
        st.caption("La evaluación revisa transiciones de entrada/salida por activo y geocerca; el envío por correo utiliza tus credenciales de notificaciones.")
