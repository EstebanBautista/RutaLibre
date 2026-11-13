// Session handling. The token lives in localStorage so a page reload keeps
// the visitor signed in.
(function () {
  'use strict';

  angular.module('rutalibre').factory('AuthService', AuthService);

  AuthService.$inject = ['$http', '$rootScope', '$window', 'CONFIG'];
  function AuthService($http, $rootScope, $window, CONFIG) {
    var STORAGE_KEY = 'rutalibre.auth';

    function read() {
      try {
        var saved = JSON.parse($window.localStorage.getItem(STORAGE_KEY));
        return saved && typeof saved.access === 'string' ? saved : null;
      } catch (error) {
        return null; // storage blocked or holding something unreadable
      }
    }

    function store(tokens) {
      try {
        $window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: tokens.access }));
      } catch (error) {
        // Private mode can refuse writes; the session then lasts until reload.
      }
      session = { access: tokens.access };
      $rootScope.$broadcast('auth:changed');
    }

    var session = read();

    return {
      login: function (username, password) {
        return $http
          .post(CONFIG.API_URL + '/auth/token/', { username: username, password: password })
          .then(function (response) { store(response.data); });
      },
      loginDemo: function () {
        return $http
          .post(CONFIG.API_URL + '/auth/demo/', {})
          .then(function (response) { store(response.data); });
      },
      logout: function () {
        try { $window.localStorage.removeItem(STORAGE_KEY); } catch (error) { /* nothing to clear */ }
        session = null;
        $rootScope.$broadcast('auth:changed');
      },
      isAuthenticated: function () { return session !== null; },
      getToken: function () { return session ? session.access : null; }
    };
  }
})();
