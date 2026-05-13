from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def feedback_keyboard(ticker: str) -> InlineKeyboardMarkup:
    """5-star inline rating keyboard for /feedback"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐", callback_data=f"fb:{ticker}:1"),
        InlineKeyboardButton(text="⭐⭐", callback_data=f"fb:{ticker}:2"),
        InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"fb:{ticker}:3"),
        InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"fb:{ticker}:4"),
        InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"fb:{ticker}:5"),
    ]])


def decision_keyboard(ticker: str, checkpoint: str) -> InlineKeyboardMarkup:
    """Human-in-the-loop BUY/NO-GO confirmation for T-3 alerts"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ CONFIRM BUY", callback_data=f"confirm:{ticker}:{checkpoint}:BUY"),
        InlineKeyboardButton(text="❌ OVERRIDE NO-GO", callback_data=f"confirm:{ticker}:{checkpoint}:NO_GO"),
    ]])


def watchlist_action_keyboard(ticker: str) -> InlineKeyboardMarkup:
    """Quick actions for a watchlist ticker"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📊 Analyze", callback_data=f"action:{ticker}:analyze"),
        InlineKeyboardButton(text="📋 Checkpoint", callback_data=f"action:{ticker}:checkpoint"),
        InlineKeyboardButton(text="💬 Feedback", callback_data=f"action:{ticker}:feedback"),
    ]])
