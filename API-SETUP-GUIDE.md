# API Setup Guide — NEWGARMENTS Ad Creation System

Vul alle API keys in na het volgen van de stappen hieronder.
Configuratiebestand: `.claude/settings.json`

---

## 1. GitHub Personal Access Token

### Wat het doet
Geeft Claude toegang tot GitHub repositories voor code management en versiebeheer.

### Stap-voor-stap
1. Ga naar [github.com/settings/tokens](https://github.com/settings/tokens)
2. Klik **"Generate new token (classic)"**
3. Geef het een naam: `claude-code-newgarments`
4. Stel expiratie in: **90 dagen** (of langer naar wens)
5. Vink deze permissions aan:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
   - `read:org` (Read org membership)
6. Klik **"Generate token"**
7. **Kopieer de token DIRECT** — je ziet hem maar 1x

### Invullen
Open `.claude/settings.json` en vervang:
```
"GITHUB_TOKEN": "VULL_HIER_JE_TOKEN_IN"
```
met:
```
"GITHUB_TOKEN": "ghp_jouw_token_hier"
```

---

## 2. Brave Search API

### Wat het doet
Geeft Claude de mogelijkheid om het internet te doorzoeken voor trends, competitor research en inspiratie.

### Stap-voor-stap
1. Ga naar [brave.com/search/api/](https://brave.com/search/api/)
2. Klik **"Get Started"**
3. Maak een account aan (of log in)
4. Kies het **Free plan** (2.000 queries per maand — meer dan genoeg)
5. Ga naar je Dashboard → **API Keys**
6. Klik **"Create API Key"**
7. Naam: `claude-newgarments`
8. Kopieer de key

### Invullen
Open `.claude/settings.json` en vervang:
```
"BRAVE_API_KEY": "VULL_HIER_JE_KEY_IN"
```
met:
```
"BRAVE_API_KEY": "BSA_jouw_key_hier"
```

### Limieten
- Free tier: 2.000 queries/maand
- Rate limit: 1 query/seconde
- Resultaten: max 20 per query

---

## 3. Google Drive MCP

### Wat het doet
Geeft Claude toegang tot Google Drive bestanden (afbeeldingen, documenten, spreadsheets).

### Stap-voor-stap

#### A. Google Cloud Project aanmaken
1. Ga naar [console.cloud.google.com](https://console.cloud.google.com/)
2. Klik op het project dropdown (bovenaan) → **"New Project"**
3. Naam: `newgarments-claude`
4. Klik **"Create"**

#### B. Google Drive API inschakelen
1. In je nieuwe project, ga naar **APIs & Services → Library**
2. Zoek "Google Drive API"
3. Klik **"Enable"**

#### C. OAuth Credentials maken
1. Ga naar **APIs & Services → Credentials**
2. Klik **"Create Credentials" → "OAuth client ID"**
3. Je moet mogelijk eerst een **consent screen** configureren:
   - User type: **External**
   - App name: `newgarments-claude`
   - Email: jouw email
   - Scopes: voeg `drive.readonly` toe
   - Test users: voeg jouw email toe
4. Terug bij Credentials:
   - Application type: **Desktop app**
   - Naam: `claude-drive-access`
5. Download het **JSON** bestand
6. Hernoem naar `gcp-oauth.keys.json`
7. Plaats in de root van dit project

#### D. Authenticatie uitvoeren
De eerste keer dat je de Google Drive MCP gebruikt, opent er een browser window voor OAuth. Log in met je Google account en sta toegang toe.

---

## 4. Notion API

### Wat het doet
Geeft Claude toegang tot Notion databases voor content planning en tracking.

### Stap-voor-stap

#### A. Integration aanmaken
1. Ga naar [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Klik **"New integration"**
3. Naam: `NEWGARMENTS Claude`
4. Associated workspace: kies je workspace
5. Capabilities: vink aan:
   - Read content
   - Update content
   - Insert content
6. Klik **"Submit"**
7. Kopieer de **Internal Integration Secret** (begint met `ntn_`)

#### B. Database delen met integration
1. Open de Notion database die je wilt gebruiken
2. Klik **"..." (menu)** rechtsboven → **"Connections"**
3. Zoek `NEWGARMENTS Claude` en voeg toe
4. Herhaal voor elke database die Claude moet kunnen lezen

#### C. Database ID vinden
1. Open de database in Notion (full page view)
2. De URL ziet er zo uit: `notion.so/Workspace/DATABASE_ID?v=VIEW_ID`
3. De DATABASE_ID is het deel tussen de laatste `/` en de `?`
4. Bewaar deze IDs in `config/automation-settings.json`

### Invullen
Open `.claude/settings.json` en vervang:
```
"NOTION_API_KEY": "VULL_HIER_JE_KEY_IN"
```
met:
```
"NOTION_API_KEY": "ntn_jouw_key_hier"
```

---

## 5. Higgsfield API (Video Generatie)

### Wat het doet
AI video generatie voor fashion content — model probeerscenes, product showcases, motion content.

### Stap-voor-stap
1. Ga naar [higgsfield.ai](https://higgsfield.ai)
2. Maak een account aan
3. Ga naar **Dashboard → API Settings**
4. Genereer een API key
5. Bewaar de key in `.env`:
   ```
   HIGGSFIELD_API_KEY=jouw_key_hier
   ```

### Limieten & Pricing
- Check het huidige pricing model op hun website
- Houd rekening met rate limits bij batch-generatie
- Bewaar credits door eerst thumbnails/previews te genereren

### Best practices
- Upload hoge-resolutie reference images (min 1024x1024)
- Gebruik consistente lighting in reference photos
- Test met 1 item voor je batch-runt

---

## Verificatie Checklist

Na het invullen van alle keys, gebruik dit om te checken:

| Service | Key ingevuld? | Getest? | Werkt? |
|---------|--------------|---------|--------|
| GitHub | [ ] | [ ] | [ ] |
| Brave Search | [ ] | [ ] | [ ] |
| Google Drive | [ ] | [ ] | [ ] |
| Notion | [ ] | [ ] | [ ] |
| Higgsfield | [ ] | [ ] | [ ] |
| Meta (bestaand in .env) | [x] | [ ] | [ ] |

---

## Troubleshooting

### "MCP server failed to start"
- Check of Node.js is geïnstalleerd: `node --version` (v18+ nodig)
- Check of npx werkt: `npx --version`
- Probeer de MCP server handmatig: `npx -y @modelcontextprotocol/server-filesystem .`

### "Authentication failed"
- Check of de API key correct is gekopieerd (geen spaties ervoor/erna)
- Check of de key niet verlopen is
- Voor Google Drive: verwijder cached credentials en doe de OAuth flow opnieuw

### "Permission denied"
- GitHub: check of de juiste permissions zijn aangevinkt
- Notion: check of de database gedeeld is met de integration
- Google Drive: check of je account als test user is toegevoegd
