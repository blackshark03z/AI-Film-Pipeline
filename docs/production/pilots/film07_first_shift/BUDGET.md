# The First Shift — dự toán chờ xác minh quote và Owner duyệt

**DRAFT_NOT_AUTHORIZED.** Chưa khởi tạo phim sản xuất, Generate, upload hay chi credits. Trần cũ256,8credits giữ nguyên.
Các mức dưới đây là đề xuất. **Quote hiện hành đã đọc ngày 11/11/2026 (09:29, chỉ đọc giá hiển thị, không Submit/upload):
giá KHÔNG đổi so với 08/11** — Omni 1.2 Flash 360p: 6s = 6, 8s = 8, 10s = 10, 12s = 14, 15s = 20 credits (1 credit/s đến
10s, 2 credits/s từ giây thứ 11); ảnh Nano Banana 2.1 hiển thị 0 credits. Danh sách model và thông báo ngừng hoạt động
(Omni 1.1 Flash, Veo 3.1 Fast/Quality ngày 05/12) không đổi. Giá đọc khi chưa gắn đầu vào nên vẫn phải kiểm tra lại sau khi
gắn frame/ingredient. Bằng chứng: `C:/film-work/production-stability-p20/proof/flow-quote-20261111.json`. Số liệu có cấu trúc
và hash kịch bản nằm trong [budget.json](budget.json).

| Phạm vi | Số generation ×6s | Lượt đầu | Dự toán theo lịch sử | Kịch bản cao theo lịch sử | Trần đề xuất |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pilot SC01–02, đoạn đầu04:38 của chính phim này | 50 | 300 | 356,67 | 420 | 535credits |
| Toàn phim dự kiến27:37, đã gồm pilot | 300 | 1.800 | 2.140 | 2.520 | 3.210credits |

Trần toàn phim **đã bao gồm535credits của giai đoạn pilot**, không cộng hai khoản. Đây không phải thay đổi cap đang áp dụng.
Giá video là6credits cho6s ở Flow Omni1.2Flash360p (đo 08/11, xác nhận lại 11/11, không đổi nên mọi số trong bảng giữ
nguyên sau khi tính lại; dự toán chỉ dùng generation 6s, kéo dài trên 10s sẽ tính gấp đôi theo giây). Hệ số retake trung bình1,1889 và mức cao1,4 lấy từ ba phim cũ
trong `production.planning.RETAKE_FACTORS`; cap đề xuất bằng1,5lần dự toán trung bình. Các tỷ lệ đó chưa chứng minh cho
phim dài có đứng/ngồi, vào/ra khung và thao tác đồ vật. Giá ảnh đầu vào hiển thị hôm nay là0credits nhưng vẫn phải đọc lại quote;
không cho phép chi phí ảnh phát sinh ngoài dự toán đã duyệt.

Sau khi có quote hiện hành và Owner duyệt đề bài, quyền tài sản, trần toàn phim, agent chỉ thực hiện hai cảnh đầu để đo
diễn xuất, continuity, thao tác tay/đồ vật, chi phí và thời gian. Phần còn lại chỉ tiếp tục khi pilot qua QC dưới cùng trần
đã được duyệt. Mọi lượt gửi có prompt/hash đầu vào/quote đóng băng trong intent; giá hiển thị sau khi gắn đủ đầu vào phải
trùng khoản giữ chỗ. Giá thiếu hoặc thay đổi làm dừng trước Submit; kết quả chưa rõ phải đối soát trước lượt tiếp theo.

Chưa cam kết ngày giao hoặc số phim/ngày. Benchmark hậu kỳ dùng lại tư liệu kỹ thuật không đo được hàng chờ provider,
thời gian tạo still, retake hay diễn xuất của phim mới. Kết quả dự toán lịch sửP19 vẫn giữ nguyên, gồm FAIL_UNDERRUN;
không dùng số liệu mới để sửa kết quả cũ. Chỉ công nhận vận hành ổn định sau hai phim dài liên tiếp được Owner duyệt.
