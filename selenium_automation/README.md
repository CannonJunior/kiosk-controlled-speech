# Optix Portal Automation Framework

## Overview
Comprehensive Selenium-based automation framework for the Optix Earth portal with Auth0 authentication flow.

## Architecture
- YAML-driven page configuration
- Modular page object model
- Agentic decision-making capabilities
- Multi-environment support
- Dynamic element detection

## Flow Analysis
1. **Landing Page** → **Auth0 Authentication** → **Main Portal** → **Sub-pages**
2. Requires handling OAuth2 flow and session management
3. Dynamic content loading after authentication

## Key Components
- `page_configs/`: YAML configurations for each page
- `automation/`: Core automation engine
- `agents/`: Intelligent automation agents
- `utils/`: Helper functions and utilities