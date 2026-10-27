# Tiền xử lý dữ liệu dự đoán vỡ nợ thẻ tín dụng

## 1. Mục tiêu và phạm vi

Chuyển dữ liệu UCI gốc thành các tập dữ liệu nhất quán để so sánh mô hình,
đồng thời tránh rò rỉ thông tin giữa các tập. Mã thực hiện: `src/preprocessing.py`.
Bước này chưa huấn luyện bộ phân loại, chưa chọn ngưỡng dự đoán và chưa đo hiệu
quả dự đoán. Các biến đổi log là cấu hình đề xuất; lợi ích cần được kiểm chứng
trong bước lựa chọn mô hình.

## 2. Kiểm tra và làm sạch

| Nội dung | Trước xử lý | Sau xử lý |
|---|---:|---:|
| Số bản ghi | 30.000 | 29.965 |
| Dòng trùng hoàn toàn khi bỏ ID | 35 | 0 |
| Giá trị thiếu | 0 | 0 |
| EDUCATION mang mã 0, 5, 6 | 345 | 0 (gộp về 4) |
| MARRIAGE mang mã 0 | 54 | 0 (gộp về 3) |
| Đặc trưng gốc, không tính ID/nhãn | 23 | 23 |

Loại trùng trước khi gộp mã, giữ bản ghi xuất hiện đầu tiên. Danh sách ID bị
loại được lưu để kiểm tra. Nhãn đổi tên thành `default`; ID chỉ phục vụ truy
vết. Các giá trị PAY âm/0, dư nợ âm, dư nợ bằng 0 và khoản tiền lớn được giữ
nguyên. Không diễn giải thêm các mã PAY chưa có mô tả rõ ràng.

Chương trình kiểm tra cấu trúc cột, ID duy nhất, nhãn 0/1, số hữu hạn, miền mã,
hạn mức dương và tiền thanh toán không âm. Nếu không đạt thì dừng để kiểm tra,
không tự điền hay xóa dữ liệu bất thường.

## 3. Chia dữ liệu và chống rò rỉ

Sau làm sạch có 21 nhóm hồ sơ có cùng 23 đặc trưng nhưng nhãn khác nhau.
Đây không phải bản sao hoàn toàn: giữ cả hai nhãn và ràng buộc cùng nhóm không
xuất hiện ở nhiều tập. Nhóm được xác định bằng các đặc trưng sau khi gộp mã.

Dùng `StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=42)`, gộp
14 folds thành train, 3 folds thành validation và 3 folds thành test. Cách này
đạt tỷ lệ xấp xỉ 70/15/15 đồng thời giữ nhóm và phân tầng gần đúng.

| Tập | Số dòng | Số vỡ nợ | Tỷ lệ vỡ nợ |
|---|---:|---:|---:|
| Train | 20.976 | 4.608 | 21,97% |
| Validation | 4.493 | 1.001 | 22,28% |
| Test | 4.496 | 1.021 | 22,71% |

Không dùng ID để chia theo thời gian: các khách hàng cùng có lịch sử sáu tháng
và nhãn tháng kế tiếp. Kết quả kiểm tra này không đại diện cho đánh giá trên
một giai đoạn tương lai mới.

Bộ chuẩn hóa chỉ fit trên train. Validation dành cho lựa chọn cấu hình và
ngưỡng; test dành cho đánh giá cuối cùng. Khi cross-validation cần dùng pipeline
chưa fit và chia theo nhóm trong train. Không dùng các CSV đã chuẩn hóa toàn
train để làm cross-validation. EDA trước đây đã xem toàn bộ dữ liệu; cần ghi
nhận điều đó trong báo cáo, vì test hiện tại không phải dữ liệu hoàn toàn chưa
được quan sát trong quá trình khám phá.

## 4. Mã hóa và biến đổi

SEX, EDUCATION và MARRIAGE được one-hot theo miền mã cố định, bỏ nhóm đầu để
tránh phụ thuộc tuyến tính hoàn toàn giữa các cột giả. Mã ngoài miền bị báo lỗi.
Các biến PAY được giữ dạng số trong cấu hình cơ sở; đây là giả định biểu diễn
cần đánh giá thêm, không khẳng định mọi mã có khoảng cách nghiệp vụ tương đương.

- **linear:** LIMIT_BAL và PAY_AMT biến đổi `log1p`; BILL_AMT biến đổi
  `sign(x) * log1p(abs(x))` để giữ số âm. Các cột số sau đó dùng StandardScaler.
  AGE và PAY chỉ chuẩn hóa. Phù hợp làm điểm khởi đầu cho logistic và LDA.
- **tree:** giữ nguyên các cột số, không chuẩn hóa/log; dùng cùng cách one-hot
  để có đầu vào nhất quán cho các mô hình cây.

Không áp dụng PCA, cắt ngoại lệ hoặc chọn đặc trưng theo nhãn ở bước mặc định.
Naive Bayes cần chọn biến thể và đánh giá riêng; các biến đổi này không đảm bảo
các giả định phân phối hay độc lập của Naive Bayes được thỏa mãn.

## 5. Đặc trưng bổ sung

Bản `base` chỉ có đặc trưng gốc; bản `extended` thêm:

| Tên | Công thức |
|---|---|
| late_month_count | Số tháng PAY > 0 |
| max_delay | max(0, max(PAY)) |
| recent_delay_change | PAY_0 - PAY_2 |
| utilization_sep | BILL_AMT1 / LIMIT_BAL |
| mean_payment | Trung bình PAY_AMT1…PAY_AMT6 |
| zero_payment_count | Số tháng PAY_AMT = 0 |

Các đặc trưng được tính riêng trên từng dòng, không dùng nhãn hoặc thống kê
của tập khác. Trong cấu hình linear, mean_payment được log1p rồi chuẩn hóa;
các đặc trưng mới còn lại chỉ chuẩn hóa. Sau mã hóa, bản base có 26 cột đầu
vào, bản extended có 32 cột. ID và default không nằm trong các con số này.

## 6. Mất cân bằng và sản phẩm bàn giao

Giữ nguyên phân bố nhãn, chưa dùng SMOTE. Khi huấn luyện sẽ so sánh mô hình
cơ sở với trọng số lớp nếu mô hình hỗ trợ; mọi phép lấy mẫu lại chỉ được thực
hiện trong phần train của mỗi fold.

`data/processed/` chứa dữ liệu sạch của ba tập, manifest ID/nhóm/fold, danh sách
ID loại, metadata và bốn thư mục linear_base, linear_extended, tree_base,
tree_extended. Mỗi thư mục cấu hình chứa ba CSV đã biến đổi và bộ tiền xử lý
đã fit. Mọi CSV dữ liệu có ID và nhãn để đối chiếu; phải loại chúng khỏi X.
Các đầu ra được tái tạo bằng `python -m src.preprocessing` từ gốc dự án.

Metadata lưu SHA-256 dữ liệu gốc và phiên bản numpy/pandas/scikit-learn.
`requirements-lock.txt` ghi phiên bản thực tế của môi trường đã chạy; dùng cùng
phiên bản để tái lập phép chia. `requirements.txt` mô tả khoảng phiên bản hỗ trợ.

Các kiểm tra tự động bao gồm tính toàn vẹn tập chia, không giao nhóm, tái lập
seed, tỷ lệ nhãn, từ chối đầu vào lỗi, số liệu scaler đúng theo train, dữ liệu
validation không thay đổi trạng thái đã fit và nạp lại artifact ở tiến trình khác.
Các đầu ra đều được kiểm tra số hữu hạn và số cột thống nhất khi sinh.

## 7. Tài liệu phương pháp

- scikit-learn, Common pitfalls: https://scikit-learn.org/stable/common_pitfalls
- scikit-learn, Pipelines and composite estimators: https://scikit-learn.org/stable/modules/compose

Quyết định về gộp mã và giữ các giá trị đặc biệt dựa trên kết quả EDA và báo cáo
bài toán hiện có của dự án; không bổ sung cách diễn giải nghiệp vụ chưa kiểm chứng.
