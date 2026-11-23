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


def send_auth0_migration_email(host: str, port: int, username: str, password: str,
                               sender: str, recipient: str, ticket_url: str,
                               ticket_kind: str, use_starttls: bool = True) -> None:
    """Deliver one-time Auth0 migration tickets without logging or persisting their URLs."""
    if ticket_kind not in {"password", "verification"}:
        raise ValueError("Type de ticket de migration invalide.")
    if not ticket_url.startswith("https://"):
        raise ValueError("Le ticket Auth0 doit utiliser HTTPS.")
    msg = EmailMessage()
    if ticket_kind == "password":
        msg["Subject"] = "Dikévia — sécurisation de votre accès"
        instruction = (
            "Votre compte Dikévia a été transféré vers le nouveau service de connexion. "
            "Définissez un nouveau mot de passe avec le lien personnel ci-dessous :\n"
        )
    else:
        msg["Subject"] = "Dikévia — vérification de votre adresse e-mail"
        instruction = (
            "Votre compte Dikévia a été transféré vers le nouveau service de connexion. "
            "Vérifiez votre adresse e-mail avec le lien personnel ci-dessous. "
            "Vous pourrez ensuite utiliser « Mot de passe oublié » sur l'écran de connexion.\n"
        )
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        "Bonjour,\n\n" + instruction + ticket_url
        + "\n\nCe lien est à usage unique et expire sous 24 heures. "
        "Si vous n'êtes pas à l'origine de cette opération, contactez l'administrateur de votre organisation.\n"
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
