"""
Standalone GitHub Error Reporter Module

A reusable module for reporting errors to GitHub Issues.
Can be used with any Python framework (Django, Flask, FastAPI, etc.)

Usage:
    from github_error_reporter import GitHubErrorReporter
    
    reporter = GitHubErrorReporter(
        repo="owner/repo",
        token="ghp_xxxxx",
        max_comments=3  # After this, reactions are used instead
    )
    
    reporter.report_error(
        error_context={
            'error_type': 'ValueError',
            'error_message': 'Invalid input',
            'path': '/api/users',
            'method': 'POST',
            'user': 'username or None',
            'timestamp': '2026-02-16T10:30:00',
        },
        traceback_text="Full traceback string..."
    )
"""
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ReportResult(Enum):
    """Result types for error reporting"""
    ISSUE_CREATED = "issue_created"
    COMMENT_ADDED = "comment_added"
    REACTION_ADDED = "reaction_added"
    FAILED = "failed"


@dataclass
class ReportOutcome:
    """Outcome of an error report attempt"""
    result: ReportResult
    issue_url: Optional[str] = None
    issue_number: Optional[int] = None
    message: str = ""


class GitHubErrorReporter:
    """
    A reusable class for reporting errors to GitHub Issues.
    
    Features:
    - Creates new issues for new errors
    - Comments on existing issues for duplicate errors
    - After max_comments reached, adds thumbs-up reaction instead
    - Searches for duplicates by error type in title
    
    Args:
        repo: GitHub repository in "owner/repo" format
        token: GitHub personal access token with repo access
        max_comments: Maximum comments per issue before switching to reactions (default: 3)
        labels: List of labels to apply to new issues (default: ['bug', 'auto-generated', 'production-error'])
    """
    
    def __init__(
        self,
        repo: str,
        token: str,
        max_comments: int = 3,
        labels: Optional[list] = None
    ):
        self.repo = repo
        self.token = token
        self.max_comments = max_comments
        self.labels = labels or ['bug', 'auto-generated', 'production-error']
        
        self._headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
        }
    
    def report_error(
        self,
        error_context: Dict[str, Any],
        traceback_text: str
    ) -> ReportOutcome:
        """
        Report an error to GitHub Issues.
        
        Args:
            error_context: Dictionary with error details:
                - error_type: Exception class name (e.g., 'ValueError')
                - error_message: The exception message
                - path: URL path where error occurred
                - method: HTTP method (GET, POST, etc.)
                - user: Username or identifier (can be None)
                - timestamp: ISO format timestamp
            traceback_text: Full traceback as a string
            
        Returns:
            ReportOutcome with result type, issue URL, and message
        """
        # Build issue title (used for searching)
        error_type = error_context.get('error_type', 'Unknown Error')
        error_message = error_context.get('error_message', '')
        title = f"🐛 {error_type}: {error_message[:80]}"
        
        # Search for existing open issues with same error
        existing_issue = self._find_existing_issue(error_type, error_message)
        
        if existing_issue:
            return self._handle_existing_issue(existing_issue, error_context, traceback_text)
        else:
            return self._create_new_issue(title, error_context, traceback_text)
    
    def _find_existing_issue(
        self,
        error_type: str,
        error_message: str
    ) -> Optional[Dict[str, Any]]:
        """Search for an existing open issue matching this error."""
        search_query = f"is:issue is:open repo:{self.repo} {error_type} in:title"
        search_url = "https://api.github.com/search/issues"
        search_params = {'q': search_query}
        
        try:
            response = requests.get(
                search_url,
                headers=self._headers,
                params=search_params,
                timeout=10
            )
            
            if response.status_code == 200:
                issues = response.json().get('items', [])
                # Look for exact match on error message
                for issue in issues:
                    if error_message[:80] in issue['title']:
                        return issue
        except requests.RequestException:
            pass  # Will create new issue if search fails
        
        return None
    
    def _get_issue_comment_count(self, issue: Dict[str, Any]) -> int:
        """Get the number of comments on an issue."""
        return issue.get('comments', 0)
    
    def _add_reaction_to_issue(self, issue: Dict[str, Any]) -> ReportOutcome:
        """Add a thumbs-up reaction to the issue."""
        issue_number = issue['number']
        reactions_url = f"https://api.github.com/repos/{self.repo}/issues/{issue_number}/reactions"
        
        # Need to use preview header for reactions API
        headers = {
            **self._headers,
            'Accept': 'application/vnd.github.squirrel-girl-preview+json',
        }
        
        try:
            response = requests.post(
                reactions_url,
                json={'content': '+1'},
                headers=headers,
                timeout=10
            )
            
            if response.status_code in (200, 201):
                return ReportOutcome(
                    result=ReportResult.REACTION_ADDED,
                    issue_url=issue['html_url'],
                    issue_number=issue_number,
                    message=f"Added 👍 reaction to existing issue (comment limit reached)"
                )
            else:
                return ReportOutcome(
                    result=ReportResult.FAILED,
                    issue_url=issue['html_url'],
                    issue_number=issue_number,
                    message=f"Failed to add reaction: {response.status_code}"
                )
        except requests.RequestException as e:
            return ReportOutcome(
                result=ReportResult.FAILED,
                message=f"Request failed: {e}"
            )
    
    def _handle_existing_issue(
        self,
        issue: Dict[str, Any],
        error_context: Dict[str, Any],
        traceback_text: str
    ) -> ReportOutcome:
        """Handle an existing issue - either add comment or reaction."""
        comment_count = self._get_issue_comment_count(issue)
        
        # If we've reached the comment limit, add a reaction instead
        if comment_count >= self.max_comments:
            return self._add_reaction_to_issue(issue)
        
        # Otherwise, add a comment
        return self._add_comment_to_issue(issue, error_context, traceback_text)
    
    def _add_comment_to_issue(
        self,
        issue: Dict[str, Any],
        error_context: Dict[str, Any],
        traceback_text: str
    ) -> ReportOutcome:
        """Add a comment to an existing issue."""
        occurrence_info = self._build_occurrence_info(error_context)
        
        comment_body = f"""## Error Occurred Again

{occurrence_info}

<details>
<summary>Traceback</summary>

```python
{traceback_text}
```
</details>
"""
        comment_url = issue['comments_url']
        
        try:
            response = requests.post(
                comment_url,
                json={'body': comment_body},
                headers=self._headers,
                timeout=10
            )
            
            if response.status_code == 201:
                return ReportOutcome(
                    result=ReportResult.COMMENT_ADDED,
                    issue_url=issue['html_url'],
                    issue_number=issue['number'],
                    message=f"Added comment to existing issue"
                )
            else:
                return ReportOutcome(
                    result=ReportResult.FAILED,
                    issue_url=issue['html_url'],
                    issue_number=issue['number'],
                    message=f"Failed to add comment: {response.status_code}"
                )
        except requests.RequestException as e:
            return ReportOutcome(
                result=ReportResult.FAILED,
                message=f"Request failed: {e}"
            )
    
    def _create_new_issue(
        self,
        title: str,
        error_context: Dict[str, Any],
        traceback_text: str
    ) -> ReportOutcome:
        """Create a new GitHub issue."""
        occurrence_info = self._build_occurrence_info(error_context)
        
        body = f"""## Error Details
        
**Error Type:** `{error_context.get('error_type', 'Unknown')}`
**Error Message:** {error_context.get('error_message', 'No message')}

{occurrence_info}

## Traceback

```python
{traceback_text}
```

---
*This issue was automatically created by the error handler.*
"""
        
        create_url = f"https://api.github.com/repos/{self.repo}/issues"
        data = {
            'title': title,
            'body': body,
            'labels': self.labels,
        }
        
        try:
            response = requests.post(
                create_url,
                json=data,
                headers=self._headers,
                timeout=10
            )
            
            if response.status_code == 201:
                issue_data = response.json()
                return ReportOutcome(
                    result=ReportResult.ISSUE_CREATED,
                    issue_url=issue_data.get('html_url'),
                    issue_number=issue_data.get('number'),
                    message="Created new GitHub issue"
                )
            else:
                return ReportOutcome(
                    result=ReportResult.FAILED,
                    message=f"Failed to create issue: {response.status_code} - {response.text}"
                )
        except requests.RequestException as e:
            return ReportOutcome(
                result=ReportResult.FAILED,
                message=f"Request failed: {e}"
            )
    
    def _build_occurrence_info(self, error_context: Dict[str, Any]) -> str:
        """Build the occurrence details markdown section."""
        user = error_context.get('user')
        if hasattr(user, 'username'):
            user_display = user.username if getattr(user, 'is_authenticated', False) else 'Anonymous'
        elif user:
            user_display = str(user)
        else:
            user_display = 'Anonymous'
        
        return f"""### Occurrence Details
**URL:** `{error_context.get('path', 'Unknown')}`
**Method:** `{error_context.get('method', 'Unknown')}`
**User:** {user_display}
**Timestamp:** {error_context.get('timestamp', 'Unknown')}
"""


class LabsSyncResult(Enum):
    """Result types for Labs Punchlist sync"""
    ITEM_CREATED = "item_created"
    ITEM_UPDATED = "item_updated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class LabsSyncOutcome:
    """Outcome of a Labs Punchlist sync attempt"""
    result: LabsSyncResult
    item_id: Optional[int] = None
    message: str = ""


class LabsPunchlistReporter:
    """
    A reusable class for syncing errors to Buildly Labs Punchlist.
    
    Can be used standalone or in conjunction with GitHubErrorReporter.
    
    Features:
    - Creates punchlist items for new errors
    - Updates occurrence count for duplicate errors
    - Links items to current release when available
    - Tracks errors by external ID (e.g., GitHub issue number)
    
    Args:
        api_url: Labs API base URL
        api_key: Labs API key for authentication
        product_uuid: UUID of the product in Labs
        auto_link_release: Automatically link items to current release (default: True)
    
    Usage standalone:
        from github_error_reporter import LabsPunchlistReporter
        
        reporter = LabsPunchlistReporter(
            api_url="https://labs.buildly.dev/api",
            api_key="your-api-key",
            product_uuid="your-product-uuid"
        )
        
        outcome = reporter.report_error(
            error_context={'error_type': 'ValueError', ...},
            traceback_text="...",
            external_id=42  # Optional, e.g., GitHub issue number
        )
    """
    
    def __init__(
        self,
        api_url: str,
        api_token: str,
        product_uuid: str,
        auto_link_release: bool = True,
        timeout: int = 30
    ):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.product_uuid = product_uuid
        self.auto_link_release = auto_link_release
        self.timeout = timeout
        
        # Labs API uses Bearer token auth (JWT from profile settings)
        self._headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_token}',
        }
    
    def report_error(
        self,
        error_context: Dict[str, Any],
        traceback_text: str,
        external_id: Optional[int] = None,
        priority: str = 'medium'
    ) -> LabsSyncOutcome:
        """
        Report an error to Labs Punchlist.
        
        Args:
            error_context: Dictionary with error details (same as GitHubErrorReporter)
            traceback_text: Full traceback as a string
            external_id: External identifier (e.g., GitHub issue number) for deduplication
            priority: Priority level ('low', 'medium', 'high', 'critical')
            
        Returns:
            LabsSyncOutcome with result type and item ID
        """
        # Determine priority based on error type
        error_type = error_context.get('error_type', 'Unknown')
        if 'Critical' in error_type or 'Fatal' in error_type:
            priority = 'critical'
        elif 'Security' in error_type or 'Auth' in error_type:
            priority = 'high'
        
        # Check for existing item by external ID
        if external_id:
            existing_item = self._find_item_by_external_id(external_id)
            if existing_item:
                return self._update_item_occurrence(existing_item)
        
        # Create new punchlist item
        return self._create_punchlist_item(error_context, traceback_text, external_id, priority)
    
    def _find_item_by_external_id(self, external_id: int) -> Optional[Dict[str, Any]]:
        """Find an existing issue by external ID (GitHub issue number)."""
        # Search for issues with matching external_id in the product
        url = f"{self.api_url}/product/issue/"
        params = {
            'product_uuid': self.product_uuid,
            'external_id': str(external_id)
        }
        
        try:
            response = requests.get(
                url,
                headers=self._headers,
                params=params,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        
        return None
    
    def _update_item_occurrence(self, item: Dict[str, Any]) -> LabsSyncOutcome:
        """Update an existing issue's occurrence count."""
        item_uuid = item.get('uuid')
        url = f"{self.api_url}/product/issue/{item_uuid}/"
        
        try:
            response = requests.patch(
                url,
                headers=self._headers,
                json={'increment_occurrence': True},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return LabsSyncOutcome(
                    result=LabsSyncResult.ITEM_UPDATED,
                    item_id=item_uuid,
                    message="Updated occurrence count on existing issue"
                )
            else:
                return LabsSyncOutcome(
                    result=LabsSyncResult.FAILED,
                    item_id=item_uuid,
                    message=f"Failed to update issue: {response.status_code}"
                )
        except requests.RequestException as e:
            return LabsSyncOutcome(
                result=LabsSyncResult.FAILED,
                message=f"Request failed: {e}"
            )
    
    def _create_punchlist_item(
        self,
        error_context: Dict[str, Any],
        traceback_text: str,
        external_id: Optional[int],
        priority: str
    ) -> LabsSyncOutcome:
        """Create a new punchlist item."""
        error_type = error_context.get('error_type', 'Unknown Error')
        error_message = error_context.get('error_message', '')
        
        # Build title and description
        title = f"{error_type}: {error_message[:100]}"
        
        user = error_context.get('user')
        if hasattr(user, 'username'):
            user_display = user.username if getattr(user, 'is_authenticated', False) else 'Anonymous'
        elif user:
            user_display = str(user)
        else:
            user_display = 'Anonymous'
        
        description = f"""## Error Details

**Error Type:** {error_type}
**Error Message:** {error_message}

### Context
- **URL:** {error_context.get('path', 'Unknown')}
- **Method:** {error_context.get('method', 'Unknown')}
- **User:** {user_display}
- **Timestamp:** {error_context.get('timestamp', 'Unknown')}

### Traceback
```
{traceback_text}
```
"""
        
        # Build metadata
        metadata = {
            'error_type': error_type,
            'path': error_context.get('path'),
            'method': error_context.get('method'),
            'timestamp': error_context.get('timestamp'),
        }
        if external_id:
            metadata['github_issue_number'] = external_id
        
        # Create the issue via Labs API
        # Endpoint: POST /product/issue/
        url = f"{self.api_url}/product/issue/"
        data = {
            'product_uuid': self.product_uuid,
            'title': title,
            'description': description,
            'status': 'open',
            # Additional fields for tracking
            'priority': priority,
            'source': 'collabhub',
            'issue_type': 'bug',
            'metadata': metadata,
        }
        if external_id:
            data['external_id'] = str(external_id)
        
        try:
            response = requests.post(
                url,
                headers=self._headers,
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code == 201:
                item_data = response.json()
                item_uuid = item_data.get('uuid')
                
                # Auto-link to current release if enabled
                if self.auto_link_release:
                    self._link_to_current_release(item_uuid)
                
                return LabsSyncOutcome(
                    result=LabsSyncResult.ITEM_CREATED,
                    item_id=item_uuid,
                    message="Created new issue in Labs"
                )
            else:
                return LabsSyncOutcome(
                    result=LabsSyncResult.FAILED,
                    message=f"Failed to create item: {response.status_code} - {response.text}"
                )
        except requests.RequestException as e:
            return LabsSyncOutcome(
                result=LabsSyncResult.FAILED,
                message=f"Request failed: {e}"
            )
    
    def _link_to_current_release(self, item_uuid: str) -> bool:
        """Link an issue to the product's current release."""
        # Get releases for the product
        release_url = f"{self.api_url}/product/release/"
        
        try:
            response = requests.get(
                release_url,
                headers=self._headers,
                params={'product_uuid': self.product_uuid},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                releases = response.json()
                # Get the most recent release (first in list, assuming ordered by date desc)
                if releases and len(releases) > 0:
                    release_uuid = releases[0].get('uuid')
                    
                    if release_uuid:
                        # Link issue to release by updating the issue
                        link_url = f"{self.api_url}/product/issue/{item_uuid}/"
                        link_response = requests.patch(
                            link_url,
                            headers=self._headers,
                            json={'release_uuid': release_uuid},
                            timeout=self.timeout
                        )
                        return link_response.status_code == 200
        except requests.RequestException:
            pass
        
        return False


class CombinedErrorReporter:
    """
    Combined reporter that sends errors to both GitHub and Labs Punchlist.
    
    Usage:
        reporter = CombinedErrorReporter(
            github_repo="owner/repo",
            github_token="ghp_xxxx",
            labs_api_url="https://labs.buildly.dev/api",
            labs_api_key="your-api-key",
            labs_product_uuid="your-product-uuid"
        )
        
        outcome = reporter.report_error(error_context, traceback_text)
        # outcome.github_outcome and outcome.labs_outcome contain individual results
    """
    
    def __init__(
        self,
        github_repo: Optional[str] = None,
        github_token: Optional[str] = None,
        github_max_comments: int = 3,
        labs_api_url: Optional[str] = None,
        labs_api_token: Optional[str] = None,
        labs_product_uuid: Optional[str] = None,
        labs_auto_link_release: bool = True
    ):
        self.github_reporter = None
        self.labs_reporter = None
        
        # Initialize GitHub reporter if configured
        if github_repo and github_token:
            self.github_reporter = GitHubErrorReporter(
                repo=github_repo,
                token=github_token,
                max_comments=github_max_comments
            )
        
        # Initialize Labs reporter if configured
        if labs_api_url and labs_api_token and labs_product_uuid:
            self.labs_reporter = LabsPunchlistReporter(
                api_url=labs_api_url,
                api_token=labs_api_token,
                product_uuid=labs_product_uuid,
                auto_link_release=labs_auto_link_release
            )
    
    def report_error(
        self,
        error_context: Dict[str, Any],
        traceback_text: str
    ) -> 'CombinedReportOutcome':
        """
        Report error to all configured services.
        
        Returns:
            CombinedReportOutcome with results from each service
        """
        github_outcome = None
        labs_outcome = None
        github_issue_number = None
        
        # Report to GitHub first (to get issue number for Labs)
        if self.github_reporter:
            github_outcome = self.github_reporter.report_error(
                error_context,
                traceback_text
            )
            github_issue_number = github_outcome.issue_number
        
        # Report to Labs with GitHub issue number as external ID
        if self.labs_reporter:
            labs_outcome = self.labs_reporter.report_error(
                error_context,
                traceback_text,
                external_id=github_issue_number
            )
        
        return CombinedReportOutcome(
            github_outcome=github_outcome,
            labs_outcome=labs_outcome
        )


@dataclass
class CombinedReportOutcome:
    """Outcome of combined error reporting"""
    github_outcome: Optional[ReportOutcome] = None
    labs_outcome: Optional[LabsSyncOutcome] = None
    
    @property
    def any_success(self) -> bool:
        """Returns True if at least one reporter succeeded"""
        github_ok = self.github_outcome and self.github_outcome.result != ReportResult.FAILED
        labs_ok = self.labs_outcome and self.labs_outcome.result != LabsSyncResult.FAILED
        return bool(github_ok or labs_ok)
    
    @property 
    def all_success(self) -> bool:
        """Returns True if all configured reporters succeeded"""
        github_ok = self.github_outcome is None or self.github_outcome.result != ReportResult.FAILED
        labs_ok = self.labs_outcome is None or self.labs_outcome.result != LabsSyncResult.FAILED
        return github_ok and labs_ok
