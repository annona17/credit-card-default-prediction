# Phương án thay thế: Random Forest

## Phương pháp và cấu hình

Tập hợp 200 cây được huấn luyện trên các mẫu bootstrap, lấy trung bình xác suất. Dùng tree_extended của Phần 2; max_features=sqrt, max_depth ∈ {8; None}, min_samples_leaf ∈ {5; 20}, seed=42. Giới hạn độ sâu/kích thước lá giúp giảm overfit. RF tạo các cây độc lập, khác cơ chế boosting tuần tự của HGB.

Điểm dự đoán là $s(x)=\frac{1}{T}\sum_{t=1}^{T}p_t(y=1\mid x)$, với $T=200$ cây; mỗi cây chỉ xét một tập con ngẫu nhiên các đặc trưng tại mỗi nút.

Tái sử dụng `clean_data`, `make_preprocessor`, manifest cố định của Phần 2–3. ID và nhãn bị loại khỏi X; mọi phép học tiền xử lý nằm trong pipeline của từng fold. Dùng cùng 5 fold StratifiedGroupKFold trên train, có nhóm hồ sơ, chọn cấu hình theo AP trung bình. Validation chỉ chọn ngưỡng nhỏ nhất của (5FN+FP)/n; dùng đúng ngưỡng đó cho test.

| Mô hình | CV AP mean | CV AP std | CV ROC mean | CV ROC std | Fit seconds | Cấu hình |
| --- | --- | --- | --- | --- | --- | --- |
| Random Forest | 0.5605 | 0.0095 | 0.7833 | 0.0049 | 70.6580 | {"clf__max_depth": 8, "clf__min_samples_leaf": 5} |

## Kết quả và nhận xét

| Mô hình | PR-AUC | ROC-AUC | Ngưỡng | Recall | Precision | Chi phí / KH | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | 0.5071 | 0.7475 | 0.2275 | 0.6161 | 0.4365 | 0.6165 | 812.0000 | 392.0000 |
| Random Forest | 0.5660 | 0.7835 | 0.1641 | 0.7365 | 0.3909 | 0.5598 | 1172.0000 | 269.0000 |

So với LR, chênh lệch AP mô tả là +0.0589, chênh lệch chi phí là -0.0567. Mô hình bỏ sót 269 khách vỡ nợ và cảnh báo nhầm 1172 khách tốt. Nhóm FN có trung bình 0.01 tháng chậm trả, so với 2.78 ở TP. Đây là mô tả test, không phải kiểm định riêng mô hình này với LR; chỉ các cặp đã chốt trong báo cáo chung được diễn giải bằng paired bootstrap.

Các chỉ số tại ngưỡng validation; chi phí dùng tỷ lệ giả định FN:FP=5:1, không phải tiền thực tế. Ngưỡng SVM là margin, ngưỡng các mô hình khác là xác suất đầu ra chưa được kiểm tra calibration.

## Phân tích lỗi theo nhóm

Ba lát cắt có chi phí cao nhất (có thể chồng nhau):

| Lát cắt | Nhóm | Số khách | Tỷ lệ vỡ nợ | PR-AUC | Recall | Precision | Chi phí / KH |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Hạn mức | ≤ 50k | 1149.0000 | 0.3055 | 0.5958 | 0.8319 | 0.3989 | 0.6397 |
| PAY_0 | 1 | 544.0000 | 0.3290 | 0.4494 | 0.9777 | 0.3564 | 0.6176 |
| PAY_0 | −2 / −1 | 1274.0000 | 0.1656 | 0.3281 | 0.5782 | 0.2681 | 0.6107 |

AP phải đối chiếu với tỷ lệ vỡ nợ của chính nhóm. Những nhóm ít mẫu có độ bất định lớn. Bảng mô tả theo giới tính không đủ để kết luận về tính công bằng.

| Mô hình | Loại lỗi | Số khách | LIMIT_BAL | AGE | PAY_0 | late_month_count | utilization_sep | zero_payment_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Random Forest | TP | 752.0000 | 121861.7021 | 35.8816 | 1.0758 | 2.7793 | 0.4966 | 2.0705 |
| Random Forest | FN | 269.0000 | 174052.0446 | 36.2528 | -0.4349 | 0.0149 | 0.5069 | 0.7881 |
| Random Forest | FP | 1172.0000 | 134223.5495 | 35.3208 | 0.1630 | 1.5162 | 0.3730 | 2.1647 |
| Random Forest | TN | 2303.0000 | 198632.2188 | 35.6314 | -0.4025 | 0.0252 | 0.4071 | 0.5766 |

## Hạn chế

Tốn bộ nhớ hơn mô hình tuyến tính; lưới nhỏ chưa khảo sát số cây/max_features. Các cây vẫn có thể khó mô hình hóa một số tương tác và chưa kiểm tra calibration.

Đợt bổ sung diễn ra sau khi kết quả test của LR/HGB đã được xem. Lưới ba mô hình mới được cố định trước khi tính test của chúng; không thay lưới sau khi xem test. Vì cùng test đã được dùng trong quá trình dự án, kết quả mở rộng mang tính khám phá, chưa phải xác nhận độc lập. Dữ liệu từ Đài Loan năm 2005, chưa đánh giá dịch chuyển theo thời gian, chưa nested CV, chưa ablation cùng bộ đặc trưng để tách ảnh hưởng thuật toán và feature engineering.

## Tái lập

Chạy `python -m src.modeling_team` từ gốc repo. Pipeline/điểm/ngưỡng lưu ở `outputs/team/random_forest.joblib`; dùng `model_scores(bundle['model'], X)` rồi so với `bundle['threshold']`. Đầu vào X là 23 cột FEATURES đã làm sạch, chưa chuẩn hóa. Không dùng `.predict()` mặc định vì ngưỡng của thực nghiệm được chọn riêng.

Nguồn thuật toán: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html

Dữ liệu: UCI Default of Credit Card Clients, DOI 10.24432/C55S3H, https://archive.ics.uci.edu/dataset/350.
