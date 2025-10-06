import unittest
from unittest.mock import patch, MagicMock

import src.rp_handler as handler


class TestHandlerSession(unittest.TestCase):
    @patch("src.rp_handler.session.post")
    def test_get_session_id_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"session_id": "abc123"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        session_id = handler.get_session_id()

        self.assertEqual(session_id, "abc123")
        mock_post.assert_called_once()

    @patch("src.rp_handler.session.post", side_effect=Exception("boom"))
    def test_get_session_id_failure(self, mock_post):
        session_id = handler.get_session_id()
        self.assertIsNone(session_id)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
