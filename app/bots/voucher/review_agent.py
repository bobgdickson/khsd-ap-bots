from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from app.services.langfuse import langfuse_handler
from .models import VoucherEntryPlan, ExecutionDecision
from .prompts.review import REVIEW_PROMPT


def review_plan(plan: VoucherEntryPlan, extra_prompt: str | None = None) -> ExecutionDecision:
    system_prompt = REVIEW_PROMPT
    if extra_prompt:
        system_prompt = system_prompt + "\n\nAdditional instructions:\n" + extra_prompt

    agent = create_agent(
        name="Voucher Review Agent",
        system_prompt=system_prompt,
        tools=[],
        model="gpt-5-mini",
        response_format=ExecutionDecision,
    )

    user_content = (
        f"Invoice: {plan.invoice.model_dump()}\n"
        f"PO: {plan.po.model_dump()}\n"
        f"Mapping: {plan.mapping.model_dump()}"
    )
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_content)]},
        config={"callbacks": [langfuse_handler]},
    )
    structured = result.get("structured_response", result)
    return structured if isinstance(structured, ExecutionDecision) else ExecutionDecision.model_validate(structured)
