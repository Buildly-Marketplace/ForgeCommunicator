"""
Email service for sending transactional emails.

Supports multiple providers via SMTP or API-based services.
Defaults to console logging in development if no SMTP configured.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service supporting SMTP and API-based providers."""
    
    def __init__(self):
        self.smtp_host = getattr(settings, 'smtp_host', None)
        self.smtp_port = getattr(settings, 'smtp_port', 587)
        self.smtp_username = getattr(settings, 'smtp_username', None)
        self.smtp_password = getattr(settings, 'smtp_password', None)
        self.smtp_use_tls = getattr(settings, 'smtp_use_tls', True)
        self.from_email = getattr(settings, 'smtp_from_email', settings.brand_support_email)
        self.from_name = getattr(settings, 'smtp_from_name', settings.brand_name)
        
        # API-based provider settings (Sendgrid, Mailgun, etc.)
        self.sendgrid_api_key = getattr(settings, 'sendgrid_api_key', None)
        self.mailgun_api_key = getattr(settings, 'mailgun_api_key', None)
        self.mailgun_domain = getattr(settings, 'mailgun_domain', None)
    
    @property
    def is_configured(self) -> bool:
        """Check if any email provider is configured."""
        return bool(
            self.smtp_host or
            self.sendgrid_api_key or
            (self.mailgun_api_key and self.mailgun_domain)
        )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
        cc_emails: list[str] | None = None,
        reply_to: str | None = None,
    ) -> bool:
        """
        Send an email using the configured provider.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML body of the email
            text_content: Plain text fallback (optional, will be generated if not provided)
            cc_emails: List of CC recipients
            reply_to: Reply-to email address
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not text_content:
            # Generate plain text from HTML (basic conversion)
            import re
            text_content = re.sub(r'<[^>]+>', '', html_content)
            text_content = text_content.replace('&nbsp;', ' ')
            text_content = re.sub(r'\s+', ' ', text_content).strip()
        
        # Try providers in order of preference
        if self.sendgrid_api_key:
            return await self._send_via_sendgrid(
                to_email, subject, html_content, text_content, cc_emails, reply_to
            )
        
        if self.mailgun_api_key and self.mailgun_domain:
            return await self._send_via_mailgun(
                to_email, subject, html_content, text_content, cc_emails, reply_to
            )
        
        if self.smtp_host:
            return await self._send_via_smtp(
                to_email, subject, html_content, text_content, cc_emails, reply_to
            )
        
        # No provider configured - log to console in development
        logger.warning(
            "No email provider configured. Email would have been sent:\n"
            f"  To: {to_email}\n"
            f"  CC: {cc_emails or 'None'}\n"
            f"  Subject: {subject}\n"
            f"  Preview: {text_content[:200]}..."
        )
        return False
    
    async def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        cc_emails: list[str] | None,
        reply_to: str | None,
    ) -> bool:
        """Send email via SMTP."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            if reply_to:
                msg['Reply-To'] = reply_to
            
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Run SMTP in thread pool to not block async
            def send_sync():
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_use_tls:
                        server.starttls()
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    
                    recipients = [to_email]
                    if cc_emails:
                        recipients.extend(cc_emails)
                    
                    server.sendmail(self.from_email, recipients, msg.as_string())
            
            await asyncio.get_event_loop().run_in_executor(None, send_sync)
            logger.info(f"Email sent via SMTP to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False
    
    async def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        cc_emails: list[str] | None,
        reply_to: str | None,
    ) -> bool:
        """Send email via SendGrid API."""
        try:
            payload: dict[str, Any] = {
                "personalizations": [{
                    "to": [{"email": to_email}],
                }],
                "from": {
                    "email": self.from_email,
                    "name": self.from_name,
                },
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": text_content},
                    {"type": "text/html", "value": html_content},
                ],
            }
            
            if cc_emails:
                payload["personalizations"][0]["cc"] = [{"email": e} for e in cc_emails]
            
            if reply_to:
                payload["reply_to"] = {"email": reply_to}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.sendgrid_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                
                if response.status_code in (200, 202):
                    logger.info(f"Email sent via SendGrid to {to_email}")
                    return True
                else:
                    logger.error(f"SendGrid error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send email via SendGrid: {e}")
            return False
    
    async def _send_via_mailgun(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        cc_emails: list[str] | None,
        reply_to: str | None,
    ) -> bool:
        """Send email via Mailgun API."""
        try:
            data = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": to_email,
                "subject": subject,
                "text": text_content,
                "html": html_content,
            }
            
            if cc_emails:
                data["cc"] = ', '.join(cc_emails)
            
            if reply_to:
                data["h:Reply-To"] = reply_to
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.mailgun.net/v3/{self.mailgun_domain}/messages",
                    auth=("api", self.mailgun_api_key),
                    data=data,
                )
                
                if response.status_code == 200:
                    logger.info(f"Email sent via Mailgun to {to_email}")
                    return True
                else:
                    logger.error(f"Mailgun error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send email via Mailgun: {e}")
            return False


# Global email service instance
email_service = EmailService()


async def send_invite_email(
    to_email: str,
    invite_token: str,
    workspace_name: str,
    inviter_name: str,
    cc_emails: list[str] | None = None,
) -> bool:
    """
    Send a workspace invitation email.
    
    Args:
        to_email: Email of the person being invited
        invite_token: The invite token for the URL
        workspace_name: Name of the workspace
        inviter_name: Name of the person sending the invite
        cc_emails: Optional list of emails to CC
        
    Returns:
        True if email was sent successfully
    """
    from app.brand import brand
    
    base_url = getattr(settings, 'base_url', 'http://localhost:8000')
    invite_url = f"{base_url}/invites/{invite_token}"
    
    subject = f"You've been invited to {workspace_name} on {brand.name}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-size: 24px; font-weight: bold; color: {settings.brand_primary_color}; }}
            .content {{ background: #f8fafc; border-radius: 8px; padding: 30px; margin-bottom: 30px; }}
            .button {{ display: inline-block; background: {settings.brand_primary_color}; color: white; text-decoration: none; padding: 14px 28px; border-radius: 6px; font-weight: 500; }}
            .button:hover {{ background: #2563eb; }}
            .footer {{ text-align: center; font-size: 12px; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">{brand.name}</div>
            </div>
            <div class="content">
                <h2>You're invited!</h2>
                <p><strong>{inviter_name}</strong> has invited you to join <strong>{workspace_name}</strong> on {brand.name}.</p>
                <p>{brand.name} is a team communication platform that helps you collaborate with your team through channels, direct messages, and more.</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{invite_url}" class="button">Accept Invitation</a>
                </p>
                <p style="font-size: 13px; color: #64748b;">
                    Or copy and paste this link into your browser:<br>
                    <a href="{invite_url}" style="color: {settings.brand_primary_color};">{invite_url}</a>
                </p>
                <p style="font-size: 13px; color: #64748b;">
                    This invitation will expire in 7 days. If you don't want to join this workspace, you can safely ignore this email.
                </p>
            </div>
            <div class="footer">
                <p>© {brand.company} | {brand.support_email}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return await email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        cc_emails=cc_emails,
    )
