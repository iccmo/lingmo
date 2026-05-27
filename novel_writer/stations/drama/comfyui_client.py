"""ComfyUI API 客户端 — 提交工作流、跟踪进度、下载结果。

通过 HTTP API 与本地 ComfyUI 实例交互：
  - POST /prompt          提交 workflow（API 格式 JSON）
  - GET  /history/{id}    查询生成结果
  - GET  /view            下载生成图片
  - POST /upload/image    上传参考图
  - GET  /system_stats    健康检查
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

logger = logging.getLogger(__name__)


class ComfyUIError(Exception):
    """ComfyUI 交互异常"""


class ComfyUIClient:
    """ComfyUI API 客户端"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188) -> None:
        self.base_url = f"http://{host}:{port}"
        self.client_id = uuid.uuid4().hex[:16]

    # ─── 健康检查 ───

    def health_check(self) -> bool:
        """GET /system_stats — 检查 ComfyUI 是否在线。"""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return "system" in data
        except Exception as e:
            logger.debug("ComfyUI health check failed: %s", e)
            return False

    def get_system_stats(self) -> dict:
        """获取 ComfyUI 系统信息。"""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return dict(json.loads(resp.read()))
        except Exception as e:
            raise ComfyUIError(f"获取系统信息失败: {e}") from e

    # ─── 工作流提交 ───

    def queue_prompt(self, workflow: dict) -> str:
        """POST /prompt — 提交 workflow 并返回 prompt_id。

        workflow 为 ComfyUI API 格式 JSON，每个 node 带 class_type + inputs。
        inputs 中的 ``["node_id", output_index]`` 表示节点间连线。

        Args:
            workflow: API 格式 workflow dict。

        Returns:
            prompt_id 字符串。

        Raises:
            ComfyUIError: 提交失败。
        """
        payload = json.dumps({
            "prompt": workflow,
            "client_id": self.client_id,
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                prompt_id = data.get("prompt_id", "")
                if not prompt_id:
                    raise ComfyUIError(f"响应缺少 prompt_id: {data}")
                logger.info("ComfyUI prompt queued: %s", prompt_id)
                return prompt_id
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            raise ComfyUIError(f"提交工作流失败 (HTTP {e.code}): {body}") from e
        except Exception as e:
            if isinstance(e, ComfyUIError):
                raise
            raise ComfyUIError(f"提交工作流失败: {e}") from e

    # ─── 进度轮询 ───

    def poll_progress(
        self,
        prompt_id: str,
        timeout: int = 300,
        interval: float = 3.0,
    ) -> dict:
        """轮询 GET /history/{prompt_id} 等待生成完成。

        Args:
            prompt_id: queue_prompt 返回的 ID。
            timeout: 最长等待秒数（默认 300 秒 = 5 分钟）。
            interval: 轮询间隔秒数（默认 3 秒）。

        Returns:
            history dict，含 outputs 信息。

        Raises:
            ComfyUIError: 超时或生成失败。
        """
        start = time.monotonic()

        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise ComfyUIError(
                    f"生成超时 ({timeout}s)，prompt_id={prompt_id}"
                )

            try:
                url = f"{self.base_url}/history/{prompt_id}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    history = json.loads(resp.read())

                # history 非空说明已完成
                if prompt_id in history:
                    entry = history[prompt_id]
                    status = entry.get("status", {})
                    if status.get("status_str") == "error":
                        msgs = status.get("messages", [])
                        raise ComfyUIError(f"生成失败: {msgs}")
                    logger.info("ComfyUI generation complete: %s", prompt_id)
                    return entry

            except (ComfyUIError, urllib.error.URLError):
                raise
            except Exception as e:
                logger.debug("Poll error: %s", e)

            time.sleep(interval)

    # ─── 图片下载 ───

    def download_image(
        self,
        filename: str,
        subfolder: str = "",
        save_path: str = "",
        img_type: str = "output",
    ) -> bool:
        """GET /view — 下载 ComfyUI 生成的图片到本地。

        Args:
            filename: ComfyUI 输出的文件名。
            subfolder: 子目录（通常为空）。
            save_path: 本地保存路径。
            img_type: 图片类型（默认 "output"）。

        Returns:
            下载成功返回 True。
        """
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": img_type,
        })
        url = f"{self.base_url}/view?{params}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(data)
                logger.info("Image downloaded: %s (%d bytes)", save_path, len(data))
                return True
        except Exception as e:
            logger.error("Download failed (%s): %s", filename, e)
            return False

    # ─── 图片上传 ───

    def upload_image(self, filepath: str, name: str = "") -> dict:
        """POST /upload/image — 上传本地图片到 ComfyUI input 目录。

        Args:
            filepath: 本地图片路径。
            name: 上传后的文件名（默认使用原始文件名）。

        Returns:
            dict: {"name": "filename.png", "subfolder": "", "type": "input"}

        Raises:
            ComfyUIError: 上传失败。
        """
        if not os.path.exists(filepath):
            raise ComfyUIError(f"文件不存在: {filepath}")

        filename = name or os.path.basename(filepath)
        boundary = f"----Boundary{uuid.uuid4().hex[:16]}"

        with open(filepath, "rb") as f:
            file_data = f.read()

        # multipart/form-data 构建
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n"
            f"\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"{self.base_url}/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                logger.info("Image uploaded: %s → %s", filepath, result.get("name"))
                return dict(result)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")[:500]
            raise ComfyUIError(f"上传失败 (HTTP {e.code}): {body_text}") from e
        except Exception as e:
            if isinstance(e, ComfyUIError):
                raise
            raise ComfyUIError(f"上传失败: {e}") from e

    # ─── 便捷方法 ───

    def generate_image(
        self,
        workflow: dict,
        save_path: str,
        timeout: int = 300,
    ) -> bool:
        """一键生成：提交 workflow → 等待完成 → 下载第一张图片。

        Args:
            workflow: ComfyUI API 格式 workflow。
            save_path: 图片保存路径。
            timeout: 最长等待秒数。

        Returns:
            成功返回 True。
        """
        try:
            prompt_id = self.queue_prompt(workflow)
            history = self.poll_progress(prompt_id, timeout=timeout)

            # 从 outputs 中找到图片
            outputs = history.get("outputs", {})
            for _node_id, node_output in outputs.items():
                images = node_output.get("images", [])
                if images:
                    img = images[0]
                    return self.download_image(
                        filename=img.get("filename", ""),
                        subfolder=img.get("subfolder", ""),
                        save_path=save_path,
                        img_type=img.get("type", "output"),
                    )

            logger.warning("No images in ComfyUI output")
            return False

        except ComfyUIError as e:
            logger.error("ComfyUI generation error: %s", e)
            return False
