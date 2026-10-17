---
name: Streamlit workflow startup
description: Replit Streamlit startup prompts that can prevent a workflow from opening its webview port.
---

For Replit Streamlit workflows, set `server.headless=true` to skip the interactive first-run email prompt. Disable usage statistics separately with `browser.gatherUsageStats=false`; the usage-stat setting alone does not suppress the email prompt.

**Why:** when stdin is interactive, Streamlit can wait for the optional onboarding email before opening the webview port, which looks like an application or port startup failure even when the code is healthy.

**How to apply:** If workflow logs stop at `Email:`, check for the onboarding prompt before changing the app or its bind address. Keep webview apps on port 5000 and bind them to `0.0.0.0`.
