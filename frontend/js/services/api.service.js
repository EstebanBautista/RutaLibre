// Thin wrapper over $http for the backend API, plus one place that turns any
// failed response into a sentence a person can read.
(function () {
  'use strict';

  angular.module('rutalibre').factory('ApiService', ApiService);

  ApiService.$inject = ['$http', 'CONFIG'];
  function ApiService($http, CONFIG) {
    function unwrap(response) { return response.data; }
    function url(path) { return CONFIG.API_URL + path; }

    var FIELD_NAMES = {
      customer_name: 'Cliente',
      address: 'Dirección',
      lat: 'Ubicación',
      lng: 'Ubicación',
      notes: 'Notas',
      driver: 'Repartidor',
      order_ids: 'Pedidos',
      date: 'Fecha',
      name: 'Nombre',
      phone: 'Teléfono'
    };

    return {
      get: function (path, params) { return $http.get(url(path), { params: params }).then(unwrap); },
      post: function (path, body) { return $http.post(url(path), body || {}).then(unwrap); },
      patch: function (path, body) { return $http.patch(url(path), body).then(unwrap); },
      delete: function (path) { return $http.delete(url(path)).then(unwrap); },

      // Builds the message to show for a rejected request.
      errorMessage: function (rejection) {
        if (!rejection || rejection.status <= 0) {
          return 'No se pudo conectar con el servidor. Revisa tu conexión e intenta de nuevo.';
        }
        var data = rejection.data;
        if (data && typeof data.detail === 'string') {
          return data.detail;
        }
        if (data && typeof data === 'object') {
          // Field errors from the API: {"lat": ["..."], "address": ["..."]}
          var parts = [];
          Object.keys(data).forEach(function (field) {
            var messages = [].concat(data[field]).join(' ');
            var label = FIELD_NAMES[field] || field;
            var line = label + ': ' + messages;
            if (parts.indexOf(line) === -1) { parts.push(line); }
          });
          if (parts.length) { return parts.join(' '); }
        }
        if (rejection.status >= 500) {
          return 'El servidor tuvo un problema. Intenta de nuevo en unos segundos.';
        }
        return 'No se pudo completar la acción (error ' + rejection.status + ').';
      }
    };
  }
})();
