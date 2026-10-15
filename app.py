"""Interfaz web de OmniVision AI (Streamlit) — edición nature/wildlife.

Clasifica una imagen en una de las 67 categorías unificadas de los cuatro
datasets locales del proyecto. El umbral de confianza no se inventa: se deriva
del conjunto de validación (results/threshold_analysis.json).

La capa visual (tema Selva en .streamlit/config.toml + CSS de este archivo)
es decorativa: no altera datos, probabilidades ni el modelo.

Ejecución (PowerShell, desde la raíz del proyecto):
    .venv\\Scripts\\streamlit run app.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from src.common import CLASS_METADATA_JSON, MODEL_PATH, RESULTS_DIR

st.set_page_config(
    page_title="OmniVision AI — Visión de la biodiversidad",
    page_icon=":material/pets:",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Identidad visual (CSS compatible con Streamlit: tarjetas, texturas, foco)
# ---------------------------------------------------------------------------
st.html(
    """
<style>
  /* ---- Cabecera hero ---- */
  .ov-hero {
    position: relative;
    padding: 2.2rem 2.4rem 1.8rem 2.4rem;
    margin: 0 0 1.2rem 0;
    border-radius: 16px;
    background:
      radial-gradient(1100px 320px at 8% -40%, rgba(217,164,65,.16), transparent 60%),
      radial-gradient(900px 300px at 92% 120%, rgba(127,166,80,.14), transparent 60%),
      linear-gradient(135deg, #12241715 0%, #16251a 55%, #101c13 100%);
    border: 1px solid #2c3f2e;
    overflow: hidden;
  }
  .ov-hero::before {          /* huellas discretas de fondo */
    content: "🐾";
    position: absolute;
    right: -12px; top: -22px;
    font-size: 120px;
    opacity: .07;
    transform: rotate(18deg);
    pointer-events: none;
  }
  .ov-eyebrow {
    font-size: .78rem;
    letter-spacing: .28em;
    text-transform: uppercase;
    color: #c9962e;
    margin: 0 0 .35rem 0;
    font-weight: 600;
  }
  .ov-title {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 2.55rem;
    font-weight: 700;
    color: #f2ecdb;
    margin: 0;
    line-height: 1.1;
  }
  .ov-title .ov-accent { color: #d9a441; }
  .ov-sub {
    margin: .55rem 0 0 0;
    color: #c9c9b4;
    font-size: 1.02rem;
    max-width: 62ch;
  }
  .ov-chips { margin-top: .9rem; display: flex; gap: .45rem; flex-wrap: wrap; }
  .ov-chip {
    display: inline-flex; align-items: center; gap: .35rem;
    padding: .22rem .65rem;
    border-radius: 999px;
    border: 1px solid #35503a;
    background: rgba(22, 37, 26, .75);
    color: #d7d3bf;
    font-size: .8rem;
  }

  /* ---- Tarjetas ---- */
  .ov-card {
    border: 1px solid #2c3f2e;
    border-radius: 14px;
    background: linear-gradient(180deg, #16251a 0%, #121f14 100%);
    padding: 1.1rem 1.2rem;
    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
  }
  .ov-card:hover {
    transform: translateY(-2px);
    border-color: #4a6a48;
    box-shadow: 0 8px 22px rgba(0, 0, 0, .35);
  }
  .ov-rank {
    font-size: .72rem; letter-spacing: .18em; text-transform: uppercase;
    color: #8f9c8f; margin: 0 0 .25rem 0;
  }
  .ov-label {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.35rem; color: #f2ecdb; margin: 0; line-height: 1.2;
  }
  .ov-meta { color: #a9b3a4; font-size: .84rem; margin: .3rem 0 0 0; }
  .ov-prob {
    font-size: 1.6rem; font-weight: 700; color: #d9a441; margin: .45rem 0 0 0;
  }

  /* ---- Zona de carga ---- */
  [data-testid="stFileUploaderDropzone"] {
    border: 1.5px dashed #4a6a48 !important;
    border-radius: 14px !important;
    background: rgba(22, 37, 26, .45) !important;
    transition: border-color .18s ease, background .18s ease;
  }
  [data-testid="stFileUploaderDropzone"]:hover {
    border-color: #d9a441 !important;
    background: rgba(27, 45, 31, .55) !important;
  }

  /* ---- Barras de probabilidad (st.progress) ---- */
  [data-testid="stProgress"] > div > div > div > div {
    background-image: linear-gradient(90deg, #7fa650, #d9a441);
  }

  /* ---- Botones ---- */
  [data-testid="stButton"] button {
    transition: transform .15s ease, background .15s ease, border-color .15s ease;
  }
  [data-testid="stButton"] button:hover {
    border-color: #d9a441;
    transform: translateY(-1px);
  }

  /* ---- Métricas del panel lateral ---- */
  div[data-testid="stMetric"] {
    border: 1px solid #2c3f2e;
    border-radius: 12px;
    padding: .6rem .75rem;
    background: rgba(19, 32, 22, .6);
  }
  div[data-testid="stMetricValue"] { color: #d9a441; }

  /* ---- Pie ---- */
  .ov-footer {
    margin-top: 2.2rem;
    padding: 1rem 0 1.6rem 0;
    border-top: 1px solid #243527;
    color: #8f9c8f;
    font-size: .85rem;
    text-align: center;
  }
  .ov-footer b { color: #c9c9b4; font-weight: 600; }

  /* ---- Insignias de estado ---- */
  .ov-ok {
    display: inline-block; padding: .25rem .7rem; border-radius: 999px;
    background: rgba(127, 166, 80, .16); color: #a9c97a;
    border: 1px solid rgba(127, 166, 80, .45); font-size: .82rem; font-weight: 600;
  }
  .ov-warn {
    display: inline-block; padding: .25rem .7rem; border-radius: 999px;
    background: rgba(201, 135, 58, .14); color: #e0b06a;
    border: 1px solid rgba(201, 135, 58, .5); font-size: .82rem; font-weight: 600;
  }

  /* ---- Divisor natural ---- */
  .ov-divider {
    display: flex; align-items: center; gap: .7rem;
    color: #4a6a48; margin: 1.4rem 0 1rem 0;
  }
  .ov-divider::before, .ov-divider::after {
    content: ""; flex: 1; height: 1px;
    background: linear-gradient(90deg, transparent, #2c3f2e, transparent);
  }
</style>
"""
)

# Iconos contextuales por grupo (solo decorativos; no alteran la clasificación)
GROUP_ICONS = {
    "scene": ":material/landscape:",
    "person": ":material/person:",
    "dinosaur": ":material/pets:",
    "animal": ":material/pets:",
    "insect": ":material/pest_control:",
    "mosquito": ":material/pest_control:",
    "plant_disease": ":material/local_florist:",
}
GROUP_NAMES_ES = {
    "scene": "Escena",
    "person": "Persona",
    "dinosaur": "Dinosaurio",
    "animal": "Animal",
    "insect": "Insecto",
    "mosquito": "Mosquito",
    "plant_disease": "Planta / enfermedad",
}


# ---------------------------------------------------------------------------
# Caché: el modelo se carga una sola vez (idéntico al original)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Cargando el modelo CNN…")
def load_predictor():
    from src.predict import Predictor
    return Predictor()


@st.cache_data(show_spinner=False)
def load_report() -> dict | None:
    p = RESULTS_DIR / "test_report.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


@st.cache_data(show_spinner=False)
def load_classes() -> pd.DataFrame:
    metadata = json.loads(CLASS_METADATA_JSON.read_text(encoding="utf-8"))
    rows = [
        {"clase": v["label"], "nombre": v["name_es"], "grupo": v["group"],
         "total": sum(v["counts"].values())}
        for v in metadata["classes"].values()
    ]
    return pd.DataFrame(rows).sort_values(["grupo", "clase"]).reset_index(drop=True)


def class_description(label: str) -> str:
    """Explicación factual construida SOLO con metadatos reales del proyecto."""
    meta = json.loads(CLASS_METADATA_JSON.read_text(encoding="utf-8"))
    cls = meta["classes"].get(label, {})
    group = cls.get("group", "unknown")
    frases = {
        "scene": "Paisaje o escena urbana/natural reconocida entre las categorías de escenarios.",
        "person": "Persona detectada; las variantes de CIFAR-100 (baby/boy/girl/man/woman) se unificaron en una sola clase.",
        "dinosaur": "Dinosaurio: categoría propia de CIFAR-100 (clase fina «dinosaur»).",
        "animal": "Vertebrado (mamífero, pez o marino) del conjunto de fauna de CIFAR-100.",
        "insect": "Insecto del subconjunto de artrópodos de CIFAR-100.",
        "mosquito": "Género de mosquito del dataset MosqVision-3K (clases: aedes, anopheles, culex).",
        "plant_disease": "Condición fitosanitaria de PlantVillage (CC0): especie y estado sanitario documentados.",
    }
    partes = [frases.get(group, "Categoría unificada del proyecto.")]
    if cls.get("species"):
        partes.append(f"Especie: {', '.join(cls['species'])}.")
    if cls.get("health_status"):
        partes.append(f"Estado sanitario: {', '.join(cls['health_status'])}.")
    if cls.get("sources"):
        fuentes = ", ".join(cls["sources"].keys())
        partes.append(f"Proviene de: {fuentes}.")
    n = sum(cls.get("counts", {}).values())
    if n:
        partes.append(f"Imágenes en el catálogo: {n:,}.".replace(",", "."))
    return " ".join(partes)


# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------
st.html(
    """
<div class="ov-hero">
  <p class="ov-eyebrow">:material/pets: Visión artificial · Biodiversidad</p>
  <h1 class="ov-title">OMNIVISION <span class="ov-accent">AI</span></h1>
  <p class="ov-sub">Reconocimiento inteligente de fauna, flora, insectos, personas
  y escenas: una única CNN unifica <b>67 categorías</b> de cuatro datasets de
  naturaleza e imágenes.</p>
  <div class="ov-chips">
    <span class="ov-chip">:material/pets: Animales</span>
    <span class="ov-chip">:material/pest_control: Insectos y mosquitos</span>
    <span class="ov-chip">:material/local_florist: Plantas y enfermedades</span>
    <span class="ov-chip">:material/landscape: Escenas</span>
    <span class="ov-chip">:material/visibility: Visión artificial</span>
  </div>
</div>
"""
)

if not MODEL_PATH.exists():
    st.error(f"No se encontró el modelo en `{MODEL_PATH}`. "
             "Entrenalo primero: `.venv\\Scripts\\python -m src.train`")
    st.stop()

report = load_report()
classes_df = load_classes()
predictor = load_predictor()
thr = predictor.threshold

# ---------------------------------------------------------------------------
# Panel lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("#### :material/forest: El modelo")
    st.markdown(
        f"- **CNN:** MobileNetV2 (ImageNet) + cabeza densa\n"
        f"- **Categorías:** {len(predictor.class_names)}\n"
        f"- **Entrada:** 128×128 RGB\n"
        f"- **Umbral (derivado en val.):** {thr if thr is not None else '—'}"
    )
    if report:
        st.markdown("#### :material/query_stats: Resultados en prueba")
        c1, c2 = st.columns(2)
        c1.metric("Accuracy", f"{report['accuracy']*100:.1f}%")
        c2.metric("Top-5", f"{report['top5_accuracy']*100:.1f}%")
        c3, c4 = st.columns(2)
        c3.metric("Macro-F1", f"{report['macro_f1']:.3f}")
        c4.metric("Imágenes", f"{report['test_images']:,}".replace(",", "."))
        with st.expander("Exactitud por fuente"):
            st.table(pd.Series(report["per_source_accuracy"], name="accuracy"))
    top_k = st.slider("Predicciones a mostrar (top-k)", 3, 10, 5)
    with st.expander("Acerca de los datos"):
        st.markdown(
            "- **CIFAR-100** (escenas, personas, dinosaurios, insectos, animales)\n"
            "- **Intel Image Classification** (escenas urbanas y naturales)\n"
            "- **PlantVillage** (38 enfermedades de plantas)\n"
            "- **MosqVision-3K** (aedes, anopheles, culex)\n\n"
            "Equivalencias fusionadas (p. ej. *forest* CIFAR ↔ Intel) y el "
            "tope de 600 imágenes por clase están documentados en "
            "`config/label_mapping.json` y `README.md`."
        )

# ---------------------------------------------------------------------------
# Zona de carga
# ---------------------------------------------------------------------------
st.html(
    """
<div class="ov-divider">:material/upload: Fotografía de campo</div>
"""
)
with st.container(border=True, key="zona_carga"):
    st.markdown(
        f"#### :material/photo_camera: Subí una fotografía\n"
        f"*Formatos admitidos: JPG y PNG — el análisis se inicia automáticamente "
        f"al cargar la imagen.*"
    )
    uploaded = st.file_uploader(
        "Imagen de campo (JPG o PNG)",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# Resultado de la clasificación
# ---------------------------------------------------------------------------
if uploaded is not None:
    col_img, col_res = st.columns([5, 7], gap="large")

    with col_img:
        st.markdown("#### :material/image: Fotografía")
        with st.container(border=True, key="tarjeta_imagen"):
            st.image(uploaded, width="stretch",
                     alt=f"Imagen subida: {uploaded.name}")
            st.caption(uploaded.name)

    with col_res:
        st.markdown("#### :material/visibility: Clasificación")
        with st.spinner("Analizando la fotografía…"):
            r = predictor.predict(uploaded.getvalue(), top_k=top_k)

        best = r["top"][0]
        icon = GROUP_ICONS.get(best["group"], ":material/help:")
        grupo_es = GROUP_NAMES_ES.get(best["group"], best["group"])

        # Tarjeta héroe del resultado principal
        with st.container(border=True, key="tarjeta_resultado"):
            if r["acepta"]:
                st.html(
                    f'<p class="ov-rank">Resultado principal</p>'
                    f'<h2 class="ov-label">{icon} {best["name_es"]}</h2>'
                    f'<p class="ov-meta">{grupo_es} · etiqueta <code>{best["label"]}</code></p>'
                    f'<p class="ov-prob">{best["probability"]*100:.1f}%</p>'
                )
                st.progress(float(best["probability"]),
                            text=f"Confianza del modelo: {best['probability']*100:.1f}% "
                                 f"(umbral {thr})")
                st.html(
                    f'<span class="ov-ok">:material/check_circle: Predicción aceptada</span>'
                )
            else:
                st.html(
                    f'<p class="ov-rank">Resultado principal</p>'
                    f'<h2 class="ov-label">{icon} {best["name_es"]}</h2>'
                    f'<p class="ov-meta">{grupo_es} · etiqueta <code>{best["label"]}</code></p>'
                    f'<p class="ov-prob">{best["probability"]*100:.1f}%</p>'
                )
                st.progress(float(best["probability"]),
                            text=f"Confianza del modelo: {best['probability']*100:.1f}% "
                                 f"(umbral {thr})")
                st.html(
                    f'<span class="ov-warn">:material/warning: Confianza baja: '
                    f'tratala como «sin confianza»</span>'
                )
                st.caption(f"Por debajo del umbral {thr} derivado en validación.")

            st.markdown("**Sobre esta categoría**")
            st.caption(class_description(best["label"]))

        # Top-3 como tarjetas (las puntuaciones reales del modelo)
        st.markdown("#### :material/leaderboard: Podio de categorías")
        cols = st.columns(min(3, len(r["top"])))
        for i, (col, item) in enumerate(zip(cols, r["top"][:3]), start=1):
            gicon = GROUP_ICONS.get(item["group"], ":material/help:")
            with col:
                with st.container(border=True, key=f"podio_{i}"):
                    st.html(
                        f'<p class="ov-rank">Puesto {i}</p>'
                        f'<p class="ov-label" style="font-size:1.05rem">'
                        f'{gicon} {item["name_es"]}</p>'
                        f'<p class="ov-meta">{GROUP_NAMES_ES.get(item["group"], item["group"])}</p>'
                        f'<p class="ov-prob" style="font-size:1.15rem">'
                        f'{item["probability"]*100:.1f}%</p>'
                    )
                    st.progress(float(item["probability"]),
                                text=f"{item['probability']*100:.1f}%")

        # Gráfica de las categorías con mayor puntuación (mismos datos)
        st.markdown("#### :material/bar_chart: Distribución de confianza")
        chart_df = pd.DataFrame({
            "categoría": [f"{t['name_es']}" for t in r["top"]],
            "probabilidad": [t["probability"] for t in r["top"]],
        }).set_index("categoría")
        st.bar_chart(chart_df, horizontal=True, color="#d9a441",
                     alt="Probabilidades del modelo para las categorías top-k")

        with st.container(border=True, key="tabla_detalle"):
            det = pd.DataFrame(r["top"])[["name_es", "label", "group", "probability"]]
            det.columns = ["Categoría (ES)", "Etiqueta", "Grupo", "Probabilidad"]
            st.dataframe(det, hide_index=True, width="stretch")

        with st.expander("Detalle de metadatos"):
            meta = json.loads(CLASS_METADATA_JSON.read_text(encoding="utf-8"))
            cls = meta["classes"][best["label"]]
            st.json({k: cls[k] for k in
                     ("name_es", "group", "sources", "counts", "species",
                      "health_status") if k in cls})

        # Historial de esta sesión (solo datos reales de análisis ya ejecutados)
        hist = st.session_state.setdefault("historial_ov", [])
        hist.append({
            "hora": time.strftime("%H:%M:%S"),
            "archivo": uploaded.name,
            "categoría": best["name_es"],
            "etiqueta": best["label"],
            "grupo": grupo_es,
            "probabilidad": best["probability"],
            "estado": "aceptada" if r["acepta"] else "baja confianza",
        })

# ---------------------------------------------------------------------------
# Historial de análisis (sesión actual)
# ---------------------------------------------------------------------------
historial = st.session_state.get("historial_ov", [])
if historial:
    st.html('<div class="ov-divider">:material/history: Historial de la expedición</div>')
    h_df = pd.DataFrame(historial).sort_values("hora", ascending=False)
    s1, s2, s3 = st.columns(3)
    s1.metric("Análisis", len(h_df))
    s2.metric("Aceptados", int((h_df["estado"] == "aceptada").sum()))
    s3.metric("Confianza media", f"{h_df['probabilidad'].mean()*100:.1f}%")
    with st.container(border=True, key="historial_tabla"):
        st.dataframe(h_df[["hora", "archivo", "categoría", "grupo",
                           "probabilidad", "estado"]],
                     hide_index=True, width="stretch")
    with st.container(border=True, key="historial_grafica"):
        st.bar_chart(h_df.groupby("categoría").size().rename("análisis"),
                     horizontal=True, color="#7fa650",
                     alt="Cantidad de análisis por categoría en esta sesión")

# ---------------------------------------------------------------------------
# Catálogo de categorías
# ---------------------------------------------------------------------------
st.html('<div class="ov-divider">:material/park: Catálogo de las 67 categorías</div>')
grupo = st.pills("Filtrar por grupo", sorted(classes_df["grupo"].unique()),
                 selection_mode="multi", key="pills_grupo")
filtrado = classes_df if not grupo else classes_df[classes_df["grupo"].isin(grupo)]
with st.container(border=True, key="catalogo"):
    st.dataframe(filtrado, hide_index=True, width="stretch",
                 column_config={
                     "total": st.column_config.NumberColumn("Imágenes (total)"),
                 })

# ---------------------------------------------------------------------------
# Pie de página
# ---------------------------------------------------------------------------
st.html(
    """
<div class="ov-footer">
  <b>🐾 OmniVision AI</b> · una sola CNN para fauna, flora, insectos, personas
  y escenas · MobileNetV2 + 67 categorías unificadas de cuatro datasets ·
  umbral de confianza derivado en validación
</div>
"""
)
