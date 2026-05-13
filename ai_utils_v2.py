"""
ai_utils.py  v2
Capa de IA desacoplada. La app funciona sin IA — las reglas siempre van primero.

Proveedores soportados (en orden de prioridad):
  1. Azure OpenAI  — recomendado si Acciona tiene contrato Microsoft/Azure
  2. OpenAI        — requiere cuenta de pago (desde 5$)
  3. Gemini        — capa gratuita (1500 peticiones/día)
  4. Anthropic     — requiere cuenta de pago

Configuración en Streamlit Secrets (solo el que tengas):
  AZURE_OPENAI_KEY        = "..."
  AZURE_OPENAI_ENDPOINT   = "https://tu-recurso.openai.azure.com"
  AZURE_OPENAI_DEPLOYMENT = "gpt-4o-mini"   # nombre del despliegue en Azure
  OPENAI_API_KEY          = "sk-..."
  GEMINI_API_KEY          = "AIza..."
  ANTHROPIC_API_KEY       = "sk-ant-..."
"""

import json
import requests
import streamlit as st
import pandas as pd


# ─── Detección de proveedores ──────────────────────────────────────────────────

def _tiene(secret: str) -> bool:
    return bool(st.secrets.get(secret, "").strip())

def azure_disponible() -> bool:
    return (_tiene("AZURE_OPENAI_KEY")
            and _tiene("AZURE_OPENAI_ENDPOINT")
            and _tiene("AZURE_OPENAI_DEPLOYMENT"))

def openai_disponible() -> bool:
    return _tiene("OPENAI_API_KEY")

def gemini_disponible() -> bool:
    return _tiene("GEMINI_API_KEY")

def anthropic_disponible() -> bool:
    return _tiene("ANTHROPIC_API_KEY")

def ia_disponible() -> bool:
    return any([azure_disponible(), openai_disponible(),
                gemini_disponible(), anthropic_disponible()])

def nombre_proveedor() -> str:
    if azure_disponible():
        dep = st.secrets.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        return f"Azure OpenAI ({dep})"
    if openai_disponible():
        return "OpenAI GPT-4o mini"
    if gemini_disponible():
        return "Gemini 1.5 Flash"
    if anthropic_disponible():
        return "Claude (Anthropic)"
    return "Sin IA configurada"

def instrucciones_configuracion() -> str:
    """Devuelve instrucciones claras según qué falta."""
    if ia_disponible():
        return f"✅ IA activa: {nombre_proveedor()}"
    return (
        "Para activar la IA, añade en Streamlit → Settings → Secrets una de estas opciones:\n\n"
        "**Azure OpenAI** (recomendado si Acciona tiene contrato Microsoft):\n"
        "`AZURE_OPENAI_KEY = \"...\"` y `AZURE_OPENAI_ENDPOINT = \"https://tu-recurso.openai.azure.com\"`\n\n"
        "**Gemini** (gratuito, 1500 peticiones/día):\n"
        "`GEMINI_API_KEY = \"AIza...\"` — obtén la clave en aistudio.google.com\n\n"
        "**OpenAI**:\n"
        "`OPENAI_API_KEY = \"sk-...\"` — requiere crédito en platform.openai.com"
    )


# ─── Taxonomía ────────────────────────────────────────────────────────────────

def _cargar_taxonomia() -> str:
    try:
        from clasificador import FAMILIA_NOMBRES
        return "\n".join(f"{k}: {v}" for k, v in FAMILIA_NOMBRES.items())
    except Exception:
        return (
            "CIV-01: Preliminares · CIV-02: Demoliciones · CIV-03: Movimiento de tierras\n"
            "CIV-04: Contenciones y achiques · CIV-05: Cimentaciones especiales\n"
            "CIV-06: Estructuras hormigón armado · CIV-07: Encofrados ferralla hormigones\n"
            "CIV-08: Estructuras metálicas · CIV-09: Cerrajería tramex vallados\n"
            "CIV-10: Redes enterradas · CIV-12: Obra marítima captación emisarios\n"
            "CIV-13: Impermeabilización protección hormigón · CIV-14: Arquitectura acabados\n"
            "CIV-15: Urbanización paisajismo · CIV-16: Servicios afectados\n"
            "CIV-17: Gestión de residuos · MEC-01..06: Mecánico\n"
            "ELE-01..08: Eléctrico · ICA-01..06: I&C · MEP-01..03: Building services\n"
            "TRV-01..08: Transversales · TRV-99: Sin clasificar"
        )

DISCIPLINA_POR_PREFIJO = {
    "CIV": "Civil", "MEC": "Mecánico", "ELE": "Eléctrico",
    "ICA": "I&C",   "MEP": "Building services", "TRV": "Transversal",
}

def _disciplina_desde_codigo(codigo_familia: str) -> str:
    pref = str(codigo_familia).split("-")[0].upper()
    return DISCIPLINA_POR_PREFIJO.get(pref, "Transversal")


# ─── Llamada a la IA ──────────────────────────────────────────────────────────

def _llamar_ia(prompt: str, max_tokens: int = 4000) -> tuple[str | None, str | None]:
    """
    Llama al proveedor disponible con fallback ordenado.
    Acumula errores para devolver el más informativo.
    Devuelve (texto_respuesta, mensaje_error).
    """
    errores = []

    # ── 1. Azure OpenAI ────────────────────────────────────────────────────────
    if azure_disponible():
        key      = st.secrets.get("AZURE_OPENAI_KEY", "")
        endpoint = st.secrets.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        deploy   = st.secrets.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        api_v = st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        url = f"{endpoint}/openai/deployments/{deploy}/chat/completions?api-version={api_v}"
        try:
            resp = requests.post(url,
                headers={"Content-Type":"application/json", "api-key": key},
                json={"model": deploy, "temperature": 0.1, "max_tokens": max_tokens,
                      "messages":[{"role":"user","content":prompt}]},
                timeout=30)
            data = resp.json()
            if "error" in data:
                errores.append(f"Azure OpenAI: {data['error'].get('message','error desconocido')}")
            else:
                return data["choices"][0]["message"]["content"].strip(), None
        except Exception as e:
            errores.append(f"Azure OpenAI timeout/red: {e}")

    # ── 2. OpenAI ──────────────────────────────────────────────────────────────
    if openai_disponible():
        key = st.secrets.get("OPENAI_API_KEY", "")
        try:
            resp = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Content-Type":"application/json",
                         "Authorization": f"Bearer {key}"},
                json={"model":"gpt-4o-mini","temperature":0.1,"max_tokens":max_tokens,
                      "messages":[{"role":"user","content":prompt}]},
                timeout=30)
            data = resp.json()
            if "error" in data:
                msg = data["error"].get("message","error desconocido")
                errores.append(f"OpenAI: {msg}")
                # Cuota agotada → no tiene sentido intentar otros
                if "quota" in msg.lower() or "insufficient" in msg.lower():
                    errores.append("💡 Cuota agotada en OpenAI. Prueba con Gemini (gratuito) o Azure OpenAI.")
            else:
                return data["choices"][0]["message"]["content"].strip(), None
        except Exception as e:
            errores.append(f"OpenAI timeout/red: {e}")

    # ── 3. Gemini ──────────────────────────────────────────────────────────────
    if gemini_disponible():
        key = st.secrets.get("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        try:
            resp = requests.post(url,
                headers={"Content-Type":"application/json"},
                json={"contents":[{"parts":[{"text":prompt}]}],
                      "generationConfig":{"temperature":0.1,"maxOutputTokens":max_tokens}},
                timeout=30)
            data = resp.json()
            if "error" in data:
                errores.append(f"Gemini: {data['error'].get('message','error desconocido')}")
            else:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip(), None
        except Exception as e:
            errores.append(f"Gemini timeout/red: {e}")

    # ── 4. Anthropic ───────────────────────────────────────────────────────────
    if anthropic_disponible():
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        try:
            resp = requests.post("https://api.anthropic.com/v1/messages",
                headers={"Content-Type":"application/json",
                         "x-api-key": key,
                         "anthropic-version":"2023-06-01"},
                json={"model": st.secrets.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),"max_tokens":max_tokens,
                      "messages":[{"role":"user","content":prompt}]},
                timeout=30)
            data = resp.json()
            if "error" in data:
                errores.append(f"Anthropic: {data['error'].get('message','error desconocido')}")
            else:
                return data["content"][0]["text"].strip(), None
        except Exception as e:
            errores.append(f"Anthropic timeout/red: {e}")

    # Todos fallaron
    if errores:
        return None, "\n".join(errores)
    return None, "No hay ningún proveedor de IA configurado en Secrets."


def _limpiar_json(texto: str) -> str:
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    return t.strip()


# ─── Función principal de clasificación ───────────────────────────────────────

def clasificar_dudosas_con_ia(
    partidas_df: pd.DataFrame,
    max_partidas: int = 25,
    umbral_confianza: int = 70,
) -> tuple[pd.DataFrame | None, str | None]:
    """
    Clasifica partidas sin clasificar (TRV-99) o con baja confianza.
    Solo envía: id_partida, codigo_original, descripcion_limpia, unidad_norm.
    Devuelve (DataFrame con sugerencias, error).

    Columnas del DataFrame devuelto:
        id_partida, codigo_familia_sugerida, familia_nombre_sugerida,
        subfamilia_sugerida, confianza_ia, motivo_ia
    """
    if not ia_disponible():
        return None, instrucciones_configuracion()
    if partidas_df.empty:
        return None, "No hay partidas para analizar."

    # Seleccionar dudosas
    col_fam  = next((c for c in ["codigo_familia_auto","familia_auto"]
                     if c in partidas_df.columns), None)
    col_conf = next((c for c in ["confianza_clasificacion","confianza"]
                     if c in partidas_df.columns), None)

    sin_clas  = partidas_df[col_fam] == "TRV-99" if col_fam else pd.Series(True, index=partidas_df.index)
    baja_conf = pd.to_numeric(partidas_df[col_conf], errors="coerce").fillna(0) < umbral_confianza if col_conf else pd.Series(False, index=partidas_df.index)
    dudosas = partidas_df[sin_clas | baja_conf].copy()

    if dudosas.empty:
        return None, "No hay partidas dudosas (todas tienen familia con confianza suficiente)."

    cols_min = [c for c in ["id_partida","codigo_original","descripcion_limpia","unidad_norm"]
                if c in dudosas.columns]
    muestra = dudosas.head(max_partidas)[cols_min].to_dict(orient="records")

    prompt = f"""Eres experto en presupuestos de infraestructuras hidráulicas (EDAR, IDAM, ETAP, conducciones, obra marítima).

Clasifica estas {len(muestra)} partidas usando EXACTAMENTE los códigos de esta taxonomía:
{_cargar_taxonomia()}

Reglas importantes:
- Si la descripción contiene "buzo", "RAEE", "PCB", "tramex", "PRFV" o "CMC" → prioridad máxima, clasificar antes
- Usa TRV-99 solo si genuinamente no puedes clasificar
- No inventes precios ni cantidades
- Responde SOLO con JSON válido, sin texto adicional

Formato requerido:
[
  {{
    "id_partida": "igual que recibes, sin modificar",
    "codigo_familia": "CIV-07",
    "familia_nombre": "Encofrados, ferralla y hormigones",
    "subfamilia": "Hormigón",
    "confianza": 90,
    "motivo": "Descripción contiene HA-30"
  }}
]

Partidas:
{json.dumps(muestra, ensure_ascii=False, indent=2)}"""

    texto, error = _llamar_ia(prompt, max_tokens=3000)
    if error:
        return None, error

    try:
        items = json.loads(_limpiar_json(texto))
        if not isinstance(items, list):
            return None, f"Formato inesperado: se esperaba lista JSON.\nRespuesta: {texto[:300]}"

        df = pd.DataFrame(items).rename(columns={
            "codigo_familia":  "codigo_familia_sugerida",
            "familia_nombre":  "familia_nombre_sugerida",
            "subfamilia":      "subfamilia_sugerida",
            "confianza":       "confianza_ia",
            "motivo":          "motivo_ia",
        })
        if "id_partida" not in df.columns:
            return None, "La respuesta no incluye id_partida."
        return df, None

    except json.JSONDecodeError as e:
        return None, f"Error parseando JSON: {e}\n\nRespuesta recibida:\n{texto[:500]}"
    except Exception as e:
        return None, f"Error procesando respuesta: {e}"


# ─── Aplicar sugerencias al master ────────────────────────────────────────────

def aplicar_sugerencias_ia(
    partidas_master: pd.DataFrame,
    sugerencias: pd.DataFrame,
    umbral_confianza_ia: int = 75,
) -> tuple[pd.DataFrame, int]:
    """
    Aplica las sugerencias de la IA al partidas_master.

    Reglas de aplicación:
    - Solo aplica si confianza_ia >= umbral_confianza_ia
    - No aplica si el código sugerido es TRV-99
    - Siempre deja requiere_revision = True (nunca valida automáticamente)
    - Deriva disciplina desde el código de familia
    - Registra en criterio_clasificacion y observaciones

    Devuelve (partidas_master actualizado, nº de partidas actualizadas).
    """
    if sugerencias is None or sugerencias.empty:
        return partidas_master, 0

    pm = partidas_master.copy()
    actualizadas = 0

    for _, sug in sugerencias.iterrows():
        id_p    = sug.get("id_partida")
        cod_fam = str(sug.get("codigo_familia_sugerida", "")).strip()
        conf    = float(sug.get("confianza_ia", 0) or 0)

        # Validaciones
        if not id_p or not cod_fam or cod_fam == "TRV-99":
            continue
        if conf < umbral_confianza_ia:
            continue

        mask = pm["id_partida"] == id_p
        if not mask.any():
            continue

        # Derivar disciplina desde código
        disciplina = _disciplina_desde_codigo(cod_fam)

        # Actualizar campos de clasificación auto
        actualizaciones = {
            "codigo_familia_auto":       cod_fam,
            "familia_nombre_auto":       sug.get("familia_nombre_sugerida", ""),
            "codigo_subfamilia_auto":    "",  # IA no devuelve código estable de subfamilia
            "subfamilia_nombre_auto":    sug.get("subfamilia_sugerida", ""),
            "codigo_disciplina_auto":    disciplina.split("-")[0] if "-" in disciplina else cod_fam.split("-")[0],
            "disciplina_nombre_auto":    disciplina,
            "confianza_clasificacion":   conf,
            "criterio_clasificacion":    f"IA ({nombre_proveedor()}): {sug.get('motivo_ia','')}",
            # Siempre pendiente de validación por el técnico
            "requiere_revision":         True,
            "estado_revision":           "Pendiente",
        }

        for campo, valor in actualizaciones.items():
            if campo in pm.columns:
                pm.loc[mask, campo] = valor

        # Añadir nota en observaciones
        if "observaciones" in pm.columns:
            obs_prev = str(pm.loc[mask, "observaciones"].iloc[0] or "")
            nueva_obs = f"IA sugirió {cod_fam} (conf {conf:.0f}%)"
            pm.loc[mask, "observaciones"] = (
                f"{obs_prev} | {nueva_obs}".strip(" |")
                if obs_prev else nueva_obs
            )

        actualizadas += 1

    return pm, actualizadas
