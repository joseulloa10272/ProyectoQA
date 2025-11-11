# Vista/menuActivos.py
import streamlit as st
import sys
import os
import pandas as pd
import folium
from streamlit_folium import st_folium

# Rutas de import (estables)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Persistencia.activosPersistencia import (
    agregarActivos,
    registrarActivosRfid,
    importarActivosMasivoDesdeArchivo,
    cargarActivosDf,
    cargarActivosIdNombre,
    cargarHistorialMovimientos,
    colsActivos,
    existeIdUnico,
    existeTagEnActivos,
    registrarMovimiento,
)
from Persistencia.usuarioPersistencia import obtenerTipoUsuario


def _map_picker(lat_default=9.75, lon_default=-83.75, key="act_map_picker"):
    """Selector de coordenadas en mapa con estado persistente."""
    if f"{key}_lat" not in st.session_state:
        st.session_state[f"{key}_lat"] = None
        st.session_state[f"{key}_lon"] = None

    lat_c = st.session_state[f"{key}_lat"] or lat_default
    lon_c = st.session_state[f"{key}_lon"] or lon_default

    st.caption("Seleccione una ubicación sobre el mapa para asociarla al activo")
    m = folium.Map(location=[lat_c, lon_c], zoom_start=7, tiles="CartoDB positron")

    # marcador persistente si ya existe selección
    if st.session_state[f"{key}_lat"] is not None and st.session_state[f"{key}_lon"] is not None:
        folium.Marker(
            [st.session_state[f"{key}_lat"], st.session_state[f"{key}_lon"]],
            tooltip="Ubicación seleccionada"
        ).add_to(m)

    out = st_folium(m, height=380, width=820, key=f"{key}_component")

    # clic del usuario
    if out and out.get("last_clicked"):
        st.session_state[f"{key}_lat"] = float(out["last_clicked"]["lat"])
        st.session_state[f"{key}_lon"] = float(out["last_clicked"]["lng"])

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.text_input(
            "Latitud seleccionada",
            value=(f"{st.session_state[f'{key}_lat']:.6f}" if st.session_state[f"{key}_lat"] is not None else ""),
            disabled=True, key=f"{key}_lat_show"
        )
    with c2:
        st.text_input(
            "Longitud seleccionada",
            value=(f"{st.session_state[f'{key}_lon']:.6f}" if st.session_state[f"{key}_lon"] is not None else ""),
            disabled=True, key=f"{key}_lon_show"
        )
    with c3:
        if st.button("Reiniciar selección", key=f"{key}_reset"):
            st.session_state[f"{key}_lat"] = None
            st.session_state[f"{key}_lon"] = None

    return st.session_state[f"{key}_lat"], st.session_state[f"{key}_lon"]


def app(usuario):
    tipoUsuario = obtenerTipoUsuario(usuario)
    st.subheader("Activos")

    option = st.radio(
        label="Seleccione una función:",
        options=("Registrar", "Importar por RFID", "Importación masiva", "Mostrar", "Historial de movimientos"),
        key="act_menu_radio",
    )

    # ================ Registrar ================
    if option == "Registrar":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para registrar activos.")
            return

        st.subheader("Registrar")

        id_unico    = st.text_input("Ingrese el ID único:")
        modelo      = st.text_input("Ingrese el modelo:")
        serie       = st.text_input("Ingrese la serie:")
        fabricante  = st.text_input("Ingrese el fabricante:")
        fechaCompra = st.text_input("Ingrese la fecha de compra (YYYY-MM-DD):")

        c1, c2 = st.columns(2)
        with c1:
            cliente  = st.text_input("Ingrese el cliente:")
            tag      = st.text_input("Ingrese el tag:")
        with c2:
            valor    = st.number_input("Ingrese el valor:", min_value=0.0, step=0.01)
            fotos    = st.text_input("Ingrese las fotos:")

        # Selector de coordenadas en mapa
        lat_sel, lon_sel = _map_picker(key="act_reg_map")

        fechaRegistro = st.text_input("Ingrese la fecha de registro (YYYY-MM-DD HH:MM:SS):")

        if st.button("Registrar Activo", key="act_reg_btn"):
            oblig = [
                ("ID único", id_unico),
                ("modelo", modelo),
                ("serie", serie),
                ("fabricante", fabricante),
                ("fecha de compra", fechaCompra),
                ("cliente", cliente),
                ("fecha de registro", fechaRegistro),
            ]
            vacios = [k for k, v in oblig if not str(v).strip()]
            if vacios:
                st.warning(f"Debe ingresar todos los datos: {', '.join(vacios)}.")
                return

            if lat_sel is None or lon_sel is None:
                st.warning("Seleccione la ubicación en el mapa antes de registrar.")
                return

            if existeIdUnico(id_unico):
                st.warning("El ID único ya existe en el sistema.")
                return
            if str(tag).strip() and existeTagEnActivos(tag):
                st.warning("El tag RFID/QR ya existe en el sistema.")
                return

            try:
                reg = agregarActivos(
                    id_unico=id_unico.strip(),
                    modelo=modelo.strip(),
                    serie=serie.strip(),
                    fabricante=fabricante.strip(),
                    fechaCompra=fechaCompra.strip(),
                    latitud=float(lat_sel),
                    longitud=float(lon_sel),
                    cliente=cliente.strip(),
                    valor=float(valor),
                    tag=str(tag).strip(),
                    fotos=str(fotos).strip(),
                    fechaRegistro=fechaRegistro.strip(),
                    usuario=str(usuario).strip(),
                )
                registrarMovimiento(id_unico, float(lat_sel), float(lon_sel), "Registro inicial de activo")
                st.success("Activo registrado con éxito y movimiento inicial guardado.")
            except Exception as e:
                st.error(f"No se registró el activo: {e}")

    # ============ Importar por RFID ============
    elif option == "Importar por RFID":
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para importar activos.")
            return

        st.subheader("Importar por RFID")
        with st.form("form_rfid", clear_on_submit=False):
            rfidCode = st.text_input("Código RFID", help="Escanéelo o escríbalo tal cual aparece en el tag.")
            submitted = st.form_submit_button("Buscar y Registrar")

        if submitted:
            try:
                ok, info = registrarActivosRfid(rfidCode, usuario)
                if ok:
                    st.success(f"Activo registrado correctamente. ID nuevo: {info}")
                else:
                    st.error(str(info))
            except Exception as e:
                st.error(f"Fallo durante el registro RFID: {e}")

    # ================= Importación masiva =================
    elif option == "Importación masiva":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para importar activos masivamente.")
            return

        st.subheader("Importación masiva desde archivo (xlsx/csv)")
        archivo = st.file_uploader(
            "Seleccione el archivo con columnas requeridas "
            "(id_unico, modelo, serie, fabricante, fechaCompra, latitud, longitud, cliente, valor, tag)",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=False,
            key="act_mass_uploader",
        )

        if archivo is not None:
            try:
                import io
                if archivo.name.lower().endswith((".xlsx", ".xls")):
                    prev = pd.read_excel(io.BytesIO(archivo.read()))
                else:
                    prev = pd.read_csv(io.BytesIO(archivo.read()))
                st.dataframe(prev.head(20), use_container_width=True, hide_index=True, key="act_mass_preview")
                archivo.seek(0)
            except Exception:
                st.info("Previsualización no disponible, aun así resulta válido validar y cargar.")

        if st.button("Validar y cargar", key="act_mass_btn"):
            if archivo is None:
                st.warning("Primero seleccione un archivo.")
            else:
                try:
                    ok, rep = importarActivosMasivoDesdeArchivo(archivo, archivo.name, usuario)
                    if ok:
                        st.success("Importación finalizada.")
                        st.write(f"Insertados: {rep.get('insertados', 0)}")
                        st.write(f"Omitidos: {rep.get('omitidos', 0)}")
                        if rep.get("razones_omision"):
                            st.subheader("Omitidos")
                            for r in rep["razones_omision"]:
                                st.write(f"Fila {r.get('fila','?')}: RFID={r.get('rfid','')} → {r.get('motivo','')}")
                    else:
                        st.error(rep.get("error", "Error desconocido."))
                except Exception as e:
                    st.error(f"Fallo en la importación: {e}")

    # ================= Mostrar =================
    elif option == "Mostrar":
        if tipoUsuario != "Administrador":
            st.warning("No tiene permiso para ver los activos registrados.")
            return
        st.subheader("Activos registrados")

        try:
            activosList = cargarActivosDf()
            df = pd.DataFrame(activosList, columns=colsActivos)
        except Exception as e:
            st.error(f"No fue posible cargar los activos: {e}")
            st.stop()
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ============== Historial de movimientos ==============
    elif option == "Historial de movimientos":
        st.subheader("Historial de movimientos")

        # lista amigable: "ID_UNICO - MODELO (CLIENTE)"
        opciones = cargarActivosIdNombre()
        if not opciones:
            st.info("No existen activos registrados.")
            return

        elegido = st.selectbox("Activo", opciones, key="act_hist_sel")
        # extraer el id_unico antes del guion
        id_unico = elegido.split(" - ")[0].strip()

        c1, c2 = st.columns(2)
        with c1:
            f_ini = st.date_input("Desde", value=None, key="act_hist_ini")
        with c2:
            f_fin = st.date_input("Hasta", value=None, key="act_hist_fin")

        f_ini_str = f_ini.strftime("%Y-%m-%d") if f_ini else None
        f_fin_str = f_fin.strftime("%Y-%m-%d") if f_fin else None

        try:
            dfh = cargarHistorialMovimientos(id_unico, f_ini_str, f_fin_str)
        except Exception as e:
            st.error(f"No fue posible cargar el historial: {e}")
            return

        if dfh is None or dfh.empty:
            st.info("Sin registros de movimientos para los filtros indicados.")
            return

        # orden cronológico descendente
        dfh = dfh.sort_values("fecha", ascending=False)
        st.dataframe(dfh, use_container_width=True, hide_index=True, key="act_hist_grid")

        # descarga opcional
        csv = dfh.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar CSV", data=csv, file_name=f"historial_{id_unico}.csv", mime="text/csv", key="act_hist_dl")