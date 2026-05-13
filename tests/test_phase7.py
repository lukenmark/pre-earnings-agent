#!/usr/bin/env python3
"""
Phase 7 verification. Tests dashboard module imports and data loaders.
Run: python3 tests/test_phase7.py
"""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

SEP = "\n" + "="*60 + "\n"

def test_imports():
    print(SEP + "DASHBOARD MODULE IMPORTS")
    import dashboard.app
    from dashboard.tabs import watchlist_tab, recommendations_tab, checkpoints_tab, feedback_tab, insights_tab
    print("  ✓ All dashboard modules import cleanly")

def test_data_loaders():
    print(SEP + "DATA LOADERS (read from DB)")
    from storage.database import init_db
    init_db()

    from dashboard.tabs.watchlist_tab import load_watchlist_data
    wl = load_watchlist_data()
    print(f"  ✓ load_watchlist_data: {len(wl)} entries")

    from dashboard.tabs.recommendations_tab import load_alerts
    alerts = load_alerts()
    print(f"  ✓ load_alerts: {len(alerts)} alerts")

    from dashboard.tabs.checkpoints_tab import load_all_checkpoints
    cps = load_all_checkpoints()
    print(f"  ✓ load_all_checkpoints: {len(cps)} tickers with checkpoint data")

    from dashboard.tabs.feedback_tab import load_feedback
    fb = load_feedback()
    print(f"  ✓ load_feedback: {len(fb)} feedback entries")

    from dashboard.tabs.insights_tab import load_insights_data
    cp_data, ind_data = load_insights_data()
    print(f"  ✓ load_insights_data: {len(cp_data)} checkpoints, {len(ind_data)} industry snapshots")

def test_streamlit_config():
    print(SEP + "STREAMLIT CONFIG")
    assert os.path.exists(".streamlit/config.toml"), "Missing .streamlit/config.toml"
    with open(".streamlit/config.toml") as f:
        content = f.read()
    assert 'base = "dark"' in content
    assert "headless = true" in content
    print("  ✓ .streamlit/config.toml present with dark theme + headless mode")

def test_run_dashboard_command():
    print(SEP + "run.py DASHBOARD COMMAND")
    import ast
    with open("run.py") as f:
        source = f.read()
    tree = ast.parse(source)
    func_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert "cmd_dashboard" in func_names, "cmd_dashboard not in run.py"
    print("  ✓ cmd_dashboard function present in run.py")

if __name__ == "__main__":
    print("\n=== Phase 7 Dashboard Verification ===\n")
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if os.path.basename(os.getcwd()) == 'tests' else '.')
    for fn in [test_imports, test_data_loaders, test_streamlit_config, test_run_dashboard_command]:
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"✗ {fn.__name__}: {e}")
            traceback.print_exc()
    print("\n=== Done ===")
