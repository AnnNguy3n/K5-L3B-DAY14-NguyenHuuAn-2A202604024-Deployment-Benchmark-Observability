# Thông tin triển khai CP6

## URL public và nền tảng

- **URL public** `https://day14-agent-xo0y.onrender.com`. [Kiểm tra /health](https://day14-agent-xo0y.onrender.com/health)
- **Nền tảng** Render Blueprint, region Singapore.
- **Dịch vụ** `day14-agent` chạy Docker từ `06-lab-complete/`. `day14-redis` là Render Key Value, kết nối với agent qua mạng nội bộ.
- **Commit đã deploy** `2a962e8`. Cấu hình nằm trong [render.yaml](06-lab-complete/render.yaml).

## Lệnh kiểm tra

Đặt `AGENT_API_KEY` trong phiên terminal bằng giá trị đã cấu hình trên Render. Các lệnh chỉ in mã HTTP.

```bash
BASE='https://day14-agent-xo0y.onrender.com'

# Process đang chạy → 200
curl -sS --max-time 90 -o /dev/null -w '%{http_code}\n' "$BASE/health"

# Agent kết nối được Redis → 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

# Thiếu API key → 401
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST "$BASE/ask" -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'

# Có API key hợp lệ → 200
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST "$BASE/ask" -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

Kết quả ghi lúc **22:00:41 (GMT+7), ngày 26/11/2026** lần lượt là **200 / 200 / 401 / 200**. [Ảnh kết quả](screenshots/test.png)

## Biến môi trường

| Biến | Cách cấu hình |
| --- | --- |
| `ENVIRONMENT` | Blueprint đặt thành `production`. |
| `PORT` | Render cấp, Dockerfile dùng để chạy Uvicorn. |
| `REDIS_URL` | Blueprint tham chiếu chuỗi kết nối nội bộ của `day14-redis`. |
| `AGENT_API_KEY` | Nhập trên Render, với `sync: false` trong Blueprint. |

## Ảnh minh chứng

- [Dashboard của Blueprint và hai dịch vụ](screenshots/dashboard.png)
- [Agent ở trạng thái Live và URL public](screenshots/running.png)
- [Kết quả bốn phép thử HTTP](screenshots/test.png)
