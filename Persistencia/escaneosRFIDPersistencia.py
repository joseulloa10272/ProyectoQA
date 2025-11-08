
from datetime import datetime
import pandas as pd
from .base import pathPair, readTable, writeTable
from .rfidPersistencia import obtenerActivoPorTag
from .gpsPersistencia import actualizarPosicion

SCAN_COLS = ["id_scan","tag","id_unico","reader_id","tipo_lector","zona","latitud","longitud","fecha_hora","usuario","evento"]
scanXlsx, scanCsv = pathPair("rfid_escaneos")

def _next_id(df: pd.DataFrame) -> int:
    if df.empty or "id_scan" not in df.columns: return 1
    vals = pd.to_numeric(df["id_scan"], errors="coerce").dropna()
    return 1 if vals.empty else int(vals.max()) + 1

def cargarEscaneos() -> pd.DataFrame:
    return readTable(scanXlsx, scanCsv, SCAN_COLS)

def guardarEscaneos(df: pd.DataFrame):
    for c in SCAN_COLS:
        if c not in df.columns: df[c] = ""
    writeTable(df[SCAN_COLS].fillna(""), scanXlsx, scanCsv)

def registrarEscaneo(tag: str, reader_id: str, tipo_lector: str, zona: str = "", latitud: float | None = None, longitud: float | None = None, usuario: str = "", evento: str = "scan"):
    df = cargarEscaneos()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    id_unico = obtenerActivoPorTag(tag) or ""
    nuevo = {
        "id_scan": str(_next_id(df)),
        "tag": str(tag).strip(),
        "id_unico": str(id_unico),
        "reader_id": str(reader_id),
        "tipo_lector": str(tipo_lector),
        "zona": str(zona),
        "latitud": "" if latitud is None else float(latitud),
        "longitud": "" if longitud is None else float(longitud),
        "fecha_hora": ahora,
        "usuario": str(usuario),
        "evento": str(evento)  # "scan" | "entrada" | "salida" | "ubicacion"
    }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    guardarEscaneos(df)
    # Propaga ubicación a GPS siempre que existan coordenadas válidas
    if id_unico and (latitud is not None) and (longitud is not None):
        actualizarPosicion(id_unico, latitud, longitud, estado="Vigente")
    return nuevo