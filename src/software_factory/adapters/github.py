import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib import parse, request

from pydantic import BaseModel, Field

from software_factory.domain.enums import PullRequestStatus
from software_factory.domain.models import IssueRecord, PullRequestRecord
from software_factory.settings import Settings


def parse_github_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class RepositorySnapshot(BaseModel):
    issues: list[IssueRecord] = Field(default_factory=list)
    pull_requests: list[PullRequestRecord] = Field(default_factory=list)


class GitHubAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def sync_repository(self) -> RepositorySnapshot:
        return RepositorySnapshot(
            issues=self.list_open_issues(),
            pull_requests=self.list_pull_requests(),
        )

    def list_open_issues(self) -> list[IssueRecord]:
        payload = self._request_json(
            "GET",
            f"/repos/{self.settings.repository_full_name}/issues",
            query={
                "state": "open",
                "per_page": str(self.settings.github.issues_per_page),
            },
        )
        issues: list[IssueRecord] = []
        for item in payload:
            if "pull_request" in item:
                continue
            issues.append(
                IssueRecord(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body") or "",
                    labels=[label["name"] for label in item.get("labels", [])],
                    html_url=item.get("html_url"),
                )
            )
        return issues

    def list_pull_requests(self) -> list[PullRequestRecord]:
        payload = self._request_json(
            "GET",
            f"/repos/{self.settings.repository_full_name}/pulls",
            query={
                "state": "open",
                "per_page": str(self.settings.github.pulls_per_page),
            },
        )
        pull_requests: list[PullRequestRecord] = []
        for item in payload:
            pull_requests.append(self._to_pull_request_record(item))
        return pull_requests

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool = False,
    ) -> PullRequestRecord:
        self._ensure_token()
        payload = self._request_json(
            "POST",
            f"/repos/{self.settings.repository_full_name}/pulls",
            data={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
                "draft": draft,
            },
        )
        return self._to_pull_request_record(payload)

    def submit_pull_request_review(self, pull_request_number: int, event: str, body: str | None = None) -> dict[str, Any]:
        self._ensure_token()
        payload: dict[str, Any] = {"event": event}
        if body:
            payload["body"] = body
        return self._request_json(
            "POST",
            f"/repos/{self.settings.repository_full_name}/pulls/{pull_request_number}/reviews",
            data=payload,
        )

    def merge_pull_request(self, pull_request_number: int) -> dict[str, Any]:
        self._ensure_token()
        return self._request_json(
            "PUT",
            f"/repos/{self.settings.repository_full_name}/pulls/{pull_request_number}/merge",
            data={"merge_method": self.settings.merge_policy.merge_method},
        )

    def _derive_review_state(self, pull_request_number: int) -> PullRequestStatus:
        reviews = self._request_json(
            "GET",
            f"/repos/{self.settings.repository_full_name}/pulls/{pull_request_number}/reviews",
            query={"per_page": "100"},
        )
        latest_state = ""
        for review in reviews:
            state = (review.get("state") or "").upper()
            if state in {"APPROVED", "CHANGES_REQUESTED"}:
                latest_state = state
        if latest_state == "APPROVED":
            return PullRequestStatus.APPROVED
        if latest_state == "CHANGES_REQUESTED":
            return PullRequestStatus.CHANGES_REQUESTED
        return PullRequestStatus.REVIEW_PENDING

    def _ensure_token(self) -> None:
        if not self.settings.github.token:
            raise RuntimeError("SOFTWARE_FACTORY_GITHUB_TOKEN is required for write operations")

    def _request_json(
        self,
        method: str,
        path: str,
        query: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        url = f"{self.settings.github.api_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "software-factory-mvp",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.settings.github.token:
            headers["Authorization"] = f"Bearer {self.settings.github.token}"
        body = None if data is None else json.dumps(data).encode("utf-8")
        http_request = request.Request(url=url, headers=headers, method=method, data=body)
        with request.urlopen(http_request) as response:
            return json.loads(response.read().decode("utf-8"))

    def _extract_issue_number(self, title: str, body: str, branch_name: str) -> int | None:
        patterns = [
            rf"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)",
            rf"issue[-_/](\d+)",
            rf"issue-(\d+)",
            rf"#(\d+)",
        ]
        haystacks = [body, title, branch_name]
        for haystack in haystacks:
            for pattern in patterns:
                match = re.search(pattern, haystack, re.IGNORECASE)
                if match:
                    return int(match.group(1))
        return None

    def _to_pull_request_record(self, item: dict[str, Any]) -> PullRequestRecord:
        review_state = self._derive_review_state(item["number"])
        issue_number = self._extract_issue_number(item.get("title") or "", item.get("body") or "", item["head"]["ref"])
        return PullRequestRecord(
            number=item["number"],
            issue_number=issue_number,
            title=item["title"],
            body=item.get("body") or "",
            branch_name=item["head"]["ref"],
            base_branch=item["base"]["ref"],
            status=review_state,
            html_url=item.get("html_url"),
            created_at=parse_github_datetime(item.get("created_at")) or datetime.now(UTC),
            updated_at=parse_github_datetime(item.get("updated_at")) or datetime.now(UTC),
            merged_at=parse_github_datetime(item.get("merged_at")),
        )
