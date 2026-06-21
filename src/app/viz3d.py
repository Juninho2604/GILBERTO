"""Visualización 3D del contenedor y sus lotes (plotly).

Dibuja el contenedor como una caja de vidrio y cada **lote** como un bloque de
carga apilado a lo largo, con tamaño proporcional a su peso y color según el
**% de material aprovechado** (ámbar = bajo, verde = alto). Interactivo: se rota
y se hace zoom. La idea es "ver" el contenedor armado, no leer una tabla.
"""

from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go

# Proporciones estilizadas de un contenedor de 40' (largo : ancho : alto).
_LEN, _WID, _HGT = 12.0, 2.4, 2.6
_GAP = 0.06  # separación visual entre lotes


@dataclass
class LotViz:
    """Datos mínimos de un lote para dibujarlo."""

    index: int
    weight_kg: float
    util_pct: float
    au_grade: float
    codes: list[str]


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
