from datetime import datetime
from flask import current_app
from flask_mail import Message
from inventory.extensions import db, mail
from inventory.utils.email_tokens import generate_email_verification_token


class EmailService:
    @staticmethod
    def send_verification_email(user):
        token = generate_email_verification_token(user.email)
        confirm_url = f"{current_app.config['BASE_URL']}/verify-email/{token}"

        msg = Message(
            subject="Confirm your WarePulse email",
            recipients=[user.email],
            sender=current_app.config["MAIL_DEFAULT_SENDER"]
        )

        msg.body = f"""Hello {user.username},

Please confirm your email by opening this link:

{confirm_url}

If you did not request this, ignore this email.
"""

        msg.html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #222;">
            <h2>Confirm your WarePulse email</h2>
            <p>Hello {user.username},</p>
            <p>Please confirm your email by clicking the button below:</p>
            <p>
              <a href="{confirm_url}" style="display:inline-block;padding:12px 20px;background:#0d6efd;color:#ffffff;text-decoration:none;border-radius:6px;">
                Confirm Email
              </a>
            </p>
            <p>Or open this link manually:</p>
            <p><a href="{confirm_url}">{confirm_url}</a></p>
            <p>If you did not request this, ignore this email.</p>
          </body>
        </html>
        """

        mail.send(msg)
        user.verification_sent_at = datetime.utcnow()
        db.session.commit()