# Agent Simulation Script
import os
from pathlib import Path

def agent_logic():
    print("Agent Starting...")
    
    # 1. Read Injected Context
    context_file = Path(".velma_context.md")
    if context_file.exists():
        context = context_file.read_text(encoding="utf-8", errors="replace")
        print(f"Context Read (chars: {len(context)})")
        if "Regla de Ordenamiento Chronos" in context:
            print("Found business rule: Descending Chronological Order.")
    
    # 2. Analyze App Code
    app_file = Path("tests/chronos_app/app.py")
    app_code = app_file.read_text(encoding="utf-8")
    print("Analyzing app.py...")
    
    # 3. Apply Fix based on VELMA Memory
    fixed_code = app_code.replace(
        "return self.events",
        "return sorted(self.events, key=lambda x: x['date'], reverse=True)"
    )
    
    app_file.write_text(fixed_code, encoding="utf-8")
    print("Fix applied to app.py (Implemented reverse=True sorting).")

if __name__ == "__main__":
    agent_logic()
