"""Service for IP geolocation lookup."""
import logging
import httpx
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class GeolocationService:
    """Service to get geolocation data from IP addresses."""
    
    # Using ip-api.com (free, no API key required, 45 requests/minute)
    # Alternative: ipapi.co (1000 requests/day free)
    BASE_URL = "http://ip-api.com/json"
    
    @staticmethod
    async def lookup_ip(ip_address: str) -> Optional[Dict[str, str]]:
        """
        Lookup geolocation information for an IP address.
        
        Args:
            ip_address: The IP address to lookup
            
        Returns:
            Dictionary with geolocation data or None if lookup fails
            {
                'country_code': 'US',
                'country_name': 'United States',
                'region': 'California',
                'city': 'San Francisco'
            }
        """
        if not ip_address or ip_address.startswith('10.') or ip_address == '127.0.0.1':
            # Skip private/local IPs
            return None
        
        try:
            # Add fields parameter to get only what we need
            url = f"{GeolocationService.BASE_URL}/{ip_address}?fields=status,country,countryCode,region,city"
            
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('status') == 'success':
                        return {
                            'country_code': data.get('countryCode'),
                            'country_name': data.get('country'),
                            'region': data.get('region'),
                            'city': data.get('city'),
                        }
                    else:
                        logger.warning(f"Geolocation lookup failed for {ip_address}: {data.get('message')}")
                        return None
                else:
                    logger.warning(f"Geolocation API returned status {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            logger.warning(f"Geolocation lookup timeout for {ip_address}")
            return None
        except Exception as e:
            logger.error(f"Error during geolocation lookup for {ip_address}: {e}")
            return None
    
    @staticmethod
    def lookup_ip_sync(ip_address: str) -> Optional[Dict[str, str]]:
        """
        Synchronous version of lookup_ip for use in non-async contexts.
        
        Args:
            ip_address: The IP address to lookup
            
        Returns:
            Dictionary with geolocation data or None if lookup fails
        """
        if not ip_address or ip_address.startswith('10.') or ip_address == '127.0.0.1':
            # Skip private/local IPs
            return None
        
        try:
            url = f"{GeolocationService.BASE_URL}/{ip_address}?fields=status,country,countryCode,region,city"
            
            with httpx.Client(timeout=3.0) as client:
                response = client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('status') == 'success':
                        return {
                            'country_code': data.get('countryCode'),
                            'country_name': data.get('country'),
                            'region': data.get('region'),
                            'city': data.get('city'),
                        }
                    else:
                        logger.warning(f"Geolocation lookup failed for {ip_address}: {data.get('message')}")
                        return None
                else:
                    logger.warning(f"Geolocation API returned status {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            logger.warning(f"Geolocation lookup timeout for {ip_address}")
            return None
        except Exception as e:
            logger.error(f"Error during geolocation lookup for {ip_address}: {e}")
            return None
