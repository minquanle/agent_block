# Agent gọi công cụ với Gemini API

Bài **Phát hiện và dừng Agent khi gọi công cụ lặp lại**, chuỗi AI Guru x TiniX. Chạy Gemini Developer API thật với **gemini-3.5-flash-lite**, hai tool Python và ba giới hạn: 5 bước, 4 call mỗi bước, 2 lần cùng tên tool và tham số. Model được cố định trong mã và cấu hình để khớp các kịch bản đã kiểm tra.

## Thiết lập

Cần Python 3.11, Internet, API key và project có quyền dùng model, còn quota. Tạo key tại [Google AI Studio](https://aistudio.google.com/apikey), xem quota của project trước khi chạy. Các lượt API có thể phát sinh chi phí tùy gói.

PowerShell:

~~~powershell
git clone https://github.com/minquanle/agent_block.git
cd agent_block
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
if (!(Test-Path .env)) { Copy-Item .env.example .env }
~~~

Nếu không kích hoạt được venv, dùng `./.venv/Scripts/python.exe` thay cho `python`. Trên macOS/Linux:

~~~bash
git clone https://github.com/minquanle/agent_block.git
cd agent_block
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
test -f .env || cp .env.example .env
~~~

Mở `.env`, thay placeholder `GOOGLE_API_KEY` bằng khóa của bạn; giữ `GEMINI_MODEL=gemini-3.5-flash-lite`. `GEMINI_REQUEST_INTERVAL=10` giãn thời điểm bắt đầu request trong cùng tiến trình; không cấp thêm quota ngày hoặc giới hạn các tiến trình khác. `.env` được Git bỏ qua; không chia sẻ file này. Biến môi trường có sẵn được ưu tiên hơn `.env`.

## Chạy

~~~powershell
python agent_loop.py "Dùng calculator tính 123 nhân 456."
python gemini_demo.py --scenario B --output my_run.json
python gemini_demo.py --all --output my_suite.json
python gemini_demo.py --compare --output my_comparison.json
~~~

Mọi lệnh trên gọi API thật. Agent dùng AUTO. E/F/H buộc chọn một tool ở request đầu, sau đó AUTO; G và so sánh dùng ANY buộc `count_words` ở mọi request. Các tình huống lỗi/lặp được tạo có chủ đích bằng prompt và cấu hình tool; Gemini vẫn sinh lời gọi và tham số.

| Kịch bản | Nội dung | Kết quả lần chạy được lưu: trạng thái / bước / call |
| --- | --- | --- |
| A | Chào hỏi, không tool | final / 1 / 0 |
| B | Nhân 123 với 456 | final / 2 / 1; 56088 |
| C | Nhân và đếm độc lập | final / 2 / 2; 56088 và 4 |
| D | Đếm rồi nhân số đếm với 25000 | final / 3 / 2; 100000 |
| E | Chỉ một bước | max_steps / 1 / 1 |
| F | Thử 1 chia 0 rồi giải thích | final / 2 / 1; invalid_arguments |
| G | Lặp cùng câu, ngưỡng 2 | repeat_limit / 3 / 2; call thứ ba không thực thi |
| H | Thử chia 0 rồi tính 1 chia 2 | final / 3 / 2; 0.5 |

`api_results.json` ghi tám kịch bản API đạt ngày **09/10/2026**, gồm trace, phiên bản model, metadata token và các điều kiện kiểm tra. `api_comparison.json` ghi hai lần gọi API đạt: ngưỡng 5 → 5 bước/5 call/max_steps; ngưỡng 2 → 3 bước/2 call/repeat_limit. Đọc `tested_at_utc` của từng báo cáo để biết thời điểm chạy, không coi file mẫu là kết quả chạy mới.

Bộ kiểm tra xác nhận trạng thái, payload số, thứ tự phụ thuộc, lỗi và call bị chặn. Văn bản/số bước có thể thay đổi khi chạy lại; điều kiện không đạt khiến demo trả mã 1, không tạo kết quả thay thế. `--output` lưu báo cáo của lượt chạy đó; nên chọn tên mới. Lỗi khởi tạo trả mã 2 trước khi ghi báo cáo, vì vậy luôn kiểm tra mã thoát và timestamp, tránh đọc nhầm file cũ.

`--all` có tối đa 36 lần gọi model với cấu hình hiện tại; `--compare` tối đa 10. Lần đã ghi dùng lần lượt 17 và 8 lượt. SDK cấu hình retry 0, timeout 30 giây, đầu ra tối đa 1024 token và thinking minimal; không đặt temperature vì model dùng lấy mẫu cố định. Timeout SDK không phải deadline toàn tác vụ. Bộ mã không có tool mạng; calculator và count_words chạy trên máy, còn câu hỏi/mô tả tool/kết quả được gửi tới Gemini.

## Bốn file Python

- `tools.py`: calculator hữu hạn và đếm đơn vị theo khoảng trắng; không dùng eval.
- `loop_core.py`: dispatcher, khóa gọi lặp, ngân sách và ghép ToolMessage theo ID; giữ nguyên AIMessage.
- `agent_loop.py`: cấu hình Gemini, giãn request, in trace và CLI.
- `gemini_demo.py`: tám kịch bản, so sánh, kiểm tra kết quả và xuất JSON.

CLI Agent trả 0 khi final, 1 khi dừng/lỗi model, 2 khi lỗi khởi tạo. Demo trả 0 khi các điều kiện kiểm tra đạt, kể cả E/G cố ý dừng. `tool_calls` đếm call đưa qua dispatcher, gồm call sai tham số; call bị chặn không tăng bộ đếm. Hai tool cùng nhóm được chạy tuần tự. `final` xác nhận có văn bản, chưa xác nhận nội dung đúng.

## Khắc phục lỗi

- Thiếu key hoặc model cấu hình khác: kiểm tra `.env` và biến môi trường đang ưu tiên nó; giữ đúng model đã kiểm.
- 401/403/404: kiểm tra key, project và quyền model. Đổi model không sửa khóa sai hoặc quyền bị thiếu.
- 429: xem RPM/TPM/RPD theo **project**; đổi key cùng project không cấp quota mới. Khoảng chờ không sửa hết quota ngày. Xem [hạn mức Google](https://ai.google.dev/gemini-api/docs/rate-limits).
- Timeout/lỗi API: Agent trả model_error, trace chỉ giữ loại ngoại lệ để tránh lộ thông báo nhạy cảm. Kiểm tra trạng thái dịch vụ/quota trong AI Studio và chạy lại khi đã xử lý nguyên nhân.
- repeat_limit/max_steps: xem trace trước khi tăng giới hạn. Khóa JSON chưa so sánh ngữ nghĩa; tool đọc dữ liệu thay đổi cần chính sách gọi lại riêng.

Môi trường đã kiểm: Windows, Python 3.11, langchain-core 1.6.7, langchain-google-genai 4.4.0, python-dotenv 1.2.4; pip check đạt. Tám demo, so sánh và CLI đều đã gọi Gemini API; hướng dẫn macOS/Linux chưa chạy trên máy tương ứng.
