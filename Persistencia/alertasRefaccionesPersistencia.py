import os, sys, pandas as pd
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import readTable, writeTable, pathPair
from Persistencia.refaccionesPersistencia import refaccionesBajoUmbral

alertXlsx, alertCsv = pathPair("alertasRefacciones")
ALERT_COLS = ["id_alerta","id_ref","id_activo","nombre","stock","umbral","generada_en","estado"]

def cargarAlertas():
    return readTable(alertXlsx, alertCsv, ALERT_COLS)

def guardarAlertas(df):
    for c in ALERT_COLS:
        if c not in df.columns: df[c] = ""
    writeTable(df[ALERT_COLS], alertXlsx, alertCsv)

def generarAlertasBajoUmbral():
    low = refaccionesBajoUmbral()
    df = cargarAlertas()

    def next_id(d):
        if d.empty or "id_alerta" not in d.columns: return 1
        return int(pd.to_numeric(d["id_alerta"], errors="coerce").fillna(0).max()) + 1

    existentes = set((str(r["id_ref"]), str(r["stock"])) for _, r in df.iterrows())
    base = next_id(df); nuevas = []; k = 0
    for _, r in low.iterrows():
        key = (str(r["id"]), str(r["stock"]))
        if key in existentes: continue
        nuevas.append({
            "id_alerta": str(base + k),
            "id_ref": str(r["id"]),
            "id_activo": str(r["id_activo"]),
            "nombre": r["nombre"],
            "stock": str(r["stock"]),
            "umbral": str(r["umbral"]),
            "generada_en": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estado": "nuevo"
        })
        k += 1

    if nuevas:
        df = pd.concat([df, pd.DataFrame(nuevas)], ignore_index=True)
        guardarAlertas(df)
    return df

def cambiarEstadoAlerta(id_alerta, estado):
    df = cargarAlertas()
    m = df["id_alerta"].astype(str) == str(id_alerta)
    if not m.any(): return False
    df.loc[m, "estado"] = estado
    guardarAlertas(df)
    return True