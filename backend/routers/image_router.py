"""Image generation API router.

Exposes ComfyUI Anima model via REST endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from services.core.comfyui_service import comfyui_service
from services.core.character_prompts import build_positive, list_characters

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


class Img2ImgRequest(BaseModel):
    reference_base64: str = Field(..., description="参考图 base64 (PNG/JPG)")
    positive: str = Field(..., description="正面提示词")
    negative: Optional[str] = Field(None, description="负面提示词")
    denoise: float = Field(0.5, ge=0.0, le=1.0, description="去噪强度 (0.3-0.5 推荐)")
    steps: int = Field(30, description="采样步数")
    cfg: float = Field(4.5, description="CFG scale")
    seed: Optional[int] = Field(None, description="种子")
    nsfw: bool = Field(False, description="NSFW 标签")


@router.post("/api/image/img2img")
async def img2img(req: Img2ImgRequest):
    kwargs = req.model_dump()
    if kwargs["negative"] is None:
        kwargs.pop("negative")

    result = await comfyui_service.img2img(**kwargs)
    if result is None:
        return {"error": "img2img 生成失败，请检查 ComfyUI 和参考图"}
    return result


class CharacterGenRequest(BaseModel):
    agent_id: str = Field(..., description="角色 ID (如 frieren, fern)")
    scene: str = Field("outdoor", description="场景 (预设 key 或自由标签)")
    extra_tags: str = Field("", description="附加标签")
    nsfw: bool = Field(False, description="NSFW 模式")
    width: int = Field(896, description="宽度")
    height: int = Field(1152, description="高度")
    steps: int = Field(30, description="步数")
    seed: Optional[int] = Field(None, description="种子")


@router.get("/api/image/characters")
async def get_characters():
    """列出所有有图片模板的角色。"""
    return {"characters": list_characters()}


@router.post("/api/image/character")
async def generate_character(req: CharacterGenRequest):
    """根据角色模板生成图片，自动锁定角色特征。"""
    positive = build_positive(
        agent_id=req.agent_id,
        scene=req.scene,
        extra_tags=req.extra_tags,
        nsfw=req.nsfw,
    )
    if not positive:
        return {"error": f"角色 {req.agent_id} 没有 image_prompt.json 模板"}

    result = await comfyui_service.generate(
        positive=positive,
        width=req.width,
        height=req.height,
        steps=req.steps,
        seed=req.seed,
        nsfw=req.nsfw,
    )
    if result is None:
        return {"error": "图片生成失败"}
    return result
