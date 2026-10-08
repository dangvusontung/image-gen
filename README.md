# Character Studio

Ứng dụng local-first biến nhiều ảnh của MỘT người thành nhân vật 3D phong cách hoá nhất quán, kèm turnaround 6 góc, 9 concept (5+4) và bản nâng cấp. Xem đặc tả đầy đủ trong [SPEC.md](SPEC.md).

**Trạng thái:**
- Phase 1: dự án, xác nhận quyền dùng ảnh, tải/xem/sắp xếp/xoá ảnh tham chiếu & ảnh nghiêng.
- Phase 2: lớp provider (Mock, Gemini, BFL FLUX, Midjourney chỉ để tham khảo), model registry, job queue bền vững, trang cài đặt nhà cung cấp, chọn model cho từng dự án.
- Phase 3: tạo 1–4 biến thể nhân vật gốc, duyệt và giữ lịch sử; turnaround sáu ảnh độc lập, tạo lại từng góc bằng phiên bản mới; chỉnh sửa/reset prompt theo dự án.
- Phase 4: chín ảnh concept độc lập theo batch A (5) và B (4), brief đa dạng, đổi phân bổ góc ở các đợt sau, tạo lại từng ô và giữ phiên bản trước.
- Phase 5: nâng cấp ảnh 3:4, so sánh trước/sau, lightbox, lịch sử job/phê duyệt, huỷ/thử lại, tải gốc/PNG/JPEG, bảng ảnh và ZIP toàn dự án.

MVP đã có đủ quy trình và test offline. Tích hợp Gemini/BFL dùng API chính thức và có test HTTP giả lập; chưa xác minh chất lượng giữ nhận diện hay kết quả từ API trả phí bằng lời gọi thật.

## Quick setup on another device

Install **Git, Python 3.12+ and Node.js 24**. Then:

```bash
git clone https://github.com/dangvusontung/image-gen.git
cd image-gen
python3 setup.py
python3 run.py
```

On Windows, use `py setup.py` and `py run.py`. On Linux, install your Python version's `venv` package if virtual-environment creation fails (for example `sudo apt install python3.12-venv`).

Open **http://127.0.0.1:5173**. The setup script creates `.env`, installs dependencies and applies database migrations. Run it again after pulling updates; it preserves your existing `.env` and data. Stop the app before updating. The launcher runs both servers in one terminal; Ctrl+C stops them. Backend changes require a launcher restart, so editing code does not interrupt generations automatically.

**Optional real images:** edit the root `.env` and add `GEMINI_API_KEY` and `BFL_API_KEY`, then restart the launcher. In a project, select **Tiết kiệm · Gemini 1K → FLUX.2 Pro**. Without keys, use **Mock** to test for free. Concurrency defaults to 9; the app spending cap is disabled (`SPEND_LIMIT_USD_PER_DAY=0`).

**Data stays local:** GitHub contains source code only. Photos, generated images, SQLite databases, `.env`, installed dependencies and build/test outputs are ignored. Another device starts with an empty workspace. To transfer projects, stop the app on both devices and copy the `data/` folder privately; configure API keys separately. Back up the destination's data before replacing it.

## Yêu cầu

- Python 3.12 + [uv](https://docs.astral.sh/uv/) (hoặc `python3.12-venv` + pip)
- Node.js 20.19+ hoặc 22.12+ (khuyên dùng 24)
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
(cd backend && venv/bin/python -m pytest tests -q)   # API, job, workflow, export, migrations
(cd frontend && npm test)                            # Vitest (unit + component)
(cd frontend && npm run build)                       # TypeScript + Vite production build
(cd frontend && npm run e2e)                         # Playwright, dùng Chrome hệ thống
```

E2E tự khởi động backend riêng (cổng 8100, dữ liệu trong thư mục tạm) và Vite (cổng 5180) — không đụng tới dữ liệu thật. Dùng Chromium của Playwright thay cho Chrome: `npx playwright install chromium && PW_CHANNEL=chromium npm run e2e`.

## Quy trình nhân vật gốc và turnaround

Sau khi cập nhật mã, chạy `(cd backend && venv/bin/alembic upgrade head)` để áp dụng migrations 003–005. Lệnh giữ nguyên dự án và ảnh hiện có.
Trong dự án, tải ảnh và xác nhận quyền sử dụng, mở **Nhân vật gốc**, chọn số biến thể và tạo ảnh. Mở ảnh để xem kích thước gốc, so sánh các biến thể trong lưới rồi duyệt một ảnh. Mở **Turnaround**, tạo sáu góc và duyệt khi cả sáu hoàn tất. Với provider trả phí, giao diện hiển thị chi phí ước tính (nếu có) và yêu cầu xác nhận trước khi tạo nhiều ảnh.

Tạo lại một góc tạo phiên bản turnaround mới, giữ nguyên năm góc còn lại và bản đã duyệt. Duyệt nhân vật gốc khác đánh dấu turnaround cũ là dựa trên master cũ; ảnh và lịch sử không bị xoá. Prompt được lưu phiên bản riêng trong backend, có override theo dự án và snapshot trong mỗi job. Dùng provider **Mock** để thử toàn bộ quy trình mà không mất phí; ảnh mock chỉ là dữ liệu thử, không thể hiện khả năng giữ nhận diện.

API mới: `GET /api/projects/{id}/workflow`, `POST /api/projects/{id}/master/generate` (`variants: 1–4`, `confirmed`), `POST /api/projects/{id}/master/{version_id}/approve`, `POST /api/projects/{id}/turnaround/generate`, `POST /api/projects/{id}/turnaround/{version_id}/views/{angle}/regenerate`, `POST /api/projects/{id}/turnaround/{version_id}/approve`, `GET/PUT /api/prompts/{name}?project_id={id}` (`body: null` để reset).

## Quy trình tiết kiệm Gemini + BFL

Trong dự án, chọn **Quy trình tạo ảnh → Tiết kiệm · Gemini 1K → FLUX.2 Pro**. Cấu hình `GEMINI_API_KEY` và `BFL_API_KEY` trong `.env`, rồi khởi động lại backend. Lựa chọn được lưu theo dự án; dự án mới và cũ mặc định vẫn dùng chế độ thủ công/Mock để không tự phát sinh chi phí.

Master, sáu ảnh turnaround và chín concept dùng `gemini-nano-banana-2.1`, mặc định **1K**. Duyệt master trước khi tạo góc, xem batch A trước khi tạo batch B. Bản nâng cấp dùng `flux-2-pro`, mặc định **1MP**, với master đã duyệt, concept nguồn và **một góc turnaround phù hợp**. Nếu chưa có turnaround, gửi master và concept. Không dùng sáu góc cho bản nâng cấp ở chế độ này. Có thể chọn kích thước khác ở bước concept/nâng cấp; chi phí được tính lại theo provider và tham chiếu thực tế.

Nếu FLUX làm thay đổi nhận diện, chọn **Tiết kiệm · Gemini 1K, hoàn thiện bằng Gemini** để các bản nâng cấp tiếp theo dùng Gemini với cùng tập tham chiếu gọn. Các ảnh và job cũ giữ nguyên provider/model/kích thước; thử lại job giữ cấu hình gốc. Chuyển lại **Thủ công** để dùng provider/model đã chọn trước đó.

Ước tính minh hoạ: 16 ảnh Gemini 1K × $0.0336 + một bản FLUX.2 Pro 1MP với ba ảnh tham chiếu mỗi ảnh tính 1MP = **$0.6126**, chưa gồm token đầu vào/văn bản Gemini, thuế hoặc lần tạo lại. Tham chiếu lớn hơn tăng chi phí BFL. Giao diện hiển thị ước tính từng bước, yêu cầu xác nhận batch trả phí và áp dụng giới hạn chi tiêu 24h cho cả hai provider. Không tự gọi provider dự phòng khi lỗi. Chế độ này được kiểm thử bằng provider giả lập; chất lượng giữ nhận diện qua hai provider cần kiểm tra với ảnh thực.

API: `PATCH /api/projects/{id}` với `workflow_mode: "manual" | "hybrid" | "hybrid_gemini"`. Các endpoint tạo ảnh tự chọn provider/model và kích thước mặc định theo chế độ; `/generation-estimate` và `/enhance-plan` dùng cùng chính sách. `/enhance-plan` trả thêm `provider`, `model`, `size`.

## Concept, nâng cấp và xuất ảnh

Menu **Chọn trang phục và bối cảnh** cho phép chọn quần short jeans, chân váy jeans/xếp ly, váy mùa hè, áo phối cùng, cảnh hồ bơi/bãi biển/cafe/vườn/phố và ánh sáng. Mặc định phối short jeans và chân váy giữa các ô. Chọn **Tùy chỉnh** để nhập trang phục hoặc bối cảnh riêng; có thể nhập hoạt động. Chọn **Số ảnh** để tạo 1–5 ảnh trong A hoặc 1–4 ảnh trong B, rồi tạo thêm đợt khi cần. Lựa chọn menu được lưu trong trình duyệt theo dự án và áp dụng khi tạo mới hoặc tạo lại ô. Backend lưu lựa chọn trong metadata job và lưu brief/prompt thực tế trong lịch sử. Tạo lại qua API mà không gửi lựa chọn giữ menu của ảnh nguồn; nút **Thử lại job** luôn giữ nguyên prompt và cấu hình gốc.

1. Mở **Concept**, chọn **Batch A · 5 ảnh**, rồi **Tạo batch A**. Chuyển sang **Batch B · 4 ảnh** để tạo bốn ảnh còn lại. Batch trả phí cần xác nhận chi phí. Mỗi ô có mood, góc máy, brief (bối cảnh/hoạt động/trang phục/tư thế/biểu cảm/hướng nhìn/ánh sáng), trạng thái job, prompt đã dùng và các nút tạo lại/nâng cấp/tải ảnh.
2. **Tạo lại ô** sinh brief và ảnh mới, giữ ảnh cũ trong phần phiên bản. **Thử lại job** dùng đúng prompt và tham chiếu đã lưu, tạo job/phiên bản mới. Lỗi một ô không xoá các ô thành công. Chọn **Đợt** để xem lại những lần chạy batch trước.
3. Chọn **Nâng cấp ô**, hoặc mở **Nâng cấp** và chọn một concept nguồn. App gửi master đã duyệt, concept nguồn và turnaround cho model để tạo một ảnh 3:4 mới; không phóng to/cắt thumbnail. Nếu vượt giới hạn tham chiếu, app hiển thị cảnh báo và cần xác nhận rõ ràng: ưu tiên master, concept, rồi góc turnaround phù hợp. Concept dùng master cũ vẫn có thể nâng cấp với master hiện tại; UI đánh dấu rõ nguồn cũ.
4. Xem ảnh nguồn bên trái, các bản nâng cấp bên phải. Nhấn ảnh nâng cấp mở lightbox so sánh trước/sau. Mỗi bản có tải ảnh gốc, PNG và JPEG. Sau khi tải lại trang, bước nâng cấp mặc định chọn concept có bản nâng cấp gần nhất.
5. **Xem bảng ảnh** ghép các ảnh độc lập trên frontend. **Tải bảng ảnh** xuất PNG từ đợt/batch đang xem; ô đang chờ/lỗi vẫn có vị trí riêng. **Tải toàn bộ dự án (ZIP)** gồm ảnh tham chiếu, mọi ảnh đã tạo, bảng ảnh tổng hợp và `manifest.json` chứa job, prompt, tham chiếu, chi phí và ID master/turnaround đã duyệt. ZIP không phải bản sao lưu có thể nhập lại; sao lưu cả `data/` để giữ nguyên DB.

Chạy thử không tốn phí: để trống các key trong `.env`, giữ provider **Mock** và model **Mock v1**, rồi làm từ bước 1 đến 5. Test browser tự động bao phủ quy trình này, so sánh trước/sau, download và cảnh báo giới hạn hai tham chiếu. Ảnh mock có chữ **MOCK PROVIDER**, chỉ là placeholder; dùng Gemini/BFL đã cấu hình key để tạo ảnh thực.

## Cấu hình provider

Cấu hình key trong `.env` (xem `.env.example`) rồi khởi động lại backend. Trang **Nhà cung cấp & model** hiển thị trạng thái key, khả năng từng model, giá ước tính, và nút kiểm tra kết nối (gọi endpoint miễn phí: `GET models/{model}` của Gemini, `GET /v1/credits` của BFL).

| Provider | Model mặc định | Ảnh tham chiếu tối đa | Gọi API |
|---|---|---|---|
| Mock | `mock-v1` | 14 | Không — offline, cho test |
| Google Gemini | `gemini-nano-banana-2.1` | 14 | REST `generateContent`, đồng bộ |
| BFL FLUX | `flux-2-pro` | 8 (FLUX 3: 10) | REST bất đồng bộ, poll `polling_url` |
| Midjourney | — | — | Không có API chính thức → chỉ hiển thị |

Model ID, payload, giới hạn và giá đã đối chiếu tài liệu chính thức ngày 2026-10-08: [Gemini GenerateContent](https://ai.google.dev/gemini-api/docs/generate-content/image-generation), [giá Gemini](https://ai.google.dev/gemini-api/docs/pricing), [FLUX.2 editing](https://docs.bfl.ai/flux_2/flux2_image_editing), [BFL OpenAPI](https://api.bfl.ai/openapi.json), [giá BFL](https://bfl.ai/pricing?category=flux.2). **Chưa kiểm chứng bằng lời gọi thật**. Cần kiểm tra lần gọi thật đầu tiên:
- BFL FLUX.2 có nhận ảnh base64 inline không (tài liệu chỉ có ví dụ URL). Nếu bị lỗi 422, đặt `BFL_IMAGE_ENCODING=data_url`.
- Kích thước ảnh và độ nhất quán nhận diện thực tế từ model đã chọn. API có thể trả lỗi quyền truy cập, moderation hoặc quota; app hiển thị lỗi theo từng job.

## Job

- Hàng đợi lưu trong SQLite, chạy trong tiến trình backend với số job đồng thời giới hạn (`JOB_CONCURRENCY`). Lỗi của một job không ảnh hưởng job khác.
- **Retry tự động** chỉ áp dụng cho lỗi chắc chắn chưa bị tính phí (429, 503, không kết nối được), với backoff luỹ thừa. Lỗi **không rõ kết quả** (timeout sau khi đã gửi, 504) không tự gửi lại, để tránh bị tính phí hai lần. Khi đó người dùng thử lại thủ công; thao tác này tạo job mới và giữ nguyên lịch sử.
- Provider bất đồng bộ (BFL) được poll phía server, ảnh kết quả tải về ngay (URL của BFL hết hạn sau khoảng 10 phút).
- Khởi động lại backend: job đang chờ kết quả (đã có request id) sẽ được poll tiếp. Job bị ngắt giữa lúc đang gửi sẽ đánh dấu lỗi `interrupted`.
- Giới hạn chi tiêu theo cửa sổ 24h (`SPEND_LIMIT_USD_PER_DAY`), tính trên chi phí thực nếu provider trả về, nếu không dùng ước tính. FLUX.2 tính cả megapixel của từng tham chiếu sau chuẩn hoá và kích thước đầu ra. Gemini dùng giá ảnh đầu ra, chưa gồm token đầu vào/văn bản. Giá không công bố được hiển thị là chưa có, không tự thay bằng giá một kích thước khác. Đây là guard theo ước tính, không phải hạn mức cứng từ nhà cung cấp.
- Job có kết quả gửi không rõ (timeout/mất kết nối sau khi gửi) vẫn giữ khoản chi ước tính; không coi là miễn phí chỉ vì chưa nhận request ID. Batch bị từ chối vì thiếu xác nhận hoặc vượt hạn mức được rollback toàn bộ, không để lại các slot/job dở dang.
- Ảnh tham chiếu được chuẩn hoá trước khi gửi: xoay đúng chiều theo EXIF, thu nhỏ tối đa 2048px, **bỏ metadata EXIF/GPS**.
- Chỉ chạy **một** tiến trình backend (không dùng `--workers > 1`).

## Cấu trúc

```
backend/
  app/
    main.py            FastAPI app, CORS, routers
    config.py          Đường dẫn & cấu hình từ .env
    models.py          Project, Asset, master/turnaround, Concept, EnhancementVersion, approvals/prompts/jobs
    schemas.py         Pydantic request/response
    routes/            projects, assets, providers, jobs, workflow, concepts, exports
    concept_planning.py  tạo brief cảnh mới và phân bổ mood/góc
    prompts/           template v1 theo file, override có phiên bản
    providers/         base.py (interface, phân loại lỗi), mock.py, gemini.py, bfl.py, registry.py
    jobs/              service.py (tạo/huỷ/thử lại, giới hạn chi), runner.py, versioning.py
    logging_setup.py   lọc API key & base64 khỏi log
    storage/           local.py (file store an toàn path), validation.py (Pillow)
  migrations/          Alembic
  tests/
frontend/
  src/
    api/client.ts      fetch client + TanStack Query hooks
    pages/             Dashboard, ProjectWorkspace
    components/        ReferencesStep, CharacterStep, ConceptsStep, EnhanceStep, HistoryStep, GenerationUI
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
| GET | `/api/assets/{id}/download?format=original\|png\|jpeg` | Tải ảnh độc lập |
| GET | `/api/projects/{id}/workflow` | Phiên bản master/turnaround và phê duyệt |
| POST | `/api/projects/{id}/master/generate`, `/master/{version}/approve` | Tạo/duyệt master |
| POST | `/api/projects/{id}/turnaround/generate`, `/turnaround/{version}/approve` | Tạo/duyệt sáu góc |
| POST | `/api/projects/{id}/turnaround/{version}/views/{angle}/regenerate` | Tạo phiên bản mới với một góc thay thế |
| GET/PUT | `/api/prompts/{name}?project_id={id}` | Prompt mặc định/override/reset |
| GET | `/api/projects/{id}/generation-estimate?purpose=concept&count=5` | Ước tính chi phí trước khi tạo |
| GET/POST | `/api/projects/{id}/concepts`, `/concepts/generate` | Lịch sử concept / tạo batch `{batch: "A"\|"B", confirmed, size?}` |
| POST | `/api/projects/{id}/concepts/{concept}/regenerate` | Tạo revision mới `{size?}` |
| GET | `/api/projects/{id}/concepts/{concept}/enhance-plan` | Tập tham chiếu, chi phí, cảnh báo trước khi nâng cấp |
| POST | `/api/projects/{id}/concepts/{concept}/enhance` | Nâng cấp `{size?, confirm_reference_subset}` |
| GET | `/api/projects/{id}/enhancements` | Phiên bản nâng cấp và job |
| GET | `/api/projects/{id}/contact-sheet?batch=A&run=1` | PNG bảng ảnh (batch/run tuỳ chọn) |
| GET | `/api/projects/{id}/export` | ZIP tất cả ảnh và manifest |
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

Giới hạn chi tiêu ứng dụng mặc định tắt: `SPEND_LIMIT_USD_PER_DAY=0` nghĩa là không giới hạn. Chi phí vẫn được theo dõi. Đặt một số USD dương để bật giới hạn 24h nếu muốn.
