from docx import Document

def convert_docx_to_html_with_styles(docx_path):
    try:
        doc = Document(docx_path)
        html = ""
        for para in doc.paragraphs:
            html += f"<p>{para.text}</p>\n"
        return html
    except Exception as e:
        return f"<div style='color: red;'>Error reading DOCX: {e}</div>"
