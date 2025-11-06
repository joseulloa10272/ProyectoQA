import streamlit as st
import menuInicial 
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.usuarioPersistencia import agregarUsuario
from Validaciones.usuarioValidaciones import existeUsuario


class MultiApp:
    def __init__(self):
        self.apps = []

    def add_app(self, title, func):
        self.apps.append({"title": title, "function": func})

    def run(self):
        st.sidebar.subheader("Iniciar sesión")
        usuario = st.sidebar.text_input("Usuario:")
        contrasena = st.sidebar.text_input("Contraseña:", type='password')

        option = st.sidebar.radio(
            label="",
            options=("No tienes cuenta? Registrarse", "Iniciar sesión")
        )
        st.sidebar.markdown("---")

        if option == "No tienes cuenta? Registrarse":
            st.sidebar.subheader("Registrarse")
            nombreUsuario = st.sidebar.text_input("Ingrese su usuario:")
            correo = st.sidebar.text_input("Ingrese su correo electrónico:")
            tipoUsuario = st.sidebar.selectbox(
                "Tipo de usuario:",
                ["Administrador", "Gerente", "Usuario General", "Técnico de mantenimiento",
                 "Encargado de almacén", "Supervisor de inventario",
                 "Auditor", "Supervisor técnico", "Gerente general", "Desarrollador"]
            )
            contrasena = st.sidebar.text_input("Ingrese su contraseña:", type='password')
            confirmarRegistro = st.sidebar.button("Confirmar")
            if confirmarRegistro:
                if not nombreUsuario.strip() or not correo.strip() or not contrasena.strip():
                    st.sidebar.warning("Debe ingresar todos los datos.")
                usuarioConfirmado = agregarUsuario(nombreUsuario, correo, tipoUsuario, contrasena)
                if (usuarioConfirmado == True):
                    st.sidebar.success("Registro exitoso!")
                else:
                    st.sidebar.error("El usuario ya existe.")
                
                
        if option == "Iniciar sesión":
            usuarioConfirmado = existeUsuario(usuario)
            if (usuarioConfirmado == True):
                menuInicial.app(usuario)
            else:
                st.sidebar.error("El usuario no existe.")

                                 
if __name__ == "__main__":
    app = MultiApp()
    app.run()