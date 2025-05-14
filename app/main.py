from flask import Flask
from flask_session import Session
from flask_session.sessions import FileSystemSessionInterface
from dotenv import load_dotenv
import os

# ✅ Load environment variables early
load_dotenv()

# ✅ Set paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ✅ Create Flask app
app = Flask(__name__,
            static_folder=os.path.join(project_root, "static"),
            template_folder=os.path.join(project_root, "templates"))

# ✅ Session config
app.secret_key = os.getenv("FLASK_SECRET", "dev-key")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session"
app.config["SESSION_COOKIE_NAME"] = "lti_session"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = False
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["TINYMCE_API_KEY"] = os.getenv("TINYMCE_API_KEY")


# ✅ Custom SafeSessionInterface
class SafeSessionInterface(FileSystemSessionInterface):
    def __init__(self, cache_dir, threshold, mode, key_prefix):
        super().__init__(cache_dir=cache_dir, threshold=threshold, mode=mode, key_prefix=key_prefix)

    def save_session(self, app, session, response):
        session_id = session.sid if hasattr(session, "sid") else None
        if isinstance(session_id, bytes):
            session_id = session_id.decode("utf-8")
        response.set_cookie(
            app.config["SESSION_COOKIE_NAME"],
            session_id,
            httponly=True,
            secure=True,
            path="/"
        )

# ✅ Attach session interface + init
app.session_interface = SafeSessionInterface(
    cache_dir=app.config["SESSION_FILE_DIR"],
    threshold=500,
    mode=0o600,
    key_prefix=""
)
Session(app)

# ✅ Register LTI routes and DB models
from app.lti_routes import register_lti_routes
from app.models import Base
from app.storage import engine

register_lti_routes(app)
print("✅ LTI routes registered")

# ✅ Quick test routes
@app.route("/")
def index():
    return "🚀 LTI tool is live!"

@app.route("/test")
def test():
    return "✅ Flask is running and routes are active!"

# ✅ Start the app only if run directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
