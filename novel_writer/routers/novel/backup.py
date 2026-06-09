"""Cloud backup endpoints for local novel data."""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["backup"])

_BACKUP_STATUS_FILE = Path("data") / ".backup_status.json"


def _read_backup_status() -> dict:
    """Read last backup status from disk."""
    try:
        if _BACKUP_STATUS_FILE.exists():
            return json.loads(_BACKUP_STATUS_FILE.read_text())
    except Exception:
        pass
    return {}


def _write_backup_status(status: dict) -> None:
    """Write last backup status to disk."""
    try:
        _BACKUP_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BACKUP_STATUS_FILE.write_text(json.dumps(status, default=str))
    except Exception:
        pass


def _s3_config() -> dict[str, str]:
    return {
        "endpoint": os.environ.get("S3_ENDPOINT", "").strip(),
        "bucket": os.environ.get("S3_BUCKET", "").strip(),
        "access_key": os.environ.get("S3_ACCESS_KEY", "").strip(),
        "secret_key": os.environ.get("S3_SECRET_KEY", "").strip(),
    }


@router.post("/api/backup/cloud")
def cloud_backup() -> dict:
    """Create a timestamped zip of data/novel_writer.db and upload to S3-compatible storage."""
    s3 = _s3_config()
    if not all(s3.values()):
        return {"status": "not_configured"}

    db_path = Path("data/novel_writer.db")
    if not db_path.exists():
        raise HTTPException(500, "Database file not found at data/novel_writer.db")

    now = dt.datetime.now()
    key = f"backup-{now.strftime('%Y-%m-%d')}.zip"

    try:
        import boto3

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_path, arcname="novel_writer.db")
        buffer.seek(0)
        data = buffer.read()

        client = boto3.client(
            "s3",
            endpoint_url=s3["endpoint"],
            aws_access_key_id=s3["access_key"],
            aws_secret_access_key=s3["secret_key"],
        )
        client.put_object(Bucket=s3["bucket"], Key=key, Body=data, ContentType="application/zip")

        response = client.list_objects_v2(Bucket=s3["bucket"], Prefix="backup-")
        if response.get("Contents"):
            backups = sorted(response["Contents"], key=lambda item: item["Key"], reverse=True)
            for item in backups[30:]:
                client.delete_object(Bucket=s3["bucket"], Key=item["Key"])

        status = {
            "last_backup": now.isoformat(),
            "last_backup_key": key,
            "last_backup_size": len(data),
            "configured": True,
        }
        _write_backup_status(status)
        return {"status": "ok", "key": key, "size": len(data)}
    except ImportError:
        raise HTTPException(500, "boto3 not installed. Run: pip install boto3")
    except Exception as exc:
        raise HTTPException(500, f"Backup failed: {str(exc)[:300]}")


@router.get("/api/backup/status")
def backup_status() -> dict:
    """Return whether cloud backup is configured and the last backup time."""
    configured = all(_s3_config().values())
    status = _read_backup_status()
    return {
        "configured": configured,
        "last_backup": status.get("last_backup"),
        "last_backup_key": status.get("last_backup_key"),
        "last_backup_size": status.get("last_backup_size"),
    }
