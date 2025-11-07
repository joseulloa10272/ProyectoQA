import os, sys, pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.refaccionesPersistencia import (
    cargarRefacciones, listarRefaccionesPorActivo, agregarRefaccion,
    registrarMovimiento, actualizarUmbral, refaccionesBajoUmbral, obtenerStock
)
from Persistencia.alertasRefaccionesPersistencia import (
    generarAlertasBajoUmbral, cargarAlertas, cambiarEstadoAlerta
)

def crearRefaccion(id_activo, nombre, modeloEquipo, stock_inicial, umbral, ubicacion):
    return agregarRefaccion(id_activo, nombre, modeloEquipo, stock_inicial, umbral, ubicacion)

def moverStock(id_ref, tipo, cantidad, motivo, usuario):
    return registrarMovimiento(id_ref, tipo, cantidad, motivo, usuario)

def setUmbral(id_ref, umbral):
    return actualizarUmbral(id_ref, umbral)

def refaccionesDeActivo(id_activo):
    return listarRefaccionesPorActivo(id_activo)

def generarAlertas():
    return generarAlertasBajoUmbral()

def enviarAlertasPorCorreo(smtp_cfg: dict, destinatario: str):
    # toma las alertas 'nuevo' y envía un resumen
    df = cargarAlertas()
    df = df.loc[df["estado"] == "nuevo"]
    if df.empty: return False
    ok = enviar_email_alerta(
        smtp_cfg["host"], smtp_cfg["port"], smtp_cfg["user"], smtp_cfg["pass"],
        destinatario, df[["id_ref","id_activo","nombre","stock","umbral"]]
    )
    return ok