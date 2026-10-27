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

## Notebook theo toàn bộ quá trình

Mở [`notebooks/eda_va_tien_xu_ly.ipynb`](notebooks/eda_va_tien_xu_ly.ipynb)
trong VS Code/Jupyter, chọn kernel Python có các thư viện trong requirements.txt
và chạy từng ô từ trên xuống. Có thể tải notebook lên Kaggle và thêm dữ liệu
qua Add Input. Notebook tự chứa code, không cần import các file trong `src/`.

Trình tự: đọc dữ liệu → EDA → làm sạch → chia train/validation/test → tạo đặc
trưng → mã hóa/chuẩn hóa → kiểm tra đầu vào mô hình. Các bảng và biểu đồ hiển
thị trực tiếp; dữ liệu chỉ được xử lý trong bộ nhớ, không tự ghi file. Notebook
được cung cấp với các ô chưa chạy. Hai script `.py` vẫn dùng độc lập như cũ.

## Tiền xử lý dữ liệu

Chạy từ thư mục gốc (Python 3.9 trở lên):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src.preprocessing
.venv/bin/python -m unittest discover -s tests -v
```

Để tái lập đúng môi trường đã kiểm tra (Python 3.9), cài bằng
`.venv/bin/python -m pip install -r requirements-lock.txt` thay cho requirements.txt.

Quy trình giữ nguyên dữ liệu gốc, loại dòng trùng, gộp mã nhân khẩu học và chia
train/validation/test xấp xỉ 70/15/15 với seed 42. Các hồ sơ giống nhau sau làm
sạch luôn nằm cùng một tập, kể cả khi khác nhãn. Tỷ lệ thực tế có thể lệch nhẹ
vì ràng buộc nhóm. Các phép chuẩn hóa chỉ học trên train.

Đầu ra trong `data/processed/` (tự sinh, không đưa vào Git):

- `train.csv`, `validation.csv`, `test.csv`: dữ liệu đã làm sạch, chưa chuẩn hóa.
- `split_manifest.csv`: ID, nhóm hồ sơ, fold và tập tương ứng.
- `removed_duplicate_ids.csv`: ID các bản ghi trùng đã loại.
- `metadata.json`: số liệu kiểm tra, seed, phiên bản thư viện, SHA-256 nguồn.
- `linear_base/`, `linear_extended/`, `tree_base/`, `tree_extended/`: mỗi thư mục
  có ba CSV đã biến đổi và `preprocessor.joblib` đã fit trên train.

Các CSV vẫn chứa `ID` để đối chiếu và `default` làm nhãn; **phải loại hai cột này
khỏi X khi huấn luyện**. Bản extended bổ sung sáu đặc trưng hành vi.
Các bộ tiền xử lý đã lưu cần được nạp từ thư mục gốc dự án để import được `src`.

Khi cross-validation, dùng dữ liệu chưa chuẩn hóa và tạo pipeline mới; không
đưa CSV đã chuẩn hóa trên toàn train vào cross-validation. Ví dụ:

```python
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedGroupKFold, cross_validate
from src.preprocessing import FEATURES, make_preprocessor

train = pd.read_csv('data/processed/train.csv')
manifest = pd.read_csv('data/processed/split_manifest.csv').set_index('ID')
groups = train.ID.map(manifest.group_id)
model = Pipeline([
    ('preprocessing', make_preprocessor('linear', with_features=True)),
    ('classifier', LogisticRegression(max_iter=2000)),
])
cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_validate(model, train[FEATURES], train['default'], groups=groups,
                        cv=cv, scoring=['roc_auc', 'average_precision'])
```

Báo cáo phương pháp: `reports/Bao_cao_Tien_xu_ly.md`.
Bảng kết quả: `reports/tables/09_preprocessing_*.csv`.
