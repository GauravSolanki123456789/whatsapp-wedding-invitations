# WhatsApp Wedding Invitations

Send wedding invitations to a guest list via WhatsApp — on **laptop** or **phone**.

## Run locally

```powershell
cd c:\Users\HP\Downloads\whatsappInvitees
pip install -r requirements.txt
streamlit run app.py
```

Open: http://localhost:8501

## Recommended: Quick Send (phone & laptop)

1. Upload Excel guest list (column 2 = mobile numbers)
2. Write your message and attach video/photo
3. Go to **4 · Send** → **Quick Send**
4. For each guest tap **Open WhatsApp**
5. In WhatsApp: tap 📎 → attach the same file → tap Send
6. Come back to the app → **Mark as sent** → next guest

This uses official `wa.me` links — the most reliable method. Works on Android/iPhone when the app is hosted online.

## Use on your phone (like an app)

WhatsApp cannot auto-attach files via links (that is a WhatsApp limitation). Quick Send pre-fills the text; you attach the file once per guest in WhatsApp.

### Option A — Add to Home Screen (easiest)

1. Host the app (see below)
2. Open the URL in **Chrome on Android** or **Safari on iPhone**
3. **Android:** Menu → Add to Home screen
4. **iPhone:** Share → Add to Home Screen

### Option B — Host online (free permanent link)

**Full step-by-step:** see **[DEPLOY.md](DEPLOY.md)** — GitHub + Streamlit Community Cloud (100% free).

Quick summary:
1. Push this folder to a free GitHub repo
2. Deploy at [share.streamlit.io](https://share.streamlit.io) → New app → `app.py`
3. Open your `.streamlit.app` link on your phone

**Instant link (no GitHub):** run `scripts\free-tunnel.bat` while your laptop is on.

### Option C — APK wrapper

Wrap your hosted URL in a WebView app (Android Studio / Capacitor). Point the WebView to your hosted Streamlit URL. Quick Send buttons will open the WhatsApp app on the phone.

## Create WhatsApp group

After uploading your guest list, use **Create WhatsApp group** (below step 2):

- **Quick Group (phone & laptop)** — Download `wedding_guest_contacts.vcf`, import on your phone, then WhatsApp → New group → select all **Wedding Guest** contacts. Works reliably on mobile.
- **Auto Group (laptop only)** — One button creates the group in automation Chrome (same window as Auto Send). Numbers must be findable in WhatsApp search.

WhatsApp allows up to **256** members when creating a group.

## Auto Send (laptop only)

Uses a **separate Chrome window** (your normal Chrome stays open) to send messages and attachments automatically.

**First time:** scan the QR code in the automation Chrome window with your phone. You stay logged in after that.

Before auto send:
- Run the app in **Edge or Brave** (not Chrome)
- Keep the automation Chrome window **maximized and visible**
- Video must be under 100 MB
- If it fails, use **Quick Send** (always works)

## Guest list Excel format

| Column 1 (ignored) | Column 2 (mobile_number) |
|--------------------|--------------------------|
| Name               | +919841188881            |

Country code `+91` is applied in Settings for numbers without a prefix.
