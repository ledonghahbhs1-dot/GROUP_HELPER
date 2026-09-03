# 🛡️ Telegram VIP Guard & Anti-Spam Bot (Phiên bản Cá Nhân Hoá cho @wolfmodyt) 👑

Bot Telegram bảo vệ nhóm toàn diện, tự động hoá kiểm duyệt nội dung, chống phá hoại, chống spam link, chặn bot lạ, lọc ngôn từ lăng mạ/chửi bậy và **hỗ trợ hiển thị Custom Emoji VIP dành cho tài khoản Telegram Premium bằng mã ID**.

---

## ✨ Điểm Cấu Hình Đặc Biệt

| Cấu hình | Chi tiết hoạt động |
| :--- | :--- |
| 👤 **Nhắn tin trực tiếp (Private Chat)** | **Chỉ cho phép duy nhất `@wolfmodyt`** được nhắn tin trực tiếp với bot. Nếu người khác nhắn tin riêng, bot sẽ hoàn toàn **im lặng và không phản hồi**. |
| ✈️ **Chữ ký cuối mỗi tin nhắn** | Mọi câu nhắn của bot đều tự động đính kèm icon Telegram Premium và tag username: `<tg-emoji emoji-id="5211129162206560202">✈️</tg-emoji> :@wolfmodyt` |
| ⏳ **Icon giới hạn thời gian (Time limit / Mute / Cooldown)** | Khi bị giới hạn thời gian, bot hiển thị icon đồng hồ Premium: `<tg-emoji emoji-id="5382194935057372936">⏳</tg-emoji>` |
| ⏱️ **Tự động xoá sau 30 giây** | Mọi thông báo cảnh báo / vi phạm trong nhóm sẽ **tự động xoá sau đúng 30 giây** để giữ cho nhóm luôn sạch đẹp. |
| 🚫 **Cảnh cáo tối đa 5 lần -> BAN** | Thành viên vi phạm (spam, link, chửi bậy, link bot khác) sẽ bị cảnh cáo (1/5 ... 5/5). **Quá 5 lần vi phạm sẽ bị BAN vĩnh viễn** khỏi nhóm chat. |
| 🤖 **Chống người lạ thêm Bot / Gửi link Bot khác** | Tự động trục xuất (Kick/Ban) ngay lập tức mọi bot lạ do thành viên thường thêm vào nhóm. Khi người dùng gửi link bot khác (trừ admin), bot sẽ xoá tin nhắn, ghi nhận cảnh cáo và chỉ trích dẫn 3-4 từ đầu của link (không hiện toàn bộ link). |

---

## 💎 Gợi Ý Thêm Các Custom Emoji VIP Khác

Bot đã hỗ trợ sẵn các slot Custom Emoji ID cao cấp mà bạn có thể dùng lệnh `/get_emoji` từ tài khoản Premium để lấy ID và gán:

- `tele_logo`: `5211129162206560202` (Icon Telegram chính)
- `clock`: `5382194935057372936` (Icon đồng hồ Time Limit)
- `vip`: Vương miện VIP hoàng gia 👑
- `shield`: Khiên bảo vệ an ninh 🛡️
- `warn`: Tam giác cảnh báo vi phạm ⚠️
- `ban`: Búa cấm / Cấm vĩnh viễn 🚫
- `mute`: Loa cấm chat 🔇
- `link`: Dây xích / Chặn liên kết 🔗
- `bot`: Robot chặn bot lạ 🤖
- `spam`: Ngọn lửa dập tắt spam 🔥
- `success`: Tích xanh hoàn thành ✅
- `error`: Dấu chéo đỏ thất bại ❌
- `diamond`: Kim cương VIP 💎
- `star`: Ngôi sao uy tín ⭐
- `lock`: Ổ khoá bảo mật 🔒
- `bell`: Chuông thông báo 🔔

---

## 🚀 Hướng Dẫn Triển Khai Lên Railway (Deploy 1-Click)

1. **Đẩy code lên GitHub:**
   ```bash
   cd "C:\Users\MSI 15\telegram-guard-bot"
   git init
   git add .
   git commit -m "Deploy Telegram Guard Bot for wolfmodyt"
   git branch -M main
   git remote add origin https://github.com/<username>/<repo_name>.git
   git push -u origin main
   ```

2. **Tạo Project trên Railway:**
   - Truy cập [Railway.app](https://railway.app) và đăng nhập bằng GitHub.
   - Nhấn **New Project** -> Chọn **Deploy from GitHub repo** -> Chọn repository vừa tạo.

3. **Cấu hình Biến Môi Trường (Variables):**
   - Thêm các biến sau:
     - `BOT_TOKEN`: Token bot từ [@BotFather](https://t.me/BotFather).
     - `OWNER_IDS`: Telegram ID của bạn.
     - `ALLOWED_PRIVATE_USERNAMES`: `wolfmodyt`
     - `DEFAULT_MAX_WARNS`: `5`
     - `DEFAULT_WARN_ACTION`: `ban`
     - `AUTO_DELETE_LOGS_SEC`: `30`
     - `EMOJI_TELE_LOGO`: `5211129162206560202`
     - `EMOJI_CLOCK`: `5382194935057372936`

4. **Tạo Volume lưu Database (Tránh mất dữ liệu):**
   - Trong Service trên Railway -> Tab **Volumes** -> Nhấn **Add Volume**.
   - Đặt Mount Path là: `/app/data`

---

## 📋 Danh Sách Lệnh Quản Trị

| Câu lệnh | Mô tả |
| :--- | :--- |
| `/settings` | Mở bảng cài đặt bảo vệ nhóm (Bật/Tắt Anti-Spam, Link, Bot, Chửi bậy) |
| `/stats` | Xem thống kê số lần bot đã ngăn chặn vi phạm |
| `/warn [user_id / reply] [lý do]` | Cảnh cáo thành viên bằng User ID hoặc Reply (Tối đa 5 lần -> BAN vĩnh viễn, hoặc gõ `warn user_id`) |
| `/unwarn [user_id / reply]` | Xoá 1 lần cảnh cáo theo User ID hoặc Reply |
| `/warns [user_id / reply]` | Xem số lần cảnh cáo của bản thân hoặc thành viên |
| `/mute [user_id / reply] [thời gian] [lý do]` | Cấm chat (vd: `/mute 30m`, `/mute 2h`, `/mute 1d`) |
| `/unmute [user_id / reply]` | Mở cấm chat |
| `/kick [user_id / reply] [lý do]` | Trục xuất thành viên khỏi nhóm |
| `/ban [user_id / reply] [lý do]` | Cấm vĩnh viễn thành viên khỏi nhóm theo User ID hoặc Reply (hoặc gõ `ban user_id`) |
| `/unban [user_id]` | Gỡ cấm cho thành viên theo User ID |
| `/addword [từ]` | Thêm từ cấm riêng của nhóm |
| `/delword [từ]` | Xoá từ cấm |
| `/listwords` | Xem danh sách từ cấm của nhóm |
| `/addlink [tên miền]` | Thêm tên miền vào danh sách cho phép (Whitelist) |
| `/dellink [tên miền]` | Xoá tên miền khỏi Whitelist |
| `/listlinks` | Xem danh sách tên miền được phép |
| `/get_emoji` | Quét mã ID của Telegram Premium Custom Emoji |
| `/set_emoji [key] [id]` | Gán mã ID cho các icon của bot |
| `/list_emojis` | Xem danh sách toàn bộ icon đang kích hoạt |
