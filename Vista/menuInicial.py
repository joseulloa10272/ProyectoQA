import streamlit as st
import sys
import os

# Rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Vistas
import menuActivos
import menuContratos
import menuRefacciones
import menuGPS
import menuRFID
import menuMantenimiento
import menuGeocercas

def app(usuario):
    st.title("Funcionalidades")
    opciones = st.container()
    funciones = st.container()

    with opciones:
        option = st.radio(
            label="Seleccione la función que desea realizar:",
            options=("Activos", "Contratos", "Refacciones", "GPS", "RFID", "Geocercas", "Mantenimientos", "Reportes"),
        )
        st.markdown("---")

    with funciones:
        if option == "Activos":
            menuActivos.app(usuario)

        elif option == "Contratos":
            menuContratos.app(usuario)

        elif option == "Refacciones":
            menuRefacciones.app(usuario)

        elif option == "GPS":
            menuGPS.app(usuario)

        elif option == "RFID":
            menuRFID.app(usuario)

        elif option == "Geocercas":
            menuGeocercas.app(usuario)

        elif option == "Mantenimientos":
            menuMantenimiento.app(usuario)

        elif option == "Reportes":
            st.subheader("Reportes")
            
