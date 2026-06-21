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

/* Botón primario con gradiente verde — texto blanco también en los hijos */
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background:var(--grad); border:0; color:#fff; font-weight:700; border-radius:14px;
  box-shadow:0 8px 20px #2E8A2333; transition:transform .12s ease; }
.stButton > button[kind="primary"] *,
button[data-testid="stBaseButton-primary"] * { color:#fff !important; }
.stButton > button[kind="primary"]:hover { transform:translateY(-1px);
  box-shadow:0 10px 26px #2E8A2344; }
.stButton > button { border-radius:14px; }

/* Navegación (st.pills) — activo en verde */
[data-testid="stPills"] button { border-radius:999px !important; font-weight:600; }

/* Sidebar verde oscuro con texto claro */
section[data-testid="stSidebar"] { background:var(--sidebar); }
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

/* Marca + cuenta + navegación del sidebar (estilo Aurix) */
.side-brand { display:flex; align-items:center; gap:.6rem; padding:.1rem .1rem 1rem; }
.side-brand .logo { width:38px; height:38px; border-radius:11px; background:var(--grad);
  display:grid; place-items:center; box-shadow:0 6px 16px #2E8A2355; }
.side-brand .logo-text { font-family:'Space Grotesk',sans-serif; font-weight:700;
  font-size:1.25rem; color:#EAF3EC; }
.side-acct { display:flex; align-items:center; gap:.6rem; background:var(--sidebar-soft);
  border:1px solid #2A352E; border-radius:14px; padding:.55rem .65rem; margin-bottom:1rem; }
.side-acct .av { width:30px; height:30px; border-radius:9px; background:#B5851F; color:#fff;
  display:grid; place-items:center; font-weight:700; font-size:.78rem; flex:0 0 auto; }
.side-acct .nm { font-weight:700; font-size:.84rem; color:#EAF3EC; line-height:1.1; }
.side-acct .sub { font-size:.71rem; color:#8CA092; }
.navsec { font-size:.66rem; text-transform:uppercase; letter-spacing:.09em;
  color:#6E8076; font-weight:700; margin:.5rem .2rem .25rem; }

/* Botones de navegación del sidebar: alineados a la izquierda, pill activo verde */
section[data-testid="stSidebar"] .stButton > button {
  justify-content:flex-start; text-align:left; border:0 !important; border-radius:12px;
  font-weight:600; background:transparent; color:#AEBCB2; padding:.5rem .8rem;
  box-shadow:none; }
section[data-testid="stSidebar"] .stButton > button:hover {
  background:#18221C; color:#EAF3EC; transform:none; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[kind="primary"] * {
  background-color:transparent; color:#10241A !important; font-weight:700; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background:#8DE05B !important; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
  background:#9BE86E !important; }
/* Etiqueta de sección un poco más clara para que se lea sobre el verde oscuro */
.navsec { color:#8EA295; }

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
_LOGO_SVG = (
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">'
    '<path d="M12 2.5l8 4.6v9.8l-8 4.6-8-4.6V7.1z" stroke="#F3F6F3" '
    'stroke-width="2" fill="none" stroke-linejoin="round"/>'
    '<circle cx="12" cy="12" r="2.4" fill="#F3F6F3"/></svg>'
)


def sidebar_brand(name: str = "Aurix") -> None:
    """Logo + nombre de la marca en el tope del sidebar."""
    st.sidebar.markdown(
        f'<div class="side-brand"><span class="logo">{_LOGO_SVG}</span>'
        f'<span class="logo-text">{name}</span></div>',
        unsafe_allow_html=True,
    )


def sidebar_account(name: str, sub: str = "Cuenta comercial", initials: str = "") -> None:
    """Tarjeta de cuenta (avatar + nombre) en el sidebar."""
    initials = initials or "".join(w[0] for w in name.split()[:2]).upper()
    st.sidebar.markdown(
        f'<div class="side-acct"><span class="av">{initials}</span>'
        f'<span><div class="nm">{name}</div><div class="sub">{sub}</div></span></div>',
        unsafe_allow_html=True,
    )


def sidebar_section(label: str) -> None:
    """Etiqueta de sección del menú lateral (p. ej. 'Menú principal')."""
    st.sidebar.markdown(f'<div class="navsec">{label}</div>', unsafe_allow_html=True)


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
