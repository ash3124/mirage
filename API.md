# Mirage: API Contract (`API.md`) v1.0.0

**Status:** DRAFT until both developers approve it in a pull request. After approval it is **FROZEN**.
**Owners:** Dev 1 (Frontend) and Dev 2 (Backend). Neither may change this file alone.

## 0. Rules (read first)

1. The frontend uses **exactly** these requests and responses. The backend implements **exactly** these.
2. Do not rename an endpoint, field, enum value, or error code. Do not change a type.
3. To change anything: open a PR that edits this file and `shared/examples/`, label it `api-change`, bump the version below, and get **both** developers to approve before either of you codes against it.
4. Unknown extra fields must be **ignored** by both sides (forward compatible). Required fields are never removed.
5. When pasting this file into an AI tool, add: *"Do not change anything in API.md. If something seems missing, tell me instead of inventing it."*

### Change log
| Version | Change |
|---------|--------|
| 1.0.0 | First contract |

---

## 1. Conventions

- **Base path:** `/api/v1`. The host is configurable on the frontend (`VITE_API_BASE` or the Settings drawer).
- **Format:** JSON (UTF-8) with `snake_case` keys. Uploads are `multipart/form-data`. Downloads are binary.
- **Time:** ISO 8601 in UTC, e.g. `2026-10-25T10:30:00Z`.
- **Scores:** integers 0 to 100. Sizes are in pixels.
- **No auth, no cookies, no database.** The service is stateless: job state and files live in server memory/temp storage and expire after `limits.ttl_seconds` (900).
- **CORS:** the server allows all origins. If ngrok is ever used, the client sends header `ngrok-skip-browser-warning: 1`.
- **URLs inside results are root-relative** (start with `/api/v1/`). The client prefixes the API host.
- **Async pattern:** start (`202`) then poll `GET /jobs/{job_id}` every 1 second until `status` is `done` or `error`. Give up after 3 minutes.
- **Uploads:** JPG, PNG or WebP, up to 10 MB. HEIC is not supported.
- **Errors:** every non-2xx response uses the error body in section 4.

---

## 2. Shared types

```ts
type Strength  = 'light' | 'standard' | 'strong';
type SimPreset = 'background_snow' | 'background_beach' | 'new_hairstyle' | 'vintage_style';
type JobType   = 'cloak' | 'attack_sim';
type JobStatus = 'queued' | 'running' | 'done' | 'error';

// cloak jobs use: queued, detecting_face, optimizing, robustness_check, finalizing, done
// attack_sim jobs use: queued, editing_original, editing_cloaked, scoring, done
type Stage = 'queued' | 'detecting_face' | 'optimizing' | 'robustness_check' | 'finalizing'
           | 'editing_original' | 'editing_cloaked' | 'scoring' | 'done';

interface ErrorObj { code: string; message: string }          // codes in section 4

interface Job<T> {
  job_id: string;                 // uuid
  type: JobType;
  status: JobStatus;
  progress: number;               // 0..100
  stage: Stage;
  result: T | null;               // non-null only when status = 'done'
  error: ErrorObj | null;         // non-null only when status = 'error'
}

interface CloakResult {
  file_id: string;                // used in file URLs; also shown for debugging
  original_url: string;           // resized working copy, metadata removed
  cloaked_url: string;
  heatmap_url: string;
  metrics: {
    protection_score: number;     // 0..100 heuristic
    robustness: {
      jpeg_q75: number;           // 0..100, protection left after JPEG q75
      resize_50: number;          // 0..100, after 50% down/up resize
      social_like: number;        // 0..100, after 75% resize + JPEG q70
    };
    visual_quality: { psnr_db: number; ssim: number };   // ssim 0..1
    working_size: { w: number; h: number };
    elapsed_s: number;
  };
  metadata_report: { had_gps: boolean; removed: string[] };
  hashes: { sha256_cloaked: string; phash_original: string };   // lowercase hex
  watermark: { embedded: boolean; tag: string } | null;
  face_found: boolean;
  expires_at: string;             // ISO 8601 UTC
}

interface SimResult {
  preset: SimPreset;
  edit_on_original_url: string;
  edit_on_cloaked_url: string;
  disruption_score: number;       // 0..100 heuristic
  seed: number;
}

interface AppConfig {
  version: string;
  mode: 'gpu' | 'cpu';
  simulator_enabled: boolean;
  features: { watermark: boolean; face_focus: boolean; robust_mode: boolean };
  limits: { max_upload_mb: number; ttl_seconds: number; max_side_px: number };
  strengths: { id: Strength; label: string; description: string }[];
  sim_presets: { id: SimPreset; label: string }[];
}
```

---

## 3. Endpoints

| # | Method | Path | Purpose |
|---|--------|------|---------|
| 1 | GET | `/health` | Is the server up |
| 2 | GET | `/config` | Options and limits for the UI |
| 3 | POST | `/cloak` | Start protecting a photo (async) |
| 4 | GET | `/jobs/{job_id}` | Poll any job |
| 5 | POST | `/attack-sim` | Start the same-AI-edit test (async) |
| 6 | POST | `/certificate` | Download the ownership PDF |
| 7 | GET | `/files/{file_id}/{name}` | Download a result image |
| 8 | POST | `/watermark/verify` | Check an image for our hidden tag (optional) |

### 3.1 `GET /health`
**200**
```json
{ "status": "ok", "version": "1.0.0", "mode": "gpu", "queue_depth": 0, "simulator_enabled": true }
```

### 3.2 `GET /config`
**200** returns `AppConfig`.
```json
{
  "version": "1.0.0",
  "mode": "gpu",
  "simulator_enabled": true,
  "features": { "watermark": false, "face_focus": true, "robust_mode": true },
  "limits": { "max_upload_mb": 10, "ttl_seconds": 900, "max_side_px": 768 },
  "strengths": [
    { "id": "light", "label": "Light", "description": "Nearly invisible, lighter protection" },
    { "id": "standard", "label": "Standard", "description": "Balanced. Recommended" },
    { "id": "strong", "label": "Strong", "description": "Strongest protection, slight grain" }
  ],
  "sim_presets": [
    { "id": "background_snow", "label": "Snowy background" },
    { "id": "background_beach", "label": "Beach background" },
    { "id": "new_hairstyle", "label": "New hairstyle" },
    { "id": "vintage_style", "label": "Vintage style" }
  ]
}
```
The frontend builds the strength cards and preset chips from this response. If the call fails, it falls back to the same values hard-coded.

### 3.3 `POST /cloak`
`multipart/form-data`

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `image` | file | yes | JPG, PNG or WebP, max 10 MB |
| `strength` | string | no | `light`, `standard` (default), `strong` |
| `face_focus` | boolean | no | default `true` |
| `robust_mode` | boolean | no | default `true` |
| `embed_watermark` | boolean | no | default `false`. Only if `features.watermark` is true |
| `owner_tag` | string | if `embed_watermark` | 1 to 4 characters, `A-Z0-9` |

**202**
```json
{ "job_id": "7c1f0c52-6b0a-4c7e-9b53-3d1b9c2a0f11", "status": "queued" }
```
**Errors:** `INVALID_IMAGE` 400, `TOO_LARGE` 413, `BAD_PARAMS` 422, `BUSY` 429.

### 3.4 `GET /jobs/{job_id}`
**200** returns `Job<CloakResult>` or `Job<SimResult>` depending on `type`.

Running:
```json
{ "job_id": "7c1f0c52-6b0a-4c7e-9b53-3d1b9c2a0f11", "type": "cloak", "status": "running",
  "progress": 42, "stage": "optimizing", "result": null, "error": null }
```
Done (cloak):
```json
{
  "job_id": "7c1f0c52-6b0a-4c7e-9b53-3d1b9c2a0f11",
  "type": "cloak",
  "status": "done",
  "progress": 100,
  "stage": "done",
  "result": {
    "file_id": "a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7",
    "original_url": "/api/v1/files/a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7/original.png",
    "cloaked_url": "/api/v1/files/a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7/cloaked.png",
    "heatmap_url": "/api/v1/files/a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7/heatmap.png",
    "metrics": {
      "protection_score": 78,
      "robustness": { "jpeg_q75": 61, "resize_50": 55, "social_like": 52 },
      "visual_quality": { "psnr_db": 36.4, "ssim": 0.96 },
      "working_size": { "w": 768, "h": 512 },
      "elapsed_s": 24.1
    },
    "metadata_report": { "had_gps": true, "removed": ["GPS location", "Camera model", "Capture date"] },
    "hashes": {
      "sha256_cloaked": "3f2a9c1e5b7d4e8a9c217d4e5f6a8b903f2a9c1e5b7d4e8a9c217d4e5f6a8b90",
      "phash_original": "d1c4b2a39e8f7061"
    },
    "watermark": null,
    "face_found": true,
    "expires_at": "2026-10-25T10:30:00Z"
  },
  "error": null
}
```
Done (attack_sim):
```json
{
  "job_id": "e2b8d4a6-1c3f-4a5b-8d7e-9f0a1b2c3d4e",
  "type": "attack_sim",
  "status": "done",
  "progress": 100,
  "stage": "done",
  "result": {
    "preset": "background_snow",
    "edit_on_original_url": "/api/v1/files/a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7/sim_background_snow_original.png",
    "edit_on_cloaked_url": "/api/v1/files/a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7/sim_background_snow_cloaked.png",
    "disruption_score": 71,
    "seed": 1234
  },
  "error": null
}
```
Failed:
```json
{ "job_id": "7c1f0c52-6b0a-4c7e-9b53-3d1b9c2a0f11", "type": "cloak", "status": "error",
  "progress": 40, "stage": "optimizing", "result": null,
  "error": { "code": "INTERNAL", "message": "Something went wrong while protecting your photo." } }
```
**Errors (HTTP level):** `JOB_NOT_FOUND` 404, `JOB_EXPIRED` 410. A job that fails while running is returned as HTTP 200 with `status: "error"`.

### 3.5 `POST /attack-sim`
`application/json`
```json
{ "job_id": "7c1f0c52-6b0a-4c7e-9b53-3d1b9c2a0f11", "preset": "background_snow" }
```
`job_id` must be a **finished cloak job**. The server maps `preset` to a fixed, harmless prompt. Free-text prompts are not accepted.

**202**
```json
{ "job_id": "e2b8d4a6-1c3f-4a5b-8d7e-9f0a1b2c3d4e", "status": "queued" }
```
This returns a **new** job id. Poll it with `GET /jobs/{job_id}`.
**Errors:** `JOB_NOT_FOUND` 404, `JOB_EXPIRED` 410, `JOB_NOT_READY` 409 (cloak job not finished), `BAD_PARAMS` 422 (unknown preset, or the job is not a cloak job), `SIM_UNAVAILABLE` 503, `BUSY` 429.
A job can fail with `SIM_BLOCKED` (the AI's safety filter blocked the edit); it appears in the job's `error`.

### 3.6 `POST /certificate`
`application/json`
```json
{ "job_id": "7c1f0c52-6b0a-4c7e-9b53-3d1b9c2a0f11", "owner_name": "Optional name, max 60 chars" }
```
**200** `application/pdf`, with `Content-Disposition: attachment; filename="mirage-protection-record.pdf"`.
Contents: thumbnails, SHA-256 of the protected image, perceptual hash of the original, UTC time, strength used, watermark tag if any, and the line *"Self-generated record. Not a legal notarization."*
**Errors:** `JOB_NOT_FOUND` 404, `JOB_EXPIRED` 410, `JOB_NOT_READY` 409, `BAD_PARAMS` 422.

### 3.7 `GET /files/{file_id}/{name}`
`name` is one of: `original.png`, `cloaked.png`, `heatmap.png`, `sim_<preset>_original.png`, `sim_<preset>_cloaked.png`.
**200** `image/png`. Add `?download=1` to get `Content-Disposition: attachment`.
**Errors:** 404 `JOB_NOT_FOUND` (unknown id or name), 410 `JOB_EXPIRED`.

### 3.8 `POST /watermark/verify` (optional, only if `features.watermark` is true)
`multipart/form-data` with `image`.
**200**
```json
{ "found": true, "tag": "AB12" }
```
or `{ "found": false, "tag": null }`. If the feature is off: `NOT_IMPLEMENTED` 501. The frontend hides the Verify page when `features.watermark` is false.

---

## 4. Errors

Body for every non-2xx response:
```json
{ "error": { "code": "INVALID_IMAGE", "message": "That file does not look like a photo we can read." } }
```

| code | HTTP | When |
|------|------|------|
| `INVALID_IMAGE` | 400 | Not decodable, or unsupported type (including HEIC) |
| `TOO_LARGE` | 413 | Over 10 MB |
| `BAD_PARAMS` | 422 | Missing or invalid field, unknown preset, bad `owner_tag`, wrong job type |
| `JOB_NOT_FOUND` | 404 | Unknown job id, file id or file name |
| `JOB_EXPIRED` | 410 | Past `ttl_seconds` |
| `JOB_NOT_READY` | 409 | Job exists but is not `done` yet |
| `BUSY` | 429 | Too many jobs waiting (optional behaviour) |
| `SIM_UNAVAILABLE` | 503 | Simulator disabled on this server |
| `SIM_BLOCKED` | 422 | AI safety filter blocked the edit (appears in a job's `error`) |
| `NOT_IMPLEMENTED` | 501 | Feature turned off |
| `INTERNAL` | 500 | Unexpected failure |

The `message` is safe to show to users. Never put stack traces or image contents in it.

---

## 5. Demo Mode manifest (static file, no server)

The backend developer generates this with `scripts/make_demo_assets.py` from **real** pipeline output. The frontend reads it in Demo Mode. Path: `/demo/manifest.json`.

```json
{
  "version": "1.0.0",
  "sample_certificate_url": "/demo/sample_certificate.pdf",
  "samples": [
    {
      "id": "sample-1",
      "label": "Portrait 1",
      "thumb_url": "/demo/sample-1/original.png",
      "cloak": { "...": "a full CloakResult; every URL starts with /demo/sample-1/" },
      "sims": {
        "background_snow": { "...": "a full SimResult; URLs start with /demo/sample-1/" },
        "background_beach": { "...": "SimResult" },
        "new_hairstyle": { "...": "SimResult" },
        "vintage_style": { "...": "SimResult" }
      }
    }
  ]
}
```
Rules: metrics are the real computed values (never hand-edited), and every `*_url` is root-relative to the site (`/demo/...`).

---

## 6. Shared example files (`shared/examples/`)

Both developers create these in the first PR, copying the JSON above. Frontend uses them as mock responses. Backend uses them as test expectations and for `MOCK=1`.

```
health.ok.json                 config.ok.json
cloak.accepted.json            job.cloak.queued.json
job.cloak.running.json         job.cloak.done.json
job.cloak.error.json           attack_sim.accepted.json
job.sim.running.json           job.sim.done.json
error.invalid_image.json       error.too_large.json
error.bad_params.json          error.job_not_found.json
error.job_expired.json         error.job_not_ready.json
error.sim_unavailable.json     watermark.verify.found.json
manifest.sample.json
```
Image and PDF placeholders live in `shared/examples/assets/` (a small original, cloaked, heatmap, two sim images, one PDF).
