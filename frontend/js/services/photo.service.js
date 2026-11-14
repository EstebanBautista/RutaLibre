// Attaching an evidence photo to a route stop.
//
// 1. Shrink the image in the browser (a phone photo can be 4 MB or more).
// 2. Ask the API for a short-lived upload URL.
// 3. PUT the image straight to the storage bucket.
// 4. Tell the API the upload is done so it can check and record it.
(function () {
  'use strict';

  angular.module('rutalibre').factory('PhotoService', PhotoService);

  PhotoService.$inject = ['$http', '$q', '$window', 'ApiService'];
  function PhotoService($http, $q, $window, ApiService) {
    // Draws the file onto a canvas at the reduced size and returns a JPEG Blob.
    function shrink(file) {
      return $q(function (resolve, reject) {
        var url = $window.URL.createObjectURL(file);
        var image = new $window.Image();
        image.onload = function () {
          $window.URL.revokeObjectURL(url);
          var size = $window.RLPhoto.fitWithin(
            image.naturalWidth, image.naturalHeight, $window.RLPhoto.MAX_SIDE);
          var canvas = $window.document.createElement('canvas');
          canvas.width = size.width;
          canvas.height = size.height;
          canvas.getContext('2d').drawImage(image, 0, 0, size.width, size.height);
          canvas.toBlob(function (blob) {
            if (blob) { resolve(blob); } else { reject(new Error('No se pudo preparar la foto.')); }
          }, 'image/jpeg', $window.RLPhoto.JPEG_QUALITY);
        };
        image.onerror = function () {
          $window.URL.revokeObjectURL(url);
          reject(new Error('No se pudo leer la imagen. Prueba con otra foto.'));
        };
        image.src = url;
      });
    }

    return {
      // Resolves with the updated route detail returned by the API.
      upload: function (routeId, stopId, file) {
        if (!file || !/^image\//.test(file.type)) {
          return $q.reject(new Error('Elige un archivo de imagen.'));
        }
        var paths = $window.RLPhoto.photoPaths(routeId, stopId);
        return shrink(file).then(function (blob) {
          return ApiService.post(paths.uploadUrl).then(function (grant) {
            // A plain $http call to another host: the interceptor only adds the
            // session token to our own API, and the bucket must not receive it.
            return $http.put(grant.upload_url, blob, {
              headers: grant.headers,
              transformRequest: angular.identity
            }).catch(function () {
              return $q.reject(new Error('No se pudo subir la foto. Intenta de nuevo.'));
            }).then(function () {
              return ApiService.post(paths.confirm, { key: grant.key });
            });
          });
        });
      }
    };
  }
})();
