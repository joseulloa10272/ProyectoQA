import pandas as pd
from pathlib import Path

import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import readTable, writeTable, pathPair, ensureFile

# Ruta del archivo Excel donde se guardarán los movimientos de activos
MOVIMIENTOS_FILE_PATH_XLSX, MOVIMIENTOS_FILE_PATH_CSV = Path('data/movimientosActivos.xlsx'), Path('data/movimientosActivos.csv')

# Asegura que el archivo de movimientos de activos exista
def initialize_movimientos_file():
    ensureFile(MOVIMIENTOS_FILE_PATH_XLSX, MOVIMIENTOS_FILE_PATH_CSV, ["ID_Activo", "Fecha_Movimiento", "Ubicación", "Tipo_Movimiento", "Estado", "Fotos", "Piezas", "Firma Digital"])

# Cargar los movimientos de activos
def load_movimientos():
    # Cargar el archivo asegurando que existe
    initialize_movimientos_file()
    return readTable(MOVIMIENTOS_FILE_PATH_XLSX, MOVIMIENTOS_FILE_PATH_CSV, ["ID_Activo", "Fecha_Movimiento", "Ubicación", "Tipo_Movimiento", "Estado", "Fotos", "Piezas", "Firma Digital"])

# Guardar los movimientos de activos
def save_movimientos(df):
    writeTable(df, MOVIMIENTOS_FILE_PATH_XLSX, MOVIMIENTOS_FILE_PATH_CSV)

# Agregar un nuevo movimiento de activo
def add_movimiento(id_activo, fecha_movimiento, ubicacion, tipo_movimiento, estado, fotos, piezas, firma):
    df = load_movimientos()
    new_entry = {
        "ID_Activo": id_activo,
        "Fecha_Movimiento": fecha_movimiento,
        "Ubicación": ubicacion,
        "Tipo_Movimiento": tipo_movimiento,
        "Estado": estado,
        "Fotos": fotos,
        "Piezas": piezas,
        "Firma Digital": firma
    }
    
    # Convertir el diccionario a DataFrame para concatenar
    new_entry_df = pd.DataFrame([new_entry])

    # Usar pd.concat en lugar de append
    df = pd.concat([df, new_entry_df], ignore_index=True)

    save_movimientos(df)

# Función para filtrar los movimientos de activos
def filter_movimientos(fecha_inicio, fecha_fin, ubicacion):
    df = load_movimientos()
    
    # Convertir las fechas de entrada a tipo datetime64
    fecha_inicio = pd.to_datetime(fecha_inicio)
    fecha_fin = pd.to_datetime(fecha_fin)
    
    df["Fecha_Movimiento"] = pd.to_datetime(df["Fecha_Movimiento"])
    
    # Filtrar por fecha y ubicación
    filtered_data = df[(df["Fecha_Movimiento"] >= fecha_inicio) & (df["Fecha_Movimiento"] <= fecha_fin) & (df["Ubicación"] <= ubicacion)]
    
    return filtered_data
