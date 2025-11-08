import os, sys, pandas as pd, random
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.base import pathPair, readTable, writeTable

# Archivos de respaldo (Excel y CSV)
gpsXlsx, gpsCsv = pathPair("gpsActivos")

GPS_COLS = [
    "id_activo",
    "cliente",
    "contrato",
    "estado",
    "latitud",
    "longitud",
    "ultima_actualizacion"
]

# -------------------------------
# Funciones principales
# -------------------------------

def cargarPosiciones():
    """
    Carga las posiciones GPS desde almacenamiento persistente.
    Si el archivo está vacío o da error, genera datos simulados.
    """
    try:
        df = readTable(gpsXlsx, gpsCsv, GPS_COLS)
        if df.empty:
            df = simularPosiciones()
        else:
            # Aseguramos que las columnas de coordenadas sean numéricas
            df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
            df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")

            # Reemplazamos NaN por coordenadas simuladas si faltan
            mask_invalid = df["latitud"].isna() | df["longitud"].isna()
            if mask_invalid.any():
                df.loc[mask_invalid, ["latitud", "longitud"]] = generarCoordenadas(len(df[mask_invalid]))

        writeTable(df, gpsXlsx, gpsCsv)
        return df
    except Exception:
        # Si hay un error en lectura, generamos datos nuevos
        return simularPosiciones()

def generarCoordenadas(n=1):
    """
    Genera coordenadas aleatorias cercanas a San José (Costa Rica)
    para n activos.
    """
    base_lat, base_lon = 9.933, -84.083
    coords = []
    for _ in range(n):
        coords.append([
            round(base_lat + random.uniform(-0.05, 0.05), 6),
            round(base_lon + random.uniform(-0.05, 0.05), 6)
        ])
    return coords if n > 1 else coords[0]

def simularPosiciones():
    """
    Crea una tabla de posiciones simuladas para 5 activos,
    útil para pruebas iniciales o cuando no existen registros.
    """
    base_lat, base_lon = 9.933, -84.083
    data = []
    for i in range(1, 6):
        data.append({
            "id_activo": f"A-{i}",
            "cliente": random.choice(["Hospital México", "Clínica Católica", "TEC", "CIMA", "Hospital del Trauma"]),
            "contrato": random.choice(["C-1001", "C-2002", "C-3003", "C-4004"]),
            "estado": random.choice(["En uso", "Disponible", "En mantenimiento"]),
            "latitud": round(base_lat + random.uniform(-0.05, 0.05), 6),
            "longitud": round(base_lon + random.uniform(-0.05, 0.05), 6),
            "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    df = pd.DataFrame(data)
    writeTable(df, gpsXlsx, gpsCsv)
    return df

def actualizarPosicion(id_activo, lat, lon):
    """
    Actualiza la posición de un activo existente.
    Si no existe, lanza un error controlado.
    """
    df = cargarPosiciones()
    m = df["id_activo"].astype(str) == str(id_activo)
    if not m.any():
        raise ValueError(f"Activo {id_activo} no encontrado para actualización GPS.")

    # Validar que las coordenadas sean numéricas
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        raise ValueError("Las coordenadas deben ser numéricas (float).")

    df.loc[m, ["latitud", "longitud", "ultima_actualizacion"]] = [
        lat, lon, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]

    writeTable(df, gpsXlsx, gpsCsv)
    return df.loc[m].iloc[0].to_dict()

def agregarActivoGPS(id_activo, cliente, contrato, estado="Disponible"):
    """
    Agrega un nuevo activo al seguimiento GPS con coordenadas simuladas.
    """
    df = cargarPosiciones()
    if str(id_activo) in df["id_activo"].astype(str).values:
        raise ValueError(f"El activo {id_activo} ya existe en el seguimiento GPS.")

    lat, lon = generarCoordenadas()
    nuevo = {
        "id_activo": str(id_activo),
        "cliente": cliente,
        "contrato": contrato,
        "estado": estado,
        "latitud": lat,
        "longitud": lon,
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    writeTable(df, gpsXlsx, gpsCsv)
    return nuevo

# Alias para compatibilidad con vistas antiguas
def obtenerPosiciones():
    return cargarPosiciones()