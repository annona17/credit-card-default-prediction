"""Kiểm tra tập đánh giá cố định và các hàm độ đo."""
import unittest

import numpy as np
import pandas as pd
from src.evaluation import (REFERENCE_SPLIT, bootstrap, evaluate, load_split, min_cost_threshold,
                            paired_diff, split_table)
from src.preprocessing import DATA, clean_data


class MetricTests(unittest.TestCase):
    y = np.array([1, 0, 1, 0])
    p = np.array([0.9, 0.6, 0.4, 0.1])

    def test_metrics_match_hand_computation(self):
        m = evaluate(self.y, self.p, 0.5)
        self.assertEqual((m['TP'], m['FP'], m['FN']), (1, 1, 1))
        self.assertEqual((m['Recall'], m['Precision'], m['F1']), (0.5, 0.5, 0.5))
        self.assertAlmostEqual(m['ROC-AUC'], 0.75)
        self.assertAlmostEqual(m['Chi phí / KH'], (5 * 1 + 1 * 1) / 4)

    def test_min_cost_threshold(self):
        # Ngưỡng 0,4: TP = 2, FP = 1, FN = 0 -> chi phí 1, nhỏ nhất
        self.assertEqual(min_cost_threshold(self.y, self.p), 0.4)

    def test_threshold_can_predict_no_default(self):
        # Khách vỡ nợ có xác suất thấp nhất: mọi ngưỡng hữu hạn tốn >= 6, không đoán ai tốn 5
        y = np.array([1, 0, 0, 0, 0, 0, 0])
        p = np.linspace(0.1, 0.7, 7)
        self.assertEqual(min_cost_threshold(y, p), np.inf)

    def test_paired_bootstrap_of_identical_models_is_zero(self):
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, 300)
        p = rng.random(300)
        boot = bootstrap(y, {'a': p, 'b': p}, {'a': 0.5, 'b': 0.5}, n_boot=50)
        self.assertTrue((paired_diff(boot, 'a', 'b').to_numpy() == 0).all())


class FixedSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean, _, _, _ = clean_data(pd.read_excel(DATA, header=1))
        cls.parts = load_split(cls.clean)

    def test_manifest_matches_reference_counts(self):
        summary = split_table(self.parts)
        for name, counts in REFERENCE_SPLIT.items():
            self.assertEqual(tuple(summary.loc[name, ['Số mẫu', 'Số vỡ nợ']]), counts)

    def test_splits_are_disjoint_and_complete(self):
        ids = [set(p.ID) for p in self.parts.values()]
        self.assertEqual(sum(len(s) for s in ids), len(self.clean))
        self.assertEqual(set().union(*ids), set(self.clean.ID))


if __name__ == '__main__':
    unittest.main()
