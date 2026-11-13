// Application module: routes, the HTTP interceptor that carries the session
// token, and the guard that keeps signed-out visitors on the login page.
(function () {
  'use strict';

  angular
    .module('rutalibre', ['ngRoute'])
    .constant('CONFIG', window.RL_CONFIG)
    .config(configureRoutes)
    .config(configureHttp)
    .factory('authInterceptor', authInterceptor)
    .run(guardRoutes);

  configureRoutes.$inject = ['$routeProvider'];
  function configureRoutes($routeProvider) {
    $routeProvider
      .when('/login', {
        templateUrl: 'views/login.html',
        controller: 'LoginController',
        controllerAs: 'vm',
        isPublic: true
      })
      .when('/pedidos', {
        templateUrl: 'views/orders.html',
        controller: 'OrdersController',
        controllerAs: 'vm'
      })
      .when('/planificar', {
        templateUrl: 'views/planner.html',
        controller: 'PlannerController',
        controllerAs: 'vm'
      })
      .when('/rutas', {
        templateUrl: 'views/routes.html',
        controller: 'RoutesController',
        controllerAs: 'vm'
      })
      .when('/rutas/:id', {
        templateUrl: 'views/route-detail.html',
        controller: 'RouteDetailController',
        controllerAs: 'vm'
      })
      .otherwise({ redirectTo: '/pedidos' });
  }

  configureHttp.$inject = ['$httpProvider'];
  function configureHttp($httpProvider) {
    $httpProvider.interceptors.push('authInterceptor');
  }

  // Adds the token to calls that go to our API, and ends the session when
  // the API answers 401 (token expired or no longer valid).
  authInterceptor.$inject = ['$q', '$injector', 'CONFIG'];
  function authInterceptor($q, $injector, CONFIG) {
    function isApiCall(config) {
      return config.url.indexOf(CONFIG.API_URL) === 0;
    }

    return {
      request: function (config) {
        if (isApiCall(config)) {
          // AuthService is resolved lazily: it depends on $http, which is
          // still being built while interceptors are registered.
          var token = $injector.get('AuthService').getToken();
          if (token) {
            config.headers.Authorization = 'Bearer ' + token;
          }
        }
        return config;
      },
      responseError: function (rejection) {
        var isLoginAttempt = rejection.config && rejection.config.url.indexOf('/auth/') !== -1;
        if (rejection.status === 401 && rejection.config && isApiCall(rejection.config) && !isLoginAttempt) {
          $injector.get('AuthService').logout();
          $injector.get('$location').path('/login');
        }
        return $q.reject(rejection);
      }
    };
  }

  guardRoutes.$inject = ['$rootScope', '$location', 'AuthService'];
  function guardRoutes($rootScope, $location, AuthService) {
    $rootScope.$on('$routeChangeStart', function (event, next) {
      var isPublic = next && next.$$route && next.$$route.isPublic;
      if (!isPublic && !AuthService.isAuthenticated()) {
        event.preventDefault();
        $location.path('/login');
      } else if (isPublic && AuthService.isAuthenticated()) {
        event.preventDefault();
        $location.path('/pedidos');
      }
    });
  }
})();
