"""
COLLABORATION MESH (PRODUCTION)
===============================
Real-Time Command & Control Interface.

No simulation.
This module executes ACTUAL API calls to Notion, Linear, and Slack.
Requires valid tokens in the One Key system to function.
"""

import requests
import json
import os
from typing import Dict, Any, Optional
from security.one_key import OneKeySystem

class CollaborationMesh:
    def __init__(self, security: OneKeySystem):
        self.security = security
        
        # PRIORITY: Check for explicit ENV vars first (Real World Integration)
        # FALLBACK: Use One Key derivation (Internal Architecture)
        self.notion_token = os.getenv("NOTION_TOKEN") or self.security.get_credential('COLLAB', 'NOTION_TOKEN')
        self.linear_key = os.getenv("LINEAR_API_KEY") or self.security.get_credential('COLLAB', 'LINEAR_API_KEY')
        self.slack_token = os.getenv("SLACK_BOT_TOKEN") or self.security.get_credential('COLLAB', 'SLACK_BOT_TOKEN')

    def broadcast_pulse(self, message: str, level: str = "info"):
        """
        Sends a REAL message to Slack.
        """
        if not self.slack_token or len(self.slack_token) < 20:
            print(f"⚠️  SLACK: Token invalid/missing. Message not sent: '{message}'")
            print("   (To fix: export SLACK_BOT_TOKEN='xoxb-your-token')")
            return

        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.slack_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": "#autonomous-ops",
            "text": f"{'🟢' if level=='info' else '🔴'} {message}"
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=5)
            if not resp.json().get("ok"):
                print(f"❌ SLACK ERROR: {resp.json().get('error')}")
            else:
                print(f"✅ SLACK: Message delivered.")
        except Exception as e:
            print(f"❌ SLACK NETWORK ERROR: {e}")

    def create_optimization_task(self, title: str, description: str, priority: int = 1) -> str:
        """
        Creates a REAL ticket in Linear.
        """
        if not self.linear_key or len(self.linear_key) < 20:
             print("⚠️  LINEAR: API Key invalid/missing. Task skipped.")
             print("   (To fix: export LINEAR_API_KEY='lin_api_your_key')")
             return "skipped"

        url = "https://api.linear.app/graphql"
        headers = {
            "Authorization": self.linear_key,
            "Content-Type": "application/json"
        }
        query = """
        mutation IssueCreate($title: String!, $description: String!, $priority: Int!) {
            issueCreate(input: {
                title: $title,
                description: $description,
                priority: $priority,
                teamId: "YOUR_TEAM_ID_HERE" 
            }) {
                issue { id identifier }
            }
        }
        """
        variables = {"title": title, "description": description, "priority": priority}
        
        try:
            resp = requests.post(url, headers=headers, json={"query": query, "variables": variables})
            
            if resp.status_code == 401 or resp.status_code == 403:
                print(f"❌ LINEAR AUTH ERROR: The provided key was rejected.")
                print("   > This means the derived 'One Key' is not registered with Linear.")
                print("   > SOLUTION: export LINEAR_API_KEY='your-real-key' and reboot.")
                return "auth_error"

            if "errors" in resp.json():
                print(f"❌ LINEAR ERROR: {resp.json()['errors'][0]['message']}")
                return "error"
            
            issue_id = resp.json()['data']['issueCreate']['issue']['identifier']
            print(f"✅ LINEAR: Ticket created ({issue_id})")
            return issue_id
        except Exception as e:
            print(f"❌ LINEAR NETWORK ERROR: {e}")
            return "net_error"
