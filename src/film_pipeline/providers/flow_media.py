"""Exact ID/resource/bytes binding for the observed Flow media contract.

Signed URLs are transient. Durable evidence contains only stable identities,
resource paths, metadata and hashes. No gallery or filename is an authority.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .flow_rpc_contract import ContractError, _uuid, _strings

VERSION = 'flow-bound-media-20261001-v1'


def exact_resource(url, media_id, kind):
    if not isinstance(url, str):
        raise ContractError('MEDIA_RESOURCE_INVALID')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'flow-content.google'
            or parsed.path != f'/{kind}/{media_id}' or parsed.fragment):
        raise ContractError('MEDIA_RESOURCE_IDENTITY_MISMATCH')
    return parsed.path


@dataclass(frozen=True, repr=False)
class MediaResource:
    media_id: str
    project_id: str
    kind: str
    byte_size: int
    mime_type: str
    width: int | None
    height: int | None
    url: str = field(repr=False)


@dataclass(frozen=True, repr=False)
class BoundMedia:
    data: bytes = field(repr=False)
    evidence: dict


def parse_media_resource(payload, *, media_id, project_id, kind):
    _uuid(media_id, 'MEDIA_ID_INVALID')
    _uuid(project_id, 'PROJECT_ID_INVALID')
    if kind not in {'image', 'video'}:
        raise ContractError('MEDIA_KIND_INVALID')
    if (not isinstance(payload, list) or len(payload) != (7 if kind == 'image' else 8)
            or payload[0] != media_id or payload[1] != project_id or payload[3] != 'CAE'):
        raise ContractError('MEDIA_RESPONSE_IDENTITY_MISMATCH')
    try:
        size = payload[5][13]
        if type(size) is not int or not 0 < size <= 256 * 1024 * 1024:
            raise ContractError('MEDIA_SIZE_INVALID')
        if kind == 'image':
            url = payload[5][10]
            if payload[6][1][3] != url:
                raise ContractError('MEDIA_IMAGE_RESOURCE_CONFLICT')
            mime = payload[6][1][6]
            if mime not in {'image/jpeg', 'image/png', 'image/webp'}:
                raise ContractError('MEDIA_IMAGE_MIME_UNQUALIFIED')
            dimensions = payload[6][2]
            if (not isinstance(dimensions, list) or len(dimensions) != 2
                    or any(type(v) is not int or not 0 < v <= 16384 for v in dimensions)):
                raise ContractError('MEDIA_DIMENSIONS_INVALID')
            width, height = dimensions
        else:
            url = payload[7][0][8]
            if payload[7][2] != [media_id]:
                raise ContractError('MEDIA_VIDEO_LINEAGE_MISMATCH')
            mime, width, height = 'video/mp4', None, None
        exact_resource(url, media_id, kind)
        # Duplicate occurrences are normal; any different same-kind resource
        # is a conflict, including different signatures for the same path.
        candidates = {s for s in _strings(payload) if s.startswith('https://')
            and urlsplit(s).hostname == 'flow-content.google'
            and urlsplit(s).path.startswith(f'/{kind}/')}
        if candidates != {url}:
            raise ContractError('MEDIA_RESOURCE_CARDINALITY')
    except (IndexError, TypeError, KeyError):
        raise ContractError('MEDIA_RESPONSE_SHAPE_DRIFT') from None
    return MediaResource(media_id, project_id, kind, size, mime, width, height, url)


def bind_media_bytes(resource, *, data, response_url, status, headers):
    path = exact_resource(response_url, resource.media_id, resource.kind)
    if (status != 200 or 'location' in headers or response_url != resource.url
            or headers.get('content-type', '').split(';')[0].lower() != resource.mime_type):
        raise ContractError('MEDIA_DOWNLOAD_RESOURCE_MISMATCH')
    if (not isinstance(data, bytes) or len(data) != resource.byte_size
            or headers.get('content-length') != str(resource.byte_size)
            or headers.get('content-encoding') not in (None, 'identity')):
        raise ContractError('MEDIA_DOWNLOAD_SIZE_MISMATCH')
    if resource.kind == 'image':
        from PIL import Image
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                if (image.size != (resource.width, resource.height)
                        or Image.MIME.get(image.format) != resource.mime_type):
                    raise ValueError()
        except Exception:
            raise ContractError('MEDIA_DECODE_METADATA_MISMATCH') from None
    return BoundMedia(data, {'version': VERSION, 'media_id': resource.media_id,
        'project_id': resource.project_id, 'kind': resource.kind,
        'response_id': resource.media_id, 'response_project_id': resource.project_id,
        'resource_host': 'flow-content.google', 'resource_path': path,
        'response_status': 200, 'redirects': 0,
        'byte_size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
        'mime_type': resource.mime_type, 'width': resource.width, 'height': resource.height})
