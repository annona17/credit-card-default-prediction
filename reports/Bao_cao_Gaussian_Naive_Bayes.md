# Phương án thay thế: Gaussian Naive Bayes

## Phương pháp và cấu hình

Gaussian Naive Bayes áp dụng Bayes với giả định các đặc trưng độc lập có điều kiện theo nhãn và mỗi đặc trưng có phân phối Gaussian trong từng lớp. Dùng linear_extended; var_smoothing ∈ {1e-9; 1e-7; 1e-5}. Prior học từ train, không cân bằng lớp bằng trọng số. Mô hình này tạo đối chứng xác suất đơn giản và huấn luyện nhanh.

Với lớp $c\in\{0,1\}$, $P(c\mid x)\propto P(c)\prod_j \mathcal{N}(x_j;\mu_{cj},\sigma_{cj}^2)$. Prior, trung bình và phương sai chỉ ước lượng trên phần train của mỗi fold; smoothing ổn định các phương sai nhỏ.

Tái sử dụng `clean_data`, `make_preprocessor`, manifest cố định của Phần 2–3. ID và nhãn bị loại khỏi X; mọi phép học tiền xử lý nằm trong pipeline của từng fold. Dùng cùng 5 fold StratifiedGroupKFold trên train, có nhóm hồ sơ, chọn cấu hình theo AP trung bình. Validation chỉ chọn ngưỡng nhỏ nhất của (5FN+FP)/n; dùng đúng ngưỡng đó cho test.

| Mô hình | CV AP mean | CV AP std | CV ROC mean | CV ROC std | Fit seconds | Cấu hình |
| --- | --- | --- | --- | --- | --- | --- |
| Gaussian Naive Bayes | 0.4886 | 0.0177 | 0.7539 | 0.0072 | 7.2844 | {"clf__var_smoothing": 1e-05} |

## Kết quả và nhận xét

| Mô hình | PR-AUC | ROC-AUC | Ngưỡng | Recall | Precision | Chi phí / KH | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | 0.5071 | 0.7475 | 0.2275 | 0.6161 | 0.4365 | 0.6165 | 812.0000 | 392.0000 |
| Gaussian Naive Bayes | 0.4879 | 0.7531 | 0.0871 | 0.6905 | 0.4085 | 0.5785 | 1021.0000 | 316.0000 |

So với LR, chênh lệch AP mô tả là -0.0192, chênh lệch chi phí là -0.0380. Mô hình bỏ sót 316 khách vỡ nợ và cảnh báo nhầm 1021 khách tốt. Nhóm FN có trung bình 0.09 tháng chậm trả, so với 2.93 ở TP. Đây là mô tả test, không phải kiểm định riêng mô hình này với LR; chỉ các cặp đã chốt trong báo cáo chung được diễn giải bằng paired bootstrap.

Các chỉ số tại ngưỡng validation; chi phí dùng tỷ lệ giả định FN:FP=5:1, không phải tiền thực tế. Ngưỡng SVM là margin, ngưỡng các mô hình khác là xác suất đầu ra chưa được kiểm tra calibration.

## Phân tích lỗi theo nhóm

Ba lát cắt có chi phí cao nhất (có thể chồng nhau):

| Lát cắt | Nhóm | Số khách | Tỷ lệ vỡ nợ | PR-AUC | Recall | Precision | Chi phí / KH |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Hạn mức | 50–100k | 721.0000 | 0.2705 | 0.5027 | 0.6872 | 0.4393 | 0.6602 |
| PAY_0 | −2 / −1 | 1274.0000 | 0.1656 | 0.2968 | 0.4692 | 0.2853 | 0.6342 |
| Hạn mức | ≤ 50k | 1149.0000 | 0.3055 | 0.5298 | 0.7892 | 0.4362 | 0.6336 |

AP phải đối chiếu với tỷ lệ vỡ nợ của chính nhóm. Những nhóm ít mẫu có độ bất định lớn. Bảng mô tả theo giới tính không đủ để kết luận về tính công bằng.

| Mô hình | Loại lỗi | Số khách | LIMIT_BAL | AGE | PAY_0 | late_month_count | utilization_sep | zero_payment_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gaussian Naive Bayes | TP | 705.0000 | 121716.3121 | 36.0908 | 1.1645 | 2.9277 | 0.5082 | 2.2482 |
| Gaussian Naive Bayes | FN | 316.0000 | 166613.9241 | 35.7310 | -0.4082 | 0.0949 | 0.4794 | 0.5823 |
| Gaussian Naive Bayes | FP | 1021.0000 | 134857.9824 | 35.5132 | 0.2752 | 1.6748 | 0.3797 | 2.7297 |
| Gaussian Naive Bayes | TN | 2454.0000 | 194405.0530 | 35.5322 | -0.4144 | 0.0509 | 0.4022 | 0.4393 |

## Hạn chế

Dư nợ và thanh toán qua các tháng tương quan, vi phạm giả định độc lập. Biến one-hot không có phân phối Gaussian; vì vậy đây là một phương án đơn giản với giả định gần đúng và xác suất có thể chưa được hiệu chỉnh tốt.

Đợt bổ sung diễn ra sau khi kết quả test của LR/HGB đã được xem. Lưới ba mô hình mới được cố định trước khi tính test của chúng; không thay lưới sau khi xem test. Vì cùng test đã được dùng trong quá trình dự án, kết quả mở rộng mang tính khám phá, chưa phải xác nhận độc lập. Dữ liệu từ Đài Loan năm 2005, chưa đánh giá dịch chuyển theo thời gian, chưa nested CV, chưa ablation cùng bộ đặc trưng để tách ảnh hưởng thuật toán và feature engineering.

## Tái lập

Chạy `python -m src.modeling_team` từ gốc repo. Pipeline/điểm/ngưỡng lưu ở `outputs/team/gaussian_nb.joblib`; dùng `model_scores(bundle['model'], X)` rồi so với `bundle['threshold']`. Đầu vào X là 23 cột FEATURES đã làm sạch, chưa chuẩn hóa. Không dùng `.predict()` mặc định vì ngưỡng của thực nghiệm được chọn riêng.

Nguồn thuật toán: https://scikit-learn.org/stable/modules/generated/sklearn.naive_bayes.GaussianNB.html

Dữ liệu: UCI Default of Credit Card Clients, DOI 10.24432/C55S3H, https://archive.ics.uci.edu/dataset/350.
