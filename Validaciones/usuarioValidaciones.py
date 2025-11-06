import os
from typing import List, Dict
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import readTable, pathPair


colsUsuarios = [
    "id",            
    "nombreUsuario",
    "correo",  
    "tipoUsuario",
    "contrasena"  
]

usuariosXlsx, usuariosCsv = pathPair("usuarios")


def existeUsuario(nombreUsuario: str) -> bool:
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)

    if df.empty or "nombreUsuario" not in df.columns:
        return False

    nombreUsuario = str(nombreUsuario).strip().lower()
    coincidencias = df["nombreUsuario"].astype(str).str.strip().str.lower() == nombreUsuario

    return coincidencias.any()


    
