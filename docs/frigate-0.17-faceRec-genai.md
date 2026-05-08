# Frigate 0.17 face_recognition + semantic_search + GenAI patch

_Phase 3 of the renovation. Applied to CM5 HAOS Frigate addon (v0.17.1) on 2026-05-07._

## What this enables

Frigate gains three new capabilities in addition to its existing object detection:

1. **Face recognition** - identifies known faces in detected events. Requires user to enroll labeled photos via Frigate UI -> Settings -> Face Library.
2. **Semantic search** - text-search across recordings ("show me when the dog was on the couch yesterday"). Uses jina-clip-v1 embeddings.
3. **GenAI review summaries** - llava:7b generates one-line natural-language summaries of alert-grade review items (currently enabled on `tapo_c260` only; expand by adding the same `review.genai` block under other cameras).

## The patch

Append the following to `/addon_configs/ccab4aaf_frigate/config.yaml` BEFORE the `version:` footer (top-level keys):

```yaml
semantic_search:
  enabled: true
  reindex: false   # set true once after enabling; reindexes existing recordings
  model_size: small

face_recognition:
  enabled: true
  model_size: small
  unknown_score: 0.8
  detection_threshold: 0.7
  recognition_threshold: 0.9
  min_area: 500
  save_attempts: 100

genai:
  provider: ollama
  base_url: http://192.168.0.94:11434
  model: llava:7b
```

And under each camera you want GenAI review summaries enabled on, append:

```yaml
    review:
      genai:
        enabled: true
        alerts: true
        detections: false
```

## Schema gotchas (Frigate 0.17)

Three schema-mismatch attempts before this landed; documenting the wrong shapes here so future-me doesn't repeat:

- WRONG: top-level `genai.enabled: true` -- no `enabled` key on top-level GenAIConfig.
- WRONG: per-camera `review.genai.objects: [person]` -- field is `additional_concerns`, not `objects`.
- WRONG: per-camera `review.alerts.genai.enabled: true` -- alerts is a sibling of genai, not a parent.

The right schema (verified against the live FrigateConfig pydantic model):
- top-level `genai`: `provider`, `base_url`, `model`, `api_key`
- per-camera `review.genai`: `enabled`, `alerts` (bool), `detections` (bool), `additional_concerns` (list[str]), `image_source`, `preferred_language`, `activity_context_prompt`

## Restart sequence

```
ssh root@192.168.0.50 "ha addons restart ccab4aaf_frigate"
# wait ~30s for boot
ssh root@192.168.0.50 "ha addons logs ccab4aaf_frigate | tail -25"
```

Look for:
- `frigate.detectors.plugins.edgetpu_tfl INFO: TPU found` (Coral OK)
- `Embedding process started` (semantic search OK)
- `Review process started` (review.genai OK)
- No `Config Validation Errors`

## Verifying

```
docker exec addon_ccab4aaf_frigate python3 -c '
import yaml
from frigate.config import FrigateConfig
data = yaml.safe_load(open("/config/config.yaml"))
c = FrigateConfig.model_validate(data)
print("face_recognition.enabled:", c.face_recognition.enabled)
print("semantic_search.enabled:", c.semantic_search.enabled)
print("genai provider:", c.genai.provider, "model:", c.genai.model)
'
```

## Next steps (user-action)

1. **Enroll faces**: Frigate sidebar -> Settings -> Face Library -> upload 3-5 labeled photos per person. Recognition kicks in immediately.
2. **Test GenAI**: walk in front of `tapo_c260`. Frigate creates an alert review item; ~5s later the item gains a `description` field with llava's summary.
3. **Expand GenAI to other cameras**: copy the `review.genai` block under `g410_front` (or any other camera).

## Memory cost

Approximate added load on CM5 HAOS:
- semantic_search small CLIP model: ~90 MB resident
- face_recognition facenet + facedet: ~50 MB resident
- review process queue: negligible
- Total: ~150 MB extra (CM5 has 11 GB available; comfortable)

## Memory cost on AM5 (Ollama)

llava:7b is already resident (~4.5 GB). Each GenAI review call adds one inference (~2-5s on RTX 3060). Frigate batches by event so the rate is bounded; ~12 calls/min during busy periods is the worst case.

## Backups

Config snapshots per change:
- `config.yaml.bak.preFaceRec-20260507-213427`
- `config.yaml.bak.preGenAI-20260507-213647`
- `config.yaml.bak.preGenAI2-...` (after schema correction)

Roll back: `cp <backup> /addon_configs/ccab4aaf_frigate/config.yaml && ha addons restart ccab4aaf_frigate`.
