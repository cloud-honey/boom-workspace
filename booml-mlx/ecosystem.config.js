module.exports = {
  apps: [
    {
      name: 'booml-mlx-server',
      script: 'server_v3_postgres_router.py',
      interpreter: 'python3',
      cwd: '/Users/sykim/.openclaw/workspace/booml-mlx',
      env: {
        PORT: '8000',
        BOOML_DB_BACKEND: 'postgresql',
        BOOML_POSTGRES_URL: 'postgresql://sykim@localhost:5432/booml',
      },
    },
    {
      name: 'booml-mlx-chat',
      script: 'server_v3_postgres_router.py',
      interpreter: 'python3',
      cwd: '/Users/sykim/.openclaw/workspace/booml-mlx',
      env: {
        PORT: '8001',
        BOOML_DB_BACKEND: 'postgresql',
        BOOML_POSTGRES_URL: 'postgresql://sykim@localhost:5432/booml',
      },
    },
  ],
};
