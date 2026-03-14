# 🚀 Deploy Bot 24/7 on Railway (Free)

Your bot goes offline when your laptop closes. Fix this by deploying to Railway — it's free and takes 5 minutes.

## Step 1 — Push code to GitHub

1. Go to https://github.com and create a new repository called `wan-bot`
2. Make it **Private** (your token is in .env)
3. Open Terminal and run:

```bash
cd ~/Desktop/WAN\ bot
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/wan-bot.git
git push -u origin main
```

## Step 2 — Deploy on Railway

1. Go to https://railway.app
2. Sign up with GitHub
3. Click **New Project** → **Deploy from GitHub repo**
4. Select your `wan-bot` repository
5. Railway will auto-detect Python and start deploying

## Step 3 — Add Environment Variables

In Railway dashboard → your project → **Variables** tab, add:

```
DISCORD_TOKEN=your_token_here
OWNER_ID=1023249972428292168
ENABLE_DASHBOARD=true
DASHBOARD_PORT=5000
DASHBOARD_SECRET_KEY=change_this_to_something_random
DATABASE_URL=sqlite+aiosqlite:///bot.db
```

## Step 4 — Done!

Railway will:
- Build your bot automatically
- Keep it running 24/7
- Restart it if it crashes
- Give you a public URL for the web dashboard

## Web Dashboard on Railway

Railway gives you a public URL like `https://wan-bot-production.up.railway.app`

Your dashboard will be accessible from anywhere, not just localhost!

## Free Tier Limits

Railway free tier gives you:
- 500 hours/month (enough for 24/7)
- 512MB RAM
- Automatic restarts
- No credit card needed

## Alternative: Render.com

If Railway doesn't work:
1. Go to https://render.com
2. New → Web Service → Connect GitHub
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python bot.py`
5. Add environment variables
6. Deploy!

## Your Bot Will Now:
- ✅ Run 24/7 even when laptop is off
- ✅ Auto-restart on crashes
- ✅ Web dashboard accessible from anywhere
- ✅ Never go offline
