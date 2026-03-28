#!/usr/bin/env python3
"""
VELMA - Agente Económico Interactivo (modo batch)

Simula un agente de IA usando VELMA como knowledge base.
Corre escenarios predefinidos, mide precision/recall/latencia
y reporta cuántos tokens habría ahorrado.

Uso:
    python tests/agent_tester.py
    python tests/agent_tester.py --db knowledge.db
    python tests/agent_tester.py --verbose
"""

import sys
import os
import time
import json
import sqlite3
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Agregar raíz al path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from search import KnowledgeSearch
from conftest import _apply_schema
from fixtures.generate_test_data import populate_db

# ============================================================
# Configuración
# ============================================================

MIN_CONFIDENCE = 0.75          # Score mínimo para considerar relevante
PASS_THRESHOLD = 0.75          # 75%: tu criterio de "bueno"
TOKENS_PER_RELEVANT_RESULT = 500  # Tokens estimados ahorrados por resultado relevante
TOKENS_PER_REASONING_FROM_SCRATCH = 2000  # Costo de razonar desde cero


# ============================================================
# Escenarios de testing
# ============================================================

@dataclass
class Scenario:
    """Un escenario de búsqueda con criterios de evaluación."""
    name: str
    query: str
    expected_keywords: List[str]   # Al menos 1 debe aparecer en los resultados
    expected_table: str            # 'issues', 'docs', o 'any'
    expected_chunk_type: Optional[str] = None  # Para docs
    description: str = ""


SCENARIOS: List[Scenario] = [
    # ── Issues: errores de infraestructura ──────────────────
    Scenario(
        name="Supabase connection error",
        query="Connection refused Supabase",
        expected_keywords=["supabase", "connection", "retry", "refused"],
        expected_table="issues",
        description="Un agente buscando cómo resolver error de conexión a Supabase",
    ),
    Scenario(
        name="JWT token expired",
        query="JWT token expired session",
        expected_keywords=["jwt", "token", "refresh", "expired"],
        expected_table="issues",
        description="Agente buscando solución para tokens JWT vencidos",
    ),
    Scenario(
        name="Aurio balance negativo",
        query="Aurio balance negative value calculation",
        expected_keywords=["aurio", "balance", "negative", "constraint"],
        expected_table="issues",
        description="Agente buscando error de balance negativo en Aurios",
    ),
    Scenario(
        name="RLS policy violation",
        query="RLS policy violation embajadores",
        expected_keywords=["rls", "policy", "supabase", "violation"],
        expected_table="issues",
        description="Agente buscando error de políticas RLS en Supabase",
    ),
    Scenario(
        name="FTS5 special chars crash",
        query="FTS5 MATCH OperationalError special characters",
        expected_keywords=["fts5", "match", "sanitiz", "special"],
        expected_table="issues",
        description="Agente buscando solución para crash de FTS5 con caracteres especiales",
    ),
    Scenario(
        name="API timeout",
        query="API call timeout endpoint",
        expected_keywords=["timeout", "api", "circuit", "breaker"],
        expected_table="issues",
        description="Agente buscando solución para timeouts en llamadas a API",
    ),

    # ── Docs: reglas de negocio ──────────────────────────────
    Scenario(
        name="Valor del Aurio",
        query="valor Aurio USD precio",
        expected_keywords=["aurio", "$0.01", "exactamente", "0.01"],
        expected_table="docs",
        expected_chunk_type="constraint",
        description="Agente verificando el valor exacto del Aurio antes de calcular",
    ),
    Scenario(
        name="Mínimo de canje",
        query="mínimo canje Aurios saldo requerido",
        expected_keywords=["1000", "mínimo", "canje", "saldo"],
        expected_table="docs",
        expected_chunk_type="constraint",
        description="Agente verificando cuántos Aurios mínimos necesita un Embajador",
    ),
    Scenario(
        name="Procedimiento de canje",
        query="cómo canjear Aurios endpoint proceso",
        expected_keywords=["canje", "api", "v1", "proceso", "48"],
        expected_table="docs",
        expected_chunk_type="procedure",
        description="Agente buscando los pasos para implementar el canje",
    ),
    Scenario(
        name="Acumulación de Aurios",
        query="acumulación misiones Aurios embajador",
        expected_keywords=["misión", "aurio", "100", "acumula"],
        expected_table="docs",
        expected_chunk_type="rule",
        description="Agente verificando cómo se acumulan los Aurios por misiones",
    ),
    Scenario(
        name="Regla de confianza mínima",
        query="score confianza mínimo knowledge base usar resultado",
        expected_keywords=["0.75", "confianza", "similitud", "razon"],
        expected_table="docs",
        expected_chunk_type="rule",
        description="Agente verificando el umbral mínimo de confianza para usar el KB",
    ),
    Scenario(
        name="Procedimiento para registrar issue",
        query="cómo registrar issue resuelto knowledge base",
        expected_keywords=["issue", "registrar", "outcome", "success", "evidencia"],
        expected_table="docs",
        expected_chunk_type="procedure",
        description="Agente buscando cómo registrar correctamente un error resuelto",
    ),

    # ── Edge cases ───────────────────────────────────────────
    Scenario(
        name="Query multipalabra con typo intencional",
        query="coneccion rehusada Supabase",  # typo: coneccion, rehusada
        expected_keywords=["connection", "supabase", "refused"],
        expected_table="any",
        description="FTS5 no es tolerante a typos — este caso puede retornar vacío (esperado)",
    ),
    Scenario(
        name="Query muy corto",
        query="error",
        expected_keywords=["error"],
        expected_table="any",
        description="Query de una sola palabra genérica — debe retornar resultados",
    ),
    Scenario(
        name="Query en inglés para docs en español",
        query="minimum redemption aurios ambassadors",
        expected_keywords=["aurio", "mínimo", "canje", "embajador"],
        expected_table="docs",
        description="FTS5 es literal, no traduce — esperamos pocos o ningún resultado",
    ),
]


# ============================================================
# Dataclasses de métricas
# ============================================================

@dataclass
class ScenarioResult:
    scenario: Scenario
    results_count: int
    top_score: float
    latency_ms: float
    relevant_found: int        # Resultados que contienen keywords esperadas
    total_returned: int        # Total de resultados retornados
    chunk_type_match: bool     # Si el chunk_type esperado está en resultados
    tokens_saved: int          # Tokens estimados ahorrados
    passed: bool               # Si pasó el criterio del 75%


@dataclass
class AgentMetrics:
    scenarios_run: int = 0
    scenarios_passed: int = 0
    total_relevant_found: int = 0
    total_results_returned: int = 0
    total_tokens_saved: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    results: List[ScenarioResult] = field(default_factory=list)

    @property
    def precision(self) -> float:
        if self.total_results_returned == 0:
            return 0.0
        return self.total_relevant_found / self.total_results_returned

    @property
    def recall_proxy(self) -> float:
        """
        Proxy de recall: % de escenarios donde se encontró al menos 1 resultado relevante.
        No es recall exacto (no tenemos ground truth completo), pero es representativo.
        """
        if self.scenarios_run == 0:
            return 0.0
        return self.scenarios_passed / self.scenarios_run

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall_proxy
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    @property
    def avg_latency_ms(self) -> float:
        return sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lats = sorted(self.latencies_ms)
        idx = int(len(sorted_lats) * 0.95)
        return sorted_lats[min(idx, len(sorted_lats) - 1)]


# ============================================================
# Agente económico
# ============================================================

class EconomicAgent:
    """
    Simula un agente de IA consultando VELMA antes de razonar.
    Mide si VELMA reduce la necesidad de razonar desde cero.
    """

    def __init__(self, db_path: str, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.search = KnowledgeSearch(db_path)
        self.search.connect()
        self.metrics = AgentMetrics()

    def close(self):
        self.search.close()

    def _count_relevant(self, results, expected_keywords: List[str]) -> int:
        """Cuenta resultados que contienen al menos una keyword esperada."""
        count = 0
        for r in results:
            content_lower = (r.title + " " + r.content).lower()
            if any(kw.lower() in content_lower for kw in expected_keywords):
                count += 1
        return count

    def _check_chunk_type(self, results, expected_type: Optional[str]) -> bool:
        if expected_type is None:
            return True
        return any(
            r.metadata.get("chunk_type") == expected_type
            for r in results
        )

    def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        """Ejecuta un escenario individual y retorna métricas."""
        if self.verbose:
            print(f"\n  {'─'*50}")
            print(f"  Escenario: {scenario.name}")
            print(f"  Query:     {scenario.query}")

        # Determinar qué tabla buscar
        t0 = time.perf_counter()
        if scenario.expected_table == "issues":
            results = self.search.search_issues(scenario.query, limit=10)
        elif scenario.expected_table == "docs":
            results = self.search.search_docs(scenario.query, limit=10)
        else:
            all_results = self.search.search_all(scenario.query, limit=10)
            results = all_results["issues"] + all_results["docs"]
        latency_ms = (time.perf_counter() - t0) * 1000

        # Evaluar relevancia
        relevant = self._count_relevant(results, scenario.expected_keywords)
        chunk_ok = self._check_chunk_type(results, scenario.expected_chunk_type)
        top_score = results[0].score if results else 0.0

        # Calcular tokens ahorrados
        if relevant > 0:
            tokens_saved = relevant * TOKENS_PER_RELEVANT_RESULT
        else:
            tokens_saved = 0  # No hubo resultado útil → agente razona desde cero

        # ¿Pasó el test? (al menos 1 resultado relevante → precision local ≥ 75% es ideal,
        # pero como proxy simple: si hay al menos 1 relevante, consideramos que pasa)
        passed = relevant >= 1

        sr = ScenarioResult(
            scenario=scenario,
            results_count=len(results),
            top_score=top_score,
            latency_ms=latency_ms,
            relevant_found=relevant,
            total_returned=len(results),
            chunk_type_match=chunk_ok,
            tokens_saved=tokens_saved,
            passed=passed,
        )

        if self.verbose:
            status = "[OK] PASS" if passed else "[FAIL] FAIL"
            print(f"  Resultados: {len(results)}  |  Relevantes: {relevant}  |  Top score: {top_score:.4f}")
            print(f"  Latencia:   {latency_ms:.2f}ms")
            print(f"  Tokens ahorrados estimados: {tokens_saved}")
            print(f"  Estado: {status}")
            if self.verbose and results:
                for r in results[:3]:
                    print(f"    [{r.score:.3f}] {r.title[:70]}")

        return sr

    def run_all_scenarios(self) -> AgentMetrics:
        """Corre todos los escenarios predefinidos y acumula métricas."""
        print(f"\n{'='*60}")
        print("  VELMA - Agente Económico Batch")
        print(f"  DB: {self.db_path}")
        print(f"  Escenarios: {len(SCENARIOS)}")
        print(f"  Threshold de aprobación: {PASS_THRESHOLD:.0%}")
        print(f"{'='*60}")

        for i, scenario in enumerate(SCENARIOS, 1):
            print(f"\n  [{i:02d}/{len(SCENARIOS)}] {scenario.name}", end="")

            sr = self.run_scenario(scenario)
            self.metrics.results.append(sr)
            self.metrics.scenarios_run += 1
            self.metrics.latencies_ms.append(sr.latency_ms)
            self.metrics.total_results_returned += sr.total_returned
            self.metrics.total_relevant_found += sr.relevant_found
            self.metrics.total_tokens_saved += sr.tokens_saved

            if sr.passed:
                self.metrics.scenarios_passed += 1
                if not self.verbose:
                    print(f"  [OK]  ({sr.relevant_found}/{sr.total_returned} relevantes, {sr.latency_ms:.1f}ms)")
            else:
                if not self.verbose:
                    print(f"  [FAIL]  (0/{sr.total_returned} relevantes, {sr.latency_ms:.1f}ms)")

        return self.metrics

    def print_report(self):
        """Imprime el reporte completo de métricas en CLI."""
        m = self.metrics
        passed = m.scenarios_passed
        total = m.scenarios_run
        overall_pass = (passed / total) >= PASS_THRESHOLD if total > 0 else False

        print(f"\n{'='*60}")
        print("  VELMA - REPORTE FINAL DEL AGENTE ECONÓMICO")
        print(f"{'='*60}")

        SEP = "  " + "-"*40

        print(f"\n  PRECISION / RECALL")
        print(SEP)
        print(f"  Escenarios pasados:  {passed}/{total}  ({passed/total:.1%})")
        print(f"  Precision:           {m.precision:.1%}  (relevantes/retornados)")
        print(f"  Recall proxy:        {m.recall_proxy:.1%}  (escenarios con >=1 relevante)")
        print(f"  F1 score:            {m.f1:.1%}")
        print(f"  Threshold (75%):     {'[OK] ALCANZADO' if overall_pass else '[FAIL] NO ALCANZADO'}")

        print(f"\n  LATENCIA")
        print(SEP)
        print(f"  Promedio:            {m.avg_latency_ms:.2f}ms")
        print(f"  P95:                 {m.p95_latency_ms:.2f}ms")
        print(f"  Min:                 {min(m.latencies_ms):.2f}ms")
        print(f"  Max:                 {max(m.latencies_ms):.2f}ms")

        print(f"\n  EFICIENCIA DE TOKENS")
        print(SEP)
        print(f"  Tokens ahorrados:    ~{m.total_tokens_saved:,}")
        tokens_without_kb = len(SCENARIOS) * TOKENS_PER_REASONING_FROM_SCRATCH
        saving_pct = (m.total_tokens_saved / tokens_without_kb) * 100 if tokens_without_kb else 0
        print(f"  Sin VELMA (estimado): ~{tokens_without_kb:,}")
        print(f"  Ahorro porcentual:   {saving_pct:.1f}%")

        print(f"\n  DETALLE POR ESCENARIO")
        print(SEP)
        for sr in m.results:
            status = "[OK]  " if sr.passed else "[FAIL]"
            ct = f"[{sr.scenario.expected_chunk_type}]" if sr.scenario.expected_chunk_type else ""
            print(f"  {status} {sr.scenario.name:<38} {ct:<14} "
                  f"score={sr.top_score:.3f}  lat={sr.latency_ms:.1f}ms  "
                  f"rel={sr.relevant_found}/{sr.total_returned}")

        print(f"\n  ANALISIS DE FALLOS")
        print(SEP)
        failed = [sr for sr in m.results if not sr.passed]
        if not failed:
            print("  Sin fallos detectados.")
        else:
            for sr in failed:
                print(f"  [FAIL] {sr.scenario.name}")
                print(f"     Query: {sr.scenario.query}")
                print(f"     Keywords esperadas: {sr.scenario.expected_keywords}")
                print(f"     Resultados retornados: {sr.total_returned}")
                if sr.total_returned == 0:
                    print(f"     Causa probable: FTS5 no matchea -> considerar embeddings o typo en datos")
                else:
                    print(f"     Causa probable: Keywords esperadas no estan en top {sr.total_returned} resultados")

        print(f"\n{'='*60}")
        verdict = "APROBADO" if overall_pass else "REPROBADO"
        print(f"  VEREDICTO FINAL: {verdict} ({passed/total:.1%} >= {PASS_THRESHOLD:.0%})")
        print(f"{'='*60}\n")

        return overall_pass


# ============================================================
# Setup de DB de testing
# ============================================================

def setup_test_db(db_path: str) -> str:
    """
    Crea una DB de testing con datos sintéticos si no existe.
    Retorna el path de la DB.
    """
    if Path(db_path).exists():
        return db_path

    print(f"  Creando DB de testing: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _apply_schema(conn)
    stats = populate_db(conn, n_issues=80)
    conn.close()
    print(f"  Insertados: {stats['issues']} issues, {stats['docs']} docs")
    return db_path


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="VELMA - Agente Económico Batch Tester"
    )
    parser.add_argument(
        "--db",
        default="knowledge.db",
        help="Path a la base de datos VELMA (default: knowledge.db)",
    )
    parser.add_argument(
        "--create-test-db",
        action="store_true",
        help="Crear una DB de testing con datos sintéticos",
    )
    parser.add_argument(
        "--test-db-path",
        default="test_velma_agent.db",
        help="Path para la DB de testing (default: test_velma_agent.db)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostrar detalle por escenario",
    )
    args = parser.parse_args()

    # Determinar qué DB usar
    if args.create_test_db:
        db_path = setup_test_db(args.test_db_path)
    else:
        db_path = args.db
        if not Path(db_path).exists():
            print(f"  ⚠️  DB no encontrada: {db_path}")
            print(f"  Creando DB de testing automáticamente...")
            db_path = setup_test_db(args.test_db_path)

    agent = EconomicAgent(db_path=db_path, verbose=args.verbose)
    try:
        agent.run_all_scenarios()
        passed = agent.print_report()
    finally:
        agent.close()

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
