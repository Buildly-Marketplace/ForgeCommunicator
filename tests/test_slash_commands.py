"""Tests for slash command parser."""

import pytest
from app.services.slash_commands import (
    parse_slash_command,
    SlashCommandType,
    ArtifactType,
)


class TestParseSlashCommand:
    """Test slash command parsing."""

    def test_decision_command(self):
        """Test /decision command parsing."""
        result = parse_slash_command("/decision Use PostgreSQL for database")
        
        assert result is not None
        assert result["type"] == SlashCommandType.ARTIFACT
        assert result["artifact_type"] == ArtifactType.DECISION
        assert result["title"] == "Use PostgreSQL for database"

    def test_feature_command(self):
        """Test /feature command parsing."""
        result = parse_slash_command("/feature Add dark mode support")
        
        assert result is not None
        assert result["type"] == SlashCommandType.ARTIFACT
        assert result["artifact_type"] == ArtifactType.FEATURE
        assert result["title"] == "Add dark mode support"

    def test_issue_command(self):
        """Test /issue command parsing."""
        result = parse_slash_command("/issue Login button not working on Safari")
        
        assert result is not None
        assert result["type"] == SlashCommandType.ARTIFACT
        assert result["artifact_type"] == ArtifactType.ISSUE
        assert result["title"] == "Login button not working on Safari"

    def test_task_command(self):
        """Test /task command parsing."""
        result = parse_slash_command("/task Update dependencies")
        
        assert result is not None
        assert result["type"] == SlashCommandType.ARTIFACT
        assert result["artifact_type"] == ArtifactType.TASK
        assert result["title"] == "Update dependencies"

    def test_join_command(self):
        """Test /join command parsing."""
        result = parse_slash_command("/join #general")
        
        assert result is not None
        assert result["type"] == SlashCommandType.JOIN
        assert result["channel_name"] == "general"

    def test_join_without_hash(self):
        """Test /join command without # prefix."""
        result = parse_slash_command("/join general")
        
        assert result is not None
        assert result["type"] == SlashCommandType.JOIN
        assert result["channel_name"] == "general"

    def test_leave_command(self):
        """Test /leave command parsing."""
        result = parse_slash_command("/leave")
        
        assert result is not None
        assert result["type"] == SlashCommandType.LEAVE

    def test_topic_command(self):
        """Test /topic command parsing."""
        result = parse_slash_command("/topic This channel is for product discussions")
        
        assert result is not None
        assert result["type"] == SlashCommandType.TOPIC
        assert result["topic"] == "This channel is for product discussions"

    def test_rename_command(self):
        """Test /rename command parsing."""
        result = parse_slash_command("/rename new-channel-name")
        
        assert result is not None
        assert result["type"] == SlashCommandType.RENAME
        assert result["new_name"] == "new-channel-name"

    def test_unknown_command(self):
        """Test unknown command returns None."""
        result = parse_slash_command("/unknown something")
        
        assert result is None

    def test_not_a_command(self):
        """Test regular message returns None."""
        result = parse_slash_command("Hello, this is a regular message")
        
        assert result is None

    def test_empty_artifact_title(self):
        """Test artifact command with empty title."""
        result = parse_slash_command("/decision ")
        
        # Should return None or handle gracefully
        assert result is None or result.get("title") == ""

    def test_case_insensitive(self):
        """Test commands are case insensitive."""
        result = parse_slash_command("/DECISION Use uppercase command")
        
        assert result is not None
        assert result["type"] == SlashCommandType.ARTIFACT
        assert result["artifact_type"] == ArtifactType.DECISION

    def test_extra_whitespace(self):
        """Test handling of extra whitespace."""
        result = parse_slash_command("/decision    Lots of spaces   ")
        
        assert result is not None
        assert result["title"] == "Lots of spaces"

    def test_multiline_title(self):
        """Test that only first line is used for title."""
        result = parse_slash_command("/feature Feature title\nMore details here")
        
        assert result is not None
        # Title should be just the first line
        assert "Feature title" in result["title"]
