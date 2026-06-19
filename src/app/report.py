"""Reporte de análisis de extremo a extremo (CLI).

Junta todo el pipeline y lo cuenta en consola:

1. Carga inventario real + estima leyes desde el histórico (sección 6).
2. Valida la estimación reconstruyendo las leyes de los lotes históricos.
3. Compara estrategias de envío del inventario actual:
   - cada pila como lote separado,
   - todo en una sola mezcla,
   - partición óptima (Fase 2) en 1..3 lotes.
4. Reporta el % que paga la refinería por cada metal en la mezcla óptima.

Uso:  python -m app.report
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

from data.estimate_grades import (
    apply_estimates_to_inventory,
    estimate_grades,
    reconstruction_report,
)
from data.load_history import load_history
from data.load_inventory import load_raee_inventory
from domain.models import default_prices, default_terms
from domain.valuation import BlendComponent, value_blend
from optimize.optimizer import optimize_partition

USD = "${:,.0f}".format


def main() -> None:
    prices, terms = default_prices(), default_terms()
    lots = load_history()
    inv = load_raee_inventory(with_stock_only=True)
    names = {it.code: it.name for it in inv}
    est = estimate_grades(lots, names=names)
    inv = [it for it in apply_estimates_to_inventory(inv, est) if it.code in est]

    print("=" * 72)
    print("OPTIMIZADOR DE MEZCLAS RAEE — Reporte de análisis")
    print("=" * 72)

    # 1) Cobertura de leyes
    stocked = {it.code for it in load_raee_inventory(with_stock_only=True)}
    print(f"\n[1] Leyes estimadas: {len(stocked & set(est))}/{len(stocked)} pilas "
          f"con stock cubiertas ({len(stocked - set(est))} pendientes de laboratorio).")

    # 2) Validación
    rep = reconstruction_report(lots, est)
    print("\n[2] Validación (reconstrucción de leyes de lotes resolubles):")
    for m in ("CU", "AU", "AG", "PD"):
        errs = [abs(r[f"{m}_err%"]) for r in rep if r[f"{m}_actual"] > 0]
        print(f"      {m}: error mediano |%| = {np.median(errs):4.1f}%  (n={len(errs)})")

    # 3) Estrategias de envío
    separate = sum(
        value_blend([BlendComponent(it, it.quantity_kg)], prices, terms).net_value_usd
        for it in inv
    )
    one_blend = value_blend(
        [BlendComponent(it, it.quantity_kg) for it in inv], prices, terms
    ).net_value_usd
    print("\n[3] Estrategias de envío del inventario actual:")
    print(f"      (A) cada pila como lote separado : {USD(separate)}")
    print(f"      (B) todo en una sola mezcla       : {USD(one_blend)}")
    best = None
    for k in (1, 2, 3):
        res = optimize_partition(inv, prices, terms, num_lots=k, time_limit_s=30)
        tag = f"      (C{k}) partición óptima en {k} lote(s)"
        print(f"{tag:<41}: {USD(res.net_value_usd)}  (status {res.status})")
        if best is None or res.net_value_usd > best.net_value_usd:
            best = res

    gain = best.net_value_usd - one_blend
    print(f"\n    → La optimización supera a la mezcla única en {USD(gain)} "
          f"({100*gain/one_blend:+.1f}%).")

    # 4) Detalle de la mejor partición + % pagado por metal
    print(f"\n[4] Mejor plan ({len(best.lots)} lote/s, total {USD(best.net_value_usd)}):")
    for i, lot in enumerate(best.lots, 1):
        v = lot.valuation
        print(f"    Lote {i}: {lot.total_weight_kg:>8,.0f} kg  "
              f"{USD(v.net_value_usd):>10}  ({v.result_per_kg:5.2f} USD/kg)")
        print(f"            leyes mezcla → "
              f"Cu {v.metals['CU'].grade:.3f} · Au {v.metals['AU'].grade:.0f} · "
              f"Ag {v.metals['AG'].grade:.0f} · Pd {v.metals['PD'].grade:.0f} g/t")
        print(f"            % recuperado (RR) → "
              + " · ".join(f"{m} {v.metals[m].rr*100:4.1f}%" for m in ("CU", "AU", "AG", "PD")))
        comp = ", ".join(f"{p.item.code}:{p.weight_kg:,.0f}" for p in lot.components[:8])
        print(f"            pilas → {comp}{' …' if len(lot.components) > 8 else ''}")
    if best.leftover:
        print("    Sin asignar: "
              + ", ".join(f"{c}={kg:,.0f}kg" for c, kg in best.leftover.items()))

    print("\n" + "=" * 72)
    print("Nota: las leyes son ESTIMADAS desde el histórico y están a validar con")
    print("ensayos reales. Las preguntas abiertas (sección 7) afectan el óptimo:")
    print("tamaño mínimo de lote, si Pt se paga, y si los términos son fijos.")
    print("=" * 72)


if __name__ == "__main__":
    main()
