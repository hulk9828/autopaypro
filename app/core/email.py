import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False
) -> bool:
    """
    Send an email asynchronously.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        is_html: Whether the body is HTML format
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
        message["To"] = to_email
        message["Subject"] = subject

        # Add body to email
        if is_html:
            message.attach(MIMEText(body, "html"))
        else:
            message.attach(MIMEText(body, "plain"))

        # Send email
        # Port 465 uses SSL/TLS, port 587 uses STARTTLS
        if settings.MAIL_PORT == 465:
            # SSL/TLS connection for port 465
            context = ssl.create_default_context()
            await aiosmtplib.send(
                message,
                hostname=settings.MAIL_SERVER,
                port=settings.MAIL_PORT,
                username=settings.MAIL_USERNAME,
                password=settings.MAIL_PASSWORD,
                use_tls=True,
                tls_context=context,
            )
        else:
            # STARTTLS connection (for port 587)
            await aiosmtplib.send(
                message,
                hostname=settings.MAIL_SERVER,
                port=settings.MAIL_PORT,
                username=settings.MAIL_USERNAME,
                password=settings.MAIL_PASSWORD,
                start_tls=True,
            )
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
        return False


async def send_customer_password_email(
    customer_email: str,
    customer_name: str,
    password: str
) -> bool:
    """
    Send password email to a newly created customer.
    
    Args:
        customer_email: Customer's email address
        customer_name: Customer's full name
        password: Generated password
    
    Returns:
        True if email sent successfully, False otherwise
    """
    subject = "Welcome to AutoLoanPro - Your Account Credentials"
    
    body = f"""
Dear {customer_name},

Welcome to AutoLoanPro! Your account has been successfully created.

Your login credentials are:
Email: {customer_email}
Password: {password}

Please keep this password secure and change it after your first login.

If you have any questions, please don't hesitate to contact our support team.

Best regards,
AutoLoanPro Team
"""
    
    html_body = f"""
<html>
  <body>
    <h2>Welcome to AutoLoanPro!</h2>
    <p>Dear {customer_name},</p>
    <p>Your account has been successfully created.</p>
    <p><strong>Your login credentials are:</strong></p>
    <ul>
      <li><strong>Email:</strong> {customer_email}</li>
      <li><strong>Password:</strong> {password}</li>
    </ul>
    <p><em>Please keep this password secure and change it after your first login.</em></p>
    <p>If you have any questions, please don't hesitate to contact our support team.</p>
    <p>Best regards,<br>AutoLoanPro Team</p>
  </body>
</html>
"""
    
    return await send_email(
        to_email=customer_email,
        subject=subject,
        body=html_body,
        is_html=True
    )


async def send_otp_email(
    customer_email: str,
    customer_name: str,
    otp_code: str
) -> bool:
    """
    Send OTP email to customer for password reset.
    
    Args:
        customer_email: Customer's email address
        customer_name: Customer's full name
        otp_code: Generated OTP code
    
    Returns:
        True if email sent successfully, False otherwise
    """
    subject = "AutoLoanPro - Password Reset OTP"
    
    body = f"""
Dear {customer_name},

You have requested to reset your password. Please use the following OTP code to proceed:

OTP Code: {otp_code}

This OTP will expire in 10 minutes. If you did not request this password reset, please ignore this email.

If you have any questions, please don't hesitate to contact our support team.

Best regards,
AutoLoanPro Team
"""
    
    html_body = f"""
<html>
  <body>
    <h2>Password Reset Request</h2>
    <p>Dear {customer_name},</p>
    <p>You have requested to reset your password. Please use the following OTP code to proceed:</p>
    <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
      <h1 style="color: #333; font-size: 32px; letter-spacing: 5px; margin: 0;">{otp_code}</h1>
    </div>
    <p><em>This OTP will expire in 10 minutes.</em></p>
    <p>If you did not request this password reset, please ignore this email.</p>
    <p>If you have any questions, please don't hesitate to contact our support team.</p>
    <p>Best regards,<br>AutoLoanPro Team</p>
  </body>
</html>
"""
    
    return await send_email(
        to_email=customer_email,
        subject=subject,
        body=html_body,
        is_html=True
    )


async def send_overdue_reminder_email(
    customer_email: str,
    customer_name: str,
    overdue_count: int,
    total_overdue_amount: float,
    *,
    subject: str | None = None,
    body_override: str | None = None,
) -> bool:
    """
    Send overdue payment reminder email to a customer.
    If subject or body_override are provided, use them; otherwise use default.
    """
    default_subject = "AutoLoanPro - Overdue Payment Reminder"
    if subject is None:
        subject = default_subject
    if body_override is not None:
        html_body = body_override
    else:
        installments = "installment" if overdue_count == 1 else "installments"
        html_body = f"""
<html>
  <body>
    <h2>Overdue Payment Reminder</h2>
    <p>Dear {customer_name},</p>
    <p>You have <strong>{overdue_count}</strong> overdue {installments} totaling <strong>${total_overdue_amount:.2f}</strong>.</p>
    <p>Please log in to your account and make a payment at your earliest convenience to avoid any additional fees or impact on your account.</p>
    <p>If you have already made a payment, please disregard this message.</p>
    <p>If you have any questions, please contact our support team.</p>
    <p>Best regards,<br>AutoLoanPro Team</p>
  </body>
</html>
"""
    return await send_email(
        to_email=customer_email,
        subject=subject,
        body=html_body,
        is_html=True,
    )
