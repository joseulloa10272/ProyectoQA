# Vista/menuGPS.py
import streamlit as st
import pandas as pd
import folium
import sys
import os
from streamlit_folium import st_folium

try:
    from streamlit_autorefresh import st_autorefresh
    _AR = True
except Exception:
    _AR = False

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.gpsPersistencia import cargarPosiciones, catalogos, contratos_norm


def _centro(df: pd.DataFrame) -> tuple[float, float]:
    lat = pd.to_numeric(df.get("latitud", pd.Series(dtype=float)), errors="coerce").dropna()
    lon = pd.to_numeric(df.get("longitud", pd.Series(dtype=float)), errors="coerce").dropna()
    if len(lat) and len(lon):
        return float(lat.mean()), float(lon.mean())
    return 9.75, -83.75  # CR fallback


def app(usuario: str = ""):
    st.header("Seguimiento GPS de activos")

    # Intervalo de actualización
    intervalo = st.select_slider(
        "Intervalo de actualización",
        options=[2, 5, 10, 15, 30],
        value=5,
        key="gps_intervalo"
    )
    if _AR:
        st_autorefresh(interval=intervalo * 1000, key="gps_autorefresh")

    # Catálogos estrictos desde contratos y dataframe para filtros dependientes
    cats = catalogos()
    dfc = contratos_norm()

    # Filtros dependientes
    c1, c2, c3 = st.columns(3)
    with c1:
        cli = st.selectbox("Cliente", ["Todos"] + cats["clientes"], key="gps_filtro_cliente")

    # contratos válidos según cliente
    if cli == "Todos":
        contratos_cli = sorted(dfc["id_contrato"].unique().tolist())
        estados_cli = sorted(dfc["estado"].unique().tolist())
    else:
        sub = dfc[dfc["cliente"] == cli]
        contratos_cli = sorted(sub["id_contrato"].unique().tolist())
        estados_cli = sorted(sub["estado"].unique().tolist())

    with c2:
        con = st.selectbox("Contrato", ["Todos"] + contratos_cli, key="gps_filtro_contrato")

    # estados válidos según cliente y contrato
    if con == "Todos":
        sub_est = dfc if cli == "Todos" else dfc[dfc["cliente"] == cli]
        estados_list = sorted(sub_est["estado"].unique().tolist())
    else:
        sub_est = dfc[dfc["id_contrato"] == con]
        estados_list = sorted(sub_est["estado"].unique().tolist())

    with c3:
        est = st.selectbox("Estado", ["Todos"] + estados_list, key="gps_filtro_estado")

    # Cargar posiciones ya sincronizadas contra contratos
    df = cargarPosiciones(sync_desde_activos=True)
    # justo después de: df = cargarPosiciones(sync_desde_activos=True)
    if "ultima_actualizacion" not in df.columns and "fecha" in df.columns:
        df["ultima_actualizacion"] = df["fecha"]
    if df is None or df.empty:
        st.info("No hay registros para mostrar.")
        return

    # Aplicar filtros coherentes con contratos
    if cli != "Todos":
        df = df[df["cliente"] == cli]
    if con != "Todos":
        df = df[df["contrato"] == con]
    if est != "Todos":
        df = df[df["estado"] == est]

    if df.empty:
        st.info("Sin coincidencias para los filtros.")
        return

    # Selector de activo
    activos = df["id_activo"].astype(str).unique().tolist()
    elegido = st.selectbox("Activo a monitorear", activos, key="gps_activo_sel")

    fila = df[df["id_activo"].astype(str) == str(elegido)].tail(1)
    if not fila.empty:
        lat_sel = pd.to_numeric(fila.iloc[0]["latitud"], errors="coerce")
        lon_sel = pd.to_numeric(fila.iloc[0]["longitud"], errors="coerce")
        ts = str(fila.iloc[0].get("ultima_actualizacion", ""))
        st.info(f"Coordenadas actuales de {elegido}: lat {float(lat_sel):.6f}, lon {float(lon_sel):.6f} — última actualización: {ts}")

    # Mapa
    lat_c, lon_c = _centro(df)
    mapa = folium.Map(location=[lat_c, lon_c], zoom_start=8, tiles="CartoDB positron")

    for _, r in df.dropna(subset=["latitud", "longitud"]).iterrows():
        try:
            lat = float(r["latitud"]); lon = float(r["longitud"])
        except Exception:
            continue
        folium.Marker(
            [lat, lon],
            tooltip=f"{r['id_activo']}",
            popup=folium.Popup(
                f"<b>Activo:</b> {r.get('id_activo','')}<br>"
                f"<b>Cliente:</b> {r.get('cliente','')}<br>"
                f"<b>Contrato:</b> {r.get('contrato','')}<br>"
                f"<b>Estado:</b> {r.get('estado','')}<br>"
                f"<b>Actualizado:</b> {r.get('ultima_actualizacion','')}",
                max_width=320
            )
        ).add_to(mapa)

    st_folium(mapa, height=480, width=800, key="gps_map")

    # Tabla
    st.markdown("#### Posiciones")
    cols_show = ["id_activo", "cliente", "contrato", "estado", "latitud", "longitud", "ultima_actualizacion"]
    df_show = df[cols_show].copy()
    df_show["__ts"] = pd.to_datetime(df_show["ultima_actualizacion"], errors="coerce")
    df_show = df_show.sort_values("__ts", ascending=False, na_position="last").drop(columns="__ts")
    st.dataframe(df_show, use_container_width=True)