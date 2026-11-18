# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 10`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có (PASS) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không (FAIL) | loại |

## ≥5 case audit thủ công (chi tiết 10 ca bất đồng của tone)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | H-081 | FAIL | PASS | Judge | Người đọc nhầm ticket; đơn O-107 từ chối là đúng chính sách -> Sửa nhãn người |
| 2 | H-042 | FAIL | PASS | Người | Bỏ yêu cầu bắt buộc "xin lỗi" khi đã giải quyết hoàn tiền đúng; rubric judge quá khắt khe |
| 3 | H-051 | FAIL | PASS | Người | Cho phép dùng từ "refund" (thuật ngữ phổ biến trong CS LogiX) |
| 4 | H-088 | FAIL | PASS | Có tranh cãi | Cần quy định rõ lỗi gõ nhẹ lặp từ ("Dạ, dạ") có bị coi là vi phạm giọng điệu hay không |
| 5 | H-008 | PASS | FAIL | Người | Thêm vào rubric: xưng hô "em" + "nha" là quá suồng sã, thiếu chuẩn mực CS |
| 6 | H-017 | PASS | FAIL | Người | Thêm vào rubric: không xưng "bạn" với khách lớn tuổi / khách khiếu nại |
| 7 | H-029 | PASS | FAIL | Người | Thêm vào rubric: cấm câu mệnh lệnh kiểu "không cần nhắn thêm" gây ức chế cho khách |
| 8 | H-063 | PASS | FAIL | Người | Thêm vào rubric: không hứa hẹn "sẽ hoàn thêm" vượt thẩm quyền và sai lệch kết quả hệ thống |
| 9 | H-070 | PASS | FAIL | Người | Thêm vào rubric: nghiêm cấm chèn emoji cợt nhả (😂😂) trong văn cảnh xử lý sự cố khiếu nại |
| 10 | H-094 | PASS | FAIL | Người | Thêm vào rubric: yêu cầu tiếng Việt chuẩn có dấu, không dùng teencode hay không dấu |

## Kết luận
- **Tiêu chí bị loại:** Loại hoàn toàn `helpful` khỏi release gate.
  - Ma trận nhầm lẫn của `helpful`: `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`, Precision = 1.0 nhưng Recall chỉ đạt 0.30 (bỏ lọt 21/30 lỗi thật).
  - Phân tích 21 ca lỗi bị bỏ lọt: có **18 ca là sai lệch số tiền** giữa phát ngôn và thực tế (FM-08) mà judge bằng prompt/LLM không đối chiếu được với ledger, và 3 ca sai xưng hô. Điều này khẳng định nguyên tắc cốt lõi: **tiền và phê duyệt bắt buộc phải chấm bằng code assertion**, không dùng LLM judge làm chốt chặn tài chính.
- **Tiêu chí được giữ:** Giữ lại `tone_ok` làm gate giọng điệu vì đạt mọi chỉ số sàn (κ = 0.757 ≥ 0.6, P = 0.857 ≥ 0.8, R = 0.800 ≥ 0.7).
- **Rủi ro còn lại:** Judge mới chỉ được hiệu chuẩn trên tập dữ liệu replay tĩnh đã công khai (100 mẫu), chưa được kiểm tra trên tập held-out mới từ người dùng thật trong môi trường production.
