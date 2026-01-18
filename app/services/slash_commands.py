"""
Slash command parser service.

Supported commands:
- /decision <title> [details]
- /feature <title> [details]
- /issue <title> [details]
- /task <title> [details] [/assign @user] [/due YYYY-MM-DD]
- /join #channel
- /leave
- /topic <topic>
- /rename <name>
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.models.artifact import ArtifactType


@dataclass
class ParsedCommand:
    """Parsed slash command result."""
    
    command: str
    is_valid: bool = True
    error: str | None = None
    
    # Common fields
    title: str | None = None
    body: str | None = None
    
    # Task-specific
    assignee: str | None = None
    due_date: date | None = None
    
    # Channel commands
    channel_name: str | None = None
    topic: str | None = None
    
    # Extra parsed data
    extra: dict[str, Any] = field(default_factory=dict)


class SlashCommandParser:
    """Parser for slash commands in messages."""
    
    # Regex patterns
    COMMAND_PATTERN = re.compile(r'^/(\w+)(?:\s+(.*))?$', re.DOTALL)
    ASSIGN_PATTERN = re.compile(r'/assign\s+@?(\w+)', re.IGNORECASE)
    DUE_PATTERN = re.compile(r'/due\s+(\d{4}-\d{2}-\d{2})', re.IGNORECASE)
    CHANNEL_PATTERN = re.compile(r'#(\w+)')
    
    # Artifact commands
    ARTIFACT_COMMANDS = {
        'decision': ArtifactType.DECISION,
        'feature': ArtifactType.FEATURE,
        'issue': ArtifactType.ISSUE,
        'task': ArtifactType.TASK,
    }
    
    # Channel commands
    CHANNEL_COMMANDS = {'join', 'leave', 'topic', 'rename'}
    
    @classmethod
    def is_command(cls, text: str) -> bool:
        """Check if text starts with a slash command."""
        return text.strip().startswith('/')
    
    @classmethod
    def parse(cls, text: str) -> ParsedCommand | None:
        """Parse a slash command from text.
        
        Returns None if text is not a command.
        Returns ParsedCommand with is_valid=False if command is invalid.
        """
        text = text.strip()
        
        if not cls.is_command(text):
            return None
        
        match = cls.COMMAND_PATTERN.match(text)
        if not match:
            return ParsedCommand(command="unknown", is_valid=False, error="Invalid command format")
        
        command = match.group(1).lower()
        args = match.group(2) or ""
        args = args.strip()
        
        # Artifact commands
        if command in cls.ARTIFACT_COMMANDS:
            return cls._parse_artifact_command(command, args)
        
        # Channel commands
        if command in cls.CHANNEL_COMMANDS:
            return cls._parse_channel_command(command, args)
        
        return ParsedCommand(command=command, is_valid=False, error=f"Unknown command: /{command}")
    
    @classmethod
    def _parse_artifact_command(cls, command: str, args: str) -> ParsedCommand:
        """Parse artifact creation commands."""
        if not args:
            return ParsedCommand(
                command=command,
                is_valid=False,
                error=f"/{command} requires a title",
            )
        
        result = ParsedCommand(command=command)
        
        # Extract /assign and /due for tasks
        if command == 'task':
            # Extract assignee
            assign_match = cls.ASSIGN_PATTERN.search(args)
            if assign_match:
                result.assignee = assign_match.group(1)
                args = cls.ASSIGN_PATTERN.sub('', args)
            
            # Extract due date
            due_match = cls.DUE_PATTERN.search(args)
            if due_match:
                try:
                    result.due_date = date.fromisoformat(due_match.group(1))
                except ValueError:
                    result.is_valid = False
                    result.error = f"Invalid date format: {due_match.group(1)}"
                    return result
                args = cls.DUE_PATTERN.sub('', args)
        
        # Clean up args
        args = args.strip()
        
        # Split title and body (first line is title)
        lines = args.split('\n', 1)
        result.title = lines[0].strip()
        
        if len(lines) > 1:
            result.body = lines[1].strip()
        
        if not result.title:
            result.is_valid = False
            result.error = f"/{command} requires a title"
        
        return result
    
    @classmethod
    def _parse_channel_command(cls, command: str, args: str) -> ParsedCommand:
        """Parse channel commands."""
        result = ParsedCommand(command=command)
        
        if command == 'join':
            # Extract channel name
            channel_match = cls.CHANNEL_PATTERN.search(args)
            if channel_match:
                result.channel_name = channel_match.group(1)
            elif args:
                # Allow without # prefix
                result.channel_name = args.strip().lstrip('#')
            else:
                result.is_valid = False
                result.error = "/join requires a channel name"
        
        elif command == 'leave':
            # No args needed
            pass
        
        elif command == 'topic':
            if not args:
                result.is_valid = False
                result.error = "/topic requires a topic text"
            else:
                result.topic = args
        
        elif command == 'rename':
            if not args:
                result.is_valid = False
                result.error = "/rename requires a new name"
            else:
                result.channel_name = args.strip().lstrip('#')
        
        return result
    
    @classmethod
    def get_artifact_type(cls, command: str) -> ArtifactType | None:
        """Get artifact type for a command."""
        return cls.ARTIFACT_COMMANDS.get(command)
    
    @classmethod
    def get_help_text(cls) -> str:
        """Get help text for all commands."""
        return """
**Artifact Commands:**
- `/decision <title>` - Create a decision record
- `/feature <title>` - Create a feature request
- `/issue <title>` - Create an issue
- `/task <title> [/assign @user] [/due YYYY-MM-DD]` - Create a task

**Channel Commands:**
- `/join #channel` - Join a channel
- `/leave` - Leave current channel
- `/topic <text>` - Set channel topic
- `/rename <name>` - Rename channel (admin only)
        """.strip()
