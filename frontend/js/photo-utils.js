// Image-size helper for evidence photos. Plain JavaScript with no framework so
// the browser and the Node tests run the same file.
(function (root) {
  'use strict';

  // Size a width x height image should be drawn at so its long side is at most
  // `max` pixels. Keeps the proportions, never enlarges, and never returns a
  // side smaller than 1 pixel. Always whole numbers.
  function fitWithin(width, height, max) {
    if (!(width > 0) || !(height > 0) || !(max > 0)) {
      throw new RangeError('width, height and max must be positive numbers');
    }
    var scale = Math.min(1, max / Math.max(width, height));
    return {
      width: Math.max(1, Math.round(width * scale)),
      height: Math.max(1, Math.round(height * scale))
    };
  }

  // API paths for a stop's photo. Both end with a slash: Django cannot redirect
  // a POST that is missing it and answers with an error instead.
  function photoPaths(routeId, stopId) {
    var base = '/routes/' + routeId + '/stops/' + stopId + '/photo/';
    return { uploadUrl: base + 'upload-url/', confirm: base };
  }

  var RLPhoto = { fitWithin: fitWithin, photoPaths: photoPaths, MAX_SIDE: 1600, JPEG_QUALITY: 0.8 };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RLPhoto; // Node (tests)
  } else {
    root.RLPhoto = RLPhoto; // browser
  }
})(typeof self !== 'undefined' ? self : this);
