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

# ===== Esquema base =====
colsContratos = [
    "id","cliente","fechaInicio","fechaFin","condiciones",
    "activosAsociados","diasNotificar","estado"
]
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

def _hoy_pd() -> pd.Timestamp:
    return pd.to_datetime(date.today())

def _recalcular_estado_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Única rutina de recálculo de estado y días restantes, usada por todo el módulo.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["id","cliente","fechaFin","diasNotificar","estado","dias_restantes"])
    df = df.copy()
    df["fechaFin"] = pd.to_datetime(df["fechaFin"], errors="coerce")
    drest = (df["fechaFin"] - _hoy_pd()).dt.days
    estado_series = pd.Series("Vigente", index=df.index, dtype="object")
    estado_series = estado_series.mask(drest <= 30, "Por vencer").mask(drest < 0, "Vencido")
    df["estado"] = estado_series
    df["dias_restantes"] = pd.Series(drest, dtype="Int64")
    return df

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
    lista = activosAsociados if isinstance(activosAsociados, list) else [
        x.strip() for x in str(activosAsociados).split(",") if x.strip()
    ]
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
    try:
        generarAlertasVencimiento_en_caliente()
    except Exception:
        pass
    return nuevo

def proximosVencimientos(hasta_dias: int = 90) -> pd.DataFrame:
    df = readTable(contratosXlsx, contratosCsv, colsContratos)
    if df.empty:
        return df
    hoy = _hoy_pd()
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

# ======== ALERTAS DE VENCIMIENTO ========
alertXlsx, alertCsv = pathPair("alertasContratos")
ALERTA_COLS = ["id_contrato","cliente","fechaFin","dias_restantes","umbral","estado","ts_alerta","notificado"]

def _contratos_df_normalizado() -> pd.DataFrame:
    cxlsx, ccsv = pathPair("contratos")
    base = readTable(cxlsx, ccsv, [])
    if base is None:
        base = pd.DataFrame()

    if "id" not in base.columns:
        base["id"] = ""
    if "cliente" not in base.columns:
        base["cliente"] = ""
    if "fechaFin" not in base.columns:
        base["fechaFin"] = ""
    if "diasNotificar" not in base.columns:
        base["diasNotificar"] = 30

    base = base.copy()
    base["fechaFin"] = pd.to_datetime(base["fechaFin"], errors="coerce")
    hoy = pd.to_datetime(date.today())
    base["dias_restantes"] = (base["fechaFin"] - hoy).dt.days
    base["estado"] = "Vigente"
    base.loc[base["dias_restantes"] <= 30, "estado"] = "Por vencer"
    base.loc[base["dias_restantes"] < 0, "estado"] = "Vencido"
    return base

def _dedupe_por_id(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    df["id_contrato"] = df["id_contrato"].astype(str).str.strip()
    df = df.sort_values(["id_contrato","dias_restantes"], ascending=[True, True])
    return df.drop_duplicates(subset=["id_contrato"], keep="first")

def generarAlertasVencimiento_en_caliente() -> pd.DataFrame:
    dfc = _contratos_df_normalizado()
    if dfc is None or dfc.empty:
        out = readTable(alertXlsx, alertCsv, ALERTA_COLS)
        writeTable(out, alertXlsx, alertCsv)
        return out

    # normalización estricta
    dfc = dfc.copy()
    dfc["id_contrato"] = dfc.get("id", "").astype(str).str.strip()
    dfc["fechaFin"]    = pd.to_datetime(dfc["fechaFin"], errors="coerce")
    dfc["umbral"]      = pd.to_numeric(dfc.get("diasNotificar", 30), errors="coerce").fillna(30).astype(int)
    dfc["dias_restantes"] = (dfc["fechaFin"] - _hoy_pd()).dt.days

    # filtro elegibles
    drest  = pd.to_numeric(dfc["dias_restantes"], errors="coerce")
    umbral = pd.to_numeric(dfc["umbral"], errors="coerce").fillna(30)
    mask = dfc["fechaFin"].notna() & (drest >= 0) & (drest <= umbral)
    elegibles = dfc.loc[mask, ["id_contrato","cliente","fechaFin","dias_restantes","umbral"]].copy()

    # estado legible
    elegibles["estado"]    = "Por vencer"
    elegibles["ts_alerta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elegibles["notificado"] = ""

    # conserva marca de notificado si existía
    prev = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if not prev.empty:
        prev = prev.dropna(subset=["id_contrato"]).copy()
        prev["id_contrato"] = prev["id_contrato"].astype(str)
        elegibles["id_contrato"] = elegibles["id_contrato"].astype(str)
        elegibles = elegibles.merge(
            prev[["id_contrato","notificado"]],
            on="id_contrato", how="left", suffixes=("", "_prev")
        )
        elegibles.loc[elegibles["notificado"].astype(str).eq(""), "notificado"] = elegibles["notificado_prev"].fillna("")
        elegibles = elegibles.drop(columns=["notificado_prev"], errors="ignore")

    # si quedara vacío por alguna inconsistencia, rescate desde proximosVencimientos
    if elegibles.empty:
        pv = proximosVencimientos(365)
        if pv is not None and not pv.empty:
            tmp = pv.copy()
            tmp["id_contrato"] = tmp["id"].astype(str)
            tmp["umbral"] = pd.to_numeric(tmp.get("diasNotificar", 30), errors="coerce").fillna(30).astype(int)
            tmp = tmp.loc[(tmp["dias_restantes"] >= 0) & (tmp["dias_restantes"] <= tmp["umbral"]),
                          ["id_contrato","cliente","fechaFin","dias_restantes","umbral"]]
            tmp["estado"] = "Por vencer"
            tmp["ts_alerta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tmp["notificado"] = ""
            elegibles = tmp

    out = _dedupe_por_id(elegibles[ALERTA_COLS].copy())
    writeTable(out, alertXlsx, alertCsv)
    return out

def cargarAlertas() -> pd.DataFrame:
    df = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if df is None or df.empty:
        return pd.DataFrame(columns=ALERTA_COLS)
    df["id_contrato"] = df["id_contrato"].astype(str).str.strip()
    return _dedupe_por_id(df)

def marcarAlertaComoNotificada(idx: int, texto: str = "enviada") -> None:
    df = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    if df is None or df.empty or not (0 <= idx < len(df)):
        return
    df.loc[idx, "notificado"] = f"{texto} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    writeTable(df, alertXlsx, alertCsv)

def enviarAlertasVencimiento_por_correo(usuario: str, destinatario: str | None = None) -> tuple[bool, str]:
    """
    Envía las alertas de vencimiento por correo al usuario actual.
    """
    df = cargarAlertas()
    if df.empty:
        return False, "No hay alertas vigentes para enviar."
    if enviar_email is None:
        return False, "El módulo de envío de correos no está disponible."

    # Resuelve el correo destino
    to = destinatario or _email_de_usuario(usuario)
    if not to:
        return False, "No se encontró un correo asociado al usuario."

    # Arma el cuerpo del mensaje
    filas = []
    for _, r in df.iterrows():
        filas.append(
            f"- Contrato {r.get('id_contrato','')} · Cliente {r.get('cliente','')} "
            f"· Vence {r.get('fechaFin','')} · Restan {r.get('dias_restantes','')} días"
        )

    asunto = "Gestemed · Alertas de contratos por vencer"
    cuerpo = (
        "Hola,\n\nLos siguientes contratos se encuentran próximos a vencer:\n\n"
        + "\n".join(filas)
        + "\n\nEste mensaje fue generado automáticamente por Gestemed."
    )

    # Envía el correo y registra el resultado
    ok, msg = enviar_email(asunto, cuerpo, to)
    ok = bool(ok)

    if ok:
        df2 = df.copy()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        df2["notificado"] = df2["notificado"].astype(str)
        df2.loc[df2["notificado"].str.strip() == "", "notificado"] = f"enviada {ts}"
        writeTable(df2, alertXlsx, alertCsv)
        return True, "Correo enviado correctamente."
    else:
        return False, f"Error al enviar el correo: {msg}"
# ======== FIN DE ALERTAS ========