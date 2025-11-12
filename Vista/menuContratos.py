# Vista/menuContratos.py
import streamlit as st
import sys, os, json, inspect
import pandas as pd

# Rutas de import estables
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Persistencia.usuarioPersistencia import obtenerTipoUsuario
# correo del usuario si existe
try:
    from Persistencia.usuarioPersistencia import obtenerCorreoUsuario as _get_user_email
except Exception:
    _get_user_email = lambda _: None  # noqa: E731

# Backend mínimo requerido de contratos
from Persistencia.contratosPersistencia import (
    agregarContratos,
    cargarContratos,
)

# Columnas de contratos si existen; si no, fallback dinámico
try:
    from Persistencia.contratosPersistencia import colsContratos
except Exception:
    colsContratos = None

# Alertas avanzadas y envío por correo si están integradas
_ALERTAS_OK = False
proximosVencimientos = None
cargarAlertas = None
generarAlertasVencimiento_en_caliente = None
_enviar_alertas_backend = None

try:
    from Persistencia.contratosPersistencia import (
        generarAlertasVencimiento_en_caliente,
        cargarAlertas,
        proximosVencimientos,
        enviarAlertasVencimiento_por_correo as _enviar_alertas_backend,
    )
    _ALERTAS_OK = True
except Exception:
    try:
        from Persistencia.alertasContratosPersistencia import (
            generarAlertasVencimiento_en_caliente,
            cargarAlertas,
            proximosVencimientos,
            enviarAlertasVencimiento_por_correo as _enviar_alertas_backend,
        )
        _ALERTAS_OK = True
    except Exception:
        try:
            from Persistencia.contratosPersistencia import proximosVencimientos  # type: ignore
        except Exception:
            pass

# Fallback de correo directo si el backend no trae función dedicada
try:
    from Persistencia.notificacionesEmail import enviar_email as _enviar_email_directo
except Exception:
    _enviar_email_directo = None

# Activos: lista legible "ID - Modelo (Cliente)"
from Persistencia.activosPersistencia import cargarActivosIdNombre
# Actas
from Persistencia.actasPersistencia import agregarActas, cargarActas
try:
    from Persistencia.actasPersistencia import colsActas
except Exception:
    colsActas = None


# ========================= Utilitarios locales =========================
def _estado_calc(fi: str, ff: str) -> str:
    hoy = pd.Timestamp.today().normalize()
    ini = pd.to_datetime(fi, errors="coerce")
    fin = pd.to_datetime(ff, errors="coerce")
    if pd.isna(fin):
        return "Sin fecha fin"
    if fin < hoy:
        return "Vencido"
    dias = int((fin - hoy).days)
    if dias <= 30:
        return "Por vencer"
    return "Vigente"

def _normalize_activo_id(s: str) -> str:
    if s is None:
        return ""
    txt = str(s).strip().strip("[]()\"' ")
    if "-" in txt:
        txt = txt.split("-", 1)[0].strip()
    if " " in txt:
        txt = txt.split(" ", 1)[0].strip()
    return "".join(ch for ch in txt if ch.isalnum())

def _map_activo_label() -> dict:
    """Construye un mapa id_unico -> 'ID - Modelo (Cliente)' desde cargarActivosIdNombre()."""
    etiquetas = cargarActivosIdNombre() or []
    out = {}
    for etq in etiquetas:
        _id = etq.split(" - ")[0].strip()
        if _id:
            out[_id] = etq
    return out

def _lista_contratos_id_cliente() -> list[str]:
    """Devuelve ['id - cliente', ...] a partir de cargarContratos()."""
    try:
        rows = cargarContratos()
        if not rows:
            return []
        df = pd.DataFrame(rows)
        if "id" not in df.columns or "cliente" not in df.columns:
            return []
        df["id"] = df["id"].astype(str).str.strip()
        df["cliente"] = df["cliente"].astype(str).str.strip()
        out = (df["id"] + " - " + df["cliente"]).tolist()
        seen, uniq = set(), []
        for x in out:
            if x not in seen:
                uniq.append(x); seen.add(x)
        return uniq
    except Exception:
        return []

def _activos_asociados_por_seleccion(contrato_sel: str) -> list[str]:
    """Desde 'id - cliente' obtiene activos asociados como etiquetas legibles, máx 5."""
    if not contrato_sel:
        return []
    id_sel = contrato_sel.split(" - ")[0].strip()
    try:
        rows = cargarContratos()
        if not rows:
            return []
        contrato = next((r for r in rows if str(r.get("id","")).strip() == id_sel), None)
        if not contrato:
            return []
        raw = contrato.get("activosAsociados", "")
        lista_ids = []
        if isinstance(raw, list):
            lista_ids = [_normalize_activo_id(x) for x in raw]
        elif isinstance(raw, str):
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    lista_ids = [_normalize_activo_id(x) for x in data]
                else:
                    lista_ids = [_normalize_activo_id(raw)]
            except Exception:
                parts = [p.strip() for p in raw.replace(";", ",").split(",")] if ("," in raw or ";" in raw) else [raw]
                lista_ids = [_normalize_activo_id(p) for p in parts]
        else:
            lista_ids = [_normalize_activo_id(str(raw))]
        lista_ids = [x for x in lista_ids if x]
        mapa = _map_activo_label()
        out = [mapa.get(aid, aid) for aid in lista_ids]
        return out[:5]
    except Exception:
        return []

def _dedupe_por_id_ui(df: pd.DataFrame) -> pd.DataFrame:
    """Defensa en UI por si el backend aún no deduplica por contrato."""
    if df is None or df.empty or "id_contrato" not in df.columns:
        return df
    df = df.copy()
    if "dias_restantes" in df.columns:
        df = df.sort_values(["id_contrato", "dias_restantes"], ascending=[True, True])
    df = df.drop_duplicates(subset=["id_contrato"], keep="first")
    return df

def _enviar_alertas_por_correo(usuario: str, destinatario: str | None = None, df_alertas: pd.DataFrame | None = None) -> tuple[bool, str]:
    """Intenta el envío con el backend y acepta override de destinatario, en su defecto usa fallback directo."""
    # Backend preferente con detección de firma
    if callable(_enviar_alertas_backend):
        try:
            sig = inspect.signature(_enviar_alertas_backend)
            if len(sig.parameters) >= 2:
                return _enviar_alertas_backend(usuario, destinatario)  # type: ignore
            return _enviar_alertas_backend(usuario)  # type: ignore
        except TypeError:
            try:
                return _enviar_alertas_backend(usuario)  # type: ignore
            except Exception as e:
                return False, f"Fallo de envío en backend: {e}"
        except Exception as e:
            return False, f"Fallo de envío en backend: {e}"

    # Fallback directo
    if _enviar_email_directo is None:
        return False, "Canal de correo no disponible en este entorno."
    destino = destinatario or _get_user_email(usuario)
    if not destino:
        return False, "El usuario no tiene correo registrado."
    df = df_alertas
    if df is None:
        try:
            df = cargarAlertas() if callable(cargarAlertas) else None
        except Exception:
            df = None
    if df is None or df.empty:
        return False, "No hay alertas vigentes para enviar."
    df = _dedupe_por_id_ui(df)
    filas = []
    for _, r in df.iterrows():
        filas.append(f"- Contrato {str(r.get('id_contrato',''))} · Cliente {str(r.get('cliente',''))} · Vence {str(r.get('fechaFin',''))} · Restan {str(r.get('dias_restantes',''))} días")
    cuerpo = "Hola,\n\nEstos contratos se encuentran próximos a vencer según el umbral configurado:\n\n" + "\n".join(filas) + "\n\nEste mensaje se generó automáticamente."
    asunto = "Alertas de contratos por vencer"
    try:
        ok, msg = _enviar_email_directo(asunto, cuerpo, destino)
        return (True, "Correo enviado correctamente.") if ok else (False, msg)
    except Exception as e:
        return False, f"Fallo al enviar correo: {e}"


# --- helper robusto para encontrar el correo del usuario actual ---
def _resolver_correo_destino(usuario: str) -> str | None:
    candidatos = [
        usuario,
        st.session_state.get("usuario"),
        st.session_state.get("user"),
        st.session_state.get("nombreUsuario"),
    ]
    for cand in candidatos:
        try:
            if cand:
                correo = _get_user_email(str(cand))
                if correo:
                    return correo
        except Exception:
            pass
    return None

# === diálogo SIEMPRE refrescando el snapshot al abrir ===
# ============== Diálogo de alertas: refresco automático y correo claro ==============
@st.dialog("Contratos por vencer")
def mostrarContratosPorVencer(usuario: str):
    try:
        dfv = None
        # 1) cálculo en caliente
        if callable(generarAlertasVencimiento_en_caliente):
            try:
                dfv = generarAlertasVencimiento_en_caliente()
            except Exception as e:
                st.caption(f"No fue posible actualizar automáticamente las alertas: {e}")

        # 2) rescates en cascada si llegara vacío
        if dfv is None or dfv.empty:
            try:
                dfv = cargarAlertas() if callable(cargarAlertas) else None
            except Exception:
                dfv = None
        if dfv is None or dfv.empty:
            try:
                pv = proximosVencimientos(365) if callable(proximosVencimientos) else None
                if pv is not None and not pv.empty:
                    dfv = pv.rename(columns={"id":"id_contrato"})[["id_contrato","cliente","fechaFin","dias_restantes"]]
                    dfv["umbral"] = pd.to_numeric(pv.get("diasNotificar", 30), errors="coerce").fillna(30).astype(int)
                    dfv["estado"] = "Por vencer"
            except Exception:
                pass

        # 3) encabezado de correo
        destino = _get_user_email(usuario) or ""
        st.text_input("Enviar a", value=destino, disabled=True)

        # 4) sin datos reales
        if dfv is None or dfv.empty:
            st.info("Sin alertas activas en este momento.")
            return

        dfv = _dedupe_por_id_ui(dfv)
        cols = [c for c in ["id_contrato","cliente","fechaFin","dias_restantes","umbral","estado"] if c in dfv.columns]

        if st.button("Enviar por correo", key="ct_alert_send"):
            ok, msg = _enviar_alertas_por_correo(usuario, destinatario=destino, df_alertas=dfv)
            st.success(msg) if ok else st.error(msg)
            try:
                dfv = _dedupe_por_id_ui(cargarAlertas())
            except Exception:
                pass

        st.dataframe(dfv[cols] if cols else dfv, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"No fue posible consultar los vencimientos: {e}")

# ========================= Interfaz principal =========================
def app(usuario: str):
    # fija el usuario para el diálogo y para resolver correo
    st.session_state["usuario"] = usuario

    st.subheader("Contratos")
    option = st.radio(
        label="Seleccione una función:",
        options=("Registrar Contrato", "Mostrar Contratos", "Registrar Acta", "Mostrar Actas"),
        key="contratos_menu_radio",
    )

    # ---------------- Registrar Contrato ----------------
    if option == "Registrar Contrato":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Gerente"]:
            st.warning("No tiene permiso para registrar contratos.")
            return

        st.subheader("Registrar Contrato")

        cliente      = st.text_input("Ingrese el nombre del cliente:", key="ct_cli")
        fechaInicio  = st.text_input("Ingrese la fecha de inicio (YYYY-MM-DD):", key="ct_fi")
        fechaFin     = st.text_input("Ingrese la fecha de finalización (YYYY-MM-DD):", key="ct_ff")
        condiciones  = st.text_area("Ingrese las condiciones:", key="ct_cond")

        # Selección de activos EXACTAMENTE como la primera versión
        activosEtiquetas = st.multiselect(
            "Activos a asociar",
            options=cargarActivosIdNombre(),   # "ID - Modelo (Cliente)"
            max_selections=5,
            key="ct_activos_sel",
        )

        diasNotificar = st.number_input(
            "Ingrese los días de anticipación para notificar:",
            min_value=1, step=1, value=30, key="ct_umbral"
        )

        if st.button("Registrar Contrato", key="ct_btn_guardar"):
            if not cliente.strip() or not fechaInicio.strip() or not fechaFin.strip() or not condiciones.strip():
                st.warning("Debe ingresar todos los datos.")
                return
            try:
                nuevo = agregarContratos(
                    cliente=cliente.strip(),
                    fechaInicio=fechaInicio.strip(),
                    fechaFin=fechaFin.strip(),
                    condiciones=condiciones.strip(),
                    activosAsociados=activosEtiquetas,  # se envían las etiquetas tal cual
                    diasNotificar=int(diasNotificar),
                )
                if _ALERTAS_OK and callable(generarAlertasVencimiento_en_caliente):
                    try:
                        generarAlertasVencimiento_en_caliente()
                    except Exception:
                        pass
                st.success(f"Contrato registrado con éxito (ID {nuevo.get('id','?')}).")
            except Exception as e:
                st.error(f"No se registró el contrato: {e}")

    # ---------------- Mostrar Contratos ----------------
    if option == "Mostrar Contratos":
        mostrarContratosPorVencer(usuario)

        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Gerente"]:
            st.warning("No tiene permiso para ver contratos.")
            return

        st.subheader("Mostrar Contratos")
        try:
            rows = cargarContratos()
            df = pd.DataFrame(rows)

            if not df.empty and "estado" not in df.columns and {"fechaInicio","fechaFin"} <= set(df.columns):
                df["estado"] = [_estado_calc(fi, ff) for fi, ff in zip(df["fechaInicio"], df["fechaFin"])]

            c1, c2 = st.columns(2)
            with c1:
                clientes = ["Todos"] + sorted(df.get("cliente", pd.Series(dtype=str)).astype(str).unique().tolist())
                f_cli = st.selectbox("Cliente", clientes, key="ct_list_cli")
            with c2:
                estados = ["Todos"] + sorted(df.get("estado", pd.Series(dtype=str)).astype(str).unique().tolist())
                f_est = st.selectbox("Estado", estados, key="ct_list_est")

            out = df.copy()
            if f_cli != "Todos":
                out = out[out["cliente"].astype(str) == f_cli]
            if f_est != "Todos":
                out = out[out["estado"].astype(str) == f_est]

            if colsContratos and isinstance(colsContratos, list):
                cols = [c for c in colsContratos if c in out.columns]
                if cols:
                    out = out[cols]
        
            st.dataframe(out, use_container_width=True, hide_index=True, key="ct_grid")
        except Exception as e:
            st.error(f"No fue posible cargar los contratos: {e}")

    # ---------------- Registrar Acta ----------------
    if option == "Registrar Acta":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para registrar actas.")
            return

        st.subheader("Registrar Acta")

        contratos_labels = _lista_contratos_id_cliente()
        contratoAsociado = st.selectbox(
            "Contrato a asociar",
            options=contratos_labels,
            key="acta_sel_contrato"
        )

        razon = st.text_area("Ingrese la razón del acta:", key="acta_razon")

        activosContrato = _activos_asociados_por_seleccion(contratoAsociado)
        activosActa = st.multiselect(
            "Activos a asociar",
            options=activosContrato,
            max_selections=5,
            key="acta_activos_sel"
        )

        st.caption("Firma digital")
        try:
            from streamlit_drawable_canvas import st_canvas
            _ = st_canvas(
                fill_color="rgba(255, 255, 255, 0)",
                stroke_width=2,
                stroke_color="black",
                background_color="#ffffff",
                height=150,
                width=400,
                drawing_mode="freedraw",
                key="acta_canvas",
            )
        except Exception:
            st.info("Módulo de firma no disponible en este entorno.")

        if st.button("Registrar Acta", key="acta_btn_guardar"):
            if not razon.strip():
                st.warning("Debe ingresar todos los datos.")
                return
            try:
                agregarActas(contratoAsociado, razon, activosActa)
                st.success("Acta registrada con éxito.")
            except Exception as e:
                st.error(f"No se registró el acta: {e}")

    # ---------------- Mostrar Actas ----------------
    if option == "Mostrar Actas":
        tipoUsuario = obtenerTipoUsuario(usuario)
        if tipoUsuario not in ["Administrador", "Técnico de mantenimiento"]:
            st.warning("No tiene permiso para ver actas.")
            return

        st.subheader("Mostrar Actas")
        try:
            rows = cargarActas()
            df = pd.DataFrame(rows)
            if colsActas and isinstance(colsActas, list):
                cols = [c for c in colsActas if c in df.columns]
                if cols:
                    df = df[cols]
            st.dataframe(df, use_container_width=True, hide_index=True, key="acta_grid")
        except Exception as e:
            st.error(f"No fue posible cargar las actas: {e}")