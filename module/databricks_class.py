import subprocess
import os
import shutil
import requests

class DatabricksDeploymentError(Exception):
    """Custom exception for Databricks deployment failures."""
    pass

class DatabricksConfig:
    """Class to manage Databricks configurations and deployments."""
    
    def __init__(self):
        # Databricks Configurations
        self.databricks_instance = os.getenv("DATABRICKS_INSTANCE", "https://<your-instance>.cloud.databricks.com")
        self.databricks_token = os.getenv("DATABRICKS_TOKEN", "your-databricks-token")  # Store securely
        self.databricks_workspace_path = os.getenv("DATABRICKS_WORKSPACE_PATH", "/Repos/prod/")

    def deploy_to_databricks(self, git_config):
        """Deploys the reverted code to Databricks workspace."""
        print("Deploying reverted code to Databricks workspace...")

        # Zip the repository contents
        zip_path = "/tmp/repo.zip"
        shutil.make_archive(zip_path.replace(".zip", ""), 'zip', git_config.local_clone_path)

        # Upload the zip to Databricks workspace
        with open(zip_path, "rb") as f:
            response = requests.post(
                f"{self.databricks_instance}/api/2.0/workspace/import",
                headers={"Authorization": f"Bearer {self.databricks_token}"},
                files={"file": f},
                data={"path": self.databricks_workspace_path, "format": "SOURCE", "overwrite": "true"}
            )

        if response.status_code == 200:
            print("Successfully deployed to Databricks workspace.")
        else:
            raise DatabricksDeploymentError(f"Deployment failed: {response.text}")

def workbook_host_token():
    """
    Retrieves the Databricks workspace host URL and API token.

    This function uses Databricks utilities (`dbutils`) to fetch the current 
    notebook execution context and extract the API URL (workspace host) and 
    the API token for authentication.

    Returns:
        tuple: A tuple containing:
            - str: The Databricks workspace host URL.
            - str: The API authentication token.
        
        If an error occurs, it returns (None, None).

    Raises:
        Exception: If the API credentials cannot be retrieved, an error message 
        is printed, but the function does not raise the exception.
    """
    try:
        context = dbutils.entry_point.getDbutils().notebook().getContext()
        host = context.apiUrl().get()
        token = context.apiToken().get()

        return host, token
    except Exception as e:
        print(f"Error retrieving API credentials: {e}")
        return None, None


def user_secret(secret_scope: str, secret_name: str) -> str:
    """
    Retrieves a secret from Databricks' secret scope.

    Parameters:
    secret_scope (str): The secret scope name.
    secret_name (str): The name of the secret key.

    Returns:
    str: The retrieved secret value.
    """
    try:
        if not secret_scope or not secret_name:
            raise ValueError("Secret scope and secret name must be provided.")

        user_api_key = dbutils.secrets.get(scope=secret_scope, key=secret_name)
        return user_api_key

    except Exception as e:
        print(f"Error retrieving secret '{secret_name}' from scope '{secret_scope}': {e}")
        return None  # or raise the exception if you want it to fail hard
