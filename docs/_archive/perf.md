# Viewer Performance Trace

Trace file: `docs/trace_viewer.json`

## Summary (Chrome DevTools MCP)
- LCP: 61 ms
- INP: 40 ms
- CLS: 0.01
- Trace target: `http://127.0.0.1:8765/` (simulator viewer load + heatmap toggle)

## Bottlenecks Observed
- Render-blocking CSS requests (`styles.css`, Google Fonts) reported as render-blocking resources.
- No cache TTL for static assets (`vendor/*.js`, `styles.css`, `app.js`) causing repeated downloads.
- Missing `/utils/BufferGeometryUtils.js` triggered 404 noise (non-fatal).

## Fixes Applied
- Added `Cache-Control: public, max-age=86400` for static JS/CSS/images in `app/sim_server.py` to improve repeat-load performance.
- Added static alias for `/utils/BufferGeometryUtils.js` to prevent 404s.

## Follow-ups (Optional)
- Self-host fonts or preconnect/preload the Google Fonts CSS to reduce render-blocking dependency.
- Consider bundling `vendor/*.js` into a single module for fewer requests.
