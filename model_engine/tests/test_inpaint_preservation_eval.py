from __future__ import annotations

import unittest

from PIL import Image

from model_engine.scripts.evaluate_inpaint_preservation import _compute_comparison_metrics


class InpaintPreservationEvalTests(unittest.TestCase):
    def test_experiment_overlay_preserves_outside_mask_better_than_full_page_baseline(self) -> None:
        original = Image.new("RGBA", (4, 4), (100, 100, 100, 255))
        baseline = Image.new("RGBA", (4, 4), (120, 120, 120, 255))
        experiment = original.copy()
        experiment.putpixel((1, 1), (150, 150, 150, 255))
        mask = Image.new("L", (4, 4), 0)
        mask.putpixel((1, 1), 255)

        metrics = _compute_comparison_metrics(
            original=original,
            baseline=baseline,
            experiment=experiment,
            mask=mask,
            changed_threshold=8,
        )

        self.assertTrue(metrics["comparison"]["experiment_full_mse_lower_than_baseline"])
        self.assertTrue(metrics["comparison"]["experiment_outside_mask_mse_lower_than_baseline"])
        self.assertEqual(0.0, metrics["experiment"]["outside_mask"]["mse"])
        self.assertGreater(metrics["baseline"]["outside_mask"]["mse"], 0.0)

    def test_empty_mask_reports_none_for_inside_mask_metrics(self) -> None:
        original = Image.new("RGBA", (2, 2), (10, 10, 10, 255))
        candidate = Image.new("RGBA", (2, 2), (10, 10, 10, 255))
        mask = Image.new("L", (2, 2), 0)

        metrics = _compute_comparison_metrics(
            original=original,
            baseline=candidate,
            experiment=candidate,
            mask=mask,
            changed_threshold=8,
        )

        self.assertEqual(0, metrics["mask_pixel_count"])
        self.assertIsNone(metrics["baseline"]["inside_mask"]["mse"])
        self.assertIsNone(metrics["experiment"]["inside_mask"]["mse"])


if __name__ == "__main__":
    unittest.main()
