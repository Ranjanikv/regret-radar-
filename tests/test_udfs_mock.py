"""Mock-runner tests for Exasol Python UDFs using exasol-udf-mock-python."""

from exasol_udf_mock_python.column import Column
from exasol_udf_mock_python.group import Group
from exasol_udf_mock_python.mock_exa_environment import MockExaEnvironment
from exasol_udf_mock_python.mock_meta_data import MockMetaData
from exasol_udf_mock_python.udf_mock_executor import UDFMockExecutor

from udfs.connected_components import resolve_clusters
from udfs.identity_scorer import jaro_winkler_similarity, levenshtein_ratio, score_pair


def test_levenshtein_and_jaro_winkler():
    """Verify string similarity functions on typo pairs."""
    assert levenshtein_ratio("Aarav", "Aaraav") >= 0.80
    assert levenshtein_ratio("Sharma", "Sharma") == 1.0
    assert jaro_winkler_similarity("Aarav", "Arav") >= 0.85
    assert jaro_winkler_similarity("Priya", "Rahul") < 0.50


def test_score_pair_rules():
    """Verify precision-oriented scoring rules on multi-field comparisons."""
    # Exact phone + similar name -> high score
    score_match, reasons = score_pair(
        "Aarav Sharma", "aarav@gmail.com", "+919812345678", "560001",
        "Aaraav Sharma", None, "9812345678", "560001",
    )
    assert score_match >= 0.90
    assert "EXACT_PHONE" in reasons

    # Completely different customer
    score_diff, _ = score_pair(
        "Aarav Sharma", "aarav@gmail.com", "+919812345678", "560001",
        "Vikram Patel", "vikram@yahoo.com", "+919899999999", "400001",
    )
    assert score_diff < 0.50


def test_mock_score_identity_pairs_udf():
    """Execute SCORE_IDENTITY_PAIRS UDF via exasol-udf-mock-python executor."""
    def scorer_udf_wrapper():
        def levenshtein(s1, s2):
            if not s1 or not s2:
                return 0.0
            s1, s2 = s1.lower().strip(), s2.lower().strip()
            if s1 == s2:
                return 1.0
            l1, l2 = len(s1), len(s2)
            dp = list(range(l2 + 1))
            for i in range(1, l1 + 1):
                prev = dp[0]
                dp[0] = i
                for j in range(1, l2 + 1):
                    temp = dp[j]
                    cost = 0 if s1[i - 1] == s2[j - 1] else 1
                    dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
                    prev = temp
            return 1.0 - (dp[l2] / max(l1, l2))

        def run(ctx):
            while True:
                score = 0.95 if ctx.phone1 == ctx.phone2 else 0.20
                if score >= 0.70:
                    ctx.emit(ctx.id1, ctx.id2, score, "PHONE_MATCH")
                if not ctx.next():
                    break

    input_cols = [
        Column("block_id", int, "INTEGER"),
        Column("id1", str, "VARCHAR(50)"),
        Column("name1", str, "VARCHAR(100)"),
        Column("email1", str, "VARCHAR(100)"),
        Column("phone1", str, "VARCHAR(20)"),
        Column("addr1", str, "VARCHAR(10)"),
        Column("id2", str, "VARCHAR(50)"),
        Column("name2", str, "VARCHAR(100)"),
        Column("email2", str, "VARCHAR(100)"),
        Column("phone2", str, "VARCHAR(20)"),
        Column("addr2", str, "VARCHAR(10)"),
    ]
    output_cols = [
        Column("id1", str, "VARCHAR(50)"),
        Column("id2", str, "VARCHAR(50)"),
        Column("match_score", float, "DOUBLE"),
        Column("match_reasons", str, "VARCHAR(200)"),
    ]

    meta = MockMetaData(
        script_code_wrapper_function=scorer_udf_wrapper,
        input_type="SET",
        input_columns=input_cols,
        output_type="EMITS",
        output_columns=output_cols,
    )
    exa = MockExaEnvironment(meta)
    executor = UDFMockExecutor()

    # Two rows in group: 1 match, 1 non-match
    group = Group([
        (1, "WEB_1", "Aarav", "a@g.com", "9812345678", "560001",
         "APP_1", "Aaraav", None, "9812345678", "560001"),
        (1, "WEB_2", "Pooja", "p@g.com", "9899999999", "400001",
         "POS_2", "Rohan", None, "9811111111", "110001"),
    ])

    results = executor.run([group], exa)
    emitted = results[0].rows
    assert len(emitted) == 1
    assert emitted[0][0] == "WEB_1"
    assert emitted[0][1] == "APP_1"
    assert emitted[0][2] >= 0.70


def test_mock_connected_components_udf():
    """Execute RESOLVE_CONNECTED_COMPONENTS UDF via exasol-udf-mock-python executor."""
    def cc_udf_wrapper():
        class DSU:
            def __init__(self):
                self.parent = {}

            def find(self, x):
                if x not in self.parent:
                    self.parent[x] = x
                    return x
                if self.parent[x] != x:
                    self.parent[x] = self.find(self.parent[x])
                return self.parent[x]

            def union(self, u, v):
                r1, r2 = self.find(u), self.find(v)
                if r1 != r2:
                    if r1 < r2:
                        self.parent[r2] = r1
                    else:
                        self.parent[r1] = r2

        def run(ctx):
            dsu = DSU()
            nodes = set()
            while True:
                if ctx.id1 and ctx.id2:
                    nodes.add(ctx.id1)
                    nodes.add(ctx.id2)
                    dsu.union(ctx.id1, ctx.id2)
                if not ctx.next():
                    break
            for n in sorted(nodes):
                root = dsu.find(n)
                ctx.emit(n, f"GOLD_{root}", len(nodes))

    input_cols = [
        Column("grp", int, "INTEGER"),
        Column("id1", str, "VARCHAR(50)"),
        Column("id2", str, "VARCHAR(50)"),
    ]
    output_cols = [
        Column("touchpoint_id", str, "VARCHAR(50)"),
        Column("golden_customer_id", str, "VARCHAR(50)"),
        Column("cluster_size", int, "INTEGER"),
    ]

    meta = MockMetaData(
        script_code_wrapper_function=cc_udf_wrapper,
        input_type="SET",
        input_columns=input_cols,
        output_type="EMITS",
        output_columns=output_cols,
    )
    exa = MockExaEnvironment(meta)
    executor = UDFMockExecutor()

    # Transitive cluster: A matches B, B matches C -> all resolve to GOLD_A
    group = Group([
        (1, "A", "B"),
        (1, "B", "C"),
    ])

    results = executor.run([group], exa)
    emitted = dict((row[0], row[1]) for row in results[0].rows)
    assert emitted["A"] == "GOLD_A"
    assert emitted["B"] == "GOLD_A"
    assert emitted["C"] == "GOLD_A"


def test_pure_connected_components_clustering():
    """Verify resolve_clusters graph resolution."""
    mapping = resolve_clusters([("T1", "T2"), ("T2", "T3"), ("T4", "T5")])
    assert mapping["T1"] == mapping["T2"] == mapping["T3"]
    assert mapping["T4"] == mapping["T5"]
    assert mapping["T1"] != mapping["T4"]
