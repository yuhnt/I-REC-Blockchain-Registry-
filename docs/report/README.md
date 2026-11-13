# Xuất báo cáo cuối kỳ ra Word và PDF

`md2docx.py` chuyển `Final Report.md` sang `.docx` theo mẫu `final/format.docx`:
- giữ trang bìa (đổi thành "BÁO CÁO CUỐI KỲ") và mục lục của mẫu;
- dùng style Title, Heading 1–3 của mẫu, chữ Times New Roman 12 pt, bảng 10 pt;
- footer đổi "Mini Proposal" thành "Final Report".

`update_word.ps1` mở file bằng Word (cần Microsoft Word trên máy), cập nhật mục lục, lưu `.docx` và xuất PDF.

```bash
python docs/report/md2docx.py ../final/format.docx "<đường dẫn>/Final Report.md" "<thư mục Attachments>" report_raw.docx
powershell -NoProfile -ExecutionPolicy Bypass -File docs/report/update_word.ps1 -In <đường dẫn tuyệt đối>/report_raw.docx -OutDocx <...>/Blockchain-Group04-Final-Report.docx -OutPdf <...>/Blockchain-Group04-Final-Report.pdf
```

Markdown được hỗ trợ: tiêu đề `#`–`####`, đoạn văn, `**đậm**`, `*nghiêng*`, `` `mã` ``, danh sách gạch đầu dòng và đánh số (một mức lồng), bảng `|`, ảnh `![chú thích|rộng](file.png)` (ảnh lấy trong thư mục Attachments), mục tài liệu tham khảo `[n] ...`.
