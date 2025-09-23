from playwright.sync_api import sync_playwright
 
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://kdfq92.hosted.cherryroad.com/")
 
    # do login manually once, including 2FA
    input("Press Enter after login + 2FA is complete...")
 
    context.storage_state(path="auth.json")
    browser.close()