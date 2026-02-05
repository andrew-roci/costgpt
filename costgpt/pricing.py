"""Hardcoded pricing for LLM models.

Prices are per 1M tokens in USD.
Last updated: 2025-02
"""

# Format: model_name -> (input_price_per_1m, output_price_per_1m)
PRICING: dict[str, tuple[float, float]] = {
    # Anthropic Claude
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),

    # OpenAI GPT-4
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),

    # OpenAI o1
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1-preview": (15.00, 60.00),

    # Google Gemini
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),

    # Mistral
    "mistral-large": (2.00, 6.00),
    "mistral-small": (0.20, 0.60),
    "codestral": (0.20, 0.60),
}

# Aliases for common model name variations
ALIASES: dict[str, str] = {
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3.5-haiku": "claude-3-5-haiku-20241022",
    "gpt-4o-2024-08-06": "gpt-4o",
    "gpt-4o-2024-05-13": "gpt-4o",
}


def get_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> tuple[float, float, float]:
    """
    Calculate cost for a model call.

    Returns:
        (input_cost, output_cost, total_cost) in USD
    """
    # Check aliases
    model_key = ALIASES.get(model, model)

    # Try exact match, then prefix match
    if model_key not in PRICING:
        for key in PRICING:
            if model_key.startswith(key) or key.startswith(model_key):
                model_key = key
                break

    if model_key not in PRICING:
        # Unknown model, return 0 cost (log warning in production)
        return (0.0, 0.0, 0.0)

    input_price, output_price = PRICING[model_key]

    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost

    return (input_cost, output_cost, total_cost)
