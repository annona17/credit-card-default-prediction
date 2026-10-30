"""Các mô hình bổ sung dùng đúng loại điểm và ngưỡng riêng của thực nghiệm."""
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.evaluation import evaluate, min_cost_threshold
from src.modeling import load_data
from src.modeling_team import NB, RF, SVM, additional_specs, model_scores
from src.preprocessing import FEATURES


class TeamModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parts, _ = load_data()
        cls.train = parts['train'].sample(180, random_state=42)
        cls.X = parts['validation'][FEATURES].head(15)

    def test_three_distinct_families_and_score_roundtrip(self):
        specs = additional_specs()
        self.assertEqual(set(specs), {RF, SVM, NB})
        for name, (pipeline, _) in specs.items():
            with self.subTest(model=name):
                pipeline.fit(self.train[FEATURES], self.train['default'])
                score = model_scores(pipeline, self.X)
                self.assertEqual(score.shape, (15,))
                self.assertTrue(np.isfinite(score).all())
                if name == SVM:
                    self.assertFalse(pipeline.named_steps['clf'].probability)
                    np.testing.assert_array_equal(score, pipeline.decision_function(self.X))
                else:
                    np.testing.assert_array_equal(score, pipeline.predict_proba(self.X)[:, 1])
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / 'model.joblib'
                    joblib.dump(pipeline, path)
                    np.testing.assert_array_equal(score, model_scores(joblib.load(path), self.X))

    def test_margin_threshold_is_invariant_to_positive_affine_rescaling(self):
        y = np.array([0, 0, 1, 1, 0, 1])
        margin = np.array([-2.2, -1.4, -1.1, -0.8, 0.2, 1.0])
        threshold = min_cost_threshold(y, margin)
        rescaled = 3 * margin + 7
        new_threshold = min_cost_threshold(y, rescaled)
        np.testing.assert_array_equal(margin >= threshold, rescaled >= new_threshold)
        self.assertAlmostEqual(evaluate(y, margin, threshold)['PR-AUC'],
                               evaluate(y, rescaled, new_threshold)['PR-AUC'])
        self.assertAlmostEqual(evaluate(y, margin, threshold)['Chi phí / KH'],
                               evaluate(y, rescaled, new_threshold)['Chi phí / KH'])

    def test_reversed_class_order_is_rejected(self):
        class ReversedClassifier:
            classes_ = np.array([1, 0])
        with self.assertRaisesRegex(ValueError, 'classes_'):
            model_scores(ReversedClassifier(), pd.DataFrame({'a': [1]}))


if __name__ == '__main__':
    unittest.main()
