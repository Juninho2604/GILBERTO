"""Sistema de diseño de la interfaz: CSS, formato y componentes reutilizables.

Mantiene toda la apariencia en un solo lugar para que las vistas se concentren
en el contenido. La estética es "panel financiero": fondo oscuro, tarjetas con
bordes suaves, acentos por color y tipografía clara.

Confidencialidad: las pilas se muestran por **número** (como las nombra
Gilberto: #1, #2, #14…) y el nombre real solo aparece si se activa el *modo
privado / leyenda* en la barra lateral. Así el material y las fórmulas no se
filtran en una demo.
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
:root { --accent:#3b82f6; --good:#22c55e; --warn:#f59e0b; --bad:#ef4444; }

/* Lienzo general */
.stApp { background: radial-gradient(1200px 600px at 20% -10%, #15233b 0%, #0d1117 55%); }
#MainMenu, footer, header [data-testid="stToolbar"] { visibility: hidden; }
.block-container { padding-top: 2.2rem; max-width: 1280px; }

h1, h2, h3 { letter-spacing: -0.02em; }
h1 { font-weight: 800; }

/* Encabezado de marca */
.brand { display:flex; align-items:center; gap:.7rem; margin-bottom:.2rem; }
.brand .dot { width:12px; height:12px; border-radius:50%;
  background:linear-gradient(135deg,#3b82f6,#22d3ee); box-shadow:0 0 16px #3b82f6aa; }
.brand .title { font-size:1.55rem; font-weight:800; color:#e6edf3; }
.subtle { color:#8b949e; font-size:.92rem; }

/* Tarjeta KPI */
.kpi { background:linear-gradient(180deg,#161b22,#0f141b); border:1px solid #232b36;
  border-radius:16px; padding:1.05rem 1.15rem; height:100%; }
.kpi .label { color:#8b949e; font-size:.78rem; text-transform:uppercase;
  letter-spacing:.06em; font-weight:600; }
.kpi .value { color:#e6edf3; font-size:1.7rem; font-weight:800; margin-top:.25rem;
  line-height:1.1; }
.kpi .delta { font-size:.85rem; font-weight:600; margin-top:.2rem; }
.kpi .hint { color:#6b7686; font-size:.76rem; margin-top:.45rem; }
.kpi.accent { border-color:#27406b; box-shadow:0 0 0 1px #1d3a66 inset, 0 8px 24px #00000040; }

/* Tarjeta genérica / panel */
.card { background:#11161d; border:1px solid #232b36; border-radius:16px;
  padding:1.1rem 1.25rem; margin-bottom:.6rem; }

/* Pills / badges */
.pill { display:inline-block; padding:.16rem .6rem; border-radius:999px;
  font-size:.74rem; font-weight:700; letter-spacing:.02em; }
.pill.rico { background:#10331f; color:#46d989; border:1px solid #1c5635; }
.pill.relleno { background:#2a2031; color:#c98bdb; border:1px solid #4a2f57; }
.pill.mixto { background:#2a2410; color:#e6c351; border:1px solid #574b1c; }
.pill.good { background:#10331f; color:#46d989; }
.pill.warn { background:#332810; color:#e6b451; }
.pill.bad  { background:#331516; color:#f08a8a; }

/* Sección */
.section-h { font-size:1.05rem; font-weight:700; color:#e6edf3; margin:.2rem 0 .15rem; }

/* Listas de "por qué" */
.why { border-left:3px solid var(--accent); padding:.35rem 0 .35rem .8rem;
  margin:.35rem 0; color:#c9d4e0; font-size:.92rem; }
.why.good { border-color:var(--good); }
.why.warn { border-color:var(--warn); }

div[data-testid="stMetric"] { background:#11161d; border:1px solid #232b36;
  border-radius:14px; padding:.7rem .9rem; }
.stTabs [data-baseweb="tab-list"] { gap:.3rem; }
.stTabs [data-baseweb="tab"] { background:#11161d; border:1px solid #232b36;
  border-radius:10px 10px 0 0; padding:.3rem .9rem; }
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
    """Etiqueta de una pila. Por número (#1) salvo modo privado con leyenda."""
    try:
        tag = f"#{int(code)}"
    except (TypeError, ValueError):
        tag = f"#{code}"
    if private and name:
        return f"{tag} · {name}"
    return tag


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
