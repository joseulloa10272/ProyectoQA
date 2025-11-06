import streamlit as st
import sys
import os
import pandas as pd  
import streamlit as st
from streamlit_drawable_canvas import st_canvas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.usuarioPersistencia import obtenerTipoUsuario
from Persistencia.contratosPersistencia import agregarContratos, cargarContratos, colsContratos, cargarContratosIdCliente, obtenerActivosAsociadosPorSeleccion
from Persistencia.activosPersistencia import cargarActivosIdNombre
from Persistencia.actasPersistencia import agregarActas, cargarActas, colsActas

def app(usuario):    
    st.subheader("Contratos")
    option = st.radio(
        label = "Seleccione una función:",
        options  = ("Registrar Contrato", "Mostrar Contratos", "Registrar Acta", "Mostrar Actas")
        )
    
    if option  == "Registrar Contrato":

        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Gerente"]:
            st.warning("No tiene permiso para registrar contratos.")
            return
        st.subheader("Registrar Contrato")
        
        cliente = st.text_input("Ingrese el nombre del cliente:")
        fechaInicio= st.text_input("Ingrese la fecha de inicio:")
        fechaFin = st.text_input("Ingrese el fecha de finalización:")    
        condiciones = st.text_area("Ingrese las condiciones:")
        activosAsociados = st.multiselect(
            "Activos a asociar",
            options= cargarActivosIdNombre(),
            max_selections=5)
        diasNotificar = st.number_input("Ingrese los días de anticipación para notificar:", min_value=1, step=1)
        registrarContrato = st.button("Registrar Contrato")
        
        if registrarContrato:
            if not cliente.strip() or not fechaInicio.strip() or not fechaFin.strip() or not condiciones.strip() or diasNotificar is None:
                    st.warning("Debe ingresar todos los datos.")
                    return
            agregarContratos(cliente, fechaInicio, fechaFin, condiciones, activosAsociados, diasNotificar)
            st.success("Contrato registrado con éxito",)

    if option  == "Mostrar Contratos":
        mostrarContratosPorVencer()
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Gerente"]:
            st.warning("No tiene permiso para ver contratos.")
            return
        st.subheader("Mostrar Contratos")
        try:
            activosList = cargarContratos()
            df = pd.DataFrame(activosList, columns=colsContratos)
        except Exception as e:
            st.error(f"No fue posible cargar los contratos: {e}")
            st.stop()
        st.dataframe(df, use_container_width=True, hide_index=True)

    if option  == "Registrar Acta":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para registrar actas.")
            return
        st.subheader("Registrar Acta")

        contratoAsociado = st.selectbox(
            "Contrato a asociar",
            options= cargarContratosIdCliente())
        razon = st.text_area("Ingrese la razón del acta:")
        activosAsociados = st.multiselect(
            "Activos a asociar",
            options= obtenerActivosAsociadosPorSeleccion(contratoAsociado),
            max_selections=5)
        
        st.title("Firma digital")

        st.write("Por favor firme en el recuadro:")
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)", 
            stroke_width=2,                      
            stroke_color="black",                
            background_color="#ffffff",         
            height=150,                           
            width=400,                            
            drawing_mode="freedraw",              
            key="canvas",
        )

        registrarActa = st.button("Registrar Acta")        
        if registrarActa:
            if not razon.strip():
                    st.warning("Debe ingresar todos los datos.")
                    return
            agregarActas(contratoAsociado, razon, activosAsociados)
            st.success("Acta registrada con éxito",)

    if option  == "Mostrar Actas":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para ver actas.")
            return
        st.subheader("Mostrar Actas")
        try:
            actasList = cargarActas()
            df = pd.DataFrame(actasList, columns=colsActas)
        except Exception as e:
            st.error(f"No fue posible cargar las actas: {e}")
            st.stop()
        st.dataframe(df, use_container_width=True, hide_index=True)
        

@st.dialog("Contratos por vencer")
def mostrarContratosPorVencer():
    try:
        df = pd.DataFrame(cargarContratos(), columns=colsContratos)
    except Exception as e:
        st.error(f"No fue posible cargar los contratos: {e}")
        return

    if df.empty:
        st.info("No hay contratos registrados.")
        return

    mask = df["estado"].astype(str).str.strip().str.lower().eq("por vencer")
    df_vencer = df.loc[mask, ["id", "cliente"]]

    if df_vencer.empty:
        st.info("No hay contratos por vencer en este momento.")
        return

    st.dataframe(df_vencer, use_container_width=True, hide_index=True)