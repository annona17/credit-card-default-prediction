"""Kiểm tra tính toàn vẹn, phân tách hồ sơ và rò rỉ thống kê."""
import unittest
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from src.preprocessing import (ROOT, DATA, FEATURES, TARGET, clean_data,
                               split_data, make_preprocessor)


class PreprocessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = pd.read_excel(DATA, header=1)
        cls.df, cls.groups, cls.audit, _ = clean_data(cls.raw)
        cls.parts, cls.manifest = split_data(cls.df, cls.groups)

    def test_cleaning_and_partition_integrity(self):
        self.assertEqual(len(self.df), 29965)
        self.assertEqual(self.audit['exact_duplicates_removed'], 35)
        self.assertFalse(self.df.EDUCATION.isin([0, 5, 6]).any())
        self.assertFalse(self.df.MARRIAGE.eq(0).any())
        self.assertEqual(set(self.manifest.ID), set(self.df.ID))
        self.assertTrue(self.manifest.ID.is_unique)
        self.assertEqual(self.manifest.groupby('group_id').split.nunique().max(), 1)
        for name, expected in [('train', .70), ('validation', .15), ('test', .15)]:
            part = self.parts[name]
            self.assertLess(abs(len(part) / len(self.df) - expected), .01)
            self.assertLess(abs(part[TARGET].mean() - self.df[TARGET].mean()), .015)
        _, repeated = split_data(self.df, self.groups)
        pd.testing.assert_frame_equal(self.manifest, repeated)

    def test_no_fit_on_validation_and_serialization(self):
        train = self.parts['train'][FEATURES]
        validation = self.parts['validation'][FEATURES].copy()
        validation['LIMIT_BAL'] = 10**12
        for kind in ['linear', 'tree']:
            for extended in [False, True]:
                pipe = clone(make_preprocessor(kind, extended)).fit(train)
                before = pipe.transform(train.iloc[:10])
                self.assertTrue(np.isfinite(pipe.transform(validation)).all())
                np.testing.assert_array_equal(before, pipe.transform(train.iloc[:10]))
                if kind == 'linear':
                    scaler = pipe.named_steps['columns'].named_transformers_['positive'].named_steps['scale']
                    self.assertAlmostEqual(scaler.mean_[0], np.log1p(train.LIMIT_BAL).mean())
                key = kind + ('_extended' if extended else '_base')
                loaded = joblib.load(ROOT / 'data/processed' / key / 'preprocessor.joblib')
                np.testing.assert_allclose(before, loaded.transform(train.iloc[:10]))
                names = pipe.named_steps['columns'].get_feature_names_out()
                self.assertFalse(any(n.endswith('__ID') or n.endswith('__default') for n in names))

    def test_invalid_inputs_fail_explicitly(self):
        for col, value in [('LIMIT_BAL', 0), ('PAY_AMT1', -1), ('EDUCATION', 99),
                           ('default payment next month', 2), ('AGE', np.nan)]:
            bad = self.raw.copy()
            bad.loc[0, col] = value
            with self.assertRaises(ValueError):
                clean_data(bad)


if __name__ == '__main__':
    unittest.main()
