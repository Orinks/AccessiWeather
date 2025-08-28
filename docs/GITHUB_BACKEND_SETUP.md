# GitHub Backend Service Setup

AccessiWeather now uses a backend service for all GitHub App authentication instead of handling credentials directly in the application.

## Configuration

The backend service URL is hardcoded in the application as:
`https://soundpack-backend.fly.dev`

Users can optionally override this by setting it in their AccessiWeather settings:

```json
{
  "settings": {
    "github_backend_url": "https://your-custom-backend.render.com"
  }
}
```

## Backend Service Requirements

Your backend service must implement the following endpoints:

### POST /upload-zip

Recommended endpoint. Accepts a ZIP containing pack.json and audio files. The backend validates the contents, creates a branch, commits files, and opens a PR.

- Request: multipart/form-data with field `zip_file` (application/zip)
- Response (200): `{ "html_url": "https://github.com/owner/repo/pull/123", "number": 123 }`

### POST /share-pack

Legacy endpoint. Accepts only pack.json metadata and opens a PR without uploading audio files.

- Request: JSON body matching pack.json schema
- Response (200): `{ "html_url": "https://github.com/owner/repo/pull/123", "number": 123 }`

## Security Benefits

Using a backend service provides several security advantages:

- **No credential embedding**: GitHub App credentials are never embedded in the client application
- **Centralized authentication**: All GitHub API calls go through your controlled backend
- **Easier credential rotation**: Update credentials on the backend without redistributing the app
- **Audit trail**: Backend service can log all submission attempts
- **Rate limiting**: Backend can implement rate limiting and abuse prevention

## Implementation Notes

The current client uses /upload-zip as the primary path for submissions and falls back to /share-pack only for JSON-only submissions.

## No Fallback

AccessiWeather no longer supports direct GitHub App authentication. All submissions go through the backend service. If the backend service is unavailable, submissions will fail with an appropriate error message.
