"""
图片质量检查器 — QualityChecker

对 AI 生成的图片做多级质量检查，支持选择性重试。

检查链（按成本递增，短路执行）：
  1. 文件完整性：文件存在、> 10KB、PIL 可读
  2. 尺寸检查：宽高 >= 512px
  3. 人脸检测（可选）：close-up 场景必须有人脸
  4. CLIP 相似度（可选）：prompt 和图片语义匹配

默认只做 1+2（零新依赖）。CLIP 和人脸检测通过配置开启。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityConfig:
    """质量检查配置。"""
    enabled: bool = True
    max_retries: int = 2
    check_file: bool = True
    check_dimensions: bool = True
    check_face: bool = False
    check_clip: bool = False
    clip_threshold: float = 0.20
    clip_model: str = "openai/clip-vit-base-patch32"
    min_file_size: int = 10_000  # 10KB
    min_dimension: int = 512

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> QualityConfig:
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", True),
            max_retries=d.get("max_retries", 2),
            check_file=d.get("check_file", True),
            check_dimensions=d.get("check_dimensions", True),
            check_face=d.get("check_face", False),
            check_clip=d.get("check_clip", False),
            clip_threshold=d.get("clip_threshold", 0.20),
            clip_model=d.get("clip_model", "openai/clip-vit-base-patch32"),
            min_file_size=d.get("min_file_size", 10_000),
            min_dimension=d.get("min_dimension", 512),
        )


@dataclass
class CheckResult:
    """单次检查结果。"""
    passed: bool
    checks_run: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    clip_score: float = 0.0
    face_detected: bool = False

    @property
    def failure_reason(self) -> str:
        return "; ".join(self.failures) if self.failures else ""


class QualityChecker:
    """图片质量检查器。

    使用方式::

        checker = QualityChecker(config)
        result = checker.check("output.png", prompt="a portrait", shot_type="close-up")
        if not result.passed:
            print(f"质量不达标: {result.failure_reason}")
    """

    def __init__(self, config: QualityConfig | None = None) -> None:
        self.config = config or QualityConfig()
        self._clip_model: Any = None
        self._clip_processor: Any = None
        self._face_detector: Any = None

    def check(
        self,
        image_path: str,
        prompt: str = "",
        shot_type: str = "",
    ) -> CheckResult:
        """对图片做质量检查。

        Args:
            image_path: 图片文件路径。
            prompt: 生成该图片的 prompt（CLIP 评分用）。
            shot_type: 镜头类型（close-up 时检查人脸）。

        Returns:
            CheckResult 包含通过/失败及详细信息。
        """
        if not self.config.enabled:
            return CheckResult(passed=True)

        result = CheckResult(passed=True)

        # ① 文件完整性检查
        if self.config.check_file:
            ok, reason = self._check_file(image_path)
            result.checks_run.append("file")
            if not ok:
                result.passed = False
                result.failures.append(reason)
                return result  # 文件不可读，后续检查无意义

        # ② 尺寸检查
        if self.config.check_dimensions:
            ok, reason = self._check_dimensions(image_path)
            result.checks_run.append("dimensions")
            if not ok:
                result.passed = False
                result.failures.append(reason)

        # ③ 人脸检测（仅 close-up）
        if self.config.check_face and shot_type == "close-up":
            ok, detected = self._check_face(image_path)
            result.checks_run.append("face")
            result.face_detected = detected
            if not ok:
                result.passed = False
                result.failures.append("close-up 场景未检测到人脸")

        # ④ CLIP 相似度
        if self.config.check_clip and prompt:
            score = self._compute_clip_score(prompt, image_path)
            result.checks_run.append("clip")
            result.clip_score = score
            if score < self.config.clip_threshold:
                result.passed = False
                result.failures.append(
                    f"CLIP 评分 {score:.3f} < 阈值 {self.config.clip_threshold}"
                )

        return result

    # ── 检查方法 ──────────────────────────────────────────────────

    def _check_file(self, path: str) -> tuple[bool, str]:
        """检查文件完整性。"""
        p = Path(path)
        if not p.exists():
            return False, "文件不存在"
        if p.stat().st_size < self.config.min_file_size:
            return False, f"文件太小: {p.stat().st_size} bytes"
        try:
            from PIL import Image
            img = Image.open(path)
            img.verify()
            return True, "ok"
        except Exception as e:
            return False, f"图片无法读取: {e}"

    def _check_dimensions(self, path: str) -> tuple[bool, str]:
        """检查图片尺寸。"""
        try:
            from PIL import Image
            img = Image.open(path)
            w, h = img.size
            if w < self.config.min_dimension or h < self.config.min_dimension:
                return False, f"尺寸太小: {w}x{h}"
            return True, "ok"
        except Exception:
            return False, "无法读取图片尺寸"

    def _check_face(self, path: str) -> tuple[bool, bool]:
        """人脸检测（mediapipe）。"""
        try:
            import mediapipe as mp
            import numpy as np
            from PIL import Image

            if self._face_detector is None:
                self._face_detector = mp.solutions.face_detection.FaceDetection(
                    model_selection=0, min_detection_confidence=0.5,
                )

            img = Image.open(path).convert("RGB")
            img_array = np.array(img)
            results = self._face_detector.process(img_array)
            detected = bool(results.detections)
            return detected, detected
        except ImportError:
            logger.warning("mediapipe not installed, skipping face check")
            return True, False
        except Exception as e:
            logger.warning("Face detection error: %s", e)
            return True, False  # 出错时不阻断

    def _compute_clip_score(self, prompt: str, image_path: str) -> float:
        """计算 CLIP 相似度评分。"""
        try:
            import torch
            from PIL import Image

            if self._clip_model is None:
                from transformers import CLIPModel, CLIPProcessor
                self._clip_processor = CLIPProcessor.from_pretrained(
                    self.config.clip_model,
                )
                self._clip_model = CLIPModel.from_pretrained(
                    self.config.clip_model,
                )

            image = Image.open(image_path).convert("RGB")
            inputs = self._clip_processor(
                text=[prompt], images=image, return_tensors="pt", padding=True,
            )
            with torch.no_grad():
                outputs = self._clip_model(**inputs)
                logits = outputs.logits_per_image
                score = float(logits[0][0]) / 100.0  # 归一化到 ~0-1 范围
            return score
        except ImportError:
            logger.warning("transformers/torch not installed, skipping CLIP check")
            return 1.0  # 不检查时默认通过
        except Exception as e:
            logger.warning("CLIP scoring error: %s", e)
            return 1.0  # 出错时不阻断

    @property
    def check_result_summary(self) -> list[str]:
        """返回当前配置下启用的检查列表。"""
        checks: list[str] = []
        if self.config.check_file:
            checks.append("file")
        if self.config.check_dimensions:
            checks.append("dimensions")
        if self.config.check_face:
            checks.append("face")
        if self.config.check_clip:
            checks.append("clip")
        return checks

    def best_of(self, candidates: list[str], prompt: str = "") -> str:
        """从多个候选中选择最好的图片。

        优先选通过检查的；都通过时选文件最大的。
        都不通过时也选文件最大的（最完整的）。

        Args:
            candidates: 候选图片路径列表。
            prompt: 用于 CLIP 评分。

        Returns:
            最佳图片路径。
        """
        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]

        scored: list[tuple[float, str]] = []
        for path in candidates:
            if not Path(path).exists():
                continue
            result = self.check(path, prompt=prompt)
            size = Path(path).stat().st_size
            # 通过检查的权重 1000，文件大小作为 tiebreaker
            score = (1000.0 if result.passed else 0.0) + size / 1_000_000.0
            scored.append((score, path))

        if not scored:
            return candidates[0]

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
