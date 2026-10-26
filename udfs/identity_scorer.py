"""Exasol Python SET-EMITS UDF for scoring candidate customer identity pairs."""

from typing import Tuple


def levenshtein_ratio(s1: str | None, s2: str | None) -> float:
    """Calculate character edit similarity ratio between 0.0 and 1.0."""
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

    distance = dp[len2]
    max_len = max(len1, len2)
    return round(1.0 - (distance / max_len), 4)


def jaro_winkler_similarity(s1: str | None, s2: str | None) -> float:
    """Calculate Jaro-Winkler similarity metric favoring common name prefixes."""
    if not s1 or not s2:
        return 0.0
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    max_dist = max(len1, len2) // 2 - 1
    if max_dist < 0:
        max_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0

    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if not s2_matches[j] and s1[i] == s2[j]:
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    transpositions = 0
    k = 0
    for i in range(len1):
        if s1_matches[i]:
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

    transpositions //= 2
    jaro = (
        (matches / len1) + (matches / len2) + ((matches - transpositions) / matches)
    ) / 3.0

    prefix = 0
    for i in range(min(len1, len2, 4)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break

    return round(jaro + prefix * 0.1 * (1.0 - jaro), 4)


def clean_phone(p: str | None) -> str:
    """Extract standard digits from phone string."""
    if not p:
        return ""
    digits = "".join(ch for ch in str(p) if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def score_pair(
    name1: str | None,
    email1: str | None,
    phone1: str | None,
    addr1: str | None,
    name2: str | None,
    email2: str | None,
    phone2: str | None,
    addr2: str | None,
) -> Tuple[float, str]:
    """Score multidimensional similarity across Name, Email, Phone, and Pincode."""
    reasons = []

    # 1. Phone match
    p1, p2 = clean_phone(phone1), clean_phone(phone2)
    phone_sim = 0.0
    if p1 and p2:
        if p1 == p2:
            phone_sim = 1.0
            reasons.append("EXACT_PHONE")
        elif "XXXX" in str(phone1) or "XXXX" in str(phone2):
            if p1[-4:] == p2[-4:]:
                phone_sim = 0.80
                reasons.append("MASKED_PHONE_MATCH")
        elif levenshtein_ratio(p1, p2) >= 0.90:
            phone_sim = 0.70
            reasons.append("PHONE_1_DIGIT_TYPO")

    # 2. Email match
    email_sim = 0.0
    if email1 and email2:
        e1, e2 = str(email1).lower().strip(), str(email2).lower().strip()
        if e1 == e2:
            email_sim = 1.0
            reasons.append("EXACT_EMAIL")
        else:
            e_ratio = levenshtein_ratio(e1, e2)
            if e_ratio >= 0.85:
                email_sim = e_ratio
                reasons.append("EMAIL_SIMILAR")

    # 3. Name match
    name_sim = 0.0
    if name1 and name2:
        jw = jaro_winkler_similarity(name1, name2)
        lev = levenshtein_ratio(name1, name2)
        name_sim = max(jw, lev)
        if name_sim >= 0.85:
            reasons.append("NAME_SIMILAR")

    # 4. Pincode / address
    addr_sim = 0.0
    if addr1 and addr2 and str(addr1).strip() == str(addr2).strip():
        addr_sim = 1.0
        reasons.append("PINCODE_MATCH")

    # Weighted aggregate score
    # High confidence rules
    if phone_sim == 1.0 and name_sim >= 0.70:
        total_score = 0.95
    elif email_sim == 1.0 and name_sim >= 0.70:
        total_score = 0.95
    else:
        total_score = (
            0.35 * name_sim + 0.35 * phone_sim + 0.20 * email_sim + 0.10 * addr_sim
        )

    return round(total_score, 4), ";".join(reasons)


def run(ctx):
    """Exasol SET-EMITS iterator entry point."""
    while True:
        score, reasons = score_pair(
            ctx.name1,
            ctx.email1,
            ctx.phone1,
            ctx.addr1,
            ctx.name2,
            ctx.email2,
            ctx.phone2,
            ctx.addr2,
        )
        if score >= 0.70:
            ctx.emit(ctx.id1, ctx.id2, score, reasons)

        if not ctx.next():
            break
