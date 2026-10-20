"""Structured outputs (Pydantic) so a UI can render cards/tables/maps instead of prose.
Reference a schema in team.yaml with `output_schema: ActionPlan`. Add your own here."""
from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    priority: int = Field(description="1 = most urgent")
    target: str = Field(description="Who/where the action applies to (person, building, neighbourhood, route)")
    action: str = Field(description="The concrete action to take")
    reason: str = Field(description="Why, citing specific numbers from the evidence")
    evidence: str = Field(description="Tables/tools/queries the numbers came from")
    needs_human_approval: bool = Field(default=True)


class ActionPlan(BaseModel):
    title: str
    summary: str = Field(description="2-3 sentence plain-language summary")
    items: list[ActionItem]
    caveats: list[str] = Field(description="Data limits, model uncertainty, what was assumed")
    data_window: str = Field(description="Date range/vintage of the data used")


class Finding(BaseModel):
    claim: str
    supported: bool
    evidence: str


class Verdict(BaseModel):
    findings: list[Finding]
    overall: str = Field(description="approve | revise | reject")


SCHEMAS = {"ActionPlan": ActionPlan, "Verdict": Verdict}
