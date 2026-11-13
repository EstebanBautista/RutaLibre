// Everything that touches Leaflet lives here, so controllers describe what
// to show (points, routes) and never how to draw it.
(function () {
  'use strict';

  angular.module('rutalibre').factory('MapService', MapService);

  MapService.$inject = ['$rootScope'];
  function MapService($rootScope) {
    function latLng(point) { return [point.lat, point.lng]; }

    // Leaflet inserts tooltip and icon content as HTML. Customer names are
    // typed by users, so they are always passed as text nodes, never markup.
    function textNode(text) {
      var span = document.createElement('span');
      span.textContent = text === undefined || text === null ? '' : String(text);
      return span;
    }

    function icon(kind, label) {
      return L.divIcon({
        className: 'pin pin--' + kind,
        html: textNode(label),
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });
    }

    return {
      // Creates a map inside the element with the given id. `center` is {lat, lng}.
      create: function (elementId, center) {
        // zoomSnap below 1 lets fitBounds fill the view instead of jumping a whole level.
        var map = L.map(elementId, { zoomControl: true, attributionControl: true, zoomSnap: 0.25 })
          .setView(latLng(center), 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(map);
        map._rlLayers = L.layerGroup().addTo(map);
        return map;
      },

      // points: [{lat, lng, kind, label, title}]. kind picks the pin style:
      // depot, pending, assigned, delivered, selected, draft.
      setMarkers: function (map, points) {
        points.forEach(function (point) {
          var marker = L.marker(latLng(point), {
            icon: icon(point.kind || 'pending', point.label),
            title: point.title || '',
            keyboard: false,
            zIndexOffset: point.kind === 'depot' ? 500 : 0
          });
          if (point.title) { marker.bindTooltip(textNode(point.title)); }
          marker.addTo(map._rlLayers);
        });
      },

      // Draws a closed or open path through the points, in order.
      drawRoute: function (map, points, options) {
        options = options || {};
        if (points.length < 2) { return; }
        L.polyline(points.map(latLng), {
          color: options.color || '#0b6b4f',
          weight: options.weight || 4,
          opacity: options.opacity || 0.9,
          dashArray: options.dashed ? '6 8' : null,
          lineJoin: 'round'
        }).addTo(map._rlLayers);
      },

      clear: function (map) { map._rlLayers.clearLayers(); },

      // Zooms so every point is visible. Does nothing for an empty list.
      fit: function (map, points) {
        if (!points.length) { return; }
        map.fitBounds(L.latLngBounds(points.map(latLng)), { padding: [28, 28], maxZoom: 15 });
      },

      // Calls cb({lat, lng}) inside Angular's digest when the map is clicked.
      onClick: function (map, cb) {
        map.on('click', function (event) {
          $rootScope.$applyAsync(function () {
            cb({ lat: event.latlng.lat, lng: event.latlng.lng });
          });
        });
      },

      destroy: function (map) { if (map) { map.remove(); } }
    };
  }
})();
