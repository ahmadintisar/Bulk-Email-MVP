# Bulk Email Sender with Template Management

A Flask-based bulk email sending application with template management and real-time analytics.

## Features

### Email Campaign Management
- Send bulk emails to multiple recipients
- Support for both manual email entry and file upload (Excel/CSV)
- Automatic email validation and duplicate removal
- Batch processing with progress tracking
- Comprehensive error handling and logging

### Template Management
- Two template options:
  * Predefined templates with automatic subject lines
  * Custom HTML template upload with selectable subjects
- Dynamic subject line generation
- Automatic name placeholder replacement
- Template preview functionality
- Secure template storage and management

### Analytics Dashboard
- Real-time SendGrid analytics integration
- 20-second refresh rate for live updates
- Key metrics tracking:
  * Email delivery statistics
  * Open and click rates
  * Bounce and spam reports
  * Campaign performance
  * Geographic distribution
  * Device and client analytics

### Security Features
- Secure file upload handling
- HTML content sanitization
- XSS prevention
- Access control and authentication
- Secure template storage
- API key protection

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd Bulk-Email-MVP
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize the application:
```bash
python app.py
```

## Usage

### Sending Emails

1. **Choose Template Type**
   - Select between predefined templates or custom template upload
   - For predefined templates, choose from available options
   - For custom templates, upload HTML file and select subject

2. **Add Recipients**
   - Enter email addresses manually (one per line)
   - Or upload Excel/CSV file with email addresses
   - System automatically detects email columns

3. **Send Campaign**
   - Review template and subject
   - Click "Send Campaign" to start
   - Monitor progress in real-time

### Analytics Dashboard

1. **View Campaign Statistics**
   - Access dashboard for real-time metrics
   - Monitor delivery rates and engagement
   - Track geographic distribution
   - Analyze device and client data

2. **Batch Activity**
   - View detailed campaign history
   - Track success and failure rates
   - Monitor processing times
   - Access detailed logs

## File Structure

```
Bulk-Email-MVP/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables
├── templates/            # Email templates
│   ├── custom_templates/ # User uploaded templates
│   └── index.html        # Main interface
├── static/              # Static assets
└── email_logs/          # Campaign logs
```

## Dependencies

- Flask
- SendGrid
- pandas
- python-dotenv
- plotly
- Other requirements listed in requirements.txt

## Security Considerations

- All file uploads are validated and sanitized
- HTML content is processed securely
- API keys are stored in environment variables
- Access control is implemented
- Regular security audits are performed

## Performance Optimization

- Efficient template processing
- Optimized file handling
- Background processing for large batches
- Cached analytics data
- Rate limit management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your License Here]

## Support

For support, please contact [Your Contact Information] 