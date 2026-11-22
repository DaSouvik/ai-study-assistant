import unittest

from identity import google_owner_id


class IdentityTests(unittest.TestCase):
    def test_owner_id_uses_provider_subject_not_email(self) -> None:
        self.assertEqual(
            google_owner_id(
                {
                    "sub": "google-user-123",
                    "email": "student@example.com",
                }
            ),
            "google:google-user-123",
        )

    def test_missing_or_empty_subject_is_rejected(self) -> None:
        for claims in ({}, {"sub": ""}, {"sub": None}):
            with self.subTest(claims=claims):
                with self.assertRaises(ValueError):
                    google_owner_id(claims)


if __name__ == "__main__":
    unittest.main()
