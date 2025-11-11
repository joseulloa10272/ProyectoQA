import os
from typing import List, Tuple, Dict
import pandas as pd

# === Rutas base ===
DirBase = os.path.dirname(os.path.abspath(__file__))
DirData = os.path.join(os.path.dirname(DirBase), "data")
os.makedirs(DirData, exist_ok=True)

def pathPair(name: str) -> Tuple[str, str]:
    xlsx = os.path.join(DirData, f"{name}.xlsx")
    csv  = os.path.join(DirData, f"{name}.csv")
    return xlsx, csv

def ensureFile(pathXlsx: str, pathCsv: str, columns: List[str]) -> Tuple[str, str]:
    # Garantiza al menos un archivo con encabezados
    if not os.path.exists(pathXlsx) and not os.path.exists(pathCsv):
        df = pd.DataFrame(columns=columns)
        df.to_excel(pathXlsx, index=False)
        df.to_csv(pathCsv, index=False, encoding="utf-8")
    return pathXlsx, pathCsv

def _read_any(pathXlsx: str, pathCsv: str) -> pd.DataFrame:
    if os.path.exists(pathXlsx):
        return pd.read_excel(pathXlsx)
    if os.path.exists(pathCsv):
        return pd.read_csv(pathCsv, encoding="utf-8")
    return pd.DataFrame()

def readTable(pathXlsx: str, pathCsv: str, columns: List[str]) -> pd.DataFrame:
    ensureFile(pathXlsx, pathCsv, columns)
    df = _read_any(pathXlsx, pathCsv)
    # Asegura columnas y orden
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    df = df[columns]
    return df.fillna("")

def writeTable(df: pd.DataFrame, pathXlsx: str, pathCsv: str) -> None:
    # Escribe ambos formatos para compatibilidad con usuarios que trabajan en Excel o CSV
    df_out = df.copy()
    df_out.to_excel(pathXlsx, index=False)
    df_out.to_csv(pathCsv, index=False, encoding="utf-8")

def dfToListOfDicts(df: pd.DataFrame) -> List[Dict]:
    return [{k: ("" if pd.isna(v) else v) for k, v in row.items()} for row in df.to_dict(orient="records")]

def listOfDictsToDf(rows: List[Dict], columns: List[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows or [])
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns].fillna("")