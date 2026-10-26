import copy
import unittest
from core.action_contracts import ActionLedger


class ActionContractTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.ledger = ActionLedger(clock=lambda: self.now)
        self.proposal = {"action_id": "a1", "tenant": "t1", "action": "test",
                         "target": "sandbox", "parameters": {"value": 1}}
        self.ledger.propose(self.proposal)

    def approve(self):
        self.ledger.authorize("a1", "trusted-test", "policy-v1", 200)

    def test_requires_authorization(self):
        with self.assertRaises(ValueError):
            self.ledger.begin(self.proposal)

    def test_mutation_is_rejected(self):
        self.approve()
        changed = copy.deepcopy(self.proposal)
        changed["parameters"]["value"] = 2
        with self.assertRaises(ValueError):
            self.ledger.begin(changed)

    def test_expiry_is_rejected(self):
        self.approve()
        self.now = 200
        with self.assertRaises(ValueError):
            self.ledger.begin(self.proposal)

    def test_duplicate_begin_is_rejected(self):
        self.approve()
        self.ledger.begin(self.proposal)
        with self.assertRaises(ValueError):
            self.ledger.begin(self.proposal)

    def test_uncertain_receipt_is_preserved(self):
        self.approve()
        attempt = self.ledger.begin(self.proposal)
        receipt = self.ledger.finish("a1", attempt, "uncertain")
        self.assertEqual(receipt.outcome, "uncertain")
        with self.assertRaises(ValueError):
            self.ledger.begin(self.proposal)

    def test_wrong_attempt_is_rejected(self):
        self.approve()
        self.ledger.begin(self.proposal)
        with self.assertRaises(ValueError):
            self.ledger.finish("a1", "wrong", "completed")

    def test_repeated_finish_is_rejected(self):
        self.approve()
        attempt = self.ledger.begin(self.proposal)
        self.ledger.finish("a1", attempt, "completed")
        with self.assertRaises(ValueError):
            self.ledger.finish("a1", attempt, "failed")

    def test_nonfinite_expiry_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.authorize("a1", "trusted-test", "policy-v1", float("inf"))


if __name__ == "__main__":
    unittest.main()
