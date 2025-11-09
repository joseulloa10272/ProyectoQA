import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.usuarioPersistencia import obtenerTipoUsuario
from Persistencia.activosPersistencia import cargarActivosDf

# === UTILIDADES INTERNAS ===
def generar_csv(df_activos):
    """Genera el archivo CSV desde un DataFrame"""
    csv = df_activos.to_csv(index=False)
    return csv

def guardar_reporte(csv_data, fecha_programada):
    carpeta_reportes = "reportes"
    
    if not os.path.exists(carpeta_reportes):
        os.makedirs(carpeta_reportes)

    nombre_archivo = f"reporte_inventario_{fecha_programada.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    
    with open(os.path.join(carpeta_reportes, nombre_archivo), "w") as f:
        f.write(csv_data)
    
    print(f"Reporte guardado en {os.path.join(carpeta_reportes, nombre_archivo)}")


def programar_guardado(csv_data, fecha_programada):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        guardar_reporte,
        'date', 
        run_date=fecha_programada,
        args=[csv_data, fecha_programada]
    )
    scheduler.start()

# === VISTA PRINCIPAL ===
def app(usuario):
    tipoUsuario = obtenerTipoUsuario(usuario)
    st.subheader("Reportes")
    option = st.radio(
        label="",  
        options=("Reporte de inventario", "Reporte de disponibilidad", "Reporte de costos", "Reporte de rentabilidad"),
        label_visibility="hidden" 
    )

    fecha_input = st.date_input("Selecciona la fecha para agendar el reporte", key="fecha_input")
    hora_input = st.time_input("Selecciona la hora para agendar el reporte", value=datetime.now().time(), key="hora_input")
    fecha_programada = datetime.combine(fecha_input, hora_input)
    
    if option ==  "Reporte de rentabilidad":            
        ingresos = st.number_input("Ingresos totales:", min_value=0, value=0, step=1000, key="ingresos_totales")

    # ------------------------------------------------------------------
    # 1️ REPORTE INVENTARIO
    # ------------------------------------------------------------------
    if st.button("Visualizar y agendar Reporte"):
        if option == "Reporte de inventario":
            st.subheader("Reporte de Inventario")

            try:
                df_activos = cargarActivosDf()  
            except Exception as e:
                st.error(f"No fue posible cargar los activos: {e}")
                return

            if df_activos.empty:
                st.info("No hay activos registrados.")
                return
            
            st.dataframe(df_activos, use_container_width=True)
            
            csv_data = generar_csv(df_activos)
            
            programar_guardado(csv_data, fecha_programada)
            st.success(f"Reporte programado para el {fecha_programada}.")
            
            st.download_button(
                label="Descargar Reporte en CSV",
                data=csv_data,
                file_name="reporte_activos.csv",
                mime="text/csv"
            )
            
        # ------------------------------------------------------------------
        # 2 REPORTE DISPONIBILIDAD
        # ------------------------------------------------------------------
        
        elif option == "Reporte de disponibilidad":
            st.subheader("Reporte de Disponibilidad")
       
            try:
                df_activos = cargarActivosDf() 
            except Exception as e:
                st.error(f"No fue posible cargar los activos: {e}")
                return

            df_activos['estado'] = df_activos['cliente'].apply(
                    lambda x: 'Disponible' if pd.isna(x) or x.strip() == '' else 'Asignado'
                )
            
            disponibles = df_activos[df_activos['estado'] == 'Disponible']
            asignados = df_activos[df_activos['estado'] == 'Asignado']

            st.write(f"Total de activos disponibles: {len(disponibles)}")
            st.write(f"Total de activos asignados: {len(asignados)}")
            
            csv_data = generar_csv(df_activos)
            
            programar_guardado(csv_data, fecha_programada)
            st.success(f"Reporte programado para el {fecha_programada}.")

            st.dataframe(df_activos, use_container_width=True)
            
            st.download_button(
                label="Descargar Reporte en CSV",
                data=csv_data,
                file_name="reporte_disponibilidad.csv",
                mime="text/csv"
            )
        

        
        # ------------------------------------------------------------------
        # 3 REPORTE DE COSTOS
        # ------------------------------------------------------------------

        elif option == "Reporte de costos":
            st.subheader("Reporte de Costos")

            try:
                df_activos = cargarActivosDf()  
            except Exception as e:
                st.error(f"No fue posible cargar los activos: {e}")
                return

            if df_activos.empty:
                st.info("No hay activos registrados.")
                return

            st.write("Reporte de costos individuales por activo:")
            
            df_activos['valor'] = pd.to_numeric(df_activos['valor'], errors='coerce')
            df_activos = df_activos.dropna(subset=['valor'])

            df_activos['costo_total'] = df_activos['valor']
            
            costo_total = df_activos['costo_total'].sum()

            st.write(f"Costo total de los activos: {costo_total:,.2f} USD")
            
            csv_data = generar_csv(df_activos)
            
            programar_guardado(csv_data, fecha_programada)
            st.success(f"Reporte programado para el {fecha_programada}.")

            st.dataframe(df_activos[['id', 'modelo', 'valor', 'costo_total']], use_container_width=True, hide_index=True)

            st.download_button(
                label="Descargar Reporte en CSV",
                data=csv_data,
                file_name="reporte_costos.csv",
                mime="text/csv"
            )
        
   
        # ------------------------------------------------------------------
        # 4 REPORTE RENTABILIDAD
        # ------------------------------------------------------------------
        elif option == "Reporte de rentabilidad":
            st.subheader("Reporte de rentabilidad")

            try:
                df_activos = cargarActivosDf()  
            except Exception as e:
                st.error(f"No fue posible cargar los activos: {e}")
                return

            if df_activos.empty:
                st.info("No hay activos registrados.")
                return
            st.write("Reporte de rentabilidad de activos:")

            df_activos['valor'] = pd.to_numeric(df_activos['valor'], errors='coerce')
            df_activos = df_activos.dropna(subset=['valor'])
            
            df_activos['costo_total'] = df_activos['valor']

            costo_total = df_activos['costo_total'].sum()

            st.write(f"Ingresos totales: {ingresos:,.2f} USD")
            st.write(f"Costo total de los activos: {costo_total:,.2f} USD")
            
            rentabilidad = ingresos - costo_total
            st.write(f"Rentabilidad: {rentabilidad:,.2f} USD")

            csv_data = generar_csv(df_activos[['id', 'modelo', 'valor', 'costo_total']])

            fecha_input = st.date_input("Selecciona la fecha para agendar el reporte")
            hora_input = st.time_input("Selecciona la hora para agendar el reporte", value=datetime.now().time())
            fecha_programada = datetime.combine(fecha_input, hora_input)

            if st.button("Programar Guardado del Reporte"):
                programar_guardado(df_activos.to_csv(), fecha_programada)
                st.success(f"Reporte programado para ser guardado el {fecha_programada}.")
            
            st.dataframe(df_activos[['id', 'modelo', 'valor', 'costo_total']], use_container_width=True, hide_index=True)

            st.download_button(
                label="Descargar Reporte de Rentabilidad en CSV",
                data=csv_data,
                file_name="reporte_rentabilidad.csv",
                mime="text/csv"
            )