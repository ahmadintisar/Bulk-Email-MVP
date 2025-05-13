from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, SelectField
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
import json
import pytz
import uuid
import glob
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Set Pakistan timezone
PAKISTAN_TZ = pytz.timezone('Asia/Karachi')

class EmailForm(FlaskForm):
    recipients = TextAreaField('Recipients', validators=[Optional()])
    excel_file = FileField('Upload File', validators=[
        FileAllowed(['xlsx', 'xls', 'csv'], 'Only Excel and CSV files are allowed!')
    ])
    subject = StringField('Subject', validators=[DataRequired()])
    template = SelectField('Email Template', choices=[
        ('email_template.html', 'Template 1'),
        ('template-2.html', 'Template 2'),
        ('template-3.html', 'Template 3'),
        ('template-4.html', 'Template 4')
    ], validators=[DataRequired()])
    submit = SubmitField('Send Campaign')

    # Predefined headers for each template
    TEMPLATE_HEADERS = {
        'email_template.html': 'Enroll {name} for Community Solar & Start Saving Today',
        'template-2.html': 'RE: Enroll {name} for Community Solar & Start Saving',
        'template-3.html': 'Follow-up: Enroll {name} for Community Solar & Start Saving',
        'template-4.html': 'Reminder: Enroll {name} for Community Solar & Start Saving'
    }

    def __init__(self, *args, **kwargs):
        super(EmailForm, self).__init__(*args, **kwargs)
        # Set initial subject based on default template
        self.subject.data = self.TEMPLATE_HEADERS['email_template.html'].format(name='')

@app.route('/', methods=['GET', 'POST'])
def index():
    form = EmailForm()
    
    # Handle template selection via AJAX
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        template = request.form.get('template')
        if template in form.TEMPLATE_HEADERS:
            return jsonify({
                'subject': form.TEMPLATE_HEADERS[template].format(name='')
            })
        return jsonify({'error': 'Invalid template'}), 400

    if form.validate_on_submit():
        try:
            # Initialize BulkEmailSender for logging
            email_sender = BulkEmailSender()
            logger.info("Starting new email campaign")
            
            # Get recipients from either text area or file
            recipients = []
            email_name_map = {}  # Dictionary to store email-name mappings
            
            if form.recipients.data:
                logger.info("Processing manual email entries")
                recipients.extend([email.strip() for email in form.recipients.data.split('\n') if email.strip()])
                # For manual entries, use email username as name
                for email in recipients:
                    email_name_map[email] = email.split('@')[0]
                logger.info(f"Processed {len(recipients)} manual email entries")
            
            if form.excel_file.data:
                logger.info(f"Processing uploaded file: {form.excel_file.data.filename}")
                file_emails, file_email_name_map = extract_emails_from_file(form.excel_file.data)
                recipients.extend(file_emails)
                # Update the email-name mapping with file data
                email_name_map.update(file_email_name_map)
                # For any emails without names, use email username
                for email in file_emails:
                    if email not in email_name_map:
                        email_name_map[email] = email.split('@')[0]
                logger.info(f"Processed {len(file_emails)} emails from file")
            
            if not recipients:
                logger.warning("No recipients provided")
                flash('Please provide recipients either in the text area or upload a file.', 'error')
                return redirect(url_for('index'))
            
            # Remove duplicates and validate emails
            recipients = list(set(recipients))
            invalid_emails = [email for email in recipients if not '@' in email]
            if invalid_emails:
                logger.warning(f"Found invalid email addresses: {invalid_emails}")
                flash(f'Invalid email addresses found: {", ".join(invalid_emails)}', 'error')
                return redirect(url_for('index'))
            
            # Use the verified sender email
            sender_email = "origination@clean-earth.org"
            
            # Get email template
            email_content = get_email_template(form.template.data)
            
            # Send emails immediately
            sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
            from_email = Email(sender_email, "Clean Earth Renewables")
            
            success_count = 0
            failed_recipients = []
            
            # Update batch data
            email_sender.batch_data.update({
                'total_emails': len(recipients),
                'subject': form.subject.data,
                'template': form.template.data,
                'source': 'manual' if form.recipients.data else 'file',
                'file_name': form.excel_file.data.filename if form.excel_file.data else None
            })
            
            for recipient in recipients:
                to_email = To(recipient)
                # Get the name for this recipient from the mapping
                name = email_name_map.get(recipient, recipient.split('@')[0])
                subject = form.TEMPLATE_HEADERS[form.template.data].format(name=name)
                content = Content("text/html", email_content)
                mail = Mail(from_email, to_email, subject, content)
                try:
                    response = sg.send(mail)
                    if response.status_code == 202:
                        success_count += 1
                        logger.info(f"Email sent successfully to {recipient}")
                        email_sender.batch_data['successful_emails'] += 1
                        email_sender.batch_data['recipients'].append({
                            'email': recipient,
                            'status': 'success',
                            'timestamp': datetime.now().isoformat(),
                            'response_code': response.status_code
                        })
                    else:
                        failed_recipients.append(f"{recipient} (Status: {response.status_code})")
                        logger.error(f"Failed to send email to {recipient}: {response.status_code}")
                        email_sender.batch_data['failed_emails'] += 1
                        email_sender.batch_data['recipients'].append({
                            'email': recipient,
                            'status': 'failed',
                            'timestamp': datetime.now().isoformat(),
                            'error': f"Status code: {response.status_code}"
                        })
                except Exception as e:
                    failed_recipients.append(f"{recipient} ({str(e)})")
                    logger.error(f"Error sending email to {recipient}: {str(e)}")
                    email_sender.batch_data['failed_emails'] += 1
                    email_sender.batch_data['recipients'].append({
                        'email': recipient,
                        'status': 'failed',
                        'timestamp': datetime.now().isoformat(),
                        'error': str(e)
                    })
                    continue
            
            # Save batch summary
            email_sender.save_batch_summary()
            
            # Show appropriate success/error messages
            if success_count > 0:
                flash(f'Successfully sent emails to {success_count} recipients!', 'success')
            if failed_recipients:
                flash(f'Failed to send campaign emails to: {", ".join(failed_recipients)}', 'error')
            
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Error in email sending process: {str(e)}", exc_info=True)
            flash(f'Error sending emails: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    return render_template('index.html', form=form)

def get_email_template(template_name='email_template.html'):
    """Get the email template."""
    template_path = os.path.join('templates', template_name)
    try:
        with open(template_path, 'r') as f:
            template = f.read()
        return template
    except Exception as e:
        logger.error(f"Error reading email template: {str(e)}")
        # Fallback to a basic template if the file can't be read
        return """
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2E7D32;">Clean Earth Renewables</h2>
                    <hr style="border: 1px solid #eee;">
                    <p style="color: #666; font-size: 12px;">
                        This email was sent from Clean Earth Renewables. Please do not reply to this email.
                    </p>
                </div>
            </body>
        </html>
        """

def extract_emails_from_file(file):
    try:
        # Get file extension
        filename = file.filename
        file_ext = filename.rsplit('.', 1)[1].lower()
        logger.debug(f"Processing file: {filename} with extension: {file_ext}")
        
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
        
        logger.debug(f"File columns: {df.columns.tolist()}")
        
        # Convert column names to lowercase for case-insensitive matching
        df.columns = df.columns.str.lower()
        
        # Look for columns that might contain email addresses and names
        email_columns = []
        name_columns = []
        email_variations = ['email', 'e-mail', 'mail', 'email address', 'emailaddress']
        name_variations = ['name', 'first name', 'firstname', 'full name', 'fullname', 'last name', 'lastname']
        
        # First, look for exact matches
        for col in df.columns:
            if any(variation in col for variation in email_variations):
                email_columns.append(col)
                logger.debug(f"Found email column: {col}")
            if any(variation in col for variation in name_variations):
                name_columns.append(col)
                logger.debug(f"Found name column: {col}")
        
        # If no email columns found, try to find columns containing email addresses
        if not email_columns:
            logger.debug("No email columns found, searching all columns for email patterns")
            all_emails = []
            for col in df.columns:
                # Convert column to string and find email-like patterns
                emails = df[col].astype(str).str.extractall(r'[\w\.-]+@[\w\.-]+\.\w+')[0].unique()
                if len(emails) > 0:  # If emails found in this column
                    all_emails.extend(emails)
                    logger.debug(f"Found emails in column {col}: {len(emails)} emails")
            return list(set(all_emails)), {}  # Return empty dict for names if none found
        
        # If email columns are found, use them
        emails = []
        email_name_map = {}
        
        # Process emails
        for col in email_columns:
            # Clean the email addresses
            col_emails = df[col].dropna().astype(str).str.strip()
            # Remove any non-email entries
            valid_emails = col_emails[col_emails.str.contains(r'^[\w\.-]+@[\w\.-]+\.\w+$')]
            emails.extend(valid_emails.tolist())
            logger.debug(f"Processed {len(valid_emails)} valid emails from column {col}")
        
        # Process names
        if name_columns:
            # Try to combine first name and last name if both exist
            first_name_col = next((col for col in name_columns if 'first' in col), None)
            last_name_col = next((col for col in name_columns if 'last' in col), None)
            
            if first_name_col and last_name_col:
                # Combine first and last names
                df['full_name'] = df[first_name_col].fillna('') + ' ' + df[last_name_col].fillna('')
                name_col = 'full_name'
            else:
                # Use the first name column found
                name_col = name_columns[0]
            
            # Create email-name mapping
            for email in emails:
                # Find the row containing this email
                email_row = df[df[email_columns[0]] == email]
                if not email_row.empty:
                    name = email_row[name_col].iloc[0]
                    if pd.notna(name) and str(name).strip():
                        email_name_map[email] = str(name).strip()
                    else:
                        email_name_map[email] = email.split('@')[0]
                else:
                    email_name_map[email] = email.split('@')[0]
            
            logger.debug(f"Created email-name mapping with {len(email_name_map)} entries")
        else:
            # If no name columns found, use email usernames
            for email in emails:
                email_name_map[email] = email.split('@')[0]
        
        return list(set(emails)), email_name_map  # Return emails and email-name mapping
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        raise ValueError(f"Error processing file: {str(e)}")

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

def get_batch_logs():
    """Get all batch logs from the email_logs directory"""
    try:
        # Get all log files
        log_files = glob.glob(os.path.join('email_logs', 'email_batch_*.log'))
        batch_data = []
        
        # Define timezones
        pkt_tz = pytz.timezone('Asia/Karachi')  # Pakistan Standard Time
        est_tz = pytz.timezone('US/Eastern')
        pst_tz = pytz.timezone('US/Pacific')
        
        for log_file in sorted(log_files, reverse=True):  # Sort by newest first
            # Get corresponding summary file
            summary_file = log_file.replace('.log', '_summary.json')
            
            # Read summary data if exists
            summary_data = {}
            if os.path.exists(summary_file):
                with open(summary_file, 'r') as f:
                    summary_data = json.load(f)
            
            # Read log file
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            # Extract timestamp from filename
            timestamp_match = re.search(r'email_batch_(\d{8}_\d{6})', log_file)
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                # Parse the timestamp and assume it's in PKT
                dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                # Make it timezone-aware in PKT
                dt = pkt_tz.localize(dt)
                # Convert to EST and PST
                est_time = dt.astimezone(est_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
                pst_time = dt.astimezone(pst_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
                pkt_time = dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                formatted_time = f"{pkt_time} / {est_time} / {pst_time}"
            else:
                formatted_time = "Unknown"
            
            # Get batch ID from summary or generate from filename
            batch_id = summary_data.get('campaign_id', timestamp)
            
            batch_data.append({
                'batch_id': batch_id,
                'timestamp': formatted_time,
                'total_emails': summary_data.get('total_emails', 0),
                'successful_emails': summary_data.get('successful_emails', 0),
                'failed_emails': summary_data.get('failed_emails', 0),
                'success_rate': summary_data.get('success_rate', '0%'),
                'source': summary_data.get('source', 'unknown'),
                'file_name': summary_data.get('file_name', 'N/A'),
                'subject': summary_data.get('subject', 'N/A'),
                'template': summary_data.get('template', 'N/A'),
                'processing_time': summary_data.get('processing_time', 'N/A'),
                'log_content': log_content
            })
        
        return batch_data
    except Exception as e:
        logger.error(f"Error reading batch logs: {str(e)}", exc_info=True)
        return []

@app.route('/batch-activity')
def batch_activity():
    try:
        batch_data = get_batch_logs()
        return render_template('batch_activity.html', batches=batch_data)
    except Exception as e:
        error_msg = f'Error loading batch activity: {str(e)}'
        logger.error(error_msg, exc_info=True)
        flash(error_msg, 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=True, host='0.0.0.0', port=port)