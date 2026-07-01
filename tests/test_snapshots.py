"""Tests de la evolución del modelo (fotos de precisión en el tiempo)."""

from data.snapshots import load_snapshots, record_snapshot


def _analysis(fid=3.1, au=5.4, n=53, covered=25):
    return {
        "n_lots": n,
        "n_resolvable": 36,
        "money_fidelity_pct": fid,
        "precision": [
            {"metal": "AU", "median_abs_err_pct": au, "n": 36},
            {"metal": "CU", "median_abs_err_pct": 2.0, "n": 36},
        ],
        "coverage": {"covered": covered, "stocked_items": 40, "pending": 15},
    }


def test_primer_registro_se_guarda(tmp_path):
    path = tmp_path / "snaps.json"
    assert record_snapshot(_analysis(), path) is True
    snaps = load_snapshots(path)
    assert len(snaps) == 1
    s = snaps[0]
    assert s["money_fidelity_pct"] == 3.1
    assert s["err_pct"]["AU"] == 5.4
    assert s["n_lots"] == 53
    assert s["timestamp"]


def test_recalcular_sin_cambios_no_duplica(tmp_path):
    path = tmp_path / "snaps.json"
    record_snapshot(_analysis(), path)
    assert record_snapshot(_analysis(), path) is False  # idéntico → no agrega
    assert len(load_snapshots(path)) == 1


def test_mejora_agrega_nueva_foto(tmp_path):
    path = tmp_path / "snaps.json"
    record_snapshot(_analysis(fid=3.1, n=53), path)
    # Llega una liquidación nueva y el error baja: nueva foto.
    assert record_snapshot(_analysis(fid=2.8, au=4.9, n=54), path) is True
    snaps = load_snapshots(path)
    assert len(snaps) == 2
    assert snaps[-1]["money_fidelity_pct"] < snaps[-2]["money_fidelity_pct"]
    assert snaps[-1]["n_lots"] == 54


def test_archivo_corrupto_no_crashea(tmp_path):
    path = tmp_path / "snaps.json"
    path.write_text("{roto", encoding="utf-8")
    assert load_snapshots(path) == []
    assert record_snapshot(_analysis(), path) is True  # se recupera escribiendo
