from flask import current_app
from itsdangerous import URLSafeTimedSerializer


def get_email_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_email_verification_token(email):
    serializer = get_email_serializer()
    return serializer.dumps(email, salt=current_app.config["SECURITY_PASSWORD_SALT"])


def verify_email_verification_token(token, max_age=3600):
    serializer = get_email_serializer()
    return serializer.loads(
        token,
        salt=current_app.config["SECURITY_PASSWORD_SALT"],
        max_age=max_age
    )