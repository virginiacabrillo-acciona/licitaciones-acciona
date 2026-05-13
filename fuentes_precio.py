"""
fuentes_precio.py  — MVP 2
Módulo de gestión de fuentes de precio.

Las fuentes de precio son las entradas que alimentan el análisis comparativo:
  - Ofertas de proveedores (acero, hormigón, bombeo, encofrado, etc.)
  - Referencias históricas de obras propias de Acciona
  - Tarifas oficiales (BOIB, Mac Insular, precios publicados)

Estas fuentes se cargan desde hojas del Excel marcadas como
"Oferta proveedor" o "Referencia histórica" en el Paso 2 de la app,
o se introducen manualmente por el técnico.

Las fuentes se vinculan automáticamente a las partidas del partidas_master
por familia técnica, unidad y similitud de descripción.

Uso:
    from fuentes_precio import GestorFuentes
    g = GestorFuentes()
    g.cargar_desde_hoja(df_raw, nombre_hoja, tipo="oferta_proveedor", ...)
    fuentes = g.fuentes          # DataFrame completo
    vinculadas = g.vincular_a_master(partidas_master)
"""

import pandas as pd
import numpy as np
import unicodedata
import csv
from datetime import datetime
from pathlib import Path


def _n(s: str) -> str:
    s = str(s).lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


TIPOS_FUENTE = [
    "oferta_proveedor",
    "referencia_historica",
    "tarifa_oficial",
]

# Columnas del DataFrame de fuentes_precio
COLS_FUENTES = [
    "id_fuente",
    "tipo_fuente",            # oferta_proveedor | referencia_historica | tarifa_oficial
    "proveedor_origen",       # nombre del proveedor u obra de referencia
    "archivo_origen",
    "hoja_origen",
    "fila_origen",
    "fecha_referencia",       # fecha de la oferta o de la obra
    "moneda",
    "tasa_actualizacion",     # factor para actualizar a precios actuales (ej: 1.05)
    "fecha_actualizacion",    # fecha base de la actualización
    # Descripción del artículo o partida
    "codigo_familia",         # CIV-07, MEC-01, etc.
    "familia_nombre",
    "descripcion_fuente",     # descripción tal como viene en la fuente
    "unidad",
    "codigo_articulo",        # código del artículo en la fuente (si existe)
    # Precios
    "precio_referencia",      # precio unitario en moneda original
    "precio_actualizado",     # precio_referencia × tasa_actualizacion
    "precio_en_eur",          # convertido a EUR si moneda ≠ EUR
    "tipo_cambio_a_eur",      # tipo de cambio usado
    # Vinculación con partidas_master
    "id_partida_vinculada",   # id_partida del master si se vinculó
    "confianza_vinculacion",  # 0-100
    "criterio_vinculacion",   # cómo se vinculó
    # Metadatos
    "valida",                 # True/False — el técnico puede invalidar
    "observaciones",
    "fecha_importacion",
]


class GestorFuentes:
    """
    Gestiona la tabla de fuentes de precio.
    Una instancia por sesión; el DataFrame se serializa en JSON de sesión.
    """

    def __init__(self, ruta_persistencia: str = None):
        self.fuentes = pd.DataFrame(columns=COLS_FUENTES)
        self._contador = 0
        if ruta_persistencia and Path(ruta_persistencia).exists():
            try:
                self.fuentes = pd.read_csv(ruta_persistencia)
                self._contador = len(self.fuentes)
            except Exception:
                pass

    def _nuevo_id(self, tipo: str) -> str:
        self._contador += 1
        pref = {"oferta_proveedor": "OF", "referencia_historica": "REF",
                "tarifa_oficial": "TAR"}.get(tipo, "FP")
        return f"{pref}-{self._contador:04d}"

    # ── Carga desde hoja de Excel ──────────────────────────────────────────────

    def cargar_desde_hoja(self, df_raw: pd.DataFrame, nombre_hoja: str,
                           tipo: str, proveedor_origen: str,
                           nombre_archivo: str,
                           fecha_referencia: str = None,
                           moneda: str = "EUR",
                           tasa_actualizacion: float = 1.0,
                           fecha_actualizacion: str = None,
                           tipo_cambio_eur: float = 1.0) -> tuple[int, list[str]]:
        """
        Carga una hoja de Excel como fuente de precio.
        Devuelve (nº de filas cargadas, lista de advertencias).
        """
        from ingesta import IngestorPresupuesto
        ing = IngestorPresupuesto.__new__(IngestorPresupuesto)
        # Reutilizar la detección de cabecera y columnas
        IngestorPresupuesto.__init__(ing, ruta_reglas="reglas.csv")

        warnings = []
        h_row = ing.detectar_cabecera(df_raw)
        try:
            df = ing.aplicar_cabecera(df_raw, h_row)
            cols = ing.detectar_columnas(df)
        except Exception as e:
            return 0, [f"Error detectando columnas: {e}"]

        col_desc = cols.get("descripcion")
        col_pu   = cols.get("precio")
        col_uni  = cols.get("unidad")
        col_cod  = cols.get("codigo")

        if not col_desc:
            return 0, ["No se detectó columna de descripción. Verifica la hoja."]
        if not col_pu:
            warnings.append("No se detectó columna de precio unitario. Solo se cargará descripción.")

        nuevas = []
        for idx, row in df.iterrows():
            desc = str(row.get(col_desc, "") or "").strip()
            if not desc or _n(desc) in {"", "nan", "none"}:
                continue

            precio_r = ing._num(row.get(col_pu)) if col_pu else None
            if precio_r is None or precio_r <= 0:
                continue  # sin precio no es útil como fuente

            unidad  = str(row.get(col_uni, "") or "").strip() if col_uni else ""
            codigo  = str(row.get(col_cod, "") or "").strip() if col_cod else ""

            precio_act = round(precio_r * tasa_actualizacion, 4)
            precio_eur = round(precio_act / tipo_cambio_eur, 4) if tipo_cambio_eur != 0 else None

            fila = {
                "id_fuente":            self._nuevo_id(tipo),
                "tipo_fuente":          tipo,
                "proveedor_origen":     proveedor_origen,
                "archivo_origen":       nombre_archivo,
                "hoja_origen":          nombre_hoja,
                "fila_origen":          int(idx) + h_row + 2,
                "fecha_referencia":     fecha_referencia or datetime.now().strftime("%Y-%m"),
                "moneda":               moneda,
                "tasa_actualizacion":   tasa_actualizacion,
                "fecha_actualizacion":  fecha_actualizacion or datetime.now().strftime("%Y-%m"),
                "codigo_familia":       None,   # se clasificará después
                "familia_nombre":       None,
                "descripcion_fuente":   desc,
                "unidad":               unidad,
                "codigo_articulo":      codigo,
                "precio_referencia":    precio_r,
                "precio_actualizado":   precio_act,
                "precio_en_eur":        precio_eur,
                "tipo_cambio_a_eur":    tipo_cambio_eur,
                "id_partida_vinculada": None,
                "confianza_vinculacion":0,
                "criterio_vinculacion": None,
                "valida":               True,
                "observaciones":        "",
                "fecha_importacion":    datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            nuevas.append(fila)

        if nuevas:
            df_nuevas = pd.DataFrame(nuevas, columns=COLS_FUENTES)
            self.fuentes = pd.concat([self.fuentes, df_nuevas], ignore_index=True)

        return len(nuevas), warnings

    # ── Añadir precio manual ───────────────────────────────────────────────────

    def añadir_manual(self, tipo: str, proveedor: str, descripcion: str,
                      unidad: str, precio: float, moneda: str = "EUR",
                      tasa_act: float = 1.0, tipo_cambio: float = 1.0,
                      codigo_familia: str = None, observaciones: str = "") -> str:
        """Añade una fuente introducida manualmente. Devuelve el id generado."""
        id_f = self._nuevo_id(tipo)
        precio_eur = round(precio * tasa_act / tipo_cambio, 4) if tipo_cambio else None
        fila = {k: None for k in COLS_FUENTES}
        fila.update({
            "id_fuente":          id_f,
            "tipo_fuente":        tipo,
            "proveedor_origen":   proveedor,
            "archivo_origen":     "manual",
            "hoja_origen":        "manual",
            "fecha_referencia":   datetime.now().strftime("%Y-%m"),
            "moneda":             moneda,
            "tasa_actualizacion": tasa_act,
            "codigo_familia":     codigo_familia,
            "descripcion_fuente": descripcion,
            "unidad":             unidad,
            "precio_referencia":  precio,
            "precio_actualizado": round(precio * tasa_act, 4),
            "precio_en_eur":      precio_eur,
            "tipo_cambio_a_eur":  tipo_cambio,
            "valida":             True,
            "observaciones":      observaciones,
            "fecha_importacion":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        self.fuentes = pd.concat([self.fuentes, pd.DataFrame([fila])],
                                  ignore_index=True)
        return id_f

    # ── Clasificar fuentes ─────────────────────────────────────────────────────

    def clasificar_fuentes(self) -> int:
        """Aplica el clasificador a las fuentes sin familia asignada. Devuelve nº clasificadas."""
        try:
            from clasificador import Clasificador
            c = Clasificador("reglas.csv")
        except Exception:
            return 0

        sin_fam = self.fuentes["codigo_familia"].isna() | (self.fuentes["codigo_familia"] == "")
        n = 0
        for idx in self.fuentes[sin_fam].index:
            desc = str(self.fuentes.at[idx, "descripcion_fuente"] or "")
            r = c.clasificar(desc)
            if r["codigo_familia"] != "TRV-99":
                self.fuentes.at[idx, "codigo_familia"] = r["codigo_familia"]
                self.fuentes.at[idx, "familia_nombre"]  = r["familia"]
                n += 1
        return n

    # ── Vincular a partidas_master ─────────────────────────────────────────────

    def vincular_a_master(self, partidas_master: pd.DataFrame,
                          umbral_confianza: int = 60) -> pd.DataFrame:
        """
        Vincula fuentes de precio a partidas del master.
        Criterios de vinculación (en orden de confianza):
          1. Misma familia + misma unidad + descripción similar → confianza alta
          2. Misma familia + misma unidad → confianza media
          3. Solo misma familia → confianza baja

        Devuelve un DataFrame con las vinculaciones (uno a muchos):
        id_partida → lista de id_fuente con precio y confianza.
        """
        if partidas_master.empty or self.fuentes.empty:
            return pd.DataFrame()

        fuentes_val = self.fuentes[self.fuentes["valida"] == True].copy()
        col_fam = "codigo_familia_auto" if "codigo_familia_auto" in partidas_master.columns \
                  else "familia_auto"

        vinculaciones = []

        for _, pm_row in partidas_master.iterrows():
            id_p   = pm_row.get("id_partida", "")
            fam_p  = str(pm_row.get(col_fam, "") or "")
            uni_p  = _n(str(pm_row.get("unidad_norm", "") or ""))
            desc_p = _n(str(pm_row.get("descripcion_limpia", "") or ""))

            if not fam_p or fam_p == "TRV-99":
                continue

            # Filtrar fuentes de la misma familia
            misma_fam = fuentes_val[fuentes_val["codigo_familia"] == fam_p]
            if misma_fam.empty:
                continue

            for _, f_row in misma_fam.iterrows():
                uni_f  = _n(str(f_row.get("unidad", "") or ""))
                desc_f = _n(str(f_row.get("descripcion_fuente", "") or ""))
                precio_f = f_row.get("precio_en_eur") or f_row.get("precio_actualizado")

                if precio_f is None or float(precio_f or 0) <= 0:
                    continue

                # Calcular confianza de vinculación
                confianza = 40  # base: misma familia
                if uni_p and uni_f and uni_p == uni_f:
                    confianza += 25  # misma unidad
                if desc_f and desc_p:
                    # Similitud por palabras comunes
                    words_p = set(desc_p.split())
                    words_f = set(desc_f.split())
                    if words_p and words_f:
                        common = len(words_p & words_f)
                        total  = len(words_p | words_f)
                        jaccard = common / total if total else 0
                        confianza += int(jaccard * 35)

                if confianza < umbral_confianza:
                    continue

                criterio = "familia"
                if confianza >= 80:
                    criterio = "familia+unidad+descripcion"
                elif confianza >= 65:
                    criterio = "familia+unidad"

                vinculaciones.append({
                    "id_partida":        id_p,
                    "id_fuente":         f_row["id_fuente"],
                    "tipo_fuente":       f_row["tipo_fuente"],
                    "proveedor_origen":  f_row["proveedor_origen"],
                    "descripcion_fuente":f_row["descripcion_fuente"],
                    "unidad_fuente":     f_row["unidad"],
                    "precio_eur":        float(precio_f),
                    "moneda_orig":       f_row["moneda"],
                    "precio_orig":       f_row["precio_referencia"],
                    "tasa_act":          f_row["tasa_actualizacion"],
                    "fecha_referencia":  f_row["fecha_referencia"],
                    "confianza_vinculacion": confianza,
                    "criterio_vinculacion":  criterio,
                })

                # Actualizar campo en tabla de fuentes
                self.fuentes.loc[self.fuentes["id_fuente"] == f_row["id_fuente"],
                                  "id_partida_vinculada"]   = id_p
                self.fuentes.loc[self.fuentes["id_fuente"] == f_row["id_fuente"],
                                  "confianza_vinculacion"]  = confianza
                self.fuentes.loc[self.fuentes["id_fuente"] == f_row["id_fuente"],
                                  "criterio_vinculacion"]   = criterio

        return pd.DataFrame(vinculaciones) if vinculaciones else pd.DataFrame()

    # ── Resúmenes ──────────────────────────────────────────────────────────────

    def resumen_por_familia(self) -> pd.DataFrame:
        """Tabla resumen de fuentes por familia técnica."""
        if self.fuentes.empty:
            return pd.DataFrame()
        f = self.fuentes[self.fuentes["valida"] == True].copy()
        f["precio_en_eur"] = pd.to_numeric(f["precio_en_eur"], errors="coerce")
        agg = f.groupby(["codigo_familia", "familia_nombre", "tipo_fuente"]).agg(
            n_fuentes=("id_fuente", "count"),
            precio_min=("precio_en_eur", "min"),
            precio_mediana=("precio_en_eur", "median"),
            precio_max=("precio_en_eur", "max"),
        ).reset_index()
        agg.columns = ["Familia", "Nombre", "Tipo", "N fuentes",
                       "Mín (€)", "Mediana (€)", "Máx (€)"]
        return agg.sort_values(["Familia", "Tipo"]).reset_index(drop=True)

    def precios_para_apu(self, codigo_familia: str,
                          tipo_fuente: str = None) -> dict:
        """
        Devuelve precios estadísticos para una familia, útil para alimentar APU.
        Si tipo_fuente=None, usa todas las fuentes válidas.
        """
        f = self.fuentes[(self.fuentes["valida"] == True) &
                          (self.fuentes["codigo_familia"] == codigo_familia)].copy()
        if tipo_fuente:
            f = f[f["tipo_fuente"] == tipo_fuente]
        if f.empty:
            return {}
        precios = pd.to_numeric(f["precio_en_eur"], errors="coerce").dropna()
        if precios.empty:
            return {}
        return {
            "n_fuentes":     len(precios),
            "precio_min":    round(float(precios.min()), 4),
            "precio_p25":    round(float(precios.quantile(0.25)), 4),
            "precio_mediana":round(float(precios.median()), 4),
            "precio_media":  round(float(precios.mean()), 4),
            "precio_p75":    round(float(precios.quantile(0.75)), 4),
            "precio_max":    round(float(precios.max()), 4),
            "coef_variacion":round(float(precios.std() / precios.mean() * 100), 1)
                             if precios.mean() != 0 else None,
        }

    def exportar_csv(self, ruta: str):
        """Exporta la tabla de fuentes a CSV."""
        self.fuentes.to_csv(ruta, index=False, quoting=csv.QUOTE_ALL)
