"""Sistema de diseño de la interfaz: CSS, formato y componentes reutilizables.

Mantiene toda la apariencia en un solo lugar para que las vistas se concentren
en el contenido. La estética es "panel de control premium": fondo oscuro con
profundidad, tarjetas de vidrio (glassmorphism), acentos con glow y tipografía
Inter.

Confidencialidad: las pilas se muestran **solo por su código** (nunca el nombre
del material), para no filtrar materiales ni fórmulas de Gilberto y su socio.
"""

from __future__ import annotations

import streamlit as st

ACCENT = "#3b82f6"
GOOD = "#22c55e"
WARN = "#f59e0b"
BAD = "#ef4444"
MUTED = "#8b949e"

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root { --accent:#3b82f6; --accent2:#22d3ee; --good:#22c55e; --warn:#f59e0b;
  --bad:#ef4444; --ink:#e8eefc; --muted:#8b97ad; --line:#202836; }

html, body, .stApp, [class*="css"] { font-family:'Inter',system-ui,sans-serif; }

/* Lienzo: profundidad con varias capas + grid muy sutil */
.stApp {
  background:
    radial-gradient(1100px 520px at 12% -8%, #15294a 0%, rgba(13,17,23,0) 55%),
    radial-gradient(900px 480px at 92% 0%, #112b33 0%, rgba(13,17,23,0) 50%),
    linear-gradient(180deg, #0b0f16 0%, #0a0d13 100%);
}
.stApp::before {
  content:""; position:fixed; inset:0; pointer-events:none; opacity:.35;
  background-image:linear-gradient(#ffffff05 1px,transparent 1px),
    linear-gradient(90deg,#ffffff05 1px,transparent 1px);
  background-size:42px 42px; mask-image:radial-gradient(circle at 50% 0%,#000,transparent 75%);
}
#MainMenu, footer, header [data-testid="stToolbar"] { visibility:hidden; }
.block-container { padding-top:2.1rem; max-width:1300px; }

h1, h2, h3 { letter-spacing:-0.025em; color:var(--ink); }
h1 { font-weight:900; }
h3 { font-weight:800; }

/* Encabezado de marca */
.brand { display:flex; align-items:center; gap:.7rem; margin-bottom:.15rem; }
.brand .dot { width:13px; height:13px; border-radius:50%;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  box-shadow:0 0 18px #3b82f6cc, 0 0 6px #22d3eeaa; }
.brand .title { font-size:1.6rem; font-weight:900; color:var(--ink);
  background:linear-gradient(90deg,#eaf1ff,#9fc6ff); -webkit-background-clip:text;
  -webkit-text-fill-color:transparent; }
.subtle { color:var(--muted); font-size:.92rem; }

/* Tarjeta KPI — vidrio con realce superior */
.kpi { position:relative; background:linear-gradient(180deg,#141a23cc,#0e131bcc);
  backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px);
  border:1px solid var(--line); border-radius:18px; padding:1.05rem 1.15rem;
  height:100%; transition:transform .15s ease, border-color .15s ease; overflow:hidden; }
.kpi::after { content:""; position:absolute; top:0; left:0; right:0; height:1px;
  background:linear-gradient(90deg,transparent,#ffffff22,transparent); }
.kpi:hover { transform:translateY(-2px); border-color:#2c3950; }
.kpi .label { color:var(--muted); font-size:.74rem; text-transform:uppercase;
  letter-spacing:.07em; font-weight:700; }
.kpi .value { color:var(--ink); font-size:1.85rem; font-weight:900; margin-top:.25rem;
  line-height:1.05; }
.kpi .delta { font-size:.84rem; font-weight:600; margin-top:.2rem; }
.kpi .hint { color:#6b7789; font-size:.76rem; margin-top:.45rem; line-height:1.3; }
.kpi.accent { border-color:#2a4a7e;
  box-shadow:0 0 0 1px #1d3a66 inset, 0 10px 30px #0b1b3a55, 0 0 26px #1e62d033; }
.kpi.accent .value { background:linear-gradient(90deg,#eafff3,#7ee6a8);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; }

/* Tarjeta genérica / panel */
.card { background:#10151ccc; backdrop-filter:blur(6px); border:1px solid var(--line);
  border-radius:18px; padding:1.1rem 1.25rem; margin-bottom:.6rem; }

/* Pills / badges */
.pill { display:inline-block; padding:.18rem .62rem; border-radius:999px;
  font-size:.74rem; font-weight:800; letter-spacing:.02em; }
.pill.rico { background:#10331f; color:#46d989; border:1px solid #1c5635; }
.pill.relleno { background:#2a2031; color:#c98bdb; border:1px solid #4a2f57; }
.pill.mixto { background:#2a2410; color:#e6c351; border:1px solid #574b1c; }
.pill.good { background:#10331f; color:#46d989; }
.pill.warn { background:#332810; color:#e6b451; }
.pill.bad  { background:#331516; color:#f08a8a; }

.section-h { font-size:1.05rem; font-weight:800; color:var(--ink); margin:.2rem 0 .15rem; }

/* Listas de "por qué" */
.why { border-left:3px solid var(--accent); padding:.4rem 0 .4rem .85rem;
  margin:.35rem 0; color:#c9d4e0; font-size:.92rem; line-height:1.5; }
.why.good { border-color:var(--good); }
.why.warn { border-color:var(--warn); }

/* Métricas nativas */
div[data-testid="stMetric"] { background:linear-gradient(180deg,#141a23cc,#0e131bcc);
  border:1px solid var(--line); border-radius:16px; padding:.8rem 1rem;
  backdrop-filter:blur(6px); transition:transform .15s ease; }
div[data-testid="stMetric"]:hover { transform:translateY(-2px); }
div[data-testid="stMetricValue"] { font-weight:900; letter-spacing:-.02em; }

/* Botón primario con gradiente y glow */
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background:linear-gradient(135deg,#2f6bff,#22d3ee); border:0; font-weight:800;
  border-radius:12px; box-shadow:0 8px 22px #2f6bff44; transition:transform .12s ease; }
.stButton > button[kind="primary"]:hover { transform:translateY(-1px);
  box-shadow:0 10px 28px #2f6bff66; }

/* Expanders y tabs */
[data-testid="stExpander"] { border:1px solid var(--line); border-radius:14px;
  background:#10151ccc; overflow:hidden; }
.stTabs [data-baseweb="tab-list"] { gap:.3rem; }
.stTabs [data-baseweb="tab"] { background:#11161d; border:1px solid var(--line);
  border-radius:10px 10px 0 0; padding:.3rem .9rem; }

/* Alertas suaves */
div[data-testid="stAlert"] { border-radius:14px; }
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
