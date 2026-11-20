# Báo cáo tổng hợp kiểm chứng Muse · Bản final

**Mốc hồ sơ 18/11/2026 · Từ các pilot đầu đến R51 · Đã đối chiếu 19 thư mục điều tra**

Muse đã tạo được footage chuyển động và thoại native, nhận một ảnh mở đầu theo từng shot, trả MP4 có thể xác thực và hỗ trợ dựng từ các đoạn nguồn đã chọn. Bản dựng nội bộ *The Spare Jacket* Cut 08 dài **14:31.375**, có 243 cue và hồ sơ đồng bộ. Bản mở rộng còn chờ nghiệm thu sáng tạo.

Các kết quả hỗ trợ quy trình có giám sát theo từng shot. Hồ sơ chưa xác lập năng suất theo **giây footage được chủ dự án duyệt trên mỗi lượt sinh** hoặc khả năng tự hoàn thành phim 25–35 phút đạt yêu cầu hình, tiếng và diễn xuất.

## Cách đọc nhãn

| Nhãn | Ý nghĩa |
| --- | --- |
| **ĐÃ CHỨNG MINH** | Có đầu ra, biên nhận, phép đo hoặc đối chứng trong hồ sơ. Kết luận chỉ áp dụng cho mẫu, giao diện và điều kiện ghi kèm. Kết quả thất bại có bằng chứng cũng mang nhãn này. |
| **CHƯA KIỂM CHỨNG** | Đề xuất, lời Agent tự báo thiếu đối chứng, khả năng được nêu trong tài liệu nhưng chưa chạy, hoặc suy rộng vượt thiết kế thử nghiệm. Một phép đo có thể đã xác nhận trong mẫu trong khi cơ chế giải thích hoặc tính tổng quát vẫn mang nhãn này. |

**Bốn mốc kết quả** gồm nhận MP4 gốc, đạt kiểm tra kỹ thuật, có đoạn ứng viên để dựng và được chủ dự án duyệt. Mỗi mốc có mẫu số riêng. Các tập kiểm tra dùng lại footage giữa nhiều vòng.

**Ba thành phần** gồm Muse Agent điều phối công cụ và file, Muse Image/Video sinh nội dung, và tầng dựng thực hiện QC, EDL, đồng bộ và xuất bản xem. Kết quả ở mỗi thành phần chỉ xác nhận phần việc tương ứng.

## 1. Agent, định dạng đầu vào và luồng giao nhận

| Nhãn | Phát hiện hợp nhất | Hồ sơ |
| --- | --- | --- |
| **ĐÃ CHỨNG MINH** | Orchestrator đã chuyển gói chứa ảnh T0 và prompt tiếng Anh cho Muse, theo dõi mã gửi, nhận MP4 và đối chiếu SHA-256. Gói Alma `fd_welcome` lưu cả đầu vào và kết quả của lượt gốc. Trong gói này các trường `first_frame`, `last_frame`, `references` và `audio_mode` thuộc hợp đồng Orchestrator. Biên nhận của Agent ghi một lệnh sinh dùng prompt văn bản và một ảnh, không kèm mẫu giọng. Gói lưu đủ dữ liệu để đối chiếu SHA đầu vào, prompt và MP4. Audit R29 đối chiếu **27/27** bộ file cục bộ của Cut 07–09 khớp prompt, SHA ảnh, SHA và số byte MP4 với yêu cầu và biên nhận do Agent ghi. Hồ sơ này xác nhận bộ file nhất quán. Chuỗi gọi backend và số lần retry vẫn dựa vào biên nhận Agent. Bộ kiểm schema R29 đạt **12/12 ca mô phỏng cục bộ**. | S01, S03 |
| **ĐÃ CHỨNG MINH** | Schema runtime thu được trong phiên R47 của `media.generate_video` có bốn trường `prompt`, `name`, `output_dir`, `resume_from_snapshot_id`. `prompt` bắt buộc, là mảng có thứ tự với loại `text` hoặc `image`. Schema không công bố trường MP4, audio mẫu, seed, duration, fps, resolution, end frame, keyframe theo thời gian hay quỹ đạo camera. R19 đính kèm được MP4 ở giao diện nhưng lời gọi sinh native báo không hỗ trợ đầu vào video. Mô tả tool giới hạn **6 video thành công/tin nhắn**. Các MP4 thường gặp dài 10 giây, 24 fps. Pilot Valerie từng ghi một đầu ra 4 giây và pilot Character DNA có 14/14 clip dài 10 giây dù yêu cầu 5 giây. | S02, S03, S07, S12 |
| **ĐÃ CHỨNG MINH** | Mô tả runtime ghi công cụ chuyển yêu cầu sang subagent chuyên sinh video để mở rộng prompt. Thứ tự thực tế của các mục ảnh/văn bản đáng lưu trong biên nhận. R34–R35 có trường hợp Agent báo đã xen văn bản gắn vai trò ảnh giữa các ảnh. | S03, S05, S12 |
| **ĐÃ CHỨNG MINH** | Một tin nhắn batch có thể trả nhiều ảnh riêng. R24 nhận 8 ảnh từ 2 yêu cầu, khoảng 129,4 giây. R35 dùng 2 tin nhắn, giới hạn một lần gọi mỗi tin, yêu cầu tổng cộng 8 ảnh và nhận 2 PNG. Schema Agent không có `n/count`. Một mẫu R46 xác nhận ảnh từ CDN là WebP 2048×1152 và file lưu trong workspace là PNG 2048×1152, lớn hơn khoảng 7,87 lần trong ca đó. SoT ghi Muse Image đã tạo ảnh theo nhiều bối cảnh từ chân dung mẫu và trả file chỉnh màu cốc. | S02, S05, S11, S12, S15 |
| **ĐÃ CHỨNG MINH** | R10 lúc chạy chỉ có 4 thông báo hoàn tất và chưa nhận được MP4 mục tiêu. R44 về sau có hai MP4 coffee A/B của R10 để đo. R39B đọc ngay MP4 gốc còn trong workspace, không cần tải lên lại, khớp 2/2 hash frame và 5/5 khoảng freeze với PC. R40 trả MP4 và QC trong cùng lượt theo nhật ký giao diện, trong khoảng quan sát **78,36–93,52 giây**. Hai hash frame mù của MP4 R40 được PC tính lại và khớp. Thứ tự và số lần gọi công cụ trong nội bộ vẫn dựa vào biên nhận Agent. | S02, S08–S10 |
| **ĐÃ CHỨNG MINH** | Ở các lượt được ghi nhận, sidecar dẫn tới bản MP4 gốc, một lần tải mất 0,931 giây và khớp SHA-256 với bản lưu. R47 nhận 2 MP4 trong khoảng **54,6 giây** qua luồng nhận trực tiếp, toàn lượt chat khoảng 63,0 giây. Hai lô 6 MP4 của R48/R49 mất **68,78 / 72,33 giây** đến khi nhận đủ raw. Các số đo dùng mốc gửi–nhận của từng lô, trước kiểm duyệt sáng tạo. | S11–S13 |
| **ĐÃ CHỨNG MINH** | R45 lưu dấu vết Noise/WebSocket, danh mục thành phần VM và trạng thái trước/sau khi dọn trên Muse_Pool_01 ngày 18/11. R46 ghi một lô thử lặp nhận 6/6 shot, tệp bộ nhớ chính vẫn 367 byte và từ sidecar cuối đến khi đóng ZIP mất 26 giây. Bộ đóng gói của dự án lúc kiểm tra truyền ảnh 2048×1152 chưa chuẩn hóa và ghi giờ địa phương vào trường thời gian DOS của ZIP, khiến mốc sửa file hiển thị lệch +7 giờ khi đọc trên VM Linux. | S11 |
| **CHƯA KIỂM CHỨNG** | Số lệnh sinh ảnh thực tế bên dưới batch R24, giới hạn song song bền vững của backend, tốc độ ở mọi phiên, mức đóng góp riêng của từng thay đổi VM vào độ trễ và mức hao token. Model/version thực sự xử lý từng lượt sinh cũng chưa được xác minh nhất quán trong toàn bộ hồ sơ. Hai tab cùng hoàn tất hoặc một batch nhanh là quan sát theo phiên. Báo cáo R45 có các nguyên nhân khả dĩ cho lỗi đính kèm và tiêu tốn token, nhưng thiếu phép cô lập nguyên nhân ở mọi ca. | S02, S05, S11–S12 |
| **ĐÃ CHỨNG MINH** | R37 đo mức giống hướng chuyển động trên cùng nguồn để kiểm công cụ QC. Điểm cosine là **0,9984** khi chỉ chỉnh màu, **0,4070** khi giữ đứng hình từ giây 4 và **−0,7439** khi đảo thứ tự frame. R38 có **19 kiểm thử ngoại tuyến** về request, hình học với tọa độ mô phỏng và quy tắc chọn phương án. | S07 |
| **CHƯA KIỂM CHỨNG** | API công khai chính thức dùng để sinh Muse Video và temporal V2V giữ diễn xuất/âm thanh trên tài khoản dự án. R37–R38 ghi nhận useapi.net và Runway Aleph có bề mặt V2V được tài liệu hóa. Tài liệu lưu ở R38 mô tả `n` cho biến thể trong Meta Muse Image Model API và giao diện phân đoạn/theo dõi của SAM 3.1. Chưa có kiểm chứng inference trên dữ liệu dự án hoặc quyền gọi model trả phí. | S07 |

## 2. Khung hình đầu, ảnh tham chiếu và nối cảnh

### ĐÃ CHỨNG MINH

- **Chuẩn hóa T0 ngang có tác dụng rõ trên các mẫu đã đo.** Từ 183 cặp *The Spare Jacket* có bản ghi chi tiết trong JSON R45, **153/153** ca dùng T0 1280×720 cho MP4 1280×720, PSNR frame 0 trung vị 38,14 dB. R45 báo tổng hợp rộng hơn 189 cặp cục bộ và thêm 18 shot đối chiếu. R46 đo 35/35 clip 1280×720 với trung vị 37,88 dB. Các tập cùng dùng kho footage sản xuất và có thể trùng nguồn. R47B thử song song cùng ảnh gốc và prompt. Ảnh 2048×1152 cho MP4 1248×704 và PSNR 14,36 dB, ảnh chuẩn hóa 1280×720 cho MP4 1280×720 và PSNR 35,43 dB (**+21,07 dB**). Zoom theo chiều cao mặt ở cặp này giảm từ 1,407× xuống 1,113×. [S11, S12]
- **T0 dọc có một cặp đối chứng cùng xu hướng.** R51: 1152×2048 → 704×1248, PSNR 15,19 dB. Nhánh 720×1280 → 720×1280, PSNR 35,50 dB (**+20,31 dB**). Metadata đầu ra của cả cặp ngang và cặp dọc đã được đọc lại bằng ffprobe trong lần tổng hợp. [S12, S14]
- **Ảnh chuẩn kỹ thuật vẫn có thể sai bố cục hoặc trạng thái.** Sau khi R33 đã sinh hai video thử tay–phong bì, phép kiểm hồi cứu xếp cả hai ảnh nguồn vào diện phải chặn trước render vì thiếu biên an toàn và chưa tách rõ tay khỏi đạo cụ. R34 và R35 mỗi vòng có 2 PNG nguyên bản, đều bị chặn trước khi gọi video. Các lỗi chung gồm thiếu khoảng trống trên đầu, tay sát phong bì và thừa cốc. R35 còn có ảnh 2240×1120 lệch tỉ lệ yêu cầu. Các pilot cũ ghi nhận thêm đạo cụ ở đầu clip và sai states sau T0. Trong R48/R46 có một shot dùng nhầm T0 chân dung với prompt ngoại cảnh máy bay, sau đó chuyển đột ngột sang ngoại cảnh tĩnh. Kiểm cả nội dung T0 và kích thước ảnh trước render. [S02, S05, S11, S13]
- **Nối bằng ảnh endpoint khả thi.** R30: snapshot riêng, ảnh T0 ban đầu riêng và snapshot + T0 ban đầu đều cho seam khoảng **10,82–10,87 dB** so với cuối SEED. Dùng ảnh trích đúng frame cuối SEED cho **34,69 dB / SSIM 0,9545**. R31 trích điểm cắt sớm phù hợp hơn, đạt **SSIM 0,97136**. R32 lặp kỹ thuật theo hai nhân vật, đạt seam **0,94892** với Alma và **0,97319** với Malcolm. Tái đo trực tiếp **7 cặp ảnh–frame đầu** từ các ZIP R30–R32 cho cùng kết quả ở độ làm tròn đã công bố. Cả bốn take R32 vẫn trượt hợp đồng nguyên clip. Khi dựng một đoạn `[in, out)`, frame phù hợp để thử nối trực tiếp là `out-1` của đoạn đã chọn. [S04, S05]
- **Snapshot + endpoint có một ứng viên tốt về chuyển động.** R48 thử cùng một đoạn nối. Snapshot riêng đạt **8,93 dB**, ảnh endpoint riêng **36,56 dB**, còn snapshot + endpoint **35,35 dB**. Nhánh kết hợp có tỷ số chuyển động cuối/đầu **0,909**, so với **0,683** và **0,214** của hai nhánh còn lại, và có ít mẫu nhắm mắt hơn trong phép đo. Chất lượng khớp hình tại điểm nối cao nhất trong cặp có ảnh thuộc về nhánh chỉ ảnh. [S13]
- **Hai ảnh trong cùng lượt sinh đã có MP4 thật.** R48_4 dùng hai ảnh có thứ tự, frame đầu đạt **35,41 dB** so với ảnh thứ nhất. Nhân vật có chuyển sang bối cảnh mục tiêu, frame cuối chỉ đạt **8,42 dB** so với ảnh thứ hai. Kết quả xác nhận một ca điều hướng ngữ nghĩa bằng ảnh thứ hai và trực tiếp cho thấy ca này không khóa pixel khung cuối. [S03, S13]

### CHƯA KIỂM CHỨNG

- Khóa tuyệt đối frame đầu/cuối, cấu trúc lưới latent cụ thể, cơ chế bên trong xử lý ảnh thứ hai và quy tắc áp dụng cho mọi kích thước hoặc phiên bản. Kho lưu trước R45 có cả đầu ra 1152×768. Bảng chi tiết R45 cũng có 13 T0 800×450 cho đầu ra 1280×720 với PSNR trung vị 15,51 dB. Chỉ số PSNR/SSIM toàn khung đo độ giống ảnh tại điểm nối. [S02, S11–S14]
- Ưu thế ổn định của snapshot kết hợp ảnh qua nhiều cảnh, nhân vật và lượt lặp, cũng như khả năng giữ trạng thái tay, đạo cụ và diễn xuất qua chuỗi dài. R48 có một clip mỗi nhánh. Kết quả của snapshot không giải thích được riêng từ PSNR. [S04, S13]
- Chỉnh ảnh sinh bằng AI mà bảo toàn nguyên pixel ngoài vùng đạo cụ chưa có xác nhận độc lập. [S02]
- Nhận diện khuôn mặt ổn định 95–100% bằng Character DNA, same-thread hoặc chuỗi ảnh Master→T0→Video. Pilot 14 MP4 ghi trôi mặt dù dùng lại DNA văn bản. KHOIKK03 có tương đồng thị giác ở 4 cảnh với 1 nhân vật, đồng thời có một lần render lại và lỗi mắt, quay đầu, đạo cụ. Độ đồng nhất qua nhiều người và cảnh còn thiếu đánh giá độc lập. [S02]

## 3. Diễn xuất, chuyển động, giọng và thoại

| Nhãn | Phát hiện hợp nhất | Hồ sơ |
| --- | --- | --- |
| **ĐÃ CHỨNG MINH** | Có chuyển động native thực. Biên độ và thời điểm hành động thay đổi khi lặp nguyên ảnh/prompt trong R9. Các ca khác ghi nhận nhắm mắt kéo dài, cúi/quay đầu quá mức, đạo cụ tự đổi trạng thái, tay sai điểm tiếp xúc và camera làm mất vật quan trọng. Ví dụ R25 có đoạn nâng góc phong bì khoảng 3,5–4,5 giây rồi dựng giấy quá cao. R33 thử chuẩn bị trước vị trí tay, nhưng cả hai take vẫn trượt hợp đồng. R36 vẫn sai tay, phong bì hoặc camera ở nguyên take dù tách riêng insert và reaction. | S02, S05, S06, S10 |
| **ĐÃ CHỨNG MINH** | Prompt có thể thay đổi kết quả camera trong điều kiện thử. Có đối chứng KEYS và R26 giữa chỉ dẫn giữ máy và prompt dễ đẩy máy, R40 có một take camera gần cố định. R51 ghi độ phóng đại của mặt **3,932×** với dolly chung chung và **2,574×** với prompt giữ các mốc trong khung. Cả hai vượt mục tiêu đẩy nhẹ. R39 thử ổn định hậu kỳ trên ca zoom/crop nặng và vẫn mất bố cục cần thiết. | S02, S08, S09, S14 |
| **ĐÃ CHỨNG MINH** | R49 trên một T0 cảnh đôi: prompt tối giản sinh 15 từ ngoài kịch bản và face zoom 1,643×. Nhánh mô tả khẳng định theo 5 nhóm chi tiết, Foley nhẹ và yêu cầu không thoại có một take với scale camera lệch 0,19%, ASR 0 từ. Nhánh ràng buộc số học/phủ định cũng giữ camera nhưng chuyển động cuối giảm rõ. R48 có một phép so Foley và im lặng, nhánh Foley giữ chuyển động cuối nhiều hơn nhưng camera bám theo hành động rộng. | S13 |
| **ĐÃ CHỨNG MINH** | Thoại tiếng Anh có thể được sinh đúng chữ và ráp từ MP4 native. R32 ghép **8,5417 giây** thoại Alma từ hai lượt. Bản QC từ ZIP ghi ASR khớp sau chuẩn hóa dấu câu, khoảng ngừng nội bộ tối đa 1 giây và giọng chưa được chủ dự án nghe duyệt. Các ví dụ R47–R49 dùng những câu và điều kiện khác nhau. Có ca 8–13 từ kèm lời loa ngoài kịch bản, hai nhánh 18 từ khớp câu, một ví dụ khoảng 25 từ đủ nội dung và một ví dụ khoảng 42 từ bị nói nhanh rồi mất phần cuối. Các mẫu yêu cầu im lặng vẫn có thể kèm track AAC hoặc có lời tự phát. | S02, S03, S05, S13 |
| **ĐÃ CHỨNG MINH** | R46 quét 43 clip. Trong tập 35 phim hàng không, không có freeze theo ngưỡng của nhóm 29 clip mang nhãn thoại và 2 clip đi bộ. R46 ghi cờ mắt nhắm kéo dài ở **7/31** thuộc nhóm 1280×720 mà JSON đánh dấu có thoại và **4/6** thuộc nhóm phản ứng 1248×704 mà JSON đánh dấu im. Bốn ca có cờ của nhóm thứ hai đều cho câu rõ trong hai lượt ASR offline khi rà lại (mục 7). R46 cũng ghi 5,04% và 15,02% mẫu bị gắn cờ ở hai cửa sổ trước và sau mốc hết lời ước lượng trên 20 clip. | S11 |
| **CHƯA KIỂM CHỨNG** | So sánh mắt nhắm giữa cảnh có thoại và cảnh thật sự im lặng bằng tỷ lệ 7/31 và 4/6. Nhãn đầu vào của nhóm đối chứng không phù hợp với kết quả ASR mới. So sánh trong clip của R46 vẫn là quan sát theo thời điểm. Ảnh hưởng nhân quả của thoại còn mở. | S11, mục 7 |
| **ĐÃ CHỨNG MINH** | Cảnh đôi một người nói đạt cách ly chuyển động môi **41,8×** và **14,5×** ở hai take R50 đối xứng dùng cùng ảnh mở đầu. Một take đối đáp hai lượt có hai giọng, đồng thời người nghe vẫn cử động môi ở nửa sau. Mức cách ly là tỷ số của chỉ số mở môi/hàm lấy mẫu. | S14 |
| **ĐÃ CHỨNG MINH** | Giọng có cặp gần nhau trên phép đo. R33 dùng speaker embedding, Alma R32 giữa hai đoạn **0,8878**, còn so với bản Alma cũ khoảng **0,80**. R50 dùng một phép đo khác: snapshot + T0 cảnh mới cho F0 **193,5 Hz** gần mẫu 189 Hz hơn gọi mới **200,0 Hz**. MFCC so với tham chiếu R47B là **0,9701** so với **0,9658** của gọi mới. So với tham chiếu R48_3, gọi mới đạt **0,9869** và snapshot đạt **0,9797**. Thứ hạng MFCC phụ thuộc vào mẫu tham chiếu. | S05, S14 |
| **ĐÃ CHỨNG MINH** | Có lần sinh bị chặn với mã `public_figure_likeness` trong sidecar R45/R46/R51. R51 ghi một ca gốc bị chặn và một biến thể đồng thời đổi ảnh nền lẫn cách mô tả nhận được MP4. Phép thử đổi cả hai yếu tố cùng lúc, nên chưa tách được tác động của ảnh và câu chữ. Usage được ghi chung cho cả lô. | S11, S14 |
| **CHƯA KIỂM CHỨNG** | Quy tắc cố định về chiều dài câu thoại, trim tự động tại ASR end +0,35 giây, khả năng Foley hoặc thoại trực tiếp ngăn lỗi mắt/camera, và tác dụng phổ quát của prompt 5 nhóm chi tiết. Các nhóm R46 khác loại cảnh, ảnh và độ phân giải. So sánh trước/sau khi hết lời cũng trùng với vị trí khác nhau trong clip. R48–R51 chủ yếu có một take cho mỗi cấu hình. | S11, S13, S14 |
| **CHƯA KIỂM CHỨNG** | Khóa màu giọng bằng snapshot xuyên cảnh, khẩu hình khớp đến từng frame và độ ổn định cảnh hai người nói. ASR, F0, MFCC và speaker embedding đo các khía cạnh riêng. Chưa có ngưỡng voice match được hiệu chuẩn cho toàn dàn diễn viên hoặc nghiệm thu mù trên phim dài. | S05, S14 |
| **CHƯA KIỂM CHỨNG** | Kiến trúc Joint Audio–Video DiT, cách subagent diễn giải từng mệnh lệnh, nơi và thời điểm chính xác bộ lọc likeness chấm hình, khả năng lặp lại biến thể R51 và tương quan quota cho từng lần bị chặn. Metadata AAC mono 24 kHz và video 24 fps mô tả file đầu ra. | S11, S12, S14 |

## 4. Cắt dựng và kiểm định chất lượng

| Nhãn | Phát hiện hợp nhất | Hồ sơ |
| --- | --- | --- |
| **ĐÃ CHỨNG MINH** | `muse.exec` và FFmpeg có thể giải mã, kiểm freeze và cắt đúng đoạn nguồn. R39 xác thực đoạn 24 frame từ frame 24, SSIM trung bình 0,98019 sau mã hóa lại. PC local cắt cửa sổ 24 frame với thời gian trung vị khoảng 0,44 giây qua ba lần thử. Bộ kiểm EDL R39 chặn hash sai, frame trùng/vượt phạm vi và thiếu phê duyệt hoặc audio gốc khi xuất bản. Cắt dựng sử dụng frame đã có. | S08 |
| **ĐÃ CHỨNG MINH** | Dùng SHA và giải mã đầy đủ để xác nhận nguồn. Các phép đo khung đen, freeze và thay đổi kích thước nền hỗ trợ sàng lọc. R36 chọn **5,5 giây ứng viên** gồm insert 1,5 giây trước khi chạm phong bì và reaction 4 giây. Cả hai qua phép kiểm chuyển động dành riêng cho cửa sổ ở R36, dù nguyên take đều bị chặn. R41C thêm ứng viên R40 3 giây và áp cổng camera/freeze, còn **4,5/8,5 giây**. R41C loại riêng đoạn reaction R36 vì vượt giới hạn camera 2% ngay frame 36. Hai cửa sổ còn lại chưa được chủ dự án duyệt. | S06, S08, S09 |
| **ĐÃ CHỨNG MINH** | R42 giữ ngưỡng R41 trên 21 MP4 ngoài tập đặt ngưỡng. Kết quả freeze khớp 21/21 báo cáo cũ. R42 báo zoom nền mạnh ở 15/21 clip, 5 gần cố định và 1 cần xem lại. R42B thử quy tắc camera hai chiều đã sửa trên 11 MP4 khác từ R26/R30 và khớp mô tả báo cáo ở 6/6 mẫu R26. Nhãn này lấy từ phép đo hoặc báo cáo cũ. Camera chủ động di chuyển vẫn có thể đúng brief. | S09 |
| **ĐÃ CHỨNG MINH** | YuNet hỗ trợ đánh dấu có mặt, nguy cơ crop và góc nghiêng. Hai clip profile R43C có **79/80** mốc YuNet phát hiện so với **8/80** MediaPipe. MediaPipe có quyết định mở/nhắm ở **10/47** mẫu mắt có nhãn rõ trong R43, trong đó 1 báo nhắm sai, 37 mẫu còn lại không quyết định. Các nhãn này đến từ một reviewer xem ảnh mẫu. | S10 |
| **ĐÃ CHỨNG MINH** | Hand Landmarker bỏ sót tay, nhất là theo phối cảnh. R44 có 11 clip qua hai đợt thử, gồm 1 clip đối chứng đã dùng ở R43B. Trên 50 ảnh của 5 clip giữ lại ở đợt đầu, detector thấy tay ở **9/30** ảnh thực sự có tay. Phép đo vùng ảnh báo sai 7/20 ảnh không có tay trong nhóm 3 clip đủ điều kiện đối chiếu. Khi chỉnh vùng ảnh rồi thử trên 5 clip mới R44E, báo sai **15/26** ảnh không có tay. Không thể tự chấm điểm tiếp xúc hoặc trạng thái đạo cụ từ tín hiệu này. | S10 |
| **ĐÃ CHỨNG MINH** | Freeze, gần tĩnh và trùng pixel là ba phép đo khác nhau. R44C thấy **0/1.434** cặp frame liền nhau giống hệt pixel, dù FFmpeg vẫn báo freeze ở một số đoạn. Source hash, biến thiên pixel và khoảng chuyển động là lớp kiểm kỹ thuật. Hành động đúng kịch bản, mắt, tay và đạo cụ cần được đánh giá trên chuỗi hình. | S10 |
| **ĐÃ CHỨNG MINH** | Giữ nguyên sample của narration bằng mux PCM đã có đối chứng: KEYS **137 frame / 274.000 mẫu / khoảng 5,708 giây**, PCM giải mã khớp bit. R6 có bản nghiên cứu MKV **102 giây** đối chiếu PCM gốc được báo cáo khớp bit, nhưng chỉ 10,5 giây hình native trong toàn dựng. Cut 08 đo **0 ms lệch âm tăng thêm ở độ phân giải 10 ms** cho 18 đoạn chèn. Ba kết quả dùng các tiêu chí khác nhau. | S01, S02 |
| **CHƯA KIỂM CHỨNG** | Cổng camera theo khoảng mất dấu R44F có tác dụng tổng quát. Nó được đặt sau khi thấy R16 có bốn mốc cuối không đo được và chỉ hạ một ca trong tập R44. R46 chạy thêm trên một tập khác với 0 cờ hạ cấp, chưa đủ đối chứng ca lỗi để khẳng định khả năng bắt lỗi. | S10, S11 |
| **CHƯA KIỂM CHỨNG** | Tự duyệt chính xác face identity, eye-line, diễn xuất, lip-sync, chữ trên đạo cụ hoặc quan hệ tay–vật. Kiểm định còn thiếu nhãn độc lập trên nhiều diễn viên và loại shot. Khả năng giữ PCM bit-exact trên master dài chưa được xác lập, và bản mã hóa lossy cần đánh giá theo đồng bộ và chất lượng nghe. | S01, S02, S08–S11 |

## 5. Tiến độ sản xuất, quota và giới hạn ngoại suy

| Nhãn | Mẫu hoặc kết luận | Hồ sơ |
| --- | --- | --- |
| **ĐÃ CHỨNG MINH** | **Valerie R3:** SoT tổng hợp 9 MP4, 7 PASS, 1 PARTIAL, 1 FAIL theo review nguồn, khoảng **56/60 giây** có thể dựng. **KEYS R1/R2:** Agent báo thiếu coverage đúng ở **1/4**. **Blue Envelope:** EDL 60 giây gồm **37,5 giây covered**, 18,5 giây planned, 4 giây gap. Kết quả 367 PASS thuộc preflight đầu vào. SoT còn ghi sáu mẫu prompt/shot được chủ dự án nhận xét đạt thủ công trong tháng 10, theo từng thử nghiệm và format lúc đó. Các kết quả lịch sử này được dẫn lại qua SoT. Các ledger R42–R44 dẫn được tới mẫu video của R11–R13, R15–R17 và R23–R28, tùy nhóm thử. Những vòng không có mẫu trong các nhóm này được dẫn theo tài liệu lưu, ví dụ R19 qua R37. | S02 |
| **ĐÃ CHỨNG MINH** | **R6–R10:** Bản nghiên cứu 102 giây xác nhận dựng và giữ narration, nhưng 91,5 giây đến từ ảnh tĩnh có chuyển động hậu kỳ. Theo yêu cầu 100% native của R7, phần đó không tính coverage. R8 có 20 giây raw và một đoạn 4 giây chờ review, thiếu coverage để dựng đủ mẫu 30 giây. R9 lặp và nhận 5/5 MP4 nhưng có sai cường độ hoặc nhịp diễn. | S02 |
| **ĐÃ CHỨNG MINH** | **R24–R28:** R29 tổng hợp **21/22 raw MP4**, **0/21** đạt toàn bộ hợp đồng nguyên take của nhóm thử chuyển động. **R32:** 4/4 raw, **13,875 giây ứng viên / 4 lượt = 3,47 giây ứng viên/lượt**, 0 giây được chủ dự án duyệt trong vòng này. **R24 C6:** một lô nhận 6/6 MP4 trong khoảng 138,4 giây nhưng cả 6 trượt hợp đồng nguyên take. | S03, S05, S15 |
| **ĐÃ CHỨNG MINH** | **The Spare Jacket:** hồ sơ R29 ghi 27 shot thoại native, 162,04 giây được chọn vào EDL. Trong hồ sơ dự án, Cut 07 nhận 8/8 yêu cầu, bản dài **13:29.875**. Cut 08 nhận 10/10 yêu cầu, dài **14:31.375**, 243 cue. Mốc **9:08** là bản đã duyệt được dùng làm cơ sở dựng. Cut 07/08 là kết quả giao nhận và dựng nội bộ. Bản mở rộng chưa có nghiệm thu sáng tạo trọn phim. | S01, S03 |
| **ĐÃ CHỨNG MINH** | **Quota Free đã quan sát:** trên Muse_Pool_03, 0 → 2 → 8 → 14 video thành công tương ứng **0% → 5% → 20% → 35%** Usage. R50/R51 tiếp tục lên **50% → 62%** sau 11 video thành công và một ca bị chặn. Riêng R51 có 6 sidecar, trong đó 1 sidecar lỗi và 5 MP4. Các vòng này dùng quota kèm theo, báo cáo ghi 0 chi phí phát sinh. Đây là số đọc hiển thị trên một profile trong kỳ theo dõi. | S12–S14 |
| **CHƯA KIỂM CHỨNG** | Công suất **40 clip/tuần/tài khoản**, 120 clip/tuần từ ba profile, 200 job/ngày, quota cho mọi độ dài/độ phân giải và chính sách tính các lượt lỗi. 40 clip/tuần là phép ngoại suy từ khoảng 2,5 điểm phần trăm/video trong đợt thử. | S02, S12–S14 |
| **CHƯA KIỂM CHỨNG** | Tự động hoàn thành phim 25–35 phút hoặc 200 shot đủ coverage, có QC và chủ dự án duyệt. Mốc **≥4 giây duyệt/lượt** trong R29–R36 là ngưỡng nghiên cứu. Với 200 đoạn cho 30 phút, timeline còn đòi khoảng **9 giây sử dụng/đoạn** nếu mỗi đoạn tương ứng một shot. Hồ sơ ứng viên, tốc độ nhận raw và preflight chưa trả lời năng suất giây duyệt. | S01, S02, S03, S05, S06, S09 |

### Luồng đã có cơ sở để dùng có giám sát

1. Chốt từng beat/câu thoại và ảnh T0. Kiểm mặt, bố cục, hướng nhìn, vùng tay/đạo cụ và khớp nội dung giữa ảnh với prompt. Với định dạng đã thử, chuẩn hóa ngang 1280×720 hoặc dọc 720×1280.
2. Theo dõi lệnh theo mã shot. Thu MP4 gốc và xác nhận SHA, thông số, decode. Khi Agent báo xong nhưng thiếu MP4, đối soát asset và biên nhận trước khi tính thêm một lượt sinh.
3. Kiểm theo loại shot. Dùng camera/freeze và detector để tìm đoạn cần xem. Nghe/xem ở tốc độ thật để chấm thoại, giọng, khẩu hình, mắt, tay, đạo cụ và hành động. Đoạn không theo dõi được giữ ở trạng thái chờ kiểm.
4. Ghi khoảng frame nguồn duy nhất đã chọn trong EDL, dựng theo clock audio/SRT của dự án, đối chiếu bản xuất. Khi hợp đồng yêu cầu footage native 100%, chỉ tính các cửa sổ từ MP4 native và ghi rõ khoảng thiếu coverage.

## 6. Chỉ mục nguồn và phạm vi đã kiểm tra

**Gốc tra cứu** `C:\Users\ADMIN\Documents\Nghiên cứu\Video\Kiểm chứng muse\Luu-tru-bao-cao-cu\`. Toàn bộ báo cáo gốc, ZIP, MP4, ảnh, bảng đo và mã kiểm tra được lưu dưới đây theo cấu trúc cũ. Các tên tệp ở cấp gốc tra trực tiếp trong thư mục này. Các đường dẫn thư mục trong bảng cũng tính từ gốc lưu trữ.

| Mã | Thư mục / hồ sơ | Bằng chứng để truy lại |
| --- | --- | --- |
| S01 | Cấp gốc của kho lưu trữ | `MUSE_ORCHESTRATOR_THE_SPARE_JACKET_PROVE_STABLE_2026-11-17.md` và `ALMA_FD_WELCOME_MUSE_REPLAY_2026-11-17.zip`. Gói Alma chứa ZIP gửi và ZIP trả về với MP4 cùng biên nhận. |
| S02 | Cấp gốc của kho lưu trữ | `MUSE_META_AGENT_VIDEO_CAPABILITY_EVIDENCE_SOT_2026-11-15.md`. Các mục 1–35 chứa pilot trước R29, các mục 36–40 nối lại R45–R51. Nguồn ngoài thư mục được dẫn qua SoT. |
| S03 | `MUSE_R29_TECHNICAL_REQ_RES_AUDIT_20261117/` | `R29_TECHNICAL_REQ_RES_CAPABILITY_MAP_VI.md`. ZIP R29 có `R29_REDACTED_ACTUAL_REQ_RES_27.json`, schema do Agent báo, 12 ca kiểm ngoại tuyến và relay. |
| S04 | Hai thư mục R30 và R31 bên trong R29 | `R30_FINAL_VERDICT_VI.md`, `R31_FINAL_QC_VERDICT_VI.md`. ZIP từng vòng có manifest nhánh, ảnh trích từ video, MP4 và JSON đo frame đầu. |
| S05 | `R32_TWO_ACTOR_EDITORIAL_CHAIN_20261117/` | Báo cáo R32 và addendum giọng. ZIP chứa stage ledger, clip Alma/Malcolm, EDL, ASR và kết quả nối frame đầu. |
| S05 | `R33_SPEAKER_AND_PROP_STATE_20261117/` | Báo cáo R33, `R33_FINAL_VERDICT.json`, số đo speaker embedding, ảnh nguồn, gate T0 và clip thử tay–phong bì trong ZIP. |
| S05 | `R34_WIDE_T0_PREFLIGHT_20261117/` | Báo cáo R34. ZIP chứa hai PNG, biên nhận, thứ tự các mục prompt và kết quả kiểm bố cục. |
| S05 | `R35_BATCH4_GEOMETRY_AUDIT_20261117/` | Báo cáo R35. ZIP chứa hai PNG nguyên bản, nhật ký các lượt batch và `R35_FINAL_GATE_VERDICT.json`. |
| S06 | `R36_INSERT_REACTION_COVERAGE_20261117/` | Báo cáo R36, gate nguyên take, `R36_SOURCE_WINDOW_TECHNICAL_GATE_V2.json` và ZIP chứa EDL 132 frame thử dựng. |
| S07 | `R37_VIDEO_CONDITIONING_CONTROL_AUDIT_20261117/` | Báo cáo R37, ma trận khả năng điều khiển, kế hoạch V2V và đối chứng optical flow trong ZIP. |
| S07 | `R38_META_OFFICIAL_IMAGE_SAM_V2V_ROUTER_20261117/` | Báo cáo R38, ma trận provider, chi phí tại thời điểm ghi nhận và ZIP kết quả 19 phép thử ngoại tuyến. |
| S08 | `R39_ZERO_COST_MUSE_SHELL_20261117/` | Báo cáo và hai ZIP R39/R39B gồm biên nhận edit, mẫu cắt, hash frame mù, đối chứng freeze, bộ kiểm EDL. |
| S08 | `R40_FREE_SAME_TURN_GENERATE_AND_QC_20261117/` | Báo cáo R40, nhật ký thời gian, MP4 gốc, hash frame mù, verdict độc lập và cửa sổ phản ứng 72 frame. |
| S09 | `R41_CLASS_SPECIFIC_FAIL_CLOSED_QC_20261117/` | Báo cáo R41, ba nguồn MP4, camera/freeze, thử YuNet và `R41C_WINDOW_QC_VERDICT.json`. |
| S09 | `R42_HELDOUT_ORIGINAL_VIDEO_QC_20261117/` | Báo cáo R42/R42B, ledger 32 MP4, kết quả camera/freeze theo ca và các ảnh chuỗi khung hình. |
| S10 | `R43_NATIVE_SEMANTIC_EYE_HEAD_PROP_QC_20261117/` | Báo cáo R43, ledger 8 MP4, nhãn mắt/tay khóa trước chạy, số đo chi tiết MediaPipe/YuNet và đối chiếu chuỗi ảnh. |
| S10 | `R44_PROP_ACTION_TEMPORAL_QC_20261118/` | Báo cáo R44, video và nhãn từng đợt, kết quả R44C về trùng pixel, R44E về vùng ảnh và R44F về khoảng camera mất dấu. |
| S11 | `R45_DEEP_WIRE_VM_DIT_AUDIT_AND_CLEANUP_20261118/` | Báo cáo R45, bản ghi chi tiết kích thước/PSNR, đường giao nhận và biên bản VM trước/sau. |
| S11 | `R46_PROSODY_LAW_WEBP_BACKEND_AND_43CLIP_BENCHMARK_20261118/` | Báo cáo R46, JSON về WebP, khôi phục sidecar, tập 35 clip và tập so landmark 43 clip. |
| S12 | `R47_SIGNED_SCHEMA_CAUSAL_AB_AND_55S_STREAM_20261118/` | Báo cáo R47, JSON schema runtime, manifest đầu vào, hai MP4 A/B, nhật ký gửi–nhận và Usage. |
| S13 | `R48_R49_UNIFIED_VIDEO_CONTROL_LAWS_20261118/` | Báo cáo R48–R49, 12 MP4, kết quả từng nhánh, chuỗi ảnh và `R49_WHISPER_WORD_COUNT_CALIBRATION.json`. |
| S14 | `R50_R51_TWOSHOT_VOICELOCK_OTS_AND_9X16_LAWS_20261118/` | Báo cáo R50–R51, 11 MP4, số đo môi/giọng, manifest ảnh, sidecar lỗi, kết quả dolly và khung dọc. |
| S15 | Cấp gốc của kho lưu trữ | Các bản `MUSE_MASTER_CAPABILITY_STATUS_*.md` đến `MUSE_MASTER_CAPABILITY_STATUS_R51_FREE_ONLY_20261118.md`, bảng verdict/CSV, README và `HANDOFF_MUSE_R39B_TO_NEW_CHAT_20261117.md`. Dùng để đối chiếu mốc chuyển trạng thái và truy về vòng cũ. |

**Kiểm tra độc lập khi tổng hợp.** Rà cả 19 thư mục điều tra và các gói lưu ở cấp gốc. Kiểm kê **612 tệp nguồn**, **25 ZIP cấp tệp rời và 3 ZIP lồng**. Kiểm CRC trong cả 28 ZIP và đối chiếu **928 mục SHA trong ZIP cùng 491 mục SHA ở tệp rời**, tất cả khớp manifest tương ứng. Kiểm cấu trúc **669 nội dung văn bản khác SHA** từ Markdown, JSON, JSONL, TXT, CSV và script. Đọc báo cáo, giao thức, ledger và bảng kết quả theo từng vòng để đối chiếu số mẫu, điều kiện thử và mức phê duyệt.

**Kiểm tra media.** 205 mục MP4 trong tệp rời và ZIP quy về **92 tệp khác SHA**, gồm video gốc, bản cắt và preview. ffprobe đọc được metadata và FFmpeg giải mã hết luồng hình cùng luồng tiếng hiện có của **92/92 tệp** mà không báo lỗi. Tái đo 7 điểm nối frame từ ZIP R30–R32, tính lại 2 hash frame R40 và đối chiếu T0, prompt, MP4 trong gói Alma. Đối chiếu thêm chuỗi ảnh R36/R43/R48/R51. Đợt rà lại theo từng MP4 nằm ở mục 7.


## 7. Rà lại diễn xuất và khẩu hình trên 92 MP4

Rà **460 ảnh theo thứ tự thời gian**, 5 ảnh mỗi tệp ở khoảng 2,5%, 25%, 50%, 75% và 95% thời lượng. Quét toàn bộ luồng tiếng hiện có bằng Faster-Whisper base.en và chạy đối chiếu bằng small.en trên 19 tệp. Đo chỉ số jawOpen + 0,5 × mouthFunnel trên 38 tệp bằng MediaPipe Face Landmarker ở 8 mẫu/giây. Các mô hình chạy cục bộ. Tiền tố SHA trong bảng giúp nhận đúng tệp trong kho, gồm cả video gốc và bản cắt thử.

**ĐÃ CHỨNG MINH trong phạm vi kiểm tra**

- Có **81 tệp có luồng tiếng** và **11 tệp không có luồng tiếng**. ASR cơ sở trả chữ ở **35/81** và không trả chữ ở **46/81**. Hai ca chỉ có một từ, 13 và 36, không lặp lại ở lượt chạy thứ hai. Số 35 bao gồm cả các ca còn nghi vấn.
- **Sai nhãn nhóm đối chứng R46.** Cả hai cấu hình ASR ra câu tiếng Anh có nghĩa ở R11 Listener Calm A/B và R13 Eyes Open B/No Eye Mention A (ca **51–54**). Đây cũng là bốn ca R46 báo mắt nhắm kéo dài trong nhóm sáu clip phản ứng được ghi là im. R12 Stable Start, R16 Listener B, R17 Listen Late (ca **62, 65, 67**) và hai nhánh cảnh rộng R28 (ca **48–49**) cũng có câu lặp lại trong hai lượt ASR. Chữ nhận dạng có thể đến từ giọng trong hoặc ngoài hình.
- **Hành động thấy trên ảnh.** Ca 08 cho thấy Malcolm ngẩng về cửa sổ, chuyển sang cỡ cận và mất vùng bàn về cuối. Ca 50/61 cho thấy tay rút khỏi khung khi cốc và bình vẫn còn. Ca 57 cho thấy phong bì dựng cao ở các mốc 7,50 và 9,50 giây. Ca 73 chuyển từ sảnh sang ngồi ở buồng lái.
- **R50 có dấu hiệu sai phân vai khẩu hình ở lượt đáp.** Với ca 82, cửa sổ thoại đầu 0,00–1,98 giây có 16 mẫu mỗi bên, độ lệch chuẩn chỉ số môi/hàm trái/phải khoảng **0,01547 / 0,00071**. Lượt sau detector chỉ bắt được người trái ở 5/32 mốc. Ca 83 trong cửa sổ thoại có **0,00021 / 0,01206** cho trái/phải, với 48 và 40 mẫu mặt. Ca 84 lượt đầu thiên về người phải. Trong cửa sổ lượt đáp 5,05–8,67 giây, cả hai bên đều có biến thiên (**0,00222 / 0,00245**, 29 mẫu mỗi bên), phù hợp với cảnh báo R50 về người nghe cũng cử động miệng. Cần kiểm ở mức từng frame nếu muốn định thời mức trùng hoặc lệch.
- **Lời ngoài nội dung chính.** Hai cấu hình ASR nhận ra câu loa trong ca 69, 71 và 79. Ca 76 có hai câu có nghĩa. Các ca 77–78 cùng cảnh nhưng ASR cơ sở không trả chữ. Ca 88 có ảnh môi hé và cả hai lượt ASR không trả chữ.

**CHƯA KIỂM CHỨNG**

- Nghe trực tiếp toàn bộ video, độ tự nhiên của giọng và diễn xuất liên tục, lệch hình–tiếng theo âm vị hoặc từng frame. Phiên này không nhận đầu vào âm thanh. Đợt rà đã xem chuỗi ảnh theo thời gian và phân tích luồng tiếng bằng ASR trên máy. Mốc ASR là ước lượng, còn MediaPipe chỉ đo chuyển động hình học. Chưa có căn cứ nâng tệp nào lên nhãn đạt khẩu hình toàn đoạn hoặc nghiệm thu diễn xuất.
- Yên tiếng trong tệp có track nhưng ASR không trả chữ, nhất là giọng nhỏ, tiếng thở và âm ngoài hình.

### Kết quả từng tệp

Mọi dòng ghi quan sát hình tại năm mốc mẫu. Cột tiếng ghi kết quả ASR hoặc tình trạng track. Cột khẩu hình áp dụng cho thoại nhìn thấy trên mặt người nói.

| # | MP4 và SHA-256 rút gọn | Diễn xuất hoặc hành động thấy trên ảnh | Tiếng đã đo | Khẩu hình |
| --- | --- | --- | --- | --- |
| 01 | `clip.mp4` · `64f77faa0809` | Alma nghiêng đầu, mỉm cười. Máy siết cỡ, khuôn miệng hiện rõ ở giữa cảnh. | 0.00–8.00s «Grant Foundation. This is Alma. Take your time.…» | Chưa kiểm chứng theo âm vị |
| 02 | `R39_MUSE_VERIFIED_1SECOND_EDIT.mp4` · `ae185746121c` | Trích 1 giây. Từ mắt hạ sang nhấc đầu nhẹ ở cuối. | Không có track tiếng | Không áp dụng |
| 03 | `R39_PC_LOCAL_FFMPEG_24_FRAMES_CONTROL.mp4` · `e0dde35fcbab` | Bản PC đối chứng 1 giây. Giữ cùng nhịp hạ mắt rồi nhấc đầu. | Không có track tiếng | Không áp dụng |
| 04 | `R39_REACTION_STABILIZED_NATIVE_NO_GEN_QC.mp4` · `4792beeed638` | Bản ổn định hậu kỳ vẫn từ trung cảnh sang cận nghiêng, cắt bớt mặt bàn. | Không có track tiếng | Không áp dụng |
| 05 | `R39_VERIFIED_NATIVE_WINDOWS_5P50S_QC_ONLY.mp4` · `5c81d568a804` | Bản ghép từ tay tiến về phong bì sang phản ứng ngẩng nhìn. Chỉ là đoạn dựng. | Không có track tiếng | Không áp dụng |
| 06 | `R39_3S_NATIVE_TEST_SOURCE.mp4` · `6720975ea5e9` | Đoạn 3 giây: mắt hạ, sau đó chuyển hướng lên phía cửa sổ. | Không có track tiếng | Không áp dụng |
| 07 | `R36_INSERT_BYTE_EXACT_NATIVE.mp4` · `4c124029725d` | Tay tiến đến phong bì, nắp giấy nhấc nhẹ. Ba ảnh cuối gần như cùng tư thế. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 08 | `R36_REACTION_BYTE_EXACT_NATIVE.mp4` · `0ae5be28bf99` | Ngẩng nhìn ngang, khuôn mặt lớn dần và mặt bàn mất khỏi khung. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 09 | `R30__R30_A_SNAPSHOT_ONLY.mp4` · `37487bae1807` | Cúi rồi há miệng ở mốc 2,50 giây, sau đó nhìn ra cửa. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 10 | `R30__R30_B_T0_ONLY.mp4` · `98f3c0bf22fe` | Cúi xuống bàn rồi quay gần nghiêng hẳn về phía cửa sổ. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 11 | `R30__R30_C_LASTFRAME_ONLY.mp4` · `882c25c2b548` | Bắt đầu cận nghiêng. Quay xa máy, làm lộ nửa sau đầu ở cuối. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 12 | `R30__R30_D_SNAPSHOT_PLUS_T0.mp4` · `d6eb5a1c26c9` | Chuyển từ nhìn bàn sang nhìn cửa sổ, cỡ hình giữ rộng hơn các nhánh A–C. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 13 | `R30__R30_R30_SEED.mp4` · `f2c2acf746f3` | Mắt hạ rồi ngẩng. Máy ép cận bên mặt rõ về cuối. | 4.72–5.26s «You». Ca một từ, lượt hai không lặp lại | Chưa kiểm chứng theo âm vị |
| 14 | `R30_4WAY_SNAPSHOT_CONDITIONING_QC_ONLY.mp4` · `b9cae1a7cb38` | Bản so sánh bốn nhánh. Thấy rõ khác biệt hướng nhìn và cỡ hình. | Không có track tiếng | Không áp dụng |
| 15 | `R31_NATIVE_ENDPOINT_T72.mp4` · `0d33ad6bed84` | Nối từ góc trung. Quay nhìn ngang và cỡ mặt tăng, phần bàn ra khỏi khung. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 16 | `R31_SEED_T3_CHAIN_6p08S_QC_ONLY.mp4` · `d880150ec3d4` | Bản thử cắt nối. Lần mở sau trở lại tư thế cúi, sau đó ngẩng. | Không có track tiếng | Không áp dụng |
| 17 | `R32__R32_ALMA_STAGE1.mp4` · `e19c72bc3bf5` | Alma đổi ánh mắt và nét cười, cỡ hình gần dần. | 0.43–7.91s «Of course. Start with the first thing you…» | Chưa kiểm chứng theo âm vị |
| 18 | `R32__R32_ALMA_STAGE2.mp4` · `517a919d50d6` | Động tác tay có bút xuất hiện, cỡ hình bó chặt khi nhân vật ngừng nói. | 0.05–3.49s «I'll write it down and we'll work through…» | Chưa kiểm chứng theo âm vị |
| 19 | `R32__R32_MALCOLM_STAGE1.mp4` · `7ace37cc2d08` | Từ nhìn ra xa đến cúi về phong bì. Mốc sau chú trọng tay, đầu bị cắt một phần. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 20 | `R32__R32_MALCOLM_STAGE2.mp4` · `6b656b281eff` | Bắt đầu gần phong bì, mặt bị cắt ở 2,50 giây rồi khung mở và nhân vật ngẩng. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 21 | `R32_ALMA_NATIVE_TWO_SHOT_8.54S_QC_ONLY.mp4` · `a61cfc5c1495` | Bản ghép Alma. Đổi góc đầu nhẹ qua hai lượt, không thấy gián đoạn lớn ở các ảnh mẫu. | 0.43–3.83s «Of course. Start with the first thing you…»<br>4.95–8.03s «I'll write it down and we'll work through…» | Chưa kiểm chứng theo âm vị |
| 22 | `R32_MALCOLM_NATIVE_TWO_SHOT_5.33S_QC_ONLY.mp4` · `c4491c3b0e86` | Bản ghép Malcolm. Đổi hướng nhìn từ cửa sổ xuống phong bì, mốc cuối cắt phần trán. | Không có track tiếng | Không áp dụng |
| 23 | `R33__A_NOT_PRESTAGED.mp4` · `f21576399cba` | Tay và giấy hiện đầu cảnh, sau 5 giây khung cận không còn vùng giấy. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 24 | `R33__B_PRESTAGED.mp4` · `20c36f4f12ad` | Tay đặt gần phong bì ở đầu, mặt và đạo cụ không cùng giữ được trong khung sau đó. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 25 | `R33_PROP_A_VS_B_NATIVE_10S_REVIEW.mp4` · `a12850546b44` | Bản so sánh hai take R33. Cả hai chuyển từ bố cục có bàn sang cận mặt. | Không có track tiếng | Không áp dụng |
| 26 | `R36_INSERT_REACTION_5p50S_NATIVE_QC_NOT_RELEASE.mp4` · `2029b254a76c` | Bản nối insert và reaction. Ngón tay tiến tới rồi cắt sang ngẩng nhìn. | Không có track tiếng | Không áp dụng |
| 27 | `R40_EDITORIAL_CANDIDATE_F084_F156_72FR_3S.mp4` · `807baddab98e` | Đoạn phản ứng 3 giây. Malcolm duy trì hướng nhìn trái với thay đổi nhỏ. | Không có track tiếng | Không áp dụng |
| 28 | `R40_MUSE_ORIGINAL_FROM_BLOB_0.mp4` · `e846d1fd6463` | Cúi, liếc trái ở giữa rồi hạ mắt lại. Bố cục bàn và hậu cảnh tương đối ổn. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 29 | `R24__V01_WIDE.mp4` · `f94041632619` | Toàn cảnh nhân vật đứng. Cúi nhìn giấy, ảnh sau giữ tư thế lâu. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 30 | `R24__V02_MEDIUM.mp4` · `fd9a156e9c4c` | Cúi và đưa tay tới giấy. Ba ảnh cuối gần như cùng bố cục. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 31 | `R24__V03_ENVELOPE.mp4` · `7a6758c20379` | Tay và tay áo đi vào từ trái, nắp phong bì giữ nguyên từ mốc 2,50 giây. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 32 | `R24__V04_TOUCH.mp4` · `27150a446041` | Ngón tay tới giấy rồi đặt cả bàn tay xuống. Không thấy giấy được nhấc. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 33 | `R24__V05_HOLD.mp4` · `b9c95afd3523` | Tay giữ phong bì trước người. Đầu và vai dần đi vào khung. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 34 | `R24__V06_FACE.mp4` · `e442dd452594` | Ngẩng và giữ hướng lên. Các ảnh sau rất ít đổi tư thế. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 35 | `R26__R26_S01_WIDE_A_POSITIVE_SHORT.mp4` · `6beea0834f7b` | Cúi đầu, camera siết dần từ toàn cảnh và mất phần mặt bàn. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 36 | `R26__R26_S01_WIDE_B_DETAILED_CONTROL.mp4` · `83e5267d3b54` | Cúi đầu tương tự nhánh A, nhưng mặt bàn và hai đạo cụ còn thấy ở cuối. | 7.41–7.97s «Okay.». Ca một từ, lượt hai không lặp lại | Chưa kiểm chứng theo âm vị |
| 37 | `R26__R26_S02_MEDIUM_A_POSITIVE_SHORT.mp4` · `c34075543a11` | Bắt đầu trung cảnh, biến thành cận mặt cúi. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 38 | `R26__R26_S02_MEDIUM_B_DETAILED_CONTROL.mp4` · `14d0f12755e8` | Cúi dần, khuôn hình giữ được bàn và cốc nhiều hơn nhánh A. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 39 | `R26__R26_S03_FACE_A_POSITIVE_SHORT.mp4` · `e4bc4380df3d` | Ngẩng mặt, sau đó khung siết sát và mắt có mốc khép. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 40 | `R26__R26_S03_FACE_B_DETAILED_CONTROL.mp4` · `adc31c7d064c` | Liếc trái rồi lại hướng cửa sổ. Cỡ hình ít đổi hơn nhánh A. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 41 | `R27__R27_FACE_WINDOW_TAKE1.mp4` · `88789de57f31` | Ngửa đầu và nhắm mắt ở các mốc sau, từ khoảng 5 giây trở thành cận nghiêng. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 42 | `R27__R27_FACE_WINDOW_TAKE2.mp4` · `b094332dcf3c` | Từ nhìn ngang sang ngửa đầu. Cuối cảnh thấy mắt khép ở cận sát. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 43 | `R27__R27_MEDIUM_GRIEF_TAKE1.mp4` · `eb38e30fde0c` | Nheo mày rồi cúi sâu. Cận cuối cắt phần vai. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 44 | `R27__R27_MEDIUM_GRIEF_TAKE2.mp4` · `a0e21be76615` | Cúi sớm. Từ trung cảnh tới cận mặt, biểu cảm tập trung vào lông mày và môi. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 45 | `R27__R27_WIDE_DOLLY_TAKE1.mp4` · `14d81931aca9` | Tiến máy từ toàn cảnh đứng sang trung/cận khi đầu cúi. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 46 | `R28__R28_FACE_A_SINGLE_T0.mp4` · `b33bf0abd922` | Ngẩng nhanh về cửa sổ, cỡ mặt lớn dần, không còn thấy bàn. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 47 | `R28__R28_FACE_B_T0_AND_T3.mp4` · `9900b0fb25e3` | Ngẩng về cửa sổ. Mắt khép ở mẫu 9,50 giây trong bố cục cận. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 48 | `R28__R28_WIDE_A_SINGLE_T0.mp4` · `509b5bead475` | Toàn cảnh chuyển dần sang trung/cận, nhân vật cúi nhìn. | 5.52–8.00s «I don't know what to do now.» | Chưa kiểm chứng theo âm vị |
| 49 | `R28__R28_WIDE_B_T0_AND_T3.mp4` · `1c3fcee25a2d` | Ban đầu thấy bàn. Về cuối trung/cận như nhánh một ảnh. | 6.35–7.93s «I didn't expect this today.» | Chưa kiểm chứng theo âm vị |
| 50 | `R11__R11_HAND_WITHDRAW_C_NATIVE_ORIGINAL.mp4` · `647d8f012012` | Tay rút sang phải, không thấy tay ở hai ảnh cuối, cốc và bình ở lại. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 51 | `R11__R11_LISTENER_CALM_A_NATIVE_ORIGINAL.mp4` · `6aa8ed3ee638` | Hướng cửa sổ, có mốc mắt khép và miệng hé. | 1.97–3.99s «I just don't know how we're going to…»<br>7.31–8.77s «It's been a lot to take in, hasn't…» | Chưa kiểm chứng theo âm vị |
| 52 | `R11__R11_LISTENER_CALM_B_NATIVE_ORIGINAL.mp4` · `872fa2b58691` | Nheo mắt giữa cảnh, miệng mở tại một số mốc, rồi dịu lại. | 4.11–6.33s «I just don't know if we're making the…» | Chưa kiểm chứng theo âm vị |
| 53 | `R13__R13_LISTEN_EYES_OPEN_B_NATIVE_ORIGINAL.mp4` · `33020841a1bc` | Nhìn ngang, nheo ở 7,50 giây. Khung gần dần. | 6.94–8.72s «Yeah, I understand what you're saying now.» | Chưa kiểm chứng theo âm vị |
| 54 | `R13__R13_LISTEN_NO_EYE_MENTION_A_NATIVE_ORIGINAL.mp4` · `473091a041e8` | Gaze hạ ở 7,50 giây rồi ngẩng nhẹ, miệng hé ở ảnh cuối. | 5.42–7.04s «I know it's not easy, Malcolm.» | Chưa kiểm chứng theo âm vị |
| 55 | `R23__R23_A_SINGLE_BEAT_NATIVE_ORIGINAL.mp4` · `68cd5db9d151` | Xoay nhìn ra vườn rồi quay lại góc nghiêng gần như ban đầu. Cốc ở tay. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 56 | `R23__R23_B_THREE_SHORT_BEATS_NATIVE_ORIGINAL.mp4` · `c3a220223012` | Nhìn ra vườn, cúi về cốc giữa cảnh rồi ngẩng, thấy rõ ba trạng thái. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 57 | `R25__R25_A_BASELINE_T03_NATIVE_ORIGINAL.mp4` · `eb435a8f72d9` | Ngón tay kẹp mép giấy. Ở mốc 7,50 và 9,50 giây phong bì dựng cao. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 58 | `R10__R10_COFFEE_REPEAT_A_ORIGINAL_NATIVE.mp4` · `05149d26fea3` | Dòng cà phê đổ vào cốc rồi ngắt. Bình hạ xuống, tay còn trong khung. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 59 | `R10__R10_COFFEE_REPEAT_B_ORIGINAL_NATIVE.mp4` · `a5a12d143c97` | Dòng ngắt, bình đặt xuống, tay ra khỏi hai ảnh cuối. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 60 | `R12__R12_COFFEE_NEAR_DONE_ORIGINAL_NATIVE.mp4` · `33f6a6e5e55e` | Dòng ngắt sớm hơn cặp R10. Đặt bình xuống và tay còn cạnh cốc. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 61 | `R12__R12_HAND_NEAR_EXIT_ORIGINAL_NATIVE.mp4` · `f2acc68ae589` | Tay rút khỏi khung, hai đạo cụ ở lại. Ảnh cuối gần như giữ nguyên bố cục. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 62 | `R12__R12_LISTENER_STABLE_START_ORIGINAL_NATIVE.mp4` · `a79edad5c885` | Nhìn ngang, có mốc môi mở giữa cảnh và mím môi cuối. | 1.68–5.98s «I remember when we first moved into this…»<br>7.26–8.94s «Things have changed a lot since then.» | Chưa kiểm chứng theo âm vị |
| 63 | `R15__R15_R15_S1_COFFEE_ORIGINAL_NATIVE.mp4` · `6d9a8443c2d1` | Dòng ngắt, bình hạ xuống, tay biến mất khỏi ảnh cuối. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 64 | `R16__R16_COFFEE_A_ORIGINAL_NATIVE.mp4` · `00e293284d92` | Dòng ngắt rồi hạ bình. Mốc cuối đổi bố cục nền rõ so với đầu. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 65 | `R16__R16_LISTENER_B_ORIGINAL_NATIVE.mp4` · `56b9a5dcd6a8` | Có mốc mắt khép, miệng hé, máy siết gần dần. | 4.85–8.77s «I remember when we first moved into this…» | Chưa kiểm chứng theo âm vị |
| 66 | `R17__R17_R15_P2_COFFEE_LATE_ORIGINAL_NATIVE.mp4` · `9c425c7d3294` | Dòng ngắt, bình hạ xuống rồi tay rút, cốc và bình cùng ở lại. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 67 | `R17__R17_R15_P2_LISTEN_LATE_ORIGINAL_NATIVE.mp4` · `2948541b8ad8` | Hướng người giữ gần giống, miệng hé ở các mốc sau. | 4.34–7.86s «I know it's been difficult, but we have…» | Chưa kiểm chứng theo âm vị |
| 68 | `ARM_A_CONTROL_2048x1152.mp4` · `c6ab270a7b4f` | Nâng điện thoại. Ánh sáng bùng từ sau rồi hình siết cận lúc cuối. | 0.02–0.96s «I will, Mum.»<br>2.80–4.34s «142 passengers today.»<br>5.52–7.08s «I'll make you proud.» | Chưa kiểm chứng theo âm vị |
| 69 | `ARM_B_TREATMENT_1280x720.mp4` · `e039e4a3cad9` | Nâng điện thoại. Khung và vùng mặt giữ ổn hơn nhánh A tại các mốc mẫu. | 0.82–4.52s «I will mum, 142 passengers today.»<br>5.54–6.30s «I'll make you proud.»<br>7.84–9.26s «Boarding now at Gate 12.» | Chưa kiểm chứng theo âm vị |
| 70 | `r48-1-lastframe.mp4` · `c7d73d720363` | Đã giữ điện thoại ở đầu. Nhìn nghiêng rồi hạ mắt ở cuối. | 0.00–6.26s «The crew just opened the boarding door mum.…» | Chưa kiểm chứng theo âm vị |
| 71 | `r48-2-snap-text.mp4` · `126e9b0ba211` | Bắt đầu khác góc và chưa áp điện thoại, sau đó đưa lên và giữ. | 0.59–5.69s «The crew just opened the boarding-door mum. I…»<br>7.03–8.75s «Final boarding call at gate 20.» | Chưa kiểm chứng theo âm vị |
| 72 | `r48-3-snap-hybrid.mp4` · `deb075a9e838` | Khớp bố cục mở gần nhánh 70. Nhìn, mỉm cười và vẫn giữ điện thoại ở cuối. | 0.37–2.37s «The crew just opened the boarding door, mum.»<br>5.38–7.40s «I will call you right after we land…» | Chưa kiểm chứng theo âm vị |
| 73 | `r48-4-dual-img.mp4` · `929448df6c92` | Từ gọi điện ở sảnh sang đi rồi ngồi trong buồng lái. Khuôn mặt tối ở giữa. | 0.34–1.64s «All right, see you later» | Chưa kiểm chứng theo âm vị |
| 74 | `r48-5-cockpit-silent.mp4` · `e0b156b28774` | Chạm bảng điều khiển trên cao rồi hạ tay, cuối giữ tay gần bảng thấp. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 75 | `r48-6-cockpit-foley.mp4` · `8760f98bbdb5` | Thao tác trên cao rồi thay đổi vị trí tay. Máy siết cỡ hơn ca 74. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 76 | `r49-1-minimal.mp4` · `67014b7df874` | Hai người cúi nhìn sổ, camera siết cận và mất phần dưới khi tới cuối. | 1.46–4.52s «This is my updated pilot certification credential.»<br>7.43–8.91s «Okay, let me have a look at that.» | Chưa kiểm chứng theo âm vị |
| 77 | `r49-2-affirmative.mp4` · `9624ab206125` | Nhấc sổ mở để cùng nhìn, cả hai còn trong khung, cuối hạ mắt. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 78 | `r49-3-negative-num.mp4` · `ff332e2babe5` | Giơ thẻ, hai người giữ cỡ trung và nhìn nhau qua các mốc cuối. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 79 | `r49-4-speech-08w.mp4` · `99a21898de33` | Đưa điện thoại lên, có nụ cười mạnh và hạ mắt cuối. | 1.49–8.65s «Flight now boarding at gate B-14 Thank you…» | Chưa kiểm chứng theo âm vị |
| 80 | `r49-5-speech-24w.mp4` · `5166f6721915` | Đưa điện thoại lên, môi thay đổi ở nhiều mốc, giữ nụ cười cuối. | 0.00–4.40s «I just finished reviewing the morning weather brief…»<br>5.68–9.42s «142 passengers are counting on us today and…» | Chưa kiểm chứng theo âm vị |
| 81 | `r49-6-speech-42w.mp4` · `714f0f89da03` | Đưa điện thoại lên, môi hoạt động dày trong ảnh mẫu, khép mắt gần cuối. | 0.00–3.46s «I just finished walking around the aircraft and…»<br>3.46–5.50s «our first officer at Gate B14 Mom.»<br>5.92–9.70s «Every system on this Boeing 737 is green,…» | Chưa kiểm chứng theo âm vị |
| 82 | `r50-1-twoshot-left.mp4` · `b65038d2fff9` | Người trái có nhiều mẫu môi đổi trạng thái. Người phải nhìn đối diện. | 0.00–1.98s «Look at my dispatch release, Miss Davis.»<br>4.06–8.04s «Flight 1128 to Atlanta is officially under my…» | Có tín hiệu người trái ở lượt đầu, lượt sau thiếu mẫu mặt |
| 83 | `r50-2-twoshot-right.mp4` · `e76af02b255f` | Người phải có nhiều mẫu mở môi. Cuối clip mặt cô ở sát mép phải. | 0.08–6.06s «Captain Henderson is listed on my cruise sheet…» | Có tín hiệu người phải trong cửa sổ thoại |
| 84 | `r50-3-twoshot-ab-turn.mp4` · `d830f8a9ad32` | Nửa đầu người phải có mẫu mở miệng, nửa sau người trái và đôi lúc cả người phải hé môi. | 0.00–2.44s «Who authorised this crew change at 6 in…»<br>5.05–8.67s «Operations Control updated the Master Flight release 20…» | Báo động phân vai ở lượt đáp |
| 85 | `r50-4-voice-cut-base.mp4` · `5383204da4d8` | Nói trong buồng lái. Mẫu cuối quay nhẹ, viền khung dần siết. | 0.00–5.68s «Flight deck pre-flight check is complete, first officer.…»<br>5.68–8.66s «Atlanta dispatch release and departure weather looks clear.» | Chưa kiểm chứng theo âm vị |
| 86 | `r50-5-voice-cut-snap.mp4` · `ba16fc2cf5f3` | Tương tự ca 85, ánh đỏ nền và cỡ mặt tăng rõ hơn cuối đoạn. | 0.85–6.13s «Flight deck. Pre-flight check is complete. First officer.…»<br>6.13–9.21s «Atlanta dispatch release and departure weather looks clear.» | Chưa kiểm chứng theo âm vị |
| 87 | `r50-6-voice-cut-dna.mp4` · `9ba8ff3cce0e` | Đưa mắt và đổi môi khi ngồi, giữ khung rộng hơn hai ca 85–86. | 0.24–3.04s «Flight deck pre-flight check is complete, first officer.»<br>4.18–8.50s «Fuel load matches our Atlanta dispatch release and…» | Chưa kiểm chứng theo âm vị |
| 88 | `r51-2-ots-cure.mp4` · `28e8ba5de45e` | Cận nghiêng người tóc vàng. Có nhiều mẫu môi hé giữa cảnh. | ASR không ra chữ | Chưa xác nhận có lời để chấm |
| 89 | `r51-3-dolly-unbounded.mp4` · `b8646bb011cf` | Từ toàn cảnh đi tới cận nghiêng. Đạo cụ cầm tay ra khỏi vùng dễ nhìn. | 1.94–7.86s «Boarding is right on schedule this morning. Everything…» | Chưa kiểm chứng theo âm vị |
| 90 | `r51-4-dolly-bounded.mp4` · `c24dc8bedca5` | Đi tới máy và dừng ở cỡ trung, vẫn tăng cỡ so với đầu. | 1.07–3.41s «Boarding is right on schedule this morning.»<br>5.33–8.81s «Everything on the walk-around looked sharp and ready…» | Chưa kiểm chứng theo âm vị |
| 91 | `r51-5-vert-1152x2048.mp4` · `c75d87ca1c73` | Khung dọc. Bên mặt sáng mạnh, hạ mắt và mỉm cười ở cuối. | 1.33–8.07s «Good morning from Gate B14 Mom. Our Boeing…» | Chưa kiểm chứng theo âm vị |
| 92 | `r51-6-vert-720x1280.mp4` · `84b9a8dc1a6c` | Khung dọc giữ ánh sáng dịu hơn. Cuối cúi nhìn ngoài khung. | 1.65–8.53s «Good morning from gate B14 mom our Boeing…» | Chưa kiểm chứng theo âm vị |
