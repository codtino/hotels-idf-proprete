"""Envoi d'un e-mail récapitulatif des nouveaux avis (SMTP, ex. Gmail + mot de passe d'application)."""
import html
import os
import smtplib
import ssl
from email.message import EmailMessage

SOURCES = {"booking": "Booking", "tripadvisor": "TripAdvisor"}


def smtp_configured():
    return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"))


def build_email(new_reviews, hotels, url):
    count = len(new_reviews)
    subject = f"{count} nouvel avis propreté" if count == 1 else f"{count} nouveaux avis propreté"
    subject += " – hôtels Île-de-France"

    lines, blocks = [], []
    for r in new_reviews[:50]:
        h = hotels.get(r["hotelKey"], {})
        rooms = f"{h['rooms']} ch." if h.get("rooms") else "taille inconnue"
        head = f"{h.get('name', r.get('hotelName', '?'))} ({h.get('city', '')}, {rooms}) – {SOURCES[r['source']]} {r['ratingLabel']}"
        quote = " … ".join(r["excerpts"][:2])
        lines.append(f"• {head}\n  {', '.join(r['categories'])}\n  « {quote} »\n  {r.get('url', '')}\n")
        blocks.append(
            f"<li style='margin-bottom:14px'><b>{html.escape(head)}</b><br>"
            f"<span style='color:#a33'>{html.escape(', '.join(r['categories']))}</span><br>"
            f"<i>« {html.escape(quote)} »</i><br>"
            + (f"<a href='{html.escape(r['url'])}'>Voir l'avis</a>" if r.get("url") else "")
            + "</li>"
        )
    more = f"\n… et {count - 50} autres." if count > 50 else ""
    footer = f"\nTous les avis : {url}" if url else ""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg.set_content("\n".join(lines) + more + footer)
    msg.add_alternative(
        f"<h2 style='font-family:sans-serif'>{html.escape(subject)}</h2>"
        f"<ul style='font-family:sans-serif;font-size:14px'>{''.join(blocks)}</ul>"
        + (f"<p>{html.escape(more)}</p>" if more else "")
        + (f"<p><a href='{html.escape(url)}'>Ouvrir le tableau de veille</a></p>" if url else ""),
        subtype="html",
    )
    return msg


def send_email(new_reviews, hotels, url):
    if not smtp_configured():
        print("SMTP non configuré : pas d'e-mail envoyé.")
        return False
    msg = build_email(new_reviews, hotels, url)
    msg["From"] = os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"]
    msg["To"] = os.environ["MAIL_TO"]
    port = int(os.environ.get("SMTP_PORT") or 465)
    ctx = ssl.create_default_context()
    if port == 465:
        server = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ctx, timeout=60)
    else:
        server = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=60)
        server.starttls(context=ctx)
    with server:
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(msg)
    print(f"E-mail envoyé à {msg['To']} ({len(new_reviews)} avis).")
    return True
