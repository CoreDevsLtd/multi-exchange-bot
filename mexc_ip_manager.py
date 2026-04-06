"""
MEXC IP Whitelist Manager
Automatically detects Railway IP and provides instructions for updating MEXC whitelist
"""

import requests
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class MEXCIPManager:
    """Manages MEXC IP whitelist for Railway deployments"""
    
    def __init__(self):
        """Initialize IP Manager"""
        self.current_ip = None
    
    def get_current_ip(self) -> Optional[str]:
        """
        Get current public IP address
        
        Returns:
            Current IP address or None if detection fails
        """
        try:
            # Try multiple IP detection services
            services = [
                'https://api.ipify.org',
                'https://icanhazip.com',
                'https://ifconfig.me/ip',
                'https://api.myip.com',
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    if response.status_code == 200:
                        ip = response.text.strip()
                        # Validate IP format (basic check)
                        if ip and '.' in ip and len(ip.split('.')) == 4:
                            self.current_ip = ip
                            logger.info(f"🌐 Detected current IP: {ip}")
                            return ip
                except Exception as e:
                    logger.debug(f"Failed to get IP from {service}: {e}")
                    continue
            
            logger.warning("⚠️  Could not detect current IP address")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting IP: {e}")
            return None
    
    def get_whitelist_instructions(self, current_ip: Optional[str] = None) -> str:
        """
        Get instructions for updating MEXC IP whitelist
        
        Args:
            current_ip: Current IP address (will detect if not provided)
            
        Returns:
            Instructions string
        """
        if not current_ip:
            current_ip = self.get_current_ip()
        
        if not current_ip:
            return """
⚠️  MEXC IP Whitelist Update Required

Could not detect current IP. Please:
1. Check Railway logs for your current IP
2. Manually add it to MEXC API whitelist
3. MEXC allows up to 20 IPs, separated by commas

Note: Keys without IP whitelist expire in 90 days.
"""
        
        instructions = f"""
⚠️  MEXC IP Whitelist Update Required

Current Railway IP: {current_ip}

To update MEXC IP whitelist:
1. Log into MEXC → API Management
2. Edit your API key
3. In "Link IP Address" field, add: {current_ip}
4. You can add up to 20 IPs, separated by commas
5. Save changes
6. Wait 1-2 minutes for changes to propagate

⚠️  Important Notes:
- Railway IPs change on each deployment
- You may need to update whitelist after each redeploy
- Keys without IP whitelist expire in 90 days (not recommended)
- Consider adding multiple Railway IPs if you know them

Alternative Solutions:
1. Use a static IP service (e.g., VPN, proxy)
2. Accept 90-day key rotation (leave whitelist empty)
3. Monitor and update whitelist after each deployment
"""
        return instructions
    
    def log_whitelist_status(self):
        """Log current IP and whitelist instructions"""
        current_ip = self.get_current_ip()
        if current_ip:
            logger.warning(self.get_whitelist_instructions(current_ip))
        else:
            logger.warning(self.get_whitelist_instructions())


def check_and_log_ip():
    """Helper function to check IP and log instructions"""
    manager = MEXCIPManager()
    manager.log_whitelist_status()
    return manager.get_current_ip()

