# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (run ID sẽ cập nhật sau khi sinh report ở M4) |
| Triệu chứng | Grader Lab 8 báo FAIL (`status resolved != denied`); ledger ghi `refund_vnd: 20000`, `refund_count: 1` và reply báo "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202" trong khi nhãn kỳ vọng `status: denied`, `refund_vnd: 0` |
| Bước sai đầu tiên | Event 3: `model_override` payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 (handoff) khởi tạo đúng hợp đồng; Event 2 (investigator) gọi `lookup_order` tra cứu DB trả về kết quả chuẩn xác: `status: delivered, delay_days: 2`. Toàn bộ dữ liệu trước Event 3 đều đúng; Event 3 là bước đầu tiên tự ý đè `delay_days` 2 của DB bằng 5 ngày khách khai trên ticket (Event 4 quote ra 20.000đ `entitled`) |
| Failure mode | `FM-03` (ticket_trust — tin ticket hơn DB) |
| Đối chứng | Cùng claim@seed trên shape `fixed`: sau Event 2 (investigator) không có Event `model_override`; Event 3 là `quote` ra `amount_vnd: 0` (`no_entitlement`); Event 4 `reply` từ chối hoàn tiền; ledger ghi `refund_vnd: 0, status: denied` (PASS) |
| Regression test | `test_c002_seeded_regression_fails_and_fixed_passes` trong `src/tests/test_lab9_trace_case.py`; kiểm tra `lab8_pass` và `status == 'denied'`. Đã xác nhận fail trên `seeded_regression` và pass trên `fixed` |
| Chưa chắc chắn | Trace chỉ ghi nhận hành vi đè giá trị của agent qua event `model_override`, không thể hiện được cơ chế suy luận bên trong prompt dẫn đến việc tin khách hơn DB |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
