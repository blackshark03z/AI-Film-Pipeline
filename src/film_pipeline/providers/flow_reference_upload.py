"""One hash-bound reference upload receipt shared by two Flow I2V shots.

This is operational transport evidence in the Film runtime database, not a
new Film domain entity. No URL, cookie, CAPTCHA token or request body is stored.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path

from ..core import canonical_json, sha256
from ..live_runtime import Asset, file_sha256
from .flow_rpc_contract import UUID_RE


class OwnerAmbiguityGate(RuntimeError):
    """The external effect may have happened; only Owner can choose next action."""


def _key(provider_id: str, project_id: str, account_id: str, asset: Asset) -> str:
    if (provider_id != "flow_veo" or not UUID_RE.fullmatch(project_id)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", account_id)
            or asset.origin != "reference" or asset.asset_type != "image"):
        raise ValueError("reference upload binding invalid")
    return "refup_" + sha256({"provider_id": provider_id,
        "project_id": project_id.lower(), "account_id": account_id,
        "asset_id": asset.asset_id, "reference_sha256": asset.sha256})


class ReferenceUploadStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def initialize(self) -> None:
        connection = self._connect()
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS reference_uploads (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    reference_sha256 TEXT NOT NULL,
                    upload_attempts INTEGER NOT NULL CHECK (upload_attempts=1),
                    request_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('RESERVED','VERIFIED')),
                    media_id TEXT,
                    provider_media_sha256 TEXT,
                    payload TEXT NOT NULL,
                    UNIQUE(provider_id,project_id)
                )
            """)
            connection.execute("CREATE TRIGGER IF NOT EXISTS reference_uploads_no_delete "
                "BEFORE DELETE ON reference_uploads BEGIN "
                "SELECT RAISE(ABORT,'immutable reference upload'); END")
            connection.execute("CREATE TRIGGER IF NOT EXISTS reference_uploads_verified_no_update "
                "BEFORE UPDATE ON reference_uploads WHEN OLD.state='VERIFIED' BEGIN "
                "SELECT RAISE(ABORT,'verified reference upload immutable'); END")
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _verify_asset(asset: Asset) -> None:
        path = Path(asset.uri_or_path)
        if not path.is_file() or file_sha256(path) != asset.sha256:
            raise ValueError("reference bytes no longer match frozen Asset")

    def _read(self, key: str):
        connection = self._connect()
        try:
            row = connection.execute("SELECT provider_id,project_id,account_id,asset_id,"
                "reference_sha256,upload_attempts,request_id,state,media_id,"
                "provider_media_sha256,payload FROM reference_uploads WHERE id=?", (key,)).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        fields = ("provider_id", "project_id", "account_id", "asset_id",
                  "reference_sha256", "upload_attempts", "request_id", "state",
                  "media_id", "provider_media_sha256")
        result = dict(zip(fields, row[:-1]))
        if json.loads(row[-1]) != {"id": key, **result}:
            raise ValueError("reference upload receipt integrity mismatch")
        return result

    def read_verified(self, provider_id: str, project_id: str, account_id: str,
                      asset: Asset) -> dict | None:
        self._verify_asset(asset)
        self.initialize()
        key = _key(provider_id, project_id, account_id, asset)
        row = self._read(key)
        if row is None:
            return None
        if (row["asset_id"] != asset.asset_id or row["reference_sha256"] != asset.sha256
                or row["project_id"] != project_id.lower() or row["account_id"] != account_id
                or row["upload_attempts"] != 1):
            raise OwnerAmbiguityGate("reference upload binding disagrees with frozen Asset")
        if row["state"] == "RESERVED":
            raise OwnerAmbiguityGate("reference upload reserved without verified receipt")
        if (row["state"] != "VERIFIED" or not UUID_RE.fullmatch(row["media_id"] or "")
                or not re.fullmatch(r"[0-9a-f]{64}", row["provider_media_sha256"] or "")):
            raise OwnerAmbiguityGate("reference upload receipt is unqualified")
        return {"id": key, **row}

    def reserve_once(self, provider_id: str, project_id: str, account_id: str,
                     asset: Asset) -> dict:
        """Reserve before the only POST; existing reservation never grants retry."""
        self._verify_asset(asset)
        key = _key(provider_id, project_id, account_id, asset)
        self.initialize()
        request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
        fields = {"id": key, "provider_id": provider_id,
            "project_id": project_id.lower(), "account_id": account_id,
            "asset_id": asset.asset_id, "reference_sha256": asset.sha256,
            "upload_attempts": 1, "request_id": request_id,
            "state": "RESERVED", "media_id": None,
            "provider_media_sha256": None}
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            # This store is dedicated to one slice: one upload reservation in
            # the whole database, even if a caller changes a binding argument.
            prior = connection.execute("SELECT id FROM reference_uploads LIMIT 1").fetchone()
            if prior is not None:
                raise OwnerAmbiguityGate("reference upload already reserved or verified")
            connection.execute("INSERT INTO reference_uploads VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, provider_id, project_id.lower(), account_id, asset.asset_id,
                 asset.sha256, 1, request_id, "RESERVED", None, None,
                 canonical_json(fields)))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return fields

    def complete(self, reservation: dict, media_id: str,
                 provider_media_sha256: str) -> dict:
        if (not UUID_RE.fullmatch(media_id)
                or not re.fullmatch(r"[0-9a-f]{64}", provider_media_sha256)):
            raise OwnerAmbiguityGate("reference upload response or readback unqualified")
        key = reservation["id"]
        row = self._read(key)
        if row is None or row["state"] != "RESERVED" or row["request_id"] != reservation["request_id"]:
            raise OwnerAmbiguityGate("reference upload reservation changed")
        result = {"id": key, **row, "state": "VERIFIED", "media_id": media_id,
                  "provider_media_sha256": provider_media_sha256}
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute("UPDATE reference_uploads SET state='VERIFIED',"
                "media_id=?,provider_media_sha256=?,payload=? "
                "WHERE id=? AND state='RESERVED' AND media_id IS NULL",
                (media_id, provider_media_sha256, canonical_json(result), key))
            if updated.rowcount != 1:
                raise OwnerAmbiguityGate("reference upload completion collision")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        if self._read(key) != {k: value for k, value in result.items() if k != "id"}:
            raise OwnerAmbiguityGate("reference upload fresh readback mismatch")
        return result
