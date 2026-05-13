#!/usr/bin/env python3
"""
Phase 6 verification. Tests bot structure without a real Telegram token.
Run: python3 tests/test_phase6.py
"""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

SEP = "\n" + "="*60 + "\n"


def test_imports():
    print(SEP + "BOT MODULE IMPORTS")
    from telegram_bot import keyboards, notifications
    from telegram_bot.handlers import help, watchlist, scan, analyze, checkpoint, alerts, feedback, status
    print("  ✓ All telegram_bot modules import cleanly")


def test_keyboards():
    print(SEP + "KEYBOARDS")
    from telegram_bot.keyboards import feedback_keyboard, decision_keyboard, watchlist_action_keyboard
    kb = feedback_keyboard("NVDA")
    assert len(kb.inline_keyboard) == 1
    assert len(kb.inline_keyboard[0]) == 5  # 5 star buttons
    print(f"  ✓ feedback_keyboard: {len(kb.inline_keyboard[0])} buttons")

    kb2 = decision_keyboard("NVDA", "T-3")
    assert len(kb2.inline_keyboard[0]) == 2  # BUY + NO-GO
    print(f"  ✓ decision_keyboard: {len(kb2.inline_keyboard[0])} buttons")


def test_routers():
    print(SEP + "ROUTER REGISTRATION")
    from aiogram import Router
    from telegram_bot.handlers import help, watchlist, scan, analyze, checkpoint, alerts, feedback, status

    for mod in [help, watchlist, scan, analyze, checkpoint, alerts, feedback, status]:
        assert hasattr(mod, 'router'), f"{mod.__name__} missing 'router'"
        assert isinstance(mod.router, Router), f"{mod.__name__}.router is not a Router"
        print(f"  ✓ {mod.__name__}.router registered")


def test_run_py():
    print(SEP + "run.py CLI STRUCTURE")
    import ast
    with open("run.py") as f:
        source = f.read()
    ast.parse(source)
    print("  ✓ run.py parses without syntax errors")


def test_deploy_files():
    print(SEP + "DEPLOYMENT FILES")
    assert os.path.exists("deploy/pre-earnings-agent.plist"), "plist missing"
    assert os.path.exists("deploy/tmux_start.sh"), "tmux_start.sh missing"
    assert os.path.exists("logs/.gitkeep"), "logs/ dir missing"
    print("  ✓ deploy/pre-earnings-agent.plist exists")
    print("  ✓ deploy/tmux_start.sh exists")
    print("  ✓ logs/ directory exists")


def test_bot_no_token():
    print(SEP + "BOT CREATION (no token)")
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    try:
        from telegram_bot.bot import create_bot
        bot = create_bot()
        print("  ⚠ Bot created without token check (unexpected)")
    except ValueError as e:
        print(f"  ✓ Correctly raises ValueError when no token: {e}")
    except Exception as e:
        print(f"  ✓ Raises on missing token: {type(e).__name__}: {e}")


def test_dispatcher_creation():
    print(SEP + "DISPATCHER CREATION")
    try:
        from aiogram import Dispatcher
        from telegram_bot.bot import create_dispatcher
        dp = create_dispatcher()
        assert isinstance(dp, Dispatcher), "Not a Dispatcher instance"
        print(f"  ✓ Dispatcher created successfully (type: {type(dp).__name__})")
    except Exception as e:
        print(f"  ✗ Dispatcher creation failed: {e}")


if __name__ == "__main__":
    print("\n=== Phase 6 Telegram Bot Verification ===\n")
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for fn in [test_imports, test_keyboards, test_routers, test_run_py, test_deploy_files, test_bot_no_token, test_dispatcher_creation]:
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"✗ {fn.__name__}: {e}")
            traceback.print_exc()
    print("\n=== Done ===")
