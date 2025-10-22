# Visual Crossing OpenAPI Sketch

This directory contains a hand-authored OpenAPI 3.1 specification that captures the parts
of the Visual Crossing *timeline* endpoint consumed by AccessiWeather. The document is a
starting point for evaluating whether we can maintain the Visual Crossing integration via
generated clients (similar to the existing `weather_gov_api_client` bundle).

## Regenerating the client

From an activated virtual environment:

```bash
openapi-python-client generate \
  --path docs/api_specs/visualcrossing_timeline.yaml \
  --output-path src/accessiweather/visual_crossing_api_client
```

The command will overwrite the contents of
`src/accessiweather/visual_crossing_api_client/`. Treat that directory as generated code
and avoid manual edits.

## Next steps

* Flesh out the specification with any additional fields or endpoints we rely on.
* Instantiate `VisualCrossingClient(..., use_timeline_api=True)` to exercise the generated
  timeline client path alongside the existing HTTPX implementation.
* Add contract tests that pin the JSON payloads we expect against the generated models.
