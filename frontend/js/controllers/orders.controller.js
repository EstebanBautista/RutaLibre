(function () {
  'use strict';

  angular.module('rutalibre').controller('OrdersController', OrdersController);

  OrdersController.$inject = ['$scope', '$q', '$timeout', 'ApiService', 'MapService'];
  function OrdersController($scope, $q, $timeout, ApiService, MapService) {
    var vm = this;
    var map = null;

    vm.loading = true;
    vm.loadError = '';
    vm.orders = [];
    vm.business = null;
    vm.saving = false;
    vm.formError = '';
    vm.listError = '';
    vm.draft = emptyDraft();

    function emptyDraft() {
      return { customer_name: '', address: '', notes: '', lat: null, lng: null };
    }

    vm.hasLocation = function () { return vm.draft.lat !== null; };

    vm.countBy = function (status) {
      return vm.orders.filter(function (order) { return order.status === status; }).length;
    };

    function redraw(fit) {
      if (!map || !vm.business) { return; }
      var depot = { lat: vm.business.depot_lat, lng: vm.business.depot_lng };
      var points = [{ lat: depot.lat, lng: depot.lng, kind: 'depot', title: 'Depósito: ' + vm.business.name }];
      vm.orders.forEach(function (order) {
        points.push({ lat: order.lat, lng: order.lng, kind: order.status, title: order.customer_name });
      });
      if (vm.hasLocation()) {
        points.push({ lat: vm.draft.lat, lng: vm.draft.lng, kind: 'draft', label: '+', title: 'Ubicación del nuevo pedido' });
      }
      MapService.clear(map);
      MapService.setMarkers(map, points);
      if (fit) { MapService.fit(map, points); }
    }

    function load() {
      vm.loading = true;
      vm.loadError = '';
      return $q
        .all([ApiService.get('/business/me/'), ApiService.get('/orders/')])
        .then(function (results) {
          vm.business = results[0];
          vm.orders = results[1];
          // The map element only exists once the view has rendered.
          $timeout(function () {
            if (!map) {
              map = MapService.create('orders-map', { lat: vm.business.depot_lat, lng: vm.business.depot_lng });
              MapService.onClick(map, function (point) {
                vm.draft.lat = point.lat;
                vm.draft.lng = point.lng;
                vm.formError = '';
                redraw(false);
              });
            }
            redraw(true);
          });
        })
        .catch(function (rejection) { vm.loadError = ApiService.errorMessage(rejection); })
        .finally(function () { vm.loading = false; });
    }

    vm.retry = load;

    vm.save = function () {
      if (!vm.draft.customer_name.trim() || !vm.draft.address.trim()) {
        vm.formError = 'Escribe el cliente y la dirección.';
        return;
      }
      if (!vm.hasLocation()) {
        vm.formError = 'Haz clic en el mapa para marcar dónde se entrega.';
        return;
      }
      vm.saving = true;
      vm.formError = '';
      ApiService.post('/orders/', vm.draft)
        .then(function (order) {
          vm.orders.unshift(order);
          vm.draft = emptyDraft();
          redraw(false);
        })
        .catch(function (rejection) { vm.formError = ApiService.errorMessage(rejection); })
        .finally(function () { vm.saving = false; });
    };

    vm.clearLocation = function () {
      vm.draft.lat = null;
      vm.draft.lng = null;
      redraw(false);
    };

    vm.remove = function (order) {
      order.removing = true;
      vm.listError = '';
      ApiService.delete('/orders/' + order.id + '/')
        .then(function () {
          vm.orders = vm.orders.filter(function (other) { return other.id !== order.id; });
          redraw(false);
        })
        .catch(function (rejection) {
          order.removing = false;
          vm.listError = ApiService.errorMessage(rejection);
        });
    };

    $scope.$on('$destroy', function () { MapService.destroy(map); });

    load();
  }
})();
