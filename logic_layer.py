import re


VAGUE_TERMS = [
    "optimal",
    "sufficient",
    "adequate",
    "smooth",
    "minimal",
    "maximum possible",
    "low",
    "high",
    "reasonable",
    "fast",
    "approximate",
    "acceptable",
    "good",
    "standard",
]

AERO_UNITS = {
    "m/s",
    "km/h",
    "knot",
    "knots",
    "mach",
    "pa",
    "kpa",
    "mpa",
    "bar",
    "k",
    "°c",
    "c",
    "deg",
    "degc",
    "rad",
    "kg/s",
    "g/s",
    "n",
    "kn",
    "mm",
    "m",
    "%",
    "ft",
    "feet",
    "psi",
}


def analyze_spec_logic(text: str) -> dict:
    """Run deterministic checks for vague language, units, and requirements."""
    text = text or ""
    text_lower = text.lower()

    found_vague = []
    for term in VAGUE_TERMS:
        if re.search(r"\b" + re.escape(term) + r"\b", text_lower):
            found_vague.append(term)

    # Keep the unit token together for common compound units such as m/s and kg/s.
    tokens = re.findall(
        r"(?<![\w.])(\d+(?:\.\d+)?)(?:\s*([a-zA-Z°%]+(?:/[a-zA-Z]+)?))?",
        text_lower,
    )
    missing_unit_numbers = []
    valid_unit_numbers = []
    for number, unit in tokens:
        normalized_unit = unit.strip().lower()
        if not normalized_unit or normalized_unit not in AERO_UNITS:
            missing_unit_numbers.append(number)
        else:
            valid_unit_numbers.append(f"{number} {normalized_unit}")

    has_imperative = bool(
        re.search(r"\b(shall|must|required to)\b", text_lower)
    )
    word_count = max(len(text.split()), 1)
    ambiguity_penalty = min(len(found_vague) * 15, 60)
    unit_penalty = min(len(missing_unit_numbers) * 10, 30)
    imperative_bonus = 0 if has_imperative else 10
    raw_score = ambiguity_penalty + unit_penalty + imperative_bonus
    ambiguity_score = min(max(raw_score, 5), 95)

    return {
        "is_valid_length": word_count >= 25,
        "word_count": word_count,
        "vague_words_found": found_vague,
        "missing_unit_numbers": missing_unit_numbers,
        "valid_unit_numbers": valid_unit_numbers,
        "has_imperative": has_imperative,
        "ambiguity_score": round(ambiguity_score, 1),
    }
