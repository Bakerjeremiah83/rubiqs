from flask import (
    request, jsonify, redirect, Blueprint, session,
    render_template, send_file
)

from app.utils.storage import (
    store_pending_feedback,
    load_pending_feedback,
    load_all_pending_feedback
)

# Removed duplicate import of check_ai_with_gpt


import json
import os
import jwt
from jwt.algorithms import RSAAlgorithm  # Ensure this is used for decoding JWTs
import requests
from jwt.exceptions import InvalidTokenError
from docx import Document
from io import BytesIO
import openai
from datetime import datetime  # Already imported; ensure no duplicates
from requests_oauthlib import OAuth1Session
import re
from pdfminer.high_level import extract_text as extract_pdf_text
from app.utils.zerogpt_api import check_ai_with_gpt
from werkzeug.utils import secure_filename
from app.utils.storage import load_assignment_data, save_assignment_data



def load_assignment_config(assignment_title):
    rubric_index_path = os.path.join("rubrics", "rubric_index.json")
    if os.path.exists(rubric_index_path):
        with open(rubric_index_path, "r") as f:
            configs = json.load(f)
        for config in configs:
            if config["assignment_title"].strip().lower() == assignment_title.strip().lower():
                return config
    return None


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
    print("🌍 DEBUG - PLATFORM_ISS =", os.getenv("PLATFORM_ISS"))

    if not jwt_token:
        return "❌ Error: No id_token (JWT) received in launch request.", 400

    # ✅ DEBUG: Print unverified JWT ISS
    try:
        unverified = jwt.decode(jwt_token, options={"verify_signature": False})
        print("🔍 UNVERIFIED JWT ISS:", unverified.get("iss"))
        print("🔍 PLATFORM_ISS from .env:", os.getenv("PLATFORM_ISS"))
    except Exception as e:
        print("❌ Failed to decode unverified JWT:", str(e))

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
    except requests.RequestException as e:
        return f"❌ Could not fetch JWKS: {str(e)}", 400

    # ✅ DEBUG: Print before decoding with validation
    print("🧪 JWT HEADERS:", jwt.get_unverified_header(jwt_token))
    print("🧪 JWT PAYLOAD:", unverified)
    print("🧪 CLIENT_IDS from .env:", os.getenv("CLIENT_IDS"))

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

        print("JWT Issuer:", decoded.get("iss"))
        print("Expected Issuer (PLATFORM_ISS):", os.getenv("PLATFORM_ISS"))
        print("✅ JWT verified")
        print(json.dumps(decoded, indent=2))

        session["launch_data"] = json.loads(json.dumps(decoded))
        session["tool_role"] = "student"

    except (InvalidTokenError, KeyError) as e:
        return f"❌ Invalid JWT signature or missing key: {str(e)}", 400

    # ✅ Continue with render_template and persona logic
    requires_persona = False
    assignment_title = decoded.get(
        "https://purl.imsglobal.org/spec/lti/claim/resource_link", {}
    ).get("title", "").strip()

    assignment_config = load_assignment_config(assignment_title)
    requires_persona = assignment_config.get("requires_persona", False) if assignment_config else False

    return render_template(
        "launch.html",
        activity_name=assignment_title,
        user_name=decoded.get("given_name", "Student"),
        user_roles=decoded.get("https://purl.imsglobal.org/spec/lti/claim/roles", []),
        requires_persona=requires_persona
    )
@lti.route("/student-test", methods=["GET"])
def student_test_upload():
    # Simulate a student launch with mock data
    session["tool_role"] = "student"
    session["launch_data"] = {
        "https://purl.imsglobal.org/spec/lti/claim/resource_link": {
            "title": "Test Assignment"
        },
        "https://purl.imsglobal.org/spec/lti/claim/roles": ["Student"],
        "given_name": "Test User"
    }

    assignment_config = load_assignment_config("Test Assignment")

    return render_template(
        "launch.html",
        user_roles=["Student"],
        requires_persona=assignment_config.get("requires_persona", False) if assignment_config else False,
        assignment_config=assignment_config
    )


@lti.route("/grade-docx", methods=["POST"])
def grade_docx():
    print("📥 /grade-docx hit")

    file = request.files.get("file")
    persona_file = request.files.get("persona")

    if not file:
        return "❌ Assignment file is required.", 400

    try:
        filename = file.filename.lower()
        if filename.endswith(".docx"):
            doc = Document(file)
            full_text = "\n".join([para.text for para in doc.paragraphs])
        elif filename.endswith(".pdf"):
            full_text = extract_pdf_text(BytesIO(file.read()))
        else:
            return "❌ Unsupported file type.", 400

        ai_check_result = check_ai_with_gpt(full_text)
        print("🤖 AI Detection Result:", ai_check_result)

    except Exception as e:
        return f"❌ Failed to extract text: {str(e)}", 500

    reference_data = ""
    if persona_file:
        try:
            persona_filename = persona_file.filename.lower()
            if persona_filename.endswith(".docx"):
                doc = Document(persona_file)
                reference_data = "\n".join([para.text for para in doc.paragraphs])
            elif persona_filename.endswith(".pdf"):
                reference_data = extract_pdf_text(BytesIO(persona_file.read()))
        except Exception as e:
            return f"❌ Failed to extract persona file: {str(e)}", 500

    launch_data = session.get("launch_data", {})
    assignment_title = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}).get("title", "").strip()
    assignment_config = load_assignment_config(assignment_title)

    if not assignment_config:
        return f"❌ No configuration found for assignment: {assignment_title}", 400

    rubric_path = os.path.join("rubrics", assignment_config.get("rubric_file", ""))
    rubric_total_points = assignment_config.get("total_points", 100)
    grading_difficulty = assignment_config.get("grading_difficulty", "balanced")
    student_level = assignment_config.get("student_level", "college")
    feedback_tone = assignment_config.get("feedback_tone", "supportive")
    ai_notes = assignment_config.get("ai_notes", "")

    try:
        if rubric_path.endswith(".json"):
            with open(rubric_path, "r") as f:
                rubric_json = json.load(f)
            rubric_text = "\n".join([f"- {c['description']}" for c in rubric_json.get("criteria", [])])
        elif rubric_path.endswith(".docx"):
            doc = Document(rubric_path)
            rubric_text = "\n".join([para.text for para in doc.paragraphs])
        elif rubric_path.endswith(".pdf"):
            rubric_text = extract_pdf_text(rubric_path)
        else:
            rubric_text = "(Rubric text could not be loaded.)"
    except Exception as e:
        return f"❌ Failed to load rubric file: {str(e)}", 500

    prompt = f"""\nYou are a helpful AI grader.

Assignment Title: {assignment_title}
Grading Difficulty: {grading_difficulty}
Student Level: {student_level}
Feedback Tone: {feedback_tone}
Total Points: {rubric_total_points}

Rubric:
{rubric_text}
"""
    if ai_notes:
        prompt += f"\nInstructor Notes:\n{ai_notes}\n"
    if reference_data:
        prompt += f"\nReference Scenario:\n{reference_data}\n"
    prompt += f"\nStudent Submission:\n---\n{full_text}\n---\n\nReturn your response in this format:\n\nScore: <number from 0 to {rubric_total_points}>\nFeedback: <detailed, encouraging, and helpful feedback>"

    try:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt.strip()}],
            temperature=0.5,
            max_tokens=1000
        )
        output = response["choices"][0]["message"]["content"]
        score_match = re.search(r"Score:\s*(\d{1,3})", output)
        score = int(score_match.group(1)) if score_match else 0
        feedback_match = re.search(r"Feedback:\s*(.+)", output, re.DOTALL)
        feedback = feedback_match.group(1).strip() if feedback_match else output.strip()

    except openai.error.OpenAIError as e:
        return f"❌ GPT error: {str(e)}", 500

    submission_id = str(uuid.uuid4())
    submission_data = {
        "submission_id": submission_id,
        "student_id": "demo_student_001",
        "assignment_title": assignment_title,
        "timestamp": datetime.utcnow().isoformat(),
        "score": score,
        "feedback": feedback,
        "student_text": full_text,
        "ai_check_result": None
    }

    if assignment_config.get("instructor_approval"):
        store_pending_feedback(submission_id, submission_data)
        log_gpt_interaction(assignment_title, prompt, feedback, score)
        return render_template("feedback.html", score=score, feedback=feedback, rubric_total_points=rubric_total_points,
                               user_roles=session.get("launch_data", {}).get("https://purl.imsglobal.org/spec/lti/claim/roles", []),
                               pending_message="This submission requires instructor review. Your feedback is saved, and your score will be posted after approval.")

    log_gpt_interaction(assignment_title, prompt, feedback, score)
    return render_template("feedback.html", score=score, feedback=feedback, rubric_total_points=rubric_total_points,
                           user_roles=session.get("launch_data", {}).get("https://purl.imsglobal.org/spec/lti/claim/roles", []))
@lti.route("/review-feedback", methods=["GET", "POST"])
def review_feedback():
    session["tool_role"] = "instructor"  # TEMP: force instructor role for local/demo

    pending_path = os.path.join("rubrics", "pending_reviews.json")
    all_reviews = []
    if os.path.exists(pending_path):
        with open(pending_path, "r") as f:
            all_reviews = json.load(f)

    # Extract assignment titles from review queue
    assignment_titles = sorted(set(r["assignment_title"] for r in all_reviews))

    selected_title = request.form.get("assignment_title") if request.method == "POST" else None
    filtered_reviews = [r for r in all_reviews if r["assignment_title"] == selected_title] if selected_title else all_reviews

    if "review_index" not in session:
        session["review_index"] = 0

    if request.method == "POST" and "nav" in request.form:
        nav = request.form.get("nav")
        session["review_index"] = max(0, min(session["review_index"] + (1 if nav == "next" else -1), len(filtered_reviews) - 1))

    if request.method == "POST" and request.form.get("action") == "Approve and Post":
        student_id = request.form.get("student_id")
        assignment_title = request.form.get("assignment_title")
        new_score = int(request.form.get("score"))
        new_feedback = request.form.get("feedback")

        matched = next((r for r in all_reviews if r["student_id"] == student_id and r["assignment_title"] == assignment_title), None)
        if matched:
            all_reviews.remove(matched)
            ags_claim = session.get("launch_data", {}).get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint")
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
                    oauth.post(
                        lineitem_url,
                        json=score_payload,
                        headers={"Content-Type": "application/vnd.ims.lis.v1.score+json"}
                    )
                except Exception as e:
                    print("❌ Grade post failed:", str(e))

        with open(pending_path, "w") as f:
            json.dump(all_reviews, f, indent=2)
        session["review_index"] = max(0, min(session["review_index"], len(filtered_reviews) - 1))

    current_review = filtered_reviews[session.get("review_index", 0)] if filtered_reviews else None

    return render_template(
        "review_feedback.html",
        assignment_titles=assignment_titles,
        selected_title=selected_title,
        current_review=current_review
    )

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

@lti.route("/assignment-config", methods=["GET", "POST"])
def assignment_config():
    session["tool_role"] = "instructor"  # TEMP: for local testing
    tool_role = session.get("tool_role")
    if tool_role != "instructor":
        return "❌ Access denied. Instructors only.", 403

    rubric_index_path = os.path.join("rubrics", "rubric_index.json")
    rubric_folder = os.path.join("rubrics")

    if not os.path.exists(rubric_index_path):
        rubric_index = []
    else:
        with open(rubric_index_path, "r") as f:
            rubric_index = json.load(f)

    # Handle new assignment trigger
    if request.method == "GET" and request.args.get("new") == "1":
        rubric_index.insert(0, {
            "assignment_title": "",
            "rubric_file": "",
            "total_points": 100,
            "instructor_approval": False,
            "requires_persona": False,
            "faith_integration": False,
            "grading_difficulty": "balanced",
            "student_level": "college",
            "feedback_tone": "supportive",
            "ai_notes": ""
        })
        with open(rubric_index_path, "w") as f:
            json.dump(rubric_index, f, indent=2)

    if request.method == "POST":
        # 📥 Get form fields
        assignment_title = request.form.get("assignment_title", "").strip()
        total_points = int(request.form.get("total_points", "100"))
        instructor_approval = request.form.get("instructor_approval") == "on"
        requires_persona = request.form.get("requires_persona") == "on"
        faith_integration = request.form.get("faith_integration") == "on"
        grading_difficulty = request.form.get("grading_difficulty", "balanced")
        student_level = request.form.get("student_level", "college")
        feedback_tone = request.form.get("feedback_tone", "").strip()
        ai_notes = request.form.get("ai_notes", "").strip()

        rubric_file = request.files.get("rubric_file")
        saved_rubric_filename = None

        if rubric_file:
            safe_name = f"{assignment_title.lower().replace(' ', '_')}_{rubric_file.filename}"
            rubric_path = os.path.join(rubric_folder, safe_name)
            rubric_file.save(rubric_path)
            saved_rubric_filename = safe_name

        updated = False
        for entry in rubric_index:
            if entry["assignment_title"].lower() == assignment_title.lower():
                entry.update({
                    "rubric_file": saved_rubric_filename,
                    "total_points": total_points,
                    "instructor_approval": instructor_approval,
                    "requires_persona": requires_persona,
                    "faith_integration": faith_integration,
                    "grading_difficulty": grading_difficulty,
                    "student_level": student_level,
                    "feedback_tone": feedback_tone,
                    "ai_notes": ai_notes
                })
                updated = True
                break

        if not updated:
            rubric_index.append({
                "assignment_title": assignment_title,
                "rubric_file": saved_rubric_filename,
                "total_points": total_points,
                "instructor_approval": instructor_approval,
                "requires_persona": requires_persona,
                "faith_integration": faith_integration,
                "grading_difficulty": grading_difficulty,
                "student_level": student_level,
                "feedback_tone": feedback_tone,
                "ai_notes": ai_notes
            })

        with open(rubric_index_path, "w") as f:
            json.dump(rubric_index, f, indent=2)

    return render_template("assignment_config.html", rubric_index=rubric_index)

@lti.route("/test-grader", methods=["GET", "POST"])
def test_grader():
    rubric_index_path = os.path.join("rubrics", "rubric_index.json")
    rubric_index = []

    if os.path.exists(rubric_index_path):
        with open(rubric_index_path, "r") as f:
            rubric_index = json.load(f)

    selected_config = None
    gpt_prompt = ""
    gpt_feedback = ""
    gpt_score = None

    if request.method == "POST":
        assignment_title = request.form.get("assignment_title")
        submission_text = request.form.get("submission_text", "").strip()

        selected_config = next((cfg for cfg in rubric_index if cfg["assignment_title"] == assignment_title), None)

        if not selected_config:
            return "❌ No config found for that assignment.", 400

        rubric_text = ""
        rubric_path = os.path.join("rubrics", selected_config.get("rubric_file", ""))
        try:
            if rubric_path.endswith(".json"):
                with open(rubric_path, "r") as f:
                    rubric_json = json.load(f)
                rubric_text = "\n".join([f"- {c['description']}" for c in rubric_json.get("criteria", [])])
            elif rubric_path.endswith(".docx"):
                doc = Document(rubric_path)
                rubric_text = "\n".join([para.text for para in doc.paragraphs])
            elif rubric_path.endswith(".pdf"):
                rubric_text = extract_pdf_text(rubric_path)
        except:
            rubric_text = "(Unable to load rubric.)"

        prompt = f"""
You are a helpful AI grader.

Assignment Title: {assignment_title}
Grading Difficulty: {selected_config.get("grading_difficulty")}
Student Level: {selected_config.get("student_level")}
Feedback Tone: {selected_config.get("feedback_tone")}
Total Points: {selected_config.get("total_points")}

Rubric:
{rubric_text}
"""
        if selected_config.get("ai_notes"):
            prompt += f"\nInstructor Notes:\n{selected_config['ai_notes']}\n"

        prompt += f"""
Student Submission:
---
{submission_text}
---

Return your response in this format:

Score: <number from 0 to {selected_config.get("total_points")}>
Feedback: <detailed, helpful feedback>
"""

        gpt_prompt = prompt.strip()

        try:
            openai.api_key = os.getenv("OPENAI_API_KEY")
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": gpt_prompt}],
                temperature=0.5,
                max_tokens=1000
            )
            output = response["choices"][0]["message"]["content"]
            score_match = re.search(r"Score:\s*(\d{1,3})", output)
            gpt_score = int(score_match.group(1)) if score_match else None
            feedback_match = re.search(r"Feedback:\s*(.+)", output, re.DOTALL)
            gpt_feedback = feedback_match.group(1).strip() if feedback_match else output.strip()

            log_gpt_interaction(assignment_title, gpt_prompt, gpt_feedback, gpt_score)
        except Exception as e:
            gpt_feedback = f"❌ GPT error: {str(e)}"

    return render_template(
        "test_grader.html",
        rubric_index=rubric_index,
        selected_config=selected_config,
        gpt_prompt=gpt_prompt,
        gpt_feedback=gpt_feedback,
        gpt_score=gpt_score if 'gpt_score' in locals() else None
    )

@lti.route("/save-assignment", methods=["POST"])
def save_assignment():
    from werkzeug.utils import secure_filename
    import os
    rubric_index_path = os.path.join("rubrics", "rubric_index.json")

    assignment_title = request.form.get("assignment_title", "").strip()
    if not assignment_title:
        return "❌ Assignment title is required", 400

    grade_level = request.form.get("grade_level")
    grading_difficulty = request.form.get("grading_difficulty")
    requires_review = request.form.get("requires_review") == "true"
    gospel_enabled = request.form.get("gospel_enabled") == "true"
    custom_ai = request.form.get("custom_ai")

    rubric_file = request.files.get("rubric_upload")
    additional_file = request.files.get("additional_files")

    upload_dir = os.path.join("uploads", secure_filename(assignment_title))
    os.makedirs(upload_dir, exist_ok=True)

    rubric_filename = ""
    if rubric_file and rubric_file.filename:
        rubric_filename = secure_filename(rubric_file.filename)
        rubric_path = os.path.join(upload_dir, rubric_filename)
        rubric_file.save(rubric_path)

    additional_filename = ""
    if additional_file and additional_file.filename:
        additional_filename = secure_filename(additional_file.filename)
        additional_path = os.path.join(upload_dir, additional_filename)
        additional_file.save(additional_path)

    # ✅ Load existing list-based config
    rubric_index = []
    if os.path.exists(rubric_index_path):
        with open(rubric_index_path, "r") as f:
            rubric_index = json.load(f)

    # ✅ Remove existing entry with same title
    rubric_index = [entry for entry in rubric_index if entry.get("assignment_title", "").strip().lower() != assignment_title.lower()]

    # ✅ Append new config
    rubric_index.append({
        "assignment_title": assignment_title,
        "rubric_file": rubric_filename,
        "total_points": 100,
        "instructor_approval": requires_review,
        "requires_persona": False,
        "faith_integration": False,
        "grading_difficulty": grading_difficulty,
        "student_level": grade_level,
        "feedback_tone": "Supportive",
        "ai_notes": custom_ai
    })

    # ✅ Save back to rubric_index.json
    with open(rubric_index_path, "w") as f:
        json.dump(rubric_index, f, indent=2)

    print("✅ Saved assignment to rubric_index.json:", assignment_title)
    return redirect("/admin-dashboard")

@lti.route("/admin-dashboard", methods=["GET", "POST"])
def admin_dashboard():
    session["tool_role"] = "instructor"  # TEMP for local testing

    rubric_index_path = os.path.join("rubrics", "rubric_index.json")
    pending_path = os.path.join("rubrics", "pending_reviews.json")

    rubric_index = []
    if os.path.exists(rubric_index_path):
        with open(rubric_index_path, "r") as f:
            rubric_index = json.load(f)

    pending_feedback = []
    if os.path.exists(pending_path):
        with open(pending_path, "r") as f:
            pending_feedback = json.load(f)

    pending_count = len(pending_feedback)
    approved_count = sum(1 for r in rubric_index if r.get("instructor_approval"))

    return render_template("admin_dashboard.html",
                           rubric_index=rubric_index,
                           pending_feedback=pending_feedback,
                           pending_count=pending_count,
                           approved_count=approved_count)


@lti.route("/export-configs", methods=["GET"])
def export_configs():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        rubric_path = os.path.join(base_dir, "..", "rubrics", "rubric_index.json")

        print("🧾 Attempting to export:", rubric_path)

        if not os.path.exists(rubric_path):
            return "No configuration file found.", 404

        return send_file(
            rubric_path,
            mimetype="application/json",
            as_attachment=True,
            download_name="rubiqs_assignment_configs.json"
        )
    except Exception as e:
        print("❌ EXPORT ERROR:", str(e))
        return f"Export failed: {str(e)}", 500
    
@lti.route("/update-config", methods=["POST"])
def update_config():
    rubric_index_path = os.path.join("rubrics", "rubric_index.json")
    assignment_title = request.form.get("assignment_title")
    total_points = int(request.form.get("total_points", 100))
    ai_notes = request.form.get("ai_notes", "").strip()
    grading_difficulty = request.form.get("grading_difficulty", "balanced")
    student_level = request.form.get("student_level", "college")
    faith_integration = request.form.get("faith_integration") == "on"

    if not os.path.exists(rubric_index_path):
        return "Config file missing", 404

    with open(rubric_index_path, "r") as f:
        rubric_index = json.load(f)

    for entry in rubric_index:
        if entry["assignment_title"] == assignment_title:
            entry["total_points"] = total_points
            entry["ai_notes"] = ai_notes
            entry["grading_difficulty"] = grading_difficulty
            entry["student_level"] = student_level
            entry["faith_integration"] = faith_integration

    with open(rubric_index_path, "w") as f:
        json.dump(rubric_index, f, indent=2)

    return redirect("/admin-dashboard")

def log_gpt_interaction(assignment_title, prompt, feedback, score=None):
    log_path = os.path.join("logs", "prompt_logs.json")
    os.makedirs("logs", exist_ok=True)

    log_entry = {
        "assignment_title": assignment_title,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "prompt": prompt,
        "feedback": feedback,
        "score": score
    }

    logs = []
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    logs.append(log_entry)

    with open(log_path, "w") as f:
        json.dump(logs, f, indent=2)

@lti.route("/test-store")
def test_store():
    import uuid
    from datetime import datetime
    from app.utils.storage import store_pending_feedback

    submission_id = str(uuid.uuid4())
    test_data = {
        "submission_id": submission_id,
        "student_id": "tester001",
        "assignment_title": "Test Assignment",
        "timestamp": datetime.utcnow().isoformat(),
        "score": 88,
        "feedback": "Nice test work!",
        "student_text": "This is a test submission.",
        "ai_check_result": None
    }

    store_pending_feedback(submission_id, test_data)
    return f"✅ Submission saved: {submission_id}"

# In app/lti_routes.py
from flask import request, jsonify
from app.utils.zerogpt_api import check_ai_with_gpt


@lti.route('/scan-ai', methods=['POST'])
def scan_ai_text():
    if 'launch_data' not in session:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        result = check_ai_with_gpt(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"AI scan failed: {str(e)}"}), 500

@lti.route("/instructor-review", methods=["GET", "POST"])
def instructor_review():
    from app.utils.storage import load_all_pending_feedback, store_pending_feedback
    from datetime import datetime
    from flask import request, redirect, render_template, session, url_for
    import os
    import json

    reviews = load_all_pending_feedback()
    if not reviews:
        return render_template("instructor_review.html", current_review=None)

    current_review = reviews[0]
    submission_id = current_review.get("submission_id", "")

    if request.method == "POST":
        # Update score and feedback
        current_review["score"] = int(request.form.get("score"))
        current_review["feedback"] = request.form.get("feedback")
        current_review["timestamp"] = datetime.utcnow().isoformat()

        if request.form.get("action") == "Approve and Post":
            matched = next((r for r in reviews if r["submission_id"] == submission_id), None)
            if matched:
                reviews.remove(matched)
            # Optionally post grade here using AGS if needed

        # Save updated review list (or remove approved)
        store_pending_feedback(submission_id, current_review)

        return redirect(url_for("lti.instructor_review"))

    return render_template("instructor_review.html", current_review=current_review, reviews=reviews)

    if request.method == "POST":
        current_review["score"] = int(request.form.get("score"))
        current_review["feedback"] = request.form.get("feedback")
        current_review["timestamp"] = datetime.utcnow().isoformat()
        store_pending_feedback(submission_id, current_review)
        
        return redirect(url_for("lti.instructor_review"))


    return render_template("instructor_review.html", current_review=current_review)

@lti.route("/instructor-review/save-notes", methods=["POST"])
def save_notes():
    submission_id = request.form.get("submission_id")
    new_notes = request.form.get("notes", "").strip()

    if not submission_id:
        return "❌ Missing submission ID", 400

    import os
    import json
    from app.utils.storage import load_pending_feedback, store_pending_feedback
import uuid

    # Load the existing submission file
def save_notes():
    submission_id = request.form.get("submission_id")
    new_notes = request.form.get("notes", "").strip()

    if not submission_id:
        return "❌ Missing submission ID", 400

    submission = load_pending_feedback(submission_id)
    if not submission:
        return f"❌ No submission found for ID {submission_id}", 404

    # Update notes and save
    submission["notes"] = new_notes
    store_pending_feedback(submission_id, submission)

    return redirect("/admin-dashboard")