# Deployed application

**Live URL:** _not deployed yet: add the Render URL here once the service is live (e.g. `https://lumora-policybot.onrender.com`)._

- Health check: `<URL>/health`
- Chat UI: `<URL>/`
- API: `POST <URL>/chat` with `{"question": "..."}`

The app is hosted on Render's free tier, as described in `render.yaml`. GitHub Actions deploys it after CI passes on `main`, using the `RENDER_DEPLOY_HOOK_URL` secret. Free instances sleep when idle, so the first request after a pause can take about 30–60 s while the instance wakes and loads the models.
