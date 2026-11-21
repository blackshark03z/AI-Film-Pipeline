# QUY TRÌNH CHUẨN SẢN XUẤT PHIM AI KHÉP KÍN — CINEMA STUDIO v5.0 (SINGLE SOURCE OF TRUTH)

> **Phiên bản:** 5.0 (In-Memory QC, Warm Browser Sessions, Character Turnarounds và Cinematic Cutaways)  
> **Áp dụng:** Toàn bộ hệ thống làm phim `d:\Muse\muse_studio` & Gemini Orchestrator  
> **Điều phối đa luồng `(N × 6)`:** `python -m muse_studio.pool_runner <capacity|keyframes|videos>`  
> **Điều phối biên dịch, Animatic, QC & hậu kỳ:** `python -m muse_studio.cli <normalize-srt|srt-audit|compile|keyframes|animatic|preflight|qc-audit|assemble|deliver>`

---

## 1. QUY TRÌNH 9 KHÂU CHUẨN NGÀNH ĐIỆN ẢNH

```
[0. Kịch bản / Tiểu thuyết / SRT + Kiểm tra công suất Pool (N x 6)]
           │
           ▼
[Khâu 1: Phân rã Scene -> Beat (`film-screenplay-normalizer`)]
           │  • Lọc CTA, chia chương, kiểm định 3 cổng HARD `srt-audit` (chống cụt đuôi/sót chương)
           │  • Chọn chế độ âm lời: `native_drama` (mặc định) hoặc `hybrid_narrated`
           ▼
[Khâu 2: Story Bible, Wardrobe Progression & Must-Show (`film-story-bible`)]
           │  • Khóa `look_verbatim`, `turnaround_images` đa góc, `wardrobe_by_chapter`, trục 180°
           │  • Sổ đạo cụ động `props_ledger` (keywords + state_tracking) & chi tiết bắt buộc `must_show`
           ▼
[Khâu 2.5: Master Location Plates & Keyframes 00.png (`KeyframeComposer` / `pool_runner keyframes`)]
           │  • Sinh `assets/setups/<loc_id>__master_plate.png` (bối cảnh trống 0 người khóa kiến trúc)
           │  • Sinh `00.png` (`N × 4` ảnh song song) neo vào Location Plate + Turnaround Ref + duyệt Contact Sheet
           ▼
[Khâu 3: Biên dịch Ngữ pháp Điện ảnh v4.2 & Preflight (`ScreenplayCompiler`)]
           │  • Pyramid Shot-Scale Budget (`MCU+CU <= 40%`, `CU <= 2` liên tiếp, Re-establishing mỗi 6 shots)
           │  • Tự động gán Lens Psychology (`24/35/50/85/100mm`), `camera_angle`, `foreground_element`, `subtext`
           │  • Dual-Layer Camera: Native AI Dolly/Slider cho cảnh hành động/thiết lập + Virtual Camera Rig hậu kỳ cho thoại
           │  • Kiểm định phủ máy đối thoại `D2`, sổ `must_show` `D6`, quy tắc `30°` chống Jump-Cut, khóa tay & trục 180°
           ▼
[Khâu 3.5: Dựng nháp Tiền kỳ Animatic Previs (`AnimaticBuilder` — `cli animatic`)]
           │  • Xuất `ANIMATIC/animatic_preview.mp4` (1280x720 @ 12fps + Director HUD + cue click + SRT)
           │  • Duyệt nhịp cắt & hướng nhìn trước khi đốt quota render video
           ▼
[Khâu 4: Sản xuất Video Hàng đợi Động & Cân bằng Tải Đuôi (`ParallelPoolEngine` — `pool_runner videos`)]
           │  • Phát tải `N tài khoản × 6 shots` song song; tự chia đều cỡ batch ở vòng retry ít shot để 100% tài khoản cùng gánh
           │  • Tự né profile đang mở ở session khác (`SessionLock` + `BusyAccountDetector`), gửi kèm `extra_refs` đồng bộ nhân dạng
           │  • Hot-swap tài khoản dự phòng khi cạn quota + tự chữa prompt bảo toàn timecode/trục (`PromptRepairAgent`)
           ▼
[Khâu 5: Hậu kiểm 7-Gate Film QC & Tuyển chọn Multi-Take (`FilmQCEngine`)]
           │  • Gate 1-3: Full Decode + Motion 4fps + Flicker/Optical Flow + 3x3 HSV Spatial Continuity (nhận diện mượt chuyển động máy)
           │  • Gate 4A/4B: Hand ROI Defensive Trim + Sinh trắc thị giác `actor_consistency` & `face_boxes`
           │  • Gate 5A/5B: Faster-Whisper `WER <= 15%` + Kiểm tra câm tiếng/clipping & chống "nói bụng" Lip-Sync
           │  • Chấm `quality_score` (0..100, công bằng cho cả cảnh tĩnh và cảnh dolly/pan) tự chọn Circle Take xuất sắc nhất
           ▼
[Khâu 6 & 7: Hậu kỳ DI Color, Virtual Camera Rig, Hòa âm 4 Tầng & Mastering (`MasterAssembler`)]
           │  • DI Color Match `(Y, R, G, B)` liên cảnh (`colorbalance ±8%`) + Mood Grade + 35mm Film Grain + Dissolve Fade-in/out
           │  • Virtual Camera Rig mượt cosine ease (`push_in`, `pull_out`, `drift_right`, `drift_left`, `handheld_subtle`)
           │  • Lọc sạch thoại AI (`afftdn`) + Khóa màu giọng nhân vật `VoiceTimbreMatcher` (FIR 16-band / STS hook)
           │  • Gối thoại `J-Cut / L-Cut` + `Ambience` 7 archetype bối cảnh + 12 lớp `Foley` + `Dynamic Analog Pad Score` theo mood
           │  • Đặt Tag nhân vật Face-Aware 1 lần toàn phim + `Opening Title` / `End Credits` (`--with-titles`)
           │  • EBU R128 2-Pass (`-16.0 LUFS`) + Phụ đề chuẩn Netflix (`<= 42` ký tự/dòng theo `word_timestamps`)
           ▼
[Khâu 8: Bản địa hóa, NLE Timeline & Gói Phát hành Thương mại (`DeliveryPackager` — `cli deliver`)]
           │  • Xuất rời `M&E Stem` (`.me_stem.m4a`) & `Dialogue Stem` + `.i18n_template.json` phục vụ lồng tiếng đa ngữ
           │  • Nhúng lossless `FFMETADATA1` Chapters vào MP4 + `.chapters.txt` + Project `CapCut Desktop Draft` thật
           │  • Xuất `DELIVERY_KIT/`: `trailer_1080p.mp4` + `shorts_vertical_9x16.mp4` (bám mặt) + `poster_1080p.png`
```

---

## 2. LỆNH ĐIỀU PHỐI THỐNG NHẤT

### A. Công cụ Pool đa luồng `N × 6` (`python -m muse_studio.pool_runner`)
- `capacity [-n N] [--verify-unchecked]`
- `keyframes <project_dir> [-n N] [--include-setups] [--include-turnarounds]`
- `videos <project_dir> [-n N] [--max-rounds 3] [--auto-repair]`

### B. Công cụ Biên dịch, QC, Hậu kỳ & Giao bản (`python -m muse_studio.cli`)
- `normalize-srt <srt> [--chapters ...] [--output ...]` / `srt-audit <target> [--srt ...]`
- `compile <project_dir> [--audio-mode native_drama|hybrid_narrated] [--cinematic-cutaways]`
- `keyframes <project_dir> [--simulate] [--include-setups] [--include-turnarounds]`
- `animatic <project_dir> [--output ...] [--fps 12]`
- `preflight <project_dir> [--srt ...]`
- `qc-audit <project_dir> [--strips]` *(tự chọn take có `quality_score` cao nhất)*
- `assemble <project_dir> [--output ...] [--with-titles] [--color-mood ...] [--capcut-draft] [--promo-kit]`
- `deliver <project_dir> [--master ...]`

## 3. v5.0 Speed & Cinematography Upgrades

- **QC và hậu kỳ.** OpenCV giải mã frame trong RAM cho các phép đo chuyển động và màu Y/R/G/B. QC audit, normalize segment và encode animatic dùng nhiều worker. Master nối các segment theo thứ tự kịch bản. EQ thoại giảm 2,2 dB ở 6,8 kHz và cửa sổ J/L-Cut dài tối đa 0,26 giây mỗi phía.
- **Warm session.** `pool_runner keyframes` và `pool_runner videos` tái sử dụng Chromium theo tài khoản trong một lượt chạy. Timeout thay đổi theo cỡ batch. Pool đợi các worker kết thúc rồi giải phóng phiên kể cả khi một worker báo lỗi. Bộ chọn tài khoản tiếp tục lọc profile do phiên khác nắm giữ.
- **`--include-turnarounds`.** Dùng cho cả hai lệnh `keyframes`. Pipeline sinh các góc 3/4 và toàn thân còn thiếu sau khi có ảnh neo gốc, ghi ảnh đạt kiểm tra vào `assets/anchors/` và cập nhật `story_bible.json` trước khi lập keyframe cảnh. Góc 3/4 ưu tiên cho OTS và trung cảnh 3/4. Góc toàn thân ưu tiên cho cảnh rộng. Duyệt `anchors_contact_sheet.jpg` và `keyframes_contact_sheet.jpg` trước khi render video.
- **`--cinematic-cutaways`.** Cho phép thêm góc quay phụ có căn cứ vào manifest. Mỗi quyết định có mục đích và trích đoạn nguồn ở `staging`. Ngân sách tối đa là 20% số beat gốc, làm tròn xuống. Dùng cùng cờ khi compile trước và sau bước sinh keyframe. `autoprod` lưu góc quay phụ cùng beat khi ingest.
- **Mặc định.** Cả hai cờ đều tắt. Dùng `--simulate` cho kiểm tra offline và `--no-ui-sync` ở `pool_runner` hoặc `autoprod` khi chạy thử trong thư mục riêng.

### Kiểm chứng bản nâng cấp 18/11/2026

Mã nguồn v5.0 nằm trong checkout cục bộ trên nền Git `b9d6d5c`.

- AST hợp lệ 59/59 file. Toàn bộ suite `python -m pytest muse_studio/tests -q --tb=short` đạt **85 passed** trong 153,17 giây. Năm ca v5.0 nằm trong `muse_studio/tests/test_v50_speed_and_quality_upgrades.py`.
- Hai phép đo QC chuyển động và optical flow chạy trong 0,656 giây trên clip tổng hợp 8 giây 720p ở lượt đo riêng. Ngưỡng kiểm thử là 1,2 giây.
- Mô phỏng độc lập từ SRT có 5 lượt thoại tạo 6 shot, một cutaway phản ứng, bốn ảnh turnaround và một Master 1920×1080 ở 24 fps dài 22,605 giây. Phụ đề đầu ra có lời thoại mẫu và kiểm tra độ phủ nguồn đạt 100%.
- Muse live đã trả 5 keyframe qua 3 batch với một lần mở Chromium. Hai batch sau giữ nguyên Playwright, context và page, và phiên được dọn cuối lượt. Hai turnaround và reaction đạt kiểm tra ảnh. Macro trượt continuity màu da và tư thế khung đầu dù qua kiểm tra kỹ thuật. Phạm vi thử là ảnh tĩnh. [Báo cáo Muse live](_live_v50_20261118/REPORT.md)
- Sau khi khóa màu da bằng ảnh neo và tách tư thế mở cảnh khỏi động tác hạ tay, Muse live chạy lại riêng macro `S06__prop_insert`. Ảnh 2048×1152 có màu da khớp khi đối chiếu với ảnh neo và khoảng hở giữa tay với chìa khóa. [Báo cáo chạy lại macro](_live_v50_macro_retest_20261118/REPORT.md)
- Muse live render riêng video macro từ keyframe mới. Clip 5 giây giữ màu da và tư thế chưa chạm ở khung đầu, nhưng nhảy hậu cảnh ở 1,92 giây và làm chìa nghiêng, nhấc khỏi mặt bàn quanh 3,50 giây. Shot trượt continuity khi kiểm tra hình. [Báo cáo video macro](_live_v50_macro_video_20261118/REPORT.md)
- Bản prompt 59 từ dùng cùng keyframe cho cú hạ tay liền mạch hơn và chìa nằm phẳng lúc chạm đầu. Clip thực trả 10 giây dù gói yêu cầu 5 giây, có tiến máy và chạm lại bằng hai ngón. [So sánh hai clip macro](_live_v50_macro_short_video_20261118/REPORT.md)

### Nâng cấp logic dàn cảnh

Đọc từng cảnh theo thứ tự và ghi lý do cho cảnh chèn ngay trên beat liên quan. Mỗi `staging` có `kind`, `purpose`, `source_field` và `source_excerpt` trích từ beat đó. Kiểm tra `staging_review` trong manifest sau compile để thấy lý do chọn, bỏ hoặc báo đề xuất thiếu căn cứ trước khi sinh ảnh.

| Quyết định | Căn cứ và kết quả |
| --- | --- |
| `omit` | Giữ beat hiện tại khi cảnh chèn chỉ lặp lại thông tin hoặc làm lộ chi tiết sớm. |
| `reaction` | Chọn `character_id` là người nghe đang có mặt và xác định câu thoại khiến phản ứng đó đáng thấy. |
| `state_insert` | Chọn `prop_id` được nêu trong beat và trạng thái đã xác lập trong `props_ledger.state_tracking[beat_id]`. Khung chỉ thể hiện đạo cụ ở trạng thái ấy. Nếu trạng thái đã được cho thấy ở cảnh này, ưu tiên giữ nhịp hiện tại. |
| `source_action` | Dàn dựng một beat hành động im lặng đã có. Dùng đầy đủ `action_summary` làm `source_excerpt`, chọn `character_id`, `prop_id`, `before_state` và `after_state` có căn cứ cùng cảnh. Hành động xuất hiện đúng một lần tại beat đó, và QC giữ toàn bộ chiều dài clip để bảo toàn phần mở và kết. |

Nguồn chỉ có lời thoại và thiếu chỉ dẫn dàn cảnh sẽ giữ các beat thoại. Khi có bộ phân tích LLM, hệ thống kiểm tra đề xuất với lời trích và hành động trong nguồn trước khi dùng. Các cutaway tự sinh theo mẫu cũ được loại khi biên dịch lại. Mỗi quyết định dàn cảnh mới có định danh riêng cho keyframe và clip.

Checkpoint render mới lưu dấu vết prompt, ảnh đầu và ảnh tham chiếu. Khi resume, clip có dấu vết khác với đầu vào hiện tại được đưa ra khỏi danh sách clip đã qua kiểm tra. Checkpoint cũ thiếu dấu vết vẫn dùng cách đọc cũ.

Kiểm chứng 19/11/2026. Toàn bộ suite đạt **97 passed** trong 164,15 giây. AST hợp lệ 61/61 file. Mô phỏng từ CLI qua keyframe và preflight xác nhận ba cách dàn dựng có căn cứ. Biên dịch lại bản sao *The Spare Key* giữ cả 10 lượt thoại và loại hai cutaway theo quy tắc cũ. Hai cảnh báo thiếu góc rộng và góc chung ở bản thử vẫn được hiện trong manifest. Bằng chứng lần này là cục bộ.
