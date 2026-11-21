# Audit quy trình SRT -> video (2026-11-01)

## 1. Cỡ cảnh (đếm tay 22 cảnh: demo 1 + đoạn 2 + đoạn 3)
| Cỡ cảnh | Số cảnh | Tỉ lệ |
|---|---|---|
| Rộng / toàn (LS/WS) | 4 (D-S3 sảnh trống, s13, s21, s22b) | 18% |
| Trung (MS, OTS, nhóm) | 5 (D-S2, s08, s11, s14, s15) | 23% |
| Cận vừa (MCU) | 6 (D-S1, D-S4, D-S6, s12, s18b, s19b) | 27% |
| Cận / insert (CU) | 7 (D-S5, s07, s09, s10, s16b, s17, s20) | 32% |
=> MCU trở lên = 13/22 = 59%. Đoạn 3: 5/9 = 56%.
Nguyên nhân: luật "một mặt đọc được mỗi khung" (né integrity_check), đạo cụ nhỏ phải phóng to, mỗi câu một cảnh, camera cố định nên không đổi cỡ bằng chuyển động.

## 2. Đo thật: độ sáng trung bình (Y) giữa các clip đoạn 3
s14 76 | s15 98 | s16b 113 | s17 114 | s18b 111 | s19b 113 | s20 118 | s21 111 | s22b 90
=> nhảy sáng tới 42/255 giữa s14 và s20; chưa có bước khớp màu giữa cảnh.
Âm lượng bản đoạn 3: -13.7 LUFS (chưa chuẩn hóa mục tiêu).
Độ phân giải bản giao: 1248x704 (chưa nâng 1080p).

## 3. Gap theo tầng
### Kịch bản / biên kịch
- Chưa có bước "visual treatment": mô-típ hình ảnh (ghim, bàn tay, ánh sáng), đường cong cảm xúc -> chọn cỡ cảnh theo nhịp cảm xúc.
- Chưa có sổ plant/payoff liên đoạn (nhẫn chưa từng hiện hình dù được nhắc; check_coverage chỉ kiểm trong một cảnh).
- Lời dẫn nội tâm ("dignity...") đang minh họa theo nghĩa đen; chưa dùng đối trọng/juxtaposition (Kuleshov) hay cutaway môi trường.
### Đạo diễn / coverage
- Chưa có quy tắc độ phủ: wide thiết lập đầu cảnh + sau mỗi ~3 cảnh; không quá 2 cảnh liền cùng cỡ; mỗi cú cắt đổi >=1 bậc cỡ hoặc >=30 độ góc.
- Eyeline/screen direction giữa các cảnh khác nhau chưa lint: nghi s16b (Marcus nhìn phải) ngược với s15 (Marcus ở phải khung, nhìn trái). Cách sửa nhanh: hflip cận mặt nền mờ, hoặc sinh lại keyframe.
- Staging lint chưa được gắn vào compile; còn chạy tay.
### Quay / camera
- 22/22 cảnh tĩnh. Không có chuyển động camera. Đề xuất: push-in số 4-6% trong post cho cảnh cảm xúc; phải thử độ mềm ở 1248x704.
- Chưa có camera bible: tiêu cự, độ cao máy, độ sâu trường ảnh theo cỡ cảnh (k17 góc rộng khác k15 tele).
- Chưa có khớp màu/grade chung theo cảnh; chưa nâng độ phân giải.
### Dựng
- Điểm vào của clip luôn là giây 0; chưa chọn cửa sổ trim theo hành động hoặc né lỗi (s18 gục đầu ở ~1.7s có thể né nếu có thêm thời lượng).
- Cắt theo khoảng lặng lời dẫn, chưa tinh chỉnh J/L-cut (nguồn: lệch ~0.5s thoại, tới ~2s khi vào đoạn lớn).
- Chưa có chuyển cảnh theo thời gian (flashback s07 vào/ra bằng dissolve hoặc grade khác).
- Ba đoạn chưa nối thành một timeline toàn cục với một track lời dẫn gốc; khe ~0.8s giữa demo 1 (kết 60.16) và đoạn 2 (bắt đầu 60.95) chưa được đối chiếu.
### Âm thanh
- Chỉ có lời dẫn. Không ambience, không foley (tiếng "clink" ghim được lời dẫn nhắc nhưng không có), không nhạc, không ducking, chưa loudnorm.
### Giao bản
- Chưa có phụ đề (SRT có sẵn nhưng chưa mux), tiêu đề, fade đầu/cuối, mục lục chương.
### Vận hành
- Tỉ lệ đạt ngay lần đầu: demo 4/6, đoạn 2 4/7, đoạn 3 6/10 video. Toàn phim ~165 cảnh, ước ~280 lượt sinh: chưa có kế hoạch thông lượng/song song.
- QC ngữ nghĩa (đếm người, tư thế, lỗi gục đầu, đạo cụ méo) chỉ do mắt đọc contact sheet; chưa có thang chấm cố định cho từng cảnh.
- Chưa có manifest nối clip <-> snapshot_id <-> prompt <-> keyframe.

## 4. Đã xử lý ngay (2026-11-01, đoạn 3)
- assemble_post.py: khớp độ sáng theo cảnh (Y về trung vị, hệ số 0.6, trần +-15, cảnh nối tiếp 'keep'), hflip chỉnh hướng nhìn (s16b), đẩy máy số 4% (s16b, s20), 1080p lanczos, tiếng phòng tổng hợp nhẹ, loudnorm -16 LUFS (đo -16.1), phụ đề mov_text từ cues.json.
- coverage_lint.py + sizes_all22.json: cảnh báo tỉ lệ cận 59% (>45%), 3 cảnh cận liền, thiếu cảnh rộng thiết lập, trùng cỡ liên tiếp, tái dùng keyframe.
- Chưa làm: foley (tiếng clink), nhạc, dissolve hồi tưởng, timeline toàn cục, J/L-cut tinh, trim theo hành động tự động.
