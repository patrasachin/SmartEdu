def evaluate_mcq(student_option, correct_option, marks):
    if not student_option:
        return 0, False
    is_correct = student_option.strip().upper() == correct_option.strip().upper()
    score = marks if is_correct else 0
    return score, is_correct
