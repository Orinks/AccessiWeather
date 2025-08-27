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

Your backend service must implement the following endpoint:

### POST /create-pr

Creates a pull request in the soundpacks repository.

**Request Body:**
```json
{
  "branch": "pack-submission-branch-name",
  "title": "Add MyPack sound pack",
  "body": "Pull request description with pack details and submitter attribution",
  "head_owner": "accessibotapp",
  "pack_data": {
    "name": "MyPack",
    "author": "Pack Author",
    "description": "Description of the sound pack",
    "version": "1.0.0",
    "sounds": {
      "alert": "alert.wav",
      "notify": "notify.wav"
    },
    "_submitter": {
      "name": "Submitter Name",
      "email": "submitter@example.com",
      "submission_type": "anonymous"
    }
  }
}
```

**Request Fields:**
- `branch`: The branch name to create the PR from (e.g., "soundpack/mypack-20250827-141921")
- `title`: Pull request title
- `body`: Pull request description with pack details and submitter attribution
- `head_owner`: (Optional) The GitHub username/organization that owns the head branch. If not provided, the backend should use its GitHub App installation account.
- `pack_data`: Complete pack metadata from pack.json, including submitter information for anonymous submissions

**Response:**
```json
{
  "html_url": "https://github.com/owner/repo/pull/123",
  "number": 123,
  "title": "Add MyPack sound pack",
  "state": "open"
}
```

## Security Benefits

Using a backend service provides several security advantages:

- **No credential embedding**: GitHub App credentials are never embedded in the client application
- **Centralized authentication**: All GitHub API calls go through your controlled backend
- **Easier credential rotation**: Update credentials on the backend without redistributing the app
- **Audit trail**: Backend service can log all submission attempts
- **Rate limiting**: Backend can implement rate limiting and abuse prevention

## Implementation Notes

The current implementation creates pull requests via the backend but still requires the full pack submission workflow (file uploads, branch creation, etc.) to be handled by the backend service.

For a complete implementation, the backend service would need additional endpoints for:
- File upload handling
- Branch creation and management
- Repository operations

This is a simplified initial implementation that demonstrates the authentication flow.

## No Fallback

AccessiWeather no longer supports direct GitHub App authentication. All submissions go through the backend service. If the backend service is unavailable, submissions will fail with an appropriate error message.
