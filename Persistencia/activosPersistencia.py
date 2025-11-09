# Persistencia/activosPersistencia.py
import os
import io
from typing import List, Dict, Tuple
from datetime import datetime
import pandas as pd
from .base import pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf

# Esquema definitivo para F-01
colsActivos = [
    "id", "id_unico", "modelo", "serie", "fabricante", "fechaCompra",
    "latitud", "longitud", "cliente", "valor", "tag", "fotos",
    "fechaRegistro", "usuario"
]

activosXlsx, activosCsv = pathPair("activos")
rfidXlsx, rfidCsv         = pathPair("rfid_activos")

rfidCols = [
    "rfid", "modelo", "serie", "fabricante", "fechaCompra",
    "latitud", "longitud", "cliente", "valor", "fotos"
]

def nextId(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return 1 if ids.empty else int(ids.max()) + 1

def cargarActivos() -> List[Dict]:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    # Garantiza columnas del esquema
    for c in colsActivos:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    # Normaliza coordenadas
    df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    return dfToListOfDicts(df)

def cargarActivosDf() -> pd.DataFrame:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    for c in colsActivos:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    return df

def guardarActivos(registros: List[Dict]) -> None:
    df = listOfDictsToDf(registros, colsActivos)
    writeTable(df, activosXlsx, activosCsv)

def existeIdUnico(id_unico: str) -> bool:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if "id_unico" not in df.columns:
        return False
    return df["id_unico"].astype(str).str.strip().str.lower().eq(str(id_unico).strip().lower()).any()

def existeTagEnActivos(tag: str) -> bool:
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if "tag" not in df.columns:
        return False
    return df["tag"].astype(str).str.strip().str.lower().eq(str(tag).strip().lower()).any()

def agregarActivos(
    id_unico: str, modelo: str, serie: str, fabricante: str, fechaCompra: str,
    latitud: float, longitud: float, cliente: str, valor: float, tag: str,
    fotos: str, fechaRegistro: str, usuario: str
) -> bool:
    # Carga y validaciones
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if existeIdUnico(id_unico):
        raise ValueError("El ID único ya existe.")
    if existeTagEnActivos(tag):
        raise ValueError("El tag RFID/QR ya existe.")

    nuevoId = nextId(df)
    nuevo = {
        "id": str(nuevoId),
        "id_unico": str(id_unico).strip(),
        "modelo": modelo,
        "serie": serie,
        "fabricante": fabricante,
        "fechaCompra": fechaCompra,
        "latitud": float(latitud),
        "longitud": float(longitud),
        "cliente": cliente,
        "valor": valor,
        "tag": tag,
        "fotos": fotos,
        "fechaRegistro": fechaRegistro,
        "usuario": usuario
    }
    # Inserta y persiste
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    writeTable(df, activosXlsx, activosCsv)
    return True

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
    fila = dfCat.loc[dfCat["rfid"].astype(str).str.strip().str.lower() == str(rfid_code).strip().lower()]
    if fila.empty:
        return (False, f"No se encontró el RFID '{rfid_code}' en el catálogo.")

    data = fila.iloc[0].to_dict()
    dfAct = readTable(activosXlsx, activosCsv, colsActivos)
    nuevoId = nextId(dfAct)

    # Para importaciones RFID no se fuerza id_unico, queda vacío si no viene en catálogo
    nuevo = {
        "id": str(nuevoId),
        "id_unico": str(nuevoId),
        "modelo": data.get("modelo", ""),
        "serie": data.get("serie", ""),
        "fabricante": data.get("fabricante", ""),
        "fechaCompra": data.get("fechaCompra", ""),
        "latitud": data.get("latitud", ""),
        "longitud": data.get("longitud", ""),
        "cliente": data.get("cliente", ""),
        "valor": data.get("valor", ""),
        "tag": str(rfid_code).strip(),
        "fotos": data.get("fotos", ""),
        "fechaRegistro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": str(usuario)
    }
    for c in colsActivos:
        if c not in nuevo:
            nuevo[c] = ""

    dfAct = pd.concat([dfAct, pd.DataFrame([nuevo])], ignore_index=True)
    writeTable(dfAct, activosXlsx, activosCsv)
    return (True, nuevoId)

def leerCatalogoDesdeObjetoSubido(fileObj, filename: str) -> pd.DataFrame:
    nombre = (filename or "").lower()
    raw = fileObj.read() if hasattr(fileObj, "read") else fileObj
    bio = io.BytesIO(raw)
    if nombre.endswith((".xlsx", ".xls")):
        return pd.read_excel(bio)
    if nombre.endswith(".csv"):
        return pd.read_csv(bio)
    try:
        return pd.read_excel(bio)
    except Exception:
        return pd.read_csv(bio)

def importarActivosMasivoDesdeArchivo(fileObj, filename: str, usuario: str) -> Tuple[bool, Dict]:
    rep = {"insertados": 0, "omitidos": 0, "razones_omision": []}
    try:
        dfIn = leerCatalogoDesdeObjetoSubido(fileObj, filename)
    except Exception as e:
        return (False, {"error": f"No se pudo leer el archivo: {e}"})

    if dfIn is None or dfIn.empty:
        return (False, {"error": "El archivo está vacío o no tiene filas."})

    # Columnas mínimas: id_unico, modelo, serie, fabricante, fechaCompra, latitud, longitud, cliente, valor, tag
    requeridas = ["id_unico", "modelo", "serie", "fabricante", "fechaCompra", "latitud", "longitud", "cliente", "valor", "tag"]
    faltantes = [c for c in requeridas if c not in dfIn.columns]
    if faltantes:
        return (False, {"error": f"Faltan columnas requeridas: {', '.join(faltantes)}"})

    dfAct = readTable(activosXlsx, activosCsv, colsActivos)
    siguienteId = nextId(dfAct)
    nuevos: List[Dict] = []
    vistos_id_unico = set()
    vistos_tag = set()

    for idx, row in dfIn.iterrows():
        data = row.to_dict()
        _id_unico = str(data.get("id_unico", "")).strip()
        _tag = str(data.get("tag", "")).strip()

        if not _id_unico or not data.get("modelo") or not data.get("serie") or not data.get("fabricante"):
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx), "rfid": _tag, "motivo": "Campos obligatorios vacíos"})
            continue

        if _id_unico.lower() in vistos_id_unico or existeIdUnico(_id_unico):
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx), "rfid": _tag, "motivo": "ID único duplicado"})
            continue

        if _tag and (_tag.lower() in vistos_tag or existeTagEnActivos(_tag)):
            rep["omitidos"] += 1
            rep["razones_omision"].append({"fila": int(idx), "rfid": _tag, "motivo": "Tag duplicado"})
            continue

        nuevo = {
            "id": str(siguienteId),
            "id_unico": _id_unico,
            "modelo": data.get("modelo", ""),
            "serie": data.get("serie", ""),
            "fabricante": data.get("fabricante", ""),
            "fechaCompra": str(data.get("fechaCompra", "")),
            "latitud": data.get("latitud", ""),
            "longitud": data.get("longitud", ""),
            "cliente": data.get("cliente", ""),
            "valor": data.get("valor", ""),
            "tag": _tag,
            "fotos": data.get("fotos", ""),
            "fechaRegistro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "usuario": str(usuario),
        }
        for c in colsActivos:
            if c not in nuevo:
                nuevo[c] = ""

        nuevos.append(nuevo)
        vistos_id_unico.add(_id_unico.lower())
        if _tag:
            vistos_tag.add(_tag.lower())
        siguienteId += 1
        rep["insertados"] += 1

    if not nuevos:
        return (True, rep)

    df_out = pd.concat([dfAct, pd.DataFrame(nuevos)], ignore_index=True)
    writeTable(df_out, activosXlsx, activosCsv)
    return (True, rep)

def cargarActivosIdNombre() -> list[str]:
    """
    Devuelve una lista de activos en formato 'ID - Modelo (Cliente)' 
    para mostrar en menús desplegables de contratos o mantenimientos.
    Incluye solo activos con ID único y modelo definidos.
    """
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if df.empty:
        return []

    df = df.dropna(subset=["id", "modelo"])
    opciones = []

    for _, row in df.iterrows():
        id_unico = str(row.get("id_unico", "")).strip()
        modelo = str(row.get("modelo", "")).strip()
        cliente = str(row.get("cliente", "")).strip()
        etiqueta = f"{id_unico} - {modelo}"
        if cliente:
            etiqueta += f" ({cliente})"
        opciones.append(etiqueta)

    return opciones


def _norm_tag(x):
    if x is None:
        return ""
    s = str(x).strip()
    return s.casefold() if s else ""

def existeTagEnActivos(tag: str) -> bool:
    """Devuelve True solo si el tag no vacío ya existe."""
    t = _norm_tag(tag)
    if not t:
        return False
    df = cargarActivosDf()  # o la función que ya usas para traer el DataFrame
    if df is None or df.empty or "tag" not in df.columns:
        return False
    return df["tag"].astype(str).map(_norm_tag).eq(t).any()

def agregarActivos(
    id_unico: str,
    modelo: str,
    serie: str,
    fabricante: str,
    fechaCompra: str,
    latitud: float,
    longitud: float,
    cliente: str,
    valor: float,
    tag: str = "",
    fotos: str = "",
    fechaRegistro: str = "",
    usuario: str = ""
    
):
    # Carga
    df = cargarActivosDf()  # asegura columnas, reemplaza NaN por ""
    if df is None or df.empty:
        df = pd.DataFrame(columns=[
            "id_unico","modelo","serie","fabricante","fechaCompra","latitud","longitud",
            "cliente","valor","tag","fotos","fechaRegistro","usuario"
        ])

    # Normalizaciones
    id_norm  = str(id_unico).strip()
    tag_norm = _norm_tag(tag)
    
    # ⬇️ En agregarActivos, sustituye el chequeo de tag por este bloque
# antes estaba: if existeTagEnActivos(tag): raise ValueError(...)
    if str(tag).strip() and existeTagEnActivos(tag):
        raise ValueError("El tag RFID/QR ya existe.")

    # Unicidad de ID siempre
    if df["id_unico"].astype(str).str.strip().eq(id_norm).any():
        raise ValueError("El ID único ya existe.")

    # Unicidad de tag solo si no está vacío
    if tag_norm:
        if df["tag"].astype(str).map(_norm_tag).eq(tag_norm).any():
            raise ValueError("El tag RFID/QR ya existe.")

    # Ensamble del nuevo registro; guarda el tag tal como lo ingresaron
    nuevo = {
        "id_unico": id_norm,
        "modelo": str(modelo).strip(),
        "serie": str(serie).strip(),
        "fabricante": str(fabricante).strip(),
        "fechaCompra": str(fechaCompra),
        "latitud": float(latitud),
        "longitud": float(longitud),
        "cliente": str(cliente).strip(),
        "valor": float(valor),
        "tag": str(tag).strip(),
        "fotos": str(fotos).strip(),
        "fechaRegistro": str(fechaRegistro),
        "usuario": str(usuario).strip()
    }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True).fillna("")
    guardarActivosDf(df)  # la rutina que ya tengas para persistir en xlsx/csv

    # coherencia de retorno: True o dict, según tu contrato; aquí devuelvo dict
    return nuevo

def guardarActivosDf(df: pd.DataFrame) -> None:
    """Compatibilidad: guardar DataFrame de activos con el backend actual."""
    writeTable(df, activosXlsx, activosCsv)

def existeTagEnActivos(tag: str) -> bool:
    """Devuelve True solo si el tag no vacío ya existe en activos."""
    t = str(tag).strip().lower()
    if t == "":                      # ignorar vacíos por ser campo opcional
        return False
    df = readTable(activosXlsx, activosCsv, colsActivos)
    if "tag" not in df.columns:
        return False
    serie = df["tag"].astype(str).str.strip().str.lower()
    serie = serie[serie != ""]       # descartar vacíos existentes
    return serie.eq(t).any()

# Persistencia/activosPersistencia.py

def cargarHistorialMovimientos(id_activo: str, fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
    """
    Carga el historial de movimientos de un activo entre dos fechas específicas.
    :param id_activo: ID del activo
    :param fecha_inicio: Fecha de inicio para el filtrado (formato 'YYYY-MM-DD')
    :param fecha_fin: Fecha de fin para el filtrado (formato 'YYYY-MM-DD')
    :return: DataFrame con el historial de movimientos filtrado por fechas
    """
    # Supongamos que hay una tabla de movimientos que incluye el id_activo, latitud, longitud, fecha, etc.
    historial_df = readTable('historialMovimientosXlsx', 'historialMovimientosCsv', ['id_activo', 'latitud', 'longitud', 'fecha', 'detalle'])

    # Aseguramos que las fechas estén en formato adecuado
    historial_df['fecha'] = pd.to_datetime(historial_df['fecha'], errors='coerce')

    # Filtramos por el ID del activo y las fechas
    historial_df = historial_df[historial_df['id_activo'] == id_activo]
    historial_df = historial_df[(historial_df['fecha'] >= fecha_inicio) & (historial_df['fecha'] <= fecha_fin)]

    return historial_df

# Persistencia/activosPersistencia.py

def registrarMovimiento(id_activo: str, latitud: float, longitud: float, detalle: str) -> None:
    """
    Registra un movimiento de un activo en la base de datos.
    :param id_activo: ID del activo
    :param latitud: Latitud de la nueva ubicación
    :param longitud: Longitud de la nueva ubicación
    :param detalle: Detalle del movimiento (por ejemplo, "entrada", "salida")
    """
    df_historial = readTable('historialMovimientosXlsx', 'historialMovimientosCsv', ['id_activo', 'latitud', 'longitud', 'fecha', 'detalle'])
    nuevo_movimiento = {
        "id_activo": id_activo,
        "latitud": latitud,
        "longitud": longitud,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detalle": detalle
    }
    df_historial = pd.concat([df_historial, pd.DataFrame([nuevo_movimiento])], ignore_index=True)
    writeTable(df_historial, 'historialMovimientosXlsx', 'historialMovimientosCsv')
