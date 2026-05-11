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
# HELPERS COMPARTIDOS
# ═══════════════════════════════════════════════════════════════════════════════
def parsear_num(valor):
    try:
        if isinstance(valor, (int, float)):
            return float(valor)
        s = str(valor).strip().replace(" ","").replace("€","").replace("$","").replace("£","")
        if "," in s and "." in s:
            s = s.replace(".","").replace(",",".")
        elif "," in s:
            s = s.replace(",",".")
        return float(s)
    except:
        return None

def col_letra(i):
    result, n = "", i + 1
    while n > 0:
        n, r = divmod(n-1, 26)
        result = chr(65+r) + result
    return result

def leer_excel_todas_hojas(archivo):
    """Lee todas las hojas de un Excel. Devuelve dict {nombre_hoja: df}."""
    try:
        if archivo.name.endswith(".csv"):
            return {"Hoja única": pd.read_csv(archivo)}, None
        xls = pd.ExcelFile(archivo)
        hojas = {}
        for hoja in xls.sheet_names:
            try:
                df_raw = pd.read_excel(xls, sheet_name=hoja, header=None)
                if df_raw.empty or len(df_raw) < 2:
                    continue
                header_row = 0
                for i, row in df_raw.iterrows():
                    if len(row.dropna()) >= 2:
                        header_row = i
                        break
                df = pd.read_excel(xls, sheet_name=hoja, header=header_row)
                df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)
                if len(df) > 0:
                    hojas[hoja] = df
            except:
                pass
        return hojas, None
    except Exception as e:
        return {}, str(e)

def call_ai(prompt, max_tokens=6000):
    """Llama a la IA disponible (Gemini 1.5 Flash preferido, luego OpenAI)."""
    gemini_key = st.secrets.get("GEMINI_API_KEY","")
    openai_key = st.secrets.get("OPENAI_API_KEY","")

    if gemini_key:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
            headers={"Content-Type":"application/json"},
            json={"contents":[{"parts":[{"text":prompt}]}],
                  "generationConfig":{"temperature":0.1,"maxOutputTokens":max_tokens}}
        )
        data = resp.json()
        if "error" in data:
            raise Exception(data["error"]["message"])
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    elif openai_key:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Content-Type":"application/json","Authorization":f"Bearer {openai_key}"},
            json={"model":"gpt-4o-mini","temperature":0.1,"max_tokens":max_tokens,
                  "messages":[{"role":"user","content":prompt}]}
        )
        data = resp.json()
        if "error" in data:
            raise Exception(data["error"]["message"])
        return data["choices"][0]["message"]["content"].strip()
    else:
        raise Exception("No hay API key configurada. Añade GEMINI_API_KEY u OPENAI_API_KEY en Secrets.")

def limpiar_json_ia(texto):
    """Limpia respuesta de IA y parsea JSON."""
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    return json.loads(t.strip())

def tiene_api_key():
    return bool(st.secrets.get("GEMINI_API_KEY","") or st.secrets.get("OPENAI_API_KEY",""))

def nombre_proveedor_ia():
    if st.secrets.get("GEMINI_API_KEY",""):
        return "Gemini 1.5 Flash"
    elif st.secrets.get("OPENAI_API_KEY",""):
        return "OpenAI GPT-4o mini"
    return "IA"

PALABRAS_RESUMEN = ["capítulo","capitulo","cap.","cap ","total","resumen","suma",
                    "subtotal","sub-total","apartado","título","titulo","chapter",
                    "section","total general","presupuesto total"]

def es_fila_resumen(desc):
    d = str(desc).lower().strip()
    return any(d.startswith(p) for p in PALABRAS_RESUMEN) or d in ["","nan"]

def calcular_precio_actualizado(precio, año_ref, familia, tasa_col=None):
    años = max(0, date.today().year - int(año_ref))
    if años == 0:
        return precio
    if tasa_col and tasa_col > 0:
        tasa = tasa_col
    else:
        disc = next((t["disciplina"] for t in TAXONOMIA if t["familia"] == familia), None)
        td = st.session_state.get("tasas_familia", {}).get(disc, 0.0) if disc else 0.0
        tasa = td if td > 0 else st.session_state.get("tasa_general", 3.0)
    return round(precio * ((1 + tasa/100) ** años), 2)

def selector_hojas(hojas_dict, key_prefix):
    """Muestra selector de hoja si hay más de una."""
    if not hojas_dict:
        return None, None
    nombres = list(hojas_dict.keys())
    if len(nombres) == 1:
        return nombres[0], hojas_dict[nombres[0]]
    sel = st.selectbox(f"El archivo tiene {len(nombres)} hojas. ¿Cuál contiene los datos?",
                       nombres, key=f"{key_prefix}_hoja")
    return sel, hojas_dict[sel]

def analizar_excel_con_ia(df, contexto, moneda="EUR"):
    """Usa IA para detectar columnas Y categorizar partidas en un solo paso."""
    sample = df.head(30).to_string(index=True, max_colwidth=80)
    cols_info = ", ".join([f"{col_letra(i)}: {c}" for i, c in enumerate(df.columns)])

    prompt = f"""Eres experto en presupuestos de construcción de infraestructuras hidráulicas (EDAR, IDAM, ETAP, conducciones).

Analiza este fragmento de Excel de {contexto} (moneda: {moneda}).
Columnas disponibles: {cols_info}

Primeras filas:
{sample}

Tarea:
1. Identifica qué columna contiene: descripción, precio unitario, medición/cantidad, importe total, unidad. Usa letras de columna.
2. Para cada fila que sea una partida real (no un resumen/capítulo/total), asigna una familia de esta lista:
{TAXONOMIA_TEXTO}

IMPORTANTE: Ignora filas que sean capítulos, subtotales, totales o filas vacías.
Solo incluye partidas con descripción real y precio > 0.

Responde SOLO con este JSON (sin texto adicional):
{{
  "columnas": {{
    "descripcion": "letra_columna o null",
    "precio_unitario": "letra_columna o null",
    "medicion": "letra_columna o null",
    "importe_total": "letra_columna o null",
    "unidad": "letra_columna o null"
  }},
  "partidas": [
    {{"fila": 0, "familia": "CIV-03 · Movimiento de tierras", "descripcion_limpia": "texto limpio"}}
  ]
}}"""
    return limpiar_json_ia(call_ai(prompt, max_tokens=8000))

def letra_a_col(letra, df):
    """Convierte letra Excel (A, B...) al nombre de columna del DataFrame."""
    if not letra or letra == "null":
        return None
    idx = 0
    for c in letra.upper():
        idx = idx * 26 + (ord(c) - 64)
    idx -= 1
    if 0 <= idx < len(df.columns):
        return df.columns[idx]
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 1 — PROYECTO
# ═══════════════════════════════════════════════════════════════════════════════
if paso == "1. Proyecto":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 1 · Identificar el proyecto</h2>
        <p>Datos básicos de la licitación</p>
    </div>
    """, unsafe_allow_html=True)

    p = st.session_state.proyecto

    col1, col2 = st.columns(2)
    with col1:
        nombre    = st.text_input("Nombre del proyecto", value=p.get("nombre",""), placeholder="EDAR El Marco — Cáceres")
        tipologia = st.selectbox("Tipología", ["EDAR","IDAM / Desaladora","ETAP","Colectores y saneamiento","Obra marítima","Infraestructura hidráulica","Otro"],
                                  index=["EDAR","IDAM / Desaladora","ETAP","Colectores y saneamiento","Obra marítima","Infraestructura hidráulica","Otro"].index(p.get("tipologia","EDAR")) if p.get("tipologia") else 0)
        pais      = st.text_input("País", value=p.get("pais","España"))
        promotor  = st.text_input("Promotor / Cliente", value=p.get("promotor",""), placeholder="Ayuntamiento de Cáceres")

    with col2:
        fecha_limite = st.date_input("Fecha límite de presentación",
                                      value=date.fromisoformat(p["fecha_limite"]) if p.get("fecha_limite") else date.today())

        c_mon1, c_mon2 = st.columns([2,1])
        moneda_cod = c_mon1.selectbox("Moneda", ["EUR","USD","GBP","MAD","SAR","AUD","CNY","HKD","SGD","AED","QAR","KWD","Otra"],
                                       index=["EUR","USD","GBP","MAD","SAR","AUD","CNY","HKD","SGD","AED","QAR","KWD","Otra"].index(p.get("moneda_cod","EUR")) if p.get("moneda_cod") in ["EUR","USD","GBP","MAD","SAR","AUD","CNY","HKD","SGD","AED","QAR","KWD"] else 0)
        moneda_otra = c_mon2.text_input("Si Otra:", value=p.get("moneda_otra",""), placeholder="BRL, MXN...")
        moneda_final = moneda_otra.strip().upper() if moneda_cod == "Otra" and moneda_otra.strip() else moneda_cod

        presupuesto_texto = st.text_input("Presupuesto de licitación", value=p.get("presupuesto_texto",""),
                                           placeholder="37.166.355,32")
        expediente  = st.text_input("Nº expediente / referencia interna", value=p.get("expediente",""))
        responsable = st.text_input("Técnico responsable", value=p.get("responsable",""))

    notas = st.text_area("Notas sobre el proyecto", value=p.get("notas",""))

    def parsear_importe(texto):
        try:
            return float(texto.strip().replace("€","").replace(" ","").replace(".","").replace(",","."))
        except:
            return 0.0

    if st.button("💾 Guardar datos del proyecto"):
        st.session_state.proyecto = {
            "nombre": nombre, "tipologia": tipologia, "pais": pais, "promotor": promotor,
            "fecha_limite": str(fecha_limite),
            "moneda_cod": moneda_cod, "moneda_otra": moneda_otra, "moneda": moneda_final,
            "presupuesto": parsear_importe(presupuesto_texto),
            "presupuesto_texto": presupuesto_texto,
            "expediente": expediente, "responsable": responsable, "notas": notas,
        }
        st.success(f"✓ Proyecto '{nombre}' guardado — Moneda: {moneda_final}")

    if st.session_state.proyecto:
        p = st.session_state.proyecto
        c1, c2, c3, c4 = st.columns(4)
        pres = p.get("presupuesto",0)
        c1.metric("Presupuesto", f"{pres:,.2f} {p.get('moneda','EUR')}" if pres else "—")
        c2.metric("Tipología", p.get("tipologia","—"))
        c3.metric("País", p.get("pais","—"))
        c4.metric("Fecha límite", p.get("fecha_limite","—"))


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 2 — PRESUPUESTO
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "2. Presupuesto":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 2 · Cargar y categorizar el presupuesto</h2>
        <p>Sube el Excel del proyecto. La IA detecta columnas, filtra resúmenes y categoriza automáticamente.</p>
    </div>
    """, unsafe_allow_html=True)

    if not tiene_api_key():
        st.markdown("""<div class="info-box-red">
        ⚠️ <strong>Necesitas configurar una API key de IA</strong> en Streamlit → Settings → Secrets:<br>
        <code>GEMINI_API_KEY = "AIza..."</code> (gratuito) · o · <code>OPENAI_API_KEY = "sk-..."</code><br>
        Obtén Gemini gratis en <strong>aistudio.google.com</strong>
        </div>""", unsafe_allow_html=True)

    moneda_proy = st.session_state.proyecto.get("moneda","EUR") if st.session_state.proyecto else "EUR"

    archivo = st.file_uploader("📂 Subir Excel del presupuesto", type=["xlsx","xls","csv"])

    if archivo:
        hojas, err = leer_excel_todas_hojas(archivo)
        if err:
            st.error(f"Error al leer: {err}")
        elif not hojas:
            st.error("El archivo no contiene datos legibles.")
        else:
            hoja_sel, df_raw = selector_hojas(hojas, "ppto")

            if df_raw is not None:
                st.success(f"✓ Hoja '{hoja_sel}': {len(df_raw)} filas · {len(df_raw.columns)} columnas")
                df_prev = df_raw.head(8).copy()
                df_prev.columns = [f"{col_letra(i)} · {c}" for i, c in enumerate(df_raw.columns)]
                st.dataframe(df_prev, use_container_width=True)

                if st.button(f"🤖 Analizar con {nombre_proveedor_ia()}", key="btn_ppto"):
                    if not tiene_api_key():
                        st.error("Configura una API key primero.")
                    else:
                        with st.spinner("La IA está leyendo el presupuesto y categorizando partidas..."):
                            try:
                                resultado = analizar_excel_con_ia(df_raw, "presupuesto de licitación", moneda_proy)

                                cols = resultado.get("columnas", {})
                                partidas_ia = resultado.get("partidas", [])

                                col_desc = letra_a_col(cols.get("descripcion"), df_raw)
                                col_pu   = letra_a_col(cols.get("precio_unitario"), df_raw)
                                col_med  = letra_a_col(cols.get("medicion"), df_raw)
                                col_imp  = letra_a_col(cols.get("importe_total"), df_raw)
                                col_uni  = letra_a_col(cols.get("unidad"), df_raw)

                                filas_ia = {p["fila"]: p for p in partidas_ia}
                                registros = []
                                for idx, p_ia in filas_ia.items():
                                    if 0 <= idx < len(df_raw):
                                        row = df_raw.iloc[idx]
                                        r = {
                                            "Descripción": p_ia.get("descripcion_limpia") or (str(row[col_desc]).strip() if col_desc else ""),
                                            "Familia": p_ia.get("familia","TRV-99 · Varios / pendiente de clasificar"),
                                            "Precio unitario": parsear_num(row[col_pu]) if col_pu else None,
                                            "Medición": parsear_num(row[col_med]) if col_med else None,
                                            "Importe total": parsear_num(row[col_imp]) if col_imp else None,
                                            "Unidad": str(row[col_uni]).strip() if col_uni else "",
                                            "Analizar": False,
                                        }
                                        imp = r["Importe total"] or 0
                                        if imp > 0 or (r["Precio unitario"] or 0) > 0:
                                            registros.append(r)

                                df_part = pd.DataFrame(registros)
                                if df_part.empty:
                                    st.warning("La IA no encontró partidas con precio. Revisa el archivo.")
                                else:
                                    # Pre-seleccionar top 80% por importe
                                    df_part["Importe total"] = pd.to_numeric(df_part["Importe total"], errors="coerce").fillna(0)
                                    df_sorted = df_part.sort_values("Importe total", ascending=False)
                                    total_imp = df_sorted["Importe total"].sum()
                                    acum, indices_top = 0, []
                                    for idx2 in df_sorted.index:
                                        acum += df_sorted.at[idx2,"Importe total"]
                                        indices_top.append(idx2)
                                        if total_imp > 0 and acum/total_imp >= 0.80:
                                            break
                                    df_part.loc[indices_top, "Analizar"] = True
                                    st.session_state.partidas = df_part
                                    n_sel = df_part["Analizar"].sum()
                                    st.success(f"✓ {len(df_part)} partidas detectadas · {int(n_sel)} pre-seleccionadas (≥80% importe) · Familias asignadas por IA")
                                    st.rerun()

                            except Exception as e:
                                st.error(f"Error en análisis IA: {e}")

    # ── Tabla de partidas categorizadas ───────────────────────────────────────
    if not st.session_state.partidas.empty:
        df_part = st.session_state.partidas.copy()
        total_imp = pd.to_numeric(df_part.get("Importe total", pd.Series()), errors="coerce").sum()
        n_sel = int(df_part.get("Analizar", pd.Series(dtype=bool)).sum())
        imp_sel = df_part[df_part.get("Analizar", False) == True]["Importe total"].sum() if "Analizar" in df_part.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Partidas", len(df_part))
        c2.metric("Seleccionadas para análisis", n_sel)
        c3.metric("% importe cubierto", f"{imp_sel/total_imp*100:.1f}%" if total_imp else "—")

        st.markdown("**Revisa la categorización. Marca ✅ las partidas a analizar.**")
        st.caption("Las familias ya están asignadas por la IA. Corrige lo que no sea correcto antes de continuar.")

        filtro_disc2 = st.selectbox("Filtrar tabla por disciplina", DISCIPLINAS, key="filtro_disc2")

        # Guardar estado antes de mostrar editor
        key_editor = "partidas_editor_v1"
        df_show = df_part.copy()

        col_config = {
            "Analizar": st.column_config.CheckboxColumn("Analizar ✅"),
            "Familia": st.column_config.SelectboxColumn("Familia", options=FAMILIAS_DEFAULT),
            "Importe total": st.column_config.NumberColumn("Importe (€)", format="%.2f"),
            "Precio unitario": st.column_config.NumberColumn("P.Unit (€)", format="%.2f"),
            "Medición": st.column_config.NumberColumn("Medición", format="%.2f"),
        }

        edited = st.data_editor(
            df_show,
            column_config=col_config,
            use_container_width=True,
            num_rows="fixed",
            height=420,
            key=key_editor,
        )

        c_a, c_b = st.columns(2)
        if c_a.button("💾 Guardar cambios"):
            st.session_state.partidas = edited
            st.success("✓ Guardado")
        if c_b.button("🔄 Recategorizar con IA"):
            st.session_state.partidas = edited
            st.info("Sube de nuevo el archivo para recategorizar.")

        # Resumen por familia
        if "Familia" in edited.columns:
            st.markdown("---")
            st.markdown("**Resumen por familia (partidas marcadas)**")
            df_sel2 = edited[edited.get("Analizar", False) == True].copy() if "Analizar" in edited.columns else edited.copy()
            df_sel2["Importe total"] = pd.to_numeric(df_sel2["Importe total"], errors="coerce")
            resumen = df_sel2.groupby("Familia")["Importe total"].agg(["sum","count"]).reset_index()
            resumen.columns = ["Familia","Importe (€)","Nº partidas"]
            resumen = resumen.sort_values("Importe (€)", ascending=False)
            total_r = resumen["Importe (€)"].sum()
            resumen["% s/total"] = (resumen["Importe (€)"]/total_r*100).round(1).astype(str) + "%" if total_r else "—"
            resumen["Importe (€)"] = resumen["Importe (€)"].map("{:,.0f}".format)
            st.dataframe(resumen, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 3 — REFERENCIAS
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "3. Referencias":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 3 · Referencias de obras anteriores</h2>
        <p>Sube Excels de obras propias. La IA interpreta la estructura y extrae precios de referencia.</p>
    </div>
    """, unsafe_allow_html=True)

    if not tiene_api_key():
        st.markdown("""<div class="info-box-red">⚠️ Necesitas configurar una API key. Ver Paso 2.</div>""", unsafe_allow_html=True)

    # Tasas de actualización
    with st.expander("⚙️ Tasas de actualización de precios", expanded=False):
        st.caption(f"Actualiza precios al año en curso ({date.today().year}). Prioridad: Excel > por disciplina > general.")
        tasa_general = st.number_input("Tasa general anual (%)", 0.0, 30.0,
                                        value=st.session_state.get("tasa_general",3.0), step=0.5, key="tg_inp", format="%.1f")
        st.session_state["tasa_general"] = tasa_general
        tasas_familia = st.session_state.get("tasas_familia",{})
        disc_cols = st.columns(3)
        for i, disc in enumerate(["Civil","Mecánico","Eléctrico","I&C","Building services","Transversal"]):
            v = disc_cols[i%3].number_input(disc, 0.0, 30.0, value=tasas_familia.get(disc,0.0), step=0.5, key=f"tf_{disc}", format="%.1f")
            tasas_familia[disc] = v
        st.session_state["tasas_familia"] = tasas_familia

    st.markdown("**Datos de la obra de referencia**")
    c1, c2, c3, c4 = st.columns(4)
    ref_nombre = c1.text_input("Nombre de la obra", key="ref_nombre", placeholder="EDAR El Marco, Cáceres")
    ref_pais   = c2.text_input("País", key="ref_pais", value="España")
    ref_anio   = c3.number_input("Año", 2000, 2030, value=2022, key="ref_anio")
    ref_moneda = c4.text_input("Moneda", key="ref_moneda", value="EUR", placeholder="EUR, USD, MAD...")

    archivo_ref = st.file_uploader("📂 Subir Excel de la obra de referencia", type=["xlsx","xls","csv"], key="up_ref")

    if archivo_ref:
        hojas_ref, err_ref = leer_excel_todas_hojas(archivo_ref)
        if err_ref:
            st.error(f"Error: {err_ref}")
        elif not hojas_ref:
            st.error("No se encontraron datos legibles.")
        else:
            hoja_ref_sel, df_ref_raw = selector_hojas(hojas_ref, "ref")
            if df_ref_raw is not None:
                st.success(f"✓ Hoja \"{hoja_ref_sel}\": {len(df_ref_raw)} filas · {len(df_ref_raw.columns)} columnas")
                st.dataframe(df_ref_raw.head(6).rename(columns={c: f"{col_letra(i)}·{c}" for i,c in enumerate(df_ref_raw.columns)}), use_container_width=True)

                if st.button(f"🤖 Interpretar con {nombre_proveedor_ia()}", key="btn_ref"):
                    if not ref_nombre:
                        st.error("Indica el nombre de la obra.")
                    elif not tiene_api_key():
                        st.error("Configura una API key.")
                    else:
                        with st.spinner("Analizando la obra de referencia con IA..."):
                            try:
                                resultado = analizar_excel_con_ia(df_ref_raw, f"obra de referencia: {ref_nombre}", ref_moneda)
                                cols = resultado.get("columnas",{})
                                partidas_ia = resultado.get("partidas",[])

                                col_desc = letra_a_col(cols.get("descripcion"), df_ref_raw)
                                col_pu   = letra_a_col(cols.get("precio_unitario"), df_ref_raw)
                                col_med  = letra_a_col(cols.get("medicion"), df_ref_raw)
                                col_imp  = letra_a_col(cols.get("importe_total"), df_ref_raw)
                                col_uni  = letra_a_col(cols.get("unidad"), df_ref_raw)

                                filas_ia = {p["fila"]: p for p in partidas_ia}
                                registros = []
                                for idx, p_ia in filas_ia.items():
                                    if 0 <= idx < len(df_ref_raw):
                                        row = df_ref_raw.iloc[idx]
                                        pu = parsear_num(row[col_pu]) if col_pu else None
                                        if not pu or pu <= 0:
                                            continue
                                        familia = p_ia.get("familia","TRV-99 · Varios / pendiente de clasificar")
                                        pu_act = calcular_precio_actualizado(pu, ref_anio, familia)
                                        disc_f = next((t["disciplina"] for t in TAXONOMIA if t["familia"]==familia), "—")
                                        registros.append({
                                            "Descripción": p_ia.get("descripcion_limpia") or (str(row[col_desc]).strip() if col_desc else ""),
                                            "Familia": familia,
                                            "Unidad": str(row[col_uni]).strip() if col_uni else "",
                                            "Medición": parsear_num(row[col_med]) if col_med else None,
                                            "Importe total": parsear_num(row[col_imp]) if col_imp else None,
                                            "P. original": pu,
                                            "Precio unitario": pu_act,
                                            "Tasa aplicada": f"{st.session_state.get('tasas_familia',{}).get(disc_f, st.session_state.get('tasa_general',3.0))}%",
                                            "Obra": ref_nombre, "País": ref_pais,
                                            "Año": ref_anio, "Año actualizado": date.today().year,
                                            "Moneda": ref_moneda, "Validado": False,
                                        })

                                df_ref_work = pd.DataFrame(registros)
                                st.session_state["df_ref_preview"] = df_ref_work
                                st.success(f"✓ {len(df_ref_work)} partidas interpretadas. Revisa antes de guardar.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error IA: {e}")

    if "df_ref_preview" in st.session_state and not st.session_state["df_ref_preview"].empty:
        st.markdown("---")
        st.markdown("**Revisa antes de añadir al historial**")
        st.caption("'Precio unitario' = precio actualizado al año en curso. 'P. original' = precio del año de referencia.")
        edited_ref = st.data_editor(
            st.session_state["df_ref_preview"],
            column_config={
                "Familia": st.column_config.SelectboxColumn("Familia", options=FAMILIAS_DEFAULT),
                "P. original": st.column_config.NumberColumn("P. original", format="%.2f"),
                "Precio unitario": st.column_config.NumberColumn(f"P. actualizado {date.today().year}", format="%.2f"),
                "Validado": st.column_config.CheckboxColumn("✅ OK"),
            },
            use_container_width=True, num_rows="fixed", height=380, key="ed_ref",
        )
        st.session_state["df_ref_preview"] = edited_ref
        if st.button("💾 Añadir al historial"):
            st.session_state.referencias.extend(edited_ref.to_dict("records"))
            del st.session_state["df_ref_preview"]
            st.success(f"✓ {len(edited_ref)} precios añadidos al historial.")
            st.rerun()

    if st.session_state.referencias:
        st.markdown("---")
        df_hist_r = pd.DataFrame(st.session_state.referencias)
        obras_r = df_hist_r["Obra"].unique().tolist() if "Obra" in df_hist_r.columns else []
        st.markdown(f"**Historial: {len(df_hist_r)} precios de {len(obras_r)} obra(s)**")
        f1, f2 = st.columns(2)
        fo = f1.selectbox("Obra", ["Todas"]+obras_r, key="fo_r")
        ff = f2.selectbox("Familia", ["Todas"]+FAMILIAS_DEFAULT, key="ff_r")
        df_hr = df_hist_r.copy()
        if fo != "Todas": df_hr = df_hr[df_hr["Obra"]==fo]
        if ff != "Todas": df_hr = df_hr[df_hr["Familia"]==ff]
        st.dataframe(df_hr, use_container_width=True, hide_index=True)
        if st.button("🗑️ Borrar historial de referencias"):
            st.session_state.referencias = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 4 — OFERTAS
# ═══════════════════════════════════════════════════════════════════════════════
elif paso == "4. Ofertas":
    st.markdown("""
    <div class="step-header">
        <h2>Paso 4 · Ofertas de proveedores</h2>
        <p>Sube Excel del proveedor. La IA extrae precios, categoriza y detecta alcance de cada precio.</p>
    </div>
    """, unsafe_allow_html=True)

    if not tiene_api_key():
        st.markdown("""<div class="info-box-red">⚠️ Necesitas configurar una API key. Ver Paso 2.</div>""", unsafe_allow_html=True)

    st.markdown("**Datos de la oferta**")
    c1, c2, c3, c4, c5 = st.columns(5)
    of_prov   = c1.text_input("Proveedor", key="of_prov", placeholder="Bortubo, Sancho...")
    of_fecha  = c2.date_input("Fecha", key="of_fecha")
    of_valid  = c3.text_input("Validez", key="of_valid", placeholder="30 días...")
    of_moneda = c4.text_input("Moneda", key="of_moneda", value="EUR")
    of_tipo   = c5.selectbox("Tipo general", ["Subcontrata","Suministro","S+Montaje","A confirmar"], key="of_tipo")
    of_notas  = st.text_area("Condiciones generales / exclusiones globales", key="of_notas",
                               placeholder="Ej: precios excluyen medios auxiliares...")

    archivo_of = st.file_uploader("📂 Subir Excel del proveedor", type=["xlsx","xls","csv"], key="up_of")

    if archivo_of:
        hojas_of, err_of = leer_excel_todas_hojas(archivo_of)
        if err_of:
            st.error(f"Error: {err_of}")
        elif not hojas_of:
            st.error("No se encontraron datos legibles.")
        else:
            hoja_of_sel, df_of_raw = selector_hojas(hojas_of, "oferta")
            if df_of_raw is not None:
                st.success(f"✓ Hoja \"{hoja_of_sel}\": {len(df_of_raw)} filas · {len(df_of_raw.columns)} columnas")
                st.dataframe(df_of_raw.head(6).rename(columns={c: f"{col_letra(i)}·{c}" for i,c in enumerate(df_of_raw.columns)}), use_container_width=True)

                if st.button(f"🤖 Analizar oferta con {nombre_proveedor_ia()}", key="btn_of"):
                    if not of_prov:
                        st.error("Indica el nombre del proveedor.")
                    elif not tiene_api_key():
                        st.error("Configura una API key.")
                    else:
                        with st.spinner("Analizando oferta con IA..."):
                            try:
                                sample = df_of_raw.head(30).to_string(index=True, max_colwidth=80)
                                cols_info = ", ".join([f"{col_letra(i)}: {c}" for i,c in enumerate(df_of_raw.columns)])
                                prompt_of = f"""Eres experto en presupuestos de infraestructuras hidráulicas.

Analiza esta oferta del proveedor "{of_prov}" (tipo: {of_tipo}, moneda: {of_moneda}).
Condiciones generales: {of_notas or "No especificadas"}
Columnas: {cols_info}

Primeras filas:
{sample}

Para cada partida real (no capítulos/totales):
1. Identifica descripción, precio unitario, unidad
2. Asigna familia de la taxonomía
3. Determina qué incluye y qué excluye el precio
4. Clasifica el tipo de precio

Familias:
{TAXONOMIA_TEXTO}

Responde SOLO con JSON:
{{
  "columnas": {{"descripcion":"letra","precio_unitario":"letra","unidad":"letra o null"}},
  "partidas": [
    {{"fila":0,"familia":"CIV-03 · Movimiento de tierras","descripcion_limpia":"texto",
      "incluye":"suministro + colocación","excluye":"medios auxiliares",
      "tipo":"S+M sin MA"}}
  ]
}}"""

                                resultado = limpiar_json_ia(call_ai(prompt_of, max_tokens=8000))
                                cols = resultado.get("columnas",{})
                                partidas_ia = resultado.get("partidas",[])

                                col_desc_of = letra_a_col(cols.get("descripcion"), df_of_raw)
                                col_pu_of   = letra_a_col(cols.get("precio_unitario"), df_of_raw)
                                col_uni_of  = letra_a_col(cols.get("unidad"), df_of_raw)

                                filas_of = {p["fila"]: p for p in partidas_ia}
                                registros_of = []
                                for idx, p_ia in filas_of.items():
                                    if 0 <= idx < len(df_of_raw):
                                        row = df_of_raw.iloc[idx]
                                        pu = parsear_num(row[col_pu_of]) if col_pu_of else None
                                        if not pu or pu <= 0:
                                            continue
                                        registros_of.append({
                                            "Descripción": p_ia.get("descripcion_limpia") or (str(row[col_desc_of]).strip() if col_desc_of else ""),
                                            "Familia": p_ia.get("familia","TRV-99 · Varios / pendiente de clasificar"),
                                            "Precio unitario": pu,
                                            "Unidad": str(row[col_uni_of]).strip() if col_uni_of else "",
                                            "Incluye": p_ia.get("incluye",""),
                                            "Excluye": p_ia.get("excluye",""),
                                            "Tipo": p_ia.get("tipo","A verificar"),
                                            "Proveedor": of_prov, "Fecha": str(of_fecha),
                                            "Validez": of_valid, "Moneda": of_moneda,
                                            "Validado": False,
                                        })

                                df_of_work = pd.DataFrame(registros_of)
                                st.session_state["df_of_preview"] = df_of_work
                                st.success(f"✓ {len(df_of_work)} partidas analizadas. Revisa antes de guardar.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error IA: {e}")

    if "df_of_preview" in st.session_state and not st.session_state["df_of_preview"].empty:
        st.markdown("---")
        st.markdown("**Revisa la oferta antes de guardar**")
        edited_of = st.data_editor(
            st.session_state["df_of_preview"],
            column_config={
                "Familia": st.column_config.SelectboxColumn("Familia", options=FAMILIAS_DEFAULT),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Completa (S+M+MA)","Solo suministro","S+M sin MA","A verificar"]),
                "Precio unitario": st.column_config.NumberColumn("P. Unitario", format="%.2f"),
                "Validado": st.column_config.CheckboxColumn("✅ OK"),
            },
            use_container_width=True, num_rows="fixed", height=400, key="ed_of",
        )
        st.session_state["df_of_preview"] = edited_of
        if st.button("💾 Añadir al historial de ofertas"):
            st.session_state.ofertas.extend(edited_of.to_dict("records"))
            del st.session_state["df_of_preview"]
            st.success(f"✓ {len(edited_of)} precios añadidos.")
            st.rerun()

    if st.session_state.ofertas:
        st.markdown("---")
        df_hist_of = pd.DataFrame(st.session_state.ofertas)
        provs = df_hist_of["Proveedor"].unique().tolist() if "Proveedor" in df_hist_of.columns else []
        st.markdown(f"**Historial: {len(df_hist_of)} precios de {len(provs)} proveedor(es)**")
        f1, f2 = st.columns(2)
        fp = f1.selectbox("Proveedor", ["Todos"]+provs, key="fp_of")
        ff2 = f2.selectbox("Familia", ["Todas"]+FAMILIAS_DEFAULT, key="ff_of")
        df_ho = df_hist_of.copy()
        if fp != "Todos": df_ho = df_ho[df_ho["Proveedor"]==fp]
        if ff2 != "Todas": df_ho = df_ho[df_ho["Familia"]==ff2]
        st.dataframe(df_ho, use_container_width=True, hide_index=True)
        if st.button("🗑️ Borrar historial de ofertas"):
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
