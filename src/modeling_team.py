"""Ba phương án bổ sung và so sánh chung: python -m src.modeling_team."""
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from src.evaluation import (MANIFEST, bootstrap, confidence_interval, evaluate,
                            min_cost_threshold, paired_diff)
from src.modeling import DUMMY, HGB, LR, error_tables, load_data, md_table, model_specs, select_model
from src.preprocessing import DATA, FEATURES, SEED, TARGET, make_preprocessor

ROOT = Path(__file__).resolve().parents[1]
RF, SVM, NB = 'Random Forest', 'SVM RBF', 'Gaussian Naive Bayes'
SLUGS = {LR: 'logistic', HGB: 'hist_gradient_boosting', RF: 'random_forest',
         SVM: 'svm_rbf', NB: 'gaussian_nb', DUMMY: 'no_skill'}
FORMULAS = {
    RF: r'Điểm dự đoán là $s(x)=\frac{1}{T}\sum_{t=1}^{T}p_t(y=1\mid x)$, '
        r'với $T=200$ cây; mỗi cây chỉ xét một tập con ngẫu nhiên các đặc trưng tại mỗi nút.',
    SVM: r'Kernel $K(x,z)=\exp(-\gamma\|x-z\|^2)$; $C$ điều khiển đánh đổi giữa '
         r'biên rộng và lỗi trên train. Điểm $s(x)=\sum_i\alpha_i y_iK(x_i,x)+b$ '
         r'dùng nhãn nội bộ $y_i\in\{-1,+1\}$, trong khi nhãn dữ liệu vẫn là 0/1.',
    NB: r'Với lớp $c\in\{0,1\}$, $P(c\mid x)\propto P(c)\prod_j '
        r'\mathcal{N}(x_j;\mu_{cj},\sigma_{cj}^2)$. Prior, trung bình và phương sai '
        r'chỉ ước lượng trên phần train của mỗi fold; smoothing ổn định các phương sai nhỏ.',
}
DESIGNS = {
    RF: ('Random_Forest',
         'Tập hợp 200 cây được huấn luyện trên các mẫu bootstrap, lấy trung bình xác suất. '
         'Dùng tree_extended của Phần 2; max_features=sqrt, max_depth ∈ {8; None}, '
         'min_samples_leaf ∈ {5; 20}, seed=42. Giới hạn độ sâu/kích thước lá giúp giảm overfit. '
         'RF tạo các cây độc lập, khác cơ chế boosting tuần tự của HGB.',
         'Tốn bộ nhớ hơn mô hình tuyến tính; lưới nhỏ chưa khảo sát số cây/max_features. '
         'Các cây vẫn có thể khó mô hình hóa một số tương tác và chưa kiểm tra calibration.',
         'ensemble.RandomForestClassifier'),
    SVM: ('SVM_RBF',
          'SVM tìm biên phân lớp với kernel RBF để biểu diễn quan hệ phi tuyến. '
          'Dùng linear_extended của Phần 2 để log hóa và chuẩn hóa trong từng fold. '
          'C ∈ {0,1; 1; 10}, gamma=scale, class_weight=None. '
          'probability=False: dùng decision_function, điểm càng lớn càng nghiêng về lớp default=1. '
          'Không dùng hiệu chỉnh xác suất nội bộ để tránh một phép chia calibration không kiểm soát nhóm.',
          'Điểm decision_function không phải xác suất, không dùng ngưỡng lý thuyết 1/6. '
          'Huấn luyện và dự đoán chậm khi nhiều support vector; gamma chỉ dùng scale trong lưới này.',
          'svm.SVC'),
    NB: ('Gaussian_Naive_Bayes',
         'Gaussian Naive Bayes áp dụng Bayes với giả định các đặc trưng độc lập có điều kiện theo nhãn '
         'và mỗi đặc trưng có phân phối Gaussian trong từng lớp. Dùng linear_extended; '
         'var_smoothing ∈ {1e-9; 1e-7; 1e-5}. Prior học từ train, không cân bằng lớp bằng trọng số. '
         'Mô hình này tạo đối chứng xác suất đơn giản và huấn luyện nhanh.',
         'Dư nợ và thanh toán qua các tháng tương quan, vi phạm giả định độc lập. '
         'Biến one-hot không có phân phối Gaussian; vì vậy đây là một phương án đơn giản với '
         'giả định gần đúng và xác suất có thể chưa được hiệu chỉnh tốt.',
         'naive_bayes.GaussianNB'),
}


def additional_specs():
    return {
        RF: (Pipeline([('pre', make_preprocessor('tree', with_features=True)),
                       ('clf', RandomForestClassifier(n_estimators=200, max_features='sqrt',
                                                       n_jobs=2, random_state=SEED))]),
             {'clf__max_depth': [8, None], 'clf__min_samples_leaf': [5, 20]}),
        SVM: (Pipeline([('pre', make_preprocessor('linear', with_features=True)),
                        ('clf', SVC(kernel='rbf', gamma='scale', probability=False, cache_size=512,
                                    random_state=SEED))]), {'clf__C': [0.1, 1.0, 10.0]}),
        NB: (Pipeline([('pre', make_preprocessor('linear', with_features=True)), ('clf', GaussianNB())]),
             {'clf__var_smoothing': [1e-9, 1e-7, 1e-5]}),
    }


def model_scores(model, X):
    """Điểm hướng về default=1; SVM dùng margin, các mô hình khác dùng xác suất."""
    if not np.array_equal(model.classes_, [0, 1]):
        raise ValueError('Bộ phân loại phải có classes_=[0, 1].')
    if hasattr(model, 'predict_proba'):
        scores = model.predict_proba(X)[:, 1]
    else:
        scores = model.decision_function(X)
    scores = np.asarray(scores)
    if scores.shape != (len(X),) or not np.isfinite(scores).all():
        raise ValueError('Điểm dự đoán không hợp lệ.')
    return scores


def plot_team(test, scores, thresholds, folder):
    y = test[TARGET].to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for name, score in scores.items():
        PrecisionRecallDisplay.from_predictions(y, score, name=name, ax=axes[0])
        RocCurveDisplay.from_predictions(y, score, name=name, ax=axes[1])
    axes[0].axhline(y.mean(), color='gray', linestyle='--')
    for ax in axes:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(folder / '12_pr_roc.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    names = [n for n in scores if n != DUMMY]
    for ax, name in zip(axes.flat, names):
        ConfusionMatrixDisplay.from_predictions(y, scores[name] >= thresholds[name], ax=ax,
                                                colorbar=False, display_labels=['Non-default', 'Default'])
        ax.set_title(name)
    for ax in list(axes.flat)[len(names):]:
        ax.set_visible(False)
    fig.tight_layout()
    fig.savefig(folder / '12_confusion.png', dpi=160)
    plt.close(fig)


def write_team_reports(cv, test, ci, comparisons, selected, slices, profiles):
    intervals = ci.copy()
    intervals.columns = [f'{m} {q:.3f}' for m, q in intervals.columns]
    compact = test[['Mô hình', 'PR-AUC', 'ROC-AUC', 'Ngưỡng', 'Recall', 'Precision', 'Chi phí / KH', 'FP', 'FN']]
    links = []
    lr = test.set_index('Mô hình').loc[LR]
    for name, (slug, method, limitation, api) in DESIGNS.items():
        row = test.set_index('Mô hình').loc[name]
        worst = slices[slices['Mô hình'].eq(name)].nlargest(3, 'Chi phí / KH')
        profile = profiles[profiles['Mô hình'].eq(name)]
        by_error = profile.set_index('Loại lỗi')
        train_result = cv[cv['Mô hình'].eq(name)]
        discussion = (
            f"So với LR, chênh lệch AP mô tả là {row['PR-AUC'] - lr['PR-AUC']:+.4f}, "
            f"chênh lệch chi phí là {row['Chi phí / KH'] - lr['Chi phí / KH']:+.4f}. "
            f"Mô hình bỏ sót {row['FN']:.0f} khách vỡ nợ và cảnh báo nhầm {row['FP']:.0f} khách tốt. "
            f"Nhóm FN có trung bình {by_error.loc['FN', 'late_month_count']:.2f} tháng chậm trả, "
            f"so với {by_error.loc['TP', 'late_month_count']:.2f} ở TP. "
            'Đây là mô tả test, không phải kiểm định riêng mô hình này với LR; '
            'chỉ các cặp đã chốt trong báo cáo chung được diễn giải bằng paired bootstrap.'
        )
        report = f'''# Phương án thay thế: {name}

## Phương pháp và cấu hình

{method}

{FORMULAS[name]}

Tái sử dụng `clean_data`, `make_preprocessor`, manifest cố định của Phần 2–3. ID và nhãn bị loại khỏi X; mọi phép học tiền xử lý nằm trong pipeline của từng fold. Dùng cùng 5 fold StratifiedGroupKFold trên train, có nhóm hồ sơ, chọn cấu hình theo AP trung bình. Validation chỉ chọn ngưỡng nhỏ nhất của (5FN+FP)/n; dùng đúng ngưỡng đó cho test.

{md_table(train_result)}

## Kết quả và nhận xét

{md_table(compact[compact['Mô hình'].isin([LR, name])])}

{discussion}

Các chỉ số tại ngưỡng validation; chi phí dùng tỷ lệ giả định FN:FP=5:1, không phải tiền thực tế. Ngưỡng SVM là margin, ngưỡng các mô hình khác là xác suất đầu ra chưa được kiểm tra calibration.

## Phân tích lỗi theo nhóm

Ba lát cắt có chi phí cao nhất (có thể chồng nhau):

{md_table(worst[['Lát cắt', 'Nhóm', 'Số khách', 'Tỷ lệ vỡ nợ', 'PR-AUC', 'Recall', 'Precision', 'Chi phí / KH']])}

AP phải đối chiếu với tỷ lệ vỡ nợ của chính nhóm. Những nhóm ít mẫu có độ bất định lớn. Bảng mô tả theo giới tính không đủ để kết luận về tính công bằng.

{md_table(profile)}

## Hạn chế

{limitation}

Đợt bổ sung diễn ra sau khi kết quả test của LR/HGB đã được xem. Lưới ba mô hình mới được cố định trước khi tính test của chúng; không thay lưới sau khi xem test. Vì cùng test đã được dùng trong quá trình dự án, kết quả mở rộng mang tính khám phá, chưa phải xác nhận độc lập. Dữ liệu từ Đài Loan năm 2005, chưa đánh giá dịch chuyển theo thời gian, chưa nested CV, chưa ablation cùng bộ đặc trưng để tách ảnh hưởng thuật toán và feature engineering.

## Tái lập

Chạy `python -m src.modeling_team` từ gốc repo. Pipeline/điểm/ngưỡng lưu ở `outputs/team/{SLUGS[name]}.joblib`; dùng `model_scores(bundle['model'], X)` rồi so với `bundle['threshold']`. Đầu vào X là 23 cột FEATURES đã làm sạch, chưa chuẩn hóa. Không dùng `.predict()` mặc định vì ngưỡng của thực nghiệm được chọn riêng.

Nguồn thuật toán: https://scikit-learn.org/stable/modules/generated/sklearn.{api}.html

Dữ liệu: UCI Default of Credit Card Clients, DOI 10.24432/C55S3H, https://archive.ics.uci.edu/dataset/350.
'''
        (ROOT / f'reports/Bao_cao_{slug}.md').write_text(report, encoding='utf-8')
        links.append(f'- [{name}](Bao_cao_{slug}.md)')
    interpretation = []
    for metric, row in comparisons.iterrows():
        lo, hi = row['KTC 2,5%'], row['KTC 97,5%']
        if lo <= 0 <= hi:
            claim = 'chưa đủ bằng chứng khác biệt'
        elif (metric == 'PR-AUC' and lo > 0) or (metric == 'Chi phí / KH' and hi < 0):
            claim = 'cải thiện'
        else:
            claim = 'kém hơn'
        interpretation.append(f"- {row['A']} − {row['B']}, {metric}: {claim}; KTC [{lo:.4f}; {hi:.4f}].")
    report = f'''# So sánh chung: một phương án cơ sở và bốn phương án thay thế

## Phạm vi

Phần đã có: Logistic Regression (cơ sở) và HistGradientBoosting (thay thế của Hiệp). Bổ sung Random Forest, SVM RBF, Gaussian Naive Bayes cho ba phần còn lại. Sheet chưa gắn thuật toán cụ thể cho từng người nên báo cáo được tách theo mô hình để nhóm phân công bàn giao; không thay bảng tự đánh giá đóng góp.

{chr(10).join(links)}

## Quy trình chung

Giữ nguyên 20.976 train / 4.493 validation / 4.496 test theo manifest, kiểm tra nhóm không giao nhau. Tất cả năm mô hình chạy lại với cùng 5 fold theo nhóm; lưới LR/HGB giữ nguyên đợt trước. Train chọn cấu hình theo AP, validation chỉ chọn ngưỡng chi phí 5FN+FP, test chỉ tính sau khi chốt. Họ mô hình chọn theo CV: ưu tiên LR nếu khoảng cách tới AP tốt nhất nhỏ hơn một SD của mô hình tốt nhất, nếu không chọn AP CV cao nhất. Chưa đặt thứ tự độ phức tạp giữa các mô hình thay thế; không áp quy tắc đơn giản hóa tùy ý giữa chúng.

**Bối cảnh mở rộng:** kết quả test LR/HGB đã được quan sát ở đợt trước, trước khi người dùng yêu cầu thêm ba phương án. Do đó bảng mở rộng là kết quả khám phá trên test đã biết, không được gọi là kiểm định xác nhận trên test hoàn toàn chưa quan sát. Không thay siêu tham số theo kết quả test. Muốn xác nhận độc lập cần dữ liệu mới.

## Chọn cấu hình trên train

{md_table(cv)}

Họ mô hình được chọn bằng CV train: **{selected}**. Không chọn lại bằng bảng test. Thời gian fit là tổng thời gian tìm cấu hình và refit, phụ thuộc máy/mức song song; không dùng để so sánh tốc độ thuật toán một cách kiểm soát.

## Kết quả test

{md_table(compact)}

AP (Average Precision) và ROC-AUC chấp nhận điểm liên tục. Riêng SVM dùng decision_function, không phải xác suất, nên ngưỡng SVM không so trực tiếp với ngưỡng các mô hình khác. No-skill dùng tỷ lệ vỡ nợ train làm xác suất cố định. Không dùng Accuracy để chọn mô hình, và không dùng `.predict()` mặc định để tính các chỉ số tại ngưỡng thực nghiệm.

KTC percentile bootstrap 95% với 1.000 lần lấy mẫu theo khách hàng, giữ cố định mô hình/ngưỡng:

{md_table(intervals.reset_index())}

## Các cặp so sánh đã chốt theo CV

Chỉ so mô hình được chọn với no-skill và LR (nếu khác LR), theo quy định Phần 3. Không kiểm định mọi cặp. Hiệu số A−B: AP dương, chi phí âm là tốt hơn. Khoảng tin cậy này không loại bỏ ảnh hưởng của việc mở rộng thí nghiệm sau khi đã xem test cũ.

{md_table(comparisons.reset_index(names='Chỉ số'))}

{chr(10).join(interpretation)}

![Precision–Recall và ROC](figures/12_pr_roc.png)

![Ma trận nhầm lẫn tại ngưỡng validation](figures/12_confusion.png)

## Bàn giao và hạn chế

`reports/tables/12_*.csv` chứa toàn bộ cấu hình CV, kết quả, KTC, phân tích nhóm và TP/FN/FP/TN. `reports/team_modeling_metadata.json` ghi lựa chọn, lưới, hash dữ liệu/manifest và phiên bản. `outputs/team/*.joblib` chứa pipeline, loại điểm và ngưỡng; `test_scores.csv` chứa điểm theo ID, đều tự sinh và gitignore.

Các pipeline thay đổi cả họ mô hình lẫn đặc trưng (`linear_base` cho LR, extended cho bốn phương án còn lại), nên chưa tách ảnh hưởng feature engineering. Các hạn chế Phần 3 còn hiệu lực: nguồn năm 2005, EDA toàn bộ dữ liệu, chi phí 5:1 là giả định, không nested CV, bootstrap không phản ánh dao động tái huấn luyện hay chọn ngưỡng. GaussianNB có giả định phân phối gần đúng; SVM chưa hiệu chỉnh xác suất. Chưa đánh giá dữ liệu mới theo thời gian hoặc calibration.

Chạy `python -m src.modeling_team` sau khi cài requirements-modeling-lock.txt. Notebook `notebooks/ba_phuong_an_bo_sung.ipynb` gọi cùng mã nguồn để tránh hai bản triển khai lệch nhau. Chạy lại là tái lập, không phải đánh giá trên một test mới.
'''
    (ROOT / 'reports/Bao_cao_So_sanh_Tat_ca_Mo_hinh.md').write_text(report, encoding='utf-8')


def run():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    tab, fig, output = ROOT / 'reports/tables', ROOT / 'reports/figures', ROOT / 'outputs/team'
    for directory in [tab, fig, output]:
        directory.mkdir(parents=True, exist_ok=True)
    parts, groups = load_data()
    train, val, test = (parts[s] for s in ['train', 'validation', 'test'])
    specs = {**model_specs(), **additional_specs()}
    metadata = {'stage': 'expanded exploratory experiment after prior LR/HGB test results',
                'grid': {name: grid for name, (_, grid) in specs.items()}, 'seed': SEED,
                'raw_sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(),
                'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                'versions': {'python': platform.python_version(), 'sklearn': sklearn.__version__,
                             'pandas': pd.__version__, 'numpy': np.__version__}}
    # Ghi lưới trước cả CV và trước khi dự đoán test của các mô hình mới.
    (output / 'design.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    models, cv_rows, all_cv = {}, [], []
    for name, (pipeline, grid) in specs.items():
        print(f'CV train: {name}', flush=True)
        start = time.perf_counter()
        search = GridSearchCV(pipeline, grid, scoring={'AP': 'average_precision', 'ROC': 'roc_auc'},
                              refit='AP', cv=StratifiedGroupKFold(5, shuffle=True, random_state=SEED),
                              n_jobs=1, error_score='raise')
        search.fit(train[FEATURES], train[TARGET], groups=groups)
        elapsed = time.perf_counter() - start
        models[name] = search.best_estimator_
        results = pd.DataFrame(search.cv_results_)
        results.insert(0, 'Mô hình', name)
        all_cv.append(results)
        k = search.best_index_
        cv_rows.append({'Mô hình': name, 'CV AP mean': results.loc[k, 'mean_test_AP'],
                        'CV AP std': results.loc[k, 'std_test_AP'],
                        'CV ROC mean': results.loc[k, 'mean_test_ROC'],
                        'CV ROC std': results.loc[k, 'std_test_ROC'],
                        'Fit seconds': elapsed, 'Cấu hình': json.dumps(search.best_params_, sort_keys=True)})
        print(f"  AP CV={results.loc[k, 'mean_test_AP']:.4f}; {elapsed:.1f}s", flush=True)
    cv = pd.DataFrame(cv_rows)
    selected = select_model(cv)
    pairs = [[selected, DUMMY]] + ([[selected, LR]] if selected != LR else [])
    metadata.update({'selected_by_train_cv': selected, 'predeclared_comparisons': pairs,
                     'selection_rule': 'LR if gap to best AP < best AP fold SD; otherwise best AP',
                     'score_kinds': {name: 'decision_function' if name == SVM else 'predict_proba'
                                     for name in [*models, DUMMY]}})
    (ROOT / 'reports/team_modeling_metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    cv.to_csv(tab / '12_cv.csv', index=False)
    pd.concat(all_cv, ignore_index=True).to_csv(tab / '12_cv_all.csv', index=False)
    models[DUMMY] = DummyClassifier(strategy='prior').fit(train[FEATURES], train[TARGET])
    thresholds, val_rows = {}, []
    for name, model in models.items():
        score = model_scores(model, val[FEATURES])
        thresholds[name] = min_cost_threshold(val[TARGET], score)
        val_rows.append({'Mô hình': name, **evaluate(val[TARGET], score, thresholds[name])})
        joblib.dump({'model': model, 'threshold': thresholds[name], 'features': FEATURES,
                     'score_kind': metadata['score_kinds'][name]}, output / f'{SLUGS[name]}.joblib')
    print(f'Đã chốt {selected} bằng CV và ngưỡng bằng validation. Tính test.', flush=True)
    scores = {name: model_scores(model, test[FEATURES]) for name, model in models.items()}
    test_rows = pd.DataFrame([{'Mô hình': name, **evaluate(test[TARGET], score, thresholds[name])}
                              for name, score in scores.items()])
    boot = bootstrap(test[TARGET], scores, thresholds)
    ci = confidence_interval(boot)
    comparisons = pd.concat([paired_diff(boot, a, b).assign(A=a, B=b) for a, b in pairs])
    slices, profiles = error_tables(test, scores, thresholds)
    for stem, frame in {'test': test_rows, 'validation': pd.DataFrame(val_rows),
                        'error_slices': slices, 'error_profiles': profiles}.items():
        frame.to_csv(tab / f'12_{stem}.csv', index=False)
    ci.to_csv(tab / '12_confidence_intervals.csv')
    comparisons.to_csv(tab / '12_paired_comparisons.csv')
    pd.DataFrame({'ID': test.ID, TARGET: test[TARGET], **scores}).to_csv(output / 'test_scores.csv', index=False)
    plot_team(test, scores, thresholds, fig)
    write_team_reports(cv, test_rows, ci, comparisons, selected, slices, profiles)
    print(test_rows.to_string(index=False), flush=True)
    return {'cv': cv, 'test': test_rows, 'selected': selected, 'comparisons': comparisons}


if __name__ == '__main__':
    run()
