# Persistencia/actasPersistencia.py
from typing import List, Dict
import json
import pandas as pd
from datetime import datetime
from .base import pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf

# === Esquema estable (versión original) ===
colsActas = ["id", "contratoAsociado", "razon", "activosAsociados"]

# === Rutas ===
actasXlsx, actasCsv = pathPair("actas")

# ---------------- Utilitarios ----------------
def _ensure_cols(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        df = pd.DataFrame(columns=colsActas)
    for c in colsActas:
        if c not in df.columns:
            df[c] = ""
    return df[colsActas]

def nextId(df: pd.DataFrame) -> int:
    if df is None or df.empty or "id" not in df.columns:
        return 1
    serie = pd.to_numeric(df["id"], errors="coerce").dropna()
    return 1 if serie.empty else int(serie.max()) + 1

# ---------------- Lectura/consulta ----------------
def cargarActas() -> List[Dict]:
    """Devuelve la tabla de actas como lista de diccionarios, con columnas garantizadas."""
    df = readTable(actasXlsx, actasCsv, colsActas)
    df = _ensure_cols(df)
    return dfToListOfDicts(df)

# ---------------- Escritura/alta ----------------
def agregarActas(contratoAsociado: str, razon: str, activosAsociados) -> bool:
    """
    Registra un acta
    - contratoAsociado: etiqueta 'id - cliente' o id de contrato
    - razon: texto libre
    - activosAsociados: lista de etiquetas 'ID - Modelo (Cliente)' o cadena
    """
    # Normalizaciones suaves
    contratoAsociado = str(contratoAsociado).strip()
    razon = str(razon).strip()

    # Serializa activos si viene como lista para conservar el formato original en disco
    if isinstance(activosAsociados, list):
        activos_val = json.dumps(activosAsociados, ensure_ascii=False)
    else:
        activos_val = str(activosAsociados).strip()

    df = readTable(actasXlsx, actasCsv, colsActas)
    df = _ensure_cols(df)
    nuevo = {
        "id": str(nextId(df)),
        "contratoAsociado": contratoAsociado,
        "razon": razon,
        "activosAsociados": activos_val,
    }
    df_out = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    writeTable(df_out, actasXlsx, actasCsv)
    return True