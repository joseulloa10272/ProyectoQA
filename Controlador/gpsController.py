from Persistencia.gpsPersistencia import (
    cargarPosiciones,
    actualizarPosicion,
    agregarActivoGPS
)
import pandas as pd


def obtenerPosiciones(filtro_cliente=None, filtro_contrato=None, filtro_estado=None):
    """
    Devuelve un DataFrame con las posiciones GPS de los activos.
    Permite filtrar por cliente, contrato o estado.
    """
    df = cargarPosiciones()

    # Limpieza y aseguramiento de tipos
    df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    df = df.dropna(subset=["latitud", "longitud"])

    # Aplicar filtros dinámicos
    if filtro_cliente:
        df = df[df["cliente"].str.contains(str(filtro_cliente), case=False, na=False)]

    if filtro_contrato:
        df = df[df["contrato"].str.contains(str(filtro_contrato), case=False, na=False)]

    if filtro_estado:
        df = df[df["estado"].str.contains(str(filtro_estado), case=False, na=False)]

    return df.reset_index(drop=True)


def registrarActivoGPS(id_activo, cliente, contrato, estado="Disponible"):
    """
    Agrega un activo al seguimiento GPS con coordenadas iniciales simuladas.
    Retorna la información completa del nuevo activo.
    """
    try:
        nuevo = agregarActivoGPS(id_activo, cliente, contrato, estado)
        return {"success": True, "data": nuevo}
    except Exception as e:
        return {"success": False, "error": str(e)}


def moverActivoGPS(id_activo, nueva_lat, nueva_lon):
    """
    Actualiza las coordenadas del activo en seguimiento.
    Retorna la información actualizada.
    """
    try:
        data = actualizarPosicion(id_activo, nueva_lat, nueva_lon)
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def obtenerClientesContratos():
    """
    Devuelve dos listas únicas: clientes y contratos, útiles para filtros en la vista.
    """
    df = cargarPosiciones()
    clientes = sorted(df["cliente"].dropna().unique().tolist())
    contratos = sorted(df["contrato"].dropna().unique().tolist())
    return clientes, contratos


def obtenerResumenGPS():
    """
    Devuelve un resumen estadístico para usar en el dashboard:
    - Total de activos
    - Total por estado
    - Última actualización global
    """
    df = cargarPosiciones()
    if df.empty:
        return {"total": 0, "por_estado": {}, "ultima": None}

    total = len(df)
    por_estado = df["estado"].value_counts().to_dict()
    ultima = df["ultima_actualizacion"].max()
    return {"total": total, "por_estado": por_estado, "ultima": ultima}