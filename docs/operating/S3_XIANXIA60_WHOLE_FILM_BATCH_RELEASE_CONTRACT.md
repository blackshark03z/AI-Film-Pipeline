# HỢP ĐỒNG PHÁT HÀNH BATCH TOÀN PHIM XIANXIA60 (X01–X12)
## GÓI ĐIỀU PHỐI SẢN XUẤT XUYÊN SUỐT TIẾN TỚI BẢN PHIM 60 GIÂY HOÀN CHỈNH
### DỰ ÁN PHIM *NHẤT KIẾM PHÁ VÂN* (60.0 GIÂY / 12-SHOT XIANXIA DUEL)

**Ngày lập:** 2026-10-21  
**Worker:** Gemini Flash 3.8  
**Worktree:** `D:/AI FILM MAKER/AI-Film-Pipeline-Film120-Gemini`  
**Worker HEAD trước thực hiện:** `feature/film120-gemini-realshot-001@b6b61d5e15973aeeae53530cf95a7f22ef4378e3`  
**Primary Repository:** `D:/AI FILM MAKER/AI-Film-Pipeline` (`mission/quality-v2-022-120s@c38c60ee867901dd94d0e973a096431f0e97e52b`)  
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Blob SHA: `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` — *VERIFIED IDENTICAL*)  
**Frozen Work Package:** [`docs/operating/TASK_S3_XIANXIA60_WHOLE_FILM_FAST_TRACK.md`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline/docs/operating/TASK_S3_XIANXIA60_WHOLE_FILM_FAST_TRACK.md)  
**WP SHA-256:** `e8b8b9c8330bbc496a9b36d9d905b5f2f88b990efb11b8a65552e575f22c8646` (*VERIFIED MATCH*)  
**Trạng thái phân loại:** `WHOLE_FILM_BATCH_RELEASE_CONTRACT_OFFLINE_PROVEN / SINGLE_FILM_LEVEL_GATE_ACTIVE / VIDEO_MUTATIONS_HELD`  

---

## 1. MỤC TIÊU SẢN XUẤT & NGUYÊN TẮC CHỈ ĐẠO CỦA OWNER

### 1.1. Chỉ đạo chiến lược của Owner:
* **Không làm lẻ tẻ từng shot**, không tổ chức nghiệm thu từng shot và không lặp lại các vòng nghiên cứu provider lý thuyết.
* **Mục tiêu tối thượng:** Tạo ra bộ phim *Nhất Kiếm Phá Vân* hoàn chỉnh, xem được liên tục, có âm thanh đồng bộ, thời lượng chuẩn **55–65 giây** (thiết kế đích: **60.0 giây**).
* **Chủ trương ngân sách:** Cấp quyền sử dụng tối đa hạn mức/quota sẵn có của tài khoản được phép để sản xuất toàn bộ footage của phim; không mua thêm thuê bao mới và không dùng các tài khoản bị hoãn (`deferred`).

### 1.2. Ranh giới thẩm quyền & Bảo vệ hệ thống (Fail-Closed Governance):
* Worker tuân thủ tuyệt đối quy định an toàn: **Không tự ý truy cập session/cookie/DPAPI bí mật, không tự chạy Chrome Dola Capture, không giả mạo số dư tín dụng, không dùng placeholder/slate để giả làm footage**.
* Khi điều kiện tài khoản/tín dụng thực tế chưa được cấp trực tiếp qua phiên làm việc mở, Worker phải **chuẩn bị 100% tài liệu kỹ thuật ở giai đoạn offline (Giai đoạn A & B) và thiết lập DUY NHẤT MỘT CỔNG PHÊ DUYỆT CẤP TOÀN PHIM (Film-Level Release Gate)**. Không xin duyệt lặp lại 12 lần cho từng shot X01–X12.

---

## 2. GIAI ĐOẠN A: KIỂM CHỨNG TOÀN DIỆN 12 CẢNH QUAY & DỮ LIỆU THAM CHIẾU (100% OFFLINE PASS)

Toàn bộ 12 phân cảnh X01–X12 đã được kiểm tra độc lập qua test suite [`tests/test_xianxia60_whole_film_batch_preflight.py`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/tests/test_xianxia60_whole_film_batch_preflight.py) (39/39 tests toàn dự án PASS):

### 2.1. Chuỗi liên tục trạng thái vật lý & kịch bản (11/11 Cuts Unbroken):
1. **X01 (Establishing, WS, 5.0s):** Đối mặt trên đài đá Vân Đài giữa biển mây. Cả hai kiếm tu đứng tĩnh, kiếm **đều còn trong vỏ** (`sheathed`).
2. **X02 (Insert, MCU, 5.0s):** Lý Phá Vân rút kiếm. Khởi đầu kiếm trong vỏ &rarr; siết chuôi &rarr; rút dứt khoát &rarr; kiếm khí thanh lam mảnh (`pale azure qi`) bùng lên, dừng ở thế thủ 45 độ.
3. **X03 (Action, MS, 5.0s):** Dạ Vô Nhai phát động tấn công, lao vút qua trục sân đá với trọng kiếm rút sẵn.
4. **X04 (Action, TWO_SHOT, 5.0s):** Giao kiếm lần một. Hai lưỡi kiếm va chạm tóe lửa, khóa cứng giữa không trung tạo sóng xung kích cục bộ.
5. **X05 (Action, MS, 5.0s):** Lý Phá Vân lướt tránh né xoay người; nhát chém thứ hai của đối thủ bổ xuống mặt đá trống.
6. **X06 (Action, MS, 5.0s):** Dạ Vô Nhai đẩy chưởng trái, kích hoạt màn chắn hộ thân bằng hắc tinh kiếm khí.
7. **X07 (Action, TWO_SHOT, 5.0s):** Mũi kiếm Lý Phá Vân đâm trúng màn hắc khí; vết nứt rạn sáng rực báo hiệu kết cấu khiên bị phá vỡ.
8. **X08 (Action, WS, 5.0s — ĐIỂM ĐẢO VỊ TRÍ CỐT LÕI):** Lý Phá Vân tung mình phi thân trên không, lướt qua đỉnh đầu đối thủ xuyên qua làn sương ngược sáng để **đảo vị trí màn hình**. Trục máy quay khóa chặt ở phía Nam nhìn về Bắc: Bạch Y chuyển từ trái sang phải màn hình; Hắc Y xoay người hướng về phía Đông.
9. **X09 (Action, MS, 5.0s):** Dạ Vô Nhai xoay người quét ngang một luồng hắc kiếm khí hình bán nguyệt bay dọc sân đấu.
10. **X10 (Action, TWO_SHOT, 5.0s — ĐÒN QUYẾT ĐỊNH NHẤT KIẾM):** Lý Phá Vân phát động đòn đâm tuyến tính tối thượng, kiếm khí thanh lam rực sáng xuyên thủng và xé tan luồng hắc khí thành màn sương xám vô hại.
11. **X11 (Reaction, MS, 5.0s — HẬU QUẢ):** Dạ Vô Nhai hạ mũi kiếm chạm đá, quỳ gối chịu thua trong tĩnh lặng.
12. **X12 (Hero, WS, 5.0s — KẾT THÚC):** Lý Phá Vân tra kiếm vào bao bạc, ánh nắng ban mai ấm áp xuyên qua mây rọi xuống hai nhân vật và mặt đài Vân Đài.

*Tất cả 11 điểm nối cảnh (`Cut`) đều đạt độ khớp trạng thái 100% (`X[n].end_state == X[n+1].start_state`).*

### 2.2. Chiến lược sử dụng ảnh tham chiếu (Reference Asset Strategy):
* **Bạch Y Kiếm Tu (Lý Phá Vân):**
  * Tệp ảnh: [`ly_pha_van_portrait_candidate.png`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/assets/references/chatgpt_candidates_wave01/XIANXIA60_ChatGPT_Reference_Candidates_v1/ly_pha_van_portrait_candidate.png) (765x626, SHA-256 `7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0`).
  * **Vai trò:** **Character / Look Ingredient ONLY**. Do trong ảnh kiếm đã rút, ảnh này tuyệt đối không được dùng làm First Frame cho các cảnh kiếm còn trong vỏ (nhất là X01, X02, X12). Nó đóng vai trò cung cấp nhận diện khuôn mặt, trang phục trắng, kiểu tóc cho mô hình học phong cách.
* **Hắc Y Kiếm Tu (Dạ Vô Nhai):**
  * Tệp ảnh: [`da_vo_nhai_portrait_candidate.png`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/assets/references/chatgpt_candidates_wave01/XIANXIA60_ChatGPT_Reference_Candidates_v1/da_vo_nhai_portrait_candidate.png) (762x626, SHA-256 `a89e067c39445c4485aa010d927270d025bc06ccffdc21d5fdc3303d493f3446`).
  * **Vai trò:** **Character / Look Ingredient**.
* **Đài Đá Vân Đài & Bối cảnh tổng thể:**
  * Tệp ảnh: [`van_dai_arena_candidate.png`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/assets/references/chatgpt_candidates_wave01/XIANXIA60_ChatGPT_Reference_Candidates_v1/van_dai_arena_candidate.png) (1536x389, SHA-256 `545d02eda6684c7121f6e49cc8e14057f9ba1630aaad49c073dfbf15a8453694`) và ảnh tổng thể composite [`owner_provisional_composite_source.png`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/assets/references/chatgpt_candidates_wave01/XIANXIA60_ChatGPT_Reference_Candidates_v1/owner_provisional_composite_source.png) (1536x1024, SHA-256 `21f7bcb26510aa110f762a577401b3f042add2916b875fe6eff750077aaaa6ad`).
* **Trạng thái xuất xứ hiện tại:** Đang lưu trong sổ theo dõi ứng viên (`candidate_reference_ledger.json`) với trạng thái `UNBOUND` và `provider_attestation_status: "NOT_ATTESTED"`, chờ bước upload lên catalog của provider.

---

## 3. GIAI ĐOẠN B: LỰA CHỌN TUYẾN SẢN XUẤT DUY NHẤT TOÀN PHIM

Dựa trên kết quả điều tra độc lập đã nộp tại [`docs/operating/S3_XIANXIA60_DOLA_X02_REFERENCE_MODE_INVESTIGATION.md`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/docs/operating/S3_XIANXIA60_DOLA_X02_REFERENCE_MODE_INVESTIGATION.md):

* **Tuyến được chọn: Google Flow / Veo 3.1 Lite (Chế độ Thành phần / Ingredients Mode):**
  * **Đặc tả giao diện chuẩn:** `NativeUiProfile(model='Veo 3.1 - Lite', toggles=['Video', 'Thành phần', '16:9', 'x1'], duration='8 giây', resolution='720p')`.
  * **Cơ chế tham chiếu:** Cho phép truyền ảnh nhân vật làm thành phần nhận diện mà **không ép buộc ảnh phải là khung hình đầu tiên**, giải quyết hoàn hảo xung đột kiếm đã rút của ảnh ứng viên đối với các nhịp kịch bản kiếm trong vỏ.
  * **Quy cách thời lượng:** Provider xuất video nguồn **8.0 giây** (16:9, 720p). Thời lượng mục tiêu trong phim là **5.0 giây** + biên độ dựng `handles: 0.25s` &rarr; tạo ra **bộ đệm cắt gọt (trim buffer) 2.5 giây**, cho phép dựng phim chọn đúng cửa sổ hành động mượt mà và chuẩn xác nhất.
  * **Định mức chi phí:** **10 credits** cho tài khoản chuẩn (hoặc **5 credits** cho tài khoản Ultra) cho mỗi lượt tạo x1.
* **Loại bỏ tuyến Dola:**
  * Dola Seedance 2.0 có năng lực khai báo `support_video_ref: false` (chỉ chạy Text-to-Video, không giữ được khuôn mặt nhân vật qua 12 shot).
  * Dola Seedance 2.5 bị khóa gói thuê bao 5x credits và mặc định hiểu ảnh nạp vào là First Frame (làm sai lệch kịch bản rút kiếm).

---

## 4. GIAI ĐOẠN C: BẢNG ĐIỀU PHỐI BATCH 12 SHOT (X01–X12)

| Thứ tự | Shot ID | Phân loại | Cỡ cảnh | Hướng nhìn | Nhân vật chính | Ảnh tham chiếu nạp vào (Media Role) | Hash PromptPlan (Flow Veo Lite) | Nguồn (s) | Dựng (s) | Trim Buffer |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **X01** | Establishing | WS | Đối diện tĩnh | Bạch Y & Hắc Y | `owner_provisional_composite_source.png` | `96f6fcc563b0f698...` | 8.0s | 5.0s | 2.5s |
| 2 | **X02** | Insert | MCU | Sang phải | Bạch Y (Lý Phá Vân) | `ly_pha_van_portrait_candidate.png` | `360b968d04f35bb4...` | 8.0s | 5.0s | 2.5s |
| 3 | **X03** | Action | MS | Sang trái | Hắc Y (Dạ Vô Nhai) | `da_vo_nhai_portrait_candidate.png` | `72fbb11a50a21b40...` | 8.0s | 5.0s | 2.5s |
| 4 | **X04** | Action | TWO_SHOT | Trái sang phải | Cả hai đấu kiếm | `ly_pha_van_portrait_candidate.png` | `7d3c3f8328e1bcaa...` | 8.0s | 5.0s | 2.5s |
| 5 | **X05** | Action | MS | Trái sang phải | Bạch Y né đòn | `ly_pha_van_portrait_candidate.png` | `5ac334a0ed51ac81...` | 8.0s | 5.0s | 2.5s |
| 6 | **X06** | Action | MS | Sang trái | Hắc Y mở khiên | `da_vo_nhai_portrait_candidate.png` | `a06582d60fc7d9c3...` | 8.0s | 5.0s | 2.5s |
| 7 | **X07** | Action | TWO_SHOT | Trái sang phải | Bạch Y kích khiên | `ly_pha_van_portrait_candidate.png` | `a5dada30d1a025ac...` | 8.0s | 5.0s | 2.5s |
| 8 | **X08** | Action | WS | Phi thân đảo vị trí | Bạch Y phi thân | `ly_pha_van_portrait_candidate.png` | `54b372bfec748b4e...` | 8.0s | 5.0s | 2.5s |
| 9 | **X09** | Action | MS | Phải sang trái | Hắc Y quét kiếm khí | `da_vo_nhai_portrait_candidate.png` | `2c635992051a6ca7...` | 8.0s | 5.0s | 2.5s |
| 10 | **X10** | Action | TWO_SHOT | Quyết đấu Nhất Kiếm | Cả hai đối kích | `ly_pha_van_portrait_candidate.png` | `e0f436fc89b11dac...` | 8.0s | 5.0s | 2.5s |
| 11 | **X11** | Reaction | MS | Nhìn sang phải | Hắc Y quỳ thua | `da_vo_nhai_portrait_candidate.png` | `72cd4a2792fac4df...` | 8.0s | 5.0s | 2.5s |
| 12 | **X12** | Hero | WS | Toàn cảnh bình minh | Bạch Y tra kiếm | `ly_pha_van_portrait_candidate.png` | `be2cee94d3b8fb45...` | 8.0s | 5.0s | 2.5s |

*Tất cả 12 PromptPlans đã được biên dịch tiền khả thi bằng bộ biên dịch `film_pipeline.compiler.compile_prompt` và sẵn sàng nạp trực tiếp vào runtime của Flow khi mở cổng.*

---

## 5. GIAI ĐOẠN D & E: QUY ĐỊNH HẠN MỨC, QC TOÀN DIỆN & HẬU KỲ ÂM THANH

### 5.1. Khung hạn mức sản xuất toàn phim (Production Budget Envelope):
* **Đợt 1 — 12 shot phủ toàn kịch bản (Coverage Wave):** 12 đầu ra video x1.
  * Chi phí ước tính: `12 x 10 = 120 credits` (hoặc `60 credits` gói Ultra).
* **Đợt 2 — Quỹ sửa chữa định hướng QC (Repair Wave):** Tối đa 12 đầu ra video. Chỉ sử dụng cho các lỗi giải phẫu nghiêm trọng, trôi dạt nhân vật không thể chấp nhận hoặc lỗi vật lý phá vỡ tính liên tục.
* **Đợt 3 — Quỹ quay bổ sung/nối cảnh (Pickup Wave):** Tối đa 6 đầu ra video cho các cú máy phản ứng hoặc nhịp chuyển tiếp nếu bản dựng thô cần bù đắp nhịp điệu.
* **TRẦN CỨNG TỐI ĐA (HARD MAX):** **30 đầu ra video** (`300 credits` tiêu chuẩn / `150 credits` Ultra). Chi phí thực tế được chốt theo số dư khả dụng thực tế của tài khoản, không tự nạp thêm tiền.

### 5.2. Tiêu chí kiểm soát chất lượng toàn phim (Film-Wide QC Protocol):
1. **Tính nhất quán trang phục & diện mạo:** Phân biệt rõ ràng Bạch Y (Lý Phá Vân) với vạt áo trắng thêu chỉ bạc và búi tóc kẹp trâm bạc vs Hắc Y (Dạ Vô Nhai) với giáp vai da hắc diện và kiếm bản rộng.
2. **Trục hành động 180 độ & Cú nhảy X08:**
   * Trước X08: Bạch Y bên trái màn hình nhìn sang phải, Hắc Y bên phải nhìn sang trái.
   * Sau cú nhảy X08: Bạch Y tiếp đất bên phải màn hình nhìn sang trái, Hắc Y ở trung tâm chếch trái xoay người nhìn sang phải.
3. **Trạng thái kiếm & kiếm khí:**
   * X01: Kiếm trong vỏ.
   * X02: Rút kiếm, kiếm khí thanh lam mảnh kích hoạt.
   * X08: Kiếm thu dọc cẳng tay khi phi thân.
   * X10: Đâm thẳng, kiếm khí thanh lam xé nát hắc khí.
   * X12: Tra kiếm vào vỏ gọn gàng.

### 5.3. Hậu kỳ dựng phim & Âm thanh hoàn chỉnh (Editorial & Audio Finishing):
* Sử dụng công cụ FFmpeg và Film Core có sẵn (chuẩn xuất xưởng H.264/AAC, 1280x720 24fps).
* Ghép 12 clip theo [`projects/xianxia60_nhat_kiem_pha_van/editorial/edit_manifest.json`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/editorial/edit_manifest.json):
  * `12 clips x 5.0s = 60.0 giây tròn`, hoàn toàn không có text slate hay bảng đen giữ chỗ.
* **Thiết kế âm thanh (Sound Design):**
  * *Room tone / Khí quyển:* Tiếng gió rít trên đỉnh núi cao, tiếng mây mù trôi nhẹ.
  * *Tiếng động chiến đấu (Foley):* Tiếng vải đạo bào bay phần phật, tiếng bước chân giậm mạnh lên phiến đá, tiếng rút kiếm thanh thoát từ bao kim loại, tiếng hai lưỡi kiếm va chạm chan chát tóe lửa.
  * *Kiếm khí & Quyết đấu:* Âm trầm khi vận khí, tiếng kiếm khí xé gió, tiếng nổ tan biến của hắc khí ở cú đâm X10.
  * *Kết thúc:* Tiếng "cạch" dứt khoát khi mũi kiếm tra hết vào vỏ, tiếng gió dịu lại và âm hưởng thanh bình khi ánh nắng chiếu rọi.

---

## 6. ĐIỀU KIỆN CẦN THIẾT DUY NHẤT ĐỂ TIẾN HÀNH SẢN XUẤT (THE ONLY SHIP BLOCKER)

Mọi công tác chuẩn bị cục bộ, biên dịch kịch bản, ánh xạ tham chiếu, định tuyến kỹ thuật và bộ kiểm thử tự động đều đã hoàn tất và vượt qua 100% kiểm định kỹ thuật offline.

Rào cản thực tế duy nhất ngăn Worker tạo footage ngay lúc này là: **Tài khoản Google Flow và phiên làm việc trình duyệt có quota chưa được kết nối trực tiếp vào môi trường thực thi của Worker** (do Worker tuân thủ nghiêm ngặt quy chế bảo mật không được tự ý khai thác session/cookie/DPAPI cá nhân của Owner).

---

### PHIẾU PHÊ DUYỆT MỞ CỔNG PHÁT HÀNH TOÀN PHIM (FILM-LEVEL RELEASE GATE)

*Owner chỉ cần xác nhận MỘT LẦN DUY NHẤT để Worker tiến hành sản xuất toàn bộ chuỗi X01–X12 mà không cần hỏi lại từng cảnh:*

1. **Tài khoản Google Flow được Owner phê duyệt sử dụng:** `[................................................]`
2. **Mã Dự Án Flow (Project ID):** `[................................................]`
3. **Số dư credit khả dụng thực tế:** `[..........]` credits (Yêu cầu tối thiểu 120 credits cho tài khoản thường hoặc 60 credits cho tài khoản Ultra để chạy đợt 1).
4. **Quyền hạn cấp cho Worker:**
   - [x] Cho phép tải 3 ảnh ứng viên (`ly_pha_van_portrait_candidate.png`, `da_vo_nhai_portrait_candidate.png`, `van_dai_arena_candidate.png`) lên catalog của Flow Project.
   - [x] Cho phép gửi batch 12 lệnh Generate tuần tự (`x1`) cho các phân cảnh X01–X12 theo đúng bảng điều phối ở Mục 4.
   - [x] Cho phép sử dụng quỹ sửa chữa (tối đa 12 lần) và quay bổ sung (tối đa 6 lần) nếu phát hiện lỗi vi phạm QC nghiêm trọng.
   - [x] Cho phép tự động dựng phim, đồng bộ âm thanh và xuất bản MP4 60.0s hoàn chỉnh để trình Owner xem xét gói tổng thể duy nhất.

---
*Hợp đồng này được lập nhằm loại bỏ triệt để tình trạng xin duyệt lặp lại nhiều lần, bảo toàn trọn vẹn tài sản và chính sách dự án, đưa dự án thẳng tiến tới bản phim xem được đầu tiên.*
