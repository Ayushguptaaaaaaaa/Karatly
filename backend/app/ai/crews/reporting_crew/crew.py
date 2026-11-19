from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

from app.ai.crews.base import CrewHelpers
from app.ai.outputs import InsightsReport


@CrewBase
class ReportingCrew(CrewHelpers):
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def report_writer(self) -> Agent:
        return self.make_agent("report_writer", ["report_style_guide.md"], [])

    @task
    def write_insights_report(self) -> Task:
        return Task(config=self.tasks_config["write_insights_report"], output_pydantic=InsightsReport)

    @crew
    def crew(self) -> Crew:
        return self.make_crew(self.agents, self.tasks)
