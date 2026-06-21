"""Visualización 3D del contenedor y sus lotes (plotly).

Dibuja el contenedor como una caja de vidrio y cada **lote** como un bloque de
carga apilado a lo largo, con tamaño proporcional a su peso y color según el
**% de material aprovechado** (ámbar = bajo, verde = alto). Interactivo: se rota
y se hace zoom. La idea es "ver" el contenedor armado, no leer una tabla.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

import plotly.graph_objects as go

# Proporciones estilizadas de un contenedor de 40' (largo : ancho : alto).
_LEN, _WID, _HGT = 12.0, 2.4, 2.6
_GAP = 0.06  # separación visual entre lotes

# Un pallet físico ≈ 1 t de material (estándar para armar la carga del contenedor).
PALLET_KG = 1000.0

# Categorías de riqueza de un pallet/lote (según concentración de oro).
RICH_VERY = "MUY RICO"
RICH_LOW = "POCO RICO"
RICH_FILL = "RELLENO"

# Color por categoría (verde profundo = muy rico → arena = relleno).
_TIER_COLOR = {
    RICH_VERY: (34, 138, 35),
    RICH_LOW: (120, 200, 80),
    RICH_FILL: (214, 178, 90),
}
_BELOW_EDGE = "rgba(192,101,74,0.95)"  # borde rojo: pallet bajo el umbral ($0)


@dataclass
class LotViz:
    """Datos mínimos de un lote para dibujarlo."""

    index: int
    weight_kg: float
    util_pct: float
    au_grade: float
    codes: list[str]
    below_threshold: bool = False  # algún metal cae bajo el umbral → paga $0


@dataclass
class Pallet:
    """Un pallet físico dentro del contenedor (subdivisión de un lote)."""

    number: int          # numeración global de carga (1..N)
    lot_index: int       # a qué lote pertenece
    weight_kg: float
    tier: str            # RICH_VERY | RICH_LOW | RICH_FILL
    au_grade: float
    util_pct: float
    below_threshold: bool
    codes: list[str] = field(default_factory=list)


def _richness_tier(au_grade: float, max_au: float) -> str:
    """Clasifica un lote por su concentración de oro relativa a la más rica.

    El oro es el metal que manda el valor y lo que el optimizador concentra, así
    que la riqueza se mide contra el lote más rico del contenedor: el tercio
    superior es **muy rico**, el del medio **poco rico** y el inferior **relleno**
    (peso que igual viaja, pero mezclado para no caer bajo el umbral).
    """
    if max_au <= 0:
        return RICH_FILL
    score = au_grade / max_au
    if score >= 0.66:
        return RICH_VERY
    if score >= 0.33:
        return RICH_LOW
    return RICH_FILL


def build_pallets(lots: list[LotViz], pallet_kg: float = PALLET_KG) -> list[Pallet]:
    """Parte los lotes en pallets de ~1 t, numerados en orden de carga.

    Los lotes se ordenan del más rico (más oro) al relleno; cada lote se reparte
    en pallets de peso parejo (~``pallet_kg`` cada uno) que heredan su categoría.
    La numeración es global y continua para dar un plan de armado del contenedor.
    """
    max_au = max((l.au_grade for l in lots), default=0.0)
    ranked = sorted(lots, key=lambda l: (-l.au_grade, -l.weight_kg))
    pallets: list[Pallet] = []
    n = 0
    for l in ranked:
        tier = _richness_tier(l.au_grade, max_au)
        count = max(1, ceil(l.weight_kg / pallet_kg))
        each = l.weight_kg / count
        for _ in range(count):
            n += 1
            pallets.append(Pallet(
                number=n, lot_index=l.index, weight_kg=each, tier=tier,
                au_grade=l.au_grade, util_pct=l.util_pct,
                below_threshold=l.below_threshold, codes=list(l.codes),
            ))
    return pallets


def _util_color(util_pct: float, alpha: float = 1.0) -> str:
    """Ámbar (bajo) → verde (alto) según el % aprovechado, en el rango 70–100."""
    t = max(0.0, min(1.0, (util_pct - 70.0) / 30.0))
    r = int(245 + (34 - 245) * t)
    g = int(158 + (197 - 158) * t)
    b = int(11 + (94 - 11) * t)
    return f"rgba({r},{g},{b},{alpha})"


def _cuboid(x0, x1, y0, y1, z0, z1, color, name, hover, opacity=0.92):
    xs = [x0, x1, x1, x0, x0, x1, x1, x0]
    ys = [y0, y0, y1, y1, y0, y0, y1, y1]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]
    # 12 triángulos (2 por cara).
    i = [0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6]
    k = [2, 3, 6, 7, 5, 4, 6, 7, 7, 4, 6, 5]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i, j=j, k=k,
        color=color, opacity=opacity, flatshading=True,
        name=name, hovertext=hover, hoverinfo="text",
        lighting=dict(ambient=0.55, diffuse=0.9, specular=0.25, roughness=0.5),
        lightposition=dict(x=120, y=200, z=140),
    )


def _wire_box(x0, x1, y0, y1, z0, z1, color="rgba(46,138,35,0.45)"):
    """Aristas del contenedor (12 líneas) como una sola traza."""
    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    xs, ys, zs = [], [], []
    for a, b in edges:
        xs += [v[a][0], v[b][0], None]
        ys += [v[a][1], v[b][1], None]
        zs += [v[a][2], v[b][2], None]
    return go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines",
        line=dict(color=color, width=4), hoverinfo="skip", showlegend=False,
    )


def container_figure(lots: list[LotViz], container_kg: float) -> go.Figure:
    """Figura 3D del contenedor con sus lotes apilados a lo largo."""
    shipped = sum(l.weight_kg for l in lots) or 1.0
    fig = go.Figure()

    # Caja de vidrio del contenedor (capacidad total) + piso tenue.
    fig.add_trace(_wire_box(0, _LEN, 0, _WID, 0, _HGT))
    fig.add_trace(_cuboid(
        0, _LEN, 0, _WID, 0, 0.02, "rgba(141,224,91,0.20)", "piso", "Contenedor",
        opacity=0.3,
    ))

    # Lotes como bloques a lo largo del eje X, tamaño ∝ peso.
    cursor = 0.0
    annos = []
    for l in lots:
        seg = (l.weight_kg / container_kg) * _LEN
        x0, x1 = cursor + _GAP / 2, cursor + seg - _GAP / 2
        cursor += seg
        hover = (
            f"<b>Lote {l.index}</b><br>{l.weight_kg/1000:,.1f} t · "
            f"{l.util_pct:.0f}% aprovechado<br>Au {l.au_grade:.0f} g/t · "
            f"{len(l.codes)} pilas"
        )
        fig.add_trace(_cuboid(
            x0, x1, 0.06, _WID - 0.06, 0.04, _HGT - 0.08,
            _util_color(l.util_pct), f"Lote {l.index}", hover,
        ))
        annos.append(dict(
            x=(x0 + x1) / 2, y=_WID / 2, z=_HGT + 0.45,
            text=f"<b>Lote {l.index}</b><br>{l.util_pct:.0f}%",
            showarrow=False, font=dict(size=13, color="#16241B"),
        ))

    fill_pct = 100.0 * shipped / container_kg
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False, range=[-0.3, _LEN + 0.3]),
            yaxis=dict(visible=False, range=[-0.3, _WID + 0.3]),
            zaxis=dict(visible=False, range=[0, _HGT + 1.0]),
            aspectmode="manual",
            aspectratio=dict(x=3.2, y=0.8, z=0.9),
            camera=dict(eye=dict(x=1.7, y=-1.9, z=1.1)),
            annotations=annos,
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        title=dict(
            text=f"Contenedor · {shipped/1000:,.1f} t / {container_kg/1000:,.0f} t "
            f"({fill_pct:.0f}% lleno)",
            x=0.5, y=0.97, font=dict(size=14, color="#5B6660", family="Space Grotesk"),
        ),
    )
    return fig


def pallet_figure(pallets: list[Pallet], container_kg: float) -> go.Figure:
    """Plano de carga: los pallets en una grilla 2-de-ancho, numerados y por color.

    Representa cómo se arma físicamente el contenedor: dos columnas de pallets a
    lo largo (como en un 40' real), cada bloque coloreado por su categoría de
    riqueza y rotulado con su número de carga. Los pallets bajo el umbral se
    marcan con borde rojo (riesgo de pagar $0).
    """
    fig = go.Figure()
    fig.add_trace(_wire_box(0, _LEN, 0, _WID, 0, _HGT))
    fig.add_trace(_cuboid(
        0, _LEN, 0, _WID, 0, 0.02, "rgba(141,224,91,0.20)", "piso", "Contenedor",
        opacity=0.3,
    ))

    n = len(pallets)
    if n == 0:
        return fig

    cols = 2 if n > 1 else 1
    rows = ceil(n / cols)
    cell_len = _LEN / rows          # avanza a lo largo (X)
    cell_wid = _WID / cols          # dos columnas a lo ancho (Y)
    mx, my = cell_len * 0.10, cell_wid * 0.12  # márgenes entre pallets

    annos = []
    below_edges = {"x": [], "y": [], "z": []}
    for p in pallets:
        idx = p.number - 1
        row, col = idx // cols, idx % cols
        x0, x1 = row * cell_len + mx, (row + 1) * cell_len - mx
        y0, y1 = col * cell_wid + my, (col + 1) * cell_wid - my
        # Altura ∝ peso (un pallet lleno ≈ 1 t llega casi al tope).
        h = 0.5 + min(1.0, p.weight_kg / PALLET_KG) * (_HGT - 0.7)
        z0, z1 = 0.04, 0.04 + h
        r, g, b = _TIER_COLOR[p.tier]
        hover = (
            f"<b>Pallet {p.number}</b> · {p.tier}<br>"
            f"Lote {p.lot_index} · {p.weight_kg:,.0f} kg<br>"
            f"Au {p.au_grade:.0f} g/t · {p.util_pct:.0f}% aprovechado"
            + ("<br><b>⚠ bajo el umbral (paga $0)</b>" if p.below_threshold else "")
        )
        fig.add_trace(_cuboid(
            x0, x1, y0, y1, z0, z1, f"rgba({r},{g},{b},0.95)",
            f"Pallet {p.number}", hover,
        ))
        annos.append(dict(
            x=(x0 + x1) / 2, y=(y0 + y1) / 2, z=z1 + 0.18,
            text=f"<b>{p.number}</b>", showarrow=False,
            font=dict(size=12, color="#16241B"),
        ))
        if p.below_threshold:
            for (ax, ay) in [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]:
                below_edges["x"].append(ax)
                below_edges["y"].append(ay)
                below_edges["z"].append(z1)
            below_edges["x"].append(None)
            below_edges["y"].append(None)
            below_edges["z"].append(None)

    if below_edges["x"]:
        fig.add_trace(go.Scatter3d(
            x=below_edges["x"], y=below_edges["y"], z=below_edges["z"],
            mode="lines", line=dict(color=_BELOW_EDGE, width=6),
            hoverinfo="skip", showlegend=False,
        ))

    shipped = sum(p.weight_kg for p in pallets)
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False, range=[-0.3, _LEN + 0.3]),
            yaxis=dict(visible=False, range=[-0.3, _WID + 0.3]),
            zaxis=dict(visible=False, range=[0, _HGT + 1.0]),
            aspectmode="manual",
            aspectratio=dict(x=3.2, y=0.8, z=0.9),
            camera=dict(eye=dict(x=0.9, y=-2.0, z=1.7)),
            annotations=annos,
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        title=dict(
            text=f"Plano de carga · {n} pallets · {shipped/1000:,.1f} t",
            x=0.5, y=0.97, font=dict(size=14, color="#5B6660", family="Space Grotesk"),
        ),
    )
    return fig
