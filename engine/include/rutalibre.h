/* Public C interface of the RutaLibre engine, as exported by engine.wasm.
 *
 * The host (JavaScript in the browser, Python on the server) talks to the
 * module through two static buffers that live in the module's linear memory:
 *
 *   rl_coords(): 2 * (RL_MAX_STOPS + 1) doubles
 *                [depot_lat, depot_lng, stop0_lat, stop0_lng, ...]
 *   rl_order():  RL_MAX_STOPS 32-bit integers, filled by rl_optimize with the
 *                stop indices (0..n-1) in visit order.
 *
 * Typical call sequence: write the coordinates into rl_coords(), call
 * rl_optimize(n), then read n integers from rl_order().
 */
#ifndef RUTALIBRE_H
#define RUTALIBRE_H

#include <stdint.h>

#define RL_MAX_STOPS 100

#ifdef __cplusplus
extern "C" {
#endif

double* rl_coords(void);
int32_t* rl_order(void);

/* Great-circle distance in km between two points given in degrees. */
double rl_haversine_km(double lat1, double lng1, double lat2, double lng2);

/* Length in km of the circuit depot -> stop 0 -> ... -> stop n-1 -> depot.
 * Returns -1.0 when n is outside 0..RL_MAX_STOPS. */
double rl_naive_km(int32_t n);

/* Computes a short circuit, writes the visit order to rl_order() and returns
 * its length in km. Returns -1.0 when n is outside 0..RL_MAX_STOPS. */
double rl_optimize(int32_t n);

#ifdef __cplusplus
}
#endif

#endif /* RUTALIBRE_H */
