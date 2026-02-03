"""
Email Service using Microsoft Graph API
Sends transactional emails for verification and password reset
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Email configuration
SENDER_EMAIL = "support@asgardsolution.io"
APP_NAME = "JarlPM"


class EmailService:
    """Service for sending transactional emails via Microsoft Graph"""
    
    def __init__(self):
        self.client_id = os.environ.get("MICROSOFT_GRAPH_CLIENT_ID")
        self.client_secret = os.environ.get("MICROSOFT_GRAPH_CLIENT_SECRET")
        self.tenant_id = os.environ.get("MICROSOFT_GRAPH_TENANT_ID")
        self.sender_email = SENDER_EMAIL
        self._client = None
    
    def is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return all([self.client_id, self.client_secret, self.tenant_id])
    
    async def _get_client(self):
        """Get or create Microsoft Graph client"""
        if self._client is None:
            from azure.identity.aio import ClientSecretCredential
            from msgraph import GraphServiceClient
            
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            self._client = GraphServiceClient(credentials=credential)
        return self._client
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via Microsoft Graph API
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body content
            text_content: Plain text fallback (optional)
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning("Email service not configured - skipping email send")
            return False
        
        try:
            from msgraph.generated.models.message import Message
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.recipient import Recipient
            from msgraph.generated.models.email_address import EmailAddress
            from msgraph.generated.models.body_type import BodyType
            from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
            
            client = await self._get_client()
            
            # Create the message
            message = Message(
                subject=subject,
                body=ItemBody(
                    content_type=BodyType.Html,
                    content=html_content
                ),
                to_recipients=[
                    Recipient(
                        email_address=EmailAddress(address=to_email)
                    )
                ]
            )
            
            # Create send mail request
            request_body = SendMailPostRequestBody(
                message=message,
                save_to_sent_items=True
            )
            
            # Send email using the sender's mailbox
            await client.users.by_user_id(self.sender_email).send_mail.post(request_body)
            
            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def send_verification_email(
        self,
        to_email: str,
        user_name: str,
        verification_token: str,
        base_url: str
    ) -> bool:
        """Send email verification email"""
        verification_link = f"{base_url}/verify-email?token={verification_token}"
        
        subject = f"Verify your {APP_NAME} email address"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: #fff; margin: 0; font-size: 28px;">{APP_NAME}</h1>
    </div>
    <div style="background: #fff; padding: 30px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="color: #2d3748; margin-top: 0;">Verify your email address</h2>
        <p>Hi {user_name},</p>
        <p>Thank you for signing up for {APP_NAME}! Please verify your email address by clicking the button below:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_link}" style="background: #4a5568; color: #fff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">Verify Email Address</a>
        </div>
        <p style="color: #718096; font-size: 14px;">Or copy and paste this link into your browser:</p>
        <p style="background: #f7fafc; padding: 12px; border-radius: 6px; word-break: break-all; font-size: 13px; color: #4a5568;">{verification_link}</p>
        <p style="color: #718096; font-size: 14px;">This link will expire in 24 hours.</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
        <p style="color: #a0aec0; font-size: 12px; margin: 0;">If you didn't create an account with {APP_NAME}, you can safely ignore this email.</p>
    </div>
</body>
</html>
"""
        
        return await self.send_email(to_email, subject, html_content)
    
    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_token: str,
        base_url: str
    ) -> bool:
        """Send password reset email"""
        reset_link = f"{base_url}/reset-password?token={reset_token}"
        
        subject = f"Reset your {APP_NAME} password"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: #fff; margin: 0; font-size: 28px;">{APP_NAME}</h1>
    </div>
    <div style="background: #fff; padding: 30px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="color: #2d3748; margin-top: 0;">Reset your password</h2>
        <p>Hi {user_name},</p>
        <p>We received a request to reset your {APP_NAME} password. Click the button below to create a new password:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background: #e53e3e; color: #fff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">Reset Password</a>
        </div>
        <p style="color: #718096; font-size: 14px;">Or copy and paste this link into your browser:</p>
        <p style="background: #f7fafc; padding: 12px; border-radius: 6px; word-break: break-all; font-size: 13px; color: #4a5568;">{reset_link}</p>
        <div style="background: #fff5f5; border: 1px solid #feb2b2; border-radius: 8px; padding: 16px; margin: 20px 0;">
            <p style="color: #c53030; margin: 0; font-size: 14px;"><strong>⚠️ This link expires in 1 hour</strong></p>
        </div>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
        <p style="color: #a0aec0; font-size: 12px; margin: 0;">If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
    </div>
</body>
</html>
"""
        
        return await self.send_email(to_email, subject, html_content)


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get the email service singleton"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
