from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

from app.ai.crews.base import CrewHelpers
from app.ai.outputs import DemandOutput, StockPositionOutput
from app.ai.tools import GetLabelDetails


@CrewBase
class InventoryAnalysisCrew(CrewHelpers):
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def stock_analyst(self) -> Agent:
        return self.make_agent("stock_analyst", ["stock_status_rules.md"], [GetLabelDetails()])

    @agent
    def demand_analyst(self) -> Agent:
        return self.make_agent("demand_analyst", ["demand_classification.md"], [GetLabelDetails()])

    @task
    def analyse_stock_position(self) -> Task:
        return Task(config=self.tasks_config["analyse_stock_position"], output_pydantic=StockPositionOutput,
                    callback=self.task_done("stock"))

    @task
    def classify_demand(self) -> Task:
        return Task(config=self.tasks_config["classify_demand"], output_pydantic=DemandOutput)

    @crew
    def crew(self) -> Crew:
        return self.make_crew(self.agents, self.tasks)
