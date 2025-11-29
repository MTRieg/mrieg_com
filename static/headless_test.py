import json
import subprocess

def run_js_simulation(pieces, board_before=800, board_after=700):
    input_data = {
        "pieces": pieces,
        "boardBefore": board_before,
        "boardAfter": board_after,
    }

    proc = subprocess.run(
        ["node", "headless.mjs"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True
    )

    if proc.returncode != 0:
        print("JS Error:", proc.stderr)
        raise RuntimeError("JavaScript simulation failed")

    return json.loads(proc.stdout)

# Example
pieces = [
    {"x": 0, "y": 0, "vx": 10, "vy": 5, "radius": 30, "color": "red"},
    {"x": 100, "y": 50, "vx": -5, "vy": 2, "radius": 30, "color": "blue"},
]

result = run_js_simulation(pieces, board_before=800, board_after=600)
print(json.dumps(result, indent=2))
