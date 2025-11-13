import os, sys, hashlib
from typing import Optional
import pandas as pd

# Rutas para importar utilitarios de IO
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import readTable, pathPair

# Esquema esperado
colsUsuarios = [
    "id",
    "nombreUsuario",
    "correo",
    "tipoUsuario",
    "contrasena",
]

usuariosXlsx, usuariosCsv = pathPair("usuarios")

# ---------- utilitarios internos ----------
def _load() -> pd.DataFrame:
    df = readTable(usuariosXlsx, usuariosCsv, colsUsuarios)
    return df.fillna("")

def _norm(s) -> str:
    return "" if s is None else str(s).strip()

def _match_username(df: pd.DataFrame, username: str) -> pd.DataFrame:
    u = _norm(username).lower()
    if df.empty or "nombreUsuario" not in df.columns:
        return pd.DataFrame(columns=colsUsuarios)
    return df[df["nombreUsuario"].astype(str).str.strip().str.lower() == u]

def _check_password(input_pw: str, stored_pw: str) -> bool:
    """Acepta contraseña en texto claro o su hash SHA-256; si el valor luce como bcrypt, lo valida si la librería está disponible."""
    inp = _norm(input_pw)
    saved = _norm(stored_pw)

    # Texto claro
    if saved and inp == saved:
        return True

    # SHA-256 hexadecimal
    sha = hashlib.sha256(inp.encode("utf-8")).hexdigest()
    if saved.lower() == sha.lower():
        return True

    # Bcrypt opcional
    if saved.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt  # type: ignore
            return bcrypt.checkpw(inp.encode("utf-8"), saved.encode("utf-8"))
        except Exception:
            # Si bcrypt no está instalado, se ignora silenciosamente
            pass
    return False

# ---------- API pública ----------
def existeUsuario(nombreUsuario: str) -> bool:
    """Verifica existencia del usuario por coincidencia exacta (case-insensitive)."""
    df = _load()
    return not _match_username(df, nombreUsuario).empty

def validarCredenciales(nombreUsuario: str, contrasena: str) -> bool:
    """Autentica usuario comparando la contraseña en texto claro, SHA-256 o bcrypt si aplica."""
    m = _match_username(_load(), nombreUsuario)
    if m.empty:
        return False
    # Si existen duplicados, se acepta la primera coincidencia válida
    for _, row in m.iterrows():
        if _check_password(contrasena, row.get("contrasena", "")):
            return True
    return False

def obtenerEmailUsuario(nombreUsuario: str) -> Optional[str]:
    m = _match_username(_load(), nombreUsuario)
    if m.empty:
        return None
    val = _norm(m.iloc[0].get("correo", ""))
    return val or None

# Alias de compatibilidad
def obtenerCorreoUsuario(nombreUsuario: str) -> Optional[str]:
    return obtenerEmailUsuario(nombreUsuario)

def obtenerTipoUsuario(nombreUsuario: str) -> Optional[str]:
    m = _match_username(_load(), nombreUsuario)
    if m.empty:
        return None
    val = _norm(m.iloc[0].get("tipoUsuario", ""))
    return val or None