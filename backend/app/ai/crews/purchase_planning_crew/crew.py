from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

from app.ai.crews.base import CrewHelpers
from app.ai.outputs import BudgetOutput, ReorderOutput
from app.ai.tools import CalculatePurchaseCost, GetLabelDetails


@CrewBase
class PurchasePlanningCrew(CrewHelpers):
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def procurement_planner(self) -> Agent:
        return self.make_agent("procurement_planner", ["reorder_quantity_rules.md"], [GetLabelDetails()])

    @agent
    def cost_accountant(self) -> Agent:
        return self.make_agent("cost_accountant", ["costing_rules.md"], [CalculatePurchaseCost()], max_iter=10)

    @task
    def recommend_reorders(self) -> Task:
        return Task(config=self.tasks_config["recommend_reorders"], output_pydantic=ReorderOutput,
                    callback=self.task_done("plan_reorder"))

    @task
    def estimate_budget(self) -> Task:
        return Task(config=self.tasks_config["estimate_budget"], output_pydantic=BudgetOutput)

    @crew
    def crew(self) -> Crew:
        return self.make_crew(self.agents, self.tasks)
