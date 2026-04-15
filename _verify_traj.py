import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from hermes_evolution.trajectory_recorder import save_trajectory, load_failed_trajectories, reflect_on_failures, evolver_update

# Test save_trajectory
id1 = save_trajectory("execute_shell_command", "npm install clawhub", False, "permission denied", ["github"])
id2 = save_trajectory("execute_shell_command", "npm install clawhub", False, "permission denied", ["github"])
print(f"save_trajectory OK: {id1}, {id2}")

# Test load_failed_trajectories
failed = load_failed_trajectories()
print(f"load_failed_trajectories OK: {len(failed)} failed trajectories")

# Test reflect_on_failures
ref = reflect_on_failures()
print(f"reflect_on_failures OK: groups={ref['groups']}, lessons={ref['reflected']}")

# Test evolver_update
result = evolver_update()
print(f"evolver_update OK: {result['status']}, lessons_written={result['lessons_written']}")

print("\n=== ALL OK ===")
