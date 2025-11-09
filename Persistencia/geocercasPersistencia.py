# Persistencia/geocercasPersistencia.py
from __future__ import annotations
import os, sys, json, math
from datetime import datetime
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import pathPair, readTable, writeTable  # noqa: E402
from Persistencia.gpsPersistencia import cargarPosiciones, catalogos  # para catálogos/monitoreo
from Persistencia.notificacionesEmail import enviar_email  # canal de salida

# Rutas de almacenamiento
geoXlsx, geoCsv           = pathPair("geocercas")
alertXlsx, alertCsv       = pathPair("alertasGeocercas")
estadoXlsx, estadoCsv     = pathPair("geocercasEstado")

# Esquemas
GEO_COLS = [
    "id_geocerca", "nombre", "tipo",          # tipo: circle | polygon
    "cliente", "contrato", "activos",         # filtros de alcance (opcionales)
    "modo",                                   # entrada | salida | ambos
    "emails",                                 # comma-separated
    "shape_json",                             # dict serializado: circle:{center:[lat,lon],radius_m}, polygon:{vertices:[[lat,lon],...]}
    "activa",                                 # bool
    "creado_por", "creado_en", "ultima_alerta_global"
]

ALERTA_COLS = [
    "ts", "id_geocerca", "nombre",
    "id_activo", "cliente", "contrato",
    "evento",           # ENTRADA | SALIDA
    "latitud", "longitud", "dist_m",
    "detalle", "enviado_email"
]

ESTADO_COLS = ["id_geocerca", "id_activo", "dentro", "ts"]

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _ensure(df: pd.DataFrame | None, cols: list[str]) -> pd.DataFrame:
    df = df if df is not None else pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

# ----------------- I/O de geocercas -----------------

def cargarGeocercas() -> pd.DataFrame:
    df = readTable(geoXlsx, geoCsv, GEO_COLS)
    return _ensure(df, GEO_COLS)

def guardarGeocerca(reg: dict) -> dict:
    df = cargarGeocercas()  # Se carga el DataFrame de geocercas
    # id si no viene
    if not reg.get("id_geocerca"):
        reg["id_geocerca"] = f"G{int(datetime.now().timestamp())}"  # Asigna un ID único basado en el timestamp
    reg["creado_en"] = reg.get("creado_en") or _now()
    reg["ultima_alerta_global"] = reg.get("ultima_alerta_global", "")
    reg["activa"] = bool(reg.get("activa", True))
    # Normaliza los datos
    for k in ("cliente", "contrato", "activos", "emails", "modo", "tipo", "nombre", "creado_por"):
        reg[k] = str(reg.get(k, "") or "").strip()
    if isinstance(reg.get("activos"), list):
        reg["activos"] = ",".join([str(x).strip() for x in reg["activos"]])
    if isinstance(reg.get("emails"), list):
        reg["emails"] = ",".join([str(x).strip() for x in reg["emails"]])
    if not isinstance(reg.get("shape_json"), str):
        reg["shape_json"] = json.dumps(reg.get("shape_json", {}))  # Serializa el shape de la geocerca

    # Inserta o actualiza el registro
    m = df["id_geocerca"].astype(str).eq(reg["id_geocerca"])  # Verifica si la geocerca ya existe
    if m.any():
        for k, v in reg.items():
            df.loc[m, k] = v  # Si existe, actualiza los valores
    else:
        df = pd.concat([df, pd.DataFrame([reg])], ignore_index=True)  # Si no existe, agrega una nueva geocerca

    # Guardar los cambios en el archivo
    writeTable(df, geoXlsx, geoCsv)  # Guarda el DataFrame actualizado en el archivo

    return reg  # Retorna el registro guardado


def eliminarGeocerca(id_geocerca: str) -> bool:
    df = cargarGeocercas()
    m = df["id_geocerca"].astype(str).eq(str(id_geocerca))
    if not m.any():
        return False
    df = df[~m].copy()
    writeTable(df, geoXlsx, geoCsv)
    # limpiar estados asociados
    est = _ensure(readTable(estadoXlsx, estadoCsv, ESTADO_COLS), ESTADO_COLS)
    est = est[~est["id_geocerca"].astype(str).eq(str(id_geocerca))]
    writeTable(est, estadoXlsx, estadoCsv)
    return True

# ----------------- Utilidades geométricas -----------------

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def _in_circle(lat, lon, center, radius_m) -> tuple[bool, float]:
    d = _haversine_m(lat, lon, center[0], center[1])
    return (d <= float(radius_m)), d

def _in_polygon(lat, lon, vertices) -> tuple[bool, float]:
    # Ray-casting básico; devuelve además distancia mínima en m a los vértices
    x, y = lon, lat
    inside = False
    mind = float("inf")
    n = len(vertices)
    for i in range(n):
        lat_i, lon_i = float(vertices[i][0]), float(vertices[i][1])
        lat_j, lon_j = float(vertices[(i - 1) % n][0]), float(vertices[(i - 1) % n][1])
        # distancia mínima a vértices
        mind = min(mind, _haversine_m(lat, lon, lat_i, lon_i))
        xi, yi, xj, yj = lon_i, lat_i, lon_j, lat_j
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        if intersect:
            inside = not inside
    return inside, mind

def _parse_shape(s: str) -> dict:
    try:
        d = json.loads(s)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

# ----------------- Estado y alertas -----------------

def _load_estado() -> pd.DataFrame:
    return _ensure(readTable(estadoXlsx, estadoCsv, ESTADO_COLS), ESTADO_COLS)

def _set_estado(idg: str, aid: str, dentro: bool):
    est = _load_estado()
    m = (est["id_geocerca"].astype(str).eq(idg)) & (est["id_activo"].astype(str).eq(aid))
    if m.any():
        est.loc[m, ["dentro", "ts"]] = [bool(dentro), _now()]
    else:
        est = pd.concat([est, pd.DataFrame([{"id_geocerca": idg, "id_activo": aid, "dentro": bool(dentro), "ts": _now()}])], ignore_index=True)
    writeTable(est, estadoXlsx, estadoCsv)

def _prev_dentro(idg: str, aid: str) -> bool | None:
    est = _load_estado()
    m = (est["id_geocerca"].astype(str).eq(idg)) & (est["id_activo"].astype(str).eq(aid))
    if m.any():
        v = est.loc[m, "dentro"].iloc[0]
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)
    return None

def _record_alerta(reg: dict):
    df = _ensure(readTable(alertXlsx, alertCsv, ALERTA_COLS), ALERTA_COLS)
    df = pd.concat([df, pd.DataFrame([reg])], ignore_index=True)
    writeTable(df, alertXlsx, alertCsv)

def cargarAlertas() -> pd.DataFrame:
    return _ensure(readTable(alertXlsx, alertCsv, ALERTA_COLS), ALERTA_COLS)

# ----------------- Evaluación principal -----------------

def evaluar_geocercas_y_alertar(intervalo_min: int = 2, enviar_correos: bool = True) -> list[dict]:
    """
    Evalúa geocercas activas contra las posiciones vigentes y, si hay transición
    de estado, registra alerta y envía correo. Retorna lista de dicts con las alertas disparadas.
    """
    alertas_emitidas = []

    df_geo = cargarGeocercas()
    df_geo = df_geo[df_geo["activa"] == True]  # noqa: E712

    if df_geo.empty:
        return alertas_emitidas

    # Posiciones frescas (ya integradas con contratos/clientes/estados reales)
    df_pos = cargarPosiciones(sync_desde_activos=True)
    if df_pos.empty:
        return alertas_emitidas

    df_pos["latitud"] = pd.to_numeric(df_pos["latitud"], errors="coerce")
    df_pos["longitud"] = pd.to_numeric(df_pos["longitud"], errors="coerce")
    df_pos = df_pos.dropna(subset=["latitud", "longitud"])

    for _, g in df_geo.iterrows():
        idg   = str(g["id_geocerca"])
        modo  = str(g.get("modo", "ambos")).lower()
        emails = [e.strip() for e in str(g.get("emails", "")).split(",") if e.strip()]
        shape = _parse_shape(str(g.get("shape_json", "{}")))
        tipo  = str(g.get("tipo", ""))

        # filtrar alcance: por cliente, contrato o lista de activos
        sub = df_pos.copy()
        if str(g.get("cliente", "")).strip():
            sub = sub[sub["cliente"].astype(str).str.strip() == str(g["cliente"]).strip()]
        if str(g.get("contrato", "")).strip():
            sub = sub[sub["contrato"].astype(str).str.strip() == str(g["contrato"]).strip()]
        if str(g.get("activos", "")).strip():
            ids = [x.strip() for x in str(g["activos"]).split(",") if x.strip()]
            sub = sub[sub["id_activo"].astype(str).isin(ids)]
        if sub.empty:
            continue

        for _, r in sub.iterrows():
            aid = str(r["id_activo"])
            lat, lon = float(r["latitud"]), float(r["longitud"])

            if tipo == "circle":
                dentro, dist = _in_circle(lat, lon, shape.get("center", [0, 0]), shape.get("radius_m", 0))
            elif tipo == "polygon":
                dentro, dist = _in_polygon(lat, lon, shape.get("vertices", []))
            else:
                continue

            prev = _prev_dentro(idg, aid)
            evento = None
            if prev is None:
                # primer muestreo: solo fija estado, sin alertar
                _set_estado(idg, aid, dentro)
                continue
            if prev and not dentro and modo in ("salida", "ambos"):
                evento = "SALIDA"
            if (not prev) and dentro and modo in ("entrada", "ambos"):
                evento = "ENTRADA"

            if evento:
                reg = {
                    "ts": _now(),
                    "id_geocerca": idg,
                    "nombre": str(g.get("nombre", "")),
                    "id_activo": aid,
                    "cliente": str(r.get("cliente", "")),
                    "contrato": str(r.get("contrato", "")),
                    "evento": evento,
                    "latitud": lat,
                    "longitud": lon,
                    "dist_m": round(float(dist), 2),
                    "detalle": f"{evento} geocerca {idg} ({g.get('nombre','')})",
                    "enviado_email": False
                }
                # correo (opcional)
                if enviar_correos and emails:
                    asunto = f"[Gestemed] {evento} de geocerca: {g.get('nombre','')} | Activo {aid}"
                    cuerpo = (
                        f"Evento: {evento}\n"
                        f"Geocerca: {g.get('nombre','')} ({idg})\n"
                        f"Activo: {aid}\n"
                        f"Cliente: {reg['cliente']}  Contrato: {reg['contrato']}\n"
                        f"Coordenadas: {lat:.6f}, {lon:.6f}\n"
                        f"Distancia al borde: {reg['dist_m']} m\n"
                        f"Fecha/Hora: {reg['ts']}\n"
                    )
                    ok, _msg = enviar_email(asunto, cuerpo, emails)
                    reg["enviado_email"] = bool(ok)

                _record_alerta(reg)
                alertas_emitidas.append(reg)
                _set_estado(idg, aid, dentro)  # actualizar estado

            else:
                # solo mantener estado si cambió sin alertar por modo
                if prev != dentro:
                    _set_estado(idg, aid, dentro)

    return alertas_emitidas

def catalogos():
    """Retorna los catálogos de clientes y contratos."""
    # Suponiendo que estos datos provienen de una fuente local o de una base de datos.
    clientes = ["Cliente 1", "Cliente 2", "Cliente 3"]  # Estos valores deben ser cargados dinámicamente
    contratos = ["Contrato 1", "Contrato 2", "Contrato 3"]  # Lo mismo aquí
    
    return {"clientes": clientes, "contratos": contratos}


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

