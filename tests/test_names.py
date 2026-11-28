from __future__ import annotations

from labelpath.textutil import (
    clip_text,
    core_name,
    first_mention_snippet,
    generic_matches_seed,
    normalize_name,
    snippet_around,
)


def test_warfarin_matches_sodium_salt():
    assert generic_matches_seed("WARFARIN SODIUM", "warfarin")
    assert core_name("WARFARIN SODIUM") == "warfarin"


def test_combination_product_is_not_the_single_component():
    assert not generic_matches_seed(
        "AMOXICILLIN AND CLAVULANATE POTASSIUM", "amoxicillin"
    )
    assert generic_matches_seed(
        "AMOXICILLIN AND CLAVULANATE POTASSIUM",
        "amoxicillin and clavulanate potassium",
    )


def test_word_boundary_match_and_snippet():
    text = "Avoid concomitant use of warfarin with aspirin because of bleeding risk."
    snippet = first_mention_snippet(text, "aspirin")
    assert snippet is not None
    assert "aspirin" in snippet.lower()
    # "iron" as a bare word should be findable, but "iron deficiency" must not
    # count as a mention of "iron sucrose".
    assert first_mention_snippet("treated for iron deficiency anemia", "iron sucrose") is None


def test_normalize_biosimilar_suffix():
    assert normalize_name("epoetin alfa-epbx") == "epoetin alfa"


def test_common_salt_and_ester_forms_match_seed():
    assert generic_matches_seed("EDOXABAN TOSYLATE", "edoxaban")
    assert generic_matches_seed("FOSFOMYCIN TROMETHAMINE", "fosfomycin")
    assert generic_matches_seed("OLMESARTAN MEDOXOMIL", "olmesartan")
    assert generic_matches_seed("FLUTICASONE PROPIONATE", "fluticasone")
    assert generic_matches_seed("TRIAMCINOLONE ACETONIDE", "triamcinolone")
    assert generic_matches_seed("SODIUM FERRIC GLUCONATE COMPLEX", "sodium ferric gluconate")
    # Combination products must still not match a single-ingredient seed.
    assert not generic_matches_seed("AMLODIPINE AND OLMESARTAN MEDOXOMIL", "olmesartan")
    assert not generic_matches_seed("ALENDRONATE SODIUM AND CHOLECALCIFEROL", "cholecalciferol")


def test_longer_condition_phrase_wins_overlap():
    from labelpath.textutil import nonoverlapping_phrase_hits
    text = "Malignant hypertension is listed as a contraindication."
    hits = dict(nonoverlapping_phrase_hits(text, ["hypertension", "malignant hypertension"]))
    assert "malignant hypertension" in hits
    assert "hypertension" not in hits


def test_snippet_around_snaps_to_word_boundaries():
    text = "alpha beta midwordgamma delta epsilon zeta"
    start = text.index("midwordgamma")
    end = start + len("midwordgamma")
    # Radius 8 starts inside "beta" ("ta midw...") and ends inside "delta" ("...mma del").
    snippet = snippet_around(text, start, end, radius=8)
    assert "midwordgamma" in snippet
    assert not snippet.startswith("...ta ")
    assert not snippet.endswith("del...")
    body = snippet
    if body.startswith("..."):
        body = body[3:]
    if body.endswith("..."):
        body = body[:-3]
    words = text.split()
    tokens = body.split()
    assert tokens
    assert tokens[0] in words
    assert tokens[-1] in words


def test_clip_text_snaps_to_word_boundary():
    text = "one two three four five six"
    clipped = clip_text(text, 12)
    assert clipped.endswith("...")
    assert " " not in clipped[:-3] or not clipped[:-3].endswith("t")
    assert clipped == "one two..."
    assert clip_text("short text", 40) == "short text"
