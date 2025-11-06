import os
import io
from typing import List, Dict, Tuple, List
from datetime import datetime, date
import pandas as pd
import sys
from .base import pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf

# === Esquema ===
colsActivos = [
    "id", "modelo", "serie", "fabricante", "fechaCompra", "pais", "provincia", "canton", "cliente",
    "valor", "tag", "fotos", "fechaRegistro", "usuario"
]

# === Rutas ===
activosXlsx, activosCsv = pathPair("activos")

rfidXlsx, rfidCsv = pathPair("rfid_activos")

rfidCols = ["rfid", "modelo", "serie", "fabricante", "fechaCompra", "pais", "provincia", "canton", "cliente", "valor", "fotos"]

# === API ===

def nextId(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    idsValidos = pd.to_numeric(df["id"], errors="coerce").dropna()
    if idsValidos.empty:
        return 1
    return int(idsValidos.max()) + 1

def cargarActivos() -> List[Dict]:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    return dfToListOfDicts(df)

def guardarActivos(activos: List[Dict]) -> None:
    df = listOfDictsToDf(activos, colsActivos)
    writeTable(df, activosXlsx, activosCsv)

def agregarActivos(modelo: str, serie: str, fabricante: str, fechaCompra: str, pais: str,
                    provincia: str, canton: str, cliente: str, valor: str, tag: str, fotos: str,  
                    fechaRegistro: str, usuario: str) -> Dict:

    df = readTable(activosXlsx, activosCsv, colsActivos)
    nuevoId = nextId(df)
    nuevo = {
            "id": str(nuevoId),
            "modelo": modelo,
            "serie": serie,
            "fabricante": fabricante,
            "fechaCompra": fechaCompra,
            "pais": pais,
            "provincia": provincia,
            "canton": canton,
            "cliente": cliente,
            "valor": valor,
            "tag": tag,
            "fotos": fotos,
            "fechaRegistro": fechaRegistro,
            "usuario": usuario
        }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)

    writeTable(df, activosXlsx, activosCsv)
    return True

def cargarActivosDf() -> pd.DataFrame:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    for c in colsActivos:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    return df

def cargarCatalogoRfidDf() -> pd.DataFrame:
    df = readTable(rfidXlsx, rfidCsv, rfidCols)
    for c in rfidCols:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    return df


def registrarActivosRfid(rfid_code: str, usuario: str) -> Tuple[bool, str | int]:
    
    if not rfid_code or not str(rfid_code).strip():
        return (False, "Debe indicar un código RFID.")

    
    dfCat = cargarCatalogoRfidDf()
    if dfCat.empty:
        return (False, "El catálogo RFID está vacío.")

    fila = dfCat.loc[
        dfCat["rfid"].astype(str).str.strip().str.lower() == str(rfid_code).strip().lower()
    ]
    if fila.empty:
        return (False, f"No se encontró el RFID '{rfid_code}' en el catálogo.")

    data = fila.iloc[0].to_dict()

    dfAct = readTable(activosXlsx, activosCsv, colsActivos)
    nuevoId = nextId(dfAct)

    nuevo = {
        "id": str(nuevoId),
        "modelo":      data.get("modelo", ""),
        "serie":       data.get("serie", ""),
        "fabricante":  data.get("fabricante", ""),
        "fechaCompra": data.get("fechaCompra", ""),
        "pais":        data.get("pais", ""),
        "provincia":   data.get("provincia", ""),
        "canton":      data.get("canton", ""),
        "cliente":     data.get("cliente", ""),
        "valor":       data.get("valor", ""),
        "tag":         str(rfid_code).strip(),
        "fotos":       data.get("fotos", ""),
        "fechaRegistro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario":     str(usuario)
    }

    for c in colsActivos:
        if c not in nuevo:
            nuevo[c] = ""

    dfAct = pd.concat([dfAct, pd.DataFrame([nuevo])], ignore_index=True)
    writeTable(dfAct, activosXlsx, activosCsv)
    return (True, nuevoId)

def existeTagEnActivos(tag: str) -> bool:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if "tag" not in df.columns:
        return False
    return df["tag"].astype(str).str.strip().str.lower().eq(str(tag).strip().lower()).any()

def leerCatalogoDesdeObjetoSubido(fileObj, filename: str) -> pd.DataFrame:
    nombre = (filename or "").lower()
    if hasattr(fileObj, "read"):
        raw = fileObj.read()
        bio = io.BytesIO(raw)
    else:
        bio = io.BytesIO(fileObj)

    if nombre.endswith(".xlsx") or nombre.endswith(".xls"):
        df = pd.read_excel(bio)
    elif nombre.endswith(".csv"):
        df = pd.read_csv(bio)
    else:
        try:
            df = pd.read_excel(bio)
        except Exception:
            df = pd.read_csv(bio)
    return df

def importarActivosMasivoDesdeArchivo(fileObj, filename: str, usuario: str) -> Tuple[bool, Dict]:
    rep = {"insertados": 0, "omitidos": 0, "razones_omision": []}

    try:
        dfIn = leerCatalogoDesdeObjetoSubido(fileObj, filename)
    except Exception as e:
        return (False, {"error": f"No se pudo leer el archivo: {e}"})

    if dfIn is None or dfIn.empty:
        return (False, {"error": "El archivo está vacío o no tiene filas."})

    if "rfid" not in dfIn.columns:
        return (False, {"error": "El archivo no contiene la columna 'rfid'."})

    dfAct = readTable(activosXlsx, activosCsv, colsActivos)
    siguienteId = nextId(dfAct)

    nuevosRegistros: List[Dict] = []
    vistosEnBatch = set() 

    for idx, row in dfIn.iterrows():
        data = row.to_dict()
        rfidCode = str(data.get("rfid", "")).strip()

        if not rfidCode:
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx), "rfid": "", "motivo": "RFID vacío"})
            continue

        key = rfidCode.lower()
        if key in vistosEnBatch:
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx), "rfid": rfidCode, "motivo": "RFID duplicado en el archivo"})
            continue

        if existeTagEnActivos(rfidCode):
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx), "rfid": rfidCode, "motivo": "RFID ya existe en activos"})
            continue

        nuevo = {
            "id": str(siguienteId),
            "modelo":        data.get("modelo", ""),
            "serie":         data.get("serie", ""),
            "fabricante":    data.get("fabricante", ""),
            "fechaCompra":   data.get("fechaCompra", ""),
            "pais":          data.get("pais", ""),
            "provincia":     data.get("provincia", ""),
            "canton":        data.get("canton", ""),
            "cliente":       data.get("cliente", ""),
            "valor":         data.get("valor", ""),
            "tag":           rfidCode,
            "fotos":         data.get("fotos", ""),
            "fechaRegistro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "usuario":       str(usuario),
        }
        for c in colsActivos:
            if c not in nuevo:
                nuevo[c] = ""

        nuevosRegistros.append(nuevo)
        vistosEnBatch.add(key)
        siguienteId += 1
        rep["insertados"] += 1

    if not nuevosRegistros:
        return (True, rep)

    df_out = pd.concat([dfAct, pd.DataFrame(nuevosRegistros)], ignore_index=True)
    writeTable(df_out, activosXlsx, activosCsv)
    return (True, rep)

def cargarActivosIdNombre() -> List[str]:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if df.empty:
        return []
    nombre_col = "nombre" if "nombre" in df.columns else "serie"
    opciones = [
        f"{int(row['id'])} - {str(row[nombre_col])}"
        for _, row in df.iterrows()
        if pd.notna(row["id"]) and pd.notna(row[nombre_col])
    ]
    return opciones