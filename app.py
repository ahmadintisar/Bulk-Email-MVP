from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional
from bulk_email_sender import BulkEmailSender
from sendgrid_analytics import SendGridAnalytics
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

class EmailForm(FlaskForm):
    recipients = TextAreaField('Recipients', validators=[Optional()])
    excel_file = FileField('Upload File', validators=[
        FileAllowed(['xlsx', 'xls', 'csv'], 'Only Excel and CSV files are allowed!')
    ])
    subject = StringField('Subject', validators=[DataRequired()])
    custom_message = TextAreaField('Custom Message', validators=[Optional()])
    submit = SubmitField('Send Emails')

def extract_emails_from_file(file):
    try:
        # Get file extension
        filename = file.filename
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        # Read file based on extension
        if file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(file)
        elif file_ext == 'csv':
            # Try different encodings for CSV
            try:
                df = pd.read_csv(file)
            except UnicodeDecodeError:
                file.seek(0)  # Reset file pointer
                df = pd.read_csv(file, encoding='latin1')
        else:
            raise ValueError("Unsupported file format")
        
        # Convert column names to lowercase for case-insensitive matching
        df.columns = df.columns.str.lower()
        
        # Look for columns that might contain email addresses
        email_columns = []
        email_variations = ['email', 'e-mail', 'mail', 'email address', 'emailaddress']
        
        # First, look for exact matches
        for col in df.columns:
            if any(variation in col for variation in email_variations):
                email_columns.append(col)
        
        # If no email columns found, try to find columns containing email addresses
        if not email_columns:
            all_emails = []
            for col in df.columns:
                # Convert column to string and find email-like patterns
                emails = df[col].astype(str).str.extractall(r'[\w\.-]+@[\w\.-]+\.\w+')[0].unique()
                if len(emails) > 0:  # If emails found in this column
                    all_emails.extend(emails)
            return list(set(all_emails))  # Remove duplicates
        
        # If email columns are found, use them
        emails = []
        for col in email_columns:
            # Clean the email addresses
            col_emails = df[col].dropna().astype(str).str.strip()
            # Remove any non-email entries
            valid_emails = col_emails[col_emails.str.contains(r'^[\w\.-]+@[\w\.-]+\.\w+$')]
            emails.extend(valid_emails.tolist())
        
        return list(set(emails))  # Remove duplicates
    except Exception as e:
        raise ValueError(f"Error processing file: {str(e)}")

def get_email_template(custom_message=None):
    """Get the email template with optional custom message."""
    template_path = os.path.join('templates', 'email_template.html')
    try:
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Replace custom message placeholder if provided
        if custom_message:
            template = template.replace('{{custom_message}}', custom_message)
        else:
            template = template.replace('{{custom_message}}', '')
        
        return template
    except Exception as e:
        logger.error(f"Error reading email template: {str(e)}")
        # Fallback to a basic template if the file can't be read
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2E7D32;">Clean Earth Renewables</h2>
                    <div style="margin: 20px 0;">
                        {custom_message or ''}
                    </div>
                    <hr style="border: 1px solid #eee;">
                    <p style="color: #666; font-size: 12px;">
                        This email was sent from Clean Earth Renewables. Please do not reply to this email.
                    </p>
                </div>
            </body>
        </html>
        """

@app.route('/', methods=['GET', 'POST'])
def index():
    form = EmailForm()
    if form.validate_on_submit():
        try:
            # Get recipients from either text area or file
            recipients = []
            if form.recipients.data:
                recipients.extend([email.strip() for email in form.recipients.data.split('\n') if email.strip()])
            
            if form.excel_file.data:
                file_emails = extract_emails_from_file(form.excel_file.data)
                recipients.extend(file_emails)
            
            if not recipients:
                flash('Please provide recipients either in the text area or upload a file.', 'error')
                return redirect(url_for('index'))
            
            # Remove duplicates and validate emails
            recipients = list(set(recipients))
            invalid_emails = [email for email in recipients if not '@' in email]
            if invalid_emails:
                flash(f'Invalid email addresses found: {", ".join(invalid_emails)}', 'error')
                return redirect(url_for('index'))
            
            # Use the verified sender email
            sender_email = "origination@clean-earth.org"
            
            # Send emails
            sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
            from_email = Email(sender_email, "Clean Earth Renewables")
            
            # Get email template with custom message
            email_content = get_email_template(form.custom_message.data)
            
            success_count = 0
            failed_recipients = []
            
            for recipient in recipients:
                to_email = To(recipient)
                subject = form.subject.data
                content = Content("text/html", email_content)
                mail = Mail(from_email, to_email, subject, content)
                try:
                    response = sg.send(mail)
                    if response.status_code == 202:
                        success_count += 1
                        logger.debug(f"Email sent to {recipient}: {response.status_code}")
                    else:
                        failed_recipients.append(f"{recipient} (Status: {response.status_code})")
                        logger.error(f"Failed to send email to {recipient}: {response.status_code}")
                except Exception as e:
                    failed_recipients.append(f"{recipient} ({str(e)})")
                    logger.error(f"Error sending email to {recipient}: {str(e)}")
                    continue
            
            # Show appropriate success/error messages
            if success_count > 0:
                flash(f'Successfully sent emails to {success_count} recipients!', 'success')
            if failed_recipients:
                flash(f'Failed to send emails to: {", ".join(failed_recipients)}', 'error')
            
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Error in email sending process: {str(e)}")
            flash(f'Error sending emails: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    return render_template('index.html', form=form)

def get_dashboard_data():
    try:
        analytics = SendGridAnalytics()
        
        # Get global stats
        logger.debug("Fetching global stats...")
        global_stats = analytics.get_global_stats()
        logger.debug(f"Global stats received: {global_stats}")
        
        # Get daily stats for the last 7 days
        logger.debug("Fetching daily stats...")
        daily_stats = analytics.get_stats(days=7)
        logger.debug(f"Daily stats received: {daily_stats}")
        
        # Prepare data for activity chart
        dates = [stat['date'] for stat in daily_stats]
        delivered = [stat['stats'][0]['metrics']['delivered'] for stat in daily_stats]
        opens = [stat['stats'][0]['metrics']['opens'] for stat in daily_stats]
        clicks = [stat['stats'][0]['metrics']['clicks'] for stat in daily_stats]
        
        # Create activity chart data as dictionaries
        activity_chart_data = [
            {
                'x': dates,
                'y': delivered,
                'name': 'Delivered',
                'mode': 'lines+markers',
                'type': 'scatter'
            },
            {
                'x': dates,
                'y': opens,
                'name': 'Opens',
                'mode': 'lines+markers',
                'type': 'scatter'
            },
            {
                'x': dates,
                'y': clicks,
                'name': 'Clicks',
                'mode': 'lines+markers',
                'type': 'scatter'
            }
        ]
        
        # Create delivery chart data as dictionaries
        delivery_chart_data = [
            {
                'x': dates,
                'y': delivered,
                'name': 'Delivered',
                'type': 'bar'
            },
            {
                'x': dates,
                'y': opens,
                'name': 'Opens',
                'type': 'bar'
            },
            {
                'x': dates,
                'y': clicks,
                'name': 'Clicks',
                'type': 'bar'
            }
        ]
        
        return {
            'global_stats': global_stats,
            'daily_stats': daily_stats,
            'activity_chart_data': activity_chart_data,
            'delivery_chart_data': delivery_chart_data
        }
    except Exception as e:
        logger.error(f"Error in get_dashboard_data: {str(e)}", exc_info=True)
        raise

@app.route('/dashboard')
def dashboard():
    try:
        data = get_dashboard_data()
        return render_template('dashboard.html',
                             global_stats=data['global_stats'],
                             daily_stats=data['daily_stats'],
                             activity_chart_data=data['activity_chart_data'],
                             delivery_chart_data=data['delivery_chart_data'])
    except Exception as e:
        error_msg = f'Error loading dashboard: {str(e)}'
        logger.error(error_msg, exc_info=True)
        flash(error_msg, 'error')
        return redirect(url_for('index'))

@app.route('/dashboard/refresh')
def refresh_dashboard():
    try:
        data = get_dashboard_data()
        return jsonify(data)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in refresh_dashboard: {error_msg}", exc_info=True)
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    app.run(debug=True) 