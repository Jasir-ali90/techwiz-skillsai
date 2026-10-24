"""Generates:
1. Individual high-definition video clips for all 14 screens/features into:
   SkillSprint_Submission/3. Project Demonstration Video/Clips/
2. A comprehensive, beautifully paced Master Demonstration Video:
   SkillSprint_Submission/3. Project Demonstration Video/SkillSprint_AI_Master_Demo.mp4
"""
import time
import shutil
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

HTML_PATH = Path("docs/app_showcase.html").resolve()
CLIPS_DIR = Path("SkillSprint_Submission/3. Project Demonstration Video/Clips")
VIDEO_DIR = Path("SkillSprint_Submission/3. Project Demonstration Video")
TEMP_DIR = Path("scratch/clips_temp")

for d in [CLIPS_DIR, VIDEO_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CHROME_PATH = r"C:\Users\Com Plus\AppData\Local\ms-playwright\chromium-1243\chrome-win64\chrome.exe"
FILE_URL = f"file:///{str(HTML_PATH).replace('\\', '/')}"

CLIPS_SPEC = [
    ("overview", "01_Overview_and_Health_Telemetry", "Overview Dashboard & Health Telemetry"),
    ("generator", "02_Pipeline1_GenAI_Plan_Generator", "Pipeline 1 GenAI Plan Generator"),
    ("plan_detail", "03_Staged_Onboarding_Modules_Day1_to_90", "Staged Modules Day 1 to 90"),
    ("validation", "04_Pipeline2_Deterministic_Python_Validation", "Pipeline 2 Deterministic Rule Engine"),
    ("comparison", "05_120_Requirement_Comparison_Matrix", "120-Requirement Comparison Matrix"),
    ("review_queue", "06_Human_Review_Queue_and_Overrides", "Human Review Queue & Overrides"),
    ("documents", "07_Document_Ingestion_and_9Pt_Validation", "Document Ingestion & 9-Pt Validation"),
    ("matrix", "08_Role_Requirement_Matrix_Builder", "Role Requirement Matrix 4-Step Builder"),
    ("policy_updates", "09_Policy_Diff_and_Selective_Regen", "Policy Diff & Selective Regeneration"),
    ("employee_journey", "10_Employee_Learning_Journey_Portal", "Employee Learning Journey Portal"),
    ("quiz_demo", "11_Interactive_Scenario_Quiz_Grading", "Source-Grounded Scenario Quiz"),
    ("reports", "12_Reports_and_Multi_Export", "Reports & Multi-Format Export"),
    ("security", "13_Security_and_Prompt_Injection_Defense", "Security & Prompt Injection Defense"),
    ("ai_providers", "14_AI_Providers_and_Fallback_Chain", "Multi-Provider Fallback Resilience"),
]

def record_clip(nav_id, clip_name, label):
    print(f"Recording clip: {label}...")
    clip_temp = TEMP_DIR / clip_name
    clip_temp.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir=str(clip_temp),
            record_video_size={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        page.goto(FILE_URL)
        page.wait_for_timeout(800)
        
        # Switch to tab
        page.evaluate(f"showPage('{nav_id}', document.querySelector('button[onclick*=\"{nav_id}\"]'))")
        page.wait_for_timeout(1000)
        
        # Interactive actions per tab
        if nav_id == "overview":
            page.mouse.move(500, 300)
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollBy({ top: 350, behavior: 'smooth' })")
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollBy({ top: -350, behavior: 'smooth' })")
            page.wait_for_timeout(1500)

        elif nav_id == "generator":
            page.mouse.move(400, 250)
            page.wait_for_timeout(1500)
            page.mouse.move(700, 250)
            page.wait_for_timeout(1500)
            page.click("button:has-text('Generate Plan Now')")
            page.wait_for_timeout(2500)

        elif nav_id == "plan_detail":
            page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
            page.wait_for_timeout(2500)
            page.evaluate("window.scrollBy({ top: -250, behavior: 'smooth' })")
            page.wait_for_timeout(1500)

        elif nav_id == "validation":
            page.mouse.move(300, 200)
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
            page.wait_for_timeout(2500)
            page.evaluate("window.scrollBy({ top: -300, behavior: 'smooth' })")
            page.wait_for_timeout(1000)

        elif nav_id == "comparison":
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollBy({ top: -500, behavior: 'smooth' })")
            page.wait_for_timeout(1000)

        elif nav_id == "review_queue":
            page.mouse.move(400, 450)
            page.wait_for_timeout(1500)
            page.click("button:has-text('Approve Override')")
            page.wait_for_timeout(2500)

        elif nav_id == "documents":
            page.click("button:has-text('Select Document')")
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
            page.wait_for_timeout(2500)

        elif nav_id == "matrix":
            page.click("button:has-text('Rebuild Matrix')")
            page.wait_for_timeout(3000)

        elif nav_id == "policy_updates":
            page.mouse.move(500, 350)
            page.wait_for_timeout(1500)
            page.click("button:has-text('Apply Selective Regeneration')")
            page.wait_for_timeout(2500)

        elif nav_id == "employee_journey":
            page.click("input[type='checkbox']:not(:checked)")
            page.wait_for_timeout(2500)

        elif nav_id == "quiz_demo":
            page.wait_for_timeout(1500)
            page.mouse.move(600, 380)
            page.wait_for_timeout(2500)

        elif nav_id == "reports":
            page.mouse.move(400, 300)
            page.wait_for_timeout(1500)
            page.mouse.move(700, 300)
            page.wait_for_timeout(2000)

        elif nav_id == "security":
            page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
            page.wait_for_timeout(3000)

        elif nav_id == "ai_providers":
            page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
            page.wait_for_timeout(3000)

        page.wait_for_timeout(1000)
        page.close()
        context.close()
        browser.close()

    # Locate recorded video
    v_files = list(clip_temp.glob("*.webm"))
    if v_files:
        src_webm = v_files[0]
        dst_webm = CLIPS_DIR / f"{clip_name}.webm"
        dst_mp4 = CLIPS_DIR / f"{clip_name}.mp4"
        shutil.copy2(src_webm, dst_webm)
        
        # Convert to MP4 with ffmpeg
        cmd = [FFMPEG, "-y", "-i", str(dst_webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(dst_mp4)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Saved clip: {dst_mp4.name} & {dst_webm.name}")

def record_all_clips():
    for nav_id, clip_name, label in CLIPS_SPEC:
        record_clip(nav_id, clip_name, label)

def record_master_video():
    print("Recording Comprehensive Master Demonstration Video...")
    master_temp = TEMP_DIR / "master"
    master_temp.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir=str(master_temp),
            record_video_size={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        page.goto(FILE_URL)
        page.wait_for_timeout(1500)

        # Iterate through all 14 screens at a realistic, comfortable demonstration pace
        for nav_id, _, label in CLIPS_SPEC:
            print(f"Master walkthrough: {label}...")
            page.evaluate(f"showPage('{nav_id}', document.querySelector('button[onclick*=\"{nav_id}\"]'))")
            page.wait_for_timeout(2000)

            if nav_id == "overview":
                page.evaluate("window.scrollBy({ top: 350, behavior: 'smooth' })")
                page.wait_for_timeout(2500)
                page.evaluate("window.scrollBy({ top: -350, behavior: 'smooth' })")
                page.wait_for_timeout(1500)

            elif nav_id == "generator":
                page.mouse.move(500, 250)
                page.wait_for_timeout(1500)
                page.click("button:has-text('Generate Plan Now')")
                page.wait_for_timeout(2000)

            elif nav_id == "plan_detail":
                page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
                page.wait_for_timeout(2500)
                page.evaluate("window.scrollBy({ top: -300, behavior: 'smooth' })")
                page.wait_for_timeout(1500)

            elif nav_id == "validation":
                page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
                page.wait_for_timeout(2500)
                page.evaluate("window.scrollBy({ top: -300, behavior: 'smooth' })")
                page.wait_for_timeout(1500)

            elif nav_id == "comparison":
                page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
                page.wait_for_timeout(2500)
                page.evaluate("window.scrollBy({ top: -300, behavior: 'smooth' })")
                page.wait_for_timeout(1500)

            elif nav_id == "review_queue":
                page.click("button:has-text('Approve Override')")
                page.wait_for_timeout(2000)

            elif nav_id == "documents":
                page.click("button:has-text('Select Document')")
                page.wait_for_timeout(1500)
                page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
                page.wait_for_timeout(2000)

            elif nav_id == "matrix":
                page.click("button:has-text('Rebuild Matrix')")
                page.wait_for_timeout(2000)

            elif nav_id == "policy_updates":
                page.click("button:has-text('Apply Selective Regeneration')")
                page.wait_for_timeout(2000)

            elif nav_id == "employee_journey":
                page.click("input[type='checkbox']:not(:checked)")
                page.wait_for_timeout(2000)

            elif nav_id == "quiz_demo":
                page.mouse.move(600, 380)
                page.wait_for_timeout(2000)

            elif nav_id == "reports":
                page.mouse.move(500, 300)
                page.wait_for_timeout(2000)

            elif nav_id == "security":
                page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
                page.wait_for_timeout(2000)

            elif nav_id == "ai_providers":
                page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
                page.wait_for_timeout(2000)

        page.wait_for_timeout(2000)
        page.close()
        context.close()
        browser.close()

    v_files = list(master_temp.glob("*.webm"))
    if v_files:
        src_webm = v_files[0]
        dst_webm = VIDEO_DIR / "SkillSprint_AI_Master_Demo.webm"
        dst_mp4 = VIDEO_DIR / "SkillSprint_AI_Master_Demo.mp4"
        shutil.copy2(src_webm, dst_webm)
        
        cmd = [FFMPEG, "-y", "-i", str(dst_webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(dst_mp4)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Also copy to primary video paths
        shutil.copy2(dst_mp4, VIDEO_DIR / "SkillSprint_AI_Demo_Video.mp4")
        shutil.copy2(dst_webm, VIDEO_DIR / "SkillSprint_AI_Demo_Video.webm")
        print(f"Master video saved successfully: {dst_mp4.name} & {dst_webm.name}")

if __name__ == '__main__':
    print("Starting clip and video generation...")
    record_all_clips()
    record_master_video()
    print("Video clips and master demonstration video finished!")
