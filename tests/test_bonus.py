"""Tests del bono de éxito (analysis.bonus) — criterios de aceptación §8."""

from analysis.bonus import (
    BonusConfig,
    calcular_bono,
    mejora_envio,
    subpago_historico,
)


def _lots():
    # 3 lotes: dos con sub-pago (óptimo > real), uno sin (óptimo ≤ real).
    return [
        {"customer_lot": 1, "actual_net_usd": 1000.0, "model_optimal_usd": 1200.0,
         "sub_pago_usd": 200.0, "low_conf_share": 0.0},
        {"customer_lot": 2, "actual_net_usd": 5000.0, "model_optimal_usd": 5500.0,
         "sub_pago_usd": 500.0, "low_conf_share": 0.5},
        {"customer_lot": 3, "actual_net_usd": 800.0, "model_optimal_usd": 700.0,
         "sub_pago_usd": 0.0, "low_conf_share": 0.0},
    ]


def test_subpago_suma_solo_positivos():
    sp = subpago_historico(_lots())
    assert sp.total_usd == 700.0          # 200 + 500 (el tercero no aporta)
    assert sp.n_lots == 2


def test_subpago_banda_de_confianza():
    sp = subpago_historico(_lots())
    # low = 200*0 + 500*0.5 = 250 ; firme = 700 - 250 = 450
    assert sp.low_conf_usd == 250.0
    assert sp.firm_usd == 450.0
    assert abs(sp.low_conf_share - 250.0 / 700.0) < 1e-9


def test_subpago_deriva_si_falta_sub_pago_usd():
    lots = [{"customer_lot": 9, "actual_net_usd": 100.0, "model_optimal_usd": 175.0}]
    sp = subpago_historico(lots)
    assert sp.total_usd == 75.0           # max(0, 175 - 100)


def test_mejora_supera_umbral():
    mj = mejora_envio([(1200.0, 1000.0)])  # +20%
    assert abs(mj.mejora - 0.20) < 1e-9
    assert mj.supera_umbral is True


def test_mejora_bajo_umbral():
    mj = mejora_envio([(1050.0, 1000.0)])  # +5%
    assert mj.supera_umbral is False


def test_mejora_ventana_promedia_varios_envios():
    cfg = BonusConfig(ventana_envios=2)
    # envío 1: +5% ; envío 2: +25% ; agregado: (1050+1250-2000)/2000 = 15%
    mj = mejora_envio([(1050.0, 1000.0), (1250.0, 1000.0)], cfg)
    assert mj.n_envios == 2
    assert abs(mj.mejora - 0.15) < 1e-9
    assert mj.supera_umbral is True


def test_bono_se_activa_con_mejora_mayor_10():
    # §8: con mejora > 10%, bono = 0.15 × sub_pago_historico
    b = calcular_bono(_lots(), [(1200.0, 1000.0)])
    assert b.activado is True
    assert abs(b.monto_usd - 0.15 * 700.0) < 1e-9
    assert abs(b.monto_firme_usd - 0.15 * 450.0) < 1e-9


def test_bono_no_se_activa_bajo_umbral():
    # §8: con mejora ≤ 10%, el bono queda en 0
    b = calcular_bono(_lots(), [(1050.0, 1000.0)])
    assert b.activado is False
    assert b.monto_usd == 0.0


def test_bono_sin_envios_no_se_activa():
    b = calcular_bono(_lots(), [])
    assert b.activado is False
    assert b.monto_usd == 0.0
    assert b.base_usd == 700.0            # la base existe igual


def test_parametros_recalculan_sin_tocar_codigo():
    # §8: cambiar umbral / tasa recalcula.
    lots = _lots()
    # tasa 0.20 en vez de 0.15
    b = calcular_bono(lots, [(1200.0, 1000.0)], BonusConfig(tasa_bono=0.20))
    assert abs(b.monto_usd - 0.20 * 700.0) < 1e-9
    # umbral 0.25 → +20% ya no dispara
    b2 = calcular_bono(lots, [(1200.0, 1000.0)], BonusConfig(umbral_mejora=0.25))
    assert b2.activado is False
