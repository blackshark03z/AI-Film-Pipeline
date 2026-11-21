# Backlog khoảng trống nghề làm phim — Muse (19/11/2026)

Danh sách việc **chưa triển khai**. Chưa có dòng code nào được sửa cho các mục dưới đây. Định nghĩa khoảng trống G1–G5:
`C:\Users\ADMIN\.claude\film-craft-inputs\GAP_ANALYSIS_2026-11-19.md`. Cách làm tạm thời bằng tay nằm trong skill
`.claude/skills/muse-director/` (generability, interaction contract, lessons). Mỗi mục ghi bằng chứng, chỗ sẽ đặt
và điều kiện "xong". Mọi lượt chạy live để kiểm chứng cần chủ dự án duyệt chi phí.

## G1 · Treatment, mô-típ và color script trong story bible và compiler

- **Bằng chứng:** không file nào trong `muse_studio` có `motif` hay `color_script`. Audit `PIPELINE_AUDIT_20261101.md`
  §3 ghi thiếu "visual treatment" và đường cong cảm xúc; chiếc nhẫn được nhắc nhưng chưa từng lên hình. Compiler chọn
  cỡ cảnh/lens theo luật chung (pyramid budget, lens psychology), chưa theo cường độ cảm xúc của cảnh. `color_mood`
  đã có theo từng shot (lấy từ beat, từ bối cảnh, hoặc `warm_flashback`; `screenplay_compiler.py` ~495, assembler ưu
  tiên giá trị theo shot, `master_assembler.py` ~674), nhưng không có color script theo cảnh do treatment quyết định.
- **Chỗ đặt:** khối `treatment` trong `story_bible.json` (theme, emotional curve theo cảnh, motif plant → payoff,
  color script theo cảnh); `core/screenplay_compiler.py` đọc treatment để chọn cỡ cảnh/lens/chuyển động;
  `core/master_assembler.py` lấy grade theo cảnh từ color script. Skill dùng chung: `film-treatment`.
- **Xong khi:** compile một dự án mẫu có treatment cho ra cỡ cảnh/lens khác nhau theo cường độ cảnh; mỗi motif có
  plant và payoff được kiểm như `must_show` (D6); test cục bộ đạt.

## G2 · Bản ghi duyệt sáng tạo cạnh FilmQC

- **Bằng chứng:** FilmQC đo lỗi kỹ thuật (decode, chuyển động, flicker, tay, mặt, WER, lip-sync). Macro `S06__prop_insert`
  được `PASS` khi chìa bị nhấc khỏi bàn (SOT dòng 99). `quality_score` chỉ xếp hạng take. Chưa có chỗ lưu nhận xét
  diễn xuất, nhịp, ai nói với ai và lời chốt của chủ dự án theo từng take.
- **Chỗ đặt:** `creative_review.json` cạnh `qc_audit_report.json` (theo shot/take: điểm theo rubric, bằng chứng,
  verdict của chủ dự án, ngày); `qc-audit` và `assemble` đọc để không ráp take bị chủ dự án loại. Rubric: skill
  `film-creative-review`.
- **Xong khi:** `assemble` bỏ qua take có verdict từ chối dù QC `PASS`; báo cáo QC hiển thị song song trạng thái kỹ
  thuật và sáng tạo; có test.

## G3 · Giọng theo nhân vật và đường xử lý thoại

- **Bằng chứng:** `core/master_assembler.py:415` `_generate_edge_tts(..., voice="en-US-ChristopherNeural")` là một giọng
  cố định; nó chỉ được gọi cho shot `HYBRID_VO` có `voiceover_text` (dòng ~666). Thoại `native_drama` dùng âm thanh của
  clip sinh ra cùng khóa màu giọng FIR (`VoiceTimbreMatcher`). Chưa có voice ID khóa theo nhân vật, chưa có mẫu giọng
  tham chiếu, chưa có đường thay/sửa thoại (ADR) khi take hình tốt nhưng giọng hoặc từ sai (B14: "Flight 1128" nghe
  thành 128/1118). Nhạc là pad tổng hợp.
- **Chỗ đặt:** `voice` theo nhân vật trong `story_bible.json` (voice id, mẫu tham chiếu, ghi chú phát âm);
  `core/master_assembler.py` chọn giọng theo `speaker`; một route thoại (native / thay giọng / TTS) theo shot, có
  kiểm tra từ khóa và số. Skill: `film-sound-design`.
- **Xong khi:** hai nhân vật cho ra hai giọng khác nhau ở chế độ hybrid; mỗi shot thoại ghi rõ route; danh sách từ/số
  quan trọng theo cảnh được ASR kiểm và bất đồng được giữ chờ nghe duyệt.

## G4 · Vòng VLM judge so với ảnh neo và kịch bản

- **Bằng chứng:** QC chỉ có `quality_score` kỹ thuật và kiểm `actor_consistency` bằng HSV/LAB. Lỗi ngữ nghĩa (đếm người,
  tư thế, đạo cụ méo, hướng nhìn, ai nói với ai) hiện chỉ do mắt người đọc contact sheet (audit §3; ERROR_CATALOG E13:
  tác tử chấm không ổn định về không gian).
- **Chỗ đặt:** bước chấm sau `qc-audit`: so khung mẫu với ảnh neo, keyframe đã duyệt, `action_summary` và câu hỏi
  interaction contract; ghi vào `creative_review.json` (G2). Chỉ tư vấn: xếp hạng và gắn cờ, không giấu take khỏi chủ
  dự án.
- **Xong khi:** trên bộ benchmark (G5) judge gắn cờ được lỗi macro (chìa nhấc) và lỗi B14 (bảng kẹp bị nâng); tỉ lệ
  báo nhầm được ghi lại.

## G5 · Bộ shot benchmark

- **Bằng chứng:** mỗi thay đổi về model, prompt hay kích thước ảnh gửi hiện được thử trên một mẫu riêng lẻ (macro
  dài vs 59 từ; T0 1672×941 vs 1280×720). Chưa có tập shot cố định để chạy lại khi nhà cung cấp hay pipeline đổi.
- **Chỗ đặt:** thư mục `benchmarks/` với 6–10 shot mẫu đã có keyframe và tiêu chí (một shot GREEN thoại, một OTS, một
  reaction, một insert không tay, một macro tay + vật nhỏ, một người đi vào khung); script đo cục bộ trên kết quả.
- **Xong khi:** mỗi shot có tiêu chí đạt/trượt viết sẵn; một lượt chạy (đã được duyệt chi phí) ra bảng so sánh với lượt
  trước.

## Generability trong `screenplay_compiler`

- **Bằng chứng:** không có trường hay kiểm tra generability. Macro tay đặt chìa (SOT dòng 97–100): nhảy hậu cảnh ở
  1,92 s, chìa nhấc khoảng 3,50 s, xin 5 s trả về 10 s; B14 bảng kẹp rơi phải ghép composite. AFP xếp "tay trên vật
  nhỏ" và "vật cầm bị thả rơi" là RED trước khi làm ảnh.
- **Chỗ đặt:** `core/screenplay_compiler.py` ghi khối `generability {level, reasons, restage, cap, exception}` cho mỗi
  shot; `cli preflight` báo HARD khi RED không có exception do chủ dự án duyệt; `pool_runner videos` giới hạn số lần gửi
  theo cap và có cách chọn tập shot cần gửi. Quy tắc: `.claude/skills/muse-director/references/generability.md`.
- **Xong khi:** compile bản sao dự án macro gắn RED cho `S06__prop_insert`, preflight chặn, restage bằng `state_insert`
  hết chặn; có test.

## Trường interaction contract

- **Bằng chứng:** chưa có addressee, listener anchor, marks, gaze target, người giữ đạo cụ, encounter. `axis_gaze` /
  `gaze` là hướng màn hình, không phải đối tượng nhìn. D2 chỉ cảnh báo khi chương có ≥ 3 shot thoại, ≥ 2 người nói và
  không có shot nhiều người. B14 01A: thân Todd mở về máy dù đầu hướng Pamela. Dry-run offline trên bản sao B14
  (phiên điều phối, 19/11/2026): các shot cận một người S10 và S13 được compile với câu "Only this character in frame,
  same cast and wardrobe as the reference." (nhánh đơn nhân vật trong `screenplay_compiler.py`), không nêu tên hay
  vị trí người nghe; `foreground_element` của S06 là `None` vì compiler chỉ chép giá trị từ beat. Tức là đầu ra
  compiler chưa đáp ứng interaction contract.
- **Chỗ đặt:** beat trong `beats.json` và shot trong `shots_manifest.json`: `addressees`, `listener_anchor`,
  `gaze_target`, `blocking`; `locations[].marks` trong bible; người giữ trong `props_ledger.state_tracking`;
  `encounter_id`. Compiler đưa addressee và anchor vào prompt keyframe và video từ cùng một nguồn; `audit_coverage`
  kiểm mỗi câu thoại có người nhận được neo. Bảng ánh xạ: `references/interaction-contract.md`.
- **Xong khi:** một cảnh thoại hai người compile ra prompt có tên người nghe và vị trí neo; thiếu addressee là cảnh báo
  preflight; OTS có tiền cảnh khác người nói; có test.

## Thời lượng shot theo hành động và lời thoại

- **Bằng chứng:** `screenplay_compiler.py` đặt `duration_s = 10.0` cho mọi shot có thoại và 5.0 cho shot im lặng ở
  `native_drama`; dry-run B14 có S10 là câu 5 từ vẫn nhận 10 s. Chỉ có cảnh báo `DIALOGUE_OVER_CAPACITY` khi câu quá
  dài, không có chiều ngược lại. Quy tắc generability: thời lượng ≈ 1 s chuẩn bị + hành động + 0,5–1 s lắng (handoff §8
  cũng nêu mặc định 10.0 s ở nhánh thoại).
- **Chỗ đặt:** `core/screenplay_compiler.py` tính `duration_s` từ `dialogue_timing` và hành động (trong giới hạn thời
  lượng Muse nhận), ghi lý do vào manifest.
- **Xong khi:** câu thoại ngắn compile ra shot ngắn hơn; câu dài vẫn bị cảnh báo; có test.

## Vệ sinh Git

- **Bằng chứng:** chỉ có một commit `b9d6d5c` ("baseline snapshot"); `.gitignore` đang sửa, 30 mục `scratch_*` bị
  đánh dấu xóa theo `git status` ngày 19/11/2026 (handoff §3 chỉ ghi "nhiều"), `muse_studio/` và các thư mục dự án chưa được theo dõi (handoff §3). Nhiều phiên đang làm việc cùng
  thư mục.
- **Chỗ đặt:** quyết định của chủ dự án: những gì đưa vào Git (code `muse_studio`, tài liệu, skill) và những gì bỏ qua
  (media, lượt chạy, `data/`, profile, thông tin đăng nhập); branch theo từng việc.
- **Xong khi:** `git status` sạch sau khi commit code + tài liệu; media và dữ liệu chạy nằm trong `.gitignore`; không
  có thông tin đăng nhập trong lịch sử.

## Phát hiện thêm khi viết skill (nhỏ)

- `python -m muse_studio.cli <lệnh> --help` lỗi `UnicodeEncodeError` trên console cp1252; cần
  `PYTHONIOENCODING=utf-8` hoặc cấu hình stdout UTF-8 trong `main()`.
- `cli qc-audit` và `cli assemble` luôn thoát mã 0 kể cả khi có shot bị loại; script tự động cần đọc báo cáo JSON.
- `pool_runner videos --auto-repair` không có tác dụng vì mặc định đã bật; tắt bằng `--no-auto-repair`.
- Không có kiểm tra thời lượng/độ phân giải clip trả về so với yêu cầu (macro: 5 s → 10 s, 1248×704).
- Contact sheet mặc định rộng 1920 px (4 × 480); quy tắc duyệt ảnh của phiên Claude là ≤ 1280 px.
