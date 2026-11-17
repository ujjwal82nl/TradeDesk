"""Number formatting utilities."""


def format_currency(value: float, compact: bool = False) -> str:
    """Format number as Indian currency."""
    if value is None:
        return "₹0"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if compact:
        if abs_val >= 1e7:
            return f"{sign}₹{abs_val/1e7:.2f}Cr"
        elif abs_val >= 1e5:
            return f"{sign}₹{abs_val/1e5:.2f}L"
        elif abs_val >= 1e3:
            return f"{sign}₹{abs_val/1e3:.2f}K"
    return f"{sign}₹{abs_val:,.2f}"


def format_pnl(value: float, percent: float = None) -> str:
    sign = "+" if value >= 0 else ""
    result = f"{sign}₹{value:,.2f}"
    if percent is not None:
        p_sign = "+" if percent >= 0 else ""
        result += f" ({p_sign}{percent:.2f}%)"
    return result
