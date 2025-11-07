import os, sys, pandas as pd
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import readTable, writeTable, pathPair

# Tablas
refXlsx, refCsv = pathPair("refacciones")
movXlsx, movCsv = pathPair("movimientosRefacciones")

# 🔗 Agregamos id_activo para vincular la refacción a un equipo concreto
COLS_REF = ["id","id_activo","nombre","modeloEquipo","stock","umbral","ubicacion","actualizado_en"]
COLS_MOV = ["id_mov","id_ref","tipo","cantidad","motivo","usuario","fecha_hora"]

def cargarRefacciones():
    return readTable(refXlsx, refCsv, COLS_REF)

def guardarRefacciones(df):
    for c in COLS_REF:
        if c not in df.columns:
            df[c] = ""
    writeTable(df[COLS_REF], refXlsx, refCsv)

def _next_id(df, col):
    if df.empty or col not in df.columns:
        return 1
    return int(pd.to_numeric(df[col], errors="coerce").fillna(0).max()) + 1

def agregarRefaccion(id_activo, nombre, modeloEquipo="", stock_inicial=0, umbral=0, ubicacion=""):
    df = cargarRefacciones()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new = {
        "id": str(_next_id(df, "id")),
        "id_activo": str(id_activo),                  # ← vinculación directa
        "nombre": str(nombre).strip(),
        "modeloEquipo": str(modeloEquipo).strip(),
        "stock": str(int(stock_inicial) if stock_inicial not in (None, "") else 0),
        "umbral": str(int(umbral) if umbral not in (None, "") else 0),
        "ubicacion": str(ubicacion).strip(),
        "actualizado_en": now,
    }
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    guardarRefacciones(df)
    return new

def actualizarUmbral(id_ref, nuevo_umbral):
    df = cargarRefacciones()
    mask = df["id"].astype(str) == str(id_ref)
    if not mask.any():
        return False
    df.loc[mask, "umbral"] = str(int(nuevo_umbral))
    df.loc[mask, "actualizado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guardarRefacciones(df)
    return True

def cargarMovimientos():
    return readTable(movXlsx, movCsv, COLS_MOV)

def guardarMovimientos(df):
    for c in COLS_MOV:
        if c not in df.columns: df[c] = ""
    writeTable(df[COLS_MOV], movXlsx, movCsv)

def registrarMovimiento(id_ref, tipo, cantidad, motivo="", usuario=""):
    assert tipo in ("entrada","salida"), "tipo debe ser 'entrada' o 'salida'"
    qty = int(cantidad)
    if qty <= 0:
        raise ValueError("cantidad debe ser > 0")

    ref = cargarRefacciones()
    row = ref.loc[ref["id"].astype(str) == str(id_ref)]
    if row.empty:
        raise ValueError("id_ref no existe")

    curr = int(pd.to_numeric([row.iloc[0]["stock"]], errors="coerce")[0])
    if tipo == "salida" and qty > curr:
        raise ValueError(f"La salida ({qty}) supera el stock disponible ({curr})")
    new_stock = curr + qty if tipo == "entrada" else curr - qty

    ref.loc[ref["id"].astype(str) == str(id_ref), "stock"] = str(new_stock)
    ref.loc[ref["id"].astype(str) == str(id_ref), "actualizado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guardarRefacciones(ref)

    mov = cargarMovimientos()
    new_mov = {
        "id_mov": str(_next_id(mov, "id_mov")),
        "id_ref": str(id_ref),
        "tipo": tipo,
        "cantidad": str(qty),
        "motivo": str(motivo).strip(),
        "usuario": str(usuario).strip(),
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    mov = pd.concat([mov, pd.DataFrame([new_mov])], ignore_index=True)
    guardarMovimientos(mov)
    return new_mov

def refaccionesBajoUmbral():
    df = cargarRefacciones()
    if df.empty: return df.copy()
    df["_stock"]  = pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)
    df["_umbral"] = pd.to_numeric(df["umbral"], errors="coerce").fillna(0).astype(int)
    low = df.loc[df["_stock"] <= df["_umbral"]].copy()
    return low[COLS_REF]

def listarRefaccionesPorActivo(id_activo):
    df = cargarRefacciones()
    return df.loc[df["id_activo"].astype(str) == str(id_activo)].copy()

def obtenerStock(id_ref) -> int:
    df = cargarRefacciones()
    row = df.loc[df["id"].astype(str) == str(id_ref)]
    if row.empty: return 0
    try:
        return int(pd.to_numeric([row.iloc[0]["stock"]], errors="coerce")[0])
    except Exception:
        return 0