"""Private footage → trimmed, captioned vertical MP4, processed by the durable worker."""

import hashlib
import hmac
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .billing import active, reserve
from .database import SessionLocal, get_db
from .models import GrowthJourney, Membership, Project, VideoAsset
from .security import Tenant, audit, owner, tenant
from .workflows.api import project_for
from .workflows.contracts import StrictModel

router = APIRouter(prefix="/v1", tags=["Real footage"])


def root():
    return Path(os.getenv("JOURNEY_MEDIA_DIR", "/tmp/rymu-media"))


def probe(path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_entries",
                "format=duration:stream=codec_type",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        if (
            not math.isfinite(duration)
            or not 1 <= duration <= 600
            or not any(s.get("codec_type") == "video" for s in info["streams"])
        ):
            raise ValueError()
        return duration
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        raise HTTPException(
            422, "Use a valid MP4 or WebM video, between 1 second and 10 minutes"
        ) from None


def signature(asset_id, expires):
    key = os.getenv("JOURNEY_MEDIA_SIGNING_KEY", "")
    if len(key) < 32:
        raise HTTPException(503, "Media signing is not configured")
    return hmac.new(
        key.encode(), f"asset:{asset_id}:{expires}".encode(), hashlib.sha256
    ).hexdigest()


def video_url(asset_id):
    base = os.getenv("PUBLIC_API_URL", "")
    if not base.startswith("https://"):
        raise HTTPException(503, "Public HTTPS media access is required")
    expires = int(time.time()) + 3600
    return f"{base.rstrip('/')}/v1/asset-video/{asset_id}?expires={expires}&signature={signature(asset_id, expires)}"


def lookup(db, project_id, asset_id, context):
    project_for(db, project_id, context)
    row = db.get(VideoAsset, asset_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Video not found")
    return row


def public(row):
    return {
        "id": row.id,
        "status": row.status,
        "duration": row.data.get("duration"),
        "clip_seconds": row.data.get("clip_seconds"),
        "caption": row.data.get("caption", ""),
        "error": row.data.get("error"),
        "journey_id": row.data.get("journey_id"),
        "video_url": video_url(row.id) if row.status == "ready" else None,
    }


@router.get("/projects/{project_id}/assets")
def assets(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project_for(db, project_id, context)
    return {
        "assets": [
            public(r)
            for r in db.scalars(
                select(VideoAsset)
                .where(VideoAsset.project_id == project_id)
                .order_by(VideoAsset.created_at.desc())
                .limit(30)
            )
        ]
    }


@router.post("/projects/{project_id}/assets", status_code=201)
async def upload(
    project_id: str,
    request: Request,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    active(db, context.organization.id)
    from .journey.api import require_enabled

    require_enabled(context)
    if len(os.getenv("JOURNEY_MEDIA_SIGNING_KEY", "")) < 32 or not os.getenv(
        "PUBLIC_API_URL", ""
    ).startswith("https://"):
        raise HTTPException(503, "Configure private media signing and public HTTPS first")
    if request.headers.get("content-type", "").split(";")[0] not in {"video/mp4", "video/webm"}:
        raise HTTPException(415, "Upload an MP4 or WebM video")
    db.refresh(context.organization, with_for_update=True)
    if (
        db.scalar(
            select(func.count()).select_from(VideoAsset).where(VideoAsset.project_id == project_id)
        )
        >= 30
    ):
        raise HTTPException(429, "Delete unused footage before uploading more")
    asset_id = str(uuid4())
    root().mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root() / (asset_id + ".source")
    size = 0
    try:
        with path.open("xb") as target:
            path.chmod(0o600)
            async for chunk in request.stream():
                size += len(chunk)
                if size > 25 * 1024 * 1024:
                    raise HTTPException(413, "Video must be under 25 MB")
                target.write(chunk)
        with path.open("rb") as source:
            header = source.read(12)
        if not (header.startswith(b"\x1aE\xdf\xa3") or header[4:8] == b"ftyp"):
            raise HTTPException(422, "Invalid MP4 or WebM")
        duration = probe(path)
        row = VideoAsset(
            id=asset_id,
            project_id=project_id,
            requested_by=context.user.id,
            status="uploaded",
            data={"source_path": str(path), "duration": duration},
        )
        db.add(row)
        audit(db, context, "footage.uploaded", asset_id)
        db.flush()
        return public(row)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


class ClipInput(StrictModel):
    start: float = Field(default=0, ge=0, le=599, allow_inf_nan=False)
    end: float = Field(ge=1, le=600, allow_inf_nan=False)
    caption: str = Field(min_length=10, max_length=2000)
    subtitles: str = Field(default="", max_length=4000)
    transcribe: bool = False


@router.post("/projects/{project_id}/assets/{asset_id}/render", status_code=202)
def render(
    project_id: str,
    asset_id: str,
    data: ClipInput,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    from .journey.api import require_enabled

    require_enabled(context)
    row = lookup(db, project_id, asset_id, context)
    if row.status != "uploaded":
        raise HTTPException(409, "This footage is already processing or finished")
    if data.end <= data.start or data.end > row.data["duration"] or data.end - data.start > 120:
        raise HTTPException(422, "Choose a clip up to 120 seconds within the source video")
    if data.transcribe and not os.getenv("TRANSCRIPTION_API_KEY"):
        raise HTTPException(503, "Connect transcription for automatic captions")
    seconds = math.ceil(data.end - data.start)
    reserve(db, context.organization.id, "footage_seconds", seconds, "clip-" + row.id)
    changed = db.execute(
        update(VideoAsset)
        .where(VideoAsset.id == row.id, VideoAsset.status == "uploaded")
        .values(status="queued", data={**row.data, **data.model_dump(), "clip_seconds": seconds})
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Video changed. Reload before continuing")
    db.refresh(row)
    return public(row)


def stamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def edit_video(row):
    data = row.data
    output = root() / (row.id + ".mp4")
    subtitles = root() / (row.id + ".srt")
    words = re.sub(r"[\x00-\x1f<>]", " ", data["subtitles"]).split()
    groups = [" ".join(words[i : i + 7]) for i in range(0, len(words), 7)]
    step = data["clip_seconds"] / max(1, len(groups))
    subtitles.write_text(
        "\n\n".join(
            f"{i + 1}\n{stamp(i * step)} --> {stamp((i + 1) * step)}\n{text}"
            for i, text in enumerate(groups)
        )
    )
    filters = "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1"
    if words and not data.get("transcribe"):
        # IDs are server-generated UUIDs; no user text enters the filter expression.
        filters += (
            f",subtitles={subtitles}:force_style='FontName=DejaVu Sans,FontSize=20,MarginV=60'"
        )
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-ss",
                str(data["start"]),
                "-i",
                data["source_path"],
                "-t",
                str(data["end"] - data["start"]),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                filters,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-threads",
                "1",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                "-fs",
                "50000000",
                str(output),
            ],
            capture_output=True,
            timeout=300,
            check=True,
        )
        if data.get("transcribe"):
            import httpx

            from .journey.providers import response_json

            with (
                output.open("rb") as clip,
                httpx.Client(timeout=120, follow_redirects=False) as client,
            ):
                result = response_json(
                    client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": "Bearer " + os.environ["TRANSCRIPTION_API_KEY"]},
                        data={
                            "model": "whisper-1",
                            "response_format": "verbose_json",
                            "timestamp_granularities[]": "segment",
                        },
                        files={"file": ("clip.mp4", clip, "video/mp4")},
                    )
                )
            segments = result.get("segments", [])
            if not segments or len(segments) > 500:
                raise ValueError("No speech captions")
            entries = []
            for item in segments:
                begin, end = float(item["start"]), float(item["end"])
                if (
                    not math.isfinite(begin)
                    or not math.isfinite(end)
                    or not 0 <= begin < end <= data["clip_seconds"] + 1
                ):
                    raise ValueError("Invalid caption timing")
                text = re.sub(r"[\x00-\x1f<>]", " ", str(item["text"]))[:500]
                entries.append(f"{len(entries) + 1}\n{stamp(begin)} --> {stamp(end)}\n{text}")
            subtitles.write_text("\n\n".join(entries))
            captioned = root() / (row.id + ".captioned.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-y",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(output),
                    "-vf",
                    f"subtitles={subtitles}:force_style='FontName=DejaVu Sans,FontSize=20,MarginV=60'",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-threads",
                    "1",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(captioned),
                ],
                capture_output=True,
                timeout=300,
                check=True,
            )
            captioned.replace(output)
        output.chmod(0o600)
        duration = probe(output)
        if duration + 0.5 < data["clip_seconds"]:
            raise ValueError("Incomplete render")
        return str(output)
    finally:
        subtitles.unlink(missing_ok=True)


def process_one(factory=SessionLocal):
    with factory() as db:
        stale = db.scalars(
            select(VideoAsset).where(
                VideoAsset.status == "processing", VideoAsset.lease_until < time.time()
            )
        ).all()
        for row in stale:
            row.status = "failed"
            row.data = {**row.data, "error": "Processing interrupted. No automatic retry."}
        db.commit()
        row = db.scalar(
            select(VideoAsset)
            .where(VideoAsset.status == "queued")
            .order_by(VideoAsset.created_at)
            .limit(1)
        )
        if not row:
            return False
        if (
            db.execute(
                update(VideoAsset)
                .where(VideoAsset.id == row.id, VideoAsset.status == "queued")
                .values(status="processing", lease_until=time.time() + 900)
            ).rowcount
            != 1
        ):
            db.rollback()
            return True
        project = db.get(Project, row.project_id)
        allowed = db.scalar(
            select(Membership.id).where(
                Membership.organization_id == project.organization_id,
                Membership.user_id == row.requested_by,
                Membership.role == "owner",
            )
        )
        db.commit()
        try:
            active(db, project.organization_id)
            from .journey.api import workspace_enabled

            if not allowed or not workspace_enabled(project.organization_id):
                raise ValueError()
            path = edit_video(row)
            row.status, row.data = "ready", {**row.data, "output_path": path}
        except Exception:
            for suffix in [".mp4", ".captioned.mp4"]:
                (root() / (row.id + suffix)).unlink(missing_ok=True)
            row.status, row.data = (
                "failed",
                {
                    **row.data,
                    "error": "Clip processing failed. Check the video format and selected range.",
                },
            )
        result_status, result_data = row.status, row.data
        db.rollback()
        db.execute(
            update(VideoAsset)
            .where(VideoAsset.id == row.id, VideoAsset.status == "processing")
            .values(status=result_status, data=result_data)
        )
        db.commit()
        return True


@router.get("/asset-video/{asset_id}")
def serve(asset_id: str, expires: int, signature: str, db: Session = Depends(get_db)):
    if (
        expires < time.time()
        or expires > time.time() + 3700
        or not hmac.compare_digest(signature, globals()["signature"](asset_id, expires))
    ):
        raise HTTPException(403, "Video link expired")
    row = db.get(VideoAsset, asset_id)
    if not row or row.status != "ready":
        raise HTTPException(404, "Video not found")
    return FileResponse(
        row.data["output_path"],
        media_type="video/mp4",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.post("/projects/{project_id}/assets/{asset_id}/use", status_code=201)
def use(
    project_id: str, asset_id: str, context: Tenant = Depends(owner), db: Session = Depends(get_db)
):
    row = lookup(db, project_id, asset_id, context)
    db.refresh(context.organization, with_for_update=True)
    db.refresh(row)
    if row.status != "ready":
        raise HTTPException(409, "Finish the clip first")
    if row.data.get("journey_id"):
        return {"journey_id": row.data["journey_id"]}
    journey = GrowthJourney(
        project_id=project_id,
        requested_by=context.user.id,
        status="video_ready",
        data={
            "asset_id": row.id,
            "video_id": "asset_" + row.id,
            "video_url": video_url(row.id),
            "script": "Original footage, edited by its owner.",
            "caption": row.data["caption"],
        },
    )
    db.add(journey)
    db.flush()
    row.data = {**row.data, "journey_id": journey.id}
    return {"journey_id": journey.id}


@router.post("/projects/{project_id}/assets/{asset_id}/delete")
def delete_asset(
    project_id: str, asset_id: str, context: Tenant = Depends(owner), db: Session = Depends(get_db)
):
    row = lookup(db, project_id, asset_id, context)
    if row.status in {"queued", "processing"}:
        raise HTTPException(409, "Wait for processing to finish")
    journey = (
        db.get(GrowthJourney, row.data.get("journey_id")) if row.data.get("journey_id") else None
    )
    if journey:
        db.refresh(journey, with_for_update=True)
    if journey and journey.status in {
        "scheduled",
        "publishing",
        "instagram_processing",
        "checking_instagram",
        "instagram_ready",
        "publishing_instagram",
    }:
        raise HTTPException(
            409, "Cancel scheduled content or wait for publication before deleting its source"
        )
    for key in ["source_path", "output_path"]:
        if row.data.get(key):
            Path(row.data[key]).unlink(missing_ok=True)
    if journey:
        if journey.status not in {"posted", "measured", "measuring"}:
            journey.status = "failed"
        journey.revision += 1
        journey.data = {**journey.data, "video_url": None, "local_asset_deleted": True}
    for suffix in [".mp4", ".captioned.mp4", ".srt"]:
        (root() / (row.id + suffix)).unlink(missing_ok=True)
    db.delete(row)
    return {"deleted": True}
