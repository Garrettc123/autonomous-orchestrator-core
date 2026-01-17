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
        self.notion_token = os.getenv("NOTION_TOKEN") or self.security.get_credential('COLLAB', 'NOTION_TOKEN')
        self.linear_key = os.getenv("LINEAR_API_KEY") or self.security.get_credential('COLLAB', 'LINEAR_API_KEY')
        self.slack_token = os.getenv("SLACK_BOT_TOKEN") or self.security.get_credential('COLLAB', 'SLACK_BOT_TOKEN')

    def broadcast_pulse(self, message: str, level: str = "info"):
        """
        Sends a REAL message to Slack.
        """
        if not self.slack_token or len(self.slack_token) < 20:
            return # Silent fail if no key

        url = "https://slack.com/api/chat.postMessage"
        headers = {"Authorization": f"Bearer {self.slack_token}", "Content-Type": "application/json"}
        payload = {"channel": "#autonomous-ops", "text": f"{'🟢' if level=='info' else '🔴'} {message}"}
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=5)
            if not resp.json().get("ok"):
                # Print error but don't crash loop
                err = resp.json().get('error')
                if err != "missing_scope": # Ignore common scope error for now
                     print(f"❌ SLACK ERROR: {err}")
            else:
                print(f"✅ SLACK: Message delivered.")
        except Exception:
            pass

    def _get_linear_team_id(self) -> Optional[str]:
        """
        Dynamically fetch the first Team ID from Linear to ensure valid ticket creation.
        """
        query = """query { teams(first: 1) { nodes { id name } } }"""
        headers = {"Authorization": self.linear_key, "Content-Type": "application/json"}
        try:
            resp = requests.post("https://api.linear.app/graphql", headers=headers, json={"query": query})
            data = resp.json()
            if "data" in data and data["data"]["teams"]["nodes"]:
                team = data["data"]["teams"]["nodes"][0]
                print(f"   > Linear Team Found: {team['name']} ({team['id']})")
                return team["id"]
        except Exception:
            pass
        return None

    def create_optimization_task(self, title: str, description: str, priority: int = 1) -> str:
        """
        Creates a REAL ticket in Linear.
        """
        if not self.linear_key or len(self.linear_key) < 20:
             print("⚠️  LINEAR: API Key invalid/missing. Task skipped.")
             return "skipped"

        # 1. Resolve Team ID dynamically
        team_id = self._get_linear_team_id()
        if not team_id:
            print("❌ LINEAR ERROR: Could not find any Team ID. Please create a team in Linear first.")
            return "no_team"

        url = "https://api.linear.app/graphql"
        headers = {"Authorization": self.linear_key, "Content-Type": "application/json"}
        
        # 2. Create Issue using valid Team ID
        query = """
        mutation IssueCreate($title: String!, $description: String!, $priority: Int!, $teamId: String!) {
            issueCreate(input: {
                title: $title,
                description: $description,
                priority: $priority,
                teamId: $teamId
            }) {
                issue { id identifier }
            }
        }
        """
        variables = {
            "title": title, 
            "description": description, 
            "priority": priority,
            "teamId": team_id 
        }
        
        try:
            resp = requests.post(url, headers=headers, json={"query": query, "variables": variables})
            if "errors" in resp.json():
                print(f"❌ LINEAR ERROR: {resp.json()['errors'][0]['message']}")
                return "error"
            
            issue_id = resp.json()['data']['issueCreate']['issue']['identifier']
            print(f"✅ LINEAR: Ticket created ({issue_id})")
            return issue_id
        except Exception as e:
            print(f"❌ LINEAR NETWORK ERROR: {e}")
            return "net_error"
