# Báo cáo kiểm thử — TBM Cassette Player

Ngày: **27/11/2026**. Môi trường: Windows 11 x64, Python 3.14.7,
PySide6/Qt 6.12.0, Qt FFmpeg 9.0.1, PyInstaller 6.22.3.

## Phạm vi đã xác minh

- 33 bài unittest: 20 bài cho ứng dụng Qt mới và 13 bài hồi quy cho `player.py`.
  Đặt `TBM_TEST_FILE` để bật bài tích hợp thực; nếu bỏ biến này có 1 bài skip.
- Giữ nguyên hai tệp `tbm_decoder.py` và `audio_utils.py`. Adapter tái sử dụng
  OGG Vorbis cùng kiểm tra CRC/codebook của decoder hiện có.
- Tệp thật `k0005.tbm`: giải mã OGG 221,867 giây, phát qua QBuffer/QByteArray
  mà không dùng fallback tệp tạm; nhận PCM thật và spectrum khác 0.
- Pause/Resume, Seek, xuất OGG khi đang phát, LRU cache, đổi phiên bản tệp cùng
  kích thước/timestamp, lỗi TBM không hợp lệ và hủy decode khi Stop/chuyển bài.
- Quét thư viện không giải mã; search, favorites, SQLite và xóa bản ghi không
  xóa tệp gốc. Thư viện test 1.000 bài dùng ListView và giữ vị trí cuộn khi lật.
- Hồi quy đường dẫn Windows: tái hiện lỗi Favorite bằng thư mục tạm dạng tên
  ngắn 8.3 rồi xác nhận lookup dùng cùng tệp đã resolve. Kiểm tra Favorite,
  highlight bài hiện tại và xóa bản ghi bằng đường dẫn có `..` hoặc tên ngắn;
  dữ liệu SQLite đồng bộ và tệp gốc được giữ nguyên.
- Hai reel xoay độc lập; Pause giữ nguyên góc, Resume tiếp tục xoay. Lật mặt
  không tạo lại transport, không thay đổi cửa sổ 640 × 440 và không đổi trạng
  thái phát. Không phát hiện lỗi binding/ReferenceError/TypeError trong QML.
- Kiểm tra Space/Tab trong cửa sổ; Space trong ô nhập không điều khiển player,
  Tab trong ô nhập không lật mặt; context menu mở được; Dark theme render được.
- Shuffle: bài đầu chọn ngẫu nhiên, không lặp trong cùng lượt, Repeat All mở
  lượt mới không phát ngay lại bài vừa kết thúc; tôn trọng bộ lọc và Play next.
  Kiểm tra Next khi bộ lọc chỉ còn một bài, lưu trạng thái ngay và đồng bộ nút
  bật màu cam ở cả Player lẫn mini playback bar của Library.
- Tự bỏ qua lỗi giải mã/phát: kiểm tra nhiều TBM hỏng liên tiếp, toàn bộ danh
  sách lỗi với Repeat Off/Track/All và Shuffle; mỗi tệp được thử tối đa một lần
  trong chuỗi phục hồi. Lỗi cuối danh sách có thể chuyển về bài còn lại ở đầu.
  Stop/chọn bài thủ công hủy chuyển bài chờ; cho phép thử lại thủ công. Lỗi xuất
  không đổi bài đang phát. Qt thử RAM rồi tệp tạm trước khi báo lỗi phát; bỏ qua
  tín hiệu lỗi của nguồn đã giải phóng. Bài tích hợp thực bắt đầu bằng TBM hỏng
  và xác nhận tự chuyển sang TBM phát được, có PCM thật.
- EXE windowed: worker trả OGG hợp lệ qua pipe; QML smoke test exit 0;
  `--smoke-test --play <TBM>` nhận PCM thực và exit 0 sau 10 giây.
- Kiểm tra ảnh chụp Player và Library với nhạc/thư viện thật, cùng ảnh Dark
  trong test UI. Ảnh tham chiếu được diễn giải thành đồ họa vector tối giản,
  không dùng texture, GIF hoặc video.

## Đo hiệu năng

Lệnh tái lập:

```powershell
./.venv/Scripts/python.exe scripts/benchmark_cassette.py "C:/My Music"
```

Thư viện đo thực tế có **5.585 tệp TBM/ABM**. CPU dưới đây tính theo **một lõi**
(`process_time / wall_time × 100`), không phải phần trăm toàn hệ thống.
Mỗi mẫu CPU dài 3 giây. RAM là working set của tiến trình GUI; không cộng
decoder worker tồn tại ngắn hạn và bộ nhớ driver/GPU bên ngoài tiến trình.

| Trạng thái | RAM working set | CPU / một lõi |
| --- | ---: | ---: |
| Chưa quét, đứng yên | 116,14 MiB | 1,04% |
| Đã quét, phát ở mặt Player | 190,80 MiB | 15,62% |
| Đang phát, mặt Library | 192,76 MiB | 7,29% |
| Sau 30 yêu cầu chuyển bài nhanh | 196,69 MiB | 5,21% |
| Sau thêm 30 lần lật mặt hoàn chỉnh | 202,59 MiB | 4,16% |

- Tải QML + chờ ổn định 150 ms: **0,329 giây**. Đây không phải cold startup
  toàn bộ tiến trình hoặc phép đo trên máy Windows sạch.
- Quét thư mục và đưa 5.585 bản ghi vào model: **5,363 giây** trong harness.
- Cache sau thử chuyển bài: **3.278.582 byte**, giới hạn cho phép 96 MiB.
- Worker đã hủy còn tồn tại sau thử: **0**.
- Working set tăng **5,90 MiB** qua 30 lần lật. Thử ngắn này chưa đủ để kết luận
  không có memory leak lâu dài; Qt/GPU có thể giữ cache đồ họa.
- Gói onedir khoảng **164,7 MiB**, không có WebEngine. Bỏ các plugin QML không
  dùng giảm từ bản thu thập mặc định khoảng 442 MiB.

Dữ liệu đo máy được lưu ở [benchmark.json](benchmark.json). Số đo thay đổi theo
phần cứng, thư viện, driver, thiết bị âm thanh và phiên bản Qt.

## Giới hạn còn lại

- Chưa kiểm chứng toàn bộ 5.585 bài qua decoder mới; chỉ quét tên, metadata
  sidecar và phát một số tệp đại diện. Giới hạn biến thể/codebook cũ vẫn áp dụng.
- Chưa chạy soak test nhiều giờ hoặc kiểm chứng mọi thiết bị âm thanh/DPI.
- Có AudioEngine interface nhưng chưa cung cấp backend libmpv. Nếu Qt không
  phát được OGG cả từ RAM và tệp tạm, UI báo lỗi để người dùng xử lý.
- Phím multimedia là shortcut Qt của cửa sổ, chưa là hotkey toàn hệ thống.
  System tray có menu điều khiển riêng. Các thao tác tray, kéo cửa sổ, pin và
  Windows Explorer cần kiểm tra thủ công trên máy đích.
- Quét chạy nền, metadata giải mã lazy; không có watcher tự cập nhật thư mục.
- Xuất âm thanh trong bản Qt là OGG Vorbis nguyên bản, không chuyển MP3/WAV.
  Xuất và phát mới dùng chung một slot decoder; chuyển bài có thể hủy tác vụ
  xuất đang chạy. Cần đợi thông báo xuất xong trước khi dùng tệp xuất.
- Các kiểm thử tự động xác nhận dữ liệu PCM/position/state, chưa thay thế việc
  nghe và đánh giá chất lượng âm thanh bằng tai.
- Gói EXE đã được chạy trên máy phát triển, chưa kiểm thử trên Windows VM sạch.

## Cách chạy lại

```powershell
$env:TBM_TEST_FILE = "C:/My Music/song.tbm"
./.venv/Scripts/python.exe -m unittest discover -s tests -v
./build-cassette.ps1
./dist/TBMCassettePlayer/TBMCassettePlayer.exe --smoke-test
./dist/TBMCassettePlayer/TBMCassettePlayer.exe --smoke-test --play "$env:TBM_TEST_FILE"
```

`work/test-results-final.txt`, `work/packaged-validation.json` và các log build
là bằng chứng chạy cục bộ, không đưa vào Git. Các kiểm thử lỗi cố ý có thể ghi
ERROR cho tệp TBM không hợp lệ. Log probe codec AV1 của FFmpeg trên máy thử
không làm hỏng phát Vorbis; kiểm tra pass dựa vào PCM thật và exit code.
