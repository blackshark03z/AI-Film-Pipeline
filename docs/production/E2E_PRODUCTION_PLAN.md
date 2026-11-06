# Kế hoạch hoàn thiện quy trình sản xuất phim E2E (Tech Lead, 2026-11-06)

Đầu vào: danh mục 168 hạng mục của Owner (`C:\Users\ADMIN\Documents\Nghiên cứu\Phim AI\Danh mục sản xuất phim e2e.txt`),
nghiên cứu gap của Codex (root `docs/research/E2E_FILM_PRODUCTION_GAP_STUDY_20261104.md`, ma trận
`E2E_FILM_CATEGORY_MATRIX_168_20261104.md`), và code thực tế trên `feature/drama-preprod-p0`.
Thực thi: loop Sonnet theo [LOOP_PROTOCOL.md](LOOP_PROTOCOL.md) và [LOOP_BACKLOG.md](LOOP_BACKLOG.md).

## 1. Hiện trạng đối chiếu (8 hệ thống của danh mục)

| Hệ thống | Đã có (nhánh drama) | Thiếu chính |
|---|---|---|
| I. Story (1–14) | Fountain intake `drama/script.py`, feasibility, comprehension (facts/carriers), `action_meaning` | Story bible: concept, audience, premise, logline, cấu trúc hồi, arc nhân vật, beat sheet, scene purpose/conflict/outcome; rewrite có impact list |
| II. Direction (15–34) | coverage (dialogue), axis 180°, choreography + performance cue, comprehension carriers | Director's treatment, visual language, POV/thông tin khán giả, dramatic emphasis, emotional curve, pacing plan, transition plan; gate coverage theo beat |
| III. Pre-prod (35–56) | bible (character refs), scene_bible (location look, occupancy, story time), storyboard schematic, preflight, generation split, continuity states | Costume/hair/prop version + state machine, lighting/camera plan, animatic có thời gian, continuity bible 6 loại, budget/risk/legal record |
| IV. Production (57–90) | Flow start-frame route (`tools/drama_flow_ui/flow_send.py`), lineage store, E2E runtime, KPI | Take log chung, dailies review theo hạng mục, retake policy (2 lần cùng nguyên nhân → đổi cách), pickup plan |
| V. Post (91–130) | `drama/post.py`: ghép, grade cố định, card, tag, subtitle, AI label, loudness | EDL/fine cut (in/out, J/L cut, dissolve), picture lock + invalidation, ambience/room tone/SFX/nhạc + mix ducking, color matching từng shot, credits |
| VI. QC (131–146) | autoqc WARN (identity, scale, set), shot QC record, E2E review template | Mô hình P0/P1/P2 theo 16 nhóm QC; 4 cấp (still / sampled frames / full motion / cut); QC master kỹ thuật (black/freeze/sync/clip) |
| VII. Delivery (147–156) | disclosure + C2PA (dev signer), E2E delivery package | Bản 9:16, thumbnail/metadata draft, archive + restore test; publish chỉ khi Owner cho |
| VIII. Management (157–168) | KPI ledger, cost theo film, hash/lineage | Một status report chung, dependency/change impact (đổi trang phục → shot bị ảnh hưởng), rights ledger, learnings |

**Vấn đề kiến trúc lớn nhất:** mỗi phim là một bộ script Python riêng (`tools/drama_film03*.py` ~830 dòng hằng số).
Hệ thống chưa phải "quy trình", mà là thư viện + kịch bản thủ công. Không scale, không kiểm tra được đủ 168 trách nhiệm.

## 2. Kiến trúc đích

**Production Package**: mỗi phim là một thư mục dữ liệu `films/<film_id>/`, không có code riêng.

```
films/<film_id>/
  film.json            # profile (drama | narration), format, budget, owner gates, status
  script.fountain      # kịch bản (drama) hoặc source/ (SRT + audio, narration)
  01_story.json        # Story bible (1-14)
  02_direction.json    # Director's treatment + per-scene direction (15-34)
  03_preprod.json      # characters/looks/costume/props/locations/lighting/camera/axis/continuity/budget/risk (35-56)
  04_shots.json        # generation units = ShotSpec + choreography + action_meaning + handoff (57-79)
  takes/  review.json  # take log + QC record P0/P1/P2 theo nhóm 131-146 (80-90, 131-140)
  05_edit.json         # EDL: selects, in/out, transitions, J/L, picture lock hash (91-106)
  06_post.json         # sound cues/mix, color, titles, subtitles (107-130)
  07_delivery.json     # master, versions, metadata, disclosure, archive (141-156)
  ledger.json          # cost, versions, dependency/invalidation, rights, learnings (157-168)
  media/               # gitignored
```

- Code mới: `src/film_pipeline/production/` (schema + loader + gates + stage runners) **tái dùng model drama**
  (CharacterLook, LocationLook, AxisBook, ContinuityState, GenerationChoreography, ActionMeaning, …), không nhân bản.
- CLI chung: `tools/film.py {new,validate,plan,animatic,generate,ingest,review,cut,post,qc,deliver,status} --film films/<id>`.
- **Tư duy đạo diễn = model + playbook + gate.** `docs/director/DIRECTOR_PLAYBOOK.md` mô tả cách model (Claude) soạn
  từng stage (quyết định sáng tạo), rút từ 168 danh mục, bài học film01–03 và luật Owner. Máy chỉ kiểm cấu trúc và
  tính nhất quán; không tự cho PASS nội dung footage.
- **Gate 1–6** đúng như danh mục: Story & Audio lock → Directorial coverage → Visual & spatial (storyboard/animatic)
  → Production asset (take QC) → Editorial (picture lock) → Final master. Gate có trạng thái `PASS/BLOCK/OWNER_PENDING`.
- Profile **narration** (SRT + audio gốc) dùng lại `e2e.py` runtime; profile **drama** dùng route start-frame Flow.

## 3. Lộ trình (phase → điểm ra kiểm được)

| Phase | Nội dung | Điểm ra |
|---|---|---|
| P0 Nền | Package schema/loader, `tools/film.py validate/status`, ma trận 168 trên nhánh này, port film03 thành package | `plan` từ package tái tạo **đúng từng byte** prompt film03 đã ship (hoặc diff có lý do ghi trong test) |
| P1 Story + Direction | Story bible, treatment, beat→carrier→shot coverage, POV/emphasis/emotional curve/pacing/transition, playbook | Gate 1–2 chặn được các lỗi film02 (dì bị hiểu là mẹ) và beat thiếu carrier |
| P2 Pre-production | Costume/prop version + state machine, lighting/camera plan, continuity bible 6 loại, animatic có tiếng, budget + risk | Animatic mp4 0 credit của film03; đổi trang phục 1 cảnh liệt kê đúng shot bị ảnh hưởng |
| P3 Production | Take log, dailies review P0/P1/P2, autoqc tích hợp, retake/pickup policy, Flow generate qua package | Chạy offline với take giả; live chỉ khi `OWNER_GO_LIVE: YES` |
| P4 Editorial | EDL, fine cut, J/L cut, transition, rhythm check, picture lock + invalidation | film03 dựng lại từ EDL khớp master cũ (±1 frame), đổi một in/out → dirty đúng post/QC |
| P5 Sound + Finish | Ambience/room tone, SFX cue, nhạc (nguồn có quyền), mix ducking, loudness, color matching, credits | film03 bản "v2 post" có ambience + nhạc + color match, QC âm thanh PASS |
| P6 Final QC + Delivery | QC master kỹ thuật, compliance/rights, 9:16, thumbnail + metadata draft, archive + restore | Gói film03 mở lại được từ thư mục mới, toàn bộ QC record trỏ đúng hash |
| P7 Management | Status report chung, cost/version/dependency/rights/learnings ledger | `film.py status` trả lời đủ "phim ở gate nào, thiếu gì, tốn bao nhiêu" |
| P8 Proof film04 | Model tự viết phim mới 90–120 s chỉ bằng package + playbook (không code riêng) | Offline tới animatic + post placeholder; live render + master khi Owner cho; KPI so film02/03 |

## 4. Nguyên tắc (không thương lượng)

- Không tạo phim bằng code riêng; nếu phim cần một thứ package không biểu diễn được → nâng cấp hệ thống.
- Lỗi phim → sửa ở stage đã bỏ lọt (memory: defects → fix the pipeline).
- Tách bạch: technical PASS ≠ product proof ≠ Owner acceptance. Máy không tự ACCEPT footage.
- Luật Owner: Generate đang tạm dừng; nghiên cứu/test video chỉ Omni Flash 360p; SRT → faithful action;
  không mua, không publish, không đụng cookie/captcha, không đóng GPM/Flow.
- 168 mục là bản đồ trách nhiệm, không phải 168 tính năng: mỗi mục = code đã kiểm / field trong package do model
  điền / thao tác operator có biên nhận / N/A có lý do theo profile.
