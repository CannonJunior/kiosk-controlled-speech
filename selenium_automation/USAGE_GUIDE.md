# Optix Portal Automation Framework - Complete Usage Guide

## 🎯 Overview

This framework provides intelligent, agentic automation for web applications using Selenium with YAML-driven configuration. It's specifically designed for the Optix Earth portal but is extensible to any web application.

## 🚀 Quick Start

### 1. Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Chrome WebDriver (automatic with webdriver-manager)
```

### 2. Configuration Setup

```bash
# Copy credentials template
cp credentials_template.json credentials.json

# Edit credentials with your actual login details
nano credentials.json
```

### 3. Basic Exploration

```bash
# Run the explorer agent
python agents/optix_explorer_agent.py --credentials-file credentials.json
```

## 📁 Framework Architecture

```
selenium_automation/
├── README.md                    # Project overview
├── USAGE_GUIDE.md              # This guide
├── requirements.txt             # Dependencies
├── credentials_template.json    # Credential template
├── 
├── page_configs/               # YAML page configurations
│   ├── auth0_login.yaml        # Auth0 authentication
│   └── optix_portal.yaml       # Main portal
├── 
├── automation/                 # Core automation engine
│   └── page_automation.py      # Main automation class
├── 
├── agents/                     # Intelligent automation agents
│   └── optix_explorer_agent.py # Optix portal explorer
├── 
└── generated_configs/          # Auto-generated configurations
    └── (runtime generated)
```

## 🎪 Core Components

### 1. YAML Page Configurations

Each page is defined by a YAML configuration containing:

- **Page Info**: URL patterns, wait conditions, framework detection
- **Selectors**: CSS/XPath selectors for interactive elements
- **Workflows**: Step-by-step automation sequences
- **Test Scenarios**: Predefined test cases

#### Example: Auth0 Login Configuration

```yaml
page_info:
  name: "Optix Auth0 Login"
  url_pattern: "https://optix-emd.us.auth0.com/authorize*"
  wait_for: ".auth0-lock-widget"

selectors:
  email_field:
    css: "input[name='email']"
    description: "Email input field"
    required: true

workflows:
  login:
    description: "Standard login flow"
    steps:
      - action: "wait_for_element"
        element: "login_widget"
      - action: "input_text"
        element: "email_field"
        data_key: "email"
```

### 2. Intelligent Page Automation

The `AgenticPageAutomation` class provides:

- **Dynamic Element Discovery**: Automatically finds interactive elements
- **Framework Detection**: Identifies React, Vue, Angular applications
- **Smart Workflows**: Executes complex multi-step procedures
- **Error Recovery**: Handles timeouts and missing elements
- **Session Persistence**: Maintains authentication across sessions

### 3. Explorer Agent

The `OptixExplorerAgent` provides:

- **Systematic Exploration**: Methodically maps entire applications
- **Priority-Based Navigation**: Explores high-value areas first
- **Workflow Discovery**: Identifies automation opportunities
- **Config Generation**: Creates YAML configurations automatically
- **Comprehensive Reporting**: Detailed analysis and recommendations

## 🛠 Advanced Usage

### Custom Page Configuration

Create a new YAML file for a specific page:

```yaml
# page_configs/custom_page.yaml
page_info:
  name: "Custom Page"
  url_pattern: "https://example.com/custom*"
  wait_for: ".page-content"

selectors:
  submit_button:
    css: "button[type='submit']"
    description: "Submit form button"
    action_type: "click"

workflows:
  custom_workflow:
    description: "Custom automation workflow"
    steps:
      - action: "wait_for_element"
        element: "submit_button"
      - action: "click"
        element: "submit_button"
```

### Programmatic Usage

```python
from automation.page_automation import AgenticPageAutomation

# Initialize automation
automation = AgenticPageAutomation()
automation.setup_driver(headless=False)

# Load configuration
config = automation.load_page_config("optix_portal")

# Navigate and explore
mapping = automation.navigate_and_explore("https://portal.optix.earth/")

# Execute workflow
success = automation.execute_workflow("login", "auth0_login", {
    "email": "user@example.com",
    "password": "password123"
})

# Generate report
report = automation.generate_automation_report()
```

### Extending Workflows

Add custom workflow steps by extending the `_execute_step` method:

```python
class CustomAutomation(AgenticPageAutomation):
    def _execute_step(self, step, config, test_data=None):
        action = step['action']
        
        if action == "custom_action":
            return self._custom_action(step, config, test_data)
        else:
            return super()._execute_step(step, config, test_data)
            
    def _custom_action(self, step, config, test_data):
        # Implement your custom action
        pass
```

## 🔧 Configuration Options

### Driver Configuration

```python
automation.setup_driver(
    headless=False,           # Run in visible browser
    user_data_dir="/path/to/profile",  # Persistent browser profile
)
```

### Exploration Settings

```python
agent = OptixExplorerAgent()
agent.setup_browser(
    headless=False,           # Visible browser for debugging
    persist_session=True      # Maintain login sessions
)
```

### Automation Rules

Configure intelligent automation behavior in YAML:

```yaml
automation_rules:
  form_strategies:
    text_inputs:
      - strategy: "smart_defaults"
        conditions: "input[name*='name']"
        action: "use_test_name"
        
  navigation_strategies:
    - strategy: "breadth_first"
      description: "Explore all top-level navigation first"
      
  error_recovery:
    - condition: "page_load_timeout"
      action: "refresh_and_retry"
      max_attempts: 3
```

## 📊 Output and Reports

### Generated Configurations

The framework automatically generates YAML configurations for discovered pages:

```bash
generated_configs/
├── portal_optix_earth_dashboard.yaml
├── portal_optix_earth_reports.yaml
└── portal_optix_earth_settings.yaml
```

### Exploration Reports

Comprehensive JSON reports include:

- **Page Mappings**: Complete element inventories
- **Navigation Structure**: Site architecture
- **Automation Opportunities**: Recommended automation targets
- **Form Analysis**: Complex form automation potential
- **Performance Metrics**: Exploration timing and statistics

### Example Report Structure

```json
{
  "exploration_summary": {
    "total_pages_explored": 15,
    "total_interactive_elements": 342,
    "automation_opportunities": 8
  },
  "automation_recommendations": [
    {
      "type": "form_automation",
      "priority": "high",
      "description": "Automate 3 complex forms for data entry efficiency"
    }
  ]
}
```

## 🎪 Use Cases

### 1. Initial Portal Exploration

```bash
# Comprehensive portal mapping
python agents/optix_explorer_agent.py \
  --url "https://portal.optix.earth/" \
  --credentials-file credentials.json \
  --output-dir exploration_results
```

### 2. Automated Testing Setup

```python
# Create test suite from discovered workflows
automation = AgenticPageAutomation()
automation.load_page_config("optix_portal")

test_scenarios = config['test_scenarios']
for scenario in test_scenarios:
    automation.execute_workflow(scenario['workflow'], "optix_portal", scenario['test_data'])
```

### 3. Data Extraction Automation

```python
# Automated data extraction from discovered tables
mapping = automation.navigate_and_explore("https://portal.optix.earth/data")

for element in mapping.elements:
    if element.tag_name == 'table':
        # Extract table data
        data = automation.extract_table_data(element.css_selector)
```

### 4. Continuous Monitoring

```python
# Set up continuous portal monitoring
import schedule

def monitor_portal():
    agent = OptixExplorerAgent()
    results = agent.intelligent_portal_exploration()
    # Check for changes and alert if needed

schedule.every().day.at("09:00").do(monitor_portal)
```

## 🚨 Best Practices

### 1. Configuration Management

- **Version Control**: Keep YAML configs in git
- **Environment-Specific**: Use different configs for dev/staging/prod
- **Validation**: Validate configs before deployment

### 2. Error Handling

- **Graceful Degradation**: Continue exploration if single page fails
- **Retry Logic**: Implement retry for transient failures
- **Logging**: Comprehensive logging for debugging

### 3. Performance Optimization

- **Headless Mode**: Use for production automation
- **Parallel Execution**: Explore multiple pages concurrently
- **Caching**: Cache discovered elements between sessions

### 4. Security Considerations

- **Credential Management**: Use environment variables or secure vaults
- **Rate Limiting**: Avoid overwhelming target servers
- **User Agent Rotation**: Vary browser signatures if needed

## 🐛 Troubleshooting

### Common Issues

#### Authentication Failures
```bash
# Check credentials format
cat credentials.json | jq

# Verify Auth0 configuration
python -c "import yaml; print(yaml.safe_load(open('page_configs/auth0_login.yaml')))"
```

#### Element Not Found
```python
# Increase wait timeouts
automation.wait = WebDriverWait(automation.driver, 30)

# Use more specific selectors
selector = "div.specific-class button[data-action='submit']"
```

#### Performance Issues
```python
# Enable headless mode
automation.setup_driver(headless=True)

# Reduce exploration depth
agent.exploration_depth = "shallow"
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Run with verbose output:

```bash
python agents/optix_explorer_agent.py --verbose --debug
```

## 🔮 Advanced Features

### 1. Machine Learning Integration

Train models to predict automation opportunities:

```python
from sklearn.ensemble import RandomForestClassifier

# Train model on automation success patterns
model = RandomForestClassifier()
model.fit(element_features, automation_success)
```

### 2. Visual Recognition

Integrate computer vision for element detection:

```python
import cv2
import pytesseract

# OCR-based element detection
screenshot = automation.driver.get_screenshot_as_png()
text = pytesseract.image_to_string(screenshot)
```

### 3. API Integration

Combine web automation with API testing:

```python
import requests

# Verify backend APIs during exploration
response = requests.get("https://api.optix.earth/status")
assert response.status_code == 200
```

## 📚 Further Reading

- [Selenium Documentation](https://selenium-python.readthedocs.io/)
- [YAML Specification](https://yaml.org/spec/)
- [Web Automation Best Practices](https://www.selenium.dev/documentation/test_practices/)
- [Page Object Model Pattern](https://selenium-python.readthedocs.io/page-objects.html)

## 🤝 Contributing

To extend this framework:

1. **Add New Page Configs**: Create YAML files for new pages
2. **Enhance Workflows**: Add new automation workflows
3. **Improve Detection**: Enhance element discovery algorithms
4. **Add Integrations**: Connect to additional tools and services

## 📄 License

This framework is provided as-is for educational and automation purposes. Ensure compliance with target website terms of service and applicable laws.