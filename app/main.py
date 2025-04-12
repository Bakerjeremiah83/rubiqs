from flask import Flask
from flask_session import Session
from dotenv import load_dotenv
import os
from flask_session.sessions import FileSystemSessionInterface
from itsdangerous import want_bytes  # ✅ Optional patch for legacy byte handling

# ✅ Load environment variables
load_dotenv()

# ✅ Explicitly set template folder so Flask can find templates from root
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__,
            static_folder=os.path.join(project_root, "static"),
            template_folder=os.path.join(project_root, "templates"))

# ✅ Session config
app.secret_key = os.getenv("SECRET_KEY", "defaultsecret")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session"
app.config["SESSION_COOKIE_NAME"] = "lti_session"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = False  # Disable signing to avoid byte encoding issues
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True


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

# ✅ Attach the safe session handler
app.session_interface = SafeSessionInterface(
    cache_dir=app.config["SESSION_FILE_DIR"],
    threshold=500,
    mode=0o600,
    key_prefix=""
)

# ✅ Initialize session
Session(app)

# ✅ Register LTI routes
from app.lti_routes import register_lti_routes
register_lti_routes(app)
print("✅ LTI routes registered")

@app.route("/")
def index():
    return "🚀 LTI tool is live!"

# ✅ Test route to confirm Flask is running
@app.route("/test")
def test():
    return "✅ Flask is live and routing works!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, FLASK_DEBUG=1)
