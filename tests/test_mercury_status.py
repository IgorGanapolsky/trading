from scripts.mercury_status import summarize_accounts


class TestSummarizeAccounts:
    def test_masks_account_numbers_to_last4(self):
        payload = {
            "accounts": [
                {
                    "name": "Mercury Checking",
                    "kind": "checking",
                    "status": "active",
                    "currentBalance": 100.0,
                    "availableBalance": 100.0,
                    "accountNumber": "123456787725",
                }
            ]
        }
        summary = summarize_accounts(payload)
        assert summary[0]["account_number_last4"] == "7725"
        assert "123456787725" not in str(summary)

    def test_handles_empty_and_malformed_rows(self):
        assert summarize_accounts({}) == []
        assert summarize_accounts({"accounts": ["not-a-dict", None]}) == []

    def test_missing_account_number_yields_none(self):
        summary = summarize_accounts({"accounts": [{"name": "X", "accountNumber": None}]})
        assert summary[0]["account_number_last4"] is None

    def test_balances_pass_through(self):
        summary = summarize_accounts(
            {"accounts": [{"currentBalance": 12.5, "availableBalance": 10.0}]}
        )
        assert summary[0]["current_balance_usd"] == 12.5
        assert summary[0]["available_balance_usd"] == 10.0
