// Tests for the image-size helper used before uploading a photo.
//   node --test "frontend/tests/*.mjs"
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const RLPhoto = require(join(here, '..', 'js', 'photo-utils.js'));

test('a wide photo is scaled so its long side is the maximum', () => {
  assert.deepEqual(RLPhoto.fitWithin(4000, 3000, 1600), { width: 1600, height: 1200 });
});

test('a tall photo is scaled so its long side is the maximum', () => {
  assert.deepEqual(RLPhoto.fitWithin(3000, 4000, 1600), { width: 1200, height: 1600 });
});

test('a photo that already fits is left alone', () => {
  assert.deepEqual(RLPhoto.fitWithin(800, 600, 1600), { width: 800, height: 600 });
});

test('a photo exactly at the maximum is left alone', () => {
  assert.deepEqual(RLPhoto.fitWithin(1600, 900, 1600), { width: 1600, height: 900 });
});

test('a very thin photo keeps at least one pixel on its short side', () => {
  assert.deepEqual(RLPhoto.fitWithin(1601, 1, 1600), { width: 1600, height: 1 });
});

test('the result is always whole numbers', () => {
  const { width, height } = RLPhoto.fitWithin(4032, 3024, 1600);
  assert.ok(Number.isInteger(width) && Number.isInteger(height));
});

test('empty or invalid sizes are rejected', () => {
  assert.throws(() => RLPhoto.fitWithin(0, 100, 1600), RangeError);
  assert.throws(() => RLPhoto.fitWithin(100, -1, 1600), RangeError);
  assert.throws(() => RLPhoto.fitWithin(100, 100, 0), RangeError);
});

test('photo endpoints end with a slash, which the API requires for POST', () => {
  assert.deepEqual(RLPhoto.photoPaths(3, 7), {
    uploadUrl: '/routes/3/stops/7/photo/upload-url/',
    confirm: '/routes/3/stops/7/photo/',
  });
});
