/*
 * CSRF-bescherming (Laravel): voegt het token uit <meta name="csrf-token"> toe
 * aan elke niet-GET fetch() naar dezelfde origin en aan elke HTMX-request.
 * Moet vóór de app-scripts geladen worden (zonder defer).
 */
(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) return;
  var token = meta.getAttribute('content');

  var originalFetch = window.fetch;
  window.fetch = function (input, init) {
    init = init || {};
    var isRequest = typeof Request !== 'undefined' && input instanceof Request;
    var method = (init.method || (isRequest ? input.method : 'GET')).toUpperCase();
    var url = new URL(isRequest ? input.url : String(input), window.location.href);
    if (method !== 'GET' && method !== 'HEAD' && url.origin === window.location.origin) {
      var headers = new Headers(init.headers || (isRequest ? input.headers : undefined));
      if (!headers.has('X-CSRF-TOKEN')) headers.set('X-CSRF-TOKEN', token);
      init.headers = headers;
    }
    return originalFetch.call(this, input, init);
  };

  document.addEventListener('htmx:configRequest', function (event) {
    event.detail.headers['X-CSRF-TOKEN'] = token;
  });
})();
