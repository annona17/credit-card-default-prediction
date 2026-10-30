# Phương án thay thế: SVM RBF

## Phương pháp và cấu hình

SVM tìm biên phân lớp với kernel RBF để biểu diễn quan hệ phi tuyến. Dùng linear_extended của Phần 2 để log hóa và chuẩn hóa trong từng fold. C ∈ {0,1; 1; 10}, gamma=scale, class_weight=None. probability=False: dùng decision_function, điểm càng lớn càng nghiêng về lớp default=1. Không dùng hiệu chỉnh xác suất nội bộ để tránh một phép chia calibration không kiểm soát nhóm.

Kernel $K(x,z)=\exp(-\gamma\|x-z\|^2)$; $C$ điều khiển đánh đổi giữa biên rộng và lỗi trên train. Điểm $s(x)=\sum_i\alpha_i y_iK(x_i,x)+b$ dùng nhãn nội bộ $y_i\in\{-1,+1\}$, trong khi nhãn dữ liệu vẫn là 0/1.

Tái sử dụng `clean_data`, `make_preprocessor`, manifest cố định của Phần 2–3. ID và nhãn bị loại khỏi X; mọi phép học tiền xử lý nằm trong pipeline của từng fold. Dùng cùng 5 fold StratifiedGroupKFold trên train, có nhóm hồ sơ, chọn cấu hình theo AP trung bình. Validation chỉ chọn ngưỡng nhỏ nhất của (5FN+FP)/n; dùng đúng ngưỡng đó cho test.

| Mô hình | CV AP mean | CV AP std | CV ROC mean | CV ROC std | Fit seconds | Cấu hình |
| --- | --- | --- | --- | --- | --- | --- |
| SVM RBF | 0.5225 | 0.0078 | 0.7203 | 0.0060 | 306.7149 | {"clf__C": 1.0} |

## Kết quả và nhận xét

| Mô hình | PR-AUC | ROC-AUC | Ngưỡng | Recall | Precision | Chi phí / KH | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | 0.5071 | 0.7475 | 0.2275 | 0.6161 | 0.4365 | 0.6165 | 812.0000 | 392.0000 |
| SVM RBF | 0.5134 | 0.7112 | -0.9928 | 0.6072 | 0.4375 | 0.6232 | 797.0000 | 401.0000 |

So với LR, chênh lệch AP mô tả là +0.0063, chênh lệch chi phí là +0.0067. Mô hình bỏ sót 401 khách vỡ nợ và cảnh báo nhầm 797 khách tốt. Nhóm FN có trung bình 0.40 tháng chậm trả, so với 3.12 ở TP. Đây là mô tả test, không phải kiểm định riêng mô hình này với LR; chỉ các cặp đã chốt trong báo cáo chung được diễn giải bằng paired bootstrap.

Các chỉ số tại ngưỡng validation; chi phí dùng tỷ lệ giả định FN:FP=5:1, không phải tiền thực tế. Ngưỡng SVM là margin, ngưỡng các mô hình khác là xác suất đầu ra chưa được kiểm tra calibration.

## Phân tích lỗi theo nhóm

Ba lát cắt có chi phí cao nhất (có thể chồng nhau):

| Lát cắt | Nhóm | Số khách | Tỷ lệ vỡ nợ | PR-AUC | Recall | Precision | Chi phí / KH |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PAY_0 | 1 | 544.0000 | 0.3290 | 0.4319 | 0.7989 | 0.3865 | 0.7482 |
| Hạn mức | ≤ 50k | 1149.0000 | 0.3055 | 0.5557 | 0.6980 | 0.4685 | 0.7032 |
| PAY_0 | −2 / −1 | 1274.0000 | 0.1656 | 0.2437 | 0.3555 | 0.2622 | 0.6994 |

AP phải đối chiếu với tỷ lệ vỡ nợ của chính nhóm. Những nhóm ít mẫu có độ bất định lớn. Bảng mô tả theo giới tính không đủ để kết luận về tính công bằng.

| Mô hình | Loại lỗi | Số khách | LIMIT_BAL | AGE | PAY_0 | late_month_count | utilization_sep | zero_payment_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SVM RBF | TP | 620.0000 | 120854.8387 | 36.3597 | 1.3242 | 3.1194 | 0.5236 | 2.1113 |
| SVM RBF | FN | 401.0000 | 158428.9277 | 35.3915 | -0.3217 | 0.3990 | 0.4617 | 1.1471 |
| SVM RBF | FP | 797.0000 | 148557.0891 | 36.5245 | 0.2999 | 1.7553 | 0.3691 | 2.1719 |
| SVM RBF | TN | 2678.0000 | 185347.2741 | 35.2296 | -0.3641 | 0.1628 | 0.4035 | 0.7969 |

## Hạn chế

Điểm decision_function không phải xác suất, không dùng ngưỡng lý thuyết 1/6. Huấn luyện và dự đoán chậm khi nhiều support vector; gamma chỉ dùng scale trong lưới này.

Đợt bổ sung diễn ra sau khi kết quả test của LR/HGB đã được xem. Lưới ba mô hình mới được cố định trước khi tính test của chúng; không thay lưới sau khi xem test. Vì cùng test đã được dùng trong quá trình dự án, kết quả mở rộng mang tính khám phá, chưa phải xác nhận độc lập. Dữ liệu từ Đài Loan năm 2005, chưa đánh giá dịch chuyển theo thời gian, chưa nested CV, chưa ablation cùng bộ đặc trưng để tách ảnh hưởng thuật toán và feature engineering.

## Tái lập

Chạy `python -m src.modeling_team` từ gốc repo. Pipeline/điểm/ngưỡng lưu ở `outputs/team/svm_rbf.joblib`; dùng `model_scores(bundle['model'], X)` rồi so với `bundle['threshold']`. Đầu vào X là 23 cột FEATURES đã làm sạch, chưa chuẩn hóa. Không dùng `.predict()` mặc định vì ngưỡng của thực nghiệm được chọn riêng.

Nguồn thuật toán: https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html

Dữ liệu: UCI Default of Credit Card Clients, DOI 10.24432/C55S3H, https://archive.ics.uci.edu/dataset/350.
