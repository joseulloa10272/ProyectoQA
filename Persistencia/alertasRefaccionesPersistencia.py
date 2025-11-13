# Persistencia/alertasRefaccionesPersistencia.py
from __future__ import annotations
import pandas as pd
from datetime import datetime
from Persistencia.base import pathPair, readTable, writeTable

# Email (opcional)
try:
    from Persistencia.notificacionesEmail import enviar_email
except Exception:
    enviar_email = None

# Resolver correo del usuario
def _email_de_usuario(usuario: str) -> str | None:
    try:
        from Persistencia.usuarioPersistencia import obtenerEmailUsuario as _get
        return _get(usuario)
    except Exception:
        try:
            from Persistencia.usuarioPersistencia import obtenerCorreoUsuario as _get_alt
            return _get_alt(usuario)
        except Exception:
            return None

# Tablas
refXlsx, refCsv   = pathPair("refacciones")
alertXlsx, alertCsv = pathPair("alertasRefacciones")

REF_COLS    = ["id","id_activo","nombre","stock","umbral","actualizado_en"]
ALERTA_COLS = ["id_unico","id_ref","refaccion","stock","umbral","enviado_email","ts"]

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------- Normalización homogénea de llaves ----------
def _norm_ids(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    for c in ("id_unico", "id_ref"):
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df

# ---------- DataFrames base ----------
def _ref_df() -> pd.DataFrame:
    df = readTable(refXlsx, refCsv, REF_COLS)
    if df is None:
        df = pd.DataFrame(columns=REF_COLS)
    # normalización mínima
    for c in ("stock","umbral"):
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0).astype(int)
    df["id"]        = df.get("id","").astype(str).str.strip()
    df["id_activo"] = df.get("id_activo","").astype(str).str.strip()
    df["nombre"]    = df.get("nombre","").astype(str).str.strip()
    return df

# --- dentro de _buzon_df() (dejamos igual lo que ya tienes y reforzamos ts) ---
def _buzon_df() -> pd.DataFrame:
    df = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if df is None:
        df = pd.DataFrame(columns=ALERTA_COLS)
    for c in ("id_unico", "id_ref", "refaccion", "enviado_email"):
        df[c] = df.get(c, "").astype(str).str.strip()
    for c in ("stock", "umbral"):
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0).astype(int)
    # fuerza datetime para ordenar sin mezclar tipos
    df["ts"] = pd.to_datetime(df.get("ts"), errors="coerce")
    df = df.sort_values("ts")
    df = df.drop_duplicates(subset=["id_unico", "id_ref"], keep="last")
    df = df.drop_duplicates(subset=["id_unico", "refaccion"], keep="last")
    return df

# ---------- Evaluación y envío automático ----------

# --- dentro de evaluar_y_enviar_alertas() ---
def evaluar_y_enviar_alertas(usuario: str | None = None) -> pd.DataFrame:
    ref = _ref_df()
    buzon_prev = _buzon_df()  # ya viene con ts en datetime

    if ref.empty:
        writeTable(buzon_prev, alertXlsx, alertCsv)
        return buzon_prev

    crit = ref[ref["stock"] <= ref["umbral"]].copy()
    if crit.empty:
        writeTable(buzon_prev, alertXlsx, alertCsv)
        return buzon_prev

    # normalización y ts como Timestamp (no string)
    now_ts = pd.Timestamp.now()
    crit["id_unico"]   = crit["id_activo"].astype(str).str.strip()
    crit["id_ref"]     = crit["id"].astype(str).str.strip()
    crit["refaccion"]  = crit["nombre"].astype(str).str.strip()
    crit["ts"]         = now_ts
    crit["enviado_email"] = ""

    nuevas = crit[["id_unico","id_ref","refaccion","stock","umbral","enviado_email","ts"]].copy()

    if not buzon_prev.empty:
        left = nuevas.merge(
            buzon_prev[["id_unico","id_ref","enviado_email"]],
            on=["id_unico","id_ref"], how="left", suffixes=("", "_prev")
        )
        left["enviado_email"] = left["enviado_email"].where(
            left["enviado_email"].astype(str).str.strip() != "",
            left["enviado_email_prev"]
        )
        nuevas = left.drop(columns=["enviado_email_prev"], errors="ignore")

    buzon_out = pd.concat([buzon_prev, nuevas], ignore_index=True)

    # asegurar tipo datetime ANTES de ordenar
    buzon_out["ts"] = pd.to_datetime(buzon_out["ts"], errors="coerce")
    buzon_out = buzon_out.sort_values("ts")
    buzon_out = buzon_out.drop_duplicates(subset=["id_unico","id_ref"], keep="last")
    buzon_out = buzon_out.drop_duplicates(subset=["id_unico","refaccion"], keep="last")

    if enviar_email is not None:
        destino = _email_de_usuario(usuario or "")
        if destino:
            pendientes = buzon_out[buzon_out["enviado_email"].astype(str).str.strip() == ""].copy()
            if not pendientes.empty:
                filas = [
                    f"- Activo {r['id_unico']} · Refacción {r['refaccion']} · Stock={r['stock']} / Umbral={r['umbral']}"
                    for _, r in pendientes.iterrows()
                ]
                asunto = "Gestemed · Refacciones bajo umbral"
                cuerpo = ("Hola,\n\nSe detectaron refacciones por debajo del umbral definido:\n\n"
                          + "\n".join(filas)
                          + "\n\nEste mensaje fue generado automáticamente por Gestemed.")
                ok, _ = enviar_email(asunto, cuerpo, destino)
                if ok:
                    marca = f"enviada {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    buzon_out.loc[
                        buzon_out["enviado_email"].astype(str).str.strip() == "", "enviado_email"
                    ] = marca

    # guardar con ts en texto ISO; al leer se volverá a datetime
    buzon_out_to_save = buzon_out.copy()
    buzon_out_to_save["ts"] = buzon_out_to_save["ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
    writeTable(buzon_out_to_save[ALERTA_COLS], alertXlsx, alertCsv)
    return buzon_out[ALERTA_COLS]

# ---------- Lectura del buzón para UI ----------
def cargar_buzon_alertas(f_id_unico: str | None = None, f_estado: str | None = None) -> pd.DataFrame:
    df = _buzon_df()
    if df.empty:
        return df
    if f_id_unico and f_id_unico != "Todos":
        df = df[df["id_unico"] == str(f_id_unico)]
    if f_estado == "Pendientes":
        df = df[df["enviado_email"].astype(str).str.strip() == ""]
    elif f_estado == "Enviadas":
        df = df[df["enviado_email"].astype(str).str.strip() != ""]
    df = df.sort_values(["enviado_email","stock","umbral","ts"], ascending=[True, True, True, False])
    return df.reset_index(drop=True)