# GitHub Pages Setup

This repository is configured to automatically deploy the `static/` directory to GitHub Pages when code is pushed to `main`.

## Initial Setup (One-time)

1. Go to your repository settings: https://github.com/psycho789/molting/settings/pages
2. Under "Source", select **"GitHub Actions"** (not "Deploy from a branch")
3. Save the settings

## How It Works

- When you push to `main`, the GitHub Actions workflow (`.github/workflows/deploy-pages.yml`) automatically runs
- It deploys the contents of the `static/` directory to GitHub Pages
- Your site will be available at: **https://psycho789.github.io/molting/**

## Generating Static Export

1. Run the SSE server: `python src/sse_server.py`
2. Open the frontend in your browser
3. Click the "Export Static" button
4. The `static/index.html` file will be generated
5. Commit and push to `main`:
   ```bash
   git add static/
   git commit -m "Update static export"
   git push origin main
   ```
6. GitHub Actions will automatically deploy it

## Manual Workflow Trigger

You can also manually trigger the deployment:
1. Go to the "Actions" tab in your repository
2. Select "Deploy to GitHub Pages" workflow
3. Click "Run workflow"
