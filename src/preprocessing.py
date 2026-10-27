"""Tiền xử lý tái lập: python -m src.preprocessing (chạy từ thư mục dự án)."""
import json
import hashlib
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/raw/default of credit card clients.xls'
TARGET = 'default'
CATEGORICAL = ['SEX', 'EDUCATION', 'MARRIAGE']
PAY = ['PAY_0', 'PAY_2', 'PAY_3', 'PAY_4', 'PAY_5', 'PAY_6']
BILL = [f'BILL_AMT{i}' for i in range(1, 7)]
PAYMENT = [f'PAY_AMT{i}' for i in range(1, 7)]
FEATURES = ['LIMIT_BAL', *CATEGORICAL, 'AGE', *PAY, *BILL, *PAYMENT]
DERIVED = ['late_month_count', 'max_delay', 'recent_delay_change',
           'utilization_sep', 'mean_payment', 'zero_payment_count']
SEED = 42


def clean_data(raw):
    """Quy tắc cố định, không ước lượng thống kê từ dữ liệu."""
    df = raw.rename(columns={'default payment next month': TARGET}).copy()
    expected = ['ID', *FEATURES, TARGET]
    if set(df.columns) != set(expected):
        raise ValueError('Cấu trúc cột không đúng với dữ liệu UCI gốc.')
    df = df[expected].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(df.to_numpy()).all():
        raise ValueError('Dữ liệu chứa giá trị thiếu hoặc vô cực; cần kiểm tra nguồn.')
    if not df[TARGET].isin([0, 1]).all() or not df.ID.is_unique:
        raise ValueError('Nhãn phải là 0/1 và ID phải duy nhất.')
    if (df.LIMIT_BAL <= 0).any() or (df[PAYMENT] < 0).any().any():
        raise ValueError('Hạn mức phải dương, số tiền thanh toán không được âm.')
    for col, valid in {'SEX': [1, 2], 'EDUCATION': list(range(7)),
                       'MARRIAGE': list(range(4)), **{p: list(range(-2, 10)) for p in PAY}}.items():
        if not df[col].isin(valid).all():
            raise ValueError(f'Mã ngoài miền dự kiến: {col}')
    duplicate = df.duplicated(subset=[*FEATURES, TARGET])
    removed_ids = df.loc[duplicate, ['ID']].copy()
    audit = {'raw_rows': len(df), 'missing_values': int(df.isna().sum().sum()),
             'exact_duplicates_removed': int(duplicate.sum())}
    df = df.loc[~duplicate].copy()
    audit['education_remapped'] = int(df.EDUCATION.isin([0, 5, 6]).sum())
    audit['marriage_remapped'] = int(df.MARRIAGE.eq(0).sum())
    df['EDUCATION'] = df.EDUCATION.replace({0: 4, 5: 4, 6: 4})
    df['MARRIAGE'] = df.MARRIAGE.replace({0: 3})
    df[TARGET] = df[TARGET].astype(int)
    df = df.reset_index(drop=True)
    # Giữ cả nhãn mâu thuẫn; gom hồ sơ giống nhau vào cùng tập sau khi gộp mã.
    groups = df.groupby(FEATURES, sort=True, dropna=False).ngroup()
    audit['clean_rows'] = len(df)
    audit['identical_feature_groups'] = int(groups.value_counts().gt(1).sum())
    audit['conflicting_label_groups'] = int(df.groupby(groups)[TARGET].nunique().gt(1).sum())
    return df, groups, audit, removed_ids


def split_data(df, groups):
    """20 folds phân tầng theo nhóm: 14 train, 3 validation, 3 test (~70/15/15)."""
    folds = np.full(len(df), -1)
    splitter = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=SEED)
    for fold, (_, indices) in enumerate(splitter.split(df[FEATURES], df[TARGET], groups)):
        folds[indices] = fold
    names = np.where(folds < 14, 'train', np.where(folds < 17, 'validation', 'test'))
    manifest = pd.DataFrame({'ID': df.ID, 'group_id': groups, 'fold': folds, 'split': names})
    if manifest.groupby('group_id')['split'].nunique().max() != 1:
        raise AssertionError('Hồ sơ giống nhau xuất hiện ở nhiều tập.')
    parts = {name: df.loc[names == name].copy() for name in ['train', 'validation', 'test']}
    for part in parts.values():
        if part[TARGET].nunique() != 2:
            raise ValueError('Mỗi tập phải có đủ hai lớp.')
    return parts, manifest


def add_features(X):
    X = X.copy()
    X['late_month_count'] = X[PAY].gt(0).sum(axis=1)
    X['max_delay'] = X[PAY].max(axis=1).clip(lower=0)
    X['recent_delay_change'] = X.PAY_0 - X.PAY_2
    X['utilization_sep'] = X.BILL_AMT1 / X.LIMIT_BAL
    X['mean_payment'] = X[PAYMENT].mean(axis=1)
    X['zero_payment_count'] = X[PAYMENT].eq(0).sum(axis=1)
    return X


def signed_log1p(X):
    return np.sign(X) * np.log1p(np.abs(X))


def make_preprocessor(kind='linear', with_features=False):
    """Trả về pipeline CHƯA fit; ghép với mô hình trước khi cross-validation."""
    if kind not in ('linear', 'tree'):
        raise ValueError('kind phải là linear hoặc tree')
    numeric = [c for c in FEATURES if c not in CATEGORICAL]
    if with_features:
        numeric += DERIVED
    cat = OneHotEncoder(categories=[[1, 2], [1, 2, 3, 4], [1, 2, 3]],
                        drop='first', handle_unknown='error', sparse_output=False)
    if kind == 'linear':
        positive = ['LIMIT_BAL', *PAYMENT] + (['mean_payment'] if with_features else [])
        other = [c for c in numeric if c not in positive + BILL]
        transforms = [
            ('positive', Pipeline([('log', FunctionTransformer(np.log1p, feature_names_out='one-to-one')),
                                   ('scale', StandardScaler())]), positive),
            ('bills', Pipeline([('log', FunctionTransformer(signed_log1p, feature_names_out='one-to-one')),
                                ('scale', StandardScaler())]), BILL),
            ('numeric', StandardScaler(), other), ('category', cat, CATEGORICAL)]
    else:
        transforms = [('numeric', 'passthrough', numeric), ('category', cat, CATEGORICAL)]
    steps = []
    if with_features:
        steps.append(('features', FunctionTransformer(add_features)))
    steps.append(('columns', ColumnTransformer(transforms, remainder='drop', verbose_feature_names_out=True)))
    return Pipeline(steps)


def run():
    out = ROOT / 'data/processed'
    reports = ROOT / 'reports/tables'
    out.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    df, groups, audit, removed = clean_data(pd.read_excel(DATA, header=1))
    parts, manifest = split_data(df, groups)
    manifest.to_csv(out / 'split_manifest.csv', index=False)
    removed.to_csv(out / 'removed_duplicate_ids.csv', index=False)
    summary = []
    for name, part in parts.items():
        part.to_csv(out / f'{name}.csv', index=False)
        summary.append({'split': name, 'rows': len(part), 'fraction': len(part) / len(df),
                        'defaults': int(part[TARGET].sum()), 'default_rate': part[TARGET].mean()})
    shapes = {}
    for kind in ['linear', 'tree']:
        for engineered in [False, True]:
            key = kind + ('_extended' if engineered else '_base')
            pipeline = make_preprocessor(kind, engineered)
            pipeline.fit(parts['train'][FEATURES])
            names = pipeline.named_steps['columns'].get_feature_names_out()
            shapes[key] = len(names)
            folder = out / key
            folder.mkdir(exist_ok=True)
            for split, part in parts.items():
                values = pipeline.transform(part[FEATURES])
                if not np.isfinite(values).all() or values.shape != (len(part), len(names)):
                    raise AssertionError(f'Đầu ra không hợp lệ: {key}/{split}')
                frame = pd.DataFrame(values, columns=names)
                frame.insert(0, 'ID', part.ID.to_numpy())
                frame[TARGET] = part[TARGET].to_numpy()
                frame.to_csv(folder / f'{split}.csv', index=False)
            joblib.dump(pipeline, folder / 'preprocessor.joblib')
    audit.update({'random_state': SEED, 'split_method': 'StratifiedGroupKFold: 14/3/3 of 20 folds',
                  'raw_sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(),
                  'feature_counts': shapes, 'versions': {'numpy': np.__version__, 'pandas': pd.__version__,
                                                       'scikit-learn': sklearn.__version__}})
    (out / 'metadata.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    pd.DataFrame(summary).to_csv(reports / '09_preprocessing_splits.csv', index=False)
    pd.DataFrame([{'metric': k, 'value': v} for k, v in audit.items() if not isinstance(v, dict)]).to_csv(
        reports / '09_preprocessing_audit.csv', index=False)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == '__main__':
    # Lưu tên module ổn định để joblib có thể nạp lại ở tiến trình khác.
    import sys
    sys.path.insert(0, str(ROOT))
    from src.preprocessing import run as run_preprocessing
    run_preprocessing()
