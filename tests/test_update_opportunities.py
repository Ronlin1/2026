import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.update_opportunities import (
    FeedItem,
    Opportunity,
    build_parser,
    clean_title,
    extract_deadline_date,
    format_opportunity_line,
    insert_opportunities,
    opportunity_from_item,
)


README_WITH_JULY = """# Tracker

<details open>
 <summary><h2> JUL :sparkles: </h2></summary>

- [ ] Existing Fellowship https://example.com/existing JUL 20
- [ ]

</details>

## Ambassadorships
- [ ] Existing Ambassador https://example.com/ambassador OPEN
"""


README_WITH_MAY_ONLY = """# Tracker

<details open>
 <summary><h2> MAY :sparkles: </h2></summary>

- [ ] Existing Fellowship https://example.com/existing MAY 30
- [ ]

</details>

## Offers & Grants
- [ ] Existing Grant https://example.com/grant OPEN
"""


README_WITH_AUG_ONLY = """# Tracker

<details open>
 <summary><h2> AUG :sparkles: </h2></summary>

- [ ] Existing Fellowship https://example.com/existing AUG 20

</details>

## Offers & Grants
- [ ] Existing Grant https://example.com/grant OPEN
"""


class OpportunityUpdaterTests(unittest.TestCase):
    def test_extract_deadline_from_common_phrase(self):
        text = "Applications close soon. Deadline: September 18, 2026."

        self.assertEqual(extract_deadline_date(text), date(2026, 9, 18))

    def test_format_opportunity_line_uses_buffered_deadline(self):
        opportunity = Opportunity(
            title="Global AI Fellowship",
            url="https://example.org/apply",
            deadline=date(2026, 8, 14),
            source="fixture",
        )

        self.assertEqual(
            format_opportunity_line(opportunity, buffer_days=3),
            "- [ ] Global AI Fellowship https://example.org/apply AUG 11",
        )

    def test_format_opportunity_line_never_lists_before_today(self):
        opportunity = Opportunity(
            title="Fast Closing Grant",
            url="https://example.org/fast",
            deadline=date(2026, 7, 21),
            source="fixture",
        )

        self.assertEqual(
            format_opportunity_line(opportunity, buffer_days=3, today=date(2026, 7, 19)),
            "- [ ] Fast Closing Grant https://example.org/fast JUL 19",
        )

    def test_default_max_items_is_five(self):
        args = build_parser().parse_args([])

        self.assertEqual(args.max_items, 5)

    def test_clean_title_removes_long_parenthetical_details(self):
        title = (
            "The Global Youth Water Envoys Program 2026 for young emerging leaders "
            "((Sponsorship to attend, mentorship and more)"
        )

        self.assertEqual(clean_title(title), "The Global Youth Water Envoys Program 2026")

    def test_clean_title_removes_long_after_year_for_details(self):
        title = (
            "The Association of Commonwealth Universities Global Grants 2026 "
            "for Undergraduate Students to Attend International Events"
        )

        self.assertEqual(clean_title(title), "The Association of Commonwealth Universities Global Grants 2026")

    def test_insert_opportunity_before_empty_placeholder_in_existing_month(self):
        opportunity = Opportunity(
            title="July Climate Grant",
            url="https://example.org/climate",
            deadline=date(2026, 7, 29),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_JULY,
            [opportunity],
            today=date(2026, 7, 19),
            buffer_days=3,
        )

        self.assertEqual(added, [opportunity])
        self.assertIn("- [ ] July Climate Grant https://example.org/climate JUL 26", updated)
        self.assertLess(
            updated.index("- [ ] July Climate Grant"),
            updated.index("- [ ]\n\n</details>"),
        )

    def test_insert_opportunity_creates_missing_month_section_before_static_sections(self):
        opportunity = Opportunity(
            title="August Robotics Hackathon",
            url="https://example.org/robotics",
            deadline=date(2026, 8, 22),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_MAY_ONLY,
            [opportunity],
            today=date(2026, 7, 19),
            buffer_days=3,
        )

        self.assertEqual(added, [opportunity])
        self.assertIn("<summary><h2> AUG :sparkles: </h2></summary>", updated)
        self.assertIn("- [ ] August Robotics Hackathon https://example.org/robotics AUG 19", updated)
        self.assertLess(updated.index("<summary><h2> AUG"), updated.index("## Offers & Grants"))

    def test_insert_missing_earlier_month_before_later_existing_month(self):
        opportunity = Opportunity(
            title="July Climate Grant",
            url="https://example.org/climate",
            deadline=date(2026, 7, 29),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_AUG_ONLY,
            [opportunity],
            today=date(2026, 7, 19),
            buffer_days=3,
        )

        self.assertEqual(added, [opportunity])
        self.assertIn("<summary><h2> JUL :sparkles: </h2></summary>", updated)
        self.assertLess(updated.index("<summary><h2> JUL"), updated.index("<summary><h2> AUG"))

    def test_created_month_section_has_no_trailing_whitespace(self):
        opportunity = Opportunity(
            title="August Robotics Hackathon",
            url="https://example.org/robotics",
            deadline=date(2026, 8, 22),
            source="fixture",
        )
        readme = "# Tracker\n\n## Offers & Grants\n- [ ] Existing Grant https://example.com/grant OPEN\n"

        updated, _ = insert_opportunities(
            readme,
            [opportunity],
            today=date(2026, 7, 19),
            buffer_days=3,
        )
        generated_section = updated.split("## Offers & Grants", 1)[0]

        for line in generated_section.splitlines():
            self.assertEqual(line, line.rstrip())

    def test_insert_opportunity_skips_duplicate_url(self):
        duplicate = Opportunity(
            title="Existing Fellowship",
            url="https://example.com/existing",
            deadline=date(2026, 7, 29),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_JULY,
            [duplicate],
            today=date(2026, 7, 19),
            buffer_days=3,
        )

        self.assertEqual(updated, README_WITH_JULY)
        self.assertEqual(added, [])

    def test_insert_opportunity_uses_future_real_deadline_even_if_buffer_is_past(self):
        opportunity = Opportunity(
            title="Fast Closing Grant",
            url="https://example.org/fast",
            deadline=date(2026, 7, 21),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_JULY,
            [opportunity],
            today=date(2026, 7, 19),
            buffer_days=3,
        )

        self.assertEqual(added, [opportunity])
        self.assertIn("- [ ] Fast Closing Grant https://example.org/fast JUL 19", updated)

    def test_insert_opportunity_skips_deadline_today_or_earlier(self):
        today_deadline = Opportunity(
            title="Deadline Today Grant",
            url="https://example.org/today",
            deadline=date(2026, 7, 19),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_JULY,
            [today_deadline],
            today=date(2026, 7, 19),
            buffer_days=3,
        )

        self.assertEqual(updated, README_WITH_JULY)
        self.assertEqual(added, [])

    def test_insert_opportunities_keeps_scanning_after_duplicate_until_limit(self):
        duplicate = Opportunity(
            title="Existing Fellowship",
            url="https://example.com/existing",
            deadline=date(2026, 7, 29),
            source="fixture",
        )
        first_new = Opportunity(
            title="Open Source Residency",
            url="https://example.org/residency",
            deadline=date(2026, 7, 30),
            source="fixture",
        )
        second_new = Opportunity(
            title="Global Builders Grant",
            url="https://example.org/builders",
            deadline=date(2026, 8, 9),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_JULY,
            [duplicate, first_new, second_new],
            today=date(2026, 7, 19),
            buffer_days=3,
            max_items=2,
        )

        self.assertEqual(added, [first_new, second_new])
        self.assertIn("- [ ] Open Source Residency https://example.org/residency JUL 27", updated)
        self.assertIn("- [ ] Global Builders Grant https://example.org/builders AUG 6", updated)

    def test_insert_opportunities_skips_near_duplicate_titles_from_different_sources(self):
        first = Opportunity(
            title="Association of Commonwealth Universities Global Grants 2026",
            url="https://example.org/acu-global-grants",
            deadline=date(2026, 8, 25),
            source="fixture",
        )
        near_duplicate = Opportunity(
            title=(
                "The Association of Commonwealth Universities Global Grants 2026 "
                "for Undergraduate Students to Attend International Events"
            ),
            url="https://example.net/acu-global-grants-2026",
            deadline=date(2026, 8, 25),
            source="fixture",
        )

        updated, added = insert_opportunities(
            README_WITH_JULY,
            [first, near_duplicate],
            today=date(2026, 7, 19),
            buffer_days=3,
            max_items=5,
        )

        self.assertEqual(added, [first])
        self.assertEqual(updated.count("Commonwealth Universities Global Grants 2026"), 1)

    def test_opportunity_from_item_skips_stale_title_year(self):
        item = FeedItem(
            title="Media Fellowship Program 2025",
            url="https://example.org/media-fellowship-2026/",
            summary="Deadline: August 1, 2026.",
            source="fixture",
        )

        self.assertIsNone(
            opportunity_from_item(item, today=date(2026, 7, 19), page_fetch_allowed=False)
        )


if __name__ == "__main__":
    unittest.main()
