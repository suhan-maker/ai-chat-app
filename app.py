import os
import time
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import google.generativeai as genai

# ---------------- CONFIG -----------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

# Gemini API Key
GENAI_API_KEY = os.environ.get("AIzaSyAzPpg5l2aVo1U9m6c4FShmPzJkM_q3EME")
if not GENAI_API_KEY:
    raise ValueError("⚠️ GENAI_API_KEY environment variable not set!")

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel("gemini-3.0-flash")

# ---------------- IN-MEMORY USERS -----------------
# For demo purposes; replace with DB for production
users = {"test@example.com": "password123"}  # email:password

# ---------------- ROUTES -----------------
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("chat"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if email in users and users[email] == password:
            session["user"] = email
            return redirect(url_for("chat"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html", user=session["user"])

# ---------------- STREAMING GEMINI -----------------
@app.route("/stream", methods=["POST"])
def stream():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_msg = request.json.get("message", "")

    def generate():
        try:
            stream = model.stream(messages=[{"role": "user", "content": user_msg}])
            for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta
                    time.sleep(0.02)  # smooth typing effect
        except Exception as e:
            yield f"⚠️ Error: {str(e)}"

    return app.response_class(generate(), mimetype="text/plain")

# ---------------- RUN APP -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
