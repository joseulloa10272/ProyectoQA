import streamlit as st, pandas as pd, sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Validación de usuario / rol
try:
    from Validaciones.usuarioValidaciones import existeUsuario as _exists_user
except Exception:
    def _exists_user(u): return True
try:
    from Validaciones.usuarioValidaciones import obtenerTipoUsuario as _get_role
except Exception:
    def _get_role(u): return "Administrador"

# Activos (para seleccionar el equipo al que se asigna la refacción)
try:
    from Persistencia.activosPersistencia import cargarActivos
except Exception:
    cargarActivos = None

from Controlador.refaccionesController import (
    crearRefaccion, moverStock, setUmbral, refaccionesDeActivo,
    generarAlertas,
)

from Persistencia.refaccionesPersistencia import (
    cargarRefacciones, refaccionesBajoUmbral, obtenerStock
)
from Persistencia.alertasRefaccionesPersistencia import (
    generarAlertasBajoUmbral, cargarAlertas, cambiarEstadoAlerta
)

ROLES_PERMITIDOS = {"Administrador","Gerente","Encargado","Almacen"}

def _check_acceso(usuario):
    if not _exists_user(usuario):
        st.error("Usuario no válido."); st.stop()
    rol = (_get_role(usuario) or "").strip().title()
    if rol not in ROLES_PERMITIDOS:
        st.error("Acceso restringido para su rol."); st.stop()
    return rol

def _lista_activos():
    if cargarActivos:
        return cargarActivos()
    # Fallback por si no existe la función (intenta leer columnas mínimas)
    st.warning("No encontré 'cargarActivos' en Persistencia. Muestra solo controles de refacciones.")
    return pd.DataFrame(columns=["id","modelo","serie","cliente"])

def mostrar_buzon_notificaciones():
    from Persistencia.alertasRefaccionesPersistencia import cargarAlertas, cambiarEstadoAlerta
    import streamlit as st
    df = cargarAlertas()
    if df.empty:
        st.info("Sin notificaciones nuevas.")
        return

    nuevas = df.loc[df["estado"] == "nuevo"]
    vistas = df.loc[df["estado"] == "visto"]

    total = len(nuevas)
    st.subheader(f"🔔 Buzón de notificaciones ({total} nuevas)")
    if total == 0:
        st.success("No hay alertas nuevas.")
    else:
        for _, r in nuevas.iterrows():
            with st.expander(f"⚠️ Refacción {r['nombre']} | Stock={r['stock']} / Umbral={r['umbral']}"):
                st.write(f"**Activo:** {r['id_activo']}")
                st.write(f"**Fecha:** {r['generada_en']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Marcar como vista", key=f"vista_{r['id_alerta']}"):
                        cambiarEstadoAlerta(r['id_alerta'], "visto")
                        st.rerun()
                with c2:
                    if st.button("Marcar como atendida", key=f"atendida_{r['id_alerta']}"):
                        cambiarEstadoAlerta(r['id_alerta'], "atendido")
                        st.rerun()

    if not vistas.empty:
        st.divider()
        st.markdown("### 🔎 Alertas vistas")
        for _, r in vistas.iterrows():
            st.text(f"{r['nombre']} — Stock {r['stock']} / Umbral {r['umbral']} (Activo {r['id_activo']})")

def app(usuario=""):
    st.title("Refacciones y Alertas")
    _check_acceso(usuario if usuario else st.session_state.get("usuario",""))

    tab1, tab2, tab3, tab4 = st.tabs(["Catálogo", "Movimientos", "Umbrales & Alertas", "Dashboard"])

    # ------------------- TAB 1: Catálogo -------------------
    with tab1:
        st.subheader("Asignar refacciones a un ACTIVO específico")
        df_act = _lista_activos()

        # Convertir lista a DataFrame si es necesario
        if isinstance(df_act, list):
            import pandas as pd
            df_act = pd.DataFrame(df_act)

        # Si sigue vacío, mostrar mensaje
        if df_act is None or df_act.empty:
            st.info("No hay activos registrados.")
        else:
            opciones_act = {f"[{r['id']}] {r.get('modelo','')} - {r.get('serie','')}": r["id"] for _, r in df_act.iterrows()}
            sel_act = st.selectbox("Seleccione activo", list(opciones_act.keys()))
            id_activo = opciones_act[sel_act]
            st.caption(f"Activo seleccionado: {sel_act}")

            st.markdown("### Refacciones del activo")
            st.dataframe(refaccionesDeActivo(id_activo), use_container_width=True)

            st.markdown("**Nueva refacción para este activo**")
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre refacción")
                modelo = st.text_input("Modelo de equipo (opcional)")
                umbral = st.number_input("Umbral", min_value=0, step=1, value=0)
            with col2:
                stock_ini = st.number_input("Stock inicial", min_value=0, step=1, value=0)
                ubic = st.text_input("Ubicación")
            if st.button("Agregar refacción", type="primary"):
                if not nombre.strip():
                    st.error("Nombre es obligatorio.")
                else:
                    nuevo = crearRefaccion(id_activo, nombre, modelo, stock_ini, umbral, ubic)
                    st.success(f"Refacción creada y vinculada al activo {id_activo} (ID refacción {nuevo['id']}).")
                    st.rerun()

    # ------------------- TAB 2: Movimientos -------------------
    with tab2:
        st.subheader("Movimientos de stock")
        df_ref = cargarRefacciones()
        if df_ref.empty:
            st.info("No hay refacciones registradas.")
        else:
            # 1️⃣ Seleccionar activo
            activos = df_ref["id_activo"].dropna().unique().astype(str)
            activo_sel = st.selectbox("Seleccione un activo", activos, format_func=lambda x: f"Activo {x}")
            df_activo = df_ref[df_ref["id_activo"].astype(str) == str(activo_sel)]

            # 2️⃣ Mostrar refacciones del activo
            st.dataframe(df_activo[["id","nombre","modeloEquipo","stock","umbral","ubicacion"]], use_container_width=True)

            # 3️⃣ Elegir refacción
            ref_opts = {f"[{r['id']}] {r['nombre']}": r["id"] for _, r in df_activo.iterrows()}
            ref_sel = st.selectbox("Refacción", list(ref_opts.keys()))
            id_ref = ref_opts[ref_sel]

            stock_actual = obtenerStock(id_ref)
            st.caption(f"Stock actual: **{stock_actual}**")

            tipo = st.radio("Tipo de movimiento", ["entrada","salida"], horizontal=True)
            cant = st.number_input("Cantidad", min_value=1, step=1, value=1)
            motivo = st.text_input("Motivo")
            usuario_mv = st.text_input("Usuario que registra", value=usuario)

            # Validación
            if tipo == "salida" and cant > stock_actual:
                st.error(f"No se puede retirar {cant} unidades (stock actual {stock_actual}).")
                disabled = True
            else:
                disabled = False

            # 4️⃣ Registrar movimiento
            if st.button("Registrar movimiento", type="primary", disabled=disabled):
                mv = moverStock(id_ref, tipo, cant, motivo, usuario_mv)
                generarAlertasBajoUmbral()  # genera nuevas alertas si aplica
                low = refaccionesBajoUmbral()
                if not low.empty and str(id_ref) in list(low["id"].astype(str)):
                    st.warning("⚠️ Esta refacción alcanzó o está por debajo del umbral.")
                    st.toast("🔔 Alerta: refacción con stock igual o menor al umbral.")
                st.success(f"Movimiento {mv['id_mov']} registrado correctamente.")
                st.toast(f"✅ Movimiento de {tipo} ({cant}) aplicado a {ref_sel}")
                st.rerun()

    # ------------------- TAB 3: Umbrales & Alertas -------------------
    with tab3:
        st.subheader("Umbrales y alertas")

        df = cargarRefacciones()
        if df.empty:
            st.info("No hay refacciones registradas.")
        else:
            activos = df["id_activo"].dropna().unique().astype(str)
            act_sel = st.selectbox("Seleccione un activo", activos)
            df_act = df[df["id_activo"].astype(str) == str(act_sel)]

            ref_opts = {f"[{r['id']}] {r['nombre']}": r["id"] for _, r in df_act.iterrows()}
            ref_sel = st.selectbox("Seleccione refacción", list(ref_opts.keys()))
            id_ref = ref_opts[ref_sel]

            umbral_actual = int(df_act[df_act["id"].astype(str) == str(id_ref)]["umbral"].iloc[0])
            n_umbral = st.number_input("Nuevo umbral", min_value=0, step=1, value=umbral_actual)
            if st.button("Actualizar umbral"):
                setUmbral(id_ref, n_umbral)
                st.success("Umbral actualizado correctamente.")
                generarAlertas()  # Genera alertas si aplica
                st.toast("🔔 Se actualizó el umbral y se verificaron alertas.")
                st.rerun()

        st.divider()
        st.markdown("### 🔔 Buzón de notificaciones")
        mostrar_buzon_notificaciones()

    # ------------------- TAB 4: Dashboard -------------------
    with tab4:
        st.subheader("Dashboard — Refacciones y Alertas")

        df = cargarRefacciones()
        df_alert = cargarAlertas()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**📦 Refacciones por Activo**")
            if not df.empty:
                ref_count = df.groupby("id_activo").size().reset_index(name="Cantidad")
                st.bar_chart(ref_count.set_index("id_activo"))
            else:
                st.info("No hay refacciones registradas.")

        with col2:
            st.markdown("**🔔 Alertas por Estado**")
            if not df_alert.empty:
                state_count = df_alert.groupby("estado").size().reset_index(name="Cantidad")
                st.bar_chart(state_count.set_index("estado"))
            else:
                st.info("No hay alertas registradas.")

        st.divider()
        st.markdown("**📋 Detalle de Refacciones bajo umbral**")
        low = refaccionesBajoUmbral()
        if low.empty:
            st.success("Todo en orden, sin refacciones bajo umbral. 🎉")
        else:
            st.warning(f"{len(low)} refacciones bajo umbral.")
            st.dataframe(low[["id","id_activo","nombre","stock","umbral"]], use_container_width=True)