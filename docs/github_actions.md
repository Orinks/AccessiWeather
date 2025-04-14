# Testing GitHub Actions Locally

This document explains how to test GitHub Actions workflows locally using the act CLI tool before pushing changes to the repository.

## Installing act CLI

The [act CLI tool](https://github.com/nektos/act) allows you to run GitHub Actions workflows locally. This is useful for testing workflow changes without having to push to GitHub.

### Windows Installation

1. Using Chocolatey:
   ```
   choco install act-cli
   ```

2. Using Scoop:
   ```
   scoop install act
   ```

3. Manual installation:
   - Download the latest release from [GitHub Releases](https://github.com/nektos/act/releases)
   - Extract the executable to a directory in your PATH

### Verify Installation

To verify that act is installed correctly:

```
act --version
```

## Running Workflows Locally

To run the workflow locally:

1. Navigate to the repository root directory:
   ```
   cd AccessiWeather
   ```

2. Run the workflow:
   ```
   act -W .github/workflows/windows-ci.yml
   ```

### Common Options

- `-W <workflow-file>`: Specify the workflow file to run
- `-j <job-name>`: Run a specific job from the workflow
- `-l`: List all available workflows and jobs
- `--secret-file <file>`: Load secrets from a file
- `-P ubuntu-latest=nektos/act-environments-ubuntu:18.04`: Use a specific Docker image for the runner

## Troubleshooting

### Docker Requirements

The act CLI tool requires Docker to be installed and running. If you encounter Docker-related errors:

1. Ensure Docker is installed and running
2. Try running with the `-P` flag to specify a Docker image:
   ```
   act -P ubuntu-latest=nektos/act-environments-ubuntu:18.04
   ```

### Windows-Specific Issues

When testing Windows workflows on a Windows machine:

1. Use the `-P` flag with a Linux image, as act doesn't support running Windows containers:
   ```
   act -P windows-latest=nektos/act-environments-ubuntu:18.04
   ```

2. Some Windows-specific commands may not work in the Linux container. You may need to modify the workflow for local testing.

### Limitations

- act doesn't support all GitHub Actions features
- Some actions may not work correctly in the local environment
- Windows-specific commands won't work in Linux containers

## Best Practices

1. Start by testing individual jobs:
   ```
   act -j build -W .github/workflows/windows-ci.yml
   ```

2. Create a `.actrc` file in the repository root with common options:
   ```
   -P ubuntu-latest=nektos/act-environments-ubuntu:18.04
   -P windows-latest=nektos/act-environments-ubuntu:18.04
   ```

3. Create a `.secrets` file for sensitive information (add to .gitignore):
   ```
   MY_SECRET=value
   ```

4. Run act with the secrets file:
   ```
   act --secret-file .secrets
   ```

## References

- [act GitHub Repository](https://github.com/nektos/act)
- [act Documentation](https://github.com/nektos/act#readme)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
