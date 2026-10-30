"""Tests for experiment configuration validation."""

import unittest

from src.config import ExperimentConfig


class ExperimentConfigTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        config = ExperimentConfig()
        self.assertGreater(config.scale_factor, 0)
        self.assertGreater(config.batch_rows, 0)
        self.assertGreater(config.repetitions, 0)

    def test_invalid_scale_factors_are_rejected(self):
        for value in (0, -1, float("inf"), float("nan"), True, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ExperimentConfig(scale_factor=value)

    def test_invalid_integer_parameters_are_rejected(self):
        for name in ("batch_rows", "repetitions"):
            for value in (0, -1, 1.5, True, "5"):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    ExperimentConfig(**{name: value})

    def test_custom_valid_values(self):
        config = ExperimentConfig(scale_factor=1, batch_rows=100, repetitions=3)
        self.assertEqual((config.scale_factor, config.batch_rows, config.repetitions), (1, 100, 3))


if __name__ == "__main__":
    unittest.main()
