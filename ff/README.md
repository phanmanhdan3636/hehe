# FF Hub

Web cộng đồng Free Fire xây bằng Flask + SQLite.

## Chạy
```bash
pip install -r requirements.txt
python app.py
```

Mở: `http://127.0.0.1:5000`

## Tài khoản mẫu
- admin / admin123
- mod / mod123
- member / member123

## Tính năng
- Đăng ký / đăng nhập
- Hash mật khẩu
- Trang chỉnh hồ sơ riêng: avatar, tên hiển thị, bio
- Admin tạo thêm member / mod
- Admin sửa tài khoản riêng: username, tên, avatar, vai trò, mật khẩu
- Chỉnh thông số giải đấu
- Đăng bài, sửa bài, xóa bài
- Upload ảnh cho bài viết / avatar
- Like, bình luận
- Duyệt bài member
- Giftcode
- API giải đấu: `/api/tournament`
