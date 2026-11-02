import os
import datetime
from flask import Flask, request, render_template, redirect, url_for, session, flash
from google.cloud import storage
import google.auth
import google.auth.transport.requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-cambiar")

BUCKET_NAME = os.environ["BUCKET_NAME"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
UPLOADER_TOKEN = os.environ["UPLOADER_TOKEN"]
SERVICE_ACCOUNT_EMAIL = os.environ["SERVICE_ACCOUNT_EMAIL"]


def get_client():
    """Usa las credenciales por defecto del entorno (ADC): la SA default
    de App Engine en producción, o `gcloud auth application-default login`
    en local."""
    return storage.Client()


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

        client = get_client()
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

    client = get_client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs())

    files = []
    for blob in blobs:
        credentials, _ = google.auth.default()
        credentials.refresh(google.auth.transport.requests.Request())
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET",
            service_account_email=SERVICE_ACCOUNT_EMAIL,
            access_token=credentials.token,
        )
        files.append({"name": blob.name, "url": url, "size": blob.size})

    return render_template("admin.html", files=files)


if __name__ == "__main__":
    app.run(debug=True, port=8080)
