"""Creates test plans from requirements and QA knowledge."""

class TestPlanner:
    def create_plan(self, requirement, knowledge=None):
        return {
            "requirement": requirement,
            "knowledge_used": knowledge or {},
            "scenarios": [],
            "status": "draft",
        }
