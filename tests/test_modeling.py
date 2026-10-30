"""Kiểm tra quy trình chọn mô hình và chống rò rỉ tập đánh giá."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from src.modeling import HGB, LR, load_data, model_specs, select_model
from src.preprocessing import FEATURES


class ModelingTests(unittest.TestCase):
    def test_simple_model_is_preferred_within_best_fold_sd(self):
        rows = pd.DataFrame({'Mô hình': [LR, HGB], 'CV AP mean': [0.50, 0.51],
                             'CV AP std': [0.001, 0.02]})
        self.assertEqual(select_model(rows), LR)
        rows.loc[1, 'CV AP mean'] = 0.60
        self.assertEqual(select_model(rows), HGB)

    def test_fixed_groups_do_not_cross_cv_folds(self):
        parts, groups = load_data()
        train = parts['train']
        self.assertEqual(len(groups), len(train))
        self.assertNotIn('ID', FEATURES)
        self.assertNotIn('default', FEATURES)
        for fit, held in StratifiedGroupKFold(5, shuffle=True, random_state=42).split(
                train[FEATURES], train['default'], groups):
            self.assertFalse(set(groups[fit]) & set(groups[held]))

    def test_preprocessor_fits_inside_cv_and_models_accept_raw_features(self):
        parts, _ = load_data()
        sample = parts['train'].sample(150, random_state=42)
        for pipeline, _ in model_specs().values():
            pipeline.fit(sample[FEATURES], sample['default'])
            p = pipeline.predict_proba(parts['validation'][FEATURES].iloc[:10])
            self.assertEqual(p.shape, (10, 2))
            np.testing.assert_allclose(p.sum(axis=1), 1)

    def test_manifest_duplicate_id_is_rejected(self):
        from src.evaluation import MANIFEST
        manifest = pd.read_csv(MANIFEST)
        with patch('src.modeling.pd.read_csv', return_value=pd.concat([manifest, manifest.iloc[:1]])):
            with self.assertRaisesRegex(ValueError, 'Manifest'):
                load_data()


if __name__ == '__main__':
    unittest.main()
