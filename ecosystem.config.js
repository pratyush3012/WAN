// PM2 Ecosystem Configuration for WAN Bot
// Install PM2: npm install -g pm2
// Start: pm2 start ecosystem.config.js
// Monitor: pm2 monit
// Logs: pm2 logs wanbot
// Stop: pm2 stop wanbot
// Restart: pm2 restart wanbot

module.exports = {
  apps: [{
    name: 'wanbot',
    script: 'bot.py',
    interpreter: 'python3',
    cwd: './',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production',
      ENABLE_DASHBOARD: 'true',
      DASHBOARD_HOST: '0.0.0.0',
      DASHBOARD_PORT: '5000'
    },
    error_file: './logs/pm2-error.log',
    out_file: './logs/pm2-out.log',
    log_file: './logs/pm2-combined.log',
    time: true,
    merge_logs: true,
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
};
