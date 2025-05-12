# Clean Earth Renewables Email Management System

A professional email management system built with Flask and SendGrid, designed for Clean Earth Renewables to handle bulk email communications with enhanced analytics and deliverability features.

## Features

- **Bulk Email Sending**: Send professional emails to multiple recipients simultaneously
- **Real-time Analytics Dashboard**: Monitor email performance with interactive charts
- **Email Templates**: Pre-designed templates for consistent branding
- **Delivery Tracking**: Track opens, clicks, and bounces
- **Auto-refresh Analytics**: Real-time updates every 20 seconds
- **Responsive Design**: Modern UI that works on all devices
- **Professional Branding**: Clean Earth Renewables' green theme throughout

## Prerequisites

- Python 3.8 or higher
- SendGrid API key
- Domain with configured SPF, DKIM, and DMARC records

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/clean-earth-email.git
cd clean-earth-email
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

4. Create a `.env` file in the root directory with your configuration:
```env
SENDGRID_API_KEY=your_sendgrid_api_key
MAIL_DEFAULT_SENDER=your_verified_sender_email
```

## Email Authentication Setup

For optimal email deliverability, configure the following DNS records for your domain:

### SPF Record
```
v=spf1 include:sendgrid.net ~all
```

### DKIM Record
Add the CNAME record provided by SendGrid in your domain settings.

### DMARC Record
```
v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@yourdomain.com
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Access the web interface at `http://localhost:5000`

3. Navigate between pages:
   - **Email Campaign**: Compose and send bulk emails
   - **Dashboard**: View email analytics and performance metrics

## Email Sending

1. Enter recipient email addresses (one per line)
2. Add a subject line
3. Include an optional custom message
4. Click "Send Campaign" to deliver

## Analytics Dashboard

The dashboard provides:
- Total emails sent
- Open rates
- Click rates
- Bounce rates
- Interactive charts for:
  - Email activity over time
  - Delivery statistics
- Recent activity table
- Auto-refresh functionality

## Security Features

- CSRF protection
- Secure password handling
- Environment variable configuration
- Input validation
- Rate limiting

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please contact:
- Email: support@clean-earth.org
- Website: https://clean-earth.org

## Acknowledgments

- SendGrid for email delivery infrastructure
- Flask for the web framework
- Bootstrap for the UI components
- Plotly for interactive charts 