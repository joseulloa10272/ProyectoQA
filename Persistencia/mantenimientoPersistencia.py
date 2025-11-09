import pandas as pd

from pathlib import Path

import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import readTable, writeTable, pathPair, ensureFile

# Ruta del archivo Excel donde se guardarán las órdenes de mantenimiento
MANTENIMIENTO_FILE_PATH_XLSX, MANTENIMIENTO_FILE_PATH_CSV = Path('data/mantenimiento.xlsx'), Path('data/mantenimiento.csv')

# Asegura que el archivo de mantenimiento exista
def initialize_mantenimiento_file():
    ensureFile(MANTENIMIENTO_FILE_PATH_XLSX, MANTENIMIENTO_FILE_PATH_CSV, ["ID_Orden", "Fecha", "Responsable", "Tareas", "Estado"])

# Cargar las órdenes de mantenimiento
def load_mantenimiento():
    # Cargar el archivo asegurando que existe
    initialize_mantenimiento_file()
    return readTable(MANTENIMIENTO_FILE_PATH_XLSX, MANTENIMIENTO_FILE_PATH_CSV, ["ID_Orden", "Fecha", "Responsable", "Tareas", "Estado"])

# Guardar las órdenes de mantenimiento
def save_mantenimiento(df):
    writeTable(df, MANTENIMIENTO_FILE_PATH_XLSX, MANTENIMIENTO_FILE_PATH_CSV)

# Crear una nueva orden de mantenimiento
def create_mantenimiento(id_orden, fecha, responsable, tareas, estado):
    df = load_mantenimiento()
    new_order = {
        "ID_Orden": id_orden,
        "Fecha": fecha,
        "Responsable": responsable,
        "Tareas": tareas,
        "Estado": estado
    }
    
    # Convertir el diccionario a DataFrame para concatenar
    new_order_df = pd.DataFrame([new_order])

    # Usar pd.concat en lugar de append
    df = pd.concat([df, new_order_df], ignore_index=True)

    save_mantenimiento(df)

# Actualizar el estado de una orden de mantenimiento
def update_mantenimiento_estado(id_orden, estado):
    df = load_mantenimiento()
    df.loc[df["ID_Orden"] == id_orden, "Estado"] = estado
    save_mantenimiento(df)
