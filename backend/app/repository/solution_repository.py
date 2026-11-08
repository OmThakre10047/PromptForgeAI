class SolutionRepository:
    def __init__(self):
        self.solutions = {}

    def add( self, model, solution):
        self.solutions[model] = solution
    
    def get(self, model):
        return self.solutions.get(model)
    
    def get_all(self):
        return self.solutions