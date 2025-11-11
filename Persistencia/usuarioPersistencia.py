# Persistencia/usuarioPersistencia.py
import os
from typing import List, Dict, Optional
import pandas as pd
import sys

from .base import pathPair, readTable, writeTable, dfToListOfDicts, listOfDictsToDf
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# validaciones (si no existe el módulo se continúa sin romper)
try:
    from Validaciones.usuarioValidaciones import existeUsuario  # firma: existeUsuario(nombreUsuario) -> bool
except Exception:
    def existeUsuario(_nombre: str) -> bool:
        return False

# ===== Esquema y rutas =====
colsUsuarios = [
    "id",
    "nombreUsuario",
    "correo",
    "tipoUsuario",
    "contrasena",
]
usuariosXlsx, usuariosCsv = pathPair("usuarios")


# ===== Normalizadores =====
def _norm_str(x) -> str:
    return "" if x is None else str(x).strip()

def _casefold(x) -> str:
    s = _norm_str(x)
    return s.casefold() if s else ""


# ===== Utilitarios internos =====
def _ensure_cols(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for c in colsUsuarios:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    # tipos básicos
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    return df[colsUsuarios]

def nextId(df: pd.DataFrame) -> int:
    df = _ensure_cols(df)
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return 1 if ids.empty else int(ids.max()) + 1


# ===== API de lectura/escritura =====
def cargarUsuarios() -> List[Dict]:
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
    df = _ensure_cols(df)
    return dfToListOfDicts(df)

def cargarUsuariosDf() -> pd.DataFrame:
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
    return _ensure_cols(df)

def guardarUsuarios(usuarios: List[Dict]) -> None:
    df = listOfDictsToDf(usuarios, colsUsuarios)
    df = _ensure_cols(df)
    writeTable(df, usuariosXlsx, usuariosCsv)


# ===== Altas y bajas =====
def agregarUsuario(nombreUsuario: str, correo: str, tipoUsuario: str, contrasena: str) -> bool:
    """
    Inserta un usuario nuevo si el nombre no existe; retorna True en inserción, False si ya existía.
    """
    nombre = _norm_str(nombreUsuario)
    mail   = _norm_str(correo)

    # verificación con validador externo y con la tabla local
    if existeUsuario(nombre):
        return False

    df = cargarUsuariosDf()
    ya_existe = df["nombreUsuario"].astype(str).str.strip().str.casefold().eq(nombre.casefold()).any()
    if ya_existe:
        return False

    # opcional: evitar correos duplicados
    if mail and df["correo"].astype(str).str.strip().str.casefold().eq(mail.casefold()).any():
        # si prefieres permitir duplicados, elimina este bloque
        return False

    nuevo = {
        "id": str(nextId(df)),
        "nombreUsuario": nombre,
        "correo": mail,
        "tipoUsuario": _norm_str(tipoUsuario),
        "contrasena": _norm_str(contrasena),
    }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    writeTable(df[colsUsuarios], usuariosXlsx, usuariosCsv)
    return True

def eliminarUsuario(id_usuario: str) -> bool:
    df = cargarUsuariosDf()
    antes = len(df)
    df = df[df["id"].astype(str) != str(id_usuario)]
    if len(df) < antes:
        writeTable(df[colsUsuarios], usuariosXlsx, usuariosCsv)
        return True
    return False


# ===== Consultas =====
def obtenerTipoUsuario(nombreUsuario: str) -> Optional[str]:
    """
    Devuelve el tipo de usuario o None si no se encontró.
    Evita excepciones cuando el usuario no existe.
    """
    nombre = _casefold(nombreUsuario)
    if not nombre:
        return None
    df = cargarUsuariosDf()
    m = df["nombreUsuario"].astype(str).str.strip().str.casefold().eq(nombre)
    if not m.any():
        return None
    return _norm_str(df.loc[m].iloc[0]["tipoUsuario"])

# === Getters de correo y endurecimiento de tipo de usuario ===

def _norm_casefold(x) -> str:
    return "" if x is None else str(x).strip().casefold()

def obtenerEmailUsuario(nombreUsuario: str) -> str | None:
    """
    Devuelve el correo asociado a 'nombreUsuario' haciendo coincidencia
    insensible a mayúsculas y espacios. Retorna None si no encuentra.
    """
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
    if df is None or df.empty:
        return None

    u = _norm_casefold(nombreUsuario)
    serie_nombres = df["nombreUsuario"].astype(str).str.strip().str.casefold()
    fila = df.loc[serie_nombres == u]

    if not fila.empty:
        correo = str(fila.iloc[0].get("correo", "")).strip()
        return correo or None

    # Fallback: si te pasan directamente un e-mail como “usuario”
    serie_correos = df["correo"].astype(str).str.strip().str.casefold()
    fila = df.loc[serie_correos == u]
    if not fila.empty:
        correo = str(fila.iloc[0].get("correo", "")).strip()
        return correo or None

    return None

# Alias usado en otros módulos (misma lógica)
def obtenerCorreoUsuario(nombreUsuario: str) -> str | None:
    return obtenerEmailUsuario(nombreUsuario)

def obtenerTipoUsuario(nombreUsuario: str) -> str | None:
    """
    Devuelve el tipo de usuario o None si no hay coincidencia,
    evitando indexaciones sobre filas vacías.
    """
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
    if df is None or df.empty:
        return None
    u = _norm_casefold(nombreUsuario)
    fila = df.loc[df["nombreUsuario"].astype(str).str.strip().str.casefold() == u]
    if fila.empty:
        return None
    return str(fila.iloc[0].get("tipoUsuario", "")).strip() or None

def obtenerUsuarioPorNombre(nombreUsuario: str) -> Optional[Dict]:
    """
    Regresa el registro completo del usuario como diccionario, o None si no existe.
    """
    nombre = _casefold(nombreUsuario)
    if not nombre:
        return None
    df = cargarUsuariosDf()
    m = df["nombreUsuario"].astype(str).str.strip().str.casefold().eq(nombre)
    if not m.any():
        return None
    return df.loc[m].iloc[0][colsUsuarios].to_dict()

def actualizarCorreoUsuario(nombreUsuario: str, nuevoCorreo: str) -> bool:
    """
    Actualiza el correo del usuario; retorna True si se actualizó una fila.
    """
    nombre = _casefold(nombreUsuario)
    df = cargarUsuariosDf()
    m = df["nombreUsuario"].astype(str).str.strip().str.casefold().eq(nombre)
    if not m.any():
        return False
    df.loc[m, "correo"] = _norm_str(nuevoCorreo)
    writeTable(df[colsUsuarios], usuariosXlsx, usuariosCsv)
    return True