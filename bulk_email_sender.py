import os
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Header
from dotenv import load_dotenv
import logging
from datetime import datetime
import json
import uuid

# Create logs directory if it doesn't exist
LOGS_DIR = 'email_logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Load environment variables
load_dotenv()

class BulkEmailSender:
    def __init__(self):
        self.sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        self.from_email = Email(os.getenv('FROM_EMAIL', 'origination@clean-earth.org'))
        
        # Create a new log file for this instance
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join(LOGS_DIR, f'email_batch_{timestamp}.log')
        
        # Configure logging
        self.logger = logging.getLogger(f'email_batch_{timestamp}')
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"Initialized BulkEmailSender with from_email: {self.from_email.email}")
        
        # Initialize batch data
        self.batch_data = {
            'timestamp': timestamp,
            'from_email': self.from_email.email,
            'total_emails': 0,
            'successful_emails': 0,
            'failed_emails': 0,
            'recipients': [],
            'errors': [],
            'source': None,  # 'manual' or 'file'
            'file_name': None,  # Name of uploaded file if source is 'file'
            'subject': None,
            'template': None,
            'campaign_id': str(uuid.uuid4()),  # Unique identifier for the campaign
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'processing_time': None
        }

    def send_email(self, to_email, subject, html_content):
        """
        Send a single email using SendGrid
        """
        try:
            message = Mail(
                from_email=self.from_email,
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            # Add headers for better deliverability
            message.add_header(Header("X-Message-ID", f"<{to_email}-{int(pd.Timestamp.now().timestamp())}@clean-earth.org>"))
            message.add_header(Header("List-Unsubscribe", "<mailto:unsubscribe@clean-earth.org>"))
            message.add_header(Header("Precedence", "bulk"))
            message.add_header(Header("X-Campaign-ID", self.batch_data['campaign_id']))
            
            # Set reply-to header
            message.reply_to = Email("david.e@clean-earth.org", "David E")
            
            self.logger.info(f"Sending email to {to_email} with subject: {subject}")
            response = self.sg.send(message)
            self.logger.info(f"Email sent successfully to {to_email}. Status code: {response.status_code}")
            self.logger.info(f"Response headers: {response.headers}")
            
            # Log the full response for debugging
            self.logger.debug(f"Full response: {response.__dict__}")
            
            # Update batch data
            self.batch_data['successful_emails'] += 1
            self.batch_data['recipients'].append({
                'email': to_email,
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'response_code': response.status_code,
                'message_id': response.headers.get('X-Message-Id', '')
            })
            
            return True
        except Exception as e:
            self.logger.error(f"Error sending email to {to_email}: {str(e)}", exc_info=True)
            
            # Update batch data
            self.batch_data['failed_emails'] += 1
            self.batch_data['recipients'].append({
                'email': to_email,
                'status': 'failed',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            })
            self.batch_data['errors'].append({
                'email': to_email,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            
            return False

    def send_bulk_emails(self, recipients_file, subject, template_path):
        """
        Send bulk emails to recipients from a CSV file
        CSV file should have at least an 'email' column
        """
        try:
            # Read recipients from CSV
            df = pd.read_csv(recipients_file)
            self.logger.info(f"Read {len(df)} recipients from {recipients_file}")
            
            # Update batch data
            self.batch_data['total_emails'] = len(df)
            self.batch_data['subject'] = subject
            self.batch_data['template_path'] = template_path
            
            # Read email template
            with open(template_path, 'r') as file:
                template = file.read()
            self.logger.info(f"Read template from {template_path}")
            
            # Send emails to each recipient
            success_count = 0
            for _, row in df.iterrows():
                email = row['email']
                # You can customize the template with recipient-specific data here
                html_content = template
                
                if self.send_email(email, subject, html_content):
                    success_count += 1
            
            self.logger.info(f"Bulk email sending completed. Successfully sent: {success_count}/{len(df)}")
            
            # Save batch summary
            self.save_batch_summary()
            
        except Exception as e:
            self.logger.error(f"Error in bulk email sending: {str(e)}", exc_info=True)
            self.batch_data['errors'].append({
                'type': 'batch_error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            self.save_batch_summary()

    def save_batch_summary(self):
        """
        Save a JSON summary of the batch
        """
        # Update end time and processing time
        end_time = datetime.now()
        self.batch_data['end_time'] = end_time.isoformat()
        start_time = datetime.fromisoformat(self.batch_data['start_time'])
        self.batch_data['processing_time'] = str(end_time - start_time)
        
        # Calculate success rate
        total = self.batch_data['total_emails']
        if total > 0:
            success_rate = (self.batch_data['successful_emails'] / total) * 100
            self.batch_data['success_rate'] = f"{success_rate:.2f}%"
        
        # Save summary to JSON file
        summary_file = self.log_file.replace('.log', '_summary.json')
        with open(summary_file, 'w') as f:
            json.dump(self.batch_data, f, indent=2)
        self.logger.info(f"Batch summary saved to {summary_file}")
        
        # Log final statistics
        self.logger.info(f"Campaign completed - ID: {self.batch_data['campaign_id']}")
        self.logger.info(f"Total emails: {total}")
        self.logger.info(f"Successful: {self.batch_data['successful_emails']}")
        self.logger.info(f"Failed: {self.batch_data['failed_emails']}")
        if total > 0:
            self.logger.info(f"Success rate: {self.batch_data['success_rate']}")
        self.logger.info(f"Processing time: {self.batch_data['processing_time']}")

def main():
    # Example usage
    sender = BulkEmailSender()
    
    # Replace these with your actual values
    recipients_file = "recipients.csv"
    subject = "Your Subject Here"
    template_path = "templates/email_template.html"
    
    sender.send_bulk_emails(recipients_file, subject, template_path)

if __name__ == "__main__":
    main() 