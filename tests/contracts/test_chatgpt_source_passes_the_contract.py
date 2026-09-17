"""The ChatGPT source against the conversation-source contract, CS-1 to CS-7 (research R11).

The suite hands over plain conversations. They are written into a synthesized export on disk and the
real `ChatGPTExportSource` reads them back, so what passes here is the parser, not a pass-through.
The two failure hooks are the parser's own failures too: a dangling parent for the unreadable
conversation, a path that does not exist for the unreachable export.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_memory.ingestion import ConversationSource
from hermes_memory.ingestion.chatgpt import ChatGPTExportSource
from hermes_memory.normalization import Conversation
from tests.contracts import conversations
from tests.contracts.source import ConversationSourceContract
from tests.synthetic import chatgpt_export as synth


class TestChatGPTExportSource(ConversationSourceContract):
    @pytest.fixture(autouse=True)
    def _workspace(self, tmp_path: Path) -> None:
        self.workspace = tmp_path
        self.exports = 0

    def _export(self, records: list[synth.Record]) -> Path:
        self.exports += 1
        return synth.write_directory(self.workspace / f"export-{self.exports}", records)

    def make_source(self, conversations: tuple[Conversation, ...]) -> ConversationSource:
        records = [synth.from_conversation(one) for one in conversations]
        return ChatGPTExportSource(self._export(records))

    def make_source_with_one_unreadable(
        self, conversations: tuple[Conversation, ...]
    ) -> ConversationSource | None:
        records = [synth.from_conversation(one) for one in conversations]
        leaf = records[1]["current_node"]
        records[1]["mapping"][leaf]["parent"] = "a-node-that-does-not-exist"
        return ChatGPTExportSource(self._export(records))

    def make_unreachable_source(self) -> ConversationSource | None:
        return ChatGPTExportSource(self.workspace / "missing.zip")

    def test_no_contract_rule_is_skipped(self) -> None:
        """SC-002: a hook returning None would skip its rule silently; none may."""
        pair = (conversations.conversation("a"), conversations.conversation("b"))

        assert self.make_source_with_one_unreadable(pair) is not None
        assert self.make_unreachable_source() is not None

    def test_the_conversations_survive_the_round_trip(self) -> None:
        """Beyond the suite: what went into the export is what the parser read back."""
        written = (
            conversations.conversation("a"),
            conversations.conversation_using_every_field("rich1"),
        )

        read = tuple(one.conversation for one in self.make_source(written).read())

        assert read[0] == written[0]
        # Two tool calls on one model turn are two call nodes in an export, so they come back as two
        # turns; what must survive is every activity, in order, with its request and result.
        assert [a for m in read[1].messages for a in m.tool_activity] == [
            a for m in written[1].messages for a in m.tool_activity
        ]
        assert read[1].title == written[1].title
        assert read[1].last_activity_at == written[1].last_activity_at
