#!/usr/bin/env python3
"""
Intelligent Page Automation Engine
Loads YAML configurations and provides agentic automation capabilities
"""

import yaml
import time
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

@dataclass
class ElementInfo:
    """Information about a discovered page element"""
    tag_name: str
    text: str
    attributes: Dict[str, str]
    location: Dict[str, int]
    size: Dict[str, int]
    is_displayed: bool
    is_enabled: bool
    css_selector: str
    xpath: str

@dataclass
class PageMapping:
    """Complete mapping of a page's interactive elements"""
    url: str
    title: str
    elements: List[ElementInfo]
    navigation_items: List[Dict[str, Any]]
    forms: List[Dict[str, Any]]
    interactive_zones: List[Dict[str, Any]]
    timestamp: float

class AgenticPageAutomation:
    """
    Intelligent automation engine that can:
    1. Load page configurations from YAML
    2. Dynamically discover page elements
    3. Execute complex workflows
    4. Make intelligent decisions about automation paths
    """
    
    def __init__(self, config_directory: str = "page_configs"):
        self.config_dir = Path(config_directory)
        self.driver = None
        self.wait = None
        self.page_configs = {}
        self.discovered_elements = {}
        self.site_map = {}
        self.automation_state = {}
        
    def setup_driver(self, headless: bool = False, user_data_dir: str = None):
        """Setup Chrome WebDriver with optimal settings"""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless")
            
        if user_data_dir:
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
            
        # Performance and automation optimizations
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 10)
        
    def load_page_config(self, config_name: str) -> Dict[str, Any]:
        """Load YAML configuration for a specific page"""
        config_path = self.config_dir / f"{config_name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Page config not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        self.page_configs[config_name] = config
        return config
        
    def auto_detect_page(self, url: str) -> Optional[str]:
        """Automatically detect which page configuration to use"""
        for config_name, config in self.page_configs.items():
            if 'page_info' in config and 'url_pattern' in config['page_info']:
                pattern = config['page_info']['url_pattern']
                if self._matches_pattern(url, pattern):
                    return config_name
        return None
        
    def _matches_pattern(self, url: str, pattern: str) -> bool:
        """Check if URL matches a pattern (supports wildcards)"""
        import fnmatch
        return fnmatch.fnmatch(url, pattern)
        
    def intelligent_element_discovery(self, page_config: Dict[str, Any] = None) -> PageMapping:
        """Discover all interactive elements on the current page"""
        current_url = self.driver.current_url
        page_title = self.driver.title
        
        elements = []
        navigation_items = []
        forms = []
        interactive_zones = []
        
        # Discover clickable elements
        clickable_selectors = [
            "button", "a[href]", "input[type='button']", "input[type='submit']", 
            "[role='button']", "[onclick]", ".btn", ".button"
        ]
        
        for selector in clickable_selectors:
            try:
                found_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in found_elements:
                    if elem.is_displayed() and elem.is_enabled():
                        element_info = self._extract_element_info(elem)
                        elements.append(element_info)
            except Exception as e:
                logger.warning(f"Error discovering elements with selector {selector}: {e}")
                
        # Discover navigation elements
        nav_selectors = ["nav a", ".navbar a", ".menu a", ".navigation a"]
        for selector in nav_selectors:
            try:
                nav_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for nav_elem in nav_elements:
                    if nav_elem.is_displayed():
                        nav_info = {
                            'text': nav_elem.text.strip(),
                            'href': nav_elem.get_attribute('href'),
                            'selector': self._generate_css_selector(nav_elem)
                        }
                        navigation_items.append(nav_info)
            except Exception as e:
                logger.warning(f"Error discovering navigation with selector {selector}: {e}")
                
        # Discover forms
        try:
            form_elements = self.driver.find_elements(By.TAG_NAME, "form")
            for form in form_elements:
                form_info = self._analyze_form(form)
                forms.append(form_info)
        except Exception as e:
            logger.warning(f"Error discovering forms: {e}")
            
        # Apply page-specific discovery if config provided
        if page_config and 'discovery_patterns' in page_config:
            self._apply_discovery_patterns(page_config['discovery_patterns'], elements, interactive_zones)
            
        mapping = PageMapping(
            url=current_url,
            title=page_title,
            elements=elements,
            navigation_items=navigation_items,
            forms=forms,
            interactive_zones=interactive_zones,
            timestamp=time.time()
        )
        
        self.discovered_elements[current_url] = mapping
        return mapping
        
    def _extract_element_info(self, element) -> ElementInfo:
        """Extract comprehensive information about an element"""
        try:
            return ElementInfo(
                tag_name=element.tag_name,
                text=element.text.strip()[:100],  # Truncate long text
                attributes=element.get_property('attributes') or {},
                location=element.location,
                size=element.size,
                is_displayed=element.is_displayed(),
                is_enabled=element.is_enabled(),
                css_selector=self._generate_css_selector(element),
                xpath=self._generate_xpath(element)
            )
        except Exception as e:
            logger.warning(f"Error extracting element info: {e}")
            return None
            
    def _generate_css_selector(self, element) -> str:
        """Generate a CSS selector for an element"""
        try:
            # Simple approach - use ID if available
            elem_id = element.get_attribute('id')
            if elem_id:
                return f"#{elem_id}"
                
            # Use class if available
            classes = element.get_attribute('class')
            if classes:
                class_selector = '.' + '.'.join(classes.split())
                return f"{element.tag_name}{class_selector}"
                
            # Fallback to tag name
            return element.tag_name
        except:
            return element.tag_name
            
    def _generate_xpath(self, element) -> str:
        """Generate XPath for an element"""
        try:
            return self.driver.execute_script(
                "function getXPath(element) {"
                "  if (element.id) return '//*[@id=\"' + element.id + '\"]';"
                "  if (element.tagName === 'BODY') return '/html/body';"
                "  var ix = 0;"
                "  var siblings = element.parentNode.childNodes;"
                "  for (var i = 0; i < siblings.length; i++) {"
                "    var sibling = siblings[i];"
                "    if (sibling === element) return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';"
                "    if (sibling.nodeType === 1 && sibling.tagName === element.tagName) ix++;"
                "  }"
                "};"
                "return getXPath(arguments[0]);", element
            )
        except:
            return ""
            
    def _analyze_form(self, form_element) -> Dict[str, Any]:
        """Analyze form structure and input fields"""
        try:
            inputs = form_element.find_elements(By.CSS_SELECTOR, "input, textarea, select")
            
            form_info = {
                'action': form_element.get_attribute('action'),
                'method': form_element.get_attribute('method') or 'GET',
                'inputs': [],
                'selector': self._generate_css_selector(form_element)
            }
            
            for input_elem in inputs:
                input_info = {
                    'type': input_elem.get_attribute('type'),
                    'name': input_elem.get_attribute('name'),
                    'id': input_elem.get_attribute('id'),
                    'placeholder': input_elem.get_attribute('placeholder'),
                    'required': input_elem.get_attribute('required') is not None,
                    'selector': self._generate_css_selector(input_elem)
                }
                form_info['inputs'].append(input_info)
                
            return form_info
        except Exception as e:
            logger.warning(f"Error analyzing form: {e}")
            return {}
            
    def _apply_discovery_patterns(self, patterns: Dict, elements: List, interactive_zones: List):
        """Apply page-specific discovery patterns"""
        for pattern_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                try:
                    css_selector = pattern.get('css', '')
                    if css_selector:
                        found_elements = self.driver.find_elements(By.CSS_SELECTOR, css_selector)
                        for elem in found_elements:
                            if elem.is_displayed():
                                zone_info = {
                                    'type': pattern_type,
                                    'description': pattern.get('description', ''),
                                    'selector': css_selector,
                                    'element_info': self._extract_element_info(elem)
                                }
                                interactive_zones.append(zone_info)
                except Exception as e:
                    logger.warning(f"Error applying discovery pattern {pattern}: {e}")
                    
    def execute_workflow(self, workflow_name: str, config_name: str, test_data: Dict = None) -> bool:
        """Execute a predefined workflow from page configuration"""
        if config_name not in self.page_configs:
            self.load_page_config(config_name)
            
        config = self.page_configs[config_name]
        
        if 'workflows' not in config or workflow_name not in config['workflows']:
            logger.error(f"Workflow '{workflow_name}' not found in config '{config_name}'")
            return False
            
        workflow = config['workflows'][workflow_name]
        logger.info(f"Executing workflow: {workflow.get('description', workflow_name)}")
        
        try:
            for step in workflow['steps']:
                success = self._execute_step(step, config, test_data)
                if not success:
                    logger.error(f"Workflow step failed: {step}")
                    return False
                    
            logger.info(f"Workflow '{workflow_name}' completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error executing workflow '{workflow_name}': {e}")
            return False
            
    def _execute_step(self, step: Dict, config: Dict, test_data: Dict = None) -> bool:
        """Execute a single workflow step"""
        action = step['action']
        
        try:
            if action == "wait_for_element":
                return self._wait_for_element(step, config)
            elif action == "click":
                return self._click_element(step, config)
            elif action == "input_text":
                return self._input_text(step, config, test_data)
            elif action == "select_option":
                return self._select_option(step, config, test_data)
            elif action == "wait_for_redirect":
                return self._wait_for_redirect(step)
            elif action == "scan_navigation":
                return self._scan_navigation()
            elif action == "catalog_interactive_elements":
                return self._catalog_interactive_elements()
            else:
                logger.warning(f"Unknown action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing step {action}: {e}")
            return False
            
    def _wait_for_element(self, step: Dict, config: Dict) -> bool:
        """Wait for an element to be present"""
        element_name = step['element']
        if element_name not in config.get('selectors', {}):
            return False
            
        selector_info = config['selectors'][element_name]
        css_selector = selector_info.get('css', '')
        
        if css_selector:
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_selector)))
                return True
            except TimeoutException:
                return False
        return False
        
    def _click_element(self, step: Dict, config: Dict) -> bool:
        """Click an element"""
        element_name = step['element']
        if element_name not in config.get('selectors', {}):
            return False
            
        selector_info = config['selectors'][element_name]
        css_selector = selector_info.get('css', '')
        
        if css_selector:
            try:
                element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
                element.click()
                return True
            except (TimeoutException, NoSuchElementException):
                return False
        return False
        
    def _input_text(self, step: Dict, config: Dict, test_data: Dict = None) -> bool:
        """Input text into a field"""
        element_name = step['element']
        data_key = step.get('data_key')
        
        if not data_key or not test_data or data_key not in test_data:
            return False
            
        if element_name not in config.get('selectors', {}):
            return False
            
        selector_info = config['selectors'][element_name]
        css_selector = selector_info.get('css', '')
        
        if css_selector:
            try:
                element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
                element.clear()
                element.send_keys(test_data[data_key])
                return True
            except (TimeoutException, NoSuchElementException):
                return False
        return False
        
    def _select_option(self, step: Dict, config: Dict, test_data: Dict = None) -> bool:
        """Select an option from dropdown"""
        element_name = step['element']
        data_key = step.get('data_key')
        
        if not data_key or not test_data or data_key not in test_data:
            return False
            
        if element_name not in config.get('selectors', {}):
            return False
            
        selector_info = config['selectors'][element_name]
        css_selector = selector_info.get('css', '')
        
        if css_selector:
            try:
                from selenium.webdriver.support.ui import Select
                element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
                select = Select(element)
                select.select_by_visible_text(test_data[data_key])
                return True
            except (TimeoutException, NoSuchElementException):
                return False
        return False
        
    def _wait_for_redirect(self, step: Dict) -> bool:
        """Wait for page redirect"""
        expected_url = step.get('expected_url_contains', '')
        if expected_url:
            try:
                WebDriverWait(self.driver, 30).until(
                    lambda driver: expected_url in driver.current_url
                )
                return True
            except TimeoutException:
                return False
        return True
        
    def _scan_navigation(self) -> bool:
        """Scan and catalog navigation elements"""
        try:
            nav_elements = self.driver.find_elements(By.CSS_SELECTOR, "nav a, .navbar a, .menu a")
            navigation_map = []
            
            for nav_elem in nav_elements:
                if nav_elem.is_displayed():
                    nav_info = {
                        'text': nav_elem.text.strip(),
                        'href': nav_elem.get_attribute('href'),
                        'selector': self._generate_css_selector(nav_elem)
                    }
                    navigation_map.append(nav_info)
                    
            self.site_map[self.driver.current_url] = {
                'navigation': navigation_map,
                'timestamp': time.time()
            }
            return True
        except Exception as e:
            logger.error(f"Error scanning navigation: {e}")
            return False
            
    def _catalog_interactive_elements(self) -> bool:
        """Catalog all interactive elements"""
        try:
            mapping = self.intelligent_element_discovery()
            logger.info(f"Catalogued {len(mapping.elements)} interactive elements")
            return True
        except Exception as e:
            logger.error(f"Error cataloging elements: {e}")
            return False
            
    def navigate_and_explore(self, url: str) -> PageMapping:
        """Navigate to URL and perform intelligent exploration"""
        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            
            # Auto-detect page type
            page_type = self.auto_detect_page(url)
            config = None
            
            if page_type:
                logger.info(f"Detected page type: {page_type}")
                config = self.page_configs[page_type]
                
                # Wait for page-specific elements
                page_info = config.get('page_info', {})
                wait_for = page_info.get('wait_for', '')
                if wait_for:
                    try:
                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_for)))
                    except TimeoutException:
                        logger.warning(f"Timeout waiting for: {wait_for}")
                        
            # Perform intelligent discovery
            mapping = self.intelligent_element_discovery(config)
            
            logger.info(f"Page exploration complete:")
            logger.info(f"  - {len(mapping.elements)} interactive elements")
            logger.info(f"  - {len(mapping.navigation_items)} navigation items")
            logger.info(f"  - {len(mapping.forms)} forms")
            logger.info(f"  - {len(mapping.interactive_zones)} interactive zones")
            
            return mapping
            
        except Exception as e:
            logger.error(f"Error exploring page {url}: {e}")
            return None
            
    def generate_automation_report(self) -> Dict[str, Any]:
        """Generate comprehensive automation report"""
        report = {
            'timestamp': time.time(),
            'total_pages_explored': len(self.discovered_elements),
            'site_map': self.site_map,
            'pages': {}
        }
        
        for url, mapping in self.discovered_elements.items():
            report['pages'][url] = {
                'title': mapping.title,
                'element_count': len(mapping.elements),
                'navigation_count': len(mapping.navigation_items),
                'form_count': len(mapping.forms),
                'interactive_zone_count': len(mapping.interactive_zones),
                'exploration_timestamp': mapping.timestamp
            }
            
        return report
        
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()