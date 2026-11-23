"""SMTP delivery for one-time CFDT JURIS invitations."""
from email.message import EmailMessage
import smtplib
import ssl


def send_invitation_email(host: str, port: int, username: str, password: str,
                          sender: str, recipient: str, organization: str,
                          role: str, invitation_url: str, use_starttls: bool = True) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"Invitation à rejoindre {organization} — CFDT JURIS"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        f"Bonjour,\n\nVous êtes invité(e) à rejoindre l'espace {organization} sur CFDT JURIS.\n"
        f"Rôle proposé : {role}.\n\nPour accepter cette invitation, créez votre compte ou connectez-vous, puis ouvrez :\n{invitation_url}\n\n"
        "Ce lien est personnel, à usage unique et expire sous 7 jours. Si vous n'attendiez pas cette invitation, ignorez ce message.\n"
    )
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=10) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if use_starttls:
                smtp.starttls(context=context)
                smtp.ehlo()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
