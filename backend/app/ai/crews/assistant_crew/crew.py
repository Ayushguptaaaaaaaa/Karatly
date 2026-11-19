from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

from app.ai.crews.base import CrewHelpers
from app.ai.outputs import ChatAnswer
from app.ai.tools import all_tools


@CrewBase
class AssistantCrew(CrewHelpers):
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def accountant_assistant(self) -> Agent:
        return self.make_agent("accountant_assistant", ["answering_guidelines.md"], all_tools())

    @task
    def answer_question(self) -> Task:
        return Task(config=self.tasks_config["answer_question"], output_pydantic=ChatAnswer)

    @crew
    def crew(self) -> Crew:
        return self.make_crew(self.agents, self.tasks)
