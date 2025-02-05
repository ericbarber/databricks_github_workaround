import subprocess
import os
import shutil
import requests
import re

class GitOperationError(Exception):
    """Custom exception for Git operation failures."""
    pass


class GitConfig:
    """Class to manage Git configurations and operations."""
    
    def __init__(self):
        # Git Configurations
        self.git_repo_url = os.getenv("GIT_REPO_URL", "git@github.com:your-org/your-repo.git")
        self.git_user_name = os.getenv("GIT_USER_NAME", "gituser")
        self.git_email = os.getenv("GIT_EMAIL", "gituser@company.com")
        self.git_host_url = os.getenv("GIT_HOST_URL", "company.com")
        self.git_repo_name = os.getenv("GIT_REPO_NAME", "company_app")
        self.git_branch_name = os.getenv("GIT_BRANCH_NAME", "dev")
        self.git_commit_hash = os.getenv("GIT_COMMIT_HASH", "")

        # Local paths
        self.local_clone_path = os.getenv("LOCAL_CLONE_PATH", "/tmp/rollback_repo")

    def run_command(self, command, cwd=None):
        """Runs a shell command and handles errors."""
        try:
            result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Error running command: {' '.join(command)}\n{e.stderr}")

    def clone_repo(self):
        """Clones the GitHub repository."""
        print(f"CURRENT WORKING DIRECTORY: {os.getcwd()}")
        if os.path.exists(self.local_clone_path):
            shutil.rmtree(self.local_clone_path)  # Clean up old clone
        print(f"Cloning repository {self.git_repo_url} into {self.local_clone_path}...")
        self.run_command(["git", "clone", self.git_repo_url, self.local_clone_path])

    def checkout_branch(self, branch_name=None):
        """Checks out a specific branch, ensuring it exists."""
        branch_name = branch_name or self.git_branch_name
        print(f"Checking out branch: {branch_name}")

        # Fetch all branches
        self.run_command(["git", "fetch", "--all"], cwd=self.local_clone_path)

        # Check if the branch exists
        branches = self.run_command(["git", "branch", "--list", branch_name], cwd=self.local_clone_path)
        if not branches:
            raise GitOperationError(f"Branch '{branch_name}' does not exist in the repository.")

        # Checkout branch
        self.run_command(["git", "checkout", branch_name], cwd=self.local_clone_path)

    def revert_to_commit(self, target_commit):
        """Reverts repository to a specific commit and commits the rollback."""
        print(f"Reverting repository to commit: {target_commit}")

        # Move to repo directory
        os.chdir(self.local_clone_path)

        # Ensure clean working directory
        status = self.run_command(["git", "status", "--porcelain"])
        if status:
            raise GitOperationError("Uncommitted changes detected. Please commit or stash them before proceeding.")

        # Get current HEAD commit
        latest_commit = self.run_command(["git", "rev-parse", "HEAD"])
        if latest_commit == target_commit:
            print("Already at the target commit. No changes needed.")
            return

        # Revert all commits from target_commit to HEAD
        print("Reverting commits...")
        self.run_command(["git", "revert", "--no-commit", f"{target_commit}..HEAD"])
        
        # Commit revert
        self.commit_and_push(f"Reverting to commit {target_commit}")

    def commit_and_push(self, commit_message="Updating repository"):
        """Commits all changes and pushes to the remote repository."""
        print(f"Committing and pushing changes: {commit_message}")
        self.run_command(["git", "add", "."], cwd=self.local_clone_path)
        self.run_command(["git", "commit", "-m", commit_message], cwd=self.local_clone_path)
        self.run_command(["git", "push", "origin", self.git_branch_name], cwd=self.local_clone_path)
        print("Changes committed and pushed.")


def create_git_clone_url(repo_name: str, repo_owner_name: str, username: str, git_api_token: str, host_url: str) -> str:
    """
    Creates a Git clone URL using a personal access token for authentication.

    Parameters:
        repo_name (str): The name of the repository to clone.
        username (str): The GitHub (or Git) username.
        git_api_token (str): The GitHub API token for authentication.
        host_url (str): The full Git host URL (e.g., "https://github.com/").

    Returns:
        str: The generated Git clone URL in the format:
             "https://username:token@github.com/repo_name.git"

    Raises:
        ValueError: If the host URL is invalid and the hostname cannot be extracted.

    Security Note:
        Be cautious when using API tokens in URLs, as they may be logged or exposed.
        Consider using SSH keys or credential helpers for better security.
    """
    # Regex pattern to extract the host from the URL
    pattern = r"https?://([^/]+)"
    match = re.match(pattern, host_url)
    
    if not match:
        raise ValueError(f"Invalid host URL: {host_url}")
    
    git_host = match.group(1)
    git_url = f"https://{username}:{git_api_token}@{git_host}/{repo_owner_name}/{repo_name}.git"
    
    return git_url
