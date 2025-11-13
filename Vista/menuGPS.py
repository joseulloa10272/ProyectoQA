
import os, sys
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.gpsPersistencia import catalogos, cargarPosiciones
from Persistencia.contratosPersistencia import cargarContratos

def app(usuario: str):
    st.subheader("Seguimiento GPS")

    base = catalogos() or {"clientes": [], "estados": [], "contratos_ids": [], "activos": []}

    c1, c2, c3 = st.columns(3)
    with c1:
        f_cli = st.selectbox("Cliente", ["Todos"] + base["clientes"], key="gps_cli")

    # contratos por ID con etiqueta legible
    dfc = pd.DataFrame(cargarContratos())
    if f_cli and f_cli != "Todos":
        dfc = dfc[dfc["cliente"].astype(str).str.strip() == f_cli]
    if dfc.empty:
        dfc = pd.DataFrame([{"id":"", "cliente":""}])
    dfc["id"] = dfc["id"].astype(str).str.strip()
    id_to_label = {r["id"]: f"{r['id']} - {r['cliente']}" for _, r in dfc.iterrows()}
    contrato_ids = ["Todos"] + sorted(id_to_label.keys(), key=lambda x: (len(x), x)) if id_to_label else ["Todos"]

    with c2:
        sel_id = st.selectbox(
            "Contrato",
            contrato_ids,
            format_func=lambda v: "Todos" if v == "Todos" else id_to_label.get(v, v),
            key="gps_ctr_id"
        )

    with c3:
        f_est = st.selectbox("Estado", ["Todos"] + base["estados"], key="gps_est")

    # Cargar posiciones sin filtro por activo
    df = cargarPosiciones(
        f_cliente=f_cli,
        f_contrato=sel_id,        # aquí viaja el ID real del contrato
        f_estado=f_est,
        sync_desde_activos=True
    )

    if not df.empty:
        df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce")
        df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
        df = df.dropna(subset=["latitud","longitud"])
        lat0, lon0 = float(df["latitud"].mean()), float(df["longitud"].mean())
    else:
        lat0, lon0 = 9.7489, -83.7534

    m = folium.Map(location=[lat0, lon0], zoom_start=7, control_scale=True)
    for _, r in df.iterrows():
        folium.Marker(
            [float(r["latitud"]), float(r["longitud"])],
            tooltip=str(r.get("id_unico", "")),
            popup=folium.Popup(
                f"ID: {r.get('id_unico','')}<br>"
                f"Cliente: {r.get('cliente','')}<br>"
                f"Contrato: {r.get('contrato','')}<br>"
                f"Estado: {r.get('estado','')}<br>"
                f"TS: {r.get('ts','')}",
                max_width=360
            ),
            icon=folium.Icon(color="blue")
        ).add_to(m)

    st_folium(m, height=520, use_container_width=True)