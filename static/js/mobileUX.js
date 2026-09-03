// Mobile viewport and keyboard helpers.
// This module only adjusts presentation state; chat and upload behavior remain
// owned by their existing modules.

(() => {
  const root = document.documentElement;
  const mobileQuery = window.matchMedia('(max-width: 768px)');
  const composer = document.getElementById('message');

  function syncViewport() {
    const vv = window.visualViewport;
    const height = Math.round(vv && vv.height ? vv.height : window.innerHeight);
    const top = Math.round(vv && vv.offsetTop ? vv.offsetTop : 0);
    const keyboardHeight = Math.max(0, Math.round(window.innerHeight - height - top));
    root.style.setProperty('--app-height', `${height}px`);
    root.style.setProperty('--keyboard-height', `${keyboardHeight}px`);
    root.classList.toggle('keyboard-open', mobileQuery.matches && keyboardHeight > 120);
  }

  function keepComposerVisible() {
    if (!mobileQuery.matches || !composer) return;
    requestAnimationFrame(() => {
      composer.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    });
  }

  syncViewport();
  window.addEventListener('resize', syncViewport, { passive: true });
  window.addEventListener('orientationchange', syncViewport, { passive: true });
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', syncViewport, { passive: true });
    window.visualViewport.addEventListener('scroll', syncViewport, { passive: true });
  }
  mobileQuery.addEventListener?.('change', syncViewport);

  if (composer) {
    composer.addEventListener('focus', () => {
      syncViewport();
      keepComposerVisible();
      setTimeout(syncViewport, 150);
    });
    composer.addEventListener('blur', () => {
      setTimeout(syncViewport, 150);
    });
  }
})();
