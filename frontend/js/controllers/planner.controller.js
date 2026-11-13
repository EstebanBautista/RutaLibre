// Route planner. The comparison between the route "as listed" and the
// optimized one is computed in the browser by the C++ engine (WebAssembly),
// so it updates the moment a checkbox changes. Confirming sends the selection
// to the backend, which computes the definitive route on the server.
(function () {
  'use strict';

  angular.module('rutalibre').controller('PlannerController', PlannerController);

  PlannerController.$inject = ['$scope', '$q', '$timeout', '$location', 'ApiService', 'MapService', 'EngineService'];
  function PlannerController($scope, $q, $timeout, $location, ApiService, MapService, EngineService) {
    var vm = this;
    var map = null;

    vm.maxStops = EngineService.MAX_STOPS;
    vm.loading = true;
    vm.loadError = '';
    vm.orders = [];
    vm.drivers = [];
    vm.business = null;
    vm.selected = {}; // order id -> true
    vm.driverId = null;
    vm.preview = null; // {naiveKm, optimizedKm, savedKm, savedPercent, sequence}
    vm.engineUnavailable = false;
    vm.confirming = false;
    vm.confirmError = '';

    vm.selectedOrders = function () {
      return vm.orders.filter(function (order) { return vm.selected[order.id]; });
    };

    vm.selectedCount = function () { return vm.selectedOrders().length; };

    vm.allSelected = function () {
      return vm.orders.length > 0 && vm.selectedCount() === vm.orders.length;
    };

    vm.toggleAll = function () {
      var value = !vm.allSelected();
      vm.orders.forEach(function (order) { vm.selected[order.id] = value; });
      vm.refresh();
    };

    vm.tooMany = function () { return vm.selectedCount() > vm.maxStops; };

    vm.canConfirm = function () {
      return vm.selectedCount() >= 1 && !vm.tooMany() && vm.driverId !== null && !vm.confirming;
    };

    // Position (1-based) of an order in the optimized route, for the list.
    vm.positionOf = function (order) {
      return vm.preview && vm.preview.sequence[order.id];
    };

    function depot() { return { lat: vm.business.depot_lat, lng: vm.business.depot_lng }; }

    function computePreview(chosen) {
      if (vm.engineUnavailable || chosen.length < 2 || chosen.length > vm.maxStops) { return null; }
      var result = EngineService.optimize(depot(), chosen);
      var sequence = {};
      result.order.forEach(function (stopIndex, position) { sequence[chosen[stopIndex].id] = position + 1; });
      var saved = result.naiveKm - result.optimizedKm;
      return {
        naiveKm: result.naiveKm,
        optimizedKm: result.optimizedKm,
        savedKm: saved,
        savedPercent: result.naiveKm > 0 ? Math.round((saved / result.naiveKm) * 100) : 0,
        // Width of the "optimized" bar relative to the "as listed" bar.
        ratioPercent: result.naiveKm > 0 ? Math.max(4, (result.optimizedKm / result.naiveKm) * 100) : 100,
        sequence: sequence,
        orderedStops: result.order.map(function (stopIndex) { return chosen[stopIndex]; })
      };
    }

    // Recomputes the preview and redraws the map. Called on every change.
    vm.refresh = function (fit) {
      if (!vm.business) { return; }
      var chosen = vm.selectedOrders();
      vm.confirmError = '';
      vm.preview = computePreview(chosen);
      if (!map) { return; }

      var home = depot();
      var points = [{ lat: home.lat, lng: home.lng, kind: 'depot', title: 'Depósito: ' + vm.business.name }];
      vm.orders.forEach(function (order) {
        var isChosen = !!vm.selected[order.id];
        points.push({
          lat: order.lat,
          lng: order.lng,
          kind: isChosen ? 'selected' : 'idle',
          label: isChosen && vm.preview ? vm.preview.sequence[order.id] : '',
          title: order.customer_name
        });
      });

      MapService.clear(map);
      if (vm.preview) {
        // Grey dashed: the route in list order. Green: the optimized route.
        MapService.drawRoute(map, [home].concat(chosen, [home]), { color: '#4a5651', dashed: true, weight: 3, opacity: 0.9 });
        MapService.drawRoute(map, [home].concat(vm.preview.orderedStops, [home]), { color: '#0b6b4f', weight: 5 });
      }
      MapService.setMarkers(map, points);
      if (fit) { MapService.fit(map, points); }
    };

    vm.confirm = function () {
      if (!vm.canConfirm()) { return; }
      vm.confirming = true;
      vm.confirmError = '';
      var payload = {
        driver: vm.driverId,
        order_ids: vm.selectedOrders().map(function (order) { return order.id; })
      };
      ApiService.post('/routes/', payload)
        .then(function (route) { $location.path('/rutas/' + route.id); })
        .catch(function (rejection) {
          vm.confirmError = ApiService.errorMessage(rejection);
          // A 400 usually means another visitor already took some orders.
          if (rejection.status === 400) { load(true); }
        })
        .finally(function () { vm.confirming = false; });
    };

    function load(keepError) {
      vm.loading = true;
      vm.loadError = '';
      var savedError = keepError ? vm.confirmError : '';
      return $q
        .all([
          ApiService.get('/business/me/'),
          ApiService.get('/orders/', { status: 'pending' }),
          ApiService.get('/drivers/'),
          // The engine failing to load must not block planning: the server
          // still computes the route. Only the preview is lost.
          EngineService.ready().then(function () { return true; }, function () { return false; })
        ])
        .then(function (results) {
          vm.business = results[0];
          vm.orders = results[1];
          vm.drivers = results[2];
          vm.engineUnavailable = !results[3];
          vm.selected = {};
          if (vm.driverId === null && vm.drivers.length) { vm.driverId = vm.drivers[0].id; }
          $timeout(function () {
            if (!map) { map = MapService.create('planner-map', depot()); }
            vm.refresh(true);
            vm.confirmError = savedError;
          });
        })
        .catch(function (rejection) { vm.loadError = ApiService.errorMessage(rejection); })
        .finally(function () { vm.loading = false; });
    }

    vm.retry = function () { load(false); };

    $scope.$on('$destroy', function () { MapService.destroy(map); });

    load(false);
  }
})();
