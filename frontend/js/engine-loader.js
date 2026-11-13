// Loads engine.wasm (the C++ route engine) and wraps it in a plain function.
// No framework here on purpose: the same file runs in the browser and in the
// Node tests.
//
// The module shares two buffers through its linear memory:
//   rl_coords() -> doubles  [depot_lat, depot_lng, stop0_lat, stop0_lng, ...]
//   rl_order()  -> int32    stop indices in visit order, written by rl_optimize
(function (root) {
  'use strict';

  var MAX_STOPS = 100;

  // The engine is built without imports. If a future build needs some (for
  // example WASI functions), give each one a do-nothing stand-in so the
  // module still loads.
  function buildImports(module) {
    var imports = {};
    WebAssembly.Module.imports(module).forEach(function (entry) {
      imports[entry.module] = imports[entry.module] || {};
      if (entry.kind === 'function') {
        imports[entry.module][entry.name] = function () { return 0; };
      }
    });
    return imports;
  }

  // bytes: ArrayBuffer or typed array with the contents of engine.wasm.
  // Resolves to { optimize(depot, stops) }.
  function instantiate(bytes) {
    return WebAssembly.compile(bytes).then(function (module) {
      return WebAssembly.instantiate(module, buildImports(module));
    }).then(function (instance) {
      var api = instance.exports;
      if (typeof api._initialize === 'function') {
        api._initialize(); // runs the module's static setup
      }
      var coordsPtr = api.rl_coords();
      var orderPtr = api.rl_order();

      // depot: {lat, lng}. stops: [{lat, lng}, ...].
      // Returns {order, optimizedKm, naiveKm}; order holds indices into stops.
      function optimize(depot, stops) {
        var n = stops.length;
        if (n > MAX_STOPS) {
          throw new RangeError('at most ' + MAX_STOPS + ' stops are supported, got ' + n);
        }
        if (n === 0) {
          return { order: [], optimizedKm: 0, naiveKm: 0 };
        }
        // Views are created per call: they point at the module's memory.
        var coords = new Float64Array(api.memory.buffer, coordsPtr, 2 * (n + 1));
        coords[0] = depot.lat;
        coords[1] = depot.lng;
        for (var i = 0; i < n; i++) {
          coords[2 * (i + 1)] = stops[i].lat;
          coords[2 * (i + 1) + 1] = stops[i].lng;
        }
        var naiveKm = api.rl_naive_km(n);
        var optimizedKm = api.rl_optimize(n);
        var order = Array.prototype.slice.call(new Int32Array(api.memory.buffer, orderPtr, n));
        return { order: order, optimizedKm: optimizedKm, naiveKm: naiveKm };
      }

      return { optimize: optimize };
    });
  }

  var RLEngine = { instantiate: instantiate, MAX_STOPS: MAX_STOPS };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RLEngine; // Node (tests)
  } else {
    root.RLEngine = RLEngine; // browser
  }
})(typeof self !== 'undefined' ? self : this);
