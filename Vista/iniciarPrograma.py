# Vista/iniciarPrograma.py
import streamlit as st
import menuInicial
import sys
import os

# Rutas de import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Persistencia de usuarios (autenticación y registro)
from Persistencia.usuarioPersistencia import (
    agregarUsuario,
    existeUsuario,
)
from Validaciones.usuarioValidaciones import validarCredenciales

class MultiApp:
    def __init__(self):
        self.apps = []

    def add_app(self, title, func):
        self.apps.append({"title": title, "function": func})

    def _logout(self):
        for k in ("auth_ok", "usuario"):
            st.session_state.pop(k, None)
        st.rerun()

    def run(self):
        st.sidebar.subheader("Autenticación")

        # Si ya hay sesión activa, mostrar botón de salir y entrar al menú principal
        if st.session_state.get("auth_ok"):
            usuario = st.session_state.get("usuario", "")
            st.sidebar.write(f"Sesión iniciada como **{usuario}**")
            if st.sidebar.button("Cerrar sesión"):
                self._logout()
                return
            # Contenido principal con el usuario autenticado
            menuInicial.app(usuario)
            return

        # Selector de acción
        option = st.sidebar.radio(label="", options=("Iniciar sesión", "Registrarse"))
        st.sidebar.markdown("---")

        if option == "Iniciar sesión":
            usuario_in = st.sidebar.text_input("Usuario:")
            contrasena_in = st.sidebar.text_input("Contraseña:", type="password")
            if st.sidebar.button("Entrar"):
                if not usuario_in.strip() or not contrasena_in.strip():
                    st.sidebar.warning("Ingrese usuario y contraseña.")
                else:
                    if validarCredenciales(usuario_in, contrasena_in):
                        st.session_state["auth_ok"] = True
                        st.session_state["usuario"] = usuario_in.strip()
                        st.sidebar.success("Ingreso correcto.")
                        st.rerun()
                    else:
                        # Diferenciar si el usuario existe o no
                        if existeUsuario(usuario_in):
                            st.sidebar.error("Contraseña incorrecta.")
                        else:
                            st.sidebar.error("El usuario no existe.")

        else:  # Registrarse
            nombreUsuario = st.sidebar.text_input("Ingrese su usuario:")
            correo = st.sidebar.text_input("Ingrese su correo electrónico:")
            tipoUsuario = st.sidebar.selectbox(
                "Tipo de usuario:",
                [
                    "Administrador", "Gerente", "Usuario General", "Técnico de mantenimiento",
                    "Encargado de almacén", "Supervisor de inventario",
                    "Auditor", "Supervisor técnico", "Gerente general", "Desarrollador",
                ],
            )
            contrasena_reg = st.sidebar.text_input("Ingrese su contraseña:", type="password")
            confirmarRegistro = st.sidebar.button("Confirmar")

            if confirmarRegistro:
                if not nombreUsuario.strip() or not correo.strip() or not contrasena_reg.strip():
                    st.sidebar.warning("Debe ingresar todos los datos.")
                elif existeUsuario(nombreUsuario):
                    st.sidebar.error("El usuario ya existe.")
                else:
                    creado = agregarUsuario(nombreUsuario.strip(), correo.strip(), tipoUsuario, contrasena_reg)
                    if creado is True:
                        st.sidebar.success("Registro exitoso. Inicie sesión con sus credenciales.")
                    else:
                        st.sidebar.error("No se completó el registro.")

if __name__ == "__main__":
    app = MultiApp()
    app.run()