import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from streamlit_drawable_canvas import st_canvas

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Persistencia.usuarioPersistencia import obtenerTipoUsuario
from Persistencia.contratosPersistencia import agregarContratos, cargarContratos, colsContratos, cargarContratosIdCliente, obtenerActivosAsociadosPorSeleccion
from Persistencia.activosPersistencia import cargarActivosDf
from Persistencia.actasPersistencia import agregarActas, cargarActas, colsActas
from Persistencia.alertasContratosPersistencia import (
    generarAlertasVencimiento, cargarAlertas, cambiarEstadoAlerta, enviar_email_alerta
)


# === UTILIDADES INTERNAS ===
def calcular_estado(fecha_inicio, fecha_fin):
    hoy = datetime.now().date()
    if hoy < fecha_inicio:
        return "Pendiente de inicio"
    elif fecha_inicio <= hoy <= fecha_fin:
        dias_restantes = (fecha_fin - hoy).days
        if dias_restantes <= 30:
            return "Por vencer"
        return "Vigente"
    else:
        return "Vencido"


@st.dialog("Contratos por vencer (30, 60 o 90 días)")
def mostrarContratosPorVencer():
    try:
        df = pd.DataFrame(cargarContratos(), columns=colsContratos)
    except Exception as e:
        st.error(f"No fue posible cargar los contratos: {e}")
        return

    if df.empty:
        st.info("No hay contratos registrados.")
        return

    df["fechaFin"] = pd.to_datetime(df["fechaFin"], errors="coerce")
    hoy = datetime.now()
    df["dias_restantes"] = (df["fechaFin"] - hoy).dt.days
    df_vencer = df[df["dias_restantes"].between(0, 90)]

    if df_vencer.empty:
        st.info("No hay contratos próximos a vencer (30, 60 o 90 días).")
        return

    df_vencer = df_vencer[["id", "cliente", "fechaFin", "dias_restantes", "estado"]]
    st.dataframe(df_vencer, use_container_width=True, hide_index=True)


# === VISTA PRINCIPAL ===
def app(usuario):
    tipoUsuario = obtenerTipoUsuario(usuario)
    st.subheader("Contratos")
    option = st.radio(
        label="Seleccione una función:",
        options=("Registrar Contrato", "Mostrar Contratos", "Registrar Acta", "Mostrar Actas")
    )

    # ------------------------------------------------------------------
    # 1️⃣ REGISTRAR CONTRATO
    # ------------------------------------------------------------------
    if option == "Registrar Contrato":
        if tipoUsuario not in ["Administrador", "Gerente"]:
            st.warning("No tiene permiso para registrar contratos.")
            return

        st.subheader("Registrar Contrato")

        cliente = st.text_input("Ingrese el nombre del cliente:")
        fechaInicio = st.date_input("Fecha de inicio:")
        fechaFin = st.date_input("Fecha de finalización:")
        condiciones = st.text_area("Condiciones del contrato:")

        # Cargar activos válidos (solo con coordenadas)
        df_activos = cargarActivosDf()
        df_activos = df_activos.dropna(subset=["latitud", "longitud"])
        df_activos = df_activos[
            df_activos["latitud"].apply(lambda x: isinstance(x, (int, float))) &
            df_activos["longitud"].apply(lambda x: isinstance(x, (int, float)))
        ]

        if df_activos.empty:
            st.error("No hay activos con coordenadas GPS válidas para asociar.")
            return

        activos_opciones = [
            f"{row['id_unico']} - {row['modelo']} ({row['cliente']})"
            for _, row in df_activos.iterrows()
            if pd.notna(row["id_unico"]) and pd.notna(row["modelo"])
        ]

        activosAsociados = st.multiselect(
            "Activos a asociar (máx. 5):",
            options=activos_opciones,
            max_selections=5
        )

        diasNotificar = st.number_input(
            "Días de anticipación para notificar vencimiento:",
            min_value=1, max_value=90, step=1, value=30
        )

        if st.button("Registrar Contrato"):
            if not cliente.strip() or not condiciones.strip():
                st.warning("Debe ingresar todos los datos obligatorios.")
                return
            if fechaFin <= fechaInicio:
                st.error("La fecha de finalización debe ser posterior a la de inicio.")
                return
            if not activosAsociados:
                st.error("Debe asociar al menos un activo con ubicación GPS válida.")
                return

            try:
                agregarContratos(cliente, str(fechaInicio), str(fechaFin), condiciones, activosAsociados, diasNotificar)
                st.success("Contrato registrado exitosamente.")
            except Exception as e:
                st.error(f"Error al registrar contrato: {e}")

    # ------------------------------------------------------------------
    # 2️⃣ MOSTRAR CONTRATOS
    # ------------------------------------------------------------------
    elif option == "Mostrar Contratos":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Gerente"]:
            st.warning("No tiene permiso para ver contratos.")
            return

        mostrarContratosPorVencer()
        st.subheader("Mostrar Contratos")

        try:
            df = pd.DataFrame(cargarContratos(), columns=colsContratos)
        except Exception as e:
            st.error(f"No fue posible cargar los contratos: {e}")
            return

        if df.empty:
            st.info("No hay contratos registrados.")
            return

        # Convertir fechas y calcular estado actual
        df["fechaInicio"] = pd.to_datetime(df["fechaInicio"], errors="coerce")
        df["fechaFin"] = pd.to_datetime(df["fechaFin"], errors="coerce")
        df["estado"] = df.apply(
            lambda r: calcular_estado(r["fechaInicio"].date(), r["fechaFin"].date())
            if pd.notna(r["fechaInicio"]) and pd.notna(r["fechaFin"]) else "Desconocido",
            axis=1
        )

        # Filtros
        colf1, colf2 = st.columns(2)
        with colf1:
            cliente_sel = st.selectbox(
                "Filtrar por cliente:",
                ["Todos"] + sorted(df["cliente"].dropna().unique())
            )
        with colf2:
            estado_sel = st.selectbox(
                "Filtrar por estado:",
                ["Todos"] + sorted(df["estado"].dropna().unique())
            )

        if cliente_sel != "Todos":
            df = df[df["cliente"] == cliente_sel]
        if estado_sel != "Todos":
            df = df[df["estado"] == estado_sel]

        if df.empty:
            st.info("No se encontraron contratos con los filtros seleccionados.")
            return

        # Mostrar tabla estilizada
        def color_estado(row):
            if row["estado"] == "Vigente":
                return ["background-color: #d4edda"] * len(row)
            elif row["estado"] == "Por vencer":
                return ["background-color: #fff3cd"] * len(row)
            elif row["estado"] == "Vencido":
                return ["background-color: #f8d7da"] * len(row)
            else:
                return ["background-color: #e2e3e5"] * len(row)

        st.dataframe(
            df.style.apply(color_estado, axis=1),
            use_container_width=True,
            hide_index=True
        )

        st.caption("Vigente | Por vencer | Vencido | Pendiente o desconocido")
        
        # --- Buzón de notificaciones: generar y mostrar ---
        df_alertas, df_nuevas = generarAlertasVencimiento(umbrales=(30, 60, 90))

        with st.expander("Buzón de notificaciones de vencimientos", expanded=True):
            if df_alertas.empty:
                st.info("No hay alertas registradas.")
            else:
                # Contadores por estado
                tot = len(df_alertas)
                n_nuevo = (df_alertas["estado"] == "nuevo").sum()
                n_enviado = (df_alertas["estado"] == "enviado").sum()
                n_leida = (df_alertas["estado"] == "leida").sum()
                st.write(f"Total: {tot} | Nuevas: {n_nuevo} | Enviadas: {n_enviado} | Leídas: {n_leida}")

                # Tabla de nuevas primero
                df_alertas = df_alertas.sort_values(by=["estado", "generada_en"], ascending=[True, False])
                st.dataframe(
                    df_alertas[["id_alerta", "id_contrato", "cliente", "activo", "fechaFin", "dias_restantes", "umbral", "estado"]],
                    use_container_width=True, hide_index=True
                )

                # Acciones sobre selección
                ids_seleccion = st.text_input("Ingrese IDs de alerta (separados por comas) para marcar o enviar:")
                colb1, colb2, colb3 = st.columns(3)
                with colb1:
                    if st.button("Marcar como leída"):
                        seleccion = [s.strip() for s in ids_seleccion.split(",") if s.strip()]
                        ok = 0
                        for sid in seleccion:
                            res, _ = cambiarEstadoAlerta(sid, "leida")
                            ok += 1 if res else 0
                        st.success(f"Alertas marcadas como leídas: {ok}")

                with colb2:
                    dest = st.text_input("Correo destinatario para envío (si está configurado SMTP):")
                with colb3:
                    if st.button("Enviar correo"):
                        seleccion = [s.strip() for s in ids_seleccion.split(",") if s.strip()]
                        df_sel = df_alertas[df_alertas["id_alerta"].astype(str).isin(seleccion)]
                        if df_sel.empty:
                            st.warning("No hay alertas seleccionadas válidas.")
                        else:
                            ok, msg = enviar_email_alerta(dest, df_sel)
                            if ok:
                                # Marcar como enviado
                                for sid in df_sel["id_alerta"].astype(str).tolist():
                                    cambiarEstadoAlerta(sid, "enviado")
                                st.success("Correo enviado y alertas marcadas como enviadas.")
                            else:
                                st.warning(f"No se envió correo: {msg}")

    # ------------------------------------------------------------------
    # 3️⃣ REGISTRAR ACTA
    # ------------------------------------------------------------------
    elif option == "Registrar Acta":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para registrar actas.")
            return

        st.subheader("Registrar Acta")

        contratoAsociado = st.selectbox("Contrato asociado:", options=cargarContratosIdCliente())
        razon = st.text_area("Razón del acta:")
        activosAsociados = st.multiselect(
            "Activos a asociar:",
            options=obtenerActivosAsociadosPorSeleccion(contratoAsociado),
            max_selections=5
        )

        st.markdown("### Firma digital")
        st.write("Firme dentro del recuadro:")
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=2,
            stroke_color="black",
            background_color="#ffffff",
            height=150,
            width=400,
            drawing_mode="freedraw",
            key="canvas"
        )

        if st.button("Registrar Acta"):
            if not razon.strip():
                st.warning("Debe ingresar todos los datos.")
                return
            agregarActas(contratoAsociado, razon, activosAsociados)
            st.success("Acta registrada con éxito.")

    # ------------------------------------------------------------------
    # 4️⃣ MOSTRAR ACTAS
    # ------------------------------------------------------------------
    elif option == "Mostrar Actas":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para ver actas.")
            return

        st.subheader("Mostrar Actas")
        try:
            df = pd.DataFrame(cargarActas(), columns=colsActas)
        except Exception as e:
            st.error(f"No fue posible cargar las actas: {e}")
            return

        if df.empty:
            st.info("No hay actas registradas.")
            return

        st.dataframe(df, use_container_width=True, hide_index=True)