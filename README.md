# Mirage

**Protect your photo before the internet does.** Mirage is a research-informed prototype for adding small, human-imperceptible image perturbations intended to interfere with some AI image-editing workflows. It also strips image metadata, compares fixed benign edits on the original and protected image, and provides a practical response kit.

Mirage is built for the **recHERsion'26 PS2 Women's Safety** track. It is a prototype, not a guarantee of protection.

## What it does

- **Protect:** upload a JPG, PNG, or WebP and create a protected copy. Choose Light, Standard, or Strong, enable face focus, and optionally use robustness mode.
- **Inspect:** compare original and protected images, view a difference heatmap, heuristic protection/robustness scores, image-quality metrics, and removed metadata.
- **Prove:** run one of four fixed, benign Stable Diffusion img2img presets on both images with the same prompt and seed.
- **Keep records:** download a self-generated PDF record with image hashes.
- **Respond:** use the offline Safety Kit to preserve evidence, draft a platform report, and find India-specific reporting resources.

## How it works

```text
React + Vite frontend
  ├─ Demo adapter: static precomputed results from frontend/public/demo/
  ├─ Mock adapter: shared contract fixtures for development
  └─ Real adapter: FastAPI at /api/v1
                    ├─ image intake and metadata removal
                    ├─ Stable Diffusion VAE-based perturbation
                    └─ fixed-prompt img2img comparison
```

The backend contract is documented in [API.md](API.md). The API document is the source of truth for endpoint paths, fields, and error codes.

## Run locally

### Frontend

Prerequisites: Node.js 18 or newer and npm.

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

The default adapter is `mock`. It runs without a backend and uses the checked-in shared examples. To use a backend instead, set `VITE_ADAPTER=real` and `VITE_API_BASE=http://localhost:8000` in `frontend/.env.local`, then restart Vite. The API base can also be changed in the Settings drawer. Browser settings are persisted in local storage and can override environment defaults.

### Backend mock API

Prerequisites: Python 3.10 or newer.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:MOCK = "1"
python -m uvicorn app.main:app --reload --port 8000
```

The mock API serves the same `/api/v1` routes and contract shapes without loading the AI models. Use `VITE_ADAPTER=real` and `VITE_API_BASE=http://localhost:8000` to exercise the frontend over HTTP against it.

Run backend tests from `backend/`:

```powershell
python -m unittest discover -s tests
```

Build the frontend from `frontend/`:

```powershell
npm run build
```

## Real backend and Kaggle

The real backend requires the Python dependencies in `backend/requirements.txt`, a compatible PyTorch installation, and access to the Stable Diffusion 1.5 VAE weights. GPU availability is strongly recommended. On CPU, the simulator is disabled.

For the notebook workflow, open [try_mirage.ipynb](notebooks/try_mirage.ipynb) to run the pipeline directly, or [colab_server.ipynb](notebooks/colab_server.ipynb) to start the API for frontend integration. The server notebook's Cloudflare quick-tunnel URL is temporary and changes between sessions. Paste the current URL into the frontend Settings drawer or `VITE_API_BASE`; do not commit it.

## Demo Mode assets

Demo Mode reads `/demo/manifest.json` and the image/PDF files referenced by that manifest from `frontend/public/demo/`. The generated assets are intentionally not included by default because they may contain identifiable photos. To create them, use exactly three JPEG, PNG, or WebP photos for which you have permission to process and publish the resulting assets, and run this on a CUDA-enabled GPU with the real backend dependencies installed:

```powershell
$env:MOCK = "0"
python backend/scripts/make_demo_assets.py C:\path\to\three-permissioned-photos
```

The script writes the manifest and precomputed outputs to `demo-assets/`. Copy them into the Vite public directory:

```powershell
New-Item -ItemType Directory -Force frontend\public\demo | Out-Null
Copy-Item demo-assets\* frontend\public\demo -Recurse -Force
```

Or use `sh scripts/sync-demo-assets.sh` from a shell with `sh` available. Do not publish real people's photos or derived images without their explicit permission. Until the generated manifest is installed, Studio Demo Mode cannot load its sample set; the landing page can still show the included hero artwork.

For a Vercel deployment, set the project root to `frontend`, build command to `npm run build`, and output directory to `dist`. Configure `VITE_ADAPTER=demo` and `VITE_DEMO_DEFAULT=true` only after the demo manifest and assets are available to the deployment.

## Privacy and limits

- No user accounts or database are implemented. Backend job state and files are held in memory/temp storage and expire after the configured TTL (15 minutes by default).
- Images are sent to the backend for processing; they do not stay on the user's device. Use only photos you own or have permission to process, and do not upload sensitive images to a server you do not control.
- The technique targets specific Stable Diffusion-family image-editing workflows. It does not prevent every model, editing tool, screenshot, or redistribution method.
- Heavy compression, resizing, or screenshots may weaken the effect. Protection, robustness, visual-quality, and disruption scores are heuristic estimates, not guarantees.
- The simulator accepts only fixed benign presets; it does not accept free-text prompts.
- The certificate is self-generated and is not a legal notarization. Watermark verification is not implemented in the current backend configuration.

## Credits

Mirage builds on public research and open-source tooling. It does not claim to have invented adversarial image perturbation methods. See [PhotoGuard](https://arxiv.org/abs/2302.06588), [Fawkes](https://sandlab.cs.uchicago.edu/fawkes/), and [Glaze](https://glaze.cs.uchicago.edu/), along with [Diffusers](https://github.com/huggingface/diffusers), [Stable Diffusion](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5), FastAPI, React, and Vite.
