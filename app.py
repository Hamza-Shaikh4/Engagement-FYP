from flask import Flask, render_template, jsonify, request
from fuzzy_logic import fuzzy_engagement
import json
import os

app = Flask(__name__)

# Page routes (these load your HTML from /templates)
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/books")
def books():
    return render_template("books.html")

@app.get("/reading/<story_id>")
def reading(story_id):
    return render_template("reading.html", story_id=story_id)

@app.route("/results")
def results():
    return render_template("results.html")

@app.route("/avatar")
def avatar():
    return render_template("avatar.html")

# API route: return stories.json as JSON 
@app.route("/api/stories")
def api_stories():
    json_path = os.path.join(app.static_folder, "stories.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


#Detect engagement variables for fuzzy logic

@app.post("/api/engagement")
def api_engagement():
    data = request.get_json(force=True)

    idle_ratio = float(data.get("idle_ratio", 0.0))
    scroll_speed_px_s = float(data.get("scroll_speed_px_s", 0.0))
    nav_rate_per_min = float(data.get("nav_rate_per_min", 0.0))
    interaction_rate_per_min = float(data.get("interaction_rate_per_min", 0.0))

    score, label = fuzzy_engagement(
        idle_ratio,
        scroll_speed_px_s,
        nav_rate_per_min,
        interaction_rate_per_min
    )

    return jsonify({
        "score": score,
        "label": label
    })


if __name__ == "__main__":
    app.run(debug=True)
