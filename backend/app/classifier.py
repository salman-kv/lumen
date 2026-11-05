"""System 1 decision #1 (Classification): what kind of question is this?

A tiny logistic-regression model on top of sentence embeddings, trained at startup on seed examples.
No LLM involved: it runs in milliseconds and is fully deterministic.
"""
import threading

import numpy as np
from sklearn.linear_model import LogisticRegression

from . import models_s1

SEED = {
    "eligibility": [
        "Am I eligible for the scholarship if I am in my second year with a 3.6 GPA?",
        "Can I qualify for the grant given my GPA and my current awards?",
        "Do I meet the requirements for remote work with 8 months of service?",
        "Would I be allowed to take this leave if I have worked here for a year?",
        "I am a third year student with a 3.2 GPA, do I qualify?",
        "Does my situation qualify me for the benefit?",
        "I have a sports scholarship already, can I still get the merit scholarship?",
        "Can I get approval for a 900 dollar expense without manager approval?",
        "Am I entitled to the allowance if I joined six months ago?",
        "Given my GPA of 3.4 and first year status, will I be accepted into the program?",
    ],
    "comparison": [
        "What is the difference between the merit and the sports scholarship?",
        "Compare sick leave and annual leave.",
        "Which is better, option A or option B?",
        "How does the merit scholarship differ from the need-based grant?",
        "Merit scholarship versus sports scholarship, which has a higher amount?",
        "Compare the remote work policy with the hybrid policy.",
        "What are the differences between full-time and part-time fees?",
        "Is leave type X more generous than leave type Y?",
    ],
    "procedural": [
        "How do I apply for the scholarship?",
        "What are the steps to request annual leave?",
        "What is the process for submitting an expense claim?",
        "How can I appeal a decision?",
        "Where do I submit the application form?",
        "What documents do I need to submit and how?",
        "How do I reset my enrolment or register for a course?",
        "What should I do to request remote work?",
    ],
    "policy": [
        "What is the policy on late fee payments?",
        "What does the policy say about carrying over unused leave?",
        "What is the refund policy?",
        "Explain the attendance policy.",
        "What are the rules about working from home?",
        "Tell me about the dress code policy.",
        "What are the grading rules for exams?",
        "What does the expense policy cover?",
    ],
    "direct_info": [
        "What is the application deadline?",
        "How much is the tuition fee?",
        "How many days of annual leave do employees get?",
        "Who is the head of the admissions office?",
        "What is the amount of the merit scholarship?",
        "When does the semester start?",
        "What is the maximum remote work days per week?",
        "What is the contact email for support?",
    ],
}

_model = None
_lock = threading.Lock()


def _train():
    X, y = [], []
    for label, qs in SEED.items():
        X.append(models_s1.embed(qs))
        y += [label] * len(qs)
    clf = LogisticRegression(C=8.0, max_iter=1000)
    clf.fit(np.vstack(X), y)
    return clf


def classify(question: str) -> tuple[str, float]:
    global _model
    with _lock:
        if _model is None:
            _model = _train()
    v = models_s1.embed([question])
    probs = _model.predict_proba(v)[0]
    i = int(np.argmax(probs))
    return str(_model.classes_[i]), float(probs[i])


def reset():
    global _model
    _model = None
