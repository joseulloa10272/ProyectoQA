import streamlit as st
import sys
import os
import pandas as pd   
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.activosPersistencia import agregarActivos, registrarActivosRfid, importarActivosMasivoDesdeArchivo, cargarActivos, colsActivos
from Persistencia.usuarioPersistencia import obtenerTipoUsuario

def app(usuario):    

    tipoUsuario = obtenerTipoUsuario(usuario)
    st.subheader("Activos")
    option = st.radio(
        label = "Seleccione una función:",
        options  = ("Registrar", "Importar con CSV/Excel", "Importación masiva", "Mostrar", "Seguimiento GPS")
        )
    
    if option  == "Registrar":

        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para registrar activos.")
            return
        st.subheader("Registrar")
        
        modelo = st.text_input("Ingrese el modelo:")
        serie = st.text_input("Ingrese la serie:")
        fabricante = st.text_input("Ingrese el fabricante:")    
        fechaCompra = st.text_input("Ingrese la fecha de compra:")
        pais = st.text_input("Ingrese el pais:")
        provincia = st.text_input("Ingrese la provincia:")
        canton = st.text_input("Ingrese el canton:")
        cliente = st.text_input("Ingrese el cliente:")
        valor = st.number_input("Ingrese el valor:")
        tag = st.text_input("Ingrese el tag:")
        fotos = st.text_input("Ingrese las fotos:")
        fechaRegistro = st.text_input("Ingrese la fecha de registro:")
         

        registrarActivo = st.button("Registrar Activo")
        if registrarActivo:
            if not modelo.strip() or not serie.strip() or not fabricante.strip() or not fechaCompra.strip() or not pais.strip() or not provincia.strip() or not canton.strip() or not cliente.strip()  or not fechaRegistro.strip():
                    st.warning("Debe ingresar todos los datos.")
                    return
            agregarActivos(modelo, serie, fabricante, fechaCompra, pais, provincia, canton, cliente, valor, tag, fotos, fechaRegistro, usuario)
            st.success("Activo registrado con exito")

        
        
    elif option  == "Importar con CSV/Excel":
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para importar activos.")
            return
        st.subheader("Importar con CSV/Excel")
        with st.form("form_rfid", clear_on_submit=False):
            rfidCode = st.text_input("Código RFID", help="Escanéalo o escríbelo tal cual viene en el tag.")
            submitted = st.form_submit_button("Buscar y Registrar")

        if submitted:
            ok, info = registrarActivosRfid(rfidCode, usuario)
            if ok == True:
                st.success(f"Activo registrado correctamente. ID nuevo: {info}")
            else:
                st.error(str(info))

        
    elif option  == "Importación masiva":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para importar activos masivamente.")
            return
        st.subheader("Importación masiva desde archivo (xlsx/csv)")

        archivo = st.file_uploader(
            "Seleccione el archivo del catálogo RFID",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=False
        )

        if archivo is not None:
            st.info(f"Archivo seleccionado: {archivo.name}")
            try:
                if archivo.name.lower().endswith((".xlsx", ".xls")):
                    import io
                    df_prev = pd.read_excel(io.BytesIO(archivo.read()))
                else:
                    import io
                    df_prev = pd.read_csv(io.BytesIO(archivo.read()))
                st.dataframe(df_prev.head(20))
                archivo.seek(0)
            except Exception:
                st.warning("No se pudo previsualizar el archivo. Igual puedes intentar importar.")

        if st.button("Validar y cargar"):
            if archivo is None:
                st.warning("Primero seleccione un archivo.")
            else:
                ok, rep = importarActivosMasivoDesdeArchivo(archivo, archivo.name, usuario)
                if ok:
                    st.success("Importación finalizada.")
                    st.write(f"Insertados: {rep.get('insertados', 0)}")
                    st.write(f"Omitidos: {rep.get('omitidos', 0)}")
                    if rep.get("razones_omision"):
                        st.subheader("Omitidos")
                        for r in rep["razones_omision"]:
                            st.write(f"Fila {r['fila']}: RFID={r.get('rfid','')} → {r['motivo']}")
                else:
                    st.error(rep.get("error", "Error desconocido."))
        
    elif option  == "Mostrar":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para ver los activos registrados.")
            return
        st.subheader("Activos registrados")

        try:
            activosList = cargarActivos()
            df = pd.DataFrame(activosList, columns=colsActivos)
        except Exception as e:
            st.error(f"No fue posible cargar los activos: {e}")
            st.stop()
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif option  == "Seguimiento GPS":
        st.subheader("Seguimiento GPS")

