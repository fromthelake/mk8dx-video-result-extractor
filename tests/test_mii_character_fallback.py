import unittest

import pandas as pd

from mk8dx_video_result_extractor.extract_text import (
    MII_CHARACTER_METHOD,
    apply_mii_character_fallback,
)


def _row(
    race: int,
    character: str,
    method: str,
    *,
    confidence: float = 75.0,
    raw_best: float | None = None,
    raw_margin: float = 1.0,
    raw_spread: float = 3.0,
    raw_family_count: int = 5,
    player: str = "Player",
    family_best: str = "",
    family_margin: float = 0.0,
) -> dict:
    return {
        "RaceClass": "video_a",
        "RaceIDNumber": race,
        "RacePosition": race,
        "FixPlayerName": player,
        "Character": character,
        "CharacterIndex": 80 if character == "Mii" else 21,
        "CharacterMatchConfidence": confidence,
        "CharacterMatchMethod": method,
        "CharacterMatchRawBest": confidence if raw_best is None else raw_best,
        "CharacterMatchRawMargin": raw_margin,
        "CharacterMatchRawTop5Spread": raw_spread,
        "CharacterMatchRawTop5FamilyCount": raw_family_count,
        "CharacterFamilyBest": family_best,
        "CharacterFamilyMargin": family_margin,
    }


class MiiCharacterFallbackTests(unittest.TestCase):
    def test_stable_closed_set_rows_are_not_group_converted_to_mii(self):
        rows = []
        for race in range(1, 7):
            rows.append(_row(race, "Waluigi", "character_shortlist_alpha_search", raw_best=75.0))
        for race in range(7, 10):
            rows.append(_row(race, "Waluigi", "character_prior_confirm", raw_best=75.0))
        for race in range(10, 13):
            rows.append(_row(race, "Mii", "character_prior_mii_likely", confidence=50.0))

        result = apply_mii_character_fallback(pd.DataFrame(rows))

        self.assertEqual((result["Character"] == "Waluigi").sum(), 12)
        self.assertEqual((result["Character"] == "Mii").sum(), 0)
        self.assertFalse(result["CharacterMatchMethod"].str.contains(MII_CHARACTER_METHOD).any())

    def test_stable_variant_family_rows_are_not_group_converted_to_mii(self):
        rows = []
        for race, character in enumerate(
            ["Blue Yoshi", "Black Yoshi", "Blue Yoshi", "Light-Blue Yoshi"],
            start=1,
        ):
            rows.append(
                _row(
                    race,
                    character,
                    "aligned_alpha_cutout_template_local_search+variant_family_aligned_color_refine",
                    confidence=88.0,
                    raw_best=88.0,
                    player="YoshiPlayer",
                    family_best=character,
                    family_margin=10.0,
                )
            )
        rows.append(
            _row(
                5,
                "Mii",
                "character_prior_mii_likely",
                confidence=50.0,
                player="YoshiPlayer",
            )
        )

        result = apply_mii_character_fallback(pd.DataFrame(rows))

        self.assertEqual((result["Character"] == "Mii").sum(), 0)
        self.assertEqual((result["Character"] != "Mii").sum(), 5)
        self.assertFalse(result["CharacterMatchMethod"].str.contains(MII_CHARACTER_METHOD).any())

    def test_weak_unstable_closed_set_rows_still_convert_to_mii(self):
        characters = ["Mario", "Luigi", "Peach", "Daisy", "Rosalina", "Toad"]
        rows = [
            _row(
                race,
                character,
                "aligned_alpha_cutout_template_local_search",
                confidence=55.0,
                raw_best=55.0,
                raw_margin=0.5,
                raw_spread=2.0,
                raw_family_count=5,
                player="UnstablePlayer",
            )
            for race, character in enumerate(characters, start=1)
        ]
        rows.extend(
            [
                _row(7, "Mii", "open_set_mii_reject", confidence=50.0, player="UnstablePlayer"),
                _row(8, "Mii", "character_prior_mii_likely", confidence=50.0, player="UnstablePlayer"),
            ]
        )

        result = apply_mii_character_fallback(pd.DataFrame(rows))

        self.assertEqual((result["Character"] == "Mii").sum(), len(rows))
        self.assertTrue(result["CharacterMatchMethod"].str.contains(MII_CHARACTER_METHOD).any())

    def test_strong_family_rows_survive_when_group_is_otherwise_mii_like(self):
        rows = [
            _row(
                1,
                "Orange Yoshi",
                "aligned_alpha_cutout_template_local_search+variant_family_aligned_color_refine",
                confidence=91.0,
                raw_best=91.0,
                player="SparseFamilyPlayer",
                family_best="Orange Yoshi",
                family_margin=2.5,
            ),
            _row(
                2,
                "Orange Yoshi",
                "aligned_alpha_cutout_template_local_search+variant_family_aligned_color_refine",
                confidence=92.0,
                raw_best=92.0,
                player="SparseFamilyPlayer",
                family_best="Orange Yoshi",
                family_margin=2.5,
            ),
            _row(3, "Mii", "open_set_mii_reject", confidence=50.0, player="SparseFamilyPlayer"),
            _row(4, "Mii", "character_prior_mii_likely", confidence=50.0, player="SparseFamilyPlayer"),
        ]

        result = apply_mii_character_fallback(pd.DataFrame(rows))

        self.assertEqual((result["Character"] == "Orange Yoshi").sum(), 2)
        self.assertEqual((result["Character"] == "Mii").sum(), 2)


if __name__ == "__main__":
    unittest.main()
