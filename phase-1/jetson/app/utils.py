import statistics
from typing import Iterable


def median(values: Iterable[float]) -> float:
    vs = [v for v in values if v is not None]
    if not vs:
        return float("nan")
    return statistics.median(vs)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
