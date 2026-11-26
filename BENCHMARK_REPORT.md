# Benchmark & Observability Report — Day 14

- **Họ tên:** Nguyễn Hữu An
- **Ngày chạy:** 26/11/2026
- **Môi trường CP7:** macOS 15.8.3 (arm64), Python 3.12.16, FastAPI/Uvicorn và mock LLM chạy qua loopback.
- **Môi trường CP8:** Docker Engine 29.9.3 trên cùng máy, 10 CPU và 7,75 GiB RAM cấp cho Docker. Mỗi replica agent giới hạn 0,5 CPU và 256 MiB, chạy một Uvicorn worker.

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

- [x] [Grafana khi đang có tải, với Golden Signals](screenshots/grafana-dashboard.png)
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [x] [Trace lỗi trong Jaeger có event `exception`](screenshots/jaeger-error-trace.png)
- [x] [Trang Alerts của Prometheus với hai alert cùng firing](screenshots/prometheus-alert-firing.png)

**Quan sát ở 30 users, ramp-up 5 users/s.** Lúc 23:29:03 (GMT+7), truy vấn cùng công thức với dashboard cho p95 **296,8 ms** và avg **249,7 ms**. Chênh lệch khoảng **47,1 ms** cho thấy một phần request mất thời gian hơn mức trung bình. Nginx chia tải gần đều cho hai replica đang chạy, **9,25** và **9,11** request/s. Input khoảng **1351 tokens/s**, output khoảng **718 tokens/s**. Prompt v2 gồm system prompt, câu hỏi và ngữ cảnh retrieval, nên có nhiều token input hơn token của câu trả lời. Gọi `GET /metrics` qua Nginx trả **404**, vì Nginx chặn route này và Prometheus scrape trực tiếp từng agent qua mạng Docker.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert firing | Từ lúc áp dụng cấu hình đến khi firing | Panel phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2`, slow rate mặc định 0,03 | `AgentHighErrorRate` | 83,4 giây | Error rate. Prometheus ghi 21,62% lúc firing. |
| B | `MOCK_SLOW_RATE=0.3`, error rate mặc định 0,01 | `AgentHighLatencyP95` | 151,0 giây | Latency p95. Prometheus ghi 1,921 giây lúc firing. |

Em giữ tải 30 users trong hai thí nghiệm và đọc trạng thái Prometheus mỗi giây. Alert A yêu cầu tỷ lệ HTTP 5xx vượt 5% liên tục trong 1 phút. Alert B yêu cầu p95 vượt 1 giây liên tục trong 2 phút. Thời gian trong bảng đo từ lúc áp dụng cấu hình, gồm cả lúc Compose tạo lại agent, Prometheus scrape đủ mẫu và điều kiện duy trì đủ lâu. Sau hai lượt riêng, em bật đồng thời hai cấu hình. Lúc **23:35:13 (GMT+7)**, Prometheus ghi nhận hai alert cùng firing, với error rate **20,19%** và p95 **1,889 giây**. `promtool test rules` báo `SUCCESS` cho bộ test có sẵn.

**Phát hiện suy giảm chất lượng khi chuyển sang v1.** v1 vẫn có thể trả HTTP 200 đúng hạn dù câu trả lời thiếu kiến thức. Em sẽ chạy eval định kỳ trên bộ câu chuẩn, theo dõi accuracy theo phiên bản và cảnh báo khi giảm dưới ngưỡng hoặc khi câu từng đạt bị regression. Quality gate trên PR giúp chặn thay đổi gây suy giảm trước lúc deploy.

### 4.3 Debug bằng trace

Trong mẫu log lúc kiểm tra stack, request thành công chậm nhất em tìm được có trace sau:

- `trace_id` **`5721614a352e3d7c9fb6cd3b8b9b3d39`**.
- Span HTTP `POST /ask` kéo dài **1723,29 ms**. Bên trong `agent.run`, bước `chat mock-llm-small` chiếm **1697,44 ms (98,50%)**, còn `agent.retrieve_context` mất **24,18 ms**.
- Dòng log `llm_call` cùng `trace_id` ghi thời gian mock LLM **1696,3 ms**. Số trong Jaeger đo cả span gọi LLM.

```json
{"ts":"2026-11-26T16:22:57.921076+00:00","level":"INFO","service":"observable-agent","instance":"9c2bc1a547bf","event":"llm_call","trace_id":"5721614a352e3d7c9fb6cd3b8b9b3d39","span_id":"928c58f54184e08c","request_id":"e7e84d2bbad1","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":0.000047,"llm_ms":1696.3}
```

Trace lỗi `58ac06f9ee1f1d71c28d34bad7e9b3ac` trả HTTP **503** sau **118,61 ms**. Span `chat mock-llm-small` có trạng thái ERROR và event `exception` thuộc loại `utils.mock_llm.LLMError`. Dòng log tương ứng:

```json
{"ts":"2026-11-26T16:22:47.729060+00:00","level":"INFO","service":"observable-agent","instance":"2e41fc07f4df","event":"llm_error","trace_id":"58ac06f9ee1f1d71c28d34bad7e9b3ac","span_id":"1bd264f95a183d60","request_id":"79618fcba021","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Mỗi lượt tăng 10 users/s đến 100 users, chạy 2 phút và dùng cùng cấu hình mock. Em kiểm tra số replica đang được Prometheus scrape trước khi bắt đầu. Locust chạy với `--no-deps` để Compose giữ số replica đã đặt và `--exit-code-on-error 0` để ghi nhận đầy đủ các lỗi mô phỏng trong CSV rồi tiếp tục lượt kế tiếp.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59,74 | 190 | 230 | 1700 | 78/7135 (1,09%) |
| 3 | 59,86 | 190 | 230 | 1700 | 79/7148 (1,11%) |

Các số lấy từ hàng `POST /ask` trong [CSV 1 instance](benchmark-results/scale_1_stats.csv) và [CSV 3 instance](benchmark-results/scale_3_stats.csv). Tăng replica từ 1 lên 3 làm RPS tăng khoảng **0,2%**, p95 và p99 bằng nhau ở độ phân giải của Locust. Tải có nhịp chờ 0,5–2 giây giữa các request, và trace cho thấy phần lớn thời gian của request chậm nằm ở LLM mock. Với tải và cấu hình này, thêm replica chưa tạo khác biệt đo được về độ trễ. Mỗi mức có một lượt đo, nên em chưa xác định được giới hạn công suất của agent.

---

## 6. Kết luận

1. p95 và p99 cho biết nhóm request chậm mà avg có thể che khuất. Trong CP7, khi `MOCK_SLOW_RATE` tăng từ 0 lên 0,03, p99 tăng từ 221,6 lên 1699,0 ms.
2. Metrics cho biết sự cố đang xảy ra ở mức hệ thống. Trace và log chung `trace_id` giúp em phân biệt thời gian retrieval với thời gian gọi LLM của một request cụ thể.
3. Eval bổ sung kiểm tra chất lượng cho các alert vận hành. v2 sau khi bổ sung kiến thức đạt 23/23 và giữ toàn bộ câu đã đạt trong baseline.

Nếu đưa agent lên production, em sẽ đo tỷ lệ lỗi ở Nginx theo mã HTTP để phát hiện lỗi gateway mà agent không ghi nhận. Em cũng sẽ chạy eval định kỳ trên bộ câu chuẩn để cảnh báo khi độ chính xác giảm.
