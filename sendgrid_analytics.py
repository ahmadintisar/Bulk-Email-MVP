import os
import requests
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

class SendGridAnalytics:
    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY')
        if not self.api_key:
            raise ValueError("SENDGRID_API_KEY not found in environment variables")
            
        self.base_url = 'https://api.sendgrid.com/v3'
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, url, params=None):
        """Helper method to make API requests with proper error handling"""
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            raise Exception(f"SendGrid API request failed: {str(e)}")

    def get_stats(self, days=7):
        """Get email statistics for the last n days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = f"{self.base_url}/stats"
        params = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'aggregated_by': 'day'
        }
        
        logger.debug(f"Fetching stats with params: {params}")
        stats = self._make_request(url, params)
        logger.debug(f"Received stats: {stats}")
        return stats

    def get_global_stats(self):
        """Get global email statistics"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Get last 30 days of data
        
        url = f"{self.base_url}/stats"
        params = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'aggregated_by': 'day'
        }
        
        logger.debug(f"Fetching global stats with params: {params}")
        stats = self._make_request(url, params)
        logger.debug(f"Received global stats: {stats}")
        
        # Initialize totals with default values
        totals = {
            'delivered': 0,
            'opens': 0,
            'clicks': 0,
            'bounces': 0,
            'open_rate': 0,
            'click_rate': 0,
            'bounce_rate': 0
        }
        
        # Process each day's stats
        for day in stats:
            metrics = day.get('stats', [{}])[0].get('metrics', {})
            totals['delivered'] += metrics.get('delivered', 0)
            totals['opens'] += metrics.get('opens', 0)
            totals['clicks'] += metrics.get('clicks', 0)
            totals['bounces'] += metrics.get('bounces', 0)
        
        # Calculate rates if we have delivered emails
        if totals['delivered'] > 0:
            totals['open_rate'] = (totals['opens'] / totals['delivered']) * 100
            totals['click_rate'] = (totals['clicks'] / totals['delivered']) * 100
            totals['bounce_rate'] = (totals['bounces'] / totals['delivered']) * 100
            
        logger.debug(f"Calculated totals: {totals}")
        return totals

    def get_bounces(self, days=7):
        """Get bounce statistics"""
        url = f"{self.base_url}/suppression/bounces"
        params = {
            'start_time': int((datetime.now() - timedelta(days=days)).timestamp()),
            'end_time': int(datetime.now().timestamp())
        }
        
        return self._make_request(url, params)

    def get_blocks(self, days=7):
        """Get block statistics"""
        url = f"{self.base_url}/suppression/blocks"
        params = {
            'start_time': int((datetime.now() - timedelta(days=days)).timestamp()),
            'end_time': int(datetime.now().timestamp())
        }
        
        return self._make_request(url, params)

    def get_spam_reports(self, days=7):
        """Get spam report statistics"""
        url = f"{self.base_url}/suppression/spam_reports"
        params = {
            'start_time': int((datetime.now() - timedelta(days=days)).timestamp()),
            'end_time': int(datetime.now().timestamp())
        }
        
        return self._make_request(url, params) 