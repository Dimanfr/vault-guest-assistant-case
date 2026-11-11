import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assistant.pii_mask import mask  # noqa: E402

# All phone numbers here are invalid by design (+49 followed by 0).
BOOKING = {"guest_name": "Alex Example", "phone": "+49 0000 0000105", "email": "alex.example@example.com"}


class KnownValues(unittest.TestCase):
    def test_full_name_any_case(self):
        result = mask("hi, ALEX EXAMPLE here", BOOKING)
        self.assertEqual(result.text, "hi, [name] here")
        self.assertEqual(result.counts["name"], 1)

    def test_name_parts_whole_words_only(self):
        result = mask("Alex wrote. Alexander and Examples are other words.", BOOKING)
        self.assertEqual(result.text, "[name] wrote. Alexander and Examples are other words.")

    def test_known_email_any_case(self):
        result = mask("Mail: ALEX.EXAMPLE@EXAMPLE.COM", BOOKING)
        self.assertEqual(result.text, "Mail: [email]")

    def test_known_phone_in_other_formats(self):
        for written in ["+49 0000 0000105", "0000 0000105", "0049-0000-0000105", "(0000) 000 0105"]:
            with self.subTest(written=written):
                self.assertEqual(mask(f"call {written} please", BOOKING).text, "call [phone] please")

    def test_known_phone_without_prefix(self):
        self.assertEqual(mask("number 49000000000105", BOOKING).text, "number [phone]")


class Patterns(unittest.TestCase):
    def test_unknown_email(self):
        self.assertEqual(mask("or friend@example.org").text, "or [email]")

    def test_unknown_phone(self):
        result = mask("my friend: +49 0000 1234567")
        self.assertEqual(result.text, "my friend: [phone]")
        self.assertEqual(result.counts["phone"], 1)

    def test_long_number(self):
        self.assertEqual(mask("card 123456789012").text, "card [number]")


class LeftAlone(unittest.TestCase):
    def test_dates_times_and_booking_code(self):
        text = "Arriving 14.11.2026 or 2026-11-14 at 13:00, booking HMA-0005, 2 guests."
        result = mask(text, BOOKING)
        self.assertEqual(result.text, text)
        self.assertEqual(result.total, 0)

    def test_short_numbers(self):
        text = "Apartment A-101, space 4, room 12, PIN request"
        self.assertEqual(mask(text).text, text)

    def test_no_booking(self):
        self.assertEqual(mask("Hello").text, "Hello")


class Counts(unittest.TestCase):
    def test_message_five(self):
        text = ("Hi, this is Alex Example, booking HMA-0005. If anything comes up, call me on "
                "0000 0000105 or write to alex.example@example.com. How do I get on the Wi-Fi?")
        result = mask(text, BOOKING)
        self.assertEqual(dict(result.counts), {"name": 1, "phone": 1, "email": 1})
        self.assertNotIn("Alex", result.text)
        self.assertNotIn("0105", result.text)
        self.assertNotIn("@", result.text)


if __name__ == "__main__":
    unittest.main()
