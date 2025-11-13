# Vista/menuRefacciones.py
import os, sys
import streamlit as st
import pandas as pd

# rutas de import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# backend de alertas (automático)
from Persistencia.alertasRefaccionesPersistencia import (
    evaluar_y_enviar_alertas,
    cargar_buzon_alertas,
)

# backend de refacciones
from Persistencia.refaccionesPersistencia import (
    refacciones_de_activo,
    agregar_refaccion,
    registrar_movimiento,
    actualizar_umbral,
)

# activos
from Persistencia.activosPersistencia import cargarActivosDf


# ================== Utilidades ==================
def _df_activos():
    df = cargarActivosDf()
    if df.empty:
        return df
    # etiqueta para selectores: conserva el id_unico
    df["label"] = df.apply(
        lambda r: f"{str(r.get('id_unico','')).strip()} - {str(r.get('modelo','')).strip()}"
                  + (f" ({str(r.get('cliente','')).strip()})" if str(r.get('cliente','')).strip() else ""),
        axis=1
    )
    # nombre para dashboard: SOLO modelo (+ cliente), sin ids
    df["nombre"] = df.apply(
        lambda r: (str(r.get('modelo','')).strip() or "Activo sin modelo")
                  + (f" ({str(r.get('cliente','')).strip()})" if str(r.get('cliente','')).strip() else ""),
        axis=1
    )
    df["id"] = df["id"].astype(str)
    df["id_unico"] = df["id_unico"].astype(str)
    return df[["id","id_unico","label","nombre"]]


def _pick_activo(key_suffix: str):
    """Selector de activo con clave única por pestaña."""
    dfA = _df_activos()
    opciones = dfA["label"].tolist()
    if not opciones:
        st.info("No hay activos registrados.")
        return None, None, None
    etiqueta = st.selectbox(
        "Seleccione un activo",
        opciones,
        key=f"rf_sel_activo_{key_suffix}",
    )
    fila = dfA[dfA["label"] == etiqueta].iloc[0]
    return (fila["id"], fila["id_unico"], etiqueta)


def _pick_refaccion(id_activo, key_suffix: str):
    """Selector de refacción con clave única por pestaña."""
    df = refacciones_de_activo(id_activo)
    if df.empty:
        return None, None
    df = df.copy()
    df["etq"] = "[" + df["id_ref"].astype(str) + "] " + df["nombre"].astype(str)
    etq = st.selectbox(
        "Seleccione refacción",
        df["etq"].tolist(),
        key=f"rf_sel_ref_{key_suffix}",
    )
    fila = df[df["etq"] == etq].iloc[0]
    return (fila["id_ref"], fila)


# ================== Pestaña: Catálogo ==================
def _tab_catalogo():
    st.subheader("Asignar refacciones a un ACTIVO específico")

    id_activo, id_unico, etiqueta = _pick_activo("cat")
    if not id_activo:
        st.info("Primero seleccione un activo del catálogo.")
        return

    st.caption(f"Activo seleccionado: {etiqueta}")

    df_ref = refacciones_de_activo(id_activo)
    if not df_ref.empty:
        st.dataframe(
            df_ref[["id_ref","nombre","modeloEquipo","stock","umbral","actualizado_en"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Este activo aún no tiene refacciones registradas.")

    st.markdown("---")
    nombre   = st.text_input("Nombre de refacción", key="rf_n_cat")
    modelo   = st.text_input("Modelo de equipo (opcional)", key="rf_m_cat")
    stock_i  = st.number_input("Stock inicial", min_value=0, step=1, value=0, key="rf_si_cat")
    umbral   = st.number_input("Umbral", min_value=0, step=1, value=0, key="rf_um_cat")

    if st.button("Agregar refacción", type="primary", key="rf_add_btn_cat"):
        try:
            agregar_refaccion(id_activo, id_unico, nombre, modelo, stock_i, umbral)
            # evaluar alertas de inmediato (por si queda bajo umbral)
            evaluar_y_enviar_alertas(st.session_state.get("usuario",""))
            st.success("Refacción registrada.")
            st.rerun()
        except Exception as e:
            st.error(f"No se registró la refacción: {e}")


# ================== Pestaña: Movimientos ==================
def _tab_movimientos():
    st.subheader("Movimientos de stock")

    id_activo, id_unico, etiqueta = _pick_activo("mov")
    if not id_activo:
        st.info("Seleccione un activo para ver y registrar movimientos.")
        return

    df_ref = refacciones_de_activo(id_activo)
    st.dataframe(
        df_ref[["id_ref","nombre","modeloEquipo","stock","umbral"]],
        use_container_width=True,
        hide_index=True
    )
    if df_ref.empty:
        return

    id_ref, fila = _pick_refaccion(id_activo, "mov")
    if id_ref is None:
        st.info("Este activo no tiene refacciones cargadas.")
        return

    st.caption(f"Stock actual de **{fila['nombre']}**: {int(fila['stock'])}  |  Umbral: {int(fila['umbral'])}")
    tipo = st.radio("Tipo de movimiento", options=("entrada","salida"), horizontal=True, key="rf_mv_tipo_mov")
    cant = st.number_input("Cantidad", min_value=1, step=1, value=1, key="rf_mv_cant_mov")
    motivo = st.text_input("Motivo", key="rf_mv_mot_mov")

    if st.button("Registrar movimiento", type="primary", key="rf_mv_btn_mov"):
        try:
            registrar_movimiento(id_activo, id_ref, tipo, cant, motivo)
            # evaluación automática tras el movimiento
            evaluar_y_enviar_alertas(st.session_state.get("usuario",""))
            st.success("Movimiento registrado.")
            st.rerun()
        except Exception as e:
            st.error(f"No se registró el movimiento: {e}")


# ================== Pestaña: Umbrales & Alertas ==================
def _tab_umbral_alertas(usuario: str):
    # evaluación + envío automático al entrar/rerun
    evaluar_y_enviar_alertas(st.session_state.get("usuario",""))

    st.subheader("Umbrales y alertas")

    # gestor de umbral por activo/refacción (sin cambios)
    id_activo, id_unico, etiqueta = _pick_activo("um")
    if not id_activo:
        st.info("Seleccione un activo para gestionar umbrales.")
        return
    df_ref = refacciones_de_activo(id_activo)
    if df_ref.empty:
        st.info("Este activo no tiene refacciones aún.")
        return

    id_ref, fila = _pick_refaccion(id_activo, "um")
    if id_ref is None:
        return
    nuevo = st.number_input("Nuevo umbral", min_value=0, step=1, value=int(fila["umbral"]), key="rf_new_um_um")
    if st.button("Actualizar umbral", key="rf_upd_um_um"):
        try:
            actualizar_umbral(id_activo, id_ref, nuevo)
            evaluar_y_enviar_alertas(st.session_state.get("usuario",""))  # recalcula buzón tras el cambio
            st.success("Umbral actualizado.")
            st.rerun()
        except Exception as e:
            st.error(f"No se actualizó el umbral: {e}")

    st.markdown("---")
    st.subheader("Buzón de notificaciones")

    # filtros del buzón
    bz_all = cargar_buzon_alertas()
    act_opts = ["Todos"] + sorted(bz_all["id_unico"].astype(str).unique().tolist()) if not bz_all.empty else ["Todos"]
    c1, c2 = st.columns([1,1])
    with c1:
        f_act = st.selectbox("Filtrar por activo", act_opts, key="rf_bz_act")
    with c2:
        f_est = st.selectbox("Estado", ["Todos","Pendientes","Enviadas"], key="rf_bz_est")

    bz = cargar_buzon_alertas(
        f_id_unico=None if f_act == "Todos" else f_act,
        f_estado=None if f_est == "Todos" else f_est
    )

    if bz is None or bz.empty:
        st.info("Sin alertas activas en este momento.")
    else:
        cols = [c for c in ["id_unico","refaccion","stock","umbral","enviado_email","ts"] if c in bz.columns]
        st.dataframe(bz[cols], use_container_width=True, hide_index=True, height=280)

# ================== Pestaña: Dashboard ==================
def _tab_dashboard():
    st.subheader("Dashboard — Refacciones y Alertas")

    try:
        import altair as alt
        _has_alt = True
    except Exception:
        _has_alt = False

    dfA = _df_activos()
    resumen = []
    for _, a in dfA.iterrows():
        df_r = refacciones_de_activo(a["id"])
        if df_r.empty:
            continue
        total = len(df_r)
        bajos = int((df_r["stock"].astype(int) <= df_r["umbral"].astype(int)).sum())
        resumen.append({
            "activo_id": a["id"],
            "activo_nombre": a["nombre"],     # sin ids
            "refacciones": total,
            "bajo_umbral": bajos
        })

    if not resumen:
        st.info("Sin datos para graficar")
        return

    df_sum = pd.DataFrame(resumen)

    c1, c2 = st.columns(2)

    if _has_alt:
        # Barras: refacciones registradas por activo
        chart_bar = (
            alt.Chart(df_sum)
            .mark_bar()
            .encode(
                x=alt.X("activo_nombre:N", sort="-y", title="Activo"),
                y=alt.Y("refacciones:Q", title="Refacciones registradas"),
                tooltip=["activo_nombre","refacciones","bajo_umbral"]
            )
            .properties(height=320)
        )
        with c1:
            st.altair_chart(chart_bar, use_container_width=True)

        # Donut: distribución de alertas por activo
        df_pie = df_sum[df_sum["bajo_umbral"] > 0][["activo_nombre","bajo_umbral"]]
        with c2:
            if df_pie.empty:
                st.info("Sin alertas bajo umbral")
            else:
                chart_pie = (
                    alt.Chart(df_pie)
                    .mark_arc(innerRadius=60)
                    .encode(
                        theta=alt.Theta("bajo_umbral:Q", title="Alertas"),
                        color=alt.Color("activo_nombre:N", title="Activo"),
                        tooltip=["activo_nombre","bajo_umbral"]
                    )
                    .properties(height=320)
                )
                st.altair_chart(chart_pie, use_container_width=True)
    else:
        with c1:
            st.bar_chart(df_sum.set_index("activo_nombre")["refacciones"])
        with c2:
            st.bar_chart(df_sum.set_index("activo_nombre")["bajo_umbral"])

    st.markdown("— Detalle de refacciones bajo umbral")
    filas = []
    for _, a in dfA.iterrows():
        df_r = refacciones_de_activo(a["id"])
        if df_r.empty:
            continue
        bajo = df_r[df_r["stock"].astype(int) <= df_r["umbral"].astype(int)]
        if not bajo.empty:
            b = bajo.copy()
            b.insert(0, "activo", a["nombre"])  # nombre sin ids
            filas.append(b[["activo","id_ref","nombre","stock","umbral"]])
    if filas:
        st.dataframe(pd.concat(filas, ignore_index=True),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No hay refacciones bajo umbral")


# ================== Entrada principal ==================
def app(usuario: str):
    st.subheader("Refacciones y Alertas")
    st.session_state["usuario"] = usuario  # para resolver correo en alertas automáticas

    tabs = st.tabs(["Catálogo","Movimientos","Umbrales & Alertas","Dashboard"])
    with tabs[0]:
        _tab_catalogo()
    with tabs[1]:
        _tab_movimientos()
    with tabs[2]:
        _tab_umbral_alertas(usuario)
    with tabs[3]:
        _tab_dashboard()