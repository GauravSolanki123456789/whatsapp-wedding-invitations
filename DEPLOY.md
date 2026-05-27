# Free hosting — WhatsApp Wedding Invitations

Two **100% free** options. Pick one.

---

## Option A — Permanent link (recommended)

**Streamlit Community Cloud** — free forever, works when your laptop is off.

### Step 1 — Create a free GitHub account

1. Go to https://github.com/signup
2. Create account (free)

### Step 2 — Create a new repository

1. Go to https://github.com/new
2. Repository name: `whatsapp-wedding-invitations`
3. Choose **Public**
4. Do **not** add README (we already have one)
5. Click **Create repository**

### Step 3 — Push this project to GitHub

Open PowerShell in the project folder and run (replace `YOUR_USERNAME`):

```powershell
cd c:\Users\HP\Downloads\whatsappInvitees

git init
git add .
git commit -m "Deploy WhatsApp Wedding Invitations app"

git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/whatsapp-wedding-invitations.git
git push -u origin main
```

When asked to sign in, use your GitHub username and a **Personal Access Token** (not password):
- Create token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token (classic) → check `repo` → Generate

### Step 4 — Deploy on Streamlit Cloud (free)

1. Go to https://share.streamlit.io
2. Sign in with **GitHub**
3. Click **New app**
4. Select your repo: `whatsapp-wedding-invitations`
5. Main file path: `app.py`
6. Click **Deploy**

Wait 2–3 minutes. You get a link like:

`https://YOUR_USERNAME-whatsapp-wedding-invitations-app-xxxxx.streamlit.app`

**Save this link** — open it on your phone, add to Home Screen.

### What works on hosted link

| Feature | Works? |
|---------|--------|
| Upload Excel guest list | Yes |
| Compose message + attach video | Yes |
| **Quick Send** (wa.me links) | Yes — on phone & laptop |
| Auto Send (Chrome automation) | No — laptop local only |

---

## Option B — Instant free link (no GitHub)

While your laptop is running:

1. Install Cloudflare tunnel (one time):
   ```powershell
   winget install Cloudflare.cloudflared
   ```

2. Double-click or run:
   ```powershell
   c:\Users\HP\Downloads\whatsappInvitees\scripts\free-tunnel.bat
   ```

3. Copy the `https://....trycloudflare.com` URL shown in the terminal
4. Open that URL on your phone

Link stops when you close the terminal. Use Option A for a permanent link.

---

## Use on phone like an app

1. Open your hosted link in **Chrome** (Android) or **Safari** (iPhone)
2. **Android:** ⋮ menu → **Add to Home screen**
3. **iPhone:** Share → **Add to Home Screen**
4. Use **Quick Send** — each tap opens WhatsApp with your message ready

---

## Quick Send workflow (hosted or local)

1. Upload guest list
2. Write message + attach video
3. **Quick Send** → tap **Open WhatsApp** for each guest
4. In WhatsApp: 📎 attach file → Send
5. Back to app → **Mark as sent** → next guest

---

## Troubleshooting

**App sleeps on free tier** — first visit after idle may take 30s to wake up. Normal on free hosting.

**Guest list resets** — on free cloud, re-upload Excel each session (or keep list in the editor).

**Auto Send greyed out on hosted link** — expected. Use Quick Send or run locally for Auto Send.
