"""Datos de arranque para el simulador (sección 10 del brief).

Mientras no existan los ``.xlsx`` reales ni la tabla de leyes estimadas
(sección 6), el simulador arranca con:

- los mayores volúmenes de inventario RAEE observados (leyes en 0, pendientes
  de estimación/laboratorio, marcadas como tales);
- una pila de demostración con las leyes del **Apéndice A**, para ver la
  fórmula viva contra números reales desde el primer minuto.

Todo es editable en la UI; estos valores son solo un punto de partida.
"""

from __future__ import annotations

from domain.models import Category, GradeSource, InventoryItem


def reference_inventory() -> list[InventoryItem]:
    """Mayores volúmenes RAEE con stock (sección 10). Leyes pendientes."""
    pending = dict(grade_source=GradeSource.MANUAL, grade_confidence=None)
    items = [
        InventoryItem("LGM", "Bajo Grado Marrón", quantity_kg=13_330, **pending),
        InventoryItem("B3", "Boards Tipo 3", quantity_kg=4_206, **pending),
        InventoryItem("B2", "Boards Tipo 2", quantity_kg=3_479, **pending),
        InventoryItem("B1", "Boards Tipo 1", quantity_kg=2_924, **pending),
        InventoryItem("CEN", "Centrales Telefónicas", quantity_kg=2_923, **pending),
        InventoryItem("LGV", "Bajo Grado Verde", quantity_kg=2_809, **pending),
    ]
    for it in items:
        it.category = Category.RAEE
        it.moisture = 0.01
    return items


def appendix_a_demo_item() -> InventoryItem:
    """Pila de demo con las leyes verificadas del Apéndice A.

    Cargando 5184 kg de esta pila, el simulador reproduce el lote del
    Apéndice A (net ≈ 70.335,68 USD; 13,57 USD/kg).
    """
    return InventoryItem(
        code="DEMO-A",
        name="Lote Apéndice A (demo)",
        category=Category.RAEE,
        quantity_kg=5_184,
        moisture=0.009,
        grade_cu=0.2113,
        grade_au=84.4,
        grade_ag=646.0,
        grade_pt=0.0,
        grade_pd=4.3,
        grade_source=GradeSource.LAB,
        grade_confidence=1.0,
    )


def seed_inventory() -> list[InventoryItem]:
    """Inventario inicial completo para el simulador."""
    return [appendix_a_demo_item(), *reference_inventory()]
