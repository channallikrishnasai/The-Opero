# OPERO landing page

`index.html` is the original standalone OPERO landing page, kept in the repository as reference material.

The Netlify deployment publishes **`public/`** — see `netlify.toml` at the repository root (`publish = "public"`, switched deliberately after this directory's original deployment). To deploy manually, drag `public/` into [Netlify Drop](https://app.netlify.com/drop).

No build step or third-party assets are required for either page.

This directory also hosts `web_background/` — the Three.js page the desktop HUD embeds at runtime (`ui/window.py`).
