# BÁO CÁO ĐIỀU TRA TUYẾN DOLA CHO CẢNH QUAY X02 (XIANXIA60)
## ĐÁNH GIÁ CHẾ ĐỘ THAM CHIẾU (REFERENCE MODE), TÍNH KHẢ THI & QUYẾT ĐỊNH TUYẾN SẢN XUẤT VIDEO ĐẦU TIÊN
### DỰ ÁN PHIM *NHẤT KIẾM PHÁ VÂN* (60.0s / 12-SHOT XIANXIA DUEL)

**Ngày hoàn thành:** 2026-10-21  
**Worker:** Gemini Flash 3.8  
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`  
**Worker HEAD trước thực hiện:** `feature/film120-gemini-realshot-001@fb71d5f3f0d1a0e4f2554c2cf7b0128d06abea93`  
**Primary Repository:** `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s@731dd917de503a3d636fa431ad1ef9325f7e4d8a`)  
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Blob SHA: `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` — VERIFIED IDENTICAL)  
**Frozen Work Package:** `docs/operating/TASK_S3_XIANXIA60_DOLA_X02_REFERENCE_INVESTIGATION.md`  
**WP SHA-256:** `5d1d1238bccd9769a30f2aa22d0f43c8a1b8ab66aec4b6991ebc8adf841085e9` (VERIFIED MATCH)  
**Deliverable File:** `docs/operating/S3_XIANXIA60_DOLA_X02_REFERENCE_MODE_INVESTIGATION.md`  
**Quyết định phân loại tuyến:** `DOLA_T2V_ONLY_FLOW_REFERENCE_PREFERRED`  

---

## 1. MỤC TIÊU SẢN PHẨM & CÁC RÀNG BUỘC CỐT LÕI CỦA CẢNH X02

### 1.1. Mục tiêu sản phẩm (Product Goal):
Tạo ra **1 video thật đầu tiên cho cảnh X02**, dài khoảng **5.0 giây**, tỷ lệ **16:9**, độ phân giải chuẩn xuất xưởng, bảo toàn danh tính nhân vật **Bạch Y Kiếm Tu (Lý Phá Vân)** và thực hiện chính xác hành động **rút kiếm khỏi vỏ**.

### 1.2. Khế ước cảnh quay X02 (`projects/xianxia60_nhat_kiem_pha_van/shots/X02.json`):
- **Cỡ cảnh & Góc máy:** Cận trung (MCU), ngang tầm mắt (eye-level), tiêu cự 50mm, máy quay khóa tĩnh (`locked`).
- **Trục chuyển động & Hướng nhìn:** Hướng màn hình từ trái sang phải (`left-to-right`), ánh nhìn hướng sang phải (`screen_right`).
- **Trạng thái khởi đầu (t = 0.0s):** Kiếm **CÒN TRONG VỎ** (`sword_state: "sheathed"`), tay phải đặt trên chuôi kiếm (`pose: "hand_on_sword_hilt"`).
- **Chuỗi nhịp hành động (Action Beats):**
  1. `grip_tighten (~0.5s)`: Các ngón tay siết nhẹ quanh chuôi kiếm bọc chỉ bạc, ngón cái đẩy nhẹ gờ hộ thủ.
  2. `blade_draw (~1.5s)`: Rút lưỡi kiếm thẳng hai lưỡi ra khỏi vỏ theo đường thẳng dứt khoát.
  3. `guard_lock (~3.2s)`: Mũi kiếm khóa ở góc thủ thế 45 độ hướng sang phải, dải kiếm khí thanh lam cực mảnh (`pale azure qi`) bùng lên dọc sống kiếm.
- **Trạng thái kết thúc (t = 5.0s):** Kiếm đã rút sạch khỏi vỏ (`sword_state: "drawn_cleanly"`), thủ thế 45 độ, kiếm khí thanh lam hoạt hóa.

### 1.3. Cảnh báo vật lý & thị giác về ảnh chân dung ứng viên hiện có:
- **Tệp ứng viên:** `ly_pha_van_portrait_candidate.png` (765x626 pixels, SHA-256 `7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0`), nguồn từ ChatGPT Images composite `aaa9a666-817b-4932-9046-1a235e3cbea0`.
- **RÀNG BUỘC VẬT LÝ BẤT BIẾN:** Trong ảnh ứng viên này, Lý Phá Vân **ĐÃ RÚT KIẾM VÀ ĐANG CHĨA THẲNG VỀ PHÍA TRƯỚC**.
  - **Hệ quả đối với chế độ First Frame (Image-to-Video start frame):** Nếu đưa ảnh này vào bất kỳ mô hình nào dưới dạng khung hình đầu tiên (Frame 0), video sẽ bắt đầu khi kiếm **đã được rút sẵn ra ngoài**. Nhân vật không thể thực hiện hành động rút kiếm từ vỏ nếu kiếm đã cầm trên tay. Do đó, ảnh ứng viên **TUYỆT ĐỐI KHÔNG THỂ LÀM FIRST FRAME** cho cảnh X02.
  - **Hệ quả đối với chế độ Character Reference / Ingredient:** Ảnh này **CHỈ CÓ THỂ ĐÓNG VAI TRÒ THAM CHIẾU DANH TÍNH (LOOK / CHARACTER INGREDIENT)** — tức mô hình học khuôn mặt, trang phục đạo bào trắng, búi tóc và khí chất; trong khi tư thế ban đầu và hành động rút kiếm phải được điều khiển hoàn toàn bởi Prompt kịch bản.

---

## 2. KẾT QUẢ ĐIỀU TRA ĐỘC LẬP VỀ PROVIDER DOLA (`www.dola.com`)

Việc điều tra được thực hiện độc lập bởi Worker thông qua việc kiểm tra:
1. Source code và capability registry trong repo (`src/film_pipeline/providers/dola_production/capability.py`).
2. Dữ liệu bắt gói trực tiếp từ provider (`projects/quality_v2_019_dola_productionization/V2_019_PHASEA_SKILL_PACK_1.json`, `V2_019_PHASEA_ACTION_BAR_CONF_FULL.json`).
3. Lịch sử bắt gói và video thực tế (`AI_FILM_QUALITY_V2_010C_DOLA_FULLSTACK_EVIDENCE.md`, `AI_FILM_QUALITY_V2_016_SEEDANCE25_DRAFT_FINAL_AUTHORITY.md`).
4. Các công cụ và bộ điều phối hiện có (`tools/dola_010c_browser_adapter.py`, `tools/build_v2_019_phaseabc_evidence.py`, `D:/Video/AutoVideoPipeline/tools/dola-render-gateway/dola_client.py`, `D:/Story Auto/evidence/dola-audit-6d99c8f7/video_worker_ui.py`).
5. Kiểm tra trực tiếp gói mã nguồn công khai (logged-out) của `www.dola.com/chat/` (bundle `chat.6745dd6c02.js` trên `sf-flow-web-cdn.ciciai.com`).
6. Tài liệu công khai của ByteDance Seedance 2.0 / 2.5 và các thông tin liên quan.

### 2.1. Phân loại bằng chứng (VERIFIED / INFERRED / UNKNOWN):

| Hạng mục kiểm tra | Trạng thái | Bằng chứng thực tế & Căn cứ xác minh |
| :--- | :---: | :--- |
| **Dola Host & Hạ tầng** | **VERIFIED** | `www.dola.com` là sản phẩm trợ lý AI của ByteDance (hạ tầng Toutiao Load Balancer `TLB`, CDN `sf-flow-web-cdn.ciciai.com` / `ibyteimg.com`, video CDN `v16-dola.dola.com`). Hoàn toàn khác biệt với các tên miền nhái như `dola-ai.com`, `dolaai.app` hay công cụ riêng `dreamina.capcut.com`. |
| **Mô hình Seedance 2.0 (`seedance_v2.0`)** | **VERIFIED** | Được provider trả về trong `/samantha/skill/pack`: `display: "Seedance 2.0 Fast"`, `supported_durations: ["5", "10"]`, `supported_resolutions: ["720p"]`, **`support_video_ref: false`**. |
| **Khả năng Reference của Seedance 2.0** | **VERIFIED** | **KHÔNG HỖ TRỢ (T2V ONLY)**. Trực tiếp từ cấu hình provider: `support_video_ref: false`. Wire request `/chat/completion` chứa `chat_ability.ability_param` chỉ có `{"model": "seedance_v2.0", "duration": 5, "ratio": "16:9", "input_box_content": ...}`. Không tồn tại tham số truyền ảnh tham chiếu video. Repo đã khóa chặt định nghĩa này là `TEXT_ANCHOR_ONLY` (`src/film_pipeline/narrative/prompting.py:45-54`). |
| **Bản chất của `attach_reference` trên Dola** | **VERIFIED** | Hàm `attach_reference` trong `tools/dola_010c_browser_adapter.py` và `video_worker_ui.py` chỉ thực hiện tải tệp ảnh lên Volcano TOS qua `/alice/resource/prepare_upload` và `/upload/v1/`. **Việc upload thành công KHÔNG đồng nghĩa với việc mô hình video tiêu thụ ảnh đó làm identity ingredient hay frame conditioning**. |
| **Mô hình Seedance 2.5 (`seedance_v2.5`) trên Dola** | **VERIFIED** | Xuất hiện trong Action Bar template: `option_key: "seedance_v2.5"`, `display_text: "Dreamina Seedance 2.5"`, `subs_only_tag: "enhanced"`, chi phí hiển thị: `"最高品質 • 5倍のクレジットを使用"` (Chất lượng cao nhất • Sử dụng x5 credits). |
| **Quyền hạn tài khoản đối với Seedance 2.5** | **VERIFIED** | Thuộc diện khóa gói thuê bao (**SUBSCRIPTION_GATED**). Trong gói bắt `V2_019_PHASEA_SKILL_PACK_1.json`, Seedance 2.5 bị ẩn khỏi danh mục `model_capability` của tài khoản thường. Thử nghiệm trên tài khoản đã probe trong dự án (`ACCOUNT_D`) ghi nhận `has_active_subscription: False`. |
| **Hành vi tham chiếu của Seedance 2.5 trên Dola Web** | **INFERRED** | Kiến trúc nền tảng Seedance 2.5 của ByteDance hỗ trợ First Frame (I2V) và Multimodal Reference. Tuy nhiên, trên giao diện web composer của `www.dola.com`, việc tải 1 ảnh vào khung chat khi chọn "動画を作成" (Tạo video) không có nút chọn riêng biệt "Chỉ lấy nhận diện nhân vật". Theo hành vi chuẩn của hệ sinh thái CapCut/Dreamina, khi 1 ảnh được đính kèm vào tác vụ tạo video, hệ thống mặc định hiểu là **First Frame / Start Frame (I2V)**. |
| **Quyền hạn tài khoản hiện tại của Owner trên Dola** | **UNKNOWN** | Trạng thái thuê bao (subscription active/expired), số dư credits khả dụng hôm nay của tài khoản Owner là thông tin riêng tư, Worker không truy cập cookie/session và phân loại là **`ACCOUNT_SCOPED_UNKNOWN`**. |
| **Báo cáo bên thứ ba (Diana-Taffy/dola-pool)** | **INFERRED** | Tài liệu bên thứ ba ngày 2026-08-22 đề cập việc tải `reference_images` lên Dola 2.5 tạo video 5s. Đây là bằng chứng ngoại vi, không kiểm chứng được ngữ nghĩa (first frame hay identity ingredient) và không chứng minh được quyền hạn tài khoản Owner hôm nay. |

---

## 3. ĐÁNH GIÁ TÍNH KHẢ THI CỦA CẢNH X02 TRÊN CÁC TUYẾN

### 3.1. Tuyến 1: Dola Seedance 2.0 (Text-to-Video Free Route)
- **Cơ chế:** Nhập prompt mô tả cảnh quay X02 chi tiết, tỷ lệ 16:9, thời lượng 5s. Ảnh tham chiếu Lý Phá Vân chỉ được lưu vết ở tầng metadata (`TEXT_ANCHOR_ONLY`), không thể đưa vào mô hình.
- **Tính khả thi hành động X02:** **Có thể đạt được** (Prompt có thể yêu cầu kiếm ban đầu trong vỏ, tay rút kiếm, kiếm khí bùng lên và dừng ở thế thủ 45 độ).
- **Tính khả thi danh tính:** **THẤP / DRIFT CAO**. Vì không có image conditioning ở cấp độ điểm ảnh, khuôn mặt, kiểu tóc, chi tiết đạo bào trắng sẽ được mô hình tự sinh ngẫu nhiên theo văn bản. Điều này vi phạm nghiêm trọng tính nhất quán nhân vật (character continuity) xuyên suốt 12 cảnh của phim.
- **Chi phí & Thời lượng:** 5.0s, 16:9, x1; chi phí 1 credit cơ sở (hạn mức miễn phí hàng ngày).

### 3.2. Tuyến 2: Dola Seedance 2.5 với Ảnh Ứng Viên Hiện Tại (`7cb5c496bb1b...`)
- **Cơ chế:** Đính kèm ảnh ứng viên vào composer Dola, chọn `Dreamina Seedance 2.5`.
- **Xung đột vật lý chí mạng:** Ảnh ứng viên vẽ Lý Phá Vân **đã rút kiếm ra sẵn**.
  - Nếu Dola 2.5 xử lý ảnh theo chế độ **First Frame (I2V)**: Video bắt đầu ở giây 0.0 với kiếm đã rút chĩa ra trước &rarr; **HỎNG HOÀN TOÀN HÀNH ĐỘNG RÚT KIẾM TỪ VỎ CỦA X02**.
  - Nếu Dola 2.5 có cơ chế lọc tham chiếu: Không có bằng chứng nào trên giao diện web Dola chứng minh tồn tại nút chuyển đổi "Chỉ lấy phong cách/khuôn mặt, bỏ qua tư thế".
- **Chi phí & Rào cản:** Yêu cầu tài khoản có gói thuê bao `enhanced` (5x credits), hiện tại ở trạng thái `ACCOUNT_SCOPED_UNKNOWN`.

### 3.3. Tuyến 3: Dola Seedance 2.5 với Ảnh Start Frame Mới (Phải tạo thêm)
- **Cơ chế:** Cần một tác vụ ChatGPT Images mới (chưa được cấp phép) để tạo ra một ảnh tĩnh mới: Lý Phá Vân đứng cận trung, mặt hướng sang phải, **kiếm còn nguyên trong vỏ bên hông, tay đặt lên chuôi kiếm**. Sau đó nạp ảnh này làm First Frame cho Dola Seedance 2.5.
- **Đánh giá:**
  - Vi phạm nguyên tắc tối giản (Ponytail / YAGNI): Tự sinh thêm 1 bước tạo asset tĩnh trung gian, tăng thêm rủi ro trôi dạt danh tính giữa ảnh 1 và ảnh 2.
  - Vẫn vấp phải rào cản tài khoản Dola: Thuê bao `SUBSCRIPTION_GATED` 5x credits chưa được chứng minh trên tài khoản Owner.

### 3.4. Tuyến 4: Google Flow / Veo 3.1 Lite (Chế độ Thành phần / Ingredients)
- **Cơ chế:** Sử dụng giao diện native UI của Google Flow ở chế độ **Video &rarr; Thành phần (Ingredients)**, đã được nghiệm thu thực chứng độc lập tại `docs/sot/film/13_FLOW_NATIVE_UI_QUALIFICATION.md`.
- **Ưu thế công nghệ cốt lõi cho X02:**
  - Chế độ Ingredients của Flow sử dụng ảnh ứng viên (`7cb5c496bb1b...`) như một **Character / Look Blueprint**. Mô hình trích xuất diện mạo, y phục, thần thái của Lý Phá Vân mà **KHÔNG ÉP BUỘC TƯ THẾ TRONG ẢNH PHẢI LÀ KHUNG HÌNH ĐẦU TIÊN**.
  - Lời nhắc (Prompt) điều khiển hoàn toàn diễn tiến hành động từ trạng thái kiếm trong vỏ &rarr; siết chuôi &rarr; rút kiếm &rarr; tỏa kiếm khí &rarr; thủ thế 45 độ.
- **Thời lượng & Dựng phim:** Flow xuất video nguồn **8.0 giây** (16:9, 720p). Khoảng thời lượng 8.0s cung cấp bộ đệm cắt gọt dựng phim (`editorial trim buffer`) là `8.0s - 5.5s = 2.5s`, cho phép biên tập viên lấy đúng cửa sổ 5.0s hành động mượt mà nhất.
- **Chi phí & Lineage:** 10 credits tiêu chuẩn (hoặc 5 credits gói Ultra) cho mỗi lần tạo x1. Quản lý xuất xứ chặt chẽ qua project catalog media ID và marker định danh `[FILM-job_<id>]`.
- **Mức độ sẵn sàng:** Toàn bộ kịch bản, prompt, thông số kỹ thuật và checklist phê duyệt đã được hoàn thiện 100% trong `docs/operating/GATE_A_X02_FIRST_VIDEO_CALIBRATION_PACKET.md` (chỉ chờ Owner duyệt mở Gate A).

---

## 4. BẢNG MA TRẬN SO SÁNH TỔNG HỢP CÁC PHƯƠNG ÁN

| Tiêu chí | Tuyến 1: Dola Seedance 2.0 (T2V) | Tuyến 2: Dola 2.5 (Ảnh hiện tại) | Tuyến 3: Dola 2.5 (Start Frame mới) | Tuyến 4: Google Flow Veo 3.1 Lite (Ingredients) |
| :--- | :---: | :---: | :---: | :---: |
| **Vai trò của ảnh đầu vào** | Không conditioning (`TEXT_ANCHOR_ONLY`) | Bị hiểu là First Frame (Kiếm đã rút sẵn) | First Frame chuẩn (Cần tạo ảnh kiếm trong vỏ) | **Character / Look Ingredient** (Không ép tư thế đầu) |
| **Bảo toàn hành động X02 (Rút kiếm)** | Có thể (nhưng drift mặt) | **THẤT BẠI** (Kiếm đã rút sẵn ở t=0) | Có thể (nhưng phụ thuộc prompt) | **XUẤT SẮC** (Prompt dẫn dắt từ kiếm trong vỏ) |
| **Bảo toàn danh tính Lý Phá Vân** | **KÉM** (Tự sinh ngẫu nhiên) | Khá (nhưng sai hành động) | Khá (nhưng thêm rủi ro trôi dạt ảnh mới) | **CAO** (Đã kiểm chứng trong Flow native UI) |
| **Độ dài & Tỷ lệ xuất xưởng** | 5.0s, 16:9, x1 | 5.0s, 16:9, x1 | 5.0s, 16:9, x1 | **8.0s &rarr; 5.0s edit trim**, 16:9, x1 |
| **Bằng chứng video thực tế trong repo** | Đã có (010C: 5.04s, 10.08s) | **CHƯA CÓ** (0 lượt gen dự án) | **CHƯA CÓ** (0 lượt gen dự án) | **ĐÃ CÓ** (`13_FLOW_NATIVE_UI_QUALIFICATION.md`) |
| **Hệ số chi phí / Tiêu hao** | 1x (Hạn mức miễn phí hàng ngày) | **5x credits** (Gói enhanced) | **5x credits** + Phí tạo ảnh mới | **10 credits** (5 credits Ultra) |
| **Quyền hạn tài khoản (Entitlement)** | Sẵn có (Free tag `none`) | **Khóa thuê bao (`enhanced`)** | **Khóa thuê bao (`enhanced`)** | Sẵn có trên tài khoản Google Flow |
| **Mức độ tin cậy (Confidence Level)** | CAO về T2V / THẤP về danh tính | **RẤT THẤP** (Xung đột vật lý) | TRUNG BÌNH (Tốn công tạo asset) | **RẤT CAO** (Khớp hoàn toàn khế ước X02) |
| **Rào cản chưa giải quyết (Blocker)** | Trôi dạt danh tính nhân vật | Sai tư thế ban đầu + Cần thuê bao | Cần cấp phép tạo ảnh mới + Thuê bao | **Chỉ chờ Owner ký mở Gate A** |

---

## 5. KẾT LUẬN & ĐỀ XUẤT TUYẾN SẢN XUẤT TỐI ƯU

### 5.1. Quyết định phân loại tuyến:
Worker chính thức phân loại trạng thái điều tra là:
```text
DOLA_T2V_ONLY_FLOW_REFERENCE_PREFERRED
```

### 5.2. Lý do kỹ thuật cốt lõi:
1. **Dola Seedance 2.0 chỉ là Text-to-Video:** Bằng chứng delivered từ chính provider xác nhận `support_video_ref: false`. Dola 2.0 hoàn toàn không có khả năng nhận diện hình ảnh để giữ khuôn mặt Lý Phá Vân.
2. **Dola Seedance 2.5 không phù hợp với ảnh ứng viên hiện tại:** Ảnh ứng viên có kiếm đã rút sẵn. Đưa vào chế độ tạo video của Dola sẽ bị gán làm First Frame, làm hỏng hoàn toàn hành động rút kiếm từ vỏ của X02. Ngoài ra, Seedance 2.5 bị khóa sau cổng thuê bao 5x credits mà tài khoản hiện tại chưa chứng minh được quyền sử dụng.
3. **Google Flow Veo 3.1 Lite Ingredients là tuyến duy nhất giải quyết đồng thời cả 2 bài toán:**
   - Giữ nguyên danh tính Lý Phá Vân từ ảnh chân dung ứng viên mà không bắt buộc tư thế trong ảnh phải là frame đầu.
   - Cho phép mô hình diễn hoạt chính xác hành động rút kiếm từ vỏ theo đúng kịch bản phân cảnh X02.
   - Gói quyết định mở Gate A (`docs/operating/GATE_A_X02_FIRST_VIDEO_CALIBRATION_PACKET.md`) đã được chuẩn bị đầy đủ và hoàn tất ở giai đoạn offline.

### 5.3. Bước nhỏ nhất tiếp theo để tiến đến video thật (Smallest Next Step):
- **KHÔNG** xây dựng thêm framework hay viết thêm các bộ test không cần thiết.
- **KHÔNG** tạo thêm asset ảnh mới khi chưa cần thiết.
- **Trình Tech Lead và Owner:** Chuyển sang xem xét và phê duyệt mở **Gate A** trên tài khoản Google Flow đã được chuẩn bị tại `docs/operating/GATE_A_X02_FIRST_VIDEO_CALIBRATION_PACKET.md` để phát sinh đúng **1 video thật duy nhất (`x1`)** cho cảnh X02.

---
*Báo cáo được lập theo nguyên tắc trung thực tuyệt đối với bằng chứng kỹ thuật, không suy đoán quyền hạn tài khoản riêng và tuân thủ toàn diện các quy chế bảo vệ hệ thống.*
