"""A Gaussian HMM with diagonal covariance, fit by Baum-Welch.

Written out rather than imported from hmmlearn for two reasons: it removes a
compiled dependency (this runs on Python 3.14, where wheels are patchy), and a
portfolio piece that claims a regime model should be able to show the E-step.

Numerical approach: scaled forward-backward, not log-sum-exp. The per-timestep
scaling factors are what keep long sequences from underflowing, and their logs
sum to the log-likelihood for free.
"""

from __future__ import annotations

import numpy as np

VAR_FLOOR = 1e-6


def _kmeans(X: np.ndarray, k: int, seed: int, iters: int = 50) -> np.ndarray:
    """Lloyd's algorithm with k-means++ seeding — used only to initialise
    the state means, so it need not be perfect, only deterministic."""
    rng = np.random.default_rng(seed)
    n = len(X)
    centers = [X[rng.integers(n)]]
    for _ in range(1, k):
        d2 = np.min(((X[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(-1), axis=1)
        total = d2.sum()
        probs = d2 / total if total > 0 else np.full(n, 1 / n)
        centers.append(X[rng.choice(n, p=probs)])
    C = np.array(centers)

    for _ in range(iters):
        lbl = np.argmin(((X[:, None, :] - C[None, :, :]) ** 2).sum(-1), axis=1)
        newC = np.array([X[lbl == j].mean(0) if (lbl == j).any() else C[j]
                         for j in range(k)])
        if np.allclose(newC, C):
            break
        C = newC
    return C


class GaussianHMM:
    def __init__(self, n_states: int, seed: int = 0, n_iter: int = 200, tol: float = 1e-5):
        self.K = n_states
        self.seed = seed
        self.n_iter = n_iter
        self.tol = tol
        self.loglik_: list[float] = []

    # -- emissions ---------------------------------------------------------
    def _log_b(self, X: np.ndarray) -> np.ndarray:
        """(T, K) log emission densities."""
        # (T, K, D)
        diff = X[:, None, :] - self.means_[None, :, :]
        return -0.5 * (np.log(2 * np.pi * self.vars_)[None, :, :]
                       + diff ** 2 / self.vars_[None, :, :]).sum(-1)

    def _b_scaled(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Emissions rescaled per timestep to avoid over/underflow.

        Returns (B, offset) with B = exp(log_b - offset). Because the offset is
        constant across states at each t, it cancels in every posterior and
        simply adds back into the log-likelihood.
        """
        lb = self._log_b(X)
        off = lb.max(axis=1)
        return np.exp(lb - off[:, None]), off

    # -- E step ------------------------------------------------------------
    def _forward(self, B: np.ndarray):
        T = len(B)
        a = np.zeros((T, self.K))
        c = np.zeros(T)
        a[0] = self.pi_ * B[0]
        c[0] = a[0].sum() or 1e-300
        a[0] /= c[0]
        for t in range(1, T):
            a[t] = (a[t - 1] @ self.A_) * B[t]
            c[t] = a[t].sum() or 1e-300
            a[t] /= c[t]
        return a, c

    def _backward(self, B: np.ndarray, c: np.ndarray):
        T = len(B)
        b = np.zeros((T, self.K))
        b[-1] = 1.0
        for t in range(T - 2, -1, -1):
            b[t] = self.A_ @ (B[t + 1] * b[t + 1]) / c[t + 1]
        return b

    # -- fit ---------------------------------------------------------------
    def fit(self, X: np.ndarray) -> "GaussianHMM":
        X = np.asarray(X, dtype=float)
        T, D = X.shape
        rng = np.random.default_rng(self.seed)

        self.means_ = _kmeans(X, self.K, self.seed)
        self.vars_ = np.tile(X.var(0) + VAR_FLOOR, (self.K, 1))
        self.pi_ = np.full(self.K, 1 / self.K)
        # Start persistent: regimes are sticky by construction, and a diffuse
        # start tends to converge to a state-swapping solution.
        self.A_ = np.full((self.K, self.K), 0.05 / (self.K - 1))
        np.fill_diagonal(self.A_, 0.95)

        prev = -np.inf
        for _ in range(self.n_iter):
            B, off = self._b_scaled(X)
            a, c = self._forward(B)
            b = self._backward(B, c)

            ll = np.log(c).sum() + off.sum()
            self.loglik_.append(float(ll))

            g = a * b
            g /= g.sum(1, keepdims=True) + 1e-300

            xi_sum = np.zeros((self.K, self.K))
            for t in range(T - 1):
                xi = (a[t][:, None] * self.A_
                      * (B[t + 1] * b[t + 1])[None, :] / c[t + 1])
                xi_sum += xi

            self.pi_ = g[0] / g[0].sum()
            self.A_ = xi_sum / (xi_sum.sum(1, keepdims=True) + 1e-300)

            w = g.sum(0) + 1e-300
            self.means_ = (g.T @ X) / w[:, None]
            for k in range(self.K):
                d = X - self.means_[k]
                self.vars_[k] = (g[:, k] @ (d ** 2)) / w[k] + VAR_FLOOR

            if abs(ll - prev) < self.tol * max(1.0, abs(prev)):
                break
            prev = ll

        return self

    # -- inference ---------------------------------------------------------
    def filtered(self, X: np.ndarray) -> np.ndarray:
        """P(state_t | observations up to and including t).

        This is the causal one. It is what an honest 'current regime' reading
        must use — it never peeks at the future.
        """
        B, _ = self._b_scaled(np.asarray(X, float))
        a, _ = self._forward(B)
        return a

    def smoothed(self, X: np.ndarray) -> np.ndarray:
        """P(state_t | all observations). Hindsight only — fine for drawing
        historical bands, wrong for claiming a live signal."""
        B, _ = self._b_scaled(np.asarray(X, float))
        a, c = self._forward(B)
        b = self._backward(B, c)
        g = a * b
        return g / (g.sum(1, keepdims=True) + 1e-300)

    def viterbi(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, float)
        lb = self._log_b(X)
        T = len(X)
        lA = np.log(self.A_ + 1e-300)
        d = np.zeros((T, self.K))
        psi = np.zeros((T, self.K), dtype=int)
        d[0] = np.log(self.pi_ + 1e-300) + lb[0]
        for t in range(1, T):
            m = d[t - 1][:, None] + lA
            psi[t] = m.argmax(0)
            d[t] = m.max(0) + lb[t]
        path = np.zeros(T, dtype=int)
        path[-1] = d[-1].argmax()
        for t in range(T - 2, -1, -1):
            path[t] = psi[t + 1, path[t + 1]]
        return path
