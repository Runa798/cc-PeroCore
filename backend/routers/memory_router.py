import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from database import engine, get_session
from models import ConversationLog
from peroproto import perolink_pb2
from services.core.gateway_client import gateway_client
from services.memory.memory_importer import MemoryImporter
from services.memory.memory_service import MemoryService
from services.memory.reflection_service import ReflectionService

router = APIRouter(prefix="/api/memories", tags=["memory"])
history_router = APIRouter(prefix="/api/history", tags=["history"])
legacy_memories_router = APIRouter(prefix="/api/memories", tags=["memory-legacy"])


class ImportStoryRequest(BaseModel):
    story: str
    agent_id: Optional[str] = "pero"


@router.post("/import_story")
async def import_story(
    request: ImportStoryRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """
    导入故事/日记初始化长期记忆（LLM提取事件）。
    """
    importer = MemoryImporter(session)
    result = await importer.import_story(request.story, request.agent_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/secretary/run")
async def run_memory_secretary(session: AsyncSession = Depends(get_session)):  # noqa: B008
    try:
        service = ReflectionService(session)
        return await service.run_maintenance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@legacy_memories_router.delete("/by_timestamp/{msg_timestamp}")
async def delete_memory_by_timestamp(
    msg_timestamp: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    service = MemoryService()
    await service.delete_by_msg_timestamp(session, msg_timestamp)
    return {"status": "success"}


@history_router.get("/{source}/{session_id}")
async def get_chat_history(
    source: str,
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    date: str = None,
    sort: str = "asc",
    agent_id: Optional[str] = None,  # 新增agent_id参数
    query: Optional[str] = None,  # [特性] 统一搜索
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    service = MemoryService()
    # 若未提供agent_id则默认为"pero"（兼容性考虑）。
    # Dashboard通常查看特定代理。

    # 若未提供 agent_id，使用当前活跃 agent
    if not agent_id:
        from services.agent.agent_manager import get_agent_manager
        agent_id = get_agent_manager().active_agent_id or "pero"
    target_agent = agent_id
    logs = await service.query_logs(
        session,
        source,
        session_id,
        limit,
        offset=offset,
        date_str=date,
        sort=sort,
        agent_id=target_agent,
        query=query,
    )
    return [
        {
            "id": log.id,
            "role": log.role,
            "content": log.content,
            "raw_content": getattr(log, "raw_content", None),  # 返回原始内容
            "timestamp": log.timestamp,
            "sentiment": getattr(log, "sentiment", None),
            "importance": getattr(log, "importance", None),
            "metadata_json": log.metadata_json,
            "pair_id": getattr(log, "pair_id", None),  # 新增pair_id
            "analysis_status": getattr(log, "analysis_status", "pending"),
            "retry_count": getattr(log, "retry_count", 0),
            "last_error": getattr(log, "last_error", None),
        }
        for log in logs
    ]


async def run_retry_background(log_id: int):
    from services.memory.scorer_service import ScorerService

    try:
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            scorer = ScorerService(session)
            await scorer.retry_interaction(log_id)

            # 广播更新
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = "backend_main"
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)
            envelope.request.action_name = "log_updated"
            envelope.request.params["id"] = str(log_id)
            envelope.request.params["operation"] = "update"
            await gateway_client.send(envelope)

    except Exception as e:
        print(f"[MemoryRouter] 后台重试日志 {log_id} 失败: {e}")


@history_router.post("/{log_id}/retry_analysis")
async def retry_log_analysis(
    log_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    log = await session.get(ConversationLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="未找到日志")

    background_tasks.add_task(run_retry_background, log_id)
    return {"status": "queued", "message": "分析重试已在后台启动"}


@history_router.delete("/{log_id}")
async def delete_chat_log(log_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    try:
        service = MemoryService()
        await service.delete_log(session, log_id)

        # 广播
        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = "backend_main"
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)
            envelope.request.action_name = "log_updated"
            envelope.request.params["id"] = str(log_id)
            envelope.request.params["operation"] = "delete"
            await gateway_client.send(envelope)
        except Exception as e:
            print(f"广播删除失败: {e}")

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@history_router.patch("/{log_id}")
async def update_chat_log(
    log_id: int,
    payload: Dict[str, Any] = Body(...),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    try:
        log = await session.get(ConversationLog, log_id)
        if not log:
            raise HTTPException(status_code=404, detail="未找到日志")
        if "content" in payload:
            log.content = payload["content"]
        await session.commit()
        await session.refresh(log)

        # 广播
        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = "backend_main"
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)
            envelope.request.action_name = "log_updated"
            envelope.request.params["id"] = str(log_id)
            envelope.request.params["operation"] = "update"
            await gateway_client.send(envelope)
        except Exception as e:
            print(f"广播更新失败: {e}")

        return log
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None
