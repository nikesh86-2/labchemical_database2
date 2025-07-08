import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
from mail_config import EMAIL_USER, EMAIL_PASS


def send_grouped_email_alert(recipient_email, low_stock_items, threshold, sender_email, sender_password, smtp_server,
                             smtp_port):
    subject = "Low Stock Alert: Multiple Chemicals Below Threshold"

    body = "The following chemicals are below the specified threshold:\n\n"
    for item in low_stock_items:
        body += (
            f"- {item['name']}\n"
            f"  Current Quantity: {item['quantity']}\n"
            f"  Threshold: {threshold}\n\n"
        )
    body += "Please reorder them as soon as possible."

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            #server.set_debuglevel(1)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print("Grouped email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")


def check_low_stock_and_alert(db_uri, threshold=0):
    low_stock_items = []

    try:
        conn = sqlite3.connect(db_uri, uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name, quantity FROM chemicals")
        rows = cursor.fetchall()
        conn.close()

        for name, quantity in rows:
            if quantity <= threshold:
                low_stock_items.append({
                    "name": name,
                    "quantity": quantity
                })

        # Send one email if any low stock items are found
        if low_stock_items:
            if not EMAIL_USER or not EMAIL_PASS:
                print("Missing credentials. Cannot proceed with email.")
                exit(1)

            send_grouped_email_alert(
                recipient_email="nikeshpatel9@gmail.com",
                low_stock_items=low_stock_items,
                threshold=threshold,
                sender_email=EMAIL_USER,
                sender_password=EMAIL_PASS,
                smtp_server="smtp.gmail.com",  # or "smtp.office365.com"
                smtp_port=587
            )

      #      print(f"email attempted")
    except Exception as e:
        print(f"Database error: {e}")