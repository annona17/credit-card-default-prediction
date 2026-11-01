# Dự đoán khả năng vỡ nợ của khách hàng sử dụng thẻ tín dụng

Bài tập nhóm cuối kỳ học phần **Nhận dạng mẫu** – Nhóm 13. Giảng viên: TS. Nguyễn Xuân Đức.

- **Báo cáo:** [PDF](reports/Bao_cao_Final.pdf) · [Word](reports/Bao_cao_Final.docx) · [Markdown](reports/Bao_cao_Final.md)
- **Bài toán:** phân loại hai lớp (vỡ nợ / không vỡ nợ trong tháng kế tiếp) trên dữ liệu mất cân bằng (22% vỡ nợ), chi phí lỗi bất đối xứng (bỏ sót một khách hàng vỡ nợ = 5 lần cảnh báo nhầm).
- **Mô hình:** Logistic Regression (cơ sở); HistGradientBoosting, Random Forest, SVM RBF, Gaussian Naive Bayes (thay thế).
- **Kết quả chính (tập test):** HistGradientBoosting đạt PR-AUC 0,569 (KTC 95% [0,533; 0,601]), ROC-AUC 0,787, expected cost 0,541 – tốt hơn có ý nghĩa thống kê so với Logistic Regression (PR-AUC 0,507; expected cost 0,617).

| Thành viên | Mã học viên |
|---|---|
| Lưu Ngọc Anh | B26CHKH006 |
| Nguyễn Hoàng Hiệp | B26CHKH042 |
| Nguyễn Anh Quân | B26CHKH080 |
| Hoàng Anh Vũ | B26CHKH103 |

## Chạy nhanh

Các lệnh chạy từ thư mục gốc của dự án. Trên Windows thay `.venv/bin/python` bằng `.venv\Scripts\python` và bật chế độ UTF-8 trước khi chạy để in được tiếng Việt ra console: `$env:PYTHONUTF8=1` (PowerShell) hoặc `set PYTHONUTF8=1` (cmd).

### 1. Cài đặt (Python 3.9 trở lên)

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 2. Dữ liệu

Tệp dữ liệu gốc đã có sẵn trong repo: `data/raw/default of credit card clients.xls`. Nếu thiếu, tải từ UCI rồi giải nén vào `data/raw/`:

- Trang dữ liệu: https://archive.ics.uci.edu/dataset/350 (DOI 10.24432/C55S3H, giấy phép CC BY 4.0)
- Tệp zip: https://archive.ics.uci.edu/static/public/350/default+of+credit+card+clients.zip

### 3. Chạy theo thứ tự

| Bước | Lệnh | Đầu ra | Chương |
|---|---|---|---|
| 1. Phân tích sơ bộ | `.venv/bin/python src/eda.py` | `reports/figures/00–10_*.png`, `reports/tables/00–08_*.csv` | 2 |
| 2. Tiền xử lý | `.venv/bin/python -m src.preprocessing` | `data/processed/` (dữ liệu sạch, 4 cấu hình đầu vào, bộ tiền xử lý đã fit) | 3 |
| 3. Tập đánh giá | `.venv/bin/python -m src.evaluation` | `reports/tables/10_*.csv` | 4 |
| 4. Huấn luyện và đánh giá 5 mô hình | `.venv/bin/python -m src.modeling_team` | `reports/tables/12_*.csv`, `reports/figures/12_*.png`, `outputs/team/*.joblib` | 5–6 |
| 5. Kiểm thử | `.venv/bin/python -m unittest discover -s tests -v` | – | – |

- Bước 4 mất khoảng 7 phút (SVM chiếm phần lớn thời gian). Bước 5 cần chạy sau bước 2.
- Bước 3 và 4 luôn đọc phép chia cố định trong `data/splits/split_manifest.csv` (train 20.976 / validation 4.493 / test 4.496), nên mọi thành viên đánh giá trên cùng một tập test dù phiên bản thư viện khác nhau.
- Bước 2 tự tạo lại phép chia; với scikit-learn khác 1.6.1, phép chia này lệch nhẹ so với manifest (ví dụ train 20.977 mẫu) và ghi đè `reports/tables/09_preprocessing_splits.csv`. Điều này không ảnh hưởng kết quả mô hình, nhưng không nên commit bảng 09 vừa sinh ra – khôi phục bằng `git checkout -- reports/tables/09_preprocessing_splits.csv`, hoặc dùng môi trường khóa ở mục 4.
- `data/processed/` và `outputs/` là đầu ra tự sinh, không đưa vào Git.

### 4. Tái lập đúng số liệu trong báo cáo

`requirements.txt` cho phép một khoảng phiên bản. Để ra đúng từng con số trong báo cáo, dùng môi trường đã khóa phiên bản:

- `requirements-lock.txt` (Python 3.9, scikit-learn 1.6.1) cho bước 1–3. Chỉ môi trường này tạo lại đúng `split_manifest.csv` nếu chạy lại phép chia từ đầu.
- `requirements-modeling-lock.txt` (Python 3.11, scikit-learn 1.9.1) cho bước 4.

```bash
python -m venv .venv-model
.venv-model/bin/python -m pip install -r requirements-modeling-lock.txt
.venv-model/bin/python -m src.modeling_team
```

## Demo tương tác

Web demo (Streamlit) cho phép thao tác trực tiếp với dữ liệu:

- **Dự đoán cho một khách hàng:** lấy ngẫu nhiên một khách hàng trong tập test hoặc tự nhập/sửa thông tin, xem xác suất vỡ nợ, quyết định cảnh báo và các đặc trưng hành vi mô hình tính thêm.
- **Chọn ngưỡng theo chi phí:** đổi tỷ lệ phạt (bỏ sót / nhắc nhầm) hoặc tự kéo ngưỡng, xem TP/FN/FP, Recall và chi phí trên tập test thay đổi thế nào.
- **Khám phá dữ liệu:** lọc theo hạn mức, tuổi, giới tính và xem tỷ lệ vỡ nợ theo từng nhóm.

```bash
.venv/bin/python -m pip install -r requirements-demo.txt
.venv/bin/python -m streamlit run demo/app.py
```

Demo tự huấn luyện lại HistGradientBoosting và Logistic Regression theo đúng cấu hình đã chọn trong báo cáo (khoảng 10 giây ở lần mở đầu), nên không cần chạy trước bước 4. Với scikit-learn 1.9.1, ngưỡng và kết quả trên test khớp với báo cáo (ngưỡng 0,167; 778 phát hiện đúng, 243 bỏ sót, 1.219 nhắc nhầm).

## Dùng mô hình đã huấn luyện

Sau bước 4, mỗi mô hình được lưu cùng ngưỡng quyết định đã chọn trên validation. Đầu vào là 23 cột gốc đã làm sạch; pipeline tự tạo đặc trưng và biến đổi.

```python
import joblib
from src.modeling_team import model_scores
from src.preprocessing import FEATURES

bundle = joblib.load('outputs/team/hist_gradient_boosting.joblib')
score = model_scores(bundle['model'], X[FEATURES])   # X: DataFrame các khách hàng cần dự đoán
canh_bao = score >= bundle['threshold']               # ngưỡng tối thiểu hóa 5·FN + FP
```

Không dùng `.predict()` mặc định (ngưỡng 0,5). Riêng SVM trả về giá trị hàm quyết định, không phải xác suất.

## Cấu trúc thư mục

```
data/raw/          dữ liệu gốc UCI
data/splits/       phép chia cố định train/validation/test
src/               mã nguồn: eda, preprocessing, evaluation, modeling, modeling_team
tests/             kiểm thử tự động
demo/              web demo tương tác (Streamlit)
notebooks/         notebook chạy từng bước (EDA → tiền xử lý → tập đánh giá → mô hình)
reports/           báo cáo, bảng số liệu (tables/) và biểu đồ (figures/)
```

**Notebook đầy đủ:** [`du_doan_vo_no_day_du.ipynb`](notebooks/du_doan_vo_no_day_du.ipynb) gộp cả bài trong một file (EDA → tiền xử lý → tập đánh giá → huấn luyện và đánh giá 5 mô hình), tự chứa code, đã lưu sẵn kết quả chạy; tải thẳng file này lên Kaggle được (thêm `data/splits/split_manifest.csv` làm input để ra đúng phép chia của báo cáo). Chạy lại toàn bộ mất khoảng 10 phút.

Các notebook theo từng phần (giữ lại để đối chiếu): [`eda_va_tien_xu_ly.ipynb`](notebooks/eda_va_tien_xu_ly.ipynb) (EDA, tiền xử lý, tập đánh giá; tự chứa code, chạy được trên Kaggle), [`mo_hinh_Hiep.ipynb`](notebooks/mo_hinh_Hiep.ipynb) và [`ba_phuong_an_bo_sung.ipynb`](notebooks/ba_phuong_an_bo_sung.ipynb) (mô hình; cần clone repo). Bản đầu tiên, chỉ có phần EDA: [`tong_hop_du_lieu.ipynb`](notebooks/tong_hop_du_lieu.ipynb).

Báo cáo thành phần của từng phần việc (đã được tổng hợp vào báo cáo cuối kỳ) nằm trong `reports/`: `Bao_cao_Phan1_Bai_toan_va_Du_lieu.docx`, `Bao_cao_Tien_xu_ly.md`, `Bao_cao_Tap_danh_gia.md`, `Bao_cao_Mo_hinh_Hiep.md`, `Bao_cao_So_sanh_Tat_ca_Mo_hinh.md` và ba báo cáo mô hình bổ sung.
