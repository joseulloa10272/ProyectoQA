# Vista/menuActivos.py
import streamlit as st
import sys
import os
import io
import pandas as pd
import menuGPS
import folium
from streamlit_folium import st_folium
from datetime import date
from Persistencia.gpsPersistencia import actualizarPosicion
from datetime import datetime, timedelta
from Persistencia.movimientosPersistencia import filter_movimientos

# Rutas de import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Persistencia.activosPersistencia import (
    agregarActivos,
    registrarActivosRfid,
    importarActivosMasivoDesdeArchivo,
    cargarActivos,
    colsActivos,
)
from Persistencia.activosPersistencia import existeIdUnico, existeTagEnActivos
from Persistencia.usuarioPersistencia import obtenerTipoUsuario


def _init_state():
    """Inicializa claves de session_state necesarias para esta vista."""
    if "lat_sel" not in st.session_state:
        st.session_state["lat_sel"] = None
    if "lon_sel" not in st.session_state:
        st.session_state["lon_sel"] = None
    if "usuario" not in st.session_state:
        st.session_state["usuario"] = ""


def app(usuario):
    _init_state()

    tipoUsuario = obtenerTipoUsuario(usuario)
    st.subheader("Activos")

    option = st.radio(
        label="Seleccione una función:",
        options=("Registrar", "Registrar por RFID", "Importación masiva", "Mostrar", "Seguimiento GPS", "Historial de Movimientos"),
    )

    # ======================================
    # OPCIÓN 1: REGISTRAR
    # ======================================
    if option == "Registrar":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para registrar activos")
            return

        st.subheader("Registrar Activo")

        # Campos requeridos y opcionales
        col1, col2 = st.columns(2)
        with col1:
            id_unico = st.text_input("ID único del activo *")
            modelo = st.text_input("Modelo *")
            serie = st.text_input("Número de serie *")
            fabricante = st.text_input("Fabricante *")
            fechaCompra = st.date_input("Fecha de compra *")
        with col2:
            cliente = st.text_input("Cliente o área asignada (opcional)")
            valor = st.number_input("Valor del activo (₡) *", min_value=0.0, step=0.01, format="%.2f")
            tag = st.text_input("Código RFID/QR (opcional)")
            fotos = st.text_input("URL o ruta de fotos (opcional)")

        st.markdown("### Ubicación inicial — selección obligatoria en el mapa")

        # Mapa centrado en último punto o centro por defecto
        center_lat = st.session_state.get("lat_sel") or 9.750000
        center_lon = st.session_state.get("lon_sel") or -83.750000
        mapa = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles="CartoDB positron")
        if st.session_state.get("lat_sel") is not None and st.session_state.get("lon_sel") is not None:
            folium.Marker(
                [st.session_state["lat_sel"], st.session_state["lon_sel"]],
                tooltip="Ubicación seleccionada",
            ).add_to(mapa)
        click = st_folium(mapa, width=700, height=420)

        # Captura del clic
        if click and click.get("last_clicked"):
            st.session_state["lat_sel"] = float(click["last_clicked"]["lat"])
            st.session_state["lon_sel"] = float(click["last_clicked"]["lng"])

        if st.session_state.get("lat_sel") is not None and st.session_state.get("lon_sel") is not None:
            st.info(f"Ubicación actual: lat {st.session_state['lat_sel']:.6f}, lon {st.session_state['lon_sel']:.6f}")
        else:
            st.warning("Seleccione la ubicación en el mapa para continuar")

        guardar = st.button("Guardar activo")

        if guardar:
            # Validación de requeridos — tag y fotos permanecen opcionales
            faltantes = []
            if not id_unico.strip():
                faltantes.append("ID único")
            if not modelo.strip():
                faltantes.append("Modelo")
            if not serie.strip():
                faltantes.append("Número de serie")
            if not fabricante.strip():
                faltantes.append("Fabricante")
            if valor is None or float(valor) <= 0:
                faltantes.append("Valor")
            if st.session_state.get("lat_sel") is None or st.session_state.get("lon_sel") is None:
                faltantes.append("Ubicación inicial en el mapa")

            if faltantes:
                st.error("Complete los campos obligatorios: " + ", ".join(faltantes))
                st.stop()

            # Unicidad después de capturar entradas
            if existeIdUnico(id_unico.strip()):
                st.error("El ID único ya existe en el inventario")
                st.stop()

            tag_norm = tag.strip()
            if tag_norm and existeTagEnActivos(tag_norm):
                st.error("El tag RFID/QR ya está asociado a otro activo")
                st.stop()

            # Inserción: la persistencia puede devolver bool o dict, se maneja en ambos casos
            res = agregarActivos(
                id_unico=id_unico.strip(),
                modelo=modelo.strip(),
                serie=serie.strip(),
                fabricante=fabricante.strip(),
                fechaCompra=str(fechaCompra),
                latitud=float(st.session_state.get("lat_sel")),
                longitud=float(st.session_state.get("lon_sel")),
                cliente=cliente.strip(),
                valor=float(valor),
                tag=tag_norm,
                fotos=fotos.strip(),
                fechaRegistro=str(date.today()),
                usuario=st.session_state.get("usuario", usuario),
            )

            if isinstance(res, dict):
                ok = True
                activo_id = res.get("id_unico", id_unico.strip())
            elif isinstance(res, bool):
                ok = res
                activo_id = id_unico.strip()
            else:
                ok = False
                activo_id = id_unico.strip()

            if ok:
                # Sembrar posición para GPS
                try:
                    actualizarPosicion(
                        id_activo=activo_id,
                        latitud=float(st.session_state.get("lat_sel")),
                        longitud=float(st.session_state.get("lon_sel")),
                        cliente=cliente.strip(),
                        estado="Vigente",
                    )
                except Exception:
                    pass

                st.success(f"Activo {activo_id} registrado y ubicado en el mapa")
                st.info(
                    f"Coordenadas registradas: lat {st.session_state.get('lat_sel'):.6f}, "
                    f"lon {st.session_state.get('lon_sel'):.6f}"
                )
                # Limpieza mínima
                st.session_state["lat_sel"] = None
                st.session_state["lon_sel"] = None
            else:
                st.error("No se registró el activo, revise el log de Persistencia")

    # ======================================
    # OPCIÓN 2: REGISTRAR POR RFID
    # ======================================
    elif option == "Registrar por RFID":
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para registrar por RFID")
            return

        st.subheader("Registrar por RFID")
        with st.form("form_rfid", clear_on_submit=False):
            rfidCode = st.text_input("Código RFID", help="Escanéelo o escríbalo tal cual aparece en el tag")
            submitted = st.form_submit_button("Buscar y Registrar")

        if submitted:
            ok, info = registrarActivosRfid(rfidCode, usuario)
            if ok:
                st.success(f"Activo registrado correctamente, ID nuevo: {info}")
            else:
                st.error(str(info))

    # ======================================
    # OPCIÓN 3: IMPORTACIÓN MASIVA
    # ======================================
    elif option == "Importación masiva":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para importar activos masivamente")
            return

        st.subheader("Importación masiva desde archivo (xlsx/csv)")

        archivo = st.file_uploader(
            "Seleccione el archivo de activos",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=False,
        )

        if archivo is not None:
            st.info(f"Archivo seleccionado: {archivo.name}")
            try:
                if archivo.name.lower().endswith((".xlsx", ".xls")):
                    df_prev = pd.read_excel(io.BytesIO(archivo.read()))
                else:
                    df_prev = pd.read_csv(io.BytesIO(archivo.read()))
                st.dataframe(df_prev.head(20))
                archivo.seek(0)
            except Exception:
                st.warning("La previsualización falló, la importación sigue disponible")

        if st.button("Validar y cargar"):
            if archivo is None:
                st.warning("Primero seleccione un archivo")
            else:
                ok, rep = importarActivosMasivoDesdeArchivo(archivo, archivo.name, usuario)
                if ok:
                    st.success("Importación finalizada")
                    st.write(f"Insertados: {rep.get('insertados', 0)}")
                    st.write(f"Omitidos: {rep.get('omitidos', 0)}")
                    if rep.get("razones_omision"):
                        st.subheader("Omitidos")
                        for r in rep["razones_omision"]:
                            st.write(f"Fila {r['fila']}: RFID={r.get('rfid','')} → {r['motivo']}")
                else:
                    st.error(rep.get("error", "Error desconocido"))

    # ======================================
    # OPCIÓN 4: MOSTRAR ACTIVOS
    # ======================================
    elif option == "Mostrar":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para ver los activos registrados")
            return

        st.subheader("Activos registrados")

        try:
            activosList = cargarActivos()
            df = pd.DataFrame(activosList, columns=colsActivos)
            if df.empty:
                st.warning("No hay activos registrados para mostrar")
                st.stop()

            # Convertir fechas y ordenar
            df["fechaRegistro"] = pd.to_datetime(df["fechaRegistro"], errors="coerce")
            df = df.sort_values(by="fechaRegistro", ascending=False)

            # Estado GPS
            df["Estado GPS"] = df.apply(
                lambda r: "Con coordenadas" if pd.notna(r["latitud"]) and pd.notna(r["longitud"]) else "Sin coordenadas",
                axis=1,
            )

            # Filtros
            st.markdown("### 🔍 Filtros de búsqueda")
            col_f1, col_f2, col_f3 = st.columns([1, 2, 2])

            with col_f1:
                clientes = sorted(df["cliente"].dropna().unique())
                cliente_sel = st.selectbox("Cliente:", ["Todos"] + clientes)

            with col_f2:
                fecha_min = df["fechaRegistro"].min()
                fecha_max = df["fechaRegistro"].max()
                rango_fechas = st.date_input(
                    "Rango de fechas:",
                    value=(fecha_min.date(), fecha_max.date()) if pd.notna(fecha_min) else (),
                )

            with col_f3:
                estado_sel = st.selectbox("Estado GPS:", ["Todos", "Con coordenadas", "Sin coordenadas"])

            # Aplicar filtros
            if cliente_sel != "Todos":
                df = df[df["cliente"] == cliente_sel]
            if estado_sel != "Todos":
                df = df[df["Estado GPS"] == estado_sel]
            if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                desde, hasta = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
                df = df[(df["fechaRegistro"] >= desde) & (df["fechaRegistro"] <= hasta)]

            if df.empty:
                st.info("No se encontraron activos con los filtros seleccionados")
                st.stop()

            # Columnas a mostrar
            columnas_mostrar = [
                "id_unico",
                "modelo",
                "serie",
                "fabricante",
                "cliente",
                "latitud",
                "longitud",
                "valor",
                "tag",
                "fechaRegistro",
                "usuario",
                "Estado GPS",
            ]
            df = df[columnas_mostrar]

            # Exportación
            st.markdown("###  Exportar resultados filtrados")
            col_exp1, col_exp2 = st.columns(2)

            fecha_export = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            nombre_base = f"Activos_{fecha_export}"

            # Excel (buffer en memoria)
            with col_exp1:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    label="📘 Descargar en Excel (.xlsx)",
                    data=excel_buffer.getvalue(),
                    file_name=f"{nombre_base}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            # CSV
            with col_exp2:
                csv_data = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📄 Descargar en CSV (.csv)",
                    data=csv_data,
                    file_name=f"{nombre_base}.csv",
                    mime="text/csv",
                )

            st.markdown("---")

            # Colorear filas
            def resaltar_gps(row):
                color = "#ffffff" if row["Estado GPS"] == "Con coordenadas" else "#fff3cd"
                return [f"background-color: {color}"] * len(row)

            st.dataframe(
                df.style.apply(resaltar_gps, axis=1),
                use_container_width=True,
                hide_index=True,
            )

            st.caption("Filtre por cliente, fecha o estado GPS, los activos resaltados en amarillo no tienen coordenadas asignadas")
        except Exception as e:
            st.error(f"No fue posible cargar los activos: {e}")
            st.stop()

    # ======================================
    # OPCIÓN 5: SEGUIMIENTO GPS
    # ======================================
    elif option == "Seguimiento GPS":
        menuGPS.app(usuario)

    # ======================================
    # OPCIÓN 6: HISTORIAL DE MOVIMIENTOS
    # ======================================

    elif option == "Historial de Movimientos":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para ver el historial de movimientos de activos")
            return
        st.subheader("Historial de Movimientos de Activos")

        # Entradas para filtro por fecha y ubicación
        fecha_inicio = st.date_input("Fecha de inicio", datetime.now() - timedelta(days=90))
        fecha_fin = st.date_input("Fecha de fin", datetime.now())
        ubicacion = st.text_input("Ubicación")

        # Filtrar y mostrar el historial
        if st.button("Filtrar Movimientos"):
            movimientos = filter_movimientos(fecha_inicio, fecha_fin, ubicacion)
            st.write(movimientos)