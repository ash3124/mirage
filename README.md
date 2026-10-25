# Mirage

Mirage is a privacy-focused photo-protection demo. It creates a subtly altered
copy, strips image metadata, and compares how fixed AI-edit presets affect the
original and protected versions. Protection and disruption scores are
heuristics, not guarantees.

## Demo Mode assets

Real pipeline output and its `manifest.json` belong in [`demo-assets/`](./demo-assets/).
Generate them with [`backend/scripts/make_demo_assets.py`](./backend/scripts/make_demo_assets.py),
then sync them into the frontend's public demo directory:

```sh
sh scripts/sync-demo-assets.sh
```

## Backend

See [`backend/README.md`](./backend/README.md) for setup and tests. The API
contract is documented in [`API.md`](./API.md).

## Run the real pipeline

The judge-facing notebook runs the cloak and simulator without starting the
API server: [Open in Colab](https://colab.research.google.com/github/ash3124/mirage/blob/main/notebooks/try_mirage.ipynb).
The separate [`notebooks/colab_server.ipynb`](./notebooks/colab_server.ipynb)
starts the API for recording or local frontend integration.
