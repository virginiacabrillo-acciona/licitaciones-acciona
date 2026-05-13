"""
clasificador.py  v2
Motor de clasificación de partidas de presupuesto.

Aplica reglas en este orden:
  1    Excepciones críticas
  1.5  Excepciones de hormigón (ganan sobre rellenos y excavaciones)
  2    Palabras clave técnicas y prefijos de código
  2b   Resolución de conflictos (post-clasificación)
  3    Sin clasificar → TRV-99 + requiere_revision=True

La IA no se aplica en este módulo. Las partidas en TRV-99 quedan
para revisión manual o módulo externo de IA.

Uso:
    from clasificador import Clasificador
    c = Clasificador("reglas.csv")
    r = c.clasificar("HA-30/F/20/IIIb en muros de deposito")
    # r["codigo_familia"] == "CIV-07"
    # r["subfamilia"] == "HA ambiente marino sumergido / equivalente XS2"
"""

import pandas as pd
import re
import unicodedata


# ─── Normalización ─────────────────────────────────────────────────────────────

def normalizar_texto(s: str) -> str:
    """Minúsculas + eliminación de tildes/diacríticos. Aplicar a inputs Y patrones."""
    s = str(s).lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _bool_robusto(valor) -> bool:
    """Si/Sí/TRUE/true/1/X/x/yes → True. Todo lo demás → False."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    # Normalizar antes de comparar: elimina tildes para que Sí == si
    s = normalizar_texto(str(valor))
    return s in {"si", "true", "1", "x", "yes", "y"}


# ─── Catálogo estable de familias ──────────────────────────────────────────────

FAMILIA_NOMBRES = {
    "CIV-01": "Preliminares, implantación y trabajos previos",
    "CIV-02": "Demoliciones, desmontajes y levantados",
    "CIV-03": "Movimiento de tierras",
    "CIV-04": "Contenciones, entibaciones y achiques",
    "CIV-05": "Tratamiento del terreno y cimentaciones especiales",
    "CIV-06": "Cimentaciones y estructuras de hormigón armado",
    "CIV-07": "Encofrados, ferralla y hormigones",
    "CIV-08": "Estructuras metálicas",
    "CIV-09": "Cerrajería, tramex, plataformas y vallados",
    "CIV-10": "Redes enterradas civiles y drenaje",
    "CIV-11": "Obra hidráulica civil",
    "CIV-12": "Obra marítima, captación y emisarios",
    "CIV-13": "Impermeabilización, revestimientos y protección de hormigón",
    "CIV-14": "Arquitectura y acabados",
    "CIV-15": "Urbanización y paisajismo",
    "CIV-16": "Servicios afectados y desvíos",
    "CIV-17": "Gestión de residuos",
    "MEC-01": "Equipos mecánicos de proceso",
    "MEC-02": "Equipos específicos IDAM / OI / desalación",
    "MEC-03": "Tuberías de proceso",
    "MEC-04": "Válvulas, actuadores y compuertas",
    "MEC-05": "Dosificación química y reactivos",
    "MEC-06": "Elevación y manutención",
    "ELE-01": "Alta y media tensión",
    "ELE-02": "Centros de transformación",
    "ELE-03": "Baja tensión, CCM y cuadros",
    "ELE-04": "Variadores, arrancadores y compensación",
    "ELE-05": "Cableado, bandejas y canalizaciones",
    "ELE-06": "Puesta a tierra y protección contra el rayo",
    "ELE-07": "Alumbrado",
    "ELE-08": "Grupos electrógenos, SAI y baterías",
    "ICA-01": "Instrumentación de campo",
    "ICA-02": "Analizadores de proceso",
    "ICA-03": "PLC, RTU y control local",
    "ICA-04": "SCADA y supervisión",
    "ICA-05": "Telecomunicaciones y red OT",
    "ICA-06": "CCTV, control de accesos y seguridad electrónica",
    "MEP-01": "HVAC",
    "MEP-02": "Protección contra incendios",
    "MEP-03": "Fontanería, saneamiento interior y servicios de edificio",
    "TRV-01": "Ingeniería, BIM y documentación técnica",
    "TRV-02": "Permisos, legalizaciones y tasas",
    "TRV-03": "Seguridad y salud",
    "TRV-04": "Control de calidad y laboratorio",
    "TRV-05": "Gestión medioambiental",
    "TRV-06": "Pruebas, commissioning y garantías",
    "TRV-07": "Explotación provisional / mantenimiento durante obras",
    "TRV-08": "Indirectos de obra y medios generales",
    "TRV-99": "Varios / pendiente de clasificar",
}

DISCIPLINA_NOMBRE = {
    "CIV": "Civil", "MEC": "Mecánico", "ELE": "Eléctrico",
    "ICA": "I&C",   "MEP": "Building services", "TRV": "Transversal",
}


def _codigo_a_disciplina(cod: str) -> tuple:
    pref = cod.split("-")[0] if cod else "TRV"
    return pref, DISCIPLINA_NOMBRE.get(pref, "Transversal")


# ─── Conflictos hardcoded (patrones se normalizan en __init__) ─────────────────

_CONFLICTOS_RAW = [
    {"desc": "Bomba + hormigon → bombeo hormigon",
     "a": ["bomba"], "b": ["hormigon"],
     "cod_fam": "CIV-07", "cod_sub": "CIV-07-HOR-BOM", "sub": "Bombeo de hormigón",
     "metodo": "Referencia histórica actualizada", "fuente": "Proveedores bombeo / oferta actual", "confianza": 98},
    {"desc": "Verja/vallado/barandilla + S275/acero → cerrajeria",
     "a": ["verja", "vallado", "barandilla"], "b": ["s275", "s355", "acero laminado"],
     "cod_fam": "CIV-09", "cod_sub": "CIV-09-VAL", "sub": "Vallados / cerrajería",
     "metodo": "Oferta específica", "fuente": "Cerrajero / metálicas", "confianza": 98},
    {"desc": "Tramex/PRFV + estructura metalica → cerrajeria",
     "a": ["tramex", "prfv", "hydroclick"], "b": ["estructura metalica", "s275", "s355"],
     "cod_fam": "CIV-09", "cod_sub": "CIV-09-TRA", "sub": "Tramex / plataformas PRFV",
     "metodo": "Oferta específica", "fuente": "Proveedor PRFV / Hydroclick", "confianza": 98},
    {"desc": "Localizacion servicios + excavacion → servicios afectados",
     "a": ["localizacion de servicios", "servicios afectados", "cata"], "b": ["excavacion"],
     "cod_fam": "CIV-16", "cod_sub": "CIV-16-SER", "sub": "Localización / servicios afectados",
     "metodo": "Proyecto provisional", "fuente": "Empresa detección servicios", "confianza": 98},
    {"desc": "RAEE/PCB/amianto + demolicion → residuos especiales",
     "a": ["raee", "pcb", "amianto", "asbesto"], "b": ["demolicion", "desmontaje", "levantado"],
     "cod_fam": "CIV-17", "cod_sub": "CIV-17-RAE", "sub": "RAEE / residuo especial",
     "metodo": "Tarifa oficial", "fuente": "Gestor RAEE autorizado", "confianza": 98},
    {"desc": "Mac Insular/vertedero + tierras → gestion residuos",
     "a": ["mac insular", "vertedero", "canon"], "b": ["tierras", "excavacion"],
     "cod_fam": "CIV-17", "cod_sub": "CIV-17-TIE", "sub": "Tierras / vertedero",
     "metodo": "Tarifa oficial", "fuente": "BOIB / Mac Insular", "confianza": 98},
    {"desc": "CMC/columnas modulo + excavacion → cimentaciones especiales",
     "a": ["columnas de modulo", "cmc", "inclusiones rigidas"], "b": ["excavacion", "movimiento de tierras"],
     "cod_fam": "CIV-05", "cod_sub": "CIV-05-CMC", "sub": "Columnas de módulo controlado",
     "metodo": "Oferta específica", "fuente": "Subcontrata geotecnia", "confianza": 98},
    {"desc": "Panel sandwich/cubierta + acero → arquitectura",
     "a": ["panel sandwich", "cubierta"], "b": ["acero", "s275", "s355"],
     "cod_fam": "CIV-14", "cod_sub": "CIV-14-CER", "sub": "Cerramientos / cubiertas",
     "metodo": "Oferta específica", "fuente": "Proveedor cerramientos", "confianza": 98},
    {"desc": "Impermeabilizacion/epoxi + hormigon → proteccion hormigon",
     "a": ["impermeabilizacion", "epoxi", "poliurea"], "b": ["hormigon"],
     "cod_fam": "CIV-13", "cod_sub": "CIV-13-IMP", "sub": "Revestimiento protector / impermeabilización",
     "metodo": "Oferta específica", "fuente": "Aplicador especializado", "confianza": 98},
    {"desc": "Variador/VFD + bomba/soplante → gana ELE-04 (variador es electrico, controla equipo)",
     "a": ["variador", "vfd", "arrancador"], "b": ["bomba", "soplante"],
     "cod_fam": "ELE-04", "cod_sub": "ELE-04-VAR", "sub": "Variadores / arrancadores",
     "metodo": "Oferta especifica", "fuente": "Proveedor VFD", "confianza": 96},
    {"desc": "Panel compacto + climatizacion/hvac → MEP",
     "a": ["panel compacto"], "b": ["climatizacion", "hvac", "ventilacion"],
     "cod_fam": "MEP-01", "cod_sub": "MEP-01-HVC", "sub": "HVAC",
     "metodo": "Oferta específica", "fuente": "Instalador HVAC", "confianza": 92},
]

_REFINADOS_RAW = [
    {"p": "xs2",        "fam": "CIV-07", "sub_cod": "CIV-07-HOR-XS2", "sub": "HA ambiente marino sumergido / XS2"},
    {"p": "iiib",       "fam": "CIV-07", "sub_cod": "CIV-07-HOR-XS2", "sub": "HA ambiente marino sumergido / equivalente XS2"},
    {"p": "xs1",        "fam": "CIV-07", "sub_cod": "CIV-07-HOR-XS1", "sub": "HA ambiente marino aereo / XS1"},
    {"p": "iiia",       "fam": "CIV-07", "sub_cod": "CIV-07-HOR-XS1", "sub": "HA ambiente marino aereo / equivalente XS1"},
    {"p": "xs3",        "fam": "CIV-07", "sub_cod": "CIV-07-HOR-XS3", "sub": "HA ambiente XS3"},
    {"p": "iiic",       "fam": "CIV-07", "sub_cod": "CIV-07-HOR-XS3", "sub": "HA ambiente salpicaduras / equivalente XS3"},
    {"p": "hl-",        "fam": "CIV-07", "sub_cod": "CIV-07-HOR-LIM", "sub": "Hormigón de limpieza"},
    {"p": "hm-",        "fam": "CIV-07", "sub_cod": "CIV-07-HOR-MAS", "sub": "Hormigón en masa"},
    {"p": "cara vista", "fam": "CIV-07", "sub_cod": "CIV-07-ENC-CVI", "sub": "Encofrado madera cara vista"},
    {"p": "fenolico",   "fam": "CIV-07", "sub_cod": "CIV-07-ENC-FEN", "sub": "Encofrado industrial / fenólico"},
    {"p": "cimbra",     "fam": "CIV-07", "sub_cod": "CIV-07-ENC-CIM", "sub": "Cimbras y apeos"},
    {"p": "roca",       "fam": "CIV-03", "sub_cod": "CIV-03-EXR",     "sub": "Excavación en roca"},
    {"p": "bataches",   "fam": "CIV-03", "sub_cod": "CIV-03-EXB",     "sub": "Excavación por bataches"},
    {"p": "prestamo",   "fam": "CIV-03", "sub_cod": "CIV-03-REP",     "sub": "Relleno con préstamo"},
]

_SIN_CLASIFICAR = {
    "codigo_disciplina": "TRV", "disciplina": "Transversal",
    "codigo_familia": "TRV-99", "familia": "Varios / pendiente de clasificar",
    "codigo_subfamilia": "TRV-99-SIN", "subfamilia": "Sin clasificar",
    "paquete_comparativo": "", "metodo_valoracion": "",
    "fuente_objetivo": "", "requiere_fuente_actual": False,
    "criterio_estadistico": "Revisión manual obligatoria",
    "confianza": 0, "criterio_clasificacion": "Sin regla aplicable",
    "requiere_revision": True, "id_regla_aplicada": None,
}


class Clasificador:

    def __init__(self, ruta_reglas: str = "reglas.csv"):
        self.reglas = self._cargar_reglas(ruta_reglas)
        self.conflictos = [
            {**c, "a": [normalizar_texto(p) for p in c["a"]],
                  "b": [normalizar_texto(p) for p in c["b"]]}
            for c in _CONFLICTOS_RAW
        ]
        self.refinados = [
            {**r, "p": normalizar_texto(r["p"])} for r in _REFINADOS_RAW
        ]

    def _cargar_reglas(self, ruta: str) -> pd.DataFrame:
        df = pd.read_csv(ruta)
        df["activa"] = df["activa"].apply(_bool_robusto)
        df = df[df["activa"]].copy()
        df["prioridad"] = pd.to_numeric(df["prioridad"], errors="coerce").fillna(99)
        df = df.sort_values(["prioridad", "id_regla"]).reset_index(drop=True)
        for col in ["patron", "patron_adicional", "patron_exclusion"]:
            if col in df.columns:
                df[col] = df[col].fillna("").apply(normalizar_texto)
        return df

    def _coincide(self, regla: pd.Series, desc: str, cod: str, cap: str, uni: str) -> bool:
        campo    = regla.get("campo_objetivo", "descripcion")
        operador = regla.get("operador", "contiene")
        pat      = str(regla.get("patron", ""))
        pat_add  = str(regla.get("patron_adicional", ""))
        pat_exc  = str(regla.get("patron_exclusion", ""))
        if not pat:
            return False
        texto = {"descripcion": desc, "codigo": cod, "capitulo": cap, "unidad": uni}.get(campo, desc)

        if operador == "contiene":
            ok = pat in texto
        elif operador == "empieza_por":
            ok = texto.startswith(pat)
        elif operador == "igual":
            ok = texto == pat
        elif operador == "no_contiene":
            ok = pat not in texto
        elif operador == "contiene_y_no_contiene":
            ok = (pat in texto) and (pat_exc not in texto)
        elif operador == "regex":
            try:
                ok = bool(re.search(pat, texto))
            except re.error:
                ok = False
        else:
            ok = pat in texto

        if not ok:
            return False
        if pat_add and operador != "contiene_y_no_contiene" and pat_add not in texto:
            return False
        if pat_exc and operador != "contiene_y_no_contiene" and pat_exc in texto:
            return False
        return True

    def _resultado_regla(self, regla: pd.Series) -> dict:
        cod_fam = str(regla.get("codigo_familia", "TRV-99")).strip()
        cod_dis, dis = _codigo_a_disciplina(cod_fam)
        return {
            "codigo_disciplina": cod_dis,
            "disciplina": dis,
            "codigo_familia": cod_fam,
            "familia": FAMILIA_NOMBRES.get(cod_fam, cod_fam),
            "codigo_subfamilia": str(regla.get("codigo_subfamilia", "")).strip(),
            "subfamilia": str(regla.get("subfamilia_nombre", regla.get("subfamilia", ""))).strip(),
            "paquete_comparativo": str(regla.get("paquete_comparativo", "")).strip(),
            "metodo_valoracion": str(regla.get("metodo_valoracion", "")).strip(),
            "fuente_objetivo": str(regla.get("fuente_objetivo", "")).strip(),
            "requiere_fuente_actual": _bool_robusto(regla.get("requiere_fuente_actual", False)),
            "criterio_estadistico": str(regla.get("criterio_estadistico", "")).strip(),
            "confianza": int(pd.to_numeric(regla.get("confianza", 80), errors="coerce") or 80),
            "criterio_clasificacion": f"R{regla['id_regla']} ({regla['tipo_regla']}): {regla.get('comentario','')}",
            "requiere_revision": _bool_robusto(regla.get("requiere_revision", True)),
            "id_regla_aplicada": regla["id_regla"],
        }

    def _aplicar_conflictos(self, res: dict, desc: str) -> dict:
        for conf in self.conflictos:
            if any(p in desc for p in conf["a"]) and any(p in desc for p in conf["b"]):
                cod = conf["cod_fam"]
                cod_dis, dis = _codigo_a_disciplina(cod)
                res.update({
                    "codigo_disciplina": cod_dis, "disciplina": dis,
                    "codigo_familia": cod, "familia": FAMILIA_NOMBRES.get(cod, cod),
                    "codigo_subfamilia": conf["cod_sub"], "subfamilia": conf["sub"],
                    "confianza": conf["confianza"],
                    "metodo_valoracion": conf.get("metodo", res.get("metodo_valoracion", "")),
                    "fuente_objetivo": conf.get("fuente", res.get("fuente_objetivo", "")),
                    "criterio_clasificacion": res["criterio_clasificacion"] + f" → CONFLICTO: {conf['desc']}",
                    "requiere_revision": True,
                })
                return res
        return res

    def _refinar_subfamilia(self, res: dict, desc: str) -> dict:
        for ref in self.refinados:
            if ref["fam"] == res.get("codigo_familia") and ref["p"] in desc:
                res["codigo_subfamilia"] = ref["sub_cod"]
                res["subfamilia"] = ref["sub"]
                return res
        return res

    def clasificar(self, descripcion: str, codigo: str = "",
                   capitulo: str = "", unidad: str = "") -> dict:
        desc = normalizar_texto(descripcion)
        cod  = normalizar_texto(codigo)
        cap  = normalizar_texto(capitulo)
        uni  = normalizar_texto(unidad)

        res = None
        for _, regla in self.reglas.iterrows():
            if self._coincide(regla, desc, cod, cap, uni):
                res = self._resultado_regla(regla)
                break

        if res is None:
            return _SIN_CLASIFICAR.copy()

        res = self._aplicar_conflictos(res, desc)
        res = self._refinar_subfamilia(res, desc)
        return res

    def clasificar_lote(self, df: pd.DataFrame,
                        col_desc: str = "Descripción",
                        col_codigo: str = None,
                        col_capitulo: str = None,
                        col_unidad: str = None) -> pd.DataFrame:
        resultados = []
        for _, row in df.iterrows():
            d = str(row.get(col_desc, "")) if col_desc else ""
            c = str(row.get(col_codigo, "")) if col_codigo and col_codigo in df.columns else ""
            ca = str(row.get(col_capitulo, "")) if col_capitulo and col_capitulo in df.columns else ""
            u = str(row.get(col_unidad, "")) if col_unidad and col_unidad in df.columns else ""
            resultados.append(self.clasificar(d, c, ca, u))

        df_res = pd.DataFrame(resultados)
        df_out = df.copy()
        ALIAS = {"codigo_familia": "codigo_familia_auto", "familia": "familia_auto",
                 "codigo_subfamilia": "codigo_subfamilia_auto", "subfamilia": "subfamilia_auto",
                 "metodo_valoracion": "metodo_valoracion_auto"}
        for campo in df_res.columns:
            df_out[ALIAS.get(campo, campo)] = df_res[campo].values
        return df_out

    def estadisticas(self, df: pd.DataFrame) -> dict:
        total = len(df)
        if total == 0:
            return {"total_partidas": 0}
        col_fam = next((c for c in ["codigo_familia_auto","codigo_familia"] if c in df.columns), None)
        sin = (df[col_fam] == "TRV-99").sum() if col_fam else 0
        conf_col = next((c for c in ["confianza"] if c in df.columns), None)
        media = float(df[conf_col].mean()) if conf_col else 0
        return {
            "total_partidas": total,
            "clasificadas": total - int(sin),
            "sin_clasificar": int(sin),
            "pct_clasificadas": round((total - int(sin)) / total * 100, 1),
            "confianza_media": round(media, 1),
            "requieren_revision": int(df.get("requiere_revision", pd.Series(dtype=bool)).sum()),
        }
