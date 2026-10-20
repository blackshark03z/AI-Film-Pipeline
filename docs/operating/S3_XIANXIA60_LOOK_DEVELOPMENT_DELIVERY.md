# BÁO CÁO TIỀN KỲ: THIẾT KẾ NGOẠI HÌNH & KIỂM KÊ REFERENCE REFERENCE PREFLIGHT
## DỰ ÁN PHIM *NHẤT KIẾM PHÁ VÂN* (XIANXIA60 — 60.0 GIÂY / 12 SHOT DUEL)

**Ngày báo cáo:** 2026-10-20  
**Người thực thi:** Gemini Flash 3.8 (Worker)  
**Worker worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`  
**Worker branch / commit:** `feature/film120-gemini-realshot-001`  
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Blob SHA: `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`)  
**Frozen Work Package:** `docs/operating/TASK_S3_XIANXIA60_LOOK_REFERENCE_PREPROD.md`  
**WP SHA-256:** `d074e73da28e245c5f6223cc35f558dc9a202715c3536f488f8f635401d5cdb3`  
**Trạng thái hệ thống:** `LOOK_DEVELOPMENT_PACKAGE_PRODUCED` / `REFERENCE_PREFLIGHT_FAIL_CLOSED` / `OWNER_LOOK_LOCK_PENDING`  
**Giới hạn tuân thủ:** **0 REQUEST MẠNG TỚI PROVIDER, $0 CHI PHÍ PHÁT SINH, 0 TRUY CẬP CREDENTIAL/SESSION, 0 MUTATION DỮ LIỆU PHIM 120S CŨ**.

---

## 1. Kết Quả Kiểm Tra Preflight & Thẩm Quyền (Preflight Truth)

| Tham Số Kiểm Tra | Giá Trị Thực Tế | Tình Trạng |
| :--- | :--- | :--- |
| **POLICY_REF** | `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` | `git cat-file -e "POLICY_REF^{commit}"` PASS |
| **AGENTS.md Blob SHA** | `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` | Trùng khớp 100% giữa Root HEAD và Worker HEAD |
| **Primary Repository** | `D:\AI FILM MAKER\AI-Film-Pipeline` | `mission/quality-v2-022-120s@b62e6b9bc6ab5ad81484dc88cb260b678c009147` |
| **Worker Worktree** | `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini` | `feature/film120-gemini-realshot-001@aae5febb7dbadbdb41b6d8aa262d2346c19da208` |
| **Frozen Work Package** | `docs/operating/TASK_S3_XIANXIA60_LOOK_REFERENCE_PREPROD.md` | SHA-256: `d074e73da28e245c5f6223cc35f558dc9a202715c3536f488f8f635401d5cdb3` PASS |
| **Master Compilation SHA** | `XIANXIA60_COMPILATION.json` | SHA-256: `f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b` (Bất biến 100%) |
| **Phạm vi bảo toàn** | Bảo toàn nguyên vẹn 100% toàn bộ source phim 120s gardener (`projects/quality_v2_022_longform_120s/`), các thư mục isolated và unwatermarked media | PASS |

> [!IMPORTANT]
> **Tuyên bố bảo vệ an toàn tuyệt đối:**
> Toàn bộ quá trình thực hiện gói công việc này diễn ra hoàn toàn offline. Worker không thực hiện bất kỳ lệnh Generate ảnh/video nào qua API provider, không mở phiên duyệt trình Chrome, không đọc cookie/token cá nhân, không can thiệp tài khoản hoặc proxy.
> Mọi thiết kế ngoại hình và hồ sơ reference đều được ánh xạ qua các model và schema hiện hữu của Film Core (`schemas/character.schema.json`, `schemas/asset.schema.json`, `schemas/shot_spec.schema.json`).

---

## 2. Thiết Kế Ngoại Hình Nhân Vật (Character Look Specifications)

Các hồ sơ nhân vật chuẩn Film Core đã được tạo lập tại `projects/xianxia60_nhat_kiem_pha_van/look_development/` và đạt chuẩn kiểm định JSON Schema Draft 2020-12:

### 2.1. Lý Phá Vân (Bạch Y Kiếm Tu — Protagonist)
- **File khế ước:** [`character_white_cultivator.json`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/look_development/character_white_cultivator.json)
- **Canonical ID:** `WHITE_CULTIVATOR` | **Identity Version:** `v1.0.0-lookdev-draft` | **LookState ID:** `LOOK_WHITE_ROBE_V1`
- **Hình thể & Thần thái:** Độ tuổi 21–24 tuổi (Early 20s), chiều cao 178cm, dáng người thon gọn, thanh thoát, lưng thẳng tắp, trọng tâm cân bằng hoàn hảo. Gương mặt thanh tú, xương hàm thon gọn sắc nét, sống mũi thẳng, đôi mắt quả hạnh đen sâu thẳm, ánh nhìn tĩnh lặng như mặt hồ không gợn sóng ngay cả giữa trận đấu sinh tử. Làn da trắng sứ phản chiếu ánh sương mù sớm.
- **Mái tóc:** Tóc đen tuyền suôn mượt dài ngang lưng, phần đỉnh đầu búi cao gọn gàng trong Ngân Quan (trâm cài bằng bạc khắc hoa văn mây), hai dải lụa đen dài rủ sau lưng bay theo chuyển động thân pháp.
- **Phục trang (Bạch Y Đạo Bào):** 
  - Lớp trong: Áo lót vải lanh thô trắng ngà tự nhiên (`#E0E7ED`).
  - Lớp giữa: Đạo bào lụa mờ màu xanh lam ngọc nhạt (`#81D4FA`), cổ chéo truyền thống.
  - Lớp ngoài: Trường bào thuần bạch lụa crepe dày dặn (`#F8F9FA`), thêu chìm hoa văn mây bạc dọc nẹp áo và tay áo; tà áo nhiều lớp xẻ tà khí động học, tà áo bay bồng bềnh tự nhiên theo gió núi (không bóng loáng polyester kiểu anime).
  - Thắt lưng: Đai lụa trắng bản rộng có móc ngọc bội bạch ngọc viền bạc sẫm (`#CFD8DC`).
  - Hộ oản: Bao tay da thuộc màu bạc sẫm siết chặt cổ tay, bảo vệ khớp tay khi đỡ đòn.
  - Hài: Hài vải chiến đấu đế mỏng màu đen, viền trắng, di chuyển nhẹ nhàng không tiếng động.
- **Binh khí (Thanh Sương Kiếm / Phá Vân Kiếm):** Trường kiếm hai lưỡi dài 92cm, bản rộng 3.2cm, trọng lượng 1.1kg. Lưỡi kiếm rèn thép vân gấp Damascus ánh lạnh; chuôi kiếm bằng ngọc cừu trắng (white mutton-fat jade) bọc chỉ bạc mảnh; bao kiếm gỗ trăn sơn mài trắng mờ bọc bạc khắc mây.
- **Kiếm khí (Pale Azure Qi `#81D4FA`):** Dạng sợi tơ pha lê và dải lụa mỏng sắc bén ngưng tụ sát thân kiếm (2–5cm), phát ra tiếng ngân tần số cao (harmonic hum), để lại những đường cắt sắc lẹm trong sương mù.
- **Ngữ pháp võ thuật:** Tiêu sái, trầm tĩnh, dĩ nhu khắc cương, bộ pháp lướt trên đá vững vàng không rung lắc đầu/thân; hóa giải các đòn chém nặng bằng chuyển động góc tối thiểu; kiên nhẫn tìm điểm sơ hở và kết thúc bằng một chiêu phản kích quyết định (*Nhất Kiếm Phá Vân*) tại X10.
- **Quy tắc cấm (Identity Negatives):** Tuyệt đối không la hét giận dữ, không vung kiếm mất kiểm soát, không tóc nhọn dựng đứng kiểu hoạt hình, không vòng sáng hay cánh phát sáng, trang phục không bị rách hay vấy bẩn bùn đất.

### 2.2. Dạ Vô Nhai (Hắc Y Kiếm Tu — Antagonist)
- **File khế ước:** [`character_black_cultivator.json`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/look_development/character_black_cultivator.json)
- **Canonical ID:** `BLACK_CULTIVATOR` | **Identity Version:** `v1.0.0-lookdev-draft` | **LookState ID:** `LOOK_BLACK_ROBE_V1`
- **Hình thể & Thần thái:** Độ tuổi 27–29 tuổi (Late 20s), chiều cao 185cm, vóc dáng vạm vỡ, bờ vai rộng dày cơ bắp, thế đứng hạ thấp trọng tâm vững như bàn thạch. Gương mặt góc cạnh, gò má cao sắc lạnh, hốc mắt sâu với ánh nhìn chim ưng dữ dội và kiên định, cằm chẻ cương nghị; phong thái bá đạo, từng trải sương gió sa trường. Nước da bánh mật sương gió (weathered pale olive).
- **Mái tóc:** Tóc đen thô cứng dài chấm vai, nửa trên buộc gọn bằng kẹp sắt huyền thiết xám, các lọn tóc mai rối tự do quất mạnh theo gió bão ngang gò má.
- **Phục trang (Huyền Sắc Võ Bào):** 
  - Lớp trong: Áo bó sát bằng vải twill màu xám than củi (`#2B2B2B`).
  - Lớp ngoài: Trường bào huyền sắc dệt thô nặng màu đen hắc diệu thạch (`#1C1D21`), tà áo viền sờn chịu ma sát; tà sau xẻ đôi linh hoạt cho các bước chém áp sát uy lực.
  - Giáp vai (Single Pauldron): Vai phải mang giáp da thuộc đen luộc cứng đính đinh tán đồng cổ (`#3E2723`), dây đai da bắt chéo trước ngực.
  - Thắt lưng: Đai da dày có khóa sắt đôi đồng thau sẫm.
  - Hộ thủ & Chiến ngoa: Hộ thủ da đen có nẹp thép mỏng bảo vệ gân tay; ủng chiến đấu mũi bọc sắt dày bám chắc khe nứt đá granite.
- **Binh khí (Huyền Minh Kiếm / Trảm Đoán Kiếm):** Trọng kiếm hai tay dài 105cm, bản rộng 14cm, dày 1.2cm, trọng lượng 4.8kg. Lưỡi kiếm bằng huyền thiết thiên thạch xám đen lì (`#546E7A`) có rãnh huyết tống sâu; chuôi kiếm dài 32cm bọc da cá đuối xám thô chống trượt; đốc kiếm hình khối cầu sắt nặng đối trọng; bao kiếm da bò viền đồng đeo chéo lưng.
- **Kiếm khí (Dark Purple Qi `#6A1B9A`):** Dạng hơi sương nén đậm đặc và sóng xung kích biến dạng không gian bán kính 30–60cm quanh thân kiếm; tạo khiên chắn khí hình mạng nhện nén chặt tại X06.
- **Ngữ pháp võ thuật:** Áp đảo, dũng mãnh, đại khai đại hợp, bộ pháp dậm chắc truyền lực từ nền đá lên lưỡi kiếm; dùng áp lực liên tục dồn ép đối thủ; sau khi khiên khí bị xuyên thủng tại X10, thu kiếm quỳ một gối tâm phục khẩu phục trong danh dự tại X11.
- **Quy tắc cấm (Identity Negatives):** Tuyệt đối không cười cợt phản diện hoạt hình, không biến hình ma quỷ hay mọc sừng, không hoảng loạn bỏ chạy, không giáp sắt hiện đại hay phụ kiện cơ khí.

---

## 3. Thiết Kế Đấu Trường Vân Đài (`LOC_VAN_DAI_TERRACE`) & Bố Cục Máy Quay

- **File khế ước:** [`location_van_dai_terrace.json`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/look_development/location_van_dai_terrace.json)
- **Bối cảnh:** Đỉnh núi thiêng cao ~2,800m vượt lên trên biển mây cuộn trào vô tận.
- **Kiến trúc & Địa chất:** Quảng trường tròn đường kính 30m lát đá granite xám sẫm ngàn năm rêu phong khô, có các đường rãnh khắc hoa văn hình học Bát Quái trận pháp mờ nhạt. Lan can đá thấp (0.7m) viền quanh rìa vực, vách đá dựng đứng chìm trong sương trắng.

### 3.1. Các Mốc Không Gian Cốt Lõi (Cardinal Landmarks)
1. **Mốc Bắc (North — Hậu cảnh vô tận):** Vực sâu mở ra biển mây cuộn sóng, các đỉnh núi nhọn hoắt đâm xuyên tầng mây mù ở đường chân trời xa.
2. **Mốc Nam (South — Vùng an toàn của máy quay):** Lưng chừng vách đá thoải nơi đặt **100% các góc máy quay (azimuth 150°–210°)**, bảo vệ tuyệt đối quy tắc trục hành động 180 độ.
3. **Mốc Tây (West — Cổng vòm đá cổ):** Vòm đá rêu phong, vị trí khởi đầu của Bạch Y (Lý Phá Vân) trong X01–X07, đứng bên trái màn ảnh (screen-left) nhìn về hướng Đông.
4. **Mốc Đông (East — Trụ đá rồng mây):** Thạch trụ cao 4m đón ánh bình minh, vị trí khởi đầu của Hắc Y (Dạ Vô Nhai) trong X01–X07, đứng bên phải màn ảnh (screen-right) nhìn về hướng Tây.
5. **Khu vực trung tâm (Center — Bán kính 8m):** Vòng giao tranh chính, nơi các lưỡi kiếm va chạm, tia lửa bốc lên và khiên khí nứt rạn.

### 3.2. Cú Đảo Trục Không Gian X08 (Aerial Inversion Trajectory)
- Tại shot **X08**, Lý Phá Vân thực hiện cú nhảy phi thân đạp gió lượn hình vòng cung qua đầu Dạ Vô Nhai:
  - *Trước X08:* Bạch Y ở Tây (trái màn ảnh), Hắc Y ở Đông (phải màn ảnh).
  - *Trong X08:* Bạch Y bay vút lên cao xuyên qua sương mù ngược sáng, vượt qua đỉnh đầu Hắc Y.
  - *Sau X08 (X09–X12):* Bạch Y đáp xuống gờ đá Đông (phải màn ảnh) xoay kiếm hướng về Tây; Hắc Y xoay người ở trung tâm/Tây (trái màn ảnh) hướng về Đông.
  - *Trục máy quay:* Vẫn kiên định nhìn từ phía Nam, bảo đảm không xảy ra hiện tượng "nhảy trục" (jump axis) và khán giả luôn nhận thức được vị trí tương quan của hai kiếm sĩ.

### 3.3. Tiến Trình Ánh Sáng Ba Giai Đoạn (Three-Phase Lighting Progression)
- **Giai đoạn 1 (X01–X06 — Căng thẳng & Giao phong):** Ánh sáng sớm lam xám lạnh (6800K), khuếch tán mềm qua lớp sương mù dày, độ tương phản dịu (1.5:1), nhấn mạnh không khí u tịch.
- **Giai đoạn 2 (X07–X09 — Cao trào & Đảo chiều):** Sương mù xoáy tròn vì chấn động kiếm, ánh sáng tạt cạnh (rim light 6200K) rọi lên hạt nước và bụi đá; tia lửa hổ phách bùng lên khi mũi kiếm đâm nứt khiên khí.
- **Giai đoạn 3 (X10–X12 — Phá Vân & Tĩnh lặng):** Đòn kiếm quyết định chém toạc tầng mây; ánh nắng sớm vàng ấm (5200K) từ hướng Đông–Đông Nam tràn ngập thạch đài, Lý Phá Vân tắm mình trong vầng hào quang rực rỡ, Dạ Vô Nhai quỳ gối thanh thản trong bóng râm mờ.

### 3.4. Bảng Phân Bổ Ống Kính Điện Ảnh Cho 12 Cảnh Quay
- **28mm Wide Cine Prime:** `X01` (Thiết lập toàn cảnh đấu trường), `X12` (Dư âm sau trận, Bạch Y bước về chân trời mây).
- **40mm Dynamic Two-Shot:** `X03` (Hắc Y sải bước áp sát), `X08` (Cú nhảy phi thân đảo trục).
- **50mm Engagement Normal:** `X05` (Bạch Y né chém vòng hai), `X06` (Hắc Y mở khiên khí hắc ám), `X09` (Hắc Y xoay người chém cầu vồng).
- **85mm Telephoto Payoff:** `X02` (Rút kiếm ngưng tụ kiếm khí), `X04` (Va chạm tia lửa bắn toé), `X07` (Mũi kiếm đâm nứt khiên chắn), `X10` (Nhất Kiếm Phá Vân đâm thủng màn khí), `X11` (Hắc Y buông kiếm quỳ gối nhận thua).

---

## 4. Gói Ý Niệm Đồ Họa Phục Vụ Owner Duyệt (Owner Concept Package)

Worker đã tạo lập bản vẽ vector kỹ thuật và tài liệu phân tích trực quan:
- **Bản vẽ vector SVG:** [`concept_schematics.svg`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/look_development/concept_schematics.svg)
- **Tài liệu hướng dẫn trực quan:** [`concept_schematics.md`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/look_development/concept_schematics.md)
- **Quy chuẩn màu sắc & Bảng mã Hex:** [`visual_style_bible.json`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/look_development/visual_style_bible.json)

> [!WARNING]
> **Ghi chú bắt buộc:** Toàn bộ các bản vẽ này mang nhãn:  
> `CONCEPT SCHEMATIC — NOT PHOTOREAL IDENTITY REFERENCE (BẢN THIẾT KẾ Ý NIỆM — KHÔNG PHẢI ẢNH NHẬN DIỆN THỰC TẾ)`  
> Đây là tài liệu xác lập tỷ lệ, màu sắc, hình khối phục vụ phê duyệt sáng tạo, không được sử dụng trực tiếp để đưa vào mô hình AI mà chưa có ảnh chụp nhân vật thực tế tương ứng.

---

## 5. Kiểm Kê Reference & Sổ Bộ Tài Sản (Asset Inventory Ledger)

Worker đã rà soát toàn diện kho lưu trữ dữ liệu local của worktree và root repo:
- **Kết quả kiểm kê:** Trong toàn bộ hệ thống cục bộ, **không tồn tại bất kỳ tệp ảnh thực tế nào thuộc thể loại Tiên Hiệp cổ phong** cho Lý Phá Vân, Dạ Vô Nhai hay Vân Đài Terrace.
- **Nguyên tắc bảo toàn tài sản:** Các tệp ảnh/video thuộc dự án phim 120s người làm vườn (`Film120`) và fixture test canary cũ được bảo vệ nghiêm ngặt, tuyệt đối không lấy gán ghép bừa bãi sang phim *Nhất Kiếm Phá Vân*.
- **Sổ bộ tài sản (Asset Ledger):** Được tạo lập tại [`reference_asset_ledger.json`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/projects/xianxia60_nhat_kiem_pha_van/look_development/reference_asset_ledger.json), ghi nhận trung thực 5 tài sản định danh chuẩn:

| Asset ID | Vai Trò Trong Phim | Trạng Thái Binding | File Hash SHA-256 | Quyền & Provenance | Hành Động Kế Tiếp |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CHAR_WHITE_CULTIVATOR_REF_V1` | Nhân diện Lý Phá Vân (Bạch Y) | `UNBOUND` | `None` (Không bịa đặt) | `PENDING_OWNER_PROVENANCE` | `OWNER_IMAGE_SOURCE_REQUIRED` |
| `CHAR_BLACK_CULTIVATOR_REF_V1` | Nhân diện Dạ Vô Nhai (Hắc Y) | `UNBOUND` | `None` (Không bịa đặt) | `PENDING_OWNER_PROVENANCE` | `OWNER_IMAGE_SOURCE_REQUIRED` |
| `WARDROBE_WHITE_ROBE_V1` | Chất liệu Bạch Y Đạo Bào | `UNBOUND` | `None` (Không bịa đặt) | `PENDING_OWNER_PROVENANCE` | `OWNER_IMAGE_SOURCE_REQUIRED` |
| `WARDROBE_BLACK_ROBE_V1` | Chất liệu Huyền Sắc Võ Bào & Giáp Vai | `UNBOUND` | `None` (Không bịa đặt) | `PENDING_OWNER_PROVENANCE` | `OWNER_IMAGE_SOURCE_REQUIRED` |
| `LOC_VAN_DAI_TERRACE_REF_V1` | Không gian Đấu Trường Vân Đài | `UNBOUND` | `None` (Không bịa đặt) | `PENDING_OWNER_PROVENANCE` | `OWNER_IMAGE_SOURCE_REQUIRED` |

- **Phân loại Tier:** Cả 5 tài sản đều ở cấp độ `DESIGN_CANDIDATE`. Không tài sản nào bị khai khống lên `LOCAL_ASSET_VERIFIED`, `OWNER_VISUAL_ACCEPTED` hay `PROVIDER_ATTESTED`.
- **Cơ chế Fail-Closed:** Khi hệ thống không tìm thấy tệp ảnh thật trên đĩa, cổng preflight tự động khóa (`UNBOUND_FAIL_CLOSED`), ngăn chặn hoàn toàn việc gọi nhầm API provider với dữ liệu giả.

---

## 6. Chứng Minh Mapping Film Core Hiện Hữu & Kiểm Thử Độc Lập

### 6.1. Khớp Nối Xuyên Suốt Không Gian — Kịch Bản — Tài Sản
Toàn bộ 12 ShotSpec hiện hữu của XIANXIA60 (`X01.json` đến `X12.json`) đã được kiểm chứng khớp nối 100%:
- `CharacterRef.character_id` (`WHITE_CULTIVATOR`, `BLACK_CULTIVATOR`) trùng khớp với các bản thiết kế `CharacterV1`.
- `CharacterRef.look_state_id` (`LOOK_WHITE_ROBE_V1`, `LOOK_BLACK_ROBE_V1`) trùng khớp với look state trong hồ sơ nhân vật.
- `Environment.location_id` (`LOC_VAN_DAI_TERRACE`) trùng khớp với hồ sơ đấu trường.
- `References.*_asset_ids` khớp nối chính xác với 5 bản ghi trong `reference_asset_ledger.json`.

### 6.2. Công Cụ Tự Động Hóa & Kiểm Định
1. [`tools/build_xianxia60_lookdev.py`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/tools/build_xianxia60_lookdev.py): Công cụ tái tạo toàn bộ gói lookdev ngoại tuyến và có tính tất định cao.
2. [`tools/validate_xianxia60_lookdev.py`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/tools/validate_xianxia60_lookdev.py): Công cụ kiểm định khế ước và cổng fail-closed preflight.
3. [`tests/test_xianxia60_look_development.py`](file:///d:/AI%20FILM%20MAKER/AI-Film-Pipeline-Film120-Gemini/tests/test_xianxia60_look_development.py): Bộ 8 bài test chuyên sâu mới.

### 6.3. Bằng Chứng Kiểm Thử Hồi Quy Toàn Diện (Focused Verification Evidence)
- **Lệnh thực thi:**
  ```powershell
  $env:PYTHONPATH="src;tools"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_film_core_slice.py tests/test_narrative_compiler_021.py tests/test_xianxia60_compilation.py tests/test_xianxia60_look_development.py -v
  ```
- **Kết quả kiểm thử:**
  - `tests/test_film_core_slice.py`: **16/16 PASS**
  - `tests/test_narrative_compiler_021.py`: **15/15 PASS**
  - `tests/test_xianxia60_compilation.py`: **16/16 PASS** (Đã hiệu chỉnh dòng trắng EOF thừa theo đúng chỉ đạo WP)
  - `tests/test_xianxia60_look_development.py`: **8/8 PASS**
  - **TỔNG CỘNG: 55/55 TESTS PASS (100% Không có hồi quy, 0 failure, thời gian chạy 0.68s)**.

---

## 7. Đánh Giá Khả Năng Provider & Giới Hạn Nghiêm Cấm

Dựa trên các khế ước năng lực provider sẵn có trong Film Core (`ProviderCapabilities`):
1. **Chế độ điều hòa tham chiếu (Reference Conditioning):**
   - Với video hành động võ thuật phức tạp (X04 va chạm kiếm, X08 phi thân lộn nhào, X10 đâm phá khiên), provider cần hỗ trợ `supports_image_input: true` và `supports_start_frame: true` để neo giữ ngoại hình trang phục và khuôn mặt nhân vật từ frame đầu tiên.
   - Các điều khiển không được hỗ trợ (như camera trajectory chính xác bằng số) đã được bộ biên dịch hạ cấp an toàn thành mô tả prompt văn bản chi tiết trong `prompt_plans/`.
2. **Hạn mức tài khoản & Chi phí:**
   - Worker báo cáo trung thực: Hạn mức quota, trạng thái tài khoản thực tế và giá tiền hiện tại của Seedance / Kling / Dola là **`UNKNOWN`** do Worker tuân thủ nghiêm ngặt lệnh cấm gọi mạng ra ngoài hoặc đọc session/cookie.
   - **Chi phí phát sinh trong slice này: $0.00**.

---

## 8. Báo Cáo STOP Tại Cổng & Đề Xuất Bước Tiếp Theo Cho Owner

> [!CAUTION]
> **LỆNH DỪNG TẠI CỔNG (STOP AT GATE — OWNER ACTION REQUIRED):**
> Worker đã hoàn thành xuất sắc toàn bộ gói thiết kế ý niệm ngoại hình, bối cảnh đấu trường và kiểm kê reference ngoại tuyến.
> Do chưa có ảnh nhân vật thực tế và chưa được cấp quyền Generate, Worker **DỪNG LẠI TẠI CỔNG** và không tự ý vượt quyền để sinh ảnh/video.

### Đề Xuất 3 Phương Án Hành Động Trình Owner Phê Duyệt:

1. **Phương án A — Owner Cung Cấp Ảnh Nguồn (Khuyến nghị nếu đã có diễn viên):**
   - Owner cung cấp 2 ảnh chân dung cho Lý Phá Vân và Dạ Vô Nhai + 1 ảnh bối cảnh Vân Đài.
   - Worker sẽ tính mã hash SHA-256 thật, đặt vào thư mục assets, chuyển trạng thái sang `LOCAL_ASSET_VERIFIED` và khóa nhận diện nhân vật.

2. **Phương án B — Owner Cấp Quyền Generate Ảnh Chân Dung (Image Reference Sourcing Wave):**
   - Owner cấp quyền cho Tech Lead / Worker chạy một phiên sinh ảnh thử nghiệm ngoại tuyến có kiểm soát (tối đa 4 ảnh cho mỗi nhân vật, ngân sách cap < $1.00) dựa trên đúng prompt chuẩn trong `visual_style_bible.json`.
   - Trình bảng ảnh kết quả để Owner bấm nút khóa ngoại hình chính thức (`OWNER_VISUAL_LOCK`).

3. **Phương án C — Owner Yêu Cầu Chỉnh Sửa Thiết Kế Sáng Tạo:**
   - Nếu Owner muốn thay đổi màu áo, kiểu tóc, dáng kiếm hay màu sắc kiếm khí, Worker sẽ cập nhật lại các bản khế ước JSON/SVG trước khi tìm kiếm ảnh reference.

### Kế Hoạch Sau Khi Có Ảnh Reference:
Ngay sau khi Owner phê duyệt ảnh reference hợp pháp, hệ thống sẽ mở cổng cho **Wave Thử Nghiệm Video Giới Hạn (Capped Video Calibration Wave)** gồm 3 shot trọng điểm đại diện cho 3 độ khó khác nhau:
- **X04:** Va chạm kiếm trực diện và tia lửa (Độ khó va chạm vật lý).
- **X08:** Cú nhảy phi thân đảo trục không gian (Độ khó chuyển động thân pháp).
- **X10:** Nhất Kiếm Phá Vân đâm vỡ khiên khí (Độ khó hiệu ứng kiếm khí và điểm rơi kịch bản).

---
*Báo cáo được đệ trình bởi Gemini Flash 3.8 — Sẵn sàng cho Tech Lead GPT-6 nghiệm thu độc lập.*
