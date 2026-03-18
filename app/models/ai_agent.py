"""
AI Agent models for workspace and user-level AI assistants.

Supports multiple AI providers (OpenAI/ChatGPT, Anthropic/Claude, Perplexity)
with configurable personas that can be added to conversations.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workspace import Workspace


class AIProvider(str, Enum):
    """Supported AI API providers."""
    OPENAI = "openai"  # ChatGPT
    ANTHROPIC = "anthropic"  # Claude
    PERPLEXITY = "perplexity"  # Perplexity AI


class AIAgentScope(str, Enum):
    """Scope of the AI agent - workspace-wide or user-specific."""
    WORKSPACE = "workspace"
    USER = "user"


class AIAgent(Base, TimestampMixin):
    """
    AI Agent configuration model.
    
    Each agent has a "profile" like a user - name, avatar, persona.
    Can be scoped to a workspace (admin-managed) or a user (personal assistant).
    """
    __tablename__ = "ai_agents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Scope - workspace or user owned
    scope: Mapped[AIAgentScope] = mapped_column(String(20), nullable=False, default=AIAgentScope.USER)
    workspace_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # Profile - like a user profile
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Shown in chat
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Bio/description
    
    # AI Provider configuration
    provider: Mapped[AIProvider] = mapped_column(String(20), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted API key
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "gpt-4", "claude-3-opus", "pplx-70b-online"
    
    # System prompt / persona configuration
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Capabilities - what the agent can do
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Example: {"scan_tasks": true, "scan_decisions": true, "scan_ideas": true, "agentic_workflows": false}
    
    # Settings
    temperature: Mapped[float] = mapped_column(default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(default=4096, nullable=False)
    context_messages: Mapped[int] = mapped_column(default=20, nullable=False)  # How many messages to include as context
    
    # Whether this agent can access workspace messages for context
    can_read_channels: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_read_dms: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_read_notes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_read_artifacts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Default agent for workspace/user
    
    # Usage tracking
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    workspace: Mapped["Workspace | None"] = relationship("Workspace", backref="ai_agents", lazy="joined")
    owner: Mapped["User | None"] = relationship("User", backref="ai_agents", lazy="joined")
    conversations: Mapped[list["AIConversation"]] = relationship(
        "AIConversation", back_populates="agent", lazy="noload", cascade="all, delete-orphan"
    )
    channel_memberships: Mapped[list["AIChannelMembership"]] = relationship(
        "AIChannelMembership", back_populates="agent", lazy="noload", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<AIAgent {self.name} ({self.provider.value})>"
    
    @property
    def is_workspace_agent(self) -> bool:
        """Check if this is a workspace-level agent."""
        return self.scope == AIAgentScope.WORKSPACE
    
    @property
    def is_user_agent(self) -> bool:
        """Check if this is a user-level agent."""
        return self.scope == AIAgentScope.USER
    
    def update_usage(self, tokens: int) -> None:
        """Update usage statistics."""
        self.total_tokens_used += tokens
        self.total_messages += 1
        self.last_used_at = datetime.now(timezone.utc)


class AIConversation(Base, TimestampMixin):
    """
    A conversation thread with an AI agent.
    
    Can be a direct 1:1 chat with the AI, or the AI participating in a channel.
    """
    __tablename__ = "ai_conversations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Optional: link to a channel if AI is participating there
    channel_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # Conversation metadata
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Auto-generated or user-set
    
    # Context - what the AI knows about this conversation
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # Rolling summary
    
    # Status
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    agent: Mapped["AIAgent"] = relationship("AIAgent", back_populates="conversations", lazy="joined")
    user: Mapped["User"] = relationship("User", backref="ai_conversations", lazy="joined")
    channel = relationship("Channel", backref="ai_conversations", lazy="joined")
    messages: Mapped[list["AIMessage"]] = relationship(
        "AIMessage", back_populates="conversation", lazy="noload", 
        order_by="AIMessage.created_at", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<AIConversation {self.id} with agent {self.agent_id}>"


class AIMessage(Base, TimestampMixin):
    """
    A message in an AI conversation.
    
    Stores both user messages and AI responses.
    """
    __tablename__ = "ai_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Who sent this message
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user", "assistant", "system"
    
    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Token usage (for assistant messages)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # If this message references channel messages for context
    referenced_message_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    # Model used (can vary per message if agent config changes)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Relationships
    conversation: Mapped["AIConversation"] = relationship("AIConversation", back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<AIMessage {self.id} ({self.role})>"


class AIChannelMembership(Base, TimestampMixin):
    """
    Tracks which channels an AI agent is a member of.
    
    When an AI is added to a channel, it can respond to @mentions
    or participate based on configuration.
    """
    __tablename__ = "ai_channel_memberships"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    # How the AI participates in this channel
    respond_to_mentions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    respond_to_all: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Respond to every message
    auto_summarize: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Auto-generate summaries
    
    # Relationships
    agent: Mapped["AIAgent"] = relationship("AIAgent", back_populates="channel_memberships")
    channel = relationship("Channel", backref="ai_memberships")
    added_by = relationship("User", lazy="joined")
    
    def __repr__(self) -> str:
        return f"<AIChannelMembership agent={self.agent_id} channel={self.channel_id}>"
