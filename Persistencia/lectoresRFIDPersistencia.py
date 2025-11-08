
import pandas as pd
from .base import pathPair, readTable, writeTable

LECTOR_COLS = ["reader_id","tipo_lector","descripcion","latitud","longitud","zona","ip","meta"]
lectXlsx, lectCsv = pathPair("rfid_lectores")

def cargarLectores() -> pd.DataFrame:
    return readTable(lectXlsx, lectCsv, LECTOR_COLS)

def guardarLectores(df: pd.DataFrame):
    for c in LECTOR_COLS:
        if c not in df.columns: df[c] = ""
    writeTable(df[LECTOR_COLS].fillna(""), lectXlsx, lectCsv)

def registrarLector(reader_id: str, tipo_lector: str, descripcion: str = "", lat: float | None = None, lon: float | None = None, zona: str = "", ip: str = "", meta: str = ""):
    df = cargarLectores()
    if (df["reader_id"].astype(str) == str(reader_id)).any():
        return False
    nuevo = {
        "reader_id": str(reader_id),
        "tipo_lector": str(tipo_lector),    # "fijo" | "movil" | "serial" | "http"
        "descripcion": str(descripcion),
        "latitud": "" if lat is None else float(lat),
        "longitud": "" if lon is None else float(lon),
        "zona": str(zona),
        "ip": str(ip),
        "meta": str(meta),
    }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    guardarLectores(df)
    return True

def obtenerLector(reader_id: str) -> dict | None:
    df = cargarLectores()
    m = df["reader_id"].astype(str) == str(reader_id)
    if not m.any(): return None
    return df.loc[m].iloc[0].to_dict()