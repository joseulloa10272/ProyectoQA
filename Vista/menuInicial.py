import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import menuActivos
import menuContratos
import menuRefacciones

def app(usuario):
    st.title("Funcionalidades")
    opciones = st.container()
    funciones = st.container()

    with opciones:
        option = st.radio(
        label = "Seleccione la función que desea realizar:",
        options  = ("Activos", "Contratos", "Refacciones", "Geocercas", "Mantenimientos", "Reportes")
        )
        st.markdown("---")
        if option  == "Activos":
            with funciones:
                menuActivos.app(usuario)

        elif option  == "Contratos":
            with funciones:
                menuContratos.app(usuario)

        elif option  == "Refacciones":
            with funciones:
                menuRefacciones.app(usuario)

        elif option  == "Geocercas":
            with funciones:
                st.subheader ("Geocercas")

        elif option  == "Mantenimientos":
            with funciones:
                st.subheader ("Mantenimientos")

        elif option  == "Reportes":
            with funciones:
                st.subheader ("Reportes")