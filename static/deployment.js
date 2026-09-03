/* Deployment bridge for a Cloudflare Pages frontend and remote GepLex API. */
(function () {
  var config = window.GEPLEX_DEPLOYMENT || {};
  var storedApi = '';
  try {
    storedApi = localStorage.getItem('geplex-backend-api-url') || '';
  } catch (_) {}
  var apiBase = String(storedApi || config.apiBase || '').replace(/\/+$/, '');
  window.__GEPLEX_API_BASE = apiBase;
  if (!apiBase) return;

  var nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var request = input instanceof Request ? input : null;
    var url = request ? request.url : String(input);
    var origin = window.location.origin;
    if (url.indexOf(origin + '/api/') === 0) {
      url = url.substring(origin.length);
    }
    if (url.indexOf('/api/') === 0) {
      url = apiBase + url;
      if (request) input = new Request(url, request);
      else input = url;
    }
    init = init || {};
    if (!init.credentials) init.credentials = 'include';
    return nativeFetch(input, init);
  };
})();
