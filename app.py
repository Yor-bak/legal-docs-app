import os
import datetime
from flask import Flask, request, render_template, redirect, url_for, session, flash
from google.cloud import storage
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-cambiar")

BUCKET_NAME = os.environ["BUCKET_NAME"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
UPLOADER_TOKEN = os.environ["UPLOADER_TOKEN"]
ADMIN_KEY_PATH = os.environ["ADMIN_KEY_PATH"]
UPLOADER_KEY_PATH = os.environ["UPLOADER_KEY_PATH"]


def get_client(role):
    """Cada rol usa su propia service account: la separación de permisos
    ocurre a nivel de IAM en GCP, no solo en el código de la app."""
    key_path = ADMIN_KEY_PATH if role == "admin" else UPLOADER_KEY_PATH
    creds = service_account.Credentials.from_service_account_file(key_path)
    return storage.Client(credentials=creds, project=creds.project_id)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    token = request.form.get("token", "")
    if token == ADMIN_TOKEN:
        session["role"] = "admin"
        return redirect(url_for("admin_panel"))
    if token == UPLOADER_TOKEN:
        session["role"] = "uploader"
        return redirect(url_for("upload_panel"))
    flash("Token inválido")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/upload", methods=["GET", "POST"])
def upload_panel():
    if session.get("role") != "uploader":
        return redirect(url_for("index"))

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Selecciona un archivo")
            return redirect(url_for("upload_panel"))

        client = get_client("uploader")
        bucket = client.bucket(BUCKET_NAME)
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        blob_name = f"{timestamp}-{file.filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.stream, content_type=file.content_type)
        flash(f"Subido: {blob_name}")
        return redirect(url_for("upload_panel"))

    return render_template("upload.html")


@app.route("/admin")
def admin_panel():
    if session.get("role") != "admin":
        return redirect(url_for("index"))

    client = get_client("admin")
    bucket = client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs())

    files = []
    for blob in blobs:
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET",
        )
        files.append({"name": blob.name, "url": url, "size": blob.size})

    return render_template("admin.html", files=files)


if __name__ == "__main__":
    app.run(debug=True, port=8080)
