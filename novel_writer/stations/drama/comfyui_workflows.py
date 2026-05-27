"""ComfyUI 工作流模板构建器。

提供 ComfyUI API 格式的 workflow JSON 构建方法。
每个 workflow 是一个 dict，key 为节点 ID（str），value 为 {class_type, inputs}。
节点间连线用 ``["target_node_id", output_index]`` 表示。

节点 ID 分配策略：用自增整数字符串，便于阅读和调试。
"""

from __future__ import annotations

import random


def build_txt2img_workflow(
    prompt: str,
    negative: str = "",
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    width: int = 768,
    height: int = 1344,
    steps: int = 25,
    cfg: float = 7.0,
    seed: int | None = None,
    batch_size: int = 1,
) -> dict:
    """构建纯文生图 workflow（无 IP-Adapter）。

    节点链:
        LoadCheckpoint → CLIPTextEncode(+) → KSampler → VAEDecode → SaveImage
                        → CLIPTextEncode(-) ↗

    Args:
        prompt: 正向提示词。
        negative: 负向提示词。
        checkpoint: SD checkpoint 文件名。
        width/height: 输出尺寸。
        steps: 采样步数。
        cfg: CFG scale。
        seed: 随机种子（None 则随机）。
        batch_size: 批量生成数量。

    Returns:
        ComfyUI API 格式 workflow dict。
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative or "low quality, blurry, deformed",
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": batch_size,
            },
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
            },
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["6", 0],
                "filename_prefix": "novel_writer",
            },
        },
    }


def build_ipadapter_faceid_workflow(
    prompt: str,
    negative: str = "",
    ref_image_name: str = "",
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    ipadapter_model: str = "ip-adapter-faceid-plusv2_sd15.bin",
    clip_vision_model: str = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    insightface_model: str = "buffalo_l",
    lora_strength: float = 0.8,
    width: int = 768,
    height: int = 1344,
    steps: int = 25,
    cfg: float = 7.0,
    seed: int | None = None,
) -> dict:
    """构建 IP-Adapter FaceID workflow。

    节点链:
        LoadCheckpoint → CLIPTextEncode(+) ─→ KSampler → VAEDecode → SaveImage
                        → CLIPTextEncode(-) ↗
        LoadImage(ref) → IPAdapterAdvanced → ApplyIPAdapter ─↗
                       → InsightFaceLoader → ApplyIPAdapter ─↗

    IP-Adapter FaceID 工作原理:
        1. InsightFace 从参考图中提取人脸 ID embedding
        2. IP-Adapter 将 face embedding 注入 U-Net 的 cross-attention
        3. 生成的图片保持参考图的面部特征

    Args:
        prompt: 正向提示词。
        negative: 负向提示词。
        ref_image_name: 已上传到 ComfyUI 的参考图文件名。
        checkpoint: SD checkpoint。
        ipadapter_model: IP-Adapter 模型文件名。
        clip_vision_model: CLIP Vision 模型（IP-Adapter 需要）。
        insightface_model: InsightFace 模型名。
        lora_strength: IP-Adapter 权重 (0.0-1.0)。
        width/height: 输出尺寸。
        steps: 采样步数。
        cfg: CFG scale。
        seed: 随机种子。

    Returns:
        ComfyUI API 格式 workflow dict。
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    workflow: dict = {
        # ── 模型加载 ──
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        # ── 参考图加载 ──
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": ref_image_name},
        },
        # ── InsightFace 人脸检测 ──
        "3": {
            "class_type": "InsightFaceLoader",
            "inputs": {"model_name": insightface_model},
        },
        # ── IP-Adapter 模型加载 ──
        "4": {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": ipadapter_model},
        },
        # ── CLIP Vision 加载（IP-Adapter 需要） ──
        "5": {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": clip_vision_model},
        },
        # ── IP-Adapter 应用到模型 ──
        "6": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "weight": lora_strength,
                "noise": 0.0,
                "weight_type": "linear",
                "start_at": 0.0,
                "end_at": 1.0,
                "unfold_batch": False,
            },
        },
        # ── FaceID 应用 ──
        "7": {
            "class_type": "IPAdapterFaceID",
            "inputs": {
                "weight": lora_strength,
                "noise": 0.0,
                "weight_type": "linear",
                "start_at": 0.0,
                "end_at": 1.0,
                "unfold_batch": False,
                "ipadapter": ["4", 0],
                "clip_vision": ["5", 0],
                "insightface": ["3", 0],
                "image": ["2", 0],
                "model": ["1", 0],
            },
        },
        # ── 提示词编码 ──
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["1", 1],
            },
        },
        "11": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative or "low quality, blurry, deformed, bad anatomy",
                "clip": ["1", 1],
            },
        },
        # ── 空白 latent ──
        "12": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        # ── 采样 ──
        "13": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["7", 0],
                "positive": ["10", 0],
                "negative": ["11", 0],
                "latent_image": ["12", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        # ── 解码 + 保存 ──
        "14": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["13", 0],
                "vae": ["1", 2],
            },
        },
        "15": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["14", 0],
                "filename_prefix": "ipadapter_faceid",
            },
        },
    }

    return workflow


def build_ipadapter_simple_workflow(
    prompt: str,
    negative: str = "",
    ref_image_name: str = "",
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    ipadapter_model: str = "ip-adapter-plus_sd15.bin",
    clip_vision_model: str = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    weight: float = 0.8,
    width: int = 768,
    height: int = 1344,
    steps: int = 25,
    cfg: float = 7.0,
    seed: int | None = None,
) -> dict:
    """构建简化版 IP-Adapter workflow（不需要 InsightFace）。

    使用 IP-Adapter Plus（整体风格参考）而非 FaceID（面部参考）。
    适用于 InsightFace 未安装的场景。

    节点链:
        LoadCheckpoint → ApplyIPAdapter → KSampler → VAEDecode → SaveImage
        LoadImage(ref) → IPAdapterApply ↗
        CLIPTextEncode(+) ────────────↗
        CLIPTextEncode(-) ────────────↗
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": ref_image_name},
        },
        "3": {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": ipadapter_model},
        },
        "4": {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": clip_vision_model},
        },
        "5": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "weight": weight,
                "noise": 0.0,
                "weight_type": "linear",
                "start_at": 0.0,
                "end_at": 1.0,
                "unfold_batch": False,
                "ipadapter": ["3", 0],
                "clip_vision": ["4", 0],
                "image": ["2", 0],
                "model": ["1", 0],
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative or "low quality, blurry, deformed",
                "clip": ["1", 1],
            },
        },
        "8": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["8", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["9", 0], "vae": ["1", 2]},
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {"images": ["10", 0], "filename_prefix": "ipadapter"},
        },
    }


def build_portrait_workflow(
    appearance: str,
    costume: str = "",
    expression: str = "",
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    width: int = 768,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 7.0,
    seed: int | None = None,
) -> dict:
    """构建角色肖像参考图生成 workflow。

    生成用于 IP-Adapter 参考的角色正面照。
    """
    parts = [f"portrait photo of {appearance}"]
    if costume:
        parts.append(costume)
    if expression:
        parts.append(expression)
    parts.append("front view, neutral lighting, white background, high detail, photorealistic, 4K")

    prompt = ", ".join(parts)
    negative = "cartoon, anime, blurry, low quality, deformed, multiple people, bad anatomy"

    return build_txt2img_workflow(
        prompt=prompt,
        negative=negative,
        checkpoint=checkpoint,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        seed=seed,
    )
