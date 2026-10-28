"""Tập đánh giá: python -m src.evaluation (chạy từ thư mục dự án).

Đọc phép chia cố định data/splits/split_manifest.csv, kiểm tra số mẫu và ghi
bảng phân bố vào reports/tables/. Các hàm giống Phần 3 của notebook.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, cross_validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.preprocessing import DATA, FEATURES, SEED, TARGET, clean_data  # noqa: E402

MANIFEST = ROOT / 'data/splits/split_manifest.csv'
TAB = ROOT / 'reports/tables'
SPLITS = ['train', 'validation', 'test']
COST_FN, COST_FP = 5, 1   # giả định: bỏ sót một khách vỡ nợ đắt gấp 5 lần từ chối nhầm
N_BOOT = 1000
# Số mẫu và số vỡ nợ của phép chia chuẩn
REFERENCE_SPLIT = {'train': (20976, 4608), 'validation': (4493, 1001), 'test': (4496, 1021)}
SLICES = {
    'PAY_0': lambda d: pd.cut(d.PAY_0, [-3, -1, 0, 1, 9], labels=['−2 / −1', '0', '1', '≥ 2']),
    'Hạn mức': lambda d: pd.cut(d.LIMIT_BAL, [0, 50_000, 100_000, 180_000, 270_000, np.inf],
                                labels=['≤ 50k', '50–100k', '100–180k', '180–270k', '> 270k']),
    'Tuổi': lambda d: pd.cut(d.AGE, [0, 29, 39, 49, 120], labels=['21–29', '30–39', '40–49', '≥ 50']),
    'Giới tính': lambda d: d.SEX.map({1: 'Nam', 2: 'Nữ'}).astype(pd.CategoricalDtype(['Nam', 'Nữ'])),
}


def load_split(clean_df, manifest_path=MANIFEST):
    split_of = clean_df.ID.map(pd.read_csv(manifest_path).set_index('ID')['split'])
    return {name: clean_df[split_of == name] for name in SPLITS}


def split_table(parts):
    return pd.DataFrame([{'Tập': name, 'Số mẫu': len(part), 'Số vỡ nợ': int(part[TARGET].sum()),
                          'Tỷ lệ vỡ nợ': part[TARGET].mean()} for name, part in parts.items()]).set_index('Tập')


def slice_share(parts):
    share = pd.DataFrame({name: pd.concat({s: make(part).value_counts(normalize=True, sort=False)
                                           for s, make in SLICES.items()})
                          for name, part in parts.items()})
    share.index.names = ['Lát cắt', 'Nhóm']
    share['Lệch lớn nhất (điểm %)'] = 100 * (share.max(axis=1) - share.min(axis=1))
    return share


def evaluate(y, p, threshold):
    y, p = np.asarray(y), np.asarray(p)
    pred = p >= threshold
    tp, fp, fn = (int(np.sum(pred & (y == 1))), int(np.sum(pred & (y == 0))),
                  int(np.sum(~pred & (y == 1))))
    return {'PR-AUC': average_precision_score(y, p), 'ROC-AUC': roc_auc_score(y, p),
            'Ngưỡng': threshold, 'Recall': tp / max(tp + fn, 1), 'Precision': tp / max(tp + fp, 1),
            'F1': 2 * tp / max(2 * tp + fp + fn, 1), 'Accuracy': np.mean(pred == y),
            'Chi phí / KH': (COST_FN * fn + COST_FP * fp) / len(y), 'TP': tp, 'FP': fp, 'FN': fn}


def min_cost_threshold(y, p):
    """Xét mọi giá trị xác suất xuất hiện và vô cực (không đoán ai vỡ nợ), chọn ngưỡng chi phí nhỏ nhất."""
    y, p = np.asarray(y), np.asarray(p)
    candidates = np.append(np.unique(p), np.inf)
    costs = [COST_FN * np.sum((p < t) & (y == 1)) + COST_FP * np.sum((p >= t) & (y == 0)) for t in candidates]
    return float(candidates[np.argmin(costs)])


def bootstrap(y, probs, thresholds, n_boot=N_BOOT, seed=SEED):
    """Bootstrap ghép cặp: mỗi lần lấy mẫu dùng chung cho mọi mô hình."""
    y = np.asarray(y)
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        for name, p in probs.items():
            m = evaluate(y[idx], np.asarray(p)[idx], thresholds[name])
            rows.append({'b': b, 'Mô hình': name, 'PR-AUC': m['PR-AUC'], 'Chi phí / KH': m['Chi phí / KH']})
    return pd.DataFrame(rows)


def confidence_interval(boot):
    return boot.groupby('Mô hình')[['PR-AUC', 'Chi phí / KH']].quantile([0.025, 0.975]).unstack()


def paired_diff(boot, a, b):
    wide = boot.pivot(index='b', columns='Mô hình')
    d = wide.xs(a, axis=1, level=1) - wide.xs(b, axis=1, level=1)
    return pd.DataFrame({'Hiệu số': d.mean(), 'KTC 2,5%': d.quantile(0.025), 'KTC 97,5%': d.quantile(0.975)})


def evaluate_model(model, parts, train_groups):
    """CV theo nhóm trên train -> fit train -> chọn ngưỡng trên validation -> dự đoán test."""
    X = {name: part[FEATURES] for name, part in parts.items()}
    y = {name: part[TARGET].to_numpy() for name, part in parts.items()}
    cv = cross_validate(clone(model), X['train'], y['train'], groups=train_groups,
                        cv=StratifiedGroupKFold(5, shuffle=True, random_state=SEED),
                        scoring={'PR-AUC': 'average_precision', 'ROC-AUC': 'roc_auc'})
    fitted = clone(model).fit(X['train'], y['train'])
    p_val, p_test = (fitted.predict_proba(X[s])[:, 1] for s in ['validation', 'test'])
    return {'cv': {f'CV {m}': f"{cv['test_' + m].mean():.4f} ± {cv['test_' + m].std():.4f}"
                   for m in ['PR-AUC', 'ROC-AUC']},
            'validation': p_val, 'test': p_test, 'threshold': min_cost_threshold(y['validation'], p_val)}


def slice_default_rate(part):
    """Số khách, số vỡ nợ và tỷ lệ vỡ nợ theo từng nhóm (mức PR-AUC ngẫu nhiên trong nhóm)."""
    return pd.concat({s: part.groupby(make(part), observed=False)[TARGET].agg(['size', 'sum', 'mean'])
                      for s, make in SLICES.items()}).set_axis(['Số khách', 'Số vỡ nợ', 'Tỷ lệ vỡ nợ'], axis=1)


def run():
    TAB.mkdir(parents=True, exist_ok=True)
    clean_df, _, _, _ = clean_data(pd.read_excel(DATA, header=1))
    parts = load_split(clean_df)
    summary = split_table(parts)
    for name, counts in REFERENCE_SPLIT.items():
        if tuple(summary.loc[name, ['Số mẫu', 'Số vỡ nợ']]) != counts:
            raise AssertionError(f'Tập {name} không khớp phép chia chuẩn.')
    summary.to_csv(TAB / '10_tap_danh_gia.csv')
    share = slice_share(parts)
    share.to_csv(TAB / '10_phan_bo_lat_cat.csv')
    rate = slice_default_rate(parts['test'])
    rate.to_csv(TAB / '10_ty_le_vo_no_theo_nhom.csv')

    with pd.option_context('display.width', 200, 'display.max_columns', 30):
        print(summary.round(4), share.round(4), rate.round(4), sep='\n\n')


if __name__ == '__main__':
    run()
