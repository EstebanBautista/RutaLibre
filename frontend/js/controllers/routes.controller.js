(function () {
  'use strict';

  angular.module('rutalibre').controller('RoutesController', RoutesController);

  RoutesController.$inject = ['ApiService'];
  function RoutesController(ApiService) {
    var vm = this;
    vm.loading = true;
    vm.loadError = '';
    vm.routes = [];

    function load() {
      vm.loading = true;
      vm.loadError = '';
      ApiService.get('/routes/')
        .then(function (routes) { vm.routes = routes; })
        .catch(function (rejection) { vm.loadError = ApiService.errorMessage(rejection); })
        .finally(function () { vm.loading = false; });
    }

    vm.retry = load;
    load();
  }
})();
