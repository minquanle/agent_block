# Agent Block — Giới hạn vòng lặp gọi công cụ

Mã thực hành cho bài **Phát hiện và dừng Agent khi gọi công cụ lặp lại** trong chuỗi **AI Guru x TiniX**.

Agent dùng calculator và count_words, giới hạn số lần gọi mô hình và chặn yêu cầu lặp theo tên tool cùng tham số JSON. Có tám demo offline và 33 kiểm thử để thử phần điều phối trước khi kết nối Gemini.

## 1. Lấy mã nguồn

Cần Python **3.11** và Git. Mở Terminal:

~~~bash
git clone https://github.com/minquanle/agent_block.git
cd agent_block
~~~

Bạn cũng có thể chọn **Code → Download ZIP** trên GitHub, giải nén rồi mở Terminal trong thư mục có requirements.txt. Các file Python nằm ngay ở thư mục gốc repo.

## 2. Tạo môi trường và cài thư viện

Windows PowerShell:

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
~~~

macOS/Linux:

~~~bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
~~~

Các lệnh dùng thẳng Python trong venv, nên không cần kích hoạt môi trường. Nếu bạn đã kích hoạt venv, có thể dùng python thay đường dẫn trên.

Thư viện trực tiếp được ghim: langchain-core 1.6.7, langchain-google-genai 4.4.0, python-dotenv 1.2.4.

## 3. Chạy thử offline

Không cần API key hoặc file .env.

Windows:

~~~powershell
.\.venv\Scripts\python.exe -m unittest -v test_loop
.\.venv\Scripts\python.exe offline_demo.py
.\.venv\Scripts\python.exe offline_demo.py --compare
~~~

macOS/Linux:

~~~bash
.venv/bin/python -m unittest -v test_loop
.venv/bin/python offline_demo.py
.venv/bin/python offline_demo.py --compare
~~~

Kết quả mong đợi: **33 test đạt**. Tám kịch bản:

| Kịch bản | Nội dung | Trạng thái | Bước | Call qua dispatcher |
|---|---|---|---:|---:|
| A | Trả lời trực tiếp | final | 1 | 0 |
| B | Một tool rồi trả lời | final | 2 | 1 |
| C | Hai tool trong cùng phản hồi | final | 2 | 2 |
| D | Đếm rồi nhân | final | 3 | 2 |
| E | Hết bước trước lượt tổng hợp | max_steps | 1 | 1 |
| F | Tool lỗi rồi giải thích | final | 2 | 1 |
| G | Cùng yêu cầu, ID khác nhau | repeat_limit | 3 | 2 |
| H | Sửa tham số sai của phép tính 1 / 2 | final | 3 | 2 |

Phản hồi mô hình được chuẩn bị sẵn, còn tool Python thực hiện phép tính thật. Output này kiểm tra vòng lặp; chưa chứng minh hành vi của Gemini.

Thử riêng kịch bản hoặc thay giới hạn:

~~~powershell
.\.venv\Scripts\python.exe offline_demo.py --scenario D --max-steps 2
.\.venv\Scripts\python.exe offline_demo.py --scenario D --max-steps 3
.\.venv\Scripts\python.exe offline_demo.py --scenario G --max-same-call 1
~~~

D với 2 bước trả max_steps, với 3 bước trả final. G với ngưỡng 1 dừng ở bước 2. Trên macOS/Linux, thay đường dẫn Python bằng .venv/bin/python.

So sánh chính sách:

~~~text
max_same_call=5: status=max_steps; steps=5; tool_calls=5
max_same_call=2: status=repeat_limit; steps=3; tool_calls=2
~~~

--compare dùng ngân sách cố định; không dùng cùng --scenario hoặc ghi đè ngân sách. E/G tạo đủ phản hồi theo ngân sách khi thay tham số.

## 4. Cấu hình và chạy Gemini

Tạo key tại [Google AI Studio](https://aistudio.google.com/apikey). Tài khoản cần có quyền truy cập model và quota.

Chỉ khi chưa có .env, sao chép file mẫu:

Windows:

~~~powershell
Copy-Item .env.example .env
~~~

macOS/Linux:

~~~bash
cp .env.example .env
~~~

Mở .env bằng trình soạn thảo, thay placeholder:

~~~dotenv
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
~~~

Nếu .env đã tồn tại, chỉnh file đó. Biến môi trường đang có được ưu tiên hơn .env. Model mẫu hỗ trợ Function Calling theo [tài liệu Google](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite); đối chiếu ngày 09/10/2026. Có thể đổi GEMINI_MODEL sang model hỗ trợ tool calling mà tài khoản của bạn được phép sử dụng.

Chạy Windows:

~~~powershell
.\.venv\Scripts\python.exe agent_loop.py "Dùng calculator tính 123 nhân 456." --max-steps 5 --max-same-call 2
~~~

Chạy macOS/Linux:

~~~bash
.venv/bin/python agent_loop.py "Dùng calculator tính 123 nhân 456." --max-steps 5 --max-same-call 2
~~~

CLI in kết quả từng tool, trạng thái, số bước, số call và câu trả lời. Kết quả phép tính là 56088; số bước và cách mô hình chọn tool có thể thay đổi. Kiểm tra log tool để biết mô hình có thực sự dùng công cụ.

## 5. Giới hạn và cấu trúc

| Thiết lập | Mặc định | Phạm vi | Nơi cấu hình |
|---|---:|---|---|
| max_steps | 5 | 1–20 | --max-steps hoặc run_agent |
| max_same_call | 2 | 1–5 | --max-same-call hoặc run_agent |
| max_calls_per_step | 4 | 1–8 | Tham số run_agent, không có cờ CLI |
| temperature | 1.0 | Cấu hình mẫu | agent_loop.py |
| timeout | 30 giây | Cho lời gọi mô hình | agent_loop.py |
| max_retries | 0 | Tắt retry cấu hình ở lớp tích hợp | agent_loop.py |

Mẫu giữ temperature=1.0 theo [khuyến nghị Gemini 3 của Google](https://ai.google.dev/gemini-api/docs/gemini-3); hạ thấp có thể gây lặp hoặc giảm chất lượng.

Một bước là một lần thử gọi mô hình, kể cả lỗi và lượt trả lời cuối. Bước cuối vẫn xử lý nhóm tool hợp lệ, sau đó dừng; không gọi thêm lượt tổng hợp ngoài ngân sách.

Khóa gọi lặp ghép tên tool với tham số JSON sắp xếp khóa và bỏ ID. Counter xét toàn lần chạy, gồm yêu cầu sai tên/tham số đã qua dispatcher. Lần thứ ba của cùng khóa bị chặn với ngưỡng 2; nếu một call vượt ngưỡng thì chặn cả nhóm. Nhóm quá lớn cũng bị chặn cả nhóm nhưng có thể tiếp tục ở bước sau. Tool chạy tuần tự.

Khóa chưa gộp 1 với 1.0, chuẩn hóa khoảng trắng hoặc so sánh ngữ nghĩa. Giới hạn này nhận diện yêu cầu lặp, chưa đánh giá mọi dạng thiếu tiến triển.

| File | Vai trò |
|---|---|
| tools.py | Hai tool, schema và registry |
| loop_core.py | RunResult, dispatcher, khóa gọi lặp và vòng lặp |
| agent_loop.py | CLI kết nối Gemini |
| offline_demo.py | Mô hình giả và tám tình huống |
| test_loop.py | 33 kiểm thử |
| requirements.txt | Phiên bản thư viện trực tiếp |
| .env.example | Mẫu cấu hình key/model |
| .gitignore | Loại key, venv và cache khỏi Git |
| VERIFICATION.md | Phạm vi và kết quả kiểm tra trước khi xuất bản |
| verification/ | Log test, demo, so sánh và kiểm tra thư viện |

Khi dùng trong chương trình khác, gọi run_agent với model đã bind_tools. RunResult giữ answer, status, steps, tool_calls, messages và trace. Trace giữ tên, args, ID, payload và thời gian. dispatched nghĩa là đã qua dispatcher; đọc payload.ok để biết tool thành công. final chỉ xác nhận có văn bản cuối, chưa xác nhận đáp án đúng.

CLI agent_loop.py trả mã thoát 0 khi final, 1 khi tác vụ dừng ở trạng thái khác, 2 khi cấu hình/khởi chạy lỗi. Demo offline minh họa trạng thái trong output; kết thúc bình thường của demo không có nghĩa mọi kịch bản đạt final.

## 6. Lỗi thường gặp và phạm vi sử dụng

- Thiếu thư viện: cài requirements bằng đúng Python trong .venv.
- Thiếu key: đặt .env cạnh agent_loop.py hoặc thiết lập GOOGLE_API_KEY trong môi trường.
- 401/403 hoặc model không truy cập được: kiểm tra key và quyền model; đổi model không sửa key sai.
- 429: kiểm tra quota và gửi lại khi được phép; mẫu không tự retry nghiệp vụ.
- protocol_error: kiểm tra ID, invalid_tool_calls và JSON hữu hạn. Lịch sử dở dang cần sửa giao thức trước khi tái sử dụng.
- repeat_limit: xem tên/args trong RunResult.trace, làm rõ yêu cầu và chỉ tăng ngưỡng khi có lý do nghiệp vụ.
- max_steps: chừa lượt tổng hợp; kiểm tra Agent có đổi tham số vô ích hay không.

calculator dùng float, chưa có quy tắc tiền tệ/làm tròn kế toán. count_words đếm các đơn vị cách trắng, không phải số từ tiếng Việt theo ngôn ngữ học; đầu vào tối đa 4000 ký tự.

Messages và counter được tạo mới cho mỗi câu hỏi. Mẫu chưa có bộ nhớ nhiều lượt, deadline toàn tác vụ, timeout tool dài, retry nghiệp vụ hoặc idempotency. Giới hạn bước không ngắt hàm đang chạy. Ngưỡng 2 vẫn cho phép cùng yêu cầu chạy hai lần; tool thay đổi dữ liệu cần cơ chế duyệt và chống thực hiện trùng riêng.

Khi chạy API, câu hỏi, mô tả tool và kết quả được gửi tới nhà cung cấp. Dùng dữ liệu mẫu, giữ key trong .env/môi trường và kiểm tra log trước khi chia sẻ. Repo chỉ chứa cấu hình mẫu.

Chưa gọi Gemini API thật trong lần kiểm tra trước khi xuất bản; xem [VERIFICATION.md](VERIFICATION.md).
