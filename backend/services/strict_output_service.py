"""
Strict Output Service for JarlPM
Ensures LLM outputs are valid, structured, and consistent.

Features:
1. Schema Validation + Auto-Repair - Validates against Pydantic, auto-fixes on failure
2. Quality Mode - Optional 2-pass: generate → critique/fix
3. Guardrail Defaults - Temperature tuning per task type
4. Weak Model Detection - Warns if model struggles with structured output
5. Delivery Context Injection - Every prompt is personalized
"""
import json
import re
import logging
from typing import Optional, Dict, Any, Type, TypeVar, List
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class TaskType(str, Enum):
    """Task types with different guardrail defaults"""
    PRD_GENERATION = "prd"
    DECOMPOSITION = "decomposition"
    PLANNING = "planning"
    CRITIC = "critic"
    ACCEPTANCE_CRITERIA = "ac"
    EXPORT = "export"
    GENERAL = "general"


class QualityMode(str, Enum):
    """Quality mode for AI generation"""
    STANDARD = "standard"  # Single pass
    QUALITY = "quality"    # 2-pass: generate → critique/fix


# Temperature settings per task type
# Higher = more creative, Lower = more deterministic
TASK_TEMPERATURE = {
    TaskType.PRD_GENERATION: 0.8,       # Higher creativity for ideation
    TaskType.DECOMPOSITION: 0.6,        # Balanced for feature breakdown
    TaskType.PLANNING: 0.3,             # Low - must follow constraints
    TaskType.CRITIC: 0.2,               # Very low - analytical
    TaskType.ACCEPTANCE_CRITERIA: 0.2,  # Very low - must be precise
    TaskType.EXPORT: 0.1,               # Lowest - strict format
    TaskType.GENERAL: 0.5,              # Default
}


REPAIR_PROMPT = """The previous output was invalid JSON or didn't match the required schema.

ERRORS FOUND:
{errors}

REQUIRED SCHEMA:
{schema_hint}

Please return ONLY valid JSON matching the schema. No explanations, no markdown, no extra text.
Fix all missing required fields and ensure proper JSON syntax.
"""

QUALITY_CRITIQUE_PROMPT = """Review and improve this output:

{output}

Check for:
1. Completeness - Are all required fields filled with meaningful content?
2. Consistency - Do the parts fit together logically?
3. Specificity - Are descriptions concrete, not vague?
4. Actionability - Can someone act on this information?

Return the IMPROVED version as valid JSON. Keep the same structure, just enhance the content.
If the output is already excellent, return it unchanged.
"""


@dataclass
class ValidationResult:
    """Result of schema validation"""
    valid: bool
    data: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    raw_response: str = ""
    repair_attempts: int = 0


@dataclass
class ModelHealthMetrics:
    """Tracks model performance for weak model detection"""
    total_calls: int = 0
    validation_failures: int = 0
    repair_successes: int = 0
    
    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.validation_failures / self.total_calls
    
    @property
    def needs_warning(self) -> bool:
        # Warn if failure rate > 30% after at least 3 calls
        return self.total_calls >= 3 and self.failure_rate > 0.3


class StrictOutputService:
    """
    Service for ensuring LLM outputs are valid and consistent.
    Wraps LLM calls with schema validation, auto-repair, and quality modes.
    """
    
    def __init__(self):
        # Track model health per user+provider
        self._model_health: Dict[str, ModelHealthMetrics] = {}
    
    def get_temperature(self, task_type: TaskType) -> float:
        """Get the recommended temperature for a task type"""
        return TASK_TEMPERATURE.get(task_type, 0.5)
    
    def _get_model_key(self, user_id: str, provider: str) -> str:
        """Generate a key for tracking model health"""
        return f"{user_id}:{provider}"
    
    def _track_call(self, user_id: str, provider: str, success: bool, repaired: bool = False):
        """Track a call for model health metrics"""
        key = self._get_model_key(user_id, provider)
        if key not in self._model_health:
            self._model_health[key] = ModelHealthMetrics()
        
        metrics = self._model_health[key]
        metrics.total_calls += 1
        if not success:
            metrics.validation_failures += 1
        if repaired:
            metrics.repair_successes += 1
    
    def get_model_warning(self, user_id: str, provider: str) -> Optional[str]:
        """Check if the model needs a warning"""
        key = self._get_model_key(user_id, provider)
        metrics = self._model_health.get(key)
        
        if metrics and metrics.needs_warning:
            rate = int(metrics.failure_rate * 100)
            return (
                f"Your selected model is struggling with structured output ({rate}% failure rate). "
                f"Consider switching to GPT-4o or Claude Sonnet for better results."
            )
        return None
    
    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from LLM response with multiple strategies.
        Handles markdown code blocks, mixed text, and malformed JSON.
        """
        if not text:
            return None
        
        # Strategy 1: Try direct parse (clean JSON)
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract from markdown code block
        code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Find outermost braces
        start = text.find('{')
        if start == -1:
            return None
        
        depth = 0
        end = start
        for i, char in enumerate(text[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        
        # Strategy 4: Try to fix common issues
        json_str = text[start:end]
        
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Fix unquoted keys (simple cases)
        json_str = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    
    def validate_against_schema(
        self,
        data: Dict[str, Any],
        schema: Type[T]
    ) -> tuple[bool, Optional[T], List[str]]:
        """
        Validate data against a Pydantic schema.
        Returns (valid, parsed_model, errors)
        """
        try:
            model = schema.model_validate(data)
            return True, model, []
        except ValidationError as e:
            errors = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                errors.append(f"{loc}: {err['msg']}")
            return False, None, errors
    
    def build_schema_hint(self, schema: Type[BaseModel]) -> str:
        """Build a human-readable schema hint for repair prompts"""
        schema_dict = schema.model_json_schema()
        
        # Extract required fields and their types
        props = schema_dict.get("properties", {})
        required = set(schema_dict.get("required", []))
        
        hints = []
        for name, prop in props.items():
            req_marker = "*" if name in required else ""
            prop_type = prop.get("type", "any")
            if "$ref" in prop:
                prop_type = prop["$ref"].split("/")[-1]
            hints.append(f"  {name}{req_marker}: {prop_type}")
        
        return "{\n" + ",\n".join(hints) + "\n}\n(* = required)"
    
    def build_repair_prompt(
        self,
        original_prompt: str,
        errors: List[str],
        schema: Type[BaseModel]
    ) -> str:
        """Build a repair prompt with errors and schema hint"""
        return original_prompt + "\n\n" + REPAIR_PROMPT.format(
            errors="\n".join(f"- {e}" for e in errors),
            schema_hint=self.build_schema_hint(schema)
        )
    
    def build_quality_prompt(self, output: Dict[str, Any]) -> str:
        """Build a quality critique prompt for 2-pass mode"""
        return QUALITY_CRITIQUE_PROMPT.format(
            output=json.dumps(output, indent=2)
        )
    
    def build_context_prompt(self, delivery_context: Optional[Dict[str, Any]]) -> str:
        """Build a context injection string from delivery context"""
        if not delivery_context or not delivery_context.get("has_context"):
            return ""
        
        parts = []
        
        if delivery_context.get("industry"):
            parts.append(f"Industry: {delivery_context['industry']}")
        
        if delivery_context.get("methodology"):
            methodology = delivery_context["methodology"]
            if methodology == "scrum":
                parts.append("Methodology: Scrum (fixed sprints, ceremonies, velocity-based)")
            elif methodology == "kanban":
                parts.append("Methodology: Kanban (continuous flow, WIP limits)")
            elif methodology == "hybrid":
                parts.append("Methodology: Hybrid Agile (sprints with flexible scope)")
        
        if delivery_context.get("team_size"):
            parts.append(f"Team Size: {delivery_context['team_size']} members")
        
        if delivery_context.get("sprint_length"):
            parts.append(f"Sprint Length: {delivery_context['sprint_length']} weeks")
        
        if delivery_context.get("velocity"):
            parts.append(f"Team Velocity: {delivery_context['velocity']} points/sprint")
        
        if delivery_context.get("platform"):
            platform = delivery_context["platform"]
            if platform == "jira":
                parts.append("Platform: Jira (use Jira terminology)")
            elif platform == "azure_devops":
                parts.append("Platform: Azure DevOps (use ADO terminology)")
            elif platform == "linear":
                parts.append("Platform: Linear (use Linear terminology)")
        
        if parts:
            return "\n\nDELIVERY CONTEXT:\n" + "\n".join(parts)
        return ""
    
    async def validate_and_repair(
        self,
        raw_response: str,
        schema: Type[T],
        repair_callback,  # async fn(prompt) -> str
        max_repairs: int = 2,
        original_prompt: str = ""
    ) -> ValidationResult:
        """
        Validate LLM output and auto-repair if needed.
        
        Args:
            raw_response: The raw LLM response text
            schema: Pydantic schema to validate against
            repair_callback: Async function to call LLM for repair
            max_repairs: Maximum repair attempts (default 2)
            original_prompt: Original prompt for repair context
            
        Returns:
            ValidationResult with valid data or errors
        """
        result = ValidationResult(valid=False, raw_response=raw_response)
        
        # Try to extract JSON
        data = self.extract_json(raw_response)
        if data is None:
            result.errors.append("No valid JSON found in response")
            
            # Try repair
            if max_repairs > 0:
                repair_prompt = self.build_repair_prompt(
                    original_prompt,
                    ["Response did not contain valid JSON"],
                    schema
                )
                repaired = await repair_callback(repair_prompt)
                result.repair_attempts += 1
                
                data = self.extract_json(repaired)
                if data is None:
                    result.errors.append("Repair attempt 1 failed: still no valid JSON")
                    return result
        
        # Validate against schema
        valid, model, errors = self.validate_against_schema(data, schema)
        
        if valid:
            result.valid = True
            result.data = model.model_dump() if model else data
            result.errors = []
            return result
        
        # Schema validation failed - try repairs
        result.errors.extend(errors)
        current_data = data
        
        for attempt in range(max_repairs):
            repair_prompt = self.build_repair_prompt(original_prompt, errors, schema)
            repaired = await repair_callback(repair_prompt)
            result.repair_attempts += 1
            
            data = self.extract_json(repaired)
            if data is None:
                result.errors.append(f"Repair attempt {attempt + 1}: No valid JSON")
                continue
            
            valid, model, errors = self.validate_against_schema(data, schema)
            if valid:
                result.valid = True
                result.data = model.model_dump() if model else data
                result.errors = []
                logger.info(f"Schema validation succeeded after {result.repair_attempts} repair(s)")
                return result
            
            result.errors = errors
            current_data = data
        
        # All repairs failed - return best effort
        result.data = current_data  # Return last parsed data even if invalid
        return result


# Singleton instance
_strict_output_service: Optional[StrictOutputService] = None


def get_strict_output_service() -> StrictOutputService:
    """Get or create the strict output service singleton"""
    global _strict_output_service
    if _strict_output_service is None:
        _strict_output_service = StrictOutputService()
    return _strict_output_service
