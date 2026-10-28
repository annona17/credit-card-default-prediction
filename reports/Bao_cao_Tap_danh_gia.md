# 3. Xây dựng tập đánh giá

Nhóm xây dựng khung đánh giá thống nhất trước khi phát triển mô hình, gồm cách phân chia dữ liệu, các chỉ số đánh giá, và quy trình thực nghiệm. Tất cả mô hình ở các chương sau đều được đánh giá theo khung này. Chương này không xây dựng mô hình phân loại; các mô hình cơ sở và mô hình đề xuất được trình bày ở các chương sau.

## 3.1. Phân chia dữ liệu

### 3.1.1. Vai trò của ba tập dữ liệu

Sau bước làm sạch ở chương 2, bộ dữ liệu [1] còn 29.965 khách hàng. Dữ liệu được chia thành ba tập với vai trò tách biệt:

- **Train** dùng để huấn luyện mô hình và chọn cấu hình bằng cross-validation.
- **Validation** chỉ dùng để chọn ngưỡng quyết định.
- **Test** chỉ dùng một lần để đánh giá cấu hình và ngưỡng đã chốt.

### 3.1.2. Ràng buộc nhóm

Một nhóm được định nghĩa là tập các khách hàng có giá trị trùng nhau trên toàn bộ 23 đặc trưng đầu vào, sau khi đã gộp mã `EDUCATION` và `MARRIAGE` ở chương 2. Sau làm sạch, dữ liệu có 21 nhóm gồm hai khách hàng; trong cả 21 nhóm, hai khách hàng có nhãn khác nhau. Ngoài ra, 35 dòng trùng cả đặc trưng lẫn nhãn đã bị loại ở bước làm sạch.

Phép chia bảo đảm mỗi nhóm nằm trọn trong một tập. Nếu không có ràng buộc này, một hồ sơ có thể nằm trong train trong khi hồ sơ trùng đặc trưng với nó nằm trong test, và mô hình sẽ được đánh giá trên một vector đặc trưng đã xuất hiện trong tập huấn luyện. Ràng buộc nhóm chỉ ngăn hiện tượng rò rỉ này; nó không giải quyết mâu thuẫn nhãn. Với hai hồ sơ có cùng đặc trưng nhưng khác nhãn, không mô hình nào chỉ dựa trên các đặc trưng này có thể phân loại đúng cả hai.

### 3.1.3. Quy trình tạo và cố định phép chia

Phép chia được tạo bằng `StratifiedGroupKFold` của scikit-learn [5] với 20 fold, `shuffle=True` và `random_state=42`. Lớp này phân tầng theo nhãn để các fold có tỷ lệ vỡ nợ xấp xỉ nhau, đồng thời xếp mỗi nhóm vào đúng một fold. Các fold được đánh số từ 0 đến 19 theo thứ tự được sinh ra và phân bổ như sau: fold 0–13 cho train, fold 14–16 cho validation và fold 17–19 cho test, tương ứng tỷ lệ xấp xỉ 70/15/15. Sau khi phân bổ, mã nguồn kiểm tra lại rằng không nhóm nào xuất hiện ở hai tập và mỗi tập đều có đủ hai lớp.

Thứ tự sinh fold phụ thuộc vào phiên bản thư viện. Khi chạy lại với scikit-learn 1.9.1, tập train có 20.977 khách hàng thay vì 20.976 và tỷ lệ vỡ nợ của test đổi từ 22,71% thành 22,14%. Vì vậy, nhóm cố định phép chia trong tệp `data/splits/split_manifest.csv`. Mỗi dòng của tệp ghi mã khách hàng, mã nhóm, số fold và tập tương ứng. Tệp này là nguồn phân chia duy nhất cho mọi thành viên. Mã tạo tệp nằm trong `src/preprocessing.py` và tái lập đúng phép chia khi dùng môi trường đã khóa phiên bản trong `requirements-lock.txt` (Python 3.9, pandas 2.3.3, scikit-learn 1.6.1).

**Bảng 3.1.** Ba tập dữ liệu dùng để đánh giá

| Tập | Fold | Số khách hàng | Số vỡ nợ | Tỷ lệ vỡ nợ |
|---|---|---:|---:|---:|
| Train | 0–13 | 20.976 | 4.608 | 21,97% |
| Validation | 14–16 | 4.493 | 1.001 | 22,28% |
| Test | 17–19 | 4.496 | 1.021 | 22,71% |
| Tổng | | 29.965 | 6.630 | 22,13% |

### 3.1.4. Kiểm tra mức cân bằng giữa ba tập

Nhóm so sánh tỷ trọng khách hàng giữa ba tập theo bốn tiêu chí: trạng thái trả nợ tháng 9/2005 (`PAY_0`), hạn mức tín dụng, nhóm tuổi và giới tính. Theo mô tả của bộ dữ liệu [1], `PAY_0` = −1 là thanh toán đúng hạn và `PAY_0` = k (k ≥ 1) là trễ hạn k tháng; các giá trị −2 và 0 có trong dữ liệu nhưng không được định nghĩa trong tài liệu gốc. Trong chương này, `PAY_0` được gộp thành bốn nhóm thống nhất: {−2, −1}, {0}, {1} và {≥ 2}.

Chênh lệch tỷ trọng lớn nhất giữa ba tập là 1,48 điểm phần trăm, ở nhóm `PAY_0` ∈ {−2, −1}; chênh lệch lớn thứ hai là 1,43 điểm phần trăm, ở nhóm tuổi 21–29. Các tỷ trọng này cho thấy ba tập có mức độ cân bằng tương đối trên bốn tiêu chí khảo sát. Tuy nhiên, kết quả chưa đủ để khẳng định toàn bộ phân bố dữ liệu giữa các tập là tương đương.

## 3.2. Chỉ số đánh giá

Các chỉ số được chia thành hai nhóm theo câu hỏi mà chúng trả lời: khả năng phân biệt của mô hình trên nhiều ngưỡng (mục 3.2.3) và hiệu quả của quyết định tại một ngưỡng cụ thể (mục 3.2.4).

### 3.2.1. Các đại lượng cơ sở

Mô hình gán cho mỗi khách hàng một điểm số $p$, được hiểu là xác suất vỡ nợ. Với ngưỡng $t$, khách hàng có $p \ge t$ được dự đoán là vỡ nợ (lớp dương). Đối chiếu với nhãn thật, mỗi khách hàng thuộc một trong bốn trường hợp: true positive (TP), false positive (FP), false negative (FN) và true negative (TN). Từ đó:

$$\text{Recall} = \frac{TP}{TP + FN}, \qquad
\text{FPR} = \frac{FP}{FP + TN}, \qquad
\text{Precision} = \frac{TP}{TP + FP}.$$

Recall và FPR được tính trong từng lớp thật; Precision được tính trên tập khách hàng được dự đoán là vỡ nợ.

### 3.2.2. Hạn chế của Accuracy

Dữ liệu mất cân bằng, với tỷ lệ vỡ nợ khoảng 22%. Bảng 3.2 so sánh hai quy tắc quyết định không dùng đặc trưng nào trên tập test. Quy tắc không cảnh báo khách hàng nào có Accuracy cao hơn nhưng có expected cost (định nghĩa ở mục 3.2.4) cao hơn quy tắc cảnh báo toàn bộ khách hàng. Ví dụ này cho thấy Accuracy có thể đánh giá sai mức độ hữu ích của một quyết định khi chi phí của hai loại lỗi khác nhau.

**Bảng 3.2.** Hai quy tắc quyết định không dùng đặc trưng trên tập test

| Quy tắc | Accuracy | Recall | Expected cost |
|---|---:|---:|---:|
| Không cảnh báo khách hàng nào | 77,3% | 0,0% | 1,135 |
| Cảnh báo toàn bộ khách hàng | 22,7% | 100,0% | 0,773 |

Do đó, Accuracy chỉ được báo cáo để mô tả, không dùng để xếp hạng mô hình.

### 3.2.3. Chỉ số đánh giá khả năng phân biệt

Khi ngưỡng giảm dần từ 1 về 0, mỗi ngưỡng cho một điểm (FPR, Recall) trên đường ROC và một điểm (Recall, Precision) trên đường Precision–Recall. Hai chỉ số tóm tắt hai đường cong này là:

- **ROC-AUC**: diện tích dưới đường ROC, bằng xác suất một khách hàng vỡ nợ chọn ngẫu nhiên có điểm số cao hơn một khách hàng không vỡ nợ chọn ngẫu nhiên (tính một nửa khi bằng điểm).
- **PR-AUC (AP)**: nhóm dùng Average Precision (`average_precision_score` [5]), được định nghĩa ở dưới.

Average Precision là tổng có trọng số của Precision theo mức tăng Recall:

$$\text{AP} = \sum_k (R_k - R_{k-1})\, P_k,$$

trong đó $P_k$ và $R_k$ là Precision và Recall tại ngưỡng thứ $k$. AP không dùng phép nội suy hình thang như khi tính diện tích thông thường. Trong báo cáo, "PR-AUC" được hiểu là AP.

ROC-AUC và PR-AUC tổng hợp khả năng phân biệt của mô hình trên nhiều ngưỡng, do đó không phụ thuộc vào một ngưỡng quyết định cụ thể. Giá trị của chúng vẫn phụ thuộc vào tập dữ liệu đánh giá; riêng PR-AUC còn phụ thuộc vào tỷ lệ giữa hai lớp.

Sự phụ thuộc này đến từ trục Precision. FPR chỉ tính trên các khách hàng không vỡ nợ nên không phụ thuộc tỷ lệ vỡ nợ $\pi$, còn Precision thì phụ thuộc [3]:

$$\text{Precision} = \frac{\text{Recall}\cdot\pi}{\text{Recall}\cdot\pi + \text{FPR}\cdot(1-\pi)}.$$

Bảng 3.3 áp dụng công thức trên cho một mô hình giả định có Recall và FPR cố định; đây không phải kết quả thực nghiệm của một mô hình đã huấn luyện. Điểm (FPR, Recall) của mô hình không đổi, nhưng Precision giảm mạnh khi $\pi$ giảm. Cũng vì vậy, một bộ phân loại không có khả năng phân biệt có PR-AUC bằng $\pi$, còn ROC-AUC luôn bằng 0,5.

**Bảng 3.3.** Precision của một mô hình giả định theo tỷ lệ vỡ nợ

| Tỷ lệ vỡ nợ $\pi$ | Recall | FPR | Precision |
|---:|---:|---:|---:|
| 22,7% (tập test) | 0,500 | 0,150 | 0,495 |
| 5,6% | 0,500 | 0,150 | 0,165 |
| 2,9% | 0,500 | 0,150 | 0,091 |

Trong bài toán cảnh báo vỡ nợ, khách hàng vỡ nợ là lớp thiểu số và là lớp cần phát hiện, nên nhóm chọn **PR-AUC (AP) làm chỉ số chính cho khả năng phân biệt**. ROC-AUC được báo cáo làm chỉ số phụ để đối chiếu với các nghiên cứu khác. Vì PR-AUC phụ thuộc $\pi$, các mô hình chỉ được so sánh trên cùng một tập test.

### 3.2.4. Chỉ số đánh giá hiệu quả quyết định

Khi áp dụng mô hình, cần một ngưỡng cụ thể, và hai loại lỗi có hậu quả khác nhau. Nhóm giả định bỏ sót một khách hàng vỡ nợ (FN) gây thiệt hại gấp 5 lần từ chối nhầm một khách hàng tốt (FP). Tỷ lệ 5 : 1 là giả định phục vụ thực nghiệm, không phải một tỷ lệ chi phí phổ quát của bài toán cho vay. Mục này phân biệt bốn khái niệm liên quan.

**Chi phí tương đối của hai loại lỗi.** $\lambda_{FN} = 5$, $\lambda_{FP} = 1$.

**Expected cost.** Chi phí trung bình trên mỗi khách hàng của một tập dữ liệu:

$$C = \frac{5 \cdot FN + 1 \cdot FP}{n},$$

với $n$ là số khách hàng của tập. $C$ được đo bằng đơn vị tương đối, một đơn vị là chi phí của một FP. Expected cost là **chỉ số chính cho hiệu quả quyết định**.

**Ngưỡng lý thuyết.** Với một khách hàng có xác suất vỡ nợ $p$, thiệt hại kỳ vọng khi cảnh báo là $(1-p)\lambda_{FP}$, khi không cảnh báo là $p\lambda_{FN}$. Theo quy tắc rủi ro tối thiểu Bayes [2], khách hàng được xếp vào lớp vỡ nợ khi

$$P(\text{vỡ nợ} \mid x) > \frac{\lambda_{FP}}{\lambda_{FP} + \lambda_{FN}} = \frac{1}{6} \approx 0{,}167.$$

**Ngưỡng thực nghiệm.** Ngưỡng lý thuyết chỉ tối ưu khi xác suất dự đoán được hiệu chỉnh tốt (calibrated). Vì vậy, ngưỡng của mỗi mô hình được chọn trên tập validation là giá trị cho expected cost nhỏ nhất, xét mọi giá trị điểm số xuất hiện trên validation và phương án không cảnh báo khách hàng nào. Ngưỡng này được giữ nguyên khi đánh giá trên tập test.

F1 không được dùng để chọn ngưỡng vì $F1 = 2TP / (2TP + FP + FN)$ đặt trọng số bằng nhau cho FP và FN, mâu thuẫn với giả định 5 : 1. Nếu tỷ lệ chi phí thay đổi, ngưỡng tối ưu và thứ hạng các mô hình theo expected cost cũng có thể thay đổi.

**Bảng 3.4.** Vai trò của các chỉ số

| Khía cạnh | Chỉ số | Vai trò |
|---|---|---|
| Khả năng phân biệt | PR-AUC (AP) | Chỉ số chính |
| | ROC-AUC | Chỉ số phụ, đối chiếu với nghiên cứu khác |
| Hiệu quả quyết định | Expected cost | Chỉ số chính, dùng để chọn ngưỡng |
| | Recall, Precision, F1, Accuracy | Mô tả kết quả tại ngưỡng đã chọn |

## 3.3. Quy trình thực nghiệm

### 3.3.1. Các bước đánh giá một mô hình

1. **Chọn cấu hình bằng cross-validation trên train.** Dùng `StratifiedGroupKFold` 5 fold với nhóm lấy từ `split_manifest.csv`, nên các fold tuân thủ cùng ràng buộc nhóm như phép chia ở mục 3.1. Bước tiền xử lý nằm trong pipeline cùng bộ phân loại, nên các tham số của nó (ví dụ trung bình và độ lệch chuẩn khi chuẩn hóa) được ước lượng lại trên phần huấn luyện của từng fold. Mọi việc dò siêu tham số chỉ diễn ra ở bước này.
2. **Huấn luyện lại** cấu hình đã chọn trên toàn bộ train.
3. **Chọn ngưỡng trên validation** theo expected cost nhỏ nhất (mục 3.2.4). Validation không được dùng cho quyết định nào khác.
4. **Đánh giá một lần trên test** với cấu hình và ngưỡng đã chốt.
5. **Ước lượng khoảng tin cậy** bằng bootstrap (mục 3.3.2) và **so sánh mô hình** theo các nguyên tắc ở mục 3.3.3.

Kết quả cross-validation (trung bình ± độ lệch chuẩn của PR-AUC và ROC-AUC trên 5 fold) có hai mục đích khác nhau. Trong bước dò siêu tham số, nó là tiêu chí lựa chọn. Khi nhiều cấu hình được thử và cấu hình có CV PR-AUC cao nhất được chọn, chính giá trị CV đó là ước lượng lạc quan của hiệu năng. Vì vậy, báo cáo dùng kết quả trên tập test làm ước lượng hiệu năng tổng quát hóa; giá trị CV chỉ được báo cáo để mô tả quá trình lựa chọn và độ ổn định giữa các fold. Nhóm không triển khai nested cross-validation và ghi nhận điều này ở mục 3.5.

### 3.3.2. Khoảng tin cậy bootstrap

Chỉ số đo trên tập test là ước lượng từ một mẫu hữu hạn 4.496 khách hàng. Để định lượng độ bất định do lấy mẫu, nhóm dùng **khoảng tin cậy percentile bootstrap 95%** [4]:

1. Lấy mẫu có hoàn lại 4.496 khách hàng từ tập test.
2. Tính lại chỉ số trên mẫu này, giữ nguyên điểm số của mô hình và ngưỡng đã chọn trên validation.
3. Lặp lại $B = 1.000$ lần. Khoảng tin cậy được xác định bởi phân vị 2,5% và 97,5% của phân bố thực nghiệm gồm 1.000 giá trị thu được.

Đơn vị lấy mẫu là khách hàng, với giả định các khách hàng trong tập test là các quan sát độc lập. Các cặp hồ sơ trùng đặc trưng có thể vi phạm một phần giả định này, nhưng tập test chỉ chứa 5 cặp (10 trên 4.496 khách hàng), nên nhóm chọn bootstrap theo khách hàng thay vì theo nhóm. Khoảng tin cậy phản ánh độ bất định của ước lượng trên tập test dưới các giả định của phương pháp, không làm cho ước lượng trở nên chính xác hơn.

### 3.3.3. So sánh các mô hình

Các chương sau đánh giá nhiều mô hình học máy. Khi số mô hình lớn, hai rủi ro cần tránh là chọn mô hình dựa trên tập test và thực hiện quá nhiều phép so sánh. Với $m$ mô hình có $m(m-1)/2$ cặp; mỗi phép so sánh ở mức tin cậy 95% đều có khả năng cho kết luận sai do ngẫu nhiên, nên khi so sánh mọi cặp, số kết luận sai kỳ vọng tăng theo số cặp (vấn đề so sánh bội). Vì vậy, nhóm quy định bốn nguyên tắc sau.

**Chọn mô hình không dùng tập test.** Mô hình được chọn là mô hình có CV PR-AUC cao nhất trên train. Nếu chênh lệch CV PR-AUC giữa mô hình này và một mô hình đơn giản hơn nhỏ hơn một độ lệch chuẩn giữa các fold, mô hình đơn giản hơn được ưu tiên.

**Báo cáo mọi mô hình trên tập test để mô tả.** Mỗi mô hình được báo cáo PR-AUC, ROC-AUC và expected cost trên test, kèm khoảng tin cậy 95% (mục 3.3.2), trong một bảng chung. Bảng này không được dùng để chọn lại mô hình.

**Chỉ thực hiện một số phép so sánh định trước.** Với hai mô hình A và B, nhóm xét hai hiệu số trên tập test:

$$\Delta_{\text{AP}} = \text{AP}_A - \text{AP}_B, \qquad \Delta_C = C_A - C_B.$$

Hai hiệu số được ước lượng bằng **paired bootstrap**: ở mỗi lần lặp, cùng một mẫu khách hàng được dùng để tính chỉ số của cả hai mô hình rồi lấy hiệu. Việc dùng chung mẫu giúp kiểm soát một phần biến động do lấy mẫu, nên phép so sánh nhạy hơn việc đối chiếu hai khoảng tin cậy riêng lẻ. Phép so sánh này chỉ áp dụng cho các cặp được xác định trước khi xem kết quả test:

- mô hình được chọn so với no-skill baseline (bộ phân loại gán cho mọi khách hàng xác suất bằng tỷ lệ vỡ nợ của train), để kiểm tra mô hình có khai thác được thông tin từ dữ liệu;
- mô hình được chọn so với mô hình cơ sở đơn giản nhất (logistic regression), để kiểm tra mức phức tạp tăng thêm có mang lại cải thiện.

**Diễn giải kết quả.** Nếu khoảng tin cậy 95% của $\Delta_{\text{AP}}$ nằm hoàn toàn trên 0, có bằng chứng thống kê rằng A có PR-AUC cao hơn B; nếu khoảng tin cậy của $\Delta_C$ nằm hoàn toàn dưới 0, A có expected cost thấp hơn B. Hai hiệu số được xét riêng, vì khả năng phân biệt và hiệu quả quyết định là hai khía cạnh khác nhau. Nếu khoảng tin cậy chứa 0, chưa đủ bằng chứng để kết luận hai mô hình khác nhau theo chỉ số đó, và mô hình đơn giản hơn được ưu tiên.

## 3.4. Phương pháp phân tích lỗi

Ngoài các chỉ số tổng thể, mỗi mô hình ở các chương sau được phân tích lỗi theo hai cách.

**Theo nhóm khách hàng.** PR-AUC, Recall, Precision và expected cost được tính trên từng nhóm của bốn tiêu chí ở mục 3.1.4. Nhóm có Recall thấp hoặc expected cost cao cho biết nơi mô hình cần cải thiện. Tiêu chí giới tính được sử dụng để khảo sát sự khác biệt về hiệu quả dự đoán giữa hai nhóm giới tính. Các kết quả được diễn giải trong bối cảnh khác biệt về tỷ lệ vỡ nợ và phân bố dữ liệu giữa các nhóm; nhóm không đưa ra kết luận về tính công bằng, vì điều đó đòi hỏi một tiêu chí công bằng xác định và đánh giá chênh lệch kèm độ bất định.

Khi đọc kết quả theo nhóm, cần lưu ý hai điểm. Thứ nhất, mức PR-AUC của bộ phân loại không có khả năng phân biệt trong mỗi nhóm bằng tỷ lệ vỡ nợ của chính nhóm đó, và tỷ lệ này khác nhau đáng kể giữa các nhóm (Bảng 3.5). Vì vậy PR-AUC của từng nhóm được đối chiếu với tỷ lệ vỡ nợ của nhóm, không so trực tiếp giữa các nhóm. Thứ hai, một số nhóm có ít khách hàng vỡ nợ (ví dụ 108 khách hàng ở nhóm tuổi ≥ 50), nên chỉ số của các nhóm này có độ bất định lớn.

**Theo loại lỗi.** Nhóm so sánh giá trị trung bình của các đặc trưng (hạn mức, tuổi, trạng thái trả nợ, số tháng trễ hạn, mức sử dụng hạn mức, số tháng không thanh toán) giữa bốn nhóm TP, FN, FP và TN, để xác định đặc điểm của các khách hàng bị bỏ sót hoặc bị cảnh báo nhầm.

**Bảng 3.5.** Số khách hàng và tỷ lệ vỡ nợ theo nhóm trên tập test

| Tiêu chí | Nhóm | Số khách hàng | Số vỡ nợ | Tỷ lệ vỡ nợ |
|---|---|---:|---:|---:|
| `PAY_0` | {−2, −1} | 1.274 | 211 | 16,6% |
| | {0} | 2.183 | 281 | 12,9% |
| | {1} | 544 | 179 | 32,9% |
| | {≥ 2} | 495 | 350 | 70,7% |
| Hạn mức (NT$) | ≤ 50.000 | 1.149 | 351 | 30,5% |
| | (50.000; 100.000] | 721 | 195 | 27,0% |
| | (100.000; 180.000] | 920 | 194 | 21,1% |
| | (180.000; 270.000] | 814 | 143 | 17,6% |
| | > 270.000 | 892 | 138 | 15,5% |
| Tuổi | 21–29 | 1.446 | 341 | 23,6% |
| | 30–39 | 1.673 | 338 | 20,2% |
| | 40–49 | 960 | 234 | 24,4% |
| | ≥ 50 | 417 | 108 | 25,9% |
| Giới tính | Nam | 1.770 | 446 | 25,2% |
| | Nữ | 2.726 | 575 | 21,1% |

## 3.5. Hạn chế

- **Khả năng khái quát theo thời gian.** Mọi khách hàng có cùng giai đoạn quan sát (4–9/2005) và nhãn tháng 10/2005, và phép chia được thực hiện theo khách hàng. Kết quả không trực tiếp cho thấy mô hình dự đoán tốt trong các giai đoạn kinh tế khác.
- **Tập test đã được quan sát ở bước phân tích dữ liệu.** Chương 1 phân tích mô tả trên toàn bộ dữ liệu, kể cả các khách hàng thuộc tập test. Tập test không được dùng để chọn mô hình, cấu hình hay ngưỡng, nên hạn chế này không đồng nghĩa với rò rỉ nhãn vào huấn luyện; tuy vậy, các quyết định thiết kế đặc trưng có thể đã chịu ảnh hưởng gián tiếp.
- **Tỷ lệ chi phí 5 : 1 là giả định.** Ngưỡng được chọn và thứ hạng các mô hình theo expected cost có thể thay đổi nếu dùng tỷ lệ chi phí khác.
- **Kích thước tập test.** Với 4.496 khách hàng (1.021 vỡ nợ), độ bất định của PR-AUC trên test không nhỏ; chênh lệch nhỏ giữa các mô hình cần được kiểm tra bằng paired bootstrap trước khi kết luận.
- **Khoảng tin cậy chưa phản ánh toàn bộ quy trình.** Khoảng tin cậy được tính trên test với mô hình và ngưỡng đã cố định, nên không phản ánh dao động do chọn siêu tham số, huấn luyện lại mô hình hay chọn ngưỡng trên các tập validation khác.
- **Không dùng nested cross-validation.** Giá trị CV của cấu hình được chọn là ước lượng lạc quan; ước lượng hiệu năng tổng quát hóa dựa trên tập test.

## Tài liệu tham khảo

[1] I.-C. Yeh, "Default of Credit Card Clients," UCI Machine Learning Repository, 2016. DOI: 10.24432/C55S3H.

[2] R. O. Duda, P. E. Hart, D. G. Stork, *Pattern Classification*, 2nd ed., Wiley, 2001.

[3] T. Saito, M. Rehmsmeier, "The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets," *PLOS ONE*, vol. 10, no. 3, e0118432, 2015.

[4] B. Efron, R. J. Tibshirani, *An Introduction to the Bootstrap*, Chapman & Hall, 1993.

[5] F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," *Journal of Machine Learning Research*, vol. 12, pp. 2825–2830, 2011.
