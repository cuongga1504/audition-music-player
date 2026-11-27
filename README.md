# Audition Music Player

Trình phát nhạc Audition offline cho Windows. Đọc TBM/ABM khi phát, hiển thị tên bài và ca sĩ nếu có dữ liệu, xuất MP3/OGG/WAV.

## Chức năng

- Thư viện nhạc, khu vực bài đang phát, thanh điều khiển và đĩa quay theo trạng thái phát.
- Bài trước/bài sau, tạm dừng/tiếp tục, tự chuyển bài khi kết thúc.
- Nhận file thêm/xóa/cập nhật trong thư mục mỗi 3 giây; giải mã khi cần nghe hoặc xuất.
- Tên bài/ca sĩ từ 852 bản ghi trích từ bảng dữ liệu game. File chưa có thông tin hiển thị tên file.
- Tìm theo tên bài có/không dấu, ca sĩ hoặc tên file. Ctrl+F để tìm kiếm.
- Ngày sửa đổi của file theo giờ Việt Nam (UTC+7).
- Kiểm tra checksum zlib, CRC OGG và mẫu header trước khi phát/xuất.

## Chạy từ mã nguồn

Đã kiểm tra trên Windows với Python 3.14. Cần Python có Tkinter và FFmpeg để nghe hoặc xuất MP3/WAV.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python player.py
```

Chương trình tự mở `D:\Audition\abm` nếu thư mục tồn tại. Có thể dùng **Mở tệp** hoặc **Mở thư mục** để chọn vị trí khác.

FFmpeg được tìm cạnh chương trình, trong PATH, `C:\ffmpeg\bin` hoặc `D:\Audition\ffmpeg64.exe`. Nút **Chọn FFmpeg** cho phép chọn thủ công. Xuất OGG không cần FFmpeg.

## Xuất bằng dòng lệnh

```powershell
python player.py "D:\Audition\abm\v3585.tbm" --export "output.mp3"
python player.py "input.tbm" --export "output.ogg" --report "receipt.json"
```

File đầu ra phải là file mới và thư mục cha phải tồn tại.

## Build EXE

```powershell
python -m pip install -r requirements-build.txt
.\build.ps1
```

Kết quả: `dist/TBMPlayer-Offline.exe`. Bảng tên bài và mẫu Vorbis được đóng gói trong EXE. File `song_metadata.json` bên cạnh EXE được ưu tiên, cho phép cập nhật bảng tên rồi mở lại chương trình.

## Kiểm tra

Chạy trên Windows có phiên desktop để Tkinter hoạt động:

```powershell
python -m unittest discover -s tests -v
```

13 kiểm tra bao gồm tự chuyển bài, dừng/tạm dừng, cập nhật thư mục và cache theo phiên bản file. Xem [VALIDATION.txt](VALIDATION.txt) cho phạm vi kiểm tra với file nhạc thật và các lượt kiểm tra giao diện/hoạt ảnh.

## Giới hạn

- Chưa hỗ trợ mọi biến thể TBM/ABM hoặc codebook Vorbis. File không đủ dữ liệu hoặc không xác định được header sẽ bị từ chối.
- Bảng tên bài trích từ dữ liệu cũ, chưa bao phủ toàn bộ thư viện nhạc.
- Header OGG được khôi phục; các trang âm thanh sau header được giữ nguyên. Không khẳng định file xuất giống từng byte với OGG gốc trước khi game đóng gói.
- MP3 là bản chuyển mã có mất dữ liệu. Chọn OGG để giữ các trang âm thanh nén sau giải mã.
- Giới hạn đầu vào/luồng OGG: 64 MiB.

## Cấu trúc

| File | Vai trò |
| --- | --- |
| `player.py` | Giao diện Tkinter, Windows MCI, thư viện và dòng lệnh |
| `tbm_decoder.py` | TBM/ABM, Blowfish, zlib và khôi phục header Vorbis |
| `audio_utils.py` | Kiểm tra OGG và xuất âm thanh bằng FFmpeg |
| `song_metadata.json` | Ghép tên file với tên bài và ca sĩ, kèm nguồn dữ liệu |
| `vorbis_templates.json` | Mẫu header/codebook và bảng hoán vị |
| `tests/test_player.py` | Kiểm tra tự chuyển bài và cập nhật thư viện |

Repository chứa mã nguồn và dữ liệu hỗ trợ, không bao gồm file nhạc/game hoặc FFmpeg. Tài liệu chi tiết: [README.txt](README.txt), [CHANGELOG.txt](CHANGELOG.txt).

## Nguồn tham khảo

Các thuật toán và dữ liệu tham khảo được ghi trong [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt). Giấy phép PyCryptodome nằm trong [PyCryptodome-LICENSE.txt](PyCryptodome-LICENSE.txt).
