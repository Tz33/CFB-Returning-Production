"""Tests for the win-distribution DP and game-prob orientation."""
import itertools

import numpy as np
import pytest

from model.game_prob import fit_logistic, game_prob, sigmoid
from model.simulate import win_distribution


def brute_force_distribution(probs):
    dist = np.zeros(len(probs) + 1)
    for outcome in itertools.product([0, 1], repeat=len(probs)):
        p = 1.0
        for won, prob in zip(outcome, probs):
            p *= prob if won else (1 - prob)
        dist[sum(outcome)] += p
    return dist


def test_dp_matches_brute_force():
    probs = [0.9, 0.5, 0.2]
    assert np.allclose(win_distribution(probs), brute_force_distribution(probs))


def test_distribution_sums_to_one_and_expected_wins():
    probs = [0.7, 0.6, 0.55, 0.9, 0.15]
    dist = win_distribution(probs)
    assert dist.sum() == pytest.approx(1.0)
    expected = sum(k * p for k, p in enumerate(dist))
    assert expected == pytest.approx(sum(probs))


def test_logistic_recovers_synthetic_betas():
    rng = np.random.default_rng(7)
    n = 20000
    X = np.column_stack([np.ones(n), rng.normal(0, 10, n), rng.integers(0, 2, n).astype(float)])
    true_beta = np.array([0.05, 0.11, 0.25])
    y = (rng.random(n) < sigmoid(X @ true_beta)).astype(float)
    beta = fit_logistic(X, y)
    assert np.allclose(beta, true_beta, atol=0.05)


def test_neutral_site_zeroes_home_term():
    beta = np.array([0.0, 0.1, 0.3])
    neutral = game_prob(10.0, 5.0, neutral=True, beta=beta)
    home = game_prob(10.0, 5.0, neutral=False, beta=beta)
    assert neutral == pytest.approx(sigmoid(np.array(0.5)))
    assert home > neutral


def test_symmetry():
    beta = np.array([0.0, 0.1, 0.0])
    assert game_prob(8.0, 3.0, True, beta) == pytest.approx(1 - game_prob(3.0, 8.0, True, beta))
