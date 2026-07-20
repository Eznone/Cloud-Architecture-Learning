# /// script
# dependencies = [
#     "python-dotenv",
#     "PyGithub",
#     "notion-client",
#     "notion-to-markdown",
# ]
# ///

import os
import shutil
from dotenv import load_dotenv
from github import Github
from notion_client import Client
from notion_to_markdown import MarkdownProvider

# Load variables from .env file
load_dotenv()

def extract_property_value(prop):
    """Helper to extract text from Notion properties safely."""
    if not prop: return "Untitled"
    if prop.get("type") == "title" and prop.get("title"):
        return prop["title"][0]["plain_text"]
    if prop.get("type") == "rich_text" and prop.get("rich_text"):
        return prop["rich_text"][0]["plain_text"]
    if prop.get("type") == "select" and prop.get("select"):
        return prop["select"]["name"]
    return "Untitled"

def publish_journal_entries():
    # Initialize clients
    notion = Client(auth=os.environ["NOTION_TOKEN"])
    n2m = MarkdownProvider(notion)
    github_client = Github(os.environ["GITHUB_TOKEN"])

    db_id = os.environ["NOTION_DATABASE_ID"]
    repo_name = os.environ["GITHUB_REPO"]
    repo = github_client.get_repo(repo_name)
    
    # Create a local staging directory if it doesn't exist
    staging_dir = "staging"
    os.makedirs(staging_dir, exist_ok=True)
    
    print("Querying Notion database for pending uploads...")
    
    response = notion.databases.query(
        database_id=db_id,
        filter={
            "property": "Uploaded to Github",
            "checkbox": {"equals": True}
        }
    )
    
    results = response.get("results", [])
    if not results:
        print("No new entries to upload. Done.")
        return

    for row in results:
        page_id = row["id"]
        props = row["properties"]
        
        name = extract_property_value(props.get("Name"))
        category = extract_property_value(props.get("Category"))
        course = extract_property_value(props.get("Course"))
        chapter = extract_property_value(props.get("Chapter"))
        
        safe_name = name.replace(" ", "-")
        
        print(f"\nProcessing: '{name}'")
        md_content = n2m.get_markdown_string(page_id)
        
        # 1. Save to local staging folder
        local_path = os.path.join(staging_dir, f"{safe_name}.md")
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        # 2. Pause for Review
        print(f"\n[PAUSED] The file has been staged at: {local_path}")
        user_input = input("Open it in IBM Bob to review and edit. Press [Enter] to approve and upload, or type 's' to skip: ")
        
        if user_input.strip().lower() == 's':
            print(" -> Skipping upload for this file.")
            continue
            
        # 3. Read the finalized content back (in case you made edits)
        with open(local_path, "r", encoding="utf-8") as f:
            final_md_content = f.read()
        
        # 4. Construct the dynamic GitHub path and upload
        file_path = f"{category}/{course}/{chapter}/{safe_name}.md"
        commit_msg = f"docs: add study notes for {name}"
        
        print(f" -> Pushing to path: {file_path}")
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, commit_msg, final_md_content, contents.sha)
            print(" -> Status: Existing file updated successfully.")
        except Exception:
            repo.create_file(file_path, commit_msg, final_md_content)
            print(" -> Status: New file created successfully.")
            
        # 5. Uncheck the Notion box
        notion.pages.update(
            page_id=page_id,
            properties={
                "Uploaded to Github": {"checkbox": False}
            }
        )
        print(" -> Notion database updated: Checkbox cleared.")
        
        # Optional: Delete the staged file after successful upload
        os.remove(local_path)

if __name__ == "__main__":
    publish_journal_entries()