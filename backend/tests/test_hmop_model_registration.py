import json
from pathlib import Path
import sys

import joblib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.app.services.kos_service import run_kos_diagnosis  # noqa: E402


REGISTRY = ROOT / "ml" / "artifacts" / "p3_alpha" / "model_registry_v0.8.json"


def test_hmop_dual_track_models_are_registered_and_loadable():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["models"]
    for track in ("prod", "eco"):
        model_id = f"hm_op_{track}_Full_RandomForest"
        entry = registry[model_id]
        assert entry["status"] == "exploratory"
        assert entry["frontend_enabled"] is False
        assert entry["metrics"]["test_spearman"] >= 0.85
        bundle = joblib.load(ROOT / entry["model_file"])
        assert "model" in bundle and "feature_cols" in bundle


def test_hmop_service_forces_review_instead_of_silent_approval():
    result = run_kos_diagnosis(
        {"Cd": 2.0, "Pb": 500.0, "BaP": 800.0, "pH": 4.8},
        track="prod", subset="hm_op",
    )
    assert "error" not in result
    assert result["model_status"] == "exploratory"
    assert result["review_required"] is True
