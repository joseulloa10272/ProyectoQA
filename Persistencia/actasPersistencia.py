from typing import List, Dict, List
import datetime as dt
import pandas as pd
from .base import pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf

# === Esquema ===
colsActas = [
    "id", "contratoAsociado", "razon", "activosAsociados"]

# === Rutas ===
actasXlsx, actasCsv = pathPair("actas")

def nextId(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    idsValidos = pd.to_numeric(df["id"], errors="coerce").dropna()
    if idsValidos.empty:
        return 1
    return int(idsValidos.max()) + 1

def cargarActas() -> List[Dict]:
    df = readTable(actasXlsx, actasCsv, colsActas)
    return dfToListOfDicts(df)

def guardarActas(actas: List[Dict]) -> None:
    df = listOfDictsToDf(actas, colsActas)
    writeTable(df, actasXlsx, actasCsv)

def agregarActas(contratoAsociado: str, razon: str, activosAsociados: str) -> Dict:

    df = readTable(actasXlsx, actasCsv, colsActas)
    nuevoId = nextId(df)
    nuevo = {
            "id": str(nuevoId),
            "contratoAsociado": contratoAsociado,
            "razon": razon,
            "activosAsociados": activosAsociados,
        }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)

    writeTable(df, actasXlsx, actasCsv)
    return True

