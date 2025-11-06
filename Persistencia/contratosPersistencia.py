from typing import List, Dict, Tuple, List
import datetime as dt
import pandas as pd
import ast
from .base import pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf

# === Esquema ===
colsContratos = [
    "id", "cliente", "fechaInicio", "fechaFin", "condiciones", "activosAsociados", "diasNotificar", "estado"]

# === Rutas ===
contratosXlsx, contratosCsv = pathPair("contratos")
'''
# === API ===
def _to_date(x):
    """Convierte string o datetime/date a date."""
    if not x:
        return None
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    if isinstance(x, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(x.strip(), fmt).date()
            except Exception:
                pass
    return None
'''
def nextId(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    idsValidos = pd.to_numeric(df["id"], errors="coerce").dropna()
    if idsValidos.empty:
        return 1
    return int(idsValidos.max()) + 1
'''
def estado(fechaInicio, fechaFin) -> str:
    """Evalúa el estado del contrato según la fecha actual."""
    ini = _to_date(fechaInicio)
    fin = _to_date(fechaFin)
    hoy = dt.date.today()  # siempre date

    if not ini or not fin:
        return "Pendiente"

    # Comparación entre objetos date
    if ini <= hoy <= fin:
        dias_restantes = (fin - hoy).days
        return "Por vencer" if dias_restantes <= 30 else "Vigente"
    elif hoy > fin:
        return "Vencido"
    else:
        return "Pendiente"
'''
def cargarContratos() -> List[Dict]:
    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    return dfToListOfDicts(df)

def guardarContratos(contratos: List[Dict]) -> None:
    df = listOfDictsToDf(contratos, colsContratos)
    writeTable(df, contratosXlsx, contratosCsv)

def agregarContratos(cliente: str, fechaInicio:str, fechaFin:str, condiciones: str, activosAsociados: str,
                    diasNotificar: int) -> Dict:

    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    nuevoId = nextId(df)
    nuevo = {
            "id": str(nuevoId),
            "cliente": cliente,
            "fechaInicio": fechaInicio,
            "fechaFin": fechaFin,
            "condiciones": condiciones,
            "activosAsociados": activosAsociados,
            "diasNotificar": diasNotificar,
            "estado": "Por vencer"#estado(fechaInicio, fechaFin)
        }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)

    writeTable(df, contratosXlsx, contratosCsv)
    return True

def cargarContratosIdCliente() -> List[str]:
    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    if df.empty:
        return []
    nombre_col = "cliente" if "cliente" in df.columns else "estado"
    opciones = [
        f"{int(row['id'])} - {str(row[nombre_col])}"
        for _, row in df.iterrows()
        if pd.notna(row["id"]) and pd.notna(row[nombre_col])
    ]
    return opciones




def obtenerActivosAsociadosPorSeleccion(contratoSeleccionado: str) -> list[str]:
    try:
        df = readTable(contratosXlsx, contratosCsv, colsContratos)
    except Exception:
        return []

    if df.empty:
        return []
    id_sel = contratoSeleccionado.split(" - ")[0].strip()
    fila = df.loc[df["id"].astype(str).str.strip() == id_sel]
    if fila.empty:
        return []
    valor = fila.iloc[0].get("activosAsociados", "")
    if not valor:
        return []
    try:
        lista = ast.literal_eval(valor)
        if isinstance(lista, list):
            return [str(x).strip() for x in lista if str(x).strip()]
    except Exception:
        pass
    return [v.strip() for v in str(valor).split(",") if v.strip()]