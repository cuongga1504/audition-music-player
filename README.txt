TBM PLAYER — AUDITION OFFLINE

Chạy TBMPlayer-Offline.exe. Không cần mở game, đăng nhập hoặc cài Python.

Giao diện
Thư viện ở giữa, bài đang phát bên phải và thanh điều khiển cố định phía dưới.
Đĩa nhạc quay khi đang phát, đứng yên khi tạm dừng/dừng/kết thúc bài,
và tiếp tục quay khi phát tiếp.
Thanh bên trái để mở tệp/thư mục và chọn FFmpeg. Bài trước/Bài sau đi theo
danh sách đang hiển thị; không tự lặp lại khi đến đầu/cuối danh sách.
Nhấn Ctrl+F để đưa con trỏ vào ô tìm kiếm.

1. Chương trình tự liệt kê nhạc trong D:\Audition\abm nếu thư mục tồn tại.
   Có thể chọn Mở tệp hoặc Mở thư mục để dùng vị trí khác.
2. Danh sách hiện tên bài, ca sĩ và tên tệp. Bài không có dữ liệu tên sẽ
   hiển thị tên file; ca sĩ để trống. Cột Ngày sửa đổi là Date Modified của
   tệp, hiển thị dd/mm/yyyy HH:MM theo giờ Việt Nam (UTC+7), tự cập nhật
   cùng thư viện. Thu nhỏ cửa sổ có thể cuộn ngang để xem đủ các cột.
   Có thể tìm theo tên bài (có/không dấu),
   ca sĩ hoặc tên file. Chọn bài rồi nhấn Nghe, hoặc nhấp đúp vào tên tệp.
   Chỉ giải mã bài khi phát/xuất tới bài đó, không giải mã trước cả thư mục.
   Khi mở thư mục, danh sách tự kiểm tra file mới/thay đổi mỗi 3 giây và
   ngay trước khi chuyển bài. File đã được cập nhật sẽ được giải mã lại
   vào lần phát tiếp theo; bài đang nghe không bị ngắt giữa chừng.
3. Dùng Tạm dừng / Tiếp tục / Dừng để điều khiển phát nhạc.
   Tự chuyển bài được bật sẵn: khi hết bài, chương trình phát bài kế tiếp
   theo danh sách đang hiển thị (kể cả bộ lọc tìm kiếm). Hết bài cuối thì dừng.
   Có thể bỏ chọn Tự chuyển bài khi hết. Nhấn Dừng không tự chuyển bài.
4. Chọn Xuất MP3 hoặc Lưu OGG / WAV để lưu thành tệp mới.
   Chương trình không ghi đè các tệp đã có.

FFmpeg
Nghe và xuất MP3/WAV cần ffmpeg.exe. Chương trình tự tìm cạnh TBMPlayer-Offline.exe,
trong C:\ffmpeg\bin, trong D:\Audition\ffmpeg64.exe hoặc trong PATH.
Máy hiện tại đã có FFmpeg, không cần cài thêm. Nếu chuyển sang máy khác,
nhấn Chọn FFmpeg để chỉ đến bản FFmpeg trên máy đó. Lưu OGG không cần FFmpeg.
FFmpeg không được đóng gói trong EXE.

Hoạt động hoàn toàn offline
Không khởi động Audition.exe, không đọc bộ nhớ game, không kết nối mạng,
không sửa DLL hoặc tệp trong thư mục game. WAV dùng khi nghe được lưu tạm
và dọn khi đóng chương trình.

Định dạng và giới hạn
- Tập thử ban đầu: 84/84 TBM. Thư viện mở rộng hiện có 5.585 TBM/ABM;
  chưa khẳng định phát được toàn bộ. Xem VALIDATION.txt để biết phạm vi thử.
- Mẫu v3585.tbm: 218,18 giây, Vorbis stereo 44.100 Hz.
- Đã kiểm chứng TBM tag FF02FF01, FF01FF1A, ABM và TBM có trailer cố định
  12 byte bằng file game thật. Bổ sung các codebook đời cũ và 48 kHz.
- Header Vorbis bị tách khỏi TBM được dựng lại bằng mẫu libvorbis khớp phần
  setup còn lại. Header/metadata của OGG xuất ra có thể khác file OGG ban đầu;
  các trang âm thanh từ sequence 2 đến hết được giữ nguyên sau giải mã.
- Không thể khẳng định hỗ trợ mọi bản Audition hoặc mọi file TBM tương lai.
  File không khớp mẫu codebook, sai zlib hoặc sai CRC OGG sẽ bị từ chối.
- MP3 là bản mã hoá lại có mất dữ liệu. Chọn OGG để giữ nguyên các trang
  âm thanh nén của bài sau giải mã.
- Giới hạn tệp đầu vào và luồng OGG: 64 MiB.

Tên bài và ca sĩ
Dữ liệu trích từ các bảng SLK trong 021.acv, 045.acv, 073.acv của game.
Có 852 mã file trong bảng, 807 mã khớp thư viện tại thời điểm trích.
Đây là bảng cũ, không bao phủ mọi bài và mọi bản cập nhật. Ghép theo tên
file đầy đủ, không suy đoán tên bài từ mã gần giống.
EXE có sẵn bảng tên; song_metadata.json bên cạnh EXE được ưu tiên nếu có.
Có thể cập nhật bảng JSON này rồi mở lại chương trình. Nếu bảng thiếu hoặc
không đọc được, chương trình dùng bảng đóng gói; nếu không có cả hai thì
vẫn liệt kê/phát theo tên file.

Mã nguồn
player.py          Giao diện, tên bài/ca sĩ, phát WAV qua Windows MCI.
song_metadata.json Bảng ghép tên file với tên bài/ca sĩ và nguồn SLK.
tbm_decoder.py     Đọc metadata ẩn, đảo khối, Blowfish, zlib, dựng header OGG.
audio_utils.py     Kiểm tra OGG/CRC và xuất MP3/OGG/WAV bằng FFmpeg.
vorbis_templates.json  Header mẫu tạo bằng libvorbis và header Vorbis cũ
                       đã kiểm chứng CRC từ THD công khai; không chứa bài nhạc.

Chạy mã nguồn (Python 64-bit trên Windows):
  python -m pip install -r requirements.txt
  python player.py

Xuất bằng dòng lệnh (cũng dùng được với TBMPlayer-Offline.exe):
  python player.py "D:\Audition\abm\v3585.tbm" --export "C:\Music\v3585.mp3"
  python player.py input.tbm --export output.ogg --report receipt.json
Đường dẫn xuất và receipt phải là tệp mới. Thư mục cha phải tồn tại.

Đóng gói lại:
  python -m pip install pyinstaller
  python -m PyInstaller --onefile --windowed --name TBMPlayer-Offline --add-data "vorbis_templates.json;." --add-data "song_metadata.json;." player.py

Nguồn nghiên cứu
- Phân tích offline bản D:\Audition\Audition.exe:
  SHA-256 a840fb88453ee2c3bf431be6521c1cecde2ab3d39a458d520b3b2216f2d2bd55
- Các điểm tham chiếu native: 0040E880 (TBM), 00863F30 (chọn khóa),
  00BBF7F0/00BC0850 (hoán vị), 00BC1D00 (MT19937).
- Mô hình bootstrap offline và thuật toán hoán vị tham khảo:
  https://github.com/yudopr11/ayodance-texture-tools
- Mô tả tách header THD/BDY và dựng header Vorbis tham khảo:
  https://github.com/jujudamara/AUCN.14.2/blob/main/publicar/gestao/claude/gerar_thd_bdy_v21.py

Ngày kiểm tra: 27/11/2026.
