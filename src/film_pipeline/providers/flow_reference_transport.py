"""Bounded reference lifecycle; private RPC remains behind the session adapter.

Adapted from Gemini's two-phase research design, with immutable identity,
all-candidate reconciliation and conservative evidence semantics. This offers
AT_MOST_ONCE_WITH_POSSIBLE_LOSS, not exactly-once delivery.
"""
from __future__ import annotations

import hashlib
import io
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from ..core import canonical_json, sha256
from . import flow_rpc_contract as contract
from .flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore, _key
from .flow_upload_classifier import (
    QualifiedUploadPending,
    UploadResponseClassified,
)

COMPARISON_VERSION = 'reference-rgb-dhash256-v2-flow-cdn-20260930'


def image_comparison(source: bytes, observed: bytes) -> dict:
    """Strong transport content check; dHash is never sufficient by itself."""
    with Image.open(io.BytesIO(source)) as left, Image.open(io.BytesIO(observed)) as right:
        left.load()
        right.load()
        a, b = left.convert('RGB'), right.convert('RGB')
        result = {'version': COMPARISON_VERSION,
            'source_sha256': hashlib.sha256(source).hexdigest(),
            'provider_media_sha256': hashlib.sha256(observed).hexdigest(),
            'source_dimensions': list(a.size), 'observed_dimensions': list(b.size),
            'strong_match': False}
        if a.size != b.size:
            return {**result, 'method': 'dimensions_mismatch'}
        if source == observed:
            return {**result, 'strong_match': True, 'method': 'exact_bytes'}
        diff = ImageChops.difference(a, b)
        if not any(diff.getbbox() or ()):
            return {**result, 'strong_match': True, 'method': 'exact_decoded_rgb'}
        stats = ImageStat.Stat(diff)
        mae, rms = max(stats.mean), max(stats.rms)
        hist = diff.histogram()
        tail = max(sum(hist[channel * 256 + 17:(channel + 1) * 256]) /
                   (a.width * a.height) for channel in range(3))
        tile_mae = max(max(ImageStat.Stat(diff.crop((x, y,
            min(x + 64, a.width), min(y + 64, a.height)))).mean)
            for y in range(0, a.height, 64) for x in range(0, a.width, 64))

        def dhash(image):
            gray = image.convert('L').resize((17, 16), Image.Resampling.LANCZOS)
            values = gray.tobytes()
            value = 0
            for y in range(16):
                for x in range(16):
                    value = (value << 1) | (values[y * 17 + x] > values[y * 17 + x + 1])
            return value

        distance = (dhash(a) ^ dhash(b)).bit_count()
        # Flow CDN calibration: true references have MAE <=1.31, RMS <=3.22,
        # ringing <=.0099, tile MAE <=5.37 and dHash distance 0. Require every
        # bound; a perceptual hash collision never qualifies content by itself.
        strong = mae <= 3 and rms <= 5 and tail <= .02 and tile_mae <= 8 and distance <= 4
        return {**result, 'method': 'conservative_rgb_and_detail',
            'strong_match': strong, 'max_channel_mae': mae, 'max_channel_rms': rms,
            'large_difference_fraction': tail, 'max_tile_mae': tile_mae,
            'dhash256_distance': distance}


class FlowReferenceTransport:
    def __init__(self, store: ReferenceUploadStore, session, *, account_id: str,
                 evidence_dir: Path, probes: int = 3, readbacks: int = 3,
                 interval_s: float = 2):
        if not 1 <= probes <= 5 or not 1 <= readbacks <= 5 or not 0 <= interval_s <= 10:
            raise ValueError('bounded reference read policy required')
        self.store, self.session, self.account_id = store, session, account_id
        self.evidence_dir = Path(evidence_dir)
        self.probes, self.readbacks, self.interval_s = probes, readbacks, interval_s
        self.last_evidence = None

    def _evidence(self, data):
        digest = sha256(data)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / f'{digest}.json'
        encoded = canonical_json(data).encode('utf-8')
        if path.exists() and path.read_bytes() != encoded:
            raise OwnerAmbiguityGate('reference evidence artifact collision')
        if not path.exists():
            with path.open('xb') as stream:
                stream.write(encoded)
                stream.flush()
                import os
                os.fsync(stream.fileno())
        self.last_evidence = {**data, 'evidence_hash': digest, 'evidence_path': str(path.resolve())}
        return digest

    def _source(self, asset):
        source = Path(asset.uri_or_path).read_bytes()
        if (asset.origin != 'reference' or asset.asset_type != 'image'
                or hashlib.sha256(source).hexdigest() != asset.sha256):
            raise ValueError('reference bytes/hash mutation rejected')
        return source

    def ensure_verified(self, asset):
        source = self._source(asset)
        key = _key('flow_veo', self.session.project_id, self.account_id, asset)
        progress = self.store.read_progress(key)
        if progress and progress['effective_state'] == 'REMOTE_RESOURCE_VERIFIED':
            return self.store.read_verified('flow_veo', self.session.project_id,
                                            self.account_id, asset)
        if progress and progress['effective_state'] == 'REMOTE_RESOURCE_IDENTIFIED':
            return self.verify_identified(asset, progress, source)
        if progress and progress['effective_state'] != 'LOCAL_RESERVED':
            return self.reconcile_only(asset)
        # Drift/auth preflight occurs before creating a new intent.
        self.session.catalog()
        if self.session.catalog_fingerprint != contract.QUALIFIED_BASELINE_FINGERPRINT:
            raise ValueError('FLOW_REFERENCE_RPC_DRIFT')
        progress = self.store.reserve_local('flow_veo', self.session.project_id,
                                            self.account_id, asset)
        if progress['effective_state'] != 'LOCAL_RESERVED':
            raise OwnerAmbiguityGate('reference lifecycle changed during preparation')
        try:
            self.session.upload_reference(source, progress['request_id'],
                before_post=lambda digest: self.store.arm_local(key, digest),
                on_http_response=lambda status, length: self.store.record_event(key,
                    'HTTP_RESPONSE_OBSERVED', {'status': status, 'response_bytes_len': length}),
                on_identified=lambda media_id: self.store.record_identified(key, media_id,
                    method='upload_response', evidence_hash=sha256({'media_id': media_id,
                        'request_id': progress['request_id'], 'source_sha256': asset.sha256})))
        except UploadResponseClassified as classified:
            digest = self._evidence({'kind': 'upload_response_skeleton',
                'classification': classified.classification, 'reason': classified.reason,
                'skeleton': classified.skeleton, 'request_id': progress['request_id'],
                'source_sha256': asset.sha256})
            self.store.record_event(key, 'UPLOAD_RESPONSE_CLASSIFIED',
                {'classification': classified.classification,
                 'skeleton_hash': classified.fingerprint})
            if isinstance(classified, QualifiedUploadPending):
                raise
            self.store.record_event(key, 'FAILED_AMBIGUOUS',
                                    {'diagnostic': 'upload_response_unresolved'})
            raise OwnerAmbiguityGate(
                'upload armed; response unresolved; no re-upload') from None
        except Exception:
            current = self.store.read_progress(key)
            if current and current['effective_state'] != 'LOCAL_RESERVED':
                self.store.record_event(key, 'FAILED_AMBIGUOUS',
                                        {'diagnostic': 'upload_response_unresolved'})
                raise OwnerAmbiguityGate('upload armed; response unresolved; no re-upload') from None
            raise
        return self.verify_identified(asset, self.store.read_progress(key), source)

    def verify_identified(self, asset, progress, source=None):
        source = self._source(asset) if source is None else source
        if not progress or progress['effective_state'] != 'REMOTE_RESOURCE_IDENTIFIED':
            raise OwnerAmbiguityGate('identified reference required before verification')
        media_id, returned = progress['media_id'], None
        for attempt in range(self.readbacks):
            try:
                returned = self.session.media(media_id, 'image')
            except OwnerAmbiguityGate:
                raise
            except Exception:
                returned = None
            if returned:
                break
            if attempt + 1 < self.readbacks:
                time.sleep(self.interval_s)
        if not returned:
            raise OwnerAmbiguityGate('identified resource retained; readback unavailable')
        try:
            comparison = image_comparison(source, returned)
        except Exception:
            raise OwnerAmbiguityGate('identified resource retained; image decode unqualified') from None
        digest = self._evidence({'kind': 'exact_identity_verification', 'reservation_id': progress['id'],
            'project_id': self.session.project_id, 'media_id': media_id, 'comparison': comparison})
        if not comparison['strong_match']:
            raise OwnerAmbiguityGate('identified resource retained; reference content mismatch')
        return self.store.complete(progress, media_id, comparison['provider_media_sha256'],
                                   verification_hash=digest)

    def reconcile_only(self, asset, *, expected_media_id=None,
                       preexisting_ids=None):
        """No upload path exists here. Missing catalog rows never grant upload.

        ``preexisting_ids`` (optional): provider media ids durably proven to
        exist BEFORE the upload — e.g. the frozen pre-dispatch catalog
        baseline. A row whose readback is unresolved but whose identity is
        proven pre-existing cannot be the uploaded media, so it does not
        block the unique-match confirmation. Any unresolved row NOT covered
        by that durable evidence still blocks (default strict behavior when
        ``preexisting_ids`` is None)."""
        source = self._source(asset)
        key = _key('flow_veo', self.session.project_id, self.account_id, asset)
        progress = self.store.read_progress(key)
        if expected_media_id is not None:
            if not isinstance(expected_media_id, str) or not contract.UUID_RE.fullmatch(expected_media_id):
                raise ValueError('expected reference identity invalid')
            if progress and progress['media_id'] not in (None, expected_media_id):
                raise OwnerAmbiguityGate('existing reference identity disagrees with Owner evidence')
        if progress is None or progress['effective_state'] == 'LOCAL_RESERVED':
            raise OwnerAmbiguityGate('existing externally uncertain reference required')
        if progress['effective_state'] == 'REMOTE_RESOURCE_VERIFIED':
            return self.store.read_verified('flow_veo', self.session.project_id,
                                            self.account_id, asset)
        if progress['effective_state'] == 'REMOTE_RESOURCE_IDENTIFIED':
            return self.verify_identified(asset, progress, source)
        stable = None
        for probe in range(self.probes):
            records = self.session.catalog()
            contract._validate_catalog_rows(records, self.session.project_id)
            if self.session.catalog_fingerprint != contract.QUALIFIED_BASELINE_FINGERPRINT:
                raise OwnerAmbiguityGate('catalog contract drift during reconciliation')
            candidates, unresolved, matches = [], [], []
            for row in records:
                if len(row) != 7:
                    continue  # Qualified length-8 video lineage; no gallery ordering.
                media_id = row[0]
                candidate = {'media_id': media_id, 'project_id': row[1], 'status': row[3]}
                try:
                    observed = self.session.media(media_id, 'image')
                    if not observed:
                        raise ValueError('readback unavailable')
                    comparison = image_comparison(source, observed)
                    candidate['comparison'] = comparison
                    if comparison['strong_match']:
                        matches.append(media_id)
                except OwnerAmbiguityGate:
                    raise
                except Exception:
                    candidate['readback'] = 'unresolved'
                    unresolved.append(media_id)
                candidates.append(candidate)
            evidence = {'kind': 'catalog_reference_reconciliation', 'probe': probe + 1,
                'reservation_id': key, 'project_id': self.session.project_id,
                'source_sha256': asset.sha256, 'catalog_ids': sorted(row[0] for row in records),
                'candidates': candidates, 'matches': sorted(matches), 'unresolved': sorted(unresolved)}
            digest = self._evidence(evidence)
            self.store.record_event(key, 'RECONCILE_PROBED', {'evidence_hash': digest,
                'candidate_count': len(candidates), 'match_count': len(matches),
                'unresolved_count': len(unresolved)})
            if len(matches) > 1:
                raise OwnerAmbiguityGate('multiple strong reference media matches')
            unresolved_blocking = [u for u in unresolved
                                   if preexisting_ids is None
                                   or u.lower() not in {p.lower() for p in preexisting_ids}]
            signature = sha256({'catalog_ids': evidence['catalog_ids'],
                'matches': matches, 'unresolved': unresolved,
                'candidate_hashes': [c.get('comparison', {}).get('provider_media_sha256')
                                     for c in candidates]})
            if len(matches) == 1 and not unresolved_blocking and \
                    (stable == signature or self.probes == 1):
                if expected_media_id is not None and matches[0] != expected_media_id:
                    raise OwnerAmbiguityGate('unique reference match disagrees with Owner evidence')
                self.store.record_identified(key, matches[0], method='catalog_strong_match',
                                              evidence_hash=digest)
                return self.verify_identified(asset, self.store.read_progress(key), source)
            stable = signature
            if probe + 1 < self.probes:
                time.sleep(self.interval_s)
        raise OwnerAmbiguityGate('bounded catalog reconciliation unresolved; no re-upload')
