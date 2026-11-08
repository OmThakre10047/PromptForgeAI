from app.engine.state import ProjectState

state = ProjectState(task="Solve Two Sum")

state.log("Developer generated first solution")
state.log("Reviewer requested optimization")

state.next_iteration()

print("Iteration:", state.iteration)
print("History:")

for event in state.history:
    print("-", event)