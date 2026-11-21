"""
Keyframe Composer & Image Verification (Khâu 2.5)
Chuẩn hóa thư mục `assets/{anchors,setups,keyframes}` trong từng dự án:
- Phát hiện và sinh bổ sung các Character Anchor còn thiếu (ví dụ vai phụ trùng ảnh).
- Sinh bộ Keyframe `00.png` đa góc theo đúng từng bối cảnh + trạng thái đạo cụ qua `HeadlessMuseClient`.
- Tiền kiểm tự động ảnh 16:9, độ tương phản (entropy), chống dải phụ đề đen/chữ rác chìm,
  và xuất `keyframes_contact_sheet.jpg` để Gemini Agent duyệt thị giác trước khi render video.
"""

import json
import re
import secrets
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageStat

try:
    from .batch_packager import BatchPackager, KeyframeItem
    from .staging import require_current_staging
    from .headless_muse_client import (
        BlockedException,
        GenerationFailedException,
        HeadlessMuseClient,
        QuotaExceededException,
        SessionInvalidException,
    )
except ImportError:
    from core.batch_packager import BatchPackager, KeyframeItem
    from core.staging import require_current_staging
    from core.headless_muse_client import (
        BlockedException,
        GenerationFailedException,
        HeadlessMuseClient,
        QuotaExceededException,
        SessionInvalidException,
    )


class KeyframeComposer:
    """Quản lý sinh, kiểm định và lập chỉ mục bộ Keyframe `00.png` theo từng bối cảnh."""

    TURNAROUND_PROMPTS = {
        "three_quarter": (
            "16:9 cinematic medium portrait, 45-degree three-quarter view, looking slightly off-camera, "
            "preserving the exact face, hair, and wardrobe of Image 1."
        ),
        "full_body": (
            "16:9 cinematic wide full-body shot, head to toe visible, "
            "matching the exact wardrobe, build, and facial features of Image 1."
        ),
    }

    @staticmethod
    def _anchor_path(raw: str, anchors_dir: Path) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else anchors_dir / path.name

    @classmethod
    def _turnaround_slots(cls, bible: Dict[str, Any], anchors_dir: Path):
        for char in bible.get("characters", []):
            if not char.get("anchor_image"):
                continue
            anchor = cls._anchor_path(char["anchor_image"], anchors_dir)
            if not anchor.is_file():
                continue
            refs = char.get("turnaround_images") or {}
            for angle, prompt in cls.TURNAROUND_PROMPTS.items():
                target = anchors_dir / f"{anchor.stem}__{angle}.png"
                configured = refs.get(angle) if isinstance(refs, dict) else None
                if configured and cls._anchor_path(configured, anchors_dir).is_file():
                    continue
                yield char, angle, anchor, target, prompt

    @classmethod
    def plan_missing_character_turnarounds(
        cls, bible: Dict[str, Any], anchors_dir: Path
    ) -> List[KeyframeItem]:
        items = {}
        for _, _, anchor, target, prompt in cls._turnaround_slots(bible, Path(anchors_dir)):
            if target.stem in items or (target.is_file() and cls.verify_keyframe_image(target)[0]):
                continue
            items[target.stem] = KeyframeItem(
                kf_id=target.stem,
                prompt=f"{prompt} No text, subtitles, logos, or watermarks.",
                reference_images=[anchor],
                aspect_ratio="16:9",
                output_format="png",
            )
        return list(items.values())

    @classmethod
    def save_character_turnarounds(
        cls,
        bible_path: Path,
        bible: Dict[str, Any],
        anchors_dir: Path,
        planned: List[KeyframeItem],
        results: Iterable[Dict[str, Any]],
        report: Dict[str, Any],
    ) -> None:
        # Deferred import because the orchestrator also uses KeyframeComposer.
        try:
            from .autoprod_orchestrator import _write_json_atomic
        except ImportError:
            from core.autoprod_orchestrator import _write_json_atomic

        returned = {}
        for result in results:
            returned.update(result.get("keyframes", {}))

        for item in planned:
            info = returned.get(item.kf_id)
            if not info:
                report["rejected"].append({"id": item.kf_id, "errors": ["MISSING_TURNAROUND_RESULT"]})
                continue
            source = Path(info["path"])
            ok, errors, _ = cls.verify_keyframe_image(source)
            if not ok:
                report["rejected"].append({"id": item.kf_id, "errors": errors})
                continue
            target = anchors_dir / f"{item.kf_id}.png"
            target.write_bytes(source.read_bytes())
            report["turnarounds_generated"].append(str(target))

        changed = False
        for char, angle, _, target, _ in cls._turnaround_slots(bible, anchors_dir):
            if target.is_file() and cls.verify_keyframe_image(target)[0]:
                if not isinstance(char.get("turnaround_images"), dict):
                    char["turnaround_images"] = {}
                char["turnaround_images"][angle] = target.name
                changed = True
        if changed:
            _write_json_atomic(bible_path, bible)

    @staticmethod
    def ensure_asset_dirs(project_dir: Path) -> Dict[str, Path]:
        project_dir = Path(project_dir)
        dirs = {
            "anchors": project_dir / "assets" / "anchors",
            "setups": project_dir / "assets" / "setups",
            "keyframes": project_dir / "assets" / "keyframes",
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    @staticmethod
    def verify_keyframe_image(img_path: Path) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Kiểm tra kỹ thuật & độ sạch chữ/sub trên một ảnh keyframe `00.png`."""
        img_path = Path(img_path)
        errors: List[str] = []
        metrics: Dict[str, Any] = {}

        if not img_path.exists():
            return False, [f"MISSING_FILE: {img_path}"], metrics
        size_b = img_path.stat().st_size
        metrics["size_bytes"] = size_b
        if size_b < BatchPackager.MIN_IMAGE_BYTES:
            errors.append(f"TINY_IMAGE: Dung lượng {size_b} bytes < 5KB")

        try:
            with Image.open(img_path) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                metrics["width"] = w
                metrics["height"] = h
                aspect = w / max(1, h)
                metrics["aspect"] = round(aspect, 3)

                if abs(aspect - (16.0 / 9.0)) > 0.08:
                    errors.append(f"BAD_ASPECT_RATIO: {w}x{h} (không đạt chuẩn 16:9)")

                gray = rgb.convert("L")
                stat = ImageStat.Stat(gray)
                stddev = float(stat.stddev[0])
                mean_luma = float(stat.mean[0])
                metrics["luma_mean"] = round(mean_luma, 2)
                metrics["luma_stddev"] = round(stddev, 2)

                if stddev < 5.0:
                    errors.append(f"FLAT_IMAGE: Ảnh phẳng/đơn sắc (stddev={stddev:.2f} < 5.0)")

                # Kiểm tra dải đen letterbox hoặc vùng chữ phụ đề sáng chói ở 16% đáy ảnh
                arr = np.asarray(gray, dtype=np.float32)
                top_strip = arr[: max(1, int(h * 0.08)), :]
                bot_strip = arr[int(h * 0.84) :, :]

                if float(top_strip.mean()) < 4.0 and float(top_strip.std()) < 2.0 and float(bot_strip.mean()) < 4.0 and float(bot_strip.std()) < 2.0:
                    errors.append("LETTERBOX_DETECTED: Phát hiện dải đen letterbox trên/dưới")

                # Quét phát hiện khối chữ trắng viền đen đặc trưng của hardsub ở vùng dưới
                # (pixel rất sáng > 240 xen kẽ pixel tối < 25 có gradient ngang dày đặc)
                sub_band = arr[int(h * 0.80) : int(h * 0.96), int(w * 0.12) : int(w * 0.88)]
                if sub_band.size > 0:
                    bright_ratio = float(np.mean(sub_band > 242))
                    dark_ratio = float(np.mean(sub_band < 20))
                    dx = np.abs(np.diff(sub_band, axis=1))
                    sharp_edges = float(np.mean(dx > 95))
                    metrics["sub_band_bright"] = round(bright_ratio, 4)
                    metrics["sub_band_edges"] = round(sharp_edges, 4)
                    if bright_ratio > 0.03 and dark_ratio > 0.05 and sharp_edges > 0.045:
                        errors.append("SUSPECTED_HARDSUB_TEXT: Vùng đáy ảnh có mật độ cạnh tương phản giống phụ đề cứng")
        except Exception as e:
            errors.append(f"CORRUPT_IMAGE: {e}")

        return len(errors) == 0, errors, metrics

    @classmethod
    def plan_missing_character_anchors(
        cls,
        bible: Dict[str, Any],
        anchors_dir: Path
    ) -> List[KeyframeItem]:
        """Lập danh sách các Character Anchor còn thiếu file trên đĩa."""
        items: List[KeyframeItem] = []
        visual_style = bible.get("world_rules", {}).get(
            "visual_style",
            "cinematic photorealistic 35mm film, realistic lighting"
        )

        for ch in bible.get("characters", []):
            anchor_raw = ch.get("anchor_image")
            if not anchor_raw:
                continue
            target_path = cls._anchor_path(anchor_raw, anchors_dir)
            if target_path.is_file() and target_path.stat().st_size >= BatchPackager.MIN_IMAGE_BYTES:
                continue

            gaze = ch.get("axis_gaze", "looking screen-right")
            anchor_setting = ch.get("anchor_setting") or "neutral realistic interior background softly blurred"
            prompt = (
                f"16:9 cinematic medium close-up portrait film still, {visual_style}. "
                f"Subject: {ch.get('look_verbatim', ch.get('name'))}. "
                f"Composition: {gaze}, eyes clearly open and attentive, {anchor_setting}, "
                f"natural lighting, crisp facial details, five distinct fingers if hands visible. "
                f"No text, no labels, no subtitles, no watermarks, nobody looking directly into the camera lens."
            )
            items.append(
                KeyframeItem(
                    kf_id=target_path.stem,
                    prompt=prompt,
                    reference_images=[],
                    aspect_ratio="16:9",
                    output_format="png",
                )
            )
        return items

    @classmethod
    def plan_missing_location_plates(
        cls,
        bible: Dict[str, Any],
        setups_dir: Path
    ) -> List[KeyframeItem]:
        """Lập danh sách Master Location Plates 16:9 trống không người (`<loc_id>__master_plate.png`) còn thiếu."""
        setups_dir = Path(setups_dir)
        setups_dir.mkdir(parents=True, exist_ok=True)
        items: List[KeyframeItem] = []
        visual_style = bible.get("world_rules", {}).get(
            "visual_style",
            "cinematic photorealistic 35mm film, realistic lighting"
        )

        for loc in bible.get("locations", []):
            loc_id = loc.get("id")
            if not loc_id:
                continue
            target_path = setups_dir / f"{loc_id}__master_plate.png"
            if target_path.exists() and target_path.stat().st_size >= BatchPackager.MIN_IMAGE_BYTES:
                continue

            loc_name = loc.get("name", loc_id)
            loc_desc = loc.get("look_verbatim") or loc_name
            set_facts = loc.get("set_facts") or []
            set_str = ("Set layout lock: " + "; ".join(set_facts) + ".") if set_facts else ""
            lighting = (loc.get("lighting_mood") or "").strip()
            lighting_str = f"Lighting: {lighting.rstrip('.')}." if lighting else ""

            prompt = (
                f"16:9 widescreen architectural master location plate, empty set with zero people, "
                f"no characters in frame, {visual_style}. "
                f"Setting ({loc_name}): {loc_desc}. {set_str} {lighting_str} "
                f"Establishing architectural perspective, consistent room geometry, natural depth and textures. "
                f"Strictly NO people, NO silhouettes, NO text, NO labels, NO subtitles, NO watermarks, NO logos."
            )
            prompt = re.sub(r"\s+", " ", prompt).strip()
            items.append(
                KeyframeItem(
                    kf_id=f"{loc_id}__master_plate",
                    prompt=prompt,
                    reference_images=[],
                    aspect_ratio="16:9",
                    output_format="png",
                )
            )
        return items

    @staticmethod
    def _resolve_character_ref(
        char_info: Optional[Dict[str, Any]],
        framing: str,
        anchors_dir: Path
    ) -> Optional[Path]:
        if not char_info:
            return None
        f_low = (framing or "").lower()
        turnaround = char_info.get("turnaround_images") or {}
        preferred_key: Optional[str] = None
        if isinstance(turnaround, dict) and turnaround:
            if "profile" in f_low:
                preferred_key = "profile"
            elif "ots" in f_low or "over-the-shoulder" in f_low or "over the shoulder" in f_low:
                preferred_key = "three_quarter"
            elif "wide" in f_low:
                preferred_key = "full_body"
            elif "three-quarter" in f_low or "three quarter" in f_low:
                preferred_key = "three_quarter"

            if preferred_key and turnaround.get(preferred_key):
                tp = KeyframeComposer._anchor_path(turnaround[preferred_key], anchors_dir)
                if tp.is_file():
                    return tp

        anchor_raw = char_info.get("anchor_image")
        if anchor_raw:
            ap = KeyframeComposer._anchor_path(anchor_raw, anchors_dir)
            if ap.is_file():
                return ap
        return None

    @classmethod
    def plan_missing_scene_keyframes(
        cls,
        bible: Dict[str, Any],
        manifest: Dict[str, Any],
        project_dir: Path
    ) -> List[KeyframeItem]:
        """
        Gom các shot theo `keyframe_key` (bối cảnh + cỡ cảnh + nhân vật + trạng thái đạo cụ)
        để sinh các Keyframe `00.png` đúng bối cảnh còn thiếu.
        """
        dirs = cls.ensure_asset_dirs(project_dir)
        anchors_dir = dirs["anchors"]
        setups_dir = dirs["setups"]
        kf_dir = dirs["keyframes"]

        char_map = {c["id"]: c for c in bible.get("characters", [])}
        loc_map = {loc["id"]: loc for loc in bible.get("locations", [])}
        visual_style = bible.get("world_rules", {}).get(
            "visual_style",
            "cinematic photorealistic 35mm film, realistic lighting"
        )

        kf_index_path = kf_dir / "keyframes_index.json"
        existing_index: Dict[str, str] = (
            json.loads(kf_index_path.read_text(encoding="utf-8")) if kf_index_path.exists() else {}
        )

        require_current_staging(manifest)
        planned: Dict[str, KeyframeItem] = {}
        for shot in manifest.get("shots", []):
            kf_key = shot.get("keyframe_key")
            if not kf_key:
                continue
            target_file = kf_dir / f"{kf_key}.png"
            if target_file.exists() and target_file.stat().st_size >= BatchPackager.MIN_IMAGE_BYTES:
                existing_index[kf_key] = str(target_file)
                continue
            mapped = existing_index.get(kf_key)
            if mapped and Path(mapped).exists() and Path(mapped).stat().st_size >= BatchPackager.MIN_IMAGE_BYTES:
                continue
            if kf_key in planned:
                continue

            loc_id = shot.get("location")
            loc_info = loc_map.get(loc_id, {})
            loc_desc = loc_info.get("look_verbatim", "realistic airport interior")
            set_facts = loc_info.get("set_facts", [])
            set_str = ("Layout: " + "; ".join(set_facts) + ".") if set_facts else ""

            chars_present = shot.get("characters_present") or []
            primary_cid = shot.get("primary_character_id")
            primary_char = char_map.get(primary_cid, {})
            framing = shot.get("framing", "Medium Shot")
            gaze = shot.get("gaze", "looking screen-right")
            chapter_id = str(shot.get("chapter_id") or "CH01")
            wardrobe = (shot.get("wardrobe_resolved") or shot.get("wardrobe_override") or "").strip()
            if not wardrobe and isinstance(primary_char.get("wardrobe_by_chapter"), dict):
                wardrobe = str(primary_char["wardrobe_by_chapter"].get(chapter_id) or "").strip()

            is_prop_insert = shot.get("cutaway_type") == "prop_insert"
            stage = shot.get("staging") or {}
            state_insert = stage.get("kind") == "state_insert"
            source_action = stage.get("kind") == "source_action"
            hand_appearance_ref = None
            refs: List[Path] = []
            if is_prop_insert and not state_insert:
                hand_appearance_ref = cls._resolve_character_ref(primary_char, "", anchors_dir)
                if hand_appearance_ref:
                    refs.append(hand_appearance_ref)
            else:
                for cid in chars_present[:2]:
                    c_info = char_map.get(cid)
                    cp = cls._resolve_character_ref(c_info, framing, anchors_dir)
                    if cp and cp not in refs:
                        refs.append(cp)
                if not refs:
                    cp = cls._resolve_character_ref(primary_char, framing, anchors_dir)
                    if cp:
                        refs.append(cp)

            if loc_id:
                plate_path = setups_dir / f"{loc_id}__master_plate.png"
                if plate_path.exists() and plate_path.stat().st_size >= BatchPackager.MIN_IMAGE_BYTES:
                    if plate_path not in refs:
                        refs.append(plate_path)

            char_look = primary_char.get("look_verbatim", "")
            if wardrobe:
                char_look = f"{char_look.rstrip('.')}. Current scene wardrobe: {wardrobe.rstrip('.')}."

            scene_context = f"Scene context: {shot.get('action_summary', '')}"
            if state_insert:
                subject_desc = f"Macro detail of {stage['prop_description']}. Keep all people, hands and faces out of frame."
                scene_context = f"Show the established state: {stage['state']}."
            elif is_prop_insert:
                hand_reference_note = (
                    "Use Image 1 only to match the hand's skin tone and the sleeve. "
                    if hand_appearance_ref else ""
                )
                subject_desc = (
                    "Table-level macro of only the prop, a single hand and its sleeve. All faces stay out of frame. "
                    f"{hand_reference_note}"
                    f"Match only the hand's skin tone and the sleeve from this cast description: {char_look} "
                )
                if source_action:
                    scene_context = (
                        f"{shot.get('prop_continuity', '')} Opening state: {stage['before_state']}. "
                        "Show the instant before the scripted action starts."
                    )
                else:
                    scene_context = (
                        f"{shot.get('prop_continuity', '')} "
                        "Opening frame, before any contact. The prop lies flat and fully visible on the tabletop. "
                        "The fingertips hover at least 5 cm above it. Show a clear, unbroken air gap between "
                        "every fingertip and the prop, visible from the side. The hand touches neither the prop nor the table."
                    )
            elif shot.get("is_multi_person") and len(chars_present) >= 2:
                c1 = char_map.get(chars_present[0], {})
                c2 = char_map.get(chars_present[1], {})
                c1_look = c1.get("look_verbatim", "")
                if chars_present[0] == primary_cid and wardrobe:
                    c1_look = char_look
                subject_desc = (
                    f"Two characters in frame facing each other across the space: "
                    f"Screen-left: {c1_look} ({c1.get('axis_gaze', 'looking screen-right')}). "
                    f"Screen-right: {c2.get('look_verbatim', '')} ({c2.get('axis_gaze', 'looking screen-left')})."
                )
                # The video prompt holds the authored opening state, so the first frame must show it too.
                opening = shot.get("opening_state")
                if opening:
                    subject_desc += f" Opening state: {opening.rstrip('.')}."
            else:
                # The authored opening state of the beat wins over the generic neutral pose.
                opening = shot.get("opening_state")
                pose = f"{gaze}. Opening state: {opening.rstrip('.')}." if opening else (
                    f"{gaze}, eyes open, mouth closed, natural expressive composure."
                )
                subject_desc = (
                    f"Single character matching the reference image exactly: {char_look}. "
                    f"Pose & gaze: {pose}"
                )

            kf_cinema_notes: List[str] = []
            if shot.get("lens_mm"):
                kf_cinema_notes.append(f"Shot on {shot['lens_mm']}mm cinema lens.")
            if shot.get("camera_angle"):
                kf_cinema_notes.append(f"Camera angle: {shot['camera_angle']}.")
            if shot.get("foreground_element"):
                kf_cinema_notes.append(f"Foreground depth: {shot['foreground_element']}.")
            if shot.get("lighting_mood"):
                kf_cinema_notes.append(f"Lighting: {str(shot['lighting_mood']).rstrip('.')}.")
            elif shot.get("is_flashback"):
                kf_cinema_notes.append("Lighting: warm nostalgic golden-hour flashback tones.")
            kf_cinema_str = " ".join(kf_cinema_notes)
            anatomy_note = "" if state_insert else "Five distinct fingers on visible hands, no extra fingers. "

            prompt = (
                f"16:9 widescreen cinematic film still, {framing}, {visual_style}. {kf_cinema_str} "
                f"Setting: {loc_desc}. {set_str} "
                f"{subject_desc} "
                f"{scene_context} "
                f"{anatomy_note}Realistic lighting matching the environment. "
                f"Strictly NO text, NO subtitles, NO captions, NO watermarks, NO logos, nobody looks into the lens."
            )
            prompt = re.sub(r"\s+", " ", prompt).strip()

            planned[kf_key] = KeyframeItem(
                kf_id=kf_key,
                prompt=prompt,
                reference_images=refs,
                aspect_ratio="16:9",
                output_format="png",
            )

        if existing_index:
            kf_index_path.write_text(json.dumps(existing_index, indent=2, ensure_ascii=False), encoding="utf-8")

        return list(planned.values())

    @staticmethod
    def build_contact_sheet(
        image_paths: List[Path],
        output_path: Path,
        cols: int = 4,
        thumb_size: Tuple[int, int] = (480, 270)
    ) -> Optional[Path]:
        """Ghép lưới ảnh Contact Sheet kèm nhãn để Agent duyệt trực quan bằng `read_file`."""
        valid = [Path(p) for p in image_paths if Path(p).exists()]
        if not valid:
            return None

        rows = (len(valid) + cols - 1) // cols
        tw, th = thumb_size
        label_h = 34
        sheet = Image.new("RGB", (cols * tw, rows * (th + label_h)), (18, 22, 30))
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            font = ImageFont.load_default()

        for idx, img_p in enumerate(valid):
            r = idx // cols
            c = idx % cols
            x = c * tw
            y = r * (th + label_h)
            try:
                with Image.open(img_p) as im:
                    thumb = im.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
                sheet.paste(thumb, (x, y))
            except Exception:
                draw.rectangle([x, y, x + tw, y + th], fill=(80, 20, 20))

            draw.rectangle([x, y + th, x + tw, y + th + label_h], fill=(28, 34, 48))
            label = img_p.stem[:52]
            draw.text((x + 8, y + th + 8), label, fill=(235, 240, 248), font=font)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path, quality=92)
        return output_path

    @staticmethod
    async def _dispatch_kf_batch_with_failover(
        client: HeadlessMuseClient,
        account_ids: List[str],
        start_offset: int,
        chunk: List[KeyframeItem],
        batch_id: str,
        out_dir: Path,
        simulate: bool,
    ) -> Dict[str, Any]:
        """Sắp xếp tài khoản theo hạn mức còn lại và tự failover sang acc kế nếu gặp lỗi/cạn quota."""
        def _rem_pct(aid: str) -> float:
            from .account_manager import AccountManager
            return AccountManager.get_effective_quota_pct(client.account_manager.get_account(aid))

        ordered = sorted(account_ids, key=_rem_pct, reverse=True)
        if ordered and start_offset:
            rot = start_offset % len(ordered)
            ordered = ordered[rot:] + ordered[:rot]

        last_err: Optional[Exception] = None
        for aid in ordered:
            try:
                return await client.generate_keyframes_batch(
                    account_id=aid,
                    keyframes=chunk,
                    batch_id=batch_id,
                    output_dir=out_dir,
                    simulate=simulate,
                )
            except BlockedException as e:
                # CAPTCHA / verification: stop all sending, never fail over. The caller records the halt.
                e.account_id, e.batch_id = aid, batch_id
                raise
            except (QuotaExceededException, SessionInvalidException, GenerationFailedException) as e:
                if getattr(e, "submitted", False):
                    raise  # reached Muse: never resend it on another account
                last_err = e
                continue
        if last_err is not None:
            raise last_err
        raise ValueError("Không còn tài khoản READY để sinh Keyframe")

    @classmethod
    async def generate_and_verify_keyframes(
        cls,
        project_dir: Path,
        account_ids: List[str],
        client: HeadlessMuseClient,
        simulate: bool = False,
        include_setups: bool = False,
        include_turnarounds: bool = False,
    ) -> Dict[str, Any]:
        """Sinh toàn bộ Character Anchors, Master Location Plates & Scene Keyframes còn thiếu theo batch <= 4."""
        project_dir = Path(project_dir)
        dirs = cls.ensure_asset_dirs(project_dir)
        bible_path = project_dir / "story_bible.json"
        bible = json.loads(bible_path.read_text(encoding="utf-8"))
        manifest_path = project_dir / "shots_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"shots": []}
        require_current_staging(manifest)
        run_token = secrets.token_hex(3)  # unique batch ids per run (L38): a reused zip name matches an old result card

        if not account_ids:
            raise ValueError("Cần ít nhất 1 tài khoản READY để sinh Keyframe")

        report: Dict[str, Any] = {
            "anchors_generated": [],
            "turnarounds_generated": [],
            "setups_generated": [],
            "keyframes_generated": [],
            "rejected": [],
            "contact_sheets": [],
        }

        # 1. Sinh Anchor nhân vật còn thiếu
        missing_anchors = cls.plan_missing_character_anchors(bible, dirs["anchors"])
        if missing_anchors:
            for b_idx in range(0, len(missing_anchors), 4):
                chunk = missing_anchors[b_idx : b_idx + 4]
                batch_id = f"KF_ANCHOR_{(b_idx // 4) + 1:02d}_{run_token}"
                res = await cls._dispatch_kf_batch_with_failover(
                    client=client,
                    account_ids=account_ids,
                    start_offset=b_idx // 4,
                    chunk=chunk,
                    batch_id=batch_id,
                    out_dir=dirs["anchors"] / "_batches" / batch_id,
                    simulate=simulate,
                )
                for kf_id, kinfo in res.get("keyframes", {}).items():
                    src_p = Path(kinfo["path"])
                    ok, errs, _ = cls.verify_keyframe_image(src_p)
                    if ok:
                        dest_p = dirs["anchors"] / f"{kf_id}.png"
                        dest_p.write_bytes(src_p.read_bytes())
                        report["anchors_generated"].append(str(dest_p))
                    else:
                        report["rejected"].append({"id": kf_id, "errors": errs})

        # 1.5. Sinh Master Location Plates còn thiếu (nếu bật include_setups hoặc bible.generate_location_plates)
        should_gen_setups = bool(include_setups) or bool(bible.get("generate_location_plates"))
        if should_gen_setups:
            missing_plates = cls.plan_missing_location_plates(bible, dirs["setups"])
            if missing_plates:
                for b_idx in range(0, len(missing_plates), 4):
                    chunk = missing_plates[b_idx : b_idx + 4]
                    batch_id = f"KF_SETUP_{(b_idx // 4) + 1:02d}_{run_token}"
                    res = await cls._dispatch_kf_batch_with_failover(
                        client=client,
                        account_ids=account_ids,
                        start_offset=b_idx // 4,
                        chunk=chunk,
                        batch_id=batch_id,
                        out_dir=dirs["setups"] / "_batches" / batch_id,
                        simulate=simulate,
                    )
                    for kf_id, kinfo in res.get("keyframes", {}).items():
                        src_p = Path(kinfo["path"])
                        ok, errs, _ = cls.verify_keyframe_image(src_p)
                        if ok:
                            dest_p = dirs["setups"] / f"{kf_id}.png"
                            dest_p.write_bytes(src_p.read_bytes())
                            report["setups_generated"].append(str(dest_p))
                        else:
                            report["rejected"].append({"id": kf_id, "errors": errs})

        if include_turnarounds:
            turnarounds = cls.plan_missing_character_turnarounds(bible, dirs["anchors"])
            results = []
            for offset in range(0, len(turnarounds), 4):
                batch_id = f"KF_TURN_{offset // 4 + 1:02d}_{run_token}"
                results.append(await cls._dispatch_kf_batch_with_failover(
                    client=client,
                    account_ids=account_ids,
                    start_offset=offset // 4,
                    chunk=turnarounds[offset : offset + 4],
                    batch_id=batch_id,
                    out_dir=dirs["anchors"] / "_batches" / batch_id,
                    simulate=simulate,
                ))
            cls.save_character_turnarounds(bible_path, bible, dirs["anchors"], turnarounds, results, report)

        # 2. Sinh Scene Keyframes còn thiếu (tự động gắn master_plate vào reference_images nếu có)
        missing_kfs = cls.plan_missing_scene_keyframes(bible, manifest, project_dir)
        kf_index_path = dirs["keyframes"] / "keyframes_index.json"
        kf_index: Dict[str, str] = (
            json.loads(kf_index_path.read_text(encoding="utf-8")) if kf_index_path.exists() else {}
        )

        if missing_kfs:
            for b_idx in range(0, len(missing_kfs), 4):
                chunk = missing_kfs[b_idx : b_idx + 4]
                batch_id = f"KF_SCENE_{(b_idx // 4) + 1:02d}_{run_token}"
                res = await cls._dispatch_kf_batch_with_failover(
                    client=client,
                    account_ids=account_ids,
                    start_offset=b_idx // 4,
                    chunk=chunk,
                    batch_id=batch_id,
                    out_dir=dirs["keyframes"] / "_batches" / batch_id,
                    simulate=simulate,
                )
                for kf_id, kinfo in res.get("keyframes", {}).items():
                    src_p = Path(kinfo["path"])
                    ok, errs, _ = cls.verify_keyframe_image(src_p)
                    if ok:
                        dest_p = dirs["keyframes"] / f"{kf_id}.png"
                        dest_p.write_bytes(src_p.read_bytes())
                        kf_index[kf_id] = str(dest_p)
                        report["keyframes_generated"].append(str(dest_p))
                    else:
                        report["rejected"].append({"id": kf_id, "errors": errs})

            kf_index_path.write_text(json.dumps(kf_index, indent=2, ensure_ascii=False), encoding="utf-8")

        # 3. Xuất Contact Sheet duyệt thị giác
        all_anchors = sorted(p for p in dirs["anchors"].glob("*.png"))
        all_setups = sorted(p for p in dirs["setups"].glob("*.png"))
        all_kfs = sorted(p for p in dirs["keyframes"].glob("*.png"))
        if all_anchors:
            cs_a = cls.build_contact_sheet(all_anchors, dirs["anchors"] / "anchors_contact_sheet.jpg")
            if cs_a:
                report["contact_sheets"].append(str(cs_a))
        if should_gen_setups and all_setups:
            cs_s = cls.build_contact_sheet(all_setups, dirs["setups"] / "setups_contact_sheet.jpg")
            if cs_s:
                report["contact_sheets"].append(str(cs_s))
        if all_kfs:
            cs_k = cls.build_contact_sheet(all_kfs, dirs["keyframes"] / "keyframes_contact_sheet.jpg")
            if cs_k:
                report["contact_sheets"].append(str(cs_k))

        return report
