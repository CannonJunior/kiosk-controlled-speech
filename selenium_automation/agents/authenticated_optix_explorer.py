#!/usr/bin/env python3
"""
Authenticated Optix Portal Explorer
Discovers real portal structure using provided credentials
"""

import json
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class AuthenticatedOptixExplorer:
    """
    Real portal exploration using authenticated access
    Discovers actual URLs, navigation, and page structures
    """
    
    def __init__(self, credentials_file: str):
        self.credentials_file = credentials_file
        self.credentials = self._load_credentials()
        self.driver = None
        self.discovered_urls = set()
        self.page_structures = {}
        self.navigation_tree = {}
        self.base_url = "https://portal.optix.earth"
        self.auth_url = None
        
    def _load_credentials(self) -> Dict[str, str]:
        """Load credentials from file but don't store them as instance variables"""
        try:
            with open(self.credentials_file, 'r') as f:
                creds = json.load(f)
            print("✅ Credentials loaded successfully")
            return creds
        except Exception as e:
            print(f"❌ Failed to load credentials: {e}")
            raise
            
    def setup_browser(self, headless: bool = False):
        """Setup Chrome browser for exploration"""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless")
        
        # Security and performance options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Install ChromeDriver automatically
        service = Service(ChromeDriverManager().install())
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Set timeouts
        self.driver.implicitly_wait(10)
        
        print("🌐 Browser setup complete")
        
    def authenticate(self) -> bool:
        """Authenticate with the portal using provided credentials"""
        try:
            print("🔐 Starting authentication process...")
            
            # Navigate to portal
            self.driver.get(self.base_url)
            
            # Wait for redirect to Auth0
            wait = WebDriverWait(self.driver, 15)
            
            # Check if we're redirected to Auth0
            current_url = self.driver.current_url
            print(f"📍 Current URL: {current_url}")
            
            if "auth0.com" in current_url:
                self.auth_url = current_url
                print(f"🔄 Redirected to Auth0: {self.auth_url}")
                
                # Wait for Auth0 lock widget
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".auth0-lock-widget, .auth0-lock-container, input[name='email'], input[type='email']")))
                    print("✅ Auth0 login page loaded")
                    
                    # Find email field
                    email_selectors = [
                        "input[name='email']",
                        "input[type='email']", 
                        ".auth0-lock-input input[type='email']",
                        "#1-email"  # Common Auth0 field ID
                    ]
                    
                    email_field = None
                    for selector in email_selectors:
                        try:
                            email_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                            print(f"✅ Found email field with selector: {selector}")
                            break
                        except:
                            continue
                    
                    if not email_field:
                        print("❌ Could not find email field")
                        return False
                    
                    # Find password field
                    password_selectors = [
                        "input[name='password']",
                        "input[type='password']",
                        ".auth0-lock-input input[type='password']",
                        "#1-password"  # Common Auth0 field ID
                    ]
                    
                    password_field = None
                    for selector in password_selectors:
                        try:
                            password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                            print(f"✅ Found password field with selector: {selector}")
                            break
                        except:
                            continue
                    
                    if not password_field:
                        print("❌ Could not find password field")
                        return False
                    
                    # Enter credentials
                    email_field.clear()
                    email_field.send_keys(self.credentials['optix_user'])
                    print("📧 Email entered")
                    
                    password_field.clear() 
                    password_field.send_keys(self.credentials['optix_password'])
                    print("🔒 Password entered")
                    
                    # Find and click submit button
                    submit_selectors = [
                        "button[type='submit']",
                        ".auth0-lock-submit",
                        "input[type='submit']",
                        "button[name='action']"
                    ]
                    
                    submit_button = None
                    for selector in submit_selectors:
                        try:
                            submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            print(f"✅ Found submit button with selector: {selector}")
                            break
                        except:
                            continue
                    
                    if not submit_button:
                        print("❌ Could not find submit button")
                        return False
                    
                    # Click login
                    submit_button.click()
                    print("🚀 Login submitted")
                    
                    # Wait for authentication and redirect
                    time.sleep(5)
                    
                    # Check if we're back at the portal
                    new_url = self.driver.current_url
                    print(f"📍 Post-auth URL: {new_url}")
                    
                    if "portal.optix.earth" in new_url and "auth0.com" not in new_url:
                        print("✅ Authentication successful!")
                        return True
                    else:
                        print(f"❌ Authentication may have failed. Current URL: {new_url}")
                        return False
                        
                except TimeoutException:
                    print("❌ Timeout waiting for Auth0 page elements")
                    return False
                    
            else:
                print(f"❌ Not redirected to Auth0. Current URL: {current_url}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
            
    def discover_navigation_structure(self) -> Dict[str, Any]:
        """Discover the actual navigation structure of the portal"""
        print("\n🗺️  Discovering navigation structure...")
        
        navigation = {
            'primary_nav': [],
            'sidebar_nav': [],
            'user_menu': [],
            'footer_links': []
        }
        
        try:
            # Look for primary navigation
            nav_selectors = [
                "nav",
                ".navbar",
                ".main-nav",
                ".navigation",
                ".nav-menu",
                "header nav",
                ".top-nav"
            ]
            
            for selector in nav_selectors:
                try:
                    nav_elements = self.driver.find_elements(By.CSS_SELECTOR, f"{selector} a")
                    if nav_elements:
                        print(f"✅ Found navigation with selector: {selector}")
                        for link in nav_elements:
                            try:
                                text = link.text.strip()
                                href = link.get_attribute('href')
                                if text and href:
                                    navigation['primary_nav'].append({
                                        'text': text,
                                        'url': href,
                                        'selector': f"{selector} a"
                                    })
                            except:
                                continue
                        break
                except:
                    continue
                    
            # Look for sidebar navigation
            sidebar_selectors = [
                ".sidebar a",
                ".side-nav a", 
                ".menu a",
                "aside a",
                ".left-nav a"
            ]
            
            for selector in sidebar_selectors:
                try:
                    sidebar_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if sidebar_elements:
                        print(f"✅ Found sidebar navigation with selector: {selector}")
                        for link in sidebar_elements:
                            try:
                                text = link.text.strip()
                                href = link.get_attribute('href')
                                if text and href:
                                    navigation['sidebar_nav'].append({
                                        'text': text,
                                        'url': href,
                                        'selector': selector
                                    })
                            except:
                                continue
                        break
                except:
                    continue
                    
            # Look for user menu
            user_menu_selectors = [
                ".user-menu a",
                ".profile-menu a",
                ".account-menu a",
                ".dropdown-menu a",
                ".user-dropdown a"
            ]
            
            for selector in user_menu_selectors:
                try:
                    user_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if user_elements:
                        print(f"✅ Found user menu with selector: {selector}")
                        for link in user_elements:
                            try:
                                text = link.text.strip()
                                href = link.get_attribute('href')
                                if text and href:
                                    navigation['user_menu'].append({
                                        'text': text,
                                        'url': href,
                                        'selector': selector
                                    })
                            except:
                                continue
                        break
                except:
                    continue
                    
            print(f"📊 Navigation discovery complete:")
            print(f"   Primary nav items: {len(navigation['primary_nav'])}")
            print(f"   Sidebar nav items: {len(navigation['sidebar_nav'])}")  
            print(f"   User menu items: {len(navigation['user_menu'])}")
            
        except Exception as e:
            print(f"❌ Error discovering navigation: {e}")
            
        return navigation
        
    def discover_page_structure(self, url: str) -> Dict[str, Any]:
        """Analyze the structure of a specific page"""
        print(f"\n📄 Analyzing page structure: {url}")
        
        try:
            self.driver.get(url)
            time.sleep(3)  # Let page load
            
            structure = {
                'url': url,
                'title': self.driver.title,
                'h1_elements': [],
                'forms': [],
                'tables': [],
                'interactive_elements': [],
                'metadata': {}
            }
            
            # Get page title and headings
            try:
                h1_elements = self.driver.find_elements(By.TAG_NAME, "h1")
                structure['h1_elements'] = [h1.text.strip() for h1 in h1_elements if h1.text.strip()]
            except:
                pass
                
            # Discover forms
            try:
                forms = self.driver.find_elements(By.TAG_NAME, "form")
                for i, form in enumerate(forms):
                    form_data = {
                        'index': i,
                        'action': form.get_attribute('action'),
                        'method': form.get_attribute('method'),
                        'inputs': []
                    }
                    
                    inputs = form.find_elements(By.TAG_NAME, "input")
                    for inp in inputs:
                        form_data['inputs'].append({
                            'type': inp.get_attribute('type'),
                            'name': inp.get_attribute('name'),
                            'placeholder': inp.get_attribute('placeholder')
                        })
                    
                    structure['forms'].append(form_data)
            except:
                pass
                
            # Discover tables
            try:
                tables = self.driver.find_elements(By.TAG_NAME, "table")
                for i, table in enumerate(tables):
                    table_data = {
                        'index': i,
                        'headers': [],
                        'row_count': 0
                    }
                    
                    # Get headers
                    headers = table.find_elements(By.TAG_NAME, "th")
                    table_data['headers'] = [h.text.strip() for h in headers if h.text.strip()]
                    
                    # Count rows
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    table_data['row_count'] = len(rows)
                    
                    structure['tables'].append(table_data)
            except:
                pass
                
            # Discover interactive elements
            interactive_selectors = [
                "button",
                "input[type='submit']",
                "input[type='button']",
                "a[href]",
                "select",
                ".btn",
                ".button"
            ]
            
            for selector in interactive_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text:
                            structure['interactive_elements'].append({
                                'type': selector,
                                'text': text,
                                'id': elem.get_attribute('id'),
                                'class': elem.get_attribute('class')
                            })
                except:
                    continue
                    
            print(f"   📊 Page analysis complete:")
            print(f"      Title: {structure['title']}")
            print(f"      H1 elements: {len(structure['h1_elements'])}")
            print(f"      Forms: {len(structure['forms'])}")
            print(f"      Tables: {len(structure['tables'])}")
            print(f"      Interactive elements: {len(structure['interactive_elements'])}")
            
            return structure
            
        except Exception as e:
            print(f"❌ Error analyzing page {url}: {e}")
            return {'url': url, 'error': str(e)}
            
    def explore_portal_systematically(self) -> Dict[str, Any]:
        """Systematically explore the entire portal"""
        print("\n🚀 Starting systematic portal exploration...")
        
        exploration_results = {
            'start_time': datetime.now().isoformat(),
            'base_url': self.base_url,
            'authentication': {
                'auth_url': self.auth_url,
                'status': 'authenticated'
            },
            'discovered_urls': [],
            'navigation_structure': {},
            'page_structures': {},
            'exploration_summary': {}
        }
        
        try:
            # Start with current page after authentication
            current_url = self.driver.current_url
            print(f"📍 Starting exploration from: {current_url}")
            
            # Discover navigation structure
            navigation = self.discover_navigation_structure()
            exploration_results['navigation_structure'] = navigation
            
            # Collect all unique URLs from navigation
            all_urls = set()
            all_urls.add(current_url)
            
            for nav_section in navigation.values():
                for item in nav_section:
                    if 'url' in item and item['url']:
                        # Only include portal URLs
                        if 'portal.optix.earth' in item['url'] or item['url'].startswith('/'):
                            full_url = urljoin(self.base_url, item['url'])
                            all_urls.add(full_url)
            
            print(f"\n🔍 Found {len(all_urls)} unique URLs to explore")
            
            # Explore each discovered URL
            for url in all_urls:
                try:
                    print(f"\n🌐 Exploring: {url}")
                    structure = self.discover_page_structure(url)
                    exploration_results['page_structures'][url] = structure
                    exploration_results['discovered_urls'].append(url)
                    
                    # Small delay between pages
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"❌ Failed to explore {url}: {e}")
                    exploration_results['page_structures'][url] = {'error': str(e)}
                    
            # Generate summary
            exploration_results['exploration_summary'] = {
                'total_urls_discovered': len(exploration_results['discovered_urls']),
                'pages_successfully_analyzed': len([p for p in exploration_results['page_structures'].values() if 'error' not in p]),
                'navigation_sections_found': len([section for section in navigation.values() if section]),
                'end_time': datetime.now().isoformat()
            }
            
            print(f"\n✅ Exploration complete!")
            print(f"   📊 Total URLs discovered: {exploration_results['exploration_summary']['total_urls_discovered']}")
            print(f"   📄 Pages analyzed: {exploration_results['exploration_summary']['pages_successfully_analyzed']}")
            
            return exploration_results
            
        except Exception as e:
            print(f"❌ Error during systematic exploration: {e}")
            exploration_results['error'] = str(e)
            return exploration_results
            
    def generate_real_sitemap(self, exploration_results: Dict[str, Any]) -> str:
        """Generate actual sitemap from discovered data"""
        print("\n📝 Generating real sitemap from discovered data...")
        
        sitemap = {
            'optix_portal_sitemap': {
                'metadata': {
                    'discovery_method': 'Authenticated browser exploration',
                    'base_url': exploration_results['base_url'],
                    'discovery_timestamp': exploration_results['start_time'],
                    'total_pages_discovered': exploration_results['exploration_summary']['total_urls_discovered']
                },
                'authentication': exploration_results['authentication'],
                'discovered_pages': {},
                'navigation_structure': exploration_results['navigation_structure'],
                'site_architecture': {
                    'entry_point': exploration_results['base_url'],
                    'auth_gateway': exploration_results['authentication']['auth_url'],
                    'discovered_urls': exploration_results['discovered_urls']
                }
            }
        }
        
        # Process each discovered page
        for url, structure in exploration_results['page_structures'].items():
            if 'error' not in structure:
                page_info = {
                    'url': url,
                    'title': structure.get('title', 'Unknown'),
                    'page_type': self._classify_page_type(structure),
                    'content_summary': {
                        'headings': structure.get('h1_elements', []),
                        'forms_count': len(structure.get('forms', [])),
                        'tables_count': len(structure.get('tables', [])),
                        'interactive_elements_count': len(structure.get('interactive_elements', []))
                    },
                    'automation_potential': self._assess_automation_potential(structure)
                }
                
                # Add detailed structure if significant
                if structure.get('forms'):
                    page_info['forms'] = structure['forms']
                if structure.get('tables'):
                    page_info['tables'] = structure['tables']
                    
                sitemap['optix_portal_sitemap']['discovered_pages'][url] = page_info
                
        # Save sitemap
        sitemap_file = Path("optix_portal_real_sitemap.yaml")
        with open(sitemap_file, 'w') as f:
            yaml.dump(sitemap, f, default_flow_style=False, indent=2, sort_keys=False)
            
        print(f"✅ Real sitemap generated: {sitemap_file}")
        return str(sitemap_file)
        
    def _classify_page_type(self, structure: Dict[str, Any]) -> str:
        """Classify page type based on discovered structure"""
        title = structure.get('title', '').lower()
        h1s = ' '.join(structure.get('h1_elements', [])).lower()
        
        if 'dashboard' in title or 'dashboard' in h1s:
            return 'dashboard'
        elif 'admin' in title or 'admin' in h1s:
            return 'administration'
        elif 'data' in title or 'data' in h1s:
            return 'data_management'
        elif 'report' in title or 'report' in h1s:
            return 'reporting'
        elif 'setting' in title or 'setting' in h1s:
            return 'configuration'
        elif structure.get('forms'):
            return 'form_page'
        elif structure.get('tables'):
            return 'data_display'
        else:
            return 'general'
            
    def _assess_automation_potential(self, structure: Dict[str, Any]) -> str:
        """Assess automation potential based on page elements"""
        forms = len(structure.get('forms', []))
        tables = len(structure.get('tables', []))
        interactive = len(structure.get('interactive_elements', []))
        
        total_elements = forms * 3 + tables * 2 + interactive
        
        if total_elements > 15:
            return 'high'
        elif total_elements > 5:
            return 'medium'
        else:
            return 'low'
            
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("🧹 Browser cleanup complete")


def main():
    """Main execution function"""
    print("🚀 Authenticated Optix Portal Explorer")
    print("=" * 50)
    
    credentials_file = "/home/kiosk_user/optix-config.json"
    
    explorer = AuthenticatedOptixExplorer(credentials_file)
    
    try:
        # Setup browser
        explorer.setup_browser(headless=False)  # Use visible browser for debugging
        
        # Authenticate
        if not explorer.authenticate():
            print("❌ Authentication failed. Exiting.")
            return
            
        # Explore portal
        results = explorer.explore_portal_systematically()
        
        # Generate real sitemap
        sitemap_file = explorer.generate_real_sitemap(results)
        
        print(f"\n✅ Real Optix portal exploration complete!")
        print(f"📄 Sitemap saved to: {sitemap_file}")
        
    except Exception as e:
        print(f"❌ Exploration failed: {e}")
    finally:
        explorer.cleanup()


if __name__ == "__main__":
    main()