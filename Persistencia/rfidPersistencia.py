
import pandas as pd
from .base import pathPair, readTable, writeTable

RFID_COLS = ["tag","id_unico"]
rfidXlsx, rfidCsv = pathPair("rfid_activos")

def cargarMapaRFID() -> pd.DataFrame:
    return readTable(rfidXlsx, rfidCsv, RFID_COLS)

def guardarMapaRFID(df: pd.DataFrame):
    for c in RFID_COLS:
        if c not in df.columns: df[c] = ""
    writeTable(df[RFID_COLS].fillna(""), rfidXlsx, rfidCsv)

def obtenerActivoPorTag(tag: str) -> str | None:
    df = cargarMapaRFID()
    if df.empty: return None
    m = df["tag"].astype(str).str.strip().str.casefold() == str(tag).strip().casefold()
    if not m.any(): return None
    return str(df.loc[m, "id_unico"].iloc[0])

def tagDisponible(tag: str) -> bool:
    return obtenerActivoPorTag(tag) is None

def vincularTagAActivo(tag: str, id_unico: str) -> bool:
    df = cargarMapaRFID()
    if not tagDisponible(tag):
        return False
    nuevo = {"tag": str(tag).strip(), "id_unico": str(id_unico).strip()}
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    guardarMapaRFID(df)
    return True

def desvincularTag(tag: str) -> bool:
    df = cargarMapaRFID()
    if df.empty: return False
    m = df["tag"].astype(str).str.strip().str.casefold() == str(tag).strip().casefold()
    if not m.any(): return False
    df = df.loc[~m].copy()
    guardarMapaRFID(df)
    return True