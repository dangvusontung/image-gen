# Character Studio

Ứng dụng local-first biến nhiều ảnh của MỘT người thành nhân vật 3D phong cách hoá nhất quán, kèm turnaround 6 góc, 9 concept (5+4) và bản nâng cấp. Xem đặc tả đầy đủ trong [SPEC.md](SPEC.md).

**Trạng thái:** Phase 1 xong — tạo dự án, xác nhận quyền dùng ảnh, tải/xem/sắp xếp/xoá ảnh tham chiếu & ảnh nghiêng, mock provider. Chưa có bước tạo ảnh (Phase 2+).

## Yêu cầu

- Python 3.12 + [uv](https://docs.astral.sh/uv/) (hoặc `python3.12-venv` + pip)
- Node.js 20+ (đã thử với 24)
- Google Chrome (chỉ cho test E2E)

## Chạy lần đầu

```bash
cp .env.example .env

# Backend — terminal 1
cd backend
uv venv --python 3.12 venv
uv pip install --python venv/bin/python -r requirements.txt
venv/bin/alembic upgrade head
venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend — terminal 2
cd frontend
npm install
npm run dev
```

Mở http://127.0.0.1:5173. API docs (OpenAPI): http://127.0.0.1:8000/docs.

Không có uv: `python3.12 -m venv venv && venv/bin/pip install -r requirements.txt` (cần gói `python3.12-venv` trên Debian/Ubuntu).

## Test

```bash
cd backend && venv/bin/python -m pytest tests -q     # API, validation, storage, migrations
cd frontend && npm test                              # Vitest (unit + component)
cd frontend && npm run e2e                           # Playwright, dùng Chrome hệ thống
```

E2E tự khởi động backend riêng (cổng 8100, dữ liệu trong thư mục tạm) và Vite (cổng 5180) — không đụng tới dữ liệu thật. Dùng Chromium của Playwright thay cho Chrome: `npx playwright install chromium && PW_CHANNEL=chromium npm run e2e`.

## Cấu trúc

```
backend/
  app/
    main.py            FastAPI app, CORS, routers
    config.py          Đường dẫn & cấu hình từ .env
    models.py          Project, Asset (SQLAlchemy)
    schemas.py         Pydantic request/response
    routes/            projects, assets, providers
    providers/         base.py (interface), mock.py
    storage/           local.py (file store an toàn path), validation.py (Pillow)
  migrations/          Alembic
  tests/
frontend/
  src/
    api/client.ts      fetch client + TanStack Query hooks
    pages/             Dashboard, ProjectWorkspace
    components/        ReferencesStep, UploadDropzone, ... ; ui/ = shadcn/ui
    lib/               upload validation, hash routing
  e2e/                 Playwright
data/                  DB SQLite + ảnh (gitignored)
```

## API (Phase 1)

| Method | Path | |
|---|---|---|
| GET/POST | `/api/projects` | Danh sách / tạo dự án |
| GET/PATCH/DELETE | `/api/projects/{id}` | Chi tiết / sửa (tên, mô tả, `rights_confirmed`) / xoá kèm file |
| GET/POST | `/api/projects/{id}/assets` | Danh sách / tải ảnh (multipart `files[]`, `kind=reference\|side_profile`) |
| PUT | `/api/projects/{id}/assets/order` | Sắp xếp lại `{asset_ids: [...]}` |
| PATCH/DELETE | `/api/assets/{id}` | Đổi loại ảnh / xoá |
| GET | `/api/assets/{id}/content` | Nội dung ảnh |
| GET | `/api/providers` | Provider khả dụng (hiện chỉ `mock`) |
| GET | `/health` | Health check |

Lỗi trả về dạng `{"detail": {"code": "...", "message": "..."}}` (ví dụ `rights_not_confirmed`, `invalid_image`, `too_many_photos`).

## Bảo mật & quyền riêng tư

- Server chỉ bind `127.0.0.1`; CORS giới hạn origin của dev server. Không có xác thực — đừng mở ra mạng.
- Upload: phải xác nhận quyền dùng ảnh; kiểm tra kích thước, giải mã thật bằng Pillow (chặn file hỏng/giả đuôi/decompression bomb), chỉ JPEG/PNG/WEBP; tên file lưu trên đĩa do server sinh (UUID), tên gốc được làm sạch; chặn path traversal.
- Ảnh và DB nằm trong `data/` (gitignored). Xoá dự án xoá luôn file trên đĩa.
- Từ Phase 2: ảnh tham chiếu sẽ được gửi tới provider bạn chọn (Gemini/BFL); xoá cục bộ không xoá bản provider đã nhận — tuỳ chính sách lưu trữ của họ. API key chỉ ở server (`.env`), không bao giờ vào bundle frontend hay log.

## Migration

```bash
cd backend
venv/bin/alembic revision --autogenerate -m "mô tả"
venv/bin/alembic upgrade head
```
