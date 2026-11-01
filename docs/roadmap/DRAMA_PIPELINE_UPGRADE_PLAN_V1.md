# Drama pipeline — kế hoạch nâng cấp V1 (Tech Lead, 2026-11-01)

Trạng thái: ĐANG THỰC HIỆN. Owner xác nhận drama là mảng chính và giao toàn quyền
cho Tech Lead (2026-11-01). Tiến độ ở Mục 7.
Nhánh: `feature/drama-preprod-p0` @ ec8c1bb.

Lưu ý canonical: `docs/operating/CURRENT_SLICE.md` / `IMPLEMENTATION_STATUS.md`
vẫn ghi mission đang ACTIVE là xianxia 60s. Toàn bộ drama (film01) đang chạy theo
chỉ đạo trực tiếp của Owner trên nhánh riêng. Nếu kế hoạch này được duyệt, cần
Owner xác nhận drama là focus đang active để ghi vào canonical status, thay vì để
hai mục tiêu song song không được ghi nhận.

## 1. Đầu vào đã đối chiếu

- Muse: `Mục tiêu và các lỗi từng gặp.txt` (6 nhóm lỗi),
  `MUSE_V2_3_PRE_IMPLEMENTATION_REVIEW.txt` (9 issue, 3 trụ cột A/B/C, gate G1–G12),
  `PILOT_R2_ERRORS_SOLUTIONS_TEST_PLAN.txt` (7 lỗi R1), addendum Temporal Narrative.
- Hệ thống của ta: `src/film_pipeline/drama/` (script, feasibility, bible, axis,
  coverage, storyboard, prompt, preflight, continuity, qc) và
  `docs/drama/FILM01_LESSONS.md`.
- Nghiên cứu ngoài (Mục 6).

## 2. Đối chiếu: lỗi Muse ↔ hệ thống của ta

| Nhóm lỗi (Muse) | Ta đã có | Còn thiếu (gap) |
|---|---|---|
| Nhất quán vị trí / số người / không gian | `AxisBook` (trái/phải màn hình, eyeline), `ContinuityState.positions` giữa các generation | Sổ đăng ký người có mặt trong cảnh (có mặt / trong khung / ngoài khung). **Look bối cảnh** khóa cứng: film01 SC03_g2 bị trôi hậu cảnh. Ảnh plate/first-frame cho không gian |
| Hành động ngắn hơn shot, cử chỉ thừa, lặp động tác | `SceneTiming`, coverage có shot reaction, `CROSS_CUT_DEPENDENCY` | Choreography theo thời gian cho từng generation (setup → action → consequence → hold), hành động "đúng một lần", ngân sách cử chỉ. Chưa có luật cảnh báo đoạn đuôi không có chức năng |
| Biểu cảm sai nghĩa (khinh bỉ → cười tươi) | Chỉ có mô tả giọng | Hợp đồng diễn xuất: `emotion_intent` + dấu hiệu nhìn thấy được + cường độ + cách hiểu sai bị cấm |
| Góc quay nghèo, quá nhiều cận | Coverage planner (master / OTS / reaction), storyboard Gate 2 | **Kiểm tra cỡ cảnh sau render**: film01 SC03_g2 ra trung cảnh thay vì cận, không có gì bắt được |
| Logic vật lý / môi trường (mưa trong nhà) | Feasibility chặn đánh nhau, chữ trên hình, đám đông | Luật nhân quả môi trường: trong/ngoài, nguồn sáng, giờ trong ngày, thời tiết, khóa theo cảnh |
| Trôi mặt | `CharacterLook` khóa chữ, `character_sheet` để người xem | Điểm danh tính tự động (embedding khuôn mặt giữa các clip). Route text-only vốn dễ trôi hơn route có ref |
| Thời gian kể chuyện (flashback, ellipsis, cold open) | Không có; `ContinuityState` giả định tuyến tính | Bản đồ thời gian truyện: story-time ≠ screen-time. Continuity so theo story-time; quay về quá khứ được phép đổi trạng thái đạo cụ, **không** được đổi look nhân vật |
| Lệch audio–hình về nghĩa (reveal sớm) | Thoại lip-sync trong generation; phụ đề đã giới hạn theo shot người nói | `EDIT_MAP` + đồng hồ audio master + cổng reveal sớm nhất. Chỉ cần khi làm chế độ narration (kiểu Muse) |
| JSON pass nhưng phim sai | `HandoffQC` thủ công, tách TECHNICAL / OWNER PASS | Rubric xem phim tốc độ thật. Công cụ QC hỗ trợ tự động (danh tính, cỡ cảnh, độ giống bối cảnh, VLM judge). Sổ KPI |
| Giới hạn engine, chi phí | Giới hạn feasibility đánh dấu `(*)` (giả định) | Capability manifest theo provider, có trạng thái "đã đo" / "giả định". Flow route chỉ nằm trong scratchpad |
| Nhãn AI / tuân thủ | Nhãn chèn tay ở bước hậu kỳ, `synthetic_person` attest | Module hậu kỳ trong `src/`. Nhãn đầu phim + watermark + marking máy đọc được (C2PA) theo EU AI Act Art. 50 |

Những gì Muse đề xuất mà ta **không** nên chép:
- Greybox 3D cho mọi cảnh.
- XYZ chính xác trong JSON: model không tuân theo được từ text.
- 10–15 file JSON trùng dữ liệu bible.
- Vòng AI phản biện nhiều lượt.

Ta giữ nguyên tắc của Muse "khóa quyết định đạo diễn, không viết prompt dài hơn",
và nguyên tắc của ta "lỗi phim → sửa đúng khâu".

## 3. Baseline đo được (film01, route text-only Flow)

- 80 s phim dùng được. Khoảng 168 credit cho route text-only (120 + 12 + 36),
  tức **~2,1 credit / giây dùng được**, chưa tính 60 credit điều tra lỗi bị chặn.
- Lượt render đầu tiên: 8/10 generation được giữ. 2 generation của SC03 phải làm
  lại, hết 3 lượt thêm.
- Lỗi chỉ phát hiện sau render: trôi tóc, logic đạo cụ qua chỗ cắt, đổi người,
  trôi hậu cảnh, sai cỡ cảnh.

Đây là baseline A/B cho mọi nâng cấp bên dưới.

## 4. Các gói công việc (theo thứ tự Tech Lead đã chốt)

Nguyên tắc: không tốn credit cho tới khi có thử nghiệm A/B. Mỗi gói có nghiệm
thu bằng phim thật hoặc tái tạo được film01, không chỉ unit test.

### WP1 — Đưa phần ad-hoc của film01 vào `src/` (P0, 0 credit)
- `GenerationPlan`: tách scene thành N generation × 8 s, kèm trạng thái đầu/cuối
  và cổng render tuần tự. Hiện việc này đang nằm trong `sc03_v2.py` ở scratchpad.
- Flow text-only adapter: gửi → chờ → tải → xác minh sha **mới** khác tile trước
  → `SEND_FAILED` / `BLOCKED` / `PASSED`. Dùng cơ chế GPM/CDP sẵn có, không đọc cookie.
- Module `post`: phụ đề giới hạn theo shot người nói, loudness 2 lượt + limiter,
  nhãn, thẻ đầu/cuối, manifest.
- Nghiệm thu: dựng lại final film01 từ repo, các thông số khớp manifest, có test
  tập trung. Giao `worker` (Sonnet) theo brief; Tech Lead review.

### WP2 — Scene bible: bối cảnh, người có mặt, môi trường, thời gian truyện (P0, 0 credit)
- `LocationLook`: text khóa cứng + invariants (kiến trúc, landmark, ánh sáng, giờ
  trong ngày, thời tiết trong/ngoài). Preflight `LOOK` áp cho bối cảnh như với
  nhân vật.
- Sổ người có mặt: `in_scene` / `visible` / `offscreen`, sự kiện vào/ra. Preflight
  chặn người xuất hiện khi chưa vào cảnh, hoặc biến mất mà không có sự kiện ra.
- `story_time` cho mỗi cảnh, cùng loại chuyển cảnh (linear / flashback /
  flashforward / ellipsis / parallel). Continuity so theo story-time; quay về quá
  khứ được reset trạng thái đạo cụ, cấm đổi look. Mâu thuẫn nguồn → `SOURCE_CONFLICT`.
- Nghiệm thu: test cho từng luật, kèm một kịch bản mẫu có cold open + flashback.

### WP3 — Choreography theo thời gian + hợp đồng diễn xuất (P0, 0 credit)
- Mỗi generation khai 2–4 pha (setup / action / consequence / hold), `once_actions`
  (ví dụ đặt chìa khóa đúng một lần), `gesture_budget`.
- Diễn xuất: `emotion_intent` + 1–3 `visible_cues` + `intensity` +
  `prohibited_misread`. Compile vào prompt dạng ngắn và tính vào giới hạn từ.
- Feasibility WARN: đoạn đuôi > N giây không có pha nào. Hành động lặp hoặc
  "continues" không kiểm soát → BLOCK.
- Nghiệm thu: test + prompt film01 compile lại vẫn ≤ 120 từ.

### WP4 — QC hỗ trợ tự động + sổ KPI (P1, 0 credit; cần cài thư viện, xin duyệt)
- Danh tính: embedding khuôn mặt (ArcFace / InsightFace) theo frame, so với frame
  look đã duyệt. Báo cả độ tương đồng lẫn **phương sai** (độ ổn định).
- Cỡ cảnh: tỉ lệ khung mặt trên frame → CU / MCU / MS / WS, so với plan.
- Bối cảnh: độ tương đồng nền (DINO / CLIP) giữa các generation cùng location.
- (Tùy chọn) VLM judge trả lời checklist sinh ra từ plan: thứ tự hành động, đạo
  cụ, biểu cảm. Chỉ là cảnh báo, người duyệt vẫn quyết định. Lý do: nghiên cứu
  ghi nhận VLM dạng yes/no hay thiên "yes".
- Sổ KPI mỗi phim: tỉ lệ dùng được ở lượt đầu, credit / giây dùng được, số lượt
  render lại / 100 s, số vi phạm continuity, phân loại nguyên nhân lỗi.
- Nghiệm thu: chạy trên clip film01. Phải bắt được tóc xoăn ở bản bị loại, DOYLE
  sai người, cỡ cảnh trung thay vì cận và trôi hậu cảnh SC03_g2 (4 lỗi đã biết).

### WP5 — Thử conditioning trên Flow (P1, ~48–72 credit, cần Owner duyệt)
- Giả thuyết: Flow chặn **mặt người** trong ref kết hợp cốt truyện nhạy cảm,
  nhưng có thể nhận **plate bối cảnh không có người** và frame đầu từ storyboard
  minh họa.
- A/B 4 generation (SC03 hoặc cảnh mới): text-only vs plate bối cảnh vs
  first-frame. Đo: bị chặn hay không, độ giống bối cảnh, cỡ cảnh đúng (dùng WP4).
- Ghi kết quả vào capability manifest của provider (đã đo / giả định).
- Đo thêm ngân sách prompt (quyết định Tech Lead 2026-11-01, sau WP2/WP3):
  khi thêm look bối cảnh, chia pha và diễn xuất, SC03_g1 lên 145 từ (đã bỏ phần
  lặp hành động trong setting). Mặc định `max_prompt_words=120` giữ nguyên
  (giả định từ thời Dola). Route Flow tạm cho phép 150 từ; A/B 120 vs 150 về độ
  tuân thủ nằm trong WP5. Khi dùng choreography, hành động chỉ mô tả trong
  timing, không lặp lại trong `setting`.

### WP6 — Tuân thủ nhãn AI (P1, 0 credit)
- Nhãn ngay đầu phim cộng watermark suốt phim (đã làm tay ở film01). Thêm
  marking máy đọc được: manifest C2PA (c2patool) hoặc metadata, kèm
  `disclosure.json` (tool, model, ngày, synthetic persons).
- Lý do: EU AI Act Art. 50 áp dụng từ 2026-08-02. Với video: báo ngay từ đầu
  hoặc dùng watermark; nội dung hư cấu được dùng nhãn kín đáo nhưng không được bỏ.
  C2PA là ví dụ được nêu, không bắt buộc.

### WP7 — Phim thử film02: benchmark A/B (P1, ~120–180 credit, cần Owner duyệt kịch bản)
- Kịch bản ngắn (3 cảnh × 16 s), thiết kế để thử đúng các lỗi Muse: 3 người
  trong một phòng, một lần xử lý đạo cụ, cười khinh bỉ, mưa ngoài cửa sổ, một
  đoạn flashback.
- So KPI với baseline film01 (Mục 3). Chỉ promote luật / tính năng nào cải thiện
  KPI mà không tăng credit / giây bất hợp lý.

### Để sau (P2, chỉ khi Owner muốn sản phẩm này)
- Chế độ narration kiểu Muse: audio gốc làm đồng hồ, `EDIT_MAP`, cổng reveal.
  Tái dùng WP2 và WP3; phần mới chủ yếu là map lời kể sang beat.

## 5. Thứ tự, chi phí, người làm

| Thứ tự | Gói | Credit | Người làm |
|---|---|---|---|
| 1 | WP1 | 0 | worker (Sonnet) theo brief, Tech Lead review |
| 2 | WP2 + WP3 (một slice, cùng schema / preflight) | 0 | Tech Lead thiết kế schema → worker viết code + test |
| 3 | WP4 | 0 (cài model ONNX, xin duyệt) | Tech Lead |
| 4 | WP6 | 0 | worker |
| 5 | WP5 | 48–72 | Tech Lead (điều khiển Flow) |
| 6 | WP7 | 120–180 | Owner duyệt kịch bản / storyboard → Tech Lead |

Owner cần duyệt: phạm vi (drama có phải focus active không), cài thư viện cho
WP4, credit cho WP5 / WP7, kịch bản film02.

## 7. Tiến độ (cập nhật 2026-11-01)

| Gói | Trạng thái | Kết quả |
|---|---|---|
| WP1–WP3 | xong | schema / preflight / choreography trong `src/film_pipeline/drama/` |
| WP4 | xong (a2f8f4f) | `autoqc.py`: identity, shot scale, set handoff (WARN) |
| WP6 | xong (d979e16) | `disclosure.py`: nhãn hiển thị + metadata + C2PA (dev signer) |
| WP1b | xong | `tools/drama_flow_ui/flow_send.py`: bind output theo network, 6/6 PASSED |
| WP5 | xong, 48 credit | `docs/drama/wp5/README.md`: route mặc định = ảnh khung đầu Flow (0 credit) + chế độ "Khung hình"; video ingredient bị loại; ngân sách prompt 170 từ |
| WP7 | đang làm | film02 benchmark theo route WP5 |

## 6. Nguồn tham khảo bên ngoài

- Veo 3.1: timestamp prompting, first/last frame (last frame chỉ là hướng dẫn
  mềm), ingredients ≤ 3 ref. Nguồn thứ cấp:
  https://dev.to/akaranjkar08/veo-31-developer-guide-timestamp-prompting-multi-shot-video-and-full-api-june-2026-3l5i ,
  https://www.atlabs.ai/blog/veo-3.1-prompting-guide-every-feature-explained-with-copy-paste-prompts
- Storyboard-first và ảnh duyệt làm anchor continuity (nguồn vendor):
  https://invideo.io/faq/what-is-a-storyboard-first-ai-filmmaking-workflow-and/ ,
  https://www.deepfiction.ai/blog/ai-filmmaking-pipeline-script-to-screen-2026
- Danh tính khuôn mặt (ArcFace, phương sai theo frame), VBench-2.0, VideoPhy-2,
  VLM judge: https://api.emergentmind.com/topics/idbench-v ,
  https://arxiv.org/pdf/2504.12626 , https://arxiv.org/html/2503.21755v2 ,
  https://arxiv.org/pdf/2503.06800
- EU AI Act Art. 50 / C2PA:
  https://www.srd-rechtsanwaelte.de/en/blog/deepfake-labelling-under-the-ai-act-what-the-new-eu-guidance-clarifies ,
  https://www.cepic.org/post/the-transparency-obligations-of-the-ai-act-take-effect-on-2-august-2026-what-cepic-members-should-consider
- Netflix GenAI partner guidelines (khai báo trước, xin duyệt khi dùng likeness
  hoặc cho final deliverable):
  https://www.tvtechnology.com/news/netflix-lays-out-guidance-for-using-generative-ai-in-content-production
