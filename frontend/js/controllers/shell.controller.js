// Controller of the page frame: top bar, account actions and the dialog that
// restores the demo data. Also home of the small display filters.
(function () {
  'use strict';

  angular
    .module('rutalibre')
    .controller('ShellController', ShellController)
    .filter('km', kmFilter)
    .filter('fecha', fechaFilter)
    .filter('estadoPedido', function () {
      var labels = { pending: 'Pendiente', assigned: 'En ruta', delivered: 'Entregado' };
      return function (status) { return labels[status] || status; };
    })
    .filter('estadoRuta', function () {
      var labels = { planned: 'Planificada', in_progress: 'En curso', done: 'Completada' };
      return function (status) { return labels[status] || status; };
    });

  // 31.787 -> "31,8 km"
  function kmFilter() {
    return function (value) {
      if (typeof value !== 'number' || !isFinite(value)) { return '—'; }
      return value.toLocaleString('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' km';
    };
  }

  // "2026-11-13" -> "13 nov 2026". Parsed by hand: new Date("2026-11-13")
  // would be read as UTC and could show the previous day in Colombia.
  function fechaFilter() {
    var months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    return function (isoDate) {
      var parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate || '');
      if (!parts) { return isoDate || ''; }
      return Number(parts[3]) + ' ' + months[Number(parts[2]) - 1] + ' ' + parts[1];
    };
  }

  ShellController.$inject = ['$scope', '$location', '$route', '$document', 'AuthService', 'ApiService', 'CONFIG'];
  function ShellController($scope, $location, $route, $document, AuthService, ApiService, CONFIG) {
    var shell = this;
    shell.config = CONFIG;
    shell.business = null;
    shell.resetting = false;
    shell.resetError = '';

    shell.isAuthenticated = AuthService.isAuthenticated;

    shell.isActive = function (prefix) {
      return $location.path().indexOf(prefix) === 0;
    };

    shell.logout = function () {
      AuthService.logout();
      $location.path('/login');
    };

    function dialog() { return $document[0].getElementById('reset-dialog'); }

    shell.askReset = function () {
      shell.resetError = '';
      dialog().showModal();
    };

    shell.closeReset = function () { dialog().close(); };

    shell.confirmReset = function () {
      shell.resetting = true;
      shell.resetError = '';
      ApiService.post('/demo/reset/')
        .then(function () {
          dialog().close();
          // A route detail no longer exists after a reset; go somewhere that does.
          if ($location.path().indexOf('/rutas/') === 0) {
            $location.path('/rutas');
          } else {
            $route.reload();
          }
        })
        .catch(function (rejection) { shell.resetError = ApiService.errorMessage(rejection); })
        .finally(function () { shell.resetting = false; });
    };

    function loadBusiness() {
      shell.business = null;
      if (!AuthService.isAuthenticated()) { return; }
      ApiService.get('/business/me/')
        .then(function (business) { shell.business = business; })
        // Without the business the top bar just hides its name and the reset
        // button. A 401 is already handled by the interceptor (back to login).
        .catch(angular.noop);
    }

    $scope.$on('auth:changed', loadBusiness);
    loadBusiness();
  }
})();
