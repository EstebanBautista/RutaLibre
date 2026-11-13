// Angular wrapper around the C++ engine running in the browser. It downloads
// and compiles engine.wasm once and then answers instantly.
(function () {
  'use strict';

  angular.module('rutalibre').factory('EngineService', EngineService);

  EngineService.$inject = ['$http', '$q'];
  function EngineService($http, $q) {
    var enginePromise = null;
    var engine = null;

    function load() {
      if (typeof WebAssembly !== 'object' || !window.RLEngine) {
        return $q.reject(new Error('WebAssembly is not available'));
      }
      return $http
        .get('wasm/engine.wasm', { responseType: 'arraybuffer' })
        .then(function (response) {
          // $q.when brings the native promise back into Angular's digest.
          return $q.when(window.RLEngine.instantiate(response.data));
        })
        .then(function (instance) {
          engine = instance;
          return instance;
        });
    }

    return {
      MAX_STOPS: window.RLEngine ? window.RLEngine.MAX_STOPS : 100,

      // Resolves when the engine can be used; rejects if it cannot be loaded.
      ready: function () {
        if (!enginePromise) {
          enginePromise = load().catch(function (error) {
            enginePromise = null; // allow a later retry
            return $q.reject(error);
          });
        }
        return enginePromise;
      },

      // Synchronous once ready() has resolved.
      // Returns {order, optimizedKm, naiveKm}; order holds indices into stops.
      optimize: function (depot, stops) {
        if (!engine) { throw new Error('engine not loaded: wait for ready()'); }
        return engine.optimize(depot, stops);
      }
    };
  }
})();
