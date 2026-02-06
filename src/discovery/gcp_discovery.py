"""
GCP Organization Discovery

Discovers GCP projects using Resource Manager API.
Supports filtering by folders and organizations.
"""
import json
from typing import List, Optional

from google.cloud import resourcemanager_v3
from google.oauth2 import service_account

from . import OrganizationDiscovery, DiscoveredAccount, register_discovery
from ..logging_config import get_logger

logger = get_logger(__name__)


@register_discovery("GCP")
class GCPOrganizationDiscovery(OrganizationDiscovery):
    """
    Discover GCP projects using Resource Manager API.
    
    Required IAM roles:
    - roles/resourcemanager.organizationViewer (at org level)
    - roles/resourcemanager.folderViewer (for folder access)
    - roles/browser (for project listing)
    """
    
    def _get_credentials(self):
        """Create GCP credentials from secret."""
        secrets = self.credential.secrets or {}
        sa_json = secrets.get("service_account_json")
        
        if not sa_json:
            raise ValueError("GCP credential missing service_account_json")
        
        if isinstance(sa_json, str):
            sa_data = json.loads(sa_json)
        else:
            sa_data = sa_json
        
        return service_account.Credentials.from_service_account_info(
            sa_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"]
        )
    
    def validate_access(self) -> tuple[bool, str]:
        """
        Validate organization access, falling back to project-level access.
        
        Returns success even for project-only access, but with a descriptive message.
        """
        try:
            credentials = self._get_credentials()
            
            org_id = self.discovery_config.get("organization_id")
            if org_id:
                # Organization ID explicitly configured - try to access it
                try:
                    client = resourcemanager_v3.OrganizationsClient(credentials=credentials)
                    request = resourcemanager_v3.GetOrganizationRequest(
                        name=f"organizations/{org_id}"
                    )
                    org = client.get_organization(request=request)
                    return True, f"Connected to GCP Organization: {org.display_name}"
                except Exception as e:
                    return False, f"Cannot access organization {org_id}: {e}"
            
            # No org_id configured - try to search organizations
            try:
                client = resourcemanager_v3.OrganizationsClient(credentials=credentials)
                request = resourcemanager_v3.SearchOrganizationsRequest()
                orgs = list(client.search_organizations(request=request))
                if orgs:
                    return True, f"Found {len(orgs)} accessible GCP organizations"
            except Exception:
                pass  # Fall through to project-level access
            
            # Fallback: Check if we can at least list projects
            try:
                project_client = resourcemanager_v3.ProjectsClient(credentials=credentials)
                request = resourcemanager_v3.SearchProjectsRequest()
                projects = list(project_client.search_projects(request=request))
                if projects:
                    return True, f"Project-level access only (no org access). Found {len(projects)} accessible projects."
                return False, "No projects accessible to this service account"
            except Exception as e:
                return False, f"Cannot list projects: {e}"
                
        except Exception as e:
            return False, f"GCP access failed: {e}"

    
    def discover(self) -> List[DiscoveredAccount]:
        """
        Discover all projects in the GCP Organization.
        
        Respects discovery_config:
        - organization_id: Organization to search in
        - include_folders: List of folder IDs to include
        - exclude_projects: List of project IDs to exclude
        """
        credentials = self._get_credentials()
        
        org_id = self.discovery_config.get("organization_id")
        include_folders = self.discovery_config.get("include_folders", [])
        exclude_projects = set(self.discovery_config.get("exclude_projects", []))
        
        discovered = []
        
        try:
            client = resourcemanager_v3.ProjectsClient(credentials=credentials)
            
            if include_folders:
                # Discover only from specified folders
                for folder_id in include_folders:
                    projects = self._list_projects_in_folder(client, folder_id)
                    discovered.extend(projects)
            elif org_id:
                # Discover all projects in the organization
                discovered = self._list_all_projects(client, f"organizations/{org_id}")
            else:
                # Search all accessible projects
                discovered = self._search_all_projects(client)
            
            # Filter out excluded projects
            discovered = [p for p in discovered if p.account_id not in exclude_projects]
            
            logger.info(f"Discovered {len(discovered)} GCP projects")
            return discovered
            
        except Exception as e:
            logger.error(f"GCP discovery failed: {e}")
            raise
    
    def _list_all_projects(self, client, parent: str) -> List[DiscoveredAccount]:
        """List all projects under a parent (org or folder)."""
        discovered = []
        
        request = resourcemanager_v3.ListProjectsRequest(parent=parent)
        
        for project in client.list_projects(request=request):
            if project.state != resourcemanager_v3.Project.State.ACTIVE:
                continue
            
            discovered.append(DiscoveredAccount(
                account_id=project.project_id,
                name=project.display_name or project.project_id,
                metadata={
                    "project_number": project.name.split("/")[-1],
                    "parent": project.parent,
                    "labels": dict(project.labels) if project.labels else {},
                    "create_time": str(project.create_time) if project.create_time else None
                }
            ))
        
        return discovered
    
    def _list_projects_in_folder(self, client, folder_id: str) -> List[DiscoveredAccount]:
        """List all projects in a specific folder (including nested folders)."""
        # Normalize folder ID
        if not folder_id.startswith("folders/"):
            folder_id = f"folders/{folder_id}"
        
        discovered = self._list_all_projects(client, folder_id)
        
        # Also list nested folders
        try:
            folder_client = resourcemanager_v3.FoldersClient(
                credentials=self._get_credentials()
            )
            request = resourcemanager_v3.ListFoldersRequest(parent=folder_id)
            
            for child_folder in folder_client.list_folders(request=request):
                child_projects = self._list_projects_in_folder(
                    client, child_folder.name
                )
                # Update metadata with folder path
                for proj in child_projects:
                    proj.metadata["folder_path"] = f"{folder_id}/{child_folder.name}"
                discovered.extend(child_projects)
                
        except Exception as e:
            logger.warning(f"Failed to list nested folders in {folder_id}: {e}")
        
        return discovered
    
    def _search_all_projects(self, client) -> List[DiscoveredAccount]:
        """Search all projects accessible to the credential."""
        discovered = []
        
        request = resourcemanager_v3.SearchProjectsRequest()
        
        for project in client.search_projects(request=request):
            if project.state != resourcemanager_v3.Project.State.ACTIVE:
                continue
            
            discovered.append(DiscoveredAccount(
                account_id=project.project_id,
                name=project.display_name or project.project_id,
                metadata={
                    "project_number": project.name.split("/")[-1],
                    "parent": project.parent,
                    "labels": dict(project.labels) if project.labels else {}
                }
            ))
        
        return discovered
    
    def _default_role(self) -> str:
        """Default SA pattern for GCP impersonation."""
        return "coalmine@{project_id}.iam.gserviceaccount.com"
