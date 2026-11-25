
from flask import Flask, render_template

app = Flask(__name__)


@app.get("/")
def landing():
    return render_template("landing.html")


def stub(page, title, text):
    return render_template("stub.html", page=page, title=title, text=text)


@app.get("/login")
def login():
    return stub("login", "Sign in",
                "Signing in with Microsoft, Google, Yandex, VK or email will be here.")


@app.get("/organiser/new")
def organiser_new():
    return stub("organiser_new", "Create a competition",
                "The competition editor will be here: stages, dates, who can join and how the winner is chosen.")


@app.get("/privacy")
def privacy():
    return stub("privacy", "Privacy",
                "How we store and delete participants' data will be described here.")


@app.get("/contact")
def contact():
    return stub("contact", "Contact",
                "A way to reach the team will be here.")


if __name__ == "__main__":
    app.run(debug=True, port=5078)
