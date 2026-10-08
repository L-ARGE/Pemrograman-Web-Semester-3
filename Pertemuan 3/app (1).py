from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
@app.route("/index")

def index():
    return render_template("index.html")

@app.route("/kontak")

def contact():  
    return render_template("kontak.html")

@app.route("/layout")

def layout():
    return render_template("layout.html")

@app.route("/nama")

def nama():
    return render_template("nama.html")

@app.route("/perkenalan")

def perkenalan():
    return render_template("perkenalan.html")

if __name__ == "__main__":
    app.run(debug=True)