"""Claude pricing calculator for cost tracking."""

from typing import Dict, Tuple
from enum import Enum


class ClaudeModel(str, Enum):
    """Claude model identifiers."""
    OPUS_4 = "claude-opus-4-20250514"
    SONNET_4_5 = "claude-sonnet-4-5-20250929"
    SONNET_4 = "claude-sonnet-4-20250514"
    HAIKU_4 = "claude-haiku-4-20250228"
    OPUS_3_5 = "claude-opus-3-5-20241022"
    SONNET_3_5 = "claude-3-5-sonnet-20241022"
    HAIKU_3_5 = "claude-3-5-haiku-20241022"


# Pricing in USD per million tokens (as of 2025)
# Format: (input_price, output_price)
CLAUDE_PRICING: Dict[ClaudeModel, Tuple[float, float]] = {
    # Claude 4 series
    ClaudeModel.OPUS_4: (15.00, 75.00),
    ClaudeModel.SONNET_4_5: (3.00, 15.00),
    ClaudeModel.SONNET_4: (3.00, 15.00),
    ClaudeModel.HAIKU_4: (0.80, 4.00),

    # Claude 3.5 series
    ClaudeModel.OPUS_3_5: (15.00, 75.00),
    ClaudeModel.SONNET_3_5: (3.00, 15.00),
    ClaudeModel.HAIKU_3_5: (0.80, 4.00),
}


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: ClaudeModel = ClaudeModel.SONNET_4_5
) -> float:
    """
    Calculate the cost in USD for a given token count.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Claude model identifier

    Returns:
        Cost in USD

    Example:
        >>> calculate_cost(1000, 500, ClaudeModel.SONNET_4_5)
        0.0105
    """
    if model not in CLAUDE_PRICING:
        # Default to Sonnet 4.5 pricing if model unknown
        model = ClaudeModel.SONNET_4_5

    input_price, output_price = CLAUDE_PRICING[model]

    # Calculate cost per million tokens
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price

    return input_cost + output_cost


def estimate_monthly_cost(
    daily_sessions: int,
    avg_input_tokens_per_session: int,
    avg_output_tokens_per_session: int,
    model: ClaudeModel = ClaudeModel.SONNET_4_5
) -> float:
    """
    Estimate monthly cost based on usage patterns.

    Args:
        daily_sessions: Average number of sessions per day
        avg_input_tokens_per_session: Average input tokens per session
        avg_output_tokens_per_session: Average output tokens per session
        model: Claude model identifier

    Returns:
        Estimated monthly cost in USD

    Example:
        >>> estimate_monthly_cost(10, 2000, 1000, ClaudeModel.SONNET_4_5)
        10.5
    """
    session_cost = calculate_cost(
        avg_input_tokens_per_session,
        avg_output_tokens_per_session,
        model
    )

    daily_cost = session_cost * daily_sessions
    monthly_cost = daily_cost * 30  # Approximate 30 days per month

    return monthly_cost


def get_model_pricing(model: ClaudeModel) -> Dict[str, float]:
    """
    Get pricing information for a specific model.

    Args:
        model: Claude model identifier

    Returns:
        Dictionary with input_price_per_mtok and output_price_per_mtok
    """
    input_price, output_price = CLAUDE_PRICING.get(
        model,
        CLAUDE_PRICING[ClaudeModel.SONNET_4_5]
    )

    return {
        "input_price_per_mtok": input_price,
        "output_price_per_mtok": output_price,
        "model": model.value
    }
