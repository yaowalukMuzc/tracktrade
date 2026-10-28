"""`/attachments` — upload (≤ MAX_UPLOAD_MB, PNG/JPEG/WebP), owner-only download, delete."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext, get_owned_or_404
from app.core.config import Settings
from app.core.db import get_session
from app.core.errors import AppError, Conflict
from app.core.storage import Storage
from app.modules.attachments.models import Attachment
from app.modules.auth.deps import get_access_context

router = APIRouter(prefix="/attachments", tags=["attachments"])

# Detect the type from the bytes, never from the client's Content-Type / filename.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def sniff_image(data: bytes) -> str | None:
    for magic, content_type in _SIGNATURES:
        if data.startswith(magic):
            return content_type
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_type: str
    size_bytes: int
    filename: str | None
    url: str
    created_at: datetime


def to_out(att: Attachment) -> AttachmentOut:
    return AttachmentOut(
        id=att.id,
        content_type=att.content_type,
        size_bytes=att.size_bytes,
        filename=att.filename,
        url=f"/api/v1/attachments/{att.id}/content",
        created_at=att.created_at,
    )


def _storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


@router.post("", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_session),
) -> AttachmentOut:
    settings: Settings = request.app.state.settings
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise AppError(
            "file_too_large",
            f"Files must be {settings.MAX_UPLOAD_MB} MB or smaller",
            status_code=413,
            details={"max_mb": settings.MAX_UPLOAD_MB},
        )
    content_type = sniff_image(data)
    if content_type is None:
        raise AppError("unsupported_file_type", "Only PNG, JPEG or WebP images", status_code=415)
    att_id = uuid.uuid4()
    key = f"{ctx.owner_id}/{att_id}"
    await _storage(request).put(key, data)
    att = Attachment(
        id=att_id,
        user_id=ctx.owner_id,
        storage_key=key,
        content_type=content_type,
        size_bytes=len(data),
        filename=(file.filename or "")[:255] or None,
        sha256=hashlib.sha256(data).hexdigest(),
    )
    session.add(att)
    await session.flush()
    await session.refresh(att)
    return to_out(att)


@router.get("/{attachment_id}/content")
async def content(
    attachment_id: uuid.UUID,
    request: Request,
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    att = await get_owned_or_404(session, Attachment, attachment_id, ctx)
    data = await _storage(request).get(att.storage_key)
    return Response(
        data,
        media_type=att.content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    attachment_id: uuid.UUID,
    request: Request,
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    att = await get_owned_or_404(session, Attachment, attachment_id, ctx)
    await session.delete(att)
    try:
        await session.flush()
    except IntegrityError as exc:  # still referenced (e.g. a playbook example)
        raise Conflict("attachment_in_use", "Remove it from where it is used first") from exc
    await _storage(request).delete(att.storage_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
