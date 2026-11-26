# Day 14 Lab — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns trong bản develop

1. **Ghi thông tin kết nối trực tiếp trong code.** [Dòng 17–18](01-localhost-vs-production/develop/app.py#L17-L18) gán API key và URL database có mật khẩu trong mã nguồn. Nếu dùng thông tin thật, người đọc repo hoặc lịch sử Git có thể lấy được.
2. **Giá trị cấu hình cố định.** [Dòng 21–22](01-localhost-vs-production/develop/app.py#L21-L22) gán trực tiếp `DEBUG` và `MAX_TOKENS`. Muốn đổi các giá trị này giữa local, staging và production phải sửa code.
3. **In câu hỏi, API key và câu trả lời ra log.** [Dòng 33–38](01-localhost-vs-production/develop/app.py#L33-L38) dùng `print()`. Log dễ chứa dữ liệu người dùng và credential, đồng thời khó lọc theo mức độ hoặc loại sự kiện.
4. **Thiếu endpoint kiểm tra liveness.** [Dòng 42–43](01-localhost-vs-production/develop/app.py#L42-L43) ghi chú về `/health` nhưng chưa khai báo route. Khi chạy thử, em nhận được `404 Not Found` từ endpoint này.
5. **Bind vào loopback và cố định cổng.** [Dòng 51–52](01-localhost-vs-production/develop/app.py#L51-L52) chọn `localhost:8000`. Trong container, bind vào loopback khiến kết nối từ bên ngoài container khó tới được app. Cổng cố định cũng có thể lệch với `PORT` do nền tảng cấp.
6. **Luôn bật reloader.** [Dòng 53](01-localhost-vs-production/develop/app.py#L53) đặt `reload=True`. Log lúc chạy xác nhận WatchFiles được bật. Cơ chế này theo dõi file và khởi động lại app khi có thay đổi, hữu ích lúc phát triển nhưng có thể làm gián đoạn request khi deploy.

### Exercise 1.2 — Chạy bản develop

Em chạy `python app.py` trong `01-localhost-vs-production/develop/`. Uvicorn khởi động tại `http://localhost:8000`.

```bash
curl -i -X POST 'http://localhost:8000/ask?question=Hello'
curl -i 'http://localhost:8000/health'
```

Kết quả thực tế của `POST /ask?question=Hello`:

```http
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Kết quả thực tế của `GET /health`:

```http
HTTP/1.1 404 Not Found
content-type: application/json

{"detail":"Not Found"}
```

Em dùng query string vì [handler bản develop](01-localhost-vs-production/develop/app.py#L29-L31) nhận `question` qua query. Trong lần chạy này, log server cũng in giá trị API key mẫu và toàn bộ câu hỏi.

### Exercise 1.3 — So sánh với bản production

Trong `01-localhost-vs-production/production/`, em chạy bản production với cấu hình local và dùng mock LLM.

```bash
HOST=127.0.0.1 PORT=8000 DEBUG=false ENVIRONMENT=development python app.py
```

| Lệnh kiểm tra | Kết quả thực tế |
| --- | --- |
| `GET /health` | `200 OK`, body có `"status":"ok"` và `"uptime_seconds":10.4`. |
| `GET /ready` | `200 OK`, body `{"ready":true}`. |
| `POST /ask` với JSON `{"question":"Hello"}` | `200 OK`, body có `question`, câu trả lời từ mock và `"model":"gpt-4o-mini"`. |

| Tiêu chí | Develop | Production | Vì sao quan trọng |
| --- | --- | --- | --- |
| Cấu hình | [Các giá trị host, port và reload cố định](01-localhost-vs-production/develop/app.py#L49-L54). | [`config.py` đọc `HOST`, `PORT` và `DEBUG` từ môi trường](01-localhost-vs-production/production/config.py#L14-L19). | Có thể dùng cùng một mã nguồn ở nhiều môi trường và cấu hình theo cổng nền tảng cấp. |
| Health và readiness | `GET /health` trả 404. | [`/health` kiểm tra liveness và `/ready` đọc trạng thái sẵn sàng](01-localhost-vs-production/production/app.py#L135-L161). Cả hai trả 200 sau khi app khởi động. | Liveness cho biết app còn phản hồi. Readiness giúp quyết định có nên chuyển traffic vào app. |
| Logging | [`print()` in câu hỏi, key và câu trả lời](01-localhost-vs-production/develop/app.py#L32-L38). | [Code ghi sự kiện và độ dài câu hỏi, câu trả lời bằng logger](01-localhost-vs-production/production/app.py#L110-L122). Output em thu được có warning về mock và access log của Uvicorn. | Các trường theo sự kiện hỗ trợ tìm kiếm và theo dõi request mà không cần ghi API key hay toàn văn câu hỏi. |
| Shutdown | App chưa khai báo bước dọn dẹp riêng. | [FastAPI lifespan đặt `is_ready = False` khi shutdown](01-localhost-vs-production/production/app.py#L39-L74). Nhận xét này dựa trên mã nguồn. | Lifecycle hook cho phép dọn tài nguyên khi app tắt. Graceful shutdown giúp các request đang xử lý có thời gian hoàn tất. |

## AI log

- **CP1:** Em hỏi Codex về thứ tự làm lab và cách thực hiện Exercise 1.1–1.3. Codex gợi ý dòng code cần đọc, chỉ ra cú pháp query string của bản develop và soạn phần trình bày từ output em cung cấp. Em tự chạy hai app trong terminal, dùng `curl` để kiểm tra mã HTTP và nội dung phản hồi, rồi gửi output thực tế làm bằng chứng.
