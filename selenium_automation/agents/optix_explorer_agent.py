#!/usr/bin/env python3
"""
Optix Portal Explorer Agent
Intelligent agent for exploring and mapping the Optix Earth portal
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from automation.page_automation import AgenticPageAutomation

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OptixExplorerAgent:
    """
    Intelligent agent that can:
    1. Handle Auth0 authentication flow
    2. Systematically explore the Optix portal
    3. Map all available functionality
    4. Generate comprehensive automation guides
    5. Adapt to new page structures
    """
    
    def __init__(self, config_dir: str = "page_configs"):
        self.automation = AgenticPageAutomation(config_dir)
        self.exploration_results = {}
        self.discovered_workflows = []
        self.automation_opportunities = []
        
    def setup_browser(self, headless: bool = False, persist_session: bool = True):
        """Setup browser with session persistence for authentication"""
        user_data_dir = None
        if persist_session:
            user_data_dir = str(Path.home() / ".selenium_profiles" / "optix_session")
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)
            
        self.automation.setup_driver(headless=headless, user_data_dir=user_data_dir)
        
    def authenticate_if_needed(self, credentials: Dict[str, str] = None) -> bool:
        """Handle authentication flow if needed"""
        try:
            current_url = self.automation.driver.current_url
            
            # Check if we're on Auth0 login page
            if "auth0.com" in current_url:
                logger.info("Authentication required - loading Auth0 configuration")
                
                # Load Auth0 configuration
                auth_config = self.automation.load_page_config("auth0_login")
                
                if credentials:
                    logger.info("Attempting to authenticate with provided credentials")
                    success = self.automation.execute_workflow("login", "auth0_login", credentials)
                    
                    if success:
                        logger.info("Authentication successful")
                        # Wait for redirect to portal
                        time.sleep(5)
                        return True
                    else:
                        logger.error("Authentication failed")
                        return False
                else:
                    logger.warning("Authentication required but no credentials provided")
                    # Still analyze the auth page
                    self.automation.navigate_and_explore(current_url)
                    return False
            else:
                logger.info("Already authenticated or no authentication required")
                return True
                
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return False
            
    def intelligent_portal_exploration(self) -> Dict[str, Any]:
        """
        Systematically explore the entire portal using intelligent strategies
        """
        exploration_start = time.time()
        
        # Step 1: Initial page analysis
        logger.info("=== Starting Intelligent Portal Exploration ===")
        initial_mapping = self.automation.navigate_and_explore(self.automation.driver.current_url)
        
        if not initial_mapping:
            logger.error("Failed to create initial page mapping")
            return {}
            
        # Step 2: Navigation discovery and mapping
        logger.info("=== Discovering Navigation Structure ===")
        navigation_map = self._discover_navigation_structure(initial_mapping)
        
        # Step 3: Systematic page exploration
        logger.info("=== Systematic Page Exploration ===")
        pages_explored = self._explore_discovered_pages(navigation_map)
        
        # Step 4: Form and workflow analysis
        logger.info("=== Analyzing Forms and Workflows ===")
        workflow_analysis = self._analyze_workflows_and_forms()
        
        # Step 5: Generate automation opportunities
        logger.info("=== Identifying Automation Opportunities ===")
        automation_opportunities = self._identify_automation_opportunities()
        
        exploration_duration = time.time() - exploration_start
        
        # Compile comprehensive results
        results = {
            'exploration_metadata': {
                'start_time': exploration_start,
                'duration_seconds': exploration_duration,
                'total_pages_explored': len(pages_explored),
                'total_navigation_items': len(navigation_map),
                'timestamp': time.time()
            },
            'initial_mapping': initial_mapping,
            'navigation_structure': navigation_map,
            'pages_explored': pages_explored,
            'workflow_analysis': workflow_analysis,
            'automation_opportunities': automation_opportunities,
            'comprehensive_site_map': self.automation.site_map
        }
        
        self.exploration_results = results
        logger.info(f"=== Exploration Complete: {exploration_duration:.2f}s ===")
        
        return results
        
    def _discover_navigation_structure(self, initial_mapping) -> List[Dict[str, Any]]:
        """Analyze navigation structure and create exploration plan"""
        navigation_items = []
        
        # Extract navigation from initial mapping
        for nav_item in initial_mapping.navigation_items:
            if nav_item['href'] and not nav_item['href'].startswith('#'):
                navigation_items.append({
                    'text': nav_item['text'],
                    'url': nav_item['href'],
                    'selector': nav_item['selector'],
                    'priority': self._calculate_navigation_priority(nav_item),
                    'explored': False
                })
                
        # Sort by priority for intelligent exploration order
        navigation_items.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"Discovered {len(navigation_items)} navigation targets")
        for item in navigation_items[:5]:  # Log top 5
            logger.info(f"  - {item['text']} (priority: {item['priority']})")
            
        return navigation_items
        
    def _calculate_navigation_priority(self, nav_item: Dict[str, str]) -> float:
        """Calculate exploration priority for navigation items"""
        text = nav_item['text'].lower()
        url = nav_item['href'].lower() if nav_item['href'] else ""
        
        priority = 1.0  # Base priority
        
        # High priority items
        high_priority_keywords = ['dashboard', 'home', 'main', 'overview', 'summary']
        if any(keyword in text for keyword in high_priority_keywords):
            priority += 2.0
            
        # Medium priority items
        medium_priority_keywords = ['data', 'reports', 'analytics', 'tools', 'settings']
        if any(keyword in text for keyword in medium_priority_keywords):
            priority += 1.0
            
        # Low priority items (but still explore)
        low_priority_keywords = ['help', 'support', 'about', 'contact']
        if any(keyword in text for keyword in low_priority_keywords):
            priority += 0.5
            
        # Adjust based on URL structure
        if 'api' in url or 'json' in url:
            priority -= 1.0  # Lower priority for API endpoints
            
        return max(priority, 0.1)  # Minimum priority
        
    def _explore_discovered_pages(self, navigation_map: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Systematically explore all discovered pages"""
        pages_explored = {}
        
        for nav_item in navigation_map:
            if nav_item['explored']:
                continue
                
            try:
                logger.info(f"Exploring: {nav_item['text']} -> {nav_item['url']}")
                
                # Navigate to the page
                mapping = self.automation.navigate_and_explore(nav_item['url'])
                
                if mapping:
                    pages_explored[nav_item['url']] = {
                        'navigation_source': nav_item,
                        'page_mapping': mapping,
                        'exploration_timestamp': time.time()
                    }
                    nav_item['explored'] = True
                    
                    # Brief pause between page explorations
                    time.sleep(2)
                    
                    logger.info(f"  ✓ Mapped {len(mapping.elements)} elements")
                else:
                    logger.warning(f"  ✗ Failed to map {nav_item['url']}")
                    
            except Exception as e:
                logger.error(f"Error exploring {nav_item['url']}: {e}")
                
        return pages_explored
        
    def _analyze_workflows_and_forms(self) -> Dict[str, Any]:
        """Analyze discovered forms and identify potential workflows"""
        workflow_analysis = {
            'forms_discovered': [],
            'potential_workflows': [],
            'data_entry_points': [],
            'action_sequences': []
        }
        
        # Analyze forms across all discovered pages
        for url, page_data in self.exploration_results.get('pages_explored', {}).items():
            mapping = page_data['page_mapping']
            
            for form in mapping.forms:
                form_analysis = {
                    'url': url,
                    'form_selector': form['selector'],
                    'input_count': len(form['inputs']),
                    'input_types': [inp['type'] for inp in form['inputs']],
                    'required_fields': [inp['name'] for inp in form['inputs'] if inp['required']],
                    'complexity_score': self._calculate_form_complexity(form)
                }
                workflow_analysis['forms_discovered'].append(form_analysis)
                
                # Identify potential automation workflows
                if form_analysis['complexity_score'] > 2:
                    workflow_analysis['potential_workflows'].append({
                        'type': 'form_automation',
                        'description': f"Automate form on {url}",
                        'complexity': form_analysis['complexity_score'],
                        'form_details': form_analysis
                    })
                    
        return workflow_analysis
        
    def _calculate_form_complexity(self, form: Dict[str, Any]) -> float:
        """Calculate form complexity for automation prioritization"""
        complexity = 0
        
        for input_field in form['inputs']:
            input_type = input_field.get('type', 'text')
            
            if input_type in ['text', 'email', 'password']:
                complexity += 1
            elif input_type in ['select', 'radio', 'checkbox']:
                complexity += 1.5
            elif input_type in ['file', 'date', 'datetime']:
                complexity += 2
                
            if input_field.get('required'):
                complexity += 0.5
                
        return complexity
        
    def _identify_automation_opportunities(self) -> List[Dict[str, Any]]:
        """Identify high-value automation opportunities"""
        opportunities = []
        
        # Analyze repetitive actions
        for url, page_data in self.exploration_results.get('pages_explored', {}).items():
            mapping = page_data['page_mapping']
            
            # Look for data tables (potential for data extraction)
            table_elements = [elem for elem in mapping.elements if elem.tag_name == 'table']
            if table_elements:
                opportunities.append({
                    'type': 'data_extraction',
                    'description': f"Extract data from tables on {url}",
                    'url': url,
                    'element_count': len(table_elements),
                    'priority': 'high',
                    'estimated_effort': 'medium'
                })
                
            # Look for repetitive button patterns
            button_elements = [elem for elem in mapping.elements 
                             if elem.tag_name in ['button', 'input'] and 'click' in elem.text.lower()]
            if len(button_elements) > 5:
                opportunities.append({
                    'type': 'bulk_actions',
                    'description': f"Automate bulk actions on {url}",
                    'url': url,
                    'action_count': len(button_elements),
                    'priority': 'medium',
                    'estimated_effort': 'low'
                })
                
            # Look for forms (potential for automated data entry)
            if len(mapping.forms) > 0:
                for form in mapping.forms:
                    if len(form['inputs']) > 3:  # Complex forms
                        opportunities.append({
                            'type': 'form_automation',
                            'description': f"Automate form completion on {url}",
                            'url': url,
                            'form_complexity': len(form['inputs']),
                            'priority': 'high',
                            'estimated_effort': 'high'
                        })
                        
        # Sort by priority and potential impact
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        opportunities.sort(key=lambda x: priority_order.get(x['priority'], 0), reverse=True)
        
        return opportunities
        
    def generate_yaml_configs(self, output_dir: str = "generated_configs") -> Dict[str, str]:
        """Generate YAML configurations for all discovered pages"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        generated_configs = {}
        
        for url, page_data in self.exploration_results.get('pages_explored', {}).items():
            mapping = page_data['page_mapping']
            
            # Generate config filename from URL
            config_name = self._url_to_config_name(url)
            config_file = output_path / f"{config_name}.yaml"
            
            # Generate YAML configuration
            config = self._generate_page_config(url, mapping)
            
            # Write to file
            with open(config_file, 'w') as f:
                import yaml
                yaml.dump(config, f, default_flow_style=False, indent=2)
                
            generated_configs[config_name] = str(config_file)
            logger.info(f"Generated config: {config_file}")
            
        return generated_configs
        
    def _url_to_config_name(self, url: str) -> str:
        """Convert URL to valid config filename"""
        import re
        # Extract meaningful parts of URL
        name = re.sub(r'https?://', '', url)
        name = re.sub(r'[^\w\-_]', '_', name)
        name = re.sub(r'_+', '_', name)
        return name.strip('_').lower()
        
    def _generate_page_config(self, url: str, mapping) -> Dict[str, Any]:
        """Generate YAML page configuration from discovered mapping"""
        
        # Extract selectors from discovered elements
        selectors = {}
        
        for elem in mapping.elements:
            if elem.text and len(elem.text.strip()) > 0:
                # Generate meaningful selector names
                selector_name = self._generate_selector_name(elem)
                selectors[selector_name] = {
                    'css': elem.css_selector,
                    'xpath': elem.xpath if elem.xpath else None,
                    'description': elem.text[:50],
                    'tag_name': elem.tag_name,
                    'action_type': self._determine_action_type(elem)
                }
                
        # Generate workflows based on discovered elements
        workflows = {}
        
        if mapping.forms:
            workflows['form_interaction'] = {
                'description': 'Interact with forms on this page',
                'steps': [
                    {'action': 'wait_for_page_load'},
                    {'action': 'catalog_interactive_elements'}
                ]
            }
            
        if mapping.navigation_items:
            workflows['navigation_discovery'] = {
                'description': 'Discover and map navigation options',
                'steps': [
                    {'action': 'scan_navigation'},
                    {'action': 'catalog_interactive_elements'}
                ]
            }
            
        config = {
            'page_info': {
                'name': mapping.title or 'Discovered Page',
                'url_pattern': url,
                'description': f'Auto-generated config for {url}',
                'discovery_timestamp': mapping.timestamp
            },
            'selectors': selectors,
            'workflows': workflows,
            'automation_opportunities': [
                opp for opp in self.automation_opportunities 
                if opp.get('url') == url
            ]
        }
        
        return config
        
    def _generate_selector_name(self, elem) -> str:
        """Generate meaningful selector name from element"""
        text = elem.text.strip() if elem.text else ''
        tag = elem.tag_name
        
        if text:
            # Use text content for naming
            name = re.sub(r'[^\w\s]', '', text)
            name = re.sub(r'\s+', '_', name.lower())
            return f"{tag}_{name[:20]}"
        else:
            # Use tag name with attributes
            elem_id = elem.attributes.get('id', '')
            if elem_id:
                return f"{tag}_{elem_id}"
            else:
                return f"{tag}_element"
                
    def _determine_action_type(self, elem) -> str:
        """Determine the primary action type for an element"""
        tag = elem.tag_name.lower()
        text = elem.text.lower() if elem.text else ''
        
        if tag in ['button', 'a']:
            return 'click'
        elif tag == 'input':
            return 'input'
        elif 'submit' in text or 'send' in text:
            return 'submit'
        elif 'search' in text:
            return 'search'
        else:
            return 'interact'
            
    def create_comprehensive_report(self, output_file: str = "optix_exploration_report.json") -> str:
        """Create comprehensive exploration report"""
        
        if not self.exploration_results:
            logger.error("No exploration results available. Run exploration first.")
            return ""
            
        # Add summary statistics
        summary = {
            'total_pages_explored': len(self.exploration_results.get('pages_explored', {})),
            'total_interactive_elements': sum(
                len(page['page_mapping'].elements) 
                for page in self.exploration_results.get('pages_explored', {}).values()
            ),
            'total_forms_found': sum(
                len(page['page_mapping'].forms)
                for page in self.exploration_results.get('pages_explored', {}).values()
            ),
            'total_navigation_items': sum(
                len(page['page_mapping'].navigation_items)
                for page in self.exploration_results.get('pages_explored', {}).values()
            ),
            'automation_opportunities': len(self.automation_opportunities),
            'generated_configs': None  # Will be filled when configs are generated
        }
        
        # Create final report
        report = {
            'exploration_summary': summary,
            'detailed_results': self.exploration_results,
            'automation_recommendations': self._generate_automation_recommendations()
        }
        
        # Save report
        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
            
        logger.info(f"Comprehensive report saved to: {output_path}")
        return str(output_path)
        
    def _generate_automation_recommendations(self) -> List[Dict[str, Any]]:
        """Generate specific automation recommendations"""
        recommendations = []
        
        # High-level recommendations based on discovered patterns
        if len(self.automation_opportunities) > 0:
            recommendations.append({
                'type': 'immediate_automation',
                'priority': 'high',
                'description': f'Implement automation for {len(self.automation_opportunities)} identified opportunities',
                'next_steps': [
                    'Review generated YAML configurations',
                    'Implement custom workflow scripts',
                    'Set up automated testing pipeline'
                ]
            })
            
        # Form automation recommendations
        form_opportunities = [opp for opp in self.automation_opportunities if opp['type'] == 'form_automation']
        if form_opportunities:
            recommendations.append({
                'type': 'form_automation',
                'priority': 'high',
                'description': f'Automate {len(form_opportunities)} complex forms for data entry efficiency',
                'estimated_time_savings': f'{len(form_opportunities) * 5} minutes per form completion'
            })
            
        # Data extraction recommendations
        data_opportunities = [opp for opp in self.automation_opportunities if opp['type'] == 'data_extraction']
        if data_opportunities:
            recommendations.append({
                'type': 'data_extraction',
                'priority': 'medium',
                'description': f'Implement automated data extraction for {len(data_opportunities)} data sources',
                'business_value': 'Enable automated reporting and data analysis'
            })
            
        return recommendations

# Usage Example and CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Optix Portal Explorer Agent')
    parser.add_argument('--url', default='https://portal.optix.earth/?wid=b266670b86fc72c90004f1', 
                       help='Portal URL to explore')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--credentials-file', help='JSON file with login credentials')
    parser.add_argument('--output-dir', default='exploration_results', help='Output directory for results')
    
    args = parser.parse_args()
    
    # Create output directory
    output_path = Path(args.output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Load credentials if provided
    credentials = None
    if args.credentials_file:
        try:
            with open(args.credentials_file, 'r') as f:
                credentials = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
    
    # Run exploration
    logger.info("Starting Optix Portal Exploration Agent")
    
    with OptixExplorerAgent() as agent:
        try:
            # Setup browser
            agent.setup_browser(headless=args.headless, persist_session=True)
            
            # Navigate to portal
            agent.automation.driver.get(args.url)
            
            # Handle authentication
            auth_success = agent.authenticate_if_needed(credentials)
            if not auth_success and credentials:
                logger.error("Authentication failed, continuing with limited exploration")
            
            # Perform comprehensive exploration
            results = agent.intelligent_portal_exploration()
            
            # Generate configurations
            config_files = agent.generate_yaml_configs(str(output_path / "configs"))
            
            # Create comprehensive report
            report_file = agent.create_comprehensive_report(str(output_path / "exploration_report.json"))
            
            logger.info("=== Exploration Complete ===")
            logger.info(f"Results saved to: {output_path}")
            logger.info(f"Generated {len(config_files)} YAML configurations")
            logger.info(f"Comprehensive report: {report_file}")
            
        except KeyboardInterrupt:
            logger.info("Exploration interrupted by user")
        except Exception as e:
            logger.error(f"Exploration failed: {e}")
            raise