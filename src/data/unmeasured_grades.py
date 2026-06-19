"""Leyes conservadoras (piso) para las pilas sin ensayo.

Las 15 pilas RAEE con stock que **no aparecen en ninguna receta histórica** no
tienen ley estimable por regresión. Para no dejarlas en cero (lo que las hace
invisibles para el optimizador), se les asigna una **ley conservadora** según el
tipo de material y la composición típica de la chatarra electrónica de esa
clase. El criterio es **el piso**: se elige el extremo bajo del rango de mercado,
para **no sobreprometer**. Cuando lleguen los ensayos de laboratorio, estos
valores se reemplazan (origen ``laboratorio``).

Referencias de mercado (rangos típicos de e-scrap, extremo bajo):
- Motherboards de PC: Au 30–120 g/t · Ag 100–250 · Cu 12–20% · Pd 10–25.
- Boards de laptop: más ricos, Au 80–250.
- Boards de celular limpios: Au 120–400, Ag 200–500, Pd 20–60.
- "Doradas" / gold-plated / memorias con dedos dorados: Au 100–250 (oro de chapado).
- Módems, fuentes, "sin chips": pobres, Au 15–40.
- Tantalio: no es pagador de Au/Ag/Cu/Pd por esta refinería (≈0).
"""

from __future__ import annotations

from domain.models import GradeSource, InventoryItem

# code → (CU fracción, AU g/t, AG g/t, PD g/t, nota)
CONSERVATIVE_GRADES: dict[str, dict] = {
    "007": {"cu": 0.16, "au": 45, "ag": 120, "pd": 12, "note": "Madre PIV colores (piso)"},
    "010": {"cu": 0.18, "au": 70, "ag": 180, "pd": 18, "note": "Boards T1 laptop (piso)"},
    "020": {"cu": 0.18, "au": 110, "ag": 250, "pd": 25, "note": "Celular limpio China (piso)"},
    "046": {"cu": 0.14, "au": 20, "ag": 60, "pd": 3, "note": "Madre PIV sin chips (piso)"},
    "023": {"cu": 0.10, "au": 110, "ag": 90, "pd": 4, "note": "Memorias doradas (piso)"},
    "048": {"cu": 0.16, "au": 70, "ag": 150, "pd": 15, "note": "Tablet (piso)"},
    "101": {"cu": 0.16, "au": 25, "ag": 80, "pd": 4, "note": "Módem sin BGA (piso)"},
    "035": {"cu": 0.30, "au": 120, "ag": 150, "pd": 3, "note": "Dorada base cobre (piso)"},
    "021": {"cu": 0.22, "au": 25, "ag": 80, "pd": 4, "note": "Bitcoin/ASIC (piso)"},
    "018": {"cu": 0.14, "au": 130, "ag": 180, "pd": 5, "note": "Centrales doradas (piso)"},
    "105": {"cu": 0.18, "au": 45, "ag": 120, "pd": 10, "note": "Cable box BGA (piso)"},
    "005": {"cu": 0.16, "au": 60, "ag": 150, "pd": 20, "note": "Madre PIII (piso)"},
    "058": {"cu": 0.05, "au": 2, "ag": 10, "pd": 0, "note": "Tantalio (no pagador, ≈0)"},
    "047": {"cu": 0.20, "au": 70, "ag": 150, "pd": 15, "note": "WIFI (piso)"},
    "036": {"cu": 0.05, "au": 120, "ag": 150, "pd": 2, "note": "Dorada base bronce (piso)"},
}


def apply_conservative_grades(items: list[InventoryItem]) -> list[InventoryItem]:
    """Asigna leyes conservadoras a las pilas que sigan sin ley (origen mercado)."""
    for it in items:
        has_grade = max(it.grade_cu, it.grade_au, it.grade_ag, it.grade_pt, it.grade_pd) > 0
        g = CONSERVATIVE_GRADES.get(it.code)
        if has_grade or g is None:
            continue
        it.grade_cu = float(g["cu"])
        it.grade_au = float(g["au"])
        it.grade_ag = float(g["ag"])
        it.grade_pd = float(g["pd"])
        it.grade_source = GradeSource.MARKET
        it.grade_confidence = 0.2
    return items
