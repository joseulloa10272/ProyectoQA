# Vista/menuGeocercas.py
import os, sys, json, ast, random, string
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw, MousePosition

# Rutas de import estables
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Persistencia / servicios base
from Persistencia.gpsPersistencia import cargarPosiciones
from Persistencia.activosPersistencia import cargarActivosDf

# Geocercas: API compatible con la versión robusta
from Persistencia.geocercasPersistencia import (
    obtenerGeocercas,                 # -> DataFrame con columnas GEO_COLS
    guardarGeocerca,                  # firma extendida; si no, se intenta la simple (nombre, coords)
    evaluar_posiciones_y_generar_alertas,  # enviar_correo: bool, usuario: str|None, destinatario: str|None
)

# =============== Utilitarios ===============

def _fallback_df(df, cols):
    """Devuelve df si no es None; si es None, entrega un DataFrame vacío con las columnas dadas."""
    if df is None:
        return pd.DataFrame(columns=cols)
    return df

def _resolve_user_email(usuario: str) -> str | None:
    try:
        from Persistencia.usuarioPersistencia import obtenerEmailUsuario as _get
        return _get(usuario)
    except Exception:
        try:
            from Persistencia.usuarioPersistencia import obtenerCorreoUsuario as _get_alt
            return _get_alt(usuario)
        except Exception:
            return None

def _id_random(prefix="G") -> str:
    suf = ''.join(random.choices(string.digits, k=6))
    return f"{prefix}{suf}"

def _activos_catalogo() -> pd.DataFrame:
    """
    Devuelve un catálogo compacto de activos con columnas:
    id, id_unico, label  — label = '<id_unico> - <modelo> (<cliente>)'.
    """
    df = cargarActivosDf()
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "id_unico", "label"])
    df = df.copy()
    for c in ("id", "id_unico"):
        df[c] = df.get(c, "").astype(str).str.strip()
    df["modelo"]  = df.get("modelo", "").astype(str)
    df["cliente"] = df.get("cliente", "").astype(str)
    df["label"] = df.apply(
        lambda r: f"{r['id_unico']} - {r['modelo']}"
                  + (f" ({r['cliente']})" if r["cliente"].strip() else ""),
        axis=1
    )
    return df[["id", "id_unico", "label"]]

def _activos_df() -> pd.DataFrame:
    df = cargarActivosDf()
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "id_unico", "modelo", "cliente", "label"])
    df = df.copy()
    df["id"] = df["id"].astype(str).str.strip()
    df["id_unico"] = df["id_unico"].astype(str).str.strip()
    df["modelo"] = df.get("modelo", "").astype(str)
    df["cliente"] = df.get("cliente", "").astype(str)
    df["label"] = df.apply(
        lambda r: f"{r['id_unico']} - {r['modelo']}" + (f" ({r['cliente']})" if r["cliente"].strip() else ""),
        axis=1
    )
    return df[["id", "id_unico", "label"]]

def _posiciones_df() -> pd.DataFrame:
    df = cargarPosiciones(sync_desde_activos=True)
    if df is None or df.empty:
        return pd.DataFrame(columns=["id_activo", "latitud", "longitud"])
    df = df.copy()
    for c in ("id_activo", "latitud", "longitud"):
        if c not in df.columns:
            df[c] = pd.NA
    df["id_activo"] = df["id_activo"].astype(str).str.strip()
    df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    return df.dropna(subset=["latitud", "longitud"])

def _geos_df() -> pd.DataFrame:
    df = obtenerGeocercas()
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df or [])
    if df.empty:
        return pd.DataFrame(columns=["id_geocerca","nombre","tipo","activos","shape_json","activa"])
    for c, d in [("id_geocerca",""),("nombre",""),("tipo","polygon"),("activos",""),("shape_json",""),("activa",True)]:
        if c not in df.columns:
            df[c] = d
    return df[["id_geocerca","nombre","tipo","activos","shape_json","activa"]].fillna("")

def _parse_activos_list(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if not isinstance(raw, str) or not raw.strip():
        return []
    s = raw.strip()
    try:
        val = json.loads(s)
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
    except Exception:
        pass
    try:
        val = ast.literal_eval(s)
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
    except Exception:
        pass
    s = s.replace(";", ",")
    return [p.strip().strip("'\"") for p in s.split(",") if p.strip()]

def _shape_to_latlon(raw) -> list[tuple[float,float]]:
    """Acepta dict o str con 'coordinates'; devuelve [(lat, lon), ...]."""
    obj = None
    if isinstance(raw, dict):
        obj = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            obj = json.loads(raw)
        except Exception:
            try:
                obj = ast.literal_eval(raw)
            except Exception:
                obj = None
    if obj is None:
        return []
    coords = None
    if isinstance(obj, dict):
        if "coordinates" in obj:
            coords = obj["coordinates"]
        elif "geometry" in obj and isinstance(obj["geometry"], dict):
            coords = obj["geometry"].get("coordinates")
    elif isinstance(obj, list):
        coords = obj
    if coords is None:
        return []
    pts = coords[0] if isinstance(coords, list) and coords and isinstance(coords[0], list) and len(coords) == 1 else coords
    latlon = []
    for p in pts:
        try:
            a, b = float(p[0]), float(p[1])
            if -180.0 <= a <= 180.0 and -90.0 <= b <= 90.0:  # [lon, lat]
                latlon.append((b, a))
            else:
                latlon.append((a, b))
        except Exception:
            continue
    return latlon

def _point_in_poly(lat, lon, polygon_latlon: list[tuple[float,float]]) -> bool:
    if not polygon_latlon:
        return False
    x, y = lon, lat
    inside = False
    n = len(polygon_latlon)
    for i in range(n):
        lat_i, lon_i = polygon_latlon[i]
        lat_j, lon_j = polygon_latlon[(i - 1) % n]
        xi, yi = lon_i, lat_i
        xj, yj = lon_j, lat_j
        inter = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi)
        inside = not inside if inter else inside
    return inside

def _activos_lookup():
    df = cargarActivosDf()
    if df is None or df.empty:
        return {}, pd.DataFrame()
    df = df.copy()
    df["label"] = df.apply(
        lambda r: f"{str(r.get('id_unico','')).strip()} - {str(r.get('modelo','')).strip()}"
                  + (f" ({str(r.get('cliente','')).strip()})" if str(r.get('cliente','')).strip() else ""),
        axis=1
    )
    idx = {str(r["id"]).strip(): r["label"] for _, r in df.iterrows()}
    for _, r in df.iterrows():
        idx[str(r["id_unico"]).strip()] = r["label"]  # permite buscar por id_unico
    return idx, df

# =============== Pestaña: Configurar ===============
def _tab_configurar(usuario: str):
    st.subheader("Configurar geocerca")

    m = folium.Map(location=[9.7489, -83.7534], zoom_start=7, control_scale=True)
    Draw(
        draw_options={
            "polyline": False, "rectangle": False, "circle": False, "circlemarker": False, "marker": False,
            "polygon": {"allowIntersection": False, "showArea": True, "shapeOptions": {"color": "#2dc937"}}
        },
        edit_options={"edit": True, "remove": True}
    ).add_to(m)
    MousePosition().add_to(m)

    res = st_folium(
        m,
        height=520,
        use_container_width=True,
        returned_objects=["last_active_drawing", "all_drawings"],
        key="geo_cfg_map",
    )

    dfA = _activos_df()
    opciones = dfA["label"].tolist()
    sel = st.multiselect("Activos vigilados", options=opciones, key="geo_cfg_activos")
    ids_unicos = []
    if sel:
        mapa = dict(zip(dfA["label"], dfA["id_unico"]))
        ids_unicos = list({mapa[s] for s in sel if s in mapa})

    nombre = st.text_input("Nombre", key="geo_cfg_nombre")
    activa = st.toggle("Activa", value=True, key="geo_cfg_activa")

    coords = []
    try:
        feat = res.get("last_active_drawing") or {}
        if not feat and isinstance(res.get("all_drawings"), list) and res["all_drawings"]:
            feat = res["all_drawings"][-1]
        if feat:
            gj = feat.get("geometry") or feat
            raw = gj.get("coordinates")
            if raw:
                inner = raw[0] if isinstance(raw[0], list) else raw
                coords = [(pt[1], pt[0]) for pt in inner if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    except Exception:
        coords = []

    st.caption("Dibuja un polígono, indica el nombre y selecciona los activos a vigilar")

    if st.button("Guardar", type="primary", key="geo_cfg_guardar"):
        if not nombre.strip():
            st.error("El nombre es obligatorio.")
            return
        if len(coords) < 3:
            st.error("La geocerca requiere al menos tres puntos.")
            return
        if not ids_unicos:
            st.error("Selecciona al menos un activo.")
            return

        shape_json = {"type": "Polygon", "coordinates": [[ [lon, lat] for lat, lon in coords ]]}
        try:
            guardarGeocerca(
                _id_random(),                           # id_geocerca
                nombre.strip(),                         # nombre
                "polygon",                              # tipo
                "",                                     # cliente
                "",                                     # contrato
                json.dumps(ids_unicos, ensure_ascii=False),  # activos
                "auto",                                 # modo (compatibilidad)
                "",                                     # emails (se usará el email del usuario al disparar)
                json.dumps(shape_json, ensure_ascii=False),  # shape_json
                bool(activa),                           # activa
                usuario,                                # creado_por
            )
            st.success("Geocerca guardada.")
            st.rerun()
        except TypeError:
            guardarGeocerca(nombre.strip(), coords)
            st.success("Geocerca guardada.")
            st.rerun()
        except Exception as e:
            st.error(f"No se guardó la geocerca: {e}")

    dfG = _geos_df()
    if not dfG.empty:
        aux = dfG.copy()
        aux["activos"] = aux["activos"].map(lambda x: ", ".join(_parse_activos_list(x)) if str(x).strip() else "")
        st.markdown("---")
        st.subheader("Geocercas registradas")
        st.dataframe(aux[["id_geocerca","nombre","tipo","activos","activa"]],
                     use_container_width=True, hide_index=True)

# =============== Pestaña: Monitoreo ===============
# =============== Pestaña: Monitoreo ===============
def _tab_monitoreo(usuario: str):
    import hashlib

    # opcional: si existe el helper de correo lo usamos para el envío inmediato de resumen
    try:
        from Persistencia.notificacionesEmail import enviar_email as _enviar_mail_directo
    except Exception:
        _enviar_mail_directo = None

    st.subheader("Monitoreo")

    df_geo = _geos_df()
    if df_geo.empty:
        st.info("No hay geocercas configuradas.")
        return

    # selector de geocercas por nombre [id]
    df_geo = df_geo.copy()
    df_geo["opcion"] = df_geo.apply(lambda r: f"{r['nombre']} [{r['id_geocerca']}]", axis=1)
    elegidas = st.multiselect(
        "Geocercas a monitorear",
        df_geo["opcion"].tolist(),
        default=[],
        key="geo_sel_mon",
        help="Selecciona una o más geocercas para iniciar el monitoreo."
    )
    ids_geo = df_geo[df_geo["opcion"].isin(elegidas)]["id_geocerca"].astype(str).tolist()
    if not ids_geo:
        st.info("Selecciona al menos una geocerca para continuar.")
        return

    # correo del usuario (solo visual)
    destinatario = _resolve_user_email(usuario or "") or ""
    st.text_input("Correo de notificación", value=(destinatario or "— sin correo configurado —"), disabled=True)

    # refresco de estado y de historial sin disparar correo (backend mantiene transiciones)
    try:
        df_alertas = evaluar_posiciones_y_generar_alertas(
            enviar_correo=False, usuario=usuario, destinatario=(destinatario or None), ids_geocerca=ids_geo
        )
    except TypeError:
        df_alertas = evaluar_posiciones_y_generar_alertas(enviar_correo=False, usuario=usuario, destinatario=(destinatario or None))

    # catálogo y mapeos
    dfA_full = cargarActivosDf()
    if dfA_full is None or dfA_full.empty:
        dfA_full = pd.DataFrame(columns=["id","id_unico","modelo","cliente"])
    dfA_full = dfA_full.copy()
    dfA_full["id"] = dfA_full.get("id","").astype(str)
    dfA_full["id_unico"] = dfA_full.get("id_unico","").astype(str)
    dfA_full["modelo"] = dfA_full.get("modelo","").astype(str)
    dfA_full["cliente"] = dfA_full.get("cliente","").astype(str)
    dfA_full["label"] = dfA_full.apply(
        lambda r: f"{r['id_unico']} - {r['modelo']}" + (f" ({r['cliente']})" if r["cliente"].strip() else ""), axis=1
    )
    map_id_to_unico    = dict(zip(dfA_full["id"], dfA_full["id_unico"]))
    map_unico_to_id    = dict(zip(dfA_full["id_unico"], dfA_full["id"]))
    map_unico_to_label = dict(zip(dfA_full["id_unico"], dfA_full["label"]))
    map_id_to_label    = dict(zip(dfA_full["id"], dfA_full["label"]))

    # universo de activos asociados a las geocercas elegidas (sin que el usuario deba elegir)
    universe_unico = set()
    for _, g in df_geo[df_geo["id_geocerca"].isin(ids_geo)].iterrows():
        raw = g.get("activos","[]")
        try:
            lista = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            lista = [t.strip() for t in str(raw).replace(";",",").split(",") if t.strip()]
        for t in lista:
            tok = str(t).split(" - ")[0].strip()
            if tok in map_unico_to_id:
                universe_unico.add(tok)
            elif tok in map_id_to_unico:
                universe_unico.add(map_id_to_unico[tok])
            else:
                universe_unico.add(tok)

    if not universe_unico:
        st.info("Las geocercas seleccionadas no tienen activos asociados.")
        return

    ids_id_sel = [map_unico_to_id.get(u, u) for u in sorted(universe_unico)]

    # mapa y evaluación de “fuera vs dentro” en tiempo real
    df_pos = _posiciones_df()
    lat0 = float(pd.to_numeric(df_pos["latitud"], errors="coerce").mean()) if not df_pos.empty else 9.7489
    lon0 = float(pd.to_numeric(df_pos["longitud"], errors="coerce").mean()) if not df_pos.empty else -83.7534
    m = folium.Map(location=[lat0, lon0], zoom_start=7, control_scale=True)

    filas_resumen, fuera_now = [], []
    for _, g in df_geo[df_geo["id_geocerca"].isin(ids_geo)].iterrows():
        latlon = _shape_to_latlon(g.get("shape_json",""))
        if latlon:
            folium.PolyLine([[la, lo] for la, lo in latlon], color="green", weight=3).add_to(m)

        sub_pos = df_pos[df_pos["id_activo"].astype(str).isin(ids_id_sel)].copy()
        for _, r in sub_pos.iterrows():
            lat, lon = float(r["latitud"]), float(r["longitud"])
            estado = "Dentro" if _point_in_poly(lat, lon, latlon) else "Fuera"
            label  = map_id_to_label.get(str(r["id_activo"]), map_unico_to_label.get(map_id_to_unico.get(str(r["id_activo"]),""), str(r["id_activo"])))
            filas_resumen.append({"geocerca": g["nombre"], "id_activo": str(r["id_activo"]), "activo": label, "estado": estado})
            if estado == "Fuera":
                fuera_now.append({
                    "geocerca": g["nombre"],
                    "id_activo": str(r["id_activo"]),
                    "id_unico": map_id_to_unico.get(str(r["id_activo"]), ""),
                    "activo": label,
                })
            folium.Marker(
                [lat, lon],
                tooltip=label,
                popup=folium.Popup(f"<b>Activo:</b> {label}<br><b>Geocerca:</b> {g['nombre']}<br><b>Estado:</b> {estado}", max_width=420),
                icon=folium.Icon(color=("green" if estado == "Dentro" else "red"), icon="info-sign"),
            ).add_to(m)

    st.markdown("**Activos seleccionados y su asociación**")
    if filas_resumen:
        st.dataframe(pd.DataFrame(filas_resumen), use_container_width=True, hide_index=True, height=220)

    # aviso y envío automático al detectar “fuera”
    if fuera_now:
        st.warning(f"Se detectaron {len(fuera_now)} activos fuera de su geocerca. Se enviará una notificación automática al correo mostrado.")
        # clave para evitar reenvíos en la misma selección/estado
        key_raw = json.dumps({
            "geos": sorted(ids_geo),
            "out": sorted([(f["id_unico"] or f["id_activo"], f["geocerca"]) for f in fuera_now])
        }, ensure_ascii=False)
        key_hash = hashlib.sha1(key_raw.encode("utf-8")).hexdigest()
        if st.session_state.get("geo_last_send_key") != key_hash and destinatario:
            # 1) refresca transiciones en backend y permite envío por transición si aplica
            try:
                evaluar_posiciones_y_generar_alertas(
                    enviar_correo=True, usuario=usuario, destinatario=destinatario, ids_geocerca=ids_geo
                )
            except TypeError:
                evaluar_posiciones_y_generar_alertas(enviar_correo=True, usuario=usuario, destinatario=destinatario)
            # 2) envía resumen inmediato del estado actual “fuera” para cubrir casos sin transición
            if _enviar_mail_directo:
                lineas = [f"- {f['activo']} · Geocerca: {f['geocerca']} · Estado: FUERA" for f in fuera_now]
                asunto = "Gestemed · Activos fuera de su geocerca"
                cuerpo = "Hola,\n\nSe detectaron los siguientes activos fuera de su geocerca:\n\n" + "\n".join(lineas) + "\n\nMensaje automático."
                try:
                    _enviar_mail_directo(asunto, cuerpo, destinatario)
                except Exception:
                    pass
            st.session_state["geo_last_send_key"] = key_hash
            st.success("Notificación enviada.")
        # lista compacta de fuera
        st.dataframe(pd.DataFrame(fuera_now)[["geocerca","activo"]], use_container_width=True, hide_index=True, height=150)
    else:
        st.info("No hay activos fuera de su geocerca en este momento.")

    st_folium(m, height=520, use_container_width=True)

    # histórico de alertas filtrado por geocercas seleccionadas
    st.markdown("**Histórico de alertas (sesión)**")
    if isinstance(df_alertas, pd.DataFrame) and not df_alertas.empty:
        ver = df_alertas.copy()
        if "id_geocerca" in ver.columns:
            ver = ver[ver["id_geocerca"].astype(str).isin(ids_geo)]
        if "ts" in ver.columns:
            ver["ts"] = pd.to_datetime(ver["ts"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        cols = [c for c in ["ts","nombre","id_unico","id_activo","evento","enviado_email"] if c in ver.columns]
        if not ver.empty and cols:
            st.dataframe(ver[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Sin eventos en esta sesión.")
    else:
        st.info("Sin eventos en esta sesión.")

# =============== Entrada principal ===============
def app(usuario: str):
    st.subheader("Geocercas y alertas de movimiento")
    tabs = st.tabs(["Configurar", "Monitoreo"])
    with tabs[0]:
        _tab_configurar(usuario)
    with tabs[1]:
        _tab_monitoreo(usuario)