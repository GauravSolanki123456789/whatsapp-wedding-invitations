"""Live QR scanner (browser) and server-side decode from photos."""

from __future__ import annotations

import streamlit.components.v1 as components

from constants import QUERY_PARAM_SCAN_TOKEN


def render_live_qr_scanner() -> None:
    """
    Live camera QR scan. On success, submits to parent page with scan_token query param
    (works inside Streamlit iframe via form target=_parent).
    """
    param = QUERY_PARAM_SCAN_TOKEN
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
      <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
      <style>
        * {{ box-sizing: border-box; }}
        body {{
          font-family: system-ui, -apple-system, sans-serif;
          margin: 0; padding: 10px 8px 12px;
          background: #FFFBF7; color: #2C2416;
        }}
        #reader {{
          width: 100%;
          max-width: 100%;
          border-radius: 14px;
          overflow: hidden;
          min-height: 220px;
          background: #1a1a1a;
        }}
        #status {{
          font-size: 0.88rem;
          color: #6B5B52;
          margin: 10px 0 8px;
          text-align: center;
          min-height: 1.3em;
        }}
        .btn {{
          display: block;
          width: 100%;
          padding: 14px 12px;
          margin: 6px 0;
          border-radius: 12px;
          border: none;
          font-size: 1rem;
          font-weight: 700;
          cursor: pointer;
        }}
        .btn-primary {{
          background: linear-gradient(135deg, #b76e79, #9e5560);
          color: #fff;
        }}
        .btn-secondary {{
          background: #fff;
          color: #5c3d42;
          border: 1px solid rgba(183,110,121,0.35);
        }}
        #qrForm {{ display: none; }}
      </style>
    </head>
    <body>
      <form id="qrForm" method="get" target="_parent">
        <input type="hidden" name="{param}" id="scanTokenField" value="" />
      </form>
      <div id="reader"></div>
      <p id="status">Tap <strong>Start scanner</strong> — point at guest QR</p>
      <button type="button" class="btn btn-primary" id="btnStart">Start scanner</button>
      <button type="button" class="btn btn-secondary" id="btnStop" style="display:none;">Stop scanner</button>

      <script>
        let html5QrCode = null;
        let running = false;
        const statusEl = document.getElementById('status');

        function submitToParent(token) {{
          const trimmed = (token || '').trim();
          if (!trimmed) return;
          statusEl.textContent = 'Found QR — opening guest…';
          let navigated = false;
          try {{
            const url = new URL(window.parent.location.href);
            url.searchParams.set('{param}', trimmed);
            window.parent.location.href = url.toString();
            navigated = true;
          }} catch (err) {{ navigated = false; }}
          if (!navigated) {{
            try {{
              const form = document.getElementById('qrForm');
              document.getElementById('scanTokenField').value = trimmed;
              form.action = window.parent.location.pathname || '/';
              form.submit();
            }} catch (e2) {{
              try {{
                window.parent.postMessage({{ type: 'waiv_qr_scan', token: trimmed }}, '*');
              }} catch (e3) {{}}
              statusEl.textContent = 'Use photo backup below if guest screen did not open.';
            }}
          }}
          if (html5QrCode && running) {{
            html5QrCode.stop().then(() => {{
              running = false;
              document.getElementById('btnStart').style.display = 'block';
              document.getElementById('btnStop').style.display = 'none';
            }}).catch(() => {{}});
          }}
        }}

        function onScanSuccess(decodedText) {{
          submitToParent(decodedText);
        }}

        async function startScanner() {{
          if (running) return;
          statusEl.textContent = 'Starting camera…';
          html5QrCode = new Html5Qrcode('reader');
          const config = {{
            fps: 12,
            qrbox: {{ width: Math.min(280, window.innerWidth - 40), height: Math.min(280, window.innerWidth - 40) }},
            aspectRatio: 1.0,
            disableFlip: false,
          }};
          try {{
            await html5QrCode.start(
              {{ facingMode: 'environment' }},
              config,
              onScanSuccess,
              () => {{}}
            );
            running = true;
            statusEl.textContent = 'Live scan on — hold QR in the box';
            document.getElementById('btnStart').style.display = 'none';
            document.getElementById('btnStop').style.display = 'block';
          }} catch (e) {{
            statusEl.textContent = 'Camera unavailable. Allow camera access or use photo backup below.';
          }}
        }}

        async function stopScanner() {{
          if (html5QrCode && running) {{
            await html5QrCode.stop();
            running = false;
            statusEl.textContent = 'Scanner stopped';
            document.getElementById('btnStart').style.display = 'block';
            document.getElementById('btnStop').style.display = 'none';
          }}
        }}

        document.getElementById('btnStart').addEventListener('click', startScanner);
        document.getElementById('btnStop').addEventListener('click', stopScanner);
      </script>
    </body>
    </html>
    """
    components.html(html, height=420, scrolling=False)


def decode_qr_from_image(image_bytes: bytes) -> str | None:
    """Server-side decode fallback (camera photo upload)."""
    try:
        import io as io_module

        from PIL import Image
        from pyzbar.pyzbar import decode as pyzbar_decode

        image = Image.open(io_module.BytesIO(image_bytes))
        codes = pyzbar_decode(image)
        for code in codes:
            text = code.data.decode("utf-8", errors="ignore").strip()
            if text:
                return text
    except Exception:
        pass
    return None
