# Character Studio

Ứng dụng local-first biến nhiều ảnh của MỘT người thành nhân vật 3D phong cách hoá nhất quán, kèm turnaround 6 góc, 9 concept (5+4) và bản nâng cấp. Xem đặc tả đầy đủ trong [SPEC.md](SPEC.md).

**Trạng thái:**
- Phase 1: dự án, xác nhận quyền dùng ảnh, tải/xem/sắp xếp/xoá ảnh tham chiếu & ảnh nghiêng.
- Phase 2: lớp provider (Mock, Gemini, BFL FLUX, Midjourney chỉ để tham khảo), model registry, job queue bền vững, trang cài đặt nhà cung cấp, chọn model cho từng dự án.
- Chưa có bước tạo nhân vật trên giao diện (Phase 3+).

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

## Nhà cung cấp

Cấu hình key trong `.env` (xem `.env.example`) rồi khởi động lại backend. Trang **Nhà cung cấp & model** hiển thị trạng thái key, khả năng từng model, giá ước tính, và nút kiểm tra kết nối (gọi endpoint miễn phí: `GET models/{model}` của Gemini, `GET /v1/credits` của BFL).

| Provider | Model mặc định | Ảnh tham chiếu tối đa | Gọi API |
|---|---|---|---|
| Mock | `mock-v1` | 14 | Không — offline, cho test |
| Google Gemini | `gemini-nano-banana-2.1` | 14 | REST `generateContent`, đồng bộ |
| BFL FLUX | `flux-2-pro` | 8 (FLUX 3: 10) | REST bất đồng bộ, poll `polling_url` |
| Midjourney | — | — | Không có API chính thức → chỉ hiển thị |

Model ID, payload, giới hạn và giá đã đối chiếu tài liệu chính thức ngày 2026-10-08 (nguồn ghi ở đầu `backend/app/providers/gemini.py`, `bfl.py`). **Chưa kiểm chứng bằng lời gọi thật** vì chưa có key. Hai điểm cần xác nhận ở lần gọi thật đầu tiên:
- BFL FLUX.2 có nhận ảnh base64 inline không (tài liệu chỉ có ví dụ URL). Nếu bị lỗi 422, đặt `BFL_IMAGE_ENCODING=data_url`.
- Gemini có tôn trọng `imageConfig.imageSize` không (có báo cáo trên forum rằng tham số này đôi khi bị bỏ qua).

## Job

- Hàng đợi lưu trong SQLite, chạy trong tiến trình backend với số job đồng thời giới hạn (`JOB_CONCURRENCY`). Lỗi của một job không ảnh hưởng job khác.
- **Retry tự động** chỉ áp dụng cho lỗi chắc chắn chưa bị tính phí (429, 503, không kết nối được), với backoff luỹ thừa. Lỗi **không rõ kết quả** (timeout sau khi đã gửi, 504) không tự gửi lại, để tránh bị tính phí hai lần. Khi đó người dùng thử lại thủ công; thao tác này tạo job mới và giữ nguyên lịch sử.
- Provider bất đồng bộ (BFL) được poll phía server, ảnh kết quả tải về ngay (URL của BFL hết hạn sau khoảng 10 phút).
- Khởi động lại backend: job đang chờ kết quả (đã có request id) sẽ được poll tiếp. Job bị ngắt giữa lúc đang gửi sẽ đánh dấu lỗi `interrupted`.
- Giới hạn chi tiêu theo cửa sổ 24h (`SPEND_LIMIT_USD_PER_DAY`), tính trên chi phí thực nếu provider trả về, nếu không thì dùng chi phí ước tính.
- Ảnh tham chiếu được chuẩn hoá trước khi gửi: xoay đúng chiều theo EXIF, thu nhỏ tối đa 2048px, **bỏ metadata EXIF/GPS**.
- Chỉ chạy **một** tiến trình backend (không dùng `--workers > 1`).

## Cấu trúc

```
backend/
  app/
    main.py            FastAPI app, CORS, routers
    config.py          Đường dẫn & cấu hình từ .env
    models.py          Project, Asset (SQLAlchemy)
    schemas.py         Pydantic request/response
    routes/            projects, assets, providers, jobs
    providers/         base.py (interface, phân loại lỗi), mock.py, gemini.py, bfl.py, registry.py
    jobs/              service.py (tạo/huỷ/thử lại, giới hạn chi), runner.py (worker async)
    logging_setup.py   lọc API key & base64 khỏi log
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

## API

| Method | Path | |
|---|---|---|
| GET/POST | `/api/projects` | Danh sách / tạo dự án |
| GET/PATCH/DELETE | `/api/projects/{id}` | Chi tiết / sửa (tên, mô tả, `rights_confirmed`) / xoá kèm file |
| GET/POST | `/api/projects/{id}/assets` | Danh sách / tải ảnh (multipart `files[]`, `kind=reference\|side_profile`) |
| PUT | `/api/projects/{id}/assets/order` | Sắp xếp lại `{asset_ids: [...]}` |
| PATCH/DELETE | `/api/assets/{id}` | Đổi loại ảnh / xoá |
| GET | `/api/assets/{id}/content` | Nội dung ảnh |
| GET | `/api/providers`, `/api/providers/{p}/models` | Provider, trạng thái key, model & khả năng |
| POST | `/api/providers/{p}/test` | Kiểm tra kết nối |
| GET | `/api/spend` | Chi tiêu 24h / giới hạn |
| GET | `/api/projects/{id}/jobs` | Lịch sử job (lọc `status`, `purpose`) |
| GET | `/api/jobs/{id}` | Trạng thái job |
| POST | `/api/jobs/{id}/cancel`, `/api/jobs/{id}/retry` | Huỷ / thử lại (tạo job mới) |
| GET | `/health` | Health check |

Lỗi trả về dạng `{"detail": {"code": "...", "message": "..."}}` (ví dụ `rights_not_confirmed`, `invalid_image`, `too_many_photos`).

## Bảo mật & quyền riêng tư

- Server chỉ bind `127.0.0.1`; CORS giới hạn origin của dev server. Không có xác thực — đừng mở ra mạng.
- Upload: phải xác nhận quyền dùng ảnh; kiểm tra kích thước, giải mã thật bằng Pillow (chặn file hỏng/giả đuôi/decompression bomb), chỉ JPEG/PNG/WEBP; tên file lưu trên đĩa do server sinh (UUID), tên gốc được làm sạch; chặn path traversal.
- Ảnh và DB nằm trong `data/` (gitignored). Xoá dự án xoá luôn file trên đĩa.
- Khi tạo ảnh, ảnh tham chiếu được gửi tới provider bạn chọn. Xoá ở máy này không xoá được bản provider đã nhận; việc đó tuỳ chính sách lưu trữ của họ:
  - Gemini gói miễn phí: Google có thể dùng dữ liệu để cải thiện sản phẩm. Nên dùng key trả phí.
  - BFL: dữ liệu có thể được dùng để huấn luyện. Muốn từ chối, gửi email tới privacy@blackforestlabs.ai.
- API key chỉ nằm ở server. Không có trong response API, bundle frontend hay log. Log có bộ lọc che key và chuỗi base64; test tự động kiểm tra cả hai điều này.
- Chỉ gửi key BFL tới `polling_url` thuộc `*.bfl.ai` qua https. Ảnh kết quả tải về không kèm key.

## Migration

```bash
cd backend
venv/bin/alembic revision --autogenerate -m "mô tả"
venv/bin/alembic upgrade head
```
