# Tự động build EXE bằng GitHub Actions

Workflow: `.github/workflows/windows-release.yml` — **Build Windows EXE**.

Máy Windows của GitHub tự cài Python 3.14 x64, cài dependencies, chạy unittest,
build bằng script sẵn có, kiểm tra EXE, xác minh ZIP rồi upload kết quả.
Máy cá nhân không cần mở hoặc tự build khi workflow chạy trên GitHub.

## 1. Đưa cấu hình lên repository

Chạy trong thư mục project:

```powershell
git add .github/workflows/windows-release.yml build-cassette.ps1 README.md docs/GITHUB_ACTIONS.md
git commit -m "ci: build Windows EXE and publish tagged releases"
git push origin main
```

Workflow cần script build mới có tham số `-Version` và tự tạo ZIP; phải đưa
cả hai lên GitHub trong cùng phiên bản mã nguồn.

Mở repository → **Settings → Actions → General**. Nếu Actions đang bị tắt,
bật để cho phép workflow và các action chính thức của GitHub (`actions/*`).
Workflow đã khai báo `permissions: contents: write` và dùng `GITHUB_TOKEN`
được GitHub cấp cho job; không cần thêm PAT hoặc secret thủ công. Nếu tổ chức
giới hạn quyền Actions, cần chủ repository/tổ chức cho phép job ghi Releases.

## 2. Chạy thử, chưa tạo Release

Mở **Actions → Build Windows EXE → Run workflow → chọn main → Run workflow**.
Nút Run workflow xuất hiện khi tệp workflow đã có trên nhánh mặc định.

Khi job xanh, mở lần chạy đó và kéo xuống **Artifacts** để tải bản build.
Artifact tải từ Actions có thể là một ZIP bọc bên ngoài ZIP phát hành; giải nén
để lấy `TBMCassettePlayer-v1.0.0-win-x64.zip`. Chạy thủ công chỉ upload artifact,
không tự đăng Release. Phiên bản của bản build thủ công lấy từ `pyproject.toml`.

## 3. Tự động đăng GitHub Release

Sau khi mã nguồn và workflow đã push lên main, tạo và push tag phiên bản:

```powershell
git checkout main
git pull --ff-only origin main
git tag -a v1.0.0 -m "TBM Cassette Player v1.0.0"
git push origin v1.0.0
```

Tag phải trỏ đến commit có workflow. Push tag kích hoạt build và tạo Release
**v1.0.0**, tự đính kèm `TBMCassettePlayer-v1.0.0-win-x64.zip` vào **Assets**.
Không cần mở trang tạo Release hoặc upload ZIP thủ công.

Phiên bản tiếp theo dùng tag mới, chẳng hạn `v1.0.1`. Nếu tag `v1.0.0` đã tồn tại,
hãy dùng phiên bản mới thay vì tạo lại tag đó. Tag `v1.1.0-beta.1` được đánh dấu
prerelease. Tag phải có dạng `vMAJOR.MINOR.PATCH` hoặc kèm hậu tố prerelease.

## 4. Tìm kết quả và xử lý lỗi

- Repository → **Actions**: xem tiến trình và mở step màu đỏ để đọc lỗi.
- Repository → **Releases**: tải ZIP sau khi job chạy theo tag thành công.
- **Install dependencies** lỗi: kiểm tra package/version trên PyPI trong log.
- **Run tests** lỗi: chưa build hoặc đăng Release; xem tên test thất bại.
- **Build EXE and release ZIP** lỗi: kiểm tra log PyInstaller/PowerShell.
- **Publish GitHub Release** lỗi 403: kiểm tra quyền Actions hoặc chính sách tổ
  chức; workflow cần `contents: write`. Không cần bật quyền tạo/duyệt pull request.
- Đã có Release của tag: chạy lại workflow sẽ upload lại asset cùng tên.
  Nếu Release bật chế độ immutable, hãy phát hành bằng tag phiên bản mới.

Bản phát hành giữ toàn bộ thư mục `TBMCassettePlayer`, gồm EXE và `_internal`.
Người dùng giải nén ZIP rồi chạy EXE, không tách EXE khỏi thư mục đi kèm.

CI không chứa tệp TBM game: bài tích hợp yêu cầu `TBM_TEST_FILE` sẽ skip.
Các test còn lại chạy với Qt offscreen/software; bước smoke test chỉ kiểm tra
khởi động EXE/QML, không xác nhận chất lượng âm thanh hoặc mọi thiết bị output.

## Tài liệu chính thức

- [GITHUB_TOKEN và quyền workflow](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)
- [Upload artifact](https://github.com/actions/upload-artifact)
- [Tạo Release bằng GitHub CLI](https://cli.github.com/manual/gh_release_create)
