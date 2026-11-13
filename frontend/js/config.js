// Addresses of the services this page talks to. On a developer machine the
// page is served from localhost and uses the local services; anywhere else it
// uses the deployed ones.
(function () {
  'use strict';

  var isLocal = ['localhost', '127.0.0.1'].indexOf(window.location.hostname) !== -1;

  var local = {
    API_URL: 'http://localhost:8000/api',
    OPTIMIZER_DOCS_URL: 'http://localhost:8001/docs'
  };

  var production = {
    API_URL: 'https://rutalibre-api.vercel.app/api',
    OPTIMIZER_DOCS_URL: 'https://rutalibre-optimizer.vercel.app/docs'
  };

  var chosen = isLocal ? local : production;

  window.RL_CONFIG = {
    API_URL: chosen.API_URL,
    OPTIMIZER_DOCS_URL: chosen.OPTIMIZER_DOCS_URL,
    REPO_URL: 'https://github.com/EstebanBautista/RutaLibre'
  };
})();
