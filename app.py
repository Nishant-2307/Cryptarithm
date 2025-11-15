from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading, os, json, time

from solver import solve_cryptarithm  # uses updated AC-3 / MAC solver

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# Path to trace file
TRACE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trace.json")


# --------------------------------------------------
# Utility: Run solver in a background thread
# --------------------------------------------------
def run_solver(words, result, use_ac3):
    """
    Runs solver in a thread, writes trace.json when done.
    """
    # Safely remove old trace if possible
    if os.path.exists(TRACE_PATH):
        for _ in range(5):  # retry up to 5 times
            try:
                os.remove(TRACE_PATH)
                break
            except PermissionError:
                # File might still be used by another process (like a previous fetch)
                time.sleep(0.3)
            except Exception as e:
                print("Warning: couldn't remove old trace:", e)
                break

    # Run solver (this will create trace.json at the end)
    try:
        solve_cryptarithm(words, result, trace_path=TRACE_PATH, use_ac3=use_ac3)
    except Exception as e:
        print("Solver error:", e)



# --------------------------------------------------
# Routes
# --------------------------------------------------
@app.route("/")
def index():
    """Serve the frontend HTML file."""
    return send_from_directory(".", "index.html")


@app.route("/solve", methods=["POST"])
def solve():
    """
    Starts solving (non-blocking thread).

    Expected JSON:
    {
      "words": ["SEND", "MORE"],
      "result": "MONEY",
      "use_ac3": true/false
    }
    """
    data = request.get_json()
    words = data.get("words", [])
    result = data.get("result", "")
    use_ac3 = bool(data.get("use_ac3", False))

    # Start background solver thread
    t = threading.Thread(target=run_solver, args=(words, result, use_ac3), daemon=True)
    t.start()

    return jsonify({"status": "started", "use_ac3": use_ac3})


@app.route("/trace", methods=["GET"])
def trace():
    """
    Returns JSON:
    {
      "ready": true/false,
      "events": [...]
    }
    """
    if not os.path.exists(TRACE_PATH):
        return jsonify({"ready": False, "events": []})

    try:
        with open(TRACE_PATH, "r", encoding="utf-8") as f:
            events = json.load(f)

        # Only report ready when solver has fully completed
        if events and events[-1].get("type") == "SOLVER_DONE":
            return jsonify({"ready": True, "events": events})
        else:
            return jsonify({"ready": False, "events": events})

    except json.JSONDecodeError:
        import time
        time.sleep(0.5)
        try:
            with open(TRACE_PATH, "r", encoding="utf-8") as f:
                events = json.load(f)
            if events and events[-1].get("type") == "SOLVER_DONE":
                return jsonify({"ready": True, "events": events})
            else:
                return jsonify({"ready": False, "events": events})
        except:
            return jsonify({"ready": False, "events": []})


@app.route("/clear", methods=["POST"])
def clear():
    """Deletes trace.json to reset solver state."""
    if os.path.exists(TRACE_PATH):
        try:
            os.remove(TRACE_PATH)
        except Exception as e:
            print("Warning: couldn't delete trace file:", e)
    return jsonify({"cleared": True})


# --------------------------------------------------
# Main entry point
# --------------------------------------------------
if __name__ == "__main__":
    print("🚀 Cryptarithm CSP visualizer running at http://127.0.0.1:5000/")
    app.run(debug=True)
