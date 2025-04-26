def build_grading_prompt(grading_difficulty="medium"):
    base_instructions = """
    Always grade based on student content only, ignoring any layout, formatting, or table structures. 
    If text appears inside tables, headers, or other formatting, treat it as normal text.
    Look for student effort and intent when identifying answers. 
    Only mark answers missing if there is absolutely no text for a question.
    Be forgiving with minor formatting, extra spaces, or misalignments.
    """

    difficulty_instructions = ""

    if grading_difficulty == "easy":
        difficulty_instructions = """
        Grade generously. Award partial or full credit for attempted answers. 
        Be positive and encouraging in your feedback. Avoid harsh penalties for minor mistakes.
        """

    elif grading_difficulty == "medium":
        difficulty_instructions = """
        Grade according to normal academic expectations. 
        Award partial credit where deserved. Provide balanced feedback noting strengths and areas to improve.
        """

    elif grading_difficulty == "hard":
        difficulty_instructions = """
        Grade strictly according to the rubric. Expect clear, thorough, and complete answers. 
        Deduct points for missing elements, unclear writing, or grammar errors if they impact quality.
        Provide detailed feedback explaining deductions.
        """

    # Combine both parts
    final_prompt = base_instructions.strip() + "\n\n" + difficulty_instructions.strip()
    return final_prompt
