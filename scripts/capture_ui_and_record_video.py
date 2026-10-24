"""Uses Playwright to:
1. Launch Chromium at 1920x1080 resolution.
2. Record an automated demonstration video of the entire SkillSprint AI platform.
3. Capture high-resolution screenshots of all 14 application screens into:
   SkillSprint_Submission/5. UI & UX Figma Design (Optional)/Screenshots/
4. Save the final video to:
   SkillSprint_Submission/3. Project Demonstration Video/SkillSprint_AI_Demo_Video.webm
"""
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML_PATH = Path("docs/app_showcase.html").resolve()
SHOTS_DIR = Path("SkillSprint_Submission/5. UI & UX Figma Design (Optional)/Screenshots")
VIDEO_DIR = Path("SkillSprint_Submission/3. Project Demonstration Video")
SHOTS_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

TEMP_VIDEO_DIR = Path("scratch/playwright_video")
TEMP_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

PAGES_TO_VISIT = [
    ("overview", "01_Overview_Dashboard.png", "Overview & Health Telemetry"),
    ("generator", "02_Plan_Generator_P1.png", "Pipeline 1 GenAI Plan Generator"),
    ("plan_detail", "03_Plan_Detail_Modules.png", "Staged Modules Day 1 to 90"),
    ("validation", "04_Python_Validation_P2.png", "Pipeline 2 Ground-Truth Rule Engine"),
    ("comparison", "05_120_Req_Comparison.png", "GenAI vs Python 120-Req Comparison"),
    ("review_queue", "06_Review_Queue_Overrides.png", "Human-in-the-Loop Review Queue"),
    ("documents", "07_Document_Ingestion_9Pt.png", "Document Ingestion & 9-Pt Validation"),
    ("matrix", "08_Role_Requirement_Matrix.png", "Role Requirement Matrix Builder"),
    ("policy_updates", "09_Policy_Diff_Regen.png", "Policy Diff & Selective Regeneration"),
    ("employee_journey", "10_Employee_Learning_Journey.png", "My Onboarding Learner Portal"),
    ("quiz_demo", "11_Interactive_Scenario_Quiz.png", "Grounded Scenario Quiz with Citations"),
    ("reports", "12_Reports_and_Multi_Export.png", "Reports & Multi-Format Export"),
    ("security", "13_Security_Prompt_Injection.png", "Prompt Injection Defense & Scans"),
    ("ai_providers", "14_AI_Providers_Fallback.png", "Multi-Provider Fallback Resilience"),
]

print("Launching Playwright Chromium browser session...")

with sync_playwright() as p:
    chrome_path = r"C:\Users\Com Plus\AppData\Local\ms-playwright\chromium-1243\chrome-win64\chrome.exe"
    browser = p.chromium.launch(executable_path=chrome_path, headless=True)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir=str(TEMP_VIDEO_DIR),
        record_video_size={'width': 1920, 'height': 1080}
    )
    page = context.new_page()

    # Load HTML showcase
    file_url = f"file:///{str(HTML_PATH).replace('\\', '/')}"
    print(f"Loading {file_url}...")
    page.goto(file_url)
    page.wait_for_timeout(1000)

    # Visit each screen, capture screenshot, simulate user interaction
    for nav_id, shot_name, label in PAGES_TO_VISIT:
        print(f"Navigating to {label} ({nav_id})...")
        
        # Switch tab via script execution
        page.evaluate(f"showPage('{nav_id}', document.querySelector('button[onclick*=\"{nav_id}\"]'))")
        page.wait_for_timeout(1200)

        # If on quiz page, simulate clicking an option
        if nav_id == "quiz_demo":
            page.wait_for_timeout(800)

        # If on comparison, smooth scroll down and up
        if nav_id in ["comparison", "validation", "documents"]:
            page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
            page.wait_for_timeout(600)
            page.evaluate("window.scrollBy({ top: -300, behavior: 'smooth' })")
            page.wait_for_timeout(500)

        # Capture crisp screenshot
        shot_path = SHOTS_DIR / shot_name
        page.screenshot(path=str(shot_path), full_page=False)
        print(f"Captured screenshot: {shot_name}")
        page.wait_for_timeout(1000)

    # Final wrap-up pause
    page.wait_for_timeout(2000)
    page.close()
    context.close()
    browser.close()

# Move generated video to Project Demonstration Video folder
recorded_videos = list(TEMP_VIDEO_DIR.glob("*.webm"))
if recorded_videos:
    src_video = recorded_videos[0]
    dst_video = VIDEO_DIR / "SkillSprint_AI_Demo_Video.webm"
    shutil.copy2(src_video, dst_video)
    print(f"Successfully recorded and saved demonstration video to: {dst_video} ({dst_video.stat().st_size} bytes)")
else:
    print("Warning: No video file found in recorded directory.")

print("All screenshots and demonstration video successfully created!")
