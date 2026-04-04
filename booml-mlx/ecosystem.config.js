module.exports = {
  apps: [
    {
      name: 'booml-mlx-server',
      script: 'server_v3_postgres_router.py',
      interpreter: 'python3',
      cwd: '/Users/sykim/.openclaw/workspace/booml-mlx',
      env: { PORT: '8000' },
    },
    {
      name: 'booml-mlx-chat',
      script: 'server_v3_postgres_router.py',
      interpreter: 'python3',
      cwd: '/Users/sykim/.openclaw/workspace/booml-mlx',
      env: { PORT: '8001' },
    },
  ],
};
