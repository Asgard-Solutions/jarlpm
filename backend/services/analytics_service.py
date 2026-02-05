"""
Analytics Service for JarlPM
Provides observability for AI generation quality tracking

Features:
- Log generation attempts with full context
- Track token usage and costs
- Monitor parse/validation success rates
- Track user edits after generation
- Aggregate metrics for prompt optimization
"""
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.analytics_models import InitiativeGenerationLog, InitiativeEditLog

logger = logging.getLogger(__name__)

# Prompt version - increment when prompts change significantly
CURRENT_PROMPT_VERSION = "v1.1"

# Token pricing (approximate, per 1K tokens)
TOKEN_PRICING = {
    "openai": {
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "default": {"input": 0.003, "output": 0.006},
    },
    "anthropic": {
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "default": {"input": 0.003, "output": 0.015},
    },
    "local": {
        "default": {"input": 0.0, "output": 0.0},  # Local models are free
    }
}


@dataclass
class PassMetrics:
    """Metrics for a single pass of the pipeline"""
    tokens_in: int = 0
    tokens_out: int = 0
    retries: int = 0
    duration_ms: int = 0
    success: bool = False
    error: Optional[str] = None


@dataclass
class GenerationMetrics:
    """Full metrics for an initiative generation"""
    user_id: str
    idea_hash: str
    idea_length: int
    product_name_provided: bool = False
    
    # Delivery context
    has_delivery_context: bool = False
    industry: Optional[str] = None
    methodology: Optional[str] = None
    team_size: Optional[int] = None
    
    # Provider info
    llm_provider: str = "openai"
    model_name: Optional[str] = None
    prompt_version: str = CURRENT_PROMPT_VERSION
    
    # Pass metrics
    pass_1: PassMetrics = field(default_factory=PassMetrics)
    pass_2: PassMetrics = field(default_factory=PassMetrics)
    pass_3: PassMetrics = field(default_factory=PassMetrics)
    pass_4: PassMetrics = field(default_factory=PassMetrics)
    
    # Output metrics
    success: bool = False
    error_message: Optional[str] = None
    features_generated: int = 0
    stories_generated: int = 0
    total_points: int = 0
    
    # Quality metrics
    critic_issues_found: int = 0
    critic_auto_fixed: int = 0
    scope_assessment: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def calculate_totals(self) -> Dict[str, Any]:
        """Calculate totals from pass metrics"""
        total_tokens = (
            self.pass_1.tokens_in + self.pass_1.tokens_out +
            self.pass_2.tokens_in + self.pass_2.tokens_out +
            self.pass_3.tokens_in + self.pass_3.tokens_out +
            self.pass_4.tokens_in + self.pass_4.tokens_out
        )
        
        total_retries = (
            self.pass_1.retries + self.pass_2.retries +
            self.pass_3.retries + self.pass_4.retries
        )
        
        duration_ms = 0
        if self.start_time and self.end_time:
            duration_ms = int((self.end_time - self.start_time).total_seconds() * 1000)
        
        # Estimate cost
        cost = self._estimate_cost(total_tokens)
        
        return {
            "total_tokens": total_tokens,
            "total_retries": total_retries,
            "duration_ms": duration_ms,
            "estimated_cost_usd": cost,
        }
    
    def _estimate_cost(self, total_tokens: int) -> float:
        """Estimate cost based on provider and model"""
        provider_pricing = TOKEN_PRICING.get(self.llm_provider, TOKEN_PRICING["openai"])
        
        # Try to find exact model pricing
        model_key = self.model_name.lower() if self.model_name else "default"
        pricing = None
        
        for key, rates in provider_pricing.items():
            if key in model_key:
                pricing = rates
                break
        
        if not pricing:
            pricing = provider_pricing.get("default", {"input": 0.003, "output": 0.006})
        
        # Rough estimate: assume 40% input, 60% output tokens
        input_tokens = total_tokens * 0.4
        output_tokens = total_tokens * 0.6
        
        cost = (input_tokens / 1000 * pricing["input"]) + (output_tokens / 1000 * pricing["output"])
        return round(cost, 6)


class AnalyticsService:
    """Service for tracking and analyzing AI generation quality"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    @staticmethod
    def hash_idea(idea: str) -> str:
        """Create a hash of the idea for dedup analysis"""
        return hashlib.sha256(idea.strip().lower().encode()).hexdigest()
    
    def create_metrics(
        self,
        user_id: str,
        idea: str,
        product_name_provided: bool = False,
        llm_provider: str = "openai",
        model_name: Optional[str] = None,
        delivery_context: Optional[Dict] = None
    ) -> GenerationMetrics:
        """Create a new metrics tracker for a generation"""
        metrics = GenerationMetrics(
            user_id=user_id,
            idea_hash=self.hash_idea(idea),
            idea_length=len(idea),
            product_name_provided=product_name_provided,
            llm_provider=llm_provider,
            model_name=model_name,
            start_time=datetime.now(timezone.utc),
        )
        
        if delivery_context:
            metrics.has_delivery_context = delivery_context.get("has_context", False)
            metrics.industry = delivery_context.get("industry")
            metrics.methodology = delivery_context.get("methodology")
            metrics.team_size = delivery_context.get("team_size")
        
        return metrics
    
    async def save_generation_log(self, metrics: GenerationMetrics) -> str:
        """Save generation metrics to database"""
        metrics.end_time = datetime.now(timezone.utc)
        totals = metrics.calculate_totals()
        
        log = InitiativeGenerationLog(
            user_id=metrics.user_id,
            idea_length=metrics.idea_length,
            idea_hash=metrics.idea_hash,
            product_name_provided=metrics.product_name_provided,
            
            has_delivery_context=metrics.has_delivery_context,
            industry=metrics.industry,
            methodology=metrics.methodology,
            team_size=metrics.team_size,
            
            llm_provider=metrics.llm_provider,
            model_name=metrics.model_name,
            prompt_version=metrics.prompt_version,
            
            pass_1_tokens_in=metrics.pass_1.tokens_in,
            pass_1_tokens_out=metrics.pass_1.tokens_out,
            pass_2_tokens_in=metrics.pass_2.tokens_in,
            pass_2_tokens_out=metrics.pass_2.tokens_out,
            pass_3_tokens_in=metrics.pass_3.tokens_in,
            pass_3_tokens_out=metrics.pass_3.tokens_out,
            pass_4_tokens_in=metrics.pass_4.tokens_in,
            pass_4_tokens_out=metrics.pass_4.tokens_out,
            total_tokens=totals["total_tokens"],
            estimated_cost_usd=totals["estimated_cost_usd"],
            
            pass_1_retries=metrics.pass_1.retries,
            pass_2_retries=metrics.pass_2.retries,
            pass_3_retries=metrics.pass_3.retries,
            pass_4_retries=metrics.pass_4.retries,
            total_retries=totals["total_retries"],
            validation_errors=metrics.validation_errors if metrics.validation_errors else None,
            
            success=metrics.success,
            error_message=metrics.error_message,
            features_generated=metrics.features_generated,
            stories_generated=metrics.stories_generated,
            total_points=metrics.total_points,
            
            critic_issues_found=metrics.critic_issues_found,
            critic_auto_fixed=metrics.critic_auto_fixed,
            scope_assessment=metrics.scope_assessment,
            
            duration_ms=totals["duration_ms"],
            pass_1_duration_ms=metrics.pass_1.duration_ms,
            pass_2_duration_ms=metrics.pass_2.duration_ms,
            pass_3_duration_ms=metrics.pass_3.duration_ms,
            pass_4_duration_ms=metrics.pass_4.duration_ms,
        )
        
        self.session.add(log)
        await self.session.commit()
        
        logger.info(f"Logged generation: success={metrics.success}, tokens={totals['total_tokens']}, cost=${totals['estimated_cost_usd']:.4f}")
        return log.log_id
    
    async def log_edit(
        self,
        user_id: str,
        epic_id: str,
        entity_type: str,
        entity_id: str,
        field_edited: str,
        original_value: Optional[str],
        new_value: Optional[str],
        generation_log_id: Optional[str] = None,
        generation_time: Optional[datetime] = None
    ) -> str:
        """Log a user edit after generation"""
        original_length = len(original_value) if original_value else 0
        edited_length = len(new_value) if new_value else 0
        
        # Classify edit type
        if not original_value and new_value:
            edit_type = "add"
        elif original_value and not new_value:
            edit_type = "remove"
        elif original_length > 0 and edited_length / original_length < 0.3:
            edit_type = "rewrite"
        else:
            edit_type = "modify"
        
        # Calculate change ratio
        change_ratio = edited_length / original_length if original_length > 0 else None
        
        # Calculate time to edit
        time_to_edit = None
        if generation_time:
            time_to_edit = int((datetime.now(timezone.utc) - generation_time).total_seconds())
        
        edit_log = InitiativeEditLog(
            user_id=user_id,
            epic_id=epic_id,
            generation_log_id=generation_log_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_edited=field_edited,
            original_length=original_length,
            edited_length=edited_length,
            change_ratio=change_ratio,
            edit_type=edit_type,
            time_to_edit_seconds=time_to_edit,
        )
        
        self.session.add(edit_log)
        await self.session.commit()
        
        logger.info(f"Logged edit: {entity_type}.{field_edited} ({edit_type})")
        return edit_log.edit_id
    
    async def get_generation_stats(
        self,
        days: int = 30,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregated generation statistics"""
        from_date = datetime.now(timezone.utc) - timedelta(days=days)
        from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Build query
        base_filter = InitiativeGenerationLog.created_at >= from_date
        if user_id:
            base_filter = and_(base_filter, InitiativeGenerationLog.user_id == user_id)
        
        # Total generations
        total_result = await self.session.execute(
            select(func.count(InitiativeGenerationLog.id)).where(base_filter)
        )
        total = total_result.scalar() or 0
        
        # Success rate
        success_result = await self.session.execute(
            select(func.count(InitiativeGenerationLog.id)).where(
                and_(base_filter, InitiativeGenerationLog.success == True)
            )
        )
        successes = success_result.scalar() or 0
        success_rate = (successes / total * 100) if total > 0 else 0
        
        # Average retries
        retries_result = await self.session.execute(
            select(func.avg(InitiativeGenerationLog.total_retries)).where(base_filter)
        )
        avg_retries = retries_result.scalar() or 0
        
        # Total tokens and cost
        tokens_result = await self.session.execute(
            select(
                func.sum(InitiativeGenerationLog.total_tokens),
                func.sum(InitiativeGenerationLog.estimated_cost_usd)
            ).where(base_filter)
        )
        row = tokens_result.fetchone()
        total_tokens = row[0] or 0
        total_cost = row[1] or 0
        
        # Provider breakdown
        provider_result = await self.session.execute(
            select(
                InitiativeGenerationLog.llm_provider,
                func.count(InitiativeGenerationLog.id)
            ).where(base_filter).group_by(InitiativeGenerationLog.llm_provider)
        )
        providers = {row[0]: row[1] for row in provider_result.fetchall()}
        
        # Prompt version breakdown
        version_result = await self.session.execute(
            select(
                InitiativeGenerationLog.prompt_version,
                func.count(InitiativeGenerationLog.id),
                func.avg(func.cast(InitiativeGenerationLog.success, Integer))
            ).where(base_filter).group_by(InitiativeGenerationLog.prompt_version)
        )
        versions = {
            row[0]: {"count": row[1], "success_rate": (row[2] or 0) * 100}
            for row in version_result.fetchall()
        }
        
        return {
            "period_days": days,
            "total_generations": total,
            "success_rate": round(success_rate, 1),
            "avg_retries": round(avg_retries, 2),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 2),
            "providers": providers,
            "prompt_versions": versions,
        }
    
    async def get_edit_patterns(
        self,
        days: int = 30,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get patterns of what users edit most"""
        from_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from_date = from_date.replace(day=from_date.day - days)
        
        base_filter = InitiativeEditLog.created_at >= from_date
        if user_id:
            base_filter = and_(base_filter, InitiativeEditLog.user_id == user_id)
        
        # Most edited fields
        field_result = await self.session.execute(
            select(
                InitiativeEditLog.entity_type,
                InitiativeEditLog.field_edited,
                func.count(InitiativeEditLog.id),
                func.avg(InitiativeEditLog.change_ratio)
            ).where(base_filter)
            .group_by(InitiativeEditLog.entity_type, InitiativeEditLog.field_edited)
            .order_by(func.count(InitiativeEditLog.id).desc())
            .limit(10)
        )
        
        most_edited = [
            {
                "entity_type": row[0],
                "field": row[1],
                "edit_count": row[2],
                "avg_change_ratio": round(row[3], 2) if row[3] else None
            }
            for row in field_result.fetchall()
        ]
        
        # Edit type breakdown
        type_result = await self.session.execute(
            select(
                InitiativeEditLog.edit_type,
                func.count(InitiativeEditLog.id)
            ).where(base_filter).group_by(InitiativeEditLog.edit_type)
        )
        edit_types = {row[0]: row[1] for row in type_result.fetchall()}
        
        # Average time to first edit
        time_result = await self.session.execute(
            select(func.avg(InitiativeEditLog.time_to_edit_seconds)).where(
                and_(base_filter, InitiativeEditLog.time_to_edit_seconds.isnot(None))
            )
        )
        avg_time_to_edit = time_result.scalar()
        
        return {
            "period_days": days,
            "most_edited_fields": most_edited,
            "edit_types": edit_types,
            "avg_time_to_edit_seconds": int(avg_time_to_edit) if avg_time_to_edit else None,
        }
