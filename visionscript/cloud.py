import json
import uuid
from io import BytesIO

import numpy as np
from flask import Flask, jsonify, redirect, render_template, request, send_file

from visionscript import lang, parser

app = Flask(__name__)

API_KEY = "test"  # uuid.uuid4().hex

with open("scripts.json", "r") as f:
    scripts = json.load(f)

for script in scripts:
    scripts[script]["session"] = lang.VisionScript()


@app.route("/")
def index_page():
    return render_template("deployintro.html")


@app.route("/<id>", methods=["GET", "POST"])
def home(id):
    if request.method == "POST":
        if scripts.get(id) is None:
            return jsonify({"error": "Invalid ID"})

        # if no session for the script, make it
        if scripts[id].get("session") is None:
            scripts[id]["session"] = lang.VisionScript()

        data = request.form
        files = request.files

        results = {}

        for variable in scripts[id]["variables"]:
            if not data.get(variable) and not files.get(variable):
                return jsonify({"error": f"Missing variable {variable}"})
            # if data is an image, turn into numpy array
            elif scripts[id]["variables"][variable] == "image":
                from PIL import Image

                ram_file = BytesIO()

                files[variable].save(ram_file)

                ram_file.seek(0)

                image = Image.open(ram_file).convert("RGB")

                results[variable] = np.array(image)[:, :, ::-1]
            else:
                results[variable] = data[variable]

        try:
            session = scripts[id]["session"]

            session.state = {**session.state, **results}
            session.notebook = True

            session.parse_tree(parser.parse(scripts[id]["script"]))
        except Exception as e:
            raise e
            return jsonify({"error": str(e)})

        output = session.state["output"]

        if isinstance(output, dict) and output.get("image"):
            # output is base64, convert to png
            import base64

            image = BytesIO(base64.b64decode(output["image"]))
            image.seek(0)
            return send_file(image, mimetype="image/png")

        return jsonify({"output": session.state["output"]})

    image_inputs = [[v, k] for k, v in scripts[id]["variables"].items() if v == "image"]
    text_inputs = [[v, k] for k, v in scripts[id]["variables"].items() if v == "text"]

    return render_template(
        "index.html",
        id=id,
        image_inputs=image_inputs,
        text_inputs=text_inputs,
        title=scripts[id]["title"],
    )


@app.route("/create", methods=["POST"])
def create():
    data = request.json

    if data.get("api_key") != API_KEY:
        return jsonify({"error": "Invalid API key"}), 401

    id = data["slug"]

    scripts[data["slug"]] = {
        "title": data["title"],
        "script": data["script"],
        "variables": data["variables"],
    }

    # make POST to http://localhost:6999/create
    import string

    import requests

    app_slug = data["title"].translate(
        str.maketrans("", "", string.punctuation.replace("-", ""))
    )

    response = requests.post(
        "http://localhost:6999/create",
        json={
            "api_key": "test",
            "title": data["title"],
            "slug": app_slug,
            "script": data["script"],
            "variables": data["variables"],
        },
    )

    if response.status_code != 200:
        return jsonify({"error": "Error creating app"}), 500

    return jsonify({"id": id})
