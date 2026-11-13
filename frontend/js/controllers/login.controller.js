(function () {
  'use strict';

  angular.module('rutalibre').controller('LoginController', LoginController);

  LoginController.$inject = ['$location', 'AuthService', 'ApiService', 'CONFIG'];
  function LoginController($location, AuthService, ApiService, CONFIG) {
    var vm = this;
    vm.config = CONFIG;
    vm.username = '';
    vm.password = '';
    vm.busy = false; // 'demo' | 'password' | false
    vm.error = '';

    function enter() { $location.path('/pedidos'); }

    function fail(rejection) {
      vm.error = rejection && rejection.status === 401
        ? 'Usuario o contraseña incorrectos.'
        : ApiService.errorMessage(rejection);
    }

    vm.enterDemo = function () {
      vm.busy = 'demo';
      vm.error = '';
      AuthService.loginDemo().then(enter).catch(fail).finally(function () { vm.busy = false; });
    };

    vm.submit = function () {
      if (!vm.username || !vm.password) {
        vm.error = 'Escribe tu usuario y tu contraseña.';
        return;
      }
      vm.busy = 'password';
      vm.error = '';
      AuthService.login(vm.username, vm.password).then(enter).catch(fail).finally(function () { vm.busy = false; });
    };
  }
})();
