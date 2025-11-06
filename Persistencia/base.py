import os
from typing import List, Dict, Tuple
import pandas as pd

# === Rutas base ===
DirBase = os.path.dirname(os.path.abspath(__file__))
DirData = os.path.join(os.path.dirname(DirBase), "data")
os.makedirs(DirData, exist_ok=True)

def pathPair(name: str):
    xlsx = os.path.join(DirData, f"{name}.xlsx")
    csv  = os.path.join(DirData, f"{name}.csv")
    return xlsx, csv

def ensureFile(pathXlsx: str, pathCsv: str, columns: List[str]) -> Tuple[str, str]:
    if os.path.exists(pathXlsx):
        return pathXlsx, "xlsx"
    if os.path.exists(pathCsv):
        return pathCsv, "csv"
    df = pd.DataFrame(columns=columns)
    df.to_excel(pathXlsx, index=False)
    return pathXlsx, "xlsx"

def readTable(pathXlsx: str, pathCsv: str, columns: List[str]) -> pd.DataFrame:
    path, kind = ensureFile(pathXlsx, pathCsv, columns)
    if kind == "xlsx":
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str, encoding="utf-8")
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    df = df[columns]
    return df.fillna("")

def writeTable(df: pd.DataFrame, pathXlsx: str, pathCsv: str):
    if os.path.exists(pathXlsx) or not os.path.exists(pathCsv):
        df.to_excel(pathXlsx, index=False)
    else:
        df.to_csv(pathCsv, index=False, encoding="utf-8")

def dfToListOfDicts(df: pd.DataFrame):
    return [{k: ("" if pd.isna(v) else v) for k, v in row.items()} for row in df.to_dict(orient="records")]

def listOfDictsToDf(rows, columns: List[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    df = df[columns]
    return df.fillna("")
