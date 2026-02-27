import os
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

AZURE_DEVOPS_PAT = os.getenv("AZURE_DEVOPS_PAT", "")
print(AZURE_DEVOPS_PAT)


def get_auth():
    return ("", AZURE_DEVOPS_PAT)


def get_base_url(org: str, project: str):
    return f"https://dev.azure.com/{org}/{project}/_apis"


def get_vssps_url(org: str):
    return f"https://vssps.dev.azure.com/{org}/_apis"


class AssignWorkItemRequest(BaseModel):
    work_item_id: int
    user: str


class UpdateAreaPathRequest(BaseModel):
    work_item_id: int
    area_path: str


@router.get("/get-work-items")
async def get_work_items(org: str = Query(...), project: str = Query(...)):
    url = f"{get_base_url(org, project)}/wit/wiql?api-version=7.0"
    query = {"query": "SELECT [System.Id] FROM WorkItems"}
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=query, auth=get_auth())
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        work_item_refs = response.json().get("workItems", [])
        if not work_item_refs:
            return []
        ids = ",".join(str(item["id"]) for item in work_item_refs[:200])
        fields = "System.Id,System.Title,System.Description,System.AssignedTo,System.State,Microsoft.VSTS.Scheduling.StoryPoints,Microsoft.VSTS.Common.Priority,Microsoft.VSTS.Common.Severity"
        details_url = f"{get_base_url(org, project)}/wit/workitems?ids={ids}&fields={fields}&api-version=7.0"
        details_response = await client.get(details_url, auth=get_auth())
        if details_response.status_code != 200:
            raise HTTPException(
                status_code=details_response.status_code, detail=details_response.text
            )
        work_items = details_response.json().get("value", [])
        result = []
        for item in work_items:
            fields_data = item.get("fields", {})
            assigned_to = fields_data.get("System.AssignedTo", {})
            result.append(
                {
                    "id": item.get("id"),
                    "title": fields_data.get("System.Title"),
                    "description": fields_data.get("System.Description"),
                    "assigned_to": (
                        assigned_to.get("displayName") if assigned_to else None
                    ),
                    "state": fields_data.get("System.State"),
                    "story_points": fields_data.get(
                        "Microsoft.VSTS.Scheduling.StoryPoints"
                    ),
                    "priority": fields_data.get("Microsoft.VSTS.Common.Priority"),
                    "difficulty": fields_data.get("Microsoft.VSTS.Common.Severity"),
                }
            )
        return result


@router.get("/get-work-item/{work_item_id}")
async def get_work_item(
    work_item_id: int, org: str = Query(...), project: str = Query(...)
):
    fields = "System.Id,System.Title,System.Description,System.AssignedTo,System.State,Microsoft.VSTS.Scheduling.StoryPoints,Microsoft.VSTS.Common.Priority,Microsoft.VSTS.Common.Severity"
    url = f"{get_base_url(org, project)}/wit/workitems/{work_item_id}?fields={fields}&api-version=7.0"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, auth=get_auth())
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Work item not found")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        item = response.json()
        fields_data = item.get("fields", {})
        assigned_to = fields_data.get("System.AssignedTo", {})
        return {
            "id": item.get("id"),
            "title": fields_data.get("System.Title"),
            "description": fields_data.get("System.Description"),
            "assigned_to": assigned_to.get("displayName") if assigned_to else None,
            "state": fields_data.get("System.State"),
            "story_points": fields_data.get("Microsoft.VSTS.Scheduling.StoryPoints"),
            "priority": fields_data.get("Microsoft.VSTS.Common.Priority"),
            "difficulty": fields_data.get("Microsoft.VSTS.Common.Severity"),
        }


@router.post("/assign-work-item")
async def assign_work_item(
    request: AssignWorkItemRequest, org: str = Query(...), project: str = Query(...)
):
    url = f"{get_base_url(org, project)}/wit/workitems/{request.work_item_id}?api-version=7.0"
    patch_body = [
        {"op": "add", "path": "/fields/System.AssignedTo", "value": request.user}
    ]
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            url,
            json=patch_body,
            auth=get_auth(),
            headers={"Content-Type": "application/json-patch+json"},
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Work item not found")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()


@router.patch("/update-work-item-area-path")
async def update_area_path(
    request: UpdateAreaPathRequest, org: str = Query(...), project: str = Query(...)
):
    url = f"{get_base_url(org, project)}/wit/workitems/{request.work_item_id}?api-version=7.0"
    patch_body = [
        {"op": "add", "path": "/fields/System.AreaPath", "value": request.area_path}
    ]
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            url,
            json=patch_body,
            auth=get_auth(),
            headers={"Content-Type": "application/json-patch+json"},
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Work item not found")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()


@router.get("/get-users")
async def get_users(org: str = Query(...)):
    url = f"{get_vssps_url(org)}/graph/users?api-version=7.0-preview.1"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, auth=get_auth())
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        users = response.json().get("value", [])
        result = []
        for user in users:
            name = user.get("displayName", "")
            if "Build Service" in name or not name:
                continue
            result.append(
                {
                    "name": name,
                    "email": user.get("mailAddress"),
                }
            )
        return result


@router.get("/get-teams")
async def get_teams(org: str = Query(...), project: str = Query(...)):
    url = f"{get_base_url(org, project)}/teams?api-version=7.0"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, auth=get_auth())
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json().get("value", [])
