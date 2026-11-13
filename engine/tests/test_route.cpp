// Tests for the route engine. No framework: a CHECK macro counts failures
// and main() returns non-zero when any check fails.
#include <cmath>
#include <cstdio>

#include "../src/route.hpp"

static int g_failures = 0;
static int g_checks = 0;

#define CHECK(cond)                                                        \
  do {                                                                     \
    ++g_checks;                                                            \
    if (!(cond)) {                                                         \
      ++g_failures;                                                        \
      std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond);          \
    }                                                                      \
  } while (0)

// True when order[0..n-1] contains every index 0..n-1 exactly once.
static bool is_permutation(const int* order, int n) {
  bool seen[rl::kMaxStops] = {false};
  for (int i = 0; i < n; ++i) {
    if (order[i] < 0 || order[i] >= n || seen[order[i]]) return false;
    seen[order[i]] = true;
  }
  return true;
}

// Small deterministic generator so the tests give the same result everywhere.
static unsigned g_seed = 12345u;
static double next_unit() {
  g_seed = g_seed * 1664525u + 1013904223u;
  return (g_seed >> 8) / 16777216.0;  // 0 <= x < 1
}

// Fills coords with a depot in Cali and n stops scattered around it.
static void fill_random(double* coords, int n, unsigned seed) {
  g_seed = seed;
  coords[0] = 3.4516;
  coords[1] = -76.5320;
  for (int i = 1; i <= n; ++i) {
    coords[2 * i] = 3.35 + next_unit() * 0.2;
    coords[2 * i + 1] = -76.60 + next_unit() * 0.15;
  }
}

static void fill_identity(int* order, int n) {
  for (int i = 0; i < n; ++i) order[i] = i;
}

static void test_haversine_same_point_is_zero() {
  CHECK(rl::haversine_km(0, 0, 0, 0) == 0.0);
}

static void test_haversine_cali_bogota() {
  double km = rl::haversine_km(3.4516, -76.5320, 4.7110, -74.0721);
  CHECK(km > 301.0 && km < 311.0);
}

static void test_optimize_zero_stops() {
  double coords[2] = {3.4516, -76.5320};
  int order[1] = {-7};
  CHECK(rl::optimize(coords, 0, order) == 0.0);
}

static void test_optimize_one_stop_is_round_trip() {
  double coords[4] = {3.4516, -76.5320, 3.4000, -76.5000};
  int order[1] = {-7};
  double km = rl::optimize(coords, 1, order);
  double one_way = rl::haversine_km(coords[0], coords[1], coords[2], coords[3]);
  CHECK(std::fabs(km - 2.0 * one_way) < 1e-9);
  CHECK(order[0] == 0);
}

static void test_optimize_uncrosses_square() {
  // Depot at one corner region; stops are the corners of a square, listed in
  // a crossing order (0,2 are opposite corners, 1,3 the other diagonal).
  double coords[10] = {
      3.40, -76.55,  // depot
      3.41, -76.54,  // stop 0: corner A
      3.45, -76.50,  // stop 1: corner C (opposite A)
      3.41, -76.50,  // stop 2: corner B
      3.45, -76.54,  // stop 3: corner D
  };
  int naive[4];
  fill_identity(naive, 4);
  int order[4];
  double optimized = rl::optimize(coords, 4, order);
  CHECK(is_permutation(order, 4));
  CHECK(optimized < rl::tour_km(coords, naive, 4));
  CHECK(std::fabs(optimized - rl::tour_km(coords, order, 4)) < 1e-9);
}

static void test_optimize_never_worse_than_naive() {
  double coords[2 * 11];
  fill_random(coords, 10, 2024u);
  int naive[10];
  fill_identity(naive, 10);
  int order[10];
  double optimized = rl::optimize(coords, 10, order);
  CHECK(is_permutation(order, 10));
  CHECK(optimized <= rl::tour_km(coords, naive, 10) + 1e-9);
}

static void test_optimize_identical_points() {
  double coords[2 * 6];
  for (int i = 0; i < 6; ++i) {
    coords[2 * i] = 3.4516;
    coords[2 * i + 1] = -76.5320;
  }
  int order[5];
  double km = rl::optimize(coords, 5, order);
  CHECK(km == 0.0);
  CHECK(!std::isnan(km));
  CHECK(is_permutation(order, 5));
}

static void test_optimize_max_stops() {
  static double coords[2 * (rl::kMaxStops + 1)];
  fill_random(coords, rl::kMaxStops, 77u);
  static int order[rl::kMaxStops];
  double km = rl::optimize(coords, rl::kMaxStops, order);
  CHECK(km > 0.0);
  CHECK(is_permutation(order, rl::kMaxStops));
}

static void test_optimize_rejects_out_of_range_n() {
  static double coords[2 * (rl::kMaxStops + 2)] = {0};
  static int order[rl::kMaxStops + 1];
  CHECK(rl::optimize(coords, -1, order) == -1.0);
  CHECK(rl::optimize(coords, rl::kMaxStops + 1, order) == -1.0);
}

static void test_optimize_is_deterministic() {
  double coords[2 * 13];
  fill_random(coords, 12, 9u);
  int a[12], b[12];
  double ka = rl::optimize(coords, 12, a);
  double kb = rl::optimize(coords, 12, b);
  CHECK(ka == kb);
  for (int i = 0; i < 12; ++i) CHECK(a[i] == b[i]);
}

int main() {
  test_haversine_same_point_is_zero();
  test_haversine_cali_bogota();
  test_optimize_zero_stops();
  test_optimize_one_stop_is_round_trip();
  test_optimize_uncrosses_square();
  test_optimize_never_worse_than_naive();
  test_optimize_identical_points();
  test_optimize_max_stops();
  test_optimize_rejects_out_of_range_n();
  test_optimize_is_deterministic();
  std::printf("%d checks, %d failures\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
