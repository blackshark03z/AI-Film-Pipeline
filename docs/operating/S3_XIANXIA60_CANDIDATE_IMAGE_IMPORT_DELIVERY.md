# BÁO CÁO NGHIỆM THU NHẬP ẢNH ỨNG VIÊN CHATGPT (TASK-S3 DELIVERY)
## DỰ ÁN PHIM *NHẤT KIẾM PHÁ VÂN* (XIANXIA60 — 60.0 GIÂY / 12 SHOT DUEL)

**Ngày thực hiện:** 2026-10-21
**Worker:** Gemini Flash 3.8
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`
**Worker branch / base commit:** `feature/film120-gemini-realshot-001@b355e255846cdf6d870f1cf5e2370a18abb2b248`
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Blob SHA: `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`)
**Frozen WP:** `docs/operating/TASK_S3_XIANXIA60_CHATGPT_CANDIDATE_IMAGE_IMPORT.md` (SHA256: `e4a1f82a2526e2aee96c6bad75dc984f747b25f4ab76fbc7eb9706d78577ba9a`)
**Tình trạng cấp phép Owner:** Owner đã phê duyệt giải nén tệp candidate pack vào staging và thực hiện đầy đủ Tasks 2–6. Look direction được Owner đánh giá *"Tạm được rồi"* (chấp nhận tạm thời hướng da ít bóng, tự nhiên; CHƯA phải Visual Lock nhân vật/trang phục/bối cảnh).

---

## 1. Xác Minh Tệp Tin, Kích Thước & Băm SHA-256 (Tất Cả Khớp 100%)

Tệp nén `XIANXIA60_ChatGPT_Reference_Candidates_v1.zip` (5,074,167 bytes, SHA256: `3711476fb7417d6ba5b4d77ed586bcf27d92e3aae35c7d2e83386e12548b2a26`) đã được giải nén vào thư mục staging:
`projects/xianxia60_nhat_kiem_pha_van/assets/references/chatgpt_candidates_wave01/XIANXIA60_ChatGPT_Reference_Candidates_v1/`

Kết quả kiểm tra thực tế trên đĩa vật lý:

| Tên Tệp | Kích Thước (Bytes) | Độ Phân Giải (Pixels) | Định Dạng / Mode | Mã Băm SHA-256 Thực Tế Trên Đĩa | Trạng Thái Đối Soát |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `owner_provisional_composite_source.png` | 2,676,300 | 1536 x 1024 | image/png (RGB) | `21f7bcb26510aa110f762a577401b3f042add2916b875fe6eff750077aaaa6ad` | **KHỚP 100%** (Gốc) |
| `ly_pha_van_portrait_candidate.png` | 692,216 | 765 x 626 | image/png (RGB) | `7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0` | **KHỚP 100%** (Crop) |
| `da_vo_nhai_portrait_candidate.png` | 698,657 | 762 x 626 | image/png (RGB) | `a89e067c39445c4485aa010d927270d025bc06ccffdc21d5fdc3303d493f3446` | **KHỚP 100%** (Crop) |
| `van_dai_arena_candidate.png` | 1,070,488 | 1536 x 389 | image/png (RGB) | `545d02eda6684c7121f6e49cc8e14057f9ba1630aaad49c073dfbf15a8453694` | **KHỚP 100%** (Crop) |
| `candidate_manifest.json` | 3,740 | N/A | application/json | `c2d1ecee1fd614fc3679add419760cd58ce207f449cdb062d191c8089da5bc38` | **KHỚP 100%** |
| `README_IMPORT.md` | 3,002 | N/A | text/markdown | `13a6383b292aea00d12c1f6ba5c99577a3034e0b1f9fba0206671a4da3afef09` | **KHỚP 100%** |

- **Toán học cắt ảnh (Crop Geometry):** 3 ảnh ứng viên được cắt không nén (lossless pixel crop) từ ảnh gốc 1536x1024; dải phân cách giữa hai ảnh chân dung là 9px (`x=765..774`); dải phân cách giữa chân dung và sàn đấu là 9px (`y=626..635`). Cả 3 ảnh đều là dẫn xuất của CÙNG MỘT lần sinh ảnh (single composite generation).

---

## 2. Ghi Nhận Xuất Xứ (Provenance) & Cơ Chế Quản Lý Khế Ước Film Core

Tuân thủ nghiêm ngặt nguyên tắc **One Product Truth**, các thông tin xuất xứ thực tế được ghi nhận trung thực:
- **Nguồn sinh:** ChatGPT Images (DALL-E 3 / GPT-4o image generator).
- **Mã định danh lần sinh gốc:** `aaa9a666-817b-4932-9046-1a235e3cbea0`.
- **Thông số không xuất ra từ tool:** `model_version: "NOT_ATTESTED_BY_ARTIFACT"`, `generation_seed: "UNKNOWN"`, `exact_image_generation_prompt: "NOT_AVAILABLE_IN_EXPORTED_TOOL_METADATA"`. Tuyệt đối không bịa đặt seed hay số phiên bản model.
- **Mã định danh media nhà cung cấp video:** `provider_asset_id: null` (hoàn toàn không chế tạo fake ID).
- **Tình trạng bản quyền:** `license_rights_review: "PENDING"`.
- **Sổ cái ứng viên mới:** Được lưu trữ tại `projects/xianxia60_nhat_kiem_pha_van/look_development/candidate_reference_ledger.json`, tuân thủ 100% lược đồ `schemas/asset.schema.json` qua `validate_contract("asset", rec)`.

---

## 3. Trạng Thái Sổ Cái Tham Chiếu Chuẩn (Canonical Reference Ledger Status)

Theo yêu cầu mục 4 của đề bài và quy chế fail-closed:
- **5/5 mục tham chiếu chuẩn trong `reference_asset_ledger.json` tiếp tục giữ nguyên 100% trạng thái `UNBOUND`**:
  1. `CHAR_WHITE_CULTIVATOR_REF_V1`: `UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED` (sha256: null, provider_asset_id: null)
  2. `CHAR_BLACK_CULTIVATOR_REF_V1`: `UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED` (sha256: null, provider_asset_id: null)
  3. `WARDROBE_WHITE_ROBE_V1`: `UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED` (chưa có tài sản hình ảnh độc lập)
  4. `WARDROBE_BLACK_ROBE_V1`: `UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED` (chưa có tài sản hình ảnh độc lập)
  5. `LOC_VAN_DAI_TERRACE_REF_V1`: `UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED` (sha256: null, provider_asset_id: null)
- Tuyệt đối không ghi đè sổ cái chuẩn để giả mạo trạng thái `BOUND` hoặc `OWNER_VISUAL_LOCKED`.

---

## 4. Đánh Giá Kỹ Thuật, Chất Lượng Thị Giác & Hạn Chế Khi Làm Video Conditioning

Qua việc tải và giải mã trực tiếp 4 tệp ảnh, Worker rút ra các đánh giá kỹ thuật trung thực:

### 4.1. Điểm đạt (Ưu điểm thị giác):
1. **Chất liệu da (Skin Texture):** Da mặt nhân vật đạt tiêu chí Owner mong muốn — chất da mờ (matte), có lỗ chân lông và tông da tự nhiên, chấm dứt hoàn toàn hiện tượng da nhựa bóng (plastic/shiny waxy skin) của các bản phác thảo cũ.
2. **Khí chất Tiên hiệp & Trang phục:** Bạch Y Kiếm Tu thể hiện tốt tà áo sáng màu lụa mỏng viền chỉ bạc, búi tóc ngân quan; Hắc Y Kiếm Tu thể hiện tốt áo vải dệt thô đen, giáp vai da đơn có hoa văn chìm; Vân Đài thể hiện được sàn đá tròn có phù điêu cổ phong, đỉnh núi đá vôi hiểm trở và biển mây cuồn cuộn.

### 4.2. Rủi ro & Hạn chế nghiêm ngặt khi dùng làm Video Conditioning:
1. **Rủi ro giống mặt nhau (Facial Twin Archetype Drift):**
   - Hai nhân vật Lý Phá Vân và Dạ Vô Nhai được sinh trong CÙNG MỘT bức triptych của ChatGPT. Cấu trúc khung xương mặt (góc cằm, sóng mũi, nhân trung, dáng lông mày) gần như giống hệt nhau, chỉ khác sắc độ da, kiểu tóc và trang phục.
   - Khi đưa vào mô hình video conditioning (như Veo 2 hoặc Seedance v2.0), nếu không kiểm soát chặt chẽ bằng prompt/mask, mô hình video rất dễ bị nhầm lẫn danh tính giữa hai kiếm thủ trong các cảnh quay cự ly trung bình (MS/TWO_SHOT).
2. **Hạn chế độ phân giải chân dung (Sub-1024px Portrait):**
   - Ảnh Lý Phá Vân đạt `765 x 626`, Dạ Vô Nhai đạt `762 x 626`. Cả hai đều dưới chuẩn master chân dung `1024x1024` hoặc `1280x720`. Khi dùng làm frame conditioning cho video HD 1080p, chi tiết khuôn mặt có thể bị mờ hoặc bị mô hình video nội suy lệch nét.
3. **Hạn chế góc nhìn đơn độc (Single-Angle Limitation):**
   - Cả hai nhân vật chỉ có 1 góc nhìn bán thân 3/4 đang hướng kiếm về phía trước; thiếu hoàn toàn ảnh chính diện (front portrait), ảnh góc nghiêng (profile) và ảnh toàn thân (full-body turnaround).
4. **Hạn chế bối cảnh Vân Đài (Ultra-Wide Letterbox Aspect Ratio):**
   - Ảnh Vân Đài có kích thước `1536 x 389` (tỷ lệ siêu rộng ~ `3.95:1`). Chiều cao chỉ có 389px, quá hẹp so với khung hình chuẩn `16:9` (`1920x1080` hoặc `1280x720`). Nếu đưa trực tiếp làm conditioning cho video 16:9, khung hình sẽ bị cắt xén trầm trọng (crop dọc) hoặc bị biến dạng méo hình.

---

## 5. Kết Quả Kiểm Thử (Test Evidence)

Toàn bộ kiểm thử hồi quy và kiểm thử khép kín đều đạt trạng thái `ALL PASS`:
1. `tests/test_xianxia60_candidate_import.py`: **5/5 PASS** (xác minh tệp staging, hash SHA-256, schema AssetV1, không fake ID, bảo vệ trạng thái UNBOUND).
2. `tools/validate_xianxia60_lookdev.py`: **PASS** (5/5 reference UNBOUND, 12/12 ShotSpecs mapped, master compilation hash giữ nguyên).
3. `tests/test_xianxia60_look_development.py`: **8/8 PASS**.
4. `tests/test_xianxia60_compilation.py`: **16/16 PASS**.
- **Tổng cộng: 29/29 tests PASS clean trong 4.04s.**
- Khế ước tổng thể `XIANXIA60_COMPILATION.json` giữ nguyên SHA-256: `f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b`.

---

## 6. Đề Xuất Bước Nhỏ Nhất Để Có Footage XIANXIA60 Thật (Next Critical-Path Step)

Để tiến tới cảnh quay video thực tế đầu tiên mà không lãng phí chi phí hay phạm quy chế:

1. **Owner Visual Review:** Owner xem xét độc lập 3 ảnh crop và xác nhận liệu diện mạo khuôn mặt hiện tại (dù có rủi ro hơi giống nhau) đã đủ để làm mốc thử nghiệm hay chưa.
2. **Thử nghiệm căn chỉnh video 1-shot (Single Calibration Shot):**
   - KHÔNG generate 12 shot cùng lúc.
   - Chọn **DUY NHẤT 1 cảnh cận đơn (CU/MCU)** — ví dụ **Shot X04** (Lý Phá Vân thủ thế kiếm) hoặc **Shot X08** (Dạ Vô Nhai tụ khí), sử dụng ảnh crop chân dung tương ứng làm start frame/reference condition trên route miễn phí được cấp phép rõ ràng.
   - Đánh giá khả năng bám giữ gương mặt của mô hình video trước khi quyết định sinh tiếp các shot còn lại.
3. **Nếu độ phân giải hiện tại chưa đạt:** Cần sinh bổ sung đúng **2 ảnh chân dung chính diện chuẩn 1024x1024** cho 2 nhân vật (và 1 ảnh Vân Đài tỷ lệ 16:9) theo gói đề xuất Option B đã được phê duyệt sơ bộ.
