# Dự đoán vỡ nợ thẻ tín dụng (Default of Credit Card Clients)

Bài tập nhóm cuối kỳ môn Nhận dạng mẫu.

## Dữ liệu
- Nguồn: UCI Machine Learning Repository, mã 350, https://archive.ics.uci.edu/dataset/350 (DOI 10.24432/C55S3H, giấy phép CC BY 4.0).
- Tải file zip từ https://archive.ics.uci.edu/static/public/350/default+of+credit+card+clients.zip, giải nén vào `data/raw/`.

## Cài đặt
```bash
pip install pandas numpy matplotlib seaborn scipy scikit-learn xlrd
```

## Chạy phân tích sơ bộ
```bash
python src/eda.py
```
Kết quả: biểu đồ ở `reports/figures/`, bảng số liệu ở `reports/tables/`. Bản notebook để chạy trên Kaggle: `kaggle/du_doan_kha_nang_vo_no_the_tin_dung.ipynb` (tự tìm dữ liệu trong `/kaggle/input`).

Báo cáo phần bài toán và dữ liệu: `reports/Bao_cao_Phan1_Bai_toan_va_Du_lieu.docx`.
