"""Phần của Hiệp: python -m src.modeling. Dùng nguyên khung đánh giá Phần 3."""
import hashlib
import json
import platform
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.pipeline import Pipeline

from src.evaluation import (MANIFEST, REFERENCE_SPLIT, SLICES, bootstrap, confidence_interval,
                            evaluate, load_split, min_cost_threshold, paired_diff, split_table)
from src.preprocessing import DATA, FEATURES, SEED, TARGET, add_features, clean_data, make_preprocessor

ROOT = Path(__file__).resolve().parents[1]
LR, HGB, DUMMY = 'Logistic Regression', 'HistGradientBoosting', 'No-skill'


def load_data():
    clean, groups, _, _ = clean_data(pd.read_excel(DATA, header=1))
    manifest = pd.read_csv(MANIFEST)
    if not manifest.ID.is_unique or set(manifest.ID) != set(clean.ID):
        raise ValueError('Manifest phải bao phủ đúng mỗi ID đã làm sạch một lần.')
    if not manifest['split'].isin(REFERENCE_SPLIT).all():
        raise ValueError('Tên tập không hợp lệ trong manifest.')
    group_split = pd.DataFrame({'group': groups, 'split': clean.ID.map(manifest.set_index('ID')['split'])})
    if group_split.groupby('group')['split'].nunique().max() != 1:
        raise ValueError('Hồ sơ trùng đặc trưng xuất hiện ở nhiều tập.')
    parts = load_split(clean)
    summary = split_table(parts)
    for name, counts in REFERENCE_SPLIT.items():
        if tuple(summary.loc[name, ['Số mẫu', 'Số vỡ nợ']]) != counts:
            raise ValueError(f'Tập {name} không khớp chuẩn Phần 3.')
    # Dùng chính nhóm sau làm sạch, căn hàng theo train; không đưa ID vào X.
    return parts, groups.loc[parts['train'].index].to_numpy()


def model_specs():
    return {
        LR: (Pipeline([('pre', make_preprocessor('linear', with_features=False)),
                       ('clf', LogisticRegression(max_iter=3000, random_state=SEED))]),
             {'clf__C': [0.1, 1.0, 10.0]}),
        HGB: (Pipeline([('pre', make_preprocessor('tree', with_features=True)),
                        ('clf', HistGradientBoostingClassifier(max_iter=150, learning_rate=0.1,
                                                              early_stopping=False, random_state=SEED))]),
              {'clf__max_leaf_nodes': [7, 15], 'clf__l2_regularization': [0.0, 10.0]}),
    }


def select_model(cv_rows):
    """Quy tắc Phần 3: ưu tiên LR nếu kém mô hình tốt nhất ít hơn 1 SD của mô hình tốt nhất."""
    best = cv_rows.loc[cv_rows['CV AP mean'].idxmax()]
    lr = cv_rows.loc[cv_rows['Mô hình'].eq(LR)].iloc[0]
    return LR if best['CV AP mean'] - lr['CV AP mean'] < best['CV AP std'] else best['Mô hình']


def error_tables(test, probs, thresholds):
    slices, profiles = [], []
    engineered = add_features(test[FEATURES])
    columns = ['LIMIT_BAL', 'AGE', 'PAY_0', 'late_month_count', 'utilization_sep', 'zero_payment_count']
    y = test[TARGET].to_numpy()
    for name, p in probs.items():
        if name == DUMMY:
            continue
        for criterion, make in SLICES.items():
            labels = make(test)
            for label in labels.dropna().unique():
                mask = labels.eq(label).to_numpy()
                metrics = evaluate(y[mask], p[mask], thresholds[name]) if np.unique(y[mask]).size == 2 else {}
                slices.append({'Mô hình': name, 'Lát cắt': criterion, 'Nhóm': str(label),
                               'Số khách': int(mask.sum()), 'Tỷ lệ vỡ nợ': float(y[mask].mean()), **metrics})
        pred = p >= thresholds[name]
        kind = np.where(y == 1, np.where(pred, 'TP', 'FN'), np.where(pred, 'FP', 'TN'))
        for label in ['TP', 'FN', 'FP', 'TN']:
            mask = kind == label
            profiles.append({'Mô hình': name, 'Loại lỗi': label, 'Số khách': int(mask.sum()),
                             **engineered.loc[mask, columns].mean().to_dict()})
    return pd.DataFrame(slices), pd.DataFrame(profiles)


def plot_results(test, probs, thresholds, folder):
    y = test[TARGET].to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for name, p in probs.items():
        PrecisionRecallDisplay.from_predictions(y, p, name=name, ax=axes[0])
        RocCurveDisplay.from_predictions(y, p, name=name, ax=axes[1])
    axes[0].axhline(y.mean(), color='gray', linestyle='--', label='Test prevalence')
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(folder / '11_pr_roc.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, name in zip(axes, [LR, HGB]):
        ConfusionMatrixDisplay.from_predictions(y, probs[name] >= thresholds[name],
                                                display_labels=['Non-default', 'Default'],
                                                ax=ax, colorbar=False)
        ax.set_title(name)
    fig.tight_layout()
    fig.savefig(folder / '11_confusion.png', dpi=160)
    plt.close(fig)


def run():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    tab, fig, output = ROOT / 'reports/tables', ROOT / 'reports/figures', ROOT / 'outputs/hiep'
    for directory in [tab, fig, output]:
        directory.mkdir(parents=True, exist_ok=True)
    parts, groups = load_data()
    train, val, test = (parts[s] for s in ['train', 'validation', 'test'])
    models, cv_records, all_cv = {}, [], []
    for name, (pipeline, grid) in model_specs().items():
        print(f'CV trên train: {name}', flush=True)
        search = GridSearchCV(pipeline, grid, scoring={'AP': 'average_precision', 'ROC': 'roc_auc'},
                              refit='AP', cv=StratifiedGroupKFold(5, shuffle=True, random_state=SEED),
                              n_jobs=1, error_score='raise', return_train_score=False)
        search.fit(train[FEATURES], train[TARGET], groups=groups)
        models[name] = search.best_estimator_
        result = pd.DataFrame(search.cv_results_)
        result.insert(0, 'Mô hình', name)
        all_cv.append(result)
        k = search.best_index_
        cv_records.append({'Mô hình': name, 'CV AP mean': result.loc[k, 'mean_test_AP'],
                           'CV AP std': result.loc[k, 'std_test_AP'],
                           'CV ROC mean': result.loc[k, 'mean_test_ROC'],
                           'CV ROC std': result.loc[k, 'std_test_ROC'],
                           'Cấu hình': json.dumps(search.best_params_, sort_keys=True)})
    cv_rows = pd.DataFrame(cv_records)
    selected = select_model(cv_rows)
    # Chốt họ mô hình trước khi tính bất kỳ chỉ số validation/test nào.
    selection = {'selected_by_train_cv': selected, 'seed': SEED,
                 'selection_rule': 'LR if gap to best CV AP < best CV AP SD; otherwise best CV AP',
                 'predeclared_comparisons': [[selected, DUMMY]] + ([[selected, LR]] if selected != LR else []),
                 'raw_sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(),
                 'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                 'versions': {'python': platform.python_version(), 'sklearn': sklearn.__version__,
                              'pandas': pd.__version__, 'numpy': np.__version__}}
    (output / 'selection.json').write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'reports/modeling_metadata.json').write_text(
        json.dumps(selection, ensure_ascii=False, indent=2), encoding='utf-8')
    models[DUMMY] = DummyClassifier(strategy='prior').fit(train[FEATURES], train[TARGET])
    thresholds, val_rows = {}, []
    for name, model in models.items():
        p = model.predict_proba(val[FEATURES])[:, 1]
        thresholds[name] = min_cost_threshold(val[TARGET], p)
        val_rows.append({'Mô hình': name, **evaluate(val[TARGET], p, thresholds[name])})
        joblib.dump({'model': model, 'threshold': thresholds[name], 'features': FEATURES},
                    output / ({LR: 'logistic', HGB: 'hist_gradient_boosting', DUMMY: 'no_skill'}[name] + '.joblib'))
    print(f'Đã chốt mô hình {selected} và ngưỡng trên validation. Đánh giá test.', flush=True)
    probs = {name: model.predict_proba(test[FEATURES])[:, 1] for name, model in models.items()}
    test_rows = pd.DataFrame([{'Mô hình': name, **evaluate(test[TARGET], p, thresholds[name])}
                              for name, p in probs.items()])
    boot = bootstrap(test[TARGET], probs, thresholds)
    ci = confidence_interval(boot)
    comparisons = pd.concat([paired_diff(boot, a, b).assign(A=a, B=b)
                             for a, b in selection['predeclared_comparisons']])
    slices, profiles = error_tables(test, probs, thresholds)
    tables = {'11_cv': cv_rows, '11_cv_all': pd.concat(all_cv, ignore_index=True),
              '11_validation': pd.DataFrame(val_rows), '11_test': test_rows,
              '11_error_slices': slices, '11_error_profiles': profiles}
    for filename, frame in tables.items():
        frame.to_csv(tab / f'{filename}.csv', index=False)
    ci.to_csv(tab / '11_confidence_intervals.csv')
    comparisons.to_csv(tab / '11_paired_comparisons.csv')
    pd.DataFrame({'ID': test.ID, 'default': test[TARGET], **probs}).to_csv(output / 'test_predictions.csv', index=False)
    plot_results(test, probs, thresholds, fig)
    write_report(cv_rows, test_rows, ci, comparisons, selected, slices, profiles)
    print(test_rows.to_string(index=False), flush=True)
    return {'cv': cv_rows, 'test': test_rows, 'selected': selected, 'comparisons': comparisons}


def md_table(frame):
    """Không yêu cầu thêm tabulate."""
    view = frame.copy()
    for c in view.select_dtypes(include='number'):
        view[c] = view[c].map(lambda v: f'{v:.4f}')
    return '| ' + ' | '.join(map(str, view.columns)) + ' |\n| ' + ' | '.join(['---'] * len(view.columns)) + ' |\n' + '\n'.join(
        '| ' + ' | '.join(map(str, row)) + ' |' for row in view.itertuples(index=False, name=None))


def write_report(cv, test, ci, comparison, selected, slices, profiles):
    scores = test.set_index('Mô hình')
    lr, hgb = scores.loc[LR], scores.loc[HGB]
    worst = slices[slices['Mô hình'].eq(selected)].nlargest(3, 'Chi phí / KH')
    intervals = ci.copy()
    intervals.columns = [f'{metric} {q:.3f}' for metric, q in intervals.columns]
    findings = []
    for metric, row in comparison.iterrows():
        lo, hi = row['KTC 2,5%'], row['KTC 97,5%']
        if lo <= 0 <= hi:
            conclusion = 'chưa đủ bằng chứng về khác biệt (KTC chứa 0)'
        elif (metric == 'PR-AUC' and lo > 0) or (metric == 'Chi phí / KH' and hi < 0):
            conclusion = 'có bằng chứng cải thiện'
        else:
            conclusion = 'có bằng chứng kém hơn'
        findings.append(f"- {row['A']} so với {row['B']}, {metric}: {conclusion}; KTC [{lo:.4f}; {hi:.4f}].")
    interpretation = '\n'.join(findings)
    chosen_profiles = profiles[profiles['Mô hình'].eq(selected)].set_index('Loại lỗi')
    fn_profile, tp_profile = chosen_profiles.loc['FN'], chosen_profiles.loc['TP']
    text = f'''# 4–5. Phương án cơ sở và phương án thay thế — Nguyễn Hoàng Hiệp

## Kế thừa kết quả nhóm

Dùng dữ liệu gốc UCI [1], `clean_data`, `make_preprocessor` của Phần 2 và manifest cố định cùng hàm đánh giá của Phần 3. Không chia lại dữ liệu: train 20.976, validation 4.493, test 4.496. ID và nhãn không nằm trong đầu vào. Chuẩn hóa chỉ fit trên train của từng fold. Ràng buộc nhóm được kiểm tra lại trước khi chạy.

## 4. Phương án cơ sở: Logistic Regression

Logistic Regression mô hình hóa log-odds vỡ nợ như tổ hợp tuyến tính của đặc trưng, dùng regularization L2 [2]. Mô hình dễ tái lập và là mốc cơ sở đã quy định ở Phần 3. Dùng 23 biến gốc qua `linear_base`: gộp mã danh mục theo Phần 2, one-hot, log số tiền dương, signed-log hóa dư nợ, rồi chuẩn hóa. Thử C ∈ {{0,1; 1; 10}} bằng CV 5 fold theo nhóm trên train, chọn AP trung bình cao nhất. Không cân bằng lớp bằng trọng số; bất đối xứng chi phí được xử lý bằng ngưỡng validation.

## 5. Phương án thay thế: HistGradientBoosting

Mô hình cộng tuần tự các cây quyết định để giảm log-loss, biểu diễn được quan hệ phi tuyến và tương tác giữa đặc trưng [3]. Dùng `tree_extended` của nhóm, bổ sung sáu đặc trưng hành vi, không chuẩn hóa. Giữ learning_rate=0,1, max_iter=150, thử max_leaf_nodes ∈ {{7; 15}}, l2_regularization ∈ {{0; 10}}. Tắt early stopping để không tạo thêm phép chia ngẫu nhiên thiếu ràng buộc nhóm. Đây là so sánh hai pipeline hoàn chỉnh; thay đổi đồng thời họ mô hình và tập đặc trưng nên chưa tách riêng đóng góp của sáu biến bổ sung.

## Thiết kế thực nghiệm và chọn mô hình

Hai lưới tham số được cố định trước khi xem test. Dùng StratifiedGroupKFold(5, shuffle=True, random_state=42). Mỗi pipeline được fit lại trên toàn train sau khi chọn cấu hình theo CV AP. Không dùng validation để chọn cấu hình/họ mô hình. Quy tắc đơn giản hóa của Phần 3 được cụ thể hóa: nếu AP trung bình của LR kém mô hình CV tốt nhất ít hơn một SD AP của mô hình tốt nhất thì ưu tiên LR; ngược lại chọn mô hình AP cao nhất. Quy tắc này là quy ước thực nghiệm, không phải kiểm định thống kê.

{md_table(cv)}

Mô hình được chọn trước khi xem test: **{selected}**. Kết quả CV của cấu hình thắng có thể lạc quan do dò tham số; không dùng làm ước lượng cuối. Sau đó chọn ngưỡng cho từng pipeline bằng min (5FN+FP)/n trên validation, giữ nguyên khi đánh giá test. No-skill gán xác suất bằng tỷ lệ vỡ nợ train. Các mô hình chỉ được huấn luyện trên train; không fit lại trên train+validation sau khi chọn ngưỡng.

## Kết quả test

{md_table(test)}

Logistic Regression có AP={lr['PR-AUC']:.4f}, ROC-AUC={lr['ROC-AUC']:.4f}, chi phí={lr['Chi phí / KH']:.4f}. HistGradientBoosting có AP={hgb['PR-AUC']:.4f}, ROC-AUC={hgb['ROC-AUC']:.4f}, chi phí={hgb['Chi phí / KH']:.4f}. Đây là kết quả mô tả trên cùng test; không chọn lại mô hình theo bảng này. Chi phí là đơn vị tương đối với giả định FN:FP=5:1, không phải tiền thực tế.

So với LR, HGB thay đổi số khách vỡ nợ bị bỏ sót từ {lr['FN']:.0f} thành {hgb['FN']:.0f}, đồng thời số cảnh báo nhầm từ {lr['FP']:.0f} thành {hgb['FP']:.0f}. Đánh đổi này giải thích vì sao Accuracy không đi cùng chiều với chi phí: giảm FN được coi trọng gấp 5 lần giảm FP theo giả định đã chốt.

KTC percentile bootstrap 95%, 1.000 mẫu ghép cặp, seed=42, giữ cố định mô hình và ngưỡng:

{md_table(intervals.reset_index())}

Các cặp so sánh định trước: mô hình đã chọn với no-skill, và với LR nếu mô hình đã chọn khác LR. Hiệu số = A − B; AP dương là tốt hơn, chi phí âm là tốt hơn. Chỉ kết luận có bằng chứng khác biệt theo một chỉ số nếu KTC của hiệu số chỉ số đó không chứa 0.

{md_table(comparison.reset_index(names='Chỉ số'))}

{interpretation}

![Đường Precision–Recall và ROC trên test](figures/11_pr_roc.png)

![Ma trận nhầm lẫn tại ngưỡng validation](figures/11_confusion.png)

## Phân tích lỗi

Ba lát cắt có chi phí cao nhất của mô hình đã chọn (các tiêu chí có thể chồng nhau):

{md_table(worst[['Lát cắt', 'Nhóm', 'Số khách', 'Tỷ lệ vỡ nợ', 'PR-AUC', 'Recall', 'Precision', 'Chi phí / KH']])}

Đối chiếu AP từng nhóm với tỷ lệ vỡ nợ của chính nhóm đó. Chi phí cao có thể do tỷ lệ vỡ nợ cao và/hoặc nhiều lỗi; không suy ra nguyên nhân nhân quả hay kết luận công bằng từ các bảng mô tả này. Chỉ số nhóm nhỏ có độ bất định lớn.

Đặc điểm trung bình theo TP/FN/FP/TN (cả hai pipeline):

{md_table(profiles)}

Với {selected}, nhóm FN có trung bình {fn_profile['late_month_count']:.2f} tháng chậm trả, so với {tp_profile['late_month_count']:.2f} ở TP; hạn mức trung bình tương ứng {fn_profile['LIMIT_BAL']:,.0f} và {tp_profile['LIMIT_BAL']:,.0f} NT$. Những khách vỡ nợ bị bỏ sót có thể thiếu dấu hiệu chậm trả rõ trong sáu tháng quan sát, cho thấy chỉ lịch sử hành vi hiện có chưa đủ để nhận diện mọi trường hợp.

FN là khách thực sự vỡ nợ bị bỏ sót; mỗi FN đóng góp 5 đơn vị chi phí. FP là cảnh báo nhầm; mỗi FP đóng góp 1 đơn vị. Các giá trị là trung bình mô tả, không phải quy tắc phân loại tất định. Bảng chi tiết mọi lát cắt: `tables/11_error_slices.csv`.

## Hạn chế

- LR giả định log-odds tuyến tính, nên hạn chế khi trạng thái chậm trả có quan hệ phi tuyến với vỡ nợ. Gradient boosting khó giải thích hơn và có thể overfit; lưới tham số nhỏ giới hạn thời gian thực nghiệm.
- Chưa ablation cùng bộ đặc trưng để tách hiệu quả thuật toán và feature engineering; chưa khảo sát calibration, thay đổi chi phí hay độ ổn định qua nhiều seed.
- Kế thừa giới hạn Phần 3: dữ liệu Đài Loan năm 2005, không đánh giá theo thời gian; EDA đã quan sát toàn bộ dữ liệu; không nested CV; bootstrap theo khách hàng và chỉ phản ánh test khi mô hình/ngưỡng đã cố định.
- Kết quả phục vụ bài tập nghiên cứu, không được diễn giải thành bằng chứng khả năng áp dụng cho quần thể hoặc thời điểm khác.

## Tái lập và bàn giao

Chạy `python -m src.modeling` từ gốc repo sau khi cài requirements.txt. Các bảng `11_*.csv` và hai biểu đồ được ghi trong reports. Pipeline cùng ngưỡng lưu ở `outputs/hiep/*.joblib`, manifest/source hash và phiên bản ở `outputs/hiep/selection.json`; thư mục outputs được gitignore. Điểm số theo ID được lưu cục bộ để nhóm tích hợp/đối chiếu. Chạy lại tái lập toàn bộ thí nghiệm; không thay cấu hình sau khi đọc test rồi báo cáo như đánh giá test lần đầu.

## Tài liệu tham khảo

[1] UCI Default of Credit Card Clients. https://archive.ics.uci.edu/dataset/350 — DOI 10.24432/C55S3H.

[2] scikit-learn, LogisticRegression. https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html

[3] scikit-learn, HistGradientBoostingClassifier. https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html
'''
    (ROOT / 'reports/Bao_cao_Mo_hinh_Hiep.md').write_text(text, encoding='utf-8')


if __name__ == '__main__':
    run()
