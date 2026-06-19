"""Parseo de las recetas históricas (sección 6 del brief).

Una receta describe qué pilas formaron un lote y en qué proporción. Sintaxis
observada en ``refining_history.xlsx``:

    "11"                          → 100% de la pila 011
    "37 + 38"                     → pilas 037 y 038, proporción no informada
    "6 + 8*33%"                   → 008 aporta 33%; 006 el resto (67%)
    "15 + 22*(8%) + 26*(2%)"      → 022=8%, 026=2%, 015 el resto (90%)
    "1*(28%) + 2*(58%) + 14*(14%)"→ porcentajes que suman 100% (limpia)
    "3 + 4 + 9*(10%)"             → 009=10%; 003 y 004 reparten el 90% (ambigua)
    "Credicar / Credit Card..."   → texto libre, no se parsea a códigos

Reglas de resolución:
- Componente con porcentaje ``code*(p%)`` o ``code*p%`` → fracción = p/100.
- Componentes **sin** porcentaje ("base") reparten el remanente ``1 − Σp``.
- Si hay **un solo** componente base, su fracción queda determinada.
- Si hay **dos o más** bases, la proporción entre ellos es ambigua: se reparte
  por igual como *supuesto* (marcado), o se descarta según el consumidor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# code, con o sin "*", con porcentaje opcional entre paréntesis o no.
_COMPONENT_RE = re.compile(
    r"^\s*(?P<code>\d+)\s*(?:\*\s*\(?\s*(?P<pct>\d+(?:\.\d+)?)\s*%\s*\)?)?\s*$"
)


@dataclass
class ParsedRecipe:
    """Resultado de parsear una receta."""

    raw: str
    fractions: dict[str, float] = field(default_factory=dict)  # code → fracción (0..1)
    resolvable: bool = False        # ¿quedó totalmente determinada?
    assumed_equal_split: bool = False  # ¿se repartió un grupo base por igual?
    note: str = ""

    @property
    def codes(self) -> list[str]:
        return list(self.fractions)


def _norm(code: str) -> str:
    return f"{int(code):03d}"


def parse_recipe(raw: str) -> ParsedRecipe:
    """Parsea una receta a fracciones por código de pila.

    Devuelve un :class:`ParsedRecipe`. Si la receta es texto libre (nombres en
    vez de códigos) o tiene grupos base ambiguos, ``resolvable`` es ``False``
    (aunque para grupos base se entrega igual el reparto equitativo, marcado).
    """
    raw = (raw or "").strip()
    if not raw:
        return ParsedRecipe(raw=raw, note="vacía")

    tokens = [t for t in raw.split("+")]
    labeled: dict[str, float] = {}
    bases: list[str] = []
    for tok in tokens:
        m = _COMPONENT_RE.match(tok)
        if not m:
            return ParsedRecipe(raw=raw, note="texto libre / no parseable")
        code = _norm(m.group("code"))
        if m.group("pct") is not None:
            labeled[code] = labeled.get(code, 0.0) + float(m.group("pct")) / 100.0
        else:
            bases.append(code)

    labeled_sum = sum(labeled.values())
    remainder = 1.0 - labeled_sum

    fractions = dict(labeled)

    if not bases:
        # Todos los componentes con porcentaje.
        resolvable = abs(labeled_sum - 1.0) < 0.02
        note = "porcentajes completos" if resolvable else f"porcentajes suman {labeled_sum:.0%}"
        return ParsedRecipe(raw, fractions, resolvable=resolvable, note=note)

    if remainder < -1e-6:
        return ParsedRecipe(raw, fractions, note="porcentajes exceden 100%")

    if len(bases) == 1:
        fractions[bases[0]] = fractions.get(bases[0], 0.0) + remainder
        return ParsedRecipe(raw, fractions, resolvable=True, note="base única (remanente)")

    # Varias bases → proporción ambigua. Reparto equitativo como supuesto.
    share = remainder / len(bases)
    for b in bases:
        fractions[b] = fractions.get(b, 0.0) + share
    return ParsedRecipe(
        raw,
        fractions,
        resolvable=False,
        assumed_equal_split=True,
        note=f"{len(bases)} bases ambiguas; repartidas por igual (supuesto)",
    )
