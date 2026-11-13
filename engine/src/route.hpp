// RutaLibre route engine: pure computation, no I/O, no dynamic memory.
//
// Coordinates layout used everywhere in this file:
//   coords = [depot_lat, depot_lng, stop0_lat, stop0_lng, stop1_lat, ...]
// so there are (n + 1) lat/lng pairs for n stops, and pair 0 is the depot.
// A route ("tour") is a circuit: depot -> stops in some order -> depot.
#pragma once

namespace rl {

constexpr int kMaxStops = 100;
constexpr double kEarthRadiusKm = 6371.0088;

// Great-circle distance between two points given in degrees.
double haversine_km(double lat1, double lng1, double lat2, double lng2);

// Length in km of the circuit that visits the stops in the given order.
// order holds n stop indices in the range 0..n-1.
double tour_km(const double* coords, const int* order, int n);

// Computes a short circuit (nearest neighbor + 2-opt) and writes the visit
// order into order_out. Returns the circuit length in km.
// Returns -1.0 when n is outside 0..kMaxStops, and 0.0 when n == 0.
double optimize(const double* coords, int n, int* order_out);

}  // namespace rl
