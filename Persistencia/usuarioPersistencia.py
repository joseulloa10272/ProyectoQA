import os
from typing import List, Dict
import pandas as pd
import sys
from .base import pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Validaciones.usuarioValidaciones import existeUsuario

def __init__(self):
        self.apps = []
        
# === Esquema de usuarios ===
colsUsuarios = [
    "id",        
    "nombreUsuario",
    "correo", 
    "tipoUsuario",
    "contrasena"   
]

# === Rutas ===
usuariosXlsx, usuariosCsv = pathPair("usuarios")

# === Funciones auxiliares ===
def nextId(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    # Ignora valores vacíos o no numéricos
    idsValidos = pd.to_numeric(df["id"], errors="coerce").dropna()
    if idsValidos.empty:
        return 1
    return int(idsValidos.max()) + 1

# === API pública ===
def cargarUsuarios() -> List[Dict]:
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
    return dfToListOfDicts(df)

def guardarUsuarios(usuarios: List[Dict]) -> None: 
    df = listOfDictsToDf(usuarios, colsUsuarios)
    writeTable(df, usuariosXlsx, usuariosCsv)

def agregarUsuario(nombreUsuario: str, correo: str, tipoUsuario: str, contrasena: str) -> Dict:
    
    existe = existeUsuario(nombreUsuario)
    if existe == True:
        return False
    else:
        
        df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
        nuevo_id = nextId(df)
        nuevo = {
            "id": str(nuevo_id),
            "nombreUsuario": nombreUsuario,
            "correo": correo,
            "tipoUsuario": tipoUsuario,
            "contrasena": contrasena
        }
        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)

        writeTable(df, usuariosXlsx, usuariosCsv)
        return True

def eliminarUsuario(id_usuario: str) -> bool:
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
    antes = len(df)
    df = df[df["id"] != str(id_usuario)]
    if len(df) < antes:
        writeTable(df, usuariosXlsx, usuariosCsv)
        return True
    return False

def obtenerTipoUsuario(nombreUsuario: str) -> str | None:
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)

    nombreUsuario = str(nombreUsuario).strip().lower()
    fila = df.loc[df["nombreUsuario"].astype(str).str.strip().str.lower() == nombreUsuario]

    return str(fila.iloc[0]["tipoUsuario"])
