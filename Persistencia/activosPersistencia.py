# Persistencia/activosPersistencia.py
from __future__ import annotations
import os, io, json
from typing import List, Dict, Tuple
from datetime import datetime
import pandas as pd

from Persistencia.base import (
    pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf
)

# ===== Esquema definitivo F-01 =====
colsActivos = [
    "id", "id_unico", "modelo", "serie", "fabricante", "fechaCompra",
    "latitud", "longitud", "cliente", "valor", "tag", "fotos",
    "fechaRegistro", "usuario"
]

activosXlsx, activosCsv = pathPair("activos")
rfidXlsx, rfidCsv       = pathPair("rfid_activos")
histXlsx, histCsv       = pathPair("historialMovimientos")

rfidCols = [
    "rfid", "modelo", "serie", "fabricante", "fechaCompra",
    "latitud", "longitud", "cliente", "valor", "fotos"
]

# ===== Utilitarios =====
def _norm_str(x) -> str:
    return "" if x is None else str(x).strip()

def _to_float(x, default=None):
    try:
        if isinstance(x, str):
            x = x.replace(",", ".")
        return float(x)
    except Exception:
        return default

def _norm_tag(x) -> str:
    s = _norm_str(x)
    return s.casefold() if s else ""

def nextId(df: pd.DataFrame) -> int:
    if df is None or df.empty or "id" not in df.columns:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return 1 if ids.empty else int(ids.max()) + 1

# ===== Lectura/Escritura =====
def cargarActivos() -> List[Dict]:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    for c in colsActivos:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    df["valor"]    = pd.to_numeric(df["valor"], errors="coerce")
    return dfToListOfDicts(df)

def cargarActivosDf() -> pd.DataFrame:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    for c in colsActivos:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    df["valor"]    = pd.to_numeric(df["valor"], errors="coerce")
    return df

def guardarActivosDf(df: pd.DataFrame) -> None:
    for c in colsActivos:
        if c not in df.columns:
            df[c] = ""
    writeTable(df[colsActivos].copy(), activosXlsx, activosCsv)

def guardarActivos(registros: List[Dict]) -> None:
    df = listOfDictsToDf(registros, colsActivos)
    guardarActivosDf(df)

# ===== Reglas de unicidad =====
def existeIdUnico(id_unico: str) -> bool:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if "id_unico" not in df.columns:
        return False
    goal = _norm_str(id_unico).casefold()
    if not goal:
        return False
    serie = df["id_unico"].astype(str).str.strip().str.casefold()
    return serie.eq(goal).any()

def existeTagEnActivos(tag: str) -> bool:
    t = _norm_tag(tag)
    if not t:
        return False
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if "tag" not in df.columns:
        return False
    serie = df["tag"].astype(str).str.strip().map(lambda s: s.casefold() if s else "")
    serie = serie[serie != ""]
    return serie.eq(t).any()

# ===== Altas individuales (con ubicación obligatoria) =====
def agregarActivos(
    id_unico: str,
    modelo: str,
    serie: str,
    fabricante: str,
    fechaCompra: str,
    latitud: float,
    longitud: float,
    cliente: str,
    valor: float,
    tag: str = "",
    fotos: str = "",
    fechaRegistro: str = "",
    usuario: str = ""
) -> Dict:
    df = cargarActivosDf()

    id_norm = _norm_str(id_unico)
    if not id_norm:
        raise ValueError("El ID único es obligatorio.")
    if existeIdUnico(id_norm):
        raise ValueError("El ID único ya existe.")
    tag_norm = _norm_tag(tag)
    if tag_norm and existeTagEnActivos(tag_norm):
        raise ValueError("El tag RFID/QR ya existe.")

    lat = _to_float(latitud)
    lon = _to_float(longitud)
    if lat is None or lon is None:
        raise ValueError("Latitud y longitud deben ser numéricas.")

    nuevoId = nextId(df)
    nuevo = {
        "id": str(nuevoId),
        "id_unico": id_norm,
        "modelo": _norm_str(modelo),
        "serie": _norm_str(serie),
        "fabricante": _norm_str(fabricante),
        "fechaCompra": _norm_str(fechaCompra),
        "latitud": float(lat),
        "longitud": float(lon),
        "cliente": _norm_str(cliente),
        "valor": _to_float(valor, 0.0) or 0.0,
        "tag": _norm_str(tag),
        "fotos": _norm_str(fotos),
        "fechaRegistro": _norm_str(fechaRegistro) or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": _norm_str(usuario),
    }
    for c in colsActivos:
        if c not in nuevo:
            nuevo[c] = ""

    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    guardarActivosDf(df)
    return nuevo

# ===== Catálogo RFID y alta por RFID =====
def cargarCatalogoRfidDf() -> pd.DataFrame:
    df = readTable(rfidXlsx, rfidCsv, rfidCols)
    for c in rfidCols:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    return df

def registrarActivosRfid(rfid_code: str, usuario: str) -> Tuple[bool, str | int]:
    code = _norm_str(rfid_code)
    if not code:
        return False, "Debe indicar un código RFID."

    cat = cargarCatalogoRfidDf()
    if cat.empty:
        return False, "El catálogo RFID está vacío."

    fila = cat.loc[cat["rfid"].astype(str).str.strip().str.casefold() == code.casefold()]
    if fila.empty:
        return False, f"No se encontró el RFID '{rfid_code}' en el catálogo."

    if existeTagEnActivos(code):
        return False, "El tag RFID ya existe en activos."

    data = fila.iloc[0].to_dict()
    lat = _to_float(data.get("latitud"))
    lon = _to_float(data.get("longitud"))
    if lat is None or lon is None:
        return False, "El catálogo RFID no incluye latitud/longitud válidas."

    dfAct = cargarActivosDf()
    nuevoId = nextId(dfAct)
    id_unico = str(nuevoId)

    reg = agregarActivos(
        id_unico=id_unico,
        modelo=_norm_str(data.get("modelo", "")),
        serie=_norm_str(data.get("serie", "")),
        fabricante=_norm_str(data.get("fabricante", "")),
        fechaCompra=_norm_str(data.get("fechaCompra", "")),
        latitud=lat,
        longitud=lon,
        cliente=_norm_str(data.get("cliente", "")),
        valor=_to_float(data.get("valor"), 0.0) or 0.0,
        tag=code,
        fotos=_norm_str(data.get("fotos", "")),
        fechaRegistro=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        usuario=_norm_str(usuario),
    )
    registrarMovimiento(id_unico, lat, lon, "Alta por RFID")
    return True, reg.get("id", nuevoId)

# ===== Importación masiva con ubicación =====
def leerCatalogoDesdeObjetoSubido(fileObj, filename: str) -> pd.DataFrame:
    nombre = (filename or "").lower()
    raw = fileObj.read() if hasattr(fileObj, "read") else fileObj
    bio = io.BytesIO(raw)
    try:
        if nombre.endswith((".xlsx", ".xls")):
            return pd.read_excel(bio)
        if nombre.endswith(".csv"):
            return pd.read_csv(bio)
        return pd.read_excel(bio)
    finally:
        try:
            fileObj.seek(0)
        except Exception:
            pass

def importarActivosMasivoDesdeArchivo(fileObj, filename: str, usuario: str) -> Tuple[bool, Dict]:
    rep = {"insertados": 0, "omitidos": 0, "razones_omision": []}
    try:
        dfIn = leerCatalogoDesdeObjetoSubido(fileObj, filename)
    except Exception as e:
        return False, {"error": f"No se pudo leer el archivo: {e}"}

    if dfIn is None or dfIn.empty:
        return False, {"error": "El archivo está vacío o no tiene filas."}

    requeridas = ["id_unico", "modelo", "serie", "fabricante", "fechaCompra",
                  "latitud", "longitud", "cliente", "valor", "tag"]
    falt = [c for c in requeridas if c not in dfIn.columns]
    if falt:
        return False, {"error": f"Faltan columnas requeridas: {', '.join(falt)}"}

    dfAct = cargarActivosDf()
    siguienteId = nextId(dfAct)

    vistos_id = set(dfAct["id_unico"].astype(str).str.strip().str.casefold()) if not dfAct.empty else set()
    vistos_tag = set(dfAct["tag"].astype(str).str.strip().str.casefold()) if not dfAct.empty else set()

    nuevos: List[Dict] = []

    for idx, row in dfIn.iterrows():
        data = row.to_dict()

        idu = _norm_str(data.get("id_unico"))
        modelo = _norm_str(data.get("modelo"))
        serie  = _norm_str(data.get("serie"))
        fab    = _norm_str(data.get("fabricante"))
        fcomp  = _norm_str(data.get("fechaCompra"))
        cli    = _norm_str(data.get("cliente"))
        tag    = _norm_str(data.get("tag"))
        lat    = _to_float(data.get("latitud"))
        lon    = _to_float(data.get("longitud"))
        val    = _to_float(data.get("valor"), 0.0) or 0.0

        oblig = [("id_unico", idu), ("modelo", modelo), ("serie", serie), ("fabricante", fab),
                 ("fechaCompra", fcomp), ("latitud", lat), ("longitud", lon), ("cliente", cli)]
        vacios = [k for k, v in oblig if v in (None, "", float("nan"))]
        if vacios:
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx) + 2, "rfid": tag, "motivo": f"Campos obligatorios vacíos: {', '.join(vacios)}"})
            continue

        if idu.casefold() in vistos_id:
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx) + 2, "rfid": tag, "motivo": "ID único duplicado"})
            continue

        if tag and tag.casefold() in vistos_tag:
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx) + 2, "rfid": tag, "motivo": "Tag duplicado"})
            continue

        reg = {
            "id": str(siguienteId),
            "id_unico": idu,
            "modelo": modelo,
            "serie": serie,
            "fabricante": fab,
            "fechaCompra": fcomp,
            "latitud": float(lat),
            "longitud": float(lon),
            "cliente": cli,
            "valor": val,
            "tag": tag,
            "fotos": _norm_str(data.get("fotos", "")),
            "fechaRegistro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "usuario": _norm_str(usuario),
        }
        for c in colsActivos:
            if c not in reg:
                reg[c] = ""

        nuevos.append(reg)
        vistos_id.add(idu.casefold())
        if tag:
            vistos_tag.add(tag.casefold())
        siguienteId += 1
        rep["insertados"] += 1

    if not nuevos:
        return True, rep

    df_out = pd.concat([dfAct, pd.DataFrame(nuevos)], ignore_index=True)
    guardarActivosDf(df_out)
    return True, rep

# --- reemplaza SOLO esta función en Persistencia/activosPersistencia.py ---
def cargarActivosIdNombre() -> List[str]:
    df = cargarActivosDf()
    if df is None or df.empty:
        return []
    df = df.dropna(subset=["id_unico", "modelo"])
    etiquetas = (
        df["id_unico"].astype(str).str.strip()
        + " - " + df["modelo"].astype(str).str.strip()
        + " (" + df["cliente"].astype(str).fillna("").str.strip() + ")"
    ).tolist()
    vistos, out = set(), []
    for e in etiquetas:
        if e not in vistos:
            out.append(e)
            vistos.add(e)
    return out

# --- opcional: alias de conveniencia si alguna vista espera lista de dicts ---
def cargarActivos() -> List[Dict]:
    return dfToListOfDicts(cargarActivosDf())

# ===== Historial de movimientos =====
def cargarHistorialMovimientos(id_activo: str, fecha_inicio: str = None, fecha_fin: str = None) -> pd.DataFrame:
    cols = ["id_activo", "latitud", "longitud", "fecha", "detalle"]
    try:
        df = readTable(histXlsx, histCsv, cols)
    except Exception:
        df = pd.DataFrame(columns=cols)

    if df.empty:
        return df

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df[df["id_activo"].astype(str).str.strip() == str(id_activo).strip()]

    if fecha_inicio:
        df = df[df["fecha"] >= pd.to_datetime(fecha_inicio, errors="coerce")]
    if fecha_fin:
        df = df[df["fecha"] <= pd.to_datetime(fecha_fin, errors="coerce")]

    return df.sort_values("fecha", ascending=False).reset_index(drop=True)

def registrarMovimiento(id_activo: str, latitud: float, longitud: float, detalle: str = "actualización de posición") -> None:
    cols = ["id_activo", "latitud", "longitud", "fecha", "detalle"]
    try:
        df_hist = readTable(histXlsx, histCsv, cols)
    except Exception:
        df_hist = pd.DataFrame(columns=cols)

    nuevo = {
        "id_activo": str(id_activo).strip(),
        "latitud": float(latitud),
        "longitud": float(longitud),
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detalle": _norm_str(detalle),
    }
    df_hist = pd.concat([df_hist, pd.DataFrame([nuevo])], ignore_index=True)
    writeTable(df_hist, histXlsx, histCsv)