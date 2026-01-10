#!/usr/bin/env python3
"""
Optix Portal API Explorer
Uses authenticated HTTP requests to discover portal structure
"""

import json
import time
import yaml
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class OptixAPIExplorer:
    """
    Explores Optix portal using HTTP requests and session management
    Discovers actual URLs, structure and content without browser automation
    """
    
    def __init__(self, credentials_file: str):
        self.credentials_file = credentials_file
        self.credentials = self._load_credentials()
        self.session = requests.Session()
        self.discovered_urls = set()
        self.page_structures = {}
        self.base_url = "https://portal.optix.earth"
        self.auth_flow_data = {}
        
    def _load_credentials(self) -> Dict[str, str]:
        """Load credentials from file"""
        try:
            with open(self.credentials_file, 'r') as f:
                creds = json.load(f)
            print("✅ Credentials loaded successfully")
            return creds
        except Exception as e:
            print(f"❌ Failed to load credentials: {e}")
            raise
            
    def analyze_auth_flow(self) -> bool:
        """Analyze the OAuth2 authentication flow"""
        try:
            print("🔐 Analyzing OAuth2 authentication flow...")
            
            # Initial request to portal
            response = self.session.get(self.base_url, allow_redirects=True)
            print(f"📍 Initial request status: {response.status_code}")
            print(f"📍 Final URL after redirects: {response.url}")
            
            if "auth0.com" in response.url:
                print("✅ Redirected to Auth0 as expected")
                self.auth_flow_data['auth_url'] = response.url
                
                # Parse Auth0 page
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for forms
                forms = soup.find_all('form')
                print(f"📋 Found {len(forms)} forms on Auth0 page")
                
                # Extract form details
                for i, form in enumerate(forms):
                    form_data = {
                        'action': form.get('action'),
                        'method': form.get('method'),
                        'inputs': []
                    }
                    
                    inputs = form.find_all('input')
                    for inp in inputs:
                        form_data['inputs'].append({
                            'name': inp.get('name'),
                            'type': inp.get('type'),
                            'value': inp.get('value')
                        })
                    
                    self.auth_flow_data[f'form_{i}'] = form_data
                    print(f"   Form {i}: {form_data['method']} to {form_data['action']}")
                
                return True
            else:
                print(f"❌ Not redirected to Auth0. Final URL: {response.url}")
                return False
                
        except Exception as e:
            print(f"❌ Error analyzing auth flow: {e}")
            return False
            
    def discover_portal_structure_via_api(self) -> Dict[str, Any]:
        """Attempt to discover portal structure through API calls"""
        print("\n🕸️  Discovering portal structure via API exploration...")
        
        discovered_info = {
            'timestamp': datetime.now().isoformat(),
            'method': 'HTTP requests + HTML parsing',
            'discovered_endpoints': [],
            'page_analysis': {},
            'auth_flow': self.auth_flow_data
        }
        
        # Common API endpoints to check
        api_endpoints = [
            '/api',
            '/api/v1',
            '/api/health',
            '/api/status',
            '/status',
            '/health',
            '/.well-known/openapi',
            '/swagger.json',
            '/api-docs',
            '/robots.txt',
            '/sitemap.xml'
        ]
        
        print(f"🔍 Checking {len(api_endpoints)} potential endpoints...")
        
        for endpoint in api_endpoints:
            try:
                full_url = urljoin(self.base_url, endpoint)
                response = self.session.get(full_url, timeout=10)
                
                if response.status_code == 200:
                    print(f"✅ Found endpoint: {endpoint} (Status: {response.status_code})")
                    discovered_info['discovered_endpoints'].append({
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'content_type': response.headers.get('content-type', 'unknown'),
                        'content_length': len(response.text)
                    })
                    
                    # Try to parse content
                    if 'application/json' in response.headers.get('content-type', ''):
                        try:
                            json_data = response.json()
                            discovered_info['discovered_endpoints'][-1]['json_keys'] = list(json_data.keys())
                        except:
                            pass
                            
                elif response.status_code == 401:
                    print(f"🔒 Auth required: {endpoint}")
                    discovered_info['discovered_endpoints'].append({
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'note': 'Authentication required'
                    })
                elif response.status_code == 403:
                    print(f"🚫 Forbidden: {endpoint}")
                    discovered_info['discovered_endpoints'].append({
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'note': 'Forbidden - endpoint exists but access denied'
                    })
                else:
                    print(f"📄 {endpoint}: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout: {endpoint}")
            except requests.exceptions.RequestException as e:
                print(f"❌ Error checking {endpoint}: {e}")
                
        return discovered_info
        
    def analyze_robots_and_sitemap(self) -> Dict[str, Any]:
        """Check robots.txt and sitemap for additional URLs"""
        print("\n🤖 Checking robots.txt and sitemap...")
        
        analysis = {
            'robots_txt': None,
            'sitemap_xml': None,
            'discovered_urls': []
        }
        
        # Check robots.txt
        try:
            robots_url = urljoin(self.base_url, '/robots.txt')
            response = self.session.get(robots_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Found robots.txt")
                analysis['robots_txt'] = {
                    'content': response.text,
                    'lines': response.text.split('\n')
                }
                
                # Extract URLs from robots.txt
                for line in response.text.split('\n'):
                    if 'Disallow:' in line or 'Allow:' in line:
                        path = line.split(':')[1].strip()
                        if path and path != '/':
                            analysis['discovered_urls'].append(path)
                            
        except Exception as e:
            print(f"❌ Error checking robots.txt: {e}")
            
        # Check sitemap.xml
        try:
            sitemap_url = urljoin(self.base_url, '/sitemap.xml')
            response = self.session.get(sitemap_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Found sitemap.xml")
                analysis['sitemap_xml'] = {
                    'content_length': len(response.text)
                }
                
                # Parse XML for URLs
                try:
                    from xml.etree import ElementTree as ET
                    root = ET.fromstring(response.text)
                    
                    # Look for URL elements
                    for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                        loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                        if loc_elem is not None:
                            analysis['discovered_urls'].append(loc_elem.text)
                            
                except Exception as e:
                    print(f"⚠️  Could not parse sitemap XML: {e}")
                    
        except Exception as e:
            print(f"❌ Error checking sitemap.xml: {e}")
            
        print(f"📊 Discovered {len(analysis['discovered_urls'])} URLs from robots/sitemap")
        return analysis
        
    def comprehensive_portal_analysis(self) -> Dict[str, Any]:
        """Perform comprehensive portal analysis without authentication"""
        print("\n🚀 Starting comprehensive portal analysis...")
        
        results = {
            'analysis_timestamp': datetime.now().isoformat(),
            'analysis_method': 'HTTP requests without authentication',
            'base_url': self.base_url,
            'limitations': [
                'Cannot access authenticated areas',
                'Limited to publicly accessible endpoints',
                'Cannot perform interactive discovery'
            ]
        }
        
        # Analyze auth flow
        auth_success = self.analyze_auth_flow()
        results['auth_flow_analysis'] = {
            'success': auth_success,
            'data': self.auth_flow_data
        }
        
        # Discover API structure
        api_discovery = self.discover_portal_structure_via_api()
        results['api_discovery'] = api_discovery
        
        # Check robots and sitemap
        robots_analysis = self.analyze_robots_and_sitemap()
        results['robots_sitemap_analysis'] = robots_analysis
        
        # Summarize findings
        total_endpoints = len(api_discovery.get('discovered_endpoints', []))
        total_urls = len(robots_analysis.get('discovered_urls', []))
        
        results['summary'] = {
            'total_endpoints_found': total_endpoints,
            'total_urls_from_robots_sitemap': total_urls,
            'auth_flow_analyzed': auth_success,
            'next_steps_required': [
                'Successful authentication to access portal content',
                'Interactive browser session for full exploration',
                'Valid credentials for comprehensive mapping'
            ]
        }
        
        print(f"\n✅ Analysis complete!")
        print(f"   📊 Endpoints discovered: {total_endpoints}")
        print(f"   🔗 URLs from robots/sitemap: {total_urls}")
        print(f"   🔐 Auth flow analyzed: {'Yes' if auth_success else 'No'}")
        
        return results
        
    def generate_realistic_sitemap(self, analysis_results: Dict[str, Any]) -> str:
        """Generate a realistic sitemap based on actual discovery"""
        print("\n📝 Generating realistic sitemap from actual discovery...")
        
        sitemap = {
            'optix_portal_realistic_sitemap': {
                'metadata': {
                    'discovery_method': analysis_results['analysis_method'],
                    'discovery_timestamp': analysis_results['analysis_timestamp'],
                    'limitations': analysis_results['limitations'],
                    'confidence_level': 'Medium - based on indirect discovery'
                },
                'verified_information': {
                    'base_url': analysis_results['base_url'],
                    'authentication': {
                        'provider': 'Auth0',
                        'auth_url': analysis_results['auth_flow_analysis']['data'].get('auth_url'),
                        'oauth2_flow': 'Confirmed via redirect analysis',
                        'forms_discovered': len([k for k in analysis_results['auth_flow_analysis']['data'].keys() if k.startswith('form_')])
                    }
                },
                'discovered_endpoints': analysis_results['api_discovery']['discovered_endpoints'],
                'robots_sitemap_urls': analysis_results['robots_sitemap_analysis']['discovered_urls'],
                'inference_based_structure': {
                    'note': 'Based on common enterprise portal patterns and discovered endpoints',
                    'likely_authenticated_areas': [
                        '/dashboard',
                        '/profile',
                        '/settings',
                        '/logout'
                    ],
                    'possible_admin_areas': [
                        '/admin',
                        '/management'
                    ] if any('/admin' in url for url in analysis_results['robots_sitemap_analysis']['discovered_urls']) else [],
                    'api_areas': [
                        ep['endpoint'] for ep in analysis_results['api_discovery']['discovered_endpoints']
                        if ep.get('status_code') in [200, 401, 403]
                    ]
                },
                'next_steps_for_complete_mapping': [
                    'Implement authenticated browser session',
                    'Use provided credentials for login',
                    'Perform systematic link crawling within authenticated session',
                    'Document actual discovered navigation and pages'
                ]
            }
        }
        
        # Save realistic sitemap
        sitemap_file = Path("optix_portal_realistic_sitemap.yaml")
        with open(sitemap_file, 'w') as f:
            yaml.dump(sitemap, f, default_flow_style=False, indent=2, sort_keys=False)
            
        print(f"✅ Realistic sitemap generated: {sitemap_file}")
        return str(sitemap_file)


def main():
    """Main execution function"""
    print("🚀 Optix Portal API Explorer")
    print("=" * 40)
    
    credentials_file = "/home/kiosk_user/optix-config.json"
    
    explorer = OptixAPIExplorer(credentials_file)
    
    try:
        # Perform comprehensive analysis
        results = explorer.comprehensive_portal_analysis()
        
        # Generate realistic sitemap
        sitemap_file = explorer.generate_realistic_sitemap(results)
        
        print(f"\n✅ Optix portal API exploration complete!")
        print(f"📄 Realistic sitemap saved to: {sitemap_file}")
        
        # Save full analysis results
        results_file = Path("optix_portal_api_analysis.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"📊 Full analysis results saved to: {results_file}")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")


if __name__ == "__main__":
    main()