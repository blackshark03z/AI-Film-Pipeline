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
from ..live_runtime import utc_now
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
            connection.execute("CREATE TABLE IF NOT EXISTS reference_upload_events ("
                "reservation_id TEXT NOT NULL, sequence INTEGER NOT NULL, stage TEXT NOT NULL, "
                "payload TEXT NOT NULL, at TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL, "
                "PRIMARY KEY(reservation_id,sequence))")
            for operation in ("UPDATE", "DELETE"):
                connection.execute(f"CREATE TRIGGER IF NOT EXISTS ref_events_no_{operation.lower()} "
                    f"BEFORE {operation} ON reference_upload_events BEGIN "
                    "SELECT RAISE(ABORT,'immutable reference event'); END")
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
        self.read_progress(key)  # Validate journal/receipt agreement on every reuse.
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
                 provider_media_sha256: str, *, verification_hash: str | None = None) -> dict:
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
            events = self._events(connection, key)
            identities = {event['data']['media_id'] for event in events
                          if event['stage'] == 'REMOTE_RESOURCE_IDENTIFIED'}
            if identities != {media_id}:
                raise OwnerAmbiguityGate("verified identity differs from identified resource")
            updated = connection.execute("UPDATE reference_uploads SET state='VERIFIED',"
                "media_id=?,provider_media_sha256=?,payload=? "
                "WHERE id=? AND state='RESERVED' AND media_id IS NULL",
                (media_id, provider_media_sha256, canonical_json(result), key))
            if updated.rowcount != 1:
                raise OwnerAmbiguityGate("reference upload completion collision")
            self._append(connection, key, "REMOTE_RESOURCE_VERIFIED",
                         {"media_id": media_id, "provider_media_sha256": provider_media_sha256,
                          "verification_hash": verification_hash or sha256({
                              'media_id': media_id, 'provider_media_sha256': provider_media_sha256})})
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        if self._read(key) != {k: value for k, value in result.items() if k != "id"}:
            raise OwnerAmbiguityGate("reference upload fresh readback mismatch")
        return result

    @staticmethod
    def _validate_event(stage: str, data: dict) -> None:
        fields = {
            'LOCAL_RESERVED': {'binding'},
            'REQUEST_ARMED': {'body_sha256'},
            'HTTP_RESPONSE_OBSERVED': {'status', 'response_bytes_len'},
            'REMOTE_RESOURCE_IDENTIFIED': {'media_id', 'method', 'evidence_hash'},
            'REMOTE_RESOURCE_VERIFIED': {'media_id', 'provider_media_sha256', 'verification_hash'},
            'RECONCILE_PROBED': {'evidence_hash', 'candidate_count', 'match_count', 'unresolved_count'},
            'FAILED_AMBIGUOUS': {'diagnostic'},
        }
        if stage not in fields or set(data) != fields[stage]:
            raise ValueError('invalid reference event')
        for key, value in data.items():
            if key == 'binding':
                if (not isinstance(value, dict) or set(value) != {'id', 'provider_id',
                    'project_id', 'account_id', 'asset_id', 'reference_sha256',
                    'request_id', 'upload_attempts', 'state', 'media_id', 'provider_media_sha256'}
                        or value['upload_attempts'] != 0 or value['state'] != 'LOCAL_RESERVED'
                        or value['media_id'] is not None or value['provider_media_sha256'] is not None):
                    raise ValueError('invalid reference intent')
                if not UUID_RE.fullmatch(value['project_id']) or not UUID_RE.fullmatch(value['request_id']):
                    raise ValueError('invalid reference intent identity')
                if any(not isinstance(value[k], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', value[k])
                       for k in ('id', 'provider_id', 'account_id', 'asset_id', 'reference_sha256')):
                    raise ValueError('unsafe reference intent')
            elif key == 'media_id':
                if not isinstance(value, str) or not UUID_RE.fullmatch(value):
                    raise ValueError('invalid remote identity')
            elif key.endswith('sha256') or key.endswith('hash'):
                if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
                    raise ValueError('invalid reference evidence hash')
            elif key == 'status' or key.endswith('count') or key == 'response_bytes_len':
                if type(value) is not int or value < 0 or (key == 'status' and not 100 <= value <= 599):
                    raise ValueError('invalid reference evidence count')
            elif not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', value):
                raise ValueError('unsafe reference evidence')

    @classmethod
    def _events(cls, connection, key):
        result, prior, stages = [], '0' * 64, set()
        for expected, (seq, stage, payload, at, previous, digest) in enumerate(connection.execute(
                'SELECT sequence,stage,payload,at,previous,digest FROM reference_upload_events '
                'WHERE reservation_id=? ORDER BY sequence', (key,)), 1):
            data = json.loads(payload)
            cls._validate_event(stage, data)
            if stage != 'RECONCILE_PROBED' and stage in stages:
                raise OwnerAmbiguityGate('duplicate reference lifecycle stage')
            if stage == 'LOCAL_RESERVED' and seq != 1:
                raise OwnerAmbiguityGate('reference local intent must be first')
            if stage == 'LOCAL_RESERVED' and data['binding']['id'] != key:
                raise OwnerAmbiguityGate('reference local intent key mismatch')
            if seq != expected or previous != prior or digest != sha256({
                    'id': key, 'sequence': seq, 'stage': stage, 'data': data,
                    'at': at, 'previous': prior}):
                raise OwnerAmbiguityGate('reference journal integrity failure')
            result.append({'stage': stage, 'data': data, 'at': at})
            stages.add(stage)
            prior = digest
        return result

    @classmethod
    def _append(cls, connection, key, stage, data):
        cls._validate_event(stage, data)
        events = cls._events(connection, key)
        if stage != 'RECONCILE_PROBED':
            previous = next((event for event in events if event['stage'] == stage), None)
            if previous:
                if previous['data'] != data:
                    raise OwnerAmbiguityGate('conflicting reference journal event')
                return
        seq = len(events) + 1
        previous = connection.execute('SELECT digest FROM reference_upload_events '
            'WHERE reservation_id=? ORDER BY sequence DESC LIMIT 1', (key,)).fetchone()
        prior, at = previous[0] if previous else '0' * 64, utc_now()
        digest = sha256({'id': key, 'sequence': seq, 'stage': stage,
                         'data': data, 'at': at, 'previous': prior})
        connection.execute('INSERT INTO reference_upload_events VALUES (?,?,?,?,?,?,?)',
                           (key, seq, stage, canonical_json(data), at, prior, digest))

    def events(self, key):
        self.initialize()
        with self._connect() as connection:
            return self._events(connection, key)

    def read_progress(self, key: str) -> dict | None:
        self.initialize()
        row, events = self._read(key), self.events(key)
        local = next((event['data']['binding'] for event in events
                      if event['stage'] == 'LOCAL_RESERVED'), None)
        if row is None and local is None:
            return None
        result = {'id': key, **row} if row else dict(local)
        if local and row and any(local[k] != result[k] for k in
                ('id', 'provider_id', 'project_id', 'account_id', 'asset_id',
                 'reference_sha256', 'request_id')):
            raise OwnerAmbiguityGate('local and durable reference bindings disagree')
        identified = next((event['data']['media_id'] for event in events
                           if event['stage'] == 'REMOTE_RESOURCE_IDENTIFIED'), None)
        verified = next((event['data'] for event in events
                        if event['stage'] == 'REMOTE_RESOURCE_VERIFIED'), None)
        if result['state'] == 'VERIFIED':
            if (identified and identified != result['media_id']) or (verified and (
                    verified['media_id'] != result['media_id'] or
                    verified['provider_media_sha256'] != result['provider_media_sha256'])):
                raise OwnerAmbiguityGate('reference receipt and journal disagree')
            effective = 'REMOTE_RESOURCE_VERIFIED'
        elif verified:
            raise OwnerAmbiguityGate('verified event without atomic reference receipt')
        elif identified:
            effective = 'REMOTE_RESOURCE_IDENTIFIED'
            result['media_id'] = identified
        elif any(e['stage'] == 'FAILED_AMBIGUOUS' for e in events):
            effective = 'FAILED_AMBIGUOUS'
        elif row:
            effective = 'REQUEST_ARMED' if any(e['stage'] == 'REQUEST_ARMED' for e in events) else 'LEGACY_RESERVED_UNCERTAIN'
        else:
            effective = 'LOCAL_RESERVED'
        return {**result, 'effective_state': effective}

    def reserve_local(self, provider_id, project_id, account_id, asset):
        self._verify_asset(asset)
        self.initialize()
        key = _key(provider_id, project_id, account_id, asset)
        existing = self.read_progress(key)
        if existing:
            return existing
        fields = {'id': key, 'provider_id': provider_id, 'project_id': project_id.lower(),
            'account_id': account_id, 'asset_id': asset.asset_id, 'reference_sha256': asset.sha256,
            'request_id': str(uuid.uuid5(uuid.NAMESPACE_URL, key)), 'upload_attempts': 0,
            'state': 'LOCAL_RESERVED', 'media_id': None, 'provider_media_sha256': None}
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if (connection.execute('SELECT id FROM reference_uploads LIMIT 1').fetchone()
                    or connection.execute('SELECT reservation_id FROM reference_upload_events LIMIT 1').fetchone()):
                # A concurrent caller may have reserved this exact intent.
                events = self._events(connection, key)
                if not events or events[0]['data'] != {'binding': fields}:
                    raise OwnerAmbiguityGate('one reference intent per database')
            else:
                self._append(connection, key, 'LOCAL_RESERVED', {'binding': fields})
        return self.read_progress(key)

    def arm_local(self, key, body_sha256):
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            events = self._events(connection, key)
            if (not events or events[0]['stage'] != 'LOCAL_RESERVED'
                    or connection.execute('SELECT id FROM reference_uploads LIMIT 1').fetchone()
                    or any(e['stage'] == 'REQUEST_ARMED' for e in events)):
                raise OwnerAmbiguityGate('reference arm already consumed or legacy uncertain')
            fields = {**events[0]['data']['binding'], 'upload_attempts': 1, 'state': 'RESERVED'}
            connection.execute('INSERT INTO reference_uploads VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                tuple(fields[k] for k in ('id', 'provider_id', 'project_id', 'account_id', 'asset_id',
                    'reference_sha256', 'upload_attempts', 'request_id', 'state', 'media_id',
                    'provider_media_sha256')) + (canonical_json(fields),))
            self._append(connection, key, 'REQUEST_ARMED', {'body_sha256': body_sha256})

    def record_event(self, key, stage, data):
        progress = self.read_progress(key)
        if progress is None:
            raise ValueError('reference reservation absent')
        if progress['effective_state'] == 'LOCAL_RESERVED':
            raise OwnerAmbiguityGate('remote evidence cannot precede request arm')
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            self._append(connection, key, stage, data)

    def record_identified(self, key, media_id, *, method, evidence_hash):
        progress = self.read_progress(key)
        if progress is None or progress['effective_state'] == 'LOCAL_RESERVED':
            raise OwnerAmbiguityGate('resource identity without armed reference')
        if progress['media_id'] not in (None, media_id):
            raise OwnerAmbiguityGate('reference resource identity changed')
        self.record_event(key, 'REMOTE_RESOURCE_IDENTIFIED',
            {'media_id': media_id, 'method': method, 'evidence_hash': evidence_hash})
