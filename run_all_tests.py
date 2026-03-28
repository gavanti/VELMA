#!/usr/bin/env python3
"""
VELMA - Runner principal de tests
Ejecuta toda la suite y reporta resultados consolidados en CLI.

Uso:
    python run_all_tests.py               # Suite completa
    python run_all_tests.py --fast        # Solo unitarios (más rápido)
    python run_all_tests.py --agent-only  # Solo el agente económico
    python run_all_tests.py --coverage    # Con reporte de coverage
"""

import sys
import os
import time
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

PASS_THRESHOLD = 0.75  # 75% de tests deben pasar


# ============================================================
# Helpers
# ============================================================

def _run_pytest(args: list, label: str) -> dict:
    """
    Ejecuta pytest con los args dados y retorna:
    {'passed': int, 'failed': int, 'errors': int, 'duration_s': float, 'exit_code': int}
    """
    print(f"\n{'-'*60}")
    print(f"  {label}")
    print(f"{'-'*60}")

    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + args,
        cwd=str(ROOT),
        capture_output=False,
    )
    duration = time.perf_counter() - t0

    return {
        "label": label,
        "exit_code": result.returncode,
        "duration_s": duration,
        # pytest retorna 0=ok, 1=some failed, 2=interrupted, 5=no tests collected
        "ok": result.returncode in (0, 5),
    }


def _run_agent(db_path: str, verbose: bool) -> dict:
    """Ejecuta el agente económico como subproceso."""
    print(f"\n{'-'*60}")
    print("  AGENTE ECONOMICO BATCH")
    print(f"{'-'*60}")

    args = [
        sys.executable,
        str(ROOT / "tests" / "agent_tester.py"),
        "--create-test-db",
    ]
    if verbose:
        args.append("--verbose")

    t0 = time.perf_counter()
    result = subprocess.run(args, cwd=str(ROOT), capture_output=False)
    duration = time.perf_counter() - t0

    return {
        "label": "Agente Económico",
        "exit_code": result.returncode,
        "duration_s": duration,
        "ok": result.returncode == 0,
    }


# ============================================================
# Checks de entorno
# ============================================================

def check_environment() -> bool:
    """Verifica que las dependencias necesarias están instaladas."""
    print("\n  Verificando entorno...")
    missing = []

    required = ["pytest", "numpy", "flask"]
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"  ❌ Paquetes faltantes: {', '.join(missing)}")
        print(f"     Instalar con: pip install -r requirements-test.txt")
        return False

    print("  [OK] Entorno OK")
    return True


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="VELMA Test Suite Runner")
    parser.add_argument("--fast", action="store_true", help="Solo tests unitarios")
    parser.add_argument("--agent-only", action="store_true", help="Solo agente económico")
    parser.add_argument("--coverage", action="store_true", help="Generar reporte de coverage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--db", default="knowledge.db", help="DB para el agente económico")
    args = parser.parse_args()

    print("=" * 60)
    print("  VELMA - Suite Completa de Tests (Fase 1)")
    print("  Principio: Pensar es caro. Recordar es barato.")
    print("=" * 60)

    # Verificar entorno
    if not check_environment():
        return 1

    suite_results = []
    t_start = time.perf_counter()

    # ── Modo: solo agente ────────────────────────────────────
    if args.agent_only:
        r = _run_agent(args.db, args.verbose)
        suite_results.append(r)

    # ── Modo: solo unitarios (rápido) ────────────────────────
    elif args.fast:
        pytest_args = [
            "tests/unit/",
            "-v" if args.verbose else "-q",
            "--tb=short",
            "--timeout=30",
        ]
        if args.coverage:
            pytest_args += ["--cov=.", "--cov-report=term-missing"]
        r = _run_pytest(pytest_args, "Tests Unitarios")
        suite_results.append(r)

    # ── Modo: suite completa ─────────────────────────────────
    else:
        # 1. Tests unitarios
        unit_args = [
            "tests/unit/",
            "-v" if args.verbose else "-q",
            "--tb=short",
            "--timeout=30",
        ]
        if args.coverage:
            unit_args += ["--cov=.", "--cov-report=term-missing", "--cov-append"]
        suite_results.append(_run_pytest(unit_args, "1/3 — Tests Unitarios"))

        # 2. Tests de integración
        int_args = [
            "tests/integration/",
            "-v" if args.verbose else "-q",
            "--tb=short",
            "--timeout=60",
        ]
        if args.coverage:
            int_args += ["--cov=.", "--cov-report=term-missing", "--cov-append"]
        suite_results.append(_run_pytest(int_args, "2/3 — Tests de Integración"))

        # 3. Agente económico
        suite_results.append(_run_agent(args.db, args.verbose))

    total_duration = time.perf_counter() - t_start

    # ── Reporte final consolidado ────────────────────────────
    print(f"\n{'='*60}")
    print("  RESUMEN FINAL DE LA SUITE")
    print("="*60)

    all_ok = True
    for r in suite_results:
        status = "[PASS]" if r["ok"] else "[FAIL]"
        print(f"  {status}  {r['label']:<35} ({r['duration_s']:.1f}s)")
        if not r["ok"]:
            all_ok = False

    print(f"\n  Tiempo total:   {total_duration:.1f}s")
    print(f"  Resultado:      {'[PASS] SUITE APROBADA' if all_ok else '[FAIL] SUITE FALLIDA'}")
    print(f"{'='*60}\n")

    if not all_ok:
        print("  Pasos para investigar fallos:")
        print("    python run_all_tests.py --fast --verbose   (solo unitarios)")
        print("    python -m pytest tests/integration/test_merge.py -v  (solo merge)")
        print("    python tests/agent_tester.py --verbose     (solo agente)")
        print()

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
