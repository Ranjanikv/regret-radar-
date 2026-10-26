-- 03_identity_udfs.sql
-- Exasol Python UDFs for pair similarity scoring and connected component clustering

OPEN SCHEMA REGRET_RADAR;

-- 1. Pair Scoring SET-EMITS Python UDF
CREATE OR REPLACE PYTHON3 SET SCRIPT SCORE_IDENTITY_PAIRS(
    block_id INT,
    id1 VARCHAR(50), name1 VARCHAR(100), email1 VARCHAR(100), phone1 VARCHAR(20), addr1 VARCHAR(10),
    id2 VARCHAR(50), name2 VARCHAR(100), email2 VARCHAR(100), phone2 VARCHAR(20), addr2 VARCHAR(10)
)
EMITS (id1 VARCHAR(50), id2 VARCHAR(50), match_score DOUBLE, match_reasons VARCHAR(200)) AS
def levenshtein_ratio(s1, s2):
    if not s1 or not s2:
        return 0.0
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    dp = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len2 + 1):
            temp = dp[j]
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = temp
    return round(1.0 - (dp[len2] / max(len1, len2)), 4)

def clean_phone(p):
    if not p:
        return ""
    digits = "".join(ch for ch in str(p) if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits

def score_pair(name1, email1, phone1, addr1, name2, email2, phone2, addr2):
    reasons = []
    p1, p2 = clean_phone(phone1), clean_phone(phone2)
    phone_sim = 0.0
    if p1 and p2:
        if p1 == p2 and len(p1) == 10:
            phone_sim = 1.0
            reasons.append("EXACT_PHONE")
        elif len(p1) == 4 or len(p2) == 4:
            if p1[-4:] == p2[-4:]:
                phone_sim = 0.80
                reasons.append("MASKED_PHONE_MATCH")
        elif levenshtein_ratio(p1, p2) >= 0.90:
            phone_sim = 0.70
            reasons.append("PHONE_1_DIGIT_TYPO")

    email_sim = 0.0
    if email1 and email2:
        e1, e2 = str(email1).lower().strip(), str(email2).lower().strip()
        if e1 == e2:
            email_sim = 1.0
            reasons.append("EXACT_EMAIL")
        elif levenshtein_ratio(e1, e2) >= 0.85:
            email_sim = levenshtein_ratio(e1, e2)
            reasons.append("EMAIL_SIMILAR")

    name_sim = 0.0
    if name1 and name2:
        name_sim = levenshtein_ratio(name1, name2)
        if name_sim >= 0.85:
            reasons.append("NAME_SIMILAR")

    addr_sim = 0.0
    if addr1 and addr2 and str(addr1).strip() == str(addr2).strip():
        addr_sim = 1.0
        reasons.append("PINCODE_MATCH")

    # High-confidence deterministic rules favoring precision
    if phone_sim == 1.0 and name_sim >= 0.65:
        score = 0.96
    elif email_sim == 1.0 and name_sim >= 0.65:
        score = 0.96
    elif phone_sim >= 0.80 and addr_sim == 1.0 and name_sim >= 0.60:
        score = 0.88
    else:
        score = 0.35 * name_sim + 0.35 * phone_sim + 0.20 * email_sim + 0.10 * addr_sim

    return round(score, 4), ";".join(reasons)

def run(ctx):
    while True:
        score, reasons = score_pair(
            ctx.name1, ctx.email1, ctx.phone1, ctx.addr1,
            ctx.name2, ctx.email2, ctx.phone2, ctx.addr2,
        )
        if score >= 0.72:
            ctx.emit(ctx.id1, ctx.id2, score, reasons)
        if not ctx.next():
            break
/

-- 2. Connected Components SET-EMITS Python UDF
CREATE OR REPLACE PYTHON3 SET SCRIPT RESOLVE_CONNECTED_COMPONENTS(
    group_id INT, id1 VARCHAR(50), id2 VARCHAR(50)
)
EMITS (touchpoint_id VARCHAR(50), golden_customer_id VARCHAR(50), cluster_size INT) AS
class DisjointSet:
    def __init__(self):
        self.parent = {}
    def find(self, item):
        if item not in self.parent:
            self.parent[item] = item
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]
    def union(self, u, v):
        r1, r2 = self.find(u), self.find(v)
        if r1 != r2:
            if r1 < r2:
                self.parent[r2] = r1
            else:
                self.parent[r1] = r2

def run(ctx):
    dsu = DisjointSet()
    nodes = set()
    while True:
        if ctx.id1 and ctx.id2:
            nodes.add(ctx.id1)
            nodes.add(ctx.id2)
            dsu.union(ctx.id1, ctx.id2)
        if not ctx.next():
            break

    mapping = {}
    counts = {}
    for node in nodes:
        root = dsu.find(node)
        gid = f"GOLD_{root}"
        mapping[node] = gid
        counts[gid] = counts.get(gid, 0) + 1

    for node, gid in mapping.items():
        ctx.emit(node, gid, counts[gid])
/
