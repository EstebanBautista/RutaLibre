#include "route.hpp"

#include <cmath>

namespace rl {

namespace {

constexpr int kMaxNodes = kMaxStops + 1;  // stops plus the depot
constexpr double kPi = 3.14159265358979323846;
constexpr double kImprovementEpsilon = 1e-9;

// Distance matrix between nodes. Node 0 is the depot, node i+1 is stop i.
// Static storage keeps the engine free of dynamic memory; the engine is
// therefore not reentrant, which is fine for a single-threaded wasm module.
double g_dist[kMaxNodes][kMaxNodes];

double to_radians(double degrees) { return degrees * kPi / 180.0; }

void build_matrix(const double* coords, int nodes) {
  for (int a = 0; a < nodes; ++a) {
    g_dist[a][a] = 0.0;
    for (int b = a + 1; b < nodes; ++b) {
      double km = haversine_km(coords[2 * a], coords[2 * a + 1],
                               coords[2 * b], coords[2 * b + 1]);
      g_dist[a][b] = km;
      g_dist[b][a] = km;
    }
  }
}

// tour holds nodes: tour[0] is the depot, tour[1..n] the stops, and
// tour[n + 1] the depot again, so every leg is tour[k] -> tour[k + 1].
double circuit_length(const int* tour, int n) {
  double total = 0.0;
  for (int k = 0; k <= n; ++k) total += g_dist[tour[k]][tour[k + 1]];
  return total;
}

// Greedy start: from the current node always go to the closest unvisited
// stop. Ties go to the lowest index so the result is deterministic.
void nearest_neighbor(int* tour, int n) {
  bool visited[kMaxNodes] = {false};
  tour[0] = 0;
  visited[0] = true;
  for (int position = 1; position <= n; ++position) {
    int current = tour[position - 1];
    int best = -1;
    for (int candidate = 1; candidate <= n; ++candidate) {
      if (visited[candidate]) continue;
      if (best == -1 || g_dist[current][candidate] < g_dist[current][best]) {
        best = candidate;
      }
    }
    tour[position] = best;
    visited[best] = true;
  }
  tour[n + 1] = 0;
}

void reverse_segment(int* tour, int i, int j) {
  while (i < j) {
    int tmp = tour[i];
    tour[i] = tour[j];
    tour[j] = tmp;
    ++i;
    --j;
  }
}

// 2-opt: take two legs (a -> b) and (c -> d) of the circuit. If connecting
// (a -> c) and (b -> d) instead is shorter, reverse the stretch b..c. That
// removes the "crossings" a greedy route leaves behind. Repeat until a full
// pass finds nothing to improve. Every accepted move shortens the circuit by
// more than epsilon, so the loop always ends.
void two_opt(int* tour, int n) {
  bool improved = true;
  while (improved) {
    improved = false;
    for (int i = 1; i < n; ++i) {
      for (int j = i + 1; j <= n; ++j) {
        int a = tour[i - 1], b = tour[i];
        int c = tour[j], d = tour[j + 1];
        double delta = g_dist[a][c] + g_dist[b][d] - g_dist[a][b] - g_dist[c][d];
        if (delta < -kImprovementEpsilon) {
          reverse_segment(tour, i, j);
          improved = true;
        }
      }
    }
  }
}

}  // namespace

double haversine_km(double lat1, double lng1, double lat2, double lng2) {
  double phi1 = to_radians(lat1);
  double phi2 = to_radians(lat2);
  double dphi = to_radians(lat2 - lat1);
  double dlambda = to_radians(lng2 - lng1);
  double sin_dphi = std::sin(dphi / 2.0);
  double sin_dlambda = std::sin(dlambda / 2.0);
  double h = sin_dphi * sin_dphi +
             std::cos(phi1) * std::cos(phi2) * sin_dlambda * sin_dlambda;
  // Rounding can push h a hair outside [0, 1]; clamp so sqrt/asin stay valid.
  if (h < 0.0) h = 0.0;
  if (h > 1.0) h = 1.0;
  return 2.0 * kEarthRadiusKm * std::asin(std::sqrt(h));
}

double tour_km(const double* coords, const int* order, int n) {
  if (n < 0 || n > kMaxStops) return -1.0;
  if (n == 0) return 0.0;
  build_matrix(coords, n + 1);
  int tour[kMaxNodes + 1];
  tour[0] = 0;
  for (int k = 0; k < n; ++k) tour[k + 1] = order[k] + 1;
  tour[n + 1] = 0;
  return circuit_length(tour, n);
}

double optimize(const double* coords, int n, int* order_out) {
  if (n < 0 || n > kMaxStops) return -1.0;
  if (n == 0) return 0.0;
  build_matrix(coords, n + 1);

  // Candidate 1: greedy nearest-neighbor start, then 2-opt.
  int greedy[kMaxNodes + 1];
  nearest_neighbor(greedy, n);
  two_opt(greedy, n);
  double greedy_km = circuit_length(greedy, n);

  // Candidate 2: the order received, then 2-opt. 2-opt never lengthens a
  // circuit, so keeping the shorter candidate guarantees the result is never
  // longer than the order the user listed.
  int listed[kMaxNodes + 1];
  listed[0] = 0;
  for (int k = 1; k <= n; ++k) listed[k] = k;
  listed[n + 1] = 0;
  two_opt(listed, n);
  double listed_km = circuit_length(listed, n);

  // Ties keep the greedy candidate, so results stay deterministic.
  const int* best = listed_km < greedy_km - kImprovementEpsilon ? listed : greedy;
  for (int k = 0; k < n; ++k) order_out[k] = best[k + 1] - 1;
  return best == listed ? listed_km : greedy_km;
}

}  // namespace rl
