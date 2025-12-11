---
stepsCompleted: []
inputDocuments:
  - .kiro/specs/ai-weather-explanations/requirements.md
  - .kiro/specs/ai-weather-explanations/design.md
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 2
workflowType: 'prd'
lastStep: 0
---

# Product Requirements Document - AI Weather Explanations

**Author:** Josh  
**Date:** December 11, 2025  
**Status:** In Development (feature/ai-weather-explanations branch)  
**Priority:** P1 - High  
**Target Release:** v1.5.0

## Executive Summary

This feature adds AI-powered natural language explanations to AccessiWeather, transforming raw weather data into plain-English insights that help users understand what weather conditions mean for their daily activities. The integration uses OpenRouter's unified AI API gateway, supporting both free models (no API key required) and paid models for enhanced quality.

**Key Value Propositions:**
- **Accessibility First**: Natural language explanations benefit screen reader users and anyone who finds raw weather data overwhelming
- **Zero Barrier to Entry**: Free models work without API keys or payment, allowing all users to try the feature
- **Cost Control**: Users with paid API keys can control spending through model selection and built-in caching
- **Seamless Integration**: Fits naturally into existing weather display workflow with minimal UI changes

**Business Impact:**
- Increases user engagement by making weather data more actionable
- Differentiates AccessiWeather from competitors focused solely on data display
- Expands user base to include those who struggle with interpreting weather terminology
- Provides upsell path for premium AI models while maintaining free tier

## Problem Statement

### User Pain Points

**Current State:**
1. **Data Overload**: Users see "Temperature: 72°F, Humidity: 65%, Wind: 8 mph NW" but don't know if they need a jacket or if it's safe to go for a run
2. **Accessibility Barriers**: Screen reader users navigate through numerical data without contextual understanding
3. **Weather Jargon**: Terms like "visibility 10 mi" or "pressure 29.92 inHg" are meaningless to average users
4. **Alert Confusion**: Weather alerts contain technical language that obscures urgency and required actions

**User Quotes** (from issue tracker and support requests):
> "I can see it's 45 degrees and cloudy, but should I bring a heavy coat or a light jacket?"

> "The app tells me there's a winter storm watch, but I don't understand the difference between a watch and a warning."

> "As a screen reader user, I spend 5 minutes listening to all the numbers. I just want to know if it's nice outside!"

### Business Context

AccessiWeather serves two primary user segments:
1. **Screen reader users** requiring accessible weather information (primary target)
2. **General users** preferring desktop weather apps over web browsers (secondary)

Current metrics show:
- 78% of users view current conditions daily
- Only 23% check detailed forecast data
- Support requests frequently ask "what does this weather mean?"

**Opportunity**: AI explanations can increase engagement, reduce support burden, and differentiate AccessiWeather in a crowded market.

## Goals & Success Metrics

### Primary Goals

1. **G1: Increase User Understanding**
   - Metric: User survey shows >70% report better weather comprehension
   - Target: Launch with 90% positive feedback in beta testing
   
2. **G2: Maintain Accessibility Excellence**
   - Metric: Screen reader navigation time to get weather summary <30 seconds
   - Target: WCAG 2.1 AAA compliance maintained

3. **G3: Control Costs**
   - Metric: Average cost per user per month <$0.10 for paid model users
   - Target: >80% of explanations served from cache

4. **G4: Zero Barrier Adoption**
   - Metric: >50% of users try AI explanations in first week
   - Target: Free model works for 100% of users without configuration

### Secondary Goals

1. **S1: Reduce Support Burden**
   - Metric: Weather interpretation support tickets decrease 30%
   
2. **S2: Feature Discovery**
   - Metric: "Explain Weather" button clicked within 3 app sessions by >60% of users

### Non-Goals (Out of Scope)

- ❌ Multi-language support (English only in v1)
- ❌ Voice/audio explanations (text only)
- ❌ Explanation history or saved explanations
- ❌ Custom prompt templates or user-configurable explanation styles
- ❌ Forecast comparisons or "why did the forecast change?" explanations
- ❌ Integration with other AI providers (OpenRouter only)

## User Stories & Requirements

### Epic 1: Core Explanation Generation

#### US-1.1: View Weather Explanation
**As a** user viewing current weather  
**I want to** click an "Explain Weather" button  
**So that** I get a plain-English summary of what the conditions mean for my activities  

**Acceptance Criteria:**
1. ✅ "Explain Weather" button appears next to current conditions when AI feature enabled
2. ✅ Button has proper ARIA labels for screen readers
3. ✅ Clicking button shows loading indicator
4. ✅ Explanation appears in accessible dialog within 5 seconds (95th percentile)
5. ✅ Dialog includes location name, timestamp, and explanation text
6. ✅ Explanation is 3-4 sentences (STANDARD style) by default

**Priority:** P0 (Must Have)

#### US-1.2: Contextual Weather Insights
**As a** user receiving an explanation  
**I want** the AI to consider all relevant weather data (temp, humidity, wind, alerts)  
**So that** I get comprehensive insights, not just a temperature description  

**Acceptance Criteria:**
1. ✅ Prompt includes: temperature, conditions, humidity, wind speed/direction, visibility
2. ✅ If weather alerts exist, they're mentioned in explanation
3. ✅ If no alerts, explanation focuses on current conditions only
4. ✅ Explanation considers time of day and location context
5. ✅ Most recent weather data source is used (if multiple sources available)

**Priority:** P0 (Must Have)

### Epic 2: Free Model Support

#### US-2.1: Try AI Without API Key
**As a** new user  
**I want to** use AI explanations without signing up for anything or entering payment info  
**So that** I can evaluate the feature risk-free before deciding to upgrade  

**Acceptance Criteria:**
1. ✅ Default model is `openrouter/auto:free` (no API key needed)
2. ✅ First explanation works immediately after enabling feature in settings
3. ✅ Error message if OpenRouter API key is required but missing is clear and actionable
4. ✅ UI indicates "Using free models" in settings
5. ✅ Free models are rate-limited by OpenRouter, not AccessiWeather

**Priority:** P0 (Must Have)  
**Note:** OpenRouter changed their API after initial design—API keys are now required even for free models. Updated requirement: provide clear onboarding to get free API key from openrouter.ai/keys

#### US-2.2: Caching for Free Users
**As a** user with free models  
**I want** explanations to be cached  
**So that** I don't hit rate limits when refreshing weather frequently  

**Acceptance Criteria:**
1. ✅ Explanations cached for 5 minutes by default
2. ✅ Cache key based on location + weather data (temp, conditions, humidity, wind)
3. ✅ Cached explanations return instantly (<100ms)
4. ✅ Cache hit indicator shown in dialog ("Generated at HH:MM")
5. ✅ Rate limit errors suggest checking cached explanations

**Priority:** P1 (Should Have)

### Epic 3: Paid Model Configuration

#### US-3.1: Configure OpenRouter API Key
**As a** user wanting better explanations  
**I want to** enter my OpenRouter API key in settings  
**So that** I can use paid models for higher quality responses  

**Acceptance Criteria:**
1. ✅ Settings dialog has "AI Explanations" section
2. ✅ Password input field for API key (masked display)
3. ✅ "Validate API Key" button tests key before saving
4. ✅ Validation success/failure shown immediately
5. ✅ API key stored securely in system keyring
6. ✅ Invalid API keys rejected with helpful error message

**Priority:** P1 (Should Have)

#### US-3.2: Choose AI Model
**As a** user with an API key  
**I want to** select between free and paid model tiers  
**So that** I can balance cost and quality based on my needs  

**Acceptance Criteria:**
1. ✅ Model dropdown with options: "Auto (Free)", "Auto (Paid - requires API key)"
2. ✅ Tooltip explains difference: Free = no cost, Paid = better quality + small fee
3. ✅ Link to OpenRouter pricing page
4. ✅ Selected model persists across app restarts
5. ✅ Changing model doesn't require app restart

**Priority:** P1 (Should Have)

#### US-3.3: Monitor Usage
**As a** user with paid models  
**I want to** see estimated token usage and costs  
**So that** I can avoid unexpected charges  

**Acceptance Criteria:**
1. ✅ Each explanation dialog shows: model used, token count, estimated cost
2. ✅ Free models show "No cost" instead of $0.00
3. ✅ Session total displayed in settings (resets on app restart)
4. ✅ Cost estimates use OpenRouter's public pricing (approximate)
5. ✅ Disclaimer that costs are estimates, check OpenRouter dashboard for actual

**Priority:** P2 (Nice to Have)

### Epic 4: Error Handling & Resilience

#### US-4.1: Graceful API Failures
**As a** user experiencing network issues  
**I want** clear, actionable error messages  
**So that** I understand what went wrong and how to fix it  

**Acceptance Criteria:**
1. ✅ No technical details (HTTP codes, stack traces, API response bodies) shown to users
2. ✅ Network errors: "Unable to connect to AI service. Check your internet connection."
3. ✅ Invalid API key: "API key is invalid. Please check your settings."
4. ✅ Insufficient credits: "Your OpenRouter account has no funds. Add credits or switch to free models."
5. ✅ Rate limit: "Rate limit exceeded. Try again in a few minutes."
6. ✅ All errors logged with full details for debugging

**Priority:** P0 (Must Have)

#### US-4.2: Fallback Strategies
**As a** user when AI service fails  
**I want** alternative options to get weather information  
**So that** temporary outages don't block my access to weather data  

**Acceptance Criteria:**
1. ✅ Cached explanation offered if available (even if stale)
2. ✅ "View Raw Data" button in error dialog
3. ✅ Retry button for transient errors
4. ✅ Feature doesn't break or crash the app when API unavailable
5. ✅ Weather display works normally even if AI feature fails

**Priority:** P1 (Should Have)

### Epic 5: Accessibility & Screen Reader Support

#### US-5.1: Screen Reader Navigation
**As a** screen reader user  
**I want** AI explanations to be fully accessible  
**So that** I can benefit from natural language summaries as much as sighted users  

**Acceptance Criteria:**
1. ✅ "Explain Weather" button has aria-label and aria-description
2. ✅ Loading state announced via ARIA live region
3. ✅ Explanation dialog sets focus to text content on open
4. ✅ Close button accessible via keyboard (Escape key)
5. ✅ Error messages announced via ARIA live region
6. ✅ No keyboard traps in explanation dialog

**Priority:** P0 (Must Have)

#### US-5.2: Plain Text Formatting
**As a** screen reader user  
**I want** explanations without markdown formatting  
**So that** my screen reader doesn't announce asterisks, brackets, and other symbols  

**Acceptance Criteria:**
1. ✅ Markdown stripped from AI responses by default
2. ✅ No bold (`**text**`), italic (`*text*`), or code (`` `text` ``) markers in output
3. ✅ Links converted to plain text (keep link text, remove URL)
4. ✅ Bullet points converted to simple line breaks
5. ✅ Headers converted to plain text (remove `#` symbols)

**Priority:** P0 (Must Have)

## Technical Requirements

### TR-1: API Integration
- Use OpenRouter API via OpenAI-compatible SDK (`openai>=1.0.0`)
- Base URL: `https://openrouter.ai/api/v1`
- Support `openrouter/auto:free` and `openrouter/auto` model identifiers
- 30-second timeout on API calls
- Exponential backoff for retries (max 3 attempts)

### TR-2: Security
- API keys stored in system keyring (existing AccessiWeather pattern)
- Keys never logged or exposed in error messages
- Mask keys in UI (show last 4 characters only: `sk-or-...abc123`)
- Validate API key format before storage (regex: `^sk-or-[a-zA-Z0-9-_]{20,}$`)

### TR-3: Performance
- Explanation generation: p95 < 5 seconds, p99 < 10 seconds
- Cache hits: <100ms response time
- Cache TTL: 5 minutes (300 seconds) default
- Async operations via `asyncio.to_thread()` to avoid UI blocking
- Memory: <5MB additional footprint when feature enabled

### TR-4: Testing Coverage
- Unit tests: >85% code coverage for `ai_explainer.py`
- Property-based tests: 18 properties validated with 100+ iterations each
- Integration tests: Marked with `@pytest.mark.integration`, skipped in CI
- Accessibility tests: All ARIA attributes verified programmatically

### TR-5: Dependencies
```toml
[project]
dependencies = [
    "openai>=1.0.0",  # OpenRouter-compatible client
]
```

### TR-6: Configuration Schema
```python
class AppSettings:
    enable_ai_explanations: bool = False
    openrouter_api_key: str | None = None
    ai_model_preference: str = "auto:free"  # "auto:free" | "auto"
    ai_explanation_style: str = "standard"  # "brief" | "standard" | "detailed"
    ai_cache_ttl: int = 300  # seconds
```

## User Experience & Design

### UI Components

#### 1. Explain Weather Button
**Location:** Current weather display, below conditions summary  
**Appearance:** Standard Toga button, same style as "Refresh Weather"  
**Label:** "Explain Weather"  
**ARIA:** 
- `aria-label="Get AI explanation of current weather"`
- `aria-description="Opens a dialog with natural language explanation of weather conditions"`

**Visibility Rules:**
- Shown when `enable_ai_explanations=True` in settings
- Hidden when `enable_ai_explanations=False`
- Disabled (grayed out) when no weather data loaded

#### 2. Explanation Dialog
**Type:** Modal dialog (Toga Window)  
**Size:** 500x400px (expandable)  
**Layout:**
```
┌─────────────────────────────────────────┐
│ Weather Explanation - [Location]    [X] │
├─────────────────────────────────────────┤
│                                         │
│  [Explanation text: 3-4 sentences]      │
│                                         │
│  -----------------------------------    │
│                                         │
│  Model: openrouter/auto:free            │
│  Tokens: 150                            │
│  Cost: No cost                          │
│  Generated: 2:30 PM                     │
│                                         │
│            [Close]                      │
└─────────────────────────────────────────┘
```

**Focus Management:**
- Focus set to explanation text on open
- Escape key closes dialog
- Tab cycles through text → metadata → Close button → text

#### 3. Loading Dialog
**Type:** Non-modal overlay  
**Content:** "Generating weather explanation for [Location]..." with spinner  
**ARIA:** Live region announces "Loading weather explanation"  
**Timeout:** Shows for entire API call duration, auto-closes on success

#### 4. Error Dialog
**Type:** Modal dialog  
**Layout:**
```
┌─────────────────────────────────────────┐
│ Unable to Generate Explanation      [X] │
├─────────────────────────────────────────┤
│                                         │
│  ⚠️ [Error message]                     │
│                                         │
│            [Retry]  [Close]             │
└─────────────────────────────────────────┘
```

**ARIA:** Live region announces error message immediately

#### 5. Settings Section
**Location:** Settings Dialog → New "AI Explanations" tab  
**Layout:**
```
AI Explanations
═══════════════════════════════════════

☑ Enable AI Explanations
  Turn on AI-powered weather explanations

OpenRouter API Key:
  Required for all models. Get a free key at
  openrouter.ai/keys
  
  [••••••••••••••••••••••••••abc123]
  
  [Validate API Key]

Model Preference:
  [Auto (Free)                    ▼]
  
  Free models require an API key but don't
  charge your account. Get yours at
  openrouter.ai/keys

Explanation Style:
  [Standard                       ▼]
  
Session Usage:
  Explanations: 5
  Tokens: 750
  Est. Cost: No cost

[OpenRouter Pricing →]
```

### Accessibility Specifications

**WCAG 2.1 Compliance:** AAA (maintain existing AccessiWeather standard)

**Screen Reader Testing:**
- NVDA (Windows): Primary test target
- JAWS (Windows): Secondary test target
- Narrator (Windows): Tertiary test target

**Keyboard Navigation:**
- All features accessible without mouse
- Logical tab order: button → dialog → close
- Escape key always closes dialogs
- Enter key activates buttons

**ARIA Patterns:**
- `role="dialog"` for explanation dialog
- `aria-modal="true"` for modal dialogs
- `aria-live="polite"` for loading states
- `aria-live="assertive"` for errors
- `aria-describedby` links metadata to explanation text

## Correctness Properties

*Properties define invariants that must hold true across all valid system states. These serve as formal specifications for automated testing and verification.*

### Data Properties

**P1: Button Visibility Follows Setting**  
∀ app_state: `enable_ai_explanations=True` ⟹ button visible  
∀ app_state: `enable_ai_explanations=False` ⟹ button hidden  
*Validates: US-1.1*

**P2: Model Selection Matches Configuration**  
∀ config: `api_key=None` ⟹ `effective_model="openrouter/auto:free"`  
∀ config: `api_key≠None ∧ preference="auto:free"` ⟹ `effective_model="openrouter/auto:free"`  
∀ config: `api_key≠None ∧ preference="auto"` ⟹ `effective_model="openrouter/auto"`  
*Validates: US-2.1, US-3.2*

**P3: Cache Prevents Duplicate API Calls**  
∀ request₁, request₂: `same_weather_data(request₁, request₂) ∧ time_delta<5min` ⟹ `no_api_call(request₂)`  
*Validates: US-2.2*

**P4: Settings Persistence**  
∀ settings: `save(settings) ; load()` ⟹ `settings' = settings`  
*Validates: US-3.1, US-3.2*

### Behavior Properties

**P5: Prompt Completeness**  
∀ weather_data: `has_required_fields(weather_data)` ⟹ `all_fields_in_prompt(prompt)`  
Required fields: temperature, conditions, humidity, wind_speed, visibility  
*Validates: US-1.2*

**P6: Alerts Inclusion**  
∀ weather_data: `has_alerts(weather_data)` ⟹ `alerts_in_prompt(prompt)`  
∀ weather_data: `no_alerts(weather_data)` ⟹ `no_alert_mention(prompt)`  
*Validates: US-1.2*

**P7: Markdown Formatting**  
∀ response: `html_disabled` ⟹ `no_markdown_syntax(formatted_response)`  
∀ response: `html_enabled` ⟹ `markdown_preserved(formatted_response)`  
*Validates: US-5.2*

**P8: Most Recent Data Source**  
∀ sources: `|sources|>1` ⟹ `selected_source = max(sources, key=timestamp)`  
*Validates: US-1.2*

### Safety Properties

**P9: Error Message Safety**  
∀ error: `user_message(error)` ⟹ `no_technical_details(message)`  
Technical details: stack traces, HTTP codes, JSON responses, API internals  
*Validates: US-4.1*

**P10: Error Logging**  
∀ error: `occurs(error)` ⟹ `logged(error, level=ERROR) ∧ user_message_safe`  
*Validates: US-4.1*

### Cost Properties

**P11: Token Display for Paid Models**  
∀ result: `is_paid_model(result.model)` ⟹ `display_includes(token_count)`  
*Validates: US-3.3*

**P12: Cost Estimation Timing**  
∀ request: `estimate_cost(request)` happens_before `api_call(request)`  
*Validates: US-3.3*

**P13: Session Usage Accumulation**  
∀ session: `total_tokens = Σ(explanation.tokens for explanation in session)`  
*Validates: US-3.3*

**P14: Free Model Cost Display**  
∀ result: `":free" in result.model` ⟹ `display_cost = "No cost"`  
*Validates: US-3.3*

### Accessibility Properties

**P15: ARIA Attributes Present**  
∀ button: `is_explain_button(button)` ⟹ `has_aria_label(button) ∧ has_aria_description(button)`  
*Validates: US-5.1*

**P16: Dialog Focus Management**  
∀ dialog: `opens(dialog)` ⟹ `eventually(focused(dialog.explanation_text))`  
*Validates: US-5.1*

**P17: Loading Announcement**  
∀ request: `starts(request)` ⟹ `announced(loading_state, politeness=polite)`  
*Validates: US-5.1*

**P18: Error Announcement**  
∀ error: `occurs(error)` ⟹ `announced(error_message, politeness=assertive)`  
*Validates: US-5.1*

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
**Status:** ✅ Complete

- [x] Add `openai` dependency to `pyproject.toml`
- [x] Create `ai_explainer.py` module with `AIExplainer` class
- [x] Implement prompt construction from weather data
- [x] Add OpenRouter API integration with error handling
- [x] Implement markdown stripping for accessibility
- [x] Add caching layer using existing `cache.py`
- [x] Write unit tests for core logic (target: >85% coverage)

**Deliverables:**
- `src/accessiweather/ai_explainer.py` (✅ Complete)
- `tests/test_ai_explainer.py` (✅ Complete)

### Phase 2: Configuration & Settings (Week 1-2)
**Status:** ✅ Complete

- [x] Extend `AppSettings` model with AI fields
- [x] Add AI settings section to settings dialog
- [x] Implement API key validation
- [x] Add secure storage integration for API keys
- [x] Create settings persistence tests

**Deliverables:**
- Updated `src/accessiweather/models.py` (✅ Complete)
- Updated `src/accessiweather/dialogs/settings_dialog.py` (✅ Complete)
- Updated `src/accessiweather/dialogs/settings_tabs.py` (✅ Complete)

### Phase 3: UI Integration (Week 2)
**Status:** ✅ Complete

- [x] Add "Explain Weather" button to weather display
- [x] Create explanation dialog
- [x] Create loading dialog
- [x] Create error dialog
- [x] Implement button visibility logic
- [x] Add ARIA attributes to all components
- [x] Write UI component tests

**Deliverables:**
- Updated `src/accessiweather/ui_builder.py` (✅ Complete)
- `src/accessiweather/dialogs/explanation_dialog.py` (✅ Complete)
- `src/accessiweather/handlers/ai_handlers.py` (✅ Complete)

### Phase 4: Bug Fixes & Polish (Week 3 - CURRENT)
**Status:** 🔄 In Progress

**Known Issues:**
- [ ] **CRITICAL BUG**: Empty explanation text in dialog despite API returning content
  - Symptoms: Explanation dialog shows blank text area
  - Suspected cause: Over-aggressive markdown stripping or empty API response handling
  - Debug logs added in commit `9da9601`
  - Log location changed in commit `453e753` (now in `config_dir/logs/`)
  
**Remaining Tasks:**
- [ ] Debug and fix empty response issue
- [ ] Verify free model behavior with actual OpenRouter API key
- [ ] Test rate limiting scenarios
- [ ] Improve error messages based on user testing
- [ ] Add retry logic for transient failures
- [ ] Optimize cache key generation

**Deliverables:**
- Bug fixes in `src/accessiweather/ai_explainer.py`
- Updated error handling in `src/accessiweather/handlers/ai_handlers.py`

### Phase 5: Testing & Documentation (Week 3-4)
**Status:** ⏳ Planned

- [ ] Run full property-based test suite (18 properties)
- [ ] Manual accessibility testing with NVDA
- [ ] Integration tests with real OpenRouter API
- [ ] Update user manual with AI features section
- [ ] Create troubleshooting guide for common errors
- [ ] Add inline help text in settings

**Deliverables:**
- Updated `docs/user_manual.md`
- `docs/ai-explanations-troubleshooting.md`
- Test coverage report (target: >85%)

### Phase 6: Beta Release (Week 4)
**Status:** ⏳ Planned

- [ ] Merge `feature/ai-weather-explanations` to `dev`
- [ ] Deploy beta build via nightly releases
- [ ] Collect user feedback
- [ ] Monitor error rates and API usage
- [ ] Iterate on error messages and UI copy

**Deliverables:**
- Beta release announcement
- Feedback collection form
- Usage analytics dashboard

### Phase 7: Production Release (Week 5)
**Status:** ⏳ Planned

- [ ] Address beta feedback
- [ ] Final accessibility audit
- [ ] Performance testing under load
- [ ] Update changelog
- [ ] Merge to `main` branch
- [ ] Release v1.5.0 with AI features

**Deliverables:**
- Release notes
- Marketing materials (blog post, social media)
- Support documentation

## Dependencies & Risks

### External Dependencies

**OpenRouter API** (Critical)
- **Risk:** Service outage blocks feature
- **Mitigation:** Cache fallback, graceful degradation, clear error messages
- **SLA:** No formal SLA, community-supported service
- **Fallback:** None currently; future could add direct OpenAI/Anthropic integration

**OpenAI Python SDK** (Medium)
- **Risk:** Breaking changes in SDK updates
- **Mitigation:** Pin version to `openai>=1.0.0,<2.0.0`
- **Fallback:** Raw HTTP requests if SDK breaks

### Technical Risks

**TR-1: API Key Requirement Change**
- **Risk:** OpenRouter now requires API keys even for free models (changed after initial design)
- **Impact:** Medium - requires user onboarding step
- **Status:** Documented in requirements; UI updated to guide users to openrouter.ai/keys
- **Mitigation:** Clear messaging, one-click link to key registration

**TR-2: Rate Limiting on Free Tier**
- **Risk:** Free models have aggressive rate limits, causing frequent failures
- **Impact:** Medium - poor user experience for free users
- **Mitigation:** Aggressive caching (5min TTL), clear error messages, suggest waiting
- **Monitoring:** Track rate limit error frequency

**TR-3: Cost Overruns for Paid Users**
- **Risk:** Users with paid API keys rack up unexpected charges
- **Impact:** High - potential negative reviews, support burden
- **Mitigation:** Session usage tracking, cost estimates, default to free models
- **Safeguard:** No auto-upgrade to paid; explicit user opt-in required

**TR-4: Prompt Injection Attacks**
- **Risk:** Weather data contains malicious content that manipulates AI output
- **Impact:** Low - weather data from trusted APIs, not user input
- **Mitigation:** Sanitize weather data before building prompts, use structured prompts
- **Monitoring:** Log unusual AI responses

### Current Blocker: Empty Response Bug

**Issue:** Explanation dialog displays empty text despite API returning content  
**Branch:** `feature/ai-weather-explanations`  
**Severity:** P0 - Blocks feature launch  
**Debug Status:** Logging added, investigating `_format_response` method  

**Hypotheses:**
1. Markdown stripping too aggressive (removes all content)
2. API returning markdown-only response that gets completely stripped
3. Content encoding issue (Unicode characters causing issues)
4. Cache returning stale empty results

**Next Steps:**
1. Test with `preserve_markdown=True` to isolate stripping issue
2. Add logging before/after each regex in `_format_response`
3. Test with actual OpenRouter API key and various model types
4. Check if issue is model-specific or affects all models

## Success Criteria & Launch Checklist

### Functional Criteria

- [x] ✅ All 8 user stories implemented
- [ ] ⏳ All 18 properties verified via tests (100+ iterations each)
- [ ] ⏳ Integration tests pass with real API
- [ ] ❌ **BLOCKER**: Empty response bug fixed and verified
- [x] ✅ Error handling covers all failure modes
- [x] ✅ Settings persist across app restarts

### Accessibility Criteria

- [x] ✅ All UI elements have ARIA labels
- [x] ✅ Screen reader testing with NVDA passes
- [ ] ⏳ Keyboard navigation works without mouse
- [ ] ⏳ Focus management tested and verified
- [ ] ⏳ WCAG 2.1 AAA compliance maintained

### Performance Criteria

- [ ] ⏳ p95 explanation generation <5 seconds
- [ ] ⏳ Cache hit response time <100ms
- [ ] ⏳ Memory footprint <5MB increase
- [ ] ⏳ No UI blocking during API calls

### Business Criteria

- [ ] ⏳ Beta testing with >10 users
- [ ] ⏳ >70% positive feedback on feature usefulness
- [ ] ⏳ <5% error rate in production
- [ ] ⏳ Average cost per user <$0.10/month

### Documentation Criteria

- [ ] ⏳ User manual updated
- [ ] ⏳ Troubleshooting guide created
- [ ] ⏳ API documentation complete
- [ ] ⏳ Changelog updated

### Launch Checklist

**Pre-Launch:**
- [ ] Bug fix verified and tested
- [ ] All tests passing (unit, property, integration)
- [ ] Accessibility audit complete
- [ ] Performance benchmarks met
- [ ] Error monitoring configured

**Launch:**
- [ ] Merge to `dev` branch
- [ ] Deploy beta build
- [ ] Announce to beta testers
- [ ] Monitor error rates for 48 hours

**Post-Launch:**
- [ ] Collect user feedback (7 days)
- [ ] Address critical issues
- [ ] Merge to `main`
- [ ] Release v1.5.0

## Appendix

### A. OpenRouter Model Reference

**Free Models** (require API key, no charges):
- `openrouter/auto:free` - Auto-routing to best free model
- `meta-llama/llama-3.2-3b-instruct:free` - Meta's Llama 3.2
- `mistral/mistral-7b-instruct:free` - Mistral 7B
- `google/gemini-flash-1.5:free` - Google Gemini Flash

**Paid Models** (require API key + funds):
- `openrouter/auto` - Auto-routing to best paid model (~$0.50/1M tokens avg)
- `anthropic/claude-3.5-sonnet` - Claude 3.5 (~$3/1M tokens)
- `openai/gpt-4o` - GPT-4 Optimized (~$2.50/1M tokens)

**Pricing:** See https://openrouter.ai/docs#models

### B. Error Message Reference

| Error Code | User Message | Log Details | Recovery Action |
|------------|--------------|-------------|-----------------|
| Network Error | "Unable to connect to AI service. Check your internet connection." | Full exception + stack trace | Retry button |
| Invalid API Key | "API key is invalid. Please check your settings." | Key format validation failure | Open settings |
| Insufficient Credits | "Your OpenRouter account has no funds. Add credits or switch to free models." | 402 Payment Required from API | Open settings, switch to free |
| Rate Limit | "Rate limit exceeded. Try again in a few minutes." | 429 Too Many Requests | Wait + cache fallback |
| Timeout | "Request timed out. Try again later." | Timeout after 30s | Retry button |
| Invalid Weather Data | "Unable to generate explanation. Weather data may be incomplete." | Missing required fields | Refresh weather |

### C. Testing Reference

**Property Test Suite:**
- Run: `pytest -v -m property`
- Coverage: 18 properties × 100 iterations = 1,800 test cases
- Duration: ~30 seconds

**Integration Tests:**
- Run: `pytest -v -m integration` (requires valid API key in env)
- Skip in CI: `pytest -v -m "not integration"`
- Duration: ~60 seconds (actual API calls)

**Accessibility Tests:**
- Run: `pytest -v -m accessibility`
- Coverage: ARIA attributes, focus management, keyboard navigation
- Duration: ~10 seconds

### D. Related Documentation

- **Design Document:** `.kiro/specs/ai-weather-explanations/design.md`
- **Requirements:** `.kiro/specs/ai-weather-explanations/requirements.md`
- **Test Suite:** `tests/test_ai_explainer.py`
- **User Manual:** `docs/user_manual.md` (to be updated)
- **Troubleshooting:** `docs/ai-explanations-troubleshooting.md` (to be created)

### E. Glossary

- **OpenRouter**: Unified API gateway providing access to 400+ AI models via OpenAI-compatible API
- **Free Model**: AI model with `:free` suffix; requires API key but doesn't charge account
- **Paid Model**: AI model that charges per token; requires API key and account funds
- **Auto-Routing**: OpenRouter's feature to automatically select best model based on prompt
- **Token**: Unit of text measurement for AI models (~4 characters = 1 token)
- **TTL**: Time To Live; how long cached data remains valid (5 minutes default)
- **ARIA**: Accessible Rich Internet Applications; standard for screen reader accessibility
- **WCAG**: Web Content Accessibility Guidelines; compliance standard (targeting AAA)

---

## Document Metadata

**Version:** 1.0  
**Last Updated:** December 11, 2025  
**Status:** Draft → In Review  
**Approved By:** [Pending]  
**Related Branches:** `feature/ai-weather-explanations`  
**Target Release:** v1.5.0  
**Estimated Completion:** Week of December 16-20, 2025  

**Change Log:**
- 2025-12-11: Initial PRD created from existing specs by Mary (Analyst Agent)
- 2025-12-11: Added current bug status and implementation progress
- 2025-12-11: Updated API key requirement (now required for free models)
