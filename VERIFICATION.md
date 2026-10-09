# Kiểm tra trước khi xuất bản

Ngày kiểm tra: **09/10/2026**, Windows, Python **3.11.9**, môi trường .venv mới được tạo từ requirements.txt.

## Kết quả

| Kiểm tra | Kết quả |
|---|---|
| Cài đủ thư viện từ requirements.txt | Đạt |
| pip check | No broken requirements found |
| py_compile năm file Python | Đạt |
| python -m unittest -v test_loop | 33/33 đạt |
| Tám tình huống offline A–H | Khớp bảng trong README |
| offline_demo.py --compare | Ngưỡng 5: max_steps/5 bước/5 call; ngưỡng 2: repeat_limit/3 bước/2 call |
| Khởi tạo ChatGoogleGenerativeAI và bind_tools bằng key giả | Đạt, không gọi mạng |
| CLI thiếu GOOGLE_API_KEY | Từ chối với mã thoát 2 |
| Đối chiếu năm file Python với nguồn demo trong bài | Khớp byte |

Log thực thi ở verification/test-results.txt, offline-output.txt, comparison-output.txt và pip-check.txt.

Phiên bản trực tiếp: langchain-core **1.6.7**, langchain-google-genai **4.4.0**, python-dotenv **1.2.4**. Phụ thuộc quan sát trong lần cài mới: google-genai **2.29.0**, pydantic **2.14.0**, langsmith **0.14.5**. requirements.txt ghim thư viện trực tiếp; các phụ thuộc gián tiếp có thể thay đổi ở lần cài khác.

## Phạm vi kiểm thử

Kiểm tra trả lời trực tiếp; nhiều tool và tool phụ thuộc; ghép kết quả đúng ID; ID thiếu/trùng/dùng lại; phản hồi rỗng/sai kiểu và tool call không phân tích được; API giả báo lỗi; lỗi tool; chia 0, số không hữu hạn và tràn số; nhóm vượt giới hạn; gọi lặp liên tiếp hoặc có thao tác khác chen giữa; cả nhóm bị chặn; sửa tham số; ngân sách bước cuối; counter tách giữa câu hỏi; trace giữ args; thay ngân sách demo E/G và từ chối cờ CLI mâu thuẫn.

Đã rà soát bài và mã theo tiêu chí tham số/môi trường, đồng bộ output, diễn đạt giới hạn, vòng đời, comment/giải thích, minh chứng, ngữ nghĩa ví dụ và năng lực mô hình. README hướng dẫn clone, cài venv, chạy offline và tạo .env cho API.

## Giới hạn xác minh

**Chưa gọi Gemini API thật** trong lần kiểm tra này. Demo dùng phản hồi chuẩn bị sẵn; các tool Python thực hiện thật. Không xác nhận quyền/quota hoặc chất lượng chọn tool và tổng hợp của Gemini. Các thiết lập mẫu được đối chiếu với [tài liệu model Google](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [khuyến nghị Gemini 3](https://ai.google.dev/gemini-api/docs/gemini-3) và [vòng lặp LangChain](https://docs.langchain.com/oss/python/langchain/models).

Giới hạn theo bước không ngắt tool đang chạy; khóa JSON chưa so sánh ngữ nghĩa. final chưa xác nhận đáp án đúng. Mẫu chưa có deadline tổng, bộ nhớ đa lượt, retry nghiệp vụ, timeout tool dài hoặc idempotency. Đây là mã thực hành cho hai tool tính toán cục bộ.
