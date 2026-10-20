# S3 XIANXIA60 — BÁO CÁO TIỀN KỲ TOÀN PHIM QUA FILM CORE
## *Nhất Kiếm Phá Vân* (60.0 giây / 12 Cảnh / Hai Nhân Vật Giao Đấu)

**Ngày báo cáo:** 2026-10-20
**Người thực thi:** Gemini Flash 3.8 (Worker)
**Trạng thái:** `FILM_CORE_TECHNICAL_PASS` / `PREPROD_CREATIVE_PROPOSAL` / `OWNER_CREATIVE_LOCK_PENDING`
**Giới hạn quyền hạn:** **0 REQUEST GENERATE RA NGOÀI, $0 CHI PHÍ PHÁT SINH, KHÔNG TRUY CẬP CREDENTIAL/SESSION**.

---

## 1. Kết Quả Kiểm Tra Preflight & Thẩm Quyền (Preflight Truth)

| Tham Số | Giá Trị Kiểm Chứng Thực Tế | Tình Trạng |
| :--- | :--- | :--- |
| **POLICY_REF** | `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` | `git cat-file -e "POLICY_REF^{commit}"` PASS |
| **AGENTS.md Blob SHA** | `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` | Trùng khớp 100% giữa Root HEAD và Worker HEAD |
| **Primary Repository** | `D:\AI FILM MAKER\AI-Film-Pipeline` | `mission/quality-v2-022-120s@37c4301336aafa5b10f167131f350454ecfab8d5` |
| **Worker Worktree** | `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini` | `feature/film120-gemini-realshot-001@e3b99a71eb60bff72ce4d94da76543164613022e` |
| **Frozen Work Package** | `docs/operating/TASK_S3_XIANXIA60_ONE_FILM_PRODUCTION_PACKAGE.md` | SHA-256: `44397bc35d8f36e4fa86fffcfd70c1b62f41db3443279a4b6046a265c77492f2` PASS |
| **Phạm vi bảo toàn** | Bảo toàn nguyên vẹn 100% toàn bộ source phim 120s gardener (`projects/quality_v2_022_longform_120s/`), các thư mục isolated, journal, latches | PASS |

> [!IMPORTANT]
> **Không có bất kỳ lệnh Generate video/ảnh nào được gửi tới provider**, không tiêu tốn credit, không đọc session/cookies, không ghi đè bất kỳ file nào thuộc dự án phim 120 giây cũ. Mọi kết quả tiền kỳ đều được biên dịch ngoại tuyến qua Film Core hiện hữu.

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
  - Bạch Y Kiếm Tu: Đứng bên **TRÁI KHUNG HÌNH (SCREEN-LEFT)**, mặt hướng sang Phải.
  - Hắc Y Kiếm Tu: Đứng bên **PHẢI KHUNG HÌNH (SCREEN-RIGHT)**, mặt hướng sang Trái.
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
`NarrativeCompiler` → `StoryGraph` → `DirectorCompiler` → `ShotGraph` → `Canonical ShotSpec (X01–X12)` → `film_pipeline.compiler.compile_prompt` → `make_edit_manifest`.

### Bảng Thống Kê Hashes & Quan Hệ Cảnh Quay (Lineage Map)

| Shot ID | Story Beat | Director Node | ShotSpec Hash (SHA-256) | PromptPlan Input Hash | Loại Cảnh / Cỡ Cảnh | Thời Lượng |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **X01** | beat_01 | S01 | `4fe7e28d207ce1e70d6b7101e6341e53495d42856242431d4f91c856cc22a3e4` | `d14fbdfb7b035503be486b298e97c46699f33b96a1e056360286d36013a00e7b` | establishing / WS | 5.0s |
| **X02** | beat_02 | S02 | `40bce6c65e0b94623b3a8aac0628f8c6584c405b48e992334e8f80c6fe673f5a` | `2247a214c1e6c3c1b9abb4a9ae76ed2e779da277538b5ad16b0b26160dff9d43` | insert / MCU | 5.0s |
| **X03** | beat_03 | S03 | `a9100d1c92d1d0e1a56fbc87048997fed9d5942d9cb89c7f110fd173657ab833` | `c51a9047b5d7a9d0b55ee0315d9ea85e0026feb2429131c1297b81318fe81c1a` | action / MS | 5.0s |
| **X04** | beat_04 | S04 | `aff9b44cbb8ddaa0a7657d4cc4535720b6280c9307b1c11b67c08abc6a4a33e3` | `95d7c671252f10b0bd31dc68e372b5c77c8791e42679f04332a897a7c078c618` | action / TWO_SHOT | 5.0s |
| **X05** | beat_05 | S05 | `539e0983b51b2be32358cfc4320df7264e4010992e4b138fe2514852d1ad2297` | `5bf084a1c348af2b4a6f399e8b7ea33978051abca7e3a1682c08c4380a071ee4` | action / MS | 5.0s |
| **X06** | beat_06 | S06 | `9ab47223741fdbd54fb82c632130a0ecd1cac0c6c095fb835baf39e1f641607e` | `4987ec54d82968225b8c728986fcb6dda8e2f0d1a2482eb1190dd122aa985052` | action / MS | 5.0s |
| **X07** | beat_07 | S07 | `5558e288d27a2bcdd4f6a96aa9df4ad29e9b6ba19a5df30bf375e3652d4da63d` | `5f73e2652d44794b2a0e3958cc32b1d2edd9c9c1165a6226ebf27b1c6eb9d33f` | action / MCU | 5.0s |
| **X08** | beat_08 | S08 | `ff45b87a8c9b9144a4f8e827326ed3038e561b7764c58a656bbc42b9b112e1c1` | `5394bc3de773cc91ef13de69f75115562a7d42d145822a99893a97e10e851c10` | action / WS | 5.0s |
| **X09** | beat_09 | S09 | `bfc5f5a091706d146b3fd673512fb80ffeb3442ac948b6e12d761436f2d8fe79` | `576c5ad7670b26017f4eed7ac21cae3180171a5be4b98e03385659ba121876d5` | action / MS | 5.0s |
| **X10** | beat_10 | S10 | `bcedea49df1761d58af0d24b59247161a9c30b9b44d8bdb04e47bc37701fc45c` | `41c10c08bf05c1f7aa198ae8159a926bf0b4db9786a1676f9fe64a70c3dce8c3` | action / TWO_SHOT | 5.0s |
| **X11** | beat_11 | S11 | `49f337665d256c7f3dd382347242c082a21caf25c8f1285109c4a2322bd6bfc1` | `aaba6696c071f82d3df14a7b26e71fbabf93e2d0f972308ab4dacc58e25f9f2b` | reaction / MS | 5.0s |
| **X12** | beat_12 | S12 | `5f8024675b29bd674afb86c23617adcea2e076db32dbf33a49245673cfeb369d` | `7bbd502ff202da176bfc780316de9958685b8652c479e142133784a3b0a5c605` | hero / WS | 5.0s |
| **TỔNG** | 12 Beats | 12 Nodes | 12 ShotSpecs chuẩn hóa JSON Schema | 12 PromptPlans chuẩn hóa JSON Schema | 12 Clips contig 1..12 | **60.0s** |

- **EditManifest ID:** `edit_75c59cd6ba7684c505349b7a2fea694f24d9b4b97ee139d5d1d92215758cfa47`
- **Tập tin tổng hợp:** `projects/xianxia60_nhat_kiem_pha_van/XIANXIA60_COMPILATION.json` (SHA-256: `5e579549057ce1f27eefdaf00de9d3c09e892d6ebec7c018ee62e7e96ab05c90`, 504,384 bytes).

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

### Đề Xuất Đợt Tạo 1 (Wave-1 Bounded Calibration Wave)
- **Mục tiêu:** Kiểm chứng tính khả thi của tạo hình 2 nhân vật và các cảnh va chạm kiếm thuật phức tạp trước khi cấp phép sản xuất toàn bộ.
- **3 Cảnh đại diện rủi ro cao nhất được chọn:**
  1. **X04:** Va chạm kiếm trực diện và tia lửa (Kiểm chứng va chạm 2 nhân vật không dính hình).
  2. **X08:** Đạp mây phi thân hoán đổi vị trí (Kiểm chứng thân pháp trên không và bóng silhouette).
  3. **X10:** Nhất Kiếm phá tan kiếm khí (Kiểm chứng đòn quyết định cao trào).
- **Hạn mức phát hành đề xuất cho Đợt 1:**
  - Số cảnh: **3 cảnh**.
  - Số lần phát hành tối đa (Max releases): **4 lần** (3 cảnh chính + 1 lần dự phòng sửa chữa).
  - Trần chi phí tối đa: **$0.00 (Chỉ chạy trên tuyến miễn phí đã xác minh hợp lệ)**.
  - Tuyến đề xuất: **Seedance 2.0 / Dola (Free route)**.
- **Cơ chế chốt an toàn (Fail-Closed):**
  - Mỗi lần tạo chạy trong một namespace cô lập có `MutationAuthority` riêng.
  - Nếu xuất hiện lỗi không xác định từ nhà cung cấp (`UNKNOWN`), lập tức dừng lại, ghi nhận bằng chứng và báo cáo, tuyệt đối không lặp lại request.

---

## 9. Bằng Chứng Thực Thi & Kiểm Chứng Hệ Thống (Technical PASS Proof)

Bộ kiểm thử chuyên sâu được thực thi trên chính mã nguồn và dữ liệu thực tế của XIANXIA60:
- **Lệnh chạy:**
  ```powershell
  $env:PYTHONPATH="src;tools"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_film_core_slice.py tests/test_narrative_compiler_021.py tests/test_xianxia60_compilation.py
  ```
- **Kết quả kiểm thử:**
  - `tests/test_xianxia60_compilation.py`: **10/10 PASS** (0.40s)
  - `tests/test_film_core_slice.py`: **16/16 PASS**
  - `tests/test_narrative_compiler_021.py`: **15/15 PASS**
  - **TỔNG CỘNG: 41/41 PASS (100% Không có hồi quy)**.

### Chi Tiết 10 Hạng Mục Đã Kiểm Chứng:
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

---

## 10. Đánh Giá Hạn Chế Của Hệ Thống Hiện Hữu (Honest Limitations & Gaps)

1. **Khả năng dàn dựng đối kháng 2 nhân vật trong `DirectorCompiler`:**
   - *Thực trạng:* `DirectorCompiler` hiện hữu được thiết kế chủ yếu cho nhân vật đơn di chuyển trái qua phải (`self.screen_direction = "left-to-right"`).
   - *Xử lý trong WP:* Báo cáo trạng thái **PARTIAL / ADAPTED**. Chúng tôi tận dụng `DirectorCompiler` cho nhịp điệu (rhythm), cỡ cảnh, chuyển động máy quay và tối ưu số lượng cảnh tối thiểu; sau đó chi tiết hóa quan hệ đối kháng hai người và tiếp xúc kiếm thuật trong tầng canonical `ShotSpec` (`blocking`, `performance_spec`, `continuity`).
2. **Khả năng điều khiển tham số gốc của Provider:**
   - *Thực trạng:* Tuyến Text-to-Video thông dụng (Dola / Seedance 2.0 / Veo) không hỗ trợ kiểm soát native thời lượng từng giây, không có native audio, không nhận multi-reference ảnh qua prompt thô.
   - *Xử lý trong WP:* Báo cáo trung thực qua các cờ `unsupported_controls` và cảnh báo `warnings` trong `PromptPlan`, chuyển hóa yêu cầu thành mô tả văn bản rõ ràng trong 10 khối canonical, không giả mạo rằng provider hỗ trợ native controls.
3. **Thẩm quyền khóa sáng tạo:**
   - Gói tiền kỳ này là **đề xuất kỹ thuật & sáng tạo đã được chứng minh khả thi** (`PREPROD_CREATIVE_PROPOSAL`). Quyền **CREATIVE LOCK** thuộc về Chủ sở hữu (Owner) và Tech Lead sau khi xem xét độc lập báo cáo này.

---

## 11. Kết Luận & Đề Xuất Hành Động Tiếp Theo

Gói tiền kỳ toàn phim cho *Nhất Kiếm Phá Vân* (60 giây / 12 cảnh) đã hoàn tất trọn vẹn, có thể tái lập 100%, bảo toàn tuyệt đối toàn bộ tài nguyên cũ.

**Bước tiếp theo đề xuất:**
1. Trình nộp báo cáo cho **Tech Lead GPT-6** thực hiện quy trình độc lập thẩm định (`independent PROVE`).
2. Tech Lead trình Owner phê duyệt khóa sáng tạo kịch bản/bối cảnh/tạo hình (`Owner Creative Lock`).
3. Owner xem xét cấp quyền **Đợt 1 (Wave-1)** cho 3 cảnh thử nghiệm then chốt (`X04`, `X08`, `X10`) với trần chi phí $0 và tối đa 4 lần phát hành trên tuyến miễn phí an toàn.
