
# ChatBot Web Full

## Cấu trúc
- app.py
- templates/login.html
- templates/index.html
- templates/admin.html
- static/nhac.mp3 (bạn tự thêm)

## Chạy
1. Cài Flask: `pip install flask`
2. Đặt project vào một thư mục riêng
3. Chạy: `python app.py`
4. Mở: `http://127.0.0.1:5000`

## Dữ liệu
Các file text vẫn dùng ở:
- /storage/emulated/0/user_data.txt
- /storage/emulated/0/public_data.txt
- /storage/emulated/0/private_data.txt
- /storage/emulated/0/messages.txt
- /storage/emulated/0/groups.txt
- /storage/emulated/0/group_members.txt
- /storage/emulated/0/report.txt

## Lưu ý
- Đổi `ADMIN` trong app.py nếu muốn.
- Nếu muốn public/private file khác, sửa phần `DATA_DIR`.
