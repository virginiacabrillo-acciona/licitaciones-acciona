"""
app.py v2 — Sistema de Análisis de Licitaciones · Acciona
Flujo mínimo robusto: Cargar → Tipar hojas → Procesar → Revisar → Exportar
"""
import streamlit as st
import pandas as pd
import json
import io
from datetime import date, datetime

st.set_page_config(page_title="Análisis de Licitaciones · Acciona",
                   page_icon="⚙️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Barlow',sans-serif;}
[data-testid="stSidebar"]{background:#0C2340!important;}
[data-testid="stSidebar"] *{color:#fff!important;}
[data-testid="stSidebar"] hr{border-color:#1e3a5c;}
.app-header{background:linear-gradient(135deg,#0C2340 0%,#14355a 55%,#DA291C 100%);
  padding:22px 32px 18px;border-radius:10px;margin-bottom:24px;}
.app-header h1{font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;font-weight:700;margin:0;color:#fff;}
.app-header span{font-size:.9rem;opacity:.7;color:#fff;}
.step-hdr{border-left:5px solid #DA291C;padding:10px 18px;background:#f1f2f3;
  border-radius:0 8px 8px 0;margin-bottom:20px;}
.step-hdr h2{font-family:'Barlow Condensed',sans-serif;font-size:1.35rem;font-weight:700;
  color:#0C2340;margin:0;text-transform:uppercase;letter-spacing:.3px;}
.step-hdr p{margin:3px 0 0;color:#546579;font-size:.88rem;}
[data-testid="metric-container"]{background:#f1f2f3;border-radius:8px;padding:10px 14px;border:1px solid #dadee2;}
[data-testid="stMetricValue"]{color:#0C2340!important;font-family:'Barlow Condensed',sans-serif!important;font-weight:700!important;}
[data-testid="stMetricLabel"]{color:#546579!important;font-size:.78rem!important;}
.stButton>button{background:#DA291C!important;color:#fff!important;border:none!important;font-weight:600!important;border-radius:6px!important;}
.stButton>button:hover{background:#961111!important;}
.box-ok{background:#d4edda;border:1px solid #28a745;border-radius:8px;padding:14px 18px;margin:10px 0;}
.box-warn{background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:14px 18px;margin:10px 0;}
.box-red{background:#ffe3e3;border:1px solid #fcb7b3;border-radius:8px;padding:14px 18px;margin:10px 0;}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.78rem;font-weight:600;}
.b-pres{background:#d4edda;color:#155724;} .b-ofer{background:#d1ecf1;color:#0c5460;}
.b-ref{background:#fff3cd;color:#856404;} .b-res,.b-aux{background:#dadee2;color:#546579;}
.b-ign{background:#f5c6cb;color:#721c24;}
</style>""", unsafe_allow_html=True)

# ─── Módulos ───────────────────────────────────────────────────────────────────
@st.cache_resource
def cargar_ingestor():
    from ingesta import IngestorPresupuesto
    return IngestorPresupuesto("reglas.csv")

# ─── Estado ────────────────────────────────────────────────────────────────────
def init():
    defs = {"paso":"1. Cargar","proyecto":{},"archivo_bytes":None,
            "archivo_nombre":"","hojas_info":{},"partidas_master":pd.DataFrame(),
            "log_ingesta":[],"resumen_ingesta":{}}
    for k,v in defs.items():
        if k not in st.session_state: st.session_state[k]=v
init()

PASOS = ["1. Cargar","2. Hojas","3. Presupuesto","4. Revisar","5. Exportar"]
TIPOS = ["Presupuesto proyecto","Oferta proveedor","Referencia histórica",
         "Resumen / dashboard","Auxiliar / análisis","Ignorar"]
BADGE = {"Presupuesto proyecto":"b-pres","Oferta proveedor":"b-ofer",
         "Referencia histórica":"b-ref","Resumen / dashboard":"b-res",
         "Auxiliar / análisis":"b-aux","Ignorar":"b-ign"}

def sugerir_tipo(nombre, n_filas, cols, importe):
    nom = nombre.lower()
    col_desc = cols.get("descripcion","")
    if any(p in nom for p in ["resumen","dashboard","summary","portada","comp_","glosario","criterio"]):
        return "Resumen / dashboard"
    if any(p in nom for p in ["aux_","rendimiento","self_perf","maquinaria","mano_obra","parametro","detalle"]):
        return "Auxiliar / análisis"
    if any(p in nom for p in ["oferta","offer","proveedor","supplier"]) and importe>0:
        return "Oferta proveedor"
    if any(p in nom for p in ["ref","historico","anterior","referencia"]):
        return "Referencia histórica"
    if col_desc and importe>100000:
        if any(p in nom for p in ["proyecto","presupuesto","ppto","budget","pem","medicion","partida","01_"]):
            return "Presupuesto proyecto"
        if n_filas>50: return "Presupuesto proyecto"
    return "Auxiliar / análisis"

# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ LICITACIONES\n**Acciona**")
    st.markdown("<hr>", unsafe_allow_html=True)
    paso = st.radio("", PASOS, index=PASOS.index(st.session_state.paso), key="nav")
    st.session_state.paso = paso
    st.markdown("<hr>", unsafe_allow_html=True)
    p = st.session_state.proyecto
    if p:
        st.markdown(f"**📁 {p.get('nombre','—')}**")
        st.markdown(f"📍 {p.get('pais','—')} · {p.get('tipologia','—')}")
        if p.get('presupuesto_texto'): st.markdown(f"💰 {p['presupuesto_texto']} {p.get('moneda','EUR')}")
    else:
        st.markdown("*Sin proyecto cargado*")
    st.markdown("<hr>", unsafe_allow_html=True)
    pm_s = st.session_state.partidas_master
    if not pm_s.empty:
        sesion = {"proyecto":st.session_state.proyecto,
                  "resumen_ingesta":st.session_state.resumen_ingesta,
                  "partidas_master":pm_s.to_dict(orient="records")}
        st.download_button("💾 Guardar sesión",
            data=json.dumps(sesion, ensure_ascii=False, default=str, indent=2),
            file_name=f"sesion_{date.today()}.json", mime="application/json")
    sf = st.file_uploader("📂 Cargar sesión", type=["json"], key="sesion_up")
    if sf:
        try:
            d = json.load(sf)
            st.session_state.proyecto = d.get("proyecto",{})
            st.session_state.resumen_ingesta = d.get("resumen_ingesta",{})
            st.session_state.partidas_master = pd.DataFrame(d.get("partidas_master",[]))
            st.success("Sesión cargada")
        except Exception as e:
            st.error(f"Error: {e}")

# ─── Header ────────────────────────────────────────────────────────────────────
st.markdown("""<div class="app-header">
  <h1>⚙️ Sistema de Análisis de Licitaciones</h1>
  <span>Acciona · Estudio comparativo de costes</span>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# P1 — CARGAR
# ══════════════════════════════════════════════════════════════════════════════
if paso == "1. Cargar":
    st.markdown("""<div class="step-hdr"><h2>Paso 1 · Datos del proyecto y carga de archivo</h2>
    <p>Rellena los datos de la licitación y sube el Excel del presupuesto</p></div>""",
    unsafe_allow_html=True)

    p = st.session_state.proyecto
    TIP = ["EDAR","IDAM / Desaladora","ETAP","Colectores y saneamiento",
           "Obra marítima","Infraestructura hidráulica","Otro"]
    MON = ["EUR","USD","GBP","MAD","SAR","AUD","CNY","HKD","AED","QAR","Otra"]

    c1,c2 = st.columns(2)
    with c1:
        nombre    = st.text_input("Nombre del proyecto *", value=p.get("nombre",""),
                                   placeholder="EDAR El Marco — Cáceres")
        tipologia = st.selectbox("Tipología", TIP,
                                  index=TIP.index(p.get("tipologia","EDAR")) if p.get("tipologia") in TIP else 0)
        pais      = st.text_input("País", value=p.get("pais","España"))
        promotor  = st.text_input("Promotor / Cliente", value=p.get("promotor",""))
    with c2:
        fecha  = st.date_input("Fecha límite",
                                value=date.fromisoformat(p["fecha_limite"]) if p.get("fecha_limite") else date.today())
        cm1,cm2 = st.columns([2,1])
        mc = cm1.selectbox("Moneda", MON,
                            index=MON.index(p.get("moneda_cod","EUR")) if p.get("moneda_cod","EUR") in MON else 0)
        mo = cm2.text_input("Si Otra:", value=p.get("moneda_otra",""), placeholder="BRL...")
        moneda = mo.strip().upper() if mc=="Otra" and mo.strip() else mc
        pres   = st.text_input("Presupuesto", value=p.get("presupuesto_texto",""),
                                placeholder="37.166.355,32")
        exp    = st.text_input("Nº expediente", value=p.get("expediente",""))
        resp   = st.text_input("Técnico responsable", value=p.get("responsable",""))
    notas = st.text_area("Notas", value=p.get("notas",""))

    if st.button("💾 Guardar datos del proyecto"):
        if not nombre:
            st.error("El nombre es obligatorio.")
        else:
            st.session_state.proyecto = {
                "nombre":nombre,"tipologia":tipologia,"pais":pais,"promotor":promotor,
                "fecha_limite":str(fecha),"moneda_cod":mc,"moneda_otra":mo,"moneda":moneda,
                "presupuesto_texto":pres,"expediente":exp,"responsable":resp,"notas":notas,
            }
            st.success(f"✓ Proyecto '{nombre}' guardado — moneda: {moneda}")

    st.markdown("---")
    st.markdown("**Subir Excel del presupuesto**")
    arch = st.file_uploader("Formatos: .xlsx, .xls", type=["xlsx","xls"], key="arch_up")
    if arch:
        st.session_state.archivo_bytes  = arch.read()
        st.session_state.archivo_nombre = arch.name
        st.session_state.hojas_info = {}
        st.session_state.partidas_master = pd.DataFrame()
        st.success(f"✓ '{arch.name}' cargado. Avanza al Paso 2.")

    if st.session_state.archivo_bytes and st.session_state.proyecto:
        st.markdown('<div class="box-ok">✅ Proyecto y archivo listos. <strong>Avanza al Paso 2.</strong></div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# P2 — HOJAS
# ══════════════════════════════════════════════════════════════════════════════
elif paso == "2. Hojas":
    st.markdown("""<div class="step-hdr"><h2>Paso 2 · Previsualizar y tipar hojas</h2>
    <p>El motor sugiere el tipo de cada hoja. Tú decides qué se procesa como presupuesto.</p>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.archivo_bytes:
        st.markdown('<div class="box-red">⚠️ Sin archivo. Ve al Paso 1.</div>', unsafe_allow_html=True)
        st.stop()

    ing = cargar_ingestor()

    if not st.session_state.hojas_info:
        with st.spinner("Analizando hojas..."):
            hojas_raw = ing.leer_todas_hojas(st.session_state.archivo_bytes,
                                              st.session_state.archivo_nombre)
            info = {}
            for hoja, df_raw in hojas_raw.items():
                h_row = ing.detectar_cabecera(df_raw)
                try:
                    df = ing.aplicar_cabecera(df_raw, h_row)
                    cols = ing.detectar_columnas(df)
                    col_imp = cols.get("importe")
                    importe = 0.0
                    if col_imp and col_imp in df.columns:
                        importe = float(pd.to_numeric(df[col_imp], errors="coerce").sum() or 0)
                    tipo_sug = sugerir_tipo(hoja, len(df), cols, importe)
                except Exception:
                    cols = {}; importe = 0.0; tipo_sug = "Ignorar"
                info[hoja] = {"n_filas":len(df_raw),"header_row":h_row,"columnas":cols,
                              "importe_est":importe,"tipo_sugerido":tipo_sug,
                              "tipo_usuario":tipo_sug,"procesar":tipo_sug=="Presupuesto proyecto"}
            st.session_state.hojas_info = info

    hi_all = st.session_state.hojas_info
    st.markdown(f"**{len(hi_all)} hojas detectadas.** Ajusta el tipo y marca cuáles procesar.")
    st.caption("Solo las hojas marcadas como 'Presupuesto proyecto' irán a partidas_master.")

    with st.form("form_hojas"):
        cols_h = st.columns([3,1,2,2,3,1])
        for lbl in ["Hoja","Filas","Importe est.","Sugerido","Tipo (tú decides)","Procesar"]:
            cols_h.pop(0).markdown(f"**{lbl}**")
        st.markdown("---")
        cambios = {}
        for hoja, hi in hi_all.items():
            rc = st.columns([3,1,2,2,3,1])
            rc[0].write(hoja[:30])
            rc[1].write(str(hi["n_filas"]))
            rc[2].write(f"{hi['importe_est']:,.0f} €" if hi["importe_est"]>0 else "—")
            bc = BADGE.get(hi["tipo_sugerido"],"b-aux")
            rc[3].markdown(f'<span class="badge {bc}">{hi["tipo_sugerido"][:12]}</span>',
                           unsafe_allow_html=True)
            idx = TIPOS.index(hi["tipo_usuario"]) if hi["tipo_usuario"] in TIPOS else 0
            cambios[hoja] = {
                "tipo":    rc[4].selectbox("", TIPOS, index=idx,
                                            key=f"t_{hoja}", label_visibility="collapsed"),
                "procesar":rc[5].checkbox("", value=hi["procesar"],
                                           key=f"p_{hoja}", label_visibility="collapsed"),
            }
        if st.form_submit_button("✅ Confirmar tipado"):
            for hoja, vals in cambios.items():
                st.session_state.hojas_info[hoja]["tipo_usuario"] = vals["tipo"]
                st.session_state.hojas_info[hoja]["procesar"]     = vals["procesar"]
            st.success("✓ Tipado guardado. Avanza al Paso 3.")

    ppto  = [h for h,hi in hi_all.items() if hi.get("procesar") and hi.get("tipo_usuario")=="Presupuesto proyecto"]
    ofertas = [h for h,hi in hi_all.items() if hi.get("tipo_usuario")=="Oferta proveedor"]
    refs  = [h for h,hi in hi_all.items() if hi.get("tipo_usuario")=="Referencia histórica"]
    st.markdown("---")
    cc1,cc2,cc3 = st.columns(3)
    cc1.metric("→ Presupuesto", len(ppto))
    cc2.metric("→ Ofertas", len(ofertas))
    cc3.metric("→ Referencias", len(refs))
    if ppto: st.markdown(f"**Hojas como presupuesto:** {', '.join(ppto)}")

    if ppto:
        with st.expander(f"🔍 Vista previa — {ppto[0]}", expanded=False):
            try:
                hojas_raw2 = ing.leer_todas_hojas(st.session_state.archivo_bytes,
                                                   st.session_state.archivo_nombre)
                hi0 = hi_all[ppto[0]]
                df_p = ing.aplicar_cabecera(hojas_raw2[ppto[0]], hi0["header_row"])
                cn   = hi0.get("columnas",{})
                st.caption(f"Cabecera fila {hi0['header_row']+1} · {len(df_p)} filas · " +
                           " · ".join(f"{k}=**{v}**" for k,v in cn.items() if v))
                st.dataframe(df_p.head(8), use_container_width=True)
            except Exception as e:
                st.error(str(e))

# ══════════════════════════════════════════════════════════════════════════════
# P3 — PRESUPUESTO
# ══════════════════════════════════════════════════════════════════════════════
elif paso == "3. Presupuesto":
    st.markdown("""<div class="step-hdr"><h2>Paso 3 · Procesar presupuesto</h2>
    <p>Genera partidas_master a partir de las hojas seleccionadas como presupuesto</p></div>""",
    unsafe_allow_html=True)

    if not st.session_state.archivo_bytes:
        st.markdown('<div class="box-red">⚠️ Sin archivo. Ve al Paso 1.</div>', unsafe_allow_html=True); st.stop()
    if not st.session_state.hojas_info:
        st.markdown('<div class="box-warn">⚠️ Tipado no completado. Ve al Paso 2.</div>', unsafe_allow_html=True); st.stop()

    ppto = [h for h,hi in st.session_state.hojas_info.items()
            if hi.get("procesar") and hi.get("tipo_usuario")=="Presupuesto proyecto"]
    if not ppto:
        st.markdown('<div class="box-warn">⚠️ Ninguna hoja como Presupuesto. Ve al Paso 2.</div>',
                    unsafe_allow_html=True); st.stop()

    ing = cargar_ingestor()
    mon = st.session_state.proyecto.get("moneda","EUR")
    id_p = st.session_state.proyecto.get("nombre","PROY").replace(" ","_").replace("/","_")[:20].upper()

    st.markdown(f"**Hojas:** {', '.join(ppto)}  ·  **Moneda:** {mon}")

    if st.button("🚀 Procesar presupuesto"):
        with st.spinner(f"Procesando {len(ppto)} hoja(s)..."):
            res = ing.procesar_archivo(st.session_state.archivo_bytes,
                                       st.session_state.archivo_nombre,
                                       id_p, mon, hojas_sel=ppto)
            st.session_state.partidas_master = res["partidas_master"]
            st.session_state.log_ingesta     = res["logs"]
            st.session_state.resumen_ingesta = res["resumen"]
        pm = st.session_state.partidas_master
        if pm.empty:
            st.error("No se extrajeron partidas. Revisa el tipado en el Paso 2.")
        else:
            r = res["resumen"]
            st.success(f"✓ {r['total_partidas']} partidas · "
                       f"{r['total_importe']:,.0f} {mon} · "
                       f"{r['pct_clasificadas']}% clasificadas")

    pm = st.session_state.partidas_master
    if not pm.empty:
        r  = st.session_state.resumen_ingesta
        im = float(pd.to_numeric(pm["importe_proyecto"], errors="coerce").sum())
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Partidas", f"{len(pm):,}")
        c2.metric(f"Importe ({mon})", f"{im:,.0f}")
        c3.metric("Clasificadas", f"{r.get('clasificadas',0)}/{len(pm)}")
        c4.metric("Descuadres", r.get("con_descuadre",0))
        with st.expander("📋 Detalle por hoja", expanded=False):
            for log in st.session_state.log_ingesta:
                n   = log.get("partidas_con_importe",0)
                cn  = log.get("columnas",{})
                nat = f" | NAT='{log.get('col_nat')}'" if log.get("col_nat") else ""
                st.markdown(f"**{log['hoja']}** — {n} partidas · "
                            f"desc=`{cn.get('descripcion','?')}` · "
                            f"precio=`{cn.get('precio','?')}`{nat}")
                for e in log.get("errores",[]): st.warning(e)
        st.info("✅ Avanza al Paso 4 para revisar las partidas.")

# ══════════════════════════════════════════════════════════════════════════════
# P4 — REVISAR
# ══════════════════════════════════════════════════════════════════════════════
elif paso == "4. Revisar":
    st.markdown("""<div class="step-hdr"><h2>Paso 4 · Revisar partidas_master</h2>
    <p>Familias, Pareto, sin clasificar, descuadres y revisión manual</p></div>""",
    unsafe_allow_html=True)

    pm = st.session_state.partidas_master
    if pm.empty:
        st.markdown('<div class="box-red">⚠️ Sin partidas. Completa el Paso 3.</div>',
                    unsafe_allow_html=True); st.stop()

    ing = cargar_ingestor()
    mon = st.session_state.proyecto.get("moneda","EUR")
    imp_total = pd.to_numeric(pm["importe_proyecto"], errors="coerce").sum()
    sin_clas  = int((pm.get("codigo_familia_auto",pd.Series())=="TRV-99").sum())
    analizables = int(pm.get("analizar",pd.Series(dtype=bool)).sum())

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Partidas", f"{len(pm):,}")
    c2.metric(f"Importe ({mon})", f"{imp_total:,.0f}")
    c3.metric("Para analizar", str(analizables))
    c4.metric("Sin clasificar", str(sin_clas))
    c5.metric("Descuadres", len(ing.audit_descuadres(pm)))

    t_fam, t_par, t_sin, t_tbl, t_dsc = st.tabs(
        ["📊 Familias","🎯 Pareto","❓ Sin clasificar","📋 Tabla completa","⚠️ Descuadres"])

    with t_fam:
        rf = ing.resumen_familias(pm)
        if not rf.empty:
            def hl(row): return ["background:#fff3cd"]*len(row) if row["Código"]=="TRV-99" else [""]*len(row)
            st.dataframe(rf.style.apply(hl,axis=1), use_container_width=True, hide_index=True)

    with t_par:
        pm_p = pm[pm.get("analizar",False)==True].copy()
        if not pm_p.empty:
            imp_p = pd.to_numeric(pm_p["importe_proyecto"],errors="coerce").sum()
            pct_p = imp_p/imp_total*100 if imp_total else 0
            st.metric("% importe cubierto", f"{pct_p:.1f}%", delta=f"{len(pm_p)} partidas")
            cs = [c for c in ["codigo_original","descripcion_limpia","unidad_norm","medicion",
                               "precio_proyecto","importe_proyecto","codigo_familia_auto",
                               "subfamilia_nombre_auto","confianza_clasificacion"] if c in pm_p.columns]
            st.dataframe(pm_p[cs].sort_values("importe_proyecto",ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.info("No hay partidas marcadas para análisis.")

    with t_sin:
        pm_sin = pm[pm.get("codigo_familia_auto","")=="TRV-99"].copy()
        baja_conf = pm[pd.to_numeric(pm.get("confianza_clasificacion",0),errors="coerce").fillna(0)<70]
        dudosas_total = len(set(pm_sin.index.tolist() + baja_conf.index.tolist()))
        if not pm_sin.empty:
            imp_s = pd.to_numeric(pm_sin["importe_proyecto"],errors="coerce").sum()
            pct_s = imp_s/imp_total*100 if imp_total else 0
            st.markdown(f"**{len(pm_sin)} sin clasificar · {imp_s:,.0f} {mon} ({pct_s:.1f}%)**")
            cs2 = [c for c in ["codigo_original","descripcion_limpia","importe_proyecto","ruta_capitulo"] if c in pm_sin.columns]
            st.dataframe(pm_sin[cs2].sort_values("importe_proyecto",ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.markdown('<div class="box-ok">✅ Todas las partidas tienen familia asignada.</div>',
                        unsafe_allow_html=True)

        # ── IA opcional para partidas dudosas ──────────────────────────────────
        st.markdown("---")
        try:
            from ai_utils import (ia_disponible, nombre_proveedor, instrucciones_configuracion,
                                   clasificar_dudosas_con_ia, aplicar_sugerencias_ia)
            hay_ia = ia_disponible()
        except Exception:
            hay_ia = False
            def nombre_proveedor(): return "sin configurar"
            def instrucciones_configuracion(): return "ai_utils.py no encontrado en el repositorio."

        col_ia1, col_ia2 = st.columns([1,3])
        usar_ia = col_ia1.toggle(
            f"Activar IA",
            value=False, disabled=not hay_ia, key="toggle_ia",
            help=nombre_proveedor() if hay_ia else "Sin IA configurada"
        )
        if not hay_ia:
            with col_ia2:
                with st.expander("⚙️ Cómo configurar la IA (opcional)", expanded=False):
                    st.markdown(instrucciones_configuracion())
                st.caption("La app funciona sin IA. Las reglas cubren el 70-80% de los casos habituales.")

        if usar_ia and hay_ia:
            col_ia2.markdown(f"**{dudosas_total} partidas candidatas** (TRV-99 o confianza < 70%). ")
            max_p = st.slider("Máximo de partidas a enviar a la IA", 5, 50, 20, key="max_ia")
            umbral_ap = st.slider("Umbral de confianza para aplicar sugerencia (%)", 50, 95, 75, key="umbral_ia")

            if st.button("🤖 Analizar partidas dudosas con IA", key="btn_ia"):
                candidatas = pd.concat([pm_sin, baja_conf]).drop_duplicates()
                with st.spinner(f"Enviando {min(len(candidatas), max_p)} partidas a {nombre_proveedor()}..."):
                    sugerencias, error = clasificar_dudosas_con_ia(candidatas, max_partidas=max_p)
                if error:
                    st.error(f"Error IA: {error}")
                elif sugerencias is not None:
                    st.markdown(f"**IA sugirió clasificación para {len(sugerencias)} partidas:**")
                    st.dataframe(sugerencias, use_container_width=True, hide_index=True)
                    if st.button("✅ Aplicar sugerencias al master (pendientes de revisión)", key="btn_aplicar_ia"):
                        pm_upd, n_act = aplicar_sugerencias_ia(pm, sugerencias, umbral_ap)
                        st.session_state.partidas_master = pm_upd
                        st.success(f"✓ {n_act} partidas actualizadas. Revisa y valida en la pestaña Tabla completa.")
                        st.rerun()

    with t_tbl:
        st.caption("Filtra y corrige clasificaciones. Guarda al terminar.")
        fc1,fc2,fc3 = st.columns(3)
        ff = fc1.selectbox("Familia", ["Todas"]+sorted(pm.get("codigo_familia_auto",
                            pd.Series()).dropna().unique().tolist()), key="ff_t")
        fr = fc2.selectbox("Estado", ["Todos","Pendiente","Revisado","Validado"], key="fr_t")
        fa = fc3.selectbox("Analizar", ["Todos","Sí","No"], key="fa_t")
        pm_s2 = pm.copy()
        if ff!="Todas": pm_s2 = pm_s2[pm_s2.get("codigo_familia_auto","") == ff]
        if fr!="Todos": pm_s2 = pm_s2[pm_s2.get("estado_revision","") == fr]
        if fa=="Sí":  pm_s2 = pm_s2[pm_s2.get("analizar",False)==True]
        elif fa=="No": pm_s2 = pm_s2[pm_s2.get("analizar",False)==False]
        CE = [c for c in ["analizar","codigo_original","descripcion_limpia","unidad_norm",
                           "medicion","precio_proyecto","importe_proyecto",
                           "codigo_familia_auto","subfamilia_nombre_auto",
                           "estado_revision","observaciones"] if c in pm_s2.columns]
        edited = st.data_editor(pm_s2[CE],
            column_config={
                "analizar": st.column_config.CheckboxColumn("Analizar"),
                "importe_proyecto": st.column_config.NumberColumn("Importe", format="%.0f"),
                "precio_proyecto":  st.column_config.NumberColumn("P.Unit",  format="%.2f"),
                "medicion":         st.column_config.NumberColumn("Medición",format="%.2f"),
                "estado_revision":  st.column_config.SelectboxColumn("Estado",
                    options=["Pendiente","Revisado","Validado","Excluir"]),
            },
            use_container_width=True, num_rows="fixed", height=420, key="tbl_edit")
        if st.button("💾 Guardar cambios"):
            st.session_state.partidas_master.update(edited)
            st.success("✓ Guardado")

    with t_dsc:
        dd = ing.audit_descuadres(pm)
        if not dd.empty:
            st.markdown(f"**{len(dd)} partidas con descuadre >0.5%**")
            st.caption("Causas: coeficientes de descuento, redondeos, columnas mal detectadas.")
            st.dataframe(dd, use_container_width=True, hide_index=True)
        else:
            st.markdown('<div class="box-ok">✅ Sin descuadres significativos.</div>',
                        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# P5 — EXPORTAR
# ══════════════════════════════════════════════════════════════════════════════
elif paso == "5. Exportar":
    st.markdown("""<div class="step-hdr"><h2>Paso 5 · Exportar control</h2>
    <p>Excel técnico con partidas_master para auditoría y seguimiento</p></div>""",
    unsafe_allow_html=True)

    pm = st.session_state.partidas_master
    if pm.empty:
        st.markdown('<div class="box-red">⚠️ Sin partidas. Completa los pasos anteriores.</div>',
                    unsafe_allow_html=True); st.stop()

    p   = st.session_state.proyecto
    mon = p.get("moneda","EUR")
    ing = cargar_ingestor()
    imp = pd.to_numeric(pm["importe_proyecto"], errors="coerce").sum()
    sin = int((pm.get("codigo_familia_auto","")=="TRV-99").sum())
    pm_par = pm[pm.get("analizar",False)==True]
    pm_sin = pm[pm.get("codigo_familia_auto","")=="TRV-99"]
    dd      = ing.audit_descuadres(pm)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Partidas",f"{len(pm):,}")
    c2.metric(f"Importe ({mon})",f"{imp:,.0f}")
    c3.metric("Para analizar",len(pm_par))
    c4.metric("Sin clasificar",sin)

    st.markdown("**Hojas que se exportarán:**")
    hojas_exp = ["RESUMEN_Familias","PARTIDAS_MASTER","PARA_ANALIZAR","SIN_CLASIFICAR","PARAMETROS"]
    if not dd.empty: hojas_exp.append("DESCUADRES")
    st.code("  ·  ".join(hojas_exp))

    if st.button("📥 Generar Excel de control"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            rf = ing.resumen_familias(pm)
            if not rf.empty: rf.to_excel(w, sheet_name="RESUMEN_Familias", index=False)
            pm.to_excel(w, sheet_name="PARTIDAS_MASTER", index=False)
            if not pm_par.empty: pm_par.to_excel(w, sheet_name="PARA_ANALIZAR", index=False)
            if not pm_sin.empty: pm_sin.to_excel(w, sheet_name="SIN_CLASIFICAR", index=False)
            if not dd.empty:     dd.to_excel(w,  sheet_name="DESCUADRES",   index=False)
            params = {
                "Proyecto":p.get("nombre",""),"Tipología":p.get("tipologia",""),
                "País":p.get("pais",""),"Moneda":mon,
                "Presupuesto":p.get("presupuesto_texto",""),
                "Responsable":p.get("responsable",""),
                "Fecha exportación":datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Total partidas":len(pm),"Importe total":round(float(imp),2),
                "Sin clasificar":sin,
            }
            pd.DataFrame(list(params.items()),columns=["Parámetro","Valor"]).to_excel(
                w, sheet_name="PARAMETROS", index=False)
        buf.seek(0)
        nom = f"Master_{p.get('nombre','licitacion').replace(' ','_')[:25]}_{date.today()}.xlsx"
        st.download_button("📥 Descargar Excel", data=buf, file_name=nom,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown(f'<div class="box-ok">✅ Excel generado: {" · ".join(hojas_exp)}</div>',
                    unsafe_allow_html=True)
