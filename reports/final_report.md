# Báo cáo độ tin cậy của LLM Gateway

## 1. Kiến trúc

Gateway kiểm tra cache trước khi gọi mô hình. Nếu không có kết quả phù hợp, yêu cầu đi qua circuit breaker của từng provider theo thứ tự cấu hình. Circuit đang `OPEN` sẽ từ chối nhanh, nhờ đó hệ thống không tiếp tục gọi một provider đang lỗi. Khi cả hai provider đều không dùng được, gateway trả về thông báo suy giảm dịch vụ thay vì để yêu cầu treo hoặc phát sinh retry liên tục.

```text
Người dùng
    |
    v
[ReliabilityGateway] -> [Cache] -> HIT -> Trả kết quả đã lưu
    |                    |
    |                    v MISS
    v
[Circuit breaker: primary] -> [Provider primary]
    | OPEN hoặc lỗi
    v
[Circuit breaker: backup]  -> [Provider backup]
    | OPEN hoặc lỗi
    v
[Static fallback]
```

Mỗi circuit breaker có ba trạng thái `CLOSED`, `OPEN` và `HALF_OPEN`. Sau thời gian chờ, `HALF_OPEN` cho phép một probe. Probe thành công đưa circuit về `CLOSED`; probe thất bại mở circuit ngay lập tức.

## 2. Cấu hình thí nghiệm

| Tham số | Giá trị | Lý do sử dụng |
|---|---:|---|
| `primary.fail_rate` | 0.25 | Mô phỏng provider chính có lỗi để kiểm tra chuyển tuyến. |
| `primary.base_latency_ms` | 180 | Provider chính là tuyến nhanh hơn. |
| `primary.cost_per_1k_tokens` | 0.01 USD | Cho phép đo chi phí của tuyến chính. |
| `backup.fail_rate` | 0.05 | Tuyến dự phòng ổn định hơn tuyến chính trong cấu hình mặc định. |
| `backup.base_latency_ms` | 260 | Mô phỏng phần độ trễ phải trả khi fallback. |
| `backup.cost_per_1k_tokens` | 0.006 USD | Tuyến dự phòng rẻ hơn nhưng chậm hơn. |
| `failure_threshold` | 3 | Mở circuit sau ba lỗi liên tiếp, tránh phản ứng với một lỗi đơn lẻ. |
| `reset_timeout_seconds` | 2 | Chờ hai giây trước khi gửi probe phục hồi. |
| `success_threshold` | 1 | Một probe thành công đủ để đóng circuit. |
| `cache.enabled` | `true` | Bật tái sử dụng câu trả lời trong thí nghiệm chính. |
| `cache.backend` | `memory` | Đây là backend mặc định; Redis được kiểm tra riêng ở Phase 5. |
| `cache.ttl_seconds` | 300 | Giới hạn dữ liệu cache trong năm phút. |
| `similarity_threshold` | 0.92 | Ngưỡng cao giảm khả năng dùng nhầm câu trả lời gần giống. |
| `redis_url` | `redis://localhost:6379/0` | Kết nối Redis do Docker Compose cung cấp. |
| `load_test.requests` | 100 mỗi scenario | Ba scenario tạo tổng cộng 300 yêu cầu. |
| `load_test.random_seed` | 20260827 | Cố định lựa chọn query, jitter và lỗi mô phỏng giữa các lần chạy. |
| `primary_timeout_100` | `primary: 1.0` | Buộc provider chính lỗi hoàn toàn. |
| `primary_flaky_50` | `primary: 0.5` | Kiểm tra circuit khi provider chính lỗi không liên tục. |
| `all_healthy` | `primary: 0.0`, `backup: 0.0` | Tạo baseline không có lỗi provider. |

Cache bỏ qua truy vấn chứa dữ liệu nhạy cảm như password, account balance, credit card hoặc SSN. Bộ kiểm tra false hit cũng từ chối ghép câu hỏi có số bốn chữ số khác nhau, ví dụ chính sách năm 2024 và năm 2026.

## 3. SLO

<!-- SLO_TABLE:START -->
| SLI | Mục tiêu | Kết quả | Đạt? |
|---|---:|---:|---|
| Availability | >= 99% | 99.00% | Có |
| Latency P95 | < 2500 ms | 317.32 ms | Có |
| Fallback success rate | >= 95% | 95.08% | Có |
| Cache hit rate | >= 10% | 59.33% | Có |
| Recovery time | < 5000 ms | 2233.90 ms | Có |
<!-- SLO_TABLE:END -->

Cả năm chỉ số tổng hợp đều đạt mục tiêu. Availability vừa chạm ngưỡng 99%, vì vậy kết quả này không có nhiều biên an toàn nếu tải hoặc tỷ lệ lỗi tăng.

## 4. Kết quả tổng hợp

Dữ liệu dưới đây lấy từ `reports/metrics.json` của lần chạy 300 yêu cầu.

<!-- METRICS_TABLE:START -->
| Chỉ số | Giá trị |
|---|---:|
| Tổng số yêu cầu | 300 |
| Availability | 0.9900 |
| Error rate | 0.0100 |
| Latency P50 | 240.13 ms |
| Latency P95 | 317.32 ms |
| Latency P99 | 320.36 ms |
| Fallback success rate | 0.9508 |
| Cache hit rate | 0.5933 |
| Circuit open count | 7 |
| Recovery time | 2233.90 ms |
| Estimated cost | 0.057436 USD |
| Estimated cost saved | 0.178000 USD |
<!-- METRICS_TABLE:END -->

`RunMetrics.write_csv()` xuất cùng nhóm chỉ số thành một dòng CSV và chuyển trạng thái scenario thành các cột có dạng `scenario_<name>`.

## 5. So sánh cache

Hai lượt thử dùng 100 yêu cầu, seed `20260827`, provider không lỗi và cùng tập 20 truy vấn. Biến thay đổi duy nhất trong cấu hình là `cache.enabled`.

| Chỉ số | Không cache | Có cache | Chênh lệch |
|---|---:|---:|---:|
| Latency P50 | 217.25 ms | 216.52 ms | -0.73 ms |
| Latency P95 | 237.60 ms | 238.58 ms | +0.98 ms |
| Estimated cost | 0.061840 USD | 0.024580 USD | -0.037260 USD |
| Cache hit rate | 0% | 63% | +63 điểm phần trăm |

Cache giảm khoảng 60.25% chi phí ước tính trong lượt thử này. Hai percentile độ trễ gần như không đổi vì `RunMetrics` chỉ lưu latency lớn hơn 0; các cache hit có latency ghi nhận bằng 0 nên không tham gia phép tính percentile. Vì vậy bảng trên phản ánh độ trễ của các lượt gọi provider, chưa phải phân phối end-to-end của toàn bộ 100 yêu cầu. Giá trị `estimated_cost_saved` cũng là ước lượng cố định 0.001 USD cho mỗi cache hit, không phải hiệu giữa hai hóa đơn thực tế.

## 6. Redis shared cache

Cache trong bộ nhớ thuộc về một tiến trình. Hai gateway chạy ở hai container khác nhau sẽ không nhìn thấy entry của nhau, và dữ liệu mất khi tiến trình khởi động lại. `SharedRedisCache` lưu query và response trong Redis Hash, đặt TTL bằng `EXPIRE`, rồi dùng chung prefix cho các instance.

Sáu bài kiểm thử Redis đều đạt, gồm kết nối, exact match, TTL, chia sẻ giữa hai instance, privacy guard và false-hit guard. Kiểm tra trực tiếp cho kết quả:

```text
INSTANCE_2_GET= ('visible from instance 2', 1.0)
KEYS= ['rl:report:f9b2bf7b0364']
TTL= 300
```

Lệnh CLI và kết quả:

```bash
docker compose exec -T redis redis-cli KEYS "rl:report:*"
rl:report:f9b2bf7b0364
```

Một lượt chaos nhỏ dùng Redis xử lý 20 yêu cầu với availability 100%, cache hit rate 75% và estimated cost saved 0.015 USD.

## 7. Các scenario lỗi

Các số liệu chi tiết bên dưới được chạy riêng với seed cố định. Mỗi scenario có 100 yêu cầu.

<!-- SCENARIO_STATUS:START -->
| Trạng thái tổng hợp | Kết quả |
|---|---|
| `primary_timeout_100` | fail |
| `primary_flaky_50` | pass |
| `all_healthy` | pass |
<!-- SCENARIO_STATUS:END -->

| Scenario | Kỳ vọng | Quan sát | Đánh giá |
|---|---|---|---|
| `primary_timeout_100` | Cache hoặc backup phục vụ yêu cầu; circuit chính mở. | Availability 98%, cache hit 66%, fallback success 94.12%, circuit mở 5 lần. Không có lần phục hồi vì primary luôn lỗi. | Fail vì thấp hơn ngưỡng fallback 95%. |
| `primary_flaky_50` | Có cả primary và fallback; circuit mở rồi phục hồi. | Availability 98%, cache hit 58%, fallback success 90.48%, circuit mở 1 lần và phục hồi sau 2247.70 ms. | Pass theo các ngưỡng đã cấu hình. |
| `all_healthy` | Primary xử lý yêu cầu và circuit không mở. | Availability 100%, error rate 0%, cache hit 63%, circuit không mở. | Pass. |
| `redis_shared_cache` | Các yêu cầu lặp lại đọc được dữ liệu từ Redis. | 20/20 yêu cầu thành công, cache hit 75%, circuit không mở. | Pass. |

Lần chạy tổng hợp ghi `primary_timeout_100` là `fail`, còn hai scenario kia là `pass`. Trạng thái được tính từ các ngưỡng riêng trong `configs/default.yaml`, gồm availability, error rate, fallback success, số lần mở circuit và yêu cầu phục hồi.

## 8. Phân tích điểm yếu còn lại

Chaos runner hiện gửi yêu cầu tuần tự. Cách chạy này kiểm tra được fallback và thời gian phục hồi, nhưng chưa cho thấy điều gì xảy ra khi nhiều request cùng đến lúc circuit chuyển sang `HALF_OPEN`. `allow_request()` đang cho phép mọi request trong trạng thái này đi qua, nên một đợt tải đồng thời có thể tạo nhiều probe thay vì đúng một probe.

Trước khi dùng trong production, circuit breaker cần khóa hoặc semaphore theo provider để chỉ một request giữ quyền probe. Các request còn lại phải fail fast hoặc chờ kết quả probe. Bài kiểm thử tải nên dùng nhiều worker đồng thời và xác nhận số cuộc gọi provider trong `HALF_OPEN` không vượt quá một.

## 9. Công việc tiếp theo

1. Tách bộ sinh query khỏi bộ sinh lỗi provider để các lần so sánh dùng đúng cùng một chuỗi yêu cầu và failure pattern.
2. Ghi latency bằng 0 của cache hit hoặc bổ sung một histogram end-to-end riêng, thay vì chỉ đo các lượt đã gọi provider.
3. Chia sẻ trạng thái circuit breaker hoặc ít nhất đồng bộ trạng thái lỗi giữa các gateway instance, thay vì để mỗi tiến trình tự học lại tình trạng provider.

Kết quả kiểm thử cuối: 38 test passed và 7 assignment marker XPASS khi Redis đang chạy. Báo cáo máy đọc được lưu tại `reports/test-results.xml`.
