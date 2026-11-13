(function () {
  'use strict';

  angular.module('rutalibre').controller('RouteDetailController', RouteDetailController);

  RouteDetailController.$inject = ['$scope', '$routeParams', '$timeout', 'ApiService', 'MapService'];
  function RouteDetailController($scope, $routeParams, $timeout, ApiService, MapService) {
    var vm = this;
    var map = null;

    vm.loading = true;
    vm.loadError = '';
    vm.notFound = false;
    vm.route = null;
    vm.deliverError = '';
    vm.delivering = {}; // stop id -> true while its request is in flight

    vm.progressPercent = function () {
      if (!vm.route || !vm.route.stops_count) { return 0; }
      return Math.round((vm.route.delivered_count / vm.route.stops_count) * 100);
    };

    function draw(fit) {
      if (!map || !vm.route) { return; }
      var depot = vm.route.depot;
      var stops = vm.route.stops.map(function (stop) {
        return {
          lat: stop.order.lat,
          lng: stop.order.lng,
          kind: stop.delivered_at ? 'delivered' : 'selected',
          label: stop.sequence,
          title: stop.order.customer_name
        };
      });
      var points = [{ lat: depot.lat, lng: depot.lng, kind: 'depot', title: 'Depósito' }].concat(stops);
      MapService.clear(map);
      MapService.drawRoute(map, [depot].concat(stops, [depot]), { color: '#0b6b4f', weight: 5 });
      MapService.setMarkers(map, points);
      if (fit) { MapService.fit(map, points); }
    }

    function show(route, fit) {
      vm.route = route;
      $timeout(function () {
        if (!map) { map = MapService.create('route-map', route.depot); }
        draw(fit);
      });
    }

    function load() {
      vm.loading = true;
      vm.loadError = '';
      vm.notFound = false;
      ApiService.get('/routes/' + encodeURIComponent($routeParams.id) + '/')
        .then(function (route) { show(route, true); })
        .catch(function (rejection) {
          if (rejection.status === 404) {
            vm.notFound = true;
          } else {
            vm.loadError = ApiService.errorMessage(rejection);
          }
        })
        .finally(function () { vm.loading = false; });
    }

    vm.retry = load;

    vm.deliver = function (stop) {
      if (vm.delivering[stop.id] || stop.delivered_at) { return; }
      vm.delivering[stop.id] = true;
      vm.deliverError = '';
      ApiService.post('/routes/' + vm.route.id + '/stops/' + stop.id + '/deliver/')
        .then(function (route) { show(route, false); })
        .catch(function (rejection) { vm.deliverError = ApiService.errorMessage(rejection); })
        .finally(function () { delete vm.delivering[stop.id]; });
    };

    $scope.$on('$destroy', function () { MapService.destroy(map); });

    load();
  }
})();
