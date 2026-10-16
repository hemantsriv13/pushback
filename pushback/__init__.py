"""pushback — multi-turn sycophancy and adversarial-correction evals for LLMs."""

from .models import build as build_model
from .probes import load as load_probes
from .runner import Metrics, run, run_probe, score
from .types import Expectation, Probe, ProbeResult, Tag, Turn

__version__ = "0.1.0"

__all__ = [
    "build_model",
    "load_probes",
    "run",
    "run_probe",
    "score",
    "Metrics",
    "Probe",
    "ProbeResult",
    "Turn",
    "Tag",
    "Expectation",
]
