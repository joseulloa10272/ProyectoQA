# Persistencia/contratosPersistencia.py
from typing import List, Dict
import pandas as pd
import json
from datetime import datetime, date
from Persistencia.base import pathPair, readTable, writeTable, dfToListOfDicts

# SMTP (opcional)
try:
    from Persistencia.notificacionesEmail import enviar_email
except Exception:
    enviar_email = None

# Resuelve el correo del usuario desde usuarioPersistencia con cualquiera de los nombres típicos
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

# Helpers para evitar variables “no definidas” en tiempo de análisis
def _get_contrato_paths():
    try:
        return contratosXlsx, contratosCsv            # ya declaradas arriba en este mismo módulo
    except NameError:
        return pathPair("contratos")                   # fallback si aún no existen

def _get_cols_contratos() -> list[str]:
    try:
        return colsContratos                          # ya declaradas arriba en este mismo módulo
    except NameError:
        return ["id","cliente","fechaInicio","fechaFin","condiciones",
                "activosAsociados","diasNotificar","estado"]          # mínimo razonable

# Archivos de salida de alertas
alertXlsx, alertCsv = pathPair("alertasContratos")
ALERTA_COLS = ["id_contrato","cliente","fechaFin","dias_restantes","umbral","estado","ts_alerta","notificado"]

__all__ = [
    "cargarContratos", "guardarContratos", "agregarContratos",
    "proximosVencimientos", "activos_de_contrato",
    "generarAlertasVencimiento_en_caliente", "cargarAlertas",
    "marcarAlertaComoNotificada"
]

# ===== Esquema base =====
colsContratos = ["id","cliente","fechaInicio","fechaFin","condiciones","activosAsociados","diasNotificar","estado"]
contratosXlsx, contratosCsv = pathPair("contratos")

# ===== Utilitarios de fecha/estado =====
def _to_date(x) -> date | None:
    if x is None or str(x).strip() == "":
        return None
    try:
        return pd.to_datetime(x).date()
    except Exception:
        return None

def estado(fechaInicio: str, fechaFin: str) -> str:
    hoy = date.today()
    fin = _to_date(fechaFin)
    if fin is None:
        return "Sin fecha fin"
    if fin < hoy:
        return "Vencido"
    dias = (fin - hoy).days
    if dias <= 30:
        return "Por vencer"
    return "Vigente"

def _recalcular_estado_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["fechaFin"] = pd.to_datetime(out["fechaFin"], errors="coerce")
    hoy = pd.to_datetime(date.today())
    out["dias_restantes_tmp"] = (out["fechaFin"] - hoy).dt.days
    out["estado"] = "Vigente"
    out.loc[out["fechaFin"].notna() & (out["fechaFin"].dt.date < date.today()), "estado"] = "Vencido"
    out.loc[(out["estado"] != "Vencido") & (out["dias_restantes_tmp"].between(0, 30, inclusive="both")), "estado"] = "Por vencer"
    return out.drop(columns=["dias_restantes_tmp"])

def _nextId(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return (int(ids.max()) + 1) if not ids.empty else 1

# ===== API de contratos =====
def cargarContratos() -> List[Dict]:
    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    df = _recalcular_estado_df(df)
    writeTable(df, contratosXlsx, contratosCsv)   # mantiene estado al día
    return dfToListOfDicts(df)

def guardarContratos(registros: List[Dict]) -> None:
    df = pd.DataFrame(registros) if isinstance(registros, list) else registros
    for c in colsContratos:
        if c not in df.columns:
            df[c] = ""
    df = _recalcular_estado_df(df[colsContratos].fillna(""))
    writeTable(df, contratosXlsx, contratosCsv)

def agregarContratos(cliente: str, fechaInicio: str, fechaFin: str, condiciones: str,
                     activosAsociados: List[str] | str, diasNotificar: int) -> Dict:
    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    new_id = _nextId(df)
    lista = activosAsociados if isinstance(activosAsociados, list) else [x.strip() for x in str(activosAsociados).split(",") if x.strip()]
    nuevo = {
        "id": str(new_id),
        "cliente": str(cliente).strip(),
        "fechaInicio": str(fechaInicio).strip(),
        "fechaFin": str(fechaFin).strip(),
        "condiciones": str(condiciones).strip(),
        "activosAsociados": json.dumps(lista, ensure_ascii=False),
        "diasNotificar": int(diasNotificar) if str(diasNotificar).strip().isdigit() else 30,
        "estado": estado(fechaInicio, fechaFin),
    }
    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    df = _recalcular_estado_df(df)
    writeTable(df, contratosXlsx, contratosCsv)
    return nuevo

def proximosVencimientos(hasta_dias: int = 90) -> pd.DataFrame:
    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    if df.empty:
        return df
    hoy = pd.to_datetime(date.today())
    fin = pd.to_datetime(df["fechaFin"], errors="coerce")
    df = df.assign(fechaFin=fin)
    df["dias_restantes"] = (df["fechaFin"] - hoy).dt.days
    return df[(df["dias_restantes"] >= 0) & (df["dias_restantes"] <= int(hasta_dias))].copy()

def activos_de_contrato(contratoSeleccionado: str) -> List[str]:
    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    if df.empty or not contratoSeleccionado:
        return []
    id_sel = str(contratoSeleccionado).split(" - ")[0].strip()
    fila = df.loc[df["id"].astype(str).str.strip() == id_sel]
    if fila.empty:
        return []
    raw = fila.iloc[0].get("activosAsociados", "")
    try:
        lista = json.loads(raw) if isinstance(raw, str) else raw
        return [str(x) for x in (lista or [])]
    except Exception:
        return [v.strip() for v in str(raw).split(",") if v.strip()]

def _hoy_pd() -> pd.Timestamp:
    return pd.to_datetime(date.today())

def _recalcular_estado_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["id","cliente","fechaFin","diasNotificar","estado","dias_restantes"])
    df = df.copy()
    df["fechaFin"] = pd.to_datetime(df["fechaFin"], errors="coerce")
    drest = (df["fechaFin"] - _hoy_pd()).dt.days
    estado = pd.Series("Vigente", index=df.index, dtype="object")
    estado = estado.mask(drest <= 30, "Por vencer").mask(drest < 0, "Vencido")
    df["estado"] = estado
    df["dias_restantes"] = drest.astype("Int64")
    return df

def _contratos_df_normalizado() -> pd.DataFrame:
    cxlsx, ccsv = _get_contrato_paths()
    base = readTable(cxlsx, ccsv, _get_cols_contratos() or [])
    if base is None:
        base = pd.DataFrame()
    # alias tolerantes para fechaFin
    if "fechaFin" not in base.columns:
        for k in ("fin","fecha_fin","end","end_date"):
            if k in base.columns:
                base = base.rename(columns={k: "fechaFin"})
                break
        if "fechaFin" not in base.columns:
            base["fechaFin"] = ""
    if "diasNotificar" not in base.columns:
        base["diasNotificar"] = 30
    if "cliente" not in base.columns:
        base["cliente"] = ""
    if "id" not in base.columns:
        base["id"] = ""
    return _recalcular_estado_df(base)

def _dedupe_por_id(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    df["__sort1"] = pd.to_numeric(df["dias_restantes"], errors="coerce").fillna(10**9)
    df["__sort2"] = pd.to_datetime(df["ts_alerta"], errors="coerce")
    df = df.sort_values(["id_contrato","__sort1","__sort2"], ascending=[True, True, False])
    df = df.drop_duplicates(subset=["id_contrato"], keep="first")
    return df.drop(columns=["__sort1","__sort2"], errors="ignore")

def generarAlertasVencimiento_en_caliente() -> pd.DataFrame:
    dfc = _contratos_df_normalizado()
    if dfc.empty:
        df_vacia = readTable(alertXlsx, alertCsv, ALERTA_COLS)
        writeTable(df_vacia, alertXlsx, alertCsv)
        return df_vacia

    dfc["id_contrato"] = dfc["id"].astype(str).str.strip()
    dfc["umbral"] = pd.to_numeric(dfc.get("diasNotificar", 30), errors="coerce").fillna(30).astype(int)

    elegibles = dfc[
        (dfc["dias_restantes"].astype("Int64") >= 0) &
        (dfc["dias_restantes"].astype("Int64") <= dfc["umbral"]) &
        (dfc["estado"] != "Vencido")
    ].copy()

    if elegibles.empty:
        df_vacia = readTable(alertXlsx, alertCsv, ALERTA_COLS)
        writeTable(df_vacia, alertXlsx, alertCsv)
        return df_vacia

    elegibles["ts_alerta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elegibles["notificado"] = ""

    prev = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if not prev.empty:
        prev = prev.dropna(subset=["id_contrato"])
        elegibles = elegibles.merge(prev[["id_contrato","notificado"]], on="id_contrato", how="left", suffixes=("", "_prev"))
        elegibles.loc[elegibles["notificado"].astype(str).eq(""), "notificado"] = elegibles["notificado_prev"].fillna("")
        elegibles = elegibles.drop(columns=["notificado_prev"], errors="ignore")

    out = elegibles[ALERTA_COLS].copy()
    out = _dedupe_por_id(out)
    writeTable(out, alertXlsx, alertCsv)
    return out

def cargarAlertas() -> pd.DataFrame:
    df = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if df is None or df.empty:
        return df
    df = _dedupe_por_id(df)
    if "dias_restantes" in df.columns:
        df = df.sort_values("dias_restantes", na_position="last")
    return df

def marcarAlertaComoNotificada(idx: int, texto: str = "enviada") -> None:
    df = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if 0 <= idx < len(df):
        df.loc[idx, "notificado"] = f"{texto} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        writeTable(df, alertXlsx, alertCsv)

def enviarAlertasVencimiento_por_correo(usuario: str, destinatario: str | None = None) -> tuple[bool, str]:
    df = cargarAlertas()
    if df is None or df.empty:
        return False, "No hay alertas vigentes para enviar."
    if enviar_email is None:
        return False, "El módulo de envío de correos no está disponible."

    to = destinatario or _email_de_usuario(usuario)
    if not to:
        return False, "No se encontró un correo asociado al usuario."

    filas = []
    for _, r in df.iterrows():
        filas.append(
            f"- Contrato {r.get('id_contrato','')} · Cliente {r.get('cliente','')} "
            f"· Vence {r.get('fechaFin','')} · Restan {r.get('dias_restantes','')} días"
        )
    asunto = "Gestemed · Alertas de contratos por vencer"
    cuerpo = (
        "Hola,\n\nEstos contratos se encuentran próximos a vencer según el umbral configurado:\n\n"
        + "\n".join(filas) +
        "\n\nEste mensaje fue generado automáticamente por Gestemed."
    )

    ok, msg = enviar_email(asunto, cuerpo, to)
    if ok:
        df2 = readTable(alertXlsx, alertCsv, ALERTA_COLS)
        if not df2.empty:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            df2["notificado"] = df2["notificado"].astype(str).mask(lambda s: s.str.strip().eq(""), f"enviada {ts}")
            writeTable(df2, alertXlsx, alertCsv)
    return ok, msg
# ==== fin de ALERTAS ====