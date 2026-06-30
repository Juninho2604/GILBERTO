"""Tests del bono de éxito (analysis.bonus): por envío (forward) e histórico."""

from analysis.bonus import (
    BonusConfig,
    bono_de_envio,
    calcular_bono,
    mejora_envio,
    rescate_historico,
)


# --- Bono por envío (la base elegida: metal rescatado, hacia adelante) ----- #
def test_bono_envio_se_activa_con_rescate_y_mejora():
    be = bono_de_envio(rescatado_usd=3212.0, mejora=0.20)  # +20% > 10%
    assert be.supera_umbral is True
    assert be.activado is True
    assert abs(be.bono_usd - 0.15 * 3212.0) < 1e-9


def test_bono_envio_sin_rescate_no_paga():
    be = bono_de_envio(rescatado_usd=0.0, mejora=0.50)
    assert be.activado is False
    assert be.bono_usd == 0.0


def test_bono_envio_bajo_umbral_no_paga():
    be = bono_de_envio(rescatado_usd=3212.0, mejora=0.05)  # +5% ≤ 10%
    assert be.supera_umbral is False
    assert be.activado is False
    assert be.bono_usd == 0.0


def test_bono_envio_respeta_tasa_configurable():
    be = bono_de_envio(3000.0, 0.20, BonusConfig(tasa_bono=0.20))
    assert abs(be.bono_usd - 0.20 * 3000.0) < 1e-9


def _lots():
    # 3 lotes: dos con rescate (>0), uno sin rescate.
    return [
        {"customer_lot": 1, "rescued_usd": 200.0, "low_conf_share": 0.0},
        {"customer_lot": 2, "rescued_usd": 500.0, "low_conf_share": 0.5},
        {"customer_lot": 3, "rescued_usd": 0.0, "low_conf_share": 0.0},
    ]


def test_rescate_suma_solo_positivos():
    rc = rescate_historico(_lots())
    assert rc.total_usd == 700.0          # 200 + 500 (el tercero no aporta)
    assert rc.n_lots == 2


def test_rescate_banda_de_confianza():
    rc = rescate_historico(_lots())
    # low = 200*0 + 500*0.5 = 250 ; firme = 700 - 250 = 450
    assert rc.low_conf_usd == 250.0
    assert rc.firm_usd == 450.0
    assert abs(rc.low_conf_share - 250.0 / 700.0) < 1e-9


def test_rescate_ignora_lotes_sin_dato():
    lots = [{"customer_lot": 9, "low_conf_share": 0.0}]  # sin rescued_usd
    rc = rescate_historico(lots)
    assert rc.total_usd == 0.0
    assert rc.n_lots == 0


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
    # §8: con mejora > 10%, bono = 0.15 × rescate
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
    lots = _lots()
    b = calcular_bono(lots, [(1200.0, 1000.0)], BonusConfig(tasa_bono=0.20))
    assert abs(b.monto_usd - 0.20 * 700.0) < 1e-9
    b2 = calcular_bono(lots, [(1200.0, 1000.0)], BonusConfig(umbral_mejora=0.25))
    assert b2.activado is False
