
import os, sys, pandas as pd
from datetime import datetime, date
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import pathPair, readTable, writeTable
from Persistencia.contratosPersistencia import cargarContratos, colsContratos

# ---------- Esquema y rutas ----------
alertasXlsx, alertasCsv = pathPair("alertasContratos")
ALERT_COLS = [
    "id_alerta", "id_contrato", "cliente", "activo", "fechaFin",
    "dias_restantes", "umbral", "generada_en", "estado"
]
ESTADOS_VALIDOS = {"nuevo", "enviado", "leida"}

def _coerce_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def _next_id(df):
    if df is None or df.empty or "id_alerta" not in df.columns:
        return 1
    vals = pd.to_numeric(df["id_alerta"], errors="coerce").fillna(0)
    return int(vals.max()) + 1

def cargarAlertas():
    df = readTable(alertasXlsx, alertasCsv, ALERT_COLS)
    for c in ALERT_COLS:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    return df

def guardarAlertas(df):
    for c in ALERT_COLS:
        if c not in df.columns:
            df[c] = ""
    writeTable(df[ALERT_COLS], alertasXlsx, alertasCsv)

def generarAlertasVencimiento(umbrales=(30, 60, 90)):
    """
    Crea alertas 'nuevo' para contratos cuya fechaFin esté a N días (N en umbrales).
    Evita duplicados por (id_contrato, umbral).
    Devuelve (df_alertas, df_nuevas) para que la UI pueda notificar.
    """
    hoy = pd.Timestamp(date.today())
    dfc = pd.DataFrame(cargarContratos(), columns=colsContratos)
    if dfc.empty:
        return cargarAlertas(), pd.DataFrame(columns=ALERT_COLS)

    dfc["fechaFin"] = pd.to_datetime(dfc["fechaFin"], errors="coerce")
    dfc = dfc.dropna(subset=["fechaFin"])
    dfc["dias_restantes"] = (dfc["fechaFin"] - hoy).dt.days

    df_alertas = cargarAlertas()
    existentes = set(
        (str(r["id_contrato"]), _coerce_int(r["umbral"], -1))
        for _, r in df_alertas.iterrows()
    )

    nuevas = []
    base = _next_id(df_alertas)
    k = 0
    for _, r in dfc.iterrows():
        dias = int(r["dias_restantes"])
        for u in umbrales:
            if dias == u:
                key = (str(r["id"]), int(u))
                if key in existentes:
                    continue
                nuevas.append({
                    "id_alerta": str(base + k),
                    "id_contrato": str(r["id"]),
                    "cliente": str(r.get("cliente", "")),
                    "activo": str(r.get("activo", "")),
                    "fechaFin": r["fechaFin"].strftime("%Y-%m-%d"),
                    "dias_restantes": str(dias),
                    "umbral": str(u),
                    "generada_en": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "estado": "nuevo"
                })
                k += 1

    if nuevas:
        df_alertas = pd.concat([df_alertas, pd.DataFrame(nuevas)], ignore_index=True)
        guardarAlertas(df_alertas)

    df_nuevas = pd.DataFrame(nuevas, columns=ALERT_COLS) if nuevas else pd.DataFrame(columns=ALERT_COLS)
    return df_alertas, df_nuevas

def cambiarEstadoAlerta(id_alerta, estado):
    if estado not in ESTADOS_VALIDOS:
        return False, "Estado inválido"
    df = cargarAlertas()
    m = df["id_alerta"].astype(str) == str(id_alerta)
    if not m.any():
        return False, "No existe la alerta"
    df.loc[m, "estado"] = estado
    guardarAlertas(df)
    return True, "OK"

# -------- Envío de correo opcional (con degradación elegante) ---------
def _smtp_params_from_secrets():
    try:
        import streamlit as st
        s = st.secrets
        conf = {
            "host": s.get("smtp", {}).get("host", ""),
            "port": int(s.get("smtp", {}).get("port", 0) or 0),
            "user": s.get("smtp", {}).get("user", ""),
            "password": s.get("smtp", {}).get("password", ""),
            "default_recipient": s.get("alerts", {}).get("default_recipient", "")
        }
        if not conf["host"] or not conf["port"] or not conf["user"] or not conf["password"]:
            return None
        return conf
    except Exception:
        return None

def enviar_email_alerta(destinatario, filas_df):
    """
    Envía un correo con el resumen de alertas. Si no hay SMTP configurado en secrets, retorna False sin fallar.
    """
    params = _smtp_params_from_secrets()
    if params is None or not destinatario:
        return False, "SMTP no configurado o destinatario vacío"

    import smtplib
    from email.mime.text import MIMEText

    lineas = ["Contratos próximos a vencer:\n"]
    for _, r in filas_df.iterrows():
        lineas.append(
            f"- Contrato {r['id_contrato']} | Cliente: {r['cliente']} | "
            f"Activos: {r['activo']} | Vence: {r['fechaFin']} | "
            f"Días restantes: {r['dias_restantes']} (umbral {r['umbral']})"
        )
    cuerpo = "\n".join(lineas)
    asunto = "Alerta de vencimiento de contratos"

    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = params["user"]
    msg["To"] = destinatario

    try:
        # TLS por defecto si no es 465; SSL si es 465
        if params["port"] == 465:
            server = smtplib.SMTP_SSL(params["host"], params["port"], timeout=30)
        else:
            server = smtplib.SMTP(params["host"], params["port"], timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

        with server:
            server.login(params["user"], params["password"])
            server.sendmail(params["user"], [destinatario], msg.as_string())
        return True, "Correo enviado"
    except Exception as e:
        return False, f"Fallo al enviar correo: {e}"