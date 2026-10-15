# xFACE static GitHub Pages demo

A pre-rendered, responsive demonstration of Subjects & Faces, Live Monitor,
and Access Logs. Every identity, avatar, face sample, event and confidence score
is fictional. The monitor plays illustrated scenarios; it does not perform face
recognition. All dates and audit statistics describe the fixed demo fixture.

The browser never accesses biometric APIs, databases, door relays,
production configuration, or external asset services. The Live monitor offers an
optional **Use my camera** button: only after the visitor clicks it and grants the
browser permission does it show a mirrored local preview. Frames are never
uploaded, stored, recorded or recognised; the outcome shown is still a simulated
scenario, and the camera turns off with **Stop camera**, when the tab is hidden,
or when the page closes. Sample previews repeat
illustrated placeholders, not biometric enrollment images. Manual unlock changes
only the local UI. Search, filters, scenario playback and filtered CSV export run
in memory; reloading resets the page. The monitor scenarios do not append audit
events to the fixed dataset. No login is required.

## Build and preview locally

From the repository root, using Python 3.10 or newer:

```sh
python3 scripts/build_demo.py
python3 scripts/build_demo.py --check
python3 -m http.server 8080 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8080/. There is no npm install, Flask startup or backend
configuration. Content is visible even with JavaScript disabled; interactions
require JavaScript.

- `scripts/build_demo.py`: deterministic synthetic fixtures, SVG avatars, HTML
  renderer and asset allowlist. It does not import the backend or read runtime data.
- `demo/assets/demo.js`: demo-only interactions. The stylesheet, icon sprite, theme
  script and favicon are copied from the application (`xface/web/static/` and
  `xface/web/templates/_icons.html`), so the demo and the app share one design system.
- `site/`: committed, generated publication artifact; rebuild after source changes.
  The builder replaces this directory, so keep manual edits in the sources.
- `.github/workflows/pages.yml`: explicit, manual publication workflow.

All navigation and asset URLs are relative, so the same files work under `/xFACE/`,
`/xFace/`, a renamed repository path, or a local preview. GitHub determines the
project URL from the exact repository name; do not hard-code a different case.
The workflow uploads **only `site/`**, not the Python app or repository data.

## Publish when you are ready

The demo is ready to publish. Publication remains a separate, manual step after
the changes are merged.

1. Review the generated site locally, then commit and push the demo sources,
   `site/`, README changes and `.github/workflows/pages.yml` to your default branch.
2. In GitHub, go to **Settings → Pages → Build and deployment → Source** and
   choose **GitHub Actions**.
3. Go to **Actions → Publish synthetic demo (manual) → Run workflow**, select
   the default branch and explicitly run it.
4. The deployment job exposes the final Pages URL. For the current `KOKUTBON/xFACE`
   repository it is normally `https://kokutbon.github.io/xFACE/`.

For a private repository owned by the personal account `reiidoda`, GitHub Pro
supports Pages; GitHub Team is an organization plan. To use the root address
`https://kokutbon.github.io/`, the publishing repository must be named
`kokutbon.github.io`. The current repository instead uses the `/xFACE/` path.
The repository can stay private while the published demo is publicly accessible.
See [GitHub plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)
and [Pages site types](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

Pushing commits alone does not trigger this publication workflow. After edits,
rebuild, verify, commit and push, then manually run it again to update the demo.
Repository or organization environment protection rules may require your approval
in GitHub. Reference: [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

This is a frontend demonstration of the project, not a hosted installation of the
Flask application. See the root README for self-hosted application setup.
