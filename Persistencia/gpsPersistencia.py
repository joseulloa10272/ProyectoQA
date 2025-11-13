# Persistencia/gpsPersistencia.py — filtros contextuales y etiquetas “id - Modelo (Cliente)”

import os, sys, re, json
from datetime import datetime, date
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import pathPair, readTable, writeTable
from Persistencia.activosPersistencia import colsActivos, cargarActivos

posXlsx, posCsv   = pathPair("posiciones")
histXlsx, histCsv = pathPair("historialMovimientos")
activosXlsx, activosCsv = pathPair("activos")
contratosXlsx, contratosCsv = pathPair("contratos")

POS_COLS  = ["id_activo","id_unico","cliente","contrato","estado","latitud","longitud","ultima_actualizacion"]
HIST_COLS = ["id_activo","latitud","longitud","fecha","detalle"]

# --- helpers de saneamiento y normalización ---
def _ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    return df

def _norm_contrato_id(sel) -> str:
    """Devuelve solo el ID del contrato, por ejemplo '12 - Ana' -> '12'."""
    if sel is None:
        return ""
    s = str(sel).strip()
    if s == "" or s == "Todos":
        return ""
    return s.split(" - ", 1)[0].strip()

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------------- utilitarios de normalización ----------------
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
    txt = str(s).strip().strip('[]()"\' ')
    if " - " in txt:
        txt = txt.split(" - ", 1)[0].strip()
    if " " in txt and not txt.replace(".", "", 1).isdigit():
        txt = txt.split(" ", 1)[0].strip()
    return re.sub(r"^[^A-Za-z0-9\.]+|[^A-Za-z0-9\.]+$", "", txt)

def _split_ids(raw: str) -> list[str]:
    if not isinstance(raw, str):
        raw = str(raw)
    s = raw.strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            return [_normalize_activo_id(x) for x in arr if _normalize_activo_id(x)]
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

# ---------------- cargas robustas ----------------
def _load_activos_df() -> pd.DataFrame:
    try:
        df = pd.DataFrame(cargarActivos(), columns=colsActivos)
    except Exception:
        df = readTable(activosXlsx, activosCsv, colsActivos)

    df = _ensure_cols(df, ["id", "id_unico", "latitud", "longitud"])
    df["id"] = df["id"].astype(str).str.strip()
    df["id_unico"] = df["id_unico"].astype(str).str.strip()
    df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    return df

def _load_contratos_df() -> pd.DataFrame:
    dfc = pd.DataFrame()
    try:
        if os.path.exists(contratosCsv):
            dfc = pd.read_csv(contratosCsv)
    except Exception:
        dfc = pd.DataFrame()
    if dfc.empty:
        try:
            from Persistencia.contratosPersistencia import cargarContratos as _cc
            data = _cc()
            dfc = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        except Exception:
            dfc = pd.DataFrame()
    if dfc.empty:
        try:
            dfc = readTable(contratosXlsx, contratosCsv,
                            ["id","cliente","fechaInicio","fechaFin","activosAsociados","estado","diasNotificar"])
        except Exception:
            dfc = pd.DataFrame(columns=["id","cliente","fechaInicio","fechaFin","activosAsociados","estado","diasNotificar"])

    if "id_contrato" not in dfc.columns:
        dfc["id_contrato"] = dfc["id"].astype(str) if "id" in dfc.columns else ""
    if "activos" not in dfc.columns:
        dfc["activos"] = dfc["activosAsociados"] if "activosAsociados" in dfc.columns else ""
    for need in ("cliente","fechaInicio","fechaFin","estado","diasNotificar"):
        if need not in dfc.columns:
            dfc[need] = ""
    if dfc["estado"].astype(str).str.strip().eq("").any():
        dfc.loc[:, "estado"] = [
            _estado_contrato(fi, ff) for fi, ff in zip(dfc["fechaInicio"], dfc["fechaFin"])
        ]
    dfc["id_contrato"] = dfc["id_contrato"].astype(str).str.strip()
    dfc["cliente"] = dfc["cliente"].astype(str).str.strip()
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

# ---------------- sincronización posiciones ----------------
def _ensure_pos_cols(df_pos: pd.DataFrame) -> pd.DataFrame:
    df_pos = df_pos.copy()
    for c in POS_COLS:
        if c not in df_pos.columns:
            df_pos[c] = pd.NA
    df_pos["id_activo"] = df_pos["id_activo"].astype(str).str.strip()
    df_pos["latitud"]  = pd.to_numeric(df_pos["latitud"], errors="coerce")
    df_pos["longitud"] = pd.to_numeric(df_pos["longitud"], errors="coerce")
    return df_pos

def _sync_from_activos(df_pos: pd.DataFrame) -> pd.DataFrame:
    df_act = _load_activos_df()
    if df_act.empty:
        return _ensure_pos_cols(df_pos)
    dfc  = _load_contratos_df()
    mapa = _map_activo_meta(dfc)
    df_pos = _ensure_pos_cols(df_pos)

    idx = {str(x).strip(): i for i, x in enumerate(df_pos["id_activo"].astype(str))}
    for _, a in df_act.iterrows():
        aid = str(a.get("id","")).strip()
        if not aid:
            continue
        lat = pd.to_numeric(a.get("latitud"), errors="coerce")
        lon = pd.to_numeric(a.get("longitud"), errors="coerce")
        if pd.isna(lat) or pd.isna(lon):
            continue
        meta = mapa.get(aid, {"cliente":"", "id_contrato":"", "estado":""})
        ts = _now()
        if aid not in idx:
            fila = {
                "id_activo": aid,
                "id_unico": str(a.get("id_unico","")).strip(),
                "cliente": meta["cliente"],
                "contrato": meta["id_contrato"],
                "estado": meta["estado"],
                "latitud": float(lat),
                "longitud": float(lon),
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
            idx[aid] = len(df_pos) - 1
        else:
            i = idx[aid]
            if str(df_pos.at[i, "id_unico"]).strip() in ("", "nan", "NaN"):
                df_pos.at[i, "id_unico"] = str(a.get("id_unico","")).strip()
            if meta["cliente"]:
                df_pos.at[i, "cliente"]  = meta["cliente"]
                df_pos.at[i, "contrato"] = meta["id_contrato"]
                df_pos.at[i, "estado"]   = meta["estado"]
    return _ensure_pos_cols(df_pos)

# ---------------- API pública usada por el menú ----------------
def cargarPosiciones(
    f_cliente: str = None,
    f_contrato: str = None,
    f_estado: str = None,
    activo: str = None,
    sync_desde_activos: bool = False
) -> pd.DataFrame:

    # lectura y normalización mínima
    df_pos = readTable(posXlsx, posCsv, POS_COLS)
    df_pos = _ensure_cols(df_pos, POS_COLS)

    # compatibilidad con archivos legados
    if "ultima_actualizacion" not in df_pos.columns and "fecha" in df_pos.columns:
        df_pos = df_pos.rename(columns={"fecha": "ultima_actualizacion"})
        df_pos = df_pos.reindex(columns=POS_COLS, fill_value="")
        writeTable(df_pos, posXlsx, posCsv)

    # sincronización opcional desde activos cuando el caller lo solicita
    if sync_desde_activos:
        df_pos = _sync_from_activos(df_pos)
        writeTable(df_pos, posXlsx, posCsv)

    # enriquecer SIEMPRE con id_unico de activos, dejando la columna aunque no haya match
    dfA = _load_activos_df()[["id", "id_unico"]].copy()
    dfA = _ensure_cols(dfA, ["id", "id_unico"])
    dfA["id"] = dfA["id"].astype(str).str.strip()

    df_pos["id_activo"] = df_pos["id_activo"].astype(str).str.strip()
    df_pos = df_pos.merge(dfA, left_on="id_activo", right_on="id", how="left")
    if "id" in df_pos.columns:
        df_pos = df_pos.drop(columns=["id"])
    if "id_unico" not in df_pos.columns:
        df_pos["id_unico"] = ""
    df_pos["id_unico"] = df_pos["id_unico"].fillna("").astype(str)

    # filtros de vista
    if f_cliente and f_cliente != "Todos":
        df_pos = df_pos[df_pos["cliente"].astype(str).str.strip() == str(f_cliente).strip()]

    cid = _norm_contrato_id(f_contrato)
    if cid:
        df_pos = df_pos[df_pos["contrato"].astype(str).str.strip() == cid]

    if f_estado and f_estado != "Todos":
        df_pos = df_pos[df_pos["estado"].astype(str).str.strip() == str(f_estado).strip()]

    if activo and activo != "Todos":
        # etiquetas “id_unico – Modelo (Cliente)” o directamente id_unico
        sel_u = str(activo).split(" - ", 1)[0].strip()
        m = df_pos["id_unico"].astype(str).str.strip().eq(sel_u)
        if not m.any():
            # fallback por id numérico del activo
            m = df_pos["id_activo"].astype(str).str.strip().eq(sel_u)
        df_pos = df_pos[m]

    # uniformar nombre del timestamp para el popup del mapa
    df_pos = df_pos.rename(columns={"ultima_actualizacion": "ts"})
    return df_pos.reset_index(drop=True)

def actualizarPosicion(id_activo: str, latitud: float, longitud: float, detalle: str = "manual") -> dict:
    aid = str(id_activo).strip()
    lat = float(latitud); lon = float(longitud); ts = _now()

    df_pos  = _ensure_pos_cols(readTable(posXlsx, posCsv, POS_COLS))
    df_hist = readTable(histXlsx, histCsv, HIST_COLS)
    meta = _map_activo_meta(_load_contratos_df()).get(aid, {"cliente":"", "id_contrato":"", "estado":""})

    m = df_pos["id_activo"].astype(str).str.strip().eq(aid)
    if not m.any():
        fila = {"id_activo": aid, "id_unico": "", "cliente": meta["cliente"], "contrato": meta["id_contrato"],
                "estado": meta["estado"], "latitud": lat, "longitud": lon, "ultima_actualizacion": ts}
        df_pos = pd.concat([df_pos, pd.DataFrame([fila])], ignore_index=True)
    else:
        i = df_pos.index[m][0]
        df_pos.at[i, "latitud"] = lat
        df_pos.at[i, "longitud"] = lon
        df_pos.at[i, "ultima_actualizacion"] = ts
        if meta["cliente"]:
            df_pos.at[i, "cliente"]  = meta["cliente"]
            df_pos.at[i, "contrato"] = meta["id_contrato"]
            df_pos.at[i, "estado"]   = meta["estado"]

    df_hist = pd.concat([df_hist, pd.DataFrame([{
        "id_activo": aid, "latitud": lat, "longitud": lon, "fecha": ts, "detalle": str(detalle)
    }])], ignore_index=True)

    writeTable(df_pos, posXlsx, posCsv)
    writeTable(df_hist, histXlsx, histCsv)

    row = df_pos[df_pos["id_activo"].astype(str).str.strip().eq(aid)].iloc[0].copy()
    row["ts"] = row["ultima_actualizacion"]
    return row.to_dict()

def catalogos(f_cliente: str = None, f_contrato: str = None, f_estado: str = None) -> dict:
    dfc = _load_contratos_df()

    if f_cliente and f_cliente != "Todos":
        dfc = dfc[dfc["cliente"].astype(str).str.strip() == str(f_cliente).strip()]

    cid = _norm_contrato_id(f_contrato)
    if cid:
        dfc = dfc[dfc["id_contrato"].astype(str).str.strip() == cid]

    if f_estado and f_estado != "Todos":
        dfc = dfc[dfc["estado"].astype(str).str.strip() == str(f_estado).strip()]

    # contratos por ID, pero con etiqueta legible para la UI
    id_to_label = _map_id_a_label_contrato(dfc)
    contratos = sorted(id_to_label.keys(), key=lambda x: (len(x), x))

    # activos asociados al conjunto filtrado (etiquetas "id_unico - Modelo (Cliente)")
    from Persistencia.activosPersistencia import cargarActivosDf
    dfA = cargarActivosDf()[["id", "id_unico", "modelo", "cliente"]].copy()
    dfA["id"] = dfA["id"].astype(str).str.strip()

    activos_etq = []
    for _, r in dfc.iterrows():
        for aid in _split_ids(r.get("activos", "")):
            fila = dfA[dfA["id"] == aid]
            if not fila.empty:
                u = str(fila.iloc[0]["id_unico"]).strip()
                m = str(fila.iloc[0]["modelo"]).strip()
                c = str(fila.iloc[0]["cliente"]).strip()
                activos_etq.append(f"{u} - {m}" + (f" ({c})" if c else ""))

    activos = sorted({x for x in activos_etq if x})

    return {
        "clientes": sorted(set(dfc["cliente"].astype(str).str.strip()) - {""}),
        "contratos": [id_to_label[k] for k in contratos],  # solo para mostrar si lo necesitas
        "contratos_ids": contratos,                        # valores reales por ID
        "estados": sorted(set(dfc["estado"].astype(str).str.strip()) - {""}),
        "activos": activos
    }

def contratos_norm() -> pd.DataFrame:
    return _load_contratos_df().copy()

# --- utilidades nuevas ---
def _norm_contrato_id(sel: str | None) -> str:
    if not sel or str(sel).strip() in ("", "Todos"):
        return ""
    s = str(sel).strip()
    return s.split(" - ", 1)[0].strip()  # si viene "12 - Laura" extrae "12"

def _map_id_a_label_contrato(dfc: pd.DataFrame) -> dict[str, str]:
    m = {}
    if not dfc.empty:
        for _, r in dfc.iterrows():
            cid = str(r.get("id_contrato", "")).strip()
            cli = str(r.get("cliente", "")).strip()
            if cid:
                m[cid] = f"{cid} - {cli}" if cli else cid
    return m