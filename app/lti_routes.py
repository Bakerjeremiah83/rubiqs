from flask import request, jsonify, redirect, Blueprint, session, render_template
import json
import os
import uuid
import jwt
import requests
from jwt.exceptions import InvalidTokenError
from docx import Document
from io import BytesIO
import openai
from datetime import datetime
from requests_oauthlib import OAuth1Session
import re
from pdfminer.high_level import extract_text as extract_pdf_text

def get_total_points_from_rubric(rubric):
    return sum(
        max(level["score"] for level in criterion["levels"])
        for criterion in rubric.get("criteria", [])
    )

lti = Blueprint('lti', __name__)

@lti.route("/login", methods=["POST"])
def login():
    print("🔐 /login route hit")
    issuer = request.form.get("iss")
    login_hint = request.form.get("login_hint")
    target_link_uri = request.form.get("target_link_uri")
    client_id = request.form.get("client_id")
    lti_message_hint = request.form.get("lti_message_hint")

    if not all([issuer, login_hint, target_link_uri, client_id]):
        return "❌ Missing required LTI launch parameters", 400

    redirect_url = (
        f"{issuer}/mod/lti/auth.php?"
        f"scope=openid&response_type=id_token&client_id={client_id}&"
        f"redirect_uri={target_link_uri}&login_hint={login_hint}&state=state123&"
        f"response_mode=form_post&nonce=nonce123&prompt=none&"
        f"lti_message_hint={lti_message_hint}"
    )

    print(f"➡️ Redirecting to: {redirect_url}")
    return redirect(redirect_url)

@lti.before_app_request
def debug_session_state():
    print("🧪 SESSION CONTENTS:", dict(session))

def register_lti_routes(app):
    app.register_blueprint(lti)
    print("✅ LTI routes registered")

@lti.route("/.well-known/jwks.json", methods=["GET"])
def jwks():
    print("📡 Serving JWKS route...")
    with open("app/keys/jwks.json", "r") as f:
        jwks_data = json.load(f)
    return jsonify(jwks_data)

@lti.route("/.well-known/openid-configuration", methods=["GET"])
def openid_configuration():
    tool_url = os.environ["TOOL_URL"]
    return jsonify({
        "issuer": tool_url,
        "authorization_endpoint": f"{tool_url}/login",
        "token_endpoint": f"{tool_url}/token",
        "jwks_uri": f"{tool_url}/.well-known/jwks.json"
    })

@lti.route("/launch", methods=["POST"])
def launch():
    print("🚀 /launch hit")
    jwt_token = request.form.get("id_token")
    if not jwt_token:
        return "❌ Error: No id_token (JWT) received in launch request.", 400

        # ✅ DEBUG: Print unverified JWT ISS
    try:
        unverified = jwt.decode(jwt_token, options={"verify_signature": False})
        print("🔍 UNVERIFIED JWT ISS:", unverified.get("iss"))
        print("🔍 PLATFORM_ISS from .env:", os.getenv("PLATFORM_ISS"))
    except Exception as e:
        print("❌ Failed to decode unverified JWT:", str(e))

    # ✅ Everything BELOW this should be outside that try/except
    jwks_url = f"{os.getenv('PLATFORM_ISS')}/mod/lti/certs.php"
    try:
        jwks_response = requests.get(jwks_url)
        jwks_response.raise_for_status()
        jwks = jwks_response.json()
        unverified_header = jwt.get_unverified_header(jwt_token)
        kid = unverified_header.get("kid")
        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                break

        if not public_key:
            return "❌ No matching public key found in JWKS", 400
    except Exception as e:
        return f"❌ Could not fetch JWKS: {str(e)}", 400

    try:
        aud = jwt.decode(
            jwt_token,
            key=public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=os.getenv("PLATFORM_ISS")
        ).get("aud")
        client_ids = os.getenv("CLIENT_IDS", "")
        valid_client_ids = [id.strip() for id in client_ids.split(",") if id.strip()]
        if aud not in valid_client_ids:
            return f"❌ JWT validation error: Audience '{aud}' not allowed.", 403

        decoded = jwt.decode(
            jwt_token,
            key=public_key,
            algorithms=["RS256"],
            audience=aud,
            issuer=os.getenv("PLATFORM_ISS")
        )
        unverified = jwt.decode(jwt_token, options={"verify_signature": False})

         # ✅ ADD DEBUG HERE
        print("JWT Issuer:", decoded.get("iss"))
        print("Expected Issuer (PLATFORM_ISS):", os.getenv("PLATFORM_ISS"))

        print("✅ JWT verified")
        print(json.dumps(decoded, indent=2))
        session["launch_data"] = json.loads(json.dumps(decoded))
        session["tool_role"] = "student"
    except InvalidTokenError as e:
        return f"❌ Invalid JWT signature: {str(e)}", 400

        # ✅ Now continue with render_template and persona toggle logic
    requires_persona = False
    assignment_title = decoded.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}).get("title", "").strip().lower()
    rubric_index_path = os.path.join("rubrics", "rubric_index.json")
    if os.path.exists(rubric_index_path):
        with open(rubric_index_path, "r") as f:
            rubric_index = json.load(f)
            for item in rubric_index:
                if item["assignment_title"].strip().lower() == assignment_title and item.get("requires_persona"):
                    requires_persona = True
                    break

    return render_template(
        "launch.html",
        activity_name=decoded.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}).get("title", "Assignment"),
        user_name=decoded.get("given_name", "Student"),
        user_roles=decoded.get("https://purl.imsglobal.org/spec/lti/claim/roles", []),
        requires_persona=requires_persona
    )

@lti.route("/grade-docx", methods=["POST"])
def grade_docx():
    print("📥 /grade-docx hit")
    file = request.files.get("file")
    rubric_file = request.files.get("rubric")
    persona_file = request.files.get("persona")

    if not file or not rubric_file:
        return "❌ Assignment and rubric files are required.", 400

    # Extract student submission text
    try:
        filename = file.filename.lower()
        if filename.endswith(".docx"):
            doc = Document(file)
            full_text = "\n".join([para.text for para in doc.paragraphs])
        elif filename.endswith(".pdf"):
            full_text = extract_pdf_text(BytesIO(file.read()))
        else:
            return "❌ Unsupported assignment file type.", 400
        print(f"📄 Assignment text extracted ({len(full_text)} characters)")
    except Exception as e:
        return f"❌ Failed to extract assignment: {str(e)}", 500

    # Extract rubric text and metadata
    try:
        rubric_filename = rubric_file.filename.lower()
        if rubric_filename.endswith(".json"):
            rubric_json = json.load(rubric_file)
            rubric_total_points = get_total_points_from_rubric(rubric_json)
            rubric_text = "\n".join(
                [f"- {c['description']}" for c in rubric_json.get("criteria", [])]
            )
            rubric_title = rubric_json.get("assignment_title", "Assignment")
            rubric_style = rubric_json.get("style_guidance", "")
        elif rubric_filename.endswith(".docx"):
            doc = Document(rubric_file)
            rubric_text = "\n".join([para.text for para in doc.paragraphs])
            rubric_title = "Assignment"
            rubric_style = ""

            # 🧠 Extract total points if labeled
            match = re.search(r'Total Points:\s*(\d+)', rubric_text)
            if match:
                rubric_total_points = int(match.group(1))

        elif rubric_filename.endswith(".pdf"):
            rubric_text = extract_pdf_text(BytesIO(rubric_file.read()))
            rubric_title = "Assignment"
            rubric_style = ""
            # 🧠 Extract total points if labeled
            match = re.search(r'Total Points:\s*(\d+)', rubric_text)
            if match:
                rubric_total_points = int(match.group(1))
        
        else:
            return "❌ Unsupported rubric file type.", 400
        print(f"📋 Rubric extracted ({len(rubric_text)} characters)")
    except Exception as e:
        return f"❌ Failed to extract rubric: {str(e)}", 500

    # Extract persona/reference scenario if available
    reference_data = ""
    if persona_file:
        try:
            persona_filename = persona_file.filename.lower()
            if persona_filename.endswith(".docx"):
                doc = Document(persona_file)
                reference_data = "\n".join([para.text for para in doc.paragraphs])
            elif persona_filename.endswith(".pdf"):
                reference_data = extract_pdf_text(BytesIO(persona_file.read()))
            print(f"👤 Persona extracted ({len(reference_data)} characters)")
        except Exception as e:
            return f"❌ Failed to extract persona file: {str(e)}", 500

    # Compose GPT prompt
    prompt = f"""
You are a helpful AI grader for a college-level course.

Evaluate the student submission below using the following rubric:

Rubric:
{rubric_text}

Style Guidance: {rubric_style}
"""
    if reference_data:
        prompt += f"\nReference Scenario:\n{reference_data}\n"

    prompt += f"""
Assignment Submission:

---
{full_text}
---

Return your response in this format:

Score: <number from 0 to {rubric_total_points}>
Feedback: <detailed, helpful feedback>
"""

    # Call OpenAI
    try:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            print("❌ OPENAI_API_KEY is missing")
        else:
            print("✅ OPENAI_API_KEY loaded")

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt.strip()}],
            temperature=0.5,
            max_tokens=1000
        )

        output = response["choices"][0]["message"]["content"]
        print("✅ GPT response received")

        score_match = re.search(r"Score:\s*(\d{1,3})", output)
        score = int(score_match.group(1)) if score_match else 0

        feedback_match = re.search(r"Feedback:\s*(.+)", output, re.DOTALL)
        feedback = feedback_match.group(1).strip() if feedback_match else output.strip()

    except Exception as e:
        return f"❌ GPT error: {str(e)}", 500

    # Check if instructor approval is required
    launch_data = session.get("launch_data", {})
    assignment_title = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}).get("title", "").strip().lower()
    rubric_index_path = os.path.join("rubrics", "rubric_index.json")
    requires_approval = False

    if os.path.exists(rubric_index_path):
        with open(rubric_index_path, "r") as f:
            rubric_index = json.load(f)
            for item in rubric_index:
                if item["assignment_title"].strip().lower() == assignment_title and item.get("instructor_approval"):
                    requires_approval = True
                    break

    if requires_approval:
        print("📥 Saving grade to pending_reviews.json")
        pending_path = os.path.join("rubrics", "pending_reviews.json")
        pending = []
        if os.path.exists(pending_path):
            with open(pending_path, "r") as f:
                pending = json.load(f)

        pending.append({
            "assignment_title": assignment_title,
            "score": score,
            "feedback": feedback,
            "student_id": launch_data.get("sub"),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        with open(pending_path, "w") as f:
            json.dump(pending, f, indent=2)

        return render_template("feedback.html", score=score, feedback=feedback, rubric_total_points=rubric_total_points)

    # Auto-post or display feedback
    return render_template("feedback.html", score=score, feedback=feedback, rubric_total_points=rubric_total_points)

@lti.route("/dashboard-launch", methods=["POST"])
def dashboard_launch():
    print("🚀 /dashboard-launch hit")
    jwt_token = request.form.get("id_token")
    if not jwt_token:
        return "❌ No id_token provided.", 400

    # 🔐 Step 1: Fetch the JWKS (public keys) from your LMS
    jwks_url = f"{os.getenv('PLATFORM_ISS')}/mod/lti/certs.php"
    try:
        jwks_response = requests.get(jwks_url)
        jwks_response.raise_for_status()
        jwks = jwks_response.json()
        unverified_header = jwt.get_unverified_header(jwt_token)
        kid = unverified_header.get("kid")
        public_key = None

        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                break

        if not public_key:
            return "❌ Public key not found.", 400

    except Exception as e:
        return f"❌ JWKS fetch failed: {str(e)}", 400

    # ✅ Step 2: Decode the JWT
    try:
        aud = jwt.decode(
            jwt_token,
            key=public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=os.getenv("PLATFORM_ISS")
        ).get("aud")

        client_ids = os.getenv("CLIENT_IDS", "")
        valid_client_ids = [id.strip() for id in client_ids.split(",") if id.strip()]

        print("🔐 Valid client IDs:", valid_client_ids)
        print("🔐 Received aud:", aud)

        if aud not in valid_client_ids:
            return f"❌ JWT validation error: Audience '{aud}' not allowed.", 403

        decoded = jwt.decode(
            jwt_token,
            key=public_key,
            algorithms=["RS256"],
            audience=aud,
            issuer=os.getenv("PLATFORM_ISS")
        )

        print("✅ Dashboard launch JWT verified")
        print(json.dumps(decoded, indent=2))

        session["launch_data"] = json.loads(json.dumps(decoded))
        session["tool_role"] = "instructor"

    except Exception as e:
        return f"❌ JWT validation error: {str(e)}", 400

    return redirect("/review-feedback")

@lti.route("/review-feedback", methods=["GET", "POST"])
def review_feedback():
    pending_path = os.path.join("rubrics", "pending_reviews.json")

    # ✅ Check if the user is actually an instructor
    tool_role = session.get("tool_role")
    if tool_role != "instructor":
        return "❌ Access denied. Instructors only.", 403

    launch_data = session.get("launch_data", {})
    print("🔍 LAUNCH DATA:", json.dumps(launch_data, indent=2))

    # ✅ Load all pending reviews
    reviews = []
    if os.path.exists(pending_path):
        with open(pending_path, "r") as f:
            reviews = json.load(f)

    # ✅ Set default review index if not set
    if "review_index" not in session:
        session["review_index"] = 0

    # ✅ Handle form submissions
    if request.method == "POST":
        nav = request.form.get("nav")
        if nav == "next":
            session["review_index"] = min(session["review_index"] + 1, len(reviews) - 1)
        elif nav == "previous":
            session["review_index"] = max(session["review_index"] - 1, 0)

        if request.form.get("action") == "Approve and Post":
            student_id = request.form.get("student_id")
            assignment_title = request.form.get("assignment_title")
            new_score = int(request.form.get("score"))
            new_feedback = request.form.get("feedback")

            matched = None
            for r in reviews:
                if r["student_id"] == student_id and r["assignment_title"] == assignment_title:
                    matched = r
                    break

            if matched:
                reviews.remove(matched)
                with open(pending_path, "w") as f:
                    json.dump(reviews, f, indent=2)

                ags_claim = launch_data.get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint")
                if ags_claim and "lineitem" in ags_claim:
                    try:
                        lineitem_url = ags_claim["lineitem"].split("?")[0] + "/scores"
                        private_key_path = os.path.join("app", "keys", "private_key.pem")
                        with open(private_key_path, "r") as f:
                            private_key = f.read()

                        oauth = OAuth1Session(
                            client_key=os.getenv("CLIENT_ID"),
                            signature_method="RSA-SHA1",
                            rsa_key=private_key,
                            signature_type="auth_header"
                        )

                        score_payload = {
                            "userId": student_id,
                            "scoreGiven": new_score,
                            "scoreMaximum": 100,
                            "activityProgress": "Completed",
                            "gradingProgress": "FullyGraded",
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }

                        ags_response = oauth.post(
                            lineitem_url,
                            json=score_payload,
                            headers={"Content-Type": "application/vnd.ims.lis.v1.score+json"}
                        )
                        ags_response.raise_for_status()
                        print(f"✅ Grade approved and posted for student {student_id}.")
                    except Exception as e:
                        print("❌ Grade post failed:", str(e))

                if session["review_index"] >= len(reviews):
                    session["review_index"] = max(0, len(reviews) - 1)

    # ✅ Load the current review
    current_review = None
    if reviews:
        review_index = session.get("review_index", 0)
        review_index = max(0, min(review_index, len(reviews) - 1))
        current_review = reviews[review_index]

    return render_template("review_feedback.html", current_review=current_review)

@lti.route("/post-grade", methods=["POST"])
def post_grade():
    score = int(request.form.get("score", 0))
    feedback = request.form.get("feedback", "")
    launch_data = session.get("launch_data", {})
    ags_claim = launch_data.get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint")

    if ags_claim and "lineitem" in ags_claim:
        try:
            lineitem_url = ags_claim["lineitem"].split("?")[0] + "/scores"
            private_key_path = os.path.join("app", "keys", "private_key.pem")
            with open(private_key_path, "r") as f:
                private_key = f.read()

            oauth = OAuth1Session(
                client_key=os.getenv("CLIENT_ID"),
                signature_method="RSA-SHA1",
                rsa_key=private_key,
                signature_type="auth_header"
            )

            score_payload = {
                "userId": launch_data.get("sub"),
                "scoreGiven": score,
                "scoreMaximum": 100,
                "activityProgress": "Completed",
                "gradingProgress": "FullyGraded",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            ags_response = oauth.post(
                lineitem_url,
                json=score_payload,
                headers={"Content-Type": "application/vnd.ims.lis.v1.score+json"}
            )
            ags_response.raise_for_status()
            print("✅ Manual grade posted by instructor.")
        except Exception as e:
            print("❌ Instructor grade post failed:", str(e))

    return render_template(
    "feedback.html",
    score=score,
    feedback=feedback,
    rubric_total_points=rubric_total_points,
    user_roles=launch_data.get("https://purl.imsglobal.org/spec/lti/claim/roles", [])
)
