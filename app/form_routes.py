from flask import Blueprint, render_template, request, redirect, url_for, session
import json
import os

form_bp = Blueprint('form', __name__)

# Load the form schema from file
def load_form_schema(form_id):
    schema_path = os.path.join('data', 'form_schemas', f'{form_id}.json')
    with open(schema_path, 'r') as f:
        return json.load(f)

@form_bp.route('/form/<assignment_id>', methods=['GET'])
def student_form(assignment_id):
    schema = load_form_schema('n400_part1_part2')  # Static for now
    # Later: load student data from Supabase
    return render_template('student_form.html', schema=schema, assignment_id=assignment_id)

@form_bp.route('/form/save/<assignment_id>', methods=['POST'])
def save_form(assignment_id):
    form_data = request.form.to_dict()
    # TODO: Save form_data to Supabase under this user + assignment_id
    return 'Saved successfully', 200

@form_bp.route('/form/submit/<assignment_id>', methods=['POST'])
def submit_form(assignment_id):
    form_data = request.form.to_dict()
    # TODO: Save + mark as submitted in Supabase
    return 'Submitted successfully', 200
