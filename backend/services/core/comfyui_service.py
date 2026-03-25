"""ComfyUI image generation service for PeroCore.

Connects to a ComfyUI instance via HTTP API to generate images
using the Anima anime model. Supports text2img and img2img, SFW/NSFW.
"""

import asyncio
import base64
import json
import logging
import random
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Workflow templates (API format JSON files from ComfyUI)
_WORKFLOW_DIR = Path("/mnt/d/ComfyUI_portable")
_WORKFLOWS = {
    "enhanced": _WORKFLOW_DIR / "anima_enhanced_api.json",
    "basic": _WORKFLOW_DIR / "anima_basic_api.json",
    "turbo": _WORKFLOW_DIR / "anima_turbo_api.json",
    "i2i_enhanced": _WORKFLOW_DIR / "anima_i2i_enhanced_api.json",
}

# Default negative prompt
_DEFAULT_NEGATIVE = (
    "worst quality, low quality, score_1, score_2, score_3, "
    "blurry, jpeg artifacts, sepia, extra fingers, mutated hands, "
    "bad anatomy, deformed, disfigured, watermark, text, username, signature"
)

COMFYUI_BASE = "http://172.21.240.1:8188"


class ComfyUIService:
    """Manages image generation requests to ComfyUI."""

    def __init__(self, base_url: str = COMFYUI_BASE):
        self.base_url = base_url.rstrip("/")
        self._client_id = str(uuid.uuid4())

    def _load_workflow(self, mode: str = "enhanced") -> Dict[str, Any]:
        path = _WORKFLOWS.get(mode, _WORKFLOWS["enhanced"])
        with open(path, "r") as f:
            return json.load(f)

    async def generate(
        self,
        positive: str,
        negative: str = _DEFAULT_NEGATIVE,
        width: int = 896,
        height: int = 1152,
        steps: int = 30,
        cfg: float = 4.5,
        seed: Optional[int] = None,
        mode: str = "enhanced",
        nsfw: bool = False,
        timeout: float = 120.0,
    ) -> Optional[Dict[str, Any]]:
        """Generate an image and return {"image_base64": ..., "seed": ..., "prompt": ...}.

        Args:
            positive: Positive prompt (Danbooru tags + natural language).
            negative: Negative prompt.
            width, height: Output resolution (keep total ~1MP).
            steps: Sampling steps (30-50 for enhanced, 6-8 for turbo).
            cfg: Classifier-free guidance scale.
            seed: RNG seed. None = random.
            mode: "enhanced" (recommended), "basic", or "turbo".
            nsfw: If True, prepends "nsfw, explicit" to positive prompt.
            timeout: Max wait time in seconds.

        Returns:
            Dict with image_base64, seed, prompt on success; None on failure.
        """
        workflow = self._load_workflow(mode)
        if seed is None:
            seed = random.randint(0, 2**53)

        # Quality prefix
        quality = "masterpiece, best quality, score_9, score_8, absurdres, "
        if nsfw:
            quality += "nsfw, explicit, "
        full_positive = quality + positive

        # Set prompts (node 4 = positive, node 5 = negative)
        workflow["4"]["inputs"]["text"] = full_positive
        workflow["5"]["inputs"]["text"] = negative

        # Set resolution
        workflow["6"]["inputs"]["width"] = width
        workflow["6"]["inputs"]["height"] = height

        # Set sampler params
        workflow["7"]["inputs"]["seed"] = seed
        workflow["7"]["inputs"]["steps"] = steps
        workflow["7"]["inputs"]["cfg"] = cfg

        if mode == "turbo":
            workflow["7"]["inputs"]["cfg"] = 1
            workflow["7"]["inputs"]["steps"] = min(steps, 8)

        logger.info("[ComfyUI] Generating: mode=%s, nsfw=%s, seed=%d", mode, nsfw, seed)

        try:
            prompt_id = await self._queue_prompt(workflow)
            if not prompt_id:
                return None

            image_data = await self._wait_and_fetch(prompt_id, timeout)
            if not image_data:
                return None

            return {
                "image_base64": base64.b64encode(image_data).decode("ascii"),
                "seed": seed,
                "prompt": full_positive,
            }
        except Exception as e:
            logger.error("[ComfyUI] Generation failed: %s", e)
            return None

    async def img2img(
        self,
        reference_base64: str,
        positive: str,
        negative: str = _DEFAULT_NEGATIVE,
        denoise: float = 0.5,
        steps: int = 30,
        cfg: float = 4.5,
        seed: Optional[int] = None,
        nsfw: bool = False,
        timeout: float = 120.0,
    ) -> Optional[Dict[str, Any]]:
        """Image-to-image: generate a variation from a reference image.

        Args:
            reference_base64: Base64-encoded reference image (PNG/JPG).
            positive: Positive prompt.
            denoise: Denoising strength (0.0 = identical, 1.0 = full regen).
                     0.3-0.5 recommended for character variations.
            Other args: same as generate().

        Returns:
            Dict with image_base64, seed, prompt on success; None on failure.
        """
        workflow = self._load_workflow("i2i_enhanced")
        if seed is None:
            seed = random.randint(0, 2**53)

        # Upload reference image to ComfyUI
        ref_filename = await self._upload_image(reference_base64)
        if not ref_filename:
            logger.error("[ComfyUI] Failed to upload reference image")
            return None

        quality = "masterpiece, best quality, score_9, score_8, absurdres, "
        if nsfw:
            quality += "nsfw, explicit, "
        full_positive = quality + positive

        workflow["4"]["inputs"]["text"] = full_positive
        workflow["5"]["inputs"]["text"] = negative
        workflow["7"]["inputs"]["seed"] = seed
        workflow["7"]["inputs"]["steps"] = steps
        workflow["7"]["inputs"]["cfg"] = cfg
        workflow["7"]["inputs"]["denoise"] = denoise
        workflow["12"]["inputs"]["image"] = ref_filename

        logger.info("[ComfyUI] img2img: denoise=%.2f, seed=%d", denoise, seed)

        try:
            prompt_id = await self._queue_prompt(workflow)
            if not prompt_id:
                return None
            image_data = await self._wait_and_fetch(prompt_id, timeout)
            if not image_data:
                return None
            return {
                "image_base64": base64.b64encode(image_data).decode("ascii"),
                "seed": seed,
                "prompt": full_positive,
                "denoise": denoise,
            }
        except Exception as e:
            logger.error("[ComfyUI] img2img failed: %s", e)
            return None

    async def _upload_image(self, image_base64: str) -> Optional[str]:
        """Upload a base64 image to ComfyUI's input folder. Returns filename."""
        image_bytes = base64.b64decode(image_base64)
        filename = f"pero_ref_{uuid.uuid4().hex[:8]}.png"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/upload/image",
                files={"image": (filename, image_bytes, "image/png")},
                data={"overwrite": "true"},
            )
            if resp.status_code == 200:
                return resp.json().get("name", filename)
            logger.error("[ComfyUI] Upload failed: %d %s", resp.status_code, resp.text[:200])
            return None

    async def _queue_prompt(self, workflow: Dict) -> Optional[str]:
        """Submit a prompt to ComfyUI and return the prompt_id."""
        payload = {"prompt": workflow, "client_id": self._client_id}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/prompt",
                json=payload,
            )
            if resp.status_code != 200:
                logger.error("[ComfyUI] Queue failed: %d %s", resp.status_code, resp.text[:200])
                return None
            return resp.json().get("prompt_id")

    async def _wait_and_fetch(self, prompt_id: str, timeout: float) -> Optional[bytes]:
        """Poll ComfyUI history until the prompt completes, then fetch the image."""
        deadline = asyncio.get_event_loop().time() + timeout
        async with httpx.AsyncClient(timeout=10) as client:
            while asyncio.get_event_loop().time() < deadline:
                resp = await client.get(f"{self.base_url}/history/{prompt_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    if prompt_id in data:
                        outputs = data[prompt_id].get("outputs", {})
                        # Find the SaveImage node output
                        for node_id, node_out in outputs.items():
                            images = node_out.get("images", [])
                            if images:
                                img_info = images[0]
                                return await self._download_image(
                                    client, img_info["filename"], img_info.get("subfolder", ""), img_info.get("type", "output")
                                )
                await asyncio.sleep(1.5)
        logger.error("[ComfyUI] Timed out waiting for prompt %s", prompt_id)
        return None

    async def _download_image(
        self, client: httpx.AsyncClient, filename: str, subfolder: str, folder_type: str
    ) -> Optional[bytes]:
        """Download a generated image from ComfyUI."""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        resp = await client.get(f"{self.base_url}/view", params=params)
        if resp.status_code == 200:
            return resp.content
        logger.error("[ComfyUI] Download failed: %d", resp.status_code)
        return None

    async def health(self) -> bool:
        """Check if ComfyUI is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/system_stats")
                return resp.status_code == 200
        except Exception:
            return False


# Singleton
comfyui_service = ComfyUIService()
