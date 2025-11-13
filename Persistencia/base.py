# Persistencia/base.py
from __future__ import annotations
import os, zipfile
from typing import List, Tuple, Dict
import pandas as pd

# === Rutas base (se conservan) ===
DirBase = os.path.dirname(os.path.abspath(__file__))
DirData = os.path.join(os.path.dirname(DirBase), "data")
os.makedirs(DirData, exist_ok=True)

def pathPair(name: str) -> Tuple[str, str]:
    xlsx = os.path.join(DirData, f"{name}.xlsx")
    csv  = os.path.join(DirData, f"{name}.csv")
    return xlsx, csv

# === Utilitarios de IO seguros ===
def _safe_write_excel(df: pd.DataFrame, path_xlsx: str) -> None:
    try:
        df.to_excel(path_xlsx, index=False, engine="openpyxl")
    except Exception:
        # Evita detener el flujo si falta openpyxl o hay bloqueo del archivo
        pass

def _safe_read_excel(path_xlsx: str) -> pd.DataFrame:
    if not os.path.exists(path_xlsx) or os.path.getsize(path_xlsx) == 0:
        return pd.DataFrame()
    try:
        return pd.read_excel(path_xlsx, engine="openpyxl")
    except (zipfile.BadZipFile, ValueError):
        # Archivo vacío/corrupto; trata como tabla vacía
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def _safe_read_csv(path_csv: str) -> pd.DataFrame:
    if not os.path.exists(path_csv) or os.path.getsize(path_csv) == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path_csv, encoding="utf-8")
    except Exception:
        return pd.DataFrame()

def _read_any(pathXlsx: str, pathCsv: str) -> pd.DataFrame:
    # Prioriza CSV si tiene contenido; si no, intenta Excel
    if os.path.exists(pathCsv):
        df = _safe_read_csv(pathCsv)
        if not df.empty:
            return df
    return _safe_read_excel(pathXlsx)

def ensureFile(pathXlsx: str, pathCsv: str, columns: List[str]) -> Tuple[str, str]:
    # Garantiza al menos un archivo con encabezados; si falla Excel, deja CSV listo
    if not os.path.exists(pathXlsx) and not os.path.exists(pathCsv):
        df = pd.DataFrame(columns=columns)
        _safe_write_excel(df, pathXlsx)
        try:
            df.to_csv(pathCsv, index=False, encoding="utf-8")
        except Exception:
            pass
    return pathXlsx, pathCsv

# === API pública (compatibles con el resto del proyecto) ===
def readTable(pathXlsx: str, pathCsv: str, columns: List[str] | None = None) -> pd.DataFrame:
    # Asegura existencia de archivos cuando se conoce el esquema
    if columns:
        ensureFile(pathXlsx, pathCsv, columns)
    df = _read_any(pathXlsx, pathCsv)
    if columns:
        # Completa columnas faltantes y ordena
        for c in columns:
            if c not in df.columns:
                df[c] = ""
        df = df[columns]
    return df.fillna("")

def writeTable(df: pd.DataFrame, pathXlsx: str, pathCsv: str) -> None:
    # Escritura defensiva en ambos formatos
    df_out = df.copy()
    try:
        df_out.to_csv(pathCsv, index=False, encoding="utf-8")
    except Exception:
        pass
    _safe_write_excel(df_out, pathXlsx)

def dfToListOfDicts(df: pd.DataFrame) -> List[Dict]:
    return [{k: ("" if pd.isna(v) else v) for k, v in row.items()}
            for row in df.to_dict(orient="records")]

def listOfDictsToDf(rows: List[Dict], columns: List[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows or [])
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns].fillna("")