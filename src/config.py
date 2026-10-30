"""Validation for the planned experiment configuration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentConfig:
    """Parameters for generating data and repeating query measurements."""

    scale_factor: float = 0.1
    batch_rows: int = 10000
    repetitions: int = 5

    def __post_init__(self):
        if isinstance(self.scale_factor, bool) or not isinstance(self.scale_factor, (int, float)):
            raise ValueError("scale_factor must be a positive finite number")
        import math

        if not math.isfinite(self.scale_factor) or self.scale_factor <= 0:
            raise ValueError("scale_factor must be a positive finite number")
        for name in ("batch_rows", "repetitions"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
