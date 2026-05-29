from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Callable, Optional
from urllib.parse import unquote, urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
from PIL import Image

from model_engine.builtin_models import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    MINDLOGIC_IMAGE_MODEL,
    MINDLOGIC_INPAINT_MODEL_ID,
    NANOBANANA_INPAINT_MODEL_ID,
    register_craft_text_detection_model,
    register_mindlogic_inpaint_model,
    register_nanobanana_inpaint_model,
)
from model_engine.config.runtime_config import load_runtime_config, runtime_config_value
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import ExecutionMode, StageRequest, StageResponse, StageRuntimeContext
from model_engine.models import ModelRegistry
from model_engine.orchestrator import PipelineOrchestrator
from model_engine.stages import AdapterBackedStage, Stage, run_mask_or_erase_planning


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_DATASET_DIR = "model_engine/datasets/benchmark"
DEFAULT_WORKSPACE_DIR = "model_engine/.runtime/inpaint_preservation_eval"


class FunctionStage(Stage):
    def __init__(
        self,
        stage_name: str,
        handler: Callable[[StageRequest], StageResponse],
        *,
        config: Optional[dict[str, object]] = None,
    ) -> None:
        self._stage_name = stage_name
        self._handler = handler
        self._config = dict(config or {})

    @property
    def stage_name(self) -> str:
        return self._stage_name

    def stage_config(self) -> dict[str, object]:
        return dict(self._config)

    def run(self, request: StageRequest) -> StageResponse:
        return self._handler(request)


@dataclass(frozen=True)
class PageEvaluation:
    image_path: Path
    page_id: str
    workspace_dir: Path
    original_path: Path
    provider_output_path: Path
    inpainting_layer_path: Path
    experiment_composite_path: Path
    mask_path: Path
    metrics: dict[str, object]
    stage_reports: list[dict[str, object]]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate source preservation for the current manga text-removal inpaint pipeline. "
            "Baseline is the provider full-page output. Experiment is the UI-style alpha overlay "
            "composited on top of the original page."
        )
    )
    parser.add_argument("--dataset-dir", default=DEFAULT_DATASET_DIR)
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE_DIR)
    parser.add_argument("--provider", choices=("mindlogic", "nanobanana"), default="mindlogic")
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip pages that already have metrics.")
    parser.add_argument("--dry-run", action="store_true", help="List benchmark pages without provider calls.")
    parser.add_argument("--padding", type=int, default=12)
    parser.add_argument("--output-mask-dilate-radius", type=int, default=2)
    parser.add_argument("--text-threshold", type=float, default=0.7)
    parser.add_argument("--link-threshold", type=float, default=0.4)
    parser.add_argument("--low-text", type=float, default=0.4)
    parser.add_argument("--changed-threshold", type=float, default=8.0)
    parser.add_argument("--alpha-threshold", type=int, default=0)
    parser.add_argument("--write-previews", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir).resolve()
    workspace_dir = Path(args.workspace).resolve()
    pages = _collect_images(dataset_dir)
    if args.limit is not None:
        pages = pages[: args.limit]

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dataset_dir": str(dataset_dir),
                    "workspace_dir": str(workspace_dir),
                    "page_count": len(pages),
                    "pages": [str(path) for path in pages],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not pages:
        raise RuntimeError(f"No benchmark images found in {dataset_dir}")

    api_key = _resolve_api_key(args.provider, args.api_key_env)
    if not api_key:
        env_hint = args.api_key_env or _default_api_key_env(args.provider)
        raise RuntimeError(
            f"Missing {args.provider} API key. Set {env_hint} or runtime_config.json before running."
        )

    workspace_dir.mkdir(parents=True, exist_ok=True)
    result_dir = workspace_dir / "results"
    page_output_dir = result_dir / "pages"
    page_output_dir.mkdir(parents=True, exist_ok=True)

    evaluations: list[PageEvaluation] = []
    failures: list[dict[str, object]] = []
    for index, image_path in enumerate(pages, start=1):
        page_id = _page_id(index, image_path)
        metrics_path = page_output_dir / page_id / "metrics.json"
        if args.resume and metrics_path.exists():
            evaluations.append(_read_existing_evaluation(metrics_path))
            print(f"[skip] {page_id} already evaluated")
            continue
        try:
            print(f"[run] {index}/{len(pages)} {image_path}")
            evaluations.append(
                _evaluate_page(
                    image_path=image_path,
                    page_id=page_id,
                    workspace_root=workspace_dir,
                    output_root=page_output_dir,
                    provider=args.provider,
                    model_name=args.model_name or _default_model_name(args.provider),
                    api_key=api_key,
                    padding=args.padding,
                    output_mask_dilate_radius=args.output_mask_dilate_radius,
                    text_threshold=args.text_threshold,
                    link_threshold=args.link_threshold,
                    low_text=args.low_text,
                    changed_threshold=args.changed_threshold,
                    alpha_threshold=args.alpha_threshold,
                    write_previews=args.write_previews,
                )
            )
        except Exception as exc:
            failure = {
                "image_path": str(image_path),
                "page_id": page_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
            failures.append(failure)
            print(f"[fail] {page_id}: {type(exc).__name__}: {exc}", file=sys.stderr)

    _write_results(result_dir, evaluations, failures)
    print(json.dumps(_summary_payload(evaluations, failures), ensure_ascii=False, indent=2))
    return 1 if failures and not evaluations else 0


def _evaluate_page(
    *,
    image_path: Path,
    page_id: str,
    workspace_root: Path,
    output_root: Path,
    provider: str,
    model_name: str,
    api_key: str,
    padding: int,
    output_mask_dilate_radius: int,
    text_threshold: float,
    link_threshold: float,
    low_text: float,
    changed_threshold: float,
    alpha_threshold: int,
    write_previews: bool,
) -> PageEvaluation:
    page_workspace = workspace_root / "workspaces" / page_id
    page_workspace.mkdir(parents=True, exist_ok=True)
    page_output_dir = output_root / page_id
    page_output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as image:
        original = image.convert("RGBA")
    original_path = page_output_dir / "original.png"
    original.save(original_path)

    input_artifact = ArtifactDescriptor(
        artifact_ref=f"artifact://benchmark/{page_id}/input_bitmap",
        kind="bitmap",
        media_type=_media_type_for_suffix(image_path.suffix),
        uri=image_path.resolve().as_uri(),
        width=original.width,
        height=original.height,
        metadata={"role": "input_page", "source_path": str(image_path)},
    )
    document = DocumentIR(
        id=f"benchmark_{page_id}",
        name=image_path.name,
        width=original.width,
        height=original.height,
    )

    registry = ModelRegistry()
    register_craft_text_detection_model(registry)
    register_nanobanana_inpaint_model(registry)
    register_mindlogic_inpaint_model(registry)

    stages: list[Stage] = [
        AdapterBackedStage(
            "text_detection",
            stage_kind=StageKind.TEXT_DETECTION,
            registry=registry,
            preferred_model_id=CRAFT_TEXT_DETECTION_MODEL_ID,
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "text_threshold": text_threshold,
                "link_threshold": link_threshold,
                "low_text": low_text,
            },
        ),
        FunctionStage(
            "mask_or_erase_planning",
            run_mask_or_erase_planning,
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "padding": padding,
                "target_layer_id": "layer_inpainting",
            },
        ),
        AdapterBackedStage(
            "inpaint",
            stage_kind=StageKind.INPAINT,
            registry=registry,
            preferred_model_id=_inpaint_model_id(provider),
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "model_name": model_name,
                "provider": provider,
                "target_layer_id": "layer_inpainting",
                "output_mask_mode": "mask_artifact",
                "output_mask_dilate_radius": output_mask_dilate_radius,
            },
        ),
    ]

    result = PipelineOrchestrator().run(
        document=document,
        stages=stages,
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=page_workspace.as_uri(),
            requested_by="evaluate_inpaint_preservation",
            session_provider_secrets={provider: api_key},
        ),
        initial_artifacts={input_artifact.artifact_ref: input_artifact},
        job_id=f"job_eval_{page_id}",
        pipeline_id=f"pipe_eval_{page_id}",
    )
    if result.status.value != "succeeded":
        raise RuntimeError(f"Pipeline did not succeed: status={result.status.value}")

    provider_output = _artifact_by_role(result.artifacts, "provider_output_bitmap")
    inpainting_layer = _artifact_by_role(result.artifacts, "inpainting_layer_bitmap")
    provider_output_path = _copy_image_artifact(
        provider_output,
        page_output_dir / "baseline_provider_output.png",
        original.size,
    )
    inpainting_layer_path = _copy_image_artifact(
        inpainting_layer,
        page_output_dir / "experiment_inpainting_layer.png",
        original.size,
    )

    with Image.open(provider_output_path) as image:
        baseline = image.convert("RGBA")
    with Image.open(inpainting_layer_path) as image:
        overlay = image.convert("RGBA")

    experiment = Image.alpha_composite(original, overlay)
    experiment_composite_path = page_output_dir / "experiment_composite.png"
    experiment.save(experiment_composite_path)

    mask = overlay.getchannel("A").point(lambda value: 255 if value > alpha_threshold else 0)
    mask_path = page_output_dir / "experiment_alpha_mask.png"
    mask.save(mask_path)

    metrics = _compute_comparison_metrics(
        original=original,
        baseline=baseline,
        experiment=experiment,
        mask=mask,
        changed_threshold=changed_threshold,
    )
    metrics.update(
        {
            "page_id": page_id,
            "image_path": str(image_path),
            "provider": provider,
            "model_name": model_name,
            "image_width": original.width,
            "image_height": original.height,
            "padding": padding,
            "output_mask_dilate_radius": output_mask_dilate_radius,
            "text_threshold": text_threshold,
            "link_threshold": link_threshold,
            "low_text": low_text,
            "changed_threshold": changed_threshold,
            "alpha_threshold": alpha_threshold,
            "baseline_path": str(provider_output_path),
            "experiment_layer_path": str(inpainting_layer_path),
            "experiment_composite_path": str(experiment_composite_path),
            "mask_path": str(mask_path),
        }
    )

    if write_previews:
        _write_side_by_side_preview(
            page_output_dir / "preview_original_baseline_experiment.png",
            original,
            baseline,
            experiment,
        )

    stage_reports = [
        {
            "stage_name": report.stage_name,
            "status": report.status.value,
            "metrics": report.metrics,
            "warnings": report.warnings,
            "error_code": report.error_code,
            "error_message": report.error_message,
            "output_refs": report.output_refs,
        }
        for report in result.stage_reports
    ]
    evaluation = PageEvaluation(
        image_path=image_path,
        page_id=page_id,
        workspace_dir=page_workspace,
        original_path=original_path,
        provider_output_path=provider_output_path,
        inpainting_layer_path=inpainting_layer_path,
        experiment_composite_path=experiment_composite_path,
        mask_path=mask_path,
        metrics=metrics,
        stage_reports=stage_reports,
    )
    _write_page_metrics(page_output_dir / "metrics.json", evaluation)
    return evaluation


def _compute_comparison_metrics(
    *,
    original: Image.Image,
    baseline: Image.Image,
    experiment: Image.Image,
    mask: Image.Image,
    changed_threshold: float,
) -> dict[str, object]:
    original_arr = _rgb_array(original)
    baseline_arr = _rgb_array(_ensure_size(baseline, original.size))
    experiment_arr = _rgb_array(_ensure_size(experiment, original.size))
    mask_arr = np.array(_ensure_size(mask, original.size).convert("L")) > 0
    outside_mask = ~mask_arr

    metrics: dict[str, object] = {
        "mask_pixel_count": int(mask_arr.sum()),
        "mask_coverage_ratio": _ratio(int(mask_arr.sum()), mask_arr.size),
        "outside_mask_pixel_count": int(outside_mask.sum()),
        "outside_mask_coverage_ratio": _ratio(int(outside_mask.sum()), outside_mask.size),
    }
    for label, candidate in (("baseline", baseline_arr), ("experiment", experiment_arr)):
        metrics[label] = {
            "full": _region_metrics(original_arr, candidate, None, changed_threshold),
            "inside_mask": _region_metrics(original_arr, candidate, mask_arr, changed_threshold),
            "outside_mask": _region_metrics(original_arr, candidate, outside_mask, changed_threshold),
        }

    baseline_full_mse = _nested_number(metrics, "baseline", "full", "mse")
    experiment_full_mse = _nested_number(metrics, "experiment", "full", "mse")
    baseline_outside_mse = _nested_number(metrics, "baseline", "outside_mask", "mse")
    experiment_outside_mse = _nested_number(metrics, "experiment", "outside_mask", "mse")
    metrics["comparison"] = {
        "full_mse_delta_baseline_minus_experiment": _delta(
            baseline_full_mse, experiment_full_mse
        ),
        "outside_mask_mse_delta_baseline_minus_experiment": _delta(
            baseline_outside_mse, experiment_outside_mse
        ),
        "experiment_full_mse_lower_than_baseline": _lower(experiment_full_mse, baseline_full_mse),
        "experiment_outside_mask_mse_lower_than_baseline": _lower(
            experiment_outside_mse, baseline_outside_mse
        ),
    }
    return metrics


def _region_metrics(
    original: np.ndarray,
    candidate: np.ndarray,
    mask: Optional[np.ndarray],
    changed_threshold: float,
) -> dict[str, object]:
    if mask is None:
        source = original.reshape(-1, 3)
        target = candidate.reshape(-1, 3)
    else:
        if int(mask.sum()) == 0:
            return {
                "pixel_count": 0,
                "mse": None,
                "normalized_mse": None,
                "rmse": None,
                "mae": None,
                "psnr_db": None,
                "global_ssim": None,
                "changed_pixel_count": 0,
                "changed_pixel_ratio": None,
                "max_abs_error": None,
            }
        source = original[mask]
        target = candidate[mask]

    diff = target - source
    squared = diff * diff
    abs_diff = np.abs(diff)
    mse = float(np.mean(squared))
    rmse = math.sqrt(mse)
    mae = float(np.mean(abs_diff))
    max_abs_error = float(np.max(abs_diff))
    per_pixel_changed = np.max(abs_diff, axis=1) > changed_threshold
    changed_count = int(np.count_nonzero(per_pixel_changed))
    pixel_count = int(source.shape[0])
    return {
        "pixel_count": pixel_count,
        "mse": _round(mse),
        "normalized_mse": _round(mse / (255.0 * 255.0)),
        "rmse": _round(rmse),
        "mae": _round(mae),
        "psnr_db": _psnr(mse),
        "global_ssim": _global_ssim(source, target),
        "changed_pixel_count": changed_count,
        "changed_pixel_ratio": _ratio(changed_count, pixel_count),
        "max_abs_error": _round(max_abs_error),
    }


def _global_ssim(source_rgb: np.ndarray, target_rgb: np.ndarray) -> Optional[float]:
    if source_rgb.size == 0 or target_rgb.size == 0:
        return None
    source_gray = _rgb_to_gray(source_rgb)
    target_gray = _rgb_to_gray(target_rgb)
    source_mean = float(np.mean(source_gray))
    target_mean = float(np.mean(target_gray))
    source_var = float(np.var(source_gray))
    target_var = float(np.var(target_gray))
    covariance = float(np.mean((source_gray - source_mean) * (target_gray - target_mean)))
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    denominator = (source_mean**2 + target_mean**2 + c1) * (source_var + target_var + c2)
    if denominator == 0:
        return None
    value = ((2 * source_mean * target_mean + c1) * (2 * covariance + c2)) / denominator
    return _round(value)


def _rgb_to_gray(rgb: np.ndarray) -> np.ndarray:
    return rgb[:, 0] * 0.299 + rgb[:, 1] * 0.587 + rgb[:, 2] * 0.114


def _rgb_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.float64)


def _ensure_size(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image
    resampling = getattr(Image, "Resampling", Image)
    return image.resize(size, resampling.LANCZOS)


def _psnr(mse: float) -> Optional[float]:
    if mse <= 0:
        return None
    return _round(20.0 * math.log10(255.0 / math.sqrt(mse)))


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return _round(numerator / denominator)


def _round(value: float) -> float:
    return round(float(value), 8)


def _nested_number(payload: dict[str, object], *keys: str) -> Optional[float]:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, (int, float)):
        return float(current)
    return None


def _delta(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    return _round(left - right)


def _lower(left: Optional[float], right: Optional[float]) -> Optional[bool]:
    if left is None or right is None:
        return None
    return left < right


def _write_results(
    result_dir: Path,
    evaluations: list[PageEvaluation],
    failures: list[dict[str, object]],
) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    payload = _summary_payload(evaluations, failures)
    (result_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (result_dir / "results.json").write_text(
        json.dumps(
            {
                "pages": [_evaluation_to_payload(evaluation) for evaluation in evaluations],
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_results_csv(result_dir / "results.csv", evaluations)


def _summary_payload(
    evaluations: list[PageEvaluation],
    failures: list[dict[str, object]],
) -> dict[str, object]:
    page_metrics = [evaluation.metrics for evaluation in evaluations]
    return {
        "page_count": len(evaluations),
        "failure_count": len(failures),
        "failures": failures,
        "aggregate": {
            "baseline_full_mse_mean": _mean_nested(page_metrics, "baseline", "full", "mse"),
            "experiment_full_mse_mean": _mean_nested(page_metrics, "experiment", "full", "mse"),
            "baseline_outside_mask_mse_mean": _mean_nested(
                page_metrics, "baseline", "outside_mask", "mse"
            ),
            "experiment_outside_mask_mse_mean": _mean_nested(
                page_metrics, "experiment", "outside_mask", "mse"
            ),
            "full_mse_delta_mean": _mean_nested(
                page_metrics, "comparison", "full_mse_delta_baseline_minus_experiment"
            ),
            "outside_mask_mse_delta_mean": _mean_nested(
                page_metrics, "comparison", "outside_mask_mse_delta_baseline_minus_experiment"
            ),
            "mask_coverage_ratio_mean": _mean_nested(page_metrics, "mask_coverage_ratio"),
            "experiment_wins_full_mse_count": _count_nested_bool(
                page_metrics, "comparison", "experiment_full_mse_lower_than_baseline"
            ),
            "experiment_wins_outside_mask_mse_count": _count_nested_bool(
                page_metrics, "comparison", "experiment_outside_mask_mse_lower_than_baseline"
            ),
        },
    }


def _write_results_csv(path: Path, evaluations: list[PageEvaluation]) -> None:
    fieldnames = [
        "page_id",
        "image_path",
        "provider",
        "model_name",
        "mask_coverage_ratio",
        "baseline_full_mse",
        "experiment_full_mse",
        "full_mse_delta_baseline_minus_experiment",
        "baseline_outside_mask_mse",
        "experiment_outside_mask_mse",
        "outside_mask_mse_delta_baseline_minus_experiment",
        "baseline_changed_pixel_ratio",
        "experiment_changed_pixel_ratio",
        "experiment_full_mse_lower_than_baseline",
        "experiment_outside_mask_mse_lower_than_baseline",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for evaluation in evaluations:
            metrics = evaluation.metrics
            writer.writerow(
                {
                    "page_id": metrics.get("page_id"),
                    "image_path": metrics.get("image_path"),
                    "provider": metrics.get("provider"),
                    "model_name": metrics.get("model_name"),
                    "mask_coverage_ratio": metrics.get("mask_coverage_ratio"),
                    "baseline_full_mse": _nested_number(metrics, "baseline", "full", "mse"),
                    "experiment_full_mse": _nested_number(metrics, "experiment", "full", "mse"),
                    "full_mse_delta_baseline_minus_experiment": _nested_number(
                        metrics, "comparison", "full_mse_delta_baseline_minus_experiment"
                    ),
                    "baseline_outside_mask_mse": _nested_number(
                        metrics, "baseline", "outside_mask", "mse"
                    ),
                    "experiment_outside_mask_mse": _nested_number(
                        metrics, "experiment", "outside_mask", "mse"
                    ),
                    "outside_mask_mse_delta_baseline_minus_experiment": _nested_number(
                        metrics,
                        "comparison",
                        "outside_mask_mse_delta_baseline_minus_experiment",
                    ),
                    "baseline_changed_pixel_ratio": _nested_number(
                        metrics, "baseline", "full", "changed_pixel_ratio"
                    ),
                    "experiment_changed_pixel_ratio": _nested_number(
                        metrics, "experiment", "full", "changed_pixel_ratio"
                    ),
                    "experiment_full_mse_lower_than_baseline": _nested_bool(
                        metrics, "comparison", "experiment_full_mse_lower_than_baseline"
                    ),
                    "experiment_outside_mask_mse_lower_than_baseline": _nested_bool(
                        metrics, "comparison", "experiment_outside_mask_mse_lower_than_baseline"
                    ),
                }
            )


def _write_page_metrics(path: Path, evaluation: PageEvaluation) -> None:
    path.write_text(
        json.dumps(_evaluation_to_payload(evaluation), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _evaluation_to_payload(evaluation: PageEvaluation) -> dict[str, object]:
    return {
        "image_path": str(evaluation.image_path),
        "page_id": evaluation.page_id,
        "workspace_dir": str(evaluation.workspace_dir),
        "original_path": str(evaluation.original_path),
        "provider_output_path": str(evaluation.provider_output_path),
        "inpainting_layer_path": str(evaluation.inpainting_layer_path),
        "experiment_composite_path": str(evaluation.experiment_composite_path),
        "mask_path": str(evaluation.mask_path),
        "metrics": evaluation.metrics,
        "stage_reports": evaluation.stage_reports,
    }


def _read_existing_evaluation(metrics_path: Path) -> PageEvaluation:
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    return PageEvaluation(
        image_path=Path(str(payload["image_path"])),
        page_id=str(payload["page_id"]),
        workspace_dir=Path(str(payload["workspace_dir"])),
        original_path=Path(str(payload["original_path"])),
        provider_output_path=Path(str(payload["provider_output_path"])),
        inpainting_layer_path=Path(str(payload["inpainting_layer_path"])),
        experiment_composite_path=Path(str(payload["experiment_composite_path"])),
        mask_path=Path(str(payload["mask_path"])),
        metrics=dict(payload["metrics"]),
        stage_reports=list(payload.get("stage_reports", [])),
    )


def _mean_nested(items: list[dict[str, object]], *keys: str) -> Optional[float]:
    values = [_nested_number(item, *keys) for item in items]
    numeric = [value for value in values if value is not None]
    if not numeric:
        return None
    return _round(sum(numeric) / len(numeric))


def _count_nested_bool(items: list[dict[str, object]], *keys: str) -> int:
    return sum(1 for item in items if _nested_bool(item, *keys) is True)


def _nested_bool(payload: dict[str, object], *keys: str) -> Optional[bool]:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, bool):
        return current
    return None


def _artifact_by_role(
    artifacts: dict[str, ArtifactDescriptor],
    role: str,
) -> ArtifactDescriptor:
    for artifact in artifacts.values():
        if artifact.metadata.get("role") == role:
            return artifact
    raise RuntimeError(f"Pipeline did not produce artifact role={role}")


def _copy_image_artifact(
    artifact: ArtifactDescriptor,
    destination: Path,
    expected_size: tuple[int, int],
) -> Path:
    source = _file_path_from_uri(artifact.uri)
    with Image.open(source) as image:
        output = _ensure_size(image.convert("RGBA"), expected_size)
        output.save(destination)
    return destination


def _write_side_by_side_preview(
    path: Path,
    original: Image.Image,
    baseline: Image.Image,
    experiment: Image.Image,
) -> None:
    width, height = original.size
    preview = Image.new("RGB", (width * 3, height), color=(255, 255, 255))
    preview.paste(original.convert("RGB"), (0, 0))
    preview.paste(_ensure_size(baseline, original.size).convert("RGB"), (width, 0))
    preview.paste(_ensure_size(experiment, original.size).convert("RGB"), (width * 2, 0))
    preview.save(path)


def _collect_images(dataset_dir: Path) -> list[Path]:
    if not dataset_dir.exists():
        return []
    return sorted(
        path
        for path in dataset_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _resolve_api_key(provider: str, api_key_env: Optional[str]) -> str:
    runtime_config = load_runtime_config()
    env_key = api_key_env or _default_api_key_env(provider)
    direct = os.environ.get(env_key)
    if direct:
        return direct
    if provider == "mindlogic":
        return runtime_config_value(
            runtime_config,
            "TOWA_PLATFORM_PROVIDER_MINDLOGIC_API_KEY",
            aliases=("TOWA_MINDLOGIC_API_KEY", "mindlogic_api_key", "inpaint.mindlogic_api_key"),
        )
    return runtime_config_value(
        runtime_config,
        "TOWA_PLATFORM_PROVIDER_NANOBANANA_API_KEY",
        aliases=("TOWA_NANOBANANA_API_KEY", "nanobanana_api_key", "inpaint.nanobanana_api_key"),
    )


def _default_api_key_env(provider: str) -> str:
    if provider == "mindlogic":
        return "TOWA_MINDLOGIC_API_KEY"
    return "TOWA_NANOBANANA_API_KEY"


def _inpaint_model_id(provider: str) -> str:
    if provider == "mindlogic":
        return MINDLOGIC_INPAINT_MODEL_ID
    return NANOBANANA_INPAINT_MODEL_ID


def _default_model_name(provider: str) -> str:
    if provider == "mindlogic":
        return MINDLOGIC_IMAGE_MODEL
    return "gemini-3.1-flash-image-preview"


def _media_type_for_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    if normalized in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if normalized == ".webp":
        return "image/webp"
    return "image/png"


def _page_id(index: int, image_path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", image_path.stem).strip("._-")
    if not slug:
        slug = "page"
    return f"{index:04d}_{slug}"


def _file_path_from_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Expected file:// artifact URI, got {uri}")
    return Path(unquote(parsed.path))


if __name__ == "__main__":
    raise SystemExit(main())
