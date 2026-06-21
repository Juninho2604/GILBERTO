"""Sistema de diseño de la interfaz: CSS, formato y componentes reutilizables.

Mantiene toda la apariencia en un solo lugar para que las vistas se concentren
en el contenido. Estética **Aurix**: tema claro (fondo verde-gris muy suave),
tarjetas blancas redondeadas con sombra leve, acento verde, sidebar verde
oscuro, y tipografía Space Grotesk (títulos/números) + Manrope (texto).

Confidencialidad: las pilas se muestran **solo por su código** (nunca el nombre
del material), para no filtrar materiales ni fórmulas de Gilberto y su socio.
"""

from __future__ import annotations

import streamlit as st

ACCENT = "#46B22C"   # verde primario
GOOD = "#2E8A23"     # verde profundo (positivo)
WARN = "#B5851F"     # ámbar (medio)
BAD = "#C0654A"      # terracota (bajo/riesgo)
MUTED = "#9AA89F"    # texto terciario

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

:root {
  --bg:#F3F6F3; --sidebar:#0F1713; --sidebar-soft:#18221C;
  --card:#FFFFFF; --border:#EDEFEC; --border2:#E7EBE7;
  --text:#16241B; --text-soft:#5B6660; --muted:#9AA89F;
  --accent:#8DE05B; --accent-deep:#46B22C; --accent-deeper:#2E8A23;
  --grad:linear-gradient(135deg,#5FBE3A,#3E9E2C,#2E8A23);
  --shadow:0 2px 14px rgba(20,40,25,.05);
}

html, body, .stApp, [class*="css"] { font-family:'Manrope',system-ui,sans-serif;
  color:var(--text); }
.stApp { background:var(--bg); }
#MainMenu, footer, header [data-testid="stToolbar"] { visibility:hidden; }
.block-container { padding-top:2rem; max-width:1300px; }

h1, h2, h3, h4 { font-family:'Space Grotesk',sans-serif; color:var(--text);
  letter-spacing:-0.02em; font-weight:700; }

/* Encabezado de marca */
.brand { display:flex; align-items:center; gap:.7rem; margin-bottom:.15rem; }
.brand .dot { width:13px; height:13px; border-radius:50%; background:var(--grad);
  box-shadow:0 0 14px #8DE05B66; }
.brand .title { font-family:'Space Grotesk',sans-serif; font-size:1.55rem;
  font-weight:700; color:var(--text); }
.subtle { color:var(--text-soft); font-size:.92rem; }

/* Tarjeta KPI — blanca, redondeada, sombra suave */
.kpi { background:var(--card); border:1px solid var(--border); border-radius:22px;
  padding:20px 22px; height:100%; box-shadow:var(--shadow);
  transition:transform .15s ease, box-shadow .15s ease; }
.kpi:hover { transform:translateY(-2px); box-shadow:0 8px 22px rgba(20,40,25,.08); }
.kpi .label { color:var(--muted); font-size:.72rem; text-transform:uppercase;
  letter-spacing:.06em; font-weight:700; }
.kpi .value { font-family:'Space Grotesk',sans-serif; color:var(--text);
  font-size:1.95rem; font-weight:700; margin-top:.3rem; line-height:1.05; }
.kpi .delta { font-size:.84rem; font-weight:600; margin-top:.2rem; }
.kpi .hint { color:var(--muted); font-size:.76rem; margin-top:.45rem; line-height:1.35; }
/* KPI destacado = hero verde */
.kpi.accent { background:var(--grad); border:0; box-shadow:0 10px 26px #2E8A2333; }
.kpi.accent .label, .kpi.accent .hint, .kpi.accent .delta { color:#E6F6DF !important; }
.kpi.accent .value { color:#fff; }

/* Tarjeta genérica / panel */
.card { background:var(--card); border:1px solid var(--border); border-radius:22px;
  padding:20px 22px; margin-bottom:.6rem; box-shadow:var(--shadow); }

/* Pills / badges (estados Aurix) */
.pill { display:inline-block; padding:.2rem .66rem; border-radius:999px;
  font-size:.74rem; font-weight:700; letter-spacing:.01em; }
.pill.rico, .pill.good { background:#EAF8E2; color:#2E8A23; }
.pill.mixto, .pill.warn { background:#FFF3DC; color:#B5851F; }
.pill.relleno { background:#EEF1EE; color:#5B6660; }
.pill.bad { background:#FBEDE8; color:#C0654A; }

.section-h { font-family:'Space Grotesk',sans-serif; font-size:1.05rem;
  font-weight:700; color:var(--text); margin:.2rem 0 .15rem; }

/* Listas de "por qué" */
.why { border-left:3px solid var(--accent-deep); padding:.5rem 0 .5rem .9rem;
  margin:.4rem 0; color:var(--text-soft); font-size:.92rem; line-height:1.5;
  background:#FAFCF9; border-radius:0 12px 12px 0; }
.why b { color:var(--text); }
.why.good { border-color:var(--accent-deeper); }
.why.warn { border-color:var(--warn); }

/* Métricas nativas → tarjeta blanca */
div[data-testid="stMetric"] { background:var(--card); border:1px solid var(--border);
  border-radius:18px; padding:.9rem 1.1rem; box-shadow:var(--shadow);
  transition:transform .15s ease; }
div[data-testid="stMetric"]:hover { transform:translateY(-2px); }
div[data-testid="stMetricValue"] { font-family:'Space Grotesk',sans-serif;
  font-weight:700; color:var(--text); letter-spacing:-.01em; }
div[data-testid="stMetricLabel"] { color:var(--muted); font-weight:600; }

/* Botón primario con gradiente verde */
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background:var(--grad); border:0; color:#fff; font-weight:700; border-radius:14px;
  box-shadow:0 8px 20px #2E8A2333; transition:transform .12s ease; }
.stButton > button[kind="primary"]:hover { transform:translateY(-1px);
  box-shadow:0 10px 26px #2E8A2344; }
.stButton > button { border-radius:14px; }

/* Navegación (st.pills) — activo en verde */
[data-testid="stPills"] button { border-radius:999px !important; font-weight:600; }

/* Sidebar verde oscuro con texto claro */
section[data-testid="stSidebar"] > div:first-child { background:var(--sidebar); }
section[data-testid="stSidebar"] * { color:#C7D2CB; }
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color:#EAF3EC; }
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background:var(--sidebar-soft) !important; color:#EAF3EC !important;
  border-color:#2A352E !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] {
  background:var(--sidebar-soft); border-color:#2A352E; }

/* Tablas / dataframes */
[data-testid="stDataFrame"], [data-testid="stTable"] {
  border:1px solid var(--border2); border-radius:14px; overflow:hidden; }

/* Expanders y tabs */
[data-testid="stExpander"] { border:1px solid var(--border); border-radius:18px;
  background:var(--card); box-shadow:var(--shadow); overflow:hidden; }
.stTabs [data-baseweb="tab-list"] { gap:.3rem; }
.stTabs [data-baseweb="tab"] { background:var(--card); border:1px solid var(--border);
  border-radius:12px 12px 0 0; padding:.3rem .9rem; }

/* Alertas redondeadas */
div[data-testid="stAlert"] { border-radius:16px; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Formato
# --------------------------------------------------------------------------- #
def usd(x: float) -> str:
    return f"${x:,.0f}"


def usd2(x: float) -> str:
    return f"${x:,.2f}"


def pct(x: float, signed: bool = True) -> str:
    return f"{x:+.1f}%" if signed else f"{x:.1f}%"


# --------------------------------------------------------------------------- #
# Confidencialidad: etiqueta de pila
# --------------------------------------------------------------------------- #
def pile_label(code: str, name: str = "", private: bool = False) -> str:
    """Etiqueta de una pila: **solo el código** asignado, como en las planillas.

    Nunca muestra el nombre del material (privacidad de Gilberto y su socio).
    Los parámetros ``name``/``private`` se conservan por compatibilidad pero se
    ignoran a propósito.
    """
    return str(code)


# --------------------------------------------------------------------------- #
# Componentes
# --------------------------------------------------------------------------- #
def brand(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="brand"><span class="dot"></span>'
        f'<span class="title">{title}</span></div>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<div class="subtle">{subtitle}</div>', unsafe_allow_html=True)


def kpi(label: str, value: str, *, delta: str = "", delta_color: str = MUTED,
        hint: str = "", accent: bool = False) -> None:
    cls = "kpi accent" if accent else "kpi"
    delta_html = (
        f'<div class="delta" style="color:{delta_color}">{delta}</div>' if delta else ""
    )
    hint_html = f'<div class="hint">{hint}</div>' if hint else ""
    st.markdown(
        f'<div class="{cls}"><div class="label">{label}</div>'
        f'<div class="value">{value}</div>{delta_html}{hint_html}</div>',
        unsafe_allow_html=True,
    )


def pill(text: str, kind: str = "mixto") -> str:
    return f'<span class="pill {kind}">{text}</span>'


def why(text: str, kind: str = "") -> None:
    cls = f"why {kind}".strip()
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def card_open() -> None:
    st.markdown('<div class="card">', unsafe_allow_html=True)


def card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
