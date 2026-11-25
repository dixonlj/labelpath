from __future__ import annotations

from labelpath.textutil import (
    core_name,
    first_mention_snippet,
    generic_matches_seed,
    normalize_name,
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
