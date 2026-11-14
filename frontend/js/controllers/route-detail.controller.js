(function () {
  'use strict';

  angular.module('rutalibre').controller('RouteDetailController', RouteDetailController);

  RouteDetailController.$inject = ['$scope', '$routeParams', '$timeout', 'ApiService', 'MapService', 'PhotoService'];
  function RouteDetailController($scope, $routeParams, $timeout, ApiService, MapService, PhotoService) {
    var vm = this;
    var map = null;

    vm.loading = true;
    vm.loadError = '';
    vm.notFound = false;
    vm.route = null;
    vm.deliverError = '';
    vm.delivering = {}; // stop id -> true while its request is in flight
    vm.photosEnabled = false;
    vm.uploading = {}; // stop id -> true while its photo is being sent
    vm.photoError = {}; // stop id -> message to show under that stop

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

    // Called by the file input of a stop (see the photoPicker directive).
    vm.attachPhoto = function (stop, file) {
      if (vm.uploading[stop.id] || !file) { return; }
      vm.uploading[stop.id] = true;
      vm.photoError[stop.id] = '';
      PhotoService.upload(vm.route.id, stop.id, file)
        .then(function (route) { show(route, false); })
        .catch(function (error) {
          // Local errors are Error objects; API errors are HTTP responses.
          vm.photoError[stop.id] = error instanceof Error ? error.message : ApiService.errorMessage(error);
        })
        .finally(function () { delete vm.uploading[stop.id]; });
    };

    // A thumbnail whose link has expired or broken is simply hidden.
    vm.hidePhoto = function (stop) { stop.photo_url = null; };

    function load() {
      vm.loading = true;
      vm.loadError = '';
      vm.notFound = false;
      // The business tells us whether photo storage is configured on the server.
      ApiService.get('/business/me/')
        .then(function (business) { vm.photosEnabled = !!business.photos_enabled; })
        .catch(angular.noop);
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

  // <input type="file" photo-picker="vm.attachPhoto(stop, file)">
  // ng-model does not support file inputs, so this reads the change event.
  angular.module('rutalibre').directive('photoPicker', function () {
    return {
      restrict: 'A',
      scope: { onPick: '&photoPicker' },
      link: function (scope, element) {
        element.on('change', function () {
          var file = element[0].files[0];
          element[0].value = ''; // lets the same file be chosen again later
          scope.$apply(function () { scope.onPick({ file: file }); });
        });
        scope.$on('$destroy', function () { element.off('change'); });
      }
    };
  });
})();
