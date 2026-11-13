// C interface exported by engine.wasm. See include/rutalibre.h.
#include "rutalibre.h"

#include "route.hpp"

static_assert(RL_MAX_STOPS == rl::kMaxStops, "header and engine limits must match");

namespace {

// Shared buffers the host reads and writes directly in linear memory.
double g_coords[2 * (RL_MAX_STOPS + 1)];
int32_t g_order[RL_MAX_STOPS];

}  // namespace

extern "C" {

double* rl_coords(void) { return g_coords; }

int32_t* rl_order(void) { return g_order; }

double rl_haversine_km(double lat1, double lng1, double lat2, double lng2) {
  return rl::haversine_km(lat1, lng1, lat2, lng2);
}

double rl_naive_km(int32_t n) {
  if (n < 0 || n > RL_MAX_STOPS) return -1.0;
  int identity[RL_MAX_STOPS];
  for (int i = 0; i < n; ++i) identity[i] = i;
  return rl::tour_km(g_coords, identity, n);
}

double rl_optimize(int32_t n) {
  if (n < 0 || n > RL_MAX_STOPS) return -1.0;
  int order[RL_MAX_STOPS];
  double km = rl::optimize(g_coords, n, order);
  for (int i = 0; i < n; ++i) g_order[i] = order[i];
  return km;
}

}  // extern "C"
