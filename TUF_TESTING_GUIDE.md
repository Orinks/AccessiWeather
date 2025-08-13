# TUF Testing Guide for AccessiWeather

This guide provides comprehensive information about testing the TUF (The Update Framework) integration in AccessiWeather.

## Overview

The TUF testing infrastructure consists of multiple test files that cover different aspects of the TUF integration:

- **`run_tuf_tests.py`** - Comprehensive test orchestration script
- **`test_tuf_package_check.py`** - Package verification and basic imports
- **`test_tuf_simple.py`** - Simple integration tests with enhanced scenarios
- **`test_tuf_integration.py`** - Comprehensive integration testing
- **`tests/test_tuf_update_service.py`** - Unit tests using pytest

## Test Files Description

### 1. Package Verification (`test_tuf_package_check.py`)
- Verifies `tufup` package installation
- Tests basic imports and dependencies
- Checks TUF system availability
- Provides diagnostic information

### 2. Simple Integration Tests (`test_tuf_simple.py`)
Enhanced with comprehensive scenarios:
- **Basic Service Testing**: TUF service initialization and settings management
- **Download Testing**: Update download functionality
- **TUF Repository Access**: Repository connectivity and availability checks
- **GitHub Fallback**: Fallback mechanism when TUF is unavailable
- **Update Channels**: Testing different channels (stable, beta, dev)
- **Error Scenarios**: Invalid methods, channels, and error handling

### 3. Comprehensive Integration Tests (`test_tuf_integration.py`)
Enhanced with advanced integration scenarios:
- **TUF Updates**: Core TUF update functionality
- **Settings Management**: Configuration management and persistence
- **Repository Validation**: TUF repository validation and connectivity
- **Metadata Validation**: TUF metadata handling and validation
- **Configuration Scenarios**: Various configuration combinations
- **Error Recovery**: Error handling and service recovery
- **Multi-Method Switching**: Dynamic switching between TUF and GitHub

### 4. Unit Tests (`tests/test_tuf_update_service.py`)
- Comprehensive unit testing with pytest
- Mock objects for isolated testing
- Individual method testing
- Edge case coverage

## Running Tests

### Option 1: Run All Tests (Recommended)
```bash
python run_tuf_tests.py
```

This orchestration script will:
1. Run package verification first
2. Execute simple integration tests
3. Run comprehensive integration tests
4. Execute pytest unit tests
5. Perform additional TUF-specific tests
6. Generate comprehensive reports

### Option 2: Run Individual Test Files
```bash
# Package verification
python test_tuf_package_check.py

# Simple integration tests
python test_tuf_simple.py

# Comprehensive integration tests
python test_tuf_integration.py

# Unit tests
python -m pytest tests/test_tuf_update_service.py -v
```

## Test Scenarios Covered

### TUF Available Scenarios
When `tufup` package is installed and TUF is available:
- TUF client initialization
- TUF repository connectivity
- TUF metadata validation
- TUF update checking
- Automatic fallback to GitHub when TUF fails

### TUF Unavailable Scenarios
When `tufup` package is not installed:
- GitHub-only operation
- Proper fallback behavior
- Error handling for missing TUF

### Channel Testing
Tests all supported update channels:
- **Stable**: Production releases
- **Beta**: Pre-release testing versions
- **Dev**: Development versions

### Error Conditions
- Invalid update methods
- Invalid channels
- Network connectivity issues
- Repository access failures
- Configuration validation errors

## Interpreting Results

### Success Indicators
- ✅ **PASS** - Test completed successfully
- All expected functionality working
- Proper error handling for invalid inputs
- Successful fallback mechanisms

### Warning Indicators
- ⚠️ **WARNING** - Non-critical issues
- TUF unavailable (expected in some environments)
- Network connectivity issues
- Repository access limitations

### Failure Indicators
- ❌ **FAIL** - Test failed
- Critical functionality not working
- Unexpected errors or crashes
- Configuration issues

### Test Output Examples

#### Successful TUF Test
```
✅ TUF Available: True
✅ TUF repository accessible: True
✅ GitHub fallback working: True
✅ All channels tested successfully
```

#### TUF Unavailable (Expected)
```
⚠️ TUF not available - tufup package not installed
✅ GitHub fallback working: True
✅ Service functioning in GitHub-only mode
```

## Troubleshooting

### Common Issues and Solutions

#### 1. TUF Package Not Found
**Error**: `ModuleNotFoundError: No module named 'tufup'`
**Solution**: Install the tufup package:
```bash
pip install tufup
```

#### 2. Import Errors
**Error**: `ImportError: cannot import name 'TUFUpdateService'`
**Solution**: Ensure you're running from the correct directory and the src path is accessible:
```bash
# Run from project root
cd /path/to/accessiweather
python test_tuf_simple.py
```

#### 3. Network Connectivity Issues
**Error**: Connection timeouts or network errors
**Solution**:
- Check internet connectivity
- Verify GitHub API access
- Check firewall settings
- Try running tests with different network conditions

#### 4. Configuration Errors
**Error**: Invalid configuration values
**Solution**:
- Check configuration file format
- Verify channel names (stable, beta, dev)
- Ensure method names are correct (tuf, github)

#### 5. Repository Access Issues
**Error**: TUF repository not accessible
**Solution**:
- Verify repository URL configuration
- Check repository availability
- Test with different repository URLs
- Ensure proper TUF metadata structure

## Prerequisites

### Required Packages
- `tufup` - For TUF functionality (optional, tests will run without it)
- `aiohttp` - For HTTP requests
- `pytest` - For unit testing

### Environment Requirements
- Python 3.8+
- Internet connectivity for GitHub API access
- Access to TUF repository (if testing TUF functionality)

### Configuration
- Valid AccessiWeather configuration directory
- Proper update service settings
- Network access for external repositories

## Expected Behavior

### With TUF Available
1. TUF client initializes successfully
2. Repository connectivity is established
3. Update checking works via TUF
4. GitHub fallback is available as backup
5. All channels are accessible
6. Configuration changes are persistent

### Without TUF Available
1. Service gracefully falls back to GitHub-only mode
2. All GitHub functionality works normally
3. TUF-specific features are properly disabled
4. No critical errors or crashes
5. User experience remains consistent

## Test Reports

The orchestration script generates two types of reports:

### Summary Report (`tuf_test_report.txt`)
- High-level test results
- Pass/fail summary
- Execution time
- Recommendations for fixes

### Detailed Report (`tuf_test_results.json`)
- Complete test output
- Diagnostic information
- Error details
- Configuration data

## Maintenance

### Adding New Tests
1. Add test functions to appropriate test files
2. Update the orchestration script if needed
3. Document new test scenarios in this guide
4. Ensure proper error handling and reporting

### Updating Test Configuration
1. Modify test configuration in individual test files
2. Update mock objects as needed
3. Adjust expected behaviors for new features
4. Update documentation accordingly

## Best Practices

1. **Run Full Test Suite**: Always use `run_tuf_tests.py` for comprehensive testing
2. **Check Prerequisites**: Ensure all required packages are installed
3. **Review Reports**: Examine both summary and detailed reports
4. **Test Different Environments**: Test with and without TUF available
5. **Validate Configuration**: Ensure proper configuration before testing
6. **Monitor Network**: Be aware of network dependencies in tests

## Support

For issues with TUF testing:
1. Check this guide for common solutions
2. Review test output and error messages
3. Verify prerequisites and configuration
4. Test individual components separately
5. Check network connectivity and repository access
