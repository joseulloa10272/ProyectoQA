# Persistencia/alertasContratosPersistencia.py
import pandas as pd
from datetime import datetime, date
from .base import pathPair, readTable, writeTable
from .contratosPersistencia import cargarContratos

alertXlsx, alertCsv = pathPair("alertasContratos")
ALERTA_COLS = ["id_contrato","cliente","fechaFin","dias_restantes","estado","ts_alerta","notificado"]

def _hoy():
    return pd.to_datetime(date.today())

def generarAlertasVencimiento() -> None:
    df = pd.DataFrame(cargarContratos())
    if df.empty:
        df_out = readTable(alertXlsx, alertCsv, ALERTA_COLS)
        writeTable(df_out, alertXlsx, alertCsv)
        return
    df["fechaFin"] = pd.to_datetime(df["fechaFin"], errors="coerce")
    df["dias_restantes"] = (df["fechaFin"] - _hoy()).dt.days
    df = df[df["dias_restantes"].between(0, 90)].copy()
    df["estado"] = df["dias_restantes"].apply(lambda d: 30 if d <= 30 else 60 if d <= 60 else 90)
    df["ts_alerta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["notificado"] = ""
    df_alertas = readTable(alertXlsx, alertCsv, ALERTA_COLS)
    df_out = df.rename(columns={"id":"id_contrato"})[ALERTA_COLS]
    df_alertas = pd.concat([df_alertas, df_out], ignore_index=True)
    writeTable(df_alertas, alertXlsx, alertCsv)

def cargarAlertas() -> pd.DataFrame:
    return readTable(alertXlsx, alertCsv, ALERTA_COLS)