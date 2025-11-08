# Vista/menuGPS.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH = True
except Exception:
    _AUTOREFRESH = False

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ✅ Import correcto según Persistencia/gpsPersistencia.py
from Persistencia.gpsPersistencia import cargarPosiciones

def _centro(df):
    try:
        lat = pd.to_numeric(df["latitud"], errors="coerce").dropna()
        lon = pd.to_numeric(df["longitud"], errors="coerce").dropna()
        if len(lat) and len(lon):
            return float(lat.mean()), float(lon.mean())
    except Exception:
        pass
    return 9.75, -83.75  # Centro aproximado de CR

def app(usuario: str = ""):
    st.header("Seguimiento GPS de activos")
    st.caption("Visualización de posiciones con actualización periódica, filtros por cliente, contrato y estado, e indicador de coordenadas vigentes")

    intervalo = st.select_slider("Intervalo de actualización", options=[2, 5, 10, 15, 30], value=5, help="segundos")
    if _AUTOREFRESH:
        st_autorefresh(interval=intervalo * 1000, key="gps_refresh")

    # ✅ Uso del nombre de función correcto
    df = cargarPosiciones()
    if df is None or len(df) == 0:
        st.warning("Aún no hay posiciones registradas")
        return

    # Normalización
    df = df.copy()
    df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    df["cliente"] = df.get("cliente", "").astype(str)
    df["contrato"] = df.get("contrato", "").astype(str)
    df["estado"] = df.get("estado", "").astype(str)
    df = df.dropna(subset=["latitud","longitud"])

    if df.empty:
        st.info("No hay activos con coordenadas válidas")
        return

    # Filtros
    c1, c2, c3 = st.columns(3)
    with c1:
        f_cli = st.selectbox("Cliente", ["Todos"] + sorted([x for x in df["cliente"].unique() if x]))
    with c2:
        f_con = st.selectbox("Contrato", ["Todos"] + sorted([x for x in df["contrato"].unique() if x]))
    with c3:
        f_est = st.selectbox("Estado", ["Todos"] + sorted([x for x in df["estado"].unique() if x]))

    df_f = df.copy()
    if f_cli != "Todos":
        df_f = df_f[df_f["cliente"] == f_cli]
    if f_con != "Todos":
        df_f = df_f[df_f["contrato"] == f_con]
    if f_est != "Todos":
        df_f = df_f[df_f["estado"] == f_est]

    if df_f.empty:
        st.info("No hay activos que cumplan los filtros seleccionados")
        return

    # Indicador de coordenadas vivas para un activo puntual
    activos = df_f["id_activo"].astype(str).unique().tolist()
    elegido = st.selectbox("Activo a monitorear", activos)
    fila = df_f[df_f["id_activo"].astype(str) == str(elegido)].tail(1)
    if not fila.empty:
        lat = float(fila.iloc[0]["latitud"]); lon = float(fila.iloc[0]["longitud"])
        ts = str(fila.iloc[0].get("ultima_actualizacion",""))
        st.info(f"Coordenadas actuales de {elegido}: lat {lat:.6f}, lon {lon:.6f} — última actualización: {ts}")

    # Mapa
    lat_c, lon_c = _centro(df_f)
    m = folium.Map(location=[lat_c, lon_c], zoom_start=8, tiles="CartoDB positron")
    for _, r in df_f.iterrows():
        popup = folium.Popup(
            f"<b>Activo:</b> {r['id_activo']}<br>"
            f"<b>Cliente:</b> {r['cliente']}<br>"
            f"<b>Contrato:</b> {r['contrato']}<br>"
            f"<b>Estado:</b> {r['estado']}<br>"
            f"<b>Lat:</b> {float(r['latitud']):.6f} — <b>Lon:</b> {float(r['longitud']):.6f}<br>"
            f"<b>Actualizado:</b> {r.get('ultima_actualizacion','')}",
            max_width=300
        )
        folium.Marker(
            [float(r["latitud"]), float(r["longitud"])],
            tooltip=f"{r['id_activo']}",
            popup=popup,
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    st_folium(m, height=480, width=800, key="gps_map")

    # Tabla compacta
    st.markdown("#### Posiciones")
    st.dataframe(
        df_f[["id_activo","cliente","contrato","estado","latitud","longitud","ultima_actualizacion"]]
        .sort_values("ultima_actualizacion", ascending=False),
        use_container_width=True
    )