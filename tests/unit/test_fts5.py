"""
Tests unitarios: Robustez FTS5 y prevención de SQL injection.
Estos son los tests de mayor riesgo operacional para VELMA:
un query malformado rompe FTS5 y devuelve OperationalError.
"""

import sqlite3
import pytest
from tests.conftest import _apply_schema


# ============================================================
# Helpers
# ============================================================

def _fresh_db_with_issues():
    """DB en memoria con un par de issues para buscar."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _apply_schema(conn)
    conn.execute("""
        INSERT INTO issues_log (error, resolution, context, owner)
        VALUES
          ('Connection refused to Supabase on port 5432', 'Add retry backoff', 'src/payments.py:100', 'dev1'),
          ('JWT token expired for user session', 'Implement silent refresh', 'src/auth.py:55', 'dev2'),
          ('Aurio balance returns negative value', 'Add non-negative constraint', 'src/wallet.py:200', 'dev1'),
          ('RLS policy violation on table embajadores', 'Add SELECT policy for embajador role', 'src/db.py:10', 'dev3'),
          ('FTS5 MATCH throws OperationalError for special chars', 'Sanitize query terms', 'search.py:87', 'dev1')
    """)
    conn.commit()
    return conn


def _fts5_search(conn: sqlite3.Connection, query: str):
    """
    Ejecuta búsqueda FTS5 tal como lo hace VELMA actualmente (sin sanitizar).
    Retorna lista de rowids o lanza la excepción si el query rompe FTS5.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rowid, rank
        FROM issues_log_fts
        WHERE issues_log_fts MATCH ?
        ORDER BY rank
        LIMIT 10
    """, (query,))
    return cursor.fetchall()


def _sanitize_fts_query(query: str) -> str:
    """
    Sanitización propuesta para VELMA:
    envuelve cada término en comillas dobles para que FTS5
    los trate como frases literales, no como operadores.
    """
    terms = query.strip().split()
    return " ".join(f'"{term}"' for term in terms) if terms else '""'


def _fts5_search_safe(conn: sqlite3.Connection, query: str):
    """Búsqueda FTS5 con sanitización aplicada."""
    safe_query = _sanitize_fts_query(query)
    return _fts5_search(conn, safe_query)


# ============================================================
# Tests: queries normales deben funcionar
# ============================================================

class TestFTS5NormalQueries:
    def test_simple_word_finds_result(self):
        conn = _fresh_db_with_issues()
        results = _fts5_search(conn, "Supabase")
        assert len(results) > 0

    def test_multiword_query(self):
        conn = _fresh_db_with_issues()
        results = _fts5_search(conn, "JWT token")
        assert len(results) > 0

    def test_partial_word_with_wildcard(self):
        """FTS5 soporta prefijos con *."""
        conn = _fresh_db_with_issues()
        results = _fts5_search(conn, "Supabase*")
        assert len(results) > 0

    def test_phrase_search(self):
        """Comillas dobles hacen búsqueda de frase exacta."""
        conn = _fresh_db_with_issues()
        results = _fts5_search(conn, '"Connection refused"')
        assert len(results) > 0

    def test_empty_results_no_crash(self):
        """Query que no matchea nada → lista vacía, sin error."""
        conn = _fresh_db_with_issues()
        results = _fts5_search(conn, "xyznonexistentterm")
        assert results == []

    def test_rank_ordering(self):
        """Los resultados deben venir ordenados por rank (desc relevancia)."""
        conn = _fresh_db_with_issues()
        results = _fts5_search(conn, "policy")
        if len(results) > 1:
            ranks = [r["rank"] for r in results]
            # FTS5 rank es negativo: más cercano a 0 = más relevante
            assert ranks == sorted(ranks)


# ============================================================
# Tests: queries con caracteres especiales
# ============================================================

class TestFTS5SpecialCharacters:
    """
    FTS5 MATCH tiene una sintaxis especial. Estos caracteres pueden
    causar OperationalError si el query no está sanitizado:
      AND, OR, NOT, NEAR, ^, *, (, ), "
    """

    DANGEROUS_QUERIES = [
        "auth AND login",           # AND como operador booleano
        "auth OR login",            # OR
        "error NOT found",          # NOT
        "NEAR(auth login)",         # NEAR
        "auth*",                    # wildcard (válido en FTS5, pero probar)
        '^"first token"',           # anchor al inicio del campo
        "error: timeout",           # dos puntos (puede ser column filter)
        "error:timeout",            # column filter FTS5
        "(auth OR login)",          # paréntesis
        'unclosed phrase',          # sin comillas — FTS5 lo acepta como literal
        "term1 term2 AND",          # AND colgante
        "OR term",                  # OR al inicio
        "NOT term",                 # NOT al inicio
        "",                         # vacío
        "   ",                      # solo espacios
    ]

    @pytest.mark.parametrize("query", DANGEROUS_QUERIES)
    def test_raw_query_behavior(self, query):
        """
        Documenta si FTS5 lanza excepción con el query sin sanitizar.
        El test NO falla si lanza excepción — solo registra el comportamiento.
        Este es el estado ACTUAL de VELMA (sin sanitización).
        """
        conn = _fresh_db_with_issues()
        try:
            results = _fts5_search(conn, query)
            # Si llegó aquí: FTS5 aceptó el query
            assert isinstance(results, list)
        except sqlite3.OperationalError:
            # FTS5 rechazó el query → conocido issue de VELMA
            pytest.xfail(f"FTS5 sin sanitizar falla con query: {repr(query)}")

    @pytest.mark.parametrize("query", DANGEROUS_QUERIES)
    def test_sanitized_query_never_crashes(self, query):
        """
        Con sanitización, NINGÚN query debe lanzar excepción.
        Este test valida la solución propuesta.
        """
        conn = _fresh_db_with_issues()
        try:
            results = _fts5_search_safe(conn, query)
            assert isinstance(results, list)
        except sqlite3.OperationalError as e:
            pytest.fail(f"Query sanitizado sigue fallando: {repr(query)} → {e}")


# ============================================================
# Tests: SQL injection
# ============================================================

class TestSQLInjection:
    """
    VELMA usa parámetros ? en todas sus queries FTS5, lo que previene
    SQL injection clásico. Estos tests verifican que la tabla
    issues_log sigue intacta después de queries maliciosos.
    """

    INJECTION_ATTEMPTS = [
        "'; DROP TABLE issues_log; --",
        "1' OR '1'='1",
        "UNION SELECT * FROM issues_log --",
        "'; INSERT INTO issues_log (error, owner) VALUES ('hacked','attacker'); --",
        "\" OR \"\"=\"",
        "1; DELETE FROM issues_log WHERE 1=1; --",
        "admin'--",
        "' OR 1=1 --",
        "'; UPDATE issues_log SET status='archived' WHERE 1=1; --",
    ]

    @pytest.mark.parametrize("malicious_query", INJECTION_ATTEMPTS)
    def test_table_survives_injection_attempt(self, malicious_query):
        """La tabla issues_log debe tener los mismos registros antes y después."""
        conn = _fresh_db_with_issues()

        # Contar registros antes
        count_before = conn.execute("SELECT COUNT(*) FROM issues_log").fetchone()[0]
        assert count_before == 5

        # Ejecutar el intento de inyección (como FTS5 query parametrizado)
        try:
            _fts5_search(conn, malicious_query)
        except sqlite3.OperationalError:
            pass  # FTS5 puede rechazar la sintaxis — ok

        # Contar registros después
        count_after = conn.execute("SELECT COUNT(*) FROM issues_log").fetchone()[0]
        assert count_after == count_before, (
            f"Posible SQL injection! Registros antes: {count_before}, después: {count_after}"
        )

    @pytest.mark.parametrize("malicious_query", INJECTION_ATTEMPTS)
    def test_status_unchanged_after_injection(self, malicious_query):
        """Los status de los issues no deben cambiar por queries maliciosos."""
        conn = _fresh_db_with_issues()

        statuses_before = set(
            r[0] for r in conn.execute("SELECT status FROM issues_log").fetchall()
        )

        try:
            _fts5_search(conn, malicious_query)
        except sqlite3.OperationalError:
            pass

        statuses_after = set(
            r[0] for r in conn.execute("SELECT status FROM issues_log").fetchall()
        )
        assert statuses_before == statuses_after


# ============================================================
# Tests: sanitize_fts_query (función propuesta)
# ============================================================

class TestSanitizeFTSQuery:
    def test_single_word(self):
        assert _sanitize_fts_query("Supabase") == '"Supabase"'

    def test_two_words(self):
        assert _sanitize_fts_query("auth login") == '"auth" "login"'

    def test_strips_whitespace(self):
        result = _sanitize_fts_query("  auth  ")
        assert result == '"auth"'

    def test_empty_string(self):
        result = _sanitize_fts_query("")
        assert result == '""'

    def test_only_spaces(self):
        result = _sanitize_fts_query("   ")
        assert result == '""'

    def test_special_chars_wrapped(self):
        """AND OR NOT deben quedar dentro de comillas, no como operadores."""
        result = _sanitize_fts_query("auth AND login")
        assert result == '"auth" "AND" "login"'
        # Verificar que FTS5 los acepta como literales
        conn = _fresh_db_with_issues()
        rows = _fts5_search(conn, result)
        assert isinstance(rows, list)

    def test_colon_wrapped(self):
        """error: no debe ser interpretado como column filter."""
        result = _sanitize_fts_query("error: timeout")
        assert '"error:"' in result or '"error"' in result

    def test_idempotent_on_quoted(self):
        """Aplicar sanitización dos veces no debe romper el query."""
        query = "Supabase connection"
        once = _sanitize_fts_query(query)
        twice = _sanitize_fts_query(once)
        conn = _fresh_db_with_issues()
        try:
            _fts5_search(conn, twice)
        except sqlite3.OperationalError as e:
            pytest.fail(f"Query doblemente sanitizado falla: {e}")
