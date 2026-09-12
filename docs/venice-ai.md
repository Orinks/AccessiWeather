# Venice AI setup

Open Settings, then AI, and choose Venice AI as the provider. Select Get Venice API key to open Venice's account and API settings in your browser. Add your own Venice API key, select Validate Venice key, and save. AccessiWeather does not provide a shared key or buy credits for you.

Venice API requests use prepaid USD API credits from your Venice account. A chat subscription is separate from API usage. Key validation checks access without generating a response; successful validation does not guarantee sufficient credits for every request.

The initial model is `venice-uncensored-1-2`. You may enter another text model ID from the [Venice model list](https://docs.venice.ai/models/overview); the Weather Assistant requires a model with function calling support.

The selected provider applies to weather explanations, forecast product summaries, and the Weather Assistant. Custom system prompts and instructions apply to both providers. AccessiWeather disables Venice's additional default system prompt. Weather questions and relevant weather context are sent to the provider you select.

Switching providers preserves each provider's key and model. OpenRouter remains the default for existing and new installations. A failed Venice request never silently switches to OpenRouter.

Installed copies use the operating system credential store. Portable copies use AccessiWeather's existing encrypted credential bundle workflow. Ordinary settings exports omit API keys.

If a request fails, check the message: add a missing key, correct an invalid key, top up an insufficient balance in your Venice account, wait after a rate limit, or check your connection after a network error. See the [Venice API reference](https://docs.venice.ai/api-reference/endpoint/chat/completions) for current service details.
