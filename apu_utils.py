"""
apu_utils.py
Motor de composición de precios unitarios (APU).

Permite calcular el precio colocado completo de una partida a partir de:
  - Precio de suministro (de fuentes_precio o introducido por el técnico)
  - Precio de bombeo (opcional, si aplica a la partida)
  - Tarifa de mano de obra (del país/zona del proyecto)
  - Rendimiento de colocación (tabla interna o sugerido por IA)
  - Coeficiente de medios auxiliares (por tipo de obra)

Familias actualmente soportadas:
  CIV-07  Encofrados, ferralla y hormigones  → composición completa
  Resto   → precio directo de fuentes sin descomposición (próxima versión)

La IA solo interviene cuando el rendimiento no está en tabla.
El resultado siempre requiere validación del técnico.
"""

import re
import json
import pandas as pd
import numpy as np
import unicodedata
from pathlib import Path


# ─── Normalización ─────────────────────────────────────────────────────────────

def _n(s: str) -> str:
    s = str(s).lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


# ─── Inferencia de tipo de elemento y bombeo ───────────────────────────────────

PATRONES_ELEMENTO = [
    ("losa_horizontal",  ["losa", "forjado", "cubierta", "techo", "solado"]),
    ("muro_alzado",      ["muro", "alzado", "paramento", "pantalla", "tabique",
                          "deposito", "depósito", "cuba", "balsa"]),
    ("cimentacion",      ["zapata", "cimentacion", "cimiento", "losa de cimentacion",
                          "encepado"]),
    ("pilares_columnas", ["pilar", "columna", "soporte"]),
    ("viga",             ["viga", "jácena", "dintel", "zuncho", "riostras"]),
    ("solera",           ["solera", "pavimento", "pavimentacion"]),
    ("limpieza",         ["limpieza", "nivelacion", "regularizacion", "hl-"]),
    ("arqueta_pozo",     ["arqueta", "pozo", "registro", "camara"]),
    ("muro_contencion",  ["contencion", "contencion", "muro de gravedad", "trasdos"]),
    ("general_proceso",  ["xs2", "xs3", "iiib", "iiic", "sumergido", "zona maritima",
                          "zona submarina"]),
]

PATRONES_BOMBEO = [
    "bombeo", "bombeado", "con bomba", "camion bomba",
    "con bombeo", "bombeable",
]

PATRONES_NO_BOMBEO = [
    "sin bombeo", "por cubilote", "por tolva",
]


def inferir_tipo_elemento(descripcion: str, capitulo: str = "") -> str:
    """
    Infiere el tipo de elemento estructural para buscar rendimiento.
    La descripción tiene prioridad sobre el capítulo.
    """
    desc_n = _n(descripcion)
    cap_n  = _n(capitulo)
    # Primero buscar en descripción sola
    for tipo, patrones in PATRONES_ELEMENTO:
        if any(p in desc_n for p in patrones):
            return tipo
    # Si no hay match en descripción, buscar en capítulo
    for tipo, patrones in PATRONES_ELEMENTO:
        if any(p in cap_n for p in patrones):
            return tipo
    return "general"


def inferir_bombeo(descripcion: str) -> bool:
    """Detecta si la partida incluye o requiere bombeo."""
    texto = _n(descripcion)
    if any(p in texto for p in PATRONES_NO_BOMBEO):
        return False
    if any(p in texto for p in PATRONES_BOMBEO):
        return True
    return None  # None = incierto, requiere decisión del técnico


# ─── Motor APU ─────────────────────────────────────────────────────────────────

class MotorAPU:
    """
    Motor de composición de APUs. Instanciar una vez por sesión.
    Las tablas de datos son CSV editables por el técnico.
    """

    def __init__(self,
                 ruta_tarifas: str = "tarifas_personal.csv",
                 ruta_rendimientos: str = "rendimientos.csv",
                 ruta_coeficientes: str = "coeficientes_aux.csv"):
        self.tarifas       = self._leer(ruta_tarifas)
        self.rendimientos  = self._leer(ruta_rendimientos)
        self.coeficientes  = self._leer(ruta_coeficientes)

    def _leer(self, ruta: str) -> pd.DataFrame:
        p = Path(ruta)
        if p.exists():
            return pd.read_csv(p)
        return pd.DataFrame()

    # ── Búsquedas en tablas ───────────────────────────────────────────────────

    def buscar_tarifa(self, pais: str, zona: str = None) -> dict | None:
        """Devuelve la fila de tarifa más específica disponible para el país/zona."""
        if self.tarifas.empty:
            return None
        t = self.tarifas.copy()
        t["_pais_n"]  = t["pais"].apply(_n)
        t["_zona_n"]  = t["zona"].apply(_n)
        pais_n = _n(pais)
        zona_n = _n(zona) if zona else ""

        # Intento exacto pais+zona
        if zona_n:
            filt = t[(t["_pais_n"] == pais_n) & (t["_zona_n"] == zona_n)]
            if not filt.empty:
                return filt.iloc[0].to_dict()

        # Fallback: país + zona General
        filt = t[(t["_pais_n"] == pais_n) & (t["_zona_n"].isin(["general","general"]))]
        if not filt.empty:
            return filt.iloc[0].to_dict()

        return None

    def buscar_rendimiento(self, codigo_familia: str, tipo_elemento: str,
                           incluye_bombeo: bool = False) -> dict | None:
        """Devuelve la fila de rendimiento más ajustada."""
        if self.rendimientos.empty:
            return None
        r = self.rendimientos.copy()
        r["_tipo_n"] = r["tipo_elemento"].apply(_n)
        tipo_n = _n(tipo_elemento)

        # Filtrar por familia
        fam = r[r["codigo_familia"] == codigo_familia].copy()
        if fam.empty:
            fam = r  # sin filtro de familia

        # Filtrar por bombeo si se sabe
        if incluye_bombeo is True:
            match_bomb = fam[fam["incluye_bombeo_base"].apply(
                lambda x: _n(str(x)) in {"si","sí","true","1","yes"})]
            if not match_bomb.empty:
                fam = match_bomb
        elif incluye_bombeo is False:
            match_no_bomb = fam[fam["incluye_bombeo_base"].apply(
                lambda x: _n(str(x)) in {"no","false","0"})]
            if not match_no_bomb.empty:
                fam = match_no_bomb

        # Filtrar por tipo de elemento
        match_tipo = fam[fam["_tipo_n"] == tipo_n]
        if not match_tipo.empty:
            return match_tipo.iloc[0].to_dict()

        # Fallback: tipo parcial
        for _, row in fam.iterrows():
            if tipo_n in row["_tipo_n"] or row["_tipo_n"] in tipo_n:
                return row.to_dict()

        return None

    def buscar_coeficiente(self, tipo_obra: str) -> dict | None:
        """Devuelve coeficiente de medios auxiliares para el tipo de obra."""
        if self.coeficientes.empty:
            return None
        c = self.coeficientes.copy()
        c["_tipo_n"] = c["tipo_obra"].apply(_n)
        tipo_n = _n(tipo_obra)
        match = c[c["_tipo_n"] == tipo_n]
        if not match.empty:
            return match.iloc[0].to_dict()
        # General como fallback
        gen = c[c["_tipo_n"] == "general"]
        if not gen.empty:
            return gen.iloc[0].to_dict()
        return None

    # ── Composición de precio ─────────────────────────────────────────────────

    def componer_hormigon(self,
                          descripcion: str,
                          capitulo: str = "",
                          codigo_familia: str = "CIV-07",
                          precio_suministro: float = None,
                          precio_bombeo: float = None,
                          pais: str = "España",
                          zona: str = None,
                          tipo_obra: str = "General",
                          tipo_elemento_manual: str = None,
                          incluye_bombeo_manual: bool = None,
                          rendimiento_manual: float = None,
                          ) -> dict:
        """
        Compone el precio unitario de 1 m³ de hormigón colocado.

        Devuelve dict con desglose completo y precio final.
        Si falta algún dato necesario, lo marca como None con indicación.
        """
        resultado = {
            "descripcion":            descripcion,
            "pais":                   pais,
            "zona":                   zona,
            "tipo_elemento":          None,
            "incluye_bombeo":         None,
            # Componentes de precio
            "precio_suministro":      precio_suministro,
            "precio_bombeo":          precio_bombeo,
            "tarifa_oficial_hora":    None,
            "tarifa_peon_hora":       None,
            "composicion_cuadrilla":  None,
            "rendimiento_m3h":        None,
            "rendimiento_fuente":     None,
            "precio_mo_calculado":    None,
            "coef_medios_auxiliares": None,
            "precio_auxiliares":      None,
            "precio_total_compuesto": None,
            # Metadatos
            "metodo":                 None,
            "completitud":            "incompleto",
            "datos_faltantes":        [],
            "avisos":                 [],
            "desglose":               {},
        }
        faltantes = []
        avisos = []

        # 1. Inferir tipo de elemento
        tipo_elem = tipo_elemento_manual or inferir_tipo_elemento(descripcion, capitulo)
        resultado["tipo_elemento"] = tipo_elem

        # 2. Inferir bombeo desde descripción; si ambiguo, consultar tabla de rendimientos
        bombeo = incluye_bombeo_manual
        if bombeo is None:
            bombeo = inferir_bombeo(descripcion)
        if bombeo is None:
            # Buscar rendimiento provisional para ver si el tipo recomienda bombeo
            tipo_prov = tipo_elemento_manual or inferir_tipo_elemento(descripcion, capitulo)
            rend_prov = self.buscar_rendimiento(codigo_familia, tipo_prov)
            if rend_prov and _n(str(rend_prov.get("bombeo_recomendado","no"))) in {"si","yes","true","1"}:
                bombeo = True
                avisos.append(f"Bombeo asumido: tipo '{tipo_prov}' lo recomienda en grandes estructuras.")
            else:
                bombeo = False
                avisos.append("Bombeo no detectado en descripción ni recomendado para este tipo. Se asume sin bombeo.")
        resultado["incluye_bombeo"] = bombeo

        # 3. Precio de suministro
        if precio_suministro is None:
            faltantes.append("precio_suministro: introduce el precio de suministro (€/m³)")

        # 4. Precio de bombeo
        if bombeo and precio_bombeo is None:
            faltantes.append("precio_bombeo: la partida parece requerir bombeo. Introduce precio de bombeo (€/m³)")
            avisos.append("Si no tienes precio de bombeo, usa la estimación por defecto según país.")

        # 5. Tarifa de mano de obra
        tarifa = self.buscar_tarifa(pais, zona)
        if tarifa:
            t_of = float(tarifa.get("oficial_1a_hora", 0) or 0)
            t_peon = float(tarifa.get("peon_hora", 0) or 0)
            resultado["tarifa_oficial_hora"] = t_of
            resultado["tarifa_peon_hora"]    = t_peon
        else:
            faltantes.append(f"tarifa_mo: no hay tarifa para '{pais}' en la tabla. Introduce tarifa manualmente.")
            t_of, t_peon = None, None

        # 6. Rendimiento
        if rendimiento_manual:
            rend = rendimiento_manual
            resultado["rendimiento_m3h"]    = rend
            resultado["rendimiento_fuente"] = "manual"
            resultado["composicion_cuadrilla"] = "1 oficial + 1 peón (manual)"
        else:
            rend_row = self.buscar_rendimiento(codigo_familia, tipo_elem, bombeo)
            if rend_row:
                rend = float(rend_row.get("rendimiento_m3h", 0) or 0)
                resultado["rendimiento_m3h"]       = rend
                resultado["rendimiento_fuente"]    = f"tabla ({rend_row.get('fuente','')})"
                resultado["composicion_cuadrilla"] = rend_row.get("composicion_cuadrilla","1 oficial + 1 peón")
                if rend_row.get("rend_min") and rend_row.get("rend_max"):
                    avisos.append(f"Rendimiento típico: {rend_row['rend_min']}–{rend_row['rend_max']} m³/h. Usado: {rend} m³/h.")
            else:
                faltantes.append(f"rendimiento: no hay rendimiento para tipo '{tipo_elem}'. Introduce manualmente o activa sugerencia IA.")
                rend = None

        # 7. Coeficiente medios auxiliares
        coef_row = self.buscar_coeficiente(tipo_obra)
        if coef_row:
            coef_aux = float(coef_row.get("coef_medios_auxiliares", 0.05) or 0.05)
            resultado["coef_medios_auxiliares"] = coef_aux
        else:
            coef_aux = 0.05
            resultado["coef_medios_auxiliares"] = coef_aux
            avisos.append("Usando coeficiente de medios auxiliares por defecto: 5%.")

        # 8. Calcular precio MO
        if t_of is not None and t_peon is not None and rend is not None and rend > 0:
            tarifa_cuadrilla = t_of + t_peon  # 1 oficial + 1 peón por hora
            precio_mo = round(tarifa_cuadrilla / rend, 4)
            resultado["precio_mo_calculado"] = precio_mo
        else:
            precio_mo = None

        # 9. Componer precio total
        componentes = {}
        precio_total = 0.0
        completo = True

        if precio_suministro is not None:
            componentes["Suministro hormigón (€/m³)"] = precio_suministro
            precio_total += precio_suministro
        else:
            completo = False

        if bombeo:
            if precio_bombeo is not None:
                componentes["Bombeo (€/m³)"] = precio_bombeo
                precio_total += precio_bombeo
            else:
                completo = False

        if precio_mo is not None:
            componentes["Mano de obra colocación (€/m³)"] = precio_mo
            precio_total += precio_mo
        else:
            completo = False

        if completo:
            precio_aux = round(precio_total * coef_aux, 4)
            componentes[f"Medios auxiliares ({coef_aux*100:.1f}%)"] = precio_aux
            precio_total = round(precio_total + precio_aux, 4)
            resultado["precio_auxiliares"]      = precio_aux
            resultado["precio_total_compuesto"] = precio_total
            resultado["completitud"] = "completo"
            resultado["metodo"] = "suministro+mo+auxiliares"
        else:
            resultado["completitud"] = "parcial"
            resultado["metodo"] = "faltan componentes"

        resultado["desglose"]        = componentes
        resultado["datos_faltantes"] = faltantes
        resultado["avisos"]          = avisos

        return resultado

    def componer_lote(self, df_master: pd.DataFrame,
                      pais: str, zona: str = None,
                      tipo_obra: str = "General",
                      precios_suministro: dict = None,
                      precios_bombeo: dict = None) -> pd.DataFrame:
        """
        Aplica composición APU a todas las partidas de hormigón del master.

        precios_suministro: {id_partida: precio} — de fuentes_precio si disponible
        precios_bombeo:     {id_partida: precio} — ídem

        Devuelve df_master con columnas APU añadidas.
        """
        if df_master.empty:
            return df_master

        precios_s = precios_suministro or {}
        precios_b = precios_bombeo     or {}

        col_fam  = "codigo_familia_auto" if "codigo_familia_auto" in df_master.columns else None
        col_desc = "descripcion_limpia"  if "descripcion_limpia"  in df_master.columns else "descripcion_original"
        col_cap  = "capitulo_1"          if "capitulo_1"          in df_master.columns else None

        # Solo hormigones para esta versión
        if col_fam:
            mask_hormigon = df_master[col_fam] == "CIV-07"
        else:
            mask_hormigon = pd.Series(True, index=df_master.index)

        # Nuevas columnas APU
        COLS_APU = [
            "apu_tipo_elemento", "apu_incluye_bombeo",
            "apu_precio_suministro", "apu_precio_bombeo",
            "apu_tarifa_oficial_hora", "apu_rendimiento_m3h",
            "apu_rendimiento_fuente", "apu_precio_mo",
            "apu_coef_auxiliares", "apu_precio_auxiliares",
            "apu_precio_compuesto", "apu_metodo",
            "apu_completitud", "apu_avisos",
        ]
        df_out = df_master.copy()
        for col in COLS_APU:
            if col not in df_out.columns:
                df_out[col] = None

        for idx in df_out[mask_hormigon].index:
            row  = df_out.loc[idx]
            id_p = row.get("id_partida", "")
            desc = str(row.get(col_desc, "") or "")
            cap  = str(row.get(col_cap, "") or "") if col_cap else ""
            fam  = str(row.get(col_fam, "CIV-07") or "CIV-07") if col_fam else "CIV-07"

            precio_s = precios_s.get(id_p)
            precio_b = precios_b.get(id_p)

            res = self.componer_hormigon(
                descripcion=desc, capitulo=cap,
                codigo_familia=fam,
                precio_suministro=precio_s,
                precio_bombeo=precio_b,
                pais=pais, zona=zona, tipo_obra=tipo_obra,
            )

            df_out.at[idx, "apu_tipo_elemento"]      = res["tipo_elemento"]
            df_out.at[idx, "apu_incluye_bombeo"]     = res["incluye_bombeo"]
            df_out.at[idx, "apu_precio_suministro"]  = res["precio_suministro"]
            df_out.at[idx, "apu_precio_bombeo"]      = res["precio_bombeo"]
            df_out.at[idx, "apu_tarifa_oficial_hora"]= res["tarifa_oficial_hora"]
            df_out.at[idx, "apu_rendimiento_m3h"]    = res["rendimiento_m3h"]
            df_out.at[idx, "apu_rendimiento_fuente"] = res["rendimiento_fuente"]
            df_out.at[idx, "apu_precio_mo"]          = res["precio_mo_calculado"]
            df_out.at[idx, "apu_coef_auxiliares"]    = res["coef_medios_auxiliares"]
            df_out.at[idx, "apu_precio_auxiliares"]  = res["precio_auxiliares"]
            df_out.at[idx, "apu_precio_compuesto"]   = res["precio_total_compuesto"]
            df_out.at[idx, "apu_metodo"]             = res["metodo"]
            df_out.at[idx, "apu_completitud"]        = res["completitud"]
            df_out.at[idx, "apu_avisos"]             = " | ".join(res["avisos"]) if res["avisos"] else ""

        return df_out

    # ── Resumen APU ───────────────────────────────────────────────────────────

    def resumen_apu(self, df_master: pd.DataFrame) -> pd.DataFrame:
        """Tabla resumen de APUs calculados para visualización."""
        if df_master.empty or "apu_completitud" not in df_master.columns:
            return pd.DataFrame()

        df_apu = df_master[df_master["apu_completitud"].notna()].copy()
        if df_apu.empty:
            return pd.DataFrame()

        col_desc = "descripcion_limpia" if "descripcion_limpia" in df_apu.columns else "descripcion_original"
        cols_show = [c for c in [
            "codigo_original", col_desc,
            "apu_tipo_elemento", "apu_incluye_bombeo",
            "apu_precio_suministro", "apu_precio_bombeo",
            "apu_precio_mo", "apu_precio_auxiliares",
            "apu_precio_compuesto",
            "apu_rendimiento_m3h", "apu_rendimiento_fuente",
            "apu_completitud", "apu_avisos",
        ] if c in df_apu.columns]

        return df_apu[cols_show].reset_index(drop=True)


# ─── Sugerencia de rendimiento via IA ─────────────────────────────────────────

def sugerir_rendimiento_ia(descripcion: str, tipo_elemento: str,
                            pais: str, codigo_familia: str = "CIV-07") -> dict | None:
    """
    Llama a la IA para sugerir rendimientos cuando no están en tabla.
    Devuelve dict con rendimiento_m3h, composicion, rango_min, rango_max, justificacion.
    Devuelve None si no hay IA disponible.
    """
    try:
        import streamlit as st
        from ai_utils import ia_disponible, _llamar_ia, _limpiar_json
    except Exception:
        return None

    if not ia_disponible():
        return None

    prompt = f"""Eres experto en presupuestos de construcción de infraestructuras hidráulicas.

Para la siguiente partida de hormigón, estima el rendimiento de colocación:

Descripción: {descripcion}
Tipo de elemento inferido: {tipo_elemento}
País / contexto: {pais}
Familia técnica: {codigo_familia}

Devuelve SOLO JSON válido con este formato:
{{
  "rendimiento_m3h": 0.40,
  "composicion_cuadrilla": "1 oficial 1ª + 1 peón",
  "rend_min": 0.30,
  "rend_max": 0.55,
  "incluye_bombeo_base": false,
  "justificacion": "Muro alzado de depósito, encofrado a dos caras, vibrado exhaustivo por ambiente agresivo XS2. Rendimiento en rango bajo-medio por complejidad."
}}

Criterios:
- Rendimiento en m³ colocado por hora de cuadrilla (1 oficial + 1 peón salvo indicación)
- Rango razonable según tipo de elemento y condiciones
- Si el tipo de elemento requiere bombeo, indícalo en incluye_bombeo_base"""

    texto, error = _llamar_ia(prompt, max_tokens=600)
    if error or not texto:
        return None

    try:
        return json.loads(_limpiar_json(texto))
    except Exception:
        return None
