"""辨識端點。

★ FR-027 的關鍵分支在此：辨識服務回傳 items: [] 時走**成功**路徑
  （HTTP 200、status=completed、item_count=0），不是錯誤。若歸為錯誤，
  前端會落入通用錯誤處理而渲染出空的結果清單。
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Query, UploadFile

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.errors import AppError
from app.db.models import STATUS_COMPLETED, STATUS_FAILED, STATUS_PROCESSING, RecognitionJob
from app.schemas.recognition import Recognition
from app.services import recognition_client
from app.services.photo_storage import get_photo_storage
from app.services.recognition_client import RecognitionServiceError

router = APIRouter(prefix="/recognitions", tags=["recognition"])


def _validate_upload(photo: UploadFile, content: bytes) -> None:
    settings = get_settings()
    if photo.content_type not in settings.photo_allowed_content_types:
        raise AppError("UNSUPPORTED_MEDIA_TYPE")
    if len(content) > settings.photo_max_bytes:
        raise AppError("PAYLOAD_TOO_LARGE")


def _to_response(job: RecognitionJob, items: list) -> Recognition:
    return Recognition(
        id=job.id,
        status=job.status,
        items=items,
        message=job.service_message,
        retry_count=job.retry_count,
        requested_at=job.requested_at,
        completed_at=job.completed_at,
    )


async def _run_recognition(
    db: DbSession, job: RecognitionJob, photo_bytes: bytes, mode: str | None
) -> Recognition:
    """呼叫辨識服務並依結果更新 job。

    同步等待（OQ-1）。非同步遷移時，本函式改為排入背景並立即回傳
    status=processing；job 的欄位已足夠承載該流程，不需 schema 變更。
    """
    try:
        raw = await recognition_client.call_recognition_service(photo_bytes, mode=mode)
    except RecognitionServiceError as exc:
        job.status = STATUS_FAILED
        job.error_code = exc.error_code
        job.completed_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        raise exc.to_app_error() from exc

    items = recognition_client.build_items(raw.items)

    # ★ items 為空也是 completed——「未偵測到食物」是成功的辨識結果。
    # 上游不提供空結果的說明文字，此處合成固定文案（research.md R-16）。
    job.status = STATUS_COMPLETED
    job.error_code = None
    job.item_count = len(items)
    job.service_message = raw.message or (
        recognition_client.DEFAULT_EMPTY_MESSAGE if not items else None
    )
    job.raw_response = raw.raw
    job.duration_ms = raw.duration_ms  # 供 OQ-1／OQ-4 實測校準
    job.completed_at = datetime.now(UTC)
    db.add(job)
    db.commit()
    db.refresh(job)

    return _to_response(job, items)


@router.post("", response_model=Recognition)
async def create_recognition(
    db: DbSession,
    user: CurrentUser,
    photo: UploadFile = File(...),
    mode: str | None = Query(default=None, include_in_schema=False),
) -> Recognition:
    content = await photo.read()
    _validate_upload(photo, content)

    # 先存檔再呼叫：重試時可重用照片，使用者不需重新上傳（FR-028）。
    storage = get_photo_storage()
    photo_path = storage.save(user.id, content)

    job = RecognitionJob(
        user_id=user.id,
        status=STATUS_PROCESSING,
        photo_path=photo_path,
        requested_at=now_utc(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return await _run_recognition(db, job, content, mode)


def _get_owned_job(db: DbSession, user_id: uuid.UUID, job_id: uuid.UUID) -> RecognitionJob:
    job = db.get(RecognitionJob, job_id)
    # 非本人一律 404（不回 403，避免洩漏資源是否存在）。
    if job is None or job.user_id != user_id:
        raise AppError("NOT_FOUND")
    return job


@router.get("/{recognition_id}", response_model=Recognition)
async def get_recognition(
    recognition_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Recognition:
    """讀取辨識資源。

    同步實作下用於重新取得結果；非同步遷移後即為輪詢端點——
    前端的 useRecognition() 已預留 processing 分支。
    """
    job = _get_owned_job(db, user.id, recognition_id)

    items = []
    if job.status == STATUS_COMPLETED and job.raw_response:
        items = recognition_client.build_items(job.raw_response.get("items") or [])

    if job.status == STATUS_FAILED and job.error_code:
        raise AppError(recognition_client.ERROR_CODE_MAP[job.error_code])

    return _to_response(job, items)


@router.post("/{recognition_id}/retry", response_model=Recognition)
async def retry_recognition(
    recognition_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    mode: str | None = Query(default=None, include_in_schema=False),
) -> Recognition:
    """以既有照片重新辨識——**不需重新上傳**（FR-028）。"""
    job = _get_owned_job(db, user.id, recognition_id)

    storage = get_photo_storage()
    if not storage.exists(job.photo_path):
        raise AppError("NOT_FOUND")

    photo_bytes = storage.read(job.photo_path)

    job.status = STATUS_PROCESSING
    job.retry_count += 1
    job.completed_at = None
    job.error_code = None
    db.add(job)
    db.commit()

    return await _run_recognition(db, job, photo_bytes, mode)
