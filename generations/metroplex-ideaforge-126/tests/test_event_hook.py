"""Tests for event_hook module."""

import pytest
from voicenotify.event_hook import parse_event, process_event
from voicenotify.models import AgentEvent


class TestParseEvent:
    """Tests for parse_event function."""

    def test_valid_completed_event(self):
        """Test parsing valid agent.completed event."""
        line = '{"event":"agent.completed","agent_id":"test1","ts":1730000000}'
        event = parse_event(line)

        assert event is not None
        assert event.event == "agent.completed"
        assert event.agent_id == "test1"
        assert event.ts == 1730000000

    def test_valid_stalled_event(self):
        """Test parsing valid agent.stalled event."""
        line = '{"event":"agent.stalled","agent_id":"test2","ts":1730000001}'
        event = parse_event(line)

        assert event is not None
        assert event.event == "agent.stalled"
        assert event.agent_id == "test2"
        assert event.ts == 1730000001

    def test_valid_need_decision_event(self):
        """Test parsing valid agent.need_decision event."""
        line = '{"event":"agent.need_decision","agent_id":"test3","ts":1730000002}'
        event = parse_event(line)

        assert event is not None
        assert event.event == "agent.need_decision"
        assert event.agent_id == "test3"
        assert event.ts == 1730000002

    def test_malformed_json(self):
        """Test handling of malformed JSON."""
        line = 'bad json'
        event = parse_event(line)

        assert event is None

    def test_invalid_json_structure(self):
        """Test handling of invalid JSON structure (not an object)."""
        line = '["not", "an", "object"]'
        event = parse_event(line)

        assert event is None

    def test_missing_event_field(self):
        """Test handling of missing event field."""
        line = '{"agent_id":"test","ts":1730000000}'
        event = parse_event(line)

        assert event is None

    def test_missing_agent_id_field(self):
        """Test handling of missing agent_id field."""
        line = '{"event":"agent.completed","ts":1730000000}'
        event = parse_event(line)

        assert event is None

    def test_missing_ts_field(self):
        """Test handling of missing ts field."""
        line = '{"event":"agent.completed","agent_id":"test"}'
        event = parse_event(line)

        assert event is None

    def test_invalid_event_type(self):
        """Test handling of invalid event type."""
        line = '{"event":"agent.invalid","agent_id":"test","ts":1730000000}'
        event = parse_event(line)

        assert event is None

    def test_invalid_agent_id_type(self):
        """Test handling of invalid agent_id type."""
        line = '{"event":"agent.completed","agent_id":123,"ts":1730000000}'
        event = parse_event(line)

        assert event is None

    def test_invalid_ts_type(self):
        """Test handling of invalid ts type."""
        line = '{"event":"agent.completed","agent_id":"test","ts":"not_a_number"}'
        event = parse_event(line)

        assert event is None

    def test_negative_ts(self):
        """Test handling of negative timestamp."""
        line = '{"event":"agent.completed","agent_id":"test","ts":-1}'
        event = parse_event(line)

        assert event is None

    def test_empty_agent_id(self):
        """Test handling of empty agent_id."""
        line = '{"event":"agent.completed","agent_id":"","ts":1730000000}'
        event = parse_event(line)

        assert event is None


class TestProcessEvent:
    """Tests for process_event function."""

    def test_process_completed_event(self):
        """Test processing completed event."""
        event = AgentEvent(
            event="agent.completed",
            agent_id="test1",
            ts=1730000000
        )
        event_type = process_event(event)

        assert event_type == "completed"

    def test_process_stalled_event(self):
        """Test processing stalled event."""
        event = AgentEvent(
            event="agent.stalled",
            agent_id="test2",
            ts=1730000001
        )
        event_type = process_event(event)

        assert event_type == "stalled"

    def test_process_need_decision_event(self):
        """Test processing need_decision event."""
        event = AgentEvent(
            event="agent.need_decision",
            agent_id="test3",
            ts=1730000002
        )
        event_type = process_event(event)

        assert event_type == "need_decision"
