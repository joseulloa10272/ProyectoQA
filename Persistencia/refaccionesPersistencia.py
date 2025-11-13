# Persistencia/refaccionesPersistencia.py
from __future__ import annotations
import json
from typing import List, Dict, Tuple
from datetime import datetime
import pandas as pd

from Persistencia.base import pathPair, readTable, writeTable
from Persistencia.activosPersistencia import cargarActivosDf, cargarActivosIdNombre

# Archivos
refXlsx, refCsv = pathPair("refacciones")
movXlsx, movCsv = pathPair("refaccionesMov")
alertXlsx, alertCsv = pathPair("alertasRefacciones")

# Esquemas
REF_COLS   = ["id_ref","id_activo","id_unico","nombre","modeloEquipo","stock","umbral","actualizado_en"]
MOV_COLS   = ["ts","id_activo","id_ref","tipo","cantidad","motivo"]
ALERTA_COLS= ["ts","id_activo","id_unico","id_ref","refaccion","stock","umbral","enviado_email"]

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _next_id(df: pd.DataFrame, col: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 1
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return int(s.max()) + 1 if not s.empty else 1

# --------------------- CARGAS BÁSICAS ---------------------
def _ref_df() -> pd.DataFrame:
    df = readTable(refXlsx, refCsv, REF_COLS)
    for c in REF_COLS:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)
    df["umbral"] = pd.to_numeric(df["umbral"], errors="coerce").fillna(0).astype(int)
    return df

def _mov_df() -> pd.DataFrame:
    df = readTable(movXlsx, movCsv, MOV_COLS)
    for c in MOV_COLS:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)
    return df

def _alert_df() -> pd.DataFrame:
    df = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    for c in ALERTA_COLS:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    return df

# --------------------- API: CATÁLOGO DE REFACCIONES ---------------------
def etiquetas_activos() -> List[str]:
    """['id_unico - Modelo (Cliente)', ...] para usar en menús."""
    return cargarActivosIdNombre()

def refacciones_de_activo(id_activo: str | int) -> pd.DataFrame:
    df = _ref_df()
    if df.empty: 
        return df
    return df[df["id_activo"].astype(str).str.strip() == str(id_activo).strip()].sort_values("nombre")

def agregar_refaccion(id_activo: str|int, id_unico: str, nombre: str, modeloEquipo: str = "",
                      stock_inicial: int = 0, umbral: int = 0) -> Dict:
    df = _ref_df()
    nuevo_id = _next_id(df, "id_ref")
    row = {
        "id_ref": str(nuevo_id),
        "id_activo": str(id_activo).strip(),
        "id_unico": str(id_unico).strip(),
        "nombre": str(nombre).strip(),
        "modeloEquipo": str(modeloEquipo or "").strip(),
        "stock": int(stock_inicial or 0),
        "umbral": int(umbral or 0),
        "actualizado_en": _now(),
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    writeTable(df[REF_COLS], refXlsx, refCsv)
    _verificar_umbral_y_alertar(row)  # alerta inmediata si ya entra bajo umbral
    return row

def actualizar_umbral(id_activo: str|int, id_ref: str|int, nuevo_umbral: int) -> None:
    df = _ref_df()
    m = (df["id_activo"].astype(str).str.strip() == str(id_activo).strip()) & \
        (df["id_ref"].astype(str).str.strip() == str(id_ref).strip())
    if not m.any():
        return
    df.loc[m, "umbral"] = int(nuevo_umbral)
    df.loc[m, "actualizado_en"] = _now()
    writeTable(df[REF_COLS], refXlsx, refCsv)
    _verificar_umbral_y_alertar(df.loc[m].iloc[0].to_dict())

# --------------------- API: MOVIMIENTOS ---------------------
def movimientos(id_activo: str|int | None = None) -> pd.DataFrame:
    df = _mov_df()
    return df if id_activo is None else df[df["id_activo"].astype(str) == str(id_activo)]

def registrar_movimiento(id_activo: str|int, id_ref: str|int, tipo: str, cantidad: int, motivo: str = "") -> Dict:
    """tipo: 'entrada' o 'salida'."""
    if tipo not in ("entrada","salida"):
        raise ValueError("Tipo inválido, use 'entrada' o 'salida'.")
    cant = int(cantidad or 0)
    if cant <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    # 1) actualizar catálogo
    df = _ref_df()
    m = (df["id_activo"].astype(str) == str(id_activo)) & (df["id_ref"].astype(str) == str(id_ref))
    if not m.any():
        raise ValueError("Refacción no encontrada para ese activo.")
    signo = 1 if tipo == "entrada" else -1
    df.loc[m, "stock"] = (df.loc[m, "stock"].astype(int) + signo * cant).clip(lower=0)
    df.loc[m, "actualizado_en"] = _now()
    writeTable(df[REF_COLS], refXlsx, refCsv)

    # 2) registrar movimiento
    mv = _mov_df()
    fila = {
        "ts": _now(),
        "id_activo": str(id_activo),
        "id_ref": str(id_ref),
        "tipo": tipo,
        "cantidad": int(cant),
        "motivo": str(motivo or "").strip(),
    }
    mv = pd.concat([mv, pd.DataFrame([fila])], ignore_index=True)
    writeTable(mv[MOV_COLS], movXlsx, movCsv)

    # 3) verificar umbral y alertar
    reg = df.loc[m].iloc[0].to_dict()
    _verificar_umbral_y_alertar(reg)

    return fila

# --------------------- ALERTAS (crear, cargar, enviar) ---------------------
def _verificar_umbral_y_alertar(reg_ref: Dict) -> None:
    """Si stock <= umbral, registra una alerta pendiente de envío; evita duplicados por id_activo+id_ref con mismo ts-dia."""
    stock = int(reg_ref.get("stock") or 0)
    umbral = int(reg_ref.get("umbral") or 0)
    if stock > umbral:
        return
    al = _alert_df()
    # dedupe: alerta “vigente” por refacción sin 'enviado_email'
    ya = (al["id_activo"].astype(str) == str(reg_ref.get("id_activo"))) & \
         (al["id_ref"].astype(str) == str(reg_ref.get("id_ref"))) & \
         (al["enviado_email"].astype(str).str.strip() == "")
    if ya.any():
        # refresca stock/umbral y ts
        i = al.index[ya][0]
        al.at[i, "stock"] = stock
        al.at[i, "umbral"] = umbral
        al.at[i, "ts"] = _now()
    else:
        fila = {
            "ts": _now(),
            "id_activo": str(reg_ref.get("id_activo","")),
            "id_unico": str(reg_ref.get("id_unico","")),
            "id_ref": str(reg_ref.get("id_ref","")),
            "refaccion": str(reg_ref.get("nombre","")),
            "stock": stock,
            "umbral": umbral,
            "enviado_email": "",
        }
        al = pd.concat([al, pd.DataFrame([fila])], ignore_index=True)
    writeTable(al[ALERTA_COLS], alertXlsx, alertCsv)

def alertas_vigentes() -> pd.DataFrame:
    """Devuelve alertas deduplicadas por id_activo+id_ref con prioridad a las no enviadas."""
    df = _alert_df()
    if df.empty:
        return df
    df = df.sort_values(["id_activo","id_ref","enviado_email","ts"], ascending=[True, True, True, False])
    df = df.drop_duplicates(subset=["id_activo","id_ref"], keep="first")
    return df

def marcar_alerta_enviada(id_activo: str|int, id_ref: str|int) -> None:
    df = _alert_df()
    m = (df["id_activo"].astype(str) == str(id_activo)) & (df["id_ref"].astype(str) == str(id_ref)) & (df["enviado_email"].astype(str).str.strip() == "")
    if not m.any():
        return
    df.loc[m, "enviado_email"] = f"enviada {_now()}"
    writeTable(df[ALERTA_COLS], alertXlsx, alertCsv)

# Envío por correo: se ofrece aquí para que el menú lo use directo
def enviar_alertas_por_correo(usuario: str, destinatario: str | None = None) -> tuple[bool, str]:
    # Resolver canal y correo
    try:
        from Persistencia.notificacionesEmail import enviar_email
    except Exception:
        enviar_email = None
    if enviar_email is None:
        return False, "El módulo de envío de correos no está disponible."

    to = destinatario
    if not to:
        try:
            from Persistencia.usuarioPersistencia import obtenerEmailUsuario as _get
            to = _get(usuario)
        except Exception:
            try:
                from Persistencia.usuarioPersistencia import obtenerCorreoUsuario as _get_alt
                to = _get_alt(usuario)
            except Exception:
                to = None
    if not to:
        return False, "No se encontró un correo asociado al usuario."

    df = alertas_vigentes()
    if df is None or df.empty:
        return False, "No hay alertas vigentes de refacciones."

    filas = []
    for _, r in df.iterrows():
        filas.append(f"- Activo {r.get('id_unico','')} · Refacción {r.get('refaccion','')} · Stock {r.get('stock','')} / Umbral {r.get('umbral','')}")

    asunto = "GESTEMED · Alertas de refacciones bajo umbral"
    cuerpo = "Hola,\n\nLas siguientes refacciones están en o por debajo del umbral configurado:\n\n" + "\n".join(filas) + "\n\nEste mensaje fue generado automáticamente por GESTEMED."
    ok, msg = enviar_email(asunto, cuerpo, to)

    if ok:
        # marca todas como enviadas
        df2 = _alert_df()
        df2.loc[df2["enviado_email"].astype(str).str.strip() == "", "enviado_email"] = f"enviada {_now()}"
        writeTable(df2[ALERTA_COLS], alertXlsx, alertCsv)
        return True, "Correo enviado correctamente."
    return False, msg