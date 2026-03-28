# Meta System User Token Setup

## Why

Personal access tokens expire every 60 days, silently breaking the automated launch workflow. System User tokens never expire — they are machine accounts tied to a Business Manager, not to a person.

Without a System User token, the launch pipeline will fail silently after 60 days with a 401 error from the Meta Graph API.

## Prerequisites

- Admin access to Meta Business Manager at [business.facebook.com](https://business.facebook.com)
- The ad account (`META_AD_ACCOUNT_ID`) must be assigned to this Business Manager
- An app associated with your ad account (create one at [developers.facebook.com](https://developers.facebook.com) if needed)

## Steps

### 1. Create a System User

1. Go to Business Manager → **Settings** (gear icon, top right)
2. In the left sidebar, under **Users**, click **System Users**
3. Click **Add** to create a new System User
4. Name: `NEWG Pipeline`
5. Role: **Admin**
6. Click **Create System User**

### 2. Grant Ad Account Access

1. On the System Users page, click your new System User
2. Click **Add Assets**
3. Select **Ad Accounts** → find your ad account
4. Grant **Full Control** access
5. Click **Save Changes**

### 3. Generate the Token

1. Back on the System Users page, click **Generate New Token** next to `NEWG Pipeline`
2. Select the app associated with your ad account
3. Grant these permissions:
   - `ads_management`
   - `ads_read`
   - `pages_read_engagement`
   - `pages_manage_ads`
   - `business_management`
4. Click **Generate Token**
5. **Copy the token immediately** — it is only shown once

## Where to Set the Token

Update `META_ACCESS_TOKEN` in all three locations:

| Location | How |
|----------|-----|
| Railway | Ad-command-center service → **Variables** → `META_ACCESS_TOKEN` |
| GitHub Actions | Repository → **Settings** → **Secrets and variables** → **Actions** → `META_ACCESS_TOKEN` |
| Local development | `.env` file → `META_ACCESS_TOKEN=<token>` |

## Verification

Run this curl command to verify the token is a System User (replace `YOUR_TOKEN`):

```bash
curl "https://graph.facebook.com/v23.0/me?fields=name,id&access_token=YOUR_TOKEN"
```

**Expected output:**
```json
{"name": "NEWG Pipeline", "id": "..."}
```

If the `name` field is a human name (e.g. `"Max Kunnen"`), you are still using a personal token — redo the steps above.

The launcher also checks this automatically at startup and logs:
- `[launcher] Token type: System User confirmed` — correct token
- `[launcher] WARNING: Token may be a personal token` — action required

## Token Rotation

System User tokens do not expire. However, you may need to regenerate a token if:
- The token is accidentally exposed (e.g. committed to git)
- You change app permissions
- Business Manager admin requests a rotation

To rotate:
1. Business Manager → Settings → System Users → **Generate New Token**
2. Update all three locations (Railway, GitHub Actions, `.env`)
3. Verify with the curl command above

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Error validating access token: Session has expired` | Personal token expired | Generate System User token (above) |
| `Invalid OAuth access token` | Token copied incorrectly | Re-copy from Business Manager |
| `Permission error: ads_management` | Missing permission | Regenerate token with all permissions listed above |
| `The user hasn't authorized the application to perform this action` | App not linked to ad account | Add app in Business Manager → Ad Accounts → Apps |
