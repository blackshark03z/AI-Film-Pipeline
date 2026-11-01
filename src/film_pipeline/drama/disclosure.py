"""Drama AI-content disclosure: visible-label policy + machine-readable marking.

EU AI Act Art. 50 (from 2026-08-02): deployers disclose AI-generated video,
providers mark output machine-readably; fictional work may use a discreet
label but not drop it. Three layers here:

1. ``Disclosure`` -> ``disclosure.json`` (tool, model, date, synthetic
   persons, visible label) with fail-closed ``problems()``.
2. ``embed_metadata``: ffmpeg stream copy (never re-encodes) writing MP4
   metadata tags incl. the IPTC digital source type.
3. ``sign_c2pa`` (optional, ``c2pa-python``): a C2PA manifest binding the
   final bytes. The dev signer is self-issued, so validators report it as
   untrusted; the manifest is still machine-readable.

``disclosure_sha256`` in the tags is the hash of the record with
``content_sha256`` blanked (``record_sha256``), which breaks the circularity
between the file bytes and the record that names them. ``check_release``
gates a release file on all of it.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from pydantic import Field

from ..core import ContractModel

IPTC_TRAINED_ALGORITHMIC_MEDIA = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia")


class GeneratorRecord(ContractModel):
    provider: str
    model: str
    role: str                       # e.g. "video+audio"
    settings: str = ""


class VisibleLabel(ContractModel):
    text: str
    start_s: float
    duration_s: float
    watermark_text: str = ""
    watermark_always_on: bool = False


class Disclosure(ContractModel):
    film_id: str
    title: str
    created: str                    # ISO date
    ai_generated: bool = True
    digital_source_type: str = IPTC_TRAINED_ALGORITHMIC_MEDIA
    generators: list[GeneratorRecord] = Field(default_factory=list)
    post_tools: list[str] = Field(default_factory=list)
    synthetic_persons: bool = True
    synthetic_persons_note: str = ""
    human_contribution: list[str] = Field(default_factory=list)
    visible_label: VisibleLabel
    jurisdiction_notes: list[str] = Field(default_factory=list)
    content_sha256: str = ""        # of the release mp4, set by the writer

    def problems(self) -> list[str]:
        out: list[str] = []
        label = self.visible_label
        if not self.ai_generated:
            out.append("ai_generated must be True (drama films are fully "
                       "generated)")
        if not label.text.strip():
            out.append("visible label text is empty")
        early = label.start_s <= 0.5 and label.duration_s >= 2.0
        if not (early or label.watermark_always_on):
            out.append("visible label must start within 0.5 s and last "
                       ">= 2 s, or the watermark must be always on "
                       f"(start {label.start_s:g} s, "
                       f"duration {label.duration_s:g} s)")
        if not self.generators:
            out.append("no generator recorded")
        return out

    def generator_summary(self) -> str:
        return "; ".join(f"{g.provider} {g.model}" for g in self.generators)


# ------------------------------------------------------------------ hashing

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record_sha256(d: Disclosure) -> str:
    """Hash of the canonical record with ``content_sha256`` blanked."""
    data = d.model_dump(mode="json")
    data["content_sha256"] = ""
    return hashlib.sha256(json.dumps(
        data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def write_disclosure(disclosure: Disclosure, video: Path,
                     out_json: Path) -> Disclosure:
    """Fill ``content_sha256`` from ``video`` and write the JSON."""
    done = disclosure.model_copy(update={"content_sha256": sha256_file(video)})
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(done.model_dump(mode="json"),
                                   sort_keys=True, indent=2,
                                   ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return done


def load_disclosure(path: Path) -> Disclosure:
    return Disclosure.model_validate_json(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- metadata

def _ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams",
         "-of", "json", str(path)], capture_output=True, text=True,
        check=True)
    return json.loads(out.stdout)


def read_metadata(path: Path) -> dict:
    """Container-level metadata tags (as written by ffmpeg) of ``path``."""
    return dict(_ffprobe(path).get("format", {}).get("tags", {}))


def _stream_signature(path: Path) -> list[tuple]:
    return [(s.get("codec_type"), s.get("codec_name"),
             round(float(s.get("duration") or 0), 2))
            for s in _ffprobe(path)["streams"]
            if s.get("codec_type") in ("video", "audio")]


def embed_metadata(src: Path, dst: Path, disclosure: Disclosure) -> Path:
    """Stream-copy ``src`` to ``dst`` with disclosure tags; verified not to
    re-encode (codecs and stream durations must match)."""
    gen = disclosure.generator_summary()
    tags = {
        "comment": f"AI-generated video ({gen}). "
                   + ("Synthetic persons. " if disclosure.synthetic_persons
                      else "") + "See disclosure.json",
        "description": f"{disclosure.title}: fully AI-generated video and "
                       f"audio ({gen}); edit and subtitles by the "
                       "production team. Fictional characters.",
        "ai_generated": "true",
        "digital_source_type": disclosure.digital_source_type,
        "disclosure_sha256": record_sha256(disclosure),
        "generator": gen,
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0",
           "-c", "copy", "-movflags", "+use_metadata_tags+faststart"]
    for k, v in tags.items():
        cmd += ["-metadata", f"{k}={v}"]
    subprocess.run([*cmd, str(dst)], check=True)
    before, after = _stream_signature(src), _stream_signature(dst)
    if before != after:
        raise ValueError(f"stream copy changed streams: {before} -> {after}")
    got = read_metadata(dst)
    missing = [k for k in tags if got.get(k) != tags[k]]
    if missing:
        raise ValueError(f"metadata not read back: {missing}")
    return dst


# --------------------------------------------------------------------- C2PA

def default_dev_cert_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local/share")
    return Path(base) / "film_pipeline" / "c2pa_dev"


def sign_c2pa(src: Path, dst: Path, disclosure: Disclosure, cert_pem: Path,
              key_pem: Path, alg: str = "es256") -> dict:
    """Add a C2PA manifest (created + edited actions, CreativeWork) to a copy
    of ``src``. Needs the ``provenance`` extra. Returns a readback summary."""
    import c2pa
    gen = disclosure.generator_summary()
    manifest = {
        "claim_generator_info": [{"name": "AI Film Pipeline", "version": "0"}],
        "title": disclosure.title,
        "format": "video/mp4",
        "assertions": [
            {"label": "c2pa.actions", "data": {"actions": [
                {"action": "c2pa.created",
                 "digitalSourceType": disclosure.digital_source_type,
                 "softwareAgent": gen},
                {"action": "c2pa.edited",
                 "softwareAgent": ", ".join(disclosure.post_tools),
                 "description": "edit, subtitles, grade, loudness"}]}},
            {"label": "stds.schema-org.CreativeWork", "data": {
                "@context": "https://schema.org", "@type": "CreativeWork",
                "name": disclosure.title,
                "description": "Fully AI-generated fictional short; see "
                               f"disclosure record {record_sha256(disclosure)}",
                "author": [{"@type": "Organization",
                            "name": "production team"}]}},
        ],
    }
    info = c2pa.C2paSignerInfo(alg.lower(), cert_pem.read_bytes(),
                               key_pem.read_bytes(), None)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    with c2pa.Signer.from_info(info) as signer, \
            c2pa.Builder(json.dumps(manifest)) as builder:
        builder.sign_file(src, dst, signer)
    store = read_c2pa(dst)
    if store is None:
        raise ValueError("C2PA manifest not readable after signing")
    return c2pa_summary(store)


def read_c2pa(path: Path) -> dict | None:
    """The C2PA manifest store of ``path`` as a dict, or None."""
    try:
        import c2pa
    except ImportError:
        return None
    try:
        reader = c2pa.Reader.try_create(path)
        if reader is None:
            return None
        with reader:
            return json.loads(reader.json())
    except Exception:
        return None


def c2pa_summary(store: dict) -> dict:
    """Compact view: active manifest, validation state, actions."""
    active = store.get("manifests", {}).get(store.get("active_manifest"), {})
    actions: list[dict] = []
    for a in active.get("assertions", []):
        if a.get("label", "").startswith("c2pa.actions"):
            actions += a.get("data", {}).get("actions", [])
    return {"active_manifest": store.get("active_manifest"),
            "validation_state": store.get("validation_state"),
            "title": active.get("title"),
            "signer": (active.get("signature_info") or {}).get("issuer"),
            "actions": actions,
            "digital_source_types": sorted(
                {a["digitalSourceType"] for a in actions
                 if "digitalSourceType" in a})}


# ------------------------------------------------------------ release gate

def check_release(target, disclosure_json: Path | None = None,
                  base: Path | None = None) -> list[str]:
    """Problems that block a release; empty means disclosure is in order.

    ``target`` is the release mp4 path, or a ``PostManifest`` whose
    ``disclosure`` dict has ``json``/``marked`` paths relative to ``base``.
    """
    if isinstance(target, Path):
        video = target
    else:
        d = getattr(target, "disclosure", None)
        if not d:
            return ["manifest has no disclosure block"]
        base = base or Path(".")
        video = base / d.get("marked", target.final)
        disclosure_json = base / d["json"]
    if not video.is_file():
        return [f"release file missing: {video}"]
    disclosure_json = disclosure_json or video.parent / "disclosure.json"
    if not disclosure_json.is_file():
        return [f"disclosure json missing: {disclosure_json}"]
    out: list[str] = []
    try:
        disc = load_disclosure(disclosure_json)
    except ValueError as e:
        return [f"disclosure json invalid: {e}"]
    out += [f"disclosure: {p}" for p in disc.problems()]
    if disc.content_sha256 != sha256_file(video):
        out.append("disclosure content_sha256 does not match the release "
                   "file")
    tags = read_metadata(video)
    if str(tags.get("ai_generated", "")).lower() != "true":
        out.append("release file lacks ai_generated=true metadata")
    elif tags.get("digital_source_type") != disc.digital_source_type:
        out.append("metadata digital_source_type differs from disclosure")
    if tags.get("disclosure_sha256") not in (None, record_sha256(disc)):
        out.append("metadata disclosure_sha256 does not match the record")
    return out
