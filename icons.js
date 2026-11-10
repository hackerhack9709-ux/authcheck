/* =========================================================================
   Icons — inline SVG icon set for PayCheck.

   Stroke-based, 24x24, inherit currentColor. Replaces emoji so the UI reads
   as a product rather than a demo.
   ========================================================================= */
(() => {
  'use strict';

  const P = {
    receipt: '<path d="M5 3.5v17l2.5-1.6 2.5 1.6 2.5-1.6 2.5 1.6 2.5-1.6V3.5L15 5.1l-2.5-1.6L10 5.1 7.5 3.5z"/><path d="M9 8.5h6M9 12h6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    shield: '<path d="M12 3.2 5 6v5.4c0 4 2.9 7.4 7 8.4 4.1-1 7-4.4 7-8.4V6z"/><path d="m9.2 12 2 2 3.6-3.9"/>',
    qr: '<rect x="3.5" y="3.5" width="6.5" height="6.5" rx="1.2"/><rect x="14" y="3.5" width="6.5" height="6.5" rx="1.2"/><rect x="3.5" y="14" width="6.5" height="6.5" rx="1.2"/><path d="M14 14h2.6v2.6H14zM20.5 14v2.6M20.5 20.5h-4M17.8 20.5v-2.6"/>',
    settings: '<circle cx="12" cy="12" r="3.1"/><path d="M19.4 14.4a1.6 1.6 0 0 0 .32 1.77l.06.06a1.9 1.9 0 1 1-2.7 2.7l-.05-.06a1.6 1.6 0 0 0-1.78-.32 1.6 1.6 0 0 0-.97 1.47v.17a1.9 1.9 0 1 1-3.8 0v-.09a1.6 1.6 0 0 0-1.05-1.47 1.6 1.6 0 0 0-1.77.32l-.06.06a1.9 1.9 0 1 1-2.7-2.7l.06-.06a1.6 1.6 0 0 0 .32-1.77 1.6 1.6 0 0 0-1.47-.97h-.17a1.9 1.9 0 0 1 0-3.8h.09A1.6 1.6 0 0 0 4.6 8.6a1.6 1.6 0 0 0-.32-1.77l-.06-.06a1.9 1.9 0 1 1 2.7-2.7l.06.06a1.6 1.6 0 0 0 1.77.32H8.9a1.6 1.6 0 0 0 .97-1.47v-.17a1.9 1.9 0 1 1 3.8 0v.09a1.6 1.6 0 0 0 .97 1.47 1.6 1.6 0 0 0 1.77-.32l.06-.06a1.9 1.9 0 1 1 2.7 2.7l-.06.06a1.6 1.6 0 0 0-.32 1.77v.08a1.6 1.6 0 0 0 1.47.97h.17a1.9 1.9 0 0 1 0 3.8h-.09a1.6 1.6 0 0 0-1.47.97z"/>',
    search: '<circle cx="10.8" cy="10.8" r="6.3"/><path d="m20 20-4.4-4.4"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.2"/><path d="M3.5 9.6h17M8.2 3.5v3M15.8 3.5v3"/>',
    filter: '<path d="M3.5 5.5h17l-6.6 7.8v5.4l-3.8 2v-7.4z"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    copy: '<rect x="8.5" y="8.5" width="12" height="12" rx="2.2"/><path d="M15.5 5.6V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8.5a2 2 0 0 0 2 2h.6"/>',
    bell: '<path d="M18 8.6a6 6 0 1 0-12 0c0 6-2.4 7.4-2.4 7.4h16.8S18 14.6 18 8.6"/><path d="M13.7 19.6a2 2 0 0 1-3.4 0"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    alert: '<path d="M10.3 3.9 2.6 17.2A1.9 1.9 0 0 0 4.3 20h15.4a1.9 1.9 0 0 0 1.7-2.8L13.7 3.9a1.9 1.9 0 0 0-3.4 0z"/><path d="M12 9v4.2M12 16.6h.01"/>',
    xcircle: '<circle cx="12" cy="12" r="8.6"/><path d="m9.2 9.2 5.6 5.6M14.8 9.2l-5.6 5.6"/>',
    checkcircle: '<circle cx="12" cy="12" r="8.6"/><path d="m8.4 12.2 2.4 2.4 4.8-5"/>',
    download: '<path d="M12 3.5v11M7.6 10.2 12 14.6l4.4-4.4"/><path d="M4.5 19.5h15"/>',
    upload: '<path d="M12 20.5v-11M7.6 13.8 12 9.4l4.4 4.4"/><path d="M4.5 4.5h15"/>',
    logout: '<path d="M9.5 20.5H6a2 2 0 0 1-2-2V5.5a2 2 0 0 1 2-2h3.5"/><path d="M15.5 16.5 20 12l-4.5-4.5M20 12H9.5"/>',
    user: '<circle cx="12" cy="8.2" r="3.7"/><path d="M4.8 20.2a7.4 7.4 0 0 1 14.4 0"/>',
    chat: '<path d="M20.5 11.6a7.6 7.6 0 0 1-8.2 7.6 9 9 0 0 1-2.6-.5l-4.7 1.4 1.5-4.3a7.3 7.3 0 0 1-.9-3.6 7.6 7.6 0 0 1 7.6-7.6 7.6 7.6 0 0 1 7.3 7z"/><path d="M9.3 9.4c.4-.9 1.7-.9 2 0l.3 1.1c.1.4-.1.8-.4 1l-.5.4c.6 1.1 1.5 2 2.6 2.6l.4-.5c.2-.3.6-.5 1-.4l1.1.3c.9.3.9 1.6 0 2a3.6 3.6 0 0 1-1.6.4c-3 0-5.5-2.5-5.5-5.5 0-.6.1-1.1.4-1.6z"/>',
    lock: '<rect x="4.5" y="10.4" width="15" height="10.1" rx="2.2"/><path d="M8.2 10.4V7.6a3.8 3.8 0 0 1 7.6 0v2.8"/>',
    info: '<circle cx="12" cy="12" r="8.6"/><path d="M12 11.2v4.6M12 8.4h.01"/>',
    store: '<path d="M4 9.6V19a1.4 1.4 0 0 0 1.4 1.4h13.2A1.4 1.4 0 0 0 20 19V9.6"/><path d="M3.2 9.6 4.7 4.2A1.3 1.3 0 0 1 6 3.3h12a1.3 1.3 0 0 1 1.3.9l1.5 5.4a2.6 2.6 0 0 1-4.9 1 2.6 2.6 0 0 1-4.9 0 2.6 2.6 0 0 1-4.9 0 2.6 2.6 0 0 1-4.9-1z"/><path d="M9.6 20.4v-5.2h4.8v5.2"/>',
    refresh: '<path d="M20 11.5A8 8 0 0 0 6.3 6.3L4 8.5"/><path d="M4 4.5v4h4"/><path d="M4 12.5a8 8 0 0 0 13.7 5.2L20 15.5"/><path d="M20 19.5v-4h-4"/>',
    activity: '<path d="M3.5 12h4l2.5-6 4 12 2.5-6h4"/>',
    layers: '<path d="m12 3.2 8.5 4.4L12 12 3.5 7.6z"/><path d="m3.5 12.4 8.5 4.4 8.5-4.4"/><path d="m3.5 16.8 8.5 4.4 8.5-4.4"/>'
  };

  /** Return an <svg> string. size in px, stroke scales with it. */
  function Icon(name, size = 20) {
    const body = P[name];
    if (!body) return '';
    const sw = (24 / size) * 1.15;
    return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none"
      stroke="currentColor" stroke-width="${sw.toFixed(2)}"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`;
  }

  /** Icon inside a span, so callers can keep using innerHTML. */
  Icon.el = (name, cls = 'ico', size = 20) => `<span class="${cls}">${Icon(name, size)}</span>`;

  Icon.has = (name) => !!P[name];
  Icon.names = () => Object.keys(P);

  window.Icon = Icon;
})();
