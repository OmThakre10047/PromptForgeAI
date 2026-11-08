import json


class JudgeAgent:

    def judge(self, algorithm_output, edge_output, optimization_output):

        return {
            "algorithm": algorithm_output,
            "edge_cases": edge_output,
            "optimization": optimization_output
        }