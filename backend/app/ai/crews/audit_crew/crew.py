from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

from app.ai.crews.base import CrewHelpers
from app.ai.outputs import AnomalyOutput
from app.ai.tools import GetLabelDetails


@CrewBase
class AuditCrew(CrewHelpers):
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def stock_auditor(self) -> Agent:
        return self.make_agent("stock_auditor", ["anomaly_checks.md"], [GetLabelDetails()])

    @task
    def detect_anomalies(self) -> Task:
        return Task(config=self.tasks_config["detect_anomalies"], output_pydantic=AnomalyOutput)

    @crew
    def crew(self) -> Crew:
        return self.make_crew(self.agents, self.tasks)
