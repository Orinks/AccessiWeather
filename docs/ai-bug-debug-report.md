# AI Explainer Empty Response Bug - Debug Report

**Date:** December 11, 2025  
**Status:** Under Investigation  
**Severity:** P0 - Blocks Feature Launch

## Bug Description

The "Explain Weather" button shows a dialog with empty explanation text, despite the API returning content.

## Testing Results

### ✅ PASSED: `_format_response` Method

Ran standalone tests of the `_format_response` regex patterns:
- **Result:** All 6 test cases passed
- **Conclusion:** The markdown stripping logic is working correctly
- **Evidence:** See `test_format_response.py` output

Test cases included:
1. Simple plain text → ✅ Works
2. Text with bold markdown → ✅ Works  
3. Text with underscores → ✅ Works (removes underscores, preserves text)
4. Realistic weather response → ✅ Works
5. Response with full markdown → ✅ Works
6. Response with single underscores → ✅ Works

**Key Finding:** The `_format_response` method is NOT the source of the bug.

## New Hypothesis: The Bug is Upstream

Since `_format_response` works correctly, the bug must be in:

### 1. **API Response Handling** ⭐ MOST LIKELY
Location: `ai_explainer.py` → `_call_openrouter()` method

**Suspicious Code:**
```python
content = response.choices[0].message.content
if content is None:
    logger.warning("OpenRouter returned None content in response")
    content = ""  # ← BUG: Sets to empty string!
```

**Problem:** If OpenRouter returns `None`, we set it to empty string and continue.  
**Fix Needed:** Should raise an error or log more aggressively.

### 2. **Cache Corruption** 
Location: `ai_explainer.py` → `explain_weather()` method

**Suspicious Code:**
```python
# Check cache first
if self.cache:
    cached_result = self.cache.get(cache_key)
    if cached_result:
        # ... may return empty cached result
```

**Problem:** If cache has an empty result from a previous failed attempt, it will be returned.  
**Fix Needed:** Validate cached results before returning.

### 3. **Dialog Display Logic**
Location: `dialogs/explanation_dialog.py`

**Problem:** The text might be generated correctly but not displayed in the dialog.  
**Fix Needed:** Check if `text` is being passed to the dialog correctly.

## Debug Strategy

### Step 1: Add Enhanced Logging (✅ DONE)

Added comprehensive logging to:
- `_format_response()` - Track each regex step
- `_call_openrouter()` - Log API response structure
- `explain_weather()` - Track data flow

### Step 2: Test with Real API Call (⏳ TODO)

**Action Items:**
1. Get a valid OpenRouter API key
2. Run the app and click "Explain Weather"
3. Check logs for where content becomes empty
4. Look for:
   - `[API] Content received: len=0` ← API returning empty
   - `[EXPLAIN] Raw content from API (len=0)` ← Empty before formatting
   - `[FORMAT] Final result: len=0` ← Empty after formatting (unlikely based on tests)

**Command to check logs:**
```bash
# Find the log file
find ~/.config/accessiweather -name "*.log" -type f

# Or check app logs
tail -f ~/accessiweather.log | grep -E "\[API\]|\[EXPLAIN\]|\[FORMAT\]|EMPTY"
```

### Step 3: Test Individual Components

**Test A: API Call Directly**
```python
# Create test_api_direct.py
import asyncio
from src.accessiweather.ai_explainer import AIExplainer

async def test():
    explainer = AIExplainer(api_key="YOUR_KEY", model="openrouter/auto:free")
    result = await explainer.explain_weather(
        {"temperature": 72, "conditions": "Sunny", "humidity": 65},
        "Test Location",
    )
    print(f"Result text: '{result.text}'")
    print(f"Length: {len(result.text)}")

asyncio.run(test())
```

**Test B: Check Cache**
```python
# See if cache has empty results
if hasattr(app, 'ai_explanation_cache'):
    cache = app.ai_explanation_cache
    # Inspect cache contents
```

**Test C: Test with `preserve_markdown=True`**
```python
# In handlers/ai_handlers.py, force preserve_markdown=True
preserve_markdown = True  # Override setting
result = await explainer.explain_weather(..., preserve_markdown=True)
```

### Step 4: Check API Key Validity

**Possible Issue:** API key might be invalid, causing OpenRouter to return empty responses.

**Test:**
1. Go to Settings → AI Explanations
2. Click "Validate API Key"
3. Check if validation passes

## Next Actions

### Immediate (Do Now):
1. ✅ Run `test_format_response.py` - **COMPLETED** (all tests passed)
2. ⏳ Get OpenRouter API key from https://openrouter.ai/keys
3. ⏳ Run the app with logging enabled
4. ⏳ Click "Explain Weather" button
5. ⏳ Check logs for `[API]`, `[EXPLAIN]`, `[FORMAT]` tags

### Short-term (If Immediate Actions Don't Reveal Issue):
1. Add validation to reject empty API responses
2. Add cache invalidation for empty results
3. Add UI check to show error if text is empty before displaying dialog
4. Test with different models (free vs paid)

### Nuclear Option (If All Else Fails):
1. Temporarily bypass `_format_response` entirely
2. Display raw API response to see if content exists
3. Work backwards to find where it disappears

## Code Changes Made

### File: `src/accessiweather/ai_explainer.py`

**Added logging in `_format_response()`:**
- Logs each regex step with before/after length
- Logs full text at key points
- Special error log if output is empty but input had content

**Added logging in `_call_openrouter()`:**
- Logs response structure
- Logs content length and preview
- Logs if content is None

**Added logging in `explain_weather()`:**
- Logs raw API content with full text
- Logs formatted result with full text
- Special error log if text is empty (🔴 EMPTY TEXT BUG DETECTED)

## Debugging Commands

```bash
# Run app in dev mode
briefcase dev

# Watch logs in real-time (if logs are written)
tail -f ~/.config/accessiweather/logs/*.log

# Or check main log
tail -f ~/accessiweather.log

# Run format tests
python3 test_format_response.py

# Search for bug indicators in logs
grep -i "empty\|none\|len=0" ~/accessiweather.log | tail -50
```

## Expected Log Pattern (Successful Explanation)

```
[API] Response object type: <class 'openai.types.chat.chat_completion.ChatCompletion'>
[API] Response choices: 1 choices
[API] Content received: len=250
[API] Content preview: The current temperature is 72°F...
[API] OpenRouter response: model=meta-llama/llama-3.2-3b-instruct:free, content_len=250

[EXPLAIN] Raw content from API (len=250)
[EXPLAIN] About to format with preserve_markdown=False

[FORMAT] Input - preserve_markdown=False, len=250
[FORMAT] Step 0 (initial): len=250, text=The current temperature...
[FORMAT] Step 10 (after whitespace cleanup): len=248, text=The current...
[FORMAT] Final result: len=248

[EXPLAIN] Formatted text returned (len=248)
```

## Expected Log Pattern (Bug Occurs)

```
[API] Content received: len=0  ← API RETURNING EMPTY!
OR
[API] OpenRouter returned None content in response  ← API RETURNING None!
OR
[EXPLAIN] Raw content from API (len=0)  ← EMPTY BEFORE FORMATTING
OR
[EXPLAIN] ❌ EMPTY TEXT BUG DETECTED! Raw had 250 chars but formatted has 0  ← FORMATTING BUG (unlikely)
```

## Status: Ready for Live Testing

With enhanced logging in place, the next step is to:
1. Run the actual app
2. Trigger the bug
3. Read the logs to see exactly where content becomes empty

The logs will definitively tell us which component is failing.
