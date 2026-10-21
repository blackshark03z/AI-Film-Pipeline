# GÓI QUYẾT ĐỊNH GATE A — THỬ NGHIỆM VIDEO ĐẦU TIÊN CẢNH X02 (XIANXIA60)
## DỰ ÁN PHIM *NHẤT KIẾM PHÁ VÂN* (60.0 GIÂY / 12 SHOT DUEL)

**Ngày lập gói:** 2026-10-21
**Worker:** Gemini Flash 3.8
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`
**Branch:** `feature/film120-gemini-realshot-001`
**Base commit:** `b6b1be156b4dcfc5f3a9b1fee6de54f5e70936cb`
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Blob SHA: `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`)
**Frozen WP:** `docs/operating/TASK_S3_XIANXIA60_X02_FIRST_VIDEO_CALIBRATION.md` (SHA256: `a26b106a76e3b7deedad88922083b4c14826e40181dc8321ef88c816f8180de7`)
**Trạng thái đề xuất của Worker:** `READY_TO_REQUEST_OWNER_GATE` (Giai đoạn Offline BUILD Stage A hoàn tất 100%; sẵn sàng trình Owner xem xét và phê duyệt mở Gate A).

---

## 1. Nội Dung Kịch Bản Bất Biến & Ánh Xạ Dựng Phim Cảnh X02

### 1.1. Khế ước cảnh quay X02 (`projects/xianxia60_nhat_kiem_pha_van/shots/X02.json`):
- **Shot ID:** `X02` (Phân đoạn `SC_XIANXIA60_DUEL`).
- **Mục tiêu kịch bản:** Bạch Y Kiếm Tu (Lý Phá Vân) cam kết bước vào trận đấu sinh tử; rút trường kiếm thẳng khỏi vỏ một cách điềm tĩnh, lưỡi kiếm phát ra một dải kiếm khí thanh lam cực mảnh.
- **Quy cách máy quay:** Cận trung (MCU), ngang tầm mắt (eye-level), tiêu cự chuẩn 50mm, máy quay khóa tĩnh (`locked`).
- **Trục hướng & Tầm nhìn:** Hướng màn hình từ trái sang phải (`left-to-right`), ánh nhìn hướng sang phải (`screen_right`), nằm phía Nam trục đối đầu 180 độ.
- **Trạng thái khởi đầu (Start State):** Kiếm nằm trong bao (`sword_state: "sheathed"`), tay phải đặt trên chuôi kiếm (`pose: "hand_on_sword_hilt"`).
- **Chuỗi nhịp hành động (Action Beats):**
  1. `grip_tighten (~0.5s)`: Ngón tay siết nhẹ quanh chuôi kiếm bọc chỉ bạc, ngón cái bật nhẹ hộ thủ.
  2. `blade_draw (~1.5s)`: Rút lưỡi kiếm thẳng hai lưỡi ra khỏi vỏ với đường chuyển động tuyến tính dứt khoát.
  3. `guard_lock (~3.2s)`: Mũi kiếm dừng ở góc thủ thế 45 độ hướng sang phải, kiếm khí thanh lam nhạt bùng lên dọc sống kiếm.
- **Trạng thái kết thúc (End State):** Kiếm đã rút sạch khỏi vỏ (`sword_state: "drawn_cleanly"`), thủ thế 45 độ (`pose: "straight_guard_at_45_degrees"`), khí thanh lam hoạt hóa (`qi_state: "pale_azure_line_active"`).

### 1.2. Ánh xạ thời lượng: Nguồn Flow 8.0s &rarr; Phim 5.0s (Editorial Trim Buffer):
- **Thời lượng nguồn Provider:** Google Flow Veo 3.1 Lite ở chế độ Thành phần (Ingredients) cố định **8.0 giây**.
- **Thời lượng mục tiêu trong phim:** **5.0 giây** (biên độ an toàn dựng phim `handles_s: 0.25s`, tổng khoảng cần lấy là `5.5 giây`).
- **Khoảng dự phòng cắt gọt (Trim Buffer):** `8.0s - 5.5s = 2.5s`. Biên tập viên và QC sẽ chọn một cửa sổ 5.0s (hoặc 5.5s có handles) liền mạch, đẹp mắt nhất chứa đủ 3 nhịp hành động mà không cần kéo giãn thời gian (time-stretch) nhân tạo.

---

## 2. Dữ Liệu Tham Chiếu & Cảnh Báo Thị Giác Nghiêm Ngặt

### 2.1. Ảnh ứng viên đầu vào:
- **Tệp tin:** `projects/xianxia60_nhat_kiem_pha_van/assets/references/chatgpt_candidates_wave01/XIANXIA60_ChatGPT_Reference_Candidates_v1/ly_pha_van_portrait_candidate.png`
- **Kích thước:** `765 x 626` pixels (RGB PNG, 692,216 bytes).
- **Mã băm SHA-256:** `7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0`.
- **Xuất xứ:** ChatGPT Images composite ID `aaa9a666-817b-4932-9046-1a235e3cbea0`.
- **Trạng thái khế ước:** Được ghi nhận tại `candidate_reference_ledger.json` với vai trò `CANDIDATE_CHAR_WHITE_CULTIVATOR_WAVE01_V1`, trạng thái `UNBOUND`, `provider_attestation_status: "NOT_ATTESTED"`.

### 2.2. Cảnh báo kỹ thuật cốt lõi (Core Physical/Visual Caveats):
1. **CHỈ LÀ THÀNH PHẦN DANH TÍNH (INGREDIENT ONLY), TUYỆT ĐỐI KHÔNG PHẢI START FRAME:**
   - Trong ảnh ứng viên, Lý Phá Vân **ĐÃ RÚT KIẾM VÀ ĐANG CHĨA VỀ PHÍA TRƯỚC**.
   - Trong khi đó, cảnh X02 bắt đầu bằng việc **KIẾM CÒN TRONG VỎ**.
   - Do đó, ảnh này chỉ được đưa vào làm **Thành phần tham chiếu nhận diện (Character / Look Ingredient)** để mô hình học khuôn mặt, trang phục, kiểu tóc; KHÔNG ĐƯỢC làm frame đầu (start frame / image-to-video literal pose). Nếu provider ép ảnh thành frame đầu, hành động rút kiếm sẽ bị hỏng hoàn toàn.
2. **Độ phân giải Sub-1024px:** Ảnh đạt 765x626, thấp hơn chuẩn master chân dung 1024px.
3. **Nguy cơ trùng lặp giải phẫu khuôn mặt:** Cùng chung nguồn gốc triptych với Hắc Y Kiếm Tu, cần theo dõi độ sắc nét và phân biệt diện mạo.

---

## 3. Lựa Chọn Tuyến Provider Ưu Tiên & Phương Án Dự Phòng

### 3.1. Tuyến ưu tiên số 1 (Priority Route): Google Flow / Veo 3.1 Lite Ingredients
- **Cơ sở thực chứng:** Đã được chứng minh độc lập tại `docs/sot/film/13_FLOW_NATIVE_UI_QUALIFICATION.md` (ngày 2026-10-02, commit `29018d3340`):
  - Giao diện provider-native UI trên trình duyệt thật (Chrome headful).
  - Chế độ: `Video` &rarr; `Thành phần` (Ingredients / reference-conditioned).
  - Tên mô hình giao diện: `Veo 3.1 - Lite` (wire model: `veo_3_1_r2v_lite`).
  - Quy cách xuất xưởng: 16:9 (1280x720, 720p), thời lượng 8.0s, số lượng `x1` duy nhất.
  - Neo giữ tham chiếu: Upload ảnh và đối soát mã media ID chính xác trong catalog trước khi phát lệnh.
  - Liên kết định danh: Marker duy nhất `[FILM-job_<id>]` trong prompt để đối soát backend catalog `Zzl0ze`.
- **Hạn mức & Chi phí:**
  - Theo tài liệu Google Flow Help chính thức (cập nhật 2026-10-21): **10 credits** cho tài khoản thông thường (hoặc **5 credits** cho tài khoản Ultra) cho mỗi video Lite được tạo.
  - Số lượng tạo: **Đúng 1 video (`x1`)**. Không chạy batch, không tự động retry khi gặp lỗi.

### 3.2. Tuyến dự phòng có điều kiện (Conditional Fallback): Dola / Seedance Video
- Chỉ xem xét nếu trong tương lai có bằng chứng khép kín chứng minh Dola hỗ trợ conditioning ảnh chân dung đạt chuẩn cho cảnh kiếm hiệp mà không bị trôi dạt khế ước. Hiện tại route này chưa đủ bằng chứng tương đương nên **tạm gác lại**.

---

## 4. Chuỗi Quản Lý Xuất Xứ (Lineage) & Kiểm Soát Chất Lượng (QC)

1. **Trước khi dispatch (Pre-dispatch):**
   - Khởi tạo Attempt ID nội bộ duy nhất và marker `[FILM-job_<id>]`.
   - Đối chiếu SHA-256 ảnh upload với ảnh cục bộ (`7cb5c496bb1b...`).
   - Xác nhận readback media ID từ catalog Flow project.
2. **Khi phát lệnh (Dispatch):**
   - Đúng một lệnh Generate duy nhất qua giao diện native UI.
   - Ghi nhận trạng thái: `DISPATCH_RELEASED` &rarr; `ADMISSION_OBSERVED` &rarr; `RENDER_PENDING`.
3. **Thu nạp & Kiểm tra (Acquisition & Decode QC):**
   - Tải tệp MP4 gốc về thư mục staging cục bộ của XIANXIA60.
   - Tính mã băm SHA-256 bất biến của tệp video nhận được.
   - Giải mã toàn bộ tệp qua `ffprobe` / `ffmpeg` không có lỗi frame hoặc lỗi audio.
   - Đo đạc chính xác thời lượng (8.0s), độ phân giải (1280x720), tốc độ khung hình (fps).
4. **Kiểm tra chuyển động & Mỹ thuật (Visual & Narrative QC):**
   - Đối soát 3 nhịp hành động: tay siết chuôi kiếm &rarr; rút kiếm tuyến tính &rarr; kiếm khí thanh lam bùng lên &rarr; thế thủ 45 độ.
   - Kiểm tra giữ nét mặt Lý Phá Vân và tính nguyên vẹn của đạo bào trắng.
   - Lập báo cáo `QCReport` chính thức. Phân biệt rõ `REAL_SOURCE_ACQUIRED` (đã có video thật) với `QC_ACCEPT` (đạt chất lượng dựng phim).

---

## 5. Bảng Kiểm Tra & Thông Tin Cần Owner Phê Duyệt Để Mở Gate A (Checklist)

Tất cả các trường dưới đây hiện ở trạng thái **UNKNOWN** (do tuân thủ nghiêm ngặt quy chế không truy cập tài khoản/phiên làm việc bí mật của Owner). Owner cần điền thông tin và ký duyệt:

- [ ] **Tài khoản Google Flow được Owner phê duyệt:** `___________________________________`
- [ ] **Mã Dự Án Flow (Project ID):** `___________________________________`
- [ ] **Mô hình được chọn trong Giao diện:** `Veo 3.1 - Lite` (`veo_3_1_r2v_lite`)
- [ ] **Chế độ tạo video:** `Thành phần (Ingredients / Reference to Video)`
- [ ] **Tỷ lệ & Độ phân giải:** `16:9` (`1280x720` / 720p)
- [ ] **Số lượng video:** `x1` (Không chọn x2 hoặc x4)
- [ ] **Báo giá Credit hiển thị trên giao diện thực tế:** `_____ credits / video` (Danh nghĩa: 10 credits hoặc 5 credits Ultra)
- [ ] **Số dư Credit hiện khả dụng trong tài khoản:** `_____ credits` (Đảm bảo đủ cho 1 lần chạy)
- [ ] **Phê duyệt tải lên ảnh ứng viên Bạch Y:** `ly_pha_van_portrait_candidate.png` (SHA256: `7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0`)
- [ ] **Mã Media ID của ảnh sau khi đối soát trên Flow:** `___________________________________`
- [ ] **Cam kết giới hạn chi phí:** Tối đa đúng 1 lần phát lệnh, 0 retry tự động.
- [ ] **Chấp thuận điều kiện Fail-Closed:** Dừng lại ngay lập tức nếu xuất hiện Captcha, lỗi mạng, hoặc tài khoản không khớp.

---

## 6. Kết Quả Kiểm Chứng Offline Của Worker

Toàn bộ các khế ước và logic offline đã được kiểm chứng khép kín:
- [`tests/test_xianxia60_x02_gate_a_preflight.py`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/tests/test_xianxia60_x02_gate_a_preflight.py): **5/5 PASS**
- Tổng kiểm thử toàn bộ dự án XIANXIA60: **34/34 PASS** (trong 0.53s).
- Công cụ kiểm tra tiền kỳ [`tools/validate_xianxia60_lookdev.py`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/tools/validate_xianxia60_lookdev.py): **PASS**.
- Sổ cái chuẩn 5 tham chiếu tiếp tục giữ nguyên **5/5 UNBOUND**, zero fake ID.
- Bản tổng hợp `XIANXIA60_COMPILATION.json` giữ nguyên SHA-256 bất biến: `f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b`.

---

## 7. Kết Luận & Đề Xuất Bước Kế Tiếp

Worker khuyến nghị trạng thái: **`READY_TO_REQUEST_OWNER_GATE`**

**Bước đi tiếp theo trên con đường xung yếu (Critical Path):**
1. Tech Lead nghiệm thu Gói Gate A này.
2. Owner mở trình duyệt Google Chrome, đăng nhập tài khoản Google Flow đã chọn, mở đúng Project ID, kiểm tra số dư credit hiển thị, tải ảnh Bạch Y lên và xác nhận bảng kiểm tra Gate A.
3. Sau khi có lệnh phê duyệt Gate A chính thức từ Owner, Worker sẽ thực thi đúng 1 lượt phát lệnh duy nhất theo khế ước, thu nạp video và tiến hành đánh giá QC.
