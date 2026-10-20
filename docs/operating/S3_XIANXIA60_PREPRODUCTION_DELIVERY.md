# S3 XIANXIA60 — BÁO CÁO TIỀN KỲ & HIỆU CHỈNH CONTINUITY TOÀN PHIM QUA FILM CORE
## *Nhất Kiếm Phá Vân* (60.0 giây / 12 Cảnh / Hai Nhân Vật Giao Đấu)

**Ngày báo cáo:** 2026-10-20
**Người thực thi:** Gemini Flash 3.8 (Worker)
**Worker worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`
**Worker branch / commit:** `feature/film120-gemini-realshot-001`
**Trạng thái hệ thống:** `FILM_CORE_TECHNICAL_PASS` / `PREPROD_CONTINUITY_RECONCILED` / `OWNER_CREATIVE_LOCK_PENDING`
**Giới hạn quyền hạn:** **0 REQUEST GENERATE RA NGOÀI, $0 CHI PHÍ PHÁT SINH, KHÔNG TRUY CẬP CREDENTIAL/SESSION**.

---

## 1. Kết Quả Kiểm Tra Preflight & Thẩm Quyền (Preflight Truth)

| Tham Số | Giá Trị Kiểm Chứng Thực Tế | Tình Trạng |
| :--- | :--- | :--- |
| **POLICY_REF** | `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` | `git cat-file -e "POLICY_REF^{commit}"` PASS |
| **AGENTS.md Blob SHA** | `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` | Trùng khớp 100% giữa Root HEAD và Worker HEAD |
| **Primary Repository** | `D:\AI FILM MAKER\AI-Film-Pipeline` | `mission/quality-v2-022-120s@df8dc8880e2030d6353e44d2f10b833ac38590d3` |
| **Worker Worktree** | `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini` | `feature/film120-gemini-realshot-001@24294f15e96a2e1073c4bcb876a036c6d9da7651` |
| **Frozen Work Package** | `docs/operating/TASK_S3_XIANXIA60_ONE_FILM_PRODUCTION_PACKAGE.md` | SHA-256: `44397bc35d8f36e4fa86fffcfd70c1b62f41db3443279a4b6046a265c77492f2` PASS |
| **Phạm vi bảo toàn** | Bảo toàn nguyên vẹn 100% toàn bộ source phim 120s gardener (`projects/quality_v2_022_longform_120s/`), các thư mục isolated, journal, latches | PASS |

> [!IMPORTANT]
> **Không có bất kỳ lệnh Generate video/ảnh nào được gửi tới provider**, không tiêu tốn credit, không đọc session/cookies, không ghi đè bất kỳ file nào thuộc dự án phim 120 giây cũ. Mọi kết quả tiền kỳ và hiệu chỉnh tính liên tục đều được biên dịch ngoại tuyến qua Film Core hiện hữu.

---

## 2. Tổng Quan Kịch Bản & Thiết Kế Phim *Nhất Kiếm Phá Vân*

- **Tựa phim:** *Nhất Kiếm Phá Vân* (One Sword Pierces the Clouds)
- **Thời lượng mục tiêu:** **60.0 giây** (12 shots x 5.0s, nằm trọn vẹn trong khoảng chuẩn 55–65 giây).
- **Thể loại:** Tiên hiệp / Tu chân đấu kiếm (Xianxia Martial Sword Duel).
- **Logline:** Trên đỉnh Vân Đài mù sương giữa biển mây bạt ngàn, hai kiếm tu chính - tà đối quyết trong một trận kiếm pháp sinh tử: từng đường kiếm, từng lần va chạm và phòng hộ bằng chân khí đều có nhân quả chuẩn xác, dẫn tới chiêu thức quyết định phá tan ám kiếm khí, phân định thắng bại trong hư không mây rạng.
- **Bối cảnh duy nhất (Vân Đài - Cloud Terrace):**
  - Đài đá tròn cổ kính bằng đá hoa cương đen, lơ lửng trên đỉnh núi cao giữa biển mây trắng bồng bềnh.
  - Lan can đá thấp, 4 trụ đá phong hóa ở 4 góc trận, hoa văn trận pháp Đạo gia mờ khắc trên nền đá.
  - Ánh sáng ban mai lạnh khuếch tán qua mây mù, gió núi nhẹ làm lay động vạt áo, sương mỏng là là mặt đá. Không có công trình hiện đại, không người thừa, không rác hình ảnh.

### Hai Nhân Vật Đối Kháng
1. **Bạch Y Kiếm Tu (Lý Phá Vân - Protagonist):**
   - *Tạo hình:* Thanh niên tuấn tú, tầm 20–22 tuổi, dáng người thanh mảnh nhưng rắn rỏi, ánh mắt tĩnh tại điềm đạm, tóc đen dài búi trâm bạc có dải lụa đen rủ sau gáy.
   - *Y phục:* Đạo bào màu trắng tinh khôi xếp lớp, cổ áo và cổ tay thêu hoa văn mây bạc nhạt, hộ uyển da bạc sẫm, đai lưng lụa trắng, hài nhẹ.
   - *Vũ khí & Khí:* Thanh kiếm thẳng truyền thống (Chính Đạo Thanh Kiếm) lưỡi thép bóng loáng, bao kiếm bọc bạc. Thanh Vân Kiếm Khí (pale azure / luminous white qi) mỏng như lưỡi dao cạo bám sát lưỡi kiếm.
   - *Phong cách:* Thân pháp né tránh linh hoạt, kiếm chiêu chuẩn xác, phòng ngự phản công bằng một kiếm quyết định.
2. **Hắc Y Kiếm Tu (Dạ Vô Nhai - Antagonist):**
   - *Tạo hình:* Nam tử sắc sảo, tầm 27–29 tuổi, thể hình vạm vỡ uy mãnh, ánh mắt sắc lạnh áp đảo, tóc đen ngang vai buộc nửa, lọn tóc bay trong gió.
   - *Y phục:* Chiến bào vải thô đen tuyền xếp lớp, giáp vai và hộ uyển da huyền thạch đen bóng, thắt lưng bản to khóa đồng cổ, ủng chiến đấu cao cổ.
   - *Vũ khí & Khí:* Trọng kiếm thẳng bản rộng (U Minh Trọng Kiếm) thép đen tuyền, chuôi quấn da đen. U Minh Kiếm Khí (dark purple / smoky obsidian qi) dày đặc, cuồn cuộn xung quanh kiếm và lòng bàn tay.
   - *Phong cách:* Áp đảo bằng sức mạnh, sải chân rộng, chém bổ nặng nề, dùng chưởng lực ngưng tụ khiên khí chặn đòn và quét kiếm khí tầm xa.

---

## 3. Trục Không Gian 180° & Quy Tắc Máy Quay (Cinematography Bible)

- **Trục chiến đấu (Duel Axis):** Trục thẳng Đông - Tây chạy ngang qua trung tâm sàn đấu Vân Đài.
- **Vị trí thiết lập ban đầu (X01–X07):**
  - Bạch Y Kiếm Tu: Đứng bên **TRÁI KHUNG HÌNH (SCREEN-LEFT)**, mặt hướng sang Phải (Đông).
  - Hắc Y Kiếm Tu: Đứng bên **PHẢI KHUNG HÌNH (SCREEN-RIGHT)**, mặt hướng sang Trái (Tây).
- **Vị trí máy quay:** Toàn bộ máy quay được bố trí nghiêm ngặt ở **PHÍA NAM CỦA TRỤC CHIẾN ĐẤU (Looking North)** nhìn ra hướng biển mây và rặng núi xa. Không bao giờ nhảy qua trục 180°.
- **Quy tắc vector chuyển động:**
  - Bạch Y di chuyển, né tránh, đâm kiếm theo hướng từ **TRÁI SANG PHẢI**.
  - Hắc Y lướt tới, chém bổ, đẩy chưởng theo hướng từ **PHẢI SANG TRÁI**.
- **Chuyển đổi vị trí chiến thuật tại X08:**
  - Tại cảnh X08, Bạch Y Kiếm Tu đạp mây phi thân hình vòng cung từ Trái sang Phải qua đầu Hắc Y.
  - Vị trí từ X09–X12 đảo ngược tự nhiên: Hắc Y xoay người ở bên Trái phóng kiếm khí sang Phải; Bạch Y đứng vững bên Phải đâm kiếm phản công sang Trái. Trục máy quay phía Nam vẫn giữ nguyên 100%, không gây mất phương hướng cho khán giả.

---

## 4. Biên Dịch Film Core Hoàn Chỉnh & Dây Chuyền Dữ Liệu (Compilation Lineage)

Dây chuyền Film Core đã được thực thi toàn bộ bằng công cụ offline:
`NarrativeCompiler` → `StoryGraph` → `XianxiaDirectorCompiler` → `ShotGraph` → `Canonical ShotSpec (X01–X12)` → `film_pipeline.compiler.compile_prompt` → `make_edit_manifest`.

### Bảng Thống Kê Hashes & Quan Hệ Cảnh Quay (Lineage Map sau Hiệu Chỉnh)

| Shot ID | Story Beat | Director Node | ShotSpec Hash (SHA-256) | PromptPlan Input Hash | Loại Cảnh / Cỡ Cảnh | Thời Lượng |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **X01** | beat_01 | S01 | `be369085504ef881fd81b4ae138ad7915b2afbcc27138c9889e869de8e0361e0` | `97297426d75739e17496e7bd53eccc54db2c04cb2abda053b956e6cf8a4c5e0f` | establishing / WS | 5.0s |
| **X02** | beat_02 | S02 | `97727d29762588a42a6aba573b14655d2f75da53329899ce95ff1119f848f117` | `aefba658eb15ef7bc554796152c40dc10e488feaa879cfb6a0d35f26b0f6d0ea` | insert / MCU | 5.0s |
| **X03** | beat_03 | S03 | `880d79d64db605257a4c2074c1c97a6369626ea644233f150de3af393ca64988` | `621001b24b547488b8d6916a8f81ad2f9c12913bb11bf132a6f6ee7cdf7f460b` | action / MS | 5.0s |
| **X04** | beat_04 | S04 | `bab0897e11f75695d405a98e9d36d19870e5f27107fd4b3ece289556963446da` | `2259e6e4290d37ce37b9600fc1a274d30d1f121109ca18dadb682f7828fa8ec1` | action / TWO_SHOT | 5.0s |
| **X05** | beat_05 | S05 | `690024962e6ff48b4589d679cb33dbddd0449ba84799b852e6925f3b83c605e4` | `26fb99ed011e54267bc2f3ea5a27b86167edbf794d8463dc55ccacdf3c944441` | action / MS | 5.0s |
| **X06** | beat_06 | S06 | `06e549ad4b531a94f7489b9b4a10e4a7deceddf837aff0402edaaeba9ff59fb0` | `e3d86873b9b8d0f0b0b94be5ca6edc7d104efac93c2caaecb8458b61b7574f26` | action / MS | 5.0s |
| **X07** | beat_07 | S07 | `39b70baea6d9cdad1fac69b465ad4ddde7b7209a326e6960eb5d66cbfa25b245` | `72b7d1a1cc2e9d2dea8f509210120a63d1eae561755f246936d365d4ab075378` | action / MCU | 5.0s |
| **X08** | beat_08 | S08 | `293c9c984cfa52a22b7f8e85904c5c9f84134c69e2d3801db90081e1e8e071cc` | `c5fa54a5dc6c2cbb643527876ba80b84a2e4c315aa9f60f8ee8f372acc684ec7` | action / WS | 5.0s |
| **X09** | beat_09 | S09 | `dcd39fe4b30784d7f391c2e0437373a73b0ede4d53d8479acbd03361fd83b864` | `eee78360525efc78ced558d09c119831a21cb6b70b68ce158ef3317143e283cd` | action / MS | 5.0s |
| **X10** | beat_10 | S10 | `e5665a27936b1a648d25454a903b25cafd3f7be69ff2ddebe6e2222656504af8` | `7ec983288ea648dd0c2f4180f544a7a85f199d0a8804f5266afbd5d92a4645e4` | action / TWO_SHOT | 5.0s |
| **X11** | beat_11 | S11 | `c6f631de448106fcfadaa30ce00e8d1bc2e4d05ee312021c9153670c0edddcf8` | `22cd63ec0d2afe17d5052b2df886300a60e7bf8470352dc7eaa00bc8815e2047` | reaction / MS | 5.0s |
| **X12** | beat_12 | S12 | `2e396c6f4c113c860dda8b6c8a19d3dc0583baa6733f11830abcb25e8e3012fb` | `b1b3dd2c28102e273202890e786ab119aac459f2a961a566c4459e40f94b00d0` | hero / WS | 5.0s |
| **TỔNG** | 12 Beats | 12 Nodes | 12 ShotSpecs chuẩn hóa JSON Schema | 12 PromptPlans chuẩn hóa JSON Schema | 12 Clips contig 1..12 | **60.0s** |

- **EditManifest ID:** `edit_bfc4829aa78e125c812b3f728a5abe1ba7ec6c8b59a9ebc9571db03fa81fa2bd`
- **Tập tin tổng hợp:** `projects/xianxia60_nhat_kiem_pha_van/XIANXIA60_COMPILATION.json` (SHA-256: `2a9f649a45d94a21cabd1993bcb25d3eb60f73715dfbbc2b6347b105ba7e5fb9`, 626,818 bytes).

---

## 5. Storyboard & Animatic Tiền Kỳ Chi Tiết (12 Thẻ Phân Cảnh)

> [!NOTE]
> Mọi thẻ phân cảnh dưới đây là **kế hoạch biên tập & dàn dựng tiền kỳ** (Pre-production planning), **KHÔNG PHẢI VIDEO ĐÃ RENDER**.

1. **X01 (00–05s) — Thiết Lập Võ Đài (ESTABLISH / WS):**
   - *Hình ảnh:* Toàn cảnh góc rộng nhìn từ phía Nam. Biển mây trắng xóa phía sau. Bạch Y (trái) và Hắc Y (phải) đứng yên cách nhau 15 bước chân. Gió núi lay động vạt áo. Sương là là mặt đá hoa cương đen.
   - *Âm thanh:* Tiếng gió núi rít xa xăm, tiếng vải áo phần phật nhè nhẹ, drone căng thẳng nền.
2. **X02 (05–10s) — Rút Kiếm Định Tâm (DECISION / MCU):**
   - *Hình ảnh:* Cận cảnh trung Bạch Y Kiếm Tu nhìn nghiêng sang phải. Tay phải rút thanh trường kiếm thẳng ra khỏi bao bạc; ánh thép lạnh phản chiếu tia sáng ban mai, một dải Thanh Vân Kiếm Khí mỏng như sương lam sáng rực dọc lưỡi kiếm.
   - *Âm thanh:* Tiếng kim loại tuốt khỏi bao vang thanh thoát (*keng*), kèm âm bội vi lượng ngân nga của chân khí.
3. **X03 (10–15s) — Áp Sát Tấn Công (APPROACH / MS Tracking):**
   - *Hình ảnh:* Máy quay góc thấp trượt ngang từ Phải sang Trái theo đà lao của Hắc Y Kiếm Tu. Ủng da nện mạnh lên mặt đá, áo choàng đen tung bay, tay phải kéo lê thanh trọng kiếm đen sẫm sát hông, khí thế hung hãn.
   - *Âm thanh:* Tiếng ủng nện đá vang dội, tiếng gió rít dồn dập, tiếng gầm gừ trầm thấp của U Minh Kiếm Khí.
4. **X04 (15–20s) — Giao Kiếm Bùng Nổ (DISCOVER / TWO_SHOT):**
   - *Hình ảnh:* Cú chém chéo sấm sét của Hắc Y va chạm trực diện với thế đỡ nghiêng của Bạch Y ở giữa lệch trái. Tia lửa trắng - vàng bắn tung tóe. Vòng sóng xung kích trong suốt hất văng mây sương xung quanh. Hai kiếm ghì chặt nhau.
   - *Âm thanh:* Tiếng thép va chạm đanh thép như sấm sét (*clash!*), tiếng tia lửa xèo xèo, tiếng nén bass trầm đục của sóng xung kích.
5. **X05 (20–25s) — Thân Pháp Né Tránh (REACTION / MS):**
   - *Hình ảnh:* Bạch Y Kiếm Tu xoay gót chân trái theo bộ pháp Bát Quái, thân hình lướt nhẹ sang tiền cảnh trái. Cú chém dọc bồi thêm của Hắc Y chém trúng khoảng không và cắm vào sàn đá hoa cương làm vỡ vụn dăm đá.
   - *Âm thanh:* Tiếng kiếm xé gió hụt, tiếng lưỡi kiếm chém găm vào đá hoa cương (*chát!*), tiếng đá vỡ lạo xạo.
6. **X06 (25–30s) — Khí Điệp Hộ Thể (PRESSURE / MS Dolly):**
   - *Hình ảnh:* Hắc Y giật kiếm khỏi sàn đá, đẩy mạnh chưởng trái sang bên trái. Một màn chắn khí hình tròn (đường kính 1m) bằng tinh thể tím đen mờ ảo ngưng tụ trước lòng bàn tay, khói đen xoáy quanh viền.
   - *Âm thanh:* Tiếng chưởng phong nén khí ùng oàng, tiếng tinh thể ngưng tụ cộng hưởng như kính cường lực.
7. **X07 (30–35s) — Mũi Kiếm Phá Giáp (DISCOVER / MCU):**
   - *Hình ảnh:* Mũi kiếm của Bạch Y đâm thẳng chuẩn xác vào tâm màn chắn khí. Tia lửa lam - tím bắn tóe. Các vết rạn nứt hình mạng nhện phát sáng rực rỡ lan rộng trên bề mặt tinh thể tím đen.
   - *Âm thanh:* Tiếng kim loại nhọn xuyên thủng tinh thể rạn vỡ (*crackle-pierce*), tiếng năng lượng rít cao tần.
8. **X08 (35–40s) — Đạp Mây Hoán Vị (DECISION / WS Low-Angle):**
   - *Hình ảnh:* Bạch Y thu kiếm, nhún chân đạp không phi thân vút lên cao 2.5m, thân hình lướt ngang qua đầu Hắc Y trong làn sương ngược sáng ban mai như cánh hạc trắng, đáp nhẹ nhàng xuống phía Đông (bên phải).
   - *Âm thanh:* Tiếng bật chân nhẹ nhàng, tiếng gió lướt qua tà áo lụa trên không trung, tiếng tiếp đất êm ái.
9. **X09 (40–45s) — U Minh Kiếm Trảm (PRESSURE / MS):**
   - *Hình ảnh:* Hắc Y xoay ngoắt 180 độ sang phải, hai tay vung kiếm quét ngang một vòng tròn cung kiếm khí màu tím đen rộng 2m bay sát mặt sàn đá phóng thẳng về phía Bạch Y Kiếm Tu.
   - *Âm thanh:* Tiếng hét vận khí ngắn (*kiai*), tiếng kiếm khí khổng lồ xé rách không khí bay ràn rạt (*whoosh-tear*).
10. **X10 (45–50s) — Nhất Kiếm Phá Vân (PAYOFF / TWO_SHOT Hero):**
    - *Hình ảnh:* Đòn quyết định của phim. Bạch Y Kiếm Tu tấn bộ đâm thẳng một kiếm; một luồng sáng thanh lam - trắng tinh khiết phát ra từ mũi kiếm đâm xuyên tâm vòng cung kiếm khí đen, làm nó vỡ vụn thành làn sương xám vô hại. Sóng xung kích làm bay sạch sương mù trên sàn đấu.
    - *Âm thanh:* Tiếng chuông bạc ngân vang thanh tịnh (*pure chime*), tiếng kiếm khí đen tiêu tán êm ả như gió thổi mây.
11. **X11 (50–55s) — Thất Thế Quy Phục (AFTERMATH / MS High-Angle):**
    - *Hình ảnh:* Hắc Y Kiếm Tu đứng thở dốc, nhận ra kiếm đạo chênh lệch; từ từ buông lỏng tay, mũi trọng kiếm hạ xuống chống lên mặt đá, đầu gối phải quỳ xuống trong tư thế tâm phục khẩu phục, đầu hơi cúi.
    - *Âm thanh:* Tiếng thở dốc nặng nhọc trong sương lạnh, tiếng mũi kiếm thép chạm khẽ mặt đá, sự im lặng trang nghiêm trở lại.
12. **X12 (55–60s) — Kiếm Thu Mây Rạng (RESOLVE / WS Tracking):**
    - *Hình ảnh:* Toàn cảnh góc rộng. Bạch Y Kiếm Tu vẩy nhẹ cổ tay tra kiếm vào bao bạc (*cạch*). Những tia nắng ban mai vàng rực xuyên qua mây mù chiếu rọi khắp đỉnh núi. Bạch Y đứng ngắm chân trời mây, Hắc Y quỳ tĩnh lặng. Phim kết thúc ở 60.0s tròn.
    - *Âm thanh:* Tiếng kiếm khóa vào bao vang giòn dứt khoát, tiếng sáo trúc và đàn tranh truyền thống vút lên huy hoàng hòa cùng dàn dây giao hưởng.

---

## 6. Kế Hoạch Hậu Kỳ m Thanh & Hoàn Thiện Màu Sắc (Audio & Resolve Finishing)

- **Chuẩn âm thanh bàn giao:** 48kHz / 24-bit, Stereo & 5.1 Surround, tích hợp trên Fairlight (DaVinci Resolve).
- **6 Lớp âm thanh chuyên biệt:**
  - `A1_Dialogue_Voice`: Tiếng thở, tiếng hét vận khí (*kiai* tại X03/X09), không lời thoại thừa.
  - `A2_Foley_Footsteps`: Tiếng ủng da trên đá hoa cương ướt, tiếng bật nhảy và tiếp đất, tiếng xao động của tà áo.
  - `A3_SFX_Weapons`: Tiếng rút kiếm (X02), tiếng chạm kiếm sấm sét (X04), tiếng kiếm cắm đá (X05), tiếng tra kiếm (X12).
  - `A4_VFX_Qi_Resonance`: Tiếng rền trầm hạ âm (sub-bass 50Hz) của Hắc Y Kiếm Khí, tiếng pha lê ngân vang của Thanh Vân Kiếm Khí.
  - `A5_Atmosphere_Ambience`: Gió núi cao liên tục, tiếng mây mù cuộn trào khuếch tán.
  - `A6_Music_Score`: Đàn Cổ Cầm (Guqin) và Sáo Trúc (Dizi) khởi đầu tĩnh lặng -> Bộ gõ Taiko và dàn nhạc dồn dập trong giao chiến -> Giai điệu bừng sáng khi mặt trời lên ở X12.
- **Hệ màu & Grade (Color Pipeline):**
  - Không gian màu chuẩn: **Rec.709 / Gamma 2.4**.
  - Bảng màu: Lạnh - u tịch (cool cyan-grey), da người giữ sắc độ tự nhiên, điểm nhấn là ánh kiếm lam sáng và tím đen, kết thúc chuyển dần sang ánh vàng ấm (golden morning light).

---

## 7. Bảng Rủi Ro Dàn Dựng & Giải Pháp Biên Tập Dự Phòng (Risk Matrix)

| Cảnh | Mức Rủi Ro | Yếu Tố Kỹ Thuật Dễ Lỗi | Rủi Ro Khi AI Video Render | Giải Pháp Biên Tập / Khắc Phục Dự Phòng |
| :--- | :--- | :--- | :--- | :--- |
| **X01** | THẤP | Đứng đối diện góc rộng | Sinh thừa nhân vật thứ 3 hoặc biến dạng trụ đá | Prompt ràng buộc nghiêm ngặt "no third person"; góc rộng cố định (locked) triệt tiêu rung giật. |
| **X02** | THẤP | Cận cảnh rút kiếm | Ngón tay dính vào chuôi hoặc kiếm cong | Cận cảnh cố định, tay cầm chuẩn xác trong PerformanceSpec. Fallback: Cắt từ cảnh tay cầm chuôi sang cảnh kiếm đã rút sẵn sàng. |
| **X03** | TRUNG BÌNH | Chạy lao người tốc độ cao | Chân trượt bay lơ lửng, kiếm biến dạng dẻo | Máy quay trượt ngang bám theo chuyển động; Fallback: Cắt nửa thân trên (waist-up) nhấn vào gương mặt hung hãn. |
| **X04** | **CAO** *(Rank #1 Wave-1)* | Hai người chạm kiếm trực diện | Hai nhân vật bị biến dạng dính vào nhau, kiếm xuyên thủng cơ thể | Cảnh quan trọng nhất cần test Đợt 1. Fallback: Cắt cận cảnh hai lưỡi kiếm va chạm tóe lửa, sau đó cắt nhanh sang phản ứng bật lùi ở X05. |
| **X05** | TRUNG BÌNH | Thân pháp xoay người né tránh | Xoay người giật cục, trượt chân trên mặt đá | Mô tả rõ bộ pháp Bát Quái trong PerformanceSpec. Fallback: Tách thành 2 shot: Bạch Y lách người + Cận cảnh kiếm cắm sàn đá văng bụi. |
| **X06** | TRUNG BÌNH | Đẩy chưởng hiện khiên khí | Khiên biến thành đám cháy hoặc vụ nổ hỗn loạn | Định nghĩa rõ "đĩa tinh thể tím đen trong suốt, không lửa, không khói mù". Fallback: Cận cảnh bàn tay đẩy chưởng. |
| **X07** | **CAO** *(Rank #2 Wave-1)* | Mũi kiếm đâm nứt khiên khí | Mũi kiếm uốn cong, khiên biến mất đột ngột | Cảnh thử nghiệm Đợt 1. Fallback: Cận cảnh góc hẹp (macro insert) mũi kiếm cắm vào bề mặt nứt, thêm hiệu ứng rạn nứt trong hậu kỳ. |
| **X08** | **CAO** | Phi thân trên không hoán đổi vị trí | Nhân vật bị biến dạng khi bay cắt qua nhau | Góc thấp ngược sáng tạo bóng silhouette rõ nét; Fallback: Cắt 3 nhịp: Nhún chân bật lên -> Lướt trên nền mây -> Tiếp đất xoay người. |
| **X09** | TRUNG BÌNH | Vung kiếm phóng kiếm khí hình cung | Kiếm khí văng lệch hướng hoặc tay vung biến dạng | Ràng buộc rõ vector ngang từ Trái sang Phải. Fallback: Cận cảnh động tác vung kiếm uy lực, kiếm khí compositing sau. |
| **X10** | **CAO** *(Rank #3 Wave-1)* | Đâm kiếm phá tan kiếm khí ("Nhất Kiếm") | Vệt sáng trắng xóa lấp hết khung hình, mất người | Cảnh cao trào then chốt. Fallback: Cận cảnh Bạch Y đâm kiếm dứt khoát + Cắt cảnh làn sương xám tan biến + Hắc Y lảo đảo lùi lại. |
| **X11** | THẤP | Quỳ gối nhận thua | Nhân vật ngã gục quá đà hoặc ho ra máu | Ràng buộc nghiêm ngặt cấm máu me/gore; động tác hạ người chậm rãi đàng hoàng; mức độ sửa chữa dễ dàng. |
| **X12** | THẤP | Tra kiếm và bình minh lên | Kiếm tra lệch miệng bao hoặc tay biến dạng | Góc rộng đại cảnh giúp bao quát; Fallback: Cận cảnh tra kiếm khớp với tiếng *cạch* hoặc bóng lưng nhìn về phía mặt trời mọc. |

---

## 8. Đề Xuất Tuyến Provider & Ngân Sách Đợt 1 (Provider Route & Wave-1 Proposal)

### Sự Thật Về Tài Khoản & Quota
- Tài khoản `ACCOUNT_A` từng được ghi nhận trong các đợt chạy trước của phim người làm vườn, nhưng **số dư hiện tại là UNKNOWN** (không tự tiện suy diễn có sẵn credit).
- Hệ thống tuân thủ nghiêm ngặt nguyên tắc: **Không thử lại mù quáng (no blind retry), không tự ý chuyển sang tuyến trả phí, không tự ý cào session trình duyệt**.

### Đề Xuất Phân Kỳ Đợt 1 (3 Cảnh Then Chốt)
- **Danh sách cảnh đề xuất Wave-1:** `X04` (va chạm kiếm trực diện), `X08` (phi thân hoán đổi vị trí), `X10` (nhất kiếm phá vỡ kiếm khí).
- **Trần ngân sách Wave-1:** **$0.00 USD**.
- **Số lần render tối đa (Budget Cap):** Tối đa **4 lần tạo (takes)** cho mỗi cảnh then chốt trên tuyến miễn phí an toàn. Nếu cả 4 lần đều không đạt, chuyển sang phương án dựng dự phòng (Fallback edit) bằng các shot cận cảnh đã được thiết kế sẵn.
- **Tuyến provider ưu tiên:** Text-to-Video miễn phí qua giao diện chuẩn của hệ thống (Dola free route / Seedance planning route).

---

## 9. Bằng Chứng Kiểm Thử Tập Trung & Hồi Quy (Verification & Regression Evidence)

Bộ kiểm thử chuyên sâu được thực thi trên chính mã nguồn và dữ liệu thực tế của XIANXIA60:
- **Lệnh chạy:**
  ```powershell
  $env:PYTHONPATH="src;tools"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_film_core_slice.py tests/test_narrative_compiler_021.py tests/test_xianxia60_compilation.py -v
  ```
- **Kết quả kiểm thử:**
  - `tests/test_xianxia60_compilation.py`: **14/14 PASS** (0.42s)
  - `tests/test_film_core_slice.py`: **16/16 PASS**
  - `tests/test_narrative_compiler_021.py`: **15/15 PASS**
  - **TỔNG CỘNG: 45/45 PASS (100% Không có hồi quy, 0 failure)**.

### Chi Tiết 14 Hạng Mục Đã Kiểm Chứng Trong `test_xianxia60_compilation.py`:
1. `test_xianxia60_compilation_executes_and_yields_valid_master`: Master JSON hợp lệ, phiên bản `xianxia60-compilation-v1`, thời lượng 60.0s.
2. `test_xianxia60_narrative_and_director_beat_structure`: Đúng 12 beats từ `ESTABLISH` đến `RESOLVE`, không có hai beat liền kề nào trùng function.
3. `test_xianxia60_character_bibles_and_fingerprints`: Fingerprint của 2 nhân vật ổn định (`edb2d2d99cd0fae0` và `451172ec254174f6`).
4. `test_xianxia60_world_state_and_transitions`: 13 world states, 12 transitions có giải trình story event.
5. `test_xianxia60_all_12_shotspecs_schema_and_model_valid`: 12 ShotSpecs đạt chuẩn JSON Schema Draft2020-12, đầy đủ `PerformanceSpec` và `ActionIntent`.
6. `test_xianxia60_all_12_promptplans_schema_and_degradation`: 12 PromptPlans đạt chuẩn schema, phản ánh trung thực việc hạ cấp điều khiển không hỗ trợ thành fallback dạng text.
7. `test_xianxia60_edit_manifest_schema_and_timeline`: EditManifest hợp lệ, thời lượng 60.0s, 12 clips liên tục 1..12 được đánh dấu planning placeholder.
8. `test_xianxia60_spatial_continuity_180_degree_axis`: Trục máy quay phía Nam và quy tắc vector chuyển động được bảo toàn.
9. `test_xianxia60_end_to_end_lineage_traceability`: Truy vết liên tục không đứt đoạn từ Beat -> ShotGraphNode -> ShotSpec Hash -> PromptPlan Input Hash -> EditManifest Clip.
10. `test_xianxia60_preproduction_bounds_enforced`: Khẳng định 0 request mạng, $0 chi phí, giữ nguyên trạng thái chờ Owner khóa sáng tạo.
11. `test_xianxia60_cross_layer_shotgraph_to_shotspec_congruence`: Đồng nhất 100% các trường camera movement, shot size, screen direction giữa Director ShotGraph và ShotSpec; kiểm tra bắt buộc X03 và X08; kiểm tra phát hiện dữ liệu lỗi (negative corruption check).
12. `test_xianxia60_consecutive_cut_continuity_end_to_start_congruence`: Kiểm tra khớp trạng thái đầu - cuối (`end_state == start_state`) qua 11 mối cắt liền kề; đảm bảo 100% các khóa thực thể đầy đủ; phát hiện lỗi dịch chuyển tức thời sai lệch.
13. `test_xianxia60_x07_x08_x09_positional_inversion_geometry`: Kiểm tra hình học hoán đổi vị trí của cú phi thân qua đầu; phân biệt thay đổi có lý do với lỗi discontinuity; bảo toàn nghiêm ngặt trục máy quay phía Nam.
14. `test_xianxia60_world_state_graph_explicit_entities`: Kiểm tra WorldStateGraph lưu trữ đầy đủ thực thể vật lý của cả hai đấu thủ, vũ khí, khiên khí, mặt đá và đường mây, không dùng mô tả rút gọn 60 ký tự.

---

## 10. Báo Cáo Hiệu Chỉnh Continuity Giữa Các Lớp Film Core (Correction Evidence)

Theo chỉ đạo của Tech Lead GPT-6 sau vòng independent PROVE sơ bộ, Worker đã thực hiện rà soát và hiệu chỉnh chuyên sâu các điểm sau:

### 10.1. Đồng Bộ Hóa ShotGraph và ShotSpec (X01–X12)
- **Nguyên nhân gốc:** `DirectorCompiler` mặc định của Film Core được xây dựng cho ngữ cảnh nhân vật đơn di chuyển tuyến tính. Do đó, các thuộc tính camera intent và screen direction trong ShotGraph chưa phản ánh đúng tính chất đối kháng hai người.
- **Giải pháp thực thi:** Kế thừa và chuyên biệt hóa `XianxiaDirectorCompiler(DirectorCompiler)` trong `tools/build_xianxia60_compilation.py`. Lớp này sinh ra tập hợp `DirectorShotIntent` và `ShotGraphNode` khớp chính xác với `ShotSpec`:
  - `S03 / X03`: `movement = "TRACKING_LATERAL" <-> "tracking"`, `screen_direction = "right-to-left"`, `framing = "MS" <-> "MEDIUM"`.
  - `S08 / X08`: `movement = "LOCKED" <-> "locked"`, `screen_direction = "left-to-right"`, `framing = "WS" <-> "WIDE"`.
  - `S10 / X10`: `movement = "LOCKED" <-> "locked"`, `screen_direction = "right-to-left"`, `framing = "TWO_SHOT" <-> "WIDE"` (hai đấu thủ trong đại cảnh đâm kiếm phá kiếm khí).
  - Chuẩn hóa chuỗi định danh `screen_direction` thành dạng có gạch nối (`left-to-right`, `right-to-left`, `static`) đồng nhất giữa mọi tầng dữ liệu.

### 10.2. Mô Hình Hóa Trạng Thái Thực Thể Vật Lý Đầy Đủ
- **Nguyên nhân gốc:** Trước đây, một số trường kiểm tra dùng 60 ký tự đầu của blocking làm đại diện trạng thái, dẫn tới nguy cơ che giấu lỗi mất tính liên tục.
- **Giải pháp thực thi:** Xây dựng cấu trúc dữ liệu `C_STATES` gồm 12 cặp trạng thái `start` và `end` chi tiết cho cả 12 shot:
  - `white_cultivator`: `position`, `orientation`, `pose`, `sword_state`, `qi_state`.
  - `black_cultivator`: `position`, `orientation`, `pose`, `sword_state`, `qi_state`.
  - `arena`: `camera_side_of_axis` (luôn là "south"), `barrier_state` (none -> solid_crystalline_disc -> spiderweb_fractured -> dissolved), `energy_projectile` (none -> flying_crescent_left_to_right -> shattered_into_grey_vapor), `pavement_state` (intact -> chipped_at_center).
  - Đảm bảo đẳng thức liên tục: `shot[i-1].end_state == shot[i].start_state` với mọi $i \in [1, 11]$.

### 10.3. Hình Học Bước Chuyển X07 → X08 → X09 (Hoán Đổi Vị Trí Hợp Lý)
- **X07 (Kết thúc):** Bạch Y ở trung tâm lệch trái (`center_left`), hướng Đông, mũi kiếm găm vào khiên khí nứt rạn. Hắc Y ở trung tâm lệch phải (`center_right`), hướng Tây, gồng mình giữ khiên. Trục máy quay: Phía Nam.
- **X08 (Bắt đầu = X07 Kết thúc):** Bạch Y nhún chân đạp không phi thân qua đầu Hắc Y.
- **X08 (Kết thúc):** Bạch Y tiếp đất an toàn tại rìa phía Đông (`east_ledge_screen_right`), hướng Tây. Hắc Y tại trung tâm lệch trái (`center_left`), bắt đầu xoay người về phía Đông. Khiên khí đã tan rã. Trục máy quay: Phía Nam.
- **X09 (Bắt đầu = X08 Kết thúc):** Hắc Y vung kiếm quét kiếm khí từ Trái sang Phải về phía Bạch Y đang thủ thế ở rìa Phải.
- **Kết luận hình học:** Vị trí hai đấu thủ hoán đổi hoàn toàn nhờ hành động nhảy có động cơ vật lý trên phim (motivated movement), nhưng **máy quay tuyệt đối không băng qua trục 180 độ** (vẫn nhìn từ phía Nam lên phía Bắc). Đây là sự thay đổi có lý do, không phải lỗi discontinuity.

### 10.4. Kiểm Thử Phát Hiện Dữ Liệu Lỗi (Negative Corruption Detection)
- Các hàm kiểm thử mới trong `tests/test_xianxia60_compilation.py` không chỉ kiểm tra chuỗi ký tự mà còn thực hiện kiểm thử phủ định (negative assertion):
  - Đưa dữ liệu di chuyển máy quay giả mạo (`LOCKED` vs `tracking`) -> Test khẳng định phải bắt được lỗi.
  - Sửa đổi vị trí nhân vật trong `start_state` thành vị trí dịch chuyển tức thời sai lệch -> Test khẳng định `start_state != end_state`.

---

## 11. Đánh Giá Hạn Chế Của Hệ Thống Hiện Hữu (Honest Limitations & Gaps)

1. **Khả năng dàn dựng đối kháng 2 nhân vật trong `DirectorCompiler`:**
   - *Thực trạng:* `DirectorCompiler` hiện hữu được thiết kế chủ yếu cho nhân vật đơn di chuyển trái qua phải (`self.screen_direction = "left-to-right"`).
   - *Xử lý trong WP:* Báo cáo trạng thái **PARTIAL / ADAPTED**. Chúng tôi chuyên biệt hóa `XianxiaDirectorCompiler` kế thừa từ `DirectorCompiler` để sinh ra ngữ pháp hai kiếm tu mà không làm phá vỡ logic gốc của Film Core.
2. **Khả năng điều khiển tham số gốc của Provider:**
   - *Thực trạng:* Tuyến Text-to-Video thông dụng (Dola / Seedance 2.0 / Veo) không hỗ trợ kiểm soát native thời lượng từng giây, không có native audio, không nhận multi-reference ảnh qua prompt thô.
   - *Xử lý trong WP:* Báo cáo trung thực qua các cờ `unsupported_controls` và cảnh báo `warnings` trong `PromptPlan`, chuyển hóa yêu cầu thành mô tả văn bản rõ ràng trong 10 khối canonical, không giả mạo rằng provider hỗ trợ native controls.
3. **Thẩm quyền khóa sáng tạo:**
   - Gói tiền kỳ này là **đề xuất kỹ thuật & sáng tạo đã được chứng minh khả thi** (`PREPROD_CREATIVE_PROPOSAL`). Quyền **CREATIVE LOCK** thuộc về Chủ sở hữu (Owner) và Tech Lead sau khi xem xét độc lập báo cáo này.

---

## 12. Kết Luận & Đề Xuất Hành Động Tiếp Theo

Gói tiền kỳ và bản hiệu chỉnh continuity toàn phim cho *Nhất Kiếm Phá Vân* (60 giây / 12 cảnh) đã hoàn tất trọn vẹn, có thể tái lập 100%, bảo toàn tuyệt đối toàn bộ tài nguyên cũ. Toàn bộ 45/45 kiểm thử trong repo đều PASS.

**Bước tiếp theo đề xuất:**
1. Trình nộp báo cáo cho **Tech Lead GPT-6** thực hiện quy trình thẩm định độc lập (`independent PROVE`).
2. Tech Lead trình Owner phê duyệt khóa sáng tạo kịch bản/bối cảnh/tạo hình (`Owner Creative Lock`).
3. Owner xem xét cấp quyền **Đợt 1 (Wave-1)** cho 3 cảnh thử nghiệm then chốt (`X04`, `X08`, `X10`) với trần chi phí $0 và tối đa 4 lần phát hành trên tuyến miễn phí an toàn.
