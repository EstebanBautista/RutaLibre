// Tests for the WebAssembly loader used by the browser. They run in Node with
// the very same engine.wasm file the site serves:  node --test frontend/tests/
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const RLEngine = require(join(here, '..', 'js', 'engine-loader.js'));
const wasmBytes = readFileSync(join(here, '..', 'wasm', 'engine.wasm'));

const DEPOT = { lat: 3.40, lng: -76.55 };
// Corners of a square, listed in an order that crosses itself.
const CROSSED_SQUARE = [
  { lat: 3.41, lng: -76.54 },
  { lat: 3.45, lng: -76.50 },
  { lat: 3.41, lng: -76.50 },
  { lat: 3.45, lng: -76.54 },
];

const load = () => RLEngine.instantiate(wasmBytes);

test('optimized route is shorter than the crossing order', async () => {
  const engine = await load();
  const result = engine.optimize(DEPOT, CROSSED_SQUARE);
  assert.ok(result.optimizedKm < result.naiveKm);
});

test('order is a permutation of the stop indices', async () => {
  const engine = await load();
  const result = engine.optimize(DEPOT, CROSSED_SQUARE);
  assert.deepEqual([...result.order].sort(), [0, 1, 2, 3]);
});

test('no stops gives an empty order and zero distance', async () => {
  const engine = await load();
  assert.deepEqual(engine.optimize(DEPOT, []), { order: [], optimizedKm: 0, naiveKm: 0 });
});

test('a single stop is a round trip', async () => {
  const engine = await load();
  const result = engine.optimize(DEPOT, [CROSSED_SQUARE[1]]);
  assert.deepEqual(result.order, [0]);
  assert.equal(result.optimizedKm, result.naiveKm);
  assert.ok(result.optimizedKm > 0);
});

test('more than 100 stops throws RangeError', async () => {
  const engine = await load();
  const tooMany = Array.from({ length: 101 }, () => ({ lat: 3.4, lng: -76.5 }));
  assert.throws(() => engine.optimize(DEPOT, tooMany), RangeError);
});

test('exactly 100 stops is accepted', async () => {
  const engine = await load();
  const stops = Array.from({ length: 100 }, (_, i) => ({ lat: 3.35 + (i % 10) * 0.01, lng: -76.6 + Math.floor(i / 10) * 0.01 }));
  const result = engine.optimize(DEPOT, stops);
  assert.equal(new Set(result.order).size, 100);
});

test('consecutive calls do not leak state', async () => {
  const engine = await load();
  const first = engine.optimize(DEPOT, CROSSED_SQUARE);
  engine.optimize(DEPOT, CROSSED_SQUARE.slice(0, 2));
  assert.deepEqual(engine.optimize(DEPOT, CROSSED_SQUARE), first);
});

test('accepts an ArrayBuffer as well as a Node Buffer', async () => {
  const arrayBuffer = wasmBytes.buffer.slice(wasmBytes.byteOffset, wasmBytes.byteOffset + wasmBytes.byteLength);
  const engine = await RLEngine.instantiate(arrayBuffer);
  assert.equal(engine.optimize(DEPOT, CROSSED_SQUARE).order.length, 4);
});

// The browser preview and the server must agree. These numbers were produced
// by the Python wrapper (optimizer/app/engine.py) for the same ten points.
const TEN_STOPS = [
  [3.4480, -76.5410], [3.3300, -76.5400], [3.4590, -76.5330], [3.3830, -76.5330], [3.4520, -76.5420],
  [3.4700, -76.5330], [3.3640, -76.5370], [3.4640, -76.5290], [3.4130, -76.5450], [3.4390, -76.5330],
].map(([lat, lng]) => ({ lat, lng }));
const CALI_DEPOT = { lat: 3.4516, lng: -76.5320 };
const EXPECTED_FROM_PYTHON = {
  order: [2, 7, 5, 4, 0, 8, 1, 6, 3, 9],
  optimizedKm: 31.787973817671872,
  naiveKm: 80.46889467220748,
};

test('matches the server-side engine for the same input', async () => {
  const engine = await load();
  const result = engine.optimize(CALI_DEPOT, TEN_STOPS);
  assert.deepEqual(result.order, EXPECTED_FROM_PYTHON.order);
  assert.ok(Math.abs(result.optimizedKm - EXPECTED_FROM_PYTHON.optimizedKm) < 1e-9);
  assert.ok(Math.abs(result.naiveKm - EXPECTED_FROM_PYTHON.naiveKm) < 1e-9);
});
