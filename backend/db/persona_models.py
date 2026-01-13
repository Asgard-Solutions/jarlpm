"""
Persona Models for JarlPM
User personas generated from completed Epics
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, DateTime, 
    ForeignKey, Boolean, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from db.database import Base


class Persona(Base):
    """
    User Persona generated from a completed Epic.
    Personas provide actionable user archetypes for development teams.
    """
    __tablename__ = "personas"
    
    persona_id = Column(String, primary_key=True, default=lambda: f"persona_{uuid.uuid4().hex[:12]}")
    epic_id = Column(String, ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Core identity
    name = Column(String(100), nullable=False)
    role = Column(String(200), nullable=False)  # e.g., "Product Manager", "Software Developer"
    
    # Demographics
    age_range = Column(String(50))  # e.g., "25-34", "35-44"
    location = Column(String(200))  # e.g., "Urban, USA", "Remote worker"
    tech_proficiency = Column(String(50))  # e.g., "High", "Medium", "Low"
    
    # Motivations & Pain Points
    goals_and_motivations = Column(JSON)  # List of strings
    pain_points = Column(JSON)  # List of strings
    
    # Behaviors
    key_behaviors = Column(JSON)  # List of strings
    
    # Jobs-to-be-done (added per user request)
    jobs_to_be_done = Column(JSON)  # List of strings
    
    # Product interaction context (added per user request)
    product_interaction_context = Column(Text)  # When/why they touch this product
    
    # Quote
    representative_quote = Column(Text)  # A quote that captures the persona
    
    # Image
    portrait_image_base64 = Column(Text, nullable=True)  # Base64 encoded image
    portrait_prompt = Column(Text, nullable=True)  # Prompt used to generate the image
    
    # Metadata
    source = Column(String(20), default="ai_generated")  # ai_generated | human_modified
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    epic = relationship("Epic", backref="personas")
    user = relationship("User", backref="personas")
    
    def to_dict(self):
        """Convert to dictionary for API response"""
        return {
            "persona_id": self.persona_id,
            "epic_id": self.epic_id,
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role,
            "age_range": self.age_range,
            "location": self.location,
            "tech_proficiency": self.tech_proficiency,
            "goals_and_motivations": self.goals_and_motivations or [],
            "pain_points": self.pain_points or [],
            "key_behaviors": self.key_behaviors or [],
            "jobs_to_be_done": self.jobs_to_be_done or [],
            "product_interaction_context": self.product_interaction_context,
            "representative_quote": self.representative_quote,
            "portrait_image_base64": self.portrait_image_base64,
            "portrait_prompt": self.portrait_prompt,
            "source": self.source,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PersonaGenerationSettings(Base):
    """
    User settings for persona generation.
    Stored per-user to maintain vendor-agnostic approach.
    """
    __tablename__ = "persona_generation_settings"
    
    settings_id = Column(String, primary_key=True, default=lambda: f"pgs_{uuid.uuid4().hex[:12]}")
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Image generation provider
    image_provider = Column(String(50), default="openai")  # openai | gemini
    image_model = Column(String(100), default="gpt-image-1")  # gpt-image-1 | dall-e-3 | nano-banana
    
    # Default persona count
    default_persona_count = Column(Integer, default=3)  # 1-5, default 3
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship
    user = relationship("User", backref="persona_settings")
