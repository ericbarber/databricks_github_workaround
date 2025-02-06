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
        self.git_api_token = os.getenv("GIT_API_TOKEN", "unset")
        self.git_user_name = os.getenv("GIT_USER_NAME", "gituser")
        self.git_email = os.getenv("GIT_EMAIL", "gituser@company.com")
        self.git_host_url = os.getenv("GIT_HOST_URL", "company.com")
        self.git_repo_name = os.getenv("GIT_REPO_NAME", "company_app")
        self.git_repo_owner = os.getenv("GIT_REPO_OWNER", "organization")
        self.git_branch_name = os.getenv("GIT_BRANCH_NAME", "dev")
        self.git_commit_hash = os.getenv("GIT_COMMIT_HASH", "")

        # Local paths (Prompt user if not set)
        self.local_clone_path = os.getenv("LOCAL_CLONE_PATH")
        if not self.local_clone_path:
            self.local_clone_path = input("Enter the local clone path (default: /tmp/rollback_repo): ").strip() or "/tmp/rollback_repo"

        # Ensure the directory exists
        os.makedirs(self.local_clone_path, exist_ok=True)

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
        """Checks out a specific branch, ensuring it exists locally or remotely."""
        branch_name = branch_name or self.git_branch_name
        print(f"Checking out branch: {branch_name}")

        # Fetch all branches
        self.run_command(["git", "fetch", "--all"], cwd=self.local_clone_path)

        # Get list of local and remote branches
        all_branches = self.run_command(["git", "branch", "--all"], cwd=self.local_clone_path)

        # Check if the branch exists locally
        if f"  {branch_name}" in all_branches.split("\n"):
            print(f"Branch '{branch_name}' found locally. Checking out.")
            self.run_command(["git", "checkout", branch_name], cwd=self.local_clone_path)
            return

        # Check if the branch exists remotely (format: remotes/origin/<branch_name>)
        remote_branch = f"remotes/origin/{branch_name}"
        if remote_branch in all_branches:
            print(f"Branch '{branch_name}' found on remote. Creating a local tracking branch.")
            self.run_command(["git", "checkout", "-b", branch_name, f"origin/{branch_name}"], cwd=self.local_clone_path)
            return

        # If the branch does not exist at all
        raise GitOperationError(f"Branch '{branch_name}' does not exist locally or remotely.")

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


    def create_git_push_url(self) -> str:
            """
            Creates a Git push URL using a personal access token for authentication.
    
            Returns:
                str: The generated Git push URL in the format:
                     "https://username:token@host_url/repo_owner/repo_name.git"
    
            Raises:
                ValueError: If the host URL is invalid and the hostname cannot be extracted.
    
            Security Note:
                Be cautious when using API tokens in URLs, as they may be logged or exposed.
                Consider using SSH keys or credential helpers for better security.
            """
            # Regex pattern to extract the host from the URL
            pattern = r"https?://([^/]+)"
            match = re.match(pattern, self.git_host_url)
            
            if not match:
                raise ValueError(f"Invalid host URL: {self.git_host_url}")
            
            git_host = match.group(1)
            git_url = f"https://{self.git_user_name}:{self.git_api_token}@{git_host}/{self.git_repo_owner}/{self.git_repo_name}.git"
            
            return git_url
    
    def set_git_remote_origin(self):
        """
        Sets or updates the Git remote origin for the repository.

        Raises:
            GitOperationError: If Git commands fail.
        """

        # Create the Git push URL using self attributes
        git_url = self.create_git_push_url()

        try:
            # Check if the remote "origin" already exists
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.local_clone_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode == 0:  # Remote exists, update it
                print(f"Updating remote origin to: {git_url}")
                self.run_command(["git", "remote", "set-url", "origin", git_url], cwd=self.local_clone_path)
            else:  # Remote does not exist, add it
                print(f"Adding remote origin: {git_url}")
                self.run_command(["git", "remote", "add", "origin", git_url], cwd=self.local_clone_path)

            print("✅ Remote origin set successfully.")

        except subprocess.CalledProcessError as e:
            print(f"Git error: {e}")
