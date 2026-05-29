# Wedding app guide — WhatsApp API, calls, and gifts

## 0. Multi-phone sync (IMPORTANT for staff scanning)

**Without a cloud database, each phone has its own copy of data** — scans on Phone A won’t show on Phone B.

### Set up free Supabase (5 minutes)

1. Go to [supabase.com](https://supabase.com) → New project (free).
2. Wait for the database to provision.
3. Click **Connect** → choose **Session pooler** (NOT “Direct connection”).
4. Copy the **URI** — host must be `aws-0-….pooler.supabase.com`, user `postgres.YOUR_PROJECT_REF`.
5. Streamlit Cloud → **Settings → Secrets**:

```toml
DATABASE_URL = "postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
```

6. Save → app reboots. Top shows **Cloud DB — all phones synced**.

**Why Direct fails:** `db….supabase.co:5432` is IPv6-only; Streamlit Cloud is IPv4-only. Use Session pooler URI from Supabase (the app also auto-converts Direct URLs when possible).

Now families, lists, gift counts, and scans are **shared live** across every staff phone.

See `.streamlit/secrets.toml.example` in the project for a template.

---

## 1. Sending 800–900 WhatsApp messages this month

### Option A — Quick Send (already in app, free)

Works on your hosted Streamlit link and phone:

1. Create a **named list** (e.g. Ranka Invitations) under **Lists**.
2. **Compose** your text + attach video (use **Download attachment** on each guest if video does not auto-attach).
3. **Send → Guided Send** — one guest at a time; best on phone.

**Limits:** Manual taps; safe for personal WhatsApp; not true bulk API.

### Option B — WhatsApp Business Cloud API (official, ~800+ in a month)

Your father’s **WhatsApp Business** app is not the same as the **Cloud API**. For automated bulk sends you need:

1. [Meta Business Suite](https://business.facebook.com/) — Business account.
2. [WhatsApp Business Platform](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) — create an app, add WhatsApp product.
3. **Phone number** — dedicated number for API (can migrate Business number with care).
4. **Message templates** — Meta must **approve** templates before bulk send (24–48h).
5. **Billing** — conversation-based pricing (India: check current Meta rates). Budget for ~900 marketing/utility conversations.

**Streamlit secrets** (Settings → Secrets on share.streamlit.io):

```toml
WHATSAPP_ACCESS_TOKEN = "your_token"
WHATSAPP_PHONE_NUMBER_ID = "your_phone_number_id"
```

Then use **Integrations** tab when configured.

**One-month tip:** Use API only for invitation + QR; keep voice/group on phone if budget is tight.

---

## 2. Automated voice calls (“You are invited…”)

Use **Twilio** (or Exotel for India):

1. Record a short MP3 invitation.
2. Host TwiML URL or use Twilio Studio.
3. Secrets:

```toml
TWILIO_ACCOUNT_SID = "..."
TWILIO_AUTH_TOKEN = "..."
TWILIO_CALL_FROM_NUMBER = "+91..."
```

Calls cost per minute; test with 5 numbers first.

**Without API:** Export list → use manual calling team with the same Excel lists in the app.

---

## 3. Named guest lists (Ranka, Solanki, …)

1. Top bar: select **Family** (e.g. Solanki Family).
2. Tab **Lists** → create **Ranka Invitations** → upload Excel.
3. When sending, enable **Use saved list** and pick the list.

Sample Excel: **Download sample (guest list)** in the Lists tab.

---

## 4. Gift QR at functions (Mayara, Reception, …)

1. **Family** → **Functions** tab → add function name.
2. Upload guest Excel with `guest_name`, `mobile_number`, `gift_quantity`.
3. **Generate QR cards** → ZIP of PNGs per guest.
4. Send PNGs via WhatsApp (Guided Send + attach image, or API template with image URL).
5. Staff: **Scan** tab → camera or paste token → enter gifts handed out.
6. **Reports** → pending vs given.

**Same QR, partial gifts:** First scan gives 1 of 4 → pending 3; next relative scans same QR → staff see **3 pending**.

---

## 5. Multi-family (Solanki vs Lalwani)

- **Families** tab: add family, switch selector at top.
- Data is isolated per family in `data/app.db`.
- On Streamlit Cloud free tier, DB may reset on redeploy — for production use [Streamlit persistent storage](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/app-settings#secrets) or mount external DB via `DATABASE_URL=sqlite:///...`.

---

## 6. Fixing video / attachment on phone

1. Compose tab → upload file → wait for green **Attached** message.
2. Send tab → **Save attachment on phone** (or Guided Send download button).
3. Open WhatsApp → 📎 → choose downloaded file → Send.

Hosted app cannot auto-attach video inside WhatsApp (browser limitation).

---

## 7. Staff scanning on iPhone / Android

- **Scan** tab → **Take photo of QR** (works on Safari) or paste token.
- Allow camera permission.
- Bright screen for guest QR; avoid glare.
