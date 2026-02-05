# CostGPT

LLM cost attribution - see spend by user, feature, and model.

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Your App      │      │    CostGPT      │      │   Dashboard     │
│                 │      │                 │      │                 │
│  Claude/GPT ────┼──────┼─► Track costs   │      │  $247.50 today  │
│  API calls      │      │  by user/feature│──────┼─► By model      │
│                 │      │                 │      │  By user        │
└─────────────────┘      └─────────────────┘      │  By feature     │
                                                  └─────────────────┘
```

## Quick Start

```bash
pip install costgpt
```

```python
from costgpt import CostTracker

tracker = CostTracker(api_key="your-api-key")
tracker.instrument_anthropic()  # Auto-track all Anthropic calls

# Or track manually
tracker.track(
    model="claude-sonnet-4-20250514",
    input_tokens=1500,
    output_tokens=800,
    user_id="user_123",
    feature="chat",
)
```

## Features

- **Auto-instrumentation**: Wrap Anthropic and OpenAI SDKs with one line
- **Cost attribution**: Tag calls with user_id and feature for breakdown
- **Real-time dashboard**: See spend by model, user, and feature
- **Hardcoded pricing**: No external API calls, works offline

## Supported Models

### Anthropic
- claude-opus-4-20250514 ($15.00 / $75.00 per 1M tokens)
- claude-sonnet-4-20250514 ($3.00 / $15.00 per 1M tokens)
- claude-3-5-haiku-20241022 ($0.80 / $4.00 per 1M tokens)

### OpenAI
- gpt-4o ($2.50 / $10.00 per 1M tokens)
- gpt-4o-mini ($0.15 / $0.60 per 1M tokens)
- gpt-4-turbo ($10.00 / $30.00 per 1M tokens)
- gpt-3.5-turbo ($0.50 / $1.50 per 1M tokens)
- o1 ($15.00 / $60.00 per 1M tokens)
- o1-mini ($3.00 / $12.00 per 1M tokens)

## API

### Manual Tracking

```python
tracker.track(
    model="claude-sonnet-4-20250514",
    input_tokens=1500,
    output_tokens=800,
    user_id="user_123",      # optional
    feature="chat",          # optional
    duration_ms=1500,        # optional
    metadata={"request_id": "abc"},  # optional
)
```

### Auto-instrumentation

```python
# Anthropic
tracker.instrument_anthropic()

# OpenAI
tracker.instrument_openai()
```

Both sync and async clients are instrumented.

## Self-Hosting

```bash
cd hosted

# Set environment variables
export DATABASE_URL="postgres://user:pass@host:5432/costgpt"
export SESSION_SECRET="your-secret-key"

# Run schema
psql $DATABASE_URL < schema.sql

# Start server
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SESSION_SECRET` | Secret for session cookies |
| `COSTGPT_API_KEY` | API key (SDK, can also pass to constructor) |
| `COSTGPT_API_URL` | API URL (SDK, defaults to https://api.cost-gpt.com) |

## License

MIT
