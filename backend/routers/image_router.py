"""Image generation API router.

Exposes ComfyUI Anima model via REST endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from services.core.comfyui_service import comfyui_service

router = APIRouter(tags=["image"])


class ImageGenRequest(BaseModel):
    positive: str = Field(..., description="正面提示词 (Danbooru tags + 自然语言)")
    negative: Optional[str] = Field(None, description="负面提示词 (留空用默认)")
    width: int = Field(896, description="宽度")
    height: int = Field(1152, description="高度")
    steps: int = Field(30, description="采样步数")
    cfg: float = Field(4.5, description="CFG scale")
    seed: Optional[int] = Field(None, description="种子 (留空随机)")
    mode: str = Field("enhanced", description="工作流: enhanced/basic/turbo")
    nsfw: bool = Field(False, description="是否启用 NSFW 标签")


@router.get("/api/image/health")
async def image_health():
    ok = await comfyui_service.health()
    return {"status": "ok" if ok else "unavailable", "backend": "ComfyUI Anima"}


@router.post("/api/image/generate")
async def generate_image(req: ImageGenRequest):
    kwargs = req.model_dump()
    if kwargs["negative"] is None:
        kwargs.pop("negative")

    result = await comfyui_service.generate(**kwargs)
    if result is None:
        return {"error": "图片生成失败，请检查 ComfyUI 是否在运行"}
    return result
