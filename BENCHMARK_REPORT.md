# Benchmark & Observability Report — Day 14

- **Họ tên:** Nguyễn Hữu An
- **Ngày chạy:** 26/11/2026
- **Môi trường CP7:** macOS 15.8.3 (arm64), Python 3.12.16, FastAPI/Uvicorn và mock LLM chạy qua loopback.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của lab. Theo dõi thời gian phản hồi của phần lớn request thành công, kể cả nhóm chậm hơn mức điển hình. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của lab, tương đương ít nhất 98% request trả HTTP 200 trong lượt đo. |
| Accuracy trên golden dataset | ≥ 100% | Gate cuối của CP7 yêu cầu v2 đạt cả 23 câu và giữ các câu đã đạt ở baseline. |

### 1.1 Metrics của agent (Exercise 7.1)

Sau một lần gọi `/ask`, `/metrics` xuất `http_requests_total` (Counter đếm request), `agent_in_flight_requests` (Gauge đếm request đang xử lý) và `http_request_duration_seconds` (Histogram độ trễ).

Histogram `agent_question_length_chars` ghi một mẫu độ dài cho mỗi lần vào handler `/ask`. Trên agent vừa khởi động, giá trị `agent_question_length_chars_count` là `1.0` sau request thử. Middleware dùng mẫu route như `/ask` và gộp URL không khớp vào `unmatched`. Nếu dùng URL thực làm label, mỗi đường dẫn lạ có thể tạo một time series riêng, làm Prometheus tốn bộ nhớ khi số đường dẫn tăng.

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.17 | 191.9 | 221.1 | 1686.5 | 0.00% | PASS |
| 10 | 39.10 | 188.4 | 220.3 | 1687.9 | 0.00% | PASS |
| 50 | 118.82 | 196.5 | 234.5 | 1703.8 | 0.00% | PASS |
| 100 | 55.37 | 398.0 | 3323.6 | 3610.7 | 0.00% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Em dùng bốn lượt đo đã lưu, mỗi lượt 300 request. RPS tăng từ 4.17 tại concurrency 1 lên 118.82 tại 50, rồi giảm còn 55.37 tại 100. Tại 100, p95 lên 3323.6 ms và làm lượt đo trượt SLO dù cả 300 request trả HTTP 200. Kết quả phù hợp với hiện tượng request phải chờ lâu hơn khi tải đồng thời tăng. Mỗi mức có một lượt đo nên chưa xác định được nghẽn ở client hay server.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 186.1 | 215.5 | 221.6 |
| 0.03 (mặc định) | 229.8 | 220.5 | 1699.0 |
| 0.1 | 389.9 | 1691.0 | 1717.9 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

Mỗi lượt giữ 300 request, concurrency 20 và `MOCK_ERROR_RATE=0` để quan sát riêng ảnh hưởng của request chậm. Ở mức 0.03, p99 tăng từ 221.6 lên 1699.0 ms, trong khi avg chỉ tăng từ 186.1 lên 229.8 ms và p95 vẫn ở 220.5 ms. Ở mức 0.1, p95 lên 1691.0 ms và vượt SLO dù avg vẫn là 389.9 ms. Percentile cho thấy nhóm request chậm mà giá trị trung bình dễ che khuất.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.00% (23/23) |
| Avg tokens / câu | 57.0 | 108.8 | 111.7 |
| Tổng cost (USD) | 0.000402 | 0.000758 | 0.000774 |
| Cost / câu đúng (USD) | 0.00040215 | 0.00003607 | 0.00003364 |
| Quality gate | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%) | PASS (ngưỡng 100%) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung tài liệu phân biệt JWT có chữ ký và thời hạn với API key được quản lý ở máy chủ. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung tài liệu về cách Kubernetes HPA điều chỉnh số pod theo CPU, memory hoặc custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Eval dùng cùng 23 câu và đặt `MOCK_ERROR_RATE=0` cho cả ba lượt. Từ v1 sang v2, retrieval tăng tokens trung bình từ 57.0 lên 108.8 và p95 từ 190.5 lên 225.6 ms. Accuracy tăng từ 1/23 lên 21/23, nên chi phí trên mỗi câu đúng giảm dù tổng chi phí tăng. Sau khi bổ sung hai tài liệu, v2 đạt 23/23, sửa đúng hai câu còn thiếu và có 0 regression so với baseline v2. Tổng chi phí tăng từ 0.000758 lên 0.000774 USD, còn chi phí mỗi câu đúng giảm còn 0.00003364 USD. p95 lượt cuối là 214.5 ms. Ba lượt eval đều có 23 câu và mock có jitter, nên mức chênh p95 giữa các lượt chỉ có ý nghĩa mô tả.

### 3.1 Quality gate trong CI

Job CI khởi động v2, đợi `/health` trả lời rồi chạy `eval/run_eval.py` với `--min-accuracy 0.85` theo Exercise 7.3. Có thể truyền `--baseline` để phát hiện câu từ đạt chuyển sang không đạt. Script thoát với mã `1` khi dưới ngưỡng hoặc có regression so với baseline, làm job thất bại. Nếu job là required check của nhánh đích, PR phải vượt gate mới được merge. Lượt nộp `eval_v2_fixed.json` dùng ngưỡng `1.0` và baseline `eval_v2.json`.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
