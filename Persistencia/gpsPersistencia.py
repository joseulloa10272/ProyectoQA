# Persistencia/gpsPersistencia.py  — versión unificada y compatible con menuGPS.py

import os, sys, re, json
from datetime import datetime, date
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import pathPair, readTable, writeTable
from Persistencia.activosPersistencia import colsActivos, cargarActivos

# Archivos estándar
posXlsx, posCsv   = pathPair("posiciones")
histXlsx, histCsv = pathPair("historialMovimientos")
activosXlsx, activosCsv = pathPair("activos")
contratosXlsx, contratosCsv = pathPair("contratos")

# Esquemas
POS_COLS  = ["id_activo","cliente","contrato","estado","latitud","longitud","ultima_actualizacion"]
HIST_COLS = ["id_activo","latitud","longitud","fecha","detalle"]

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------- normalización de contratos ----------
def _parse_ts(s):
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.NaT

def _estado_contrato(fini, ffin, umbral=60) -> str:
    hoy = pd.Timestamp(date.today())
    ini = _parse_ts(fini); fin = _parse_ts(ffin)
    if pd.isna(fin):
        return ""
    if hoy > fin:
        return "Vencido"
    if not pd.isna(ini) and hoy < ini:
        return "Pendiente"
    dias = int((fin - hoy).days)
    return "Por vencer" if 0 <= dias <= umbral else "Vigente"

def _normalize_activo_id(s: str) -> str:
    if s is None:
        return ""
    txt = str(s).strip().strip("[]()\"' ")
    if "-" in txt:
        txt = txt.split("-", 1)[0].strip()
    if " " in txt:
        txt = txt.split(" ", 1)[0].strip()
    return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", txt)

def _split_ids(raw: str) -> list[str]:
    if not isinstance(raw, str):
        raw = str(raw)
    s = raw.strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            return [ _normalize_activo_id(x) for x in arr if _normalize_activo_id(x) ]
        except Exception:
            s = s[1:-1]
    s = s.replace(";", ",")
    parts = [p.strip() for p in s.split(",")] if "," in s else [s]
    out = []
    for p in parts:
        nid = _normalize_activo_id(p.strip().strip("\"'"))
        if nid:
            out.append(nid)
    return out

def _load_activos_df() -> pd.DataFrame:
    try:
        df = pd.DataFrame(cargarActivos(), columns=colsActivos)
    except Exception:
        df = readTable(activosXlsx, activosCsv, colsActivos)
    for c in ("id","id_unico","latitud","longitud"):
        if c not in df.columns:
            df[c] = pd.NA
    df["id"] = df["id"].astype(str).str.strip()
    df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    return df

def _load_contratos_df() -> pd.DataFrame:
    try:
        from Persistencia.contratosPersistencia import cargarContratos
        dfc = cargarContratos()
        dfc = dfc if isinstance(dfc, pd.DataFrame) else pd.DataFrame(dfc)
    except Exception:
        dfc = readTable(contratosXlsx, contratosCsv,
                        ["id","cliente","fechaInicio","fechaFin","activosAsociados","estado","diasNotificar"])
    if "id_contrato" not in dfc.columns:
        dfc = dfc.rename(columns={"id":"id_contrato"}) if "id" in dfc.columns else dfc.assign(id_contrato="")
    if "activos" not in dfc.columns:
        dfc = dfc.rename(columns={"activosAsociados":"activos"}) if "activosAsociados" in dfc.columns else dfc.assign(activos="")
    for need in ("cliente","fechaInicio","fechaFin","estado","diasNotificar"):
        if need not in dfc.columns:
            dfc[need] = ""
    if dfc["estado"].astype(str).str.strip().eq("").any():
        dfc.loc[:, "estado"] = [
            _estado_contrato(fi, ff) for fi, ff in zip(dfc["fechaInicio"], dfc["fechaFin"])
        ]
    return dfc

def _map_activo_meta(dfc: pd.DataFrame) -> dict[str, dict]:
    mapa = {}
    for _, r in dfc.iterrows():
        idc = str(r.get("id_contrato","")).strip()
        cli = str(r.get("cliente","")).strip()
        est = str(r.get("estado","")).strip()
        for aid in _split_ids(r.get("activos","")):
            mapa[aid] = {"cliente": cli, "id_contrato": idc, "estado": est}
    return mapa

# ---------- sincronización y API pública ----------
def _sync_from_activos(df_pos: pd.DataFrame) -> pd.DataFrame:
    df_act = _load_activos_df()
    if df_act.empty:
        return df_pos
    dfc  = _load_contratos_df()
    mapa = _map_activo_meta(dfc)
    df_pos = df_pos.copy()

    for _, a in df_act.iterrows():
        aid = str(a.get("id","")).strip()
        lat = pd.to_numeric(a.get("latitud"), errors="coerce")
        lon = pd.to_numeric(a.get("longitud"), errors="coerce")
        if not aid or pd.isna(lat) or pd.isna(lon):
            continue
        meta = mapa.get(aid, {"cliente":"", "id_contrato":"", "estado":""})
        m = df_pos["id_activo"].astype(str).str.strip().eq(aid)
        ts = _now()
        if not m.any():
            fila = {
                "id_activo": aid, "cliente": meta["cliente"], "contrato": meta["id_contrato"],
                "estado": meta["estado"], "latitud": float(lat), "longitud": float(lon),
                "ultima_actualizacion": ts
            }
            df_pos = pd.concat([df_pos, pd.DataFrame([fila])], ignore_index=True)
            df_hist = readTable(histXlsx, histCsv, HIST_COLS)
            if df_hist[df_hist["id_activo"].astype(str).str.strip().eq(aid)].empty:
                df_hist = pd.concat([df_hist, pd.DataFrame([{
                    "id_activo": aid, "latitud": float(lat), "longitud": float(lon),
                    "fecha": ts, "detalle": "sincronizacion_inicial"
                }])], ignore_index=True)
                writeTable(df_hist, histXlsx, histCsv)
        else:
            i = df_pos.index[m][0]
            # enriquecimiento de metadatos si estaban vacíos
            if meta["cliente"]:
                df_pos.at[i, "cliente"]  = meta["cliente"]
                df_pos.at[i, "contrato"] = meta["id_contrato"]
                df_pos.at[i, "estado"]   = meta["estado"]
    return df_pos

def cargarPosiciones(id_activo: str | None = None, *args, **kwargs) -> pd.DataFrame:
    """
    Carga posiciones con compatibilidad hacia 'sync_desde_activos=True' y hacia archivos legados con columna 'fecha'.
    """
    df_pos = readTable(posXlsx, posCsv, POS_COLS)
    if "ultima_actualizacion" not in df_pos.columns and "fecha" in df_pos.columns:
        df_pos = df_pos.rename(columns={"fecha": "ultima_actualizacion"})
        df_pos = df_pos.reindex(columns=POS_COLS, fill_value="")
        writeTable(df_pos, posXlsx, posCsv)
    if kwargs.get("sync_desde_activos") is True:
        df_pos = _sync_from_activos(df_pos)
        writeTable(df_pos, posXlsx, posCsv)
    if id_activo:
        return df_pos[df_pos["id_activo"].astype(str).str.strip().eq(str(id_activo).strip())]
    return df_pos

def actualizarPosicion(id_activo: str, latitud: float, longitud: float, detalle: str = "manual") -> dict:
    aid = str(id_activo).strip()
    lat = float(latitud); lon = float(longitud); ts = _now()
    df_pos  = readTable(posXlsx, posCsv, POS_COLS)
    df_hist = readTable(histXlsx, histCsv, HIST_COLS)
    meta = _map_activo_meta(_load_contratos_df()).get(aid, {"cliente":"", "id_contrato":"", "estado":""})

    m = df_pos["id_activo"].astype(str).str.strip().eq(aid)
    if not m.any():
        fila = {"id_activo": aid, "cliente": meta["cliente"], "contrato": meta["id_contrato"],
                "estado": meta["estado"], "latitud": lat, "longitud": lon,
                "ultima_actualizacion": ts}
        df_pos = pd.concat([df_pos, pd.DataFrame([fila])], ignore_index=True)
    else:
        i = df_pos.index[m][0]
        df_pos.at[i, "latitud"] = lat
        df_pos.at[i, "longitud"] = lon
        df_pos.at[i, "ultima_actualizacion"] = ts

    df_hist = pd.concat([df_hist, pd.DataFrame([{
        "id_activo": aid, "latitud": lat, "longitud": lon, "fecha": ts, "detalle": str(detalle)
    }])], ignore_index=True)

    writeTable(df_pos, posXlsx, posCsv)
    writeTable(df_hist, histXlsx, histCsv)
    return df_pos[df_pos["id_activo"].astype(str).str.strip().eq(aid)].iloc[0].to_dict()

def cargarHistorialMovimientos(id_activo: str | None = None) -> pd.DataFrame:
    df = readTable(histXlsx, histCsv, HIST_COLS)
    if id_activo:
        df = df[df["id_activo"].astype(str).str.strip().eq(str(id_activo).strip())]
    return df

# Catálogos para filtros en la vista GPS
def catalogos() -> dict:
    dfc = _load_contratos_df()
    return {
        "clientes": sorted(set(dfc["cliente"].astype(str).str.strip()) - {""}),
        "contratos": sorted(set(dfc["id_contrato"].astype(str).str.strip()) - {""}),
        "estados": sorted(set(dfc["estado"].astype(str).str.strip()) - {""}),
    }

def contratos_norm() -> pd.DataFrame:
    return _load_contratos_df().copy()