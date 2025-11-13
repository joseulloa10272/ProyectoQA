# Persistencia/geocercasPersistencia.py — versión robusta y compatible con el menú nuevo
from __future__ import annotations
import json, re, ast
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd

from Persistencia.base import pathPair, readTable, writeTable
from Persistencia.gpsPersistencia import cargarPosiciones
from Persistencia.activosPersistencia import cargarActivosDf

# Email opcional
try:
    from Persistencia.notificacionesEmail import enviar_email
except Exception:
    enviar_email = None

def _email_de_usuario(usuario: str) -> str | None:
    try:
        from Persistencia.usuarioPersistencia import obtenerEmailUsuario as _get
        return _get(usuario)
    except Exception:
        try:
            from Persistencia.usuarioPersistencia import obtenerCorreoUsuario as _get_alt
            return _get_alt(usuario)
        except Exception:
            return None

geoXlsx, geoCsv       = pathPair("geocercas")
estadoXlsx, estadoCsv = pathPair("geocercasEstado")
alertXlsx, alertCsv   = pathPair("alertasGeocercas")

GEO_COLS    = ["id_geocerca","nombre","tipo","cliente","contrato","activos","modo","emails","shape_json","activa","creado_por","creado_en","ultima_alerta_global"]
EST_COLS    = ["id_geocerca","id_activo","id_unico","dentro","ts"]
ALERTA_COLS = ["ts","id_geocerca","nombre","id_activo","id_unico","evento","latitud","longitud","dist_m","detalle","enviado_email"]

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ========== normalizaciones ==========
def _norm_id_token(txt: str) -> str:
    if txt is None:
        return ""
    s = str(txt).strip()
    s = s.split(" - ")[0].split(" ")[0]
    m = re.match(r"^\d+(?:\.\d+)?$", s)
    return m.group(0) if m else s

def _parse_ids(raw) -> List[str]:
    if isinstance(raw, list):
        base = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not s:
            base = []
        else:
            try:
                v = json.loads(s)
                base = v if isinstance(v, list) else [s]
            except Exception:
                try:
                    v = ast.literal_eval(s)
                    base = v if isinstance(v, list) else [s]
                except Exception:
                    base = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
    else:
        base = []
    return [_norm_id_token(x) for x in base if _norm_id_token(x)]

def _parse_polygon(shape_json) -> List[Tuple[float,float]]:
    """
    Retorna [(lat,lon), ...] bien formado desde:
      - dict GeoJSON con 'coordinates'
      - string JSON o literal Python
      - lista con pares [lon,lat] o [lat,lon]
    """
    val = shape_json
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        try:
            val = json.loads(s)
        except Exception:
            try:
                val = ast.literal_eval(s)
            except Exception:
                return []
    if isinstance(val, dict):
        coords = val.get("coordinates") or val.get("geometry", {}).get("coordinates") or []
    else:
        coords = val
    # desanidar [[[ ... ]]] -> [[ ... ]]
    if isinstance(coords, list) and coords and isinstance(coords[0], (list, tuple)) and coords and isinstance(coords[0][0], (list, tuple)):
        coords = coords[0]

    pts: List[Tuple[float,float]] = []
    if not isinstance(coords, list):
        return pts
    for p in coords:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        a, b = float(p[0]), float(p[1])
        # heurística: si a luce longitud y b latitud, invierte
        if abs(a) > 90 and abs(b) <= 90:
            lat, lon = b, a
        elif abs(a) <= 90 and abs(b) > 90:
            lat, lon = a, b
        else:
            lat, lon = a, b
        pts.append((lat, lon))
    return pts

def _point_in_poly(lat: float, lon: float, poly_latlon: List[Tuple[float,float]]) -> bool:
    n = len(poly_latlon)
    if n < 3:
        return False
    inside = False
    for i in range(n):
        lat_i, lon_i = poly_latlon[i]
        lat_j, lon_j = poly_latlon[(i - 1) % n]
        xi, yi = lon_i, lat_i
        xj, yj = lon_j, lat_j
        inter = ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi)
        inside = not inside if inter else inside
    return inside

# ========== dataframes ==========
def _geos_df() -> pd.DataFrame:
    df = readTable(geoXlsx, geoCsv, GEO_COLS)
    if df is None:
        df = pd.DataFrame(columns=GEO_COLS)
    df = df.copy()
    if "activa" in df.columns:
        df["activa"] = df["activa"].astype(str).str.lower().isin(["1","true","t","si","sí","yes","y"])
    return df

def obtenerGeocercas() -> pd.DataFrame:
    return _geos_df()

# acepta dict completo o firma histórica anterior
def guardarGeocerca(*args, **kwargs) -> dict:
    df = _geos_df()
    if len(args) == 1 and isinstance(args[0], dict):
        reg = args[0]
        row = {k: reg.get(k, "") for k in GEO_COLS}
        row["id_geocerca"] = str(row.get("id_geocerca") or f"G{int(datetime.now().timestamp())}")
        row["nombre"] = str(row.get("nombre","")).strip()
        row["tipo"] = str(row.get("tipo","polygon")).strip().lower()
        row["activos"] = json.dumps(_parse_ids(row.get("activos","")), ensure_ascii=False)
        sj = reg.get("shape_json","")
        row["shape_json"] = json.dumps(sj, ensure_ascii=False) if not isinstance(sj, str) else sj
        row["activa"] = bool(reg.get("activa", True))
        row["creado_en"] = row.get("creado_en") or _now()
        row["ultima_alerta_global"] = row.get("ultima_alerta_global","")
    else:
        id_geocerca, nombre, tipo, cliente, contrato, activos, modo, emails, shape_json, activa, creado_por = args[:11]
        row = {
            "id_geocerca": str(id_geocerca).strip() or f"G{int(datetime.now().timestamp())}",
            "nombre": str(nombre).strip(),
            "tipo": str(tipo or "polygon").strip().lower(),
            "cliente": str(cliente or "").strip(),
            "contrato": str(contrato or "").strip(),
            "activos": json.dumps(_parse_ids(activos), ensure_ascii=False),
            "modo": str(modo or "").strip().lower(),
            "emails": str(emails or "").strip(),
            "shape_json": json.dumps(shape_json, ensure_ascii=False) if isinstance(shape_json, dict) else str(shape_json),
            "activa": bool(activa),
            "creado_por": str(creado_por or "").strip(),
            "creado_en": _now(),
            "ultima_alerta_global": "",
        }

    if not df.empty and row["id_geocerca"] in df["id_geocerca"].astype(str).tolist():
        df.loc[df["id_geocerca"].astype(str) == row["id_geocerca"], list(row.keys())] = list(row.values())
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    writeTable(df, geoXlsx, geoCsv)
    return row

def eliminarGeocerca(id_geocerca: str) -> None:
    df = _geos_df()
    df = df[df["id_geocerca"].astype(str) != str(id_geocerca)]
    writeTable(df, geoXlsx, geoCsv)

def _estado_df() -> pd.DataFrame:
    df = readTable(estadoXlsx, estadoCsv, EST_COLS)
    if df is None:
        df = pd.DataFrame(columns=EST_COLS)
    return df

def _alertas_df() -> pd.DataFrame:
    df = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if df is None:
        df = pd.DataFrame(columns=ALERTA_COLS)
    return df

# ========== núcleo de evaluación ==========

def _to_dt(s: str) -> datetime:
    try:
        return pd.to_datetime(s, errors="coerce").to_pydatetime()
    except Exception:
        return datetime.now()

def evaluar_posiciones_y_generar_alertas(
    enviar_correo: bool = True,
    usuario: str | None = None,
    destinatario: str | None = None,
    ids_geocerca: list[str] | None = None,
    disparar_fuera_actual: bool = True,
    persistencia_min: int = 5,        # minutos fuera continuos antes de alertar
    enfriamiento_min: int = 30,       # minutos mínimos entre correos por activo+geocerca
) -> pd.DataFrame:
    geos = _geos_df()
    if geos.empty:
        out = pd.DataFrame(columns=ALERTA_COLS)
        writeTable(out, alertXlsx, alertCsv)
        return out

    if ids_geocerca:
        ids_set = {str(x) for x in ids_geocerca}
        geos = geos[geos["id_geocerca"].astype(str).isin(ids_set)]
        if geos.empty:
            return pd.DataFrame(columns=ALERTA_COLS)

    dfp = cargarPosiciones(sync_desde_activos=True)
    if dfp is None or dfp.empty:
        out = pd.DataFrame(columns=ALERTA_COLS)
        writeTable(out, alertXlsx, alertCsv)
        return out

    dfp = dfp.copy()
    dfp["id_activo"] = dfp["id_activo"].astype(str).str.strip()
    dfp["latitud"]   = pd.to_numeric(dfp["latitud"], errors="coerce")
    dfp["longitud"]  = pd.to_numeric(dfp["longitud"], errors="coerce")
    dfp = dfp.dropna(subset=["latitud","longitud"])

    dfA = cargarActivosDf()
    if dfA is None:
        dfA = pd.DataFrame(columns=["id","id_unico"])
    dfA = dfA.copy()
    dfA["id"]       = dfA.get("id","").astype(str).str.strip()
    dfA["id_unico"] = dfA.get("id_unico","").astype(str).str.strip()
    map_id_to_unico = dict(zip(dfA["id"], dfA["id_unico"]))
    map_unico_to_id = dict(zip(dfA["id_unico"], dfA["id"]))

    dfp["id_unico"] = dfp["id_activo"].map(map_id_to_unico).astype(str)

    est_hist = _estado_df()     # histórico completo de estados
    est_prev = est_hist.drop_duplicates(subset=["id_geocerca","id_activo","id_unico"], keep="last") \
                        if not est_hist.empty else est_hist

    hist_alertas = _alertas_df()

    ahora = datetime.now()
    nuevas_filas = []          # todas las filas de esta evaluación
    filas_a_enviar = []        # solo las que sí mandan correo ahora

    for _, g in geos.iterrows():
        if not bool(g.get("activa", True)):
            continue

        pts = _parse_polygon(g.get("shape_json",""))
        if len(pts) < 3:
            continue

        ids_tokens = _parse_ids(g.get("activos",""))
        ids_unico  = set(ids_tokens)
        ids_id     = {map_unico_to_id[x] for x in ids_unico if x in map_unico_to_id}

        sub = dfp[(dfp["id_unico"].isin(ids_unico)) | (dfp["id_activo"].isin(ids_id))].copy()
        if sub.empty:
            continue

        for _, r in sub.iterrows():
            lat = float(r["latitud"]); lon = float(r["longitud"])
            dentro = _point_in_poly(lat, lon, pts)

            key = {
                "id_geocerca": str(g["id_geocerca"]),
                "id_activo":   str(r["id_activo"]),
                "id_unico":    str(r.get("id_unico","")),
            }

            # registrar estado (para trazar persistencia)
            est_row = dict(key, dentro=bool(dentro), ts=_now())
            est_hist = pd.concat([est_hist, pd.DataFrame([est_row])], ignore_index=True)

            # decidir si se genera evento y si se envía correo
            evento = None
            motivo_silencio = ""

            # transición previa
            prevq = est_prev[
                (est_prev["id_geocerca"].astype(str)==key["id_geocerca"]) &
                (est_prev["id_activo"].astype(str)==key["id_activo"])
            ]
            prev_dentro = None if prevq.empty else bool(prevq.iloc[0]["dentro"])

            if disparar_fuera_actual and not dentro:
                evento = "SALIO"
            elif prev_dentro is None and not dentro:
                evento = "SALIO"
            elif prev_dentro is not None and prev_dentro != dentro:
                evento = "ENTRO" if dentro else "SALIO"

            if evento:
                # regla 1: persistencia mínima cuando está fuera
                if evento == "SALIO" or not dentro:
                    # último timestamp en que estuvo dentro, para calcular racha fuera
                    hist_key = est_hist[
                        (est_hist["id_geocerca"].astype(str)==key["id_geocerca"]) &
                        (est_hist["id_activo"].astype(str)==key["id_activo"])
                    ].sort_values("ts")
                    # busca desde el final hacia atrás el último 'dentro=True'
                    ult_dentro = None
                    for _, rr in hist_key[::-1].iterrows():
                        if bool(rr["dentro"]):
                            ult_dentro = _to_dt(rr["ts"])
                            break
                    inicio_fuera = ult_dentro or ahora   # si nunca se vio dentro, toma ahora
                    minutos_fuera = max(0, int((ahora - inicio_fuera).total_seconds() // 60))
                    if minutos_fuera < persistencia_min:
                        motivo_silencio = f"silenciado por persistencia<{persistencia_min}min"

                # regla 2: enfriamiento por activo+geocerca
                if not motivo_silencio:
                    ult_envio = None
                    if not hist_alertas.empty:
                        env = hist_alertas[
                            (hist_alertas["id_geocerca"].astype(str)==key["id_geocerca"]) &
                            ((hist_alertas["id_unico"].astype(str)==key["id_unico"]) |
                             (hist_alertas["id_activo"].astype(str)==key["id_activo"])) &
                            (hist_alertas["enviado_email"].astype(str).str.startswith("enviada"))
                        ]
                        if not env.empty:
                            ult_envio = _to_dt(env.sort_values("ts").iloc[-1]["ts"])
                    if ult_envio and (ahora - ult_envio) < timedelta(minutes=enfriamiento_min):
                        motivo_silencio = f"silenciado por enfriamiento<{enfriamiento_min}min"

                fila = {
                    "ts": _now(),
                    "id_geocerca": key["id_geocerca"],
                    "nombre": str(g.get("nombre","")),
                    "id_activo": key["id_activo"],
                    "id_unico":  key["id_unico"],
                    "evento":    evento,
                    "latitud":   lat,
                    "longitud":  lon,
                    "dist_m":    0.0,
                    "detalle":   f"Activo {key['id_unico'] or key['id_activo']} {evento.lower()} de '{str(g.get('nombre',''))}'",
                    "enviado_email": motivo_silencio,   # vacío si va para envío
                }
                nuevas_filas.append(fila)
                if motivo_silencio == "":
                    filas_a_enviar.append(fila)

    # persiste estados y alertas
    writeTable(est_hist, estadoXlsx, estadoCsv)
    nuevo_df = pd.DataFrame(nuevas_filas) if nuevas_filas else pd.DataFrame(columns=ALERTA_COLS)

    # evitar duplicados exactos dentro de la misma evaluación
    if not nuevo_df.empty:
        nuevo_df = nuevo_df.drop_duplicates(subset=["id_geocerca","id_unico","id_activo","evento"], keep="last")
        writeTable(pd.concat([hist_alertas, nuevo_df], ignore_index=True), alertXlsx, alertCsv)

    # envío consolidado
    if enviar_correo and enviar_email and filas_a_enviar:
        dest = destinatario or (_email_de_usuario(usuario) if usuario else None)
        if dest:
            lineas = [f"- {a['ts']} · {a['nombre']} · {a['id_unico'] or a['id_activo']} · {a['evento']}"
                      for a in filas_a_enviar]
            try:
                enviar_email(
                    "Gestemed · Alertas de geocercas",
                    "Hola,\n\nSe generaron las siguientes alertas de movimiento:\n\n"
                    + "\n".join(lineas) + "\n\nMensaje automático.",
                    dest
                )
                # marca como enviadas solo las filas realmente enviadas
                enviados_idx = nuevo_df[nuevo_df["enviado_email"]==""].index
                nuevo_df.loc[enviados_idx, "enviado_email"] = f"enviada {_now()}"
                writeTable(pd.concat([hist_alertas, nuevo_df], ignore_index=True), alertXlsx, alertCsv)
            except Exception:
                pass

    return nuevo_df