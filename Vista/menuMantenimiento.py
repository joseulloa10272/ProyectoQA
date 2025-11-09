import streamlit as st
import sys
import os
from streamlit_drawable_canvas import st_canvas

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Persistencia.usuarioPersistencia import obtenerTipoUsuario
from Persistencia.mantenimientoPersistencia import create_mantenimiento, update_mantenimiento_estado
from Persistencia.movimientosPersistencia import add_movimiento

def app(usuario):
    st.title("Gestión de Mantenimiento")

    tipoUsuario = obtenerTipoUsuario(usuario)

    # Corregido el control de acceso
    if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
        st.warning("No tiene permiso para registrar órdenes de mantenimiento.")
        return

    # Crear orden de mantenimiento
    st.header("Crear Orden de Mantenimiento")
    id_orden = st.text_input("ID de Orden")
    fecha = st.date_input("Fecha de Mantenimiento")
    responsable = st.text_input("Responsable")
    ubicacion = st.text_input("Ubicación")
    tareas = st.text_area("Tareas")
    estado = st.selectbox("Estado", ["Pendiente", "En Curso", "Finalizado"])

    if st.button("Crear Orden de Mantenimiento"):
        create_mantenimiento(id_orden, fecha, responsable, tareas, estado)
        st.success("Orden de Mantenimiento Creada")

    # Actualizar estado de la orden
    st.header("Actualizar Estado de Mantenimiento")
    id_orden_update = st.text_input("ID de Orden a Actualizar")
    nuevo_estado = st.selectbox("Nuevo Estado", ["Pendiente", "En Curso", "Finalizado"])

    if st.button("Actualizar Estado"):
        update_mantenimiento_estado(id_orden_update, nuevo_estado)
        st.success("Estado de Mantenimiento Actualizado")

    # Registrar evidencia de mantenimiento
    st.header("Registrar Evidencia de Mantenimiento")
    fotos = st.file_uploader("Cargar Fotos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    piezas = st.text_area("Piezas Consumidas")

    # Firma digital con el lienzo
    st.header("Firma Digital")
    st.write("Firma aquí usando el ratón o la pantalla táctil.")
    
    # Canvas para la firma
    canvas_result = st_canvas(
        fill_color="white",  # Color de fondo
        stroke_width=3,  # Grosor de la línea
        stroke_color="black",  # Color de la línea
        background_color="white",  # Color de fondo
        width=700,  # Ancho del lienzo
        height=200,  # Alto del lienzo
        drawing_mode="freedraw",  # Modo de dibujo libre
        key="signature_canvas"
    )

    # Verificar si se ha dibujado algo en el canvas
    if canvas_result.image_data is not None:
        # Mostrar la firma digital
        st.image(canvas_result.image_data, caption="Tu Firma Digital", use_column_width=True)

        # Usamos la imagen tal como está sin la conversión
        signature_image = canvas_result.image_data

        st.success("Firma registrada con éxito.")
    else:
        st.warning("Por favor, firma antes de continuar.")

    if st.button("Registrar Evidencia"):
        # Aquí asumimos que el id de orden es el de la creación o la actualización
        add_movimiento(id_orden, fecha, ubicacion, "Mantenimiento", "Finalizado", fotos, piezas, signature_image)
        st.success("Evidencia Registrada")
