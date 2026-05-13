"""
ingesta.py  v2
Módulo de ingesta de presupuestos — capa fiable de datos.

Convierte cualquier Excel de presupuesto en partidas_master normalizada,
clasificada y auditable. Incluye:
  - Detección de cabecera por scoring (compatible con Presto)
  - Columna Nat opcional: Capítulo / Partida / Texto / Total
  - Unión de descripciones multilínea
  - Filtro fuerte de totales y subtotales
  - Auditoría de importes (original vs calculado, descuadre)
  - Campos completos de trazabilidad y clasificación con códigos estables
"""

import pandas as pd
import numpy as np
import unicodedata
from io import BytesIO
from datetime import datetime


# ─── Normalización ─────────────────────────────────────────────────────────────

def normalizar_texto(s: str) -> str:
    """Minúsculas + eliminación de tildes. Compartida con clasificador.py."""
    s = str(s).lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


# ─── Scoring para detección de cabecera ───────────────────────────────────────

SCORING = {
    "codigo":      (["codigo", "cod", "ref", "partida", "item", "numero", "num"], 2),
    "nat":         (["nat", "naturaleza", "tipo", "nature", "clase"], 2),
    "unidad":      (["ud", "unidad", "um", "u.m.", "unit", "uni"], 2),
    "descripcion": (["descripcion", "resumen", "concepto", "texto", "description",
                     "denominacion", "detalle", "nombre"], 3),
    "medicion":    (["medicion", "cantidad", "canpres", "qty", "quantity",
                     "q", "med", "cant"], 3),
    "precio":      (["precio", "pres", "p.u.", "pu", "precio unitario", "tarifa",
                     "unitario", "eur/ud", "e/ud"], 3),
    "importe":     (["importe", "imppres", "total", "parcial", "amount",
                     "coste total", "presupuesto"], 3),
}

# Palabras que indican fila de total/resumen — se ignoran como partidas
TOTAL_PALABRAS = {normalizar_texto(p) for p in [
    "total", "subtotal", "sub-total", "suma", "pem", "pec",
    "total capitulo", "total capítulo", "total parcial",
    "presupuesto de ejecucion material", "gastos generales",
    "beneficio industrial", "presupuesto de contrata",
    "importe capitulo", "importe capítulo", "total presupuesto",
    "resumen presupuesto", "total general", "total obra",
]}

# Palabras que indican fila de capítulo
CAPITULO_PALABRAS = {normalizar_texto(p) for p in [
    "capítulo", "capitulo", "cap.", "cap", "chapter",
    "apartado", "título", "titulo", "subcapítulo", "subcapitulo",
    "epígrafe", "epigrafe", "section", "bloque",
]}

# Valores de la columna Nat por categoría
NAT_CAPITULO = {normalizar_texto(v) for v in
                ["capítulo", "capitulo", "cap", "chapter", "cap.", "c", "resumen"]}
NAT_PARTIDA  = {normalizar_texto(v) for v in
                ["partida", "part", "item", "pa", "p", "precio"]}
NAT_TEXTO    = {normalizar_texto(v) for v in
                ["texto", "text", "descripción", "descripcion", "info",
                 "información", "nota", "observacion"]}
NAT_TOTAL    = {normalizar_texto(v) for v in
                ["total", "subtotal", "sub-total", "suma"]}

UNIDADES_NORM = {normalizar_texto(k): v for k, v in {
    "m3":"m³","m³":"m³","m2":"m²","m²":"m²","ml":"ml","m":"ml",
    "kg":"kg","t":"t","tn":"t","tm":"t","ud":"ud","u":"ud",
    "pa":"PA","h":"h","hora":"h",
}.items()}


class IngestorPresupuesto:

    def __init__(self, ruta_reglas: str = "reglas.csv", api_secrets: dict = None):
        self.api_secrets = api_secrets or {}
        self._clasificador = None
        try:
            from clasificador import Clasificador
            self._clasificador = Clasificador(ruta_reglas)
        except Exception:
            pass

    # ── Utilidades ─────────────────────────────────────────────────────────────

    def _num(self, v) -> float | None:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            f = float(v)
            return None if (f != f or abs(f) == float("inf")) else f
        s = str(v).strip().replace(" ", "").replace("€", "").replace("$", "").replace("\xa0", "")
        if not s or s in {"-", "—", "n/a"}:
            return None
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            f = float(s)
            return None if (f != f or abs(f) == float("inf")) else f
        except (ValueError, OverflowError):
            return None

    def _uni(self, u: str) -> str:
        if not u:
            return ""
        return UNIDADES_NORM.get(normalizar_texto(str(u).strip()), str(u).strip())

    def _col_letra(self, i: int) -> str:
        result, n = "", i + 1
        while n > 0:
            n, r = divmod(n - 1, 26)
            result = chr(65 + r) + result
        return result

    def _celda_no_vacia(self, v) -> bool:
        return v is not None and str(v).strip() not in {"", "nan", "None", "NaN"}

    # ── Lectura de Excel ───────────────────────────────────────────────────────

    def leer_todas_hojas(self, bytes_: bytes, nombre: str) -> dict:
        """Devuelve {nombre_hoja: df_raw} con todas las hojas no vacías."""
        hojas = {}
        try:
            xls = pd.ExcelFile(BytesIO(bytes_))
            for hoja in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name=hoja, header=None, dtype=str)
                    df = df.where(df.notna(), None)
                    if len(df) >= 3:
                        hojas[hoja] = df
                except Exception:
                    continue
        except Exception as e:
            raise ValueError(f"Error leyendo {nombre}: {e}")
        return hojas

    # ── Detección de cabecera por scoring ──────────────────────────────────────

    def detectar_cabecera(self, df_raw: pd.DataFrame) -> int:
        """
        Devuelve índice de la fila cabecera usando scoring por palabras clave.
        Compatible con salidas Presto: Código, Nat, Ud, Resumen, CanPres, Pres, ImpPres.
        """
        mejor_fila, mejor_score = 0, -1

        for i in range(min(30, len(df_raw))):
            celdas = [normalizar_texto(str(v))
                      for v in df_raw.iloc[i] if self._celda_no_vacia(v)]
            if len(celdas) < 2:
                continue

            score = 0
            grupos = set()
            for grupo, (palabras, pts) in SCORING.items():
                for cel in celdas:
                    if any(p in cel for p in palabras):
                        score += pts
                        grupos.add(grupo)
                        break

            # Bonus fuerte: tiene descripcion + (precio o importe) → muy probable cabecera
            if "descripcion" in grupos and ("precio" in grupos or "importe" in grupos):
                score += 5

            if score > mejor_score:
                mejor_score = score
                mejor_fila = i

        return mejor_fila

    def aplicar_cabecera(self, df_raw: pd.DataFrame, header_row: int) -> pd.DataFrame:
        """Aplica la fila como cabecera y devuelve DataFrame limpio."""
        cols = []
        visto = {}
        for j, v in enumerate(df_raw.iloc[header_row]):
            nombre = str(v).strip() if self._celda_no_vacia(v) else f"col_{j}"
            if nombre in visto:
                visto[nombre] += 1
                nombre = f"{nombre}_{visto[nombre]}"
            else:
                visto[nombre] = 0
            cols.append(nombre)

        df = df_raw.iloc[header_row + 1:].copy()
        df.columns = cols
        df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)

        # Intentar convertir columnas numéricas donde sea posible
        for col in df.columns:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() > df[col].notna().sum() * 0.3:
                df[col] = converted

        return df

    # ── Detección de columnas ──────────────────────────────────────────────────

    def _match_columna(self, col_n: str, palabras: list) -> bool:
        """
        Evita falsos positivos en detección de columnas.
        Tokens cortos (<=2 chars): solo match exacto o token completo.
        Tokens largos: coincidencia por inclusión también permitida.
        """
        tokens = set(col_n.replace(".", " ").replace("_", " ")
                         .replace("-", " ").replace("/", " ").split())
        for p in palabras:
            p_n = normalizar_texto(p)
            if len(p_n) <= 2:
                # Corto: solo exacto o token aislado
                if col_n == p_n or p_n in tokens:
                    return True
            else:
                # Largo: exacto, token completo o substring
                if col_n == p_n or p_n in tokens or p_n in col_n:
                    return True
        return False

    def detectar_columnas(self, df: pd.DataFrame) -> dict:
        """Detecta columnas por nombre. Fallback numérico para precio/importe."""
        cols_n = {c: normalizar_texto(str(c)) for c in df.columns}
        result = {g: None for g in SCORING}

        # Orden explícito: campos fuertes primero para evitar capturas erróneas
        ORDEN = ["codigo", "nat", "descripcion", "precio", "importe",
                 "medicion", "unidad"]
        for grupo in ORDEN:
            palabras, _ = SCORING[grupo]
            for col, col_n in cols_n.items():
                if result[grupo] is None and self._match_columna(col_n, palabras):
                    if col not in {v for v in result.values() if v}:
                        result[grupo] = col
                    break

        # Fallback numérico si precio o importe no se detectaron
        if result["importe"] is None or result["precio"] is None:
            num_info = []
            for col in df.columns:
                nums = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(nums) > len(df) * 0.2:
                    num_info.append((col, float(nums.max()), float(nums.sum())))
            num_info.sort(key=lambda x: x[2], reverse=True)
            assigned = {v for v in result.values() if v}
            for col, max_v, total_v in num_info:
                if col not in assigned:
                    if result["importe"] is None:
                        result["importe"] = col
                        assigned.add(col)
                    elif result["precio"] is None and max_v < 1_000_000:
                        result["precio"] = col
                        assigned.add(col)

        return result

    # ── Clasificación de tipo de fila ──────────────────────────────────────────

    def _tipo_fila(self, row: pd.Series, cols: dict) -> str:
        """
        Clasifica una fila como:
        Capítulo / Partida / Texto continuación / Total / Desconocido
        Si existe columna Nat, tiene prioridad absoluta.
        """
        col_nat  = cols.get("nat")
        col_desc = cols.get("descripcion")
        col_cod  = cols.get("codigo")
        col_pu   = cols.get("precio")
        col_imp  = cols.get("importe")

        # 1. Columna Nat tiene prioridad
        if col_nat:
            nat = normalizar_texto(str(row.get(col_nat, "") or ""))
            if nat in NAT_CAPITULO: return "Capítulo"
            if nat in NAT_PARTIDA:  return "Partida"
            if nat in NAT_TEXTO:    return "Texto continuación"
            if nat in NAT_TOTAL:    return "Total"

        desc = normalizar_texto(str(row.get(col_desc, "") or "")) if col_desc else ""
        cod  = normalizar_texto(str(row.get(col_cod, "") or "")) if col_cod else ""
        pu   = self._num(row.get(col_pu))  if col_pu  else None
        imp  = self._num(row.get(col_imp)) if col_imp else None

        # 2. Total por descripción
        if desc and (any(desc.startswith(p) for p in TOTAL_PALABRAS)
                     or desc in TOTAL_PALABRAS):
            return "Total"

        # 3. Capítulo por descripción
        if desc and any(desc.startswith(p) for p in CAPITULO_PALABRAS):
            return "Capítulo"

        # 4. Sin descripción → descartable
        if not desc:
            return "Desconocido"

        # 4b. Partida alzada: unidad PA + importe > 0 (aunque no tenga precio unitario)
        col_uni_ = cols.get("unidad")
        uni_ = normalizar_texto(str(row.get(col_uni_, "") or "")) if col_uni_ else ""
        es_pa = uni_ in {"pa", "p.a.", "partida alzada", "alzada"}
        if es_pa and imp is not None and imp > 0:
            return "Partida"

        # 5. Tiene precio → Partida
        if pu is not None and pu > 0:
            return "Partida"

        # 6. Tiene importe pero no precio → Capítulo/Total (salvo PA)
        if imp is not None and imp > 0 and not (pu and pu > 0):
            return "Capítulo"

        # 7. Sin código y sin precio → texto de continuación
        if not cod and pu is None:
            return "Texto continuación"

        return "Partida"

    # ── Detección de nivel de capítulo ─────────────────────────────────────────

    def _nivel_cap(self, codigo: str) -> int:
        c = str(codigo).strip()
        puntos = c.count(".")
        if puntos == 0 and len(c) <= 3:
            return 1
        if puntos == 1:
            return 2
        return 3

    # ── Extracción de registros ────────────────────────────────────────────────

    def _extraer_registros(self, df: pd.DataFrame, cols: dict,
                           header_row: int = 0) -> list:
        """
        Recorre el DataFrame fila a fila y extrae partidas con jerarquía
        y descripción extendida (multilínea).
        """
        col_desc = cols.get("descripcion")
        col_cod  = cols.get("codigo")
        col_pu   = cols.get("precio")
        col_imp  = cols.get("importe")
        col_med  = cols.get("medicion")
        col_uni  = cols.get("unidad")

        if not col_desc:
            return []

        stack_cap = []        # [(nivel, descripcion)]
        registros = []
        ultima = None         # último registro de partida (para texto multilínea)

        for idx in range(len(df)):
            row = df.iloc[idx]
            tipo = self._tipo_fila(row, cols)
            desc_raw = str(row.get(col_desc, "") or "").strip()

            # Descartar
            if tipo in ("Total", "Desconocido"):
                ultima = None  # romper continuación
                continue

            # Capítulo → actualizar jerarquía
            if tipo == "Capítulo":
                cod = str(row.get(col_cod, "") or "").strip() if col_cod else ""
                nivel = self._nivel_cap(cod) if cod else (len(stack_cap) + 1)
                nivel = max(1, min(nivel, 3))
                stack_cap = [(n, d) for n, d in stack_cap if n < nivel]
                stack_cap.append((nivel, desc_raw))
                ultima = None
                continue

            # Texto de continuación → concatenar a última partida
            if tipo == "Texto continuación":
                if ultima is not None and desc_raw:
                    ultima["descripcion_extendida"] = (
                        ultima["descripcion_extendida"].rstrip() + " " + desc_raw
                    ).strip()
                continue

            # Partida
            cod     = str(row.get(col_cod, "") or "").strip() if col_cod else ""
            pu_raw  = self._num(row.get(col_pu))  if col_pu  else None
            imp_raw = self._num(row.get(col_imp)) if col_imp else None
            med_raw = self._num(row.get(col_med)) if col_med else None
            uni_raw = str(row.get(col_uni, "") or "").strip() if col_uni else ""

            # Excepción partida alzada: si unidad=PA y no hay precio, precio=importe
            if pu_raw is None and imp_raw and imp_raw > 0:
                uni_norm = normalizar_texto(uni_raw)
                if uni_norm in {"pa", "p.a.", "pa.", "alzada"} or (not med_raw or med_raw == 1.0):
                    pu_raw = imp_raw
                    if not med_raw:
                        med_raw = 1.0

            # Importe calculado
            imp_calc = round(pu_raw * med_raw, 4) if (pu_raw and med_raw) else None
            imp_proy = imp_raw if (imp_raw and imp_raw > 0) else imp_calc

            # Excepción PA: precio unitario = importe si no hay precio explícito
            if pu_raw is None and imp_proy and imp_proy > 0:
                uni_check = normalizar_texto(uni_raw)
                if uni_check in {"pa", "p.a.", "partida alzada", "alzada"}:
                    pu_raw = imp_proy  # PA: 1 ud × importe = precio

            # Jerarquía
            cap1 = next((d for n, d in stack_cap if n == 1), "")
            cap2 = next((d for n, d in stack_cap if n == 2), "")
            cap3 = next((d for n, d in stack_cap if n == 3), "")
            ruta = " > ".join(d for _, d in stack_cap if d)

            fila_df    = int(idx) + 1          # fila dentro del DataFrame tras cabecera
            fila_excel = header_row + idx + 2    # fila real en Excel (1-based)

            rec = {
                "fila_origen":            fila_excel,   # fila real Excel
                "header_row":             header_row,
                "fila_df":                fila_df,       # fila relativa post-cabecera
                "tipo_fila_original":     "Partida",
                "codigo_original":        cod,
                "descripcion_original":   desc_raw,
                "descripcion_extendida":  desc_raw,
                "capitulo_1":             cap1,
                "capitulo_2":             cap2,
                "capitulo_3":             cap3,
                "ruta_capitulo":          ruta,
                "unidad_original":        uni_raw,
                "medicion":               med_raw,
                "precio_proyecto":        pu_raw,
                "importe_original_excel": imp_raw,
                "importe_calculado":      imp_calc,
                "importe_proyecto":       imp_proy,
            }
            registros.append(rec)
            ultima = rec

        return registros

    # ── Construcción de partidas_master ────────────────────────────────────────

    def _construir_partidas_master(self, registros: list,
                                   hoja: str, archivo: str,
                                   id_proyecto: str, moneda: str) -> pd.DataFrame:
        if not registros:
            return pd.DataFrame()

        total_imp = sum(r.get("importe_proyecto") or 0 for r in registros)
        TOL_PCT = 0.005   # 0.5%
        TOL_EUR = 1.0     # 1 €
        filas = []

        for i, r in enumerate(registros):
            id_ = f"{id_proyecto}_{hoja[:8]}_{i+1:04d}"
            imp_o = r.get("importe_original_excel")
            imp_c = r.get("importe_calculado")
            imp_p = r.get("importe_proyecto")

            # Auditoría de descuadre
            desc_abs = desc_pct = None
            obs = ""
            if imp_o is not None and imp_c is not None:
                desc_abs = round(imp_o - imp_c, 4)
                if imp_o != 0:
                    desc_pct = round(desc_abs / imp_o * 100, 3)
                    if abs(desc_pct) > TOL_PCT * 100 and abs(desc_abs) > TOL_EUR:
                        obs = (f"Descuadre: original={imp_o:.2f} "
                               f"calculado={imp_c:.2f} ({desc_pct:+.2f}%)")

            pct = round(imp_p / total_imp * 100, 4) if (total_imp and imp_p) else None

            filas.append({
                # Trazabilidad
                "id_partida":               id_,
                "id_proyecto":              id_proyecto,
                "archivo_origen":           archivo,
                "hoja_origen":              hoja,
                "fila_origen":              r["fila_origen"],
                "fila_excel":               r.get("fila_excel", r["fila_origen"]),    # fila real Excel (1-based)
                "fila_df":                  r.get("fila_df"),    # fila post-cabecera
                "tipo_fila_original":       r["tipo_fila_original"],
                "header_row_detectado":     r.get("header_row", 0),
                "es_total_o_subtotal":      False,
                "es_texto_continuacion":    False,
                # Codificación
                "codigo_original":          r["codigo_original"],
                "codigo_normalizado":       r["codigo_original"].upper().strip(),
                # Jerarquía
                "capitulo_1":               r["capitulo_1"],
                "capitulo_2":               r["capitulo_2"],
                "capitulo_3":               r["capitulo_3"],
                "ruta_capitulo":            r["ruta_capitulo"],
                # Descripciones
                "descripcion_original":     r["descripcion_original"],
                "descripcion_limpia":       r["descripcion_extendida"],  # usa texto completo para clasificación
                "descripcion_extendida":    r["descripcion_extendida"],
                # Medición y precio
                "unidad_original":          r["unidad_original"],
                "unidad_norm":              self._uni(r["unidad_original"]),
                "medicion":                 r["medicion"],
                "precio_proyecto":          r["precio_proyecto"],
                "importe_proyecto":         imp_p,
                "importe_original_excel":   imp_o,
                "importe_calculado":        imp_c,
                "descuadre_importe":        desc_abs,
                "descuadre_pct":            desc_pct,
                "moneda":                   moneda,
                "porcentaje_sobre_total":   pct,
                # Clasificación auto
                "codigo_disciplina_auto":   None,
                "disciplina_nombre_auto":   None,
                "codigo_familia_auto":      None,
                "familia_nombre_auto":      None,
                "codigo_subfamilia_auto":   None,
                "subfamilia_nombre_auto":   None,
                "paquete_comparativo":      None,
                "metodo_valoracion":        None,
                "fuente_objetivo":          None,
                "requiere_fuente_actual":   None,
                "criterio_estadistico":     None,
                "criterio_clasificacion":   None,
                "confianza_clasificacion":  0,
                # Clasificación validada (usuario)
                "codigo_familia_validada":  None,
                "familia_validada":         None,
                "codigo_subfamilia_validada": None,
                "subfamilia_validada":      None,
                # Estado
                "requiere_revision":        bool(obs),
                "analizar":                 False,
                "estado_revision":          "Pendiente",
                "criticidad":               None,
                "observaciones":            obs,
                "tags":                     "",
                "fecha_importacion":        datetime.now().strftime("%Y-%m-%d %H:%M"),
                "usuario_revision":         "",
            })

        return pd.DataFrame(filas)

    # ── Clasificación ──────────────────────────────────────────────────────────

    def _clasificar(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._clasificador is None or df.empty:
            return df
        for idx, row in df.iterrows():
            r = self._clasificador.clasificar(
                str(row.get("descripcion_limpia", "") or ""),
                str(row.get("codigo_original", "") or ""),
            )
            df.at[idx, "codigo_disciplina_auto"]  = r["codigo_disciplina"]
            df.at[idx, "disciplina_nombre_auto"]  = r["disciplina"]
            df.at[idx, "codigo_familia_auto"]      = r["codigo_familia"]
            df.at[idx, "familia_nombre_auto"]      = r["familia"]
            df.at[idx, "codigo_subfamilia_auto"]   = r["codigo_subfamilia"]
            df.at[idx, "subfamilia_nombre_auto"]   = r["subfamilia"]
            df.at[idx, "paquete_comparativo"]      = r["paquete_comparativo"]
            df.at[idx, "metodo_valoracion"]        = r["metodo_valoracion"]
            df.at[idx, "fuente_objetivo"]          = r["fuente_objetivo"]
            df.at[idx, "requiere_fuente_actual"]   = r["requiere_fuente_actual"]
            df.at[idx, "criterio_estadistico"]     = r["criterio_estadistico"]
            df.at[idx, "criterio_clasificacion"]   = r["criterio_clasificacion"]
            df.at[idx, "confianza_clasificacion"]  = r["confianza"]
            if r["requiere_revision"]:
                df.at[idx, "requiere_revision"] = True
        return df

    def _pareto(self, df: pd.DataFrame, umbral: float = 0.80) -> pd.DataFrame:
        df = df.copy()
        df["analizar"] = False
        imp = pd.to_numeric(df["importe_proyecto"], errors="coerce").fillna(0)
        total = imp.sum()
        if total == 0:
            return df
        orden = imp.sort_values(ascending=False).index.tolist()
        acum = 0
        for idx in orden:
            acum += imp[idx]
            df.at[idx, "analizar"] = True
            if acum / total >= umbral:
                break
        return df

    # ── Procesamiento de una hoja ──────────────────────────────────────────────

    def procesar_hoja(self, df_raw: pd.DataFrame, hoja: str,
                      archivo: str, id_proyecto: str,
                      moneda: str = "EUR") -> dict:
        log = {
            "hoja": hoja, "filas_raw": len(df_raw),
            "header_row": None, "columnas": {},
            "col_nat": None, "partidas_extraidas": 0,
            "partidas_con_importe": 0, "errores": [],
        }

        # Detectar cabecera
        h = self.detectar_cabecera(df_raw)
        log["header_row"] = h
        df = self.aplicar_cabecera(df_raw, h)

        if df.empty or len(df) < 2:
            log["errores"].append("Hoja vacía tras aplicar cabecera.")
            return {"partidas_master": pd.DataFrame(), "log": log}

        # Detectar columnas
        cols = self.detectar_columnas(df)
        log["columnas"] = {k: v for k, v in cols.items() if v}
        log["col_nat"] = cols.get("nat")

        if not cols.get("descripcion"):
            log["errores"].append("No se detectó columna de descripción.")
            return {"partidas_master": pd.DataFrame(), "log": log}

        # Extraer registros
        registros = self._extraer_registros(df, cols, header_row=h)
        log["partidas_extraidas"] = len(registros)

        if not registros:
            log["errores"].append("No se encontraron partidas válidas.")
            return {"partidas_master": pd.DataFrame(), "log": log}

        # Construir master
        df_m = self._construir_partidas_master(registros, hoja, archivo,
                                               id_proyecto, moneda)

        # Filtrar sin importe ni precio
        mask = (
            pd.to_numeric(df_m["importe_proyecto"], errors="coerce").fillna(0) > 0
        ) | (
            pd.to_numeric(df_m["precio_proyecto"], errors="coerce").fillna(0) > 0
        )
        df_m = df_m[mask].reset_index(drop=True)
        log["partidas_con_importe"] = len(df_m)

        # Clasificar
        if not df_m.empty:
            df_m = self._clasificar(df_m)

        return {"partidas_master": df_m, "log": log}

    # ── Procesamiento de archivo completo ──────────────────────────────────────

    def procesar_archivo(self, bytes_: bytes, nombre: str,
                         id_proyecto: str, moneda: str = "EUR",
                         hojas_sel: list = None) -> dict:
        """
        Procesa un Excel completo. Devuelve:
        partidas_master, logs, hojas_disponibles, resumen, audit.
        """
        hojas_raw = self.leer_todas_hojas(bytes_, nombre)
        if not hojas_raw:
            return {"partidas_master": pd.DataFrame(), "logs": [],
                    "hojas_disponibles": [],
                    "resumen": {"error": "Sin datos legibles"}}

        a_procesar = hojas_sel or list(hojas_raw.keys())
        dfs, logs = [], []
        audit = {
            "archivo": nombre,
            "fecha": datetime.now().isoformat(),
            "hojas_disponibles": list(hojas_raw.keys()),
            "hojas_procesadas": [],
            "hojas_omitidas": [],
        }

        for hoja in a_procesar:
            if hoja not in hojas_raw:
                audit["hojas_omitidas"].append({"hoja": hoja, "motivo": "No existe"})
                continue
            res = self.procesar_hoja(hojas_raw[hoja], hoja, nombre,
                                     id_proyecto, moneda)
            logs.append(res["log"])
            pm = res["partidas_master"]
            if not pm.empty:
                dfs.append(pm)
                audit["hojas_procesadas"].append({
                    "hoja": hoja, "partidas": len(pm),
                    "col_nat": res["log"].get("col_nat"),
                    "errores": res["log"].get("errores", []),
                })
            else:
                audit["hojas_omitidas"].append({
                    "hoja": hoja,
                    "motivo": "; ".join(res["log"].get("errores", ["Sin partidas"])),
                })

        if not dfs:
            return {"partidas_master": pd.DataFrame(), "logs": logs,
                    "hojas_disponibles": list(hojas_raw.keys()),
                    "audit": audit,
                    "resumen": {"error": "Ninguna hoja con datos válidos"}}

        df_final = pd.concat(dfs, ignore_index=True)

        # Recalcular porcentaje global
        total_g = pd.to_numeric(df_final["importe_proyecto"], errors="coerce").sum()
        if total_g > 0:
            df_final["porcentaje_sobre_total"] = (
                pd.to_numeric(df_final["importe_proyecto"], errors="coerce")
                / total_g * 100
            ).round(4)

        df_final = self._pareto(df_final)

        # Resumen
        sin_clas = (df_final.get("codigo_familia_auto",
                                  pd.Series()) == "TRV-99").sum()
        desc_count = (
            pd.to_numeric(df_final.get("descuadre_pct", pd.Series()),
                          errors="coerce").abs() > 0.5
        ).sum()

        resumen = {
            "total_partidas":       len(df_final),
            "total_importe":        round(float(total_g), 2),
            "hojas_procesadas":     len(audit["hojas_procesadas"]),
            "hojas_omitidas":       len(audit["hojas_omitidas"]),
            "para_analizar":        int(df_final.get("analizar",
                                        pd.Series(dtype=bool)).sum()),
            "clasificadas":         len(df_final) - int(sin_clas),
            "sin_clasificar":       int(sin_clas),
            "pct_clasificadas":     round((len(df_final) - int(sin_clas))
                                          / len(df_final) * 100, 1)
                                    if len(df_final) else 0,
            "con_descuadre":        int(desc_count),
            "requieren_revision":   int(df_final.get(
                                        "requiere_revision",
                                        pd.Series(dtype=bool)).sum()),
        }

        return {
            "partidas_master": df_final,
            "logs": logs,
            "hojas_disponibles": list(hojas_raw.keys()),
            "audit": audit,
            "resumen": resumen,
        }

    # ── Resúmenes ──────────────────────────────────────────────────────────────

    # ── Sugerencia de tipo de hoja ────────────────────────────────────────────

    def sugerir_tipo_hoja(self, df_raw: pd.DataFrame) -> dict:
        """
        Analiza una hoja sin procesar y sugiere su tipo para la app.
        Devuelve dict con: tipo_sugerido, score_presupuesto, importe_detectado,
                           header_row, columnas_detectadas, filas, motivo.

        Tipos posibles:
          Presupuesto proyecto    → procesar en partidas_master
          Oferta proveedor        → procesar en fuentes_precio
          Referencia histórica    → procesar en fuentes_precio
          Auxiliar / análisis     → no procesar como presupuesto
          Resumen / dashboard     → ignorar
          Parámetros / listas     → ignorar
          Desconocido             → revisar manualmente
        """
        if df_raw is None or len(df_raw) < 3:
            return {"tipo_sugerido": "Desconocido", "score_presupuesto": 0,
                    "importe_detectado": None, "filas": 0, "motivo": "Hoja vacía"}

        header_row = self.detectar_cabecera(df_raw)
        df = self.aplicar_cabecera(df_raw, header_row)
        cols = self.detectar_columnas(df)

        score = 0
        motivo = []

        # Presencia de columnas clave
        if cols.get("descripcion"): score += 3; motivo.append("desc✓")
        if cols.get("precio"):      score += 3; motivo.append("pu✓")
        if cols.get("importe"):     score += 3; motivo.append("imp✓")
        if cols.get("medicion"):    score += 2; motivo.append("med✓")
        if cols.get("codigo"):      score += 2; motivo.append("cod✓")
        if cols.get("nat"):         score += 1; motivo.append("nat✓")

        # Detectar importe total aproximado
        imp_total = None
        if cols.get("importe"):
            try:
                imp_col = pd.to_numeric(df[cols["importe"]], errors="coerce")
                imp_total = float(imp_col.sum())
                if imp_total > 0:
                    score += 2
            except Exception:
                pass

        # Palabras clave en nombre de hoja o columnas (heurística de tipo)
        col_names = " ".join(normalizar_texto(str(c)) for c in df.columns)

        # Señales de auxiliar/análisis
        if any(p in col_names for p in ["self_performing", "rendimiento", "parametro",
                                         "maquinaria", "mano de obra", "auxiliar"]):
            score -= 3

        # Señales de oferta
        es_oferta = any(p in col_names for p in ["proveedor", "oferta", "licitador"])

        # Señales de resumen
        n_desc_unicas = 0
        if cols.get("descripcion"):
            n_desc_unicas = df[cols["descripcion"]].nunique()
            if n_desc_unicas < 5:
                score -= 2; motivo.append("pocas_desc")

        # Clasificar
        if es_oferta:
            tipo = "Oferta proveedor"
        elif score >= 10:
            tipo = "Presupuesto proyecto"
        elif score >= 6:
            tipo = "Referencia histórica" if "referencia" in col_names else "Presupuesto proyecto"
        elif score >= 3:
            tipo = "Auxiliar / análisis"
        elif imp_total and imp_total > 0 and score < 3:
            tipo = "Resumen / dashboard"
        else:
            tipo = "Desconocido"

        return {
            "tipo_sugerido":      tipo,
            "score_presupuesto":  score,
            "importe_detectado":  round(imp_total, 2) if imp_total else None,
            "header_row":         header_row,
            "columnas_detectadas": {k: v for k, v in cols.items() if v},
            "filas":              len(df),
            "motivo":             ", ".join(motivo),
        }

    def analizar_hojas_archivo(self, bytes_: bytes, nombre: str) -> pd.DataFrame:
        """
        Devuelve tabla con sugerencia de tipo para cada hoja del archivo.
        Útil para mostrar al usuario antes de procesar.
        """
        hojas = self.leer_todas_hojas(bytes_, nombre)
        filas = []
        for hoja, df_raw in hojas.items():
            info = self.sugerir_tipo_hoja(df_raw)
            filas.append({
                "Hoja":              hoja,
                "Filas":             info["filas"],
                "Header detectado":  info["header_row"],
                "Importe detectado": f"{info['importe_detectado']:,.0f} €"
                                     if info["importe_detectado"] else "—",
                "Columnas":          ", ".join(info["columnas_detectadas"].keys()),
                "Tipo sugerido":     info["tipo_sugerido"],
                "Score":             info["score_presupuesto"],
                "Procesar":          info["tipo_sugerido"] in
                                     ("Presupuesto proyecto", "Oferta proveedor",
                                      "Referencia histórica"),
            })
        return pd.DataFrame(filas)


    def resumen_familias(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        df = df.copy()
        df["importe_proyecto"] = pd.to_numeric(
            df["importe_proyecto"], errors="coerce").fillna(0)
        col_cod = "codigo_familia_auto"
        col_nom = "familia_nombre_auto"
        if col_cod not in df.columns:
            return pd.DataFrame()
        agg = df.groupby([col_cod, col_nom], dropna=False).agg(
            partidas=("id_partida", "count"),
            importe=("importe_proyecto", "sum"),
            analizar=("analizar", "sum"),
            confianza=("confianza_clasificacion", "mean"),
        ).reset_index()
        agg.columns = ["Código", "Familia", "Nº", "Importe (€)", "Analizar", "Conf."]
        total = agg["Importe (€)"].sum()
        agg["% s/total"] = (agg["Importe (€)"] / total * 100).round(1).astype(str) + "%"
        agg = agg.sort_values("Importe (€)", ascending=False).reset_index(drop=True)
        agg["Importe (€)"] = agg["Importe (€)"].map("{:,.0f}".format)
        agg["Conf."] = agg["Conf."].round(0).fillna(0).astype(int).astype(str) + "%"
        return agg

    def audit_descuadres(self, df: pd.DataFrame,
                         umbral_pct: float = 0.5) -> pd.DataFrame:
        if df.empty or "descuadre_pct" not in df.columns:
            return pd.DataFrame()
        mask = pd.to_numeric(df["descuadre_pct"],
                             errors="coerce").abs() > umbral_pct
        cols = ["id_partida", "hoja_origen", "fila_origen", "codigo_original",
                "descripcion_original", "medicion", "precio_proyecto",
                "importe_original_excel", "importe_calculado",
                "descuadre_importe", "descuadre_pct"]
        return df[mask][[c for c in cols if c in df.columns]].reset_index(drop=True)
