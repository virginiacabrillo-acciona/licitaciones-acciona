import streamlit as st
import pandas as pd
import json
import io
import requests
from datetime import date

# ─── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Análisis de Licitaciones · Acciona",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Estilos Acciona ───────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0C2340 !important;
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] hr {
    border-color: #354259;
}

/* Header principal */
.main-header {
    background: linear-gradient(135deg, #0C2340 0%, #1a3a5c 60%, #DA291C 100%);
    padding: 28px 36px;
    border-radius: 10px;
    margin-bottom: 28px;
    color: white;
}
.main-header h1 {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin: 0;
    color: white;
}
.main-header p {
    margin: 6px 0 0;
    opacity: 0.8;
    font-size: 1rem;
    color: white;
}

/* Tarjeta de paso activo */
.step-header {
    border-left: 5px solid #DA291C;
    padding: 12px 20px;
    background: #F1F2F3;
    border-radius: 0 8px 8px 0;
    margin-bottom: 24px;
}
.step-header h2 {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: #0C2340;
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.step-header p {
    margin: 4px 0 0;
    color: #546579;
    font-size: 0.9rem;
}

/* Info boxes */
.info-box {
    background: #F1F2F3;
    border: 1px solid #DADEE2;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 12px 0;
}
.info-box-red {
    background: #FFE3E3;
    border: 1px solid #FCB7B3;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 12px 0;
}

/* Botón primario */
.stButton > button {
    background-color: #DA291C !important;
    color: white !important;
    border: none !important;
    font-family: 'Barlow', sans-serif !important;
    font-weight: 600 !important;
    padding: 8px 24px !important;
    border-radius: 6px !important;
}
.stButton > button:hover {
    background-color: #961111 !important;
}

/* Tablas */
.dataframe {
    font-size: 0.85rem !important;
}

/* Métricas */
[data-testid="metric-container"] {
    background: #F1F2F3;
    border-radius: 8px;
    padding: 12px 16px;
    border: 1px solid #DADEE2;
}
[data-testid="stMetricValue"] {
    color: #0C2340 !important;
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #546579 !important;
}

/* Separador */
.divider {
    height: 2px;
    background: linear-gradient(to right, #DA291C, #0C2340);
    border: none;
    margin: 20px 0;
    border-radius: 2px;
}

/* Badge de estado */
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-ok { background: #d4edda; color: #155724; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-empty { background: #DADEE2; color: #546579; }
</style>
""", unsafe_allow_html=True)

# ─── Estado de sesión ──────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "proyecto": {},
        "partidas": pd.DataFrame(),
        "familias_config": {},
        "referencias": [],
        "ofertas": [],
        "precios_adoptados": {},
        "paso_activo": "1. Proyecto",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

PASOS = [
    "1. Proyecto",
    "2. Presupuesto",
    "3. Referencias",
    "4. Ofertas",
    "5. Análisis",
    "6. Exportar",
]

FAMILIAS_DEFAULT = [
    "Movimiento de tierras",
    "Hormigón estructural",
    "Tuberías y conducciones",
    "Equipos electromecánicos",
    "Obras de fábrica",
    "Prefabricados",
    "Instalaciones eléctricas",
    "Mano de obra especializada",
    "Otros",
]

# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏗️ LICITACIONES")
    st.markdown("**Acciona**")
    st.markdown("<hr>", unsafe_allow_html=True)

    paso = st.radio("Paso actual", PASOS, index=PASOS.index(st.session_state.paso_activo))
    st.session_state.paso_activo = paso

    st.markdown("<hr>", unsafe_allow_html=True)

    # Resumen del proyecto activo
    if st.session_state.proyecto:
        p = st.session_state.proyecto
        st.markdown(f"**📁 {p.get('nombre', '—')}**")
        st.markdown(f"📍 {p.get('pais', '—')} · {p.get('tipologia', '—')}")
        presupuesto = p.get('presupuesto', 0)
        if presupuesto:
            st.markdown(f"💰 {presupuesto:,.0f} €")
    else:
        st.markdown("*Sin proyecto cargado*")

    st.markdown("<hr>", unsafe_allow_html=True)

    # Guardar / Cargar sesión
    st.markdown("**💾 Guardar trabajo**")
    if st.button("Descargar sesión (.json)"):
        sesion = {
            "proyecto": st.session_state.proyecto,
            "familias_config": st.session_state.familias_config,
            "referencias": st.session_state.referencias,
            "ofertas": st.session_state.ofertas,
            "precios_adoptados": st.session_state.precios_adoptados,
            "partidas": st.session_state.partidas.to_dict() if not st.session_state.partidas.empty else {},
        }
        st.download_button(
            "📥 Descargar",
            data=json.dumps(sesion, ensure_ascii=False, indent=2, default=str),
            file_name=f"licitacion_{date.today()}.json",
            mime="application/json"
        )

    archivo_sesion = st.file_uploader("Cargar sesión guardada", type=["json"], key="cargar_sesion")
    if archivo_sesion:
        datos = json.load(archivo_sesion)
        st.session_state.proyecto = datos.get("proyecto", {})
        st.session_state.familias_config = datos.get("familias_config", {})
        st.session_state.referencias = datos.get("referencias", [])
        st.session_state.ofertas = datos.get("ofertas", [])
        st.session_state.precios_adoptados = datos.get("precios_adoptados", {})
        partidas_dict = datos.get("partidas", {})
        st.session_state.partidas = pd.DataFrame(partidas_dict) if partidas_dict else pd.DataFrame()
        st.success("Sesión cargada ✓")

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>⚙️ Sistema de Análisis de Licitaciones</h1>
    <p>Guía paso a paso para el estudio comparativo de costes · Acciona</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PASO 1 — PROYECTO
# ═══════════════════════════════════════════════════════════════════════════════
if paso == "1. Proyecto":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 1 · Identificar el proyecto</h2>
        <p>Datos básicos de la licitación que vamos a analizar</p>
    </div>
    """, unsafe_allow_html=True)

    p = st.session_state.proyecto

    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre del proyecto", value=p.get("nombre", ""), placeholder="EDAR El Marco — Cáceres")
        tipologia = st.selectbox("Tipología", ["EDAR", "IDAM / Desaladora", "ETAP", "Colectores y saneamiento", "Obra marítima", "Infraestructura hidráulica", "Otro"],
                                  index=["EDAR", "IDAM / Desaladora", "ETAP", "Colectores y saneamiento", "Obra marítima", "Infraestructura hidráulica", "Otro"].index(p.get("tipologia", "EDAR")) if p.get("tipologia") else 0)
        pais = st.text_input("País", value=p.get("pais", "España"))
        promotor = st.text_input("Promotor / Cliente", value=p.get("promotor", ""), placeholder="Ayuntamiento de Cáceres")

    with col2:
        fecha_limite = st.date_input("Fecha límite de presentación",
                                      value=date.fromisoformat(p["fecha_limite"]) if p.get("fecha_limite") else date.today())
        presupuesto_texto = st.text_input(
            "Presupuesto de licitación (€)",
            value=p.get("presupuesto_texto", ""),
            placeholder="37.166.355,32"
        )
        expediente = st.text_input("Nº expediente / referencia interna", value=p.get("expediente", ""))
        responsable = st.text_input("Técnico responsable del análisis", value=p.get("responsable", ""))

    notas = st.text_area("Notas sobre el proyecto", value=p.get("notas", ""), placeholder="Aspectos relevantes, condiciones particulares, plazos de ejecución...")

    st.markdown("<hr>", unsafe_allow_html=True)

    def parsear_importe(texto):
        try:
            limpio = texto.strip().replace("€", "").replace(" ", "").replace(".", "").replace(",", ".")
            return float(limpio)
        except:
            return 0.0

    if st.button("💾 Guardar datos del proyecto"):
        presupuesto_valor = parsear_importe(presupuesto_texto)
        st.session_state.proyecto = {
            "nombre": nombre,
            "tipologia": tipologia,
            "pais": pais,
            "promotor": promotor,
            "fecha_limite": str(fecha_limite),
            "presupuesto": presupuesto_valor,
            "presupuesto_texto": presupuesto_texto,
            "expediente": expediente,
            "responsable": responsable,
            "notas": notas,
        }
        st.success(f"✓ Proyecto '{nombre}' guardado correctamente")

    # Resumen si ya hay datos
    if st.session_state.proyecto:
        p = st.session_state.proyecto
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        pres = p.get("presupuesto", 0)
        col1.metric("Presupuesto", f"{pres:,.2f} €" if pres else "—")
        col2.metric("Tipología", p.get("tipologia", "—"))
        col3.metric("Fecha límite", p.get("fecha_limite", "—"))


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 2 — PRESUPUESTO
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "2. Presupuesto":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 2 · Cargar y seleccionar partidas</h2>
        <p>Sube el Excel del proyecto. La herramienta identifica las partidas más relevantes automáticamente.</p>
    </div>
    """, unsafe_allow_html=True)

    def parsear_numero_eu(valor):
        """Convierte número en formato europeo (1.234,56) a float."""
        try:
            if isinstance(valor, (int, float)):
                return float(valor)
            s = str(valor).strip().replace(" ", "").replace("€", "")
            # Formato europeo: punto como miles, coma como decimal
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            return float(s)
        except:
            return None

    def col_letra(i):
        """Devuelve letra de columna estilo Excel: A, B, ..., Z, AA, AB..."""
        result = ""
        n = i + 1
        while n > 0:
            n, r = divmod(n - 1, 26)
            result = chr(65 + r) + result
        return result

    archivo = st.file_uploader("📂 Subir Excel del presupuesto", type=["xlsx", "xls", "csv"])

    if archivo:
        try:
            if archivo.name.endswith(".csv"):
                df_raw = pd.read_csv(archivo)
            else:
                df_raw = pd.read_excel(archivo, header=None)
                # Detectar fila de cabeceras
                header_row = 0
                for i, row in df_raw.iterrows():
                    if len(row.dropna()) >= 3:
                        header_row = i
                        break
                df_raw = pd.read_excel(archivo, header=header_row)
                df_raw = df_raw.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)

            # Construir etiquetas columna: "A · Código", "B · Descripción", etc.
            etiquetas = {col: f"{col_letra(i)} · {col}" for i, col in enumerate(df_raw.columns)}
            etiquetas_lista = ["— no incluida —"] + [etiquetas[c] for c in df_raw.columns]
            etiqueta_a_col = {v: k for k, v in etiquetas.items()}

            st.success(f"✓ Archivo leído: {len(df_raw)} filas · {len(df_raw.columns)} columnas")

            st.markdown("**Vista previa (primeras 6 filas)**")
            df_preview = df_raw.head(6).copy()
            df_preview.columns = [f"{col_letra(i)} · {c}" for i, c in enumerate(df_raw.columns)]
            st.dataframe(df_preview, use_container_width=True)

            st.markdown("---")
            st.markdown("**Indica qué columna contiene cada dato**")
            st.caption("Las letras (A, B, C...) corresponden a las columnas del Excel tal como están en la vista previa.")

            c1, c2, c3 = st.columns(3)
            sel_desc = c1.selectbox("Descripción ✱", etiquetas_lista, key="sel_desc")
            sel_imp  = c2.selectbox("Importe total ✱", etiquetas_lista, key="sel_imp")
            sel_pu   = c3.selectbox("Precio unitario", etiquetas_lista, key="sel_pu")

            c4, c5 = st.columns(2)
            sel_med  = c4.selectbox("Medición / cantidad", etiquetas_lista, key="sel_med")
            sel_uni  = c5.selectbox("Unidad", etiquetas_lista, key="sel_uni")
            sel_cod  = st.selectbox("Código / referencia (opcional)", etiquetas_lista, key="sel_cod")

            if st.button("✅ Cargar partidas"):
                if sel_desc == "— no incluida —" or sel_imp == "— no incluida —":
                    st.error("⚠️ Descripción e Importe total son obligatorios.")
                else:
                    col_desc_real = etiqueta_a_col[sel_desc]
                    col_imp_real  = etiqueta_a_col[sel_imp]

                    cols_sel = {col_desc_real: "Descripción", col_imp_real: "Importe total"}
                    if sel_pu  != "— no incluida —": cols_sel[etiqueta_a_col[sel_pu]]  = "Precio unitario"
                    if sel_med != "— no incluida —": cols_sel[etiqueta_a_col[sel_med]] = "Medición"
                    if sel_uni != "— no incluida —": cols_sel[etiqueta_a_col[sel_uni]] = "Unidad"
                    if sel_cod != "— no incluida —": cols_sel[etiqueta_a_col[sel_cod]] = "Código"

                    partidas = df_raw[list(cols_sel.keys())].rename(columns=cols_sel).copy()
                    partidas["Importe total"] = partidas["Importe total"].apply(parsear_numero_eu)
                    if "Precio unitario" in partidas.columns:
                        partidas["Precio unitario"] = partidas["Precio unitario"].apply(parsear_numero_eu)
                    if "Medición" in partidas.columns:
                        partidas["Medición"] = partidas["Medición"].apply(parsear_numero_eu)

                    partidas = partidas.dropna(subset=["Importe total"])
                    partidas = partidas[partidas["Importe total"] > 0].reset_index(drop=True)
                    partidas["Familia"] = "Sin asignar"
                    partidas["Analizar"] = False

                    # Pre-seleccionar partidas hasta el 80% del importe acumulado
                    partidas_sorted = partidas.sort_values("Importe total", ascending=False).copy()
                    total_imp = partidas_sorted["Importe total"].sum()
                    acum = 0
                    indices_top = []
                    for idx in partidas_sorted.index:
                        acum += partidas_sorted.at[idx, "Importe total"]
                        indices_top.append(idx)
                        if acum / total_imp >= 0.80:
                            break
                    partidas.loc[indices_top, "Analizar"] = True

                    st.session_state.partidas = partidas
                    st.success(f"✓ {len(partidas)} partidas cargadas. {sum(partidas['Analizar'])} pre-seleccionadas (≥80% del importe).")
                    st.rerun()

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

    # ── Selección y categorización ─────────────────────────────────────────────
    if not st.session_state.partidas.empty:
        df_part = st.session_state.partidas.copy()
        total_imp = pd.to_numeric(df_part["Importe total"], errors="coerce").sum()
        n_sel = df_part["Analizar"].sum() if "Analizar" in df_part.columns else 0
        imp_sel = df_part[df_part.get("Analizar", False) == True]["Importe total"].sum() if "Analizar" in df_part.columns else 0

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total partidas", len(df_part))
        c2.metric("Seleccionadas para análisis", int(n_sel))
        c3.metric("% importe cubierto", f"{imp_sel/total_imp*100:.1f}%" if total_imp else "—")

        st.markdown("**Selecciona qué partidas analizar y categoriza con IA**")
        st.caption("Marca ✅ en la columna 'Analizar' las partidas que quieres incluir. Las más importantes ya están marcadas.")

        col_config = {
            "Analizar": st.column_config.CheckboxColumn("Analizar ✅", default=False),
            "Familia": st.column_config.SelectboxColumn("Familia", options=FAMILIAS_DEFAULT, required=False),
            "Importe total": st.column_config.NumberColumn("Importe total (€)", format="%.2f"),
        }
        if "Precio unitario" in df_part.columns:
            col_config["Precio unitario"] = st.column_config.NumberColumn("P. Unitario (€)", format="%.2f")

        edited = st.data_editor(
            df_part,
            column_config=col_config,
            use_container_width=True,
            num_rows="fixed",
            height=420,
        )
        st.session_state.partidas = edited

        col_a, col_b = st.columns(2)
        if col_a.button("🤖 Categorizar seleccionadas con IA"):
            api_key = st.secrets.get("GEMINI_API_KEY", "")
            if not api_key:
                st.error("⚠️ Falta la API key de Anthropic en los Secrets de Streamlit. Ver instrucciones abajo.")
            else:
                seleccionadas = edited[edited["Analizar"] == True].copy()
                if seleccionadas.empty:
                    st.warning("No hay partidas seleccionadas.")
                else:
                    familias_str = ", ".join(FAMILIAS_DEFAULT)
                    descripciones = seleccionadas["Descripción"].fillna("").tolist()
                    indices_orig = seleccionadas.index.tolist()

                    prompt = f"""Eres un experto en presupuestos de infraestructuras civiles e hidráulicas (depuradoras, desaladoras, conducciones, obras marítimas).

Asigna cada partida a UNA de estas familias exactamente como están escritas:
{familias_str}

Responde ÚNICAMENTE con JSON, sin texto adicional ni bloques de código:
[{{"indice": 0, "familia": "nombre exacto"}}, ...]

Partidas (índice: descripción):
""" + "\n".join([f"{i}: {d}" for i, d in enumerate(descripciones)])

                    try:
                        with st.spinner("Categorizando con IA..."):
                            resp = requests.post(
                                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                                headers={"Content-Type": "application/json"},
                                json={
                                    "contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4000}
                                }
                            )
                            data = resp.json()
                            if "error" in data:
                                st.error(f"Error API: {data['error']['message']}")
                            else:
                                texto = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                                if texto.startswith("```"):
                                    texto = texto.split("```")[1]
                                    if texto.startswith("json"):
                                        texto = texto[4:]
                                asignaciones = json.loads(texto.strip())
                                df_result = st.session_state.partidas.copy()
                                for item in asignaciones:
                                    idx_local = item["indice"]
                                    if idx_local < len(indices_orig):
                                        idx_real = indices_orig[idx_local]
                                        df_result.at[idx_real, "Familia"] = item["familia"]
                                st.session_state.partidas = df_result
                                st.success(f"✓ {len(asignaciones)} partidas categorizadas. Revisa y ajusta si es necesario.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error inesperado: {e}")

        if col_b.button("💾 Guardar selección y familias"):
            st.success("✓ Guardado")

        # Resumen por familia (solo seleccionadas)
        df_sel = st.session_state.partidas[st.session_state.partidas.get("Analizar", False) == True].copy() if "Analizar" in st.session_state.partidas.columns else pd.DataFrame()
        if not df_sel.empty and "Familia" in df_sel.columns:
            st.markdown("---")
            st.markdown("**Resumen por familia (partidas seleccionadas)**")
            df_sel["Importe total"] = pd.to_numeric(df_sel["Importe total"], errors="coerce")
            resumen_fam = df_sel.groupby("Familia")["Importe total"].sum().reset_index()
            resumen_fam.columns = ["Familia", "Importe (€)"]
            resumen_fam = resumen_fam.sort_values("Importe (€)", ascending=False)
            total_r = resumen_fam["Importe (€)"].sum()
            resumen_fam["% s/ total"] = (resumen_fam["Importe (€)"] / total_r * 100).round(1).astype(str) + "%"
            resumen_fam["Importe (€)"] = resumen_fam["Importe (€)"].map("{:,.0f}".format)
            st.dataframe(resumen_fam, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("""
        <div class="info-box">
        <strong>⚙️ Configurar la API key de Anthropic (necesario para la IA)</strong><br><br>
        1. Ve a <strong>share.streamlit.io</strong> → tu app → <strong>Settings → Secrets</strong><br>
        2. Añade esto:<br>
        <code>GEMINI_API_KEY = "AIza..."</code><br>
        3. Guarda y la app se reiniciará automáticamente.<br><br>
        Si no tienes API key, créala en <strong>aistudio.google.com</strong>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 3 — REFERENCIAS
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "3. Referencias":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 3 · Referencias de obras anteriores</h2>
        <p>Precios de otras licitaciones u obras de Acciona que sirven como base de comparación</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_referencia"):
        st.markdown("**Añadir nueva referencia**")
        c1, c2, c3 = st.columns(3)
        ref_nombre = c1.text_input("Nombre de la obra")
        ref_pais = c2.text_input("País")
        ref_año = c3.number_input("Año", min_value=2000, max_value=2030, value=2023)

        c4, c5 = st.columns(2)
        ref_familia = c4.selectbox("Familia de coste", FAMILIAS_DEFAULT)
        ref_unidad = c5.text_input("Unidad", placeholder="m³, ud, ml...")

        c6, c7 = st.columns(2)
        ref_precio = c6.number_input("Precio unitario (€)", min_value=0.0, step=1.0, format="%.2f")
        ref_descripcion = c7.text_input("Descripción de la partida", placeholder="Qué incluye exactamente")

        ref_notas = st.text_area("Notas / condiciones / exclusiones")

        submitted = st.form_submit_button("➕ Añadir referencia")
        if submitted and ref_nombre and ref_precio > 0:
            st.session_state.referencias.append({
                "Obra": ref_nombre,
                "País": ref_pais,
                "Año": ref_año,
                "Familia": ref_familia,
                "Unidad": ref_unidad,
                "Precio (€)": ref_precio,
                "Descripción": ref_descripcion,
                "Notas": ref_notas,
            })
            st.success(f"✓ Referencia de '{ref_nombre}' añadida")

    # Tabla de referencias
    if st.session_state.referencias:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(f"**Referencias cargadas: {len(st.session_state.referencias)}**")
        df_refs = pd.DataFrame(st.session_state.referencias)
        st.dataframe(df_refs, use_container_width=True, hide_index=True)

        if st.button("🗑️ Borrar todas las referencias"):
            st.session_state.referencias = []
            st.rerun()
    else:
        st.markdown("""
        <div class="info-box">
        Aún no hay referencias cargadas. Añade precios de obras anteriores que tengan partidas similares a este proyecto.
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 4 — OFERTAS
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "4. Ofertas":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 4 · Registrar ofertas de proveedores</h2>
        <p>Precios recibidos para este proyecto concreto, con detalle de qué incluye cada uno</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_oferta"):
        st.markdown("**Añadir nueva oferta**")
        c1, c2, c3 = st.columns(3)
        of_proveedor = c1.text_input("Proveedor / Subcontrata")
        of_fecha = c2.date_input("Fecha de oferta")
        of_validez = c3.text_input("Validez", placeholder="30 días, hasta 31/12/2025...")

        c4, c5 = st.columns(2)
        of_familia = c4.selectbox("Familia de coste", FAMILIAS_DEFAULT)
        of_unidad = c5.text_input("Unidad", placeholder="m³, ud, ml...")

        c6, c7 = st.columns(2)
        of_precio = c6.number_input("Precio unitario ofertado (€)", min_value=0.0, step=1.0, format="%.2f")
        of_tipo = c7.selectbox("Tipo de precio", ["Suministro + colocación", "Solo suministro", "Solo colocación", "Partida completa (S+C+MA)", "A confirmar"])

        of_incluye = st.text_area("¿Qué incluye?", placeholder="Suministro, transporte, colocación, grúa propia...")
        of_excluye = st.text_area("¿Qué NO incluye / exclusiones?", placeholder="Medios auxiliares, hormigonado, pruebas...")
        of_notas = st.text_area("Notas adicionales")

        submitted = st.form_submit_button("➕ Añadir oferta")
        if submitted and of_proveedor and of_precio > 0:
            st.session_state.ofertas.append({
                "Proveedor": of_proveedor,
                "Fecha": str(of_fecha),
                "Validez": of_validez,
                "Familia": of_familia,
                "Unidad": of_unidad,
                "Precio (€)": of_precio,
                "Tipo": of_tipo,
                "Incluye": of_incluye,
                "Excluye": of_excluye,
                "Notas": of_notas,
            })
            st.success(f"✓ Oferta de '{of_proveedor}' registrada")

    # Tabla de ofertas
    if st.session_state.ofertas:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(f"**Ofertas registradas: {len(st.session_state.ofertas)}**")

        familia_filtro = st.selectbox("Filtrar por familia", ["Todas"] + FAMILIAS_DEFAULT)
        df_of = pd.DataFrame(st.session_state.ofertas)
        if familia_filtro != "Todas":
            df_of = df_of[df_of["Familia"] == familia_filtro]

        st.dataframe(df_of, use_container_width=True, hide_index=True)

        if st.button("🗑️ Borrar todas las ofertas"):
            st.session_state.ofertas = []
            st.rerun()
    else:
        st.markdown("""
        <div class="info-box">
        Aún no hay ofertas registradas. Añade los precios recibidos de proveedores para este proyecto.
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 5 — ANÁLISIS
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "5. Análisis":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 5 · Análisis comparativo y precio adoptado</h2>
        <p>Compara referencias y ofertas por familia. Decide y justifica el precio adoptado.</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.ofertas and not st.session_state.referencias:
        st.markdown("""
        <div class="info-box-red">
        ⚠️ Aún no hay referencias ni ofertas cargadas. Completa los pasos 3 y 4 primero.
        </div>
        """, unsafe_allow_html=True)
    else:
        # Familias con datos
        familias_con_datos = set()
        for r in st.session_state.referencias:
            familias_con_datos.add(r["Familia"])
        for o in st.session_state.ofertas:
            familias_con_datos.add(o["Familia"])

        familia_sel = st.selectbox("Seleccionar familia a analizar", sorted(familias_con_datos))

        if familia_sel:
            st.markdown("<hr>", unsafe_allow_html=True)

            # Referencias de esta familia
            refs_familia = [r for r in st.session_state.referencias if r["Familia"] == familia_sel]
            ofertas_familia = [o for o in st.session_state.ofertas if o["Familia"] == familia_sel]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**📚 Referencias de obras anteriores**")
                if refs_familia:
                    df_r = pd.DataFrame(refs_familia)[["Obra", "Año", "Precio (€)", "Unidad", "Descripción"]]
                    st.dataframe(df_r, use_container_width=True, hide_index=True)
                else:
                    st.caption("Sin referencias para esta familia")

            with col2:
                st.markdown("**📋 Ofertas recibidas**")
                if ofertas_familia:
                    df_o = pd.DataFrame(ofertas_familia)[["Proveedor", "Precio (€)", "Unidad", "Tipo", "Excluye"]]
                    st.dataframe(df_o, use_container_width=True, hide_index=True)
                else:
                    st.caption("Sin ofertas para esta familia")

            # Estadísticos
            todos_precios = [r["Precio (€)"] for r in refs_familia] + [o["Precio (€)"] for o in ofertas_familia]
            if todos_precios:
                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown("**📊 Estadísticos de precios**")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Mínimo", f"{min(todos_precios):,.2f} €")
                c2.metric("Mediana", f"{sorted(todos_precios)[len(todos_precios)//2]:,.2f} €")
                c3.metric("Máximo", f"{max(todos_precios):,.2f} €")
                c4.metric("Nº fuentes", len(todos_precios))

            # Precio adoptado
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("**✅ Precio adoptado**")

            precio_prev = st.session_state.precios_adoptados.get(familia_sel, {})

            c1, c2 = st.columns(2)
            precio_adoptado = c1.number_input(
                "Precio adoptado (€/unidad)",
                value=float(precio_prev.get("precio", 0)),
                step=0.5,
                format="%.2f",
                key=f"precio_{familia_sel}"
            )
            medicion = c2.number_input(
                "Medición del proyecto (unidades)",
                value=float(precio_prev.get("medicion", 0)),
                step=1.0,
                key=f"med_{familia_sel}"
            )

            justificacion = st.text_area(
                "Justificación del precio adoptado",
                value=precio_prev.get("justificacion", ""),
                placeholder="Por qué se adopta este precio, qué incluye, qué se ha estimado...",
                key=f"just_{familia_sel}"
            )

            if precio_adoptado > 0 and medicion > 0:
                total_familia = precio_adoptado * medicion
                st.metric("💰 Importe total de la familia", f"{total_familia:,.0f} €")

            if st.button("💾 Guardar precio adoptado"):
                st.session_state.precios_adoptados[familia_sel] = {
                    "precio": precio_adoptado,
                    "medicion": medicion,
                    "justificacion": justificacion,
                    "total": precio_adoptado * medicion,
                }
                st.success(f"✓ Precio adoptado para '{familia_sel}' guardado")


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 6 — EXPORTAR
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "6. Exportar":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 6 · Exportar resultado</h2>
        <p>Excel estructurado con el análisis completo, listo para la oferta</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.precios_adoptados:
        st.markdown("""
        <div class="info-box-red">
        ⚠️ Aún no hay precios adoptados. Completa el análisis en el paso 5 antes de exportar.
        </div>
        """, unsafe_allow_html=True)
    else:
        p = st.session_state.proyecto

        st.markdown("**Resumen del análisis**")

        # Tabla resumen
        resumen_data = []
        for familia, datos in st.session_state.precios_adoptados.items():
            resumen_data.append({
                "Familia": familia,
                "Precio adoptado (€/ud)": datos["precio"],
                "Medición": datos["medicion"],
                "Importe total (€)": datos["total"],
                "Justificación": datos["justificacion"],
            })

        df_resumen = pd.DataFrame(resumen_data)
        total_analizado = df_resumen["Importe total (€)"].sum()
        presupuesto_proyecto = p.get("presupuesto", 0)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total analizado", f"{total_analizado:,.0f} €")
        col2.metric("Presupuesto proyecto", f"{presupuesto_proyecto:,.0f} €" if presupuesto_proyecto else "—")
        if presupuesto_proyecto:
            pct = total_analizado / presupuesto_proyecto * 100
            col3.metric("% analizado", f"{pct:.1f}%")

        st.dataframe(df_resumen, use_container_width=True, hide_index=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        if st.button("📥 Generar Excel de análisis"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:

                # Pestaña resumen
                df_resumen.to_excel(writer, sheet_name="Resumen", index=False)

                # Pestaña por familia
                for familia, datos in st.session_state.precios_adoptados.items():
                    nombre_hoja = familia[:30]
                    rows = []

                    for r in st.session_state.referencias:
                        if r["Familia"] == familia:
                            rows.append({
                                "Fuente": r["Obra"],
                                "Tipo": "Referencia obra anterior",
                                "Precio (€/ud)": r["Precio (€)"],
                                "Unidad": r["Unidad"],
                                "Descripción / Qué incluye": r["Descripción"],
                                "Notas / Exclusiones": r["Notas"],
                                "Año": r["Año"],
                            })
                    for o in st.session_state.ofertas:
                        if o["Familia"] == familia:
                            rows.append({
                                "Fuente": o["Proveedor"],
                                "Tipo": f"Oferta ({o['Tipo']})",
                                "Precio (€/ud)": o["Precio (€)"],
                                "Unidad": o["Unidad"],
                                "Descripción / Qué incluye": o["Incluye"],
                                "Notas / Exclusiones": o["Excluye"],
                                "Año": o["Fecha"],
                            })

                    if rows:
                        df_fam = pd.DataFrame(rows)
                        precios = df_fam["Precio (€/ud)"].tolist()
                        precios_sorted = sorted(precios)
                        estadisticos = pd.DataFrame([{
                            "Fuente": "── ESTADÍSTICOS ──",
                            "Tipo": "",
                            "Precio (€/ud)": "",
                            "Unidad": "",
                            "Descripción / Qué incluye": f"Mín: {min(precios):,.2f} | Med: {precios_sorted[len(precios_sorted)//2]:,.2f} | Máx: {max(precios):,.2f}",
                            "Notas / Exclusiones": "",
                            "Año": "",
                        }, {
                            "Fuente": "✅ PRECIO ADOPTADO",
                            "Tipo": "",
                            "Precio (€/ud)": datos["precio"],
                            "Unidad": "",
                            "Descripción / Qué incluye": datos["justificacion"],
                            "Notas / Exclusiones": f"Medición: {datos['medicion']} | Total: {datos['total']:,.0f} €",
                            "Año": "",
                        }])
                        df_final = pd.concat([df_fam, estadisticos], ignore_index=True)
                        df_final.to_excel(writer, sheet_name=nombre_hoja, index=False)

                # Pestaña de partidas si existen
                if not st.session_state.partidas.empty:
                    st.session_state.partidas.to_excel(writer, sheet_name="Partidas proyecto", index=False)

            output.seek(0)
            nombre_archivo = f"Analisis_{p.get('nombre', 'licitacion').replace(' ', '_')}_{date.today()}.xlsx"
            st.download_button(
                label="📥 Descargar Excel",
                data=output,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("✓ Excel generado. Haz clic arriba para descargarlo.")


