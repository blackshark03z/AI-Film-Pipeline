# Bàn giao hệ thống sản xuất local — 2026-11-04

## Kết quả và phạm vi

Theo chỉ đạo mới nhất của Owner, đầu ra lượt này là **hệ thống sản xuất có thể vận hành lại**, không phải hoàn thành sáng tạo hoặc ship phim mẫu. Bốn lệnh `prepare`, `resume`, `status`, `finish` dùng runtime SQLite, ShotSpec, SelectedTake, QC, editorial và DeliveryManifest có sẵn. Không thêm dependency, orchestrator, dashboard hay hệ thống policy.

Checkout triển khai: `C:\Users\ADMIN\.codex\worktrees\film-e2e-ship\AI-Film-Pipeline`, branch `codex/film-e2e-ship`, tiếp nối `d1b742254ee615f131815c8b0ce3f6f37d0f695b`. Revision chính xác của gói nằm trong `BUILD.json`. Canonical project vẫn ở `D:\AI FILM MAKER\AI-Film-Pipeline`; WIP tại đó được giữ nguyên. Trạng thái mới nhất ở hai operating file của canonical root; lịch sử cũ trong source archive không thay đổi mục tiêu hiện tại.

Ba gap đã khép:

- `status --project` tự đọc Flow ID đã khóa và runtime local, không khởi tạo lại DB hoặc tự duyệt QC. Có thể chỉ định `--db` nếu dùng DB khác.
- Sau khi người vận hành chỉnh mốc shot, lần `resume` đầu cập nhật lời nguồn từ SRT, kể cả cue chồng thời gian, trước khi khóa plan. Không sửa prompt hoặc plan lịch sử đã khóa. Mốc bool/NaN/Infinity bị từ chối.
- `finish` tạo thư mục `delivery/` với master, SRT, provenance và manifest. `status --package` kiểm tra được sau khi chuyển thư mục, không cần runtime hoặc browser; file thiếu/đổi hash trả FAIL và mã thoát khác 0. Không ghi đè master hoặc gói sai lệch.

## Chạy lại

Xem [E2E_LOCAL_RUN.md](E2E_LOCAL_RUN.md) để vận hành đầy đủ. Dùng Python 3.11+, dependency hiện có trong `pyproject.toml`, FFmpeg/ffprobe. Dùng đường dẫn Windows ngắn, ví dụ `D:\film-work\film-01`.

Gói local gồm `code/`, `sample/` và `proof/`. `sample/audio.mp3` là âm thanh sine nhân tạo, SRT và `sample/delivery/` là fixture kỹ thuật, không phải phim hoặc bản duyệt của Owner. Để bắt đầu dự án mới từ dữ liệu mẫu, chạy trong `code/`:

```powershell
python tools/film_e2e.py prepare --audio ..\sample\audio.mp3 --srt ..\sample\captions.srt --start 18 --end 48 --out D:\film-work\demo-01
python tools/film_e2e.py status --project D:\film-work\demo-01
python tools/film_e2e.py status --package ..\sample\delivery
```

Người vận hành chỉnh `shots.json`, tạo/tải ảnh từ đúng profile, nộp receipt và duyệt từng clip. Không cần sửa Python giữa các lần chạy. Trước Generate phải khóa ngoại hình, phục trang, vị trí, đạo cụ và mô tả rõ hành động. Phần mềm không tự hiểu nội dung, tự tạo ảnh ChatGPT hay tự chứng nhận continuity. `resume` chỉ gọi Flow khi có `--flow-profile` và từng `--shot` cụ thể. Lượt hoàn thiện hệ thống này **không cho phép Generate thêm**.

Gói delivery dùng để phát và đối chiếu nguồn; production DB còn đường dẫn tuyệt đối nên tiếp tục ở thư mục dự án ban đầu. Không sửa immutable receipt để đổi đường dẫn. Tạo dự án mới bằng `prepare` khi cần vận hành ở nơi khác. Gói không chứa browser profile, cookie hoặc thông tin đăng nhập.

## Bằng chứng vừa đủ

Các receipt ở `proof/` trong gói, bản gốc tại `projects/e2e_system_20261104/`:

- `candidate_tests.xml`: 100 đạt, 1 lỗi do đường dẫn fixture quá dài trên Windows. Không xóa hoặc đổi nhãn kết quả này.
- `journey_short_path.xml`: đi hết export nhưng đổi tên thư mục bị SQLite handle chờ thu hồi giữ trên Windows. Test đã thu hồi handle trước bước đổi tên; không đổi acceptance hoặc logic production để né lỗi.
- `final_changed_tests.xml`: 8/8 đạt, 19,14 giây. Gồm toàn bộ kiểm tra thay đổi và một ca 8-shot offline đi qua prepare, khóa plan/ảnh, runtime, chờ QC, duyệt fixture rõ danh tính, SelectedTake, finish thật, decode toàn bộ và đọc gói bằng CLI sau khi thư mục gốc đã đổi tên. Các module Flow/QC/editorial/delivery còn lại đã đạt trong candidate run và không thay đổi sau đó. Không cộng các lượt chạy trùng thành số test lớn hơn.
- Ca âm tính: nguồn đổi hash, cue chồng, thiếu shot, gate chưa duyệt, sửa plan đã khóa, mốc sai, master cũ không receipt, FFmpeg lỗi, gói đổi hash và mã thoát CLI. Resume cùng version giữ cùng job, dispatch_count=1. Các kiểm tra ambiguous submission/repair có trong suite runtime đã đạt.
- Readback runtime Flow thật bằng `status` mới: 2 shot được chọn, 8 clip chờ review; hash DB không thay đổi. Nó báo các `source_text` cũ lệch mốc ở shot02–09 và giữ nguyên plan đã khóa. Đây là dữ liệu lịch sử, không tự sửa hoặc tự ACCEPT.

Provider thật đã được kiểm chứng ở lần trước: 11/14 lượt Flow trong project `de921fec-458c-45ee-865a-3d3d0ef9e688`, gồm initial/resume và repair thay đổi có predecessor bị từ chối rõ ràng. Receipt/runtime ở `projects/e2e_badge_20261104`; M1 được Owner chấp nhận hai shot để dựng tiếp. SHOT08 v2 và toàn phim chưa được chấp nhận. Lượt này không dùng thêm quota, không mua credits, không đổi account/provider.

## Quyết định tiếp quản

**Technical pass:** các hành vi phần mềm trong phạm vi này được chứng minh offline, có readback runtime thật và gói local mở lại được. **Product journey:** luồng vận hành được chứng minh bằng fixture có nhãn; không tuyên bố chất lượng hình ảnh/motion của phim đã đạt. **Owner acceptance:** không suy diễn từ test, decode hay việc đóng gói.

Bộ pytest toàn repo trước đó vẫn **NOT PASS**: 1.223 đạt, 133 lỗi assertion và 62 errors, chủ yếu thiếu dữ liệu lịch sử ignored; giữ receipt cũ, không chạy lại hoặc sửa backlog ngoài luồng này. X04 và toàn bộ 168 danh mục chưa được đóng. Giới hạn Windows long-path và DB không di chuyển là giới hạn đã biết.

Đầu việc hiện tại dừng ở increment hệ thống local này. Tech Lead có thể vận hành dự án tiếp theo bằng bốn lệnh và receipt có sẵn; chỉ mở phạm vi mới khi có gap thực tế trên luồng sử dụng. Không biến lỗi sáng tạo của phim mẫu thành chuỗi Generate hoặc hạng mục kiến trúc mới. Không push, merge hoặc phát hành công khai trong lượt này.
