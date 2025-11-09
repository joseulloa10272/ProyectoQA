# Persistencia/gpsPersistencia.py
import os
import sys
from datetime import datetime
import pandas as pd
import re 

# Rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Persistencia.base import pathPair, readTable, writeTable  # noqa: E402
from Persistencia.activosPersistencia import colsActivos, cargarActivos  # noqa: E402
from Persistencia.activosPersistencia import existeIdUnico, existeTagEnActivos


# Intento de API de contratos; si falla, se usa archivo
try:
    from Persistencia.contratosPersistencia import cargarContratos  # noqa: F401
    _HAS_CONTRATOS_API = True
except Exception:
    _HAS_CONTRATOS_API = False

gpsXlsx, gpsCsv = pathPair("gpsActivos")
activosXlsx, activosCsv = pathPair("activos")
contratosXlsx, contratosCsv = pathPair("contratos")

GPS_COLS = [
    "id_activo", "cliente", "contrato", "estado",
    "latitud", "longitud", "ultima_actualizacion"
]

# ---------------- Utilidades básicas ----------------

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _ensure_cols(df: pd.DataFrame | None, cols: list[str]) -> pd.DataFrame:
    if df is None:
        df = pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

def _parse_ts(s):
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.NaT

def _estado_contrato(fini, ffin, umbral=60) -> str:
    hoy = pd.Timestamp.now().normalize()
    ini = _parse_ts(fini)
    fin = _parse_ts(ffin)
    if pd.isna(fin):
        return ""
    if hoy > fin:
        return "Vencido"
    if not pd.isna(ini) and hoy < ini:
        return "Pendiente"
    dias = int((fin - hoy).days)
    if 0 <= dias <= umbral:
        return "Por vencer"
    return "Vigente"

def _split_ids(raw: str) -> list[str]:
    if not isinstance(raw, str):
        raw = str(raw)
    raw = raw.replace(";", ",")
    if "," in raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    val = raw.strip()
    return [val] if val else []

# ---------------- Carga y normalización de catálogos ----------------

def _load_activos_df() -> pd.DataFrame:
    try:
        lst = cargarActivos()
        df = pd.DataFrame(lst, columns=colsActivos)
    except Exception:
        df = readTable(activosXlsx, activosCsv, colsActivos)

    df = df.copy() if df is not None else pd.DataFrame(columns=["id_unico", "latitud", "longitud"])
    for c in ("id_unico", "latitud", "longitud"):
        if c not in df.columns:
            df[c] = pd.NA

    df["id_unico"] = df["id_unico"].astype(str).str.strip()
    df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    return df

def _id_contrato_col(dfc: pd.DataFrame) -> str | None:
    for k in ("id_contrato", "contrato", "codigo", "codigoContrato", "id"):
        if k in dfc.columns:
            return k
    return None

def _load_contratos_df() -> pd.DataFrame:
    dfc: pd.DataFrame | None = None

    if _HAS_CONTRATOS_API:
        try:
            data = cargarContratos()
            dfc = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        except Exception:
            dfc = None

    if dfc is None or dfc.empty:
        try:
            dfc = readTable(contratosXlsx, contratosCsv, [])
        except Exception:
            dfc = None

    if dfc is None:
        dfc = pd.DataFrame()

    # Normalización laxa
    idc = _id_contrato_col(dfc) or "id_contrato"
    if idc != "id_contrato":
        dfc = dfc.rename(columns={idc: "id_contrato"})
    if "id_contrato" not in dfc.columns:
        dfc["id_contrato"] = ""

    if "cliente" not in dfc.columns:
        for k in ("Cliente", "cliente_nombre", "customer", "entidad"):
            if k in dfc.columns:
                dfc = dfc.rename(columns={k: "cliente"})
                break
    if "cliente" not in dfc.columns:
        dfc["cliente"] = ""

    ini = next((k for k in ("fechaInicio", "inicio", "start", "fecha_inicio", "start_date") if k in dfc.columns), None)
    fin = next((k for k in ("fechaFin", "fin", "end", "fecha_fin", "end_date") if k in dfc.columns), None)
    if ini and ini != "fechaInicio":
        dfc = dfc.rename(columns={ini: "fechaInicio"})
    if fin and fin != "fechaFin":
        dfc = dfc.rename(columns={fin: "fechaFin"})
    if "fechaInicio" not in dfc.columns:
        dfc["fechaInicio"] = ""
    if "fechaFin" not in dfc.columns:
        dfc["fechaFin"] = ""

    if "activos" not in dfc.columns:
        if "activosAsociados" in dfc.columns:
            dfc = dfc.rename(columns={"activosAsociados": "activos"})
        else:
            for c in ("id_activo", "id_unico", "activo"):
                if c in dfc.columns:
                    dfc["activos"] = dfc[c].astype(str)
                    break
    if "activos" not in dfc.columns:
        dfc["activos"] = ""

    if "estado" not in dfc.columns:
        dfc["estado"] = ""
    dfc["estado_calc"] = [_estado_contrato(fi, ff) for fi, ff in zip(dfc["fechaInicio"], dfc["fechaFin"])]
    dfc.loc[dfc["estado"].astype(str).str.strip().eq(""), "estado"] = dfc["estado_calc"]

    # Tipos básicos
    for col in ("id_contrato", "cliente", "estado", "activos"):
        dfc[col] = dfc[col].astype(str).str.strip()

    return dfc

def _map_activo_meta(dfc: pd.DataFrame) -> dict[str, dict]:
    """Devuelve mapa id_activo -> {cliente, id_contrato, estado} a partir de contratos."""
    mapa: dict[str, dict] = {}
    for _, r in dfc.iterrows():
        idc = r.get("id_contrato", "")
        cli = r.get("cliente", "")
        est = r.get("estado", "") or r.get("estado_calc", "")
        for aid in _split_ids(r.get("activos", "")):
            mapa[aid] = {"cliente": cli, "id_contrato": idc, "estado": est}
    return mapa

def _catalogos_validos(dfc: pd.DataFrame) -> tuple[set, set, set]:
    clientes = set(dfc.get("cliente", pd.Series(dtype=str)).astype(str).str.strip())
    contratos = set(dfc.get("id_contrato", pd.Series(dtype=str)).astype(str).str.strip())
    estados = set(dfc.get("estado", pd.Series(dtype=str)).astype(str).str.strip())
    clientes.discard(""); contratos.discard(""); estados.discard("")
    return clientes, contratos, estados

# ---------------- API pública ----------------

def cargarPosiciones(sync_desde_activos: bool = True) -> pd.DataFrame:
    df_gps = readTable(gpsXlsx, gpsCsv, GPS_COLS)
    df_gps = _ensure_cols(df_gps, GPS_COLS)
    df_gps["id_activo"] = df_gps["id_activo"].astype(str).str.strip()
    df_gps["latitud"]  = pd.to_numeric(df_gps["latitud"], errors="coerce")
    df_gps["longitud"] = pd.to_numeric(df_gps["longitud"], errors="coerce")

    if sync_desde_activos:
        dfc   = _load_contratos_df()
        mapa  = _map_activo_meta(dfc)              # universo de seguimiento: solo activos presentes en contratos
        ids   = sorted(set(mapa.keys()))

        df_act = _load_activos_df()
        idx    = df_act.set_index("id_unico")      # catálogo de coordenadas

        registros = []
        for aid in ids:
            meta = mapa[aid]
            lat = idx.at[aid, "latitud"]  if aid in idx.index else pd.NA
            lon = idx.at[aid, "longitud"] if aid in idx.index else pd.NA

            # conservar timestamp previo si la fila ya existía
            m = df_gps["id_activo"] == aid
            ts_prev = df_gps.loc[m, "ultima_actualizacion"].iloc[0] if m.any() else ""
            ts = _now() if (pd.notna(lat) and pd.notna(lon)) else ts_prev

            registros.append({
                "id_activo": aid,
                "cliente":   meta.get("cliente", ""),
                "contrato":  meta.get("id_contrato", ""),
                "estado":    meta.get("estado", ""),
                "latitud":   lat,
                "longitud":  lon,
                "ultima_actualizacion": ts
            })

        df_gps = pd.DataFrame(registros, columns=GPS_COLS)

    writeTable(df_gps, gpsXlsx, gpsCsv)
    return df_gps

def actualizarPosicion(
    id_activo: str,
    latitud: float,
    longitud: float,
    ts: str | None = None
) -> dict:
    """
    Actualiza coordenadas de un activo presente en contratos, si el id no figura en contratos
    se rechaza la operación.
    """
    dfc = _load_contratos_df()
    mapa = _map_activo_meta(dfc)
    aid = str(id_activo).strip()
    if aid not in mapa:
        raise ValueError(f"El activo {aid} no está asociado a ningún contrato vigente o registrado.")

    df = cargarPosiciones(sync_desde_activos=True)
    lat = float(latitud); lon = float(longitud)
    stamp = ts or _now()

    m = df["id_activo"].astype(str).str.strip().eq(aid)
    if not m.any():
        meta = mapa[aid]
        fila = {
            "id_activo": aid,
            "cliente": meta.get("cliente", ""),
            "contrato": meta.get("id_contrato", ""),
            "estado": meta.get("estado", ""),
            "latitud": lat,
            "longitud": lon,
            "ultima_actualizacion": stamp
        }
        df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
    else:
        i = df.index[m][0]
        df.at[i, "latitud"] = lat
        df.at[i, "longitud"] = lon
        df.at[i, "ultima_actualizacion"] = stamp
        # cliente/contrato/estado siguen dictados por el contrato

    writeTable(df, gpsXlsx, gpsCsv)
    return df[df["id_activo"].astype(str).str.strip().eq(aid)].iloc[0].to_dict()

def catalogos() -> dict:
    """Catálogos estrictos basados solo en contratos."""
    dfc = _load_contratos_df()
    cli, con, est = _catalogos_validos(dfc)
    return {"clientes": sorted(cli), "contratos": sorted(con), "estados": sorted(est)}

# utilidades públicas para la vista
def contratos_norm() -> pd.DataFrame:
    """Devuelve el DataFrame de contratos normalizado para construir filtros dependientes en la vista."""
    return _load_contratos_df().copy()

def obtenerPosiciones():
    return cargarPosiciones(sync_desde_activos=True)

def _normalize_activo_id(s: str) -> str:
    """
    Normaliza un elemento de la columna 'activos' de contratos y devuelve el id_unico.
    Soporta formatos como:
      '100001 - ECG-3000 (Hospital México)'
      ['01 - M11 (111)']
      100003
    Regla: tomar el primer token antes de un guion '-' o del primer espacio.
    """
    if s is None:
        return ""
    txt = str(s).strip()

    # eliminar envoltorios de listas/tuplas y comillas
    txt = txt.strip("[]()\"' ").strip()
    # si el valor vino como "100001 - Modelo ..." tomar la cabeza antes del guion
    if "-" in txt:
        txt = txt.split("-", 1)[0].strip()
    # si aún queda espacio, tomar el primer token
    if " " in txt:
        txt = txt.split(" ", 1)[0].strip()

    # limpiar cualquier carácter no alfanumérico remanente al inicio/fin
    txt = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", txt)
    return txt


def _split_ids(raw: str) -> list[str]:
    """
    Divide la columna 'activos' en ids individuales, limpia brackets y comillas,
    acepta separadores ',' o ';' y devuelve ids normalizados listos para cruzar
    con activos.xlsx.
    """
    if not isinstance(raw, str):
        raw = str(raw)
    s = raw.strip()

    # si viene como lista textual, quitar brackets
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]

    # unificar separadores
    s = s.replace(";", ",")

    parts = [p.strip() for p in s.split(",")] if "," in s else [s]
    out = []
    for p in parts:
        p = p.strip().strip("\"'").strip()
        nid = _normalize_activo_id(p)
        if nid:
            out.append(nid)
    return out


def _map_activo_meta(dfc: pd.DataFrame) -> dict[str, dict]:
    """id_activo -> {cliente, id_contrato, estado} desde contratos, limitado a 5 activos por contrato."""
    mapa: dict[str, dict] = {}
    for _, r in dfc.iterrows():
        idc = str(r.get("id_contrato", "")).strip()
        cli = str(r.get("cliente", "")).strip()
        est = str(r.get("estado", "") or r.get("estado_calc", "")).strip()

        ids = _split_ids(r.get("activos", ""))
        if not ids:
            continue

        # respetar máximo 5 activos por contrato
        ids = ids[:5]

        for aid in ids:
            # si el mismo activo aparece en varios contratos, la última fila prevalece
            mapa[aid] = {"cliente": cli, "id_contrato": idc, "estado": est}
    return mapa

def cargarHistorialMovimientos(id_activo, fecha_inicio, fecha_fin):
    """Consulta el historial de movimientos de un activo entre dos fechas."""
    # Suponiendo que tienes un archivo o base de datos con el historial de movimientos
    historial = readTable('movimientos')  # Cargar historial desde un archivo
    # Filtrar por activo y por fechas
    historial = historial[historial['id_activo'] == id_activo]
    historial = historial[(historial['fecha'] >= str(fecha_inicio)) & (historial['fecha'] <= str(fecha_fin))]
    
    return historial
