import unittest
from unittest.mock import MagicMock, patch

import src.rp_handler as handler


class TestHandlerHelpers(unittest.TestCase):
    @patch("src.rp_handler.session.post")
    def test_get_session_id_success(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"session_id": "abc123"}
        mock_post.return_value = mock_response

        session_id = handler.get_session_id()

        self.assertEqual(session_id, "abc123")
        mock_post.assert_called_once_with(
            f"{handler.SWARMUI_API_URL}/API/GetNewSession",
            json={},
            timeout=30,
        )

    @patch("src.rp_handler.session.post", side_effect=Exception("boom"))
    def test_get_session_id_failure(self, mock_post: MagicMock) -> None:
        session_id = handler.get_session_id()

        self.assertIsNone(session_id)
        mock_post.assert_called_once()

    def test_prepare_text2image_payload_defaults(self) -> None:
        payload = handler.prepare_text2image_payload({}, "session-1")

        self.assertEqual(payload["session_id"], "session-1")
        self.assertEqual(payload["images"], 1)
        raw_input = payload["rawInput"]
        self.assertIn("prompt", raw_input)
        self.assertIn("model", raw_input)

    def test_prepare_text2image_payload_images_validation(self) -> None:
        with self.assertRaises(ValueError):
            handler.prepare_text2image_payload({"images": "many"}, "session-2")


if __name__ == "__main__":
    unittest.main()
