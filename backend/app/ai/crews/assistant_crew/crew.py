from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

from app.ai.crews.base import CrewHelpers
from app.ai.outputs import ChatAnswer
from app.ai.tools import ComparePeriods, GetLabelDetails, GetProfitability, GetSalesSummary, SearchDesigns
from app.core.config import get_settings


@CrewBase
class AssistantCrew(CrewHelpers):
    """Fast chat: the shop snapshot is in the prompt, so most answers take a single LLM call.
    Tools are only for details the snapshot doesn't hold (other periods, a specific label)."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    rpm_override = get_settings().LLM_CHAT_MAX_RPM

    @agent
    def accountant_assistant(self) -> Agent:
        return self.make_agent(
            "accountant_assistant", ["answering_guidelines.md"],
            [GetLabelDetails(), GetProfitability(), GetSalesSummary(), ComparePeriods(), SearchDesigns()],
            max_iter=3, max_retry_limit=0,
        )

    @task
    def answer_question(self) -> Task:
        return Task(config=self.tasks_config["answer_question"], output_pydantic=ChatAnswer)

    @crew
    def crew(self) -> Crew:
        return self.make_crew(self.agents, self.tasks)
