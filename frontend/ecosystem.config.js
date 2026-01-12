module.exports = {
  apps: [{
    name: 'kai-frontend',
    script: 'npm',
    args: 'start',
    cwd: '/var/www/kai/frontend',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production',
      PORT: 3000
    },
    error_file: '/root/.pm2/logs/kai-frontend-error.log',
    out_file: '/root/.pm2/logs/kai-frontend-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true
  }]
}

