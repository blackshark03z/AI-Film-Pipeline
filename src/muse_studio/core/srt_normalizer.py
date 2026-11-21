"""
SRT Screenplay Normalizer & Coverage Gate (Khâu 1 -> Gate 0)
- Đọc hiểu & làm sạch file phụ đề `.srt` dài (tước tag tiếng ồn `[snorts]`, lọc CTA YouTube like/subscribe).
- Đọc bảng phân chương (`chapters.txt`) và phân rã thành khung Narrative Beats tuần tự theo thời gian.
- Kiểm định độ phủ toàn bộ dòng thời gian gốc (`SRT Coverage Gate`): phát hiện thiếu chương, cụt đuôi,
  hoặc thời lượng chuyển thể quá ngắn so với truyện gốc trước khi đưa vào biên dịch / render.
"""

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from .srt_diarizer import SRTCue, parse_srt, parse_timestamp_to_seconds
except ImportError:
    from core.srt_diarizer import SRTCue, parse_srt, parse_timestamp_to_seconds


class SRTNormalizer:
    """Chuẩn hóa SRT dài thành khung Narrative Beats và kiểm định độ phủ 100% câu chuyện."""

    CTA_PHRASES = (
        "hit that like button",
        "drop your answer below",
        "answer it in the comments",
        "like, share, and subscribe",
        "haven't already, subscribe",
    )

    STOPWORDS: Set[str] = {
        "that", "this", "with", "from", "they", "have", "were", "been", "what",
        "when", "where", "which", "will", "your", "just", "there", "their", "about",
        "would", "could", "into", "than", "then", "some", "only", "more", "over",
        "such", "here", "also", "even", "them", "these", "those", "very", "much",
        "said", "like", "back", "down", "didn", "wasn", "couldn", "wouldn",
        "because", "before", "after", "while", "through", "across", "still",
    }

    @staticmethod
    def _format_mmss(seconds: float) -> str:
        seconds = max(0, int(round(seconds)))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    @classmethod
    def parse_chapters_file(
        cls,
        chapters_path: Optional[Path],
        total_duration_s: float,
    ) -> List[Dict[str, Any]]:
        """Phân tích file `chapters.txt` dạng `MM:SS - Title` hoặc chia mặc định mỗi 300s."""
        total_duration_s = max(1.0, float(total_duration_s or 0.0))
        raw_entries: List[Tuple[float, str]] = []

        if chapters_path and Path(chapters_path).exists():
            txt = Path(chapters_path).read_text(encoding="utf-8-sig", errors="ignore")
            pat = re.compile(r"^\s*((?:\d{1,2}:)?\d{1,2}:\d{2})\s*[-–|]\s*(.+?)\s*$")
            for line in txt.splitlines():
                m = pat.match(line)
                if not m:
                    continue
                sec = parse_timestamp_to_seconds(m.group(1))
                title = m.group(2).strip()
                raw_entries.append((sec, title))

        if not raw_entries:
            n_bins = max(1, math.ceil(total_duration_s / 300.0))
            chapters = []
            for idx in range(1, n_bins + 1):
                s0 = (idx - 1) * 300.0
                s1 = min(total_duration_s, idx * 300.0)
                if s1 <= s0 and idx > 1:
                    break
                chapters.append({
                    "chapter_id": f"CH{idx:02d}",
                    "index": idx,
                    "title": f"Section {idx}",
                    "start_s": round(s0, 2),
                    "end_s": round(max(s0 + 1.0, s1), 2),
                })
            return chapters

        raw_entries.sort(key=lambda x: x[0])
        chapters = []
        for idx, (s0, title) in enumerate(raw_entries, start=1):
            s1 = raw_entries[idx][0] if idx < len(raw_entries) else total_duration_s
            s1 = max(s0 + 1.0, s1)
            chapters.append({
                "chapter_id": f"CH{idx:02d}",
                "index": idx,
                "title": title,
                "start_s": round(s0, 2),
                "end_s": round(s1, 2),
            })
        return chapters

    @classmethod
    def clean_srt_cues(cls, cues: List[SRTCue], strip_youtube_cta: bool = True) -> List[SRTCue]:
        """Làm sạch cue SRT: bỏ tag `[snorts]`, lọc câu CTA YouTube và gộp trùng liên tiếp."""
        cleaned: List[SRTCue] = []
        prev_norm = ""

        for c in cues:
            txt = re.sub(r"\[[^\]]*\]", " ", c.text or "")
            txt = txt.replace(">>", " ")
            txt = re.sub(r"\s+", " ", txt).strip()
            if not txt:
                continue

            if strip_youtube_cta:
                # Lọc theo từng câu để giữ nguyên câu truyện nếu CTA nằm lẫn trong cùng cue
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", txt) if s.strip()]
                kept_sents = [
                    s for s in sentences
                    if not any(ph in s.lower() for ph in cls.CTA_PHRASES)
                ]
                txt = " ".join(kept_sents).strip()
                if not txt or any(ph in txt.lower() for ph in cls.CTA_PHRASES):
                    continue

            norm_key = txt.lower()
            if norm_key == prev_norm:
                continue
            prev_norm = norm_key
            cleaned.append(SRTCue(index=c.index, start_s=c.start_s, end_s=c.end_s, text=txt))

        return cleaned

    @classmethod
    def normalize_srt_to_beats_skeleton(
        cls,
        srt_path: Path,
        chapters_path: Optional[Path] = None,
        window_s: float = 22.0,
    ) -> Dict[str, Any]:
        """Phân rã SRT dài thành các khung Narrative Beat có gắn source_start_s / source_end_s."""
        raw_cues = parse_srt(Path(srt_path))
        cleaned = cls.clean_srt_cues(raw_cues, strip_youtube_cta=True)
        source_duration_s = max((c.end_s for c in raw_cues), default=0.0)
        story_end_s = max((c.end_s for c in cleaned), default=source_duration_s)
        chapters = cls.parse_chapters_file(chapters_path, total_duration_s=story_end_s or source_duration_s)

        beats: List[Dict[str, Any]] = []
        beat_idx = 1

        for ch in chapters:
            ch_cues = [c for c in cleaned if ch["start_s"] - 0.1 <= c.start_s < ch["end_s"]]
            if not ch_cues:
                continue

            cur_texts: List[str] = []
            cur_start = ch_cues[0].start_s
            cur_end = ch_cues[0].end_s

            def _flush() -> None:
                nonlocal beat_idx, cur_texts
                if not cur_texts:
                    return
                raw_text = re.sub(r"\s+", " ", " ".join(cur_texts)).strip()
                beats.append({
                    "beat_id": f"B{beat_idx:03d}",
                    "order": beat_idx,
                    "chapter_id": ch["chapter_id"],
                    "chapter_title": ch["title"],
                    "source_start_s": round(cur_start, 2),
                    "source_end_s": round(cur_end, 2),
                    "source_reference": f"SRT {cls._format_mmss(cur_start)} -> {cls._format_mmss(cur_end)}",
                    "raw_text": raw_text,
                    "has_dialogue_hint": ('"' in raw_text or "?" in raw_text),
                })
                beat_idx += 1
                cur_texts = []

            for c in ch_cues:
                if cur_texts and (c.start_s - cur_start >= window_s) and cur_texts[-1].endswith((".", "!", "?", '"')):
                    _flush()
                    cur_start = c.start_s
                cur_texts.append(c.text)
                cur_end = max(cur_end, c.end_s)

            _flush()

        return {
            "source_type": "srt",
            "source_duration_s": round(source_duration_s, 2),
            "story_end_s": round(story_end_s, 2),
            "total_beats": len(beats),
            "chapters": chapters,
            "beats": beats,
        }

    @classmethod
    def _extract_content_words(cls, text: str) -> Set[str]:
        tokens = re.findall(r"[a-z0-9]{4,}", (text or "").lower())
        return {t for t in tokens if t not in cls.STOPWORDS}

    @classmethod
    def _resolve_item_span(
        cls,
        item: Dict[str, Any],
        srt_buckets: Dict[int, Set[str]],
        story_end_s: float,
    ) -> Optional[Tuple[float, float]]:
        if item.get("source_start_s") is not None:
            s0 = float(item["source_start_s"])
            s1 = float(item["source_end_s"]) if item.get("source_end_s") is not None else (s0 + 15.0)
            return s0, max(s0 + 1.0, s1)

        src_ref = str(item.get("source_reference") or "")
        if src_ref:
            ts_matches = re.findall(r"(?:\d{1,2}:)?\d{1,2}:\d{2}", src_ref)
            if ts_matches:
                parsed = [parse_timestamp_to_seconds(t) for t in ts_matches]
                s0 = parsed[0]
                s1 = parsed[-1] if len(parsed) > 1 and parsed[-1] > s0 else (s0 + 15.0)
                return s0, s1

        text = " ".join(
            str(item.get(k) or "")
            for k in ("action_summary", "dialogue", "narration", "voiceover_text", "raw_text")
        )
        bwords = cls._extract_content_words(text)
        if len(bwords) < 2 or not srt_buckets:
            return None

        best_bucket = -1
        best_overlap = 0
        for b_idx, words in srt_buckets.items():
            ov = len(bwords & words)
            if ov > best_overlap:
                best_overlap = ov
                best_bucket = b_idx

        if best_overlap >= 2 and best_bucket >= 0:
            s0 = best_bucket * 15.0
            s1 = min(max(s0 + 1.0, story_end_s), (best_bucket + 1) * 15.0)
            return s0, s1
        return None

    @classmethod
    def audit_srt_coverage(
        cls,
        srt_path: Path,
        beats_or_manifest: Any,
        chapters_path: Optional[Path] = None,
        min_duration_ratio: float = 0.28,
        max_uncovered_tail_s: float = 90.0,
        min_chapter_beats: int = 2,
    ) -> Dict[str, Any]:
        """
        Kiểm định 3 cổng HARD cho kịch bản/manifest chuyển thể từ SRT:
        1. UNCOVERED_SRT_TAIL: Không được bỏ sót phần cuối truyện gốc.
        2. UNCOVERED_SRT_CHAPTER: Mỗi chương gốc >= 45s phải có đủ beat bao phủ.
        3. ADAPTATION_TOO_SHORT: Với truyện >= 10 phút, thời lượng dự kiến sau trim phải đạt >= min_duration_ratio.
        """
        raw_cues = parse_srt(Path(srt_path))
        cleaned = cls.clean_srt_cues(raw_cues, strip_youtube_cta=True)
        source_duration_s = max((c.end_s for c in raw_cues), default=0.0)
        story_end_s = max((c.end_s for c in cleaned), default=source_duration_s)
        chapters = cls.parse_chapters_file(chapters_path, total_duration_s=story_end_s or source_duration_s)

        if isinstance(beats_or_manifest, list):
            items = beats_or_manifest
        elif isinstance(beats_or_manifest, dict):
            items = beats_or_manifest.get("shots") or beats_or_manifest.get("beats") or []
        else:
            items = []

        # Lập bucket từ khóa mỗi 15 giây để đối chiếu trường hợp beat không ghi source_start_s
        srt_buckets: Dict[int, Set[str]] = {}
        for c in cleaned:
            b_idx = int(c.start_s // 15.0)
            srt_buckets.setdefault(b_idx, set()).update(cls._extract_content_words(c.text))

        spans: List[Tuple[float, float]] = []
        unresolved = 0
        estimated_adapted_s = 0.0

        for it in items:
            if not isinstance(it, dict):
                continue
            trim_est = it.get("target_trim_duration_s")
            if trim_est is None:
                dur_raw = float(it.get("duration_s", 10.0))
                trim_est = 7.2 if dur_raw >= 8.0 else 3.5
            estimated_adapted_s += float(trim_est)

            if it.get("cutaway_type") and (it.get("staging") or {}).get("kind") != "source_action":
                continue
            sp = cls._resolve_item_span(it, srt_buckets, story_end_s)
            if sp:
                spans.append(sp)
            else:
                unresolved += 1

        max_covered_end_s = max((s1 for _, s1 in spans), default=0.0)
        errors: List[str] = []
        warnings: List[str] = []

        if story_end_s > max_uncovered_tail_s and max_covered_end_s < (story_end_s - max_uncovered_tail_s):
            errors.append(
                f"UNCOVERED_SRT_TAIL: Dòng thời gian chuyển thể mới phủ tới {cls._format_mmss(max_covered_end_s)} "
                f"trong khi truyện gốc kết thúc ở {cls._format_mmss(story_end_s)} (bỏ sót {story_end_s - max_covered_end_s:.0f}s cuối)."
            )

        chapter_coverage: List[Dict[str, Any]] = []
        for ch in chapters:
            ch_start, ch_end = ch["start_s"], ch["end_s"]
            ch_dur = max(0.0, ch_end - ch_start)
            matched_cnt = sum(1 for s0, s1 in spans if s0 < ch_end and s1 > ch_start)
            req_beats = max(min_chapter_beats, int(ch_dur // 120)) if ch_dur >= 240.0 else min_chapter_beats
            ch_ok = (ch_dur < 45.0) or (matched_cnt >= req_beats)
            chapter_coverage.append({
                "chapter_id": ch["chapter_id"],
                "title": ch["title"],
                "start_s": ch_start,
                "end_s": ch_end,
                "matched_beats": matched_cnt,
                "required_beats": req_beats if ch_dur >= 45.0 else 0,
                "covered": ch_ok,
            })
            if not ch_ok:
                errors.append(
                    f"UNCOVERED_SRT_CHAPTER: {ch['chapter_id']} ({ch['title']}, "
                    f"{cls._format_mmss(ch_start)}-{cls._format_mmss(ch_end)}) chỉ có {matched_cnt}/{req_beats} beats."
                )

        if story_end_s >= 600.0 and estimated_adapted_s < story_end_s * min_duration_ratio:
            req_min = (story_end_s * min_duration_ratio) / 60.0
            errors.append(
                f"ADAPTATION_TOO_SHORT: Thời lượng chuyển thể dự kiến {estimated_adapted_s / 60.0:.2f} phút "
                f"< tối thiểu {req_min:.2f} phút (ratio {estimated_adapted_s / max(1.0, story_end_s):.2f} < {min_duration_ratio:.2f})."
            )

        if unresolved > max(3, int(len(items) * 0.35)):
            warnings.append(f"Có {unresolved}/{len(items)} beat thiếu timestamp nguồn `source_start_s`/`source_reference`.")

        coverage_pct = round(min(100.0, (max_covered_end_s / max(1.0, story_end_s)) * 100.0), 1)
        return {
            "passed": len(errors) == 0,
            "source_duration_s": round(source_duration_s, 2),
            "story_end_s": round(story_end_s, 2),
            "max_covered_end_s": round(max_covered_end_s, 2),
            "coverage_pct": coverage_pct,
            "total_items": len(items),
            "estimated_adapted_s": round(estimated_adapted_s, 2),
            "estimated_adapted_min": round(estimated_adapted_s / 60.0, 2),
            "chapter_coverage": chapter_coverage,
            "errors": errors,
            "warnings": warnings,
        }
