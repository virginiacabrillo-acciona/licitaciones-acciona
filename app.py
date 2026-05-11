import streamlit as st
import pandas as pd
import json
import io
import requests
from datetime import date

# ─── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Análisis de Precios Unitarios en Licitaciones · Acciona",
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

# ─── Taxonomía de familias ────────────────────────────────────────────────────
TAXONOMIA = [
    # CIVIL
    {"codigo": "CIV-01", "familia": "CIV-01 · Preliminares, implantación y trabajos previos", "disciplina": "Civil"},
    {"codigo": "CIV-02", "familia": "CIV-02 · Demoliciones, desmontajes y levantados", "disciplina": "Civil"},
    {"codigo": "CIV-03", "familia": "CIV-03 · Movimiento de tierras", "disciplina": "Civil"},
    {"codigo": "CIV-04", "familia": "CIV-04 · Contenciones, entibaciones y achiques", "disciplina": "Civil"},
    {"codigo": "CIV-05", "familia": "CIV-05 · Tratamiento del terreno y cimentaciones especiales", "disciplina": "Civil"},
    {"codigo": "CIV-06", "familia": "CIV-06 · Cimentaciones y estructuras de hormigón armado", "disciplina": "Civil"},
    {"codigo": "CIV-07", "familia": "CIV-07 · Encofrados, ferralla y hormigones", "disciplina": "Civil"},
    {"codigo": "CIV-08", "familia": "CIV-08 · Estructuras metálicas", "disciplina": "Civil"},
    {"codigo": "CIV-09", "familia": "CIV-09 · Cerrajería, tramex, plataformas y vallados", "disciplina": "Civil"},
    {"codigo": "CIV-10", "familia": "CIV-10 · Redes enterradas civiles y drenaje", "disciplina": "Civil"},
    {"codigo": "CIV-11", "familia": "CIV-11 · Obra hidráulica civil", "disciplina": "Civil"},
    {"codigo": "CIV-12", "familia": "CIV-12 · Obra marítima, captación y emisarios", "disciplina": "Civil"},
    {"codigo": "CIV-13", "familia": "CIV-13 · Impermeabilización, revestimientos y protección de hormigón", "disciplina": "Civil"},
    {"codigo": "CIV-14", "familia": "CIV-14 · Arquitectura y acabados", "disciplina": "Civil"},
    {"codigo": "CIV-15", "familia": "CIV-15 · Urbanización y paisajismo", "disciplina": "Civil"},
    {"codigo": "CIV-16", "familia": "CIV-16 · Servicios afectados y desvíos", "disciplina": "Civil"},
    {"codigo": "CIV-17", "familia": "CIV-17 · Gestión de residuos", "disciplina": "Civil"},
    # MECÁNICO
    {"codigo": "MEC-01", "familia": "MEC-01 · Equipos mecánicos de proceso", "disciplina": "Mecánico"},
    {"codigo": "MEC-02", "familia": "MEC-02 · Equipos específicos IDAM / OI / desalación", "disciplina": "Mecánico"},
    {"codigo": "MEC-03", "familia": "MEC-03 · Tuberías de proceso", "disciplina": "Mecánico"},
    {"codigo": "MEC-04", "familia": "MEC-04 · Válvulas, actuadores y compuertas", "disciplina": "Mecánico"},
    {"codigo": "MEC-05", "familia": "MEC-05 · Dosificación química y reactivos", "disciplina": "Mecánico"},
    {"codigo": "MEC-06", "familia": "MEC-06 · Elevación y manutención", "disciplina": "Mecánico"},
    # ELÉCTRICO
    {"codigo": "ELE-01", "familia": "ELE-01 · Alta y media tensión", "disciplina": "Eléctrico"},
    {"codigo": "ELE-02", "familia": "ELE-02 · Centros de transformación", "disciplina": "Eléctrico"},
    {"codigo": "ELE-03", "familia": "ELE-03 · Baja tensión, CCM y cuadros", "disciplina": "Eléctrico"},
    {"codigo": "ELE-04", "familia": "ELE-04 · Variadores, arrancadores y compensación", "disciplina": "Eléctrico"},
    {"codigo": "ELE-05", "familia": "ELE-05 · Cableado, bandejas y canalizaciones", "disciplina": "Eléctrico"},
    {"codigo": "ELE-06", "familia": "ELE-06 · Puesta a tierra y protección contra el rayo", "disciplina": "Eléctrico"},
    {"codigo": "ELE-07", "familia": "ELE-07 · Alumbrado", "disciplina": "Eléctrico"},
    {"codigo": "ELE-08", "familia": "ELE-08 · Grupos electrógenos, SAI y baterías", "disciplina": "Eléctrico"},
    # I&C
    {"codigo": "ICA-01", "familia": "ICA-01 · Instrumentación de campo", "disciplina": "I&C"},
    {"codigo": "ICA-02", "familia": "ICA-02 · Analizadores de proceso", "disciplina": "I&C"},
    {"codigo": "ICA-03", "familia": "ICA-03 · PLC, RTU y control local", "disciplina": "I&C"},
    {"codigo": "ICA-04", "familia": "ICA-04 · SCADA y supervisión", "disciplina": "I&C"},
    {"codigo": "ICA-05", "familia": "ICA-05 · Telecomunicaciones y red OT", "disciplina": "I&C"},
    {"codigo": "ICA-06", "familia": "ICA-06 · CCTV, control de accesos y seguridad electrónica", "disciplina": "I&C"},
    # BUILDING SERVICES / MEP
    {"codigo": "MEP-01", "familia": "MEP-01 · HVAC", "disciplina": "Building services"},
    {"codigo": "MEP-02", "familia": "MEP-02 · Protección contra incendios", "disciplina": "Building services"},
    {"codigo": "MEP-03", "familia": "MEP-03 · Fontanería, saneamiento interior y servicios de edificio", "disciplina": "Building services"},
    # TRANSVERSALES
    {"codigo": "TRV-01", "familia": "TRV-01 · Ingeniería, BIM y documentación técnica", "disciplina": "Transversal"},
    {"codigo": "TRV-02", "familia": "TRV-02 · Permisos, legalizaciones y tasas", "disciplina": "Transversal"},
    {"codigo": "TRV-03", "familia": "TRV-03 · Seguridad y salud", "disciplina": "Transversal"},
    {"codigo": "TRV-04", "familia": "TRV-04 · Control de calidad y laboratorio", "disciplina": "Transversal"},
    {"codigo": "TRV-05", "familia": "TRV-05 · Gestión medioambiental", "disciplina": "Transversal"},
    {"codigo": "TRV-06", "familia": "TRV-06 · Pruebas, commissioning y garantías", "disciplina": "Transversal"},
    {"codigo": "TRV-07", "familia": "TRV-07 · Explotación provisional / mantenimiento durante obras", "disciplina": "Transversal"},
    {"codigo": "TRV-08", "familia": "TRV-08 · Indirectos de obra y medios generales", "disciplina": "Transversal"},
    {"codigo": "TRV-99", "familia": "TRV-99 · Varios / pendiente de clasificar", "disciplina": "Transversal"},
]

DISCIPLINAS = ["Todas", "Civil", "Mecánico", "Eléctrico", "I&C", "Building services", "Transversal"]

def familias_por_disciplina(disciplina="Todas"):
    if disciplina == "Todas":
        return [f["familia"] for f in TAXONOMIA]
    return [f["familia"] for f in TAXONOMIA if f["disciplina"] == disciplina]

FAMILIAS_DEFAULT = [f["familia"] for f in TAXONOMIA]
TAXONOMIA_TEXTO = "\n".join([f"{t['codigo']} | {t['familia']} | {t['disciplina']}" for t in TAXONOMIA])


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

                    # ── Filtrar filas de resumen / capítulo ──────────────────
                    n_antes = len(partidas)
                    PALABRAS_RESUMEN = [
                        "capítulo", "capitulo", "cap.", "cap ", "total", "resumen",
                        "suma", "subtotal", "sub-total", "apartado", "título", "titulo"
                    ]
                    def es_resumen(row):
                        desc = str(row.get("Descripción", "")).strip().lower()
                        # Si empieza por palabra de resumen → probable capítulo
                        if any(desc.startswith(p) for p in PALABRAS_RESUMEN):
                            return True
                        # Si tiene precio unitario mapeado y es nulo o cero → resumen
                        if "Precio unitario" in row and (pd.isna(row["Precio unitario"]) or row["Precio unitario"] == 0):
                            return True
                        return False

                    mask_resumen = partidas.apply(es_resumen, axis=1)
                    partidas_filtradas = partidas[~mask_resumen].reset_index(drop=True)
                    n_filtradas = n_antes - len(partidas_filtradas)

                    partidas_filtradas["Familia"] = "Sin asignar"
                    partidas_filtradas["Analizar"] = False

                    # Pre-seleccionar partidas hasta el 80% del importe acumulado
                    partidas_sorted = partidas_filtradas.sort_values("Importe total", ascending=False).copy()
                    total_imp = partidas_sorted["Importe total"].sum()
                    acum = 0
                    indices_top = []
                    for idx in partidas_sorted.index:
                        acum += partidas_sorted.at[idx, "Importe total"]
                        indices_top.append(idx)
                        if acum / total_imp >= 0.80:
                            break
                    partidas_filtradas.loc[indices_top, "Analizar"] = True

                    # Guardar también las filas de resumen por separado por si acaso
                    st.session_state.partidas = partidas_filtradas
                    st.session_state.partidas_resumen = partidas[mask_resumen].reset_index(drop=True)

                    msg = f"✓ {len(partidas_filtradas)} partidas unitarias cargadas"
                    if n_filtradas > 0:
                        msg += f" · {n_filtradas} filas de capítulo/resumen descartadas"
                    msg += f" · {sum(partidas_filtradas['Analizar'])} pre-seleccionadas (≥80% del importe)"
                    st.success(msg)
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
        st.caption("Marca ✅ en 'Analizar'. Filtra por disciplina para ver solo las familias relevantes.")

        filtro_disc = st.selectbox("Filtrar familias por disciplina", DISCIPLINAS, key="filtro_disc_tabla")
        familias_visibles = familias_por_disciplina(filtro_disc)

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
            api_key = st.secrets.get("OPENAI_API_KEY", "")
            if not api_key:
                st.error("⚠️ Falta la API key de OpenAI en los Secrets de Streamlit. Añade: OPENAI_API_KEY = \"sk-...\"")
            else:
                seleccionadas = edited[edited["Analizar"] == True].copy()
                if seleccionadas.empty:
                    st.warning("No hay partidas seleccionadas.")
                else:
                    descripciones = seleccionadas["Descripción"].fillna("").tolist()
                    indices_orig = seleccionadas.index.tolist()

                    prompt = f"""Eres un experto en presupuestos de construcción de infraestructuras hidráulicas (EDAR, IDAM, ETAP, conducciones, obras marítimas).

Asigna cada partida a UNA de estas familias. Usa exactamente el texto de la columna "Familia" tal como aparece:

{TAXONOMIA_TEXTO}

Responde ÚNICAMENTE con JSON sin texto adicional ni bloques de código:
[{{"indice": 0, "familia": "CIV-03 · Movimiento de tierras"}}, ...]

Partidas (índice: descripción):
""" + "\n".join([f"{i}: {d}" for i, d in enumerate(descripciones)])

                    try:
                        with st.spinner("Categorizando con IA..."):
                            resp = requests.post(
                                "https://api.openai.com/v1/chat/completions",
                                headers={
                                    "Content-Type": "application/json",
                                    "Authorization": f"Bearer {api_key}"
                                },
                                json={
                                    "model": "gpt-4o-mini",
                                    "temperature": 0.1,
                                    "max_tokens": 4000,
                                    "messages": [{"role": "user", "content": prompt}]
                                }
                            )
                            data = resp.json()
                            if "error" in data:
                                st.error(f"Error API: {data['error']['message']}")
                            else:
                                texto = data["choices"][0]["message"]["content"].strip()
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

        if not st.secrets.get("GEMINI_API_KEY", ""):
            st.markdown("---")
            st.markdown("""
            <div class="info-box">
            <strong>⚙️ Configura la API key de Gemini para activar la IA</strong><br><br>
            1. Ve a <strong>share.streamlit.io</strong> → tu app → <strong>Settings → Secrets</strong><br>
            2. Añade: <code>GEMINI_API_KEY = "AIza..."</code><br>
            3. Guarda — la app se reinicia sola.<br><br>
            Obtén tu clave gratuita en <strong>aistudio.google.com</strong>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 3 — REFERENCIAS
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "3. Referencias":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 3 · Referencias de obras anteriores</h2>
        <p>Sube Excels de obras propias. La IA cruza las partidas con la taxonomía y extrae precios de referencia.</p>
    </div>
    """, unsafe_allow_html=True)

    def leer_excel_generico(archivo):
        """Lee un Excel detectando automáticamente la fila de cabecera."""
        try:
            if archivo.name.endswith(".csv"):
                return pd.read_csv(archivo), None
            df_raw = pd.read_excel(archivo, header=None)
            header_row = 0
            for i, row in df_raw.iterrows():
                if len(row.dropna()) >= 3:
                    header_row = i
                    break
            df = pd.read_excel(archivo, header=header_row)
            df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)
            return df, None
        except Exception as e:
            return None, str(e)

    def col_letra(i):
        result, n = "", i + 1
        while n > 0:
            n, r = divmod(n - 1, 26)
            result = chr(65 + r) + result
        return result

    def parsear_num(valor):
        try:
            if isinstance(valor, (int, float)):
                return float(valor)
            s = str(valor).strip().replace(" ", "").replace("€", "").replace("$", "")
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            return float(s)
        except:
            return None

    def call_openai(prompt, api_key, max_tokens=4000):
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={"model": "gpt-4o-mini", "temperature": 0.1, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]}
        )
        data = resp.json()
        if "error" in data:
            raise Exception(data["error"]["message"])
        texto = data["choices"][0]["message"]["content"].strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return texto.strip()

    # ── Metadatos de la obra de referencia ────────────────────────────────────
    st.markdown("**Datos de la obra de referencia**")
    c1, c2, c3, c4 = st.columns(4)
    ref_nombre = c1.text_input("Nombre de la obra", key="ref_nombre", placeholder="EDAR El Marco, Cáceres")
    ref_pais   = c2.text_input("País", key="ref_pais", value="España")
    ref_anio   = c3.number_input("Año", min_value=2000, max_value=2030, value=2022, key="ref_anio")
    ref_moneda = c4.text_input("Moneda", key="ref_moneda", value="EUR", placeholder="EUR, USD, MAD, SAR...")

    # ── Tasas de actualización ───────────────────────────────────────────────
    with st.expander("⚙️ Tasas de actualización de precios", expanded=False):
        st.caption(f"Se actualizan los precios al año en curso ({date.today().year}). Prioridad: columna Excel > tasa por familia > tasa general.")

        tasa_general = st.number_input("Tasa general anual (%)", min_value=0.0, max_value=30.0,
                                        value=st.session_state.get("tasa_general", 3.0), step=0.5,
                                        key="tasa_general_inp", format="%.1f")
        st.session_state["tasa_general"] = tasa_general

        st.markdown("**Tasas por disciplina** (dejar en 0 para usar la tasa general)")
        tasas_familia = st.session_state.get("tasas_familia", {})
        disc_cols = st.columns(3)
        disciplinas_lista = ["Civil", "Mecánico", "Eléctrico", "I&C", "Building services", "Transversal"]
        for i, disc in enumerate(disciplinas_lista):
            val = tasas_familia.get(disc, 0.0)
            nuevo = disc_cols[i % 3].number_input(
                disc, min_value=0.0, max_value=30.0, value=val, step=0.5,
                key=f"tasa_{disc}", format="%.1f"
            )
            tasas_familia[disc] = nuevo
        st.session_state["tasas_familia"] = tasas_familia

    def calcular_precio_actualizado(precio_orig, año_ref, familia, col_tasa=None):
        """Aplica tasa compuesta. Prioridad: columna Excel > familia > general."""
        año_actual = date.today().year
        años = max(0, año_actual - int(año_ref))
        if años == 0:
            return precio_orig

        # Determinar tasa a aplicar
        if col_tasa is not None and col_tasa > 0:
            tasa = col_tasa
        else:
            # Buscar disciplina de la familia
            disc_fam = next((t["disciplina"] for t in TAXONOMIA if t["familia"] == familia), None)
            tasa_disc = st.session_state.get("tasas_familia", {}).get(disc_fam, 0.0) if disc_fam else 0.0
            tasa = tasa_disc if tasa_disc > 0 else st.session_state.get("tasa_general", 3.0)

        return round(precio_orig * ((1 + tasa / 100) ** años), 2)

    archivo_ref = st.file_uploader("📂 Subir Excel de la obra de referencia", type=["xlsx", "xls", "csv"], key="up_ref")

    if archivo_ref:
        df_ref, err = leer_excel_generico(archivo_ref)
        if err:
            st.error(f"Error al leer el archivo: {err}")
        else:
            etiquetas = {col: f"{col_letra(i)} · {col}" for i, col in enumerate(df_ref.columns)}
            etiquetas_lista = ["— no incluida —"] + list(etiquetas.values())
            etiqueta_a_col = {v: k for k, v in etiquetas.items()}

            st.success(f"✓ {len(df_ref)} filas · {len(df_ref.columns)} columnas")
            df_prev = df_ref.head(6).copy()
            df_prev.columns = [f"{col_letra(i)} · {c}" for i, c in enumerate(df_ref.columns)]
            st.dataframe(df_prev, use_container_width=True)

            st.markdown("**Indica las columnas**")
            c1, c2, c3, c4, c5 = st.columns(5)
            s_desc  = c1.selectbox("Descripción ✱", etiquetas_lista, key="rs_desc")
            s_pu    = c2.selectbox("Precio unitario ✱", etiquetas_lista, key="rs_pu")
            s_uni   = c3.selectbox("Unidad", etiquetas_lista, key="rs_uni")
            s_imp   = c4.selectbox("Importe total", etiquetas_lista, key="rs_imp")
            s_tasa  = c5.selectbox("Col. tasa revisión % (si existe)", etiquetas_lista, key="rs_tasa")

            if st.button("✅ Cargar y categorizar con IA", key="btn_ref"):
                api_key = st.secrets.get("OPENAI_API_KEY", "")
                if not ref_nombre:
                    st.error("Indica el nombre de la obra antes de continuar.")
                elif s_desc == "— no incluida —" or s_pu == "— no incluida —":
                    st.error("Descripción y Precio unitario son obligatorios.")
                elif not api_key:
                    st.error("⚠️ Falta OPENAI_API_KEY en Secrets.")
                else:
                    cols_map = {etiqueta_a_col[s_desc]: "Descripción", etiqueta_a_col[s_pu]: "Precio unitario"}
                    if s_uni  != "— no incluida —": cols_map[etiqueta_a_col[s_uni]]  = "Unidad"
                    if s_imp  != "— no incluida —": cols_map[etiqueta_a_col[s_imp]]  = "Importe total"
                    if s_tasa != "— no incluida —": cols_map[etiqueta_a_col[s_tasa]] = "Tasa revisión %"

                    df_work = df_ref[list(cols_map.keys())].rename(columns=cols_map).copy()
                    df_work["Precio unitario"] = df_work["Precio unitario"].apply(parsear_num)
                    if "Importe total" in df_work.columns:
                        df_work["Importe total"] = df_work["Importe total"].apply(parsear_num)
                    if "Tasa revisión %" in df_work.columns:
                        df_work["Tasa revisión %"] = df_work["Tasa revisión %"].apply(parsear_num)
                    df_work = df_work.dropna(subset=["Precio unitario"])
                    df_work = df_work[df_work["Precio unitario"] > 0].reset_index(drop=True)

                    PALABRAS_RESUMEN = ["capítulo","capitulo","cap.","cap ","total","resumen","suma","subtotal","apartado"]
                    mask = df_work["Descripción"].apply(lambda d: any(str(d).lower().strip().startswith(p) for p in PALABRAS_RESUMEN))
                    df_work = df_work[~mask].reset_index(drop=True)

                    with st.spinner("Categorizando con IA..."):
                        descs = df_work["Descripción"].fillna("").tolist()
                        prompt = f"""Eres experto en presupuestos de infraestructuras hidráulicas.
Asigna cada partida a UNA familia de esta lista (usa el texto exacto):
{TAXONOMIA_TEXTO}

Responde SOLO con JSON sin texto adicional:
[{{"indice": 0, "familia": "CIV-03 · Movimiento de tierras"}}, ...]

Partidas:
""" + "\n".join([f"{i}: {d}" for i, d in enumerate(descs)])

                        try:
                            texto = call_openai(prompt, api_key)
                            asignaciones = json.loads(texto)
                            df_work["Familia"] = "TRV-99 · Varios / pendiente de clasificar"
                            for item in asignaciones:
                                if item["indice"] < len(df_work):
                                    df_work.at[item["indice"], "Familia"] = item["familia"]

                            # Calcular precio actualizado
                            año_actual = date.today().year
                            precios_act = []
                            tasas_aplicadas = []
                            for _, row in df_work.iterrows():
                                col_tasa_val = row.get("Tasa revisión %", None)
                                if pd.isna(col_tasa_val): col_tasa_val = None
                                p_act = calcular_precio_actualizado(
                                    row["Precio unitario"], ref_anio,
                                    row.get("Familia", ""), col_tasa_val
                                )
                                precios_act.append(p_act)
                                # Registrar tasa efectiva aplicada
                                if col_tasa_val and col_tasa_val > 0:
                                    tasas_aplicadas.append(f"{col_tasa_val}% (Excel)")
                                else:
                                    disc_f = next((t["disciplina"] for t in TAXONOMIA if t["familia"] == row.get("Familia","")), None)
                                    td = st.session_state.get("tasas_familia", {}).get(disc_f, 0.0) if disc_f else 0.0
                                    tef = td if td > 0 else st.session_state.get("tasa_general", 3.0)
                                    tasas_aplicadas.append(f"{tef}%")

                            df_work["P. unitario original"] = df_work["Precio unitario"]
                            df_work["Precio unitario"] = precios_act
                            df_work["Tasa aplicada"] = tasas_aplicadas
                            df_work["Año original"] = ref_anio
                            df_work["Año actualizado"] = año_actual

                            # Añadir metadatos
                            df_work["Obra"] = ref_nombre
                            df_work["País"] = ref_pais
                            df_work["Año"] = ref_anio
                            df_work["Moneda"] = ref_moneda
                            df_work["Validado"] = False

                            st.session_state["df_ref_preview"] = df_work
                            st.success(f"✓ {len(df_work)} partidas categorizadas. Revisa y valida.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error IA: {e}")

    # ── Revisión y guardado ───────────────────────────────────────────────────
    if "df_ref_preview" in st.session_state and not st.session_state["df_ref_preview"].empty:
        st.markdown("---")
        st.markdown("**Revisa la categorización antes de guardar**")

        df_prev_ref = st.session_state["df_ref_preview"]
        año_actual = date.today().year
        if "P. unitario original" in df_prev_ref.columns:
            st.info(f"💡 Precios actualizados de {df_prev_ref['Año original'].iloc[0]} → {año_actual} con tasa compuesta. Columna 'Precio unitario' = precio actualizado.")

        col_config_ref = {
            "Familia": st.column_config.SelectboxColumn("Familia", options=FAMILIAS_DEFAULT),
            "P. unitario original": st.column_config.NumberColumn("P. original (€)", format="%.2f"),
            "Precio unitario": st.column_config.NumberColumn(f"P. actualizado {año_actual} (€)", format="%.2f"),
            "Tasa aplicada": st.column_config.TextColumn("Tasa aplicada"),
            "Validado": st.column_config.CheckboxColumn("✅ OK"),
        }
        if "Importe total" in df_prev_ref.columns:
            col_config_ref["Importe total"] = st.column_config.NumberColumn("Importe total (€)", format="%.2f")

        edited_ref = st.data_editor(
            df_prev_ref,
            column_config=col_config_ref,
            use_container_width=True, num_rows="fixed", height=380,
        )
        st.session_state["df_ref_preview"] = edited_ref

        if st.button("💾 Añadir al historial de referencias"):
            nuevas = edited_ref.to_dict("records")
            st.session_state.referencias.extend(nuevas)
            del st.session_state["df_ref_preview"]
            st.success(f"✓ {len(nuevas)} precios de referencia añadidos al historial.")
            st.rerun()

    # ── Historial de referencias cargadas ─────────────────────────────────────
    if st.session_state.referencias:
        st.markdown("---")
        df_hist = pd.DataFrame(st.session_state.referencias)
        obras = df_hist["Obra"].unique().tolist() if "Obra" in df_hist.columns else []
        st.markdown(f"**Historial: {len(df_hist)} precios de {len(obras)} obra(s)**")

        filtro_obra = st.selectbox("Filtrar por obra", ["Todas"] + obras, key="filtro_obra_ref")
        filtro_fam = st.selectbox("Filtrar por familia", ["Todas"] + FAMILIAS_DEFAULT, key="filtro_fam_ref")

        df_show = df_hist.copy()
        if filtro_obra != "Todas": df_show = df_show[df_show["Obra"] == filtro_obra]
        if filtro_fam != "Todas": df_show = df_show[df_show["Familia"] == filtro_fam]

        st.dataframe(df_show, use_container_width=True, hide_index=True)

        if st.button("🗑️ Borrar todo el historial de referencias"):
            st.session_state.referencias = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 4 — OFERTAS
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "4. Ofertas":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 4 · Ofertas de proveedores</h2>
        <p>Sube Excel del proveedor. La IA extrae precios, categoriza y detecta qué incluye y qué no.</p>
    </div>
    """, unsafe_allow_html=True)

    def leer_excel_generico(archivo):
        try:
            if archivo.name.endswith(".csv"):
                return pd.read_csv(archivo), None
            df_raw = pd.read_excel(archivo, header=None)
            header_row = 0
            for i, row in df_raw.iterrows():
                if len(row.dropna()) >= 3:
                    header_row = i
                    break
            df = pd.read_excel(archivo, header=header_row)
            df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)
            return df, None
        except Exception as e:
            return None, str(e)

    def col_letra(i):
        result, n = "", i + 1
        while n > 0:
            n, r = divmod(n - 1, 26)
            result = chr(65 + r) + result
        return result

    def parsear_num(valor):
        try:
            if isinstance(valor, (int, float)):
                return float(valor)
            s = str(valor).strip().replace(" ", "").replace("€", "").replace("$", "")
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            return float(s)
        except:
            return None

    def call_openai(prompt, api_key, max_tokens=4000):
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={"model": "gpt-4o-mini", "temperature": 0.1, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]}
        )
        data = resp.json()
        if "error" in data:
            raise Exception(data["error"]["message"])
        texto = data["choices"][0]["message"]["content"].strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return texto.strip()

    # ── Metadatos del proveedor ───────────────────────────────────────────────
    st.markdown("**Datos de la oferta**")
    c1, c2, c3, c4, c5 = st.columns(5)
    of_proveedor = c1.text_input("Proveedor", key="of_proveedor", placeholder="Bortubo, Sancho...")
    of_fecha     = c2.date_input("Fecha oferta", key="of_fecha")
    of_validez   = c3.text_input("Validez", key="of_validez", placeholder="30 días, 31/12/25...")
    of_moneda    = c4.text_input("Moneda", key="of_moneda", value="EUR")
    of_tipo_gen  = c5.selectbox("Tipo general", ["Subcontrata", "Suministro", "Suministro + montaje", "A confirmar"], key="of_tipo_gen")

    of_notas_gen = st.text_area("Condiciones generales / exclusiones globales de la oferta", key="of_notas_gen",
                                 placeholder="Ej: todos los precios excluyen medios auxiliares. Válido para suministro únicamente...")

    archivo_of = st.file_uploader("📂 Subir Excel del proveedor", type=["xlsx", "xls", "csv"], key="up_of")

    if archivo_of:
        df_of, err = leer_excel_generico(archivo_of)
        if err:
            st.error(f"Error al leer: {err}")
        else:
            etiquetas = {col: f"{col_letra(i)} · {col}" for i, col in enumerate(df_of.columns)}
            etiquetas_lista = ["— no incluida —"] + list(etiquetas.values())
            etiqueta_a_col = {v: k for k, v in etiquetas.items()}

            st.success(f"✓ {len(df_of)} filas · {len(df_of.columns)} columnas")
            df_prev = df_of.head(6).copy()
            df_prev.columns = [f"{col_letra(i)} · {c}" for i, c in enumerate(df_of.columns)]
            st.dataframe(df_prev, use_container_width=True)

            st.markdown("**Indica las columnas**")
            c1, c2, c3, c4, c5 = st.columns(5)
            s_desc    = c1.selectbox("Descripción ✱", etiquetas_lista, key="os_desc")
            s_pu      = c2.selectbox("Precio unitario ✱", etiquetas_lista, key="os_pu")
            s_uni     = c3.selectbox("Unidad", etiquetas_lista, key="os_uni")
            s_incluye = c4.selectbox("Col. 'qué incluye' (si existe)", etiquetas_lista, key="os_inc")
            s_notas   = c5.selectbox("Col. notas / comentarios", etiquetas_lista, key="os_not")

            if st.button("✅ Cargar y analizar con IA", key="btn_of"):
                api_key = st.secrets.get("OPENAI_API_KEY", "")
                if not of_proveedor:
                    st.error("Indica el nombre del proveedor.")
                elif s_desc == "— no incluida —" or s_pu == "— no incluida —":
                    st.error("Descripción y Precio unitario son obligatorios.")
                elif not api_key:
                    st.error("⚠️ Falta OPENAI_API_KEY en Secrets.")
                else:
                    cols_map = {etiqueta_a_col[s_desc]: "Descripción", etiqueta_a_col[s_pu]: "Precio unitario"}
                    if s_uni     != "— no incluida —": cols_map[etiqueta_a_col[s_uni]]     = "Unidad"
                    if s_incluye != "— no incluida —": cols_map[etiqueta_a_col[s_incluye]] = "Incluye_raw"
                    if s_notas   != "— no incluida —": cols_map[etiqueta_a_col[s_notas]]   = "Notas_raw"

                    df_work = df_of[list(cols_map.keys())].rename(columns=cols_map).copy()
                    df_work["Precio unitario"] = df_work["Precio unitario"].apply(parsear_num)
                    df_work = df_work.dropna(subset=["Precio unitario"])
                    df_work = df_work[df_work["Precio unitario"] > 0].reset_index(drop=True)

                    PALABRAS_RESUMEN = ["capítulo","capitulo","cap.","total","resumen","suma","subtotal"]
                    mask = df_work["Descripción"].apply(lambda d: any(str(d).lower().strip().startswith(p) for p in PALABRAS_RESUMEN))
                    df_work = df_work[~mask].reset_index(drop=True)

                    with st.spinner("Analizando oferta con IA..."):
                        descs = df_work["Descripción"].fillna("").tolist()
                        notas_cols = df_work.get("Incluye_raw", pd.Series([""] * len(df_work))).fillna("").tolist()

                        prompt = f"""Eres experto en presupuestos de construcción de infraestructuras hidráulicas.
Analiza cada partida de esta oferta del proveedor "{of_proveedor}".
Condiciones generales de la oferta: {of_notas_gen or "No especificadas"}

Para cada partida indica:
1. "familia": una de la lista (texto exacto)
2. "incluye": resumen breve de qué cubre el precio (suministro, montaje, medios auxiliares...)
3. "excluye": qué NO incluye o qué hay que completar
4. "tipo": "Completa (S+M+MA)", "Solo suministro", "S+M sin MA", "A verificar"

Familias disponibles:
{TAXONOMIA_TEXTO}

Responde SOLO con JSON sin texto adicional:
[{{"indice":0,"familia":"...","incluye":"...","excluye":"...","tipo":"..."}}]

Partidas (índice: descripción | notas columna si existe):
""" + "\n".join([f"{i}: {d} | {n}" for i, (d, n) in enumerate(zip(descs, notas_cols))])

                        try:
                            texto = call_openai(prompt, api_key, max_tokens=6000)
                            asignaciones = json.loads(texto)

                            df_work["Familia"] = "TRV-99 · Varios / pendiente de clasificar"
                            df_work["Incluye"] = ""
                            df_work["Excluye"] = ""
                            df_work["Tipo"] = "A verificar"

                            for item in asignaciones:
                                idx = item.get("indice", -1)
                                if 0 <= idx < len(df_work):
                                    df_work.at[idx, "Familia"]  = item.get("familia", "TRV-99 · Varios / pendiente de clasificar")
                                    df_work.at[idx, "Incluye"]  = item.get("incluye", "")
                                    df_work.at[idx, "Excluye"]  = item.get("excluye", "")
                                    df_work.at[idx, "Tipo"]     = item.get("tipo", "A verificar")

                            df_work["Proveedor"] = of_proveedor
                            df_work["Fecha"]     = str(of_fecha)
                            df_work["Validez"]   = of_validez
                            df_work["Moneda"]    = of_moneda
                            df_work["Validado"]  = False

                            st.session_state["df_of_preview"] = df_work
                            st.success(f"✓ {len(df_work)} partidas analizadas. Revisa antes de guardar.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error IA: {e}")

    # ── Revisión y guardado ───────────────────────────────────────────────────
    if "df_of_preview" in st.session_state and not st.session_state["df_of_preview"].empty:
        st.markdown("---")
        st.markdown("**Revisa la oferta antes de guardar**")
        st.caption("Corrige familia, incluye/excluye si la IA se equivocó. Marca ✅ las que hayas validado.")

        edited_of = st.data_editor(
            st.session_state["df_of_preview"],
            column_config={
                "Familia":  st.column_config.SelectboxColumn("Familia", options=FAMILIAS_DEFAULT),
                "Tipo":     st.column_config.SelectboxColumn("Tipo", options=["Completa (S+M+MA)", "Solo suministro", "S+M sin MA", "A verificar"]),
                "Precio unitario": st.column_config.NumberColumn("P. Unitario", format="%.2f"),
                "Validado": st.column_config.CheckboxColumn("✅ OK"),
            },
            use_container_width=True, num_rows="fixed", height=400,
        )
        st.session_state["df_of_preview"] = edited_of

        if st.button("💾 Añadir al historial de ofertas"):
            nuevas = edited_of.to_dict("records")
            st.session_state.ofertas.extend(nuevas)
            del st.session_state["df_of_preview"]
            st.success(f"✓ {len(nuevas)} precios de oferta añadidos.")
            st.rerun()

    # ── Historial de ofertas ───────────────────────────────────────────────────
    if st.session_state.ofertas:
        st.markdown("---")
        df_hist_of = pd.DataFrame(st.session_state.ofertas)
        proveedores = df_hist_of["Proveedor"].unique().tolist() if "Proveedor" in df_hist_of.columns else []
        st.markdown(f"**Historial: {len(df_hist_of)} precios de {len(proveedores)} proveedor(es)**")

        filtro_prov = st.selectbox("Filtrar por proveedor", ["Todos"] + proveedores, key="filtro_prov")
        filtro_fam2 = st.selectbox("Filtrar por familia", ["Todas"] + FAMILIAS_DEFAULT, key="filtro_fam_of")

        df_show_of = df_hist_of.copy()
        if filtro_prov != "Todos": df_show_of = df_show_of[df_show_of["Proveedor"] == filtro_prov]
        if filtro_fam2 != "Todas": df_show_of = df_show_of[df_show_of["Familia"] == filtro_fam2]

        st.dataframe(df_show_of, use_container_width=True, hide_index=True)

        if st.button("🗑️ Borrar todo el historial de ofertas"):
            st.session_state.ofertas = []
            st.rerun()


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
