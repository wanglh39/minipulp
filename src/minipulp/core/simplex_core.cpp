/*
 * simplex_core.cpp - C++ 两阶段单纯形法 + pybind11 绑定
 *
 * 教学定位：展示"建模层 Python / 计算层 C++"分工范式。
 * 算法逻辑与 solvers/simplex_py.py 完全一致，便于对照阅读。
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <vector>

namespace py = pybind11;

static constexpr double EPS = 1e-9;

static inline bool is_zero(double x) { return std::abs(x) < EPS; }

static void pivot(
    std::vector<std::vector<double>>& A,
    std::vector<double>& b,
    int pr, int pc, int m, int n_total)
{
    double pivot_val = A[pr][pc];
    for (int j = 0; j < n_total; ++j)
        A[pr][j] /= pivot_val;
    b[pr] /= pivot_val;
    for (int i = 0; i < m; ++i) {
        if (i == pr) continue;
        double factor = A[i][pc];
        if (is_zero(factor)) continue;
        for (int j = 0; j < n_total; ++j)
            A[i][j] -= factor * A[pr][j];
        b[i] -= factor * b[pr];
    }
}

static int simplex_loop(
    std::vector<std::vector<double>>& A,
    std::vector<double>& b,
    std::vector<double>& cost,
    std::vector<int>& basis,
    int n_total, int m)
{
    int max_iter = 10000;
    for (int iter = 0; iter < max_iter; ++iter) {
        std::vector<double> c_basis(m);
        for (int i = 0; i < m; ++i)
            c_basis[i] = cost[basis[i]];

        int pivot_col = -1;
        for (int j = 0; j < n_total; ++j) {
            double reduced = cost[j];
            for (int i = 0; i < m; ++i)
                reduced -= c_basis[i] * A[i][j];
            if (reduced < -EPS) {
                pivot_col = j;
                break;
            }
        }
        if (pivot_col == -1) return 1;

        int pivot_row = -1;
        double min_ratio = std::numeric_limits<double>::infinity();
        for (int i = 0; i < m; ++i) {
            if (A[i][pivot_col] > EPS) {
                double ratio = b[i] / A[i][pivot_col];
                if (ratio < min_ratio - EPS) {
                    min_ratio = ratio;
                    pivot_row = i;
                }
            }
        }
        if (pivot_row == -1) return -2;

        pivot(A, b, pivot_row, pivot_col, m, n_total);
        basis[pivot_row] = pivot_col;
    }
    return -3;
}

std::pair<int, std::vector<double>> solve_simplex(
    std::vector<double> cost,
    std::vector<std::vector<double>> A,
    std::vector<double> b,
    std::vector<int> senses)
{
    int n = static_cast<int>(cost.size());
    int m = static_cast<int>(A.size());

    if (m == 0) {
        for (int j = 0; j < n; ++j)
            if (std::abs(cost[j]) > EPS)
                return {-2, std::vector<double>(n, 0.0)};
        return {1, std::vector<double>(n, 0.0)};
    }

    for (int i = 0; i < m; ++i) {
        if (b[i] < -EPS) {
            for (int j = 0; j < n; ++j)
                A[i][j] = -A[i][j];
            b[i] = -b[i];
            if (senses[i] == 0) senses[i] = 2;
            else if (senses[i] == 2) senses[i] = 0;
        }
    }

    int n_total = n;
    std::vector<int> basis(m, -1);
    std::set<int> artificial_cols;

    for (int i = 0; i < m; ++i) {
        if (senses[i] == 0) {
            int col = n_total++;
            for (int r = 0; r < m; ++r)
                A[r].push_back(r == i ? 1.0 : 0.0);
            basis[i] = col;
        } else if (senses[i] == 2) {
            int col_s = n_total++;
            for (int r = 0; r < m; ++r)
                A[r].push_back(r == i ? -1.0 : 0.0);
            int col_a = n_total++;
            for (int r = 0; r < m; ++r)
                A[r].push_back(r == i ? 1.0 : 0.0);
            basis[i] = col_a;
            artificial_cols.insert(col_a);
        } else {
            int col_a = n_total++;
            for (int r = 0; r < m; ++r)
                A[r].push_back(r == i ? 1.0 : 0.0);
            basis[i] = col_a;
            artificial_cols.insert(col_a);
        }
    }

    if (!artificial_cols.empty()) {
        std::vector<double> phase1_cost(n_total, 0.0);
        for (int j : artificial_cols)
            phase1_cost[j] = 1.0;

        int status = simplex_loop(A, b, phase1_cost, basis, n_total, m);
        if (status != 1) return {status, std::vector<double>(n, 0.0)};

        double art_value = 0.0;
        for (int i = 0; i < m; ++i)
            if (artificial_cols.count(basis[i]))
                art_value += b[i];
        if (art_value > EPS) return {-1, std::vector<double>(n, 0.0)};

        for (int i = 0; i < m; ++i) {
            if (artificial_cols.count(basis[i])) {
                for (int j = 0; j < n_total; ++j) {
                    if (artificial_cols.count(j)) continue;
                    if (std::abs(A[i][j]) > EPS) {
                        pivot(A, b, i, j, m, n_total);
                        basis[i] = j;
                        break;
                    }
                }
            }
        }

        for (int j : artificial_cols)
            for (int i = 0; i < m; ++i)
                A[i][j] = 0.0;
    }

    std::vector<double> full_cost(n_total, 0.0);
    for (int j = 0; j < n; ++j)
        full_cost[j] = cost[j];

    int status = simplex_loop(A, b, full_cost, basis, n_total, m);
    if (status != 1) return {status, std::vector<double>(n, 0.0)};

    std::vector<double> solution(n, 0.0);
    for (int i = 0; i < m; ++i)
        if (basis[i] < n)
            solution[basis[i]] = b[i];
    return {status, solution};
}

PYBIND11_MODULE(_native, m) {
    m.doc() = "C++ simplex core for minipulp";
    m.def("solve_simplex", &solve_simplex,
          "Solve LP using two-phase simplex method");
}
